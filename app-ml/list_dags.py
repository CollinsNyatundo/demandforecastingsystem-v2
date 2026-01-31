#!/usr/bin/env python
import requests

auth = ('Cole', 'admin')
r = requests.get('http://localhost:8081/api/v1/dags', auth=auth, timeout=10)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    dags = r.json()
    dag_list = [d["dag_id"] for d in dags.get("dags", [])]
    print(f"Total DAGs: {len(dag_list)}")
    print(f"DAG IDs: {dag_list}")
else:
    print(f"Error: {r.text[:200]}")
