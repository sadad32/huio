import logging
from telegram import Update, Bot # Bot needed for error handler context
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# --- Logging Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration Variables ---
# الرجاء إدخال توكن البوت الخاص بك هنا (Please enter your Bot Token here)
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
# الرجاء إدخال رقم شات آي دي الخاص بك هنا لاستقبال الرسائل أو الإشعارات (Please enter your Chat ID here to receive messages or notifications)
CHAT_ID = "YOUR_TELEGRAM_CHAT_ID_HERE"


# --- Command Handlers ---
def start(update: Update, context: CallbackContext) -> None:
    """Sends a welcome message when the /start command is issued."""
    # رسالة ترحيب باللغة العربية
    welcome_message = "مرحباً! أنا بوت مساعد التداول الخاص بك. كيف يمكنني المساعدة اليوم؟"
    update.message.reply_text(welcome_message)
    logger.info(f"User {update.effective_user.id} started the bot.")


# --- Message Handlers ---
def echo(update: Update, context: CallbackContext) -> None:
    """Echoes the user's message, prefixed with an Arabic phrase."""
    # يرد على رسالة المستخدم بإعادة إرسالها مع عبارة باللغة العربية
    user_message = update.message.text
    reply_message = f"لقد أرسلت: {user_message}"
    update.message.reply_text(reply_message)
    logger.info(f"Echoed message from user {update.effective_user.id}: {user_message}")


# --- Error Handler ---
def error_handler(update: object, context: CallbackContext) -> None:
    """Log Errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    # Optionally send a message to the CHAT_ID if an error occurs and CHAT_ID is configured
    if CHAT_ID and CHAT_ID != "YOUR_TELEGRAM_CHAT_ID_HERE": # Check if CHAT_ID is valid and configured
        try:
            # Ensure context.bot is available. For some errors, it might not be.
            if hasattr(context, 'bot') and isinstance(context.bot, Bot):
                 context.bot.send_message(chat_id=CHAT_ID, text="حدث خطأ ما في البوت.") # An error occurred in the bot.
            else:
                logger.warning("context.bot is not available or not a Bot instance in error_handler for sending message.")
        except Exception as e:
            logger.error(f"Failed to send error notification to CHAT_ID: {e}")


# --- Main Function ---
def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("Bot token is not configured. Please set BOT_TOKEN in the script.")
        return

    updater = Updater(BOT_TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Register command handlers
    dispatcher.add_handler(CommandHandler("start", start))

    # Register message handlers
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    # Register the error handler
    dispatcher.add_error_handler(error_handler)

    # Start the Bot
    logger.info("Starting bot polling...")
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()
    logger.info("Bot polling stopped.")


if __name__ == '__main__':
    main()
