#!/usr/bin/env python3
"""
吵架助手完整测试
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_service.mcp_server import get_argument_ammo


def test_argument_ammo():
    """测试弹药包生成"""
    print("="*70)
    print("🧪 测试 Argument Ammo 功能")
    print("="*70)
    
    # 测试 1: Jenkins（默认 3 天）
    print("\n✅ 测试 1: Jenkins 过去 3 天")
    ammo = get_argument_ammo(resource_kind="Jenkins", days=3)
    print(f"   摘要：{ammo.summary}")
    print(f"   统计：总数={ammo.statistics.total_problems}")
    print(f"   Schema 验证：✅")
    assert hasattr(ammo, 'resource_kind')
    assert hasattr(ammo, 'time_range')
    assert hasattr(ammo, 'statistics')
    assert hasattr(ammo, 'fault_breakdown')
    assert hasattr(ammo, 'timeline')
    assert hasattr(ammo, 'key_evidence')
    
    # 测试 2: 自定义天数
    print("\n✅ 测试 2: Jenkins 过去 7 天")
    ammo7 = get_argument_ammo(resource_kind="Jenkins", days=7)
    print(f"   摘要：{ammo7.summary}")
    
    # 测试 3: 特定故障类型
    print("\n✅ 测试 3: build failed 问题")
    ammo_build = get_argument_ammo(
        resource_kind="Jenkins",
        fault_type="build failed",
        days=3
    )
    print(f"   摘要：{ammo_build.summary}")
    
    # 测试 4: 未知资源
    print("\n✅ 测试 4: Unknown 资源")
    ammo_unknown = get_argument_ammo(resource_kind="Unknown")
    print(f"   摘要：{ammo_unknown.summary}")
    
    print("\n" + "="*70)
    print("🎉 所有测试通过！")
    print("="*70)
    
    # 打印示例输出
    print("\n" + "="*70)
    print("📊 示例弹药包结构")
    print("="*70)
    import json
    print(json.dumps(ammo.model_dump(), indent=2, ensure_ascii=False))
    
    return True


if __name__ == "__main__":
    success = test_argument_ammo()
    sys.exit(0 if success else 1)
