import os

baseDir = (
    r"D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"
)

# Fix explainability/nodes.py - read actual content and rewrite
explainPath = os.path.join(
    baseDir,
    "src/demand_forecasting/pipelines/explainability/nodes.py".replace("/", "\\"),
)

# Read the entire raw file
with open(explainPath, "rb") as f:
    raw_content = f.read()

# If it starts with ### or backticks, it's corrupted
if raw_content.startswith(b"###") or raw_content.startswith(b"```"):
    pass
else:
    # Decode and check first real line
    text_content = raw_content.decode("utf-8", errors="ignore")
    first_line = text_content.split("\n")[0]
