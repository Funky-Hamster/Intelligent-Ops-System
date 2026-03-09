# /vsi-ai-om/config.py
"""
VSI-AI-OM 项目统一配置文件
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """统一配置类"""
    
    # ========== RAG 配置 ==========
    # 混合检索策略：RRF (Reciprocal Rank Fusion)
    # 设计理念：BM25 主导（词频匹配） + Vector 辅助（语义相似度）
    
    # RRF 参数
    RAG_RRF_K = 40  # 已优化（测试显示 k=20/40/60/80 命中率相同 85.7%，但 k=40 在 BM25(83.3%) 和 Vector(66.7%) 间取得最佳平衡）
    RAG_TOP_K_BM25 = 50      # BM25 粗筛数量
    RAG_TOP_K_VECTOR = 50    # Vector 粗筛数量
    RAG_TOP_K = 5            # 最终返回 Top K
    RAG_SCORE_THRESHOLD = 0.6  # 相关性分数阈值
    
    # 保留旧参数用于兼容（实际使用 RRF 时不使用）
    RAG_ALPHA = 0.7  # BM25 权重（理念值）
    RAG_BETA = 0.3   # Vector 权重（理念值）
    
    # ========== LLM 配置 ==========
    LLM_MODEL = os.getenv("LLM_MODEL", "qwen-max")
    LLM_MAX_TOKENS = 512
    LLM_TEMPERATURE_AGENT = 0.0  # Agent 温度（确定性高）
    LLM_TEMPERATURE_WRITER = 0.3  # 文案生成温度（适度创意）
    
    # ========== SSH 配置 ==========
    JENKINS_SSH_KEY_PATH = os.getenv("JENKINS_SSH_KEY_PATH", "/var/jenkins/ssh_key")
    JENKINS_SSH_USER = os.getenv("JENKINS_SSH_USER", "jenkins-agent")
    JENKINS_SSH_HOST = os.getenv("JENKINS_SSH_HOST", "agent-host")
    JENKINS_KNOWN_HOSTS_PATH = os.getenv("JENKINS_KNOWN_HOSTS_PATH", "/var/jenkins/known_hosts")
    SSH_TIMEOUT = 30  # SSH 超时时间（秒）
    
    # ========== Jenkins 配置 ==========
    JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8080")
    JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN", "")
    
    # ========== 重试配置 ==========
    MAX_RETRY_ATTEMPTS = 10
    MIN_RETRY_ATTEMPTS = 1
    DEFAULT_RETRY_ATTEMPTS = 3
    
    # ========== 数据库配置 ==========
    MCP_DB_PATH = os.getenv("MCP_DB_PATH", "mcp_service/problems.db")
    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "rag/chroma_db")
    
    # ========== 日志配置 ==========
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # ========== API 配置 ==========
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
    
    # ========== MCP Service 配置 ==========
    MCP_SERVICE_PORT = int(os.getenv("MCP_SERVICE_PORT", "8000"))
    AGENT_SERVICE_PORT = int(os.getenv("AGENT_SERVICE_PORT", "8001"))
    
    # ========== 安全配置 ==========
    ALLOWED_RESOURCE_KINDS = {"Jenkins", "Artifactory", "DRP", "SRO", "LabOps", "GitHub", "IT", "Unknown"}
    MAX_INPUT_LENGTH = 200  # 最大输入长度
    MAX_EVIDENCE_LENGTH = 5000  # 证据最大长度


# 导出配置实例
config = Config()
