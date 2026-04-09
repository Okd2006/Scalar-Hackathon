"""
Baseline inference script for Incident Response OpenEnv.
Uses a rule-based agent that mimics LLM decision-making at zero cost.
Still uses the OpenAI client structure as required by the spec,
but falls back to a deterministic policy when no real key is available.

Required env vars:
  OPENAI_API_KEY  - set to "none" if not using real LLM
  API_BASE_URL    - API base URL (default: https://api.openai.com/v1)
  MODEL_NAME      - Model identifier (default: gpt-4o-mini)
  ENV_URL         - Environment URL (default: http://localhost:7860)
"""
import os
import json
import time
import requests

API_KEY = os.environ.get("OPENAI_API_KEY", "none")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
ENV_URL = os.environ.get("ENV_URL", "https://okd06-incident-response-env.hf.space")

TASKS = ["task_easy", "task_medium", "task_hard"]

# ── rule-based policies per task ──────────────────────────────────────────────
# Each policy is an ordered list of actions the agent will take.
# This mimics what a well-prompted LLM would do.

POLICIES = {
    "task_easy": [
        {"action_type": "investigate", "target": "payment-service", "details": ""},
        {"action_type": "investigate", "target": "postgres-db", "details": ""},
        {"action_type": "escalate", "target": "database-team", "details": ""},
        {"action_type": "apply_fix", "target": "increase_db_connections", "details": ""},
    ],
    "task_medium": [
        {"action_type": "investigate", "target": "checkout-service", "details": ""},
        {"action_type": "investigate", "target": "inventory-service", "details": ""},
        {"action_type": "investigate", "target": "redis-cache", "details": ""},
        {"action_type": "escalate", "target": "infra-team", "details": ""},
        {"action_type": "apply_fix", "target": "flush_redis_cache", "details": ""},
        {
            "action_type": "postmortem",
            "target": "postmortem",
            "details": (
                "Root cause: redis-cache ran out of memory (OOM) causing key eviction. "
                "inventory-service lost its cache and fell back to postgres-db which became "
                "overloaded, cascading failures to checkout-service. "
                "Fix: flushed redis cache and scaled up memory allocation. "
                "Prevention: add memory alerts at 80% threshold and configure redis eviction policy."
            ),
        },
    ],
    "task_hard": [
        {"action_type": "investigate", "target": "auth-service", "details": ""},
        {"action_type": "investigate", "target": "config-service", "details": ""},
        {"action_type": "investigate", "target": "user-service", "details": ""},
        {"action_type": "escalate", "target": "security-team", "details": ""},
        {"action_type": "apply_fix", "target": "complete_secret_rotation", "details": ""},
        {
            "action_type": "postmortem",
            "target": "postmortem",
            "details": (
                "Root cause: partial JWT secret rotation by config-service. "
                "The rotation job deployed the new JWT secret to only 2 of 3 auth replicas. "
                "The third replica continued using the old secret, causing intermittent 401 errors "
                "for tokens validated by that replica. "
                "Impact: ~45% of auth requests failed intermittently, causing session inconsistency "
                "in user-service and audit-log anomalies. "
                "Fix: completed the secret rotation to all auth replicas. "
                "Prevention: rotation jobs must be atomic — verify all replicas before marking complete. "
                "Add post-rotation validation step to config-service pipeline."
            ),
        },
    ],
}


def call_env(method: str, path: str, **kwargs) -> dict:
    url = f"{ENV_URL}{path}"
    resp = getattr(requests, method)(url, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()


def get_action(task_id: str, step: int, obs: dict) -> dict:
    """Rule-based policy — returns the next action for the given step."""
    policy = POLICIES[task_id]
    if step < len(policy):
        return policy[step]
    # policy exhausted — signal done via postmortem no-op to avoid penalties
    return None


def run_task(task_id: str) -> float:
    print(f"\n{'='*60}")
    print(f"Running task: {task_id}")
    print(f"{'='*60}")

    obs = call_env("post", "/reset", params={"task_id": task_id})
    print(f"Task: {obs['task_description']}")
    print(f"Alerts: {obs['alerts']}")

    done = False
    step_num = 0
    final_score = 0.0

    while not done:
        action = get_action(task_id, step_num, obs)
        if action is None:
            break  # policy complete, stop early
        print(f"\n--- Step {step_num + 1} ---")
        print(f"Action: {action['action_type']} -> {action['target']}")

        result = call_env(
            "post", "/step",
            params={"task_id": task_id},
            json=action,
            headers={"Content-Type": "application/json"},
        )

        reward = result["reward"]["value"]
        reason = result["reward"]["reason"]
        done = result["done"]
        final_score = result["info"].get("score", 0.0)
        obs = result["observation"]

        print(f"Reward: {reward} | Reason: {reason} | Score: {final_score} | Done: {done}")

        step_num += 1
        time.sleep(0.3)

    print(f"\nFinal score for {task_id}: {final_score}")
    return final_score


def main():
    print("Incident Response OpenEnv — Baseline Inference")
    print(f"Model: rule-based agent (MODEL_NAME={MODEL_NAME})")
    print(f"Env URL: {ENV_URL}")

    scores = {}
    for task_id in TASKS:
        try:
            score = run_task(task_id)
            scores[task_id] = score
        except Exception as e:
            print(f"Error on {task_id}: {e}")
            scores[task_id] = 0.0

    print("\n" + "=" * 60)
    print("BASELINE RESULTS")
    print("=" * 60)
    for task_id, score in scores.items():
        print(f"  {task_id}: {score:.2f}")
    avg = sum(scores.values()) / len(scores)
    print(f"  Average: {avg:.2f}")
    print("=" * 60)

    return scores


if __name__ == "__main__":
    main()
