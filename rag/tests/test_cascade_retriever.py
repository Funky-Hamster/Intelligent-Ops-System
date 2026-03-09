"""
快速测试 RAG+LLM 级联架构
"""

import os
import sys

os.environ['HF_HUB_OFFLINE'] = '1'
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from rag.cascade_retriever import create_cascade_retriever

# 创建检索器
print("正在初始化级联检索器...")
retriever = create_cascade_retriever()
print("✅ 检索器初始化完成\n")

# 测试用例 1: RAG 能处理的场景
print("="*80)
print("测试 1: Docker daemon 连接失败（预期：RAG 处理）")
print("="*80)
result = retriever.retrieve(
    "Cannot connect to the Docker daemon at unix:///var/run/docker.sock",
    return_details=True
)
print(f"来源：{result['source']}")
print(f"置信度：{result['confidence']}")
print(f"RRF 分数：{result.get('rag_score', 0):.6f}")
print(f"答案预览：{result['answer'][:100]}...")
if result.get('details'):
    print(f"决策逻辑：{result['details']['decision']}")
print()

# 测试用例 2: 需要 LLM 的场景
print("="*80)
print("测试 2: Kubernetes Pod 崩溃（预期：LLM 处理）")
print("="*80)
result = retriever.retrieve(
    "CrashLoopBackOff: Back-off restarting failed container",
    return_details=True
)
print(f"来源：{result['source']}")
print(f"置信度：{result['confidence']}")
print(f"RRF 分数：{result.get('rag_score', 0):.6f}")
print(f"答案预览：{result['answer'][:200]}...")
print(f"说明：{result.get('llm_note', '')}")
if result.get('details'):
    print(f"决策逻辑：{result['details']['decision']}")
print()

print("="*80)
print("✅ 测试完成！")
print("="*80)
