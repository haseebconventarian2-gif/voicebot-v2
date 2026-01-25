"""
FastAPI Backend for Bank Islami WhatsApp & ACS Bot
Features:
- Text input -> text reply with RAG context from Azure AI Search
- Audio (voice message) input -> transcription -> text reply -> TTS audio
- Unified /message endpoint for both types of communication
- GPT-4o multimodal support with function calling
"""

import asyncio
import json
import os

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
# from azure.communication.messages import NotificationMessagesClient

from .azure import (
    audio_content_type,
    generate_text,
    synthesize_speech,
    transcribe_audio,
)
from .ai_search import build_rag_context, search_tool
from .whatsapp import (
    debug_access_token,
    download_media,
    get_audio,
    parse_message,
    push_text,
    reply_audio,
    reply_text,
)
from .ui import UI_HTML
from dotenv import load_dotenv

load_dotenv()

# _acs_client = NotificationMessagesClient.from_connection_string(
#     os.environ["ACS_CONNECTION_STRING"]
# )


# async def send_text(to_e164: str, text: str) -> None:
#     """Send text message via Azure Communication Services."""
#     body = {
#         "channelRegistrationId": os.environ["ACS_CHANNEL_REGISTRATION_ID"],
#         "to": [to_e164],
#         "kind": "text",
#         "content": text,
#     }
#     resp = _acs_client.send(body=body)
#     print("ACS SEND RESPONSE:", resp)


def _load_voice_config() -> dict:
    """Load voice configuration from JSON file."""
    path = os.getenv("VOICE_CONFIG_PATH", "bankislami_voice_config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_app() -> FastAPI:
    app = FastAPI(title="Bank Islami AI Bot - Azure OpenAI + Search")
    
    # Load configuration
    try:
        voice_config = _load_voice_config()
        system_prompt = voice_config.get("system_prompt", {}).get("content")
        if not system_prompt:
            system_prompt = (
                "You are a helpful Bank Islami customer service assistant. "
                "Provide accurate information about banking products and services. "
                "Keep replies concise and helpful. Reply in the same language as the user."
            )
    except Exception as e:
        print(f"Warning: Could not load voice config: {e}")
        system_prompt = (
            "You are a helpful Bank Islami customer service assistant. "
            "Provide accurate information about banking products and services. "
            "Keep replies concise and helpful. Reply in the same language as the user."
        )

    async def process_query(user_text: str) -> str:
        """
        Process user query with RAG context from Azure AI Search.
        
        Args:
            user_text: User's message or transcribed text
            
        Returns:
            Response text from GPT-4o with RAG context
        """
        if not user_text or not user_text.strip():
            return "Please provide a message or question."
        
        # Handle greetings
        normalized = user_text.strip().lower()
        if normalized in {"hi", "hello", "hey", "salam", "assalamualaikum", "asalamualaikum"}:
            return "Assalam-o-Alaikum! Welcome to Bank Islami. How can I help you today?"
        
        # Build RAG context from Azure AI Search
        rag_context = await build_rag_context(user_text)
        if not rag_context:
            return "Please ask questions related to Bank Islami. Bank Islami se mutalaq sawal pouchain"
        
        # Generate response using GPT-4o with RAG context
        try:
            rag_system_prompt = (
                f"{system_prompt}\n\n"
                "Use ONLY the context provided. If the answer is not in the context, "
                "reply with: Please ask questions related to Bank Islami. Bank Islami se mutalaq sawal pouchain"
            )
            response = await generate_text(
                user_prompt=(
                    f"Question: {user_text}\n\n"
                    f"Context:\n{rag_context}"
                ),
                system_prompt=rag_system_prompt,
                use_tools=False
            )
            
            if response is None:
                # Function was called, use fallback
                response = "I need to search our knowledge base for the most current information."
            
            return response or "Sorry, I could not generate a response."
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I apologize, there was an issue processing your request. Please try again."

    # ==================== ENDPOINTS ====================
    
    @app.get("/")
    def ui() -> Response:
        """Serve the web UI."""
        return Response(content=UI_HTML, media_type="text/html")

    @app.get("/health")
    def health() -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"ok": True, "version": "2.0", "rag": "Azure AI Search"})

    # ==================== UNIFIED MESSAGE ENDPOINT ====================
    
    @app.post("/message")
    async def unified_message(
        text: str | None = Query(default=None),
        file: UploadFile | None = File(default=None)
    ) -> JSONResponse:
        """
        Unified endpoint for both text and voice message interaction.
        
        Query Parameters:
            text: Text message (optional)
            file: Audio file (multipart form, optional)
            
        Returns:
            JSON response with text and/or audio reply
        """
        message_text = None
        
        # Handle text input
        if text:
            message_text = str(text).strip()
        
        # Handle audio input
        if file:
            try:
                audio_bytes = await file.read()
                if audio_bytes:
                    message_text = await transcribe_audio(
                        audio_bytes, 
                        file.filename or "audio", 
                        file.content_type
                    )
                    print(f"Transcribed audio: {message_text}")
            except Exception as e:
                print(f"Audio transcription error: {e}")
                return JSONResponse(
                    {"error": "Failed to process audio", "details": str(e)},
                    status_code=400
                )
        
        # Validate we have some input
        if not message_text:
            return JSONResponse(
                {"error": "Please provide either text or audio"},
                status_code=400
            )
        
        # Process the query
        try:
            response_text = await process_query(message_text)
        except Exception as e:
            print(f"Query processing error: {e}")
            return JSONResponse(
                {"error": "Failed to process query", "details": str(e)},
                status_code=500
            )
        
        # Generate audio response
        try:
            audio_response = await synthesize_speech(response_text)
        except Exception as e:
            print(f"TTS error: {e}")
            # Return text-only if TTS fails
            return JSONResponse({
                "text": response_text,
                "warning": "Audio generation failed"
            })
        
        return JSONResponse({
            "text": response_text,
            "audio": {
                "format": audio_content_type(),
                "size_bytes": len(audio_response)
            }
        })
    
    # ==================== LEGACY ENDPOINTS ====================
    
    @app.post("/text")
    async def text_reply(payload: dict) -> JSONResponse:
        """Legacy text-only endpoint."""
        user_text = str(payload.get("text") or "").strip()
        if not user_text:
            raise HTTPException(status_code=400, detail="Missing text")
        answer = await process_query(user_text)
        return JSONResponse({"text": answer})

    @app.post("/audio")
    async def audio_reply(file: UploadFile = File(...)) -> Response:
        """Legacy audio endpoint."""
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Missing audio file")

        transcript = await transcribe_audio(audio_bytes, file.filename or "", file.content_type)
        answer = await process_query(transcript)
        audio_out = await synthesize_speech(answer)
        return Response(content=audio_out, media_type=audio_content_type())

    @app.get("/tts")
    async def tts(text: str = Query(min_length=1)) -> Response:
        """Text-to-speech endpoint."""
        audio_out = await synthesize_speech(text)
        return Response(content=audio_out, media_type=audio_content_type())

    @app.get("/media/{media_id}")
    def media(media_id: str) -> Response:
        """Retrieve cached audio media."""
        item = get_audio(media_id)
        if not item:
            raise HTTPException(status_code=404, detail="Not found")
        return Response(content=item["buffer"], media_type=item["content_type"])

    # ==================== WHATSAPP WEBHOOK ====================
    
    @app.get("/webhook")
    def webhook_verify(
        hub_mode: str | None = Query(default=None, alias="hub.mode"),
        hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
        hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    ) -> Response:
        """WhatsApp webhook verification."""
        verify_token = os.getenv("VERIFY_TOKEN", "")
        if hub_mode == "subscribe" and hub_verify_token == verify_token and hub_challenge:
            return Response(content=hub_challenge, media_type="text/plain")
        return Response(status_code=403, content="Forbidden", media_type="text/plain")

    @app.post("/webhook")
    async def webhook_events(request: Request) -> JSONResponse:
        """
        WhatsApp webhook for receiving messages (text and voice).
        Handles both text messages and voice messages (audio).
        """
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"ok": True})

        print("Webhook payload received")

        msg = parse_message(payload)
        if not msg:
            return JSONResponse({"ok": True})

        async def handle_message() -> None:
            """Handle incoming message asynchronously."""
            try:
                recipient = os.getenv("RECIPIENT_WAID") or msg["from"]
                
                if msg["type"] == "text":
                    # Handle text message - respond with text only
                    answer = await process_query(msg["text"])
                    await reply_text(recipient, answer)
                    return

                if msg["type"] == "audio":
                    # Handle voice message - respond with voice only
                    audio_bytes = await download_media(msg["media_id"])
                    transcript = await transcribe_audio(
                        audio_bytes, 
                        "audio", 
                        msg.get("media_type") or None
                    )
                    print(f"Voice message transcribed: {transcript}")
                    
                    answer = await process_query(transcript)
                    
                    # Send audio reply only
                    audio_out = await synthesize_speech(answer)
                    await reply_audio(recipient, audio_out, audio_content_type())
                    return
            except Exception as exc:
                print(f"Webhook handler error: {exc}")

        asyncio.create_task(handle_message())
        return JSONResponse({"ok": True})

    # ==================== WHATSAPP UTILITIES ====================
    
    @app.get("/whatsapp/diagnose")
    async def whatsapp_diagnose(check_token: bool = False) -> JSONResponse:
        """Diagnose WhatsApp configuration."""
        report = {
            "has_access_token": bool(os.getenv("ACCESS_TOKEN")),
            "has_phone_number_id": bool(os.getenv("PHONE_NUMBER_ID")),
            "has_verify_token": bool(os.getenv("VERIFY_TOKEN")),
            "has_public_base_url": bool(os.getenv("PUBLIC_BASE_URL")),
            "has_app_id": bool(os.getenv("APP_ID")),
            "has_app_secret": bool(os.getenv("APP_SECRET")),
            "has_recipient_waid": bool(os.getenv("RECIPIENT_WAID")),
            "version": os.getenv("VERSION") or os.getenv("META_API_VERSION") or "v20.0",
        }
        if check_token:
            try:
                report["token_debug"] = await debug_access_token()
            except Exception as exc:
                report["token_debug_error"] = str(exc)
        return JSONResponse(report)

    @app.post("/whatsapp/push")
    async def whatsapp_push(payload: dict) -> JSONResponse:
        """Push a text message to WhatsApp."""
        text = str(payload.get("text") or "").strip()
        to_number = str(payload.get("to") or "").strip() or None
        if not text:
            raise HTTPException(status_code=400, detail="Missing text")
        await push_text(text, to_number)
        return JSONResponse({"ok": True})

    # ==================== ACS (AZURE COMMUNICATION SERVICES) ====================
#     
#     @app.post("/acs/events")
#     async def acs_events(request: Request) -> Response:
#         """
#         Azure Communication Services Event Grid webhook.
#         Handles both text and voice messages from ACS.
#         """
#         eventgrid_secret = (os.getenv("EVENTGRID_SECRET") or "").strip()
#         if eventgrid_secret:
#             header_secret = (request.headers.get("x-eventgrid-secret") or "").strip()
#             if header_secret != eventgrid_secret:
#                 return Response(status_code=401, content="Unauthorized", media_type="text/plain")
# 
#         try:
#             payload = await request.json()
#         except Exception:
#             print("ACS Event Grid payload: <invalid json>")
#             return JSONResponse({"ok": True})
# 
#         if isinstance(payload, dict):
#             events = [payload]
#         elif isinstance(payload, list):
#             events = payload
#         else:
#             events = []
# 
        # Handle validation events
#         for event in events:
#             event_type = event.get("eventType")
#             if event_type == "Microsoft.EventGrid.SubscriptionValidationEvent":
#                 validation_code = event.get("data", {}).get("validationCode")
#                 return JSONResponse({"validationResponse": validation_code})
# 
        # Handle message events
#         for event in events:
#             event_type = event.get("eventType")
#             if event_type == "Microsoft.Communication.AdvancedMessageReceived":
#                 data = event.get("data", {})
#                 message = data.get("message", {})
#                 sender = (
#                     data.get("from")
#                     or data.get("fromPhoneNumber")
#                     or data.get("sender")
#                     or message.get("from")
#                 )
#                 message_id = data.get("messageId") or message.get("id")
#                 content = data.get("content") or message.get("content") or {}
#                 
#                 if isinstance(content, dict):
#                     text = content.get("text") or data.get("text")
#                 else:
#                     text = str(content) if content is not None else data.get("text")
#                 
#                 print(f"ACS message received from {sender}: {text}")
#                 
                # Handle debug audio path
#                 audio_path = data.get("debugAudioPath")
#                 if audio_path and os.path.exists(audio_path):
#                     try:
#                         with open(audio_path, "rb") as f:
#                             audio_bytes = f.read()
#                         transcript = await transcribe_audio(audio_bytes, audio_path, None)
#                         print(f"Debug audio transcribed: {transcript}")
#                         text = transcript
#                     except Exception as e:
#                         print(f"Debug audio processing error: {e}")
#                 
                # Process message
#                 answer = await process_query(text or "")
#                 if sender:
#                     try:
#                         await send_text(sender, answer)
#                         print(f"ACS message sent to {sender}")
#                     except Exception as e:
#                         print(f"ACS send failed: {e}")
#                         
#             elif event_type == "Microsoft.Communication.AdvancedMessageDeliveryStatusUpdated":
#                 data = event.get("data", {})
#                 print(f"ACS delivery status: {data.get('status')}")
# 
#         return JSONResponse({"ok": True})
# 
#     @app.post("/acs/test-send")
#     async def acs_test_send() -> JSONResponse:
#         """Test sending a message via ACS."""
#         test_number = "+923335437234"
#         test_message = "ACS test message ??? If you see this, sending works."
# 
#         try:
#             await send_text(test_number, test_message)
#             return JSONResponse({"ok": True, "sent_to": test_number})
#         except Exception as e:
#             return JSONResponse({"ok": False, "error": repr(e)})
# 
    return app
