# 吵架助手 - Argument Agent

## 📢 功能说明

基于 MCP 提供的数据，自动生成 Slack 和 Jira 沟通文案。

**核心特点**：
- ✅ **按需触发** - 只有你运行命令时才工作
- ✅ **数据驱动** - 基于真实问题数据
- ✅ **文案生成** - LLM 生成专业表达
- ✅ **即拿即用** - 格式友好，可直接复制

---

## 🚀 快速开始

### 前置条件

1. 设置环境变量：
```bash
# Windows PowerShell
$env:DASHSCOPE_API_KEY="your-api-key"

# Linux/Mac
export DASHSCOPE_API_KEY="your-api-key"
```

2. 确保已安装依赖：
```bash
pip install langchain-community dashscope
```

---

## 💡 使用示例

### 基础用法

```bash
# 查询 Jenkins 过去 3 天的问题
python -m agent.argument_agent --target Jenkins
```

### 自定义时间范围

```bash
# 查询过去 7 天
python -m agent.argument_agent --target Jenkins --days 7

# 查询过去 14 天
python -m agent.argument_agent --target DRP --days 14
```

### 指定故障类型

```bash
# 只查询构建失败的问题
python -m agent.argument_agent --target Jenkins --fault-type "build failed"

# 只查询部署超时的问题
python -m agent.argument_agent --target DRP --fault-type "deploy timeout"
```

---

## 📊 输出示例

```
======================================================================
📊 数据摘要
======================================================================
Jenkins 过去 3 天共发生 15 起故障，影响 12 个 Job，涉及 5 种故障类型

总故障数：15
影响 Job 数：12
故障类型数：5

======================================================================
💬 Slack 文案（可直接复制）
======================================================================
@jenkins-team 📢 

过去**3 天**内，Jenkins 共发生**15 起**故障，影响**12 个**Job。

主要问题:
• build failed - 8 次 (53%)
• disk full - 4 次 (27%)

建议优先检查构建配置和磁盘空间...

======================================================================
📝 Jira 文案（可直接复制）
======================================================================
h3. 问题概述

在过去 *3 天* 内，*Jenkins* 资源共发生 *15 起* 故障，影响 *12 个* Job。

h3. 统计数据
|| 指标 || 数值 ||
| 总故障数 | 15 |
| 故障类型 | 5 |
| 影响 Job 数 | 12 |

h3. 故障类型分布
# build failed - 8 次 (53%)
# disk full - 4 次 (27%)

h3. 建议行动项
* 立即检查 Jenkins agent 磁盘空间
* 审查 build 配置是否有资源泄漏

======================================================================
✅ 文案生成完成！
======================================================================
```

---

## 🔧 参数说明

| 参数 | 简写 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--target` | `-t` | ✅ | - | 资源类型 |
| `--days` | `-d` | ❌ | 3 | 查询天数 |
| `--fault-type` | `-f` | ❌ | None | 故障类型 |

---

## 🎯 支持的资源类型

- `Jenkins` - Jenkins 构建服务
- `Artifactory` - Artifactory 制品库
- `DRP` - DRP 部署平台
- `SRO` - SRO 运行服务
- `LabOps` - LabOps 实验室管理
- `GitHub` - GitHub 代码仓库
- `IT` - IT 基础设施
- `Unknown` - 未知资源类型

---

## 🏗️ 技术架构

```
用户命令
  ↓
Argument Agent
  ↓
├─→ MCP Service (获取数据)
│     └─→ problems.db
│
└─→ LLM Qwen (生成文案)
      ├─→ Slack 文案
      └─→ Jira 文案
```

---

## 📝 最佳实践

### 1. 选择合适的资源类型

```bash
# ✅ 明确知道是哪个团队
python -m agent.argument_agent --target Jenkins

# ✅ 不确定时标记为 Unknown
python -m agent.argument_agent --target Unknown --fault-type "network error"
```

### 2. 合理的时间范围

```bash
# ✅ 日常检查：3 天
python -m agent.argument_agent --target Jenkins --days 3

# ✅ 周报：7 天
python -m agent.argument_agent --target Jenkins --days 7

# ✅ 月度总结：30 天
python -m agent.argument_agent --target Jenkins --days 30
```

### 3. 针对性沟通

```bash
# ✅ 针对特定问题
python -m agent.argument_agent --target Jenkins --fault-type "build failed"

# ✅ 全面总结（不指定 fault-type）
python -m agent.argument_agent --target Jenkins
```

---

## ⚠️ 注意事项

1. **API Key**: 必须设置 `DASHSCOPE_API_KEY` 环境变量
2. **网络**: 需要访问阿里云 DashScope API
3. **语气**: 生成的文案是辅助工具，发送前请人工审核
4. **隐私**: 不要包含敏感信息

---

## 🎓 设计亮点

- ✅ **MCP Protocol 标准实践**
- ✅ **Agentic Workflow 案例**
- ✅ **数据驱动文案生成**
- ✅ **分层架构设计**

---

## 📖 相关文档

- [MCP Service 使用指南](../mcp_service/USAGE_GUIDE.md)
- [resource_kind 字段说明](../mcp_service/RESOURCE_KIND_GUIDE.md)
- [项目架构](../README.md)
