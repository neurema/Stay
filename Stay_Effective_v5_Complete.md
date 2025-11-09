
# 🧠 Stay Effective v5 — Complete Specification (Deterministic Version)

This document defines the **Stay Effective v5** adaptive revision scheduling system — an evolution of v2.1 and v4.x models — with **deterministic scheduling**, **dynamic base intervals**, and **normalized performance interpretation tables**.

> **Sources referenced:** core formulas and tables below are taken from the Neurema / Stay drafts. See the bibliography at the end.

---

## 1. Parameters
```
TOTAL_DAYS           ← total duration (e.g., 270)
REVISION_INTERVALS   ← [0, 1, 3, 7, 14, 30]       # standard spaced intervals (INTRO → 30D)
BUBBLE_WINDOW        ← [202, 269]                 # final revision window (last 25% of timeline)
MAX_REVISIONS_DAY    ← 25                         # daily capacity (user tuneable)
EF_MIN               ← 1.3
ALPHA_PI             ← 0.85                       # inertia for PI updates (α)
GAMMA_CRS            ← 0.05                       # CRS exponential mixing (γ)
P_REF                ← 0.9                        # reference mastery (Pref)
P_NEXT               ← 0.75                       # next target probability (Pnext)
KAPPA                ← 1.5                        # CRS scaling constant κ (v2.1)
SIGMOID_GAMMA        ← 3.0                        # γ parameter for αM sigmoid
SIGMOID_MU           ← 2.8                        # µ parameter for αM sigmoid
```

Notes:
- These constants and defaults are taken from the Neurema / Stay specs. 

---

## 2. Topic Structure
```
Each Topic has:
  id
  subject_tag
  difficulty ∈ [0,1]
  add_day
  EF        (Easiness Factor)
  PI        (Possibility / Performance Index)
  CRS       (Composite Readiness / Cognitive Retention Score)
  is_hard   (bool)
  schedule  = list of revision days (deterministic queue)
  history   = list of (day, outcome, EF, PI, CRS, notes)
  revision_count = integer (how many revisions executed so far)
```
---

## 3. Initialization
```
function INIT_TOPIC(id, subject, add_day, difficulty, RT, AS):
    topic.id          ← id
    topic.subject_tag ← subject
    topic.difficulty  ← difficulty
    topic.add_day     ← add_day
    topic.is_hard     ← (difficulty ≥ 0.7)
    # Base_EF can be computed from normalized inputs (v2.1):
    # RT, AS and D (difficulty index) are provided or computed externally and normalized to [0.6,1.2]
    # Base_EF (v2.1 style) = RT + D + AS
    topic.Base_EF     ← RT + normalized_difficulty_index(difficulty) + AS
    topic.EF          ← topic.Base_EF   # starting EF (subject to EF_MIN clipping later)
    topic.PI          ← default_PI()    # application can set initial PI (e.g., 0.8)
    topic.CRS         ← (topic.EF * topic.PI) / KAPPA   # initial composite readiness (v2.1). 
    topic.schedule    ← []
    topic.history     ← []
    topic.revision_count ← 0
    return topic
```
Notes:
- `normalized_difficulty_index()` maps difficulty levels to D ∈ {1.2, 0.9, 0.6} as in §12.  
- `RT` and `AS` are the normalized RT and Accuracy indices from §12.

---

## 4. Build Base Revision Schedule (deterministic)
```
function BUILD_SCHEDULE(topic):
    for each interval in REVISION_INTERVALS:
        day ← topic.add_day + interval
        if day ≤ TOTAL_DAYS:
            topic.schedule.append(day)
```
Notes:
- REVISION_INTERVALS = [0,1,3,7,14,30]. The "INTRO" (0) means same-day initial exposure. fileciteturn1file0

---

## 5. Add Bubble Revisions (structural)
```
function ADD_BUBBLE_REVISIONS(topic):
    # Two bubble events per topic placed inside BUBBLE_WINDOW. Placement differs by is_hard flag.
    if topic.is_hard:
        bubble_days ← two evenly spaced days between midpoint(BUBBLE_WINDOW) and end(BUBBLE_WINDOW)
    else:
        bubble_days ← two evenly spaced days between start(BUBBLE_WINDOW) and midpoint(BUBBLE_WINDOW)

    for bday in bubble_days:
        topic.schedule.append(bday)

    sort(topic.schedule)      # keep schedule ordered
```
Notes: bubble policy is structural in v5; adaptive entry can be added later.

---

## 6. Exact Canonical Formulas (EF, PI, CRS & Session Probability)

### 6.1 Session Success Probability (deterministic evaluation)
```
P_success = clip(0.05, 0.95, CRS * (0.6 + 0.4 / EF))
```
- `clip(a,b,x)` bounds `x` to `[a,b]`. This formula appears in the v5 draft as the deterministic session success model. fileciteturn1file0

### 6.2 EF Update (SM-2 exact)
```
EF_new = max(EF_MIN, EF_old + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
```
- `q` is the quality code for the session: `q = 5` for success, `q = 1` for failure (deterministic binary mapping used in v5). fileciteturn1file0

### 6.3 PI (Possibility / Performance Index)
```
# v2.1 definition (worked example)
PI = log10(1 + ND / (NS * Tmin))
```
Where:
- `ND` = number of days until target exam date (or horizon remaining).  
- `NS` = number of study slots (or sessions) available per topic set.  
- `Tmin` = minimum time fraction per session (days). Typical Tmin values: Major: 0.10, Medium: 0.06, Minor: 0.03. 

Notes: PI is unbounded in raw form but used as a multiplier; in practice you may clamp or normalize PI depending on downstream usage.

### 6.4 CRS (Composite Readiness / Cognitive Retention Score)

Two complementary uses of CRS appear across v2.1 and v5:

**(A) v2.1 initial composite readiness (static initialization)**  
```
CRS_initial = (EF * PI) / KAPPA
```
(where `KAPPA` default 1.5). 

**(B) v5 dynamic CRS update rule (online mixing)**  
After each executed session, update CRS as:
```
CRS_new = (1 - GAMMA_CRS) * CRS_old + GAMMA_CRS * σ( ln(EF) + 2 * (PI - 0.5) )
```
where:
- `σ(x) = 1 / (1 + exp(-x))` (sigmoid),
- `GAMMA_CRS` is the mixing constant (default 0.05). fileciteturn1file0

Use (A) to initialize, and use (B) to update CRS over time when sessions are executed.

### 6.5 αM modulation (EF → spacing multiplier)
Use the sigmoid modulation:
```
αM(EF) = 0.5 + 1 / (1 + exp( - SIGMOID_GAMMA * (EF - SIGMOID_MU) ))
```
Default `SIGMOID_GAMMA = 3`, `SIGMOID_MU = 2.8`. This factor stretches I_eff relative to BaseInterval. 

---

## 7. From CRS → Effective Interval → Exponential Spacing (deterministic)

1. Compute `I_eff` (effective interval):
```
I_eff = I_base * CRS * αM(EF)
```
- `I_base` is selected from the revision-linked `BASE_INTERVALS` array per revision count (see §7.1). 

2. Convert `I_eff` to an exponential time-constant `S` using the reference probability `P_REF`:
```
S = - I_eff / ln(P_REF)
```
3. For any desired revisit target probability `P*` (e.g., `P_NEXT`), compute time `t` (days) until revisit:
```
t = - S * ln(P*)
```
This yields the deterministic `delta` for scheduling the next revision after the current exposure. 

### 7.1 Dynamic BaseInterval per Revision Number
```
BASE_INTERVALS = [0, 1, 3, 7, 14, 30]  # INTRO, 1D, 3D, 7D, 14D, 30D
if revision_number < len(BASE_INTERVALS):
    I_base = BASE_INTERVALS[revision_number]
else:
    I_base = BASE_INTERVALS[-1]  # cap at 30D
```

---

## 8. Complete Revision Execution Routine (deterministic)
```
function EXECUTE_REVISION(topic, current_day, success_boolean):
    # success_boolean ∈ {True, False}, externally provided (no random draw)
    q = 5 if success_boolean else 1
    s = 1 if success_boolean else 0

    # 1) Update EF (SM-2)
    topic.EF = max(EF_MIN, topic.EF + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))

    # 2) Update PI (possibility / performance index)
    # PI can be recomputed externally per the definition or updated with smoothing
    topic.PI = UPDATE_PI_DETERMINISTIC(topic)  # e.g. recompute PI via formula or keep current

    # 3) Update CRS (dynamic v5 mixing)
    topic.CRS = (1 - GAMMA_CRS) * topic.CRS + GAMMA_CRS * sigmoid( ln(topic.EF) + 2 * (topic.PI - 0.5) )

    # 4) Compute next desired day using I_base determined by topic.revision_count
    I_base = get_I_base(topic.revision_count)
    alphaM = 0.5 + 1 / (1 + exp(-SIGMOID_GAMMA * (topic.EF - SIGMOID_MU)))
    I_eff = I_base * topic.CRS * alphaM
    S = - I_eff / ln(P_REF)
    delta = ceil( -S * ln(P_NEXT) )

    next_day = current_day + delta
    if next_day <= TOTAL_DAYS:
        topic.schedule.append(next_day)

    topic.revision_count += 1
    topic.history.append( (current_day, success_boolean, topic.EF, topic.PI, topic.CRS, next_day) )
```
Notes:
- `UPDATE_PI_DETERMINISTIC` may either recompute PI from static availability (ND, NS, Tmin) or use an EMA smoothing variant; the spec supports both. 

---

## 9. Daily Scheduler & PendingPool (capacity-aware)

High-level:
1. Insert every "next desired event" into a PendingPool as `(desired_day, priority=CRS, topicID)`. 
2. On day `d`, pop candidates with `desired_day ≤ d`, order by `CRS` desc. Respect capacity knobs:
   - `CAPtopics/day` (e.g., MAX_REVISIONS_DAY or CAPtopics/day default 20), and
   - `CAPbubbles/day` (default 5).
3. Form bubbles first when possible (alikeness constraint), then fill remaining individual slots with highest-priority topics. Unschedulable candidates are reinserted into the PendingPool. 

---

## 10. Normalized Interpretation Tables (v2.1 mapping)

Each raw metric is normalized to `[0.6–1.2]` using the tables below before being used to compute `Base_EF` or other indices. These are verbatim from v2.1. 

### (a) Time Ratio Index (RT)
| TE / TT | Interpretation | RT |
|---:|---|:---:|
| ≥ 1.2 | Much faster than expected | 1.1 |
| 1.0–1.2 | Slightly faster | 1.0 |
| 0.8–1.0 | On time / slightly slower | 0.9 |
| 0.6–0.8 | Slower than expected | 0.8 |
| < 0.6 | Very slow | 0.7 |

### (b) Accuracy Score Index (AS)
| Accuracy (%) | Interpretation | AS |
|---:|---|:---:|
| ≥ 90% | Excellent mastery | 1.2 |
| 80–89% | High accuracy | 1.1 |
| 70–79% | Moderate understanding | 1.0 |
| 60–69% | Weak grasp | 0.9 |
| < 60% | Poor performance | 0.8 |

### (c) Difficulty Index (D)
| Difficulty Level | Interpretation | D |
|---:|---|:---:|
| Easy | Low cognitive load | 1.2 |
| Moderate | Normal effort | 0.9 |
| Hard | Conceptually dense | 0.6 |

### (d) EF Range Interpretation
| EF Range | Topic Type | Meaning |
|---:|---|:---:|
| < 2.6 | Struggling | Poor retention – early revision |
| 2.6–3.0 | Average | Normal grasp – standard interval |
| > 3.0 | Confident | Strong understanding – revise later |

---

## 11. Worked Example (deterministic, using v2.1 numbers)
Given:
- RT = 1.1, D = 0.9, AS = 1.1 ⇒ Base_EF = 3.1. 
- ND = 180, NS = 50, Tmin = 0.10 ⇒ PI = log10(1 + 180/(50*0.10)) ≈ log10(1 + 36) ≈ 1.568. 
- CRS_initial = (3.1 × 1.568) / 1.5 ≈ 3.2405. 

Compute αM(EF) with γ=3, µ=2.8 ⇒ αM ≈ 1.21.  
If current revision_number maps to I_base = 5 (legacy example), then I_eff ≈ 5 × 3.2405 × 1.21 ≈ 19.6.  
S = − I_eff / ln(P_REF) with P_REF = 0.9 ⇒ S ≈ 186.1.  
For P_NEXT = 0.75, t = −S ln(0.75) ≈ 53.9 days. 

---

## 12. Implementation Notes & Edge Cases
- Use (A) initial CRS formula at topic creation and (B) dynamic CRS mixing on every executed session. This honours both v2.1 initialization and v5 online updates. fileciteturn1file0turn1file1
- PI can be recomputed deterministically when ND/NS/Tmin change (e.g., when target exam date shifts). Otherwise treat PI as slowly varying and optionally smooth it. 
- EF is clipped to EF_MIN to avoid degenerate spacing. fileciteturn1file0
- If capacity is tight, implement `max_wait_cap` fairness corrections to avoid starvation. 
- Bubble formation uses topic taxonomy/subject tags and prefers hardest topics by CRS. 

---

## 13. Bibliography (source snippets)
- Stay_effective_v5 (Neurema Research Draft) — Canonical EF/PI/CRS updates, session probability, and v5 mixing rules. 
- Neurema (v2.1) — EF composition, PI definition, CRS initial formula, αM, S mapping, and worked numeric example. 

---

## ✅ End of Definitive Specification
This file contains the **exact formulas** and deterministic step-by-step procedure requested. Save and use this as the authoritative v5 reference for implementation.
