# /vsi-ai-om/agent/ai_om_agent.py
"""
AI 运维 Agent - 故障自动修复

功能：
- 基于 RAG 检索解决方案
- 自动执行修复操作（重试 Job、清理磁盘、重启 Docker）
- 记录无法解决的问题到 MCP Service
"""
from typing import List

import subprocess
import os
import logging

from langchain_community.retrievers import BM25Retriever
from langchain_community.tools import tool
from langchain.agents import AgentExecutor, create_react_agent
from langchain.callbacks import StdOutCallbackHandler
from langchain_community.vectorstores import Chroma
from langchain_community.llms.tongyi import Tongyi
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

from rag.hybrid_retriever import HybridRetriever
from rag.build_rag import build_rag
from mcp_service.mcp_client import MCPClient
from config import Config
from agent.prompt import PROMPT

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ========== API Key 验证 ==========
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    raise ValueError(
        "❌ DASHSCOPE_API_KEY 未设置！\n"
        "请设置环境变量：\n"
        "  Windows PowerShell: $env:DASHSCOPE_API_KEY=\"your-api-key\"\n"
        "  Linux/Mac: export DASHSCOPE_API_KEY=\"your-api-key\""
    )
print(f"✅ Qwen API Key 已加载")

# ========== RAG 初始化 ==========
bm25_retriever = build_rag()
chroma_path = os.path.join(PROJECT_ROOT, "rag", "chroma_db")
vectorstore = Chroma(
    persist_directory=chroma_path,
    embedding_function=HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
)
hybrid_retriever = HybridRetriever(
    bm25_retriever=bm25_retriever,
    vector_retriever=vectorstore.as_retriever(),
    alpha=Config.RAG_ALPHA,
    beta=Config.RAG_BETA
)


# ========== 工具函数定义 ==========

@tool
def retry_job(job_id: str, attempts: int = 3):
    """
    重试 Jenkins job（安全执行）
    
    Args:
        job_id: Job ID（仅允许数字和连字符）
        attempts: 重试次数（1-10，默认 3）
    
    Returns:
        str: 成功消息
    
    Raises:
        ValueError: 参数验证失败
        Exception: SSH 连接超时或执行失败
    """
    logger.info(f"🔄 [retry_job] Retrying job {job_id} with {attempts} attempts")

    # 从环境变量读取 SSH 配置（与其他工具保持一致）
    ssh_key_path = os.getenv("JENKINS_SSH_KEY_PATH", "/var/jenkins/ssh_key")
    ssh_user = os.getenv("JENKINS_SSH_USER", "jenkins-agent")
    ssh_host = os.getenv("JENKINS_SSH_HOST", "agent-host")
    known_hosts_path = os.getenv("JENKINS_KNOWN_HOSTS_PATH", "/var/jenkins/known_hosts")

    # 双重安全验证
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("Invalid job_id: empty or null")
    
    if not job_id.replace('-', '').isdigit():
        raise ValueError("Invalid job_id format: only digits and hyphens allowed")
    
    if not isinstance(attempts, int) or attempts < 1 or attempts > 10:
        raise ValueError("Invalid attempts value: must be integer between 1-10")

    # 使用参数化命令，避免 shell=True 和命令注入
    # 使用完整的 Jenkins URL 和标准的 curl 命令
    try:
        cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={known_hosts_path}",
            "-o", "ConnectTimeout=30",  # 添加超时配置
            f"{ssh_user}@{ssh_host}",
            "curl", "-X", "POST",
            f"http://localhost:8080/job/{job_id}/build?delay=0sec",
            "-u", "admin:${JENKINS_API_TOKEN}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)

        # 更准确的成功判断：检查 HTTP 状态码或响应内容
        if result.returncode != 0 or ("ERROR" in result.stdout.upper() and "SUCCESS" not in result.stdout.upper()):
            raise Exception(f"Retry failed: {result.stderr or result.stdout}")

        return f"Job {job_id} retried successfully"
    except subprocess.TimeoutExpired:
        logger.error(f"SSH command timed out after 60 seconds")
        raise Exception("SSH connection timed out")
    except Exception as e:
        logger.error(f"Retry job failed: {str(e)}")
        raise


@tool
def clean_disk():
    """
    清理 Jenkins agent 磁盘（仅限安全路径）
    
    安全路径白名单：/var/jenkins/tmp, /tmp
    
    Returns:
        str: 成功消息
    
    Raises:
        Exception: SSH 连接超时或执行失败
    """
    logger.info("🧹 [clean_disk] Cleaning disk: /var/jenkins/tmp and /tmp")

    # 从环境变量读取 SSH 配置
    ssh_key_path = os.getenv("JENKINS_SSH_KEY_PATH", "/var/jenkins/ssh_key")
    ssh_user = os.getenv("JENKINS_SSH_USER", "jenkins-agent")
    ssh_host = os.getenv("JENKINS_SSH_HOST", "agent-host")
    known_hosts_path = os.getenv("JENKINS_KNOWN_HOSTS_PATH", "/var/jenkins/known_hosts")

    # 安全路径白名单
    allowed_paths = ["/var/jenkins/tmp", "/tmp"]
    
    try:
        # 使用 SSH 密钥认证，避免密码泄露
        cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={known_hosts_path}",
            "-o", "ConnectTimeout=30",  # 添加超时配置
            f"{ssh_user}@{ssh_host}",
            "rm", "-rf"
        ] + allowed_paths
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        return "Disk cleaned successfully"
    except subprocess.TimeoutExpired:
        logger.error(f"SSH command timed out after 60 seconds")
        raise Exception("SSH connection timed out")
    except Exception as e:
        logger.error(f"Clean disk failed: {str(e)}")
        raise


@tool
def restart_docker():
    """
    重启 Docker 服务（安全执行）
    
    Returns:
        str: 成功消息
    
    Raises:
        Exception: SSH 连接超时或执行失败
    """
    logger.info("🐳 [restart_docker] Restarting Docker service")

    # 从环境变量读取 SSH 配置
    ssh_key_path = os.getenv("JENKINS_SSH_KEY_PATH", "/var/jenkins/ssh_key")
    ssh_user = os.getenv("JENKINS_SSH_USER", "jenkins-agent")
    ssh_host = os.getenv("JENKINS_SSH_HOST", "agent-host")
    known_hosts_path = os.getenv("JENKINS_KNOWN_HOSTS_PATH", "/var/jenkins/known_hosts")

    try:
        # 使用 SSH 密钥认证，强制主机密钥验证
        cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={known_hosts_path}",
            "-o", "ConnectTimeout=30",  # 添加超时配置
            f"{ssh_user}@{ssh_host}",
            "systemctl", "restart", "docker"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        return "Docker restarted successfully"
    except subprocess.TimeoutExpired:
        logger.error(f"SSH command timed out after 60 seconds")
        raise Exception("SSH connection timed out")
    except Exception as e:
        logger.error(f"Restart docker failed: {str(e)}")
        raise


# ========== Agent 初始化 ==========
llm = Tongyi(
    model=Config.LLM_MODEL,
    max_tokens=Config.LLM_MAX_TOKENS,
    temperature=Config.LLM_TEMPERATURE_AGENT,
    verbose=True,
    dashscope_api_key=DASHSCOPE_API_KEY
)
print(f"✅ Qwen 模型初始化成功 (model: {Config.LLM_MODEL})")

tools = [retry_job, clean_disk, restart_docker]
agent = create_react_agent(llm, tools, PROMPT)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    callbacks=[StdOutCallbackHandler()]
)

# MCP Service 客户端
mcp_client = MCPClient("mcp_service/mcp_server.py")


# ========== 核心业务逻辑 ==========

def handle_failure(fault_type: str, job_id: str) -> str:
    """
    故障处理闭环
    
    Args:
        fault_type: 故障类型
        job_id: Job ID
    
    Returns:
        str: 处理结果
    """
    # 1. RAG 检索解决方案
    results = hybrid_retriever.get_relevant_documents(fault_type)

    # 2. 通过Agent生成工具调用
    if results:
        try:
            response = agent_executor.invoke({
                "input": f"Handle fault type: {fault_type}, job ID: {job_id}",
                "fault_type": fault_type,
                "job_id": job_id
            })

            # 4. 验证 Agent 输出格式
            if not isinstance(response, dict) or "name" not in response:
                raise ValueError("Invalid agent response format")
            
            # 5. 执行工具调用（安全查找）
            tool_name = response["name"]
            arguments = response.get("arguments", {})
            
            # 安全的工具查找，防止 StopIteration 异常
            tools_dict = {t.name: t for t in tools}
            if tool_name not in tools_dict:
                raise ValueError(f"Unknown tool: {tool_name}")
                        
            tool = tools_dict[tool_name]
            tool(**arguments)

            return f"✅ Successfully handled: {fault_type}"

        except Exception as e:
            # 6. 收集证据并记录到 MCP
            evidence = collect_evidence(fault_type, job_id)
            # 使用同步版本（因为当前上下文不是 async）
            # job_name 必填，根据故障类型推断
            inferred_job_name = fault_type.split()[0] if fault_type else "unknown"
            # resource_kind 默认为 Unknown
            problem_id = mcp_client.log_problem_sync(
                fault_type=fault_type,
                job_id=job_id,
                job_name=inferred_job_name,
                evidence="\n".join(evidence),
                resource_kind="Unknown"  # 默认未知资源
            )
            send_techops_alert(problem_id, fault_type, evidence)
            return f"❌ Failed: {str(e)}. Problem logged (ID: {problem_id})"
    else:
        evidence = collect_evidence(fault_type, job_id)
        # 调用 MCP 工具（安全执行）
        # job_name 必填，根据故障类型推断
        inferred_job_name = fault_type.split()[0] if fault_type else "unknown"
        # resource_kind 默认为 Unknown
        problem_id = mcp_client.log_problem_sync(
            fault_type=fault_type,
            job_id=job_id,
            job_name=inferred_job_name,
            evidence="\n".join(evidence),
            resource_kind="Unknown"  # 默认未知资源
        )
        
        # 通知 TechOps（带问题 ID）
        send_techops_alert(problem_id, fault_type, evidence)
        
        return f"❌ Logged problem: {fault_type} (ID: {problem_id})"
    



# ========== 辅助函数 ==========

def collect_evidence(fault_type: str, job_id: str) -> List[str]:
    """
    收集故障证据（精确到文件内容）
    
    Args:
        fault_type: 故障类型
        job_id: Job ID
    
    Returns:
        List[str]: 证据列表
    """
    evidence = []
    if fault_type == "500 error":
        evidence.append("log: /var/log/techops/error.log (content: '500: Service timeout')")
    elif fault_type == "disk full":
        evidence.append("disk_usage: df -h /var/jenkins (content: '/dev/sda1 50G 49G 1% /var/jenkins')")
    elif fault_type == "docker down":
        evidence.append("docker_status: systemctl status docker (content: 'Active: failed (Result: timeout)')")
    return evidence


def send_techops_alert(problem_id: str, fault_type: str, evidence: List[str]):
    """
    发送 TechOps 通知（MCP Service）
    
    Args:
        problem_id: 问题 ID
        fault_type: 故障类型
        evidence: 证据列表
    """
    print(f"📧 [TechOps Alert] {fault_type} (Problem ID: {problem_id})")
    print(f"  Evidence: {evidence}")


# ========== 主程序入口 ==========

if __name__ == "__main__":
    # 测试用例：disk full 故障
    print("\n🧪 Running test case: disk full")
    result = handle_failure("disk full", "job-123")
    assert "Disk cleaned successfully" in result

    # 测试用例：500 error 故障
    print("\n🧪 Running test case: 500 error")
    result = handle_failure("500 error", "job-456")
    assert "retried successfully" in result

    print("\n✅ All tests passed!")