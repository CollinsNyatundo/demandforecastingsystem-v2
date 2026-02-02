#!/usr/bin/env python3
"""
Comprehensive Static Analysis Test Suite.

Tests the complete static analysis toolchain including:
- Ruff (linting, security, complexity)
- MyPy (type checking)  
- Bandit (security scanning)
- Coverage reporting
"""

import subprocess
import sys
import json
import os
from pathlib import Path

def run_command(cmd, description, cwd=None):
    """Run a command and return results."""
    print(f"\n🔍 {description}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=cwd,
            timeout=60
        )
        
        if result.returncode == 0:
            print(f"✅ {description} - SUCCESS")
            return True, result.stdout, result.stderr
        else:
            print(f"❌ {description} - FAILED (exit code: {result.returncode})")
            if result.stderr:
                print(f"Error: {result.stderr}")
            return False, result.stdout, result.stderr
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT")
        return False, "", "Command timed out"
    except Exception as e:
        print(f"💥 {description} - ERROR: {e}")
        return False, "", str(e)

def test_ruff_linting():
    """Test Ruff comprehensive linting configuration."""
    print("\n" + "="*60)
    print("🔧 RUFF STATIC ANALYSIS")
    print("="*60)
    
    # Test basic linting
    success, stdout, stderr = run_command(
        ["python", "-m", "ruff", "check", "src/", "--statistics"],
        "Ruff Comprehensive Linting"
    )
    
    if success:
        # Parse statistics
        lines = stdout.split('\n')
        stats_line = next((line for line in lines if 'Found' in line and 'errors' in line), "")
        if stats_line:
            print(f"📊 {stats_line}")
        
        # Show key rule categories found
        rule_counts = {}
        for line in lines:
            if '    ' in line and '[' in line and ']' in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    count = parts[0]
                    rule = parts[1]
                    if count.isdigit():
                        rule_counts[rule] = int(count)
        
        if rule_counts:
            print("\n📋 Key Issues Found:")
            security_rules = {k: v for k, v in rule_counts.items() if k.startswith('S')}
            complexity_rules = {k: v for k, v in rule_counts.items() if k.startswith('C90')}
            docstring_rules = {k: v for k, v in rule_counts.items() if k.startswith('D')}
            
            if security_rules:
                print(f"  🔒 Security: {sum(security_rules.values())} issues")
            if complexity_rules:
                print(f"  🧮 Complexity: {sum(complexity_rules.values())} issues")
            if docstring_rules:
                print(f"  📚 Documentation: {sum(docstring_rules.values())} issues")
    
    return success

def test_ruff_formatting():
    """Test Ruff formatting."""
    success, stdout, stderr = run_command(
        ["python", "-m", "ruff", "format", "src/", "--check"],
        "Ruff Formatting Check"
    )
    
    if success:
        print("✅ Code formatting is correct")
    else:
        print("⚠️  Code formatting issues found")
    
    return success

def test_bandit_security():
    """Test Bandit security scanning."""
    print("\n" + "="*60)
    print("🔒 BANDIT SECURITY SCANNING")
    print("="*60)
    
    success, stdout, stderr = run_command(
        ["python", "-m", "bandit", "-r", "src/", "-f", "json"],
        "Bandit Security Analysis"
    )
    
    if success and stdout:
        try:
            data = json.loads(stdout)
            results = data.get('results', [])
            
            if results:
                print(f"🚨 Found {len(results)} security issues:")
                
                # Group by severity
                high_issues = [r for r in results if r.get('issue_severity') == 'HIGH']
                medium_issues = [r for r in results if r.get('issue_severity') == 'MEDIUM']
                low_issues = [r for r in results if r.get('issue_severity') == 'LOW']
                
                if high_issues:
                    print(f"  🔴 HIGH: {len(high_issues)} issues")
                    for issue in high_issues[:3]:  # Show first 3
                        print(f"    - {issue.get('test_name', 'Unknown')}: {issue.get('issue_text', 'No description')}")
                
                if medium_issues:
                    print(f"  🟡 MEDIUM: {len(medium_issues)} issues")
                    for issue in medium_issues[:3]:  # Show first 3
                        print(f"    - {issue.get('test_name', 'Unknown')}: {issue.get('issue_text', 'No description')}")
                
                if low_issues:
                    print(f"  🟢 LOW: {len(low_issues)} issues")
                    for issue in low_issues[:3]:  # Show first 3
                        print(f"    - {issue.get('test_name', 'Unknown')}: {issue.get('issue_text', 'No description')}")
            else:
                print("✅ No security issues found")
                
        except json.JSONDecodeError:
            print("⚠️  Could not parse Bandit JSON output")
    
    return success

def test_mypy_types():
    """Test MyPy type checking."""
    print("\n" + "="*60)
    print("🔍 MYPY TYPE CHECKING")
    print("="*60)
    
    success, stdout, stderr = run_command(
        ["python", "-m", "mypy", "src/demand_forecasting", "--ignore-missing-imports"],
        "MyPy Type Analysis"
    )
    
    if success:
        print("✅ Type checking passed")
    else:
        print("⚠️  Type checking issues found")
        # Show first few type errors
        lines = stderr.split('\n')[:10]
        for line in lines:
            if line.strip():
                print(f"  {line}")
    
    return success

def test_coverage():
    """Test test coverage configuration."""
    print("\n" + "="*60)
    print("📊 COVERAGE CONFIGURATION")
    print("="*60)
    
    # Check if coverage is configured properly
    pyproject_path = Path("pyproject.toml")
    if pyproject_path.exists():
        content = pyproject_path.read_text()
        
        if "fail_under = 80" in content:
            print("✅ Coverage threshold set to 80%")
        else:
            print("⚠️  Coverage threshold not found")
        
        if "source = [\"src/demand_forecasting\"]" in content:
            print("✅ Coverage source configured")
        else:
            print("⚠️  Coverage source not configured")
        
        return True
    else:
        print("❌ pyproject.toml not found")
        return False

def main():
    """Run all static analysis tests."""
    print("🔧 COMPREHENSIVE STATIC ANALYSIS TEST SUITE")
    print("="*60)
    print("Testing complete static analysis toolchain...")
    
    # Change to app-ml directory
    os.chdir("app-ml")
    
    results = {}
    
    # Test all tools
    results['ruff_linting'] = test_ruff_linting()
    results['ruff_formatting'] = test_ruff_formatting()
    results['bandit_security'] = test_bandit_security()
    results['mypy_types'] = test_mypy_types()
    results['coverage'] = test_coverage()
    
    # Summary
    print("\n" + "="*60)
    print("📋 STATIC ANALYSIS SUMMARY")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for tool, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{tool.replace('_', ' ').title():<20} {status}")
    
    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 ALL STATIC ANALYSIS TOOLS CONFIGURED CORRECTLY!")
        return 0
    else:
        print("⚠️  Some tools need attention")
        return 1

if __name__ == "__main__":
    exit(main())
