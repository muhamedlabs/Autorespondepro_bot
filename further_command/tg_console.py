import sys
import asyncio
from html import escape
from telegram import Bot
from telegram.error import TimedOut, NetworkError
from BANNED_FILES.config import TG_CHANNEL_ID, telegram_bots, START_GIF


class ConsoleToTelegram:
    def __init__(self):
        self.original_stdout = sys.__stdout__
        self.original_stderr = sys.__stderr__
        self.bot: Bot | None = None
        self.initialized = False

        # Пропуск первых сообщений
        self._messages_to_skip = 3
        self._skipped = 0

        # Задержка старта
        self._delay_seconds = 10
        self._delay_active = True
        self._buffer: list[str] = []

        # Анти-спам повторяющихся сообщений
        self._last_message: str | None = None
        self._last_message_time: float = 0.0
        self._repeat_block_seconds = 15

    async def init_bot(self):
        """Инициализация бота с повторными попытками при ошибках подключения"""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                self.bot = Bot(token=telegram_bots)
                self.bot._timeout = 30.0

                await self.bot.get_me()
                self.initialized = True

                await self.bot.send_animation(
                    chat_id=TG_CHANNEL_ID,
                    animation=START_GIF,
                    caption=(
                        "🌌 <b>Console Activated!</b>\n\n"
                        "Дух отточен, как клинок. Сознание чисто, как вода в горном ручье после дождя. "
                        "Три первых шепота ветра пропущу — чтобы услышать истинный голос задачи за суетой.\n\n"
                        "Канал связи <b>открыт</b>. Готов ловить импульсы из консоли в реальном потоке. "
                        "Пусть <b>данные</b> струятся, словно молнии в грозовом небе <b>самурайской</b> решимости!"
                    ),
                    parse_mode="HTML"
                )

                asyncio.create_task(self._delayed_flush())
                return True

            except (TimedOut, NetworkError):
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return False
            except Exception:
                return False

    async def _delayed_flush(self):
        """Обработка буферизированных сообщений после задержки"""
        await asyncio.sleep(self._delay_seconds)
        self._delay_active = False

        for msg in self._buffer:
            try:
                await self._send_with_retry(msg)
                await asyncio.sleep(0.05)
            except Exception:
                pass

        self._buffer.clear()

    def write(self, text):
        self.original_stdout.write(text)

        if not self.initialized or not text.strip():
            return

        if self._skipped < self._messages_to_skip:
            self._skipped += 1
            return

        if self._delay_active:
            self._buffer.append(text)
            return

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._send_with_retry(text))
        except RuntimeError:
            pass

    def flush(self):
        self.original_stdout.flush()

    async def _send_with_retry(self, text: str):
        max_retries = 2
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                return await self._send(text)
            except (TimedOut, NetworkError):
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
            except Exception:
                break

    async def _send(self, text: str):
        try:
            clean = text.rstrip()
            if not clean or not self.bot:
                return

            now = asyncio.get_running_loop().time()

            # Блок повторяющихся сообщений (15 сек)
            if (
                clean == self._last_message
                and now - self._last_message_time < self._repeat_block_seconds
            ):
                return

            self._last_message = clean
            self._last_message_time = now

            safe_text = escape(clean)
            MAX_LEN = 4000

            if len(safe_text) > MAX_LEN:
                for i in range(0, len(safe_text), MAX_LEN):
                    await self.bot.send_message(
                        chat_id=TG_CHANNEL_ID,
                        text=safe_text[i:i + MAX_LEN],
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(0.05)
            else:
                await self.bot.send_message(
                    chat_id=TG_CHANNEL_ID,
                    text=safe_text,
                    parse_mode="HTML"
                )

        except Exception:
            pass


# ===== Глобальный экземпляр =====
_console_logger: ConsoleToTelegram | None = None


def get_console_capture() -> ConsoleToTelegram:
    global _console_logger
    if _console_logger is None:
        _console_logger = ConsoleToTelegram()
    return _console_logger


async def setup_console_logger() -> bool:
    logger = get_console_capture()
    try:
        success = await logger.init_bot()
        if success:
            sys.stdout = logger
            sys.stderr = logger
        return success
    except Exception:
        return False


def tg_print(*args, bold=False, italic=False, code=False, **kwargs):
    text = " ".join(str(arg) for arg in args)

    if code:
        text = f"<code>{text}</code>"
    if italic:
        text = f"<i>{text}</i>"
    if bold:
        text = f"<b>{text}</b>"

    print(text, **kwargs)
