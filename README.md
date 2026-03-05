# VSI-AI-OM 智能运维系统

基于 MCP Protocol + AI Agent 的运维自动化系统。

---

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────┐
│            用户交互层                        │
│  CLI / Python API                           │
└──────────────┬──────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────┐
│         AI Agent 层                          │
│  • 故障修复 Agent                            │
│  • 沟通文案 Agent（吵架助手）✨              │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴───────┐
       ↓               ↓
┌─────────────┐ ┌─────────────┐
│ MCP Service │ │  LLM Qwen   │
│ (数据服务)  │ │ (文案生成)  │
└──────┬──────┘ └─────────────┘
       │
       ↓
┌─────────────────────────────────────────────┐
│          Database                           │
│  problems.db + RAG ChromaDB                │
└─────────────────────────────────────────────┘
```

---

## 🚀 核心功能

### 1. 自动故障修复

**场景**: Jenkins Job 失败时自动处理

```python
from agent.ai_om_agent import handle_failure

result = handle_failure("disk full", "job-123")
# → 自动清理磁盘并重试
```

**技术栈**:
- RAG: ChromaDB + BM25 混合检索
- Agent: LangChain ReAct 模式
- Tools: retry_job, clean_disk, restart_docker

---

### 2. 智能沟通助手（吵架助手）✨

**场景**: 需要向其他团队反馈问题时

```bash
# 查询 Jenkins 过去 3 天的问题并生成文案
python -m agent.argument_agent --target Jenkins --days 3
```

**输出**:
- ✅ Slack 文案（@团队 + 关键数据）
- ✅ Jira Issue 描述（正式报告）
- ✅ 完整证据链

**特点**:
- 按需触发，不主动发送
- 基于真实数据
- 格式友好，可直接复制

---

## 📦 安装配置

### 环境变量

```bash
# Windows PowerShell
$env:DASHSCOPE_API_KEY="your-api-key"

# Linux/Mac
export DASHSCOPE_API_KEY="your-api-key"
```

### 依赖安装

```bash
pip install -r requirements.txt
```

---

## 💡 使用示例

### 故障修复

```python
# 测试用例
python agent/ai_om_agent.py
```

### 沟通文案

```bash
# 基础用法
python -m agent.argument_agent --target Jenkins

# 自定义时间
python -m agent.argument_agent --target DRP --days 7

# 特定问题
python -m agent.argument_agent --target Jenkins --fault-type "build failed"
```

---

## 🎯 MCP Service

### 标准工具

| 工具 | 说明 |
|------|------|
| `log_problem()` | 记录故障问题 |
| `search_problems()` | 查询历史问题 |
| `get_argument_ammo()` ✨ | 获取吵架弹药包 |
| `escalate_problem()` | 生成升级报告 |

### 资源访问

```
problem://{problem_id}  # 获取单个问题详情
```

---

## 📊 数据库 Schema

```sql
CREATE TABLE problems (
  id TEXT PRIMARY KEY,
  fault_type TEXT,
  job_name TEXT NOT NULL,
  job_id TEXT,
  timestamp TEXT,
  evidence TEXT,
  resource_kind TEXT  -- Jenkins/Artifactory/DRP/SRO/LabOps/GitHub/IT/Unknown
);
```

---

## 🧪 测试

```bash
# MCP Service 测试
python mcp_service/test_mcp_service.py

# Resource Kind 测试
python mcp_service/test_resource_kind.py

# Argument Agent 测试
python test_argument_agent.py
```

---

## 📁 项目结构

```
Intelligent-Ops-System/
├── agent/
│   ├── ai_om_agent.py          # 故障修复 Agent
│   ├── argument_agent.py       # 沟通文案 Agent ✨
│   └── prompt.py               # Prompt 模板
├── mcp_service/
│   ├── mcp_server.py           # MCP 服务端
│   ├── mcp_client.py           # MCP 客户端
│   └── problems.db             # 问题数据库
├── rag/
│   ├── build_rag.py            # RAG 构建
│   └── hybrid_retriever.py     # 混合检索器
├── test_argument_agent.py      # 集成测试
├── requirements.txt
└── docker-compose.yml
```

---

## 🎓 技术亮点

### 1. MCP Protocol 标准实践 ✅

- Tool 定义符合规范
- Resource URI 模式
- 支持 Agent 编排

### 2. Agentic Workflow 案例 ✅

- 数据驱动决策
- Tool Use 模式
- 分层架构清晰

### 3. 大模型应用开发 ✅

- RAG + Agent 结合
- LLM 文案生成
- 提示词工程

### 4. 工程素养 ✅

- Pydantic Schema
- 向后兼容设计
- 完整测试覆盖

---

## 📖 文档

- [MCP Service 使用指南](mcp_service/USAGE_GUIDE.md)
- [Resource Kind 字段说明](mcp_service/RESOURCE_KIND_GUIDE.md)
- [Argument Agent 文档](agent/README_ARGUMENT_AGENT.md)
- [实现总结](mcp_service/IMPLEMENTATION_SUMMARY.md)
- [更新日志](mcp_service/CHANGELOG.md)

---

## 💼 简历价值

**适合写入简历的技术点**:

```
项目：基于 MCP 的 AI 运维助手

• 基于 MCP Protocol 设计标准化数据服务，提供 get_argument_ammo 等工具
• 构建双 Agent 系统（修复 Agent + 沟通 Agent），展示 Agentic Workflow 实践
• 采用分层架构（数据层-Agent 层 - 表现层），职责清晰
• 使用 Pydantic 定义 Schema，类型安全，符合企业级开发规范
• 包含完整的测试套件，展示工程素养
```

---

## 🚧 后续扩展

- [ ] 添加邮件发送功能
- [ ] 支持更多资源类型
- [ ] 添加问题趋势预测
- [ ] Web UI 界面

---

## 📝 License

MIT
