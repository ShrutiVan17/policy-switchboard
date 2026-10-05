"""Prefer the FastAPI runtime; retain the no-install demo fallback."""
def main():
    import os
    try:
        import uvicorn
        import fastapi
    except ImportError:
        if os.environ.get('SWITCHBOARD_PUBLIC_ORIGIN'):raise RuntimeError('Public hosting requires the FastAPI runtime')
        print("FastAPI is not installed. Starting the standard-library local demo.", flush=True)
        from .server import main as fallback
        fallback()
        return
    print("Policy Switchboard: http://127.0.0.1:8765 | FastAPI docs: /docs", flush=True)
    port=int(os.environ.get('SWITCHBOARD_PORT',os.environ.get('PORT','8765')))
    host=os.environ.get('SWITCHBOARD_HOST','0.0.0.0' if os.environ.get('PORT') else '127.0.0.1')
    uvicorn.run("switchboard.api:app",host=host,port=port,log_level="warning")


if __name__ == "__main__":
    main()
