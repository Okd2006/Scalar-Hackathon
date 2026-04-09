"""
Server entry point — required by openenv multi-mode deployment.
Exposes the FastAPI app and a main() entrypoint for `uv run server`.
"""
import uvicorn
from main import app  # noqa: F401 — re-export for openenv discovery


def main():
    uvicorn.run("main:app", host="0.0.0.0", port=7860, reload=False)


if __name__ == "__main__":
    main()
