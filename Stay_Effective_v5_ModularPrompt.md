
# 🧱 Modular FastAPI Implementation Prompt — Stay Effective v5 (for GPT‑5‑Code)

This Markdown file instructs **GPT‑5‑Code** (Codex) to build a **modular deterministic FastAPI backend**
that implements the Stay Effective v5 specification from `Stay_Effective_v5_Complete.md`.

---

## 🔍 Purpose
Create a *multi‑file* Python project that exactly reproduces all formulas and behavior from the Stay Effective v5 spec — deterministic, test‑verified, and modular.

---

## 📁 Project Layout

```
app/
 ├── __init__.py
 ├── main.py                # FastAPI entrypoint
 ├── constants.py           # constants & tables from spec
 ├── models.py              # Pydantic models
 ├── formulas.py            # EF / PI / CRS / alphaM / I_eff / S logic
 ├── scheduler.py           # deterministic daily & bubble scheduling
 ├── services.py            # orchestration of topic creation & revision
 ├── routes/
 │     ├── __init__.py
 │     ├── topics.py        # /topics endpoints
 │     └── revision.py      # /revision endpoints
 └── tests/
       └── test_selfcheck.py # reproduces Worked Example assertions
```

Each file must include docstrings citing the relevant section from
`Stay_Effective_v5_Complete.md` (e.g., 'Section 6.2 EF Update (SM-2)').

---

## ⚙️ Required Constants (from the MD)

```
EF_MIN, ALPHA_PI, GAMMA_CRS, KAPPA,
SIGMOID_GAMMA, SIGMOID_MU,
P_REF, P_NEXT,
BASE_INTERVALS, REVISION_INTERVALS, BUBBLE_WINDOW,
Tmin defaults (Major 0.10 / Medium 0.06 / Minor 0.03),
RT / AS / D mapping tables,
Worked Example numeric targets.
```

If any are missing in the MD, Codex must **abort with a clear error** referencing the MD section.

---

## 🧩 Module Behavior

### constants.py
- Contain every constant & mapping table.
- Add WORKED_EXAMPLE dictionary with expected numeric values for PI, CRS, alphaM, I_eff, S, and delta.

### models.py
- Define TopicCreate, Topic, SessionResult per spec.

### formulas.py
Implement deterministic math functions:
```
clip(x, lo, hi)
update_ef(EF, success)
compute_pi(ND, NS, Tmin)
compute_crs_initial(EF, PI)
update_crs(CRS_old, EF, PI)
compute_alphaM(EF)
get_I_base(revision_count)
compute_I_eff(I_base, CRS, EF)
compute_S_and_delta(I_eff)
```
Each must include inline assertions comparing to the Worked Example (≤ 1 % error).

### scheduler.py
- Deterministic schedule construction & bubble logic (Section 9).

### services.py
- Functions:
  - create_topic() → computes Base_EF, EF, PI, CRS, initial schedule.
  - execute_revision() → updates EF, PI, CRS → computes next_day → updates schedule.
- In‑memory dictionary store for topics.

### routes/topics.py
- POST /topics/ → create_topic  
- GET /topics/{id} → fetch topic

### routes/revision.py
- POST /revision/ → execute_revision  
- GET /schedule/day/{day} → topics scheduled that day

### main.py
- Assemble FastAPI app, include routers, log spec version.

---

## 🧪 Self‑Check Suite (tests/test_selfcheck.py)

Replicate the Worked Example exactly:

```
ND = 180
NS = 50
Tmin = 0.10
EF = 3.1
Expected:
  PI ≈ 1.568
  CRS ≈ 3.2405
  alphaM ≈ 1.21
  I_eff ≈ 19.6
  S ≈ 186.1
  delta ≈ 53.9
```
Assertions must pass ≤ 1 % relative error.

Run via:
```
python -m app.tests.test_selfcheck
```

---

## ✅ Validation Flow

1. Import all modules — no circular import errors.  
2. Run self‑checks — all must pass.  
3. Confirm `uvicorn app.main:app --reload` starts successfully.  
4. Verify revision endpoint reproduces numeric outputs of the spec.

---

## 🧠 Final Output Rule

Only output all module files **after** successful self‑checks.  
Each file must be complete, syntactically valid, and ready to run.  
If a check fails or a formula is ambiguous, Codex must print a short diagnostic and stop.

---

### Command for Codex

```
Read Stay_Effective_v5_Complete.md → extract constants and formulas → build the above modular FastAPI project → run tests → output source tree only if all tests pass.
```

---

**End of Prompt** — paste this Markdown into GPT‑5‑Code and run.
