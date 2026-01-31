import sys

import pypdf

# Set encoding to utf-8 for console output to avoid encoding errors
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore

pdf_path = r"d:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\MANNING_Practical_Guide_to_Apache_Airflow_3.pdf"


def search_pdf(path, keywords):
    print(f"Reading {path}...")
    try:
        reader = pypdf.PdfReader(path)
        print(f"Total pages: {len(reader.pages)}")

        found_content = []

        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    # Capture context
                    found_content.append(
                        f"\n--- MATCH: '{keyword}' on Page {i + 1} ---\n{text[:2000]}..."
                    )
                    # Limit to first few matches to avoid flooding
                    if len(found_content) > 5:
                        return found_content

        if not found_content:
            print("No matches found.")
        return found_content

    except Exception as e:
        print(f"Error reading PDF: {e}")
        return []


# Keywords related to Airflow 3 Architecture / AIP-44
keywords = [
    "Rate Limiting",
    "storage backend",
    "flask-limiter",
    "redis",
    "Auth Manager",
    "FabAuthManager",
    "SimpleAuthManager",
    "deprecated permissions",
    "security.permissions",
    "AIP-44 auth",
]
results = search_pdf(pdf_path, keywords)

for result in results:
    print(result)
