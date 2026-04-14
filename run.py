import asyncio
import os
import signal
import sys
import uvicorn
from config import (
    SERVER_HOST,
    SERVER_PORT,
    logger
)
from main import app


async def main():
    """Start the voice agent service without tunnel (run locally)."""
    
    print("⚠️  Running locally without tunnel")
    print(f"  Local URL: http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"  Health Check: http://{SERVER_HOST}:{SERVER_PORT}/health")
    print(f"  To expose publicly, use: npx localtunnel --port {SERVER_PORT}")
    print(f"  Or deploy to production server (AWS/DigitalOcean/Heroku)")
    
    # Start FastAPI server
    config = uvicorn.Config(
        app=app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    # Handle shutdown
    def signal_handler(sig, frame):
        print("\nShutting down...")
        if NGROK_AUTH_TOKEN:
            try:
                ngrok.kill()
            except:
                pass
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("\n" + "="*60)
    print("Medical Receptionist Voice Agent Starting...")
    print("="*60)
    print(f"Server: http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"Health Check: http://{SERVER_HOST}:{SERVER_PORT}/health")
    print("="*60 + "\n")
    
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
        if NGROK_AUTH_TOKEN:
            try:
                ngrok.kill()
            except:
                pass
