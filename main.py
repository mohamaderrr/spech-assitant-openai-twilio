import os
import asyncio
import json
import dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
import websockets

# Load environment variables
dotenv.load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", 5050))

if not OPENAI_API_KEY:
    raise ValueError("Missing OpenAI API key. Please set it in the .env file.")

app = FastAPI()

SYSTEM_MESSAGE = (
    "You are a helpful and bubbly AI assistant who loves to chat about anything the user is interested in. "
    "You have a penchant for dad jokes, owl jokes, and rickrolling – subtly. "
    "Always stay positive, but work in a joke when appropriate."
)
VOICE = "alloy"
SHOW_TIMING_MATH = False

@app.get("/")
async def root():
    return {"message": "Twilio Media Stream Server is running!"}

@app.post("/incoming-call")
async def incoming_call():
    twiml_response = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Response>"
        "<Say>Please wait while we connect your call to the A. I. voice assistant, powered by Twilio and OpenAI.</Say>"
        "<Pause length='1'/>"
        "<Say>O.K. you can start talking!</Say>"
        "<Connect>"
        "<Stream url='wss://your_server_address/media-stream' />"
        "</Connect>"
        "</Response>"
    )
    return Response(content=twiml_response, media_type="text/xml")

@app.websocket("/media-stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")
    
    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01",
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as openai_ws:
        try:
            session_update = {
                "type": "session.update",
                "session": {
                    "turn_detection": {"type": "server_vad"},
                    "input_audio_format": "g711_ulaw",
                    "output_audio_format": "g711_ulaw",
                    "voice": VOICE,
                    "instructions": SYSTEM_MESSAGE,
                    "modalities": ["text", "audio"],
                    "temperature": 0.8,
                }
            }
            await openai_ws.send(json.dumps(session_update))
            
            async def receive_from_client():
                while True:
                    try:
                        data = await websocket.receive_text()
                        await openai_ws.send(data)
                    except WebSocketDisconnect:
                        break
            
            async def receive_from_openai():
                while True:
                    try:
                        response = await openai_ws.recv()
                        await websocket.send_text(response)
                    except Exception:
                        break
            
            await asyncio.gather(receive_from_client(), receive_from_openai())
        except Exception as e:
            print("Error:", e)
        finally:
            await websocket.close()
            print("Client disconnected.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
