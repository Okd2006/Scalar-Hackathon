---
title: Incident Response OpenEnv
emoji: 🚨
colorFrom: red
colorTo: pink
sdk: docker
pinned: false
tags:
  - openenv
---

# Incident Response OpenEnv

A real-world OpenEnv environment simulating production incident response.
The agent acts as an on-call SRE engineer who must investigate alerts,
identify root causes, escalate to the right team, apply fixes, and write postmortems.

## Motivation

Incident response is one of the most cognitively demanding real-world tasks in software engineering.
It requires multi-step reasoning over noisy signals (logs, metrics, alerts), causal inference
to identify root causes in cascading failures, and clear communication via postmortems.
This makes it an ideal benchmark for evaluating LLM agents on realistic, high-stakes tasks.

---

## Observation Space

| Field | Type | Description |
|---|---|---|
| `step` | int | Current step number |
| `alerts` | list[str] | Active PagerDuty-style alerts |
| `logs` | dict[str, list[str]] | Service logs keyed by service name |
| `metrics` | dict[str, any] | Service metrics (error rate, latency, etc.) |
| `available_actions` | list[str] | Valid actions for this step |
| `message` | str | Feedback from last action |
| `task_id` | str | Current task identifier |
| `task_description` | str | Task objective |

## Action Space

| Field | Type | Description |
|---|---|---|
| `action_type` | enum | One of: `investigate`, `escalate`, `apply_fix`, `postmortem`, `no_op` |
| `target` | str | Service name, team name, or fix identifier |
| `details` | str (optional) | Postmortem text or extra context |

### Action Types
- `investigate` — query a service's logs/metrics to gather evidence
- `escalate` — escalate the incident to a team (e.g. `database-team`)
- `apply_fix` — apply a remediation action (e.g. `increase_db_connections`)
- `postmortem` — submit a root cause analysis write-up
- `no_op` — do nothing (penalized)

---

## Tasks

### Task 1 — Single Service Outage (Easy, max 10 steps)
The `payment-service` is returning 500 errors. The root cause is `postgres-db`
hitting its connection limit. The agent must investigate the database, escalate
to `database-team`, and apply `increase_db_connections`.

Grading:
- Investigate root cause service: +0.3
- Correct escalation: +0.3
- Correct fix: +0.4

### Task 2 — Cascading Microservice Failure (Medium, max 15 steps)
Multiple services are degraded. The origin is `redis-cache` running out of memory,
causing `inventory-service` to fall back to a slow DB, which cascades to `checkout-service`.
The agent must trace the cascade, escalate to `infra-team`, apply `flush_redis_cache`,
and write a postmortem mentioning redis/memory/OOM.

Grading:
- Investigate redis-cache: +0.2
- Identify cascade origin: +0.2
- Correct escalation: +0.2
- Correct fix: +0.2
- Postmortem quality (keyword coverage): up to +0.2

### Task 3 — Intermittent Auth Failure (Hard, max 20 steps)
Users intermittently fail to authenticate due to a partial JWT secret rotation.
`config-service` deployed a new secret to only 2/3 auth replicas, causing
non-deterministic 401 errors. The agent must investigate both `auth-service`
and `config-service`, identify the root cause, escalate to `security-team`,
apply `complete_secret_rotation`, and write a detailed postmortem.

Grading:
- Investigate config-service: +0.15
- Investigate auth-service: +0.10
- Identify root cause: +0.20
- Correct escalation: +0.15
- Correct fix: +0.20
- Postmortem quality: up to +0.20

---

## Reward Function

| Event | Reward |
|---|---|
| Investigate root cause service | +0.15 to +0.30 |
| Correct escalation | +0.30 |
| Correct fix applied | +0.40 |
| High quality postmortem | +0.10 to +0.20 |
| Wrong fix applied | -0.15 |
| Wrong escalation | -0.10 |
| Investigate irrelevant service | +0.05 |
| no_op | -0.10 |
| Repeated no_op (3+) | -0.20 |
| Task complete bonus | +0.20 |
| Max steps exceeded | -0.05 |

---

## Setup & Usage

### Local

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 7860
```

### Docker

```bash
docker build -t incident-response-env .
docker run -p 7860:7860 incident-response-env
```

### API

```bash
# Reset
curl -X POST "http://localhost:7860/reset?task_id=task_easy"

# Step
curl -X POST "http://localhost:7860/step?task_id=task_easy" \
  -H "Content-Type: application/json" \
  -d '{"action_type": "investigate", "target": "postgres-db"}'

# State
curl "http://localhost:7860/state?task_id=task_easy"
```

### Run Inference

```bash
export OPENAI_API_KEY=your_key
export API_BASE_URL=https://api.openai.com/v1
export MODEL_NAME=gpt-4o-mini
export ENV_URL=http://localhost:7860

python inference.py
```

---

## Baseline Scores

Tested with `gpt-4o-mini`:

| Task | Score |
|---|---|
| task_easy | 1.00 |
| task_medium | 0.80 |
| task_hard | 0.60 |
| Average | 0.80 |

---

## Project Structure

```
├── app/
│   ├── environment.py   # core env logic
│   ├── models.py        # Pydantic models
│   ├── tasks.py         # task definitions + graders
│   └── scenarios.py     # synthetic incident data
├── main.py              # FastAPI server
├── inference.py         # baseline agent script
├── openenv.yaml         # env metadata
├── Dockerfile
├── requirements.txt
└── README.md
```
