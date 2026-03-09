"""
规则引擎 - 基于关键词的规则匹配
优先于 LLM 进行决策
"""
from typing import Optional, Dict, Any


class RuleEngine:
    """规则引擎"""
    
    def __init__(self):
        # 定义规则：关键词 -> (工具名，置信度)
        self.rules = {
            # Docker 相关
            "docker daemon": ("restart_docker", 0.90),
            "docker.sock": ("restart_docker", 0.90),
            "docker service": ("restart_docker", 0.85),
            "restart docker": ("restart_docker", 0.85),
            
            # 磁盘空间相关
            "no space left": ("clean_disk", 0.95),
            "disk full": ("clean_disk", 0.90),
            "disk space": ("clean_disk", 0.80),
            
            # NPM 相关
            "npm err!": ("retry_job", 0.85),
            "npm.*err!": ("retry_job", 0.85),
            "elfecycle": ("retry_job", 0.90),
            "npm.*install.*failed": ("retry_job", 0.85),
            "errno": ("retry_job", 0.85),
            
            # Maven/Java 相关（OOM 不应该重试）
            "outofmemoryerror": ("log_to_mcp", 0.90),
            "gc overhead": ("log_to_mcp", 0.85),
            "heap space": ("log_to_mcp", 0.85),
            "permgen": ("log_to_mcp", 0.85),
            
            # 网络/临时问题相关
            "timeout": ("retry_job", 0.60),  # 降低优先级
            "transient": ("retry_job", 0.75),
            "temporary": ("retry_job", 0.75),
            "network instability": ("retry_job", 0.80),
            "retry": ("retry_job", 0.65),
            "re-run": ("retry_job", 0.70),
            "connection refused": ("retry_job", 0.70),
            "connection timed out": ("retry_job", 0.75),
            
            # HTTP 错误码相关
            "http.*401": ("retry_job", 0.70),
            "401": ("retry_job", 0.65),
            "unauthorized": ("retry_job", 0.70),
            "http.*403": ("retry_job", 0.65),
            "403": ("retry_job", 0.60),
            "forbidden": ("retry_job", 0.65),
            "http.*500": ("retry_job", 0.75),
            "internal server error": ("retry_job", 0.75),
            "http.*502": ("retry_job", 0.80),
            "bad gateway": ("retry_job", 0.80),
            "http.*503": ("retry_job", 0.80),
            "service unavailable": ("retry_job", 0.80),
            
            # 认证相关
            "authentication failed": ("retry_job", 0.70),
            "credential.*expired": ("retry_job", 0.65),
            
            # DNS/网络解析
            "dns resolution failed": ("retry_job", 0.75),
            "network unreachable": ("retry_job", 0.70),
            
            # Kubernetes 相关
            "pod.*failed": ("log_to_mcp", 0.85),
            "pod failed": ("log_to_mcp", 0.85),
            "crashloopbackoff": ("log_to_mcp", 0.90),
            "imagepullbackoff": ("retry_job", 0.75),
            "errimagepull": ("retry_job", 0.75),
            "evicted": ("log_to_mcp", 0.85),
            "oom killed": ("log_to_mcp", 0.90),
            "pending pod": ("log_to_mcp", 0.80),
            "container creating": ("log_to_mcp", 0.75),
            "readiness probe failed": ("retry_job", 0.70),
            "liveness probe failed": ("retry_job", 0.70),
            
            # 数据库连接相关
            "mysql.*connection.*refused": ("restart_mysql", 0.85),
            "mysql connection refused": ("restart_mysql", 0.85),
            "mysql.*connection.*timeout": ("retry_job", 0.75),
            "mysql connection timeout": ("retry_job", 0.75),
            "mysql timeout": ("retry_job", 0.75),
            "redis.*connection.*refused": ("restart_redis", 0.85),
            "redis connection refused": ("restart_redis", 0.85),
            "redis.*connection.*timeout": ("retry_job", 0.75),
            "redis connection timeout": ("retry_job", 0.75),
            "redis timeout": ("retry_job", 0.75),
            "database connection failed": ("retry_job", 0.70),
            
            # Git/版本控制相关
            "git.*push.*failed": ("retry_git", 0.70),
            "git push failed": ("retry_git", 0.70),
            "push failed": ("retry_git", 0.65),
            "git.*pull.*failed": ("retry_git", 0.70),
            "git pull failed": ("retry_git", 0.70),
            "pull failed": ("retry_git", 0.65),
            "remote.*repository.*not found": ("log_to_mcp", 0.85),
            "repository not found": ("log_to_mcp", 0.85),
            "authentication failed.*git": ("retry_git", 0.70),
            "authentication failed for git": ("retry_git", 0.70),
            "authentication failed": ("retry_job", 0.65),
            "merge conflict": ("log_to_mcp", 0.90),
            
            # 资源限制相关
            "too many open files": ("log_to_mcp", 0.90),
            "file descriptor": ("log_to_mcp", 0.85),
            "ulimit": ("log_to_mcp", 0.75),
            "cpu.*throttling": ("log_to_mcp", 0.80),
            "cpu throttling": ("log_to_mcp", 0.80),
            "throttling": ("log_to_mcp", 0.70),
            "memory limit exceeded": ("log_to_mcp", 0.85),
            "resource quota exceeded": ("log_to_mcp", 0.80),
            
            # SSL/TLS 证书相关
            "ssl.*certificate.*verify failed": ("retry_job", 0.70),
            "ssl certificate verify failed": ("retry_job", 0.70),
            "certificate verify failed": ("retry_job", 0.70),
            "ssl verify failed": ("retry_job", 0.70),
            "certificate verify": ("retry_job", 0.65),
            "certificate expired": ("log_to_mcp", 0.90),
            "ssl handshake failed": ("retry_job", 0.75),
            
            # 权限相关
            "permission denied": ("log_to_mcp", 0.85),
            "access denied": ("log_to_mcp", 0.80),
            "unauthorized access": ("log_to_mcp", 0.80),
        }
    
    def match(self, fault_type: str, rag_solutions: str = "") -> Optional[Dict[str, Any]]:
        """
        匹配规则
        
        Args:
            fault_type: 故障类型描述
            rag_solutions: RAG 检索到的解决方案
            
        Returns:
            Dict: {"tool": tool_name, "confidence": score, "reason": reason} 或 None
        """
        text_to_match = f"{fault_type} {rag_solutions}".lower()
        
        best_match = None
        best_confidence = 0.0
        
        for keyword, (tool_name, confidence) in self.rules.items():
            if keyword.lower() in text_to_match:
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = {
                        "tool": tool_name,
                        "confidence": confidence,
                        "reason": f"Matched keyword: '{keyword}'"
                    }
        
        # 只有置信度超过阈值才返回
        if best_confidence >= 0.7:
            return best_match
        
        return None
    
    def should_use_llm(self, match_result: Optional[Dict]) -> bool:
        """判断是否需要使用 LLM"""
        if match_result is None:
            return True  # 没有匹配到规则，需要 LLM
        
        if match_result["confidence"] < 0.85:
            return True  # 置信度不够高，需要 LLM 确认
        
        return False  # 规则匹配度高，直接执行


# 测试
if __name__ == "__main__":
    engine = RuleEngine()
    
    test_cases = [
        "Cannot connect to the Docker daemon",
        "No space left on device",
        "Connection timeout",
        "Maven compilation failed"
    ]
    
    for fault in test_cases:
        result = engine.match(fault)
        if result:
            print(f"✅ {fault[:50]} -> {result['tool']} (conf: {result['confidence']:.2f})")
        else:
            print(f"❌ {fault[:50]} -> No match (need LLM)")
