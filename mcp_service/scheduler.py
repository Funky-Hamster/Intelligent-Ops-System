# /vsi-ai-om/mcp_service/scheduler.py
"""
定时任务调度器

功能：
- 每日自动生成日报
- 每周自动生成周报
- 自动推送到 Slack/Email
"""

import schedule
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


class ReportScheduler:
    """报表调度器"""
    
    def __init__(self, output_dir: str = None):
        """
        初始化调度器
        
        Args:
            output_dir: 报表输出目录（默认：./reports）
        """
        if output_dir is None:
            project_root = Path(__file__).parent.parent
            output_dir = project_root / "reports"
        
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"📂 报表输出目录：{output_dir}")
    
    def generate_daily_report(self, resource_kind: str = "Jenkins"):
        """
        生成昨日的日报
        
        Args:
            resource_kind: 资源类型
        """
        from mcp_service.mcp_server import generate_executive_report
        
        # 计算昨日日期
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        print(f"\n{'='*60}")
        print(f"📅 生成 {resource_kind} 日报 ({yesterday})")
        print(f"{'='*60}")
        
        try:
            # 生成 Markdown 报表
            report = generate_executive_report(
                resource_kind=resource_kind,
                start_date=yesterday,
                end_date=yesterday,
                format="markdown"
            )
            
            # 保存到文件
            filename = f"daily_{resource_kind.lower()}_{yesterday.replace('-', '')}.md"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"✅ 日报已保存：{filepath}")
            
            # TODO: 发送到 Slack/Email
            # self.send_to_slack(report, channel="#devops-reports")
            # self.send_to_email(report, recipients=["team@company.com"])
            
        except Exception as e:
            print(f"❌ 生成日报失败：{str(e)}")
    
    def generate_weekly_report(self, resource_kind: str = "Jenkins"):
        """
        生成上周的周报
        
        Args:
            resource_kind: 资源类型
        """
        from mcp_service.mcp_server import generate_executive_report
        
        # 计算上周一和周日
        today = datetime.now()
        last_monday = today - timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)
        
        start_date = last_monday.strftime("%Y-%m-%d")
        end_date = last_sunday.strftime("%Y-%m-%d")
        
        print(f"\n{'='*60}")
        print(f"📊 生成 {resource_kind} 周报 ({start_date} ~ {end_date})")
        print(f"{'='*60}")
        
        try:
            # 生成 Markdown 报表
            report = generate_executive_report(
                resource_kind=resource_kind,
                start_date=start_date,
                end_date=end_date,
                format="markdown"
            )
            
            # 保存到文件
            filename = f"weekly_{resource_kind.lower()}_{start_date.replace('-', '')}.md"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"✅ 周报已保存：{filepath}")
            
            # TODO: 发送到 Slack/Email
            # self.send_to_slack(report, channel="#devops-reports")
            # self.send_to_email(report, recipients=["leadership@company.com"])
            
        except Exception as e:
            print(f"❌ 生成周报失败：{str(e)}")
    
    def send_to_slack(self, report: str, channel: str = "#devops-reports"):
        """
        发送报表到 Slack
        
        Args:
            report: 报表内容
            channel: Slack channel
        """
        # TODO: 集成 Slack API
        print(f"💬 发送到 Slack {channel}: (功能待实现)")
        print("提示：需要配置 SLACK_BOT_TOKEN 和 SLACK_API_URL")
    
    def send_to_email(self, report: str, recipients: list, subject: str = None):
        """
        发送报表到 Email
        
        Args:
            report: 报表内容
            recipients: 收件人列表
            subject: 邮件主题
        """
        # TODO: 集成 SMTP
        print(f"📧 发送邮件给 {recipients}: (功能待实现)")
        print("提示：需要配置 SMTP_SERVER, SMTP_USER, SMTP_PASSWORD")
    
    def start(self, daily_time: str = "09:00", weekly_day: str = "monday", weekly_time: str = "10:00"):
        """
        启动定时任务
        
        Args:
            daily_time: 日报生成时间（默认 09:00）
            weekly_day: 周报生成星期（默认 monday）
            weekly_time: 周报生成时间（默认 10:00）
        """
        print(f"\n{'='*60}")
        print("⏰ 定时任务调度器启动")
        print(f"{'='*60}")
        print(f"📅 日报时间：每天 {daily_time}")
        print(f"📊 周报时间：每周一 {weekly_time}")
        print(f"\n按 Ctrl+C 停止服务...\n")
        
        # 安排日报任务
        schedule.every().day.at(daily_time).do(
            lambda: self.generate_daily_report(resource_kind="Jenkins")
        )
        
        # 安排周报任务
        getattr(schedule.every(), weekly_day).at(weekly_time).do(
            lambda: self.generate_weekly_report(resource_kind="Jenkins")
        )
        
        # 持续运行
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次


def run_scheduler():
    """快捷函数：启动调度器"""
    scheduler = ReportScheduler()
    scheduler.start()


if __name__ == "__main__":
    run_scheduler()
