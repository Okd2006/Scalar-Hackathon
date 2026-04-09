"""FastAPI server exposing the OpenEnv interface."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict

from app.environment import IncidentResponseEnv
from app.models import Action, Observation, StepResult, StateModel

app = FastAPI(
    title="Incident Response OpenEnv",
    description="A real-world on-call incident response environment for AI agents.",
    version="1.0.0",
)

# one env instance per task_id stored in memory
_envs: Dict[str, IncidentResponseEnv] = {}


def _get_env(task_id: str) -> IncidentResponseEnv:
    if task_id not in _envs:
        try:
            _envs[task_id] = IncidentResponseEnv(task_id=task_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return _envs[task_id]


@app.get("/", summary="Health check")
def root():
    return {"status": "ok", "env": "incident-response-openenv", "version": "1.0.0"}


@app.get("/health", summary="Health check")
def health():
    return {"status": "healthy"}


@app.post("/reset", response_model=Observation, summary="Reset environment")
def reset(task_id: str = "task_easy"):
    env = _get_env(task_id)
    obs = env.reset()
    return obs


@app.post("/step", response_model=StepResult, summary="Take a step")
def step(action: Action, task_id: str = "task_easy"):
    env = _get_env(task_id)
    result = env.step(action)
    return result


@app.get("/state", response_model=StateModel, summary="Get current state")
def state(task_id: str = "task_easy"):
    env = _get_env(task_id)
    return env.state()


@app.get("/tasks", summary="List available tasks")
def list_tasks():
    return {
        "tasks": [
            {"id": "task_easy", "difficulty": "easy", "title": "Single Service Outage", "max_steps": 10},
            {"id": "task_medium", "difficulty": "medium", "title": "Cascading Microservice Failure", "max_steps": 15},
            {"id": "task_hard", "difficulty": "hard", "title": "Intermittent Auth Failure with Data Corruption Risk", "max_steps": 20},
        ]
    }
