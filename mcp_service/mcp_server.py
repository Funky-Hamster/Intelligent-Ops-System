# /vsi-ai-om/mcp_service/mcp_server.py
from mcp.server.fastmcp import FastMCP
import sqlite3
import uuid
import time
from typing import List, Dict
import os
import re
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 输入验证函数
def validate_input(value: str, max_length: int = 200) -> bool:
    """
    验证输入安全性
    
    Args:
        value: 待验证的字符串
        max_length: 最大长度限制
        
    Returns:
        bool: 是否通过验证
    """
    if not value or not isinstance(value, str) or len(value) > max_length:
        return False
    # 只允许字母、数字、下划线、连字符、空格、中文
    if not re.match(r'^[a-zA-Z0-9_\-\u4e00-\u9fa5\s]+$', value):
        return False
    return True

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "mcp_service", "problems.db")
# 确保数据库目录存在
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# 初始化数据库
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS problems
             (id TEXT PRIMARY KEY, 
              fault_type TEXT, 
              job_name TEXT NOT NULL,  -- Job 名称（如：build, test, deploy）
              job_id TEXT,
              timestamp TEXT,
              evidence TEXT)''')
conn.commit()
conn.close()

mcp = FastMCP("VSI DevOps MCP Service")

@mcp.tool()
def health_check() -> Dict:
    """健康检查（MCP 标准工具）"""
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "database": "connected"
    }

@mcp.tool()
def log_problem(fault_type: str, 
                job_id: str, 
                job_name: str,
                evidence: str) -> str:
    """记录无法解决的故障（MCP 标准工具）"""
    logger.info(f"📝 Logging problem: {fault_type} for job={job_name}, id={job_id}")
    
    # 完整的安全验证
    if not validate_input(fault_type, 100):
        raise ValueError("Invalid fault_type: must be alphanumeric with underscores/hyphens, max 100 chars")
    if not validate_input(job_id, 100):
        raise ValueError("Invalid job_id: must be alphanumeric with underscores/hyphens, max 100 chars")
    if not validate_input(job_name, 150):
        raise ValueError("Invalid job_name: must be alphanumeric with underscores/hyphens, max 150 chars")
    if not validate_input(evidence, 5000):
        raise ValueError("Invalid evidence: exceeds max length of 5000 chars")
    
    # 生成唯一 ID
    problem_id = f"prob-{uuid.uuid4().hex[:8]}"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # 使用参数化查询防止 SQL 注入
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO problems VALUES (?, ?, ?, ?, ?, ?)",
              (problem_id, fault_type, job_name, job_id, timestamp, evidence))
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Problem logged: {problem_id}")
    return f"Problem logged: {problem_id}"

@mcp.tool()
def search_problems(fault_type: str = None, 
                   start_time: str = None, 
                   end_time: str = None) -> List[Dict]:
    """按类型/时间范围查询历史问题（MCP 标准工具）"""
    query = "SELECT * FROM problems WHERE 1=1"
    params = []
    
    if fault_type:
        query += " AND fault_type = ?"
        params.append(fault_type)
    
    if start_time:
        query += " AND timestamp >= ?"
        params.append(start_time)
    
    if end_time:
        query += " AND timestamp <= ?"
        params.append(end_time)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, params)
    results = c.fetchall()
    conn.close()
    
    # 格式化为标准返回
    return [
        {
            "id": r[0],
            "fault_type": r[1],
            "job_name": r[2],
            "job_id": r[3],
            "timestamp": r[4],
            "evidence": r[5]
        } for r in results
    ]

@mcp.resource("problem://{problem_id}")
def get_problem(problem_id: str) -> str:
    """获取单个问题的详细信息"""
    import json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM problems WHERE id = ?", (problem_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return json.dumps({
            "id": result[0],
            "fault_type": result[1],
            "job_name": result[2],
            "job_id": result[3],
            "timestamp": result[4],
            "evidence": result[5]
        }, ensure_ascii=False)
    return "Problem not found"

if __name__ == "__main__":
    print("🚀 MCP Service starting at http://localhost:8000")
    mcp.run()