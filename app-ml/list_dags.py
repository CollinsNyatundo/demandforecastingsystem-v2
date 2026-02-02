#!/usr/bin/env python
import requests

auth = ("Cole", "admin")
r = requests.get("http://localhost:8081/api/v1/dags", auth=auth, timeout=10)
if r.status_code == 200:
    dags = r.json()
    dag_list = [d["dag_id"] for d in dags.get("dags", [])]
else:
    pass
