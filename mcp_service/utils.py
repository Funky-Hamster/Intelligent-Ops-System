# /vsi-ai-om/mcp_service/utils.py
"""
公共工具函数

提供全局使用的辅助函数
"""

import re


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


def validate_resource_kind(resource_kind: str) -> bool:
    """
    验证资源类型是否合法
    
    Args:
        resource_kind: 资源类型
        
    Returns:
        bool: 是否合法
    """
    allowed_kinds = {"Jenkins", "Artifactory", "DRP", "SRO", "LabOps", "GitHub", "IT", "Unknown"}
    return resource_kind in allowed_kinds
