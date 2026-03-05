# /vsi-ai-om/rag/build_rag.py
import pandas as pd
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
from langchain_community.document_loaders import CSVLoader
from langchain_community.retrievers import BM25Retriever


def build_rag():
    """构建 Chroma 向量数据库 + BM25 索引"""
    # 获取项目根目录
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 1. 加载故障记录
    csv_path = os.path.join(project_root, "rag/docs", "exp.csv")
    df = pd.read_csv(csv_path)

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

    # 3. 初始化 Chroma
    chroma_path = os.path.join(project_root, "rag", "chroma_db")
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

    # 5. 创建BM25索引
    bm25_retriever = BM25Retriever.from_texts(docs, k=5)

    print("✅ RAG知识库构建成功 (Chroma + BM25)")
    return bm25_retriever


if __name__ == "__main__":
    build_rag()