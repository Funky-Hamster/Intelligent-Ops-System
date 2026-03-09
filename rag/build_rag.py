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
from pathlib import Path


def build_rag():
    """
    构建 Chroma 向量数据库 + BM25 索引
    
    Returns:
        tuple: (BM25Retriever, Chroma vectorstore or None)
    
    Raises:
        FileNotFoundError: CSV 文件不存在
        Exception: Chroma 初始化失败
    """
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 1. 加载主知识库 exp.csv（添加错误处理）
    csv_path = os.path.join(project_root, "rag/docs", "exp.csv")
    try:
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV 文件不存在：{csv_path}")
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ 加载 CSV 失败：{str(e)}")
        print("⚠️ 返回空的 BM25Retriever")
        return BM25Retriever.from_texts(["placeholder"], k=5)
    
    # 2. 加载扩展知识库 exp_extended.csv（如果存在）
    extended_csv_path = os.path.join(project_root, "rag/docs", "exp_extended.csv")
    if os.path.exists(extended_csv_path):
        print(f"正在加载扩展知识库：{extended_csv_path}")
        try:
            df_extended = pd.read_csv(extended_csv_path)
            df = pd.concat([df, df_extended], ignore_index=True)
            print(f"✅ 扩展知识库加载完成，总计 {len(df)} 个故障场景")
        except Exception as e:
            print(f"⚠️ 加载扩展库失败：{str(e)}，继续使用基础库")
    else:
        print(f"ℹ️ 未找到扩展知识库，仅使用基础库 ({len(df)} 个场景)")

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
    vectorstore = None
    try:
        # 强制设置为离线模式，禁止联网
        os.environ['HF_HUB_OFFLINE'] = '1'
        
        # 统一使用 HuggingFaceEmbeddings，必须指定 cache_folder 避免联网
        from langchain_community.vectorstores import Chroma
        from langchain_community.embeddings import HuggingFaceEmbeddings
        
        # 确保 models 目录存在
        models_dir = os.path.join(project_root, "models")
        os.makedirs(models_dir, exist_ok=True)
        
        embedding_func = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            cache_folder=models_dir  # 显式指定本地缓存
        )
        
        # 直接使用 LangChain Chroma API 创建
        vectorstore = Chroma(
            persist_directory=chroma_path,
            embedding_function=embedding_func,
            collection_name="devops_faults"
        )
        
        # 手动添加文档（使用统一的 embedding）
        texts = [doc for doc in docs]
        metadatas = [{"id": f"fault_{i}"} for i in range(len(docs))]
        ids = [f"fault_{i}" for i in range(len(docs))]
        
        # 先尝试删除，如果不存在则忽略错误
        try:
            vectorstore._client.delete_collection(name="devops_faults")
        except Exception:
            pass  # Collection 不存在也没关系
        
        # 重新创建并添加
        vectorstore = Chroma(
            persist_directory=chroma_path,
            embedding_function=embedding_func,
            collection_name="devops_faults"
        )
        vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        
        print("✅ Chroma 向量数据库初始化成功")
    except Exception as e:
        print(f"❌ Chroma 初始化失败：{str(e)}")
        print("⚠️ 仅使用 BM25Retriever")

    # 5. 创建 BM25 索引
    bm25_retriever = BM25Retriever.from_texts(docs, k=5)
    
    print("✅ RAG 知识库构建成功 (Chroma + BM25)")
    return bm25_retriever, vectorstore


if __name__ == "__main__":
    build_rag()