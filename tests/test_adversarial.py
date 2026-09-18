"""
Comprehensive Adversarial & Boundary Test Suite for GridWise Energy Optimization Service.
Pytest-compatible test harness covering:
1. Malformed JSON, non-JSON, missing keys, invalid types -> HTTP 400
2. Battery specification physical bounds -> HTTP 400
3. 24-hour sequence integrity (length, range, ordering, uniqueness) -> HTTP 400
4. Directive invariant (applies == False <=> directive_type == 'no_op')
5. Complex edge time expressions (cross-noon, midnight, 24h, 12h)
6. Factor inversion ("reduced by X%" vs "reduced to X%")
7. Substring collision ("discharge" vs "charge")
8. Controlled HTTP 500 error sanitization (no stack trace, no secret leakage)
9. Guardrail numeric sanitization (NaN, Inf, unit suffixes)
10. Security injection, extreme inputs, and offline fallback mode
"""

import sys
import json
import asyncio
import math
import copy
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app
from app.schemas import (
    BatterySpec,
    HourEntry,
    OptimizeEnergyRequest,
    DirectiveInterpretation,
)
from app.guardrails import (
    sanitize_hours,
    _clean_finite_float,
    validate_and_guardrail_interpretation,
)
from app.llm_interpreter import parse_time_window, fallback_extract_note, interpret_operator_notes


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def base_valid_payload() -> Dict[str, Any]:
    sample_file = PROJECT_ROOT / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
    if sample_file.exists():
        with open(sample_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return copy.deepcopy(data["cases"][0]["input"])
    
    # Fallback minimal valid payload if json not found
    return {
        "scenario_id": "BASE-SCENARIO-01",
        "operator_notes": ["Solar panels cleaned from noon until 2 PM, usable solar reduced by 75%."],
        "hours": [
            {"hour": h, "demand_kwh": 100.0, "solar_kwh": 20.0 if 8 <= h <= 17 else 0.0, "tariff_bdt_per_kwh": 10.0}
            for h in range(24)
        ],
        "battery": {
            "capacity_kwh": 200.0,
            "initial_energy_kwh": 80.0,
            "minimum_energy_kwh": 40.0,
            "max_charge_kwh_per_hour": 50.0,
            "max_discharge_kwh_per_hour": 50.0,
        },
    }


# =============================================================================
# 1. Malformed JSON / Missing Keys / Invalid Types -> HTTP 400
# =============================================================================

class TestMalformedJsonAndTypes:
    """Validate that invalid payloads fail fast with HTTP 400 Bad Request."""

    def test_raw_non_json_string(self, client: TestClient):
        r = client.post(
            "/optimize-energy",
            content=b"this is definitely not a json string",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 400
        assert "detail" in r.json()

    def test_truncated_json(self, client: TestClient):
        r = client.post(
            "/optimize-energy",
            content=b'{"scenario_id": "TEST", "hours": [',
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 400
        assert "detail" in r.json()

    def test_empty_http_body(self, client: TestClient):
        r = client.post(
            "/optimize-energy",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 400
        assert "detail" in r.json()

    def test_root_json_array_instead_of_object(self, client: TestClient):
        r = client.post(
            "/optimize-energy",
            content=b"[1, 2, 3]",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 400

    @pytest.mark.parametrize("missing_field", ["scenario_id", "operator_notes", "hours", "battery"])
    def test_missing_top_level_fields(self, client: TestClient, base_valid_payload: Dict[str, Any], missing_field: str):
        payload = copy.deepcopy(base_valid_payload)
        del payload[missing_field]
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_empty_operator_notes_list(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["operator_notes"] = []
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_too_many_operator_notes(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["operator_notes"] = ["Note 1", "Note 2", "Note 3", "Note 4"]
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_empty_string_in_operator_notes(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["operator_notes"] = [""]
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_whitespace_only_operator_note(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["operator_notes"] = ["     "]
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_invalid_data_types(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["scenario_id"] = {"nested": "dict"}
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_string_in_hourly_numeric_field(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["hours"][0]["demand_kwh"] = "not-a-number"
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_negative_demand_rejected(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["hours"][0]["demand_kwh"] = -25.0
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_negative_solar_rejected(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["hours"][0]["solar_kwh"] = -10.0
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_negative_tariff_rejected(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["hours"][0]["tariff_bdt_per_kwh"] = -5.0
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400


# =============================================================================
# 2. Battery Spec Bounds -> HTTP 400
# =============================================================================

class TestBatterySpecBounds:
    """Validate microgrid physical laws and bounds on battery parameters."""

    def test_initial_energy_exceeds_capacity(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["battery"]["capacity_kwh"] = 200.0
        payload["battery"]["initial_energy_kwh"] = 250.0  # E0 > capacity
        payload["battery"]["minimum_energy_kwh"] = 40.0
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_minimum_energy_exceeds_capacity(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["battery"]["capacity_kwh"] = 200.0
        payload["battery"]["initial_energy_kwh"] = 150.0
        payload["battery"]["minimum_energy_kwh"] = 250.0  # R > capacity
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_initial_energy_below_minimum_energy(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["battery"]["capacity_kwh"] = 200.0
        payload["battery"]["initial_energy_kwh"] = 20.0  # E0 < R
        payload["battery"]["minimum_energy_kwh"] = 40.0
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_negative_capacity(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["battery"]["capacity_kwh"] = -100.0
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_zero_capacity(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["battery"]["capacity_kwh"] = 0.0
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_negative_max_charge_rate(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["battery"]["max_charge_kwh_per_hour"] = -10.0
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_negative_max_discharge_rate(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["battery"]["max_discharge_kwh_per_hour"] = -10.0
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_direct_pydantic_battery_spec_validation(self):
        with pytest.raises(ValueError):
            BatterySpec(
                capacity_kwh=100.0,
                initial_energy_kwh=120.0,
                minimum_energy_kwh=20.0,
                max_charge_kwh_per_hour=25.0,
                max_discharge_kwh_per_hour=25.0,
            )

        with pytest.raises(ValueError):
            BatterySpec(
                capacity_kwh=100.0,
                initial_energy_kwh=50.0,
                minimum_energy_kwh=150.0,
                max_charge_kwh_per_hour=25.0,
                max_discharge_kwh_per_hour=25.0,
            )

        with pytest.raises(ValueError):
            BatterySpec(
                capacity_kwh=100.0,
                initial_energy_kwh=10.0,
                minimum_energy_kwh=30.0,
                max_charge_kwh_per_hour=25.0,
                max_discharge_kwh_per_hour=25.0,
            )


# =============================================================================
# 3. 24-Hour Sequence Integrity -> HTTP 400
# =============================================================================

class TestHourlySequenceIntegrity:
    """Validate 24-hour sequence length, indices, ordering, and uniqueness."""

    def test_wrong_length_too_few_hours(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["hours"] = payload["hours"][:12]  # Only 12 hours
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_wrong_length_too_many_hours(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        extra = copy.deepcopy(payload["hours"][0])
        extra["hour"] = 24
        payload["hours"].append(extra)  # 25 hours
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_negative_hour_index(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["hours"][0]["hour"] = -1
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_out_of_range_hour_index(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["hours"][23]["hour"] = 24
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_duplicate_hours(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["hours"][5]["hour"] = 4  # Duplicate hour 4
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_out_of_order_hours(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        # Swap hour 0 and hour 1
        payload["hours"][0], payload["hours"][1] = payload["hours"][1], payload["hours"][0]
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400

    def test_non_consecutive_hours_skipping_one(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        # Skip hour 10 and replace with hour 24
        for entry in payload["hours"]:
            if entry["hour"] == 10:
                entry["hour"] = 24
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 400


# =============================================================================
# 4. Directive Invariant (applies == False <=> directive_type == 'no_op')
# =============================================================================

class TestDirectiveInvariant:
    """Verify that applies == False if and only if directive_type == 'no_op'."""

    def test_schema_rejects_applies_true_for_no_op(self):
        with pytest.raises(ValueError, match="applies must be False when directive_type is 'no_op'"):
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type="no_op",
                structured_adjustment=None,
                explanation="Invalid no_op with applies=True",
            )

    def test_schema_rejects_structured_adjustment_for_no_op(self):
        with pytest.raises(ValueError, match="structured_adjustment must be null/None when directive_type is 'no_op'"):
            DirectiveInterpretation(
                note_index=0,
                applies=False,
                directive_type="no_op",
                structured_adjustment={"hours": [12, 13]},
                explanation="Invalid no_op with adjustment",
            )

    @pytest.mark.parametrize("dtype", [
        "solar_reduction",
        "minimum_battery_reserve",
        "no_charge_window",
        "no_discharge_window",
        "max_grid_window",
    ])
    def test_schema_rejects_applies_false_for_active_directives(self, dtype: str):
        with pytest.raises(ValueError, match="applies must be True"):
            DirectiveInterpretation(
                note_index=0,
                applies=False,
                directive_type=dtype,
                structured_adjustment={"hours": [1, 2]},
                explanation="Invalid active directive with applies=False",
            )

    @pytest.mark.parametrize("dtype", [
        "solar_reduction",
        "minimum_battery_reserve",
        "no_charge_window",
        "no_discharge_window",
        "max_grid_window",
    ])
    def test_schema_rejects_none_adjustment_for_active_directives(self, dtype: str):
        with pytest.raises(ValueError, match="structured_adjustment cannot be None"):
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type=dtype,
                structured_adjustment=None,
                explanation="Invalid active directive with null adjustment",
            )

    def test_guardrails_enforces_invariant_on_adversarial_inputs(self):
        battery = BatterySpec(
            capacity_kwh=200.0,
            initial_energy_kwh=80.0,
            minimum_energy_kwh=40.0,
            max_charge_kwh_per_hour=50.0,
            max_discharge_kwh_per_hour=50.0,
        )

        adversarial_entries = [
            # Missing adjustment dict
            {"note_index": 0, "directive_type": "solar_reduction", "applies": True, "structured_adjustment": None},
            # Empty hours list
            {"note_index": 1, "directive_type": "no_charge_window", "applies": True, "structured_adjustment": {"hours": []}},
            # Negative / non-finite factor
            {"note_index": 2, "directive_type": "solar_reduction", "applies": True, "structured_adjustment": {"hours": [12], "factor": float("nan")}},
            # Reserve with string 'invalid'
            {"note_index": 3, "directive_type": "minimum_battery_reserve", "applies": True, "structured_adjustment": {"hours": [18], "minimum_energy_kwh": "infinite"}},
            # Max grid negative
            {"note_index": 4, "directive_type": "max_grid_window", "applies": True, "structured_adjustment": {"hours": [14], "max_grid_kwh": -50.0}},
            # Unknown directive type
            {"note_index": 5, "directive_type": "nuclear_shutdown", "applies": True, "structured_adjustment": {"hours": [1, 2]}},
        ]
        notes = [f"Raw operator note {i}" for i in range(len(adversarial_entries))]

        sanitized = validate_and_guardrail_interpretation(adversarial_entries, notes, battery)
        assert len(sanitized) == len(adversarial_entries)

        for d in sanitized:
            # Invariant check: applies is True iff directive_type != 'no_op'
            assert d.applies == (d.directive_type != "no_op")
            if not d.applies:
                assert d.directive_type == "no_op"
                assert d.structured_adjustment is None
            else:
                assert d.directive_type != "no_op"
                assert isinstance(d.structured_adjustment, dict)


# =============================================================================
# 5. Complex Edge Time Expressions
# =============================================================================

class TestEdgeTimeExpressions:
    """Verify robust deterministic parsing of complex time windows."""

    @pytest.mark.parametrize("text,expected_hours", [
        ("11 to 2 pm", [11, 12, 13]),
        ("from 11 to 2 pm", [11, 12, 13]),
        ("11 am to 2 pm", [11, 12, 13]),
        ("10 pm to midnight", [22, 23]),
        ("between 10 PM and midnight", [22, 23]),
        ("10 pm until midnight", [22, 23]),
        ("10 pm to 12 am", [22, 23]),
        ("12 am to 4 am", [0, 1, 2, 3]),
        ("from noon until 2 PM", [12, 13]),
        ("from noon until 3 pm", [12, 13, 14]),
        ("13:00 and 15:00", [13, 14]),
        ("13:00 to 15:00", [13, 14]),
        ("22:00 to 24:00", [22, 23]),
        ("2 AM until 5 AM", [2, 3, 4]),
        ("6 PM until 10 PM", [18, 19, 20, 21]),
        ("one until three in the morning", [1, 2]),
    ])
    def test_time_window_variations(self, text: str, expected_hours: List[int]):
        assert parse_time_window(text) == expected_hours

    def test_isolated_until_midnight_safely_falls_back(self):
        # Without a starting hour, isolated "until midnight" should safely return []
        assert parse_time_window("until midnight") == []


# =============================================================================
# 6. Factor Inversion ("reduced by X%" vs "reduced to X%")
# =============================================================================

class TestFactorInversion:
    """Verify semantic distinction between relative decrease and absolute remaining."""

    @pytest.mark.parametrize("note_text,expected_factor", [
        ("Solar forecast is reduced by 75% between 12:00 and 14:00 due to cleaning.", 0.25),
        ("Solar forecast is reduced to 25% between 12:00 and 14:00 due to cleaning.", 0.25),
        ("Solar output reduced by 20% from 1 pm to 3 pm due to cloud cover.", 0.80),
        ("Solar output reduced to 20% from 1 pm to 3 pm due to cloud cover.", 0.20),
        ("Solar generation drops by 80% between 11 am and 1 pm.", 0.20),
        ("Solar generation is down to 30% between 11 am and 1 pm.", 0.30),
        ("Solar output is expected at roughly 25% of forecast between 12:00 and 14:00.", 0.25),
        ("Solar production cut by 40% from 10 am to 12 pm.", 0.60),
    ])
    def test_factor_inversion_cases(self, note_text: str, expected_factor: float):
        extracted = fallback_extract_note(note_text, 0, capacity=200.0)
        assert extracted["applies"] is True
        assert extracted["directive_type"] == "solar_reduction"
        factor = extracted["structured_adjustment"]["factor"]
        assert pytest.approx(factor, rel=1e-3) == expected_factor


# =============================================================================
# 7. Substring Collision ("discharge" vs "charge")
# =============================================================================

class TestSubstringCollision:
    """Verify that 'discharge' does not trigger 'no_charge_window'."""

    @pytest.mark.parametrize("note_text,expected_type", [
        ("Battery discharge maintenance is scheduled from 5 PM until 7 PM.", "no_discharge_window"),
        ("Battery discharge is disabled from 5 PM until 7 PM during relay testing.", "no_discharge_window"),
        ("Discharging is not allowed from 2 pm to 5 pm.", "no_discharge_window"),
        ("Battery charging maintenance from 10 am to 12 pm.", "no_charge_window"),
        ("Battery charge is unavailable between 1 pm and 3 pm.", "no_charge_window"),
    ])
    def test_charge_discharge_discrimination(self, note_text: str, expected_type: str):
        extracted = fallback_extract_note(note_text, 0, capacity=200.0)
        assert extracted["applies"] is True
        assert extracted["directive_type"] == expected_type


# =============================================================================
# 8. Controlled HTTP 500 Error Sanitization
# =============================================================================

class TestControlledHttp500Sanitization:
    """Verify that unexpected 500 errors never leak tracebacks, paths, or secrets."""

    def test_unhandled_exception_sanitization(self, base_valid_payload: Dict[str, Any]):
        leak_canary = "SUPER_SECRET_AWS_KEY_DO_NOT_LEAK_12345"
        
        with patch("app.main.solve_energy_schedule", side_effect=RuntimeError(leak_canary)):
            # raise_server_exceptions=False ensures Starlette routes through exception handler
            safe_client = TestClient(app, raise_server_exceptions=False)
            r = safe_client.post("/optimize-energy", json=base_valid_payload)
            
            assert r.status_code == 500
            data = r.json()
            assert "detail" in data
            # Secret Canary must NEVER appear in response
            assert leak_canary not in r.text
            # Internal Python stack traces must NEVER appear in response
            assert "traceback" not in r.text.lower()
            assert 'file "' not in r.text.lower()


# =============================================================================
# 9. Guardrail Numeric Sanitization (NaN / Inf / Unit Suffixes)
# =============================================================================

class TestGuardrailNumericSanitizer:
    """Verify that NaN, Inf, and common unit strings are safely sanitized."""

    @pytest.mark.parametrize("input_val,expected_clean", [
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        ("NaN", None),
        ("inf", None),
        ("-infinity", None),
        ("100.5", 100.5),
        ("250 kWh", 250.0),
        ("20%", 0.2),
        ("invalid", None),
        (None, None),
    ])
    def test_clean_finite_float(self, input_val: Any, expected_clean: Any):
        res = _clean_finite_float(input_val)
        if expected_clean is None:
            assert res is None
        else:
            assert pytest.approx(res, rel=1e-4) == expected_clean


# =============================================================================
# 10. Security Injections, Extreme Values & Offline Fallback
# =============================================================================

class TestSecurityAndOfflineGuarantees:
    """Verify resilient operation under injection attacks, edge values, and offline mode."""

    def test_sql_injection_string_in_scenario_id(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["scenario_id"] = "' OR 1=1; DROP TABLE campus; --"
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 200
        assert r.json().get("scenario_id") == payload["scenario_id"]

    def test_unicode_and_emoji_in_scenario_and_notes(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        payload["scenario_id"] = "SCENARIO-⚡-2026-🎯"
        payload["operator_notes"] = ["Solar panels washed ☀️ from 11 am to 1 pm, cut by 50%."]
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 200
        assert r.json().get("scenario_id") == payload["scenario_id"]
        assert len(r.json().get("hourly_plan", [])) == 24

    def test_zero_demand_solar_and_tariff(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        payload = copy.deepcopy(base_valid_payload)
        for h in payload["hours"]:
            h["demand_kwh"] = 0.0
            h["solar_kwh"] = 0.0
            h["tariff_bdt_per_kwh"] = 0.0
        r = client.post("/optimize-energy", json=payload)
        assert r.status_code == 200
        assert r.json().get("total_cost_bdt") == 0.0

    def test_offline_fallback_mode_guarantee(self, client: TestClient, base_valid_payload: Dict[str, Any]):
        with patch("app.llm_interpreter.call_external_llm", return_value=None):
            r = client.post("/optimize-energy", json=base_valid_payload)
            assert r.status_code == 200
            res = r.json()
            assert len(res.get("hourly_plan", [])) == 24
            assert res.get("total_cost_bdt") is not None


# =============================================================================
# 11. LLM / Fallback Merge (LLM key-name drift)
# =============================================================================

class TestLlmFallbackMerge:
    """A valid LLM directive must survive the hybrid merge even when the model names the key 'type'."""

    def test_llm_directive_keyed_type_is_not_overridden_by_fallback(self):
        # The regex fallback only reads percentages written with '%', so it answers factor 0.5 here.
        note = "Solar output will fall by 30 percent from 1 PM to 3 PM."
        llm_entries = [{"note_index": 0, "type": "solar_reduction", "applies": True,
                        "structured_adjustment": {"hours": [13, 14], "factor": 0.7}}]
        battery = BatterySpec(capacity_kwh=200, initial_energy_kwh=120, minimum_energy_kwh=40,
                              max_charge_kwh_per_hour=50, max_discharge_kwh_per_hour=50)
        with patch("app.llm_interpreter.call_external_llm", return_value=llm_entries):
            d = asyncio.run(interpret_operator_notes([note], battery))[0]
        assert d.directive_type == "solar_reduction"
        assert d.structured_adjustment == {"hours": [13, 14], "factor": 0.7}


if __name__ == "__main__":
    pytest.main(["-v", __file__])
