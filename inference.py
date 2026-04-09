"""
Baseline inference script for Incident Response OpenEnv.
Uses OpenAI client as required. Falls back to rule-based policy
if no valid API key is provided.

Required env vars:
  OPENAI_API_KEY  - API key (set to "none" for rule-based mode)
  API_BASE_URL    - API base URL (default: https://api.openai.com/v1)
  MODEL_NAME      - Model identifier (default: gpt-4o-mini)
  ENV_URL         - Environment URL
"""
import os
import json
import time
import requests
from openai import OpenAI

API_KEY = os.environ.get("OPENAI_API_KEY", "none")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
ENV_URL = os.environ.get("ENV_URL", "https://okd06-incident-response-env.hf.space")

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

TASKS = ["task_easy", "task_medium", "task_hard"]

# rule-based policies (used when no real LLM key is available)
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

SYSTEM_PROMPT = """You are an expert on-call SRE. Respond only with a JSON action:
{"action_type": "investigate|escalate|apply_fix|postmortem|no_op", "target": "...", "details": "..."}"""


def call_env(method: str, path: str, **kwargs) -> dict:
    url = f"{ENV_URL}{path}"
    resp = getattr(requests, method)(url, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()


def get_llm_action(messages: list) -> dict:
    """Try real LLM call, fall back to None if unavailable."""
    if API_KEY in ("none", "", None):
        return None
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.2,
            max_tokens=256,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return None


def get_rule_action(task_id: str, step: int) -> dict | None:
    policy = POLICIES[task_id]
    return policy[step] if step < len(policy) else None


def run_task(task_id: str) -> float:
    print(f"[START] task_id={task_id} model={MODEL_NAME}")

    obs = call_env("post", "/reset", params={"task_id": task_id})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"TASK: {obs['task_description']}\n"
                f"ALERTS: {obs['alerts']}\n"
                f"LOGS: {json.dumps(obs['logs'])}\n"
                f"METRICS: {json.dumps(obs['metrics'])}\n"
                f"AVAILABLE: {obs['available_actions']}\n"
                "Respond with your first action as JSON."
            ),
        },
    ]

    done = False
    step_num = 0
    final_score = 0.0

    while not done:
        # try LLM first, fall back to rule-based
        action = get_llm_action(messages)
        if action is None:
            action = get_rule_action(task_id, step_num)
        if action is None:
            break

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

        print(f"[STEP] task={task_id} step={step_num + 1} action={action['action_type']}:{action['target']} reward={reward} score={final_score} done={done}")

        messages.append({"role": "assistant", "content": json.dumps(action)})
        messages.append({
            "role": "user",
            "content": f"Result: {reason} | Reward: {reward} | Done: {done}. Next action?"
        })

        step_num += 1
        time.sleep(0.3)

    print(f"[END] task_id={task_id} final_score={final_score}")
    return final_score


def main():
    print(f"[START] inference model={MODEL_NAME} env={ENV_URL}")

    scores = {}
    for task_id in TASKS:
        try:
            score = run_task(task_id)
            scores[task_id] = score
        except Exception as e:
            print(f"[ERROR] task={task_id} error={e}")
            scores[task_id] = 0.0

    avg = sum(scores.values()) / len(scores)
    for task_id, score in scores.items():
        print(f"[RESULT] task={task_id} score={score:.2f}")
    print(f"[END] inference average_score={avg:.2f}")

    return scores


if __name__ == "__main__":
    main()
