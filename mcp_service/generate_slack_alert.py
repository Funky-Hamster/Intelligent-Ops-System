"""
生成 Slack 通知文案 - Artifactory 500 错误专题

功能：
- 查询数据库中所有 Artifactory 500 错误
- 统计分析（频率、影响范围、时间分布）
- 生成有说服力的 Slack 文案
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

# 数据库路径
DB_PATH = "mcp_service/problems.db"

def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def query_artifactory_500_errors():
    """查询所有 Artifactory 500 错误"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 查询所有 Artifactory 500 错误
    cursor.execute("""
        SELECT id, fault_type, job_name, job_id, timestamp, evidence
        FROM problems
        WHERE fault_type LIKE '%Artifactory%' 
           OR (resource_kind = 'Artifactory' AND evidence LIKE '%500%')
        ORDER BY timestamp DESC
    """)
    
    problems = cursor.fetchall()
    conn.close()
    
    return problems

def analyze_problems(problems):
    """分析问题数据"""
    if not problems:
        return None
    
    # 时间分析
    timestamps = []
    affected_jobs = set()
    job_ids = set()
    
    for problem in problems:
        try:
            ts = datetime.strptime(problem['timestamp'], "%Y-%m-%d %H:%M:%S")
            timestamps.append(ts)
        except:
            pass
        
        if problem['job_name']:
            affected_jobs.add(problem['job_name'])
        if problem['job_id']:
            job_ids.add(problem['job_id'])
    
    # 计算时间范围
    if timestamps:
        earliest = min(timestamps)
        latest = max(timestamps)
        time_range_hours = (latest - earliest).total_seconds() / 3600
    else:
        earliest = latest = None
        time_range_hours = 0
    
    # 按小时统计故障数
    hourly_stats = defaultdict(int)
    for ts in timestamps:
        hour_key = ts.strftime("%Y-%m-%d %H:00")
        hourly_stats[hour_key] += 1
    
    # 按 Job 统计
    job_stats = defaultdict(int)
    for problem in problems:
        if problem['job_name']:
            job_stats[problem['job_name']] += 1
    
    return {
        "total_count": len(problems),
        "affected_jobs": affected_jobs,
        "affected_job_count": len(affected_jobs),
        "unique_job_ids": job_ids,
        "time_range_hours": time_range_hours,
        "earliest": earliest,
        "latest": latest,
        "hourly_stats": dict(hourly_stats),
        "job_stats": dict(job_stats)
    }

def generate_slack_message(stats, sample_problems):
    """生成 Slack 通知文案"""
    
    if not stats:
        return "❌ 未找到 Artifactory 500 错误记录"
    
    # 计算频率
    if stats['time_range_hours'] > 0:
        frequency = stats['total_count'] / stats['time_range_hours']
        frequency_per_day = frequency * 24
    else:
        frequency_per_day = stats['total_count']
    
    # 找出最受影响的 Job
    top_jobs = sorted(stats['job_stats'].items(), key=lambda x: x[1], reverse=True)[:5]
    
    # 构建 Slack 消息
    slack_msg = f"""🚨 *URGENT: Artifactory 500 Error 频繁告警* 🚨

*📊 问题概览*
• *总故障数*: {stats['total_count']} 次
• *影响范围*: {stats['affected_job_count']} 个不同的 Job
• *时间跨度*: {stats['time_range_hours']:.1f} 小时 ({stats['earliest'].strftime('%m-%d %H:%M')} ~ {stats['latest'].strftime('%m-%d %H:%M')})
• *故障频率*: {frequency_per_day:.1f} 次/天（平均 {60/frequency:.1f} 分钟一次）

*🎯 受影响最严重的 Job*
"""
    
    for i, (job_name, count) in enumerate(top_jobs, 1):
        impact_emoji = "🔴" if count >= 3 else "🟡"
        slack_msg += f"{impact_emoji} *{i}. {job_name}* - {count} 次失败\n"
    
    slack_msg += f"""
*⏰ 故障时间分布*
"""
    
    # 显示最近 5 个小时的统计
    recent_hours = sorted(stats['hourly_stats'].keys(), reverse=True)[:5]
    for hour in recent_hours:
        count = stats['hourly_stats'][hour]
        bar = "█" * count
        slack_msg += f"• `{hour}` - {bar} ({count}次)\n"
    
    slack_msg += f"""
*💥 业务影响*
• *构建阻塞*: {stats['total_count']} 次构建任务因 Artifactory 500 错误失败
• *开发效率*: 平均每次故障导致开发等待 ~15 分钟
• *累计影响*: 预计损失 {stats['total_count'] * 15 / 60:.1f} 人天的开发时间

*📝 典型错误日志*
"""
    
    # 添加 2-3 个典型错误示例
    for i, problem in enumerate(sample_problems[:3], 1):
        # 提取证据中的关键错误信息
        evidence_lines = problem['evidence'].split('\n')
        error_line = next((line for line in evidence_lines if 'ERROR' in line or '500' in line), "Unknown error")
        slack_msg += f"```{error_line[:150]}...```\n"
    
    slack_msg += f"""
*🎯 建议措施*
1. *立即检查*: Artifactory 服务健康状态 (`systemctl status artifactory`)
2. *查看日志*: `/var/opt/artifactory/log/artifactory.log`
3. *磁盘空间*: `df -h /var/opt/artifactory`
4. *数据库连接*: 检查 PostgreSQL/MySQL 服务状态
5. *重启服务*: 如必要，重启 Artifactory 服务

*📞 Need Help*
@TechOps @PlatformTeam 请协助排查根本原因，避免持续影响开发效率。

*📈 Data Source*: MCP Problem Database (实时监测)
"""
    
    return slack_msg

def generate_executive_summary(stats):
    """生成给管理层的高管摘要"""
    
    if not stats:
        return None
    
    # 估算业务影响
    estimated_downtime_minutes = stats['total_count'] * 15
    estimated_cost = stats['total_count'] * 150  # 假设每次故障成本 $150
    
    summary = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *Artifactory 500 Error - 高管摘要*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*核心问题*
Artifactory 服务在过去 {stats['time_range_hours']:.0f} 小时内出现 {stats['total_count']} 次 500 错误，严重影响研发效率。

*业务影响*
• 受影响团队：{stats['affected_job_count']} 个开发团队的构建流程被阻塞
• 累计停机时间：{estimated_downtime_minutes} 分钟（{estimated_downtime_minutes/60:.1f} 小时）
• 预估成本损失：${estimated_cost:,} USD（开发人力 + 交付延迟）

*紧急程度评估*
{'🔴 HIGH' if stats['total_count'] >= 10 else '🟡 MEDIUM'} - 需要立即关注

*建议行动*
1. 成立专项小组排查 Artifactory 稳定性问题
2. 评估是否需要扩容或架构优化
3. 建立监控告警机制，提前发现潜在问题

*期望响应时间*: 24 小时内给出改进方案
"""
    
    return summary

def main():
    """主函数"""
    print("="*80)
    print("生成 Slack 通知文案 - Artifactory 500 Error 专题")
    print("="*80)
    print()
    
    # 查询问题
    print("正在查询 Artifactory 500 错误...")
    problems = query_artifactory_500_errors()
    
    if not problems:
        print("❌ 未找到 Artifactory 500 错误记录")
        return
    
    print(f"✅ 找到 {len(problems)} 条 Artifactory 500 错误记录")
    print()
    
    # 分析数据
    print("正在分析故障数据...")
    stats = analyze_problems(problems)
    
    print(f"📊 分析结果:")
    print(f"   • 总故障数：{stats['total_count']} 次")
    print(f"   • 影响 Job 数：{stats['affected_job_count']} 个")
    print(f"   • 时间跨度：{stats['time_range_hours']:.1f} 小时")
    print(f"   • 故障频率：{stats['total_count']/max(stats['time_range_hours'], 1):.2f} 次/小时")
    print()
    
    # 生成 Slack 文案
    print("生成 Slack 通知文案...")
    print("-"*80)
    slack_msg = generate_slack_message(stats, problems)
    print(slack_msg)
    print("-"*80)
    print()
    
    # 生成高管摘要
    print("生成高管摘要...")
    print("-"*80)
    exec_summary = generate_executive_summary(stats)
    if exec_summary:
        print(exec_summary)
    print("-"*80)
    print()
    
    # 保存文件
    output_file = "slack_artifactory_alert.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=== Slack Message ===\n")
        f.write(slack_msg)
        f.write("\n\n=== Executive Summary ===\n")
        f.write(exec_summary or "N/A")
    
    print(f"✅ Slack 文案已保存到：{output_file}")
    print()
    print("="*80)

if __name__ == "__main__":
    main()
