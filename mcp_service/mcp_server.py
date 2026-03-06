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
import re
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 输入验证函数
def validate_input(value: str, max_length: int = 200) -> bool:
    """
    验证输入安全性
    
    Args:
        value: 待验证的字符串
        max_length: 最大长度限制
        
    Returns:
        bool: 是否通过验证
    """
    if not value or not isinstance(value, str) or len(value) > max_length:
        return False
    # 只允许字母、数字、下划线、连字符、空格、中文
    if not re.match(r'^[a-zA-Z0-9_\-\u4e00-\u9fa5\s]+$', value):
        return False
    return True


def validate_resource_kind(resource_kind: str) -> bool:
    """
    验证资源类型是否合法
    
    Args:
        resource_kind: 资源类型
        
    Returns:
        bool: 是否合法
    """
    allowed_kinds = {"Jenkins", "Artifactory", "DRP", "SRO", "LabOps", "GitHub", "IT", "Unknown"}
    return resource_kind in allowed_kinds


# ========== Pydantic Schema 定义 ==========

class TimeRange(BaseModel):
    """时间范围"""
    start: str
    end: str
    days: int


class SummaryStats(BaseModel):
    """统计摘要"""
    total_problems: int
    unique_fault_types: int
    affected_jobs: int
    first_occurrence: str
    last_occurrence: str


class FaultBreakdown(BaseModel):
    """故障类型分解"""
    type: str
    count: int
    percentage: float


class TimelineEntry(BaseModel):
    """时间线条目"""
    date: str
    count: int


class EvidenceItem(BaseModel):
    """证据项"""
    timestamp: str
    job_id: str
    job_name: str
    fault_type: str
    evidence: str


class ArgumentAmmo(BaseModel):
    """吵架弹药包 - 标准 Schema"""
    resource_kind: str
    time_range: TimeRange
    summary: str
    statistics: SummaryStats
    fault_breakdown: List[FaultBreakdown]
    timeline: List[TimelineEntry]
    key_evidence: List[EvidenceItem]

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


# ========== 辅助函数 ==========

def build_ammo_package(problems: List[Dict], resource_kind: str, days: int) -> ArgumentAmmo:
    """
    构建弹药包
    
    Args:
        problems: 问题列表
        resource_kind: 资源类型
        days: 天数
        
    Returns:
        ArgumentAmmo: 标准弹药包
    """
    if not problems:
        # 无数据时的处理
        return ArgumentAmmo(
            resource_kind=resource_kind,
            time_range=TimeRange(
                start=(datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"),
                end=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                days=days
            ),
            summary=f"{resource_kind} 过去 {days} 天未发现问题",
            statistics=SummaryStats(
                total_problems=0,
                unique_fault_types=0,
                affected_jobs=0,
                first_occurrence="N/A",
                last_occurrence="N/A"
            ),
            fault_breakdown=[],
            timeline=[],
            key_evidence=[]
        )
    
    # 1. 时间范围
    timestamps = [p["timestamp"] for p in problems]
    start_time = min(timestamps)
    end_time = max(timestamps)
    
    # 2. 基础统计
    total = len(problems)
    unique_fault_types = len(set(p["fault_type"] for p in problems))
    affected_jobs = len(set(p["job_id"] for p in problems))
    
    # 3. 故障类型分解
    fault_counts = {}
    for p in problems:
        ft = p["fault_type"]
        fault_counts[ft] = fault_counts.get(ft, 0) + 1
    
    fault_breakdown = [
        FaultBreakdown(
            type=ft,
            count=count,
            percentage=round(count / total * 100, 1)
        )
        for ft, count in sorted(fault_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    
    # 4. 时间线（按日期分组）
    date_counts = {}
    for p in problems:
        date = p["timestamp"].split()[0]
        date_counts[date] = date_counts.get(date, 0) + 1
    
    timeline = [
        TimelineEntry(date=date, count=count)
        for date, count in sorted(date_counts.items())
    ]
    
    # 5. 关键证据（选择最近的 5 条）
    sorted_problems = sorted(problems, key=lambda x: x["timestamp"], reverse=True)
    key_evidence = [
        EvidenceItem(
            timestamp=p["timestamp"],
            job_id=p["job_id"],
            job_name=p["job_name"],
            fault_type=p["fault_type"],
            evidence=p["evidence"][:200] + "..." if len(p["evidence"]) > 200 else p["evidence"]
        )
        for p in sorted_problems[:5]
    ]
    
    # 6. 生成摘要
    summary = f"{resource_kind} 过去 {days} 天共发生 {total} 起故障，影响 {affected_jobs} 个 Job，涉及 {unique_fault_types} 种故障类型"
    
    return ArgumentAmmo(
        resource_kind=resource_kind,
        time_range=TimeRange(start=start_time, end=end_time, days=days),
        summary=summary,
        statistics=SummaryStats(
            total_problems=total,
            unique_fault_types=unique_fault_types,
            affected_jobs=affected_jobs,
            first_occurrence=start_time,
            last_occurrence=end_time
        ),
        fault_breakdown=fault_breakdown,
        timeline=timeline,
        key_evidence=key_evidence
    )


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
    """生成结构化沟通文案（解决TechOps推诿）"""
    # 1. 查询历史问题（近days天内）
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
        f"• 时间分布: {', '.join([p['timestamp'][:10] for p in problems])}\n"
        f"• 关键证据:\n{timeline}\n\n"
        f"💡 建议立即优先处理，避免重复影响构建稳定性。"
    )

if __name__ == "__main__":
    print("🚀 MCP Service starting at http://localhost:8000")
    mcp.run()