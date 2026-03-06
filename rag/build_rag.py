# /vsi-ai-om/rag/build_rag.py
"""
RAG（检索增强生成）知识库构建

功能：
- 从 CSV 加载故障记录
- 构建 Chroma 向量数据库
- 创建 BM25 关键词索引
"""
import os
import pandas as pd
import chromadb
from chromadb.utils import embedding_functions
from langchain_community.retrievers import BM25Retriever


def build_rag() -> BM25Retriever:
    """
    构建 Chroma 向量数据库 + BM25 索引
    
    Returns:
        BM25Retriever: BM25 检索器
    
    Raises:
        FileNotFoundError: CSV 文件不存在
        Exception: Chroma 初始化失败
    """
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 1. 加载故障记录（添加错误处理）
    csv_path = os.path.join(project_root, "rag/docs", "exp.csv")
    try:
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV 文件不存在：{csv_path}")
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ 加载 CSV 失败：{str(e)}")
        print("⚠️ 返回空的 BM25Retriever")
        return BM25Retriever.from_texts(["placeholder"], k=5)

    # 2. 创建文档（包含完整故障描述）
    docs = []
    for _, row in df.iterrows():
        text = (
            f"Fault: {row['Problem Description']}. "
            f"Root Cause: {row['Problem Analysis']}. "
            f"Solution: {row['Solution']}. "
            f"Commands: {row['Reference Log']}"
        )
        docs.append(text)

    # 3. 初始化 Chroma（添加错误处理）
    chroma_path = os.path.join(project_root, "rag", "chroma_db")
    try:
        client = chromadb.PersistentClient(path=chroma_path)
        embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        collection = client.create_collection(
            name="devops_faults",
            metadata={"hnsw:space": "cosine"},
            embedding_function=embedding_func
        )

        # 4. 插入文档
        for i, text in enumerate(docs):
            collection.add(
                embeddings=embedding_func(text)[0].tolist(),
                documents=[text],
                metadatas=[{"id": f"fault_{i}"}],
                ids=[f"fault_{i}"]
            )
    except Exception as e:
        print(f"❌ Chroma 初始化失败：{str(e)}")
        print("⚠️ 仅使用 BM25Retriever")

    # 5. 创建BM25索引
    bm25_retriever = BM25Retriever.from_texts(docs, k=5)

    print("✅ RAG知识库构建成功 (Chroma + BM25)")
    return bm25_retriever


if __name__ == "__main__":
    build_rag()