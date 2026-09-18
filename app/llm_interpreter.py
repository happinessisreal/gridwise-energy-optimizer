"""
LLM Directive Interpreter for operator notes.
Supports OpenAI, Groq, Google Gemini, OpenRouter, and Local endpoints,
with a deterministic semantic extractor fallback for resilient safe failure.
"""
import re
import json
import logging
from typing import List, Dict, Any, Optional
import httpx

from app.config import settings
from app.schemas import BatterySpec, DirectiveInterpretation
from app.guardrails import validate_and_guardrail_interpretation

logger = logging.getLogger("gridwise.llm")

SYSTEM_PROMPT = """You are an expert energy operations assistant for a smart university campus microgrid.
Your task is to interpret 1 to 3 short operator notes into machine-checkable operational directives for a 24-hour energy optimization schedule.

### Supported Directive Types:
1. "solar_reduction": Usable solar forecast is reduced during specific hours.
   - structured_adjustment: {"hours": [int, ...], "factor": number}
   - factor is the USABLE fraction remaining (between 0.0 and 1.0). Example: an 80% reduction means factor = 0.2. A drop to 25% means factor = 0.25.
2. "minimum_battery_reserve": Battery energy must stay at or above a required kWh level during specific hours.
   - structured_adjustment: {"hours": [int, ...], "minimum_energy_kwh": number}
   - If stated as a percentage (e.g., 50% of capacity), calculate absolute kWh = capacity_kwh * (percentage / 100).
3. "no_charge_window": Battery charging is disabled/unavailable during specific hours.
   - structured_adjustment: {"hours": [int, ...]}
4. "no_discharge_window": Battery discharging is disabled/unavailable during specific hours.
   - structured_adjustment: {"hours": [int, ...]}
5. "max_grid_window": Grid electricity import may not exceed a stated kWh amount during specific hours.
   - structured_adjustment: {"hours": [int, ...], "max_grid_kwh": number}
6. "no_op": The note is an irrelevant distractor or does not affect the 24-hour schedule.
   - applies: false
   - structured_adjustment: null

### Rules:
- Time windows are whole-hour intervals: start-inclusive and end-exclusive.
  - "1 PM to 3 PM" -> [13, 14]
  - "from noon until 2 PM" -> [12, 13]
  - "2 AM until 5 AM" -> [2, 3, 4]
  - "from 6 PM until 9 PM" -> [18, 19, 20]
  - "from 6 PM until 10 PM" -> [18, 19, 20, 21]
  - "13:00 and 15:00" -> [13, 14]
- Each entry must be a JSON object with exactly these keys: "note_index" (integer), "applies" (boolean), "directive_type", "structured_adjustment" (object, or null for no_op), "explanation" (short string).
- For every non-no_op directive, applies must be true. For no_op, applies must be false.
- Hours must be strictly ascending unique integers from 0 through 23.
- Output MUST be valid JSON with top-level key "directive_interpretation" containing a list in note_index order (0..N-1).
"""

def parse_time_window(text: str) -> List[int]:
    """Deterministic extraction of whole-hour intervals."""
    text_norm = text.lower()
    text_norm = re.sub(r'\bnoon\b', '12 pm', text_norm)
    
    # Preprocess midnight: if preceded by to/until/and/-, it's the end of window -> 24:00
    # Otherwise if start of window (e.g. from midnight to 4 am) -> 0:00
    text_norm = re.sub(r'(?:until|to|and|-)\s+midnight\b', 'to 24:00', text_norm)
    text_norm = re.sub(r'\bmidnight\b', '0:00', text_norm)
    
    # 24h format: 13:00 to 15:00, 10:00 and 12:00, 22:00 to 24:00
    m_24 = re.search(r'(\d{1,2}):00\s*(?:and|to|until|-)\s*(\d{1,2}):00', text_norm)
    if m_24:
        start = int(m_24.group(1))
        end = int(m_24.group(2))
        return sorted(list(set(h for h in range(start, end) if 0 <= h <= 23)))
        
    # 'to 24:00' with am/pm or number on first: e.g. '10 pm to 24:00' or '22 to 24:00'
    m_to24 = re.search(r'(\d{1,2})\s*(am|pm)?\s*(?:to|until|and|-)\s*24:00', text_norm)
    if m_to24:
        h1 = int(m_to24.group(1))
        mer = m_to24.group(2)
        if mer == 'pm' and h1 < 12:
            h1 += 12
        elif not mer and 6 <= h1 < 12:
            h1 += 12
        return sorted(list(set(h for h in range(h1, 24) if 0 <= h <= 23)))

    # Pattern with 12 am as end hour (e.g. '10 pm to 12 am')
    m_end12am = re.search(r'(\d{1,2})\s*(am|pm)?\s*(?:to|until|and|-)\s*12\s*am\b', text_norm)
    if m_end12am:
        h1 = int(m_end12am.group(1))
        mer = m_end12am.group(2)
        if mer == 'pm' and h1 < 12:
            h1 += 12
        elif not mer and h1 >= 6:
            h1 += 12
        return sorted(list(set(h for h in range(h1, 24) if 0 <= h <= 23)))

    # Flexible AM/PM pattern with optional from/between: e.g. '11 am until 1 pm', '11 to 2 pm', '1-3 pm'
    m = re.search(r'(?:(?:from|between)\s+)?(\d{1,2})(?::00)?\s*(am|pm)?\s*(?:until|to|and|-)\s*(\d{1,2})(?::00)?\s*(am|pm)', text_norm)
    if m:
        h1 = int(m.group(1))
        m1 = m.group(2)
        h2 = int(m.group(3))
        m2 = m.group(4)
        
        # If m1 missing, infer from m2 and values
        if not m1:
            if m2 == 'pm':
                # e.g. 11 to 2 pm -> h1 is 11 am (11 > 2)
                if h1 > h2:
                    m1 = 'am'
                else:
                    m1 = 'pm'
            else:
                m1 = m2
                
        if m1 == 'pm' and h1 < 12:
            h1 += 12
        elif m1 == 'am' and h1 == 12:
            h1 = 0
        
        if m2 == 'pm' and h2 < 12:
            h2 += 12
        elif m2 == 'am' and h2 == 12:
            h2 = 0
        
        # If end is 0 and start is evening, end means hour 24
        if h2 == 0 and h1 > 0:
            h2 = 24
            
        return sorted(list(set(h for h in range(h1, h2) if 0 <= h <= 23)))

    # Worded time ranges (e.g. 'one until three', 'eight until eleven in the morning')
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
    is_morning = any(k in text_norm for k in ["morning", "am"])
    for w1, v1 in words.items():
        for w2, v2 in words.items():
            if f"{w1} until {w2}" in text_norm or f"{w1} to {w2}" in text_norm:
                if not is_morning:
                    v1 = v1 + 12 if v1 < 12 else v1
                    v2 = v2 + 12 if v2 < 12 else v2
                return sorted(list(set(h for h in range(v1, v2) if 0 <= h <= 23)))
                
    return []

def fallback_extract_note(note: str, note_idx: int, capacity: float) -> Dict[str, Any]:
    """Semantic pattern extractor for safe fallback."""
    text = note.lower()
    
    # Check distractors
    distractors = [
        "cafeteria", "sports office", "book-return", "seminar room",
        "club notice", "registration deadline", "menu", "library", "student affairs"
    ]
    if any(k in text for k in distractors):
        return {
            "note_index": note_idx,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "This note does not affect today's 24-hour energy schedule."
        }
        
    hours = parse_time_window(note)
    
    # Invariant: non-no_op requires valid non-empty hours
    if not hours:
        return {
            "note_index": note_idx,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "No applicable hourly time window identified in note."
        }
    
    # 1. Solar reduction
    if any(k in text for k in ["solar", "pv", "panel", "sun"]) and any(
        k in text for k in ["reduc", "drop", "cut", "decreas", "curtail", "wash", "clean", "cloud", "cover", "haze", "inverter", "inspect", "output", "forecast", "production", "down", "generation"]
    ):
        factor = 0.5
        m_by = re.search(r'(?:reduced|reduction|drop|drops|dropped|cut|decrease|decreased|fall|falls|curtail|curtailed)\s+by\s+(\d+(?:\.\d+)?)\s*%', text)
        m_to = re.search(r'(?:reduced|reduction|drop|drops|dropped|fall|falls|down)\s+to\s+(?:about\s+|roughly\s+)?(\d+(?:\.\d+)?)\s*%', text)
        m_noun_red = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:reduction|cut|decrease|curtailment|drop)', text)
        m_target_pct = re.search(r'(?:roughly|about|leave|at|to|remain|remaining)\s+(\d+(?:\.\d+)?)\s*%', text)
        m_pct_of = re.search(r'(\d+(?:\.\d+)?)\s*%\s+of\s+(?:the\s+)?(?:forecast|normal|usual|baseline)', text)
        m_generic_pct = re.search(r'(\d+(?:\.\d+)?)\s*%', text)

        if m_by:
            pct = float(m_by.group(1))
            factor = (100.0 - pct) / 100.0
        elif m_noun_red:
            pct = float(m_noun_red.group(1))
            factor = (100.0 - pct) / 100.0
        elif m_to:
            pct = float(m_to.group(1))
            factor = pct / 100.0
        elif m_target_pct:
            pct = float(m_target_pct.group(1))
            factor = pct / 100.0
        elif m_pct_of:
            pct = float(m_pct_of.group(1))
            factor = pct / 100.0
        elif m_generic_pct:
            pct = float(m_generic_pct.group(1))
            if any(k in text for k in ["reduction", "reduce", "cut", "decreas", "curtail"]):
                factor = (100.0 - pct) / 100.0
            else:
                factor = pct / 100.0
        elif "half" in text:
            factor = 0.5
        elif "one-fifth" in text or "fifth" in text:
            factor = 0.2
        elif "one-fourth" in text or "quarter" in text:
            factor = 0.25
        elif "one-third" in text or "third" in text:
            factor = 1.0 / 3.0
            
        factor = max(0.0, min(1.0, factor))
        return {
            "note_index": note_idx,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {"hours": hours, "factor": round(factor, 4)},
            "explanation": "Solar availability is reduced during the maintenance/weather window."
        }

    # 2. No discharge window (Check discharge BEFORE charge to avoid substring collision)
    is_discharge = any(k in text for k in ["discharge", "discharging"])
    if is_discharge and any(k in text for k in ["not discharge", "not allowed", "disabled", "testing", "relay", "protection", "maintenance", "unavailable", "isolated", "offline"]):
        return {
            "note_index": note_idx,
            "applies": True,
            "directive_type": "no_discharge_window",
            "structured_adjustment": {"hours": hours},
            "explanation": "Battery discharge is disabled during the testing window."
        }

    # 3. No charge window (Ensures 'discharge' is not matched)
    is_charge = bool(re.search(r'\bcharg(?:e|ing|er|ers)?\b', text)) and not is_discharge
    if is_charge and any(k in text for k in ["not charge", "not allowed", "unavailable", "isolated", "maintenance", "disabled", "inspection", "offline", "testing"]):
        return {
            "note_index": note_idx,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {"hours": hours},
            "explanation": "Battery charging is unavailable during the maintenance window."
        }

    # 4. Minimum battery reserve
    if any(k in text for k in ["reserve", "emergency", "stored in the battery", "remain in the battery", "in the battery", "keep at least"]):
        m_pct = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if m_pct:
            pct = float(m_pct.group(1))
            min_kwh = capacity * (pct / 100.0)
        else:
            m_kwh = re.search(r'(\d+(?:\.\d+)?)\s*kwh', text)
            min_kwh = float(m_kwh.group(1)) if m_kwh else 50.0
            
        return {
            "note_index": note_idx,
            "applies": True,
            "directive_type": "minimum_battery_reserve",
            "structured_adjustment": {"hours": hours, "minimum_energy_kwh": round(min_kwh, 2)},
            "explanation": f"Reserve of {min_kwh} kWh required for backup/emergency operations."
        }

    # 5. Max grid window
    if any(k in text for k in ["grid import", "grid intake", "feeder", "transformer", "substation", "grid cap"]):
        m_kwh = re.search(r'(\d+(?:\.\d+)?)\s*kwh', text)
        max_grid = float(m_kwh.group(1)) if m_kwh else 150.0
        return {
            "note_index": note_idx,
            "applies": True,
            "directive_type": "max_grid_window",
            "structured_adjustment": {"hours": hours, "max_grid_kwh": round(max_grid, 2)},
            "explanation": f"Grid import is capped at {max_grid} kWh during the restriction window."
        }

    return {
        "note_index": note_idx,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": "This note does not affect today's 24-hour energy schedule."
    }

async def call_external_llm(notes: List[str], battery: BatterySpec) -> Optional[List[Dict[str, Any]]]:
    """Call external LLM API via httpx with strict timeout."""
    if settings.LLM_PROVIDER in ("", "fallback") or not settings.LLM_API_KEY:
        return None
        
    prompt_user = f"Battery Capacity: {battery.capacity_kwh} kWh\nOperator Notes:\n"
    for i, note in enumerate(notes):
        prompt_user += f"Note {i}: {note}\n"
    prompt_user += "\nReturn JSON object with key 'directive_interpretation' containing one entry per note in note_index order."

    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_user}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
        "max_tokens": 1000
    }

    try:
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                content_clean = content.strip()
                m_json = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content_clean, re.DOTALL)
                if m_json:
                    content_clean = m_json.group(1).strip()
                else:
                    m_obj = re.search(r'\{.*\}', content_clean, re.DOTALL)
                    if m_obj:
                        content_clean = m_obj.group(0).strip()
                parsed = json.loads(content_clean)
                if isinstance(parsed, dict) and "directive_interpretation" in parsed:
                    return parsed["directive_interpretation"]
            else:
                logger.warning(f"External LLM call ({settings.LLM_PROVIDER}) returned status {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.warning(f"External LLM invocation failed: {e}")
        
    return None

async def interpret_operator_notes(
    operator_notes: List[str],
    battery: BatterySpec
) -> List[DirectiveInterpretation]:
    """
    Main interpretation pipeline:
    1. Attempts LLM extraction via configured provider.
    2. Falls back to semantic pattern extractor if LLM is unavailable or unparseable.
    3. Deterministically validates and normalizes all extracted directives through guardrails.
    """
    raw_entries = await call_external_llm(operator_notes, battery)
    
    if raw_entries is None:
        # Fallback to high-precision semantic extractor
        raw_entries = [
            fallback_extract_note(note, i, battery.capacity_kwh)
            for i, note in enumerate(operator_notes)
        ]
    else:
        # Hybrid safety check: if external LLM missed a directive or returned no_op,
        # but deterministic fallback extracted a concrete directive, use the fallback.
        raw_by_idx = {
            e.get("note_index"): e
            for e in raw_entries
            if isinstance(e, dict) and "note_index" in e
        }
        merged = []
        for i, note in enumerate(operator_notes):
            llm_entry = raw_by_idx.get(i)
            fb_entry = fallback_extract_note(note, i, battery.capacity_kwh)
            if not llm_entry or (llm_entry.get("directive_type") or llm_entry.get("type")) in ("no_op", None, ""):
                if fb_entry.get("applies", False):
                    merged.append(fb_entry)
                else:
                    merged.append(llm_entry if llm_entry else fb_entry)
            else:
                merged.append(llm_entry)
        raw_entries = merged
        
    # Pass through strict guardrails and normalizer
    return validate_and_guardrail_interpretation(raw_entries, operator_notes, battery)
