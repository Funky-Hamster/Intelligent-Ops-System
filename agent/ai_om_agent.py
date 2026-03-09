# /vsi-ai-om/agent/ai_om_agent.py
"""
AI 运维 Agent - 故障自动修复

功能：
- 基于 RAG 检索解决方案
- 自动执行修复操作（重试 Job、清理磁盘、重启 Docker）
- 记录无法解决的问题到 MCP Service
"""
from typing import List
from pathlib import Path

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

from rag.hybrid_retriever import HybridRetriever_RRF as HybridRetriever
from rag.build_rag import build_rag
from rag.cascade_retriever import create_cascade_retriever, KnowledgeBaseManager  # 新增级联检索器
from mcp_service.mcp_client import MCPClient
from config import Config
from agent.prompt import PROMPT
from agent.rule_engine import RuleEngine

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
# 使用级联式 RAG+LLM 架构
print("正在初始化级联检索器...")
cascade_retriever = create_cascade_retriever()
kb_manager = KnowledgeBaseManager(cascade_retriever)
print("✅ 级联检索器初始化成功 (RAG + LLM)")


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
        # 记录到 MCP（TechOps 服务可能有问题）
        log_retry_failure_sync(
            job_id=job_id,
            job_name="build",  # 默认假设是 build job
            retry_action="retry_job",
            failure_reason=str(e),
            suggestion="TechOps service may be unavailable. Check Jenkins API connectivity."
        )
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


@tool
def search_solution(error_message: str):
    """
    使用 RAG+LLM 级联检索搜索故障解决方案
    
    Args:
        error_message: Jenkins 错误日志或描述
    
    Returns:
        str: 解决方案（来自 RAG 或 LLM）
    """
    logger.info(f"🔍 [search_solution] Searching for: {error_message[:50]}...")
    
    # 使用级联检索
    result = cascade_retriever.retrieve(error_message, return_details=True)
    
    if result['source'] == 'RAG':
        logger.info(f"✅ Found in RAG (confidence: {result['confidence']})")
        return f"【知识库方案】\n{result['answer']}\n\n置信度：{result['confidence']}\nRRF 分数：{result['rag_score']:.6f}"
    else:
        logger.info(f"🤖 Generated by LLM (fallback)")
        return f"【AI 推理建议】\n{result['answer']}\n\n说明：{result['llm_note']}"


@tool
def clear_maven_cache():
    """
    清理 Maven 本地仓库缓存（解决依赖下载失败问题）
    
    安全操作：仅删除 .lastUpdated 和 .repositories 文件
    
    Returns:
        str: 成功消息
    
    Raises:
        Exception: SSH 连接超时或执行失败
    """
    logger.info("🧹 [clear_maven_cache] Cleaning Maven cache (.lastUpdated and .repositories files)")
    
    ssh_key_path = os.getenv("JENKINS_SSH_KEY_PATH", "/var/jenkins/ssh_key")
    ssh_user = os.getenv("JENKINS_SSH_USER", "jenkins-agent")
    ssh_host = os.getenv("JENKINS_SSH_HOST", "agent-host")
    known_hosts_path = os.getenv("JENKINS_KNOWN_HOSTS_PATH", "/var/jenkins/known_hosts")
    
    try:
        cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={known_hosts_path}",
            "-o", "ConnectTimeout=30",
            f"{ssh_user}@{ssh_host}",
            "find",
            "/var/jenkins/.m2/repository",
            "-name",
            "*.lastUpdated",
            "-o",
            "-name",
            "*.repositories",
            "-delete"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
        return "Maven cache cleaned successfully (.lastUpdated and .repositories files removed)"
    except subprocess.TimeoutExpired:
        logger.error("SSH command timed out after 120 seconds")
        raise Exception("SSH connection timed out")
    except Exception as e:
        logger.error(f"Clear Maven cache failed: {str(e)}")
        raise


@tool
def clear_npm_cache():
    """
    清理 NPM 缓存（解决依赖安装失败问题）
    
    执行：npm cache clean --force
    
    Returns:
        str: 成功消息
    
    Raises:
        Exception: SSH 连接超时或执行失败
    """
    logger.info("🧹 [clear_npm_cache] Cleaning NPM cache")
    
    ssh_key_path = os.getenv("JENKINS_SSH_KEY_PATH", "/var/jenkins/ssh_key")
    ssh_user = os.getenv("JENKINS_SSH_USER", "jenkins-agent")
    ssh_host = os.getenv("JENKINS_SSH_HOST", "agent-host")
    known_hosts_path = os.getenv("JENKINS_KNOWN_HOSTS_PATH", "/var/jenkins/known_hosts")
    
    try:
        cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={known_hosts_path}",
            "-o", "ConnectTimeout=30",
            f"{ssh_user}@{ssh_host}",
            "npm",
            "cache",
            "clean",
            "--force"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
        return "NPM cache cleaned successfully"
    except subprocess.TimeoutExpired:
        logger.error("SSH command timed out after 120 seconds")
        raise Exception("SSH connection timed out")
    except Exception as e:
        logger.error(f"Clear NPM cache failed: {str(e)}")
        raise


@tool
def restart_jenkins_agent():
    """
    重启 Jenkins Agent 服务
    
    适用于：Agent 失联、JNLP 连接失败等场景
    
    Returns:
        str: 成功消息
    
    Raises:
        Exception: SSH 连接超时或执行失败
    """
    logger.info("🔄 [restart_jenkins_agent] Restarting Jenkins Agent service")
    
    ssh_key_path = os.getenv("JENKINS_SSH_KEY_PATH", "/var/jenkins/ssh_key")
    ssh_user = os.getenv("JENKINS_SSH_USER", "jenkins-agent")
    ssh_host = os.getenv("JENKINS_SSH_HOST", "agent-host")
    known_hosts_path = os.getenv("JENKINS_KNOWN_HOSTS_PATH", "/var/jenkins/known_hosts")
    
    try:
        cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={known_hosts_path}",
            "-o", "ConnectTimeout=30",
            f"{ssh_user}@{ssh_host}",
            "systemctl",
            "restart",
            "jenkins-agent"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        return "Jenkins Agent restarted successfully"
    except subprocess.TimeoutExpired:
        logger.error("SSH command timed out after 60 seconds")
        raise Exception("SSH connection timed out")
    except Exception as e:
        logger.error(f"Restart Jenkins Agent failed: {str(e)}")
        raise


@tool
def fix_docker_permissions():
    """
    修复 Docker Socket 权限问题
    
    执行：chmod 666 /var/run/docker.sock
    
    Returns:
        str: 成功消息
    
    Raises:
        Exception: SSH 连接超时或执行失败
    """
    logger.info("🔧 [fix_docker_permissions] Fixing Docker socket permissions")
    
    ssh_key_path = os.getenv("JENKINS_SSH_KEY_PATH", "/var/jenkins/ssh_key")
    ssh_user = os.getenv("JENKINS_SSH_USER", "jenkins-agent")
    ssh_host = os.getenv("JENKINS_SSH_HOST", "agent-host")
    known_hosts_path = os.getenv("JENKINS_KNOWN_HOSTS_PATH", "/var/jenkins/known_hosts")
    
    try:
        cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={known_hosts_path}",
            "-o", "ConnectTimeout=30",
            f"{ssh_user}@{ssh_host}",
            "sudo",
            "chmod",
            "666",
            "/var/run/docker.sock"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        return "Docker socket permissions fixed successfully (chmod 666)"
    except subprocess.TimeoutExpired:
        logger.error("SSH command timed out after 60 seconds")
        raise Exception("SSH connection timed out")
    except Exception as e:
        logger.error(f"Fix Docker permissions failed: {str(e)}")
        raise


@tool
def cleanup_workspace():
    """
    清理 Jenkins 工作空间中的旧构建文件
    
    保留最近 3 次构建，删除更早的 artifacts
    
    Returns:
        str: 成功消息
    
    Raises:
        Exception: SSH 连接超时或执行失败
    """
    logger.info("🧹 [cleanup_workspace] Cleaning old workspace builds (keeping last 3)")
    
    ssh_key_path = os.getenv("JENKINS_SSH_KEY_PATH", "/var/jenkins/ssh_key")
    ssh_user = os.getenv("JENKINS_SSH_USER", "jenkins-agent")
    ssh_host = os.getenv("JENKINS_SSH_HOST", "agent-host")
    known_hosts_path = os.getenv("JENKINS_KNOWN_HOSTS_PATH", "/var/jenkins/known_hosts")
    
    try:
        # 查找并删除旧的构建目录（保留最近的 3 个）
        cmd = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={known_hosts_path}",
            "-o", "ConnectTimeout=30",
            f"{ssh_user}@{ssh_host}",
            "bash",
            "-c",
            "cd /var/jenkins/workspace && ls -dt */ | tail -n +4 | xargs rm -rf"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
        return "Workspace cleaned successfully (kept last 3 builds)"
    except subprocess.TimeoutExpired:
        logger.error("SSH command timed out after 120 seconds")
        raise Exception("SSH connection timed out")
    except Exception as e:
        logger.error(f"Cleanup workspace failed: {str(e)}")
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

tools = [
    retry_job,
    clean_disk,
    restart_docker,
    search_solution,
    clear_maven_cache,
    clear_npm_cache,
    restart_jenkins_agent,
    fix_docker_permissions,
    cleanup_workspace
]
tools_dict = {t.name: t for t in tools}

# 添加 log_to_mcp 作为虚拟工具（用于规则引擎）
def log_to_mcp_placeholder():
    """Placeholder for MCP logging (handled separately)"""
    raise ValueError("Should use mcp_client.log_problem_sync directly")

# 扩展工具列表（支持新规则）
extended_tools = [
    # K8s 相关 - 暂时都用 log_to_mcp
    # 数据库相关 - 暂时都用 log_to_mcp  
    # Git 相关 - 暂时都用 log_to_mcp
]

# 初始化规则引擎
rule_engine = RuleEngine()

# MCP Service 客户端
mcp_client = MCPClient("mcp_service/mcp_server.py")


def log_retry_failure_sync(job_id: str, job_name: str, retry_action: str, failure_reason: str, suggestion: str = None):
    """
    同步记录重试失败案例到 MCP（用于追踪 TechOps 服务问题）
    
    Args:
        job_id: Job ID
        job_name: Job 名称
        retry_action: 重试操作
        failure_reason: 失败原因
        suggestion: AI 建议
    """
    try:
        # 使用 asyncio 运行异步方法
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            problem_id = loop.run_until_complete(
                mcp_client.log_retry_failure(job_id, job_name, retry_action, failure_reason, suggestion)
            )
            logger.info(f"✅ Retry failure logged to MCP: {problem_id}")
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Failed to log retry failure to MCP: {str(e)}")


# ========== 核心业务逻辑 ==========

def handle_failure(fault_type: str, job_id: str) -> str:
    """
    故障处理闭环（阶段 1 + 阶段 2：规则优化 + LLM 验证）
    
    Args:
        fault_type: 故障类型
        job_id: Job ID
    
    Returns:
        str: 处理结果
    """
    # 1. RAG 检索解决方案
    results = hybrid_retriever.get_relevant_documents(fault_type)
    
    # 格式化 RAG 结果为字符串
    rag_context = ""
    if results:
        for i, result in enumerate(results, 1):
            if isinstance(result, dict):
                text = result.get('text', '')
                score = result.get('score', 'N/A')
                rag_context += f"[Solution {i}] (Score: {score})\n{text}\n\n"
            else:
                rag_context += f"[Solution {i}] {str(result)}\n\n"
    else:
        rag_context = "No relevant solutions found in RAG database."
    
    # ========== 阶段 1: 规则引擎优先 ==========
    print("\n🔍 [Phase 1] Rule Engine Matching...")
    rule_match = rule_engine.match(fault_type, rag_context)
    
    if rule_match:
        print(f"✅ Matched rule: {rule_match['tool']} (confidence: {rule_match['confidence']:.2f})")
        print(f"   Reason: {rule_match['reason']}")
        
        # 高置信度规则直接执行
        if rule_match['confidence'] >= 0.85:
            print(f"⚡ High confidence, executing tool directly...\n")
            try:
                # 特殊处理 log_to_mcp
                if rule_match['tool'] == 'log_to_mcp':
                    print(f"📝 Rule suggests logging to MCP (needs manual intervention)\n")
                    raise ValueError("Rule engine suggests manual intervention")
                
                # 检查工具是否在 tools_dict 中，不在则记录到 MCP
                if rule_match['tool'] not in tools_dict:
                    print(f"⚠️ Tool '{rule_match['tool']}' not implemented, logging to MCP...\n")
                    raise ValueError(f"Tool '{rule_match['tool']}' not available")
                
                tool = tools_dict[rule_match['tool']]
                if rule_match['tool'] == 'retry_job':
                    result = tool.invoke({"job_id": job_id, "attempts": 3})
                elif rule_match['tool'] in ['clean_disk', 'restart_docker']:
                    result = tool.invoke({})
                return f"✅ [Rule Engine] {rule_match['tool']}: {result}"
            except Exception as e:
                print(f"❌ Tool execution failed: {str(e)}")
                # Fall through to LLM or MCP logging
        else:
            print(f"🤔 Medium confidence, will verify with LLM...\n")
    else:
        print(f"❌ No matching rules found\n")
    
    # ========== 阶段 2: LLM 验证 ==========
    print("🧠 [Phase 2] LLM Decision Making...")
    
    # 如果规则引擎没有高置信度匹配，使用 LLM
    try:
        from langchain_core.prompts import PromptTemplate
        
        prompt_template = PromptTemplate(
            template=PROMPT.template,
            input_variables=["fault_type", "job_id", "rag_solutions"]
        )
        
        formatted_prompt = prompt_template.format(
            fault_type=fault_type,
            job_id=job_id,
            rag_solutions=rag_context
        )
        
        # 调用 LLM
        response_text = llm.invoke(formatted_prompt)
        
        # 解析 JSON 响应
        import json
        response = json.loads(response_text)
        
        # 验证 Agent 输出格式
        if not isinstance(response, dict) or "name" not in response:
            raise ValueError("Invalid agent response format")
        
        # 执行工具调用
        tool_name = response["name"]
        arguments = response.get("arguments", {})
        
        if tool_name not in tools_dict:
            raise ValueError(f"Unknown tool: {tool_name}")
                    
        tool = tools_dict[tool_name]
        result = tool.invoke(arguments)
        
        return f"✅ [LLM] Successfully handled: {fault_type}"
        
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