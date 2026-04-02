"""Core Incident Response OpenEnv environment."""
import copy
from typing import Any, Dict, Tuple

from app.models import Action, ActionType, Observation, Reward, StateModel, StepResult
from app.scenarios import SCENARIOS
from app.tasks import GRADERS, TASK_META


class IncidentResponseEnv:
    def __init__(self, task_id: str = "task_easy"):
        if task_id not in SCENARIOS:
            raise ValueError(f"Unknown task_id: {task_id}. Choose from {list(SCENARIOS.keys())}")
        self.task_id = task_id
        self.scenario = SCENARIOS[task_id]
        self.meta = TASK_META[task_id]
        self._reset_state()

    def _reset_state(self):
        self.step_count = 0
        self.done = False
        self.cumulative_score = 0.0
        self.history = []
        self.grader_state: Dict[str, Any] = {
            "investigated_root_cause": False,
            "correct_escalation": False,
            "correct_fix_applied": False,
            # medium/hard extras
            "identified_cascade_origin": False,
            "identified_root_cause": False,
            "investigated_config_service": False,
            "investigated_auth_service": False,
            "postmortem_quality": 0.0,
            "no_op_count": 0,
        }

    def reset(self) -> Observation:
        self._reset_state()
        return self._build_observation("Incident detected. Begin your investigation.")

    def state(self) -> StateModel:
        grader_fn = GRADERS[self.task_id]
        score, _ = grader_fn(self.grader_state)
        return StateModel(
            task_id=self.task_id,
            step=self.step_count,
            max_steps=self.meta["max_steps"],
            score=score,
            done=self.done,
            history=self.history,
            grader_state=self.grader_state,
        )

    def step(self, action: Action) -> StepResult:
        if self.done:
            obs = self._build_observation("Episode already finished.")
            return StepResult(observation=obs, reward=Reward(value=0.0, reason="already done"), done=True, info={})

        self.step_count += 1
        reward_value, reward_reason = self._process_action(action)

        # penalize no_op
        if action.action_type == ActionType.NO_OP:
            self.grader_state["no_op_count"] += 1
            reward_value = -0.1
            reward_reason = "no_op penalty"

        # penalize excessive no_ops
        if self.grader_state["no_op_count"] >= 3:
            reward_value = -0.2
            reward_reason = "repeated no_op — agent appears stuck"

        grader_fn = GRADERS[self.task_id]
        current_score, _ = grader_fn(self.grader_state)

        # check done conditions
        max_steps_reached = self.step_count >= self.meta["max_steps"]
        task_complete = self._is_task_complete()

        if task_complete:
            self.done = True
            reward_value = max(reward_value, 0.2)
            reward_reason += " | task complete bonus"

        if max_steps_reached and not self.done:
            self.done = True
            reward_value = min(reward_value, -0.05)
            reward_reason += " | max steps reached"

        self.cumulative_score = current_score

        self.history.append({
            "step": self.step_count,
            "action": action.model_dump(),
            "reward": reward_value,
            "reason": reward_reason,
        })

        obs = self._build_observation(reward_reason)
        return StepResult(
            observation=obs,
            reward=Reward(value=round(reward_value, 3), reason=reward_reason),
            done=self.done,
            info={"score": current_score, "grader_state": copy.deepcopy(self.grader_state)},
        )

    def _process_action(self, action: Action) -> Tuple[float, str]:
        scenario = self.scenario
        atype = action.action_type
        target = action.target.lower().strip()

        if atype == ActionType.INVESTIGATE:
            return self._handle_investigate(target)

        elif atype == ActionType.ESCALATE:
            correct = scenario["correct_escalation"]
            if target == correct:
                if not self.grader_state["correct_escalation"]:
                    self.grader_state["correct_escalation"] = True
                    return 0.3, f"correct escalation to {target}"
                return 0.0, "already escalated correctly"
            else:
                return -0.1, f"wrong escalation target: {target}"

        elif atype == ActionType.APPLY_FIX:
            correct = scenario["correct_fix"]
            if target == correct:
                if not self.grader_state["correct_fix_applied"]:
                    self.grader_state["correct_fix_applied"] = True
                    return 0.4, f"correct fix applied: {target}"
                return 0.0, "fix already applied"
            else:
                return -0.15, f"wrong fix applied: {target} — may worsen incident"

        elif atype == ActionType.POSTMORTEM:
            return self._handle_postmortem(action.details or "")

        return 0.0, "unknown action"

    def _handle_investigate(self, target: str) -> Tuple[float, str]:
        scenario = self.scenario
        root_cause = scenario["root_cause"]

        # task-specific investigation tracking
        if self.task_id == "task_hard":
            if target == "config-service" and not self.grader_state["investigated_config_service"]:
                self.grader_state["investigated_config_service"] = True
                return 0.15, "investigated config-service — found partial secret rotation failure"
            if target == "auth-service" and not self.grader_state["investigated_auth_service"]:
                self.grader_state["investigated_auth_service"] = True
                return 0.10, "investigated auth-service — found JWT verification failures"

        if target == root_cause:
            if not self.grader_state["investigated_root_cause"]:
                self.grader_state["investigated_root_cause"] = True
                if self.task_id == "task_medium":
                    self.grader_state["identified_cascade_origin"] = True
                if self.task_id == "task_hard":
                    self.grader_state["identified_root_cause"] = True
                return 0.3, f"investigated root cause: {target} — anomalies found"
            return 0.05, f"re-investigated {target} — no new findings"

        if target in scenario.get("available_services", []):
            return 0.05, f"investigated {target} — no critical issues found"

        return -0.05, f"unknown service: {target}"

    def _handle_postmortem(self, text: str) -> Tuple[float, str]:
        keywords = self.scenario.get("postmortem_keywords", [])
        if not keywords:
            # easy task doesn't require postmortem
            return 0.0, "postmortem not required for this task"

        text_lower = text.lower()
        matched = [kw for kw in keywords if kw in text_lower]
        quality = len(matched) / len(keywords)
        self.grader_state["postmortem_quality"] = max(self.grader_state.get("postmortem_quality", 0), quality)

        if quality >= 0.8:
            return 0.2, f"high quality postmortem ({len(matched)}/{len(keywords)} keywords)"
        elif quality >= 0.5:
            return 0.1, f"partial postmortem ({len(matched)}/{len(keywords)} keywords)"
        else:
            return 0.0, f"low quality postmortem ({len(matched)}/{len(keywords)} keywords)"

    def _is_task_complete(self) -> bool:
        gs = self.grader_state
        if self.task_id == "task_easy":
            return gs["investigated_root_cause"] and gs["correct_escalation"] and gs["correct_fix_applied"]
        elif self.task_id == "task_medium":
            return (gs["investigated_root_cause"] and gs["correct_escalation"]
                    and gs["correct_fix_applied"] and gs["postmortem_quality"] >= 0.5)
        elif self.task_id == "task_hard":
            return (gs["investigated_config_service"] and gs["investigated_auth_service"]
                    and gs["identified_root_cause"] and gs["correct_escalation"]
                    and gs["correct_fix_applied"] and gs["postmortem_quality"] >= 0.6)
        return False

    def _build_observation(self, message: str) -> Observation:
        scenario = self.scenario
        available = (
            [f"investigate:{s}" for s in scenario["available_services"]]
            + [f"escalate:{t}" for t in scenario["available_teams"]]
            + [f"apply_fix:{f}" for f in scenario["available_fixes"]]
            + ["postmortem:<text>", "no_op"]
        )
        return Observation(
            step=self.step_count,
            alerts=scenario["alerts"],
            logs=scenario["logs"],
            metrics=scenario["metrics"],
            available_actions=available,
            message=message,
            task_id=self.task_id,
            task_description=scenario["description"],
        )
