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


class HybridRetriever(BaseRetriever):
    """混合 BM25 + FAISS 检索器 (权重：alpha BM25, beta Vector)"""

    def __init__(self, bm25_retriever, vector_retriever, alpha=None, beta=None):
        self.bm25_retriever = bm25_retriever
        self.vector_retriever = vector_retriever
        # 使用配置文件中的默认值
        self.alpha = alpha if alpha is not None else Config.RAG_ALPHA
        self.beta = beta if beta is not None else Config.RAG_BETA

    def _get_relevant_documents(self, query: str, **kwargs) -> List[Dict]:
        # BM25检索
        bm25_results = self.bm25_retriever.get_relevant_documents(query)
        bm25_scores = {doc.page_content: doc.metadata.get("score", 0.5) for doc in bm25_results}

        # FAISS检索
        faiss_results = self.vector_retriever.get_relevant_documents(query)
        faiss_scores = {doc.page_content: doc.metadata.get("similarity", 0.5) for doc in faiss_results}

        # 混合得分
        combined = {}
        for text in set(bm25_scores.keys()) | set(faiss_scores.keys()):
            bm25_score = bm25_scores.get(text, 0.0)
            faiss_score = faiss_scores.get(text, 0.0)
            combined[text] = self.alpha * bm25_score + self.beta * faiss_score

        # 排序并返回Top 5
        sorted_texts = sorted(combined.items(), key=lambda x: x[1], reverse=True)
        return [
            {"text": text, "score": score}
            for text, score in sorted_texts[:5]
        ]


# 初始化示例
if __name__ == "__main__":
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    from rag.build_rag import build_rag

    bm25_retriever = build_rag()

    chroma_path = os.path.join(project_root, "rag", "chroma_db")
    vectorstore = Chroma(
        persist_directory=chroma_path,
        embedding_function=HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    )

    retriever = HybridRetriever(
        bm25_retriever=bm25_retriever,
        vector_retriever=vectorstore.as_retriever(),
        alpha=0.7,
        beta=0.3
    )

    # 验证用例
    results = retriever.get_relevant_documents("disk full")
    print("✅ Hybrid Retriever Test:", results[0]["text"][:100] + "...")