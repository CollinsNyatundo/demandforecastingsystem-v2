"""
Simple Load Testing Script for Model Server
AUDIT-M2: Load testing implementation

Uses Python's concurrent.futures for simple load testing
(Free-tier alternative to Locust/k6)
"""

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

import requests


def make_prediction_request(
    url: str, payload: dict[str, Any], timeout: int = 30
) -> dict[str, Any]:
    """Make a single prediction request and return timing metrics."""
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        end_time = time.time()
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "response_time": end_time - start_time,
            "error": None,
        }
    except requests.exceptions.RequestException as e:
        end_time = time.time()
        return {
            "success": False,
            "status_code": None,
            "response_time": end_time - start_time,
            "error": str(e),
        }


def run_load_test(
    url: str,
    num_requests: int = 100,
    concurrency: int = 10,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run load test with specified concurrency.
    
    Args:
        url: Prediction endpoint URL
        num_requests: Total number of requests to make
        concurrency: Number of concurrent workers
        payload: Request payload (uses default if None)
    
    Returns:
        Dictionary with test results and statistics
    """
    if payload is None:
        # Default payload for bike sharing prediction
        payload = {
            "season": 1,
            "mnth": 1,
            "hr": 12,
            "holiday": 0,
            "weekday": 1,
            "workingday": 1,
            "weathersit": 1,
            "temp": 0.5,
            "atemp": 0.5,
            "hum": 0.5,
            "windspeed": 0.2,
        }
    
    print(f"\n{'='*60}")
    print(f"Load Test Configuration")
    print(f"{'='*60}")
    print(f"URL: {url}")
    print(f"Total Requests: {num_requests}")
    print(f"Concurrency: {concurrency}")
    print(f"{'='*60}\n")
    
    results: list[dict[str, Any]] = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(make_prediction_request, url, payload)
            for _ in range(num_requests)
        ]
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            results.append(future.result())
            if completed % 10 == 0:
                print(f"Progress: {completed}/{num_requests} requests completed")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Calculate statistics
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    response_times = [r["response_time"] for r in successful]
    
    stats = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "url": url,
            "num_requests": num_requests,
            "concurrency": concurrency,
        },
        "summary": {
            "total_requests": num_requests,
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "success_rate": len(successful) / num_requests * 100 if num_requests > 0 else 0,
            "total_time_seconds": total_time,
            "requests_per_second": num_requests / total_time if total_time > 0 else 0,
        },
        "response_times": {},
        "errors": [],
    }
    
    if response_times:
        stats["response_times"] = {
            "min_ms": min(response_times) * 1000,
            "max_ms": max(response_times) * 1000,
            "mean_ms": statistics.mean(response_times) * 1000,
            "median_ms": statistics.median(response_times) * 1000,
            "stdev_ms": statistics.stdev(response_times) * 1000 if len(response_times) > 1 else 0,
            "p95_ms": sorted(response_times)[int(len(response_times) * 0.95)] * 1000,
            "p99_ms": sorted(response_times)[int(len(response_times) * 0.99)] * 1000,
        }
    
    # Collect unique errors
    error_counts: dict[str, int] = {}
    for r in failed:
        error = r.get("error", "Unknown error")
        error_counts[error] = error_counts.get(error, 0) + 1
    stats["errors"] = [{"error": k, "count": v} for k, v in error_counts.items()]
    
    return stats


def print_results(stats: dict[str, Any]) -> None:
    """Print formatted test results."""
    print(f"\n{'='*60}")
    print("Load Test Results")
    print(f"{'='*60}")
    
    summary = stats["summary"]
    print(f"\n📊 Summary:")
    print(f"   Total Requests:     {summary['total_requests']}")
    print(f"   Successful:         {summary['successful_requests']}")
    print(f"   Failed:             {summary['failed_requests']}")
    print(f"   Success Rate:       {summary['success_rate']:.2f}%")
    print(f"   Total Time:         {summary['total_time_seconds']:.2f}s")
    print(f"   Requests/Second:    {summary['requests_per_second']:.2f}")
    
    if stats["response_times"]:
        rt = stats["response_times"]
        print(f"\n⏱️ Response Times:")
        print(f"   Min:                {rt['min_ms']:.2f}ms")
        print(f"   Max:                {rt['max_ms']:.2f}ms")
        print(f"   Mean:               {rt['mean_ms']:.2f}ms")
        print(f"   Median:             {rt['median_ms']:.2f}ms")
        print(f"   Std Dev:            {rt['stdev_ms']:.2f}ms")
        print(f"   P95:                {rt['p95_ms']:.2f}ms")
        print(f"   P99:                {rt['p99_ms']:.2f}ms")
    
    if stats["errors"]:
        print(f"\n❌ Errors:")
        for error in stats["errors"]:
            print(f"   {error['error']}: {error['count']} occurrences")
    
    # Performance assessment
    print(f"\n{'='*60}")
    if summary["success_rate"] >= 99:
        print("✅ PASSED: Success rate >= 99%")
    elif summary["success_rate"] >= 95:
        print("⚠️ WARNING: Success rate 95-99%")
    else:
        print("❌ FAILED: Success rate < 95%")
    
    if stats["response_times"]:
        if rt["p95_ms"] < 1000:
            print("✅ PASSED: P95 latency < 1 second")
        elif rt["p95_ms"] < 5000:
            print("⚠️ WARNING: P95 latency 1-5 seconds")
        else:
            print("❌ FAILED: P95 latency > 5 seconds")
    
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Load testing for model server")
    parser.add_argument(
        "--url",
        default="http://localhost:8000/predict",
        help="Prediction endpoint URL",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Number of requests to make",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent requests",
    )
    parser.add_argument(
        "--output",
        help="Output file for JSON results",
    )
    
    args = parser.parse_args()
    
    stats = run_load_test(
        url=args.url,
        num_requests=args.requests,
        concurrency=args.concurrency,
    )
    
    print_results(stats)
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(stats, f, indent=2)
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
