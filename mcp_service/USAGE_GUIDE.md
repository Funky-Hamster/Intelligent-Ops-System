# MCP Service 使用指南

## 📋 接口设计

### 1. log_problem - 记录故障

**用途**：记录无法解决的故障到数据库

**签名**：
```python
def log_problem_sync(
    fault_type: str,      # 故障类型（必填）
    job_id: str,          # Job ID（必填）
    job_name: str,        # Job 阶段名称（必填）
    evidence: str         # 证据链（必填）
) -> str
```

**使用示例**：
```python
from mcp_service.mcp_client import MCPClient

mcp_client = MCPClient()

# 记录构建失败
problem_id = mcp_client.log_problem_sync(
    fault_type="build failed",
    job_id="job-001",
    job_name="build",
    evidence="Build error log:\n- Missing dependency\n- Exit code 1"
)
print(f"Problem logged: {problem_id}")

# 记录测试失败
problem_id = mcp_client.log_problem_sync(
    fault_type="test failed",
    job_id="job-002",
    job_name="test",
    evidence="Test assertion failed:\n- Expected: 200\n- Actual: 500"
)
```

---

### 2. search_problems - 查询历史问题

**用途**：按故障类型和时间范围查询所有历史问题

**签名**：
```python
def search_problems_sync(
    fault_type: str = None,     # 故障类型（可选）
    start_time: str = None,     # 开始时间（可选，格式：YYYY-MM-DD HH:MM:SS）
    end_time: str = None        # 结束时间（可选，格式：YYYY-MM-DD HH:MM:SS）
) -> List[Dict]
```

**返回数据结构**：
```python
[
    {
        "id": "prob-866cce6d",
        "fault_type": "build failed",
        "job_name": "build",
        "job_id": "job-001",
        "timestamp": "2026-03-05 02:44:40",
        "evidence": "Build error log..."
    },
    ...
]
```

---

## 🔍 查询场景示例

### 场景 1：查询某类故障的所有历史记录

```python
# 查询所有 "build failed" 故障
results = mcp_client.search_problems_sync(
    fault_type="build failed"
)

print(f"找到 {len(results)} 条记录")
for r in results:
    print(f"- {r['id']}: {r['job_name']} ({r['timestamp']})")
```

### 场景 2：查询某个时间段内的所有故障

```python
# 查询今天的所有故障
from datetime import datetime

today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")
today_end = datetime.now().strftime("%Y-%m-%d 23:59:59")

results = mcp_client.search_problems_sync(
    start_time=today_start,
    end_time=today_end
)

print(f"今天发生 {len(results)} 起故障")
```

### 场景 3：查询某类故障在特定时间段内的所有信息（推荐）

```python
# 查询本周的 "build failed" 故障
week_start = "2026-03-01 00:00:00"
week_end = "2026-03-07 23:59:59"

results = mcp_client.search_problems_sync(
    fault_type="build failed",
    start_time=week_start,
    end_time=week_end
)

print(f"本周 'build failed' 故障统计:")
print(f"总数：{len(results)} 起")
print(f"\n详细列表:")
for r in results:
    print(f"  [{r['timestamp']}] {r['job_name']} - {r['job_id']}")
    print(f"    证据：{r['evidence'][:100]}...")
```

### 场景 4：故障趋势分析

```python
# 分析 "test failed" 故障的趋势
results = mcp_client.search_problems_sync(
    fault_type="test failed"
)

# 按日期分组统计
from collections import defaultdict
daily_stats = defaultdict(int)

for r in results:
    date = r['timestamp'].split()[0]  # 提取日期部分
    daily_stats[date] += 1

print("每日故障统计:")
for date, count in sorted(daily_stats.items()):
    print(f"  {date}: {count} 起")
```

### 场景 5：获取完整证据链

```python
# 获取最近一次故障的完整证据
results = mcp_client.search_problems_sync(
    fault_type="deploy failed"
)

if results:
    latest = results[-1]  # 最后一条记录
    print(f"最新故障 ID: {latest['id']}")
    print(f"发生时间：{latest['timestamp']}")
    print(f"Job 阶段：{latest['job_name']}")
    print(f"Job ID: {latest['job_id']}")
    print(f"\n完整证据:\n{latest['evidence']}")
```

---

## 📊 典型应用场景

### 1. 周期性故障报告

```python
# 生成周报
def generate_weekly_report(fault_type, week_start, week_end):
    results = mcp_client.search_problems_sync(
        fault_type=fault_type,
        start_time=week_start,
        end_time=week_end
    )
    
    report = f"# {fault_type} 周报\n\n"
    report += f"统计周期：{week_start} 至 {week_end}\n"
    report += f"故障总数：{len(results)} 起\n\n"
    
    # 按 Job 阶段分组
    job_stats = defaultdict(list)
    for r in results:
        job_stats[r['job_name']].append(r)
    
    for job_name, jobs in job_stats.items():
        report += f"## {job_name}\n"
        report += f"故障数：{len(jobs)} 起\n"
        for job in jobs:
            report += f"- [{job['timestamp']}] {job['job_id']}\n"
        report += "\n"
    
    return report
```

### 2. 故障模式识别

```python
# 识别高频故障 Job
def identify_problem_jobs(fault_type):
    results = mcp_client.search_problems_sync(fault_type=fault_type)
    
    job_counts = defaultdict(int)
    for r in results:
        job_counts[r['job_name']] += 1
    
    # 排序
    sorted_jobs = sorted(job_counts.items(), key=lambda x: x[1], reverse=True)
    
    print(f"{fault_type} 故障高发 Job 阶段:")
    for job_name, count in sorted_jobs[:5]:
        print(f"  {job_name}: {count} 起")
```

### 3. 时间相关性分析

```python
# 分析故障是否集中在特定时间段
def analyze_time_pattern(fault_type, days=7):
    from datetime import datetime, timedelta
    
    end = datetime.now()
    start = end - timedelta(days=days)
    
    results = mcp_client.search_problems_sync(
        fault_type=fault_type,
        start_time=start.strftime("%Y-%m-%d %H:%M:%S"),
        end_time=end.strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # 按小时统计
    hour_stats = defaultdict(int)
    for r in results:
        hour = r['timestamp'].split()[1].split(':')[0]
        hour_stats[hour] += 1
    
    print(f"近 {days} 天故障时间分布:")
    for hour in sorted(hour_stats.keys()):
        count = hour_stats[hour]
        bar = "█" * (count // 2)
        print(f"  {hour}:00 | {bar} ({count})")
```

---

## ⚠️ 注意事项

1. **时间格式**：必须为 `YYYY-MM-DD HH:MM:SS`
2. **fault_type**：建议使用统一的命名规范（如 `build failed`, `test failed`）
3. **job_name**：必填字段，用于标识 Job 阶段（如 `build`, `test`, `deploy`）
4. **查询性能**：建议添加时间范围限制，避免查询全量数据

---

## 🎯 最佳实践

### 1. 统一的故障类型命名

```python
# ✅ 推荐
fault_type = "build failed"
fault_type = "test failed"
fault_type = "deploy failed"
fault_type = "disk full"

# ❌ 不推荐
fault_type = "Build Error"  # 大小写不一致
fault_type = "构建失败"      # 语言不一致
fault_type = "error_123"    # 语义不明确
```

### 2. 合理的时间范围

```python
# ✅ 推荐：查询最近 24 小时
from datetime import datetime, timedelta

now = datetime.now()
yesterday = now - timedelta(days=1)

results = mcp_client.search_problems_sync(
    fault_type="build failed",
    start_time=yesterday.strftime("%Y-%m-%d %H:%M:%S"),
    end_time=now.strftime("%Y-%m-%d %H:%M:%S")
)

# ❌ 不推荐：无时间限制的全量查询
results = mcp_client.search_problems_sync(fault_type="build failed")
```

### 3. 结构化的证据信息

```python
# ✅ 推荐：结构化证据
evidence = """
Error Message: Connection timeout
Exit Code: 1
Log Snippet:
  [ERROR] Failed to connect to database
  [ERROR] Retry 1/3 failed
  [ERROR] Retry 2/3 failed
"""

# ❌ 不推荐：杂乱的信息
evidence = "error!!! connection failed omg"
```

---

## 📝 总结

**核心设计理念**：
- ✅ `search_problems` 只关注 **故障类型** 和 **时间范围**
- ✅ 返回该条件下的**所有**故障信息
- ✅ 不包含 `job_name` 查询参数，避免过度筛选
- ✅ 适合做故障统计、趋势分析、模式识别

**典型工作流**：
1. 使用 `log_problem` 记录故障（包含完整的 job_name 信息）
2. 使用 `search_problems` 按 fault_type + 时间范围查询
3. 在应用层对结果进行进一步分析和展示

这样设计的好处是可以在固定时间段内看到某个故障类型的全貌，而不是被单个 Job 名称限制视野。
