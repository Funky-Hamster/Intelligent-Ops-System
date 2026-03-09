# /vsi-ai-om/rag/hybrid_retriever.py
from langchain_core.retrievers import BaseRetriever
from typing import List, Dict, Any
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
import numpy as np
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config


class HybridRetriever_RRF(BaseRetriever):
    """基于 RRF (Reciprocal Rank Fusion) 的混合检索器
    
    设计理念：
    - BM25 主导（词频匹配，权重约 0.7）
    - Vector 辅助（语义相似度，权重约 0.3）
    - 通过排名融合而非分数融合，避免尺度不一致问题
    """
    
    bm25_retriever: Any
    vector_retriever: Any
    top_k_bm25: int  # BM25 粗筛数量
    top_k_vector: int  # Vector 粗筛数量
    top_k_final: int  # 最终返回数量
    k: float  # RRF 平滑参数（推荐 60）
    
    def __init__(self, bm25_retriever=None, vector_retriever=None, 
                 top_k_bm25=50, top_k_vector=50, top_k_final=5, k=60.0):
        super().__init__(
            bm25_retriever=bm25_retriever,
            vector_retriever=vector_retriever,
            top_k_bm25=top_k_bm25,
            top_k_vector=top_k_vector,
            top_k_final=top_k_final,
            k=k
        )

    def _get_relevant_documents(self, query: str, **kwargs) -> List[Dict]:
        # Step 1: 分别检索
        bm25_docs = self.bm25_retriever.get_relevant_documents(query)[:self.top_k_bm25]
        vector_docs = self.vector_retriever.get_relevant_documents(query)[:self.top_k_vector]
        
        # Step 2: 构建排名映射
        bm25_ranks = {doc.page_content: i+1 for i, doc in enumerate(bm25_docs)}
        vector_ranks = {doc.page_content: i+1 for i, doc in enumerate(vector_docs)}
        
        # Step 3: 合并所有文档
        all_docs = {}
        for doc in bm25_docs + vector_docs:
            text = doc.page_content
            if text not in all_docs:
                all_docs[text] = {
                    "doc": doc, 
                    "bm25_rank": float('inf'), 
                    "vector_rank": float('inf')
                }
            
            if text in bm25_ranks:
                all_docs[text]["bm25_rank"] = bm25_ranks[text]
            if text in vector_ranks:
                all_docs[text]["vector_rank"] = vector_ranks[text]
        
        # Step 4: 计算 RRF 得分
        # 公式：rrf_score = 1/(k + rank_bm25) + 1/(k + rank_vector)
        for item in all_docs.values():
            item["rrf_score"] = (
                1.0 / (self.k + item["bm25_rank"]) + 
                1.0 / (self.k + item["vector_rank"])
            )
        
        # Step 5: 按 RRF 得分排序并返回 Top K
        sorted_docs = sorted(
            all_docs.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )
        
        return [
            {"text": item["doc"].page_content, "score": item["rrf_score"]}
            for item in sorted_docs[:self.top_k_final]
        ]


# 初始化示例（RRF 版本）
if __name__ == "__main__":
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    from rag.build_rag import build_rag

    bm25_retriever = build_rag()

    chroma_path = os.path.join(project_root, "rag", "chroma_db")
    
    # 强制离线模式
    os.environ['HF_HUB_OFFLINE'] = '1'
    
    # 使用模型名称（自动从缓存加载）- 必须指定 cache_folder 避免联网
    vectorstore = Chroma(
        persist_directory=chroma_path,
        embedding_function=HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            cache_folder=os.path.join(project_root, "models")
        )
    )

    retriever = HybridRetriever_RRF(
        bm25_retriever=bm25_retriever,
        vector_retriever=vectorstore.as_retriever(),
        top_k_bm25=50,    # BM25 粗筛 50 个
        top_k_vector=50,  # Vector 粗筛 50 个
        top_k_final=5,    # 最终返回 Top 5
        k=60.0            # RRF 参数（经验值）
    )

    # 验证用例
    results = retriever.get_relevant_documents("disk full")
    print("✅ RRF Hybrid Retriever Test:", results[0]["text"][:100] + "...")
    print(f"   RRF Score: {results[0]['score']:.4f}")