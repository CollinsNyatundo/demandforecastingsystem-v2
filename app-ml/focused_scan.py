import os
import ast
import re
import json
from pathlib import Path
from collections import defaultdict

base_path = r"D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"
issues_found = []

print("="*80)
print("COMPREHENSIVE CODE AND LOGIC ISSUE SCAN")
print("="*80)

# ==================== SCAN 1: Critical Python Syntax Issues ====================
print("\nSCAN 1: Python Syntax Issues")
print("-"*80)

python_files = []
for root, dirs, files in os.walk(base_path):
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'tests']]
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            python_files.append(filepath)
            rel_path = os.path.relpath(filepath, base_path)
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    issues_found.append({
                        'severity': 'CRITICAL',
                        'type': 'Syntax Error',
                        'file': rel_path,
                        'line': e.lineno,
                        'message': str(e.msg),
                        'category': 'Code Quality'
                    })
                    print(f"  [CRITICAL] {rel_path}:{e.lineno} - {e.msg}")
            except Exception as e:
                print(f"  [ERROR] Failed to parse {rel_path}: {str(e)[:100]}")

print(f"Scanned {len(python_files)} Python files")

# ==================== SCAN 2: Missing Type Hints ====================
print("\nSCAN 2: Type Hints Analysis")
print("-"*80)

type_hint_issues = 0
for filepath in python_files:
    rel_path = os.path.relpath(filepath, base_path)
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if 'def ' in content:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check return type hint
                    if node.returns is None and node.name != '__init__':
                        issues_found.append({
                            'severity': 'MEDIUM',
                            'type': 'Missing Return Type Hint',
                            'file': rel_path,
                            'line': node.lineno,
                            'message': f'Function {node.name} missing return type',
                            'category': 'Type Hints'
                        })
                        type_hint_issues += 1
                    
                    # Check parameter type hints
                    for arg in node.args.args:
                        if arg.annotation is None and arg.arg != 'self' and arg.arg != 'cls':
                            issues_found.append({
                                'severity': 'MEDIUM',
                                'type': 'Missing Parameter Type Hint',
                                'file': rel_path,
                                'line': node.lineno,
                                'message': f'Parameter {arg.arg} in {node.name} missing type',
                                'category': 'Type Hints'
                            })
                            type_hint_issues += 1
    except:
        pass

print(f"Found {type_hint_issues} missing type hints")

# ==================== SCAN 3: Logic Issues ====================
print("\nSCAN 3: Logic and Runtime Issues")
print("-"*80)

logic_issues = 0
for filepath in python_files:
    rel_path = os.path.relpath(filepath, base_path)
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Check for bare except clauses
        for i, line in enumerate(lines, 1):
            if 'except:' in line and 'except Exception' not in line:
                issues_found.append({
                    'severity': 'HIGH',
                    'type': 'Bare Except Clause',
                    'file': rel_path,
                    'line': i,
                    'message': 'Bare except clause catches all exceptions including SystemExit',
                    'category': 'Error Handling'
                })
                logic_issues += 1
                print(f"  [HIGH] {rel_path}:{i} - Bare except clause")
        
        # Check for potential None type errors
        if 'is None' in content or '== None' in content:
            for i, line in enumerate(lines, 1):
                if '.split(' in line or '.strip(' in line or '.replace(' in line:
                    if not any(check in lines[max(0, i-3):i] for check in ['is not None', 'if ', 'assert ']):
                        pass  # This is often OK
        
        # Check for missing return statements in conditional functions
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.returns and node.returns.id not in ['None'] if hasattr(node.returns, 'id') else True:
                    has_return = any(isinstance(n, ast.Return) and n.value for n in ast.walk(node))
                    if not has_return:
                        issues_found.append({
                            'severity': 'HIGH',
                            'type': 'Missing Return Statement',
                            'file': rel_path,
                            'line': node.lineno,
                            'message': f'Function {node.name} has return type but no return statement',
                            'category': 'Logic Error'
                        })
                        logic_issues += 1
    except:
        pass

print(f"Found {logic_issues} potential logic issues")

# ==================== SCAN 4: Data Pipeline Issues ====================
print("\nSCAN 4: Pipeline and Catalog Issues")
print("-"*80)

# Check catalog
catalog_path = os.path.join(base_path, 'conf', 'base', 'catalog.yml')
catalog_entries = set()
catalog_issues = 0

if os.path.exists(catalog_path):
    with open(catalog_path, 'r', encoding='utf-8', errors='ignore') as f:
        catalog_content = f.read()
    
    # Extract dataset names
    for match in re.finditer(r'^([a-zA-Z_][a-zA-Z0-9_]*):', catalog_content, re.MULTILINE):
        catalog_entries.add(match.group(1))
    
    print(f"  Catalog entries found: {len(catalog_entries)}")
    
    # Check for duplicate entries
    lines = catalog_content.split('\n')
    seen = set()
    for i, line in enumerate(lines, 1):
        match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*):', line)
        if match:
            entry = match.group(1)
            if entry in seen:
                issues_found.append({
                    'severity': 'HIGH',
                    'type': 'Duplicate Catalog Entry',
                    'file': 'conf/base/catalog.yml',
                    'line': i,
                    'message': f'Duplicate entry: {entry}',
                    'category': 'Configuration'
                })
                catalog_issues += 1
                print(f"  [HIGH] Duplicate catalog entry: {entry}")
            seen.add(entry)
    
    # Check for missing credentials
    if 'credentials:' in catalog_content:
        for match in re.finditer(r'credentials:\s*([a-zA-Z_][a-zA-Z0-9_]*)', catalog_content):
            cred = match.group(1)
            # Would need to check credentials.yml - skip for now
    
else:
    print("  WARNING: catalog.yml not found")

# Check pipeline files
pipeline_files = []
for root, dirs, files in os.walk(base_path):
    if 'pipeline.py' in files:
        pipeline_files.append(os.path.join(root, 'pipeline.py'))

print(f"\n  Found {len(pipeline_files)} pipeline files")

for pipeline_path in pipeline_files:
    rel_path = os.path.relpath(pipeline_path, base_path)
    try:
        with open(pipeline_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Check for unconnected nodes
        if 'node(' in content:
            # Count nodes, inputs, outputs
            nodes = content.count('node(')
            inputs = content.count('inputs=')
            outputs = content.count('outputs=')
            
            if nodes != inputs or nodes != outputs:
                issues_found.append({
                    'severity': 'HIGH',
                    'type': 'Incomplete Node Definition',
                    'file': rel_path,
                    'message': f'{nodes} nodes, {inputs} inputs, {outputs} outputs - check definitions',
                    'category': 'Pipeline Logic'
                })
                print(f"  [HIGH] {rel_path} - Node/input/output count mismatch")
        
        # Check for undefined references
        referenced = set(re.findall(r'["']([a-zA-Z_][a-zA-Z0-9_]*)["']', content))
        undefined = referenced - catalog_entries - {'default', 'memory', 'parameters'}
        
        # Filter out common false positives
        undefined = {x for x in undefined if not x.startswith('_') and x.islower()}
        
        if undefined:
            print(f"  [WARN] {rel_path} - Possible undefined references: {undefined}")
    except:
        pass

# ==================== SCAN 5: Missing Documentation ====================
print("\nSCAN 5: Documentation Issues")
print("-"*80)

doc_issues = 0
for filepath in python_files:
    rel_path = os.path.relpath(filepath, base_path)
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        # Check module docstring
        if not ast.get_docstring(tree):
            if 'pipeline' in rel_path.lower() or 'node' in rel_path.lower():
                issues_found.append({
                    'severity': 'LOW',
                    'type': 'Missing Module Docstring',
                    'file': rel_path,
                    'message': 'Module missing docstring',
                    'category': 'Documentation'
                })
                doc_issues += 1
        
        # Check function docstrings in important files
        if 'pipeline' in rel_path.lower() or 'node' in rel_path.lower():
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not ast.get_docstring(node) and not node.name.startswith('_'):
                        issues_found.append({
                            'severity': 'LOW',
                            'type': 'Missing Function Docstring',
                            'file': rel_path,
                            'line': node.lineno,
                            'message': f'Function {node.name} missing docstring',
                            'category': 'Documentation'
                        })
                        doc_issues += 1
    except:
        pass

print(f"Found {doc_issues} missing docstrings")

# ==================== SUMMARY ====================
print("\n" + "="*80)
print("SCAN COMPLETE - DETAILED RESULTS")
print("="*80)

# Group by severity
by_severity = defaultdict(list)
by_category = defaultdict(list)

for issue in issues_found:
    by_severity[issue['severity']].append(issue)
    by_category[issue['category']].append(issue)

print(f"\nTotal issues found: {len(issues_found)}")
print(f"\nBy Severity:")
for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
    count = len(by_severity[severity])
    if count > 0:
        print(f"  {severity}: {count} issues")

print(f"\nBy Category:")
for category in sorted(by_category.keys()):
    count = len(by_category[category])
    print(f"  {category}: {count} issues")

# Save detailed results
with open(os.path.join(base_path, 'DETAILED_SCAN_RESULTS.json'), 'w') as f:
    json.dump(issues_found, f, indent=2, default=str)

print(f"\nDetailed results saved to DETAILED_SCAN_RESULTS.json")
