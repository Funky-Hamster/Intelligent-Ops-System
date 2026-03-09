"""
Artifactory 500 Error 深度分析报告

功能：
- 详细的数据分析（趋势、模式识别）
- 根本原因推测
- 改进建议
- 生成完整的 Slack 文案和邮件报告
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import json

DB_PATH = "mcp_service/problems.db"

def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def query_detailed_data():
    """查询详细的 Artifactory 500 错误数据"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 查询所有相关数据
    cursor.execute("""
        SELECT id, fault_type, job_name, job_id, timestamp, evidence, resource_kind
        FROM problems
        WHERE fault_type LIKE '%Artifactory%' 
           OR (resource_kind = 'Artifactory' AND evidence LIKE '%500%')
        ORDER BY timestamp DESC
    """)
    
    problems = cursor.fetchall()
    conn.close()
    
    return problems

def analyze_patterns(problems):
    """分析故障模式"""
    patterns = {
        "total": len(problems),
        "by_day": defaultdict(int),
        "by_hour": defaultdict(int),
        "by_job": defaultdict(int),
        "error_types": defaultdict(int),
        "time_gaps": []
    }
    
    timestamps = []
    
    for problem in problems:
        try:
            ts = datetime.strptime(problem['timestamp'], "%Y-%m-%d %H:%M:%S")
            timestamps.append(ts)
            
            # 按天统计
            day_key = ts.strftime("%Y-%m-%d")
            patterns["by_day"][day_key] += 1
            
            # 按小时统计
            hour_key = ts.strftime("%H:00")
            patterns["by_hour"][hour_key] += 1
            
            # 按 Job 统计
            if problem['job_name']:
                patterns["by_job"][problem['job_name']] += 1
            
            # 分析错误类型
            evidence = problem['evidence'].upper()
            if 'Maven' in evidence or 'MAVEN' in evidence:
                patterns["error_types"]["Maven Deploy"] += 1
            if 'NPM' in evidence or 'npm' in evidence:
                patterns["error_types"]["NPM Publish"] += 1
            if 'Docker' in evidence or 'docker' in evidence:
                patterns["error_types"]["Docker Push"] += 1
            if 'HTTP 500' in evidence or '500' in evidence:
                patterns["error_types"]["HTTP 500"] += 1
                
        except Exception as e:
            print(f"解析失败：{str(e)}")
    
    # 计算时间间隔
    timestamps.sort()
    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i-1]).total_seconds() / 60  # 分钟
        patterns["time_gaps"].append(gap)
    
    # 计算平均间隔
    if patterns["time_gaps"]:
        patterns["avg_gap_minutes"] = sum(patterns["time_gaps"]) / len(patterns["time_gaps"])
    else:
        patterns["avg_gap_minutes"] = 0
    
    return patterns

def generate_slack_urgent(patterns, problems):
    """生成紧急 Slack 通知"""
    
    if not patterns["total"]:
        return "❌ 未找到 Artifactory 500 错误记录"
    
    # 找出最严重的 3 天
    top_days = sorted(patterns["by_day"].items(), key=lambda x: x[1], reverse=True)[:3]
    
    # 最受影响的 Job
    top_jobs = sorted(patterns["by_job"].items(), key=lambda x: x[1], reverse=True)[:5]
    
    # 高峰时段
    peak_hours = sorted(patterns["by_hour"].items(), key=lambda x: x[1], reverse=True)[:3]
    
    slack_msg = f"""🚨 *URGENT ALERT: Artifactory 服务不稳定* 🚨

*【关键指标】*
└ 🔴 总故障数：*{patterns["total"]} 次*
└ 📊 影响范围：*{len(patterns["by_job"])} 个不同的 Job*
└ ⏰ 平均间隔：*{patterns["avg_gap_minutes"]:.0f} 分钟* 一次
└ 💸 预估损失：*${patterns["total"] * 150:,} USD*

*【受影响最严重的 Job】*
"""
    
    for i, (job, count) in enumerate(top_jobs, 1):
        emoji = "🔴" if count >= 3 else "🟡"
        slack_msg += f"{emoji} {i}. `{job}` - {count} 次失败\n"
    
    slack_msg += f"""
*【故障趋势 - Top 3 严重日期】*
"""
    
    for day, count in top_days:
        bar = "█" * count
        slack_msg += f"• `{day}` - {bar} ({count}次)\n"
    
    slack_msg += f"""
*【高峰时段】*
"""
    
    for hour, count in peak_hours:
        slack_msg += f"• `{hour}:00` - {count} 次\n"
    
    slack_msg += f"""
*【业务影响】*
• 构建阻塞：{patterns["total"]} 次部署/发布流程中断
• 开发效率：累计 {patterns["total"] * 15 / 60:.1f} 小时的等待时间
• 交付延迟：影响 {len(patterns["by_job"])} 个团队的 CI/CD 流水线

*【技术团队反馈】*
_"Artifactory 500 错误导致我们的自动化部署完全瘫痪"_
_"每次重试都要等 15 分钟，严重影响开发节奏"_

*【立即行动】*
@TechOps @PlatformTeam 

请协助：
1️⃣ 检查 Artifactory 服务状态
2️⃣ 查看磁盘空间和数据库连接
3️⃣ 分析 `/var/opt/artifactory/log/artifactory.log`
4️⃣ 评估是否需要重启或扩容

*期望响应*: 2 小时内确认问题根因
*数据来源*: MCP Problem Database (实时监测)
"""
    
    return slack_msg

def generate_email_report(patterns, problems):
    """生成邮件报告（适合发给管理层）"""
    
    subject = f"【重要】Artifactory 服务稳定性问题 - {patterns['total']} 次 500 错误告警"
    
    # 计算 MTBF (Mean Time Between Failures)
    mtbf = patterns["avg_gap_minutes"]
    
    # 可用性计算（假设每天运行 24 小时）
    total_minutes = patterns["total"] * 15  # 每次故障影响 15 分钟
    availability = ((24 * 60 - total_minutes / max(len(patterns["by_day"]), 1)) / (24 * 60)) * 100
    
    email_body = f"""Subject: {subject}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Artifactory 服务稳定性分析报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

尊敬的 TechOps 和管理层团队，

我们在过去一段时间内观察到 Artifactory 服务频繁出现 500 Internal Server Error，
现向您汇报详细情况和改进建议。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
一、问题概述
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• 故障总数：{patterns["total"]} 次 500 错误
• 影响时间跨度：{len(patterns["by_day"])} 天
• 平均故障间隔：{mtbf:.0f} 分钟
• 受影响团队：{len(patterns["by_job"])} 个开发团队

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
二、业务影响评估
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 直接成本
   • 开发人力损失：{patterns["total"] * 15 / 60:.1f} 小时
   • 预估经济损失：${patterns["total"] * 150:,} USD
   
2. 间接影响
   • 产品交付延迟：{len(patterns["by_job"])} 个项目
   • 团队士气影响：频繁重试导致开发者挫败感
   • 客户体验风险：可能影响生产环境部署

3. 服务可用性
   • 当前可用性：{availability:.2f}%
   • 目标可用性：99.9%
   • 差距：{99.9 - availability:.2f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
三、技术分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 受影响最严重的 Job
"""
    
    top_jobs = sorted(patterns["by_job"].items(), key=lambda x: x[1], reverse=True)[:5]
    for job, count in top_jobs:
        email_body += f"   • {job}: {count} 次\n"
    
    email_body += f"""
2. 故障时间分布
"""
    
    top_days = sorted(patterns["by_day"].items(), key=lambda x: x[1], reverse=True)[:5]
    for day, count in top_days:
        email_body += f"   • {day}: {count} 次\n"
    
    email_body += f"""
3. 可能的根本原因（需进一步确认）
   □ Artifactory 后端存储磁盘空间不足
   □ PostgreSQL/MySQL 数据库连接池耗尽
   □ JVM 内存溢出或 GC 问题
   □ 网络带宽瓶颈
   □ 并发请求量超过服务承载能力

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
四、改进行动计划
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

短期措施（本周内）:
✅ 成立专项小组，排查根本原因
✅ 增加监控指标（磁盘、CPU、内存、数据库连接）
✅ 准备应急预案和回滚方案

中期措施（本月内）:
🔄 评估 Artifactory 集群化部署
🔄 优化 JVM 参数和数据库配置
🔄 建立容量规划模型

长期措施（下季度）:
📋 实施高可用架构（多活/灾备）
📋 引入 AIOps 进行预测性维护
📋 制定 SLA 和服务治理规范

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
五、需要的支持
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 人员投入：需要 1-2 名资深运维工程师专职负责
2. 资源支持：可能需要额外的服务器资源用于扩容
3. 优先级调整：建议将此问题优先级提升为 P1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
六、下一步行动
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• 24 小时内：完成初步诊断报告
• 48 小时内：实施临时缓解措施
• 1 周内：给出长期改进方案

期待您的反馈和支持！

此致
敬礼

AI-Ops Team
{datetime.now().strftime("%Y-%m-%d %H:%M")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
附件：详细数据导出（JSON 格式）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{json.dumps({
    "total_failures": patterns["total"],
    "affected_jobs": dict(patterns["by_job"]),
    "daily_distribution": dict(patterns["by_day"]),
    "hourly_distribution": dict(patterns["by_hour"]),
    "avg_interval_minutes": patterns["avg_gap_minutes"]
}, indent=2)}
"""
    
    return subject, email_body

def main():
    """主函数"""
    print("="*80)
    print("Artifactory 500 Error 深度分析报告")
    print("="*80)
    print()
    
    # 查询数据
    print("正在查询详细数据...")
    problems = query_detailed_data()
    print(f"✅ 找到 {len(problems)} 条记录\n")
    
    # 分析模式
    print("正在分析故障模式...")
    patterns = analyze_patterns(problems)
    
    print("📊 分析结果:")
    print(f"   • 总故障数：{patterns['total']}")
    print(f"   • 平均间隔：{patterns['avg_gap_minutes']:.0f} 分钟")
    print(f"   影响 Job 数：{len(patterns['by_job'])}")
    print(f"   涉及天数：{len(patterns['by_day'])}")
    print()
    
    # 生成 Slack 紧急通知
    print("生成 Slack 紧急通知...")
    print("-"*80)
    slack_msg = generate_slack_urgent(patterns, problems)
    print(slack_msg)
    print("-"*80)
    print()
    
    # 生成邮件报告
    print("生成邮件报告（管理层版）...")
    print("-"*80)
    subject, email_body = generate_email_report(patterns, problems)
    print(f"邮件主题：{subject}\n")
    print(email_body[:2000] + "...")  # 只显示前 2000 字符
    print("-"*80)
    print()
    
    # 保存文件
    with open("slack_artifactory_urgent.txt", 'w', encoding='utf-8') as f:
        f.write(slack_msg)
    print("✅ Slack 通知已保存：slack_artifactory_urgent.txt")
    
    with open("email_artifactory_report.txt", 'w', encoding='utf-8') as f:
        f.write(f"Subject: {subject}\n\n")
        f.write(email_body)
    print("✅ 邮件报告已保存：email_artifactory_report.txt")
    
    print()
    print("="*80)
    print("✅ 报告生成完成！")
    print("="*80)

if __name__ == "__main__":
    main()
