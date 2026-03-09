-- /vsi-ai-om/mcp_service/migrations/000_init_database.sql
-- 完整数据库初始化脚本
-- 适用场景：全新安装，从零开始创建所有表

-- ============================================
-- 基础问题表
-- ============================================
CREATE TABLE IF NOT EXISTS problems (
  id TEXT PRIMARY KEY,              -- 问题唯一 ID (如 prob-abc123)
  fault_type TEXT NOT NULL,         -- 故障类型 (如 Disk Full)
  job_name TEXT NOT NULL,           -- Job 名称
  job_id TEXT,                      -- Job ID
  timestamp TEXT NOT NULL,          -- 发生时间
  evidence TEXT,                    -- 证据/日志
  resource_kind TEXT DEFAULT 'Unknown'  -- 资源类型
);

-- ============================================
-- Jira Ticket 表
-- ============================================
CREATE TABLE IF NOT EXISTS jira_tickets (
  id TEXT PRIMARY KEY,              -- "PROJ-456"
  key TEXT NOT NULL UNIQUE,         -- Jira Key (唯一)
  summary TEXT NOT NULL,            -- 摘要
  status TEXT DEFAULT 'Open',       -- Open/In Progress/Done/Closed
  created_at TEXT NOT NULL,         -- 创建时间
  updated_at TEXT,                  -- 更新时间
  reporter TEXT,                    -- 报告人
  assignee TEXT,                    -- 负责人
  priority TEXT DEFAULT 'Medium',   -- Priority
  url TEXT,                         -- Jira URL
  notes TEXT,                       -- 备注说明
  problem_count INTEGER DEFAULT 0   -- 关联的问题数（冗余字段，便于统计）
);

-- ============================================
-- Slack Thread 表
-- ============================================
CREATE TABLE IF NOT EXISTS slack_threads (
  id TEXT PRIMARY KEY,              -- thread_ts 或自定义 ID
  channel TEXT NOT NULL,            -- Slack channel
  message_url TEXT,                 -- 消息 URL
  summary TEXT,                     -- 讨论摘要
  created_at TEXT NOT NULL,         -- 创建时间
  last_activity TEXT,               -- 最后活跃时间
  participants_count INTEGER DEFAULT 0,  -- 参与人数
  is_resolved BOOLEAN DEFAULT 0,    -- 是否已解决
  notes TEXT                        -- 备注说明
);

-- ============================================
-- 问题与 Jira 的多对多关联表
-- ============================================
CREATE TABLE IF NOT EXISTS problem_jira_links (
  problem_id TEXT NOT NULL,
  jira_ticket_id TEXT NOT NULL,
  linked_at TEXT NOT NULL,          -- 关联时间
  linked_by TEXT DEFAULT 'manual',  -- manual/auto/batch
  note TEXT,                        -- 关联说明
  PRIMARY KEY (problem_id, jira_ticket_id),
  FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
  FOREIGN KEY (jira_ticket_id) REFERENCES jira_tickets(id) ON DELETE CASCADE
);

-- ============================================
-- 问题与 Slack 的多对多关联表
-- ============================================
CREATE TABLE IF NOT EXISTS problem_slack_links (
  problem_id TEXT NOT NULL,
  slack_thread_id TEXT NOT NULL,
  linked_at TEXT NOT NULL,          -- 关联时间
  summary TEXT,                     -- 这次沟通的结论
  is_resolved BOOLEAN DEFAULT 0,    -- 是否通过此沟通解决
  PRIMARY KEY (problem_id, slack_thread_id),
  FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
  FOREIGN KEY (slack_thread_id) REFERENCES slack_threads(id) ON DELETE CASCADE
);

-- ============================================
-- 索引优化（提升查询性能）
-- ============================================

-- 基础表索引
CREATE INDEX IF NOT EXISTS idx_problems_timestamp ON problems(timestamp);
CREATE INDEX IF NOT EXISTS idx_problems_fault_type ON problems(fault_type);
CREATE INDEX IF NOT EXISTS idx_problems_resource_kind ON problems(resource_kind);
CREATE INDEX IF NOT EXISTS idx_problems_job_id ON problems(job_id);

-- 关联表索引
CREATE INDEX IF NOT EXISTS idx_problem_jira ON problem_jira_links(problem_id);
CREATE INDEX IF NOT EXISTS idx_jira_problem ON problem_jira_links(jira_ticket_id);
CREATE INDEX IF NOT EXISTS idx_problem_slack ON problem_slack_links(problem_id);
CREATE INDEX IF NOT EXISTS idx_slack_problem ON problem_slack_links(slack_thread_id);

-- Jira 表索引
CREATE INDEX IF NOT EXISTS idx_jira_status ON jira_tickets(status);
CREATE INDEX IF NOT EXISTS idx_jira_created ON jira_tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_jira_key ON jira_tickets(key);

-- Slack 表索引
CREATE INDEX IF NOT EXISTS idx_slack_channel ON slack_threads(channel);
CREATE INDEX IF NOT EXISTS idx_slack_resolved ON slack_threads(is_resolved);
CREATE INDEX IF NOT EXISTS idx_slack_created ON slack_threads(created_at);

-- ============================================
-- 视图：简化报表查询
-- ============================================

-- 问题汇总视图（按资源和故障类型）
CREATE VIEW IF NOT EXISTS v_problem_summary AS
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

-- Jira Ticket 汇总视图
CREATE VIEW IF NOT EXISTS v_jira_summary AS
SELECT 
  j.key,
  j.summary,
  j.status,
  j.priority,
  j.problem_count,
  j.created_at,
  j.updated_at,
  GROUP_CONCAT(p.fault_type, ', ') as fault_types,
  MIN(p.timestamp) as first_problem,
  MAX(p.timestamp) as last_problem
FROM jira_tickets j
LEFT JOIN problem_jira_links pj ON j.id = pj.jira_ticket_id
LEFT JOIN problems p ON pj.problem_id = p.id
GROUP BY j.id, j.key, j.summary, j.status, j.priority, j.problem_count;

-- Slack 沟通汇总视图
CREATE VIEW IF NOT EXISTS v_slack_summary AS
SELECT 
  st.channel,
  st.is_resolved,
  COUNT(DISTINCT st.id) as thread_count,
  SUM(COALESCE(st.participants_count, 0)) as total_participants,
  COUNT(DISTINCT ps.problem_id) as related_problems
FROM slack_threads st
LEFT JOIN problem_slack_links ps ON st.id = ps.slack_thread_id
GROUP BY st.channel, st.is_resolved;

-- ============================================
-- 数据完整性触发器
-- ============================================

-- 更新 jira_tickets.problem_count (INSERT)
CREATE TRIGGER IF NOT EXISTS trg_update_jira_problem_count_after_insert
AFTER INSERT ON problem_jira_links
BEGIN
  UPDATE jira_tickets 
  SET problem_count = problem_count + 1
  WHERE id = NEW.jira_ticket_id;
END;

-- 更新 jira_tickets.problem_count (DELETE)
CREATE TRIGGER IF NOT EXISTS trg_update_jira_problem_count_after_delete
AFTER DELETE ON problem_jira_links
BEGIN
  UPDATE jira_tickets 
  SET problem_count = problem_count - 1
  WHERE id = OLD.jira_ticket_id;
END;
