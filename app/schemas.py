"""
Pydantic schemas strictly matching the BUP CSE Fest 2026 GridWise API contract.
"""
from typing import List, Optional, Any, Dict, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

DirectiveType = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op"
]

BatteryActionType = Literal["charge", "discharge", "idle"]

# --- Request Models ---

class HourEntry(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0-23)")
    demand_kwh: float = Field(..., ge=0, description="Campus demand in kWh")
    solar_kwh: float = Field(..., ge=0, description="Base solar generation forecast in kWh")
    tariff_bdt_per_kwh: float = Field(..., ge=0, description="Grid tariff in BDT per kWh")

# Backward-compatible alias for HourlyData
HourlyData = HourEntry

class BatterySpec(BaseModel):
    capacity_kwh: float = Field(..., gt=0, description="Total battery capacity in kWh")
    initial_energy_kwh: float = Field(..., ge=0, description="Energy in battery at start of day")
    minimum_energy_kwh: float = Field(..., ge=0, description="Base minimum reserve level")
    max_charge_kwh_per_hour: float = Field(..., gt=0, description="Maximum charge rate in kWh/hour")
    max_discharge_kwh_per_hour: float = Field(..., gt=0, description="Maximum discharge rate in kWh/hour")

    @model_validator(mode="after")
    def validate_battery_bounds(self) -> "BatterySpec":
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError(
                f"initial_energy_kwh ({self.initial_energy_kwh}) cannot exceed capacity_kwh ({self.capacity_kwh})"
            )
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError(
                f"minimum_energy_kwh ({self.minimum_energy_kwh}) cannot exceed capacity_kwh ({self.capacity_kwh})"
            )
        if self.initial_energy_kwh < self.minimum_energy_kwh:
            raise ValueError(
                f"initial_energy_kwh ({self.initial_energy_kwh}) cannot be below minimum_energy_kwh ({self.minimum_energy_kwh})"
            )
        return self

class OptimizeEnergyRequest(BaseModel):
    scenario_id: str = Field(..., description="Unique scenario identifier")
    operator_notes: List[str] = Field(..., min_length=1, max_length=3, description="1 to 3 operator notes")
    hours: List[HourEntry] = Field(..., min_length=24, max_length=24, description="Hourly forecast for 24 hours")
    battery: BatterySpec = Field(..., description="Battery specification and parameters")

    @field_validator("operator_notes")
    @classmethod
    def validate_operator_notes(cls, notes: List[str]) -> List[str]:
        if not (1 <= len(notes) <= 3):
            raise ValueError("Must provide between 1 and 3 operator notes.")
        for idx, note in enumerate(notes):
            if not isinstance(note, str) or not note.strip():
                raise ValueError(f"Operator note at index {idx} must be a non-empty string.")
        return notes

    @field_validator("hours")
    @classmethod
    def validate_hours_sequence(cls, v: List[HourEntry]) -> List[HourEntry]:
        if len(v) != 24:
            raise ValueError(f"Request must contain exactly 24 hourly forecast entries, got {len(v)}")
        hours_set = set(h.hour for h in v)
        if len(hours_set) != 24 or hours_set != set(range(24)):
            raise ValueError("Hours must contain exactly 24 distinct hours from 0 through 23.")
        actual = [h.hour for h in v]
        if actual != list(range(24)):
            raise ValueError(f"Hours must be sequential integers from 0 through 23, got: {actual}")
        return v

# --- Response Models ---

class DirectiveInterpretation(BaseModel):
    note_index: int = Field(..., ge=0, description="0-based index of corresponding operator note")
    applies: bool = Field(..., description="True for all applicable directives; False only for no_op")
    directive_type: DirectiveType = Field(..., description="One of the supported directive types or no_op")
    structured_adjustment: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Structured directive adjustments or null for no_op"
    )
    explanation: str = Field(..., description="Short explanation of the interpretation")

    @model_validator(mode="after")
    def validate_directive_invariant(self) -> "DirectiveInterpretation":
        if self.directive_type == "no_op":
            if self.applies:
                raise ValueError("applies must be False when directive_type is 'no_op'")
            if self.structured_adjustment is not None:
                raise ValueError("structured_adjustment must be null/None when directive_type is 'no_op'")
        else:
            if not self.applies:
                raise ValueError(f"applies must be True when directive_type is '{self.directive_type}'")
            if self.structured_adjustment is None:
                raise ValueError(f"structured_adjustment cannot be None when directive_type is '{self.directive_type}'")
        return self

class HourlyPlanEntry(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour integer 0 through 23")
    grid_kwh: float = Field(..., ge=0, description="Grid electricity imported in kWh")
    solar_used_kwh: float = Field(..., ge=0, description="Solar electricity used on campus in kWh")
    battery_action: BatteryActionType = Field(..., description="Battery action: charge, discharge, or idle")
    battery_kwh: float = Field(..., ge=0, description="Magnitude of battery charge/discharge; 0 when idle")
    battery_energy_after_kwh: float = Field(..., ge=0, description="Battery energy state after this hour")

class OptimizeEnergyResponse(BaseModel):
    scenario_id: str = Field(..., description="Echo of input scenario_id")
    directive_interpretation: List[DirectiveInterpretation] = Field(
        ..., description="Directive interpretation per note in note_index order"
    )
    hourly_plan: List[HourlyPlanEntry] = Field(
        ..., min_length=24, max_length=24, description="24-hour optimized energy plan"
    )
    total_grid_kwh: float = Field(..., ge=0, description="Sum of grid_kwh across all 24 hours")
    total_cost_bdt: float = Field(..., ge=0, description="Calculated total grid electricity cost in BDT")
    peak_grid_kwh: float = Field(..., ge=0, description="Peak hourly grid import in kWh")
    plan_summary: str = Field(..., description="Human-readable explanation of the final strategy")

class HealthResponse(BaseModel):
    status: str = Field("ok", description="Readiness status")
