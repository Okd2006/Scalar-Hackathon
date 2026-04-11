"""
Baseline inference script for Incident Response OpenEnv.
Uses OpenAI client routed through the provided LiteLLM proxy.

Required env vars (injected by validator):
  API_KEY        - API key for the LiteLLM proxy
  API_BASE_URL   - LiteLLM proxy base URL
  MODEL_NAME     - Model identifier (e.g. gpt-4o-mini)
  ENV_URL        - Environment URL (default: https://okd06-incident-response-env.hf.space)
"""
import os
import json
import time
import requests
from openai import OpenAI

API_KEY = os.environ.get("API_KEY") or os.environ.get("OPENAI_API_KEY", "none")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
ENV_URL = os.environ.get("ENV_URL", "https://okd06-incident-response-env.hf.space")

# always use the injected base_url and api_key — never hardcode
client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

TASKS = ["task_easy", "task_medium", "task_hard"]


def strict_score(score: float) -> float:
    """Keep task-level scores strictly inside the open interval (0, 1)."""
    return max(0.01, min(0.99, round(score, 4)))

SYSTEM_PROMPT = """You are an expert on-call Site Reliability Engineer (SRE).
You are given an active production incident. Your job is to:
1. Investigate services to find the root cause
2. Escalate to the correct team
3. Apply the correct fix
4. Submit a postmortem (for medium/hard tasks)

Respond ONLY with a JSON object — no markdown, no explanation:
{
  "action_type": "investigate" | "escalate" | "apply_fix" | "postmortem" | "no_op",
  "target": "<service-name | team-name | fix-name>",
  "details": "<optional postmortem text>"
}"""


def call_env(method: str, path: str, **kwargs) -> dict:
    url = f"{ENV_URL}{path}"
    resp = getattr(requests, method)(url, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()


def get_llm_action(messages: list) -> dict:
    """Call LLM through the injected proxy."""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.2,
        max_tokens=300,
    )
    raw = response.choices[0].message.content.strip()
    # strip markdown fences if model wraps in them
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def run_task(task_id: str) -> float:
    print(f"[START] task_id={task_id} model={MODEL_NAME}")

    obs = call_env("post", "/reset", params={"task_id": task_id})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"TASK: {obs['task_description']}\n\n"
                f"ALERTS:\n" + "\n".join(obs["alerts"]) + "\n\n"
                f"LOGS:\n{json.dumps(obs['logs'], indent=2)}\n\n"
                f"METRICS:\n{json.dumps(obs['metrics'], indent=2)}\n\n"
                f"AVAILABLE ACTIONS:\n" + "\n".join(obs["available_actions"]) + "\n\n"
                "Respond with your first action as JSON."
            ),
        },
    ]

    done = False
    step_num = 0
    final_score = 0.01

    while not done:
        try:
            action = get_llm_action(messages)
        except Exception as e:
            print(f"[ERROR] task={task_id} step={step_num + 1} llm_error={e}")
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
        final_score = strict_score(result["info"].get("score", 0.01))

        print(f"[STEP] task={task_id} step={step_num + 1} action={action.get('action_type')}:{action.get('target')} reward={reward} score={final_score} done={done}")

        messages.append({"role": "assistant", "content": json.dumps(action)})
        messages.append({
            "role": "user",
            "content": (
                f"Result: {reason} | Reward: {reward} | Score: {final_score} | Done: {done}\n\n"
                + (
                    "Episode complete."
                    if done else
                    f"Current alerts: {result['observation']['alerts']}\n"
                    f"Available actions: {result['observation']['available_actions']}\n"
                    "Respond with your next action as JSON."
                )
            ),
        })

        step_num += 1
        time.sleep(0.5)

    print(f"[END] task_id={task_id} final_score={final_score}")
    return strict_score(final_score)


def main():
    print(f"[START] inference model={MODEL_NAME} env={ENV_URL} base_url={API_BASE_URL}")

    scores = {}
    for task_id in TASKS:
        try:
            score = run_task(task_id)
            scores[task_id] = strict_score(score)
        except Exception as e:
            print(f"[ERROR] task={task_id} error={e}")
            scores[task_id] = 0.01

    avg = sum(scores.values()) / len(scores)
    for task_id, score in scores.items():
        print(f"[RESULT] task={task_id} score={score:.2f}")
    print(f"[END] inference average_score={avg:.2f}")

    return scores


if __name__ == "__main__":
    main()
