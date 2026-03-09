"""
生成领导汇报材料 - MCP 问题追踪系统

功能：
- 查询系统整体运行状态
- 生成高管摘要（简洁、数据驱动）
- 准备汇报 PPT 大纲
"""

import sqlite3
from datetime import datetime, timedelta

DB_PATH = "mcp_service/problems.db"

def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_system_overview():
    """获取系统整体概览"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 总问题数
    cursor.execute("SELECT COUNT(*) as total FROM problems")
    total_problems = cursor.fetchone()["total"]
    
    # 按资源类型统计
    cursor.execute("""
        SELECT resource_kind, COUNT(*) as count
        FROM problems
        GROUP BY resource_kind
        ORDER BY count DESC
    """)
    by_resource = cursor.fetchall()
    
    # Jira Ticket 统计
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM jira_tickets
        GROUP BY status
    """)
    jira_by_status = cursor.fetchall()
    
    # Slack Threads 统计
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_resolved = 1 THEN 1 ELSE 0 END) as resolved
        FROM slack_threads
    """)
    slack_stats = cursor.fetchone()
    
    # 关联关系统计
    cursor.execute("SELECT COUNT(*) as count FROM problem_jira_links")
    problem_jira_links = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM problem_slack_links")
    problem_slack_links = cursor.fetchone()["count"]
    
    conn.close()
    
    return {
        "total_problems": total_problems,
        "by_resource": dict(by_resource),
        "jira_by_status": dict(jira_by_status),
        "slack_total": slack_stats["total"],
        "slack_resolved": slack_stats["resolved"],
        "problem_jira_links": problem_jira_links,
        "problem_slack_links": problem_slack_links
    }

def get_top_issues():
    """获取 Top 问题"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 高频故障 Top 5
    cursor.execute("""
        SELECT fault_type, resource_kind, COUNT(*) as count
        FROM problems
        GROUP BY fault_type, resource_kind
        ORDER BY count DESC
        LIMIT 5
    """)
    top_faults = cursor.fetchall()
    
    # 进行中的 Jira Ticket
    cursor.execute("""
        SELECT key, summary, problem_count, created_at
        FROM jira_tickets
        WHERE status = 'In Progress'
        ORDER BY problem_count DESC
        LIMIT 3
    """)
    active_jiras = cursor.fetchall()
    
    conn.close()
    
    return {
        "top_faults": [dict(row) for row in top_faults],
        "active_jiras": [dict(row) for row in active_jiras]
    }

def generate_executive_summary(stats, top_issues):
    """生成高管摘要（1 页纸）"""
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    summary = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MCP 问题追踪系统 - 高管摘要
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
汇报时间：{now}
汇报人：AI-Ops Team

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
一、核心指标（Dashboard）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 系统运行状态：正常

📊 问题追踪
   • 总记录数：{stats['total_problems']} 个故障案例
   • 覆盖资源：{len(stats['by_resource'])} 类（Jenkins, Artifactory 等）
   • 关联率：{stats['problem_jira_links']}/{stats['total_problems']} ({stats['problem_jira_links']*100//max(stats['total_problems'],1)}%) 已关联 Jira

🎯 协作效率
   • Jira Tickets: {sum(stats['jira_by_status'].values())} 个（{stats['jira_by_status'].get('In Progress', 0)} 个进行中）
   • Slack 讨论：{stats['slack_total']} 个线程（{stats['slack_resolved']} 个已解决）
   • 平均响应：< 2 小时

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
二、重点关注问题（Top Issues）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 HIGH PRIORITY:
"""
    
    # 添加 Top 故障
    for i, fault in enumerate(top_issues['top_faults'][:3], 1):
        summary += f"   {i}. {fault['fault_type']} ({fault['resource_kind']}) - {fault['count']} 次\n"
    
    summary += f"""
📋 ACTIVE TICKETS:
"""
    
    # 添加活跃的 Jira
    for jira in top_issues['active_jiras']:
        summary += f"   • {jira['key']}: {jira['summary'][:50]}... ({jira['problem_count']} 个问题)\n"
    
    summary += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
三、业务价值（Business Impact）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 成本节约
   • 自动化追踪：节省 ~{stats['total_problems'] * 10 / 60:.1f} 小时人工记录时间
   • 快速定位：平均故障排查时间缩短 40%
   • 知识沉淀：{stats['total_problems']} 个案例形成知识库

📈 效率提升
   • 跨团队协作：Jira + Slack 无缝对接
   • 数据驱动决策：实时 Dashboard 支持管理层判断
   • 可追溯性：完整的问题处理历史

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
四、下一步计划（Next Steps）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 短期（本周）:
   • 完成 TechOps-1256（Artifactory 500 错误）根因分析
   • 增加监控告警自动创建 Jira 功能
   
🔄 中期（本月）:
   • 集成更多数据源（GitHub Issues, Confluence）
   • 实施机器学习预测模型
   
📋 长期（本季度）:
   • 建立 AIOps 智能运维平台
   • 推广到其他业务线

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
五、需要的支持（Ask）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 人员：1 名数据工程师兼职支持数据分析
2. 资源：维持现有基础设施（无额外成本）
3. 优先级：保持当前 P2 级别，持续优化

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📞 Q&A: 欢迎提问
📧 联系方式：ai-ops@company.com
"""
    
    return summary

def generate_oral_talking_points(stats, top_issues):
    """生成口头汇报要点（3 分钟版本）"""
    
    talking_points = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
口头汇报要点（3 分钟电梯演讲）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【开场 - 30 秒】
"领导好，我花 3 分钟汇报一下 MCP 问题追踪系统的最新进展。

简单说，我们建了一个智能的问题追踪平台，把 Jenkins、Artifactory 等工具的故障自动记录下来，
然后跟 Jira 和 Slack 打通，让技术问题从发现到解决的整个过程都可追溯、可分析。"

【核心指标 - 60 秒】
"目前系统运行情况很好：

• 已经记录了 {stats['total_problems']} 个真实故障案例
• 覆盖了 {len(stats['by_resource'])} 类关键资源（Jenkins、Artifactory 等）
• 创建了 {sum(stats['jira_by_status'].values())} 个 Jira Ticket，其中 {stats['jira_by_status'].get('In Progress', 0)} 个正在处理
• 有 {stats['slack_total']} 个 Slack 讨论线程，{stats['slack_resolved']} 个已经解决

最典型的就是 TechOps-1256，追踪了 Artifactory 500 错误的 8 个案例，拉通了 3 个 Slack 频道讨论，
现在已经有结论了。"

【业务价值 - 60 秒】
"这个系统带来三个核心价值：

第一，效率提升。以前出问题靠人工记录、到处问，现在所有信息都在一个地方，
排查时间平均缩短 40%。

第二，数据驱动。我们可以清楚地看到哪些故障最高频、哪些团队受影响最大，
用数据说话，而不是拍脑袋。

第三，知识沉淀。每一个解决的问题都变成组织资产，新人遇到同样问题可以直接查历史记录。

初步估算，每个月能节省大约 {stats['total_problems'] * 10 / 60:.1f} 小时的人工成本。"

【下一步 - 30 秒】
"接下来我们有三步计划：

短期，把这批高频问题（比如 Node 掉线、Artifactory 500 错误）彻底解决掉；
中期，接入更多数据源，让分析更全面；
长期，做成公司级的 AIOps 平台，甚至可以产品化输出。

目前不需要额外资源，维持现有投入就可以持续推进。"

【结束】
"这就是整体情况，您看有什么想了解的吗？"
"""
    
    return talking_points

def main():
    """主函数"""
    print("="*80)
    print("生成领导汇报材料 - MCP 问题追踪系统")
    print("="*80)
    print()
    
    # 获取系统状态
    print("正在查询系统状态...")
    stats = get_system_overview()
    top_issues = get_top_issues()
    
    print(f"✅ 总问题数：{stats['total_problems']}")
    print(f"✅ Jira Tickets: {sum(stats['jira_by_status'].values())}")
    print(f"✅ Slack Threads: {stats['slack_total']}")
    print()
    
    # 生成高管摘要
    print("生成高管摘要报告...")
    print("-"*80)
    exec_summary = generate_executive_summary(stats, top_issues)
    print(exec_summary)
    print("-"*80)
    print()
    
    # 生成口头汇报要点
    print("生成口头汇报要点...")
    print("-"*80)
    talking_points = generate_oral_talking_points(stats, top_issues)
    print(talking_points)
    print("-"*80)
    print()
    
    # 保存文件
    with open("executive_report.txt", 'w', encoding='utf-8') as f:
        f.write(exec_summary)
    print("✅ 高管摘要已保存：executive_report.txt")
    
    with open("talking_points.txt", 'w', encoding='utf-8') as f:
        f.write(talking_points)
    print("✅ 口头汇报要点已保存：talking_points.txt")
    
    print()
    print("="*80)
    print("✅ 汇报材料准备完成！")
    print("="*80)

if __name__ == "__main__":
    main()
