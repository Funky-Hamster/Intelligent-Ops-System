# /vsi-ai-om/mcp_service/services/problem_service.py
"""
问题管理服务

提供问题相关的业务逻辑处理
"""

import datetime
from typing import List, Dict
from mcp_service.schemas import (
    ArgumentAmmo, TimeRange, SummaryStats,
    FaultBreakdown, TimelineEntry, EvidenceItem
)


def build_ammo_package(problems: List[Dict], resource_kind: str, days: int) -> ArgumentAmmo:
    """
    构建吵架弹药包
    
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
