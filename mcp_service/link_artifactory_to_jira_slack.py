"""
关联数据到 Jira 和 Slack

功能：
- 创建 Jira Ticket (TechOps-1256)
- 创建 Slack Threads
- 将 Artifactory 500 问题关联到 Jira 和 Slack
"""

import sqlite3
from datetime import datetime
import uuid

DB_PATH = "mcp_service/problems.db"

def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def generate_id(prefix=""):
    """生成唯一 ID"""
    return f"{prefix}{uuid.uuid4().hex[:8]}"

def create_jira_ticket():
    """创建 Jira Ticket: TechOps-1256"""
    conn = get_connection()
    cursor = conn.cursor()
    
    jira_id = generate_id("jira-")
    jira_key = "TechOps-1256"
    
    # 检查是否已存在
    cursor.execute("SELECT id FROM jira_tickets WHERE key = ?", (jira_key,))
    existing = cursor.fetchone()
    
    if existing:
        print(f"⚠️  Jira Ticket {jira_key} 已存在，跳过创建")
        conn.close()
        return existing['id']
    
    # 创建 Jira Ticket
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        INSERT INTO jira_tickets 
        (id, key, summary, status, created_at, updated_at, reporter, assignee, priority, url, notes, problem_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        jira_id,
        jira_key,
        "Artifactory 500 Internal Server Error - 频繁发生影响构建",
        "In Progress",
        now,
        now,
        "ai-ops-system",
        "techops-team",
        "High",
        "https://jira.company.com/browse/TechOps-1256",
        "Artifactory 服务在过去 5 天内出现 8 次 500 错误，严重影响多个团队的 CI/CD 流水线。需要成立专项小组排查根本原因。",
        0  # problem_count 会通过 trigger 自动更新
    ))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Jira Ticket 创建成功：{jira_key} (ID: {jira_id})")
    return jira_id

def create_slack_threads():
    """创建多个 Slack Threads"""
    conn = get_connection()
    cursor = conn.cursor()
    
    threads_data = [
        {
            "channel": "#techops-alerts",
            "summary": "Artifactory 500 错误告警讨论 - 初步判断为磁盘空间问题",
            "participants_count": 5,
            "is_resolved": False,
            "notes": "参与人员：@john(DevOps), @sarah(SRE), @mike(TechLead)"
        },
        {
            "channel": "#dev-builds",
            "summary": "container-image-build 频繁失败 - Artifactory 返回 500",
            "participants_count": 8,
            "is_resolved": False,
            "notes": "开发团队反馈：每次重试都要等 15 分钟，严重影响开发效率"
        },
        {
            "channel": "#incident-management",
            "summary": "P2 Incident: Artifactory service degradation",
            "participants_count": 12,
            "is_resolved": True,
            "notes": "临时解决方案：重启 Artifactory 服务。长期方案：评估集群化部署"
        }
    ]
    
    created_threads = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for thread_data in threads_data:
        thread_id = generate_id("slack-")
        thread_ts = str(uuid.uuid4())[:10]  # 模拟 Slack timestamp
        
        cursor.execute("""
            INSERT INTO slack_threads 
            (id, channel, message_url, summary, created_at, last_activity, participants_count, is_resolved, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            thread_id,
            thread_data["channel"],
            f"https://company.slack.com/archives/{thread_data['channel'].replace('#', '')}/p{thread_ts}",
            thread_data["summary"],
            now,
            now,
            thread_data["participants_count"],
            1 if thread_data["is_resolved"] else 0,
            thread_data["notes"]
        ))
        
        created_threads.append(thread_id)
        print(f"✅ Slack Thread 创建成功：{thread_data['channel']} - {thread_data['summary'][:50]}...")
    
    conn.commit()
    conn.close()
    
    return created_threads

def link_problems_to_jira(jira_id):
    """将所有 Artifactory 500 问题关联到 Jira Ticket"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 查询所有 Artifactory 500 问题
    cursor.execute("""
        SELECT id, fault_type, job_name
        FROM problems
        WHERE fault_type LIKE '%Artifactory%' 
           OR (resource_kind = 'Artifactory' AND evidence LIKE '%500%')
    """)
    
    problems = cursor.fetchall()
    
    linked_count = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for problem in problems:
        try:
            cursor.execute("""
                INSERT INTO problem_jira_links 
                (problem_id, jira_ticket_id, linked_at, linked_by, note)
                VALUES (?, ?, ?, ?, ?)
            """, (
                problem['id'],
                jira_id,
                now,
                "auto",
                f"Automatically linked: {problem['fault_type']} in {problem['job_name']}"
            ))
            linked_count += 1
        except sqlite3.IntegrityError as e:
            # 可能已经关联过了
            print(f"⚠️  Problem {problem['id']} 已关联到 Jira")
    
    conn.commit()
    conn.close()
    
    print(f"✅ 成功关联 {linked_count}/{len(problems)} 个问题到 Jira Ticket")
    return linked_count

def link_problems_to_slack(slack_thread_ids):
    """将部分问题关联到 Slack Threads"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 查询所有 Artifactory 500 问题
    cursor.execute("""
        SELECT id, fault_type, job_name
        FROM problems
        WHERE fault_type LIKE '%Artifactory%' 
           OR (resource_kind = 'Artifactory' AND evidence LIKE '%500%')
    """)
    
    problems = cursor.fetchall()
    
    linked_count = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 轮询关联到不同的 Slack threads
    for i, problem in enumerate(problems):
        thread_id = slack_thread_ids[i % len(slack_thread_ids)]
        
        try:
            cursor.execute("""
                INSERT INTO problem_slack_links 
                (problem_id, slack_thread_id, linked_at, summary, is_resolved)
                VALUES (?, ?, ?, ?, ?)
            """, (
                problem['id'],
                thread_id,
                now,
                f"Discussed in {thread_id}",
                0
            ))
            linked_count += 1
        except sqlite3.IntegrityError as e:
            print(f"⚠️  Problem {problem['id']} 已关联到 Slack")
    
    conn.commit()
    conn.close()
    
    print(f"✅ 成功关联 {linked_count}/{len(problems)} 个问题到 Slack Threads")
    return linked_count

def verify_links(jira_id, slack_thread_ids):
    """验证关联关系"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("验证关联关系")
    print("="*80)
    
    # 1. 验证 Jira Ticket
    cursor.execute("""
        SELECT key, summary, status, problem_count
        FROM jira_tickets
        WHERE id = ?
    """, (jira_id,))
    
    jira = cursor.fetchone()
    if jira:
        print(f"\n✅ Jira Ticket: {jira['key']}")
        print(f"   摘要：{jira['summary']}")
        print(f"   状态：{jira['status']}")
        print(f"   关联问题数：{jira['problem_count']}")
    
    # 2. 验证关联的问题
    cursor.execute("""
        SELECT p.id, p.fault_type, p.job_name, p.timestamp
        FROM problems p
        INNER JOIN problem_jira_links pj ON p.id = pj.problem_id
        WHERE pj.jira_ticket_id = ?
        ORDER BY p.timestamp DESC
    """, (jira_id,))
    
    problems = cursor.fetchall()
    print(f"\n📊 关联到 Jira 的问题 ({len(problems)} 个):")
    for p in problems[:5]:  # 只显示前 5 个
        print(f"   • {p['id']} - {p['fault_type']} ({p['job_name']})")
    if len(problems) > 5:
        print(f"   ... 还有 {len(problems) - 5} 个")
    
    # 3. 验证 Slack Threads
    print(f"\n📊 Slack Threads:")
    for thread_id in slack_thread_ids:
        cursor.execute("""
            SELECT channel, summary, participants_count, is_resolved
            FROM slack_threads
            WHERE id = ?
        """, (thread_id,))
        
        thread = cursor.fetchone()
        if thread:
            resolved_mark = "✅" if thread['is_resolved'] else "🔴"
            print(f"   {resolved_mark} {thread['channel']}: {thread['summary'][:50]}... ({thread['participants_count']} 人参与)")
    
    # 4. 使用视图验证
    cursor.execute("""
        SELECT resource_kind, fault_type, total_problems, jira_count, slack_count
        FROM v_problem_summary
        WHERE fault_type LIKE '%Artifactory%'
    """)
    
    summary = cursor.fetchone()
    if summary:
        print(f"\n📈 汇总视图 (v_problem_summary):")
        print(f"   故障类型：{summary['fault_type']}")
        print(f"   总问题数：{summary['total_problems']}")
        print(f"   关联 Jira: {summary['jira_count']}")
        print(f"   关联 Slack: {summary['slack_count']}")
    
    conn.close()
    print("\n" + "="*80)

def main():
    """主函数"""
    print("="*80)
    print("创建 Jira Ticket 和 Slack Threads 并关联问题")
    print("="*80)
    print()
    
    # Step 1: 创建 Jira Ticket
    print("Step 1: 创建 Jira Ticket (TechOps-1256)...")
    jira_id = create_jira_ticket()
    print()
    
    # Step 2: 创建 Slack Threads
    print("Step 2: 创建 Slack Threads...")
    slack_thread_ids = create_slack_threads()
    print()
    
    # Step 3: 关联问题到 Jira
    print("Step 3: 关联 Artifactory 500 问题到 Jira...")
    link_problems_to_jira(jira_id)
    print()
    
    # Step 4: 关联问题到 Slack
    print("Step 4: 关联部分问题到 Slack Threads...")
    link_problems_to_slack(slack_thread_ids)
    print()
    
    # Step 5: 验证关联关系
    print("Step 5: 验证关联关系...")
    verify_links(jira_id, slack_thread_ids)
    
    print("\n✅ 所有操作完成！")
    print("="*80)

if __name__ == "__main__":
    main()
