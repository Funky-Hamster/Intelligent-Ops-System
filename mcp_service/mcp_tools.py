# /vsi-ai-om/mcp_service/mcp_tools.py
"""
MCP 问题追踪工具 - CLI 接口

使用方式:
    python -m mcp_service.mcp_tools <command> [options]
    
命令:
    add-jira      - 添加 Jira Ticket
    link-jira     - 关联问题到 Jira
    link-slack    - 关联问题到 Slack
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp_service.mcp_server import (
    add_jira_ticket,
    link_problem_to_jira,
    link_problem_to_slack
)


def cmd_add_jira(args):
    """添加 Jira Ticket"""
    result = add_jira_ticket(
        key=args.key,
        summary=args.summary,
        status=args.status,
        reporter=args.reporter,
        assignee=args.assignee,
        priority=args.priority,
        url=args.url,
        notes=args.notes
    )
    print(f"✅ {result}")


def cmd_link_jira(args):
    """关联问题到 Jira"""
    result = link_problem_to_jira(
        problem_id=args.problem_id,
        jira_key=args.jira_key,
        note=args.note
    )
    print(f"✅ {result}")


def cmd_link_slack(args):
    """关联问题到 Slack"""
    result = link_problem_to_slack(
        problem_id=args.problem_id,
        slack_url=args.slack_url,
        channel=args.channel,
        summary=args.summary,
        is_resolved=args.is_resolved
    )
    print(f"✅ {result}")


def cmd_generate_report(args):
    """生成领导简报"""
    from mcp_service.mcp_server import generate_executive_report
    
    result = generate_executive_report(
        resource_kind=args.resource,
        start_date=args.start,
        end_date=args.end,
        format=args.format
    )
    
    # 输出到文件或终端
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"📄 报表已保存到：{args.output}")
    else:
        print(result)


def cmd_detect_anomalies(args):
    """检测数据异常"""
    from mcp_service.mcp_server import detect_data_anomalies
    
    result = detect_data_anomalies(days=args.days)
    
    print("\n" + "="*60)
    print(f"🔍 数据异常检测报告 (最近 {args.days} 天)")
    print("="*60)
    print(f"\n{result['summary']}\n")
    
    if result.get('unlinked_problems'):
        print(f"⚠️ 未关联的问题 ({len(result['unlinked_problems'])} 个):")
        for p in result['unlinked_problems'][:5]:
            print(f"   - {p['id']}: {p['fault_type']} ({p['timestamp'][:10]})")
        if len(result['unlinked_problems']) > 5:
            print(f"   ... 还有 {len(result['unlinked_problems']) - 5} 个")
        print()
    
    if result.get('stale_jiras'):
        print(f"⚠️ 长期未更新的 Jira ({len(result['stale_jiras'])} 个):")
        for j in result['stale_jiras'][:5]:
            print(f"   - {j['key']}: {j['summary']} (状态：{j['status']})")
        print()
    
    if result.get('low_jira_rate'):
        print("⚠️ Jira 创建率偏低 (<50%)")
        print("💡 建议：为重要问题创建 Jira ticket\n")


def cmd_batch_link(args):
    """批量关联问题到 Jira"""
    from mcp_service.mcp_server import batch_link_problems_to_jira
    
    result = batch_link_problems_to_jira(
        fault_type=args.fault_type,
        jira_key=args.jira_key,
        days=args.days,
        resource_kind=args.resource,
        note=args.note
    )
    
    print("\n" + "="*60)
    print("📦 批量关联结果")
    print("="*60)
    print(f"\n{result['message']}\n")
    print(f"📊 统计:")
    print(f"   • 找到问题数：{result['total_found']}")
    print(f"   • 成功关联数：{result['linked_count']}")
    if result['failed_ids']:
        print(f"   • 失败数：{len(result['failed_ids'])}")
    
    if result['problem_ids']:
        print(f"\n📋 关联的问题列表:")
        for pid in result['problem_ids'][:10]:
            print(f"   - {pid}")
        if len(result['problem_ids']) > 10:
            print(f"   ... 还有 {len(result['problem_ids']) - 10} 个")


def main():
    parser = argparse.ArgumentParser(
        description="MCP 问题追踪工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # ========== add-jira 命令 ==========
    add_jira_parser = subparsers.add_parser('add-jira', help='添加 Jira Ticket')
    add_jira_parser.add_argument('--key', '-k', required=True, help='Jira Key (如 PROJ-456)')
    add_jira_parser.add_argument('--summary', '-s', required=True, help='摘要/标题')
    add_jira_parser.add_argument('--status', default='Open', help='状态 (默认：Open)')
    add_jira_parser.add_argument('--reporter', help='报告人')
    add_jira_parser.add_argument('--assignee', help='负责人')
    add_jira_parser.add_argument('--priority', default='Medium', help='优先级 (默认：Medium)')
    add_jira_parser.add_argument('--url', help='Jira URL')
    add_jira_parser.add_argument('--notes', help='备注说明')
    add_jira_parser.set_defaults(func=cmd_add_jira)
    
    # ========== link-jira 命令 ==========
    link_jira_parser = subparsers.add_parser('link-jira', help='关联问题到 Jira')
    link_jira_parser.add_argument('--problem-id', required=True, help='问题 ID (如 prob-12345)')
    link_jira_parser.add_argument('--jira-key', required=True, help='Jira Key')
    link_jira_parser.add_argument('--note', help='关联说明')
    link_jira_parser.set_defaults(func=cmd_link_jira)
    
    # ========== link-slack 命令 ==========
    link_slack_parser = subparsers.add_parser('link-slack', help='关联问题到 Slack')
    link_slack_parser.add_argument('--problem-id', required=True, help='问题 ID')
    link_slack_parser.add_argument('--slack-url', required=True, help='Slack 消息 URL')
    link_slack_parser.add_argument('--channel', required=True, help='Slack Channel')
    link_slack_parser.add_argument('--summary', help='讨论摘要')
    link_slack_parser.add_argument('--is-resolved', action='store_true', help='是否已解决')
    link_slack_parser.set_defaults(func=cmd_link_slack)
    
    # ========== generate-report 命令 ==========
    report_parser = subparsers.add_parser('report', help='生成领导简报')
    report_parser.add_argument('--resource', '-r', required=True, help='资源类型')
    report_parser.add_argument('--start', '-s', required=True, help='开始日期 (YYYY-MM-DD)')
    report_parser.add_argument('--end', '-e', required=True, help='结束日期 (YYYY-MM-DD)')
    report_parser.add_argument('--format', '-f', default='markdown', choices=['markdown', 'csv', 'html'], help='输出格式')
    report_parser.add_argument('--output', '-o', help='输出文件路径（默认：终端）')
    report_parser.set_defaults(func=cmd_generate_report)
    
    # ========== detect-anomalies 命令 ==========
    anomaly_parser = subparsers.add_parser('anomalies', help='检测数据异常')
    anomaly_parser.add_argument('--days', '-d', type=int, default=7, help='最近 N 天（默认 7）')
    anomaly_parser.set_defaults(func=cmd_detect_anomalies)
    
    # ========== batch-link 命令 ==========
    batch_parser = subparsers.add_parser('batch-link', help='批量关联问题到 Jira')
    batch_parser.add_argument('--fault-type', '-f', required=True, help='故障类型（支持模糊匹配）')
    batch_parser.add_argument('--jira-key', '-j', required=True, help='Jira Key')
    batch_parser.add_argument('--days', '-d', type=int, default=7, help='最近 N 天（默认 7）')
    batch_parser.add_argument('--resource', '-r', help='资源类型（可选）')
    batch_parser.add_argument('--note', '-n', help='关联说明')
    batch_parser.set_defaults(func=cmd_batch_link)
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行命令
    args.func(args)


if __name__ == "__main__":
    main()
