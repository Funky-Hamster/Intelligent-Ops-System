# /vsi-ai-om/mcp_service/smart_match.py
"""
智能匹配助手

功能：
- 基于相似度推荐 Jira Ticket 关联
- 未关联问题检测
- 数据质量分析
"""

import sqlite3
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timedelta


class SmartMatcher:
    """智能匹配助手"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            project_root = Path(__file__).parent.parent
            db_path = project_root / "mcp_service" / "problems.db"
        self.db_path = db_path
    
    def suggest_jira_links(self, problem_id: str) -> List[Dict]:
        """
        基于故障类型和时间，推荐可能相关的 Jira tickets
        
        Args:
            problem_id: 问题 ID
        
        Returns:
            List[Dict]: 推荐的 Jira tickets，按相似度排序
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # 获取问题信息
        c.execute("""
            SELECT fault_type, job_id, resource_kind, timestamp
            FROM problems
            WHERE id = ?
        """, (problem_id,))
        
        problem = c.fetchone()
        if not problem:
            return []
        
        # 查询相同故障类型的 Jira tickets
        c.execute("""
            SELECT DISTINCT
                j.id,
                j.key,
                j.summary,
                j.status,
                j.problem_count,
                CASE
                    WHEN p2.fault_type = ? THEN 50
                    ELSE 0
                END as fault_score,
                CASE
                    WHEN p2.job_id = ? THEN 30
                    ELSE 0
                END as job_score,
                CASE
                    WHEN p2.resource_kind = ? THEN 20
                    ELSE 0
                END as resource_score
            FROM jira_tickets j
            JOIN problem_jira_links pj ON j.id = pj.jira_ticket_id
            JOIN problems p2 ON pj.problem_id = p2.id
            WHERE j.status != 'Closed'
            ORDER BY fault_score + job_score + resource_score DESC
            LIMIT 5
        """, (problem['fault_type'], problem['job_id'], problem['resource_kind']))
        
        suggestions = []
        for row in c.fetchall():
            similarity = row['fault_score'] + row['job_score'] + row['resource_score']
            
            # 计算相似度原因
            reasons = []
            if row['fault_score'] > 0:
                reasons.append("同类型故障")
            if row['job_score'] > 0:
                reasons.append("同一 Job")
            if row['resource_score'] > 0:
                reasons.append("同资源类型")
            
            suggestions.append({
                "jira_key": row['key'],
                "similarity": similarity,
                "reasons": reasons,
                "status": row['status'],
                "problem_count": row['problem_count']
            })
        
        conn.close()
        return suggestions
    
    def detect_unlinked_problems(
        self,
        resource_kind: str = None,
        days: int = 7
    ) -> List[Dict]:
        """
        检测未关联任何 Jira/Slack 的问题
        
        Args:
            resource_kind: 资源类型（可选）
            days: 最近 N 天
        
        Returns:
            List[Dict]: 未关联的问题列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        
        query = """
            SELECT 
                p.id,
                p.fault_type,
                p.job_id,
                p.timestamp,
                p.resource_kind
            FROM problems p
            LEFT JOIN problem_jira_links pj ON p.id = pj.problem_id
            LEFT JOIN problem_slack_links ps ON p.id = ps.problem_id
            WHERE p.timestamp >= ?
            AND pj.jira_ticket_id IS NULL
            AND ps.slack_thread_id IS NULL
        """
        
        params = [start_date]
        
        if resource_kind:
            query += " AND p.resource_kind = ?"
            params.append(resource_kind)
        
        query += " ORDER BY p.timestamp DESC"
        
        c.execute(query, params)
        unlinked = c.fetchall()
        
        conn.close()
        
        return [dict(row) for row in unlinked]
    
    def detect_data_anomalies(self, days: int = 7) -> Dict:
        """
        检测数据异常
        
        Args:
            days: 最近 N 天
        
        Returns:
            Dict: 异常检测结果
        """
        anomalies = {
            "unlinked_problems": [],
            "stale_jiras": [],
            "low_jira_rate": False,
            "summary": ""
        }
        
        # 1. 检测未关联的问题
        unlinked = self.detect_unlinked_problems(days=days)
        if len(unlinked) > 0:
            anomalies["unlinked_problems"] = unlinked[:10]  # 最多显示 10 个
        
        # 2. 检测长期未更新的 Jira
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        stale_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        
        c.execute("""
            SELECT key, summary, status, created_at
            FROM jira_tickets
            WHERE updated_at < ? OR updated_at IS NULL
            AND status != 'Closed'
        """, (stale_date,))
        
        stale_jiras = c.fetchall()
        if stale_jiras:
            anomalies["stale_jiras"] = [dict(row) for row in stale_jiras[:5]]
        
        # 3. 计算 Jira 创建率
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        
        c.execute("""
            SELECT 
                COUNT(DISTINCT p.id) as total,
                COUNT(DISTINCT pj.jira_ticket_id) as linked
            FROM problems p
            LEFT JOIN problem_jira_links pj ON p.id = pj.problem_id
            WHERE p.timestamp >= ?
        """, (start_date,))
        
        stats = c.fetchone()
        if stats['total'] > 0:
            jira_rate = stats['linked'] / stats['total'] * 100
            if jira_rate < 50:
                anomalies["low_jira_rate"] = True
        
        conn.close()
        
        # 生成摘要
        anomaly_count = (
            (1 if anomalies["unlinked_problems"] else 0) +
            (1 if anomalies["stale_jiras"] else 0) +
            (1 if anomalies["low_jira_rate"] else 0)
        )
        
        if anomaly_count == 0:
            anomalies["summary"] = "✅ 数据质量良好，未发现异常"
        else:
            anomalies["summary"] = f"⚠️ 发现 {anomaly_count} 项异常需要关注"
        
        return anomalies


def suggest_jira_links(problem_id: str) -> List[Dict]:
    """快捷函数：推荐 Jira 关联"""
    matcher = SmartMatcher()
    return matcher.suggest_jira_links(problem_id)


def detect_unlinked_problems(resource_kind: str = None, days: int = 7) -> List[Dict]:
    """快捷函数：检测未关联问题"""
    matcher = SmartMatcher()
    return matcher.detect_unlinked_problems(resource_kind, days)


def detect_data_anomalies(days: int = 7) -> Dict:
    """快捷函数：检测数据异常"""
    matcher = SmartMatcher()
    return matcher.detect_data_anomalies(days)
