"""
RAG + LLM 级联式混合检索器

架构设计:
1. 优先使用 RAG 检索（准确、快速、成本低）
2. RAG 无高置信度结果时，调用 LLM 辅助（灵活、创新、兜底）
3. 形成正向循环：LLM 生成的优质答案可回填到知识库

级联逻辑:
Jenkins Log → RAG 检索 → Score > threshold? 
    ├─ YES → 返回 RAG Top5 答案 ✅
    └─ NO  → LLM 推理 🔮
              ↓
          生成定制化解决方案
              ↓
          可选：回填到知识库
"""

import os
import sys
from typing import List, Dict, Optional, Tuple
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.schema import Document
import dashscope
from dashscope import Generation

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from config import Config


class CascadeRetriever:
    """级联式检索器 (RAG + LLM)"""
    
    def __init__(self, chroma_path: str, collection_name: str = "devops_faults"):
        """
        初始化级联检索器
        
        Args:
            chroma_path: ChromaDB 持久化路径
            collection_name: Collection 名称
        """
        self.chroma_path = chroma_path
        self.collection_name = collection_name
        
        # 初始化 RAG 组件
        self._init_rag()
        
        # 初始化 LLM 组件
        self._init_llm()
        
        # RAG 置信度阈值（低于此值则调用 LLM）
        # 基于真实测试数据优化：精确匹配场景分数约 0.048-0.049
        # 知识外问题分数约 0.024-0.025
        self.rag_threshold = 0.045  # 调整到中间值，更准确区分
    
    def _init_rag(self):
        """初始化 RAG 检索组件 - 复用 build_rag 的初始化逻辑避免重复加载模型"""
        os.environ['HF_HUB_OFFLINE'] = '1'
        
        # 直接使用 build_rag() 返回的已初始化检索器
        from rag.build_rag import build_rag
        bm25, vectorstore_from_build = build_rag()
        self.bm25_retriever = bm25
        self.vectorstore = vectorstore_from_build
        
        # 从 vectorstore 获取文档来初始化 BM25
        try:
            all_docs = self.vectorstore.get()
            if all_docs and all_docs['documents']:
                from langchain_community.retrievers import BM25Retriever
                from langchain.schema import Document
                
                docs = [
                    Document(page_content=content, metadata=all_docs['metadatas'][i] if all_docs['metadatas'] else {})
                    for i, content in enumerate(all_docs['documents'])
                ]
                self.bm25_retriever = BM25Retriever.from_documents(docs)
            else:
                self.bm25_retriever = BM25Retriever.from_texts(["placeholder"])
        except Exception as e:
            # 如果失败，使用 placeholder
            from langchain_community.retrievers import BM25Retriever
            self.bm25_retriever = BM25Retriever.from_texts(["placeholder"])
        
        # 混合检索器（RRF）
        from rag.hybrid_retriever import HybridRetriever_RRF
        
        # 只有当 vectorstore 成功初始化时才使用混合检索
        if self.vectorstore is not None:
            self.hybrid_retriever = HybridRetriever_RRF(
                bm25_retriever=self.bm25_retriever,
                vector_retriever=self.vectorstore.as_retriever(),
                top_k_bm25=Config.RAG_TOP_K_BM25,
                top_k_vector=Config.RAG_TOP_K_VECTOR,
                top_k_final=Config.RAG_TOP_K,
                k=Config.RAG_RRF_K
            )
        else:
            print("⚠️ VectorStore 初始化失败，仅使用 BM25Retriever")
            self.hybrid_retriever = self.bm25_retriever
    
    def _init_llm(self):
        """初始化 LLM 组件"""
        dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.llm_model = Config.LLM_MODEL
    
    def retrieve(self, query: str, return_details: bool = False) -> Dict:
        """
        级联式检索
        
        Args:
            query: 查询语句（Jenkins log 关键错误）
            return_details: 是否返回详细信息
            
        Returns:
            {
                "source": "RAG" | "LLM",
                "confidence": "high" | "medium" | "low",
                "answer": str,
                "results": List[Dict],  # RAG 结果
                "rag_score": float,  # RAG 最高分
                "llm_note": str  # LLM 说明
            }
        """
        # Step 1: RAG 检索
        rrf_results = self.hybrid_retriever.get_relevant_documents(query)
        
        # Step 2: 判断置信度
        if rrf_results and len(rrf_results) > 0:
            top_score = rrf_results[0].get('score', 0)
            
            if top_score > self.rag_threshold:
                # RAG 有高置信度结果
                response = {
                    "source": "RAG",
                    "confidence": "high",
                    "answer": rrf_results[0]['text'],
                    "results": rrf_results[:Config.RAG_TOP_K],
                    "rag_score": top_score,
                    "llm_note": None
                }
                
                if return_details:
                    response["details"] = {
                        "query": query,
                        "threshold": self.rag_threshold,
                        "top_score": top_score,
                        "decision": f"RAG score ({top_score:.6f}) > threshold ({self.rag_threshold})"
                    }
                
                return response
        
        # Step 3: RAG 无高置信度结果，调用 LLM
        llm_response = self._call_llm(query, rrf_results[:2] if rrf_results else [])
        
        response = {
            "source": "LLM",
            "confidence": "medium",
            "answer": llm_response["answer"],
            "results": [],
            "rag_score": rrf_results[0]['score'] if rrf_results else 0,
            "llm_note": llm_response.get("note", "知识库未找到直接答案，以下为 AI 推理建议")
        }
        
        if return_details:
            response["details"] = {
                "query": query,
                "threshold": self.rag_threshold,
                "top_score": rrf_results[0]['score'] if rrf_results else 0,
                "decision": f"RAG score < threshold, fallback to LLM"
            }
        
        return response
    
    def _call_llm(self, query: str, rag_context: List[Dict]) -> Dict:
        """
        调用 LLM 进行推理
        
        Args:
            query: 用户查询
            rag_context: RAG 检索到的相关上下文（即使分数低也可能有帮助）
            
        Returns:
            {
                "answer": str,
                "note": str
            }
        """
        # 构建增强提示词
        prompt = self._build_enhanced_prompt(query, rag_context)
        
        try:
            # 调用 DashScope API
            response = Generation.call(
                model=self.llm_model,
                prompt=prompt,
                max_tokens=1024,
                temperature=0.3  # 适度创意，保持专业性
            )
            
            if response.status_code == 200:
                return {
                    "answer": response.output.text,
                    "note": "AI 推理建议（基于通用运维知识）"
                }
            else:
                return {
                    "answer": f"LLM 调用失败：{response.message}",
                    "note": "Error"
                }
                
        except Exception as e:
            return {
                "answer": f"LLM 调用异常：{str(e)}",
                "note": "Exception"
            }
    
    def _build_enhanced_prompt(self, query: str, rag_context: List[Dict]) -> str:
        """
        构建增强的 LLM 提示词（结构化 + 示例驱动）
        
        Args:
            query: 用户查询
            rag_context: RAG 检索到的相关上下文
            
        Returns:
            增强后的提示词
        """
        context_text = ""
        if rag_context:
            context_text = "\n\n【相关知识库参考】\n"
            for i, item in enumerate(rag_context, 1):
                context_text += f"{i}. {item['text'][:300]}...\n"
        
        prompt = f"""# 角色设定
你是一位拥有 10 年经验的资深运维工程师，专注于 Jenkins CI/CD 和云原生技术栈。
你的任务是分析构建失败日志，提供专业、可执行的解决方案。

# 错误信息
```log
{query}
```
{context_text}
# 任务要求

请按照以下结构提供详细的故障分析报告：

## 1. 问题诊断
- **错误类型**：识别这是哪种类型的故障（如 Docker、Maven、NPM、K8s 等）
- **严重程度**：评估对构建流程的影响（阻塞/警告/可忽略）
- **可能原因**：列出 3-5 个最可能的根本原因（按可能性排序）

## 2. 排查步骤
提供详细的诊断流程，每一步包含：
- **步骤编号**：Step 1, Step 2...
- **操作说明**：清晰描述要做什么
- **执行命令**：具体的 shell 命令（使用```bash 代码块）
- **预期结果**：正常情况应该看到什么输出
- **异常处理**：如果这一步失败，下一步该怎么做

## 3. 解决方案
针对每个可能原因，提供：
- **修复方法**：具体的操作步骤
- **配置文件**：如果需要修改配置，指明文件路径和具体参数
- **验证方式**：如何确认问题已解决
- **回滚方案**：如果修复失败，如何恢复原状

## 4. 预防措施
- **监控告警**：建议添加哪些监控指标和阈值
- **自动化**：如何通过脚本或工具避免人工干预
- **最佳实践**：相关的运维规范和注意事项

# 输出规范

- ✅ **专业性**：使用准确的运维术语（如 Pod、Deployment、ConfigMap）
- ✅ **可执行性**：所有命令必须经过验证，可以直接复制执行
- ✅ **安全性**：考虑生产环境，避免危险操作（如 rm -rf /）
- ✅ **完整性**：包含前置条件、依赖检查、后续验证
- ✅ **结构化**：使用 Markdown 格式，层次清晰，重点突出

# 示例格式

```markdown
## 1. 问题诊断
**错误类型**: Docker daemon 连接失败
**严重程度**: 🔴 阻塞（构建无法继续）
**可能原因**:
1. Docker 服务未启动或已崩溃
2. Socket 权限配置错误
3. 磁盘空间耗尽导致 Docker 无法写入

## 2. 排查步骤
### Step 1: 检查 Docker 服务状态
**操作**: 查看 Docker 服务是否正在运行
**命令**:
```bash
systemctl status docker
```
**预期结果**: Active: active (running)
**异常处理**: 如果显示 failed 或 inactive，执行 Step 2

...
```

请开始分析上述错误日志。"""
        
        return prompt
    
    def search(self, query: str) -> List[Dict]:
        """兼容旧接口（简单搜索）"""
        result = self.retrieve(query)
        return result.get("results", [{"text": result["answer"], "score": 0}])


class KnowledgeBaseManager:
    """知识库管理器（支持 LLM 答案回填）"""
    
    def __init__(self, cascade_retriever: CascadeRetriever):
        self.retriever = cascade_retriever
        self.vectorstore = cascade_retriever.vectorstore
    
    def add_case(self, query: str, solution: str, metadata: Optional[Dict] = None):
        """
        添加新案例到知识库
        
        Args:
            query: 问题描述
            solution: 解决方案
            metadata: 元数据（标签、来源等）
        """
        if metadata is None:
            metadata = {}
        
        # 生成唯一 ID
        import hashlib
        doc_id = hashlib.md5(f"{query}_{solution}".encode()).hexdigest()[:8]
        
        # 添加到向量库
        self.vectorstore.add_texts(
            texts=[solution],
            metadatas=[{
                "id": f"case_{doc_id}",
                "query": query,
                "source": metadata.get("source", "manual"),
                "tags": metadata.get("tags", []),
                "created_at": metadata.get("created_at", "")
            }],
            ids=[f"case_{doc_id}"]
        )
    
    def add_llm_solution(self, query: str, llm_answer: str, quality_score: float):
        """
        将 LLM 生成的优质答案回填到知识库
        
        Args:
            query: 原始查询
            llm_answer: LLM 生成的解决方案
            quality_score: 质量评分（1-5）
        """
        if quality_score >= 4:  # 只回填高质量答案
            metadata = {
                "source": "llm_generated",
                "quality_score": quality_score,
                "tags": ["ai_generated", "verified"],
                "created_at": ""
            }
            self.add_case(query, llm_answer, metadata)


def create_cascade_retriever():
    """工厂函数：创建级联检索器实例"""
    chroma_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
    return CascadeRetriever(chroma_path=chroma_path)


# ========== 使用示例 ==========
if __name__ == "__main__":
    retriever = create_cascade_retriever()
    
    # 测试用例 1: RAG 能处理的场景
    print("="*80)
    print("测试 1: Docker daemon 连接失败（RAG 处理）")
    print("="*80)
    result = retriever.retrieve(
        "Cannot connect to the Docker daemon at unix:///var/run/docker.sock",
        return_details=True
    )
    print(f"来源：{result['source']}")
    print(f"置信度：{result['confidence']}")
    print(f"答案：{result['answer'][:100]}...")
    if result.get('details'):
        print(f"决策：{result['details']['decision']}")
    
    # 测试用例 2: 需要 LLM 的场景
    print("\n" + "="*80)
    print("测试 2: Kubernetes Pod 崩溃（LLM 处理）")
    print("="*80)
    result = retriever.retrieve(
        "CrashLoopBackOff: Back-off restarting failed container",
        return_details=True
    )
    print(f"来源：{result['source']}")
    print(f"置信度：{result['confidence']}")
    print(f"答案：{result['answer'][:200]}...")
    print(f"说明：{result['llm_note']}")
    if result.get('details'):
        print(f"决策：{result['details']['decision']}")
