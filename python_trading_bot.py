import MetaTrader5 as mt5
import time
import logging
import pandas as pd
import numpy as np
import threading
import datetime
import uuid
from telegram import Update, Bot as TelegramBot, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

# Import indicator calculation functions
import indicator_calculator as ic

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Configurations ---
STRATEGY_CONFIG = {
    "symbol": "EURUSD",
    "timeframe": mt5.TIMEFRAME_M1,
    "rsi_period": 14, "rsi_oversold": 30.0, "rsi_overbought": 70.0,
    "stoch_k_period": 14, "stoch_d_period": 3, "stoch_slowing": 3,
    "stoch_oversold": 20.0, "stoch_overbought": 80.0,
    "bb_period": 20, "bb_std_dev": 2.0,
    "pivot_buffer_pips": 5,
    "enable_volume_confirmation": True, "volume_lookback_period": 20, "volume_multiplier": 1.5,
    "enable_macd_confirmation": True, "macd_fast_ema": 12, "macd_slow_ema": 26, "macd_signal_ma": 9,
    "magic_number": 202403,
    "lot_sizing_strategy": "FIXED",
    "fixed_lot_size": 0.01,
    "equity_percentage_risk": 1.0,
    "sl_tp_mode": "ATR",
    "sl_pips": 15, "tp_pips": 30,
    "atr_period_sltp": 14,
    "atr_multiplier_sl": 2.0, "atr_multiplier_tp": 3.0,
    "allowed_slippage_points": 5,
    "enable_trailing_stop": True, "trailing_stop_trigger_pips": 20, "trailing_stop_step_pips": 10,
    "trade_comment": "PythonBot_0.1_Reversal",
    "reconnect_delay_on_loss": 30
}

TELEGRAM_CONFIG = {
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN_HERE",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID_HERE",
    "enabled": True
}

# --- Bot Control State ---
bot_control_state = {
    "auto_trade_enabled": True,
    "ea_active": True # Master switch for the EA's trading activity. True = Run, False = Pause
}

# Global dictionary for daily pivots, symbol info cache, and pending alerts
daily_pivots_global = {}
last_pivot_calc_day_str = ""
symbol_info_cache = {}
pending_trade_alerts = {}

mt5_connected = False
telegram_updater = None

# --- Telegram Bot Functions ---
def send_telegram_message(message_text: str, keyboard_markup=None, chat_id_to_send=None):
    global telegram_updater
    admin_chat_id = chat_id_to_send if chat_id_to_send else TELEGRAM_CONFIG.get("chat_id")
    if not telegram_updater or not telegram_updater.bot:
        logger.error("Telegram updater/bot not initialized. Cannot send message.")
        return False
    if not admin_chat_id or admin_chat_id == "YOUR_TELEGRAM_CHAT_ID_HERE":
        logger.warning("Admin CHAT_ID not configured in TELEGRAM_CONFIG. Cannot send message.")
        return False
    try:
        logger.debug(f"Sending Telegram message to {admin_chat_id}: {message_text[:100]}...")
        sent_message = telegram_updater.bot.send_message(
            chat_id=admin_chat_id, text=message_text,
            reply_markup=keyboard_markup, parse_mode=ParseMode.MARKDOWN
        )
        logger.debug(f"Message sent successfully to {admin_chat_id}. Message ID: {sent_message.message_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message to {admin_chat_id}: {e}", exc_info=True)
        return False

def format_trade_alert_message_and_keyboard(signal_details: dict, trade_id: str):
    s_info = get_symbol_info_cached(signal_details["symbol"])
    digits = s_info.digits if s_info else 5
    order_type_str = "شراء" if signal_details["order_type"] == mt5.ORDER_TYPE_BUY else "بيع"
    message = (
        f"🚨 *تنبيه بفرصة تداول!* 🚨\n\n"
        f"**الرمز:** `{signal_details['symbol']}`\n"
        f"**الاتجاه:** {order_type_str}\n"
        f"**السعر التقريبي للدخول:** `{signal_details['entry_price']:.{digits}f}`\n"
        f"**وقف الخسارة المقترح:** `{signal_details['sl_price']:.{digits}f}`\n"
        f"**جني الأرباح المقترح:** `{signal_details['tp_price']:.{digits}f}`\n\n"
        f"هل توافق على تنفيذ هذه الصفقة؟"
    )
    keyboard = [[
        InlineKeyboardButton("موافقة ✅", callback_data=f"approve_{trade_id}"),
        InlineKeyboardButton("رفض ❌", callback_data=f"reject_{trade_id}"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return message, reply_markup

def trade_alert_button_callback(update: Update, context: CallbackContext):
    global pending_trade_alerts, bot_control_state
    query = update.callback_query
    query.answer()
    action, trade_id = query.data.split("_", 1)
    user_who_clicked = query.from_user.first_name
    chat_id_of_alert = query.message.chat_id
    logger.info(f"Telegram: Received callback action '{action}' for trade_id '{trade_id}' from user {user_who_clicked}.")

    if trade_id not in pending_trade_alerts:
        logger.warning(f"Trade ID {trade_id} not found in pending_trade_alerts.")
        query.edit_message_text(text=query.message.text + f"\n\n⚠️ *هذا التنبيه لم يعد صالحاً أو تمت معالجته بالفعل.* (بواسطة {user_who_clicked})", parse_mode=ParseMode.MARKDOWN)
        return

    signal_details = pending_trade_alerts.pop(trade_id)

    if action == "approve":
        logger.info(f"User {user_who_clicked} approved trade {trade_id}. Details: {signal_details}")
        if bot_control_state["auto_trade_enabled"]:
             query.edit_message_text(text=query.message.text + f"\n\n⚠️ *تم تفعيل التداول التلقائي. لا يمكن تنفيذ الصفقة يدوياً الآن.* (بواسطة {user_who_clicked})", parse_mode=ParseMode.MARKDOWN)
             logger.warning(f"Trade {trade_id} approved, but auto_trade is now enabled. Manual execution skipped.")
             return
        if not bot_control_state["ea_active"]: # Check if EA itself is paused
             query.edit_message_text(text=query.message.text + f"\n\n⚠️ *الخبير متوقف حالياً (/stop_ea). لا يمكن تنفيذ الصفقة حتى يتم تفعيله (/start_ea).* (بواسطة {user_who_clicked})", parse_mode=ParseMode.MARKDOWN)
             logger.warning(f"Trade {trade_id} approved, but EA is paused. Manual execution skipped.")
             # Re-add to pending alerts or discard? For now, discard.
             return


        required_bars = max(STRATEGY_CONFIG["rsi_period"], STRATEGY_CONFIG["stoch_k_period"],
                            STRATEGY_CONFIG["bb_period"], STRATEGY_CONFIG["volume_lookback_period"],
                            STRATEGY_CONFIG["macd_slow_ema"], STRATEGY_CONFIG["atr_period_sltp"]) + 50
        current_market_data_df = get_historical_data(signal_details["symbol"], STRATEGY_CONFIG["timeframe"], count=required_bars)

        if current_market_data_df is not None and not current_market_data_df.empty and len(current_market_data_df) >= required_bars - 45:
            current_market_data_df_with_indicators = calculate_all_indicators(current_market_data_df.copy(), STRATEGY_CONFIG)
            execute_trade(
                signal_details["symbol"], signal_details["order_type"],
                STRATEGY_CONFIG, current_market_data_df_with_indicators
            )
            query.edit_message_text(text=query.message.text + f"\n\n✅ *تمت الموافقة على الصفقة وتم إرسال الأمر.* (بواسطة {user_who_clicked})", parse_mode=ParseMode.MARKDOWN)
        else:
            logger.error(f"Could not fetch fresh market data to execute approved trade {trade_id}.")
            query.edit_message_text(text=query.message.text + f"\n\n⚠️ *خطأ في جلب بيانات السوق لتنفيذ الصفقة.* (بواسطة {user_who_clicked})", parse_mode=ParseMode.MARKDOWN)
            send_telegram_message("⚠️ لم يتم تنفيذ الصفقة المعتمدة بسبب خطأ في بيانات السوق.", chat_id_to_send=chat_id_of_alert)
    elif action == "reject":
        logger.info(f"User {user_who_clicked} rejected trade {trade_id}. Details: {signal_details}")
        query.edit_message_text(text=query.message.text + f"\n\n❌ *تم رفض الصفقة.* (بواسطة {user_who_clicked})", parse_mode=ParseMode.MARKDOWN)
        send_telegram_message(f"تم رفض الصفقة المقترحة للرمز {signal_details['symbol']}.", chat_id_to_send=chat_id_of_alert)

def tg_start_command(update: Update, context: CallbackContext):
    user_name = update.effective_user.first_name
    welcome_message = f"مرحباً {user_name}! أنا بوت مساعد التداول الخاص بك. الأوامر الأساسية قيد الإنشاء."
    update.message.reply_text(welcome_message)
    logger.info(f"Telegram: /start command executed by user {user_name} (ID: {update.effective_user.id})")

def tg_echo_handler(update: Update, context: CallbackContext):
    user_message = update.message.text
    reply_message = f"لقد أرسلت: \"{user_message}\" (هذه وظيفة صدى للرسائل للاختبار)"
    update.message.reply_text(reply_message)
    logger.info(f"Telegram: Echoed message from user {update.effective_user.first_name}: {user_message}")

def tg_error_handler(update: object, context: CallbackContext):
    logger.error(f"Telegram Update {update} caused error {context.error}", exc_info=context.error)

def tg_status_command(update: Update, context: CallbackContext):
    global bot_control_state
    if not check_mt5_connection():
        update.message.reply_text("لا يمكن الاتصال بـ MetaTrader 5 حالياً. يرجى المحاولة مرة أخرى لاحقاً.")
        return
    symbol = STRATEGY_CONFIG["symbol"]
    magic = STRATEGY_CONFIG["magic_number"]
    acc_info = mt5.account_info()
    account_currency = acc_info.currency if acc_info else ""
    status_text = "--- حالة البوت ومتابعة الصفقات ---\n"
    status_text += f"🤖 **وضع التداول التلقائي:** {'مفعّل ✅' if bot_control_state['auto_trade_enabled'] else 'متوقف ❌ (إرسال تنبيهات فقط)'}\n"
    status_text += f"🏃 **نشاط الخبير (المعالجة):** {'نشط حالياً ✅' if bot_control_state['ea_active'] else 'متوقف 🛑'}\n"
    open_positions = mt5.positions_get(symbol=symbol, magic=magic)
    if open_positions is None: status_text += "⚠️ لم يتمكن من جلب الصفقات المفتوحة.\n"
    elif not open_positions: status_text += f"📊 **الربح/الخسارة للصفقات المفتوحة ({symbol}):** لا توجد صفقات مفتوحة حالياً لهذا الرمز بالرقم السحري المحدد.\n"
    else:
        total_pl = 0; num_positions = len(open_positions)
        status_text += f"📊 **الربح/الخسارة للصفقات المفتوحة ({symbol}):** يوجد {num_positions} صفقة/صفقات مفتوحة:\n"
        for pos in open_positions:
            total_pl += pos.profit; pos_type = "شراء" if pos.type == mt5.ORDER_TYPE_BUY else "بيع"
            status_text += (f"  - تذكرة {pos.ticket}: {pos_type} بحجم {pos.volume:.2f} "
                            f" بسعر فتح {pos.price_open:.5f}, ربح/خسارة: {pos.profit:.2f} {account_currency}\n")
        status_text += f"💰 **إجمالي الربح/الخسارة للصفقات المفتوحة:** {total_pl:.2f} {account_currency}\n"
    from_dt = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    to_dt = datetime.datetime.now()
    deals = mt5.history_deals_get(from_dt, to_dt)
    realized_pl_today = 0
    if deals is not None:
        for deal in deals:
            if deal.magic == magic and deal.symbol == symbol and deal.entry == mt5.DEAL_ENTRY_OUT:
                 realized_pl_today += deal.profit
        status_text += f"📈 **الربح/الخسارة المحققة اليوم ({symbol}):** {realized_pl_today:.2f} {account_currency}\n"
    else: status_text += "⚠️ لم يتمكن من جلب سجل الصفقات لحساب الربح المحقق اليوم.\n"
    update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"Telegram: /status command executed by {update.effective_user.first_name}")

def tg_enable_autotrade_command(update: Update, context: CallbackContext):
    global bot_control_state
    bot_control_state["auto_trade_enabled"] = True
    reply_message = "✅ تم تفعيل وضع التداول التلقائي. سيقوم البوت بتنفيذ الصفقات مباشرة."
    update.message.reply_text(reply_message)
    logger.info(f"Telegram: /enable_autotrade command executed by {update.effective_user.first_name}. Auto_trade set to True.")

def tg_disable_autotrade_command(update: Update, context: CallbackContext):
    global bot_control_state
    bot_control_state["auto_trade_enabled"] = False
    reply_message = "❌ تم إيقاف وضع التداول التلقائي. سيرسل البوت تنبيهات بالصفقات المقترحة للموافقة اليدوية."
    update.message.reply_text(reply_message)
    logger.info(f"Telegram: /disable_autotrade command executed by {update.effective_user.first_name}. Auto_trade set to False.")

def tg_start_ea_command(update: Update, context: CallbackContext):
    global bot_control_state
    if bot_control_state["ea_active"]:
        reply_message = "🟢 الخبير يعمل بالفعل ويقوم بمعالجة بيانات السوق."
    else:
        bot_control_state["ea_active"] = True
        reply_message = "✅ تم تفعيل الخبير. سيبدأ في معالجة بيانات السوق والبحث عن إشارات."
    update.message.reply_text(reply_message)
    logger.info(f"Telegram: /start_ea command executed by {update.effective_user.first_name}. ea_active set to True.")

def tg_stop_ea_command(update: Update, context: CallbackContext):
    global bot_control_state
    if not bot_control_state["ea_active"]:
        reply_message = "🔴 الخبير متوقف بالفعل عن معالجة البيانات."
    else:
        bot_control_state["ea_active"] = False
        reply_message = "🛑 تم إيقاف الخبير. سيتوقف عن معالجة بيانات السوق والبحث عن إشارات جديدة. (التحكم بالصفقات المفتوحة مثل الـ Trailing Stop قد يستمر إذا كان مفعلاً)."
    update.message.reply_text(reply_message)
    logger.info(f"Telegram: /stop_ea command executed by {update.effective_user.first_name}. ea_active set to False.")

def start_telegram_bot(config_tg: dict):
    global telegram_updater
    if not config_tg.get("enabled", False) or config_tg["bot_token"] == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or not config_tg["bot_token"]:
        logger.info("Telegram bot is disabled or token is not configured. Skipping Telegram bot start.")
        return None
    try:
        logger.info("Starting Telegram bot...")
        updater = Updater(token=config_tg["bot_token"], use_context=True)
        dispatcher = updater.dispatcher
        dispatcher.add_handler(CommandHandler("start", tg_start_command))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, tg_echo_handler))
        dispatcher.add_handler(CommandHandler("status", tg_status_command))
        dispatcher.add_handler(CommandHandler("enable_autotrade", tg_enable_autotrade_command))
        dispatcher.add_handler(CommandHandler("disable_autotrade", tg_disable_autotrade_command))
        dispatcher.add_handler(CommandHandler("start_ea", tg_start_ea_command))
        dispatcher.add_handler(CommandHandler("stop_ea", tg_stop_ea_command))
        dispatcher.add_handler(CallbackQueryHandler(trade_alert_button_callback))
        dispatcher.add_error_handler(tg_error_handler)
        bot_thread = threading.Thread(target=updater.start_polling, name="TelegramBotThread")
        bot_thread.daemon = True
        bot_thread.start()
        logger.info("Telegram bot polling started in a separate thread.")
        telegram_updater = updater
        return updater
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}", exc_info=True)
        return None

def stop_telegram_bot():
    global telegram_updater
    if telegram_updater:
        logger.info("Stopping Telegram bot...")
        try:
            telegram_updater.stop()
            telegram_updater = None
            logger.info("Telegram bot stopped.")
        except Exception as e:
            logger.error(f"Error while stopping Telegram bot: {e}", exc_info=True)

# --- MT5 Connection Functions --- (Keep existing)
def connect_to_mt5(retries=3, delay=5):
    global mt5_connected
    for i in range(retries):
        logger.info(f"Attempting to connect to MetaTrader 5 (Attempt {i+1}/{retries})...")
        if not mt5.initialize():
            logger.error(f"mt5.initialize() failed. Error code: {mt5.last_error()}")
            time.sleep(delay)
            continue
        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            logger.error(f"Failed to get terminal info after initialize. Error code: {mt5.last_error()}")
            mt5.shutdown()
            time.sleep(delay)
            continue
        account_info = mt5.account_info()
        if account_info is None:
            logger.error(f"Failed to get account info. Error code: {mt5.last_error()}")
            mt5.shutdown()
            time.sleep(delay)
            continue
        logger.info(f"Successfully connected to MetaTrader 5: Account {account_info.login} on {account_info.server}")
        logger.info(f"Terminal version: {terminal_info.build}, Path: {terminal_info.path}")
        mt5_connected = True
        return True
    logger.error(f"Failed to connect to MetaTrader 5 after {retries} attempts.")
    mt5_connected = False
    return False

def disconnect_from_mt5():
    global mt5_connected
    if mt5_connected:
        logger.info("Disconnecting from MetaTrader 5...")
        mt5.shutdown()
        logger.info("Successfully disconnected from MetaTrader 5.")
    else:
        logger.info("Already disconnected or failed to connect to MetaTrader 5. Shutdown not explicitly called.")
    mt5_connected = False

def check_mt5_connection():
    global mt5_connected
    if not mt5_connected:
         logger.warning("MT5 status is 'disconnected'. Attempting to reconnect.")
         return connect_to_mt5()
    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        logger.warning(f"MT5 connection lost (terminal_info is None). Error: {mt5.last_error()}. Attempting to reconnect.")
        mt5_connected = False
        return connect_to_mt5()
    account_info = mt5.account_info()
    if account_info is None:
       logger.warning(f"MT5 connection issue (account_info is None). Error: {mt5.last_error()}. Attempting to reconnect.")
       mt5_connected = False
       return connect_to_mt5()
    return True

# --- Symbol Info Helper --- (Keep existing)
def get_symbol_info_cached(symbol: str):
    global symbol_info_cache
    if symbol not in symbol_info_cache:
        if not check_mt5_connection():
            return None
        info = mt5.symbol_info(symbol)
        if not info:
            logger.error(f"Failed to get symbol_info for {symbol}. Error: {mt5.last_error()}")
            return None
        symbol_info_cache[symbol] = info
        logger.info(f"Cached symbol_info for {symbol}")
    return symbol_info_cache[symbol]

# --- Data Fetching and Indicator Calculation --- (Keep existing)
def get_historical_data(symbol: str, timeframe_mt5, count: int = 100, from_date=None, to_date=None):
    if not check_mt5_connection():
        logger.error("Cannot fetch data, MT5 not connected or connection check failed.")
        return pd.DataFrame()
    rates = None
    logger.debug(f"Fetching historical data for {symbol}, timeframe {timeframe_mt5}, count {count} or range {from_date}-{to_date}")
    if from_date is not None and to_date is not None:
        rates = mt5.copy_rates_range(symbol, timeframe_mt5, from_date, to_date)
    elif count > 0 :
        rates = mt5.copy_rates_from_pos(symbol, timeframe_mt5, 0, count)
    else:
        logger.error("Either count or from_date/to_date must be specified for get_historical_data.")
        return pd.DataFrame()
    if rates is None or len(rates) == 0:
        logger.warning(f"No data returned from MT5 for {symbol} with timeframe {timeframe_mt5}. Error: {mt5.last_error()}")
        return pd.DataFrame()
    rates_df = pd.DataFrame(rates)
    rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s')
    rates_df.set_index('time', inplace=True)
    rates_df.rename(columns={'tick_volume': 'volume', 'real_volume': 'volume_real'}, inplace=True, errors='ignore')
    if 'volume' not in rates_df.columns and 'volume_real' in rates_df.columns:
        rates_df.rename(columns={'volume_real': 'volume'}, inplace=True, errors='ignore')
    elif 'volume' not in rates_df.columns:
        logger.warning(f"No 'tick_volume' or 'real_volume' found for {symbol}. Volume confirmation might not work.")
        rates_df['volume'] = 0
    logger.debug(f"Fetched {len(rates_df)} bars for {symbol} timeframe {timeframe_mt5}")
    return rates_df

def calculate_all_indicators(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    logger.debug("Calculating all indicators...")
    df['rsi'] = ic.calculate_rsi(df, period=config["rsi_period"])
    df['stoch_k'], df['stoch_d'] = ic.calculate_stochastic(
        df, k_period=config["stoch_k_period"], d_period=config["stoch_d_period"], slowing=config["stoch_slowing"]
    )
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = ic.calculate_bollinger_bands(
        df, period=config["bb_period"], std_dev_multiplier=config["bb_std_dev"]
    )
    df['macd_line'], df['macd_signal'], _ = ic.calculate_macd(
        df, period_fast=config["macd_fast_ema"], period_slow=config["macd_slow_ema"], period_signal=config["macd_signal_ma"]
    )
    df['atr'] = ic.calculate_atr(df, period=config["atr_period_sltp"])
    logger.debug("Indicator calculation complete.")
    return df

def update_daily_pivots_if_needed(symbol: str, config: dict):
    global daily_pivots_global, last_pivot_calc_day_str
    today_str = pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d')
    if last_pivot_calc_day_str != today_str:
        logger.info(f"Calculating daily pivot points for {today_str} for symbol {symbol}...")
        if not check_mt5_connection():
            logger.error("Cannot calculate pivots, MT5 not connected.")
            return False if not daily_pivots_global else True
        yesterday_d1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 1)
        if yesterday_d1_rates is not None and len(yesterday_d1_rates) == 1:
            prev_day_series = pd.Series(yesterday_d1_rates[0])
            daily_pivots_global = ic.calculate_daily_pivot_points(prev_day_series)
            last_pivot_calc_day_str = today_str
            logger.info(f"Pivots for {today_str} (based on D1 bar {pd.to_datetime(prev_day_series['time'], unit='s')}): {daily_pivots_global}")
            return True
        else:
            logger.warning(f"Could not fetch yesterday's D1 bar data for Pivot Point calculation for {symbol}. Error: {mt5.last_error()}")
            if not daily_pivots_global:
                 logger.error("CRITICAL: No pivot points available and failed to calculate new ones.")
                 return False
            logger.info("Using previously calculated pivot points due to fetch failure.")
            return True
    return True

# --- Strategy Signal Checking --- (Keep existing)
def check_strategy_signals(df: pd.DataFrame, pivots: dict, config: dict, symbol: str) -> str:
    logger.debug(f"Checking signals for {symbol} on last completed bar...")
    min_bars_needed = max(config["rsi_period"], config["stoch_k_period"] + config["stoch_slowing"],
                          config["bb_period"], config["volume_lookback_period"],
                          config["macd_slow_ema"] + config["macd_signal_ma"], config["atr_period_sltp"]) + 2
    if df.empty or len(df) < min_bars_needed:
        logger.warning(f"Not enough data to check signals for {symbol}. Have {len(df)} bars, need ~{min_bars_needed}.")
        return "NONE"
    last_bar = df.iloc[-1]
    prev_bar = df.iloc[-2]
    rsi_oversold_cond = last_bar['rsi'] < config["rsi_oversold"]
    stoch_oversold_cond = (last_bar['stoch_k'] < config["stoch_oversold"] and
                           last_bar['stoch_d'] < config["stoch_oversold"] and
                           last_bar['stoch_k'] > last_bar['stoch_d'] and
                           prev_bar['stoch_k'] <= prev_bar['stoch_d'])
    bb_lower_touch_cond = last_bar['low'] <= last_bar['bb_lower']
    s_info = get_symbol_info_cached(symbol)
    point_value = s_info.point if s_info else 0.00001
    pivot_buffer_abs = config["pivot_buffer_pips"] * point_value
    pivot_support_cond = False
    if pivots:
        for p_level_name in ["PP", "S1", "S2", "S3"]:
            pivot_val = pivots.get(p_level_name)
            if pivot_val is not None and abs(last_bar['low'] - pivot_val) <= pivot_buffer_abs:
                pivot_support_cond = True
                logger.debug(f"Buy signal: Price {last_bar['low']} near support pivot {p_level_name} ({pivot_val}) for {symbol}")
                break
    core_buy_signal = (rsi_oversold_cond and stoch_oversold_cond and
                       bb_lower_touch_cond and pivot_support_cond)
    if core_buy_signal:
        logger.info(f"Core BUY Signal for {symbol} met. RSI={last_bar['rsi']:.2f}, StochK={last_bar['stoch_k']:.2f}, BB_Low_Touch={bb_lower_touch_cond}, Pivot_Support={pivot_support_cond}")
        if config["enable_volume_confirmation"]:
            if len(df) > config["volume_lookback_period"] + 1:
                avg_volume = df['volume'].iloc[-(config["volume_lookback_period"] + 2) : -2].mean()
                if last_bar['volume'] < avg_volume * config["volume_multiplier"]:
                    logger.info(f"Volume confirmation FAILED for BUY on {symbol}. Vol: {last_bar['volume']}, AvgVol: {avg_volume:.0f}")
                    return "NONE"
                logger.info(f"Volume confirmation PASSED for BUY on {symbol}. Vol: {last_bar['volume']}, AvgVol: {avg_volume:.0f}")
            else:
                logger.warning(f"Not enough data for volume confirmation lookback for BUY on {symbol}.")
                return "NONE"
        if config["enable_macd_confirmation"]:
            macd_bullish_cross = (last_bar['macd_line'] > last_bar['macd_signal'] and
                                  prev_bar['macd_line'] <= prev_bar['macd_signal'])
            if not macd_bullish_cross:
                logger.info(f"MACD confirmation FAILED for BUY on {symbol}. MACD={last_bar['macd_line']:.5f}, Signal={last_bar['macd_signal']:.5f}")
                return "NONE"
            logger.info(f"MACD confirmation PASSED for BUY on {symbol}.")
        return "BUY"
    rsi_overbought_cond = last_bar['rsi'] > config["rsi_overbought"]
    stoch_overbought_cond = (last_bar['stoch_k'] > config["stoch_overbought"] and
                             last_bar['stoch_d'] > config["stoch_overbought"] and
                             last_bar['stoch_k'] < last_bar['stoch_d'] and
                             prev_bar['stoch_k'] >= prev_bar['stoch_d'])
    bb_upper_touch_cond = last_bar['high'] >= last_bar['bb_upper']
    pivot_resistance_cond = False
    if pivots:
        for p_level_name in ["PP", "R1", "R2", "R3"]:
            pivot_val = pivots.get(p_level_name)
            if pivot_val is not None and abs(last_bar['high'] - pivot_val) <= pivot_buffer_abs:
                pivot_resistance_cond = True
                logger.debug(f"Sell signal: Price {last_bar['high']} near resistance pivot {p_level_name} ({pivot_val}) for {symbol}")
                break
    core_sell_signal = (rsi_overbought_cond and stoch_overbought_cond and
                        bb_upper_touch_cond and pivot_resistance_cond)
    if core_sell_signal:
        logger.info(f"Core SELL Signal for {symbol} met. RSI={last_bar['rsi']:.2f}, StochK={last_bar['stoch_k']:.2f}, BB_Up_Touch={bb_upper_touch_cond}, Pivot_Resist={pivot_resistance_cond}")
        if config["enable_volume_confirmation"]:
            if len(df) > config["volume_lookback_period"] + 1:
                avg_volume = df['volume'].iloc[-(config["volume_lookback_period"] + 2) : -2].mean()
                if last_bar['volume'] < avg_volume * config["volume_multiplier"]:
                    logger.info(f"Volume confirmation FAILED for SELL on {symbol}. Vol: {last_bar['volume']}, AvgVol: {avg_volume:.0f}")
                    return "NONE"
                logger.info(f"Volume confirmation PASSED for SELL on {symbol}. Vol: {last_bar['volume']}, AvgVol: {avg_volume:.0f}")
            else:
                logger.warning(f"Not enough data for volume confirmation lookback for SELL on {symbol}.")
                return "NONE"
        if config["enable_macd_confirmation"]:
            macd_bearish_cross = (last_bar['macd_line'] < last_bar['macd_signal'] and
                                  prev_bar['macd_line'] >= prev_bar['macd_signal'])
            if not macd_bearish_cross:
                logger.info(f"MACD confirmation FAILED for SELL on {symbol}. MACD={last_bar['macd_line']:.5f}, Signal={last_bar['macd_signal']:.5f}")
                return "NONE"
            logger.info(f"MACD confirmation PASSED for SELL on {symbol}.")
        return "SELL"
    return "NONE"

# --- Trade Execution and Position Management Modules --- (Keep existing)
def calculate_lot_size(config: dict, symbol: str, stop_loss_distance_price: float = None) -> float:
    logger.info(f"Calculating lot size for {symbol}...")
    lot_strategy = config.get("lot_sizing_strategy", "FIXED")
    s_info = get_symbol_info_cached(symbol)
    if not s_info: return 0.0
    lot = 0.0
    if lot_strategy == "FIXED":
        lot = config.get("fixed_lot_size", 0.01)
    elif lot_strategy == "PERCENT_EQUITY":
        if stop_loss_distance_price is None or stop_loss_distance_price <= 1e-9:
            logger.error(f"Stop loss distance in price must be provided and > 0 for PERCENT_EQUITY lot sizing for {symbol}.")
            return 0.0
        account_info = mt5.account_info()
        if not account_info:
            logger.error(f"Failed to get account info for lot calculation for {symbol}.")
            return 0.0
        equity = account_info.equity
        risk_percent = config.get("equity_percentage_risk", 1.0) / 100.0
        risk_amount_account_currency = equity * risk_percent
        conversion_rate = 1.0
        if s_info.currency_profit != account_info.currency:
             pair1 = s_info.currency_profit + account_info.currency
             pair2 = account_info.currency + s_info.currency_profit
             tick1 = mt5.symbol_info_tick(pair1)
             tick2 = mt5.symbol_info_tick(pair2)
             if tick1 and tick1.bid > 1e-9 : conversion_rate = tick1.bid
             elif tick2 and tick2.ask > 1e-9 : conversion_rate = 1.0 / tick2.ask
             else:
                  logger.error(f"Cannot determine conversion rate from {s_info.currency_profit} to {account_info.currency} for {symbol}.")
                  return 0.0
        current_tick = mt5.symbol_info_tick(symbol)
        if not current_tick:
            logger.error(f"Could not get current tick for {symbol} for order_calc_profit.")
            return 0.0
        sl_loss_for_one_lot_symbol_currency = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, symbol, 1.0,
                                                                  current_tick.ask,
                                                                  current_tick.ask - stop_loss_distance_price)
        if sl_loss_for_one_lot_symbol_currency is None:
            logger.error(f"order_calc_profit failed for {symbol}. Error: {mt5.last_error()}")
            return 0.0
        sl_loss_for_one_lot_account_currency = abs(sl_loss_for_one_lot_symbol_currency * conversion_rate)
        if sl_loss_for_one_lot_account_currency <= 1e-9:
            logger.error(f"Calculated SL loss for 1 lot is too small or zero ({sl_loss_for_one_lot_account_currency}) for {symbol}. Cannot determine lot size.")
            return 0.0
        lot = risk_amount_account_currency / sl_loss_for_one_lot_account_currency
        logger.info(f"Equity: {equity:.2f} {account_info.currency}, Risk%: {risk_percent*100:.2f}%, RiskAmt: {risk_amount_account_currency:.2f} {account_info.currency}, SL_Loss_1Lot: {sl_loss_for_one_lot_account_currency:.2f} {account_info.currency}, CalcLot: {lot:.4f} for {symbol}")
    else:
        logger.warning(f"Unknown lot sizing strategy: {lot_strategy} for {symbol}. Defaulting to min lot.")
        lot = s_info.volume_min if s_info else 0.01
    if s_info.volume_step == 0:
        logger.error(f"Volume step for {symbol} is zero, cannot normalize lot.")
        return 0.0
    lot = round(lot / s_info.volume_step) * s_info.volume_step
    volume_step_str = str(s_info.volume_step)
    if '.' in volume_step_str:
        decimal_places = len(volume_step_str.split('.')[1])
        lot = round(lot, decimal_places)
    else:
        lot = round(lot, 0)
    lot = max(s_info.volume_min, lot)
    lot = min(s_info.volume_max, lot)
    logger.info(f"Final Lot Size for {symbol}: {lot} (Min: {s_info.volume_min}, Max: {s_info.volume_max}, Step: {s_info.volume_step})")
    return lot if lot >= s_info.volume_min else 0.0

def calculate_sl_tp_prices(config: dict, symbol: str, order_type: int, entry_price: float, current_atr_value: float = None) -> dict:
    s_info = get_symbol_info_cached(symbol)
    if not s_info: return {"sl": 0.0, "tp": 0.0, "sl_dist_price": 0.0}
    point = s_info.point
    sl_distance_price, tp_distance_price = 0.0, 0.0
    if config["sl_tp_mode"] == "ATR":
        if current_atr_value is not None and current_atr_value > 1e-9:
            sl_distance_price = current_atr_value * config["atr_multiplier_sl"]
            tp_distance_price = current_atr_value * config["atr_multiplier_tp"]
            logger.info(f"ATR SL/TP distances for {symbol} (price units): SL_dist={sl_distance_price:.{s_info.digits}f}, TP_dist={tp_distance_price:.{s_info.digits}f} (ATR: {current_atr_value:.{s_info.digits}f})")
        else:
            logger.warning(f"ATR mode selected for SL/TP for {symbol}, but ATR value ({current_atr_value}) is invalid. SL/TP will not be set using ATR.")
    elif config["sl_tp_mode"] == "PIPS":
        sl_distance_price = config["sl_pips"] * point
        tp_distance_price = config["tp_pips"] * point
        logger.info(f"PIPS SL/TP distances for {symbol}: SL={config['sl_pips']} pips, TP={config['tp_pips']} pips")
    sl_price, tp_price = 0.0, 0.0
    if order_type == mt5.ORDER_TYPE_BUY:
        if sl_distance_price > 0: sl_price = entry_price - sl_distance_price
        if tp_distance_price > 0: tp_price = entry_price + tp_distance_price
    elif order_type == mt5.ORDER_TYPE_SELL:
        if sl_distance_price > 0: sl_price = entry_price + sl_distance_price
        if tp_distance_price > 0: tp_price = entry_price - tp_distance_price
    if sl_price != 0.0: sl_price = round(sl_price, s_info.digits)
    if tp_price != 0.0: tp_price = round(tp_price, s_info.digits)
    return {"sl": sl_price, "tp": tp_price, "sl_dist_price": sl_distance_price}

def execute_trade(symbol: str, order_type: int, config: dict, market_data_df: pd.DataFrame):
    logger.info(f"Attempting to execute {'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL'} trade for {symbol}")
    if not check_mt5_connection(): return
    s_info = get_symbol_info_cached(symbol)
    if not s_info: return
    open_positions = mt5.positions_get(symbol=symbol)
    if open_positions is not None:
        for pos in open_positions:
            if pos.magic == config["magic_number"]:
                logger.info(f"Position with magic number {config['magic_number']} already exists for {symbol} (Ticket: {pos.ticket}). Skipping new trade.")
                return
    else:
        logger.warning(f"Could not get open positions for {symbol}. Error: {mt5.last_error()}. Proceeding with trade attempt.")
    current_tick = mt5.symbol_info_tick(symbol)
    if not current_tick or current_tick.ask == 0.0 or current_tick.bid == 0.0 :
        logger.error(f"Could not get valid market tick for {symbol} to execute trade. Ask: {current_tick.ask if current_tick else 'N/A'}, Bid: {current_tick.bid if current_tick else 'N/A'}")
        return
    entry_price = current_tick.ask if order_type == mt5.ORDER_TYPE_BUY else current_tick.bid
    current_atr = market_data_df['atr'].iloc[-1] if 'atr' in market_data_df.columns and not market_data_df['atr'].empty else None
    sl_tp_calc_result = calculate_sl_tp_prices(config, symbol, order_type, entry_price, current_atr)
    sl_distance_for_lot_calc = sl_tp_calc_result["sl_dist_price"]
    if config["lot_sizing_strategy"] == "PERCENT_EQUITY" and sl_distance_for_lot_calc <= 1e-9 :
        logger.error(f"Stop loss distance is zero or negative ({sl_distance_for_lot_calc:.{s_info.digits}f}), cannot calculate PERCENT_EQUITY lot size for {symbol}.")
        return
    lot = calculate_lot_size(config, symbol, sl_distance_for_lot_calc if config["lot_sizing_strategy"] == "PERCENT_EQUITY" else None)
    if lot <= 1e-9 :
        logger.error(f"Calculated lot size is {lot:.4f} for {symbol}. Trade cannot be executed.")
        return
    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": lot, "type": order_type,
        "price": entry_price, "sl": sl_tp_calc_result["sl"], "tp": sl_tp_calc_result["tp"],
        "deviation": config["allowed_slippage_points"], "magic": config["magic_number"],
        "comment": config["trade_comment"], "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    if request["sl"] == 0.0: del request["sl"]
    if request["tp"] == 0.0: del request["tp"]
    logger.info(f"Sending trade request for {symbol}: {request}")
    result = mt5.order_send(request)
    if result is None:
        logger.error(f"order_send failed for {symbol}, returned None. Error: {mt5.last_error()}")
    elif result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"Order executed successfully for {symbol}. Ticket: {result.order}, Comment: {result.comment}")
    else:
        logger.error(f"Order execution failed for {symbol}. Retcode: {result.retcode} - {result.comment} (MT5 Error: {mt5.last_error()})")
        if hasattr(result, 'request_id') and result.request_id > 0:
             logger.error(f"Request ID was {result.request_id}, but cannot fetch request details directly via simple function.")
        elif hasattr(result, 'order') and result.order > 0:
             order_info_list = mt5.history_orders_get(ticket=result.order)
             if order_info_list and len(order_info_list) > 0: logger.error(f"Failed order details: {order_info_list[0]}")

def manage_open_positions(config: dict):
    if not config.get("enable_trailing_stop", False): return
    if not check_mt5_connection():
        logger.warning("MT5 not connected, cannot manage positions.")
        return
    symbol_to_manage = config.get("symbol", None)
    if not symbol_to_manage:
        logger.warning("Symbol not configured for position management.")
        return
    s_info = get_symbol_info_cached(symbol_to_manage)
    if not s_info:
        logger.warning(f"Could not get symbol info for {symbol_to_manage} in position management.")
        return
    point = s_info.point
    magic = config["magic_number"]
    trigger_distance_price = config["trailing_stop_trigger_pips"] * point
    step_distance_price = config["trailing_stop_step_pips"] * point
    if trigger_distance_price <= 0 or step_distance_price <= 0:
        logger.warning("Trailing stop trigger or step pips are not positive. Trailing stop disabled.")
        return
    open_positions = mt5.positions_get(symbol=symbol_to_manage)
    if open_positions is None:
        logger.error(f"Failed to get open positions for {symbol_to_manage}. Error: {mt5.last_error()}")
        return
    if not open_positions: return
    logger.debug(f"Found {len(open_positions)} positions for {symbol_to_manage}. Checking for magic {magic}...")
    for pos in open_positions:
        if pos.magic != magic: continue
        logger.info(f"Managing position ticket: {pos.ticket} for symbol {pos.symbol}, magic {pos.magic}, SL: {pos.sl}, TP: {pos.tp}, Open: {pos.price_open}")
        new_sl_price = pos.sl
        modify_position = False
        current_tick_pos = mt5.symbol_info_tick(pos.symbol)
        if not current_tick_pos:
            logger.warning(f"Could not get current tick for {pos.symbol} to trail position {pos.ticket}.")
            continue
        if pos.type == mt5.ORDER_TYPE_BUY:
            current_market_price = current_tick_pos.bid
            if current_market_price == 0:
                logger.warning(f"Could not get current BID price for {pos.symbol} to trail BUY position {pos.ticket}.")
                continue
            if current_market_price > pos.price_open + trigger_distance_price:
                potential_new_sl = current_market_price - step_distance_price
                if potential_new_sl > pos.price_open and (potential_new_sl > pos.sl or pos.sl == 0.0):
                    new_sl_price = round(potential_new_sl, s_info.digits)
                    modify_position = True
                    logger.info(f"BUY Trail Triggered for {pos.ticket}. Market Bid: {current_market_price}, Open: {pos.price_open}, Current SL: {pos.sl}, New SL: {new_sl_price}")
                else: logger.debug(f"BUY Trail for {pos.ticket}: Potential new SL {potential_new_sl:.{s_info.digits}f} not better than current SL {pos.sl:.{s_info.digits}f} or not above open price.")
        elif pos.type == mt5.ORDER_TYPE_SELL:
            current_market_price = current_tick_pos.ask
            if current_market_price == 0:
                logger.warning(f"Could not get current ASK price for {pos.symbol} to trail SELL position {pos.ticket}.")
                continue
            if current_market_price < pos.price_open - trigger_distance_price:
                potential_new_sl = current_market_price + step_distance_price
                if potential_new_sl < pos.price_open and (potential_new_sl < pos.sl or pos.sl == 0.0):
                    new_sl_price = round(potential_new_sl, s_info.digits)
                    modify_position = True
                    logger.info(f"SELL Trail Triggered for {pos.ticket}. Market Ask: {current_market_price}, Open: {pos.price_open}, Current SL: {pos.sl}, New SL: {new_sl_price}")
                else: logger.debug(f"SELL Trail for {pos.ticket}: Potential new SL {potential_new_sl:.{s_info.digits}f} not better than current SL {pos.sl:.{s_info.digits}f} or not below open price.")
        if modify_position and abs(new_sl_price - pos.sl) > (point * 0.1) :
            request_sltp = {"action": mt5.TRADE_ACTION_SLTP, "position": pos.ticket, "sl": new_sl_price, "tp": pos.tp, "comment": "Trailing SL Update"}
            logger.info(f"Attempting to modify SL for position {pos.ticket} to {new_sl_price:.{s_info.digits}f}")
            result = mt5.order_send(request_sltp)
            if result is None: logger.error(f"Trailing SL modification for ticket {pos.ticket} failed (order_send returned None). Error: {mt5.last_error()}")
            elif result.retcode == mt5.TRADE_RETCODE_DONE: logger.info(f"Trailing SL for ticket {pos.ticket} modified successfully to {new_sl_price:.{s_info.digits}f}. Result comment: {result.comment}")
            else: logger.error(f"Trailing SL modification for ticket {pos.ticket} failed. Retcode: {result.retcode} - {result.comment} (MT5 Error: {mt5.last_error()})")
        elif modify_position: logger.debug(f"Trailing SL for {pos.ticket}: New SL {new_sl_price} is not meaningfully different from current SL {pos.sl}. No modification sent.")

# --- Main Execution Block ---
if __name__ == '__main__':
    if connect_to_mt5():
        logger.info("MT5 Connection Established.")
        start_telegram_bot(TELEGRAM_CONFIG)
        sym_info_startup = get_symbol_info_cached(STRATEGY_CONFIG["symbol"])
        if sym_info_startup is None:
            logger.error(f"Symbol {STRATEGY_CONFIG['symbol']} not found by MT5. Check symbol name. Bot cannot start.")
            if telegram_updater: stop_telegram_bot()
            disconnect_from_mt5()
        elif not sym_info_startup.visible:
            logger.info(f"Symbol {STRATEGY_CONFIG['symbol']} not visible, attempting to select.")
            if not mt5.symbol_select(STRATEGY_CONFIG["symbol"], True):
                 logger.warning(f"Failed to make {STRATEGY_CONFIG['symbol']} visible. Trading might fail if not allowed.")

        if not mt5_connected:
             logger.error("Exiting due to symbol issues or connection failure during startup.")
             if telegram_updater: stop_telegram_bot()
        else:
            try:
                while True:
                    if not bot_control_state["ea_active"]:
                        logger.info("EA is currently PAUSED (via /stop_ea). Sleeping for 10 seconds...")
                        time.sleep(10)
                        # Still manage positions even if EA is paused for new signals
                        if check_mt5_connection(): # Ensure connection for position management
                             manage_open_positions(STRATEGY_CONFIG)
                        continue

                    if not check_mt5_connection():
                        logger.error("MT5 connection lost. Attempting to reconnect in next cycle.")
                        time.sleep(STRATEGY_CONFIG.get("reconnect_delay_on_loss", 30))
                        continue
                    if not update_daily_pivots_if_needed(STRATEGY_CONFIG["symbol"], STRATEGY_CONFIG):
                        logger.warning("Could not update pivot points. Signals might be unreliable or skipped if pivots are missing.")
                        if not daily_pivots_global:
                            time.sleep(60)
                            continue
                    required_bars = max(STRATEGY_CONFIG["rsi_period"], STRATEGY_CONFIG["stoch_k_period"] + STRATEGY_CONFIG["stoch_slowing"],
                                        STRATEGY_CONFIG["bb_period"], STRATEGY_CONFIG["volume_lookback_period"],
                                        STRATEGY_CONFIG["macd_slow_ema"] + STRATEGY_CONFIG["macd_signal_ma"],
                                        STRATEGY_CONFIG["atr_period_sltp"] ) + 50
                    hist_data_df = get_historical_data(STRATEGY_CONFIG["symbol"], STRATEGY_CONFIG["timeframe"], count=required_bars)
                    if hist_data_df is not None and not hist_data_df.empty and len(hist_data_df) >= required_bars - 45:
                        data_with_indicators = calculate_all_indicators(hist_data_df.copy(), STRATEGY_CONFIG)
                        signal = check_strategy_signals(data_with_indicators, daily_pivots_global, STRATEGY_CONFIG, STRATEGY_CONFIG["symbol"])
                        if signal == "BUY" or signal == "SELL":
                            order_type_to_execute = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
                            if bot_control_state["auto_trade_enabled"]:
                                logger.info(f"Auto-trade is ENABLED for {signal} on {STRATEGY_CONFIG['symbol']}. Attempting to execute trade.")
                                execute_trade(STRATEGY_CONFIG['symbol'], order_type_to_execute, STRATEGY_CONFIG, data_with_indicators)
                            else:
                                logger.info(f"Auto-trade is DISABLED. Signal for {signal} on {STRATEGY_CONFIG['symbol']} detected. Sending alert to Telegram...")
                                s_info_alert = get_symbol_info_cached(STRATEGY_CONFIG['symbol'])
                                digits_alert = s_info_alert.digits if s_info_alert else 5
                                tick_alert = mt5.symbol_info_tick(STRATEGY_CONFIG['symbol'])
                                entry_price_for_alert = tick_alert.ask if signal == "BUY" else tick_alert.bid if tick_alert else 0.0
                                if entry_price_for_alert == 0.0:
                                    logger.error(f"Cannot send Telegram alert for {signal} on {STRATEGY_CONFIG['symbol']} due to invalid entry price from tick.")
                                else:
                                    current_atr_for_alert = data_with_indicators['atr'].iloc[-1] if 'atr' in data_with_indicators.columns and not data_with_indicators['atr'].empty else None
                                    alert_sltp = calculate_sl_tp_prices(STRATEGY_CONFIG, STRATEGY_CONFIG['symbol'],
                                                                        order_type_to_execute, entry_price_for_alert,
                                                                        current_atr_for_alert)
                                    trade_id = str(uuid.uuid4())
                                    alert_details = {
                                        "symbol": STRATEGY_CONFIG['symbol'], "order_type": order_type_to_execute,
                                        "entry_price": round(entry_price_for_alert, digits_alert),
                                        "sl_price": round(alert_sltp["sl"], digits_alert),
                                        "tp_price": round(alert_sltp["tp"], digits_alert),
                                        "atr_value": current_atr_for_alert, "timestamp": datetime.datetime.now()
                                    }
                                    pending_trade_alerts[trade_id] = alert_details
                                    alert_message_text, reply_markup = format_trade_alert_message_and_keyboard(alert_details, trade_id)
                                    send_telegram_message(alert_message_text, reply_markup)
                        else:
                            logger.debug(f"No signal detected for {STRATEGY_CONFIG['symbol']}.")
                        manage_open_positions(STRATEGY_CONFIG)
                    else:
                        logger.warning(f"Could not fetch sufficient data for {STRATEGY_CONFIG['symbol']} (got {len(hist_data_df) if hist_data_df is not None else 0}, needed ~{required_bars}) to check signals.")
                    time_to_sleep = 60
                    tf = STRATEGY_CONFIG["timeframe"]
                    if tf == mt5.TIMEFRAME_M5: time_to_sleep = 300
                    elif tf == mt5.TIMEFRAME_M15: time_to_sleep = 900
                    elif tf == mt5.TIMEFRAME_H1: time_to_sleep = 3600
                    logger.info(f"Main trading loop iteration complete (EA Active: {bot_control_state['ea_active']}). Waiting for {time_to_sleep} seconds...")
                    time.sleep(time_to_sleep)
            except KeyboardInterrupt: logger.info("Trading bot run interrupted by user.")
            except Exception as e: logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
            finally:
                logger.info("Shutting down...")
                stop_telegram_bot()
                disconnect_from_mt5()
                logger.info("Trading bot has been shut down.")
    else:
        logger.error("Failed to connect to MT5 during initial startup. Bot will not start.")
