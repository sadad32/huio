from fastapi import FastAPI, Request, HTTPException
import httpx
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

# --- Validation at startup ---
if not TG_BOT_TOKEN:
    logger.error("FATAL: TG_BOT_TOKEN environment variable not set.")
if not TG_CHAT_ID:
    logger.error("FATAL: TG_CHAT_ID environment variable not set.")

app = FastAPI(title="TradingView Signal Bot", version="1.0.0")

# --- Telegram Sender Function ---
async def send_telegram_message(message: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        logger.error("Telegram Bot Token or Chat ID is not configured. Cannot send message.")
        return {"ok": False, "error": "Telegram bot not configured"}

    telegram_api_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(telegram_api_url, json=payload)
            response.raise_for_status()
            logger.info(f"Message sent to Telegram. Response: {response.json()}")
            return {"ok": True, "telegram_response": response.json()}
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred while sending message to Telegram: {e.response.status_code} - {e.response.text}")
        return {"ok": False, "error": "HTTP error sending to Telegram", "details": e.response.text}
    except httpx.RequestError as e:
        logger.error(f"Request error occurred while sending message to Telegram: {e}")
        return {"ok": False, "error": "Request error sending to Telegram", "details": str(e)}
    except Exception as e:
        logger.error(f"An unexpected error occurred in send_telegram_message: {e}")
        return {"ok": False, "error": "Unexpected error in Telegram sender", "details": str(e)}

# --- Webhook Endpoint ---
@app.post("/tv")
async def tradingview_webhook_receiver(request: Request):
    try:
        raw_data = await request.body()
        data_str = raw_data.decode('utf-8')
        logger.info(f"Received webhook data: {data_str}")
    except Exception as e:
        logger.error(f"Error reading or decoding request body: {e}")
        raise HTTPException(status_code=400, detail="Could not read or decode request body.")

    parts = data_str.strip().split("|")
    if not parts:
        logger.warning("Received empty or invalid data format.")
        raise HTTPException(status_code=400, detail="Received empty or invalid data format. Expected pipe-separated string.")

    tag = parts[0].upper()
    message_to_telegram = ""

    try:
        if tag == "START" and len(parts) == 8:
            _, trade_id, symbol, side, entry_price, sl_price, tp1_price, tp2_price = parts
            message_to_telegram = (
                f"🚀 *صفقة جديدة*\n"
                f"ID: `{trade_id}`\n"
                f"زوج: *{symbol}*\n"
                f"اتجاه: *{side.upper()}*\n"
                f"دخول: {entry_price}\n"
                f"SL: {sl_price}\n"
                f"TP1: {tp1_price}\n"
                f"TP2: {tp2_price}"
            )
        elif tag == "PROGRESS" and len(parts) == 3:
            _, trade_id, percentage = parts
            message_to_telegram = f"⏳ *{trade_id}* - تقدّم الصفقة: {percentage}%"
        elif tag == "TP1" and len(parts) == 2:
            _, trade_id = parts
            message_to_telegram = f"🎯 *{trade_id}* وصل إلى TP1 – تم نقل الستوب للتعادل."
        elif tag == "CLOSE" and len(parts) == 4:
            _, trade_id, result, r_value = parts
            emoji = "✅" if result.upper() == "WIN" else "❌"
            message_to_telegram = f"{emoji} *{trade_id}* أُغلقت الصفقة: {result.upper()}  |  R = {r_value}"
        else:
            logger.warning(f"Received unknown tag or incorrect number of parts: '{data_str}'")
            return {"ok": True, "status": "Unknown tag or format, message not processed by Telegram bot"}

    except IndexError:
        logger.error(f"Error parsing parts for tag '{tag}'. Data: '{data_str}'")
        raise HTTPException(status_code=400, detail=f"Invalid number of parameters for tag {tag}.")
    except Exception as e:
        logger.error(f"Unexpected error processing message parts for tag '{tag}': {e}. Data: '{data_str}'")
        raise HTTPException(status_code=500, detail=f"Server error processing message for tag {tag}.")

    if message_to_telegram:
        # Replace literal \n with
 for Telegram Markdown
        message_to_telegram = message_to_telegram.replace("\\n", "\n")
        tg_response = await send_telegram_message(message_to_telegram)
        if not tg_response.get("ok"):
            logger.error(f"Failed to send message to Telegram for trade ID {parts[1] if len(parts) > 1 else 'N/A'}")
            return {"ok": True, "status": "Webhook received, Telegram send failed", "telegram_error": tg_response.get("error")}
        return {"ok": True, "status": "Webhook received and processed by Telegram bot"}
    else:
        return {"ok": True, "status": "Message not applicable for Telegram"}

@app.get("/")
async def root():
    return {"message": "TradingView Signal Bot is running. POST to /tv for alerts."}

# To run: uvicorn signal_bot:app --reload --port 8000
# Ensure TG_BOT_TOKEN and TG_CHAT_ID are set as environment variables.
