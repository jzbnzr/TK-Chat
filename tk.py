from fastapi import FastAPI, WebSocket, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sqlite3
import json
from datetime import datetime
import base64
import os
from typing import List, Dict
import asyncio

app = FastAPI()

# Ensure static directory exists for storing images
if not os.path.exists("static"):
    os.makedirs("static")

# Mount static files directory to serve images
app.mount("/static", StaticFiles(directory="static"), name="static")


# Configure CORS to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tk-chat-g1l6.onrender.com/", "*"],  # Replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT,
                  content TEXT,
                  content_type TEXT,
                  timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY,
                  avatar TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Ensure static directory exists for storing images
if not os.path.exists("static"):
    os.makedirs("static")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[username] = websocket

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

manager = ConnectionManager()

# HTML for the chat interface
html = "index.html"


@app.get("/")
async def get():
   with open("static/index.html", "r") as file:
    html_content = file.read()
    return HTMLResponse(content=html_content)

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(websocket, username)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            # Save message to database
            conn = sqlite3.connect("chat.db")
            c = conn.cursor()
            c.execute("INSERT INTO messages (username, content, content_type, timestamp) VALUES (?, ?, ?, ?)",
                      (message["username"], message["content"], message["content_type"], message["timestamp"]))
            conn.commit()
            conn.close()
            # Broadcast message
            await manager.broadcast(message)
    except Exception:
        manager.disconnect(username)

@app.post("/upload_avatar")
async def upload_avatar(username: str, avatar: UploadFile = File(...)):
    content = await avatar.read()
    avatar_b64 = base64.b64encode(content).decode("utf-8")
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (username, avatar) VALUES (?, ?)", (username, avatar_b64))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/upload_image")
async def upload_image(username: str, file: UploadFile = File(...)):
    try:
        # Ensure static directory exists
        os.makedirs("static", exist_ok=True)
        
        # Read file content
        content = await file.read()
        
        # Generate filename
        file_extension = file.filename.split(".")[-1]
        filename = f"static/{username}_{datetime.now().isoformat()}.{file_extension}"
        
        # Write file
        with open(filename, "wb") as f:
            f.write(content)
        
        return {"image_url": f"/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.get("/messages")
async def get_messages():
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute("SELECT username, content, content_type, timestamp FROM messages ORDER BY timestamp")
    messages = [{"username": row[0], "content": row[1], "content_type": row[2], "timestamp": row[3]} for row in c.fetchall()]
    conn.close()
    return messages

@app.get("/get_avatar/{username}")
async def get_avatar(username: str):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute("SELECT avatar FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return {"avatar": result[0] if result else None}

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=10000)
