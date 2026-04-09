"""Server entry point — required by openenv multi-mode deployment."""
import uvicorn
from main import app  # noqa: F401


def main():
    uvicorn.run("main:app", host="0.0.0.0", port=7860, reload=False)


if __name__ == "__main__":
    main()
