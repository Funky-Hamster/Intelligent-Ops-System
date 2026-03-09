# /vsi-ai-om/mcp_service/database.py
"""
数据库管理模块

功能：
- 数据库初始化
- 迁移执行
- 连接管理
"""

import sqlite3
from pathlib import Path
from typing import Optional


def get_db_path() -> Path:
    """获取数据库文件路径"""
    project_root = Path(__file__).parent.parent
    return project_root / "mcp_service" / "problems.db"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    获取数据库连接
    
    Args:
        db_path: 数据库文件路径（默认：problems.db）
    
    Returns:
        sqlite3.Connection: 数据库连接
    """
    if db_path is None:
        db_path = get_db_path()
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 支持字典访问
    return conn


def init_database(db_path: Optional[Path] = None) -> bool:
    """
    初始化数据库（如果不存在则创建）
    
    Args:
        db_path: 数据库文件路径
    
    Returns:
        bool: 是否成功
    """
    if db_path is None:
        db_path = get_db_path()
    
    try:
        # 读取初始化脚本
        migration_script = Path(__file__).parent / "migrations" / "000_init_database.sql"
        
        if not migration_script.exists():
            print(f"❌ 迁移脚本不存在：{migration_script}")
            return False
        
        with open(migration_script, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # 执行迁移
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.executescript(sql_script)
        conn.commit()
        conn.close()
        
        print(f"✅ 数据库初始化成功：{db_path}")
        print("📋 创建内容:")
        print("   • 表：problems, jira_tickets, slack_threads")
        print("   • 关联表：problem_jira_links, problem_slack_links")
        print("   • 索引：14 个")
        print("   • 视图：3 个 (v_problem_summary, v_jira_summary, v_slack_summary)")
        print("   • 触发器：2 个")
        return True
        
    except Exception as e:
        print(f"❌ 数据库初始化失败：{str(e)}")
        return False


def run_migration(migration_name: str, db_path: Optional[Path] = None) -> bool:
    """
    执行指定迁移脚本
    
    Args:
        migration_name: 迁移脚本名称（如 001_add_tracking_tables.sql）
        db_path: 数据库文件路径
    
    Returns:
        bool: 是否成功
    """
    if db_path is None:
        db_path = get_db_path()
    
    try:
        # 读取迁移脚本
        migration_script = Path(__file__).parent / "migrations" / migration_name
        
        if not migration_script.exists():
            print(f"❌ 迁移脚本不存在：{migration_script}")
            return False
        
        with open(migration_script, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # 执行迁移
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.executescript(sql_script)
        conn.commit()
        conn.close()
        
        print(f"✅ 迁移执行成功：{migration_name}")
        return True
        
    except Exception as e:
        print(f"❌ 迁移执行失败：{str(e)}")
        return False


if __name__ == "__main__":
    # 测试用：初始化数据库
    init_database()
