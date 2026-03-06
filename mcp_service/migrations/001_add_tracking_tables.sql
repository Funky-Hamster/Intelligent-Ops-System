-- /vsi-ai-om/mcp_service/migrations/001_add_tracking_tables.sql
-- 问题追踪与报表系统 - 数据库迁移
-- 执行时间：2026-03-06

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
CREATE INDEX IF NOT EXISTS idx_problem_jira ON problem_jira_links(problem_id);
CREATE INDEX IF NOT EXISTS idx_jira_problem ON problem_jira_links(jira_ticket_id);
CREATE INDEX IF NOT EXISTS idx_problem_slack ON problem_slack_links(problem_id);
CREATE INDEX IF NOT EXISTS idx_slack_problem ON problem_slack_links(slack_thread_id);

CREATE INDEX IF NOT EXISTS idx_jira_status ON jira_tickets(status);
CREATE INDEX IF NOT EXISTS idx_jira_created ON jira_tickets(created_at);

CREATE INDEX IF NOT EXISTS idx_slack_channel ON slack_threads(channel);
CREATE INDEX IF NOT EXISTS idx_slack_resolved ON slack_threads(is_resolved);

-- ============================================
-- 视图：简化报表查询
-- ============================================
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

-- ============================================
-- 数据完整性触发器
-- ============================================

-- 更新 jira_tickets.problem_count
CREATE TRIGGER IF NOT EXISTS trg_update_jira_problem_count_after_insert
AFTER INSERT ON problem_jira_links
BEGIN
  UPDATE jira_tickets 
  SET problem_count = problem_count + 1
  WHERE id = NEW.jira_ticket_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_update_jira_problem_count_after_delete
AFTER DELETE ON problem_jira_links
BEGIN
  UPDATE jira_tickets 
  SET problem_count = problem_count - 1
  WHERE id = OLD.jira_ticket_id;
END;
