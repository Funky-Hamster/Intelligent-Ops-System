# 问题追踪系统使用指南

## 📋 功能概述

问题追踪系统允许你手动关联问题与 Jira Ticket、Slack 讨论，生成统计简报。

**核心原则**：
- ✅ **人工决策**：Jira 创建由你判断，AI 不自动执行
- ✅ **灵活录入**：支持事后补充关联信息
- ✅ **数据完整**：所有操作都有日志记录

---

## 🚀 快速开始

### Step 1: 执行数据库迁移

```bash
python -m mcp_service.migrate_db
```

输出：
```
✅ 数据库迁移成功
📋 新增表:
   • jira_tickets
   • slack_threads
   • problem_jira_links
   • problem_slack_links
📋 新增视图:
   • v_problem_summary
```

---

## 📝 使用场景

### 场景 1：添加 Jira Ticket

你在 Jira 创建了 ticket `PROJ-456`，现在录入系统：

```bash
python -m mcp_service.mcp_tools add-jira \
  --key "PROJ-456" \
  --summary "Jenkins Disk Full 问题修复" \
  --status "Open" \
  --assignee "TechOps Team" \
  --priority "High" \
  --url "https://yourcompany.atlassian.net/browse/PROJ-456" \
  --notes "需要清理 /var/jenkins 磁盘空间"
```

---

### 场景 2：关联问题到 Jira

查询到最近有 5 次 Disk Full 问题（problem IDs），关联到同一个 Jira：

```bash
# 单个关联
python -m mcp_service.mcp_tools link-jira \
  --problem-id "prob-12345" \
  --jira-key "PROJ-456" \
  --note "这是 5 次 Disk Full 问题中的第 1 次"

# 批量关联（推荐）
# 先查询最近的 Disk Full 问题
python -c "
from mcp_service.mcp_server import search_problems
problems = search_problems(fault_type='disk full', start_time='2026-03-01')
for p in problems:
    print(f\"{p['id']}: {p['timestamp']}\")
"

# 然后批量执行关联
python -m mcp_service.mcp_tools link-jira \
  --problem-id "prob-12345" \
  --jira-key "PROJ-456"

python -m mcp_service.mcp_tools link-jira \
  --problem-id "prob-12346" \
  --jira-key "PROJ-456"

# ... 重复直到所有问题都关联
```

---

### 场景 3：关联 Slack 讨论

你和 DevOps 团队在 Slack 讨论了某个问题：

```bash
python -m mcp_service.mcp_tools link-slack \
  --problem-id "prob-12345" \
  --slack-url "https://yourcompany.slack.com/archives/C123/p123456" \
  --channel "devops-alerts" \
  --summary "已与@DevOps 确认，是监控脚本 bug" \
  --is-resolved
```

---

## 🔍 查询与验证

### 查看数据库内容

```bash
python -c "
import sqlite3
conn = sqlite3.connect('mcp_service/problems.db')
c = conn.cursor()

# 查看所有 Jira tickets
print('=== Jira Tickets ===')
c.execute('SELECT key, summary, status, problem_count FROM jira_tickets')
for row in c.fetchall():
    print(f'{row[0]}: {row[1]} ({row[2]}) - {row[3]} problems')

# 查看关联关系
print('\n=== Problem-Jira Links ===')
c.execute('''
    SELECT p.fault_type, j.key, pj.linked_at, pj.note
    FROM problem_jira_links pj
    JOIN problems p ON pj.problem_id = p.id
    JOIN jira_tickets j ON pj.jira_ticket_id = j.id
''')
for row in c.fetchall():
    print(f'{row[0]} -> {row[1]} ({row[2]})')

conn.close()
"
```

---

## 📊 报表生成（即将实现）

下一步将实现：

```bash
# 生成周报
python -m mcp_service.report generate \
  --resource Jenkins \
  --start 2026-03-01 \
  --end 2026-03-07 \
  --format markdown

# 导出 Excel
python -m mcp_service.report export \
  --resource Jenkins \
  --month 2026-03 \
  --format excel
```

---

## ⚠️ 注意事项

1. **输入验证**：
   - Jira Key 不能超过 50 字符
   - Summary 不能超过 500 字符
   - 只允许字母、数字、下划线、连字符、空格、中文

2. **数据完整性**：
   - 每个 problem 可以关联多个 Jira tickets
   - 每个 Jira ticket 可以关联多个 problems
   - 重复关联会被拒绝（ IntegrityError）

3. **权限与安全**：
   - 所有操作都会记录到数据库
   - 建议定期备份 problems.db

---

## 🛠️ MCP API 调用（编程方式）

```python
from mcp_service.mcp_server import (
    add_jira_ticket,
    link_problem_to_jira,
    link_problem_to_slack
)

# 添加 Jira
ticket_id = add_jira_ticket(
    key="PROJ-456",
    summary="Disk Full Fix",
    assignee="TechOps"
)

# 关联问题
link_problem_to_jira(
    problem_id="prob-12345",
    jira_key="PROJ-456",
    note="批量关联"
)

# 关联 Slack
link_problem_to_slack(
    problem_id="prob-12345",
    slack_url="https://...",
    channel="devops",
    summary="已解决"
)
```

---

## 📈 下一步计划

- [ ] 生成领导简报（Markdown/Excel）
- [ ] 智能匹配建议（基于故障类型相似度）
- [ ] 异常检测提醒（未关联的问题）
- [ ] 定时同步 Jira 状态

---

## 💡 最佳实践

1. **及时录入**：创建 Jira 后立即关联
2. **批量操作**：同类问题关联到同一个 ticket
3. **详细备注**：说明关联原因和背景
4. **定期检查**：每周查看未关联的问题

---

**最后更新**: 2026-03-06  
**版本**: v1.0.0 (MVP)
