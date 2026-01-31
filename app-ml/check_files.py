
import os

baseDir = r"D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"

# Fix explainability/nodes.py - read actual content and rewrite
explainPath = os.path.join(baseDir, "src/demand_forecasting/pipelines/explainability/nodes.py".replace("/", "\\"))

# Read the entire raw file
with open(explainPath, "rb") as f:
    raw_content = f.read()

# If it starts with ### or backticks, it's corrupted
if raw_content.startswith(b"###") or raw_content.startswith(b"```"):
    print(f"[CORRUPTED] {explainPath}")
    print(f"First 100 bytes: {raw_content[:100]}")
else:
    print(f"[VALID] {explainPath}")
    # Decode and check first real line
    text_content = raw_content.decode('utf-8', errors='ignore')
    first_line = text_content.split('\n')[0]
    print(f"First line: {first_line[:80]}")
