
import os
import ast
import re
from pathlib import Path
from collections import defaultdict

base_path = r"D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"
issues_found = []
scan_stats = {
    "total_files": 0,
    "python_files": 0,
    "yaml_files": 0,
    "config_files": 0,
    "test_files": 0
}

# ==================== SCAN 1: Python Syntax & Import Issues ====================
print("="*80)
print("SCAN 1: Python Syntax and Import Issues")
print("="*80)

for root, dirs, files in os.walk(base_path):
    # Skip hidden directories and common non-source directories
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
    
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, base_path)
            scan_stats["python_files"] += 1
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Check for syntax errors
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    issues_found.append({
                        'severity': 'CRITICAL',
                        'type': 'Syntax Error',
                        'file': rel_path,
                        'line': e.lineno,
                        'message': str(e.msg),
                        'details': f"Line {e.lineno}: {e.msg}"
                    })
                    print(f"[SYNTAX ERROR] {rel_path}:{e.lineno} - {e.msg}")
                
                # Check for common issues
                lines = content.split('\n')
                
                # Check for unused imports
                try:
                    tree = ast.parse(content)
                    imported_names = set()
                    used_names = set()
                    
                    class ImportVisitor(ast.NodeVisitor):
                        def visit_Import(self, node):
                            for alias in node.names:
                                imported_names.add(alias.asname or alias.name)
                            self.generic_visit(node)
                        
                        def visit_ImportFrom(self, node):
                            for alias in node.names:
                                imported_names.add(alias.asname or alias.name)
                            self.generic_visit(node)
                        
                        def visit_Name(self, node):
                            used_names.add(node.id)
                            self.generic_visit(node)
                    
                    ImportVisitor().visit(tree)
                    unused = imported_names - used_names
                    
                    if unused:
                        print(f"[WARN] {rel_path} - Unused imports: {unused}")
                        issues_found.append({
                            'severity': 'LOW',
                            'type': 'Unused Imports',
                            'file': rel_path,
                            'message': f"Unused imports: {', '.join(sorted(unused))}",
                            'details': f"These imports are not used in the file: {', '.join(sorted(unused))}"
                        })
                except:
                    pass
                
                # Check for missing type hints in function definitions
                if 'def ' in content and 'from typing import' not in content and 'import typing' not in content:
                    func_pattern = r'def\s+\w+\([^)]*\)\s*->'
                    if not re.search(func_pattern, content):
                        print(f"[WARN] {rel_path} - Missing return type hints on functions")
                        issues_found.append({
                            'severity': 'MEDIUM',
                            'type': 'Missing Return Type Hints',
                            'file': rel_path,
                            'message': 'Functions defined without return type hints',
                            'details': 'Add -> ReturnType to function definitions'
                        })
                
            except Exception as e:
                print(f"[ERROR] Failed to scan {rel_path}: {e}")

# ==================== SCAN 2: Configuration Files ====================
print("\n" + "="*80)
print("SCAN 2: Configuration Files (YAML, JSON)")
print("="*80)

for root, dirs, files in os.walk(base_path):
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__']]
    
    for file in files:
        if file.endswith(('.yml', '.yaml', '.json')):
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, base_path)
            scan_stats["config_files"] += 1
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Check for YAML-specific issues
                if file.endswith(('.yml', '.yaml')):
                    # Check for tab characters (YAML doesn't allow tabs)
                    if '\t' in content:
                        print(f"[YAML ERROR] {rel_path} - Contains tab characters (not allowed in YAML)")
                        issues_found.append({
                            'severity': 'HIGH',
                            'type': 'YAML Tab Characters',
                            'file': rel_path,
                            'message': 'YAML file contains tab characters instead of spaces',
                            'details': 'Replace all tabs with spaces (2 or 4 spaces per indent level)'
                        })
                    
                    # Check for inconsistent indentation
                    lines = content.split('\n')
                    indent_chars = set()
                    for line in lines:
                        if line and line[0] in ' \t':
                            indent_chars.add(line[0])
                    if len(indent_chars) > 1:
                        print(f"[YAML WARN] {rel_path} - Inconsistent indentation (spaces and tabs mixed)")
                        issues_found.append({
                            'severity': 'MEDIUM',
                            'type': 'YAML Indentation',
                            'file': rel_path,
                            'message': 'Mixed spaces and tabs in indentation',
                            'details': 'Use consistent indentation (spaces only recommended)'
                        })
                
                # Check for JSON syntax
                if file.endswith('.json'):
                    try:
                        import json
                        json.loads(content)
                    except json.JSONDecodeError as e:
                        print(f"[JSON ERROR] {rel_path}:{e.lineno} - {e.msg}")
                        issues_found.append({
                            'severity': 'HIGH',
                            'type': 'JSON Syntax Error',
                            'file': rel_path,
                            'line': e.lineno,
                            'message': e.msg,
                            'details': f"Line {e.lineno}: {e.msg}"
                        })
                
            except Exception as e:
                print(f"[ERROR] Failed to parse {rel_path}: {e}")

# ==================== SCAN 3: Pipeline Logic Issues ====================
print("\n" + "="*80)
print("SCAN 3: Pipeline Logic and Dependencies")
print("="*80)

# Check pipeline.py files for complete node definitions
pipeline_files = []
for root, dirs, files in os.walk(base_path):
    for file in files:
        if file == 'pipeline.py':
            pipeline_files.append(os.path.join(root, file))

for pipeline_file in pipeline_files:
    rel_path = os.path.relpath(pipeline_file, base_path)
    try:
        with open(pipeline_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Check if nodes are properly connected
        if 'node(' in content:
            node_count = content.count('node(')
            inputs_count = content.count('inputs=')
            outputs_count = content.count('outputs=')
            
            if node_count != inputs_count or node_count != outputs_count:
                print(f"[PIPELINE ERROR] {rel_path} - Node definitions incomplete")
                issues_found.append({
                    'severity': 'HIGH',
                    'type': 'Incomplete Node Definition',
                    'file': rel_path,
                    'message': f'Found {node_count} nodes, {inputs_count} inputs, {outputs_count} outputs - mismatch',
                    'details': 'Each node must have inputs and outputs defined'
                })
        
        # Check for orphaned outputs
        if 'outputs=' in content:
            output_pattern = r'outputs=["']([^"']+)["']'
            outputs = re.findall(output_pattern, content)
            print(f"[INFO] {rel_path} - Found outputs: {outputs}")
        
    except Exception as e:
        print(f"[ERROR] Failed to analyze {pipeline_file}: {e}")

# ==================== SCAN 4: Node Functions Analysis ====================
print("\n" + "="*80)
print("SCAN 4: Node Functions - Signatures and Parameters")
print("="*80)

nodes_files = []
for root, dirs, files in os.walk(base_path):
    if 'nodes.py' in files or 'nodes' in root:
        for file in files:
            if 'node' in file and file.endswith('.py'):
                nodes_files.append(os.path.join(root, file))

for node_file in nodes_files:
    rel_path = os.path.relpath(node_file, base_path)
    try:
        with open(node_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Parse to find all functions
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if function has docstring
                    if not ast.get_docstring(node):
                        print(f"[WARN] {rel_path}:def {node.name} - Missing docstring")
                        issues_found.append({
                            'severity': 'LOW',
                            'type': 'Missing Docstring',
                            'file': rel_path,
                            'line': node.lineno,
                            'message': f'Function {node.name} missing docstring',
                            'details': f'Add docstring to function {node.name} at line {node.lineno}'
                        })
                    
                    # Check function parameters
                    args = node.args
                    for arg in args.args:
                        if not arg.annotation:
                            print(f"[WARN] {rel_path}:def {node.name} - Parameter {arg.arg} missing type hint")
                            issues_found.append({
                                'severity': 'MEDIUM',
                                'type': 'Missing Parameter Type Hint',
                                'file': rel_path,
                                'line': node.lineno,
                                'message': f'Parameter {arg.arg} in {node.name} missing type hint',
                                'details': f'Add type annotation to parameter {arg.arg}'
                            })
        except:
            pass
        
    except Exception as e:
        print(f"[ERROR] Failed to analyze {node_file}: {e}")

# ==================== SCAN 5: Data Flow and Connections ====================
print("\n" + "="*80)
print("SCAN 5: Data Flow - Catalog and Pipeline Connections")
print("="*80)

catalog_file = os.path.join(base_path, 'conf', 'base', 'catalog.yml')
if os.path.exists(catalog_file):
    try:
        with open(catalog_file, 'r', encoding='utf-8', errors='ignore') as f:
            catalog_content = f.read()
        
        # Extract dataset names from catalog
        catalog_entries = re.findall(r'^([a-zA-Z_][a-zA-Z0-9_]*):', catalog_content, re.MULTILINE)
        print(f"[INFO] Catalog has {len(catalog_entries)} dataset entries: {catalog_entries}")
        
        # Check each pipeline for referenced datasets
        for pipeline_file in pipeline_files:
            rel_path = os.path.relpath(pipeline_file, base_path)
            with open(pipeline_file, 'r', encoding='utf-8', errors='ignore') as f:
                pipeline_content = f.read()
            
            # Find referenced datasets
            inputs_pattern = r'inputs=\[([^\]]+)\]'
            outputs_pattern = r'outputs=\[?([^\]]+)\]?'
            
            referenced = set()
            for match in re.finditer(inputs_pattern, pipeline_content):
                items = re.findall(r'["']([^"']+)["']', match.group(1))
                referenced.update(items)
            
            for match in re.finditer(outputs_pattern, pipeline_content):
                items = re.findall(r'["']([^"']+)["']', match.group(1))
                referenced.update(items)
            
            # Check if all referenced datasets are in catalog
            undefined = referenced - set(catalog_entries)
            if undefined:
                print(f"[PIPELINE ERROR] {rel_path} - References undefined datasets: {undefined}")
                issues_found.append({
                    'severity': 'HIGH',
                    'type': 'Undefined Dataset References',
                    'file': rel_path,
                    'message': f'References datasets not in catalog: {undefined}',
                    'details': f'These datasets are referenced but not defined in catalog: {", ".join(sorted(undefined))}'
                })
    except Exception as e:
        print(f"[ERROR] Failed to analyze catalog: {e}")

# ==================== SCAN 6: Error Handling and Validation ====================
print("\n" + "="*80)
print("SCAN 6: Error Handling and Input Validation")
print("="*80)

for root, dirs, files in os.walk(base_path):
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__']]
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, base_path)
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Check for bare except clauses
                if 'except:' in content:
                    print(f"[WARN] {rel_path} - Contains bare except clause")
                    issues_found.append({
                        'severity': 'MEDIUM',
                        'type': 'Bare Exception Handler',
                        'file': rel_path,
                        'message': 'Found bare except: clause (catches all exceptions)',
                        'details': 'Specify exception type: except ExceptionType as e:'
                    })
                
                # Check for missing input validation
                if 'def ' in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if 'def ' in line and '-> ' not in line:
                            # Check if function validates inputs
                            func_body = '\n'.join(lines[i:min(i+10, len(lines))])
                            if 'if ' not in func_body and 'assert ' not in func_body:
                                # Don't flag every function, just complex ones
                                if any(param in line for param in ['DataFrame', 'Series', 'dict', 'list']):
                                    pass  # Could check for validation, but many are valid
            except:
                pass

# ==================== SCAN 7: Performance Issues ====================
print("\n" + "="*80)
print("SCAN 7: Performance Issues and Code Quality")
print("="*80)

for root, dirs, files in os.walk(base_path):
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__']]
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, base_path)
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Check for inefficient patterns
                if '.copy()' in content and 'df = df.copy()' in content:
                    count = content.count('df = df.copy()')
                    if count > 3:
                        print(f"[PERF WARN] {rel_path} - Multiple df.copy() calls ({count})")
                        issues_found.append({
                            'severity': 'LOW',
                            'type': 'Potential Performance Issue',
                            'file': rel_path,
                            'message': f'Multiple .copy() calls on DataFrames ({count} times)',
                            'details': 'Consider consolidating DataFrame copy operations'
                        })
                
                # Check for hardcoded values that should be constants
                numbers = re.findall(r'\b\d{2,}\b', content)
                if len(numbers) > 10:
                    print(f"[CODE STYLE] {rel_path} - Contains many hardcoded numbers")
                    issues_found.append({
                        'severity': 'LOW',
                        'type': 'Hardcoded Magic Numbers',
                        'file': rel_path,
                        'message': f'File contains many hardcoded numbers ({len(numbers)})',
                        'details': 'Consider defining constants for magic numbers'
                    })
            except:
                pass

# ==================== FINAL REPORT ====================
print("\n" + "="*80)
print("SCAN SUMMARY")
print("="*80)
print(f"Total Python files scanned: {scan_stats['python_files']}")
print(f"Total configuration files scanned: {scan_stats['config_files']}")
print(f"Total issues found: {len(issues_found)}")

print("\n" + "="*80)
print("ISSUES BY SEVERITY")
print("="*80)

by_severity = defaultdict(list)
for issue in issues_found:
    by_severity[issue['severity']].append(issue)

for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
    if by_severity[severity]:
        print(f"\n{severity}: {len(by_severity[severity])} issues")
        for issue in by_severity[severity]:
            print(f"  - {issue['file']}: {issue['type']} - {issue['message']}")

# Save detailed report
import json
with open(r"D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml\DETAILED_SCAN_RESULTS.json", 'w') as f:
    json.dump(issues_found, f, indent=2, default=str)

print(f"\nDetailed results saved to: DETAILED_SCAN_RESULTS.json")
