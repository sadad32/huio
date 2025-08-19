import json
import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio

# --- Configuration and Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def load_config():
    """Loads configuration from config.json."""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("config.json not found. Please create it.")
        return None
    except json.JSONDecodeError:
        logger.error("Error decoding config.json.")
        return None

def load_database():
    """Loads the mock database from database.json."""
    try:
        with open('database.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("database.json not found.")
        return None
    except json.JSONDecodeError:
        logger.error("Error decoding database.json.")
        return None

def format_recommendation(rec):
    """Formats a recommendation object into a user-friendly string."""
    header_icon = "📈" if rec['type'] == 'BUY' else "📉"
    signal_type = "شراء" if rec['type'] == 'BUY' else "بيع"

    strategies_text = ""
    for name, confidence in rec['strategies'].items():
        strategies_text += f"- {name} تدعم بنسبة {confidence}%\n"

    message = (
        f"{header_icon} *توصية جديدة على {rec['asset']}*\n\n"
        f"📌 *نوع الصفقة:* {signal_type} ({rec['type']})\n"
        f"🎯 *منطقة الدخول:* `{rec['entry_zone']}`\n"
        f"🎯 *الهدف الأول:* `{rec['target1']}` (مضمون بنسبة {rec['target1_confidence']}%)\n"
        f"🎯 *الهدف الثاني:* `{rec['target2']}` (مضمون بنسبة {rec['target2_confidence']}%)\n"
        f"🛑 *وقف الخسارة:* `{rec['stop_loss']}`\n\n"
        f"📊 *الاستراتيجية:*\n{strategies_text}\n"
        f"✅ *نسبة نجاح الصفقة المتوقعة:* {rec['overall_confidence']}%\n\n"
        f"🔍 *ملاحظة:* {rec['note']}"
    )
    return message

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the /start command is issued."""
    welcome_message = (
        "أهلاً بك في بوت توصيات التداول.\n"
        "استخدم الأوامر التالية للحصول على المعلومات:\n"
        "/last - لعرض آخر توصية.\n"
        "/stats - لعرض إحصائيات الأداء.\n"
        "/strategy - لشرح الاستراتيجيات المعتمدة."
    )
    await update.message.reply_text(welcome_message)

async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the last active recommendation."""
    db = load_database()
    if not db or not db.get('recommendations'):
        await update.message.reply_text("لا توجد توصيات متاحة حالياً.")
        return

    last_rec = db['recommendations'][-1] # Get the most recent one
    message = format_recommendation(last_rec)
    await update.message.reply_text(message, parse_mode='Markdown')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Calculates and sends performance statistics."""
    db = load_database()
    if not db or not db.get('performance_history'):
        await update.message.reply_text("لا توجد بيانات أداء متاحة حالياً.")
        return

    history = db['performance_history']
    total_trades = len(history)
    profitable_trades = sum(1 for trade in history if trade['result'] == 'profit')
    loss_trades = total_trades - profitable_trades
    win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0

    message = (
        f"*📊 إحصائيات الأداء:*\n\n"
        f"- إجمالي الصفقات: {total_trades}\n"
        f"- الصفقات الرابحة: {profitable_trades}\n"
        f"- الصفقات الخاسرة: {loss_trades}\n"
        f"- نسبة النجاح: {win_rate:.2f}%"
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provides a brief explanation of the strategies."""
    # This can be expanded with more details as requested
    strategy_info = (
        "*الاستراتيجيات المعتمدة:*\n\n"
        "1. *SMC (Smart Money Concept):* نتبع حركة صناع السوق بتحديد مناطق العرض والطلب.\n\n"
        "2. *Insider Traders:* نحلل بيانات كبار المتداولين لمعرفة توجهاتهم.\n\n"
        "3. *ICT (Inner Circle Trader):* نستخدم نماذج متقدمة مثل فجوات القيمة العادلة (FVG) للدخول الدقيق."
    )
    await update.message.reply_text(strategy_info, parse_mode='Markdown')

# --- Main Function to Run the Bot ---

def main():
    """Start the bot."""
    config = load_config()
    if not config:
        return

    TOKEN = config.get("telegram_token")
    if not TOKEN:
        logger.error("Telegram token not found in config.json")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("last", last))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("strategy", strategy))

    logger.info("Bot is starting...")
    # Run the bot until the user presses Ctrl-C
    # The script is intended to be run directly.
    # To run, use `python telegram_bot.py` in your terminal.
    application.run_polling()

if __name__ == '__main__':
    # Note: To run this bot, you would execute `python telegram_bot.py` from your terminal.
    # The code below is commented out to prevent execution in this environment.
    # main()

    # --- Example of sending a message directly ---
    # This shows how the main analysis script would call the bot.
    async def send_test_recommendation():
        config = load_config()
        if not config:
            return

        bot = Bot(token=config['telegram_token'])
        chat_id = config['telegram_chat_id']
        db = load_database()
        if not db:
            return

        # Get the first recommendation as a test
        test_rec = db['recommendations'][0]
        message = format_recommendation(test_rec)

        logger.info(f"Sending test message to chat_id: {chat_id}")
        try:
            await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
            logger.info("Test message sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    # To run the test send function:
    # asyncio.run(send_test_recommendation())
    print("telegram_bot.py created successfully. It contains the logic for the bot.")
    print("To run the bot, uncomment the 'main()' call at the end of the file and run 'python telegram_bot.py'.")
