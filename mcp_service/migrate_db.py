# /vsi-ai-om/mcp_service/migrate_db.py
"""
数据库迁移工具

使用方式:
    python -m mcp_service.migrate_db
"""

import sqlite3
import os
from pathlib import Path


def run_migration(db_path: str = None):
    """
    执行数据库迁移
    
    Args:
        db_path: 数据库文件路径（默认：problems.db）
    """
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    if db_path is None:
        db_path = project_root / "mcp_service" / "problems.db"
    
    # 读取迁移脚本
    migration_script = Path(__file__).parent / "migrations" / "001_add_tracking_tables.sql"
    
    if not migration_script.exists():
        print(f"❌ 迁移脚本不存在：{migration_script}")
        return False
    
    with open(migration_script, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    # 执行迁移
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 执行所有 SQL 语句
        cursor.executescript(sql_script)
        
        conn.commit()
        conn.close()
        
        print(f"✅ 数据库迁移成功：{db_path}")
        print("📋 新增表:")
        print("   • jira_tickets")
        print("   • slack_threads")
        print("   • problem_jira_links")
        print("   • problem_slack_links")
        print("📋 新增视图:")
        print("   • v_problem_summary")
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败：{str(e)}")
        return False


if __name__ == "__main__":
    run_migration()
