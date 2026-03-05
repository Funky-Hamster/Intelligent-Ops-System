# /vsi-ai-om/mcp_service/mcp_client.py
"""
MCP (Model Context Protocol) 客户端
用于与 MCP Server 进行通信，调用标准工具
"""
import asyncio
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from typing import List, Dict
import json
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPClient:
    """MCP 标准客户端（异步实现）"""
    
    def __init__(self, server_script: str = "mcp_service/mcp_server.py"):
        """
        初始化 MCP 客户端
        
        Args:
            server_script: MCP Server 脚本路径
        """
        self.server_params = StdioServerParameters(
            command="python",
            args=[server_script]
        )
    
    async def log_problem(self, 
                         fault_type: str, 
                         job_id: str, 
                         job_name: str,
                         evidence: str) -> str:
        """
        记录故障问题到 MCP Server
        
        Args:
            fault_type: 故障类型
            job_id: Job ID
            job_name: Job 名称（必填，如 build/test/deploy）
            evidence: 证据信息
            
        Returns:
            Problem ID
        """
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "log_problem",
                    arguments={
                        "fault_type": fault_type,
                        "job_id": job_id,
                        "job_name": job_name,
                        "evidence": evidence
                    }
                )
                return result.content[0].text
    
    async def search_problems(self, 
                             fault_type: Optional[str] = None,
                             start_time: Optional[str] = None,
                             end_time: Optional[str] = None) -> List[Dict]:
        """
        查询历史故障问题
        
        Args:
            fault_type: 故障类型（可选）
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
            
        Returns:
            问题列表
        """
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "search_problems",
                    arguments={
                        "fault_type": fault_type,
                        "start_time": start_time,
                        "end_time": end_time
                    }
                )
                # 安全的 JSON 解析，添加异常处理
                try:
                    return json.loads(result.content[0].text)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON response: {str(e)}")
                    raise ValueError(f"Invalid JSON response from server: {str(e)}")
                except IndexError:
                    logger.error("Empty response from server")
                    raise ValueError("Empty response from server")
    
    # 同步包装器（方便在不支持 async 的地方使用）
    def log_problem_sync(self, 
                        fault_type: str, 
                        job_id: str, 
                        job_name: str,
                        evidence: str) -> str:
        """同步版本的 log_problem"""
        return asyncio.run(self.log_problem(
            fault_type=fault_type,
            job_id=job_id,
            job_name=job_name,
            evidence=evidence
        ))
    
    def search_problems_sync(self, 
                            fault_type: Optional[str] = None,
                            start_time: Optional[str] = None,
                            end_time: Optional[str] = None) -> List[Dict]:
        """同步版本的 search_problems"""
        return asyncio.run(self.search_problems(
            fault_type=fault_type,
            start_time=start_time,
            end_time=end_time
        ))