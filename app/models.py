from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum


class ActionType(str, Enum):
    INVESTIGATE = "investigate"
    ESCALATE = "escalate"
    APPLY_FIX = "apply_fix"
    POSTMORTEM = "postmortem"
    NO_OP = "no_op"


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
    value: float = Field(..., description="Reward signal for this step")
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
    score: float = Field(..., gt=0.0, lt=1.0, description="Task score strictly between 0 and 1 exclusive")
    done: bool
    history: List[Dict[str, Any]] = Field(default_factory=list)
    grader_state: Dict[str, Any] = Field(default_factory=dict)
