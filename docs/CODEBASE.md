# Stay Effective v5 – Codebase Overview

This document maps the main modules and explains how requests flow through the system. It’s aimed at contributors who want to understand “what is what.”

## Architecture at a glance
- Entry: `app/main.py` initialises FastAPI, resolves bubble templates, and wires routers.
- HTTP layer: `app/routes/*.py` validates payloads (via `app/models.py`) and calls services.
- Service layer: `app/services.py` orchestrates topic lifecycle, state updates, scheduling, and CSV export.
- Scheduling primitives: `app/formulas.py` (math) and `app/scheduler.py` (per‑day buckets) power planning.
- Configuration: `app/constants.py` centralises tunables and worked‑example values.
- Bubble templates: `app/bubble_templates.py` provides defaults and environment overrides.
- Tests: `app/tests/` validates formulas, endpoints, and aggregate load behaviour.

## Modules

### app/main.py
- Creates the FastAPI app with `title="Stay Effective v5"`.
- Calls `bubble_templates.resolve_templates()` and `services.configure_bubble_templates(...)` at startup.
- Registers routers from `app/routes/topics.py`, `app/routes/revision.py`, and `app/routes/analysis.py`.
- Exposes `/health` for a quick status/spec probe.

### app/models.py
- Pydantic models for request/response bodies:
  - `TopicCreate` – payload to create a topic.
  - `Topic` – serialised topic state returned by endpoints.
  - `SessionResult` – payload to execute a revision.
  - `MonteCarlo*` – request/response scaffolding for future analysis API.
- Compatibility note: fields `base_ef`, `ef`, `pi`, `crs` map to the decay model while preserving legacy names.

### app/constants.py
- Core tunables and defaults (planning horizon, caps per day, index tables, threshold, scaling factors, and Tmin defaults).
- `WORKED_EXAMPLE` collects canonical numbers used by both tests and inline checks in `formulas.py`.

### app/formulas.py
- Implements the decay‑based model:
  - `recall_probability(Δt, S)`
  - `interval_for_threshold(S, T)` then short‑horizon and difficulty scalers
  - `compute_interval(...)` as the composed policy
- Inline assertions cross‑check the math against `WORKED_EXAMPLE` on import.

### app/scheduler.py
- Builds initial per‑topic schedules from revision and bubble offsets.
- `DeterministicScheduler` stores a mapping of `day -> [topic_id, ...]` with helpers to register/update/remove.

### app/bubble_templates.py
- Default soft/hard/balanced templates (relative to `add_day`).
- Environment override via `STAY_BUBBLE_TEMPLATES_FILE` (absolute days or `{values, relative}` object).
- Normalises, validates, and returns templates; `services.configure_bubble_templates(...)` registers them.

### app/services.py
- In‑memory authoritative state of topics and bubble templates.
- Topic creation flow:
  1. Map `rt_ratio`, `accuracy`, and `difficulty` to indices; compute base/initial forgetting rate.
  2. Resolve Tmin and optional explicit bubble template; build initial schedule.
  3. Extend schedule forward to the horizon using deterministic success simulation.
  4. Register with `DeterministicScheduler` and return serialised `Topic`.
- Revision execution flow:
  1. Remove the current day from the schedule; update recall probability and forgetting rate.
  2. Apply optional updates (`nd`, `ns`, `tmin`, `accuracy`, `rt_ratio`, `difficulty`).
  3. Rebuild future schedule from the new anchor day, carrying forward remaining bubble days.
  4. Record history with `next_day` preview and re‑register with the scheduler.
- Daily schedule summary: applies global caps (`MAX_REVISIONS_DAY`, `MAX_BUBBLE_DAY`) and reports capped/overflow counts.
- CSV export: `export_topic_schedule_csv(Path)` writes intro, completed, and planned events per topic.
- Extensibility: `register_bubble_template(...)` and `configure_bubble_templates(...)` manage templates programmatically.

Note: The analysis endpoint calls `services.run_monte_carlo_batch(...)` which is intentionally unimplemented; add it here to return a `MonteCarloBatchResponse` when building out analysis.

### app/routes/
- `topics.py` – `POST /topics/` to create a topic; `GET /topics/{id}` to fetch it.
- `revision.py` – `POST /revision/` executes a revision; `GET /revision/schedule/day/{day}` returns a capped summary for the day.
- `analysis.py` – `POST /analysis/monte-carlo` stub wired to the future `services.run_monte_carlo_batch`.

### app/tests/
- `test_selfcheck.py` – verifies formulas against the worked example with ≤1% relative error.
- `test_endpoints.py` – exercises endpoints via `httpx` ASGI transport; prints request/response payloads for visibility.
- `test_api_revision_load.py` – creates a 900‑topic cohort, assigns bubbles to 100 topics, computes per‑day caps, and plots the load. Produces PNG + CSV artifacts under `app/tests/artifacts/`.

## Data and control flow
1. Client calls a route → Pydantic validates → router delegates to `services`.
2. Services compute intervals using `formulas`, decide days using `scheduler`, and update in‑memory state.
3. Responses serialise internal state into `models.Topic` for clients.

## State and persistence
- This backend stores everything in memory for determinism and simplicity. Restarting the process clears all state.
- Tests reset state by re‑initialising the scheduler and clearing topic maps.
- To add persistence, introduce a repository layer in `services.py` (e.g., swap `_topics`/`_scheduler` with injected interfaces).

## Error handling
- Validation errors (bad Tmin label, out‑of‑range day, etc.) surface as `400` responses.
- Missing topics return `404`.
- The `/analysis/monte-carlo` route currently returns `500` due to the missing service implementation; add it to enable the endpoint.

## Configuration knobs
- Planning horizon: `TOTAL_DAYS`.
- Daily caps: `MAX_REVISIONS_DAY`, `MAX_BUBBLE_DAY`.
- Indices and thresholds: `RT_INDEX_TABLE`, `AS_INDEX_TABLE`, `DIFFICULTY_INDEX_TABLE`, `RECALL_THRESHOLD`.
- Horizon and scaling: `SHORT_HORIZON_DAYS`, `HARD_INTERVAL_SCALE`, `SOFT_INTERVAL_SCALE`, `MIN_INTERVAL_DAYS`.
- Bubble templates: `STAY_BUBBLE_TEMPLATES_FILE` for environment overrides.

