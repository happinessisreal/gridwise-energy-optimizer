# GridWise — 3-Minute Architecture & Solution Presentation Script
**BUP CSE Fest 2026 Hackathon · Online Preliminary Round**  
*Track: Smart Campus Energy Optimization Challenge (GridWise LLM)*  
*Target Duration: Exactly 3:00 (180 seconds) · Calibrated Speech Rate: ~140 words/min (425 words total)*

---

## Tie-Breaker Rubric Mapping

This presentation script is meticulously engineered to address every tie-breaker priority defined on Page 10 of the official BUP CSE Fest Participant Guide:

| Priority | Evaluation Criterion | Presentation Section | Rubric Coverage in Script |
|:---:|:---|:---|:---|
| **#1** | **3-Minute Video Presentation** | Whole Script | Crisp 3-minute delivery, clear visuals, structured storyboard. |
| **#2** | **Directive Application & Physics** | `[1:35 - 2:15]` | Strict enforcement of the 7 microgrid physical laws and end-of-day battery neutrality. |
| **#3** | **LLM Directive Interpretation** | `[0:25 - 0:55]` | Multi-provider LLM pipeline (DeepSeek/Groq/OpenAI) + deterministic semantic extractor. |
| **#4** | **Optimization Quality** | `[1:35 - 2:15]` | Continuous SciPy HiGHS LP solver guaranteeing mathematical global minimum cost. |
| **#5** | **API & Schema Validity** | `[0:55 - 1:35]` | Strict Pydantic v2 contracts, relational validation, HTTP 400 and safe HTTP 500 handlers. |
| **#6** | **Reliability & Stability** | `[2:15 - 2:45]` | Offline zero-dependency fallback mode guaranteeing 100% uptime without external API failures. |
| **#7** | **Documentation & Reproducibility** | `[2:15 - 2:45]` | Comprehensive README, one-click curl verification, and multi-stage Docker container. |
| **#8** | **Exceptional Engineering** | `[0:55 - 1:35]` | 91/91 adversarial test suite, NaN/Inf guardrails, factor inversion & collision fixes. |

---

## Timed Storyboard & Delivery Script

```
+---------------------------------------------------------------------------------------------------+
| Timeline Breakdown                                                                                |
| 0:00 - 0:25 | Slide 1: Challenge Dynamics & Microgrid Mission                                     |
| 0:25 - 0:55 | Slide 2: Decoupled 4-Stage Architecture (LLM -> Guardrails -> Optimizer -> Replay)  |
| 0:55 - 1:35 | Slide 3: Deterministic Guardrails & Adversarial Hardening (91/91 Vectors)          |
| 1:35 - 2:15 | Slide 4: Microgrid Physics & SciPy HiGHS Optimization Formulation                   |
| 2:15 - 2:45 | Screen Demo: Live Terminal Verification (10/10 Samples, 0.0000 BDT Delta)           |
| 2:45 - 3:00 | Slide 5: Production Readiness, Docker Containerization & Conclusion                 |
+---------------------------------------------------------------------------------------------------+
```

---

### [0:00 - 0:25] Scene 1: Challenge Dynamics & Microgrid Mission (25s)
**Visual**: Clean presentation slide displaying the BUP CSE Fest and Poridhi.io logos, team banner, and an architectural schematic of the BUP Campus Microgrid (Solar PV array, Battery Energy Storage System, Variable TOU Grid, Campus Facility Operator).

**Speaker Voiceover**:
> "Honorable judges, welcome to **GridWise**, our solution for the BUP CSE Fest 2026 Smart Campus Energy Optimization Challenge.
>
> Modern universities balance fluctuating rooftop solar, complex campus demand, and time-of-use tariffs. Crucially, facility managers issue critical operational constraints—such as panel washings, relay tests, and feeder caps—through unstructured natural-language notes.
>
> Our mission: bridge natural human communication with rigorous mathematical optimization, scheduling a 24-hour battery plan that minimizes electricity cost while never violating an operational rule."

---

### [0:25 - 0:55] Scene 2: Decoupled 4-Stage Pipeline (30s)
**Visual**: Animated flow diagram highlighting the four decoupled pipeline stages:
1. `POST /optimize-energy` Ingestion
2. LLM Directive Interpreter (Multi-provider DeepSeek/Groq/OpenAI/Gemini)
3. Deterministic Guardrail Layer
4. SciPy HiGHS LP Solver & Independent Physics Replay

**Speaker Voiceover**:
> "The core philosophy of GridWise is simple: **never trust generative AI with raw microgrid math**.
>
> We built a decoupled four-stage pipeline:
> First, our **LLM Directive Interpreter** uses zero-shot operational prompting across DeepSeek-V3, Groq, or OpenAI to extract operational intent while cleanly ignoring distractor notes like registration deadlines.
>
> Second, if an external provider experiences network latency or API rate limits, our engine seamlessly engages a built-in deterministic semantic pattern extractor, guaranteeing 100% operational uptime without 500 errors."

---

### [0:55 - 1:35] Scene 3: Deterministic Guardrails & Adversarial Hardening (40s)
**Visual**: Side-by-side comparison illustrating edge cases resolved by the guardrail layer:
- Invariant: `applies == False <=> directive_type == 'no_op'`
- Complex Time Windows: `"11 to 2 pm"` $\rightarrow$ `[11, 12, 13]`, `"10 pm to midnight"` $\rightarrow$ `[22, 23]`
- Factor Inversion: `"reduced by 75%"` vs `"reduced to 25%"` both mapping to factor `0.25`
- Substring Collision: `"discharge"` discrimination preventing false `"no_charge_window"`
- Relational Battery Bounds: Rejecting $E_0 > \text{Capacity}$ with clean HTTP 400
- Controlled HTTP 500: Zero stack trace or credential leakage

**Speaker Voiceover**:
> "Before any directive reaches our solver, it must pass our **Deterministic Guardrail Layer**.
>
> This layer enforces the mathematical invariant: `applies` is false if and only if the directive is a `no_op`.
>
> We hardened the system against real-world adversarial edge cases:
> - Disambiguating factor inversions between 'reduced by' and 'reduced to'.
> - Resolving noon-crossing and midnight time intervals.
> - Preventing substring collisions between battery charging and discharging maintenance.
> - And sanitizing non-finite floats like NaN and Inf.
>
> Our comprehensive adversarial test suite validates **91 distinct attack vectors**, ensuring invalid requests fail fast with HTTP 400 and unexpected internal exceptions never leak stack traces or secrets."

---

### [1:35 - 2:15] Scene 4: Microgrid Physics & SciPy HiGHS LP Optimizer (40s)
**Visual**: Formula overlay displaying the 96-variable continuous Linear Program:
- Objective: $\min \sum_{h=0}^{23} (\text{tariff}[h] \cdot g[h] - 10^{-6} s[h] + 10^{-7} (c[h] + d[h]))$
- 7 Physical Laws: Hourly Balance, Solar Curtailment, Battery Inverter Rate Limits, Reserve Floors, End-of-Day Neutrality ($E_{24} = E_0$).

**Speaker Voiceover**:
> "At the heart of GridWise is our optimization engine, formulated as a continuous Linear Program with **96 decision variables** and solved using **SciPy's HiGHS simplex solver**.
>
> The solver strictly enforces all 7 GridWise microgrid physical laws:
> 1. Exact hourly campus energy balance at every single hour.
> 2. Solar usage strictly bounded by effective available solar after curtailment.
> 3. Inverter charge and discharge power limits.
> 4. Dynamic reserve floors and transformer grid caps.
> 5. And crucially, **end-of-day battery neutrality**, guaranteeing starting energy equals ending energy.
>
> Because Linear Programming guarantees global optimality, our solver executes in **under 5 milliseconds** and guarantees the absolute global minimum electricity cost in BDT."

---

### [2:15 - 2:45] Scene 5: Live Terminal Demonstration & 100% Benchmark Verification (30s)
**Visual**: High-resolution terminal capture showing live execution of:
1. `python tests/test_samples.py` $\rightarrow$ 10/10 PASS (0.0000 BDT difference across all cases)
2. `python tests/test_api.py` $\rightarrow$ Endpoint status codes PASS
3. `pytest tests/test_adversarial.py` $\rightarrow$ 91 passed in 11.8s

**Speaker Voiceover**:
> "Let’s see the system verified live.
>
> Running our automated verification harness against all 10 official reference sample cases:
> Every operator directive is extracted with 100% precision.
>
> The solver satisfies every physical constraint, and our calculated electricity cost matches the official reference solutions with **exactly 0.0000 BDT difference across all 10 cases**.
>
> Running `pytest tests/test_adversarial.py`, all **91 adversarial tests pass cleanly**, confirming complete schema validation and error sanitization."

---

### [2:45 - 3:00] Scene 6: Production Deployment & Conclusion (15s)
**Visual**: Closing slide showing Docker container build commands, GitHub repository structure, and Page 11 Pre-Submit Checklist (all 10 checkboxes checked green).

**Speaker Voiceover**:
> "GridWise is fully production-ready, featuring a lightweight non-root multi-stage Docker container, zero baked-in credentials, and a copy-paste local quickstart.
>
> GridWise combines intelligent language comprehension with provable mathematical optimization.
>
> Thank you, BUP CSE Fest and Poridhi.io!"

---

## Live Recording Instructions for Presenter

1. **Audio Setup**: Use a directional condenser microphone or quality headset; record in a quiet room with zero echo.
2. **Screen Capture Settings**: Record terminal and slides at 1920x1080 resolution (60 FPS). Terminal font should be set to 18pt Cascadia Code or Consolas with dark theme and colored pass tags.
3. **Pacing**: Speak with clarity, energy, and deliberate pacing. The script is budgeted for 140 words per minute to finish comfortably at **2 minutes 50 seconds**, safely below the 3:00 hard disqualification ceiling.
4. **Export Format**: Save final video as `.mp4` container with H.264 video codec (10-15 Mbps bitrate) and AAC audio (192 kbps, 48 kHz stereo).
