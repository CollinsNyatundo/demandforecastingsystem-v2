import requests
import time
import sys

SERVICES = {
    "Model Server": "http://localhost:8000/health",
    "Model Metrics": "http://localhost:8000/metrics",
    "Model Drift": "http://localhost:8000/metrics/drift",
    "MLflow": "http://localhost:5000/health",
    "Airflow": "http://localhost:8081/health",
    "MinIO": "http://localhost:9000/minio/health/live",
    "Dashboard": "http://localhost:8050"
}

def check_services():
    print("Verifying services...")
    all_healthy = True
    for name, url in SERVICES.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"[OK] {name}: OK ({url})")
            else:
                print(f"[ERROR] {name}: Status {response.status_code} ({url})")
                all_healthy = False
        except Exception as e:
            print(f"[ERROR] {name}: Error ({e})")
            all_healthy = False
    return all_healthy

if __name__ == "__main__":
    for i in range(12): # Try for 60 seconds
        if check_services():
            print("\n🎉 All services are healthy!")
            sys.exit(0)
        print("\nWaiting 5s for services to stabilize...")
        time.sleep(5)
    
    print("\n⚠️ Some services failed to start.")
    sys.exit(1)
