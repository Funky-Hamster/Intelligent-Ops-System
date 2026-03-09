"""
生成 MCP 测试数据

功能：
- 生成 Jenkins 与 Jenkins node 连接时断时续的故障数据
- 生成 Artifactory 500 错误的故障数据
- 生成其他常见故障数据
- 写入 MCP problems 数据库
"""

import sqlite3
import uuid
from datetime import datetime, timedelta
import random

# 数据库路径
DB_PATH = "mcp_service/problems.db"

def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def generate_id(prefix="prob"):
    """生成唯一 ID"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

def generate_timestamp(days_ago=0, hours_ago=0, minutes_ago=0):
    """生成时间戳"""
    now = datetime.now()
    past = now - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
    return past.strftime("%Y-%m-%d %H:%M:%S")

def create_jenkins_node_connectivity_issues(count=10):
    """
    生成 Jenkins 与 Jenkins node 连接时断时续的故障数据
    
    特征：
    - 故障类型：Node Offline / Connection Lost
    - 资源类型：Jenkins
    - 证据：包含 SSH 连接超时、JNLP 断开等信息
    """
    problems = []
    
    job_names = [
        "vsi-ui-build", "iapi-core-test", "data-pipeline-sync",
        "frontend-deploy", "backend-integration", "microservice-health-check"
    ]
    
    job_ids = [str(random.randint(10000, 99999)) for _ in range(20)]
    
    error_messages = [
        "ERROR: Node 'agent-01' is offline. Connection was lost.",
        "WARNING: SSH connection timeout after 30 seconds to agent-host",
        "SEVERE: JNLP agent disconnected unexpectedly",
        "ERROR: Cannot reach Jenkins agent at tcp://agent-02:50000",
        "WARNING: Agent node temporarily unavailable. Retrying...",
        "ERROR: Connection refused when trying to connect to agent-03",
        "SEVERE: Node 'build-agent-01' has been offline for 5 minutes",
        "ERROR: Slave connection failed. java.io.EOFException",
        "WARNING: Agent 'docker-builder' is not responding. Marked as offline.",
        "ERROR: Failed to launch agent via SSH. Connection timed out."
    ]
    
    suggestions = [
        "Check agent network connectivity and firewall rules",
        "Verify Jenkins agent service status on the node",
        "Increase agent JVM heap size (-Xmx2g)",
        "Check Jenkins master-agent security configuration",
        "Review agent logs at /var/log/jenkins/agent.log",
        "Restart Jenkins agent service: systemctl restart jenkins-agent",
        "Verify JNLP port (50000) is accessible from master",
        "Check DNS resolution for agent hostname"
    ]
    
    for i in range(count):
        problem_id = generate_id()
        timestamp = generate_timestamp(
            days_ago=random.randint(0, 7),
            hours_ago=random.randint(0, 23),
            minutes_ago=random.randint(0, 59)
        )
        
        job_name = random.choice(job_names)
        job_id = random.choice(job_ids)
        error_msg = random.choice(error_messages)
        suggestion = random.choice(suggestions)
        
        evidence = f"""Log Snippet:
{error_msg}

Stack Trace:
at hudson.slaves.SlaveComputer.trySetOffline(SlaveComputer.java:123)
at hudson.model.Node.setOffline(Node.java:456)

AI Suggestion: {suggestion}

Retry Action: retry_job
Failure Reason: Agent node unavailable during build execution"""
        
        problems.append({
            "id": problem_id,
            "fault_type": "Node Connectivity Issue",
            "job_name": job_name,
            "job_id": job_id,
            "timestamp": timestamp,
            "evidence": evidence,
            "resource_kind": "Jenkins"
        })
    
    return problems

def create_artifactory_500_errors(count=8):
    """
    生成 Artifactory 500 Internal Server Error 的故障数据
    
    特征：
    - 故障类型：Artifactory 500 Error
    - 资源类型：Artifactory
    - 证据：包含 HTTP 500、部署失败等信息
    """
    problems = []
    
    job_names = [
        "artifact-deploy-prod", "npm-publish", "maven-release",
        "docker-push-latest", "container-image-build"
    ]
    
    job_ids = [str(random.randint(10000, 99999)) for _ in range(20)]
    
    error_messages = [
        "ERROR: Failed to deploy artifact: HTTP 500 Internal Server Error",
        "SEVERE: Artifactory returned 500 during upload: myapp-1.0.0.jar",
        "ERROR: Deployment failed. Remote end closed connection without response",
        "WARNING: Artifactory service temporarily unavailable (500)",
        "ERROR: Failed to upload to libs-release-local. HTTP 500",
        "SEVERE: Artifactory backend storage error. Check disk space.",
        "ERROR: Maven deployment failed: Could not transfer artifact. 500 Service Error",
        "ERROR: NPM publish failed. Registry responded with 500"
    ]
    
    suggestions = [
        "Check Artifactory service health: systemctl status artifactory",
        "Verify Artifactory disk space: df -h /var/opt/artifactory",
        "Review Artifactory logs: /var/opt/artifactory/log/artifactory.log",
        "Check database connectivity (Artifactory uses PostgreSQL/MySQL)",
        "Restart Artifactory service if necessary",
        "Verify reverse proxy (Nginx) configuration",
        "Check Artifactory license validity"
    ]
    
    for i in range(count):
        problem_id = generate_id()
        timestamp = generate_timestamp(
            days_ago=random.randint(0, 7),
            hours_ago=random.randint(0, 23),
            minutes_ago=random.randint(0, 59)
        )
        
        job_name = random.choice(job_names)
        job_id = random.choice(job_ids)
        error_msg = random.choice(error_messages)
        suggestion = random.choice(suggestions)
        
        evidence = f"""HTTP Response:
Status Code: 500 Internal Server Error

Request Details:
PUT https://artifactory.company.com/libs-release-local/myapp/1.0.0/myapp-1.0.0.jar
Content-Length: 2456789

Error Message:
{error_msg}

AI Suggestion: {suggestion}

Retry Action: log_to_mcp
Failure Reason: Artifactory service returned 500 error repeatedly"""
        
        problems.append({
            "id": problem_id,
            "fault_type": "Artifactory 500 Error",
            "job_name": job_name,
            "job_id": job_id,
            "timestamp": timestamp,
            "evidence": evidence,
            "resource_kind": "Artifactory"
        })
    
    return problems

def create_retry_failures(count=5):
    """
    生成 retry_job 失败的故障数据（用于追踪 TechOps 服务问题）
    """
    problems = []
    
    for i in range(count):
        problem_id = generate_id()
        timestamp = generate_timestamp(
            days_ago=random.randint(0, 5),
            hours_ago=random.randint(0, 23),
            minutes_ago=random.randint(0, 59)
        )
        
        job_id = str(random.randint(10000, 99999))
        
        evidence = f"""Retry Action: retry_job
Failure Reason: Connection timeout after 60 seconds

Jenkins API Response:
curl: (7) Failed to connect to localhost port 8080: Connection timed out

AI Suggestion: TechOps service may be unavailable. Check Jenkins API connectivity.

Troubleshooting Steps:
1. Verify Jenkins service status: systemctl status jenkins
2. Check Jenkins logs: /var/log/jenkins/jenkins.log
3. Test API endpoint: curl -I http://localhost:8080
4. Review firewall rules: iptables -L -n"""
        
        problems.append({
            "id": problem_id,
            "fault_type": "RetryFailure",
            "job_name": "build",
            "job_id": job_id,
            "timestamp": timestamp,
            "evidence": evidence,
            "resource_kind": "Jenkins"
        })
    
    return problems

def create_disk_full_issues(count=3):
    """
    生成磁盘空间耗尽的故障数据
    """
    problems = []
    
    for i in range(count):
        problem_id = generate_id()
        timestamp = generate_timestamp(
            days_ago=random.randint(0, 10),
            hours_ago=random.randint(0, 23),
            minutes_ago=random.randint(0, 59)
        )
        
        evidence = f"""Disk Usage:
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1       100G   98G  2.0G  98% /var/jenkins

Error Message:
No space left on device

Build Failure:
ERROR: Failed to write to workspace: /var/jenkins/workspace/vsi-ui-build
java.io.IOException: No space left on device

AI Suggestion: Clean old builds and workspace to free up disk space.

Cleanup Commands:
1. Find large files: find /var/jenkins -type f -size +100M
2. Clean old builds: rm -rf /var/jenkins/jobs/*/builds/[0-9]*
3. Clear workspace: rm -rf /var/jenkins/workspace/*
4. Empty trash: rm -rf /var/jenkins/.trash/*"""
        
        problems.append({
            "id": problem_id,
            "fault_type": "Disk Full",
            "job_name": "vsi-ui-build",
            "job_id": str(random.randint(10000, 99999)),
            "timestamp": timestamp,
            "evidence": evidence,
            "resource_kind": "Jenkins"
        })
    
    return problems

def insert_problems(problems):
    """
    批量插入问题到数据库
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    inserted_count = 0
    
    for problem in problems:
        try:
            cursor.execute("""
                INSERT INTO problems (id, fault_type, job_name, job_id, timestamp, evidence, resource_kind)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                problem["id"],
                problem["fault_type"],
                problem["job_name"],
                problem["job_id"],
                problem["timestamp"],
                problem["evidence"],
                problem["resource_kind"]
            ))
            inserted_count += 1
            print(f"✅ Inserted: {problem['id']} - {problem['fault_type']} ({problem['job_name']})")
        except Exception as e:
            print(f"❌ Failed to insert {problem['id']}: {str(e)}")
    
    conn.commit()
    conn.close()
    
    return inserted_count

def print_summary():
    """打印数据库统计信息"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("📊 数据库统计")
    print("="*80)
    
    # 总问题数
    cursor.execute("SELECT COUNT(*) as total FROM problems")
    total = cursor.fetchone()["total"]
    print(f"\n总问题数：{total}")
    
    # 按故障类型统计
    cursor.execute("""
        SELECT fault_type, resource_kind, COUNT(*) as count
        FROM problems
        GROUP BY fault_type, resource_kind
        ORDER BY count DESC
    """)
    
    print("\n按故障类型和资源分类:")
    print("-"*80)
    print(f"{'故障类型':<30} {'资源类型':<15} {'数量':>10}")
    print("-"*80)
    
    for row in cursor.fetchall():
        print(f"{row['fault_type']:<30} {row['resource_kind']:<15} {row['count']:>10}")
    
    # 按资源类型统计
    cursor.execute("""
        SELECT resource_kind, COUNT(*) as count
        FROM problems
        GROUP BY resource_kind
        ORDER BY count DESC
    """)
    
    print("\n按资源类型统计:")
    print("-"*80)
    print(f"{'资源类型':<20} {'数量':>10}")
    print("-"*80)
    
    for row in cursor.fetchall():
        print(f"{row['resource_kind']:<20} {row['count']:>10}")
    
    # 最近的问题
    cursor.execute("""
        SELECT id, fault_type, job_name, timestamp
        FROM problems
        ORDER BY timestamp DESC
        LIMIT 5
    """)
    
    print("\n最近 5 个问题:")
    print("-"*80)
    for row in cursor.fetchall():
        print(f"  {row['id']} - {row['fault_type']} ({row['job_name']}) @ {row['timestamp']}")
    
    conn.close()
    print("\n" + "="*80)

def main():
    """主函数"""
    print("="*80)
    print("生成 MCP 测试数据")
    print("="*80)
    print()
    
    # 生成各类故障数据
    print("正在生成测试数据...")
    print("-"*80)
    
    jenkins_node_issues = create_jenkins_node_connectivity_issues(count=10)
    print(f"✅ Jenkins Node 连接问题：{len(jenkins_node_issues)} 条")
    
    artifactory_500 = create_artifactory_500_errors(count=8)
    print(f"✅ Artifactory 500 错误：{len(artifactory_500)} 条")
    
    retry_failures = create_retry_failures(count=5)
    print(f"✅ Retry 失败：{len(retry_failures)} 条")
    
    disk_full = create_disk_full_issues(count=3)
    print(f"✅ 磁盘空间耗尽：{len(disk_full)} 条")
    
    all_problems = jenkins_node_issues + artifactory_500 + retry_failures + disk_full
    print(f"\n总计：{len(all_problems)} 条")
    print()
    
    # 插入数据库
    print("正在写入数据库...")
    print("-"*80)
    inserted = insert_problems(all_problems)
    print(f"\n✅ 成功插入 {inserted}/{len(all_problems)} 条记录")
    
    # 打印统计
    print_summary()
    
    print("\n✅ 测试数据生成完成！")
    print("="*80)

if __name__ == "__main__":
    main()
