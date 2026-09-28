import os
import base64
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from ai_engine import get_text_reply, transcribe_audio, get_image_reply
from datetime import datetime

load_dotenv(dotenv_path="../.env")

app = FastAPI()

# Enable CORS for Frontend UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = "../temp_downloads"

# Global System State
state = {
    "status": "DISCONNECTED",
    "qr_code": "",
    "logs": []
}

@app.get("/")
@app.get("/dashboard")
def get_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"message": "dashboard.html not found"}

@app.get("/api/status")
def get_status():
    return {
        "status": state["status"],
        "qr_code": state["qr_code"],
        "logs": state["logs"]
    }

@app.delete("/api/logs/{log_id}")
@app.post("/api/logs/delete/{log_id}")
def delete_log(log_id: int):
    state["logs"] = [log for log in state["logs"] if log.get("id") != log_id]
    return {"status": "ok", "message": f"Log {log_id} deleted", "logs": state["logs"]}

@app.delete("/api/logs")
@app.post("/api/logs/clear")
def clear_all_logs():
    state["logs"] = []
    return {"status": "ok", "message": "All logs cleared", "logs": []}

@app.post("/api/update-status")
async def update_status(request: Request):
    data = await request.json()
    state["status"] = data.get("status", state["status"])
    state["qr_code"] = data.get("qr_code", "")
    return {"status": "ok"}

@app.post("/api/test-chat")
async def test_chat(request: Request):
    data = await request.json()
    user_text = data.get("message", "").strip()
    sender = data.get("sender", "You (Test User)")
    
    if not user_text:
        return {"error": "Message is empty"}
        
    try:
        reply = get_text_reply(user_text)
    except Exception as e:
        reply = f"Error generating reply: {str(e)}"

    log_entry = {
        "id": len(state["logs"]) + 1,
        "sender": sender,
        "time": datetime.now().strftime("%I:%M %p"),
        "type": "text (test)",
        "incoming": user_text,
        "reply": reply
    }
    state["logs"].insert(0, log_entry)
    
    return {
        "reply": reply,
        "time": log_entry["time"],
        "sender": sender
    }

@app.post("/whatsapp-webhook")
async def whatsapp_webhook(request: Request):
    data = await request.json()
    sender = data.get("sender", "Unknown")
    msg_type = data.get("type")
    user_text = data.get("text", "")
    media_b64 = data.get("mediaB64", None)

    reply = ""

    try:
        if msg_type == "audio" and media_b64:
            file_path = os.path.join(TEMP_DIR, "voice.ogg")
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(media_b64))
            
            user_text = transcribe_audio(file_path)
            reply = get_text_reply(user_text)

            if os.path.exists(file_path):
                os.remove(file_path)

        elif msg_type == "image" and media_b64:
            file_path = os.path.join(TEMP_DIR, "image.jpg")
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(media_b64))
            
            reply = get_image_reply(file_path, caption=user_text)

            if os.path.exists(file_path):
                os.remove(file_path)

        else:
            reply = get_text_reply(user_text)

        # Log entry for Dashboard
        log_entry = {
            "id": len(state["logs"]) + 1,
            "sender": sender,
            "time": datetime.now().strftime("%I:%M %p"),
            "type": msg_type,
            "incoming": user_text if user_text else "[Media Sent]",
            "reply": reply
        }
        state["logs"].insert(0, log_entry)

    except Exception as e:
        print(f"Error Processing Message: {e}")
        reply = "Koinmasla aagaya hai, dobara try karein."

    return {"reply": reply}