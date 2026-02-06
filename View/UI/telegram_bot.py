import asyncio

from ccxt.static_dependencies.ethereum.abi.grammar import normalize
from telegram.ext import ApplicationBuilder, CommandHandler

from View.entity.user_settings import UserSettings
from View.trayding_controller import TradingController
from View.factory import create_wavex_trading_service
from View.UI.keyboards import main_menu
from telegram.ext import CallbackQueryHandler
from config import ExchangeConfig
from View.UI.signal_formatter import build_signal_text

class TelegramTradingBot:
    def __init__(self, token: str, loop: asyncio.AbstractEventLoop = None):
        self._user_settings = {}
        self._controller = TradingController(create_wavex_trading_service)

        self._app = ApplicationBuilder().token(token).build()
        self._loop = loop
        # self._app.add_handler(CommandHandler("start_trading", self.start_trading))
        # self._app.add_handler(CommandHandler("stop_trading", self.stop_trading))
        self._app.add_handler(CommandHandler("start", self.start))
        self._app.add_handler(CommandHandler("trading", self.trading))
        self._app.add_handler(CallbackQueryHandler(self.on_button))
        self._app.add_handler(CommandHandler("symbol", self.set_symbol))
        self._app.add_handler(CommandHandler("timeframe", self.set_timeframe))
        self._app.add_handler(CommandHandler("amount", self.set_amount))
        self._app.add_handler(CommandHandler("leverage", self.set_leverage))

    async def start(self, update, context):
        # is_running = self._controller.is_running()
        #
        # text = (
        #     "🤖 *WAVEX Trading Bot*\n\n"
        #     "Управление стратегией:"
        # )
        #
        # await update.message.reply_text(
        #     text,
        #     parse_mode="Markdown",
        #     reply_markup=main_menu(is_running)
        # )
        text = (
            "👋 *Добро пожаловать в WAVEX Trading Bot*\n\n"
            "Я — торговый бот для работы со стратегией *WAVEX*.\n\n"
            "*Доступные команды:*\n"
            "🔹 /trading — управление торговлей\n"
            "🔹 /symbol BTCUSDT — выбрать торговую пару\n"
            "🔹 /timeframe 15m — выбрать таймфрейм\n"
            "🔹 /amount 150 — сумма сделки (USDT)\n"
            "🔹 /leverage 5 — кредитное плечо\n\n"
            "ℹ️ Перед запуском стратегии обязательно задай параметры.\n"
            "Затем используй команду /trading 👇"
        )

        await update.message.reply_text(
            text,
            parse_mode="Markdown"
        )

    async def trading(self, update, context):
        chat_id = update.effective_chat.id
        is_running = self._controller.is_running()

        text = (
            "🤖 *WAVEX Trading Control*\n\n"
            "Управление стратегией:"
        )

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu(is_running)
        )

    async def on_button(self, update, context):
        query = update.callback_query
        await query.answer()

        chat_id = query.message.chat_id
        action = query.data  # START / STOP

        if action == "START":
            await self._handle_start(query, chat_id)

        elif action == "STOP":
            await self._handle_stop(query, chat_id)

    async def _handle_start(self, query, chat_id: int):
        settings = self._get_settings(chat_id)

        try:
            trading_service = self._controller.start(
                params=settings,
                on_signal=None
            )

            send_signal = self._make_signal_sender(chat_id, trading_service)
            self._controller.attach_signal_handler(send_signal)

            text = (
                "▶ *WAVEX Strategy started*\n"
                f"📊 *Symbol:* {settings.symbol}\n"
                f"⏱ *Timeframe:* {settings.timeframe}\n"
                f"💰 *Amount:* {settings.amount}\n"
                f"⚡ *Leverage:* {settings.leverage}"
            )

        except RuntimeError:
            text = "⚠️ Trading already running"

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu(self._controller.is_running())
        )

    async def _handle_stop(self, query, chat_id: int):
        try:
            self._controller.stop()
            text = "⏹ *WAVEX Strategy stopped*"
        except RuntimeError:
            text = "⚠️ Trading is not running"

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu(self._controller.is_running())
        )

    def _make_signal_sender(self, chat_id: int, trading_service):
        def send_signal(signal: dict):
            text = build_signal_text(
                signal=signal,
                symbol=trading_service.symbol,
                timeframe=trading_service.timeframe
            )

            if not text:
                return

            asyncio.run_coroutine_threadsafe(
                self._app.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode = "Markdown"
                ),
                self._loop
            )

        return send_signal

    def _get_settings(self, chat_id: int) -> UserSettings:
        if chat_id not in self._user_settings:
            self._user_settings[chat_id] = UserSettings()
        return self._user_settings[chat_id]

    def normalize_timeframe(self, tf: str) -> str | None:
        key = tf.strip().lower()
        return ExchangeConfig.TIMEFRAME_MAP.get(key)


    async def set_symbol(self, update, context):
        chat_id = update.effective_chat.id
        settings = self._get_settings(chat_id)

        if not context.args:
            await update.message.reply_text("❌ Usage: /symbol BTCUSDT")
            return

        settings.symbol = context.args[0].upper()
        await update.message.reply_text(f"✅ Symbol set to {settings.symbol}")

    async def set_timeframe(self, update, context):
        chat_id = update.effective_chat.id
        settings = self._get_settings(chat_id)

        if not context.args:
            await update.message.reply_text("❌ Usage: /timeframe 1H")
            return

        normalized = self.normalize_timeframe(context.args[0])

        # tf = context.args[0].upper()

        if not normalized:
            await update.message.reply_text(
                "❌ Unsupported timeframe.\n"
                "Examples: 1m, 3m, 5m, 15m, 30m,"
                " 1H, 4H, 6H ,12H, 1D, 1W, 1M "
            )
            return

        settings.timeframe = normalized
        await update.message.reply_text(f"✅ Timeframe set to {settings.timeframe}")

    async def set_amount(self, update, context):
        chat_id = update.effective_chat.id
        settings = self._get_settings(chat_id)

        if not context.args:
            await update.message.reply_text("❌ Usage: /amount 100")
            return

        try:
            amount = float(context.args[0])
            if amount <= 0:
                raise ValueError

            settings.amount = amount
            await update.message.reply_text(f"✅ Amount set to {settings.amount}")
        except ValueError:
            await update.message.reply_text("❌ Usage: /amount 100")

    async def set_leverage(self, update, context):
        chat_id = update.effective_chat.id
        settings = self._get_settings(chat_id)

        if not context.args:
            await update.message.reply_text("❌ Usage: /leverage 5")
            return

        try:
            leverage = int(context.args[0])
            if leverage <= 0:
                raise ValueError
            settings.leverage = leverage
            await update.message.reply_text(f"✅ Leverage set to {settings.leverage}x")

        except Exception:
            await update.message.reply_text("❌ Usage: /leverage 5")

    def run(self):
        self._app.run_polling()