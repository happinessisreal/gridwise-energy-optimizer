"""
Integration tests for FastAPI endpoints: GET /health and POST /optimize-energy.
"""
import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app

client = TestClient(app)

def test_health_endpoint():
    """Verify GET /health returns HTTP 200 with status 'ok'."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    print("[PASS] GET /health returns status: ok")

def test_optimize_energy_valid_request():
    """Verify POST /optimize-energy returns valid schema and correct calculations."""
    sample_file = Path(__file__).parent.parent / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
    with open(sample_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    sample_01 = data["cases"][0]["input"]
    response = client.post("/optimize-energy", json=sample_01)
    
    assert response.status_code == 200
    res_json = response.json()

    # Check top-level fields
    assert res_json["scenario_id"] == "SAMPLE-01"
    assert "directive_interpretation" in res_json
    assert "hourly_plan" in res_json
    assert "total_grid_kwh" in res_json
    assert "total_cost_bdt" in res_json
    assert "peak_grid_kwh" in res_json
    assert "plan_summary" in res_json

    # Check directive interpretation
    interp = res_json["directive_interpretation"]
    assert len(interp) == 2
    assert interp[0]["directive_type"] == "solar_reduction"
    assert interp[0]["applies"] is True
    assert interp[0]["structured_adjustment"]["hours"] == [12, 13]
    assert interp[0]["structured_adjustment"]["factor"] == 0.25
    assert interp[1]["directive_type"] == "no_op"
    assert interp[1]["applies"] is False
    assert interp[1]["structured_adjustment"] is None

    # Check hourly plan length
    assert len(res_json["hourly_plan"]) == 24
    
    # Check cost matches reference
    assert abs(res_json["total_cost_bdt"] - 38365.0) < 0.05
    print(f"[PASS] POST /optimize-energy valid scenario processed successfully! Cost: {res_json['total_cost_bdt']}")

def test_optimize_energy_malformed_request():
    """Verify POST /optimize-energy handles malformed/missing fields with controlled HTTP 400."""
    # Missing battery and hours
    bad_payload = {
        "scenario_id": "BAD-01",
        "operator_notes": ["Do something."]
    }
    response = client.post("/optimize-energy", json=bad_payload)
    assert response.status_code == 400
    assert "detail" in response.json()
    print("[PASS] Malformed request correctly rejected with HTTP 400")

def test_optimize_energy_invalid_hours_count():
    """Verify that submitting fewer than 24 hours returns HTTP 400."""
    sample_file = Path(__file__).parent.parent / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
    with open(sample_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    bad_sample = dict(data["cases"][0]["input"])
    bad_sample["hours"] = bad_sample["hours"][:12] # Only 12 hours
    response = client.post("/optimize-energy", json=bad_sample)
    assert response.status_code == 400
    print("[PASS] Request with invalid hours count rejected with HTTP 400")

if __name__ == "__main__":
    test_health_endpoint()
    test_optimize_energy_valid_request()
    test_optimize_energy_malformed_request()
    test_optimize_energy_invalid_hours_count()
    print("\nALL API INTEGRATION TESTS PASSED SUCCESSFULLY!")
