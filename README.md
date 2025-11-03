# Study Planner API

The Study Planner API generates adaptive, neuroscience-informed revision schedules that combine spaced repetition, retrieval practice, and interleaving. It supports three study modes (Academic, Effective, Crunch) and dynamically adjusts plans as learners report progress.

## Features

- Create personalized revision schedules with mode-specific spacing strategies.
- Suggest review techniques for every scheduled session.
- Adapt schedules based on reported performance, new topics, or availability changes.
- Retrieve the latest plan at any time.

## Getting Started

### Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt`

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the API server

```bash
uvicorn app.main:app --reload
```

The interactive API documentation will be available at `http://127.0.0.1:8000/docs`.

## Usage Overview

### Create a schedule

```http
POST /schedule
Content-Type: application/json

{
  "mode": "Effective",
  "examDate": "2025-12-15",
  "topics": [
    { "name": "Intro to Thermodynamics", "lastCovered": "2025-09-01", "importance": 4 },
    { "name": "Quantum Mechanics Practice", "lastCovered": "2025-09-15", "importance": 5 }
  ],
  "pastPerformance": {
    "Intro to Thermodynamics": { "masteryLevel": 0.8 },
    "Quantum Mechanics Practice": { "masteryLevel": 0.3 }
  }
}
```

### Update a schedule

```http
PATCH /schedule/{scheduleId}
Content-Type: application/json

{
  "completedSessions": [
    { "topic": "Intro to Thermodynamics", "date": "2025-11-07", "result": "success" },
    { "topic": "Quantum Mechanics Practice", "date": "2025-11-07", "result": "failure" }
  ],
  "availabilityChanges": {
    "noStudyDays": ["2025-11-10"],
    "maxSessionsPerDay": 3
  }
}
```

### Retrieve the latest schedule

```http
GET /schedule/{scheduleId}
```

## Development Notes

The implementation stores plans in memory for simplicity. Replace `app.scheduler.MemoryStore` with a persistent store for production deployments. Scheduling heuristics are inspired by spaced repetition research and can be tuned further if needed.
