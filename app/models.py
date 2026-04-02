from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum


class ActionType(str, Enum):
    INVESTIGATE = "investigate"   # query a service/log
    ESCALATE = "escalate"         # escalate to a team
    APPLY_FIX = "apply_fix"       # apply a remediation
    POSTMORTEM = "postmortem"     # submit root cause + summary
    NO_OP = "no_op"               # do nothing (penalized)


class Action(BaseModel):
    action_type: ActionType
    target: str = Field(..., description="Service name, team name, or fix identifier")
    details: Optional[str] = Field(None, description="Extra context or postmortem text")


class Observation(BaseModel):
    step: int
    alerts: List[str] = Field(default_factory=list)
    logs: Dict[str, List[str]] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    available_actions: List[str] = Field(default_factory=list)
    message: str = ""
    task_id: str = ""
    task_description: str = ""


class Reward(BaseModel):
    value: float = Field(..., ge=-1.0, le=1.0)
    reason: str


class StepResult(BaseModel):
    observation: Observation
    reward: Reward
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)


class StateModel(BaseModel):
    task_id: str
    step: int
    max_steps: int
    score: float
    done: bool
    history: List[Dict[str, Any]] = Field(default_factory=list)
    grader_state: Dict[str, Any] = Field(default_factory=dict)
