"""Task definitions and graders for each difficulty level."""
from typing import Any, Dict, Tuple


def grade_easy(grader_state: Dict[str, Any]) -> Tuple[float, str]:
    """
    Task 1 (Easy): Single service outage.
    Agent must:
      - Investigate postgres-db (0.3)
      - Escalate to database-team (0.3)
      - Apply fix: increase_db_connections (0.4)
    """
    score = 0.0
    reasons = []

    if grader_state.get("investigated_root_cause"):
        score += 0.3
        reasons.append("correctly investigated root cause service (+0.3)")

    if grader_state.get("correct_escalation"):
        score += 0.3
        reasons.append("escalated to correct team (+0.3)")

    if grader_state.get("correct_fix_applied"):
        score += 0.4
        reasons.append("applied correct fix (+0.4)")

    score = max(0.01, min(0.99, score))
    return round(score, 2), "; ".join(reasons) if reasons else "no progress"


def grade_medium(grader_state: Dict[str, Any]) -> Tuple[float, str]:
    """
    Task 2 (Medium): Cascading failure.
    Agent must:
      - Investigate redis-cache (0.2)
      - Identify it as root cause (0.2)
      - Escalate to infra-team (0.2)
      - Apply fix: flush_redis_cache (0.2)
      - Submit postmortem mentioning redis/memory/oom (0.2)
    """
    score = 0.0
    reasons = []

    if grader_state.get("investigated_root_cause"):
        score += 0.2
        reasons.append("investigated redis-cache (+0.2)")

    if grader_state.get("identified_cascade_origin"):
        score += 0.2
        reasons.append("identified cascade origin (+0.2)")

    if grader_state.get("correct_escalation"):
        score += 0.2
        reasons.append("correct escalation (+0.2)")

    if grader_state.get("correct_fix_applied"):
        score += 0.2
        reasons.append("correct fix applied (+0.2)")

    if grader_state.get("postmortem_quality", 0) > 0:
        score += 0.2 * grader_state["postmortem_quality"]
        reasons.append(f"postmortem quality (+{0.2 * grader_state['postmortem_quality']:.2f})")

    score = max(0.01, min(0.99, score))
    return round(min(score, 1.0), 2), "; ".join(reasons) if reasons else "no progress"


def grade_hard(grader_state: Dict[str, Any]) -> Tuple[float, str]:
    """
    Task 3 (Hard): Intermittent auth failure.
    Agent must:
      - Investigate config-service (0.15)
      - Investigate auth-service (0.1)
      - Identify root cause as config-service (0.2)
      - Escalate to security-team (0.15)
      - Apply correct fix: complete_secret_rotation (0.2)
      - Submit detailed postmortem with 4+ keywords (0.2)
    """
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
        score += 0.15
        reasons.append("correct escalation (+0.15)")

    if grader_state.get("correct_fix_applied"):
        score += 0.20
        reasons.append("correct fix applied (+0.20)")

    pm_quality = grader_state.get("postmortem_quality", 0)
    if pm_quality > 0:
        score += 0.20 * pm_quality
        reasons.append(f"postmortem quality (+{0.20 * pm_quality:.2f})")

    score = max(0.01, min(0.99, score))
    return round(min(score, 1.0), 2), "; ".join(reasons) if reasons else "no progress"


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
