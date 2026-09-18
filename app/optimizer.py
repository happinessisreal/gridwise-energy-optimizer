"""
High-performance Mathematical Energy Optimizer for GridWise.
Uses SciPy HiGHS linear programming solver for guaranteed global cost minimization.
"""
from typing import List, Dict, Tuple
import numpy as np
from scipy.optimize import linprog

from app.schemas import (
    HourEntry,
    BatterySpec,
    DirectiveInterpretation,
    HourlyPlanEntry,
    OptimizeEnergyResponse
)

def solve_energy_schedule(
    scenario_id: str,
    hours: List[HourEntry],
    battery: BatterySpec,
    directives: List[DirectiveInterpretation]
) -> OptimizeEnergyResponse:
    """
    Formulates and solves the 24-hour campus energy scheduling problem as a Linear Program (LP).
    Guarantees mathematically optimal total grid cost while respecting all GridWise rules
    and active operator directives.
    """
    n_hours = 24
    
    # 1. Initialize base parameters across all 24 hours
    effective_solar = [h.solar_kwh for h in hours]
    min_reserve = [battery.minimum_energy_kwh] * n_hours
    max_charge = [battery.max_charge_kwh_per_hour] * n_hours
    max_discharge = [battery.max_discharge_kwh_per_hour] * n_hours
    max_grid = [float('inf')] * n_hours
    
    # 2. Apply validated directives
    for d in directives:
        if not d.applies or not d.structured_adjustment:
            continue
            
        dtype = d.directive_type
        adj = d.structured_adjustment
        target_hours = adj.get("hours", [])
        
        if dtype == "solar_reduction":
            factor = adj.get("factor", 1.0)
            for h in target_hours:
                if 0 <= h < n_hours:
                    effective_solar[h] = hours[h].solar_kwh * factor
                    
        elif dtype == "minimum_battery_reserve":
            req_reserve = adj.get("minimum_energy_kwh", battery.minimum_energy_kwh)
            for h in target_hours:
                if 0 <= h < n_hours:
                    min_reserve[h] = max(min_reserve[h], req_reserve)
                    
        elif dtype == "no_charge_window":
            for h in target_hours:
                if 0 <= h < n_hours:
                    max_charge[h] = 0.0
                    
        elif dtype == "no_discharge_window":
            for h in target_hours:
                if 0 <= h < n_hours:
                    max_discharge[h] = 0.0
                    
        elif dtype == "max_grid_window":
            cap = adj.get("max_grid_kwh", float('inf'))
            for h in target_hours:
                if 0 <= h < n_hours:
                    max_grid[h] = min(max_grid[h], cap)

    # 3. Decision variables: 4 variables per hour -> 96 total
    # Var index mapping:
    # 4*h + 0: grid[h]
    # 4*h + 1: solar_used[h]
    # 4*h + 2: charge[h]
    # 4*h + 3: discharge[h]
    
    n_vars = 4 * n_hours
    c = np.zeros(n_vars)
    for h in range(n_hours):
        c[4*h + 0] = hours[h].tariff_bdt_per_kwh
        c[4*h + 1] = -1e-6   # Encourage solar usage over curtailment
        c[4*h + 2] = 1e-7    # Tiny penalty to prevent simultaneous charge/discharge
        c[4*h + 3] = 1e-7

    bounds = []
    for h in range(n_hours):
        bounds.append((0.0, None if max_grid[h] == float('inf') else max_grid[h]))
        bounds.append((0.0, effective_solar[h]))
        bounds.append((0.0, max_charge[h]))
        bounds.append((0.0, max_discharge[h]))

    # 4. Equality constraints (25 total):
    # - 24 hourly energy balances: grid[h] + solar_used[h] + discharge[h] - charge[h] = demand[h]
    # - 1 battery neutrality: sum(charge[h] - discharge[h]) = 0
    A_eq = []
    b_eq = []
    
    for h in range(n_hours):
        row = np.zeros(n_vars)
        row[4*h + 0] = 1.0  # grid
        row[4*h + 1] = 1.0  # solar_used
        row[4*h + 2] = -1.0 # charge
        row[4*h + 3] = 1.0  # discharge
        A_eq.append(row)
        b_eq.append(hours[h].demand_kwh)

    # Neutrality
    row_neut = np.zeros(n_vars)
    for h in range(n_hours):
        row_neut[4*h + 2] = 1.0   # charge
        row_neut[4*h + 3] = -1.0  # discharge
    A_eq.append(row_neut)
    b_eq.append(0.0)

    # 5. Inequality constraints (48 total):
    # - Upper capacity bound for each h: sum_{i=0}^h (charge[i] - discharge[i]) <= capacity - E_0
    # - Lower reserve bound for each h: -sum_{i=0}^h (charge[i] - discharge[i]) <= E_0 - min_reserve[h]
    A_ub = []
    b_ub = []
    
    for h in range(n_hours):
        # Battery capacity constraint
        row_cap = np.zeros(n_vars)
        for i in range(h + 1):
            row_cap[4*i + 2] = 1.0
            row_cap[4*i + 3] = -1.0
        A_ub.append(row_cap)
        b_ub.append(battery.capacity_kwh - battery.initial_energy_kwh)

        # Minimum reserve constraint
        row_res = np.zeros(n_vars)
        for i in range(h + 1):
            row_res[4*i + 2] = -1.0
            row_res[4*i + 3] = 1.0
        A_ub.append(row_res)
        b_ub.append(battery.initial_energy_kwh - min_reserve[h])

    # 6. Solve Linear Program with HiGHS
    res = linprog(
        c,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs"
    )

    if not res.success:
        raise RuntimeError(f"Linear program failed to converge: {res.message}")

    sol = res.x

    # 7. Construct 24-hour schedule and simulate state replay
    hourly_plan: List[HourlyPlanEntry] = []
    current_energy = battery.initial_energy_kwh

    for h in range(n_hours):
        g = max(0.0, float(sol[4*h + 0]))
        s = max(0.0, float(sol[4*h + 1]))
        chg = max(0.0, float(sol[4*h + 2]))
        dis = max(0.0, float(sol[4*h + 3]))

        # Discrete action classification
        if chg > 1e-4:
            action = "charge"
            b_kwh = chg
            current_energy += chg
        elif dis > 1e-4:
            action = "discharge"
            b_kwh = dis
            current_energy -= dis
        else:
            action = "idle"
            b_kwh = 0.0

        # Maintain exact energy accounting
        current_energy = max(min_reserve[h], min(battery.capacity_kwh, current_energy))

        hourly_plan.append(HourlyPlanEntry(
            hour=h,
            grid_kwh=round(g, 4),
            solar_used_kwh=round(s, 4),
            battery_action=action,
            battery_kwh=round(b_kwh, 4),
            battery_energy_after_kwh=round(current_energy, 4)
        ))

    # 8. Recalculate summary metrics from hourly_plan
    total_grid_kwh = round(sum(p.grid_kwh for p in hourly_plan), 2)
    total_cost_bdt = round(sum(p.grid_kwh * hours[p.hour].tariff_bdt_per_kwh for p in hourly_plan), 2)
    peak_grid_kwh = round(max(p.grid_kwh for p in hourly_plan), 2)

    # 9. Formulate descriptive plan summary
    total_solar_used = sum(p.solar_used_kwh for p in hourly_plan)
    total_solar_avail = sum(effective_solar)
    solar_pct = (total_solar_used / total_solar_avail * 100) if total_solar_avail > 0 else 0
    active_directives_count = sum(1 for d in directives if d.applies)

    summary = (
        f"Optimized 24-hour schedule satisfying all {active_directives_count} active directives. "
        f"Achieved minimum grid electricity cost of {total_cost_bdt:,.2f} BDT with {total_grid_kwh:,.2f} kWh total grid import. "
        f"Peak grid demand capped at {peak_grid_kwh:.2f} kWh. Utilized {solar_pct:.1f}% of available solar energy "
        f"with complete battery neutrality at {battery.initial_energy_kwh:.1f} kWh."
    )

    return OptimizeEnergyResponse(
        scenario_id=scenario_id,
        directive_interpretation=directives,
        hourly_plan=hourly_plan,
        total_grid_kwh=total_grid_kwh,
        total_cost_bdt=total_cost_bdt,
        peak_grid_kwh=peak_grid_kwh,
        plan_summary=summary
    )
