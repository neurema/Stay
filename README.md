# Stay Effective v5 Backend

Stay Effective v5 is a deterministic spaced‑repetition scheduler exposed via FastAPI. It models topic creation, adaptive revision spacing, and optional "bubble" prioritisation windows for harder material. The codebase implements the specification documented in `Stay_Effective_v5_Complete.md` and includes self‑checks that reproduce the worked examples from that document.

## Why this project exists
- Plan revision sessions for up to 270 days with hard and soft topic bands.
- Keep all logic deterministic so that the backend can be validated against the written spec.
- Offer simple HTTP endpoints for creating topics, logging session outcomes, and inspecting daily load.
- Provide scaffolding for Monte Carlo experimentation to stress-test schedules at scale.

## Repository layout
- `app/main.py` – FastAPI application entry point and router registration.
- `app/models.py` – Pydantic schemas for requests/responses (topics, sessions, Monte Carlo payloads).
- `app/services.py` – Deterministic business logic for topics, schedules, bubble templates, and CSV export.
- `app/scheduler.py` – In‑memory day‑by‑day scheduler backing the `/revision/schedule` endpoint.
- `app/formulas.py` – Decay‑based recall model and threshold scheduling (Δt = −S ln T), with inline worked‑example assertions.
- `app/constants.py` – Tunable constants, bands, caps, and worked example values.
- `app/bubble_templates.py` – Built‑in bubble schedules plus environment‑driven overrides.
- `app/routes/` – API route handlers for topics, revision execution, and analytical endpoints.
- `app/tests/` – `unittest` suites that exercise endpoints, recreate spec math, and generate load charts. Artifacts land in `app/tests/artifacts/`.

For a deeper architecture walkthrough of “what is what,” see `docs/CODEBASE.md`.

## Prerequisites
- Python 3.11 (or newer 3.10+ with `venv`).
- Shell of choice (PowerShell, bash, zsh).
- Packages: `fastapi`, `uvicorn[standard]`, `pydantic`, `httpx`, `anyio` (tests), `matplotlib` (optional for plotting tests).

### Create a virtual environment (Windows PowerShell)
```powershell
py -3.11 -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pydantic httpx anyio matplotlib
```

If you prefer a requirements file, freeze the environment once the basics are installed and commit the list for teammates.

### Create a virtual environment (Linux/macOS)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install fastapi "uvicorn[standard]" pydantic httpx anyio matplotlib
```

## Running the API locally
1. Activate your virtual environment.
2. From the repository root run:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
3. Visit `http://127.0.0.1:8000/docs` for the interactive Swagger UI.

### Key endpoints
| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Simple status probe returning the spec version string.
| `POST` | `/topics/` | Create a topic with deterministic schedule and optional bubble template.
| `GET` | `/topics/{topic_id}` | Fetch the current state, schedule, and history for a topic.
| `POST` | `/revision/` | Log a finished session; updates topic state and rebuilds the future schedule.
| `GET` | `/revision/schedule/day/{day}` | Inspect capped vs total revision load for a given day.
| `POST` | `/analysis/monte-carlo` | Placeholder for batch schedule simulations (service hook currently unimplemented).

#### Example: create a topic
```bash
curl -X POST http://127.0.0.1:8000/topics/ \
  -H "Content-Type: application/json" \
  -d '{
    "subject_tag": "Cardiology",
    "difficulty": 0.65,
    "add_day": 12,
    "rt_ratio": 1.05,
    "accuracy": 0.82,
    "nd": 210,
    "ns": 60,
    "tmin_label": "Major"
  }'
```

#### Example: record a revision session
```bash
curl -X POST http://127.0.0.1:8000/revision/ \
  -H "Content-Type: application/json" \
  -d '{
    "topic_id": "<replace-with-topic-id>",
    "day": 13,
    "success": true
  }'
```
The response includes an updated schedule and the next planned day.

## Bubble templates
Bubble templates let you reserve additional revisions for selected topics.
- Built-in defaults (`default-soft`, `default-hard`, `default-balanced`) apply relative offsets (e.g. +14, +30 days).
- Set `STAY_BUBBLE_TEMPLATES_FILE` to a JSON file that maps template names to either:
  ```json
  {
    "custom-hard": {"values": [20, 35, 48], "relative": true},
    "competition-week": [180, 185, 189]
  }
  ```
- Templates marked `relative: true` treat values as offsets from the topic's `add_day`.
- Use `services.register_bubble_template()` to add templates at runtime (tests demonstrate this pattern).

At startup the app resolves bubble templates via `bubble_templates.resolve_templates()` which reads `STAY_BUBBLE_TEMPLATES_FILE` if provided, or falls back to the built‑ins. The `services.configure_bubble_templates()` call registers them for use by topic creation.

## Exporting schedules
Call `services.export_topic_schedule_csv(Path("./output.csv"))` to materialise a per-topic timeline containing intro, completed revisions, and future planned days. The `app/tests/test_api_revision_load.py` test uses this helper after generating 900 topics.

## Monte Carlo analysis
The `/analysis/monte-carlo` route is wired to `services.run_monte_carlo_batch`. The current codebase does not provide an implementation, so calling this endpoint raises a 500 error. Add your simulation engine there to return `MonteCarloBatchResponse` payloads, and extend the tests to cover typical scenarios.

## Running the test suites
Tests use Python's built‑in `unittest` runner (using httpx’s ASGI transport to exercise endpoints). Execute everything with:
```bash
python -m unittest discover app/tests
```
Key suites:
- `test_selfcheck.py` validates the mathematical formulas against the official worked example (≤1% error).
- `test_endpoints.py` exercises core endpoints via httpx's ASGI transport (avoids environment-specific TestClient lifespan issues).
- `test_api_revision_load.py` generates a 900-topic plan, plots the daily revision load (requires `matplotlib`), and writes CSV artifacts under `app/tests/artifacts/`.

## Troubleshooting tips
- **State resets** – Services store topics in memory. Restart the process or call the private reset helpers (see tests) for a clean slate.
- **Bubble template errors** – Messages such as "Bubble 'xyz' has not been registered" mean you referenced an unknown template id.
- **Schedule bounds** – Days and offsets must be between 0 and `TOTAL_DAYS` (270). Inputs outside that range raise `ValueError`.
- **Matplotlib missing** – The large cohort test skips automatically if `matplotlib` is not installed, so install it when you need the graph artifacts.

## Next steps for contributors
1. Implement `services.run_monte_carlo_batch` to deliver the analysis API.
2. Add persistence (database or file-backed store) if you need state across restarts.
3. Publish an OpenAPI client or simple CLI to manage topics outside the Swagger UI.
4. Automate linting and tests via GitHub Actions once the dependency list is stable.

Happy scheduling! Feel free to adapt the deterministic formulas to your domain while keeping the spec-aligned tests passing.

## Compatibility notes
- Response field names remain `base_ef`, `ef`, `pi`, and `crs` for backward compatibility with existing clients. Internally, these now map to the decay-based model:
  - `base_ef` = base forgetting rate (was base ease factor)
  - `ef` = current forgetting rate (was ease factor)
  - `pi` = current recall probability (was performance index)
  - `crs` = next-interval estimate in days (was composite revision score)
- The endpoint shapes and request payloads are unchanged.

---

For a module-by-module architecture guide, see `docs/CODEBASE.md`.
