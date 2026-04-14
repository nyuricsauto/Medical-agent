import os
import uuid
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import Response, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from config import (
    WS_URL,
    SERVER_HOST,
    SERVER_PORT,
    logger
)
from websocket_handler import handle_websocket

app = FastAPI(title="Medical Receptionist Voice Agent")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Medical Receptionist Voice Agent",
        "version": "1.0.0"
    }


@app.post("/answer")
async def handle_incoming_call(request: Request):
    """
    Vobiz will POST to this endpoint when an inbound call arrives.
    Return Voice XML pointing to WebSocket for audio streaming.
    """
    try:
        # Log all incoming parameters for debugging
        query_params = dict(request.query_params)
        logger.info(f"Incoming request query params: {query_params}")
        
        # Vobiz sends parameters in the request body as form data
        form_data = await request.form()
        form_params = dict(form_data)
        logger.info(f"Incoming request body params: {form_params}")
        
        # Extract caller info from request body (form data) or query params
        caller_id = form_params.get("From", form_params.get("from", query_params.get("From", query_params.get("from", "Unknown"))))
        call_sid = form_params.get("CallSid", form_params.get("callSid", query_params.get("CallSid", query_params.get("callSid", str(uuid.uuid4())))))
        
        logger.info(f"Incoming call from {caller_id} (CallSid: {call_sid})")
        
        # Get WebSocket URL from environment or construct dynamically
        ws_url = WS_URL
        if not ws_url:
            # Fallback: construct from request host
            host = request.headers.get("host", f"{SERVER_HOST}:{SERVER_PORT}")
            scheme = "wss" if request.url.scheme == "https" else "ws"
            ws_url = f"{scheme}://{host}/ws"
        
        # Return Vobiz Voice XML
        voice_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
<Connect>
<Stream url="{ws_url}?call_id={call_sid}&caller_id={caller_id}" />
</Connect>
</Response>'''
        
        logger.info(f"Returning Voice XML with WebSocket URL: {ws_url}")
        logger.info(f"Exact XML being returned (repr): {repr(voice_xml)}")
        return PlainTextResponse(content=voice_xml, headers={"Content-Type": "application/xml"})
    
    except Exception as e:
        logger.error(f"Error handling incoming call: {e}")
        # Return error response in Voice XML format (Vobiz doesn't support <Say>)
        error_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
<Hangup />
</Response>'''
        return PlainTextResponse(content=error_xml, headers={"Content-Type": "application/xml"})


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    call_id: str = Query(..., description="Call session ID"),
    caller_id: str = Query(..., description="Caller phone number")
):
    """
    WebSocket endpoint for real-time audio streaming.
    Vobiz will connect here after receiving the Voice XML from /answer.
    """
    await handle_websocket(websocket, call_id, caller_id)


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "service": "Medical Receptionist Voice Agent",
        "version": "1.0.0",
        "websocket_url": WS_URL or f"ws://{SERVER_HOST}:{SERVER_PORT}/ws"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        log_level="info"
    )
