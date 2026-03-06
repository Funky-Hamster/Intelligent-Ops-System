# /vsi-ai-om/mcp_service/mcp_server.py
import datetime
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP
import sqlite3
import uuid
import time
from typing import List, Dict, Optional
from pydantic import BaseModel
import os
import logging

# 导入公共模块
from mcp_service.schemas import (
    TimeRange, SummaryStats, FaultBreakdown,
    TimelineEntry, EvidenceItem, ArgumentAmmo,
    JiraTicket, SlackThread, ProblemLink
)
from mcp_service.utils import validate_input, validate_resource_kind
from mcp_service.services.problem_service import build_ammo_package

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ========== Pydantic Schema 定义 ==========
# 已从 schemas.py 导入，无需在此定义

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "mcp_service", "problems.db")
# 确保数据库目录存在
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# 初始化数据库
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS problems
             (id TEXT PRIMARY KEY, 
              fault_type TEXT, 
              job_name TEXT NOT NULL,
              job_id TEXT,
              timestamp TEXT,
              evidence TEXT,
              resource_kind TEXT)''')
conn.commit()
conn.close()

mcp = FastMCP("VSI DevOps MCP Service")

# ========== 健康检查 ==========

@mcp.tool()
def health_check() -> Dict:
    """健康检查（MCP 标准工具）"""
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "database": "connected"
    }

@mcp.tool()
def log_problem(fault_type: str, 
                job_id: str, 
                job_name: str,
                evidence: str,
                resource_kind: str = "Unknown") -> str:
    """记录无法解决的故障（MCP 标准工具）"""
    logger.info(f"📝 Logging problem: {fault_type} for job={job_name}, id={job_id}")
    
    # 完整的安全验证
    if not validate_input(fault_type, 100):
        raise ValueError("Invalid fault_type: must be alphanumeric with underscores/hyphens, max 100 chars")
    if not validate_input(job_id, 100):
        raise ValueError("Invalid job_id: must be alphanumeric with underscores/hyphens, max 100 chars")
    if not validate_input(job_name, 150):
        raise ValueError("Invalid job_name: must be alphanumeric with underscores/hyphens, max 150 chars")
    if not validate_input(evidence, 5000):
        raise ValueError("Invalid evidence: exceeds max length of 5000 chars")
    if not validate_resource_kind(resource_kind):
        raise ValueError(f"Invalid resource_kind: must be one of {', '.join(['Jenkins', 'Artifactory', 'DRP', 'SRO', 'LabOps', 'GitHub', 'IT', 'Unknown'])}")
    
    # 生成唯一 ID
    problem_id = f"prob-{uuid.uuid4().hex[:8]}"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # 使用参数化查询防止 SQL 注入
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO problems VALUES (?, ?, ?, ?, ?, ?, ?)",
              (problem_id, fault_type, job_name, job_id, timestamp, evidence, resource_kind))
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Problem logged: {problem_id}")
    return f"Problem logged: {problem_id}"

@mcp.tool()
def search_problems(fault_type: str = None, 
                   start_time: str = None, 
                   end_time: str = None) -> List[Dict]:
    """按类型/时间范围查询历史问题（MCP 标准工具）"""
    query = "SELECT * FROM problems WHERE 1=1"
    params = []
    
    if fault_type:
        query += " AND fault_type = ?"
        params.append(fault_type)
    
    if start_time:
        query += " AND timestamp >= ?"
        params.append(start_time)
    
    if end_time:
        query += " AND timestamp <= ?"
        params.append(end_time)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, params)
    results = c.fetchall()
    conn.close()
    
    # 格式化为标准返回
    return [
        {
            "id": r[0],
            "fault_type": r[1],
            "job_name": r[2],
            "job_id": r[3],
            "timestamp": r[4],
            "evidence": r[5],
            "resource_kind": r[6]
        } for r in results
    ]


# ========== MCP 工具：吵架助手 ==========

@mcp.tool()
def get_argument_ammo(
    resource_kind: str,           # 必填：找谁
    fault_type: str = None,       # 可选：什么问题
    days: int = 3,                # 默认：3 天
    start_time: str = None,       # 可选：自定义开始
    end_time: str = None          # 可选：自定义结束
) -> ArgumentAmmo:
    """
    获取吵架弹药包 - 数据 + 证据
    
    Args:
        resource_kind: 资源类型（Jenkins/Artifactory/DRP/SRO/LabOps/GitHub/IT/Unknown）
        fault_type: 故障类型（可选）
        days: 查询最近 N 天（默认 3，仅在未指定时间范围时生效）
        start_time: 开始时间（可选，格式：YYYY-MM-DD HH:MM:SS）
        end_time: 结束时间（可选，格式：YYYY-MM-DD HH:MM:SS）
    
    Returns:
        ArgumentAmmo: 包含统计数据、时间线、关键证据的完整弹药包
    
    使用示例:
        - get_argument_ammo("Jenkins")                    # 默认 3 天
        - get_argument_ammo("Jenkins", days=7)           # 7 天
        - get_argument_ammo("Jenkins", "build failed")   # 特定故障
        - get_argument_ammo("Jenkins", start_time="2026-03-01", end_time="2026-03-06")  # 自定义范围
    """
    logger.info(f"📊 Getting argument ammo for {resource_kind}")
    
    # 1. 验证 resource_kind
    if not validate_resource_kind(resource_kind):
        raise ValueError(f"Invalid resource_kind: must be one of Jenkins, Artifactory, DRP, SRO, LabOps, GitHub, IT, Unknown")
    
    # 2. 计算时间范围
    if not start_time:
        start_time = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    if not end_time:
        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 3. 查询问题
    problems = search_problems(
        fault_type=fault_type,
        start_time=start_time,
        end_time=end_time
    )
    
    # 4. 按 resource_kind 过滤
    filtered_problems = [p for p in problems if p["resource_kind"] == resource_kind]
    
    # 5. 构建弹药包
    ammo = build_ammo_package(filtered_problems, resource_kind, days)
    
    logger.info(f"✅ Ammo package generated: {ammo.summary}")
    return ammo

@mcp.resource("problem://{problem_id}")
def get_problem(problem_id: str) -> str:
    """获取单个问题的详细信息"""
    import json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM problems WHERE id = ?", (problem_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return json.dumps({
            "id": result[0],
            "fault_type": result[1],
            "job_name": result[2],
            "job_id": result[3],
            "timestamp": result[4],
            "evidence": result[5],
            "resource_kind": result[6]
        }, ensure_ascii=False)
    return "Problem not found"

@mcp.tool()
def escalate_problem(fault_type: str, days: int = 7) -> str:
    """生成结构化沟通文案（解决 TechOps 推诿）"""
    # 1. 查询历史问题（近 days 天内）
    problems = search_problems(
        fault_type=fault_type,
        start_time=(datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    )

    # 2. 计算统计 & 生成文案
    count = len(problems)
    if count == 0:
        return f"⚠️ 问题类型 '{fault_type}' 近 {days} 天未发生。"

    # 生成时间线（格式：日期 | Job ID | 证据摘要）
    timeline = "\n".join([
        f"- {p['timestamp'][:10]} | {p['job_id']} | {p['evidence'][:80]}..."
        for p in problems
    ])

    return (
        f"【问题重复性报告】{fault_type}\n"
        f"• 近 {days} 天已发生 {count} 次\n"
        f"• 时间分布：{', '.join([p['timestamp'][:10] for p in problems])}\n"
        f"• 关键证据:\n{timeline}\n\n"
        f"💡 建议立即优先处理，避免重复影响构建稳定性。"
    )


# ========== 问题追踪系统工具 ==========

@mcp.tool()
def add_jira_ticket(
    key: str,
    summary: str,
    status: str = "Open",
    reporter: str = None,
    assignee: str = None,
    priority: str = "Medium",
    url: str = None,
    notes: str = None
) -> str:
    """
    添加 Jira Ticket 到数据库
    
    Args:
        key: Jira Key (必填，如 "PROJ-456")
        summary: 摘要 (必填)
        status: 状态 (默认 Open)
        reporter: 报告人
        assignee: 负责人
        priority: 优先级
        url: Jira URL
        notes: 备注说明
    
    Returns:
        str: Jira Ticket ID
    """
    logger.info(f"📋 Adding Jira ticket: {key}")
    
    # 验证输入
    if not validate_input(key, 50):
        raise ValueError("Invalid Jira key")
    if not validate_input(summary, 500):
        raise ValueError("Invalid summary")
    
    ticket_id = key  # 使用 Jira Key 作为 ID
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO jira_tickets 
        (id, key, summary, status, created_at, reporter, assignee, priority, url, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticket_id, key, summary, status, created_at, reporter, assignee, priority, url, notes))
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Jira ticket added: {ticket_id}")
    return f"Jira ticket added: {ticket_id}"


@mcp.tool()
def link_problem_to_jira(
    problem_id: str,
    jira_key: str,
    note: str = None
) -> str:
    """
    关联问题到 Jira Ticket
    
    Args:
        problem_id: 问题 ID
        jira_key: Jira Key
        note: 关联说明
    
    Returns:
        str: 成功消息
    """
    logger.info(f"🔗 Linking problem {problem_id} to Jira {jira_key}")
    
    linked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO problem_jira_links (problem_id, jira_ticket_id, linked_at, linked_by, note)
            VALUES (?, ?, ?, 'manual', ?)
        """, (problem_id, jira_key, linked_at, note))
        conn.commit()
        logger.info(f"✅ Problem linked to Jira: {problem_id} -> {jira_key}")
        return f"Problem {problem_id} linked to Jira {jira_key}"
    except sqlite3.IntegrityError as e:
        logger.error(f"Link already exists: {str(e)}")
        return f"Error: Link already exists"
    finally:
        conn.close()


@mcp.tool()
def link_problem_to_slack(
    problem_id: str,
    slack_url: str,
    channel: str,
    summary: str = None,
    is_resolved: bool = False
) -> str:
    """
    关联问题到 Slack Thread
    
    Args:
        problem_id: 问题 ID
        slack_url: Slack 消息 URL
        channel: Slack channel
        summary: 讨论摘要
        is_resolved: 是否已解决
    
    Returns:
        str: 成功消息
    """
    logger.info(f"💬 Linking problem {problem_id} to Slack thread")
    
    thread_id = f"slack-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linked_at = created_at
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # 1. 添加 Slack thread
        c.execute("""
            INSERT INTO slack_threads 
            (id, channel, message_url, summary, created_at, is_resolved)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (thread_id, channel, slack_url, summary, created_at, is_resolved))
        
        # 2. 创建关联
        c.execute("""
            INSERT INTO problem_slack_links (problem_id, slack_thread_id, linked_at, summary, is_resolved)
            VALUES (?, ?, ?, ?, ?)
        """, (problem_id, thread_id, linked_at, summary, is_resolved))
        
        conn.commit()
        logger.info(f"✅ Problem linked to Slack: {problem_id} -> {thread_id}")
        return f"Problem {problem_id} linked to Slack thread {thread_id}"
    except Exception as e:
        logger.error(f"Failed to link: {str(e)}")
        raise
    finally:
        conn.close()


# ========== 报表生成工具 ==========

@mcp.tool()
def generate_executive_report(
    resource_kind: str,
    start_date: str,
    end_date: str,
    format: str = "markdown"
) -> str:
    """
    生成领导简报
    
    Args:
        resource_kind: 资源类型 (Jenkins/Artifactory/DRP/SRO/LabOps/GitHub/IT/Unknown)
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        format: 输出格式 (markdown/csv/html)
    
    Returns:
        str: 报表内容
    
    使用示例:
        - generate_executive_report("Jenkins", "2026-03-01", "2026-03-07")
        - generate_executive_report("Jenkins", "2026-03-01", "2026-03-07", "csv")
        - generate_executive_report("Jenkins", "2026-03-01", "2026-03-07", "html")
    """
    logger.info(f"📊 Generating executive report for {resource_kind}")
    
    if not validate_resource_kind(resource_kind):
        raise ValueError(f"Invalid resource_kind: must be one of Jenkins, Artifactory, DRP, SRO, LabOps, GitHub, IT, Unknown")
    
    from mcp_service.report_generator import ReportGenerator
    
    generator = ReportGenerator()
    report = generator.generate_executive_report(resource_kind, start_date, end_date, format)
    
    logger.info(f"✅ Executive report generated for {resource_kind}")
    return report


# ========== 智能辅助工具 ==========

@mcp.tool()
def suggest_jira_links(problem_id: str) -> List[Dict]:
    """
    基于故障类型和时间，推荐可能相关的 Jira tickets
    
    Args:
        problem_id: 问题 ID
    
    Returns:
        List[Dict]: 推荐的 Jira tickets
        [
          {"jira_key": "PROJ-456", "similarity": 80, "reasons": ["同类型故障", "同一 Job"]},
          ...
        ]
    """
    logger.info(f"🔍 Suggesting Jira links for {problem_id}")
    
    from mcp_service.smart_match import SmartMatcher
    
    matcher = SmartMatcher()
    suggestions = matcher.suggest_jira_links(problem_id)
    
    if suggestions:
        logger.info(f"✅ Found {len(suggestions)} suggestions")
    else:
        logger.info("ℹ️ No suggestions found")
    
    return suggestions


@mcp.tool()
def detect_data_anomalies(days: int = 7) -> Dict:
    """
    检测数据异常
    
    Args:
        days: 最近 N 天（默认 7）
    
    Returns:
        Dict: 异常检测结果
        {
          "summary": "⚠️ 发现 2 项异常需要关注",
          "unlinked_problems": [...],
          "stale_jiras": [...],
          "low_jira_rate": true
        }
    """
    logger.info(f"🔍 Detecting data anomalies for past {days} days")
    
    from mcp_service.smart_match import SmartMatcher
    
    matcher = SmartMatcher()
    anomalies = matcher.detect_data_anomalies(days)
    
    logger.info(anomalies["summary"])
    return anomalies


# ========== 批量操作工具 ==========

@mcp.tool()
def batch_link_problems_to_jira(
    fault_type: str,
    jira_key: str,
    days: int = 7,
    resource_kind: str = None,
    note: str = None
) -> Dict:
    """
    批量关联问题到 Jira Ticket
    
    Args:
        fault_type: 故障类型（支持模糊匹配）
        jira_key: Jira Key
        days: 最近 N 天（默认 7）
        resource_kind: 资源类型（可选，用于过滤）
        note: 关联说明
    
    Returns:
        Dict: 关联结果统计
        {
          "total_found": 5,
          "linked_count": 5,
          "failed_ids": [],
          "problem_ids": ["prob-123", "prob-456"]
        }
    
    使用示例:
        - batch_link_problems_to_jira("Disk Full", "PROJ-456")
        - batch_link_problems_to_jira("disk", "PROJ-456", days=14, resource_kind="Jenkins")
    """
    logger.info(f"🔄 Batch linking problems to Jira {jira_key}")
    
    from datetime import timedelta
    
    # 计算时间范围
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    
    # 查询符合条件的问题
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = """
        SELECT id, fault_type, job_id, timestamp
        FROM problems
        WHERE LOWER(fault_type) LIKE LOWER(?)
        AND timestamp >= ?
    """
    params = [f"%{fault_type}%", start_date]
    
    if resource_kind:
        query += " AND resource_kind = ?"
        params.append(resource_kind)
    
    c.execute(query, params)
    problems = c.fetchall()
    conn.close()
    
    if not problems:
        return {
            "total_found": 0,
            "linked_count": 0,
            "failed_ids": [],
            "problem_ids": [],
            "message": f"未找到符合条件的問題"
        }
    
    # 批量关联
    linked_count = 0
    failed_ids = []
    problem_ids = []
    linked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    for problem in problems:
        problem_id = problem['id']
        problem_ids.append(problem_id)
        
        try:
            c.execute("""
                INSERT INTO problem_jira_links (problem_id, jira_ticket_id, linked_at, linked_by, note)
                VALUES (?, ?, ?, 'batch', ?)
            """, (problem_id, jira_key, linked_at, note))
            linked_count += 1
            logger.info(f"✅ Linked {problem_id} to {jira_key}")
        except sqlite3.IntegrityError:
            failed_ids.append(problem_id)
            logger.warning(f"⚠️ Link already exists for {problem_id}")
    
    conn.commit()
    conn.close()
    
    result = {
        "total_found": len(problems),
        "linked_count": linked_count,
        "failed_ids": failed_ids,
        "problem_ids": problem_ids,
        "message": f"成功关联 {linked_count}/{len(problems)} 个问题到 Jira {jira_key}"
    }
    
    logger.info(f"✅ Batch link completed: {result['message']}")
    return result

if __name__ == "__main__":
    print("🚀 MCP Service starting at http://localhost:8000")
    mcp.run()