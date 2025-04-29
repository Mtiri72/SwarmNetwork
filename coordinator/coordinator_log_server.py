# coordinator_log_server.py
import sys
import os
import json
import threading

# Allow imports from parent directory (SwarmNetwork/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(BASE_DIR)


from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
import lib.database_comms as db
import asyncio
import logging
import queue

import socket
import threading


# TCP log server
def start_tcp_log_server(host='0.0.0.0', port=5000):
    def handle_tcp_client(client_socket):
        with client_socket:
            try:
                while True:
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    message = data.decode('utf-8').strip()
                    print(f"🛜 [AP Log Received]: {message}")
                    log_queue.put(message)
            except Exception as e:
                print(f"❌ TCP client error: {e}")

    def server_loop():
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f"🚀 TCP Log Server listening on {host}:{port}...")
        while True:
            client_socket, addr = server_socket.accept()
            print(f"✅ New AP Connected for logs from {addr}")
            threading.Thread(target=handle_tcp_client, args=(client_socket,), daemon=True).start()

    threading.Thread(target=server_loop, daemon=True).start()

#  Immediately start TCP server
start_tcp_log_server()
# FastAPI app
app = FastAPI()

# Live WebSocket connections
active_websockets = set()
active_database_websockets = set()


# Queue for live broadcasting
log_queue = queue.Queue()

# Circular buffer to store recent logs
log_buffer = []
MAX_LOG_BUFFER = 1000  # You can adjust this if needed

# Define base directory for static files
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

@app.get("/")
async def get_homepage():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


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

    try:
        asyncio.create_task(websocket_broadcast_loop())
        print("✅ Started websocket_broadcast_loop")
    except Exception as e:
        print(f"❌ Error starting websocket_broadcast_loop: {e}")

    try:
        asyncio.create_task(database_broadcast_loop())
        print("✅ Started database_broadcast_loop")
    except Exception as e:
        print(f"❌ Error starting database_broadcast_loop: {e}")


# Custom WebSocket logging handler
class WebSocketHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        log_queue.put(msg)

        # ➡️ Save in circular buffer
        if len(log_buffer) >= MAX_LOG_BUFFER:
            log_buffer.pop(0)  # Remove oldest
        log_buffer.append(msg)

def fetch_all_smart_nodes_as_list():
    """Fetch all smart nodes from the database as a list of dicts."""
    try:
        session = db.DATABASE_SESSION
        query = "SELECT uuid, ap_port, current_ap, current_swarm, last_update, virt_ip FROM ks_swarm.art;"
        rows = session.execute(query)
        return [dict(row._asdict()) for row in rows]
    except Exception as e:
        print(f"❌ Error fetching database: {e}")
        return []

@app.websocket("/ws/database")
async def websocket_database(websocket: WebSocket):
    await websocket.accept()
    active_database_websockets.add(websocket)
    print("✅ Browser connected for Database streaming:", websocket.client)

    try:
        while True:
            await asyncio.sleep(10)  # Just keep connection open
    except WebSocketDisconnect:
        active_database_websockets.remove(websocket)

async def database_broadcast_loop():
    print("🚀🚀 database_broadcast_loop() function entered")
    """Continuously check for database changes and broadcast updates."""
    last_snapshot = None  # Previous known database state

    while True:
        current_snapshot = fetch_all_smart_nodes_as_list()
        if current_snapshot != last_snapshot:
            print(" Database changed, broadcasting new snapshot...")
            last_snapshot = current_snapshot
            json_data = json.dumps(current_snapshot, default=str)

            to_remove = set()
            for ws in active_database_websockets:
                try:
                    await ws.send_text(json_data)
                except:
                    to_remove.add(ws)
            active_database_websockets.difference_update(to_remove)

        await asyncio.sleep(1)  # Check every 1 second


    def handle_client(client_socket, address):
        print(f"✅ TCP Client connected from {address}")

        try:
            while True:
                data = client_socket.recv(4096)
                if not data:
                    break
                log_message = data.decode('utf-8').strip()
                print(f"📝 [TCP Log] {log_message}")

                # ➡️ Push log to WebSocket broadcast system
                log_queue.put(log_message)  # ADD THIS LINE!

        except Exception as e:
            print(f"❌ TCP Client Error: {repr(e)}")
        finally:
            client_socket.close()
            print(f"❌ TCP Client disconnected: {address}")

