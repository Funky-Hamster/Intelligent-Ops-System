# 数据库管理指南

## 📋 概述

数据库管理系统提供完整的初始化和迁移功能，支持新安装和升级场景。

---

## 🎯 文件结构

```
mcp_service/
├── migrations/
│   ├── 000_init_database.sql      ✨ 完整初始化脚本
│   └── 001_add_tracking_tables.sql  增量迁移脚本
│
├── database.py                     ✨ 数据库管理模块
└── migrate_db.py                   (向后兼容)
```

---

## 🚀 使用方式

### 场景 1: 全新安装（推荐）

```bash
# 方式 1: 使用新命令
python -m mcp_service.database

# 方式 2: 直接调用函数
python -c "from mcp_service.database import init_database; init_database()"
```

**输出示例**:
```
✅ 数据库初始化成功：C:\...\problems.db
📋 创建内容:
   • 表：problems, jira_tickets, slack_threads
   • 关联表：problem_jira_links, problem_slack_links
   • 索引：14 个
   • 视图：3 个 (v_problem_summary, v_jira_summary, v_slack_summary)
   • 触发器：2 个
```

---

### 场景 2: 增量升级（已有 problems 表）

```bash
# 执行增量迁移
python -m mcp_service.migrate_db

# 或指定迁移脚本
python -c "
from mcp_service.database import run_migration
run_migration('001_add_tracking_tables.sql')
"
```

**输出示例**:
```
✅ 迁移执行成功：001_add_tracking_tables.sql
```

---

### 场景 3: 在代码中使用

```python
from mcp_service.database import get_connection, init_database

# 获取数据库连接
conn = get_connection()

# 使用字典访问查询结果
cursor = conn.cursor()
cursor.execute("SELECT * FROM problems WHERE resource_kind = ?", ("Jenkins",))
for row in cursor.fetchall():
    print(row['fault_type'], row['timestamp'])

conn.close()
```

---

## 📊 数据库 Schema

### 核心表

#### problems (基础问题表)
```sql
CREATE TABLE problems (
  id TEXT PRIMARY KEY,              -- 问题唯一 ID
  fault_type TEXT NOT NULL,         -- 故障类型
  job_name TEXT NOT NULL,           -- Job 名称
  job_id TEXT,                      -- Job ID
  timestamp TEXT NOT NULL,          -- 发生时间
  evidence TEXT,                    -- 证据/日志
  resource_kind TEXT DEFAULT 'Unknown'
);
```

#### jira_tickets (Jira Ticket 表)
```sql
CREATE TABLE jira_tickets (
  id TEXT PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,
  summary TEXT NOT NULL,
  status TEXT DEFAULT 'Open',
  created_at TEXT NOT NULL,
  updated_at TEXT,
  reporter TEXT,
  assignee TEXT,
  priority TEXT DEFAULT 'Medium',
  url TEXT,
  notes TEXT,
  problem_count INTEGER DEFAULT 0
);
```

#### slack_threads (Slack Thread 表)
```sql
CREATE TABLE slack_threads (
  id TEXT PRIMARY KEY,
  channel TEXT NOT NULL,
  message_url TEXT,
  summary TEXT,
  created_at TEXT NOT NULL,
  last_activity TEXT,
  participants_count INTEGER DEFAULT 0,
  is_resolved BOOLEAN DEFAULT 0,
  notes TEXT
);
```

---

### 关联表

#### problem_jira_links (多对多关联)
```sql
CREATE TABLE problem_jira_links (
  problem_id TEXT NOT NULL,
  jira_ticket_id TEXT NOT NULL,
  linked_at TEXT NOT NULL,
  linked_by TEXT DEFAULT 'manual',
  note TEXT,
  PRIMARY KEY (problem_id, jira_ticket_id),
  FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
  FOREIGN KEY (jira_ticket_id) REFERENCES jira_tickets(id) ON DELETE CASCADE
);
```

#### problem_slack_links (多对多关联)
```sql
CREATE TABLE problem_slack_links (
  problem_id TEXT NOT NULL,
  slack_thread_id TEXT NOT NULL,
  linked_at TEXT NOT NULL,
  summary TEXT,
  is_resolved BOOLEAN DEFAULT 0,
  PRIMARY KEY (problem_id, slack_thread_id),
  FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
  FOREIGN KEY (slack_thread_id) REFERENCES slack_threads(id) ON DELETE CASCADE
);
```

---

### 视图（简化查询）

#### v_problem_summary (问题汇总)
```sql
CREATE VIEW v_problem_summary AS
SELECT 
  p.resource_kind,
  p.fault_type,
  COUNT(DISTINCT p.id) as total_problems,
  COUNT(DISTINCT pj.jira_ticket_id) as jira_count,
  COUNT(DISTINCT ps.slack_thread_id) as slack_count,
  MAX(p.timestamp) as last_occurrence
FROM problems p
LEFT JOIN problem_jira_links pj ON p.id = pj.problem_id
LEFT JOIN problem_slack_links ps ON p.id = ps.problem_id
GROUP BY p.resource_kind, p.fault_type;
```

#### v_jira_summary (Jira 汇总)
```sql
CREATE VIEW v_jira_summary AS
SELECT 
  j.key,
  j.summary,
  j.status,
  j.priority,
  j.problem_count,
  GROUP_CONCAT(p.fault_type, ', ') as fault_types,
  MIN(p.timestamp) as first_problem,
  MAX(p.timestamp) as last_problem
FROM jira_tickets j
LEFT JOIN problem_jira_links pj ON j.id = pj.jira_ticket_id
LEFT JOIN problems p ON pj.problem_id = p.id
GROUP BY j.id, j.key, j.summary, j.status, j.priority;
```

#### v_slack_summary (Slack 汇总)
```sql
CREATE VIEW v_slack_summary AS
SELECT 
  st.channel,
  st.is_resolved,
  COUNT(DISTINCT st.id) as thread_count,
  SUM(COALESCE(st.participants_count, 0)) as total_participants,
  COUNT(DISTINCT ps.problem_id) as related_problems
FROM slack_threads st
LEFT JOIN problem_slack_links ps ON st.id = ps.slack_thread_id
GROUP BY st.channel, st.is_resolved;
```

---

### 触发器（自动维护数据）

#### trg_update_jira_problem_count_after_insert
```sql
-- 当添加关联时，自动增加 Jira ticket 的问题计数
CREATE TRIGGER trg_update_jira_problem_count_after_insert
AFTER INSERT ON problem_jira_links
BEGIN
  UPDATE jira_tickets 
  SET problem_count = problem_count + 1
  WHERE id = NEW.jira_ticket_id;
END;
```

#### trg_update_jira_problem_count_after_delete
```sql
-- 当删除关联时，自动减少 Jira ticket 的问题计数
CREATE TRIGGER trg_update_jira_problem_count_after_delete
AFTER DELETE ON problem_jira_links
BEGIN
  UPDATE jira_tickets 
  SET problem_count = problem_count - 1
  WHERE id = OLD.jira_ticket_id;
END;
```

---

## 🔧 API 参考

### database.py 函数

#### `get_db_path() -> Path`
获取数据库文件路径

#### `get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection`
获取数据库连接

**参数**:
- `db_path`: 数据库文件路径（默认：problems.db）

**返回**:
- `sqlite3.Connection`: 数据库连接（row_factory=sqlite3.Row）

**示例**:
```python
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT * FROM problems")
for row in cursor.fetchall():
    print(row['fault_type'])
```

---

#### `init_database(db_path: Optional[Path] = None) -> bool`
初始化数据库（如果不存在则创建）

**参数**:
- `db_path`: 数据库文件路径

**返回**:
- `bool`: 是否成功

**示例**:
```python
if init_database():
    print("✅ 初始化成功")
```

---

#### `run_migration(migration_name: str, db_path: Optional[Path] = None) -> bool`
执行指定迁移脚本

**参数**:
- `migration_name`: 迁移脚本名称（如 `001_add_tracking_tables.sql`）
- `db_path`: 数据库文件路径

**返回**:
- `bool`: 是否成功

**示例**:
```python
run_migration('001_add_tracking_tables.sql')
```

---

## 📈 迁移历史

| 版本 | 脚本 | 描述 | 日期 |
|------|------|------|------|
| 000 | 000_init_database.sql | 完整初始化 | 2026-03-06 |
| 001 | 001_add_tracking_tables.sql | 追踪系统 | 2026-03-06 |

---

## ⚠️ 注意事项

1. **生产环境**:
   - 建议先备份数据库再执行迁移
   - 在测试环境验证后再应用到生产

2. **数据完整性**:
   - 外键约束已启用（ON DELETE CASCADE）
   - 触发器自动维护计数

3. **性能优化**:
   - 所有常用查询字段都有索引
   - 视图预计算复杂查询

4. **向后兼容**:
   - `migrate_db.py` 保持兼容但建议使用新命令
   - 旧功能不受影响

---

## 🐛 故障排查

### 问题 1: 表不存在

**症状**: `no such table: problems`

**解决**:
```bash
python -m mcp_service.database
```

---

### 问题 2: 迁移失败

**症状**: `table already exists`

**解决**:
- 检查是否已经执行过初始化
- 使用 `IF NOT EXISTS` 语法的脚本已自动跳过已存在的表

---

### 问题 3: 连接失败

**症状**: `unable to open database file`

**解决**:
- 检查目录权限
- 确保父目录存在

---

## 📚 相关文档

- [P0 实现报告](./P0_IMPLEMENTATION_REPORT.md)
- [P1 实现报告](./P1_IMPLEMENTATION_REPORT.md)
- [P2 实现报告](./P2_IMPLEMENTATION_REPORT.md)
- [使用指南](./TRACKING_GUIDE.md)
