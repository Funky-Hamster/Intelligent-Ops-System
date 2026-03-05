# /vsi-ai-om/agent/argument_agent.py
"""
吵架助手 Agent - 按需生成沟通文案

使用方式：
    python -m agent.argument_agent --target Jenkins --days 3
"""

import argparse
import json
from pathlib import Path
from typing import Dict
import os

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from mcp_service.mcp_client import MCPClient
from langchain_community.llms.tongyi import Tongyi


class ArgumentAgent:
    """吵架助手 Agent - 数据驱动文案生成"""
    
    def __init__(self):
        """初始化 Agent"""
        self.mcp = MCPClient("mcp_service/mcp_server.py")
        
        # 验证 API Key
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("❌ DASHSCOPE_API_KEY 未设置！")
        
        self.llm = Tongyi(
            model="qwen-max",
            max_tokens=1024,
            temperature=0.3,  # 降低随机性，更稳定
            verbose=False,
            dashscope_api_key=api_key
        )
    
    def prepare_argument(self, 
                        resource_kind: str, 
                        days: int = 3,
                        fault_type: str = None) -> Dict:
        """
        准备吵架材料
        
        Args:
            resource_kind: 资源类型
            days: 天数（默认 3）
            fault_type: 故障类型（可选）
            
        Returns:
            包含 Slack 和 Jira 文案的字典
        """
        print(f"📊 正在获取 {resource_kind} 的数据...")
        
        # Step 1: 获取数据（MCP）
        ammo = self.mcp.get_argument_ammo_sync(
            resource_kind=resource_kind,
            days=days,
            fault_type=fault_type
        )
        
        print(f"✅ 数据获取完成：{ammo['summary']}")
        
        # Step 2: 生成 Slack 文案（LLM）
        print("💬 正在生成 Slack 文案...")
        slack_message = self._generate_slack_draft(ammo, resource_kind)
        
        # Step 3: 生成 Jira 文案（LLM）
        print("📝 正在生成 Jira 文案...")
        jira_description = self._generate_jira_draft(ammo, resource_kind)
        
        return {
            "slack_message": slack_message,
            "jira_description": jira_description,
            "data_summary": ammo["summary"],
            "statistics": ammo["statistics"]
        }
    
    def _generate_slack_draft(self, ammo: Dict, resource_kind: str) -> str:
        """生成 Slack 文案草稿"""
        
        prompt = f"""你是一个专业的 DevOps 工程师，需要向 {resource_kind} 团队反馈问题。

基于以下数据生成一段 Slack 消息：

【数据】
{json.dumps(ammo, ensure_ascii=False, indent=2)}

【要求】
1. 语气专业但坚定，不要过于攻击性
2. 突出关键数字（用**加粗**）
3. 使用 emoji 增强可读性
4. @{resource_kind.lower()}-team
5. 长度控制在 200 字以内
6. 包含：问题统计、主要故障类型、建议行动

直接输出文案内容，不要解释。"""

        response = self.llm.invoke(prompt)
        return response.strip()
    
    def _generate_jira_draft(self, ammo: Dict, resource_kind: str) -> str:
        """生成 Jira Issue 描述"""
        
        prompt = f"""你是一个专业的 QA 工程师，需要创建一个 Jira Issue。

基于以下数据生成 Jira 描述：

【数据】
{json.dumps(ammo, ensure_ascii=False, indent=2)}

【要求】
1. 使用 Jira Markdown 格式
2. 结构清晰：
   h3. 问题概述
   h3. 统计数据
   || 指标 || 数值 ||
   | 总故障数 | X |
   h3. 故障类型分布
   # 类型 1 - X 次
   h3. 关键证据
   {{代码块}}
   h3. 建议行动项
   * 立即行动
   * 长期改进
3. 语气正式、客观
4. 基于真实数据，不要编造

直接输出文案内容，不要解释。"""

        response = self.llm.invoke(prompt)
        return response.strip()


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        description="📢 吵架助手 - 生成沟通文案",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python -m agent.argument_agent --target Jenkins
  python -m agent.argument_agent --target Jenkins --days 7
  python -m agent.argument_agent --target Artifactory --fault-type "upload failed"
        """
    )
    
    parser.add_argument(
        "--target", "-t",
        required=True,
        help="资源类型（Jenkins/Artifactory/DRP/SRO/LabOps/GitHub/IT/Unknown）"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=3,
        help="查询最近 N 天（默认 3）"
    )
    parser.add_argument(
        "--fault-type", "-f",
        help="故障类型（可选）"
    )
    
    args = parser.parse_args()
    
    # 创建 Agent 并执行
    agent = ArgumentAgent()
    result = agent.prepare_argument(
        resource_kind=args.target,
        days=args.days,
        fault_type=args.fault_type
    )
    
    # 输出结果
    print("\n" + "="*70)
    print("📊 数据摘要")
    print("="*70)
    print(result["data_summary"])
    print(f"\n总故障数：{result['statistics']['total_problems']}")
    print(f"影响 Job 数：{result['statistics']['affected_jobs']}")
    print(f"故障类型数：{result['statistics']['unique_fault_types']}")
    
    print("\n" + "="*70)
    print("💬 Slack 文案（可直接复制）")
    print("="*70)
    print(result["slack_message"])
    
    print("\n" + "="*70)
    print("📝 Jira 文案（可直接复制）")
    print("="*70)
    print(result["jira_description"])
    
    print("\n" + "="*70)
    print("✅ 文案生成完成！")
    print("="*70)


if __name__ == "__main__":
    main()
