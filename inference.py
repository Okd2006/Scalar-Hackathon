"""
Baseline inference script for Incident Response OpenEnv.
Uses OpenAI client to run an LLM agent against all 3 tasks.

Required env vars:
  OPENAI_API_KEY  - API key
  API_BASE_URL    - API base URL (e.g. https://api.openai.com/v1)
  MODEL_NAME      - Model identifier (e.g. gpt-4o-mini)
"""
import os
import json
import time
import requests
from openai import OpenAI

# ── config ────────────────────────────────────────────────────────────────────
API_KEY = os.environ["OPENAI_API_KEY"]
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
ENV_URL = os.environ.get("ENV_URL", "http://localhost:7860")

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

TASKS = ["task_easy", "task_medium", "task_hard"]

SYSTEM_PROMPT = """You are an expert on-call Site Reliability Engineer (SRE).
You are given an active production incident. Your job is to:
1. Investigate services to find the root cause
2. Escalate to the correct team
3. Apply the correct fix
4. Submit a postmortem (for medium/hard tasks)

At each step you must respond with a JSON object with these fields:
{
  "action_type": one of ["investigate", "escalate", "apply_fix", "postmortem", "no_op"],
  "target": "service-name or team-name or fix-name",
  "details": "optional explanation or postmortem text"
}

Available action types:
- investigate: examine a service's logs/metrics (target = service name)
- escalate: escalate to a team (target = team name)
- apply_fix: apply a remediation (target = fix identifier)
- postmortem: submit root cause analysis (details = full postmortem text)
- no_op: do nothing (avoid this)

Always respond with valid JSON only. No markdown, no explanation outside the JSON.
"""


def call_env(method: str, path: str, **kwargs) -> dict:
    url = f"{ENV_URL}{path}"
    resp = getattr(requests, method)(url, **kwargs)
    resp.raise_for_status()
    return resp.json()


def run_task(task_id: str) -> float:
    print(f"\n{'='*60}")
    print(f"Running task: {task_id}")
    print(f"{'='*60}")

    # reset
    obs = call_env("post", "/reset", params={"task_id": task_id})
    print(f"Task: {obs['task_description']}")
    print(f"Alerts: {obs['alerts']}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"INCIDENT TASK: {obs['task_description']}\n\n"
                f"ALERTS:\n" + "\n".join(obs["alerts"]) + "\n\n"
                f"LOGS:\n{json.dumps(obs['logs'], indent=2)}\n\n"
                f"METRICS:\n{json.dumps(obs['metrics'], indent=2)}\n\n"
                f"AVAILABLE ACTIONS:\n" + "\n".join(obs["available_actions"]) + "\n\n"
                "Begin your investigation. Respond with your first action as JSON."
            ),
        },
    ]

    done = False
    step_num = 0
    final_score = 0.0

    while not done:
        step_num += 1
        print(f"\n--- Step {step_num} ---")

        # get LLM action
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.2,
                max_tokens=512,
            )
            raw = response.choices[0].message.content.strip()
            print(f"LLM response: {raw}")
        except Exception as e:
            print(f"LLM error: {e}")
            break

        # parse action
        try:
            # strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            action_data = json.loads(raw.strip())
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e} — sending no_op")
            action_data = {"action_type": "no_op", "target": "none", "details": ""}

        # step env
        try:
            result = call_env(
                "post", "/step",
                params={"task_id": task_id},
                json=action_data,
                headers={"Content-Type": "application/json"},
            )
        except Exception as e:
            print(f"Env step error: {e}")
            break

        reward = result["reward"]["value"]
        reason = result["reward"]["reason"]
        done = result["done"]
        final_score = result["info"].get("score", 0.0)

        print(f"Reward: {reward} | Reason: {reason} | Done: {done} | Score: {final_score}")

        # add to conversation
        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": (
                f"Result: {reason}\nReward: {reward}\nDone: {done}\n\n"
                f"Current observation:\n{json.dumps(result['observation'], indent=2)}\n\n"
                "Continue. Respond with your next action as JSON."
                if not done else
                f"Episode complete. Final score: {final_score}"
            ),
        })

        time.sleep(0.5)  # rate limit buffer

    print(f"\nFinal score for {task_id}: {final_score}")
    return final_score


def main():
    print("Incident Response OpenEnv — Baseline Inference")
    print(f"Model: {MODEL_NAME}")
    print(f"Env URL: {ENV_URL}")

    scores = {}
    for task_id in TASKS:
        try:
            score = run_task(task_id)
            scores[task_id] = score
        except Exception as e:
            print(f"Error on {task_id}: {e}")
            scores[task_id] = 0.0

    print("\n" + "="*60)
    print("BASELINE RESULTS")
    print("="*60)
    for task_id, score in scores.items():
        print(f"  {task_id}: {score:.2f}")
    avg = sum(scores.values()) / len(scores)
    print(f"  Average: {avg:.2f}")
    print("="*60)

    return scores


if __name__ == "__main__":
    main()
