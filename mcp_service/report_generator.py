# /vsi-ai-om/mcp_service/report_generator.py
"""
报表生成器

功能：
- 生成领导简报（Markdown/CSV/HTML）
- 统计问题分析
- 趋势可视化数据
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class ReportGenerator:
    """报表生成器"""
    
    def __init__(self, db_path: str = None):
        """
        初始化报表生成器
        
        Args:
            db_path: 数据库路径（默认：problems.db）
        """
        if db_path is None:
            project_root = Path(__file__).parent.parent
            db_path = project_root / "mcp_service" / "problems.db"
        self.db_path = db_path
    
    def generate_executive_report(
        self,
        resource_kind: str,
        start_date: str,
        end_date: str,
        format: str = "markdown"
    ) -> str:
        """
        生成领导简报
        
        Args:
            resource_kind: 资源类型
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            format: 输出格式 (markdown/csv/html)
        
        Returns:
            str: 报表内容
        """
        # 获取统计数据
        stats = self._get_statistics(resource_kind, start_date, end_date)
        
        if format == "markdown":
            return self._generate_markdown_report(stats, resource_kind, start_date, end_date)
        elif format == "csv":
            return self._generate_csv_report(stats)
        elif format == "html":
            return self._generate_html_report(stats, resource_kind, start_date, end_date)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _get_statistics(self, resource_kind: str, start_date: str, end_date: str) -> Dict:
        """获取统计数据"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # 基础统计
        c.execute("""
            SELECT 
                COUNT(DISTINCT p.id) as total_problems,
                COUNT(DISTINCT p.job_id) as affected_jobs,
                COUNT(DISTINCT p.fault_type) as fault_types
            FROM problems p
            WHERE p.resource_kind = ?
            AND p.timestamp >= ?
            AND p.timestamp <= ?
        """, (resource_kind, f"{start_date} 00:00:00", f"{end_date} 23:59:59"))
        
        base_stats = c.fetchone()
        
        # Jira 统计
        c.execute("""
            SELECT 
                COUNT(DISTINCT pj.jira_ticket_id) as jira_count,
                COUNT(DISTINCT j.key) as unique_jiras
            FROM problems p
            LEFT JOIN problem_jira_links pj ON p.id = pj.problem_id
            LEFT JOIN jira_tickets j ON pj.jira_ticket_id = j.id
            WHERE p.resource_kind = ?
            AND p.timestamp >= ?
            AND p.timestamp <= ?
        """, (resource_kind, f"{start_date} 00:00:00", f"{end_date} 23:59:59"))
        
        jira_stats = c.fetchone()
        
        # Slack 统计
        c.execute("""
            SELECT 
                COUNT(DISTINCT ps.slack_thread_id) as slack_count,
                SUM(CASE WHEN ps.is_resolved = 1 THEN 1 ELSE 0 END) as resolved_count
            FROM problems p
            LEFT JOIN problem_slack_links ps ON p.id = ps.problem_id
            WHERE p.resource_kind = ?
            AND p.timestamp >= ?
            AND p.timestamp <= ?
        """, (resource_kind, f"{start_date} 00:00:00", f"{end_date} 23:59:59"))
        
        slack_stats = c.fetchone()
        
        # 故障类型 Top 5
        c.execute("""
            SELECT 
                p.fault_type,
                COUNT(*) as count,
                COUNT(DISTINCT pj.jira_ticket_id) as jira_linked,
                COUNT(DISTINCT ps.slack_thread_id) as slack_linked
            FROM problems p
            LEFT JOIN problem_jira_links pj ON p.id = pj.problem_id
            LEFT JOIN problem_slack_links ps ON p.id = ps.problem_id
            WHERE p.resource_kind = ?
            AND p.timestamp >= ?
            AND p.timestamp <= ?
            GROUP BY p.fault_type
            ORDER BY count DESC
            LIMIT 5
        """, (resource_kind, f"{start_date} 00:00:00", f"{end_date} 23:59:59"))
        
        top_faults = c.fetchall()
        
        # 每日趋势
        c.execute("""
            SELECT 
                DATE(p.timestamp) as date,
                COUNT(*) as count
            FROM problems p
            WHERE p.resource_kind = ?
            AND p.timestamp >= ?
            AND p.timestamp <= ?
            GROUP BY DATE(p.timestamp)
            ORDER BY date
        """, (resource_kind, f"{start_date} 00:00:00", f"{end_date} 23:59:59"))
        
        daily_trend = c.fetchall()
        
        conn.close()
        
        return {
            "total_problems": base_stats["total_problems"],
            "affected_jobs": base_stats["affected_jobs"],
            "fault_types": base_stats["fault_types"],
            "jira_count": jira_stats["jira_count"],
            "unique_jiras": jira_stats["unique_jiras"],
            "slack_count": slack_stats["slack_count"],
            "resolved_count": slack_stats["resolved_count"] or 0,
            "top_faults": [dict(row) for row in top_faults],
            "daily_trend": [dict(row) for row in daily_trend]
        }
    
    def _generate_markdown_report(
        self,
        stats: Dict,
        resource_kind: str,
        start_date: str,
        end_date: str
    ) -> str:
        """生成 Markdown 格式报表"""
        
        # 计算环比（简单版）
        prev_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
        prev_end = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        
        report = f"""# {resource_kind} 问题追踪周报 ({start_date} ~ {end_date})

## 📊 关键指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 问题总数 | **{stats['total_problems']}** | 本周发生的问题数 |
| 影响 Job 数 | **{stats['affected_jobs']}** | 受影响的唯一 Job 数量 |
| Jira Ticket 创建率 | **{self._calc_percentage(stats['jira_count'], stats['total_problems'])}** | 已关联 Jira 的问题比例 |
| Slack 沟通次数 | **{stats['slack_count']}** | Slack 讨论次数 |
| 已解决问题 | **{stats['resolved_count']}** | 通过沟通解决的问题 |

## 🔥 故障类型 Top 5

| 排名 | 故障类型 | 次数 | 占比 | Jira 关联 | Slack 关联 |
|------|----------|------|------|-----------|------------|
"""
        
        for i, fault in enumerate(stats['top_faults'], 1):
            percentage = self._calc_percentage(fault['count'], stats['total_problems'])
            report += f"| {i} | {fault['fault_type']} | {fault['count']} | {percentage}% | {fault['jira_linked']} | {fault['slack_linked']} |\n"
        
        report += f"""
## 📈 每日趋势

| 日期 | 问题数 | 趋势 |
|------|--------|------|
"""
        
        for day in stats['daily_trend']:
            trend_icon = "📈" if day['count'] > stats['total_problems'] / len(stats['daily_trend']) else "📉"
            report += f"| {day['date']} | {day['count']} | {trend_icon} |\n"
        
        report += f"""
## 💡 建议行动

1. **优先处理**: {stats['top_faults'][0]['fault_type'] if stats['top_faults'] else '无'} (占比最高)
2. **Jira 跟进**: {"需要加强" if self._calc_percentage(stats['jira_count'], stats['total_problems']) < 50 else '良好'} (当前创建率 {self._calc_percentage(stats['jira_count'], stats['total_problems'])}%)
3. **沟通效果**: {"显著" if stats['resolved_count'] > stats['slack_count'] * 0.5 else "一般"} (解决率 {self._calc_percentage(stats['resolved_count'], stats['slack_count'])}%)

---

*报告生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}*
*数据来源：MCP 问题追踪系统*
"""
        
        return report
    
    def _generate_csv_report(self, stats: Dict) -> str:
        """生成 CSV 格式报表"""
        csv = "日期，问题数\n"
        for day in stats['daily_trend']:
            csv += f"{day['date']},{day['count']}\n"
        return csv
    
    def _generate_html_report(
        self,
        stats: Dict,
        resource_kind: str,
        start_date: str,
        end_date: str
    ) -> str:
        """生成 HTML 格式报表"""
        # 简单 HTML 模板
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{resource_kind} 问题追踪周报</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        h1 {{ color: #333; }}
        .metric {{ display: inline-block; margin: 10px; padding: 20px; background: #f9f9f9; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>{resource_kind} 问题追踪周报 ({start_date} ~ {end_date})</h1>
    
    <div class="metric">
        <h3>问题总数</h3>
        <p style="font-size: 2em; color: #e74c3c;">{stats['total_problems']}</p>
    </div>
    <div class="metric">
        <h3>Jira 创建率</h3>
        <p style="font-size: 2em; color: #3498db;">{self._calc_percentage(stats['jira_count'], stats['total_problems'])}%</p>
    </div>
    <div class="metric">
        <h3>Slack 沟通</h3>
        <p style="font-size: 2em; color: #2ecc71;">{stats['slack_count']}</p>
    </div>
    
    <h2>故障类型 Top 5</h2>
    <table>
        <tr><th>故障类型</th><th>次数</th><th>占比</th></tr>
"""
        
        for fault in stats['top_faults']:
            percentage = self._calc_percentage(fault['count'], stats['total_problems'])
            html += f"        <tr><td>{fault['fault_type']}</td><td>{fault['count']}</td><td>{percentage}%</td></tr>\n"
        
        html += """    </table>
</body>
</html>"""
        
        return html
    
    def _calc_percentage(self, part: int, total: int) -> float:
        """计算百分比"""
        if total == 0:
            return 0.0
        return round(part / total * 100, 1)


def generate_report(
    resource_kind: str,
    start_date: str,
    end_date: str,
    format: str = "markdown"
) -> str:
    """
    快捷函数：生成报表
    
    Args:
        resource_kind: 资源类型
        start_date: 开始日期
        end_date: 结束日期
        format: 输出格式
    
    Returns:
        str: 报表内容
    """
    generator = ReportGenerator()
    return generator.generate_executive_report(resource_kind, start_date, end_date, format)
