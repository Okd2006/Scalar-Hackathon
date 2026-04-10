"""Task definitions and graders — scores strictly between 0 and 1 exclusive."""
from typing import Any, Dict, Tuple


def _strict(score: float) -> float:
    """Ensure score is strictly between 0 and 1 (never 0.0 or 1.0)."""
    return round(max(0.01, min(0.99, score)), 2)


def grade_easy(grader_state: Dict[str, Any]) -> Tuple[float, str]:
    score = 0.0
    reasons = []
    if grader_state.get("investigated_root_cause"):
        score += 0.32
        reasons.append("investigated root cause (+0.32)")
    if grader_state.get("correct_escalation"):
        score += 0.32
        reasons.append("correct escalation (+0.32)")
    if grader_state.get("correct_fix_applied"):
        score += 0.35
        reasons.append("correct fix applied (+0.35)")
    return _strict(score), "; ".join(reasons) if reasons else "no progress"


def grade_medium(grader_state: Dict[str, Any]) -> Tuple[float, str]:
    score = 0.0
    reasons = []
    if grader_state.get("investigated_root_cause"):
        score += 0.20
        reasons.append("investigated root cause (+0.20)")
    if grader_state.get("identified_cascade_origin"):
        score += 0.19
        reasons.append("identified cascade origin (+0.19)")
    if grader_state.get("correct_escalation"):
        score += 0.20
        reasons.append("correct escalation (+0.20)")
    if grader_state.get("correct_fix_applied"):
        score += 0.20
        reasons.append("correct fix applied (+0.20)")
    pm = grader_state.get("postmortem_quality", 0)
    if pm > 0:
        pts = round(0.20 * pm, 2)
        score += pts
        reasons.append(f"postmortem quality (+{pts})")
    return _strict(score), "; ".join(reasons) if reasons else "no progress"


def grade_hard(grader_state: Dict[str, Any]) -> Tuple[float, str]:
    score = 0.0
    reasons = []
    if grader_state.get("investigated_config_service"):
        score += 0.15
        reasons.append("investigated config-service (+0.15)")
    if grader_state.get("investigated_auth_service"):
        score += 0.10
        reasons.append("investigated auth-service (+0.10)")
    if grader_state.get("identified_root_cause"):
        score += 0.20
        reasons.append("identified root cause (+0.20)")
    if grader_state.get("correct_escalation"):
        score += 0.14
        reasons.append("correct escalation (+0.14)")
    if grader_state.get("correct_fix_applied"):
        score += 0.20
        reasons.append("correct fix applied (+0.20)")
    pm = grader_state.get("postmortem_quality", 0)
    if pm > 0:
        pts = round(0.20 * pm, 2)
        score += pts
        reasons.append(f"postmortem quality (+{pts})")
    return _strict(score), "; ".join(reasons) if reasons else "no progress"


GRADERS = {
    "task_easy": grade_easy,
    "task_medium": grade_medium,
    "task_hard": grade_hard,
}

TASK_META = {
    "task_easy": {"difficulty": "easy", "max_steps": 10},
    "task_medium": {"difficulty": "medium", "max_steps": 15},
    "task_hard": {"difficulty": "hard", "max_steps": 20},
}
