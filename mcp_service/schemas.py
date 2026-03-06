# /vsi-ai-om/mcp_service/schemas.py
"""
Pydantic Schema 定义

包含所有 MCP 工具使用的数据模型
"""

from pydantic import BaseModel
from typing import List, Optional


# ========== 基础 Schema ==========

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


# ========== 吵架助手 Schema ==========

class ArgumentAmmo(BaseModel):
    """吵架弹药包 - 标准 Schema"""
    resource_kind: str
    time_range: TimeRange
    summary: str
    statistics: SummaryStats
    fault_breakdown: List[FaultBreakdown]
    timeline: List[TimelineEntry]
    key_evidence: List[EvidenceItem]


# ========== 问题追踪系统 Schema ==========

class JiraTicket(BaseModel):
    """Jira Ticket"""
    id: str
    key: str
    summary: str
    status: str = "Open"
    created_at: str
    updated_at: Optional[str] = None
    reporter: Optional[str] = None
    assignee: Optional[str] = None
    priority: str = "Medium"
    url: Optional[str] = None
    notes: Optional[str] = None
    problem_count: int = 0


class SlackThread(BaseModel):
    """Slack Thread"""
    id: str
    channel: str
    message_url: Optional[str] = None
    summary: Optional[str] = None
    created_at: str
    last_activity: Optional[str] = None
    participants_count: int = 0
    is_resolved: bool = False
    notes: Optional[str] = None


class ProblemLink(BaseModel):
    """问题关联记录"""
    problem_id: str
    linked_id: str  # jira_ticket_id or slack_thread_id
    linked_at: str
    linked_by: str = "manual"
    note: Optional[str] = None
    summary: Optional[str] = None
    is_resolved: bool = False
