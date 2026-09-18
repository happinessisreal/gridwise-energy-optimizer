"""
Comprehensive verification test runner for all 10 official public sample cases.
Replays the final schedule against all GridWise physical, electrical, and operational rules.
"""
import sys
import os
import json
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.schemas import OptimizeEnergyRequest, OptimizeEnergyResponse
from app.llm_interpreter import interpret_operator_notes
from app.optimizer import solve_energy_schedule

async def run_all_sample_cases():
    data_path = Path(__file__).parent.parent / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
    if not data_path.exists():
        data_path = Path("BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json")

    with open(data_path, "r", encoding="utf-8") as f:
        case_pack = json.load(f)

    cases = case_pack["cases"]
    total_cases = len(cases)
    passed_cases = 0

    print(f"\n========================================================")
    print(f"Running GridWise Evaluation Suite on {total_cases} Sample Cases")
    print(f"========================================================\n")

    for idx, case in enumerate(cases):
        cid = case["id"]
        label = case.get("label", "")
        print(f"--- Testing {cid}: {label} ---")
        
        req_data = case["input"]
        exp_data = case["expected_output"]

        # Validate with Pydantic request schema
        req = OptimizeEnergyRequest(**req_data)

        # 1. LLM / Semantic Interpretation
        directives = await interpret_operator_notes(
            operator_notes=req.operator_notes,
            battery=req.battery
        )

        # Verify Directive Ground Truth
        exp_directives = exp_data["directive_interpretation"]
        assert len(directives) == len(exp_directives), f"Directive count mismatch for {cid}"
        
        for i, (actual_d, exp_d) in enumerate(zip(directives, exp_directives)):
            assert actual_d.note_index == exp_d["note_index"], f"Note index mismatch on note {i}"
            assert actual_d.applies == exp_d["applies"], f"Applies mismatch on note {i}: actual={actual_d.applies} vs exp={exp_d['applies']}, actual={actual_d}"
            assert actual_d.directive_type == exp_d["directive_type"], f"Directive type mismatch on note {i}: actual={actual_d.directive_type} vs exp={exp_d['directive_type']}"
            if exp_d["structured_adjustment"] is not None:
                assert actual_d.structured_adjustment == exp_d["structured_adjustment"], (
                    f"Structured adjustment mismatch on note {i}: "
                    f"got {actual_d.structured_adjustment} vs exp {exp_d['structured_adjustment']}"
                )
            else:
                assert actual_d.structured_adjustment is None, f"Expected null adjustment on note {i}"
        print(f"  [PASS] Directive extraction matches 100%")

        # 2. Mathematical Optimization
        response: OptimizeEnergyResponse = solve_energy_schedule(
            scenario_id=req.scenario_id,
            hours=req.hours,
            battery=req.battery,
            directives=directives
        )

        # 3. Independent Judge Replay & Physics Consistency
        plan = response.hourly_plan
        assert len(plan) == 24, f"Plan must contain exactly 24 hours, got {len(plan)}"

        # Compute effective solar
        effective_solar = [h.solar_kwh for h in req.hours]
        min_reserve = [req.battery.minimum_energy_kwh] * 24
        max_grid = [float('inf')] * 24

        for d in directives:
            if not d.applies: continue
            adj = d.structured_adjustment
            if d.directive_type == "solar_reduction":
                for h in adj["hours"]:
                    effective_solar[h] = req.hours[h].solar_kwh * adj["factor"]
            elif d.directive_type == "minimum_battery_reserve":
                for h in adj["hours"]:
                    min_reserve[h] = max(min_reserve[h], adj["minimum_energy_kwh"])
            elif d.directive_type == "max_grid_window":
                for h in adj["hours"]:
                    max_grid[h] = min(max_grid[h], adj["max_grid_kwh"])

        # Replay hour by hour
        curr_battery = req.battery.initial_energy_kwh
        for h in range(24):
            entry = plan[h]
            assert entry.hour == h, f"Hour index mismatch at hour {h}"
            assert entry.grid_kwh >= -1e-4, f"Negative grid at hour {h}"
            assert entry.solar_used_kwh >= -1e-4, f"Negative solar at hour {h}"
            assert entry.solar_used_kwh <= effective_solar[h] + 1e-4, (
                f"Solar overuse at hour {h}: used {entry.solar_used_kwh} > avail {effective_solar[h]}"
            )

            # Check directive specific limits
            if entry.grid_kwh > max_grid[h] + 1e-2:
                raise AssertionError(f"Max grid limit violated at hour {h}: {entry.grid_kwh} > {max_grid[h]}")

            # Battery state update
            chg = entry.battery_kwh if entry.battery_action == "charge" else 0.0
            dis = entry.battery_kwh if entry.battery_action == "discharge" else 0.0

            if entry.battery_action == "charge":
                assert chg <= req.battery.max_charge_kwh_per_hour + 1e-4, f"Max charge exceeded at hour {h}"
                curr_battery += chg
            elif entry.battery_action == "discharge":
                assert dis <= req.battery.max_discharge_kwh_per_hour + 1e-4, f"Max discharge exceeded at hour {h}"
                curr_battery -= dis
            else:
                assert entry.battery_kwh == 0.0, f"Idle battery must have 0 kwh at hour {h}"

            # Check no charge / no discharge windows
            for d in directives:
                if not d.applies: continue
                if d.directive_type == "no_charge_window" and h in d.structured_adjustment["hours"]:
                    assert chg <= 1e-4, f"Charged during no_charge_window at hour {h}"
                elif d.directive_type == "no_discharge_window" and h in d.structured_adjustment["hours"]:
                    assert dis <= 1e-4, f"Discharged during no_discharge_window at hour {h}"

            # Check battery bounds
            assert curr_battery >= min_reserve[h] - 1e-2, (
                f"Battery reserve breached at hour {h}: {curr_battery} < {min_reserve[h]}"
            )
            assert curr_battery <= req.battery.capacity_kwh + 1e-2, (
                f"Battery capacity exceeded at hour {h}: {curr_battery} > {req.battery.capacity_kwh}"
            )

            # Energy balance: grid + solar_used + discharge = demand + charge
            lhs = entry.grid_kwh + entry.solar_used_kwh + dis
            rhs = req.hours[h].demand_kwh + chg
            assert abs(lhs - rhs) < 0.05, f"Energy balance violated at hour {h}: {lhs} != {rhs}"

        # End of day neutrality
        assert abs(curr_battery - req.battery.initial_energy_kwh) < 0.05, (
            f"End-of-day battery neutrality failed: {curr_battery} != {req.battery.initial_energy_kwh}"
        )

        # Check recalculated metrics match
        recalc_grid = round(sum(p.grid_kwh for p in plan), 2)
        recalc_cost = round(sum(p.grid_kwh * req.hours[p.hour].tariff_bdt_per_kwh for p in plan), 2)
        recalc_peak = round(max(p.grid_kwh for p in plan), 2)

        assert abs(response.total_grid_kwh - recalc_grid) < 0.05, "total_grid_kwh mismatch"
        assert abs(response.total_cost_bdt - recalc_cost) < 0.05, "total_cost_bdt mismatch"
        assert abs(response.peak_grid_kwh - recalc_peak) < 0.05, "peak_grid_kwh mismatch"

        # Compare with expected cost
        exp_cost = exp_data["total_cost_bdt"]
        diff = abs(response.total_cost_bdt - exp_cost)
        print(f"  [PASS] Cost: {response.total_cost_bdt:,.2f} BDT (Ref: {exp_cost:,.2f} BDT, Diff: {diff:.4f})")
        assert diff < 0.05, f"Cost optimality discrepancy: {diff} BDT"

        passed_cases += 1
        print(f"  [PASS] {cid} passed all judge checks successfully.\n")

    print(f"========================================================")
    print(f"TEST SUMMARY: {passed_cases}/{total_cases} CASES PASSED (100% SUCCESS RATE)")
    print(f"========================================================\n")

def test_all_sample_cases():
    asyncio.run(run_all_sample_cases())

if __name__ == "__main__":
    test_all_sample_cases()
