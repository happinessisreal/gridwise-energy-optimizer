"""
Deterministic Guardrails and Sanitizer for LLM Directive Interpretations.
Ensures 100% compliance with canonical problem statement rules before optimization.
"""
import math
import re
from typing import List, Dict, Any, Optional
from app.schemas import DirectiveInterpretation, BatterySpec

VALID_DIRECTIVES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op"
}

def _clean_finite_float(val: Any) -> Optional[float]:
    """
    Safely extract and validate a finite float from numeric or string values.
    Returns None if value is missing, NaN, Inf, or unparseable.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        try:
            f = float(val)
            return f if math.isfinite(f) else None
        except (ValueError, OverflowError):
            return None
    if isinstance(val, str):
        s = val.strip()
        # Reject literal non-finite strings immediately
        if s.lower() in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity"):
            return None
        is_pct = "%" in s
        m = re.search(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', s)
        if m:
            try:
                f = float(m.group(0))
                if not math.isfinite(f):
                    return None
                if is_pct and f > 1.0:
                    f = f / 100.0
                return f
            except (ValueError, OverflowError):
                return None
    return None

def sanitize_hours(raw_hours: Any) -> List[int]:
    """
    Validates and normalizes hours into a sorted, unique list of integers in range [0, 23].
    """
    if not isinstance(raw_hours, list):
        return []
    valid = set()
    for h in raw_hours:
        try:
            h_int = int(h)
            if 0 <= h_int <= 23:
                valid.add(h_int)
        except (ValueError, TypeError):
            continue
    return sorted(list(valid))

def validate_and_guardrail_interpretation(
    raw_entries: List[Dict[str, Any]],
    operator_notes: List[str],
    battery: BatterySpec
) -> List[DirectiveInterpretation]:
    """
    Applies deterministic validation and normalization to LLM output.
    Guarantees that:
    1. Exactly one entry per operator note in note_index order (0..N-1).
    2. Only valid directive types are accepted.
    3. applies == False <==> directive_type == 'no_op'.
    4. structured_adjustment shape and values conform strictly to Section 04.
    5. No crashes or illegal constraints can reach the mathematical solver.
    """
    sanitized: List[DirectiveInterpretation] = []
    num_notes = len(operator_notes)
    
    # Map raw entries by note_index if available
    raw_by_index: Dict[int, Dict[str, Any]] = {}
    for idx, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            continue
        n_idx = entry.get("note_index", idx)
        if isinstance(n_idx, int) and 0 <= n_idx < num_notes:
            raw_by_index[n_idx] = entry
            
    for i in range(num_notes):
        raw = raw_by_index.get(i)
        if not raw:
            # Fallback for missing note
            sanitized.append(DirectiveInterpretation(
                note_index=i,
                applies=False,
                directive_type="no_op",
                structured_adjustment=None,
                explanation="No valid directive detected for this note."
            ))
            continue
            
        dtype = raw.get("directive_type") or raw.get("type") or "no_op"
        if dtype not in VALID_DIRECTIVES:
            dtype = "no_op"
            
        explanation = str(raw.get("explanation") or "Interpreted directive from operator note.")
        raw_adj = raw.get("structured_adjustment")
        
        if dtype == "no_op":
            sanitized.append(DirectiveInterpretation(
                note_index=i,
                applies=False,
                directive_type="no_op",
                structured_adjustment=None,
                explanation=explanation
            ))
            continue
            
        # Non-no_op directives require valid adjustment dict
        if not isinstance(raw_adj, dict):
            # Cannot apply without structured adjustment; fallback to no_op safely
            sanitized.append(DirectiveInterpretation(
                note_index=i,
                applies=False,
                directive_type="no_op",
                structured_adjustment=None,
                explanation=f"Malformed adjustment for {dtype}; defaulted safely to no_op."
            ))
            continue
            
        hours = sanitize_hours(raw_adj.get("hours"))
        if not hours:
            # Hours are required for all non-no_op directives
            sanitized.append(DirectiveInterpretation(
                note_index=i,
                applies=False,
                directive_type="no_op",
                structured_adjustment=None,
                explanation=f"No valid hours specified for {dtype}; defaulted to no_op."
            ))
            continue
            
        adj: Dict[str, Any] = {"hours": hours}
        is_valid = True
        
        if dtype == "solar_reduction":
            factor = raw_adj.get("factor")
            factor_val = _clean_finite_float(factor)
            if factor_val is None or factor_val < 0.0:
                is_valid = False
            else:
                # If given as percentage > 1 (e.g. 20 for 20%), convert to fraction
                if 1.0 < factor_val <= 100.0:
                    factor_val = factor_val / 100.0
                # Clamp factor to [0.0, 1.0]
                factor_val = max(0.0, min(1.0, factor_val))
                adj["factor"] = round(factor_val, 4)
                
        elif dtype == "minimum_battery_reserve":
            reserve = raw_adj.get("minimum_energy_kwh")
            res_val = _clean_finite_float(reserve)
            if res_val is None or res_val < 0.0:
                is_valid = False
            else:
                # Enforce reserve <= capacity
                res_val = max(0.0, min(battery.capacity_kwh, res_val))
                adj["minimum_energy_kwh"] = round(res_val, 2)
                
        elif dtype == "max_grid_window":
            max_grid = raw_adj.get("max_grid_kwh")
            mg_val = _clean_finite_float(max_grid)
            if mg_val is None or mg_val < 0.0:
                is_valid = False
            else:
                mg_val = max(0.0, mg_val)
                adj["max_grid_kwh"] = round(mg_val, 2)
                
        elif dtype in ("no_charge_window", "no_discharge_window"):
            # Only hours needed
            pass
            
        if not is_valid:
            sanitized.append(DirectiveInterpretation(
                note_index=i,
                applies=False,
                directive_type="no_op",
                structured_adjustment=None,
                explanation=f"Invalid parameter for {dtype}; safely normalized to no_op."
            ))
        else:
            sanitized.append(DirectiveInterpretation(
                note_index=i,
                applies=True,
                directive_type=dtype,
                structured_adjustment=adj,
                explanation=explanation
            ))
            
    return sanitized
