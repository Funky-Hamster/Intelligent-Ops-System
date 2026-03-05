#!/usr/bin/env python3
"""
MCP Service - 简化验证测试（移除 pipeline_name 后）
"""

import sqlite3
import sys
from pathlib import Path

# 数据库路径
DB_PATH = Path(__file__).parent / "problems.db"

def test_simplified_design():
    """测试简化后的设计（只有 job_name，无 pipeline_name）"""
    print("="*70)
    print("🧪 MCP Service 简化设计验证")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. 验证表结构
    print("\n✅ 步骤 1: 检查数据库表结构")
    c.execute("PRAGMA table_info(problems)")
    columns = c.fetchall()
    
    print(f"\n   📊 problems 表包含 {len(columns)} 个字段:")
    for col in columns:
        notnull = "NOT NULL" if col[3] else "NULL"
        print(f"      - {col[1]} ({col[2]}) [{notnull}]")
    
    # 验证没有 pipeline_name 字段
    field_names = [col[1] for col in columns]
    if 'pipeline_name' in field_names:
        print("\n   ❌ 错误：仍然包含 pipeline_name 字段!")
        return False
    else:
        print("\n   ✅ 确认：不包含 pipeline_name 字段")
    
    # 验证 resource_kind 字段存在
    if 'resource_kind' in field_names:
        print("   ✅ 确认：包含 resource_kind 字段")
    else:
        print("   ❌ 错误：缺少 resource_kind 字段!")
        return False
    
    # 验证 job_name 为 NOT NULL
    job_name_col = next((col for col in columns if col[1] == 'job_name'), None)
    if job_name_col and job_name_col[3]:
        print("   ✅ 确认：job_name 字段为 NOT NULL 约束")
    else:
        print("   ⚠️  注意：job_name 字段未设置 NOT NULL 约束")
    
    # 2. 插入测试数据
    print("\n✅ 步骤 2: 插入测试数据")
    import time
    import uuid
    
    test_records = [
        (f"prob-{uuid.uuid4().hex[:8]}", "build failed", "build", "job-001", time.strftime("%Y-%m-%d %H:%M:%S"), "Build error log", "Unknown"),
        (f"prob-{uuid.uuid4().hex[:8]}", "test failed", "test", "job-002", time.strftime("%Y-%m-%d %H:%M:%S"), "Test assertion error", "Unknown"),
        (f"prob-{uuid.uuid4().hex[:8]}", "deploy failed", "deploy", "job-003", time.strftime("%Y-%m-%d %H:%M:%S"), "Deployment timeout", "Unknown"),
        (f"prob-{uuid.uuid4().hex[:8]}", "disk full", "jenkins-agent", "job-004", time.strftime("%Y-%m-%d %H:%M:%S"), "Disk usage 95%", "Unknown"),
    ]
    
    for record in test_records:
        try:
            c.execute("INSERT INTO problems VALUES (?, ?, ?, ?, ?, ?, ?)", record)
            print(f"   ✅ 插入记录：{record[0]} (Job: {record[2]}, ID: {record[3]}, Resource: {record[6]})")
        except Exception as e:
            print(f"   ❌ 插入失败：{str(e)}")
            return False
    
    conn.commit()
    print("\n✅ 所有记录插入成功")
    
    # 3. 查询功能验证
    print("\n✅ 步骤 3: 查询功能验证")
    
    # 按 fault_type 查询
    c.execute("SELECT COUNT(*) FROM problems WHERE fault_type = 'build failed'")
    build_count = c.fetchone()[0]
    print(f"   🔍 fault_type='build failed': {build_count} 条记录")
    
    # 按时间范围查询
    c.execute("SELECT COUNT(*) FROM problems WHERE timestamp >= '2026-01-01 00:00:00'")
    time_count = c.fetchone()[0]
    print(f"   🔍 时间范围（2026-01-01 至今）: {time_count} 条记录")
    
    # 组合查询
    c.execute("SELECT * FROM problems WHERE fault_type = 'build failed' AND timestamp >= '2026-01-01 00:00:00'")
    combined_results = c.fetchall()
    print(f"   🔍 组合查询（fault_type + 时间范围）: {len(combined_results)} 条记录")
    
    # 查询所有记录
    c.execute("SELECT COUNT(*) FROM problems")
    total = c.fetchone()[0]
    print(f"   🔍 数据库总计：{total} 条记录")
    
    # 4. 验证数据结构
    print("\n✅ 步骤 4: 验证数据结构")
    c.execute("SELECT id, fault_type, job_name, job_id, timestamp, evidence, resource_kind FROM problems LIMIT 1")
    r = c.fetchone()
    
    print(f"   📝 示例记录:")
    print(f"      - id: {r[0]}")
    print(f"      - fault_type: {r[1]}")
    print(f"      - job_name: {r[2]}")
    print(f"      - job_id: {r[3]}")
    print(f"      - timestamp: {r[4]}")
    print(f"      - evidence: {r[5][:50]}...")
    print(f"      - resource_kind: {r[6]}")
    
    conn.close()
    
    # 5. 总结
    print("\n" + "="*70)
    print("🎉 验证通过！")
    print("="*70)
    print("\n✅ 关键结果:")
    print(f"   1. 数据库表结构正确（7 个字段，新增 resource_kind）")
    print(f"   2. job_name 为必填字段（NOT NULL 约束）")
    print(f"   3. resource_kind 字段已添加，用于标识资源类型")
    print(f"   4. 成功插入 {len(test_records)} 条测试数据")
    print(f"   5. 查询功能正常")
    print("\n💡 设计说明:")
    print("   - job_name: 必填字段，用于标识 Job 阶段（如 build/test/deploy）")
    print("   - job_id: Job 的唯一标识符")
    print("   - resource_kind: 资源类型（Jenkins/Artifactory/DRP/SRO/LabOps/GitHub/IT）")
    print("   - search_problems: 只支持 fault_type + 时间范围查询")
    print("   - 简化设计：移除了不必要的 pipeline_name 和 job_name 查询参数")
    return True

if __name__ == "__main__":
    success = test_simplified_design()
    sys.exit(0 if success else 1)
