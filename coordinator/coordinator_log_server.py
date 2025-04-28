# coordinator_log_server.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio
import logging
import queue

# FastAPI app
app = FastAPI()

# Live WebSocket connections
active_websockets = set()

# Queue for live broadcasting
log_queue = queue.Queue()

# Circular buffer to store recent logs
log_buffer = []
MAX_LOG_BUFFER = 1000  # You can adjust this if needed

# HTML page
html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Swarm Live Logs</title>
    <style>
        body { font-family: monospace; background: #111; color: #0f0; padding: 20px; }
        .log-line { margin: 5px 0; }
    </style>
</head>
<body>
    <h2>Live Swarm Logs</h2>
    <div id="logs"></div>
    <script>
        console.log("Connecting to WebSocket...");
        const ws = new WebSocket(`ws://${location.host}/ws/logs`);
        
        ws.onopen = function(event) {
            console.log("✅ Connected to WebSocket Server");
        };

        ws.onmessage = function(event) {
            console.log("📩 New message received:", event.data);
            const line = document.createElement("div");
            line.className = "log-line";
            line.textContent = event.data;
            document.getElementById("logs").prepend(line);
        };

        ws.onerror = function(event) {
            console.error("❌ WebSocket error observed:", event);
        };

        ws.onclose = function(event) {
            console.warn("⚠️ WebSocket connection closed:", event);
        };
    </script>
</body>
</html>
"""

# Serve the HTML page
@app.get("/")
async def get():
    return HTMLResponse(html)

# WebSocket endpoint
@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.add(websocket)
    print("✅ Browser connected:", websocket.client)

    # ➡️ Send buffered logs first
    for old_log in log_buffer:
        try:
            await websocket.send_text(old_log)
        except:
            pass  # Ignore sending failures

    try:
        while True:
            await asyncio.sleep(10)  # Keep connection alive
    except WebSocketDisconnect:
        active_websockets.remove(websocket)

# Background loop to broadcast logs
async def websocket_broadcast_loop():
    while True:
        msg = await asyncio.get_event_loop().run_in_executor(None, log_queue.get)
        print(f"🟢 [DEBUG] Broadcasting log message: {msg}")
        to_remove = set()
        for ws in active_websockets:
            try:
                await ws.send_text(msg)
            except:
                to_remove.add(ws)
        active_websockets.difference_update(to_remove)

# Start broadcast loop after FastAPI app is ready
@app.on_event("startup")
async def startup_event():
    print("🚀 WebSocket broadcast loop is starting...")
    asyncio.create_task(websocket_broadcast_loop())

# Custom WebSocket logging handler
class WebSocketHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        log_queue.put(msg)

        # ➡️ Save in circular buffer
        if len(log_buffer) >= MAX_LOG_BUFFER:
            log_buffer.pop(0)  # Remove oldest
        log_buffer.append(msg)
