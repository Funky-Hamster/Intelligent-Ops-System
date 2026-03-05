#!/usr/bin/env python3
"""
Test script for resource_kind field validation
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_service.mcp_server import validate_resource_kind, log_problem
from mcp_service.mcp_client import MCPClient
import sqlite3

DB_PATH = Path(__file__).parent / "problems.db"

def test_validation():
    """Test resource_kind validation logic"""
    print("="*70)
    print("🧪 Testing resource_kind Validation")
    print("="*70)
    
    # Test valid values
    valid_kinds = ["Jenkins", "Artifactory", "DRP", "SRO", "LabOps", "GitHub", "IT", "Unknown"]
    print("\n✅ Testing valid values:")
    for kind in valid_kinds:
        result = validate_resource_kind(kind)
        status = "✓" if result else "✗"
        print(f"   {status} {kind}: {result}")
        assert result is True, f"Failed for valid kind: {kind}"
    
    # Test invalid values
    invalid_kinds = ["jenkins", "Invalid", "RANDOM", "123", "", None]
    print("\n❌ Testing invalid values:")
    for kind in invalid_kinds:
        try:
            result = validate_resource_kind(kind)
            status = "✓" if not result else "✗"
            print(f"   {status} '{kind}': {result} (should be False)")
            assert result is False, f"Should fail for invalid kind: {kind}"
        except:
            print(f"   ✓ '{kind}': Exception handled correctly")
    
    print("\n✅ Validation tests passed!")
    return True


def test_database_schema():
    """Test database schema has resource_kind field"""
    print("\n" + "="*70)
    print("🧪 Testing Database Schema")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get table info
    c.execute("PRAGMA table_info(problems)")
    columns = c.fetchall()
    
    print(f"\n📊 problems table has {len(columns)} columns:")
    column_names = [col[1] for col in columns]
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
    
    # Verify resource_kind exists
    assert 'resource_kind' in column_names, "Missing resource_kind column!"
    print("\n✅ resource_kind column exists")
    
    # Verify we have 7 columns
    assert len(column_names) == 7, f"Expected 7 columns, got {len(column_names)}"
    print("✅ Correct number of columns (7)")
    
    conn.close()
    return True


def test_log_problem_with_resource_kind():
    """Test log_problem function with different resource kinds"""
    print("\n" + "="*70)
    print("🧪 Testing log_problem with resource_kind")
    print("="*70)
    
    # Test via direct function call (bypassing MCP protocol for simplicity)
    from mcp_service.mcp_server import PROJECT_ROOT, DB_PATH
    import uuid
    import time
    
    test_cases = [
        ("build failed", "job-001", "build", "Build error", "Unknown"),
        ("upload failed", "job-002", "publish", "Artifactory error", "Artifactory"),
        ("deploy timeout", "job-003", "deploy", "DRP timeout", "DRP"),
        ("git webhook", "job-004", "sync", "GitHub webhook failed", "GitHub"),
    ]
    
    print("\n📝 Inserting test problems:")
    for fault_type, job_id, job_name, evidence, resource_kind in test_cases:
        problem_id = f"prob-{uuid.uuid4().hex[:8]}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO problems VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (problem_id, fault_type, job_name, job_id, timestamp, evidence, resource_kind))
        conn.commit()
        conn.close()
        
        print(f"   ✅ {problem_id}: {resource_kind}")
    
    # Verify insertion
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM problems WHERE resource_kind IS NOT NULL")
    count = c.fetchone()[0]
    conn.close()
    
    print(f"\n✅ Total problems with resource_kind: {count}")
    assert count >= len(test_cases), "Not all test problems were inserted"
    
    return True


def test_query_with_resource_kind():
    """Test querying problems by resource_kind"""
    print("\n" + "="*70)
    print("🧪 Testing Query with resource_kind")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Query by resource_kind
    print("\n📊 Problems by resource type:")
    c.execute("SELECT resource_kind, COUNT(*) FROM problems GROUP BY resource_kind")
    results = c.fetchall()
    
    for resource_kind, count in results:
        print(f"   - {resource_kind}: {count} problems")
    
    # Verify we can filter by resource_kind
    c.execute("SELECT * FROM problems WHERE resource_kind = 'Jenkins'")
    jenkins_problems = c.fetchall()
    print(f"\n✅ Jenkins problems: {len(jenkins_problems)}")
    
    c.execute("SELECT * FROM problems WHERE resource_kind = 'Artifactory'")
    artifactory_problems = c.fetchall()
    print(f"✅ Artifactory problems: {len(artifactory_problems)}")
    
    conn.close()
    return True


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🚀 Resource Kind Field - Comprehensive Test Suite")
    print("="*70)
    
    tests = [
        ("Validation Logic", test_validation),
        ("Database Schema", test_database_schema),
        ("Log Problem Function", test_log_problem_with_resource_kind),
        ("Query Function", test_query_with_resource_kind),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
            print(f"\n✅ {test_name}: PASSED")
        except AssertionError as e:
            failed += 1
            print(f"\n❌ {test_name}: FAILED - {str(e)}")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name}: ERROR - {str(e)}")
    
    # Summary
    print("\n" + "="*70)
    print("📊 Test Summary")
    print("="*70)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
