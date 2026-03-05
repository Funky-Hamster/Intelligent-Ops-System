#!/usr/bin/env python3
"""
测试吵架助手功能
"""

import sys
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_service.mcp_client import MCPClient


def test_get_argument_ammo():
    """测试获取弹药包"""
    print("="*70)
    print("🧪 测试 get_argument_ammo 功能")
    print("="*70)
    
    mcp = MCPClient()
    
    # 测试 1: 查询 Jenkins（默认 3 天）
    print("\n✅ 测试 1: 查询 Jenkins 过去 3 天")
    try:
        ammo = mcp.get_argument_ammo_sync(resource_kind="Jenkins")
        print(f"   摘要：{ammo['summary']}")
        print(f"   统计：总数={ammo['statistics']['total_problems']}, Job 数={ammo['statistics']['affected_jobs']}")
        print(f"   故障类型：{len(ammo['fault_breakdown'])} 种")
        print(f"   时间线：{len(ammo['timeline'])} 天")
        print(f"   证据数：{len(ammo['key_evidence'])} 条")
        assert "resource_kind" in ammo
        assert "time_range" in ammo
        assert "statistics" in ammo
        print("   ✅ 测试通过")
    except Exception as e:
        print(f"   ❌ 测试失败：{str(e)}")
        return False
    
    # 测试 2: 查询特定故障类型
    print("\n✅ 测试 2: 查询 Jenkins 的 'build failed' 问题")
    try:
        ammo = mcp.get_argument_ammo_sync(
            resource_kind="Jenkins",
            fault_type="build failed"
        )
        print(f"   摘要：{ammo['summary']}")
        if ammo['statistics']['total_problems'] > 0:
            print(f"   找到 {ammo['statistics']['total_problems']} 条记录")
        else:
            print(f"   ⚠️ 未找到相关记录")
        print("   ✅ 测试通过")
    except Exception as e:
        print(f"   ❌ 测试失败：{str(e)}")
        return False
    
    # 测试 3: 自定义天数
    print("\n✅ 测试 3: 查询 Jenkins 过去 7 天")
    try:
        ammo = mcp.get_argument_ammo_sync(
            resource_kind="Jenkins",
            days=7
        )
        print(f"   摘要：{ammo['summary']}")
        print("   ✅ 测试通过")
    except Exception as e:
        print(f"   ❌ 测试失败：{str(e)}")
        return False
    
    # 测试 4: 无数据情况
    print("\n✅ 测试 4: 查询 Unknown 资源（可能无数据）")
    try:
        ammo = mcp.get_argument_ammo_sync(resource_kind="Unknown")
        print(f"   摘要：{ammo['summary']}")
        if "未发现问题" in ammo['summary']:
            print(f"   ℹ️  预期结果：无数据")
        print("   ✅ 测试通过")
    except Exception as e:
        print(f"   ❌ 测试失败：{str(e)}")
        return False
    
    print("\n" + "="*70)
    print("🎉 所有测试通过！")
    print("="*70)
    return True


if __name__ == "__main__":
    success = test_get_argument_ammo()
    sys.exit(0 if success else 1)
