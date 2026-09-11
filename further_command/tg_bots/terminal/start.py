from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler

user_started = set()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_started:
        user_started.add(user_id)

    # Вступительный текст с командами
    welcome_text = (
        "🌌 <b>Приветствуем тебя в мире нашего бота!</b>\n\n"
        "💡 Вот список доступных команд:\n"
        "/start - запустить бота\n"
        "/help - помощь по командам\n"
        "/profile - твой профиль\n"
        "/settings - настройки бота\n\n"
        "Нажми на кнопки ниже для быстрых действий:"
    )

    # Кнопки снизу
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Донат", url="https://www.donationalerts.com/r/andremuhamad"),
            InlineKeyboardButton("📡 Основной канал", url="https://t.me/muhamedlabs")
        ]
    ])

    # Отправка сообщения
    await update.message.reply_html(
        welcome_text,
        reply_markup=keyboard
    )

def command_handler():
    """Возвращает обработчик команды /start"""
    return CommandHandler("start", start_command)
