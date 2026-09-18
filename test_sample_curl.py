"""
Quick command-line utility to test a running GridWise service using a sample request.
Uses standard library urllib.request for zero-dependency execution.
"""
import sys
import json
import urllib.request
import urllib.error

def test_service(base_url="http://127.0.0.1:8000", sample_file="BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"):
    # 1. Health check
    health_url = f"{base_url.rstrip('/')}/health"
    print(f"Testing GET {health_url}...")
    try:
        req = urllib.request.Request(health_url, headers={"User-Agent": "GridWise-Test/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            status_code = response.getcode()
            body = json.loads(response.read().decode("utf-8"))
            print(f"  Health status: {status_code}, response: {body}")
            assert status_code == 200 and body.get("status") == "ok"
    except Exception as e:
        print(f"  Health check failed: {e}")
        return False

    # 2. Optimization check
    opt_url = f"{base_url.rstrip('/')}/optimize-energy"
    print(f"\nTesting POST {opt_url} with SAMPLE-01...")
    try:
        with open(sample_file, "r", encoding="utf-8") as f:
            sample_data = json.load(f)["cases"][0]["input"]

        req_data = json.dumps(sample_data).encode("utf-8")
        req = urllib.request.Request(
            opt_url,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "GridWise-Test/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=25) as response:
            status_code = response.getcode()
            res = json.loads(response.read().decode("utf-8"))
            print(f"  Optimization status: {status_code}")
            if status_code == 200:
                print(f"  Scenario: {res['scenario_id']}")
                print(f"  Total Cost: {res['total_cost_bdt']:,.2f} BDT")
                print(f"  Total Grid: {res['total_grid_kwh']:,.2f} kWh")
                print(f"  Peak Grid:  {res['peak_grid_kwh']:,.2f} kWh")
                print(f"  Directives: {len(res['directive_interpretation'])} processed")
                print(f"  Summary:    {res['plan_summary']}")
                return True
            else:
                print(f"  Unexpected status code: {status_code}")
                return False
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP Error {e.code}: {err_body}")
        return False
    except Exception as e:
        print(f"  Optimization call failed: {e}")
        return False

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    success = test_service(url)
    sys.exit(0 if success else 1)
