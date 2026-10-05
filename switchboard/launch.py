"""Prefer the FastAPI runtime; retain the no-install demo fallback."""
def main():
    import os
    try:
        import uvicorn
        import fastapi
    except ImportError:
        print("FastAPI is not installed. Starting the standard-library local demo.", flush=True)
        from .server import main as fallback
        fallback()
        return
    print("Policy Switchboard: http://127.0.0.1:8765 | FastAPI docs: /docs", flush=True)
    uvicorn.run("switchboard.api:app", host=os.environ.get('SWITCHBOARD_HOST','127.0.0.1'), port=int(os.environ.get('SWITCHBOARD_PORT','8765')), log_level="warning")


if __name__ == "__main__":
    main()
