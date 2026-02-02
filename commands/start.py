import asyncio
import os
from datetime import datetime, timedelta
from telethon.errors import YouBlockedUserError
from BANNED_FILES.config import RedisManager, VIDEO_FILE
from redis_storage.users_info import UsersInfo
from language_file.transcribation.UserLanguage import get_user_language
from language_file.main import get_translation

# ===== Redis =====
redis = RedisManager()

# ===== Локи пользователей =====
user_locks: dict[str, bool] = {}
LOCK_EXPIRATION = 10  # секунд

# ===== Анти-дубль логов (по тексту) =====
_last_log_text: str | None = None
_last_log_time: float = 0.0
LOG_BLOCK_SECONDS = 15


def safe_log(text: str):
    """
    Печатает лог, если он не повторяется в течение LOG_BLOCK_SECONDS
    """
    global _last_log_text, _last_log_time

    now = asyncio.get_running_loop().time()

    if text == _last_log_text and now - _last_log_time < LOG_BLOCK_SECONDS:
        return

    _last_log_text = text
    _last_log_time = now
    print(text)


# ===== Время Украина (UTC+2) =====
def get_ukraine_time():
    return datetime.utcnow() + timedelta(hours=2)


def format_ukraine_time(dt=None):
    if dt is None:
        dt = get_ukraine_time()
    return dt.strftime('%d.%m.%y %H:%M:%S')


# ===== Redis helpers =====
async def has_replied(user_id: str) -> bool:
    async with redis:
        return await redis.load(UsersInfo, key=str(user_id)) is not None


async def save_replied_user(user_id: str, **kwargs):
    current_time = format_ukraine_time()

    async with redis:
        user_record = UsersInfo(
            user_id=str(user_id),
            timestamp=current_time,
            **kwargs
        )
        await redis.save(user_record, key=str(user_id))

    safe_log(f"Пользователь {user_id} сохранён в Redis")


async def remove_user_from_redis(user_id: str):
    async with redis:
        await redis.delete(UsersInfo, key=str(user_id))

    safe_log(f"Пользователь {user_id} удалён из Redis")


# ===== Локи =====
async def set_user_lock(user_id: str):
    user_locks[user_id] = True
    await asyncio.sleep(LOCK_EXPIRATION)
    user_locks.pop(user_id, None)


def is_user_locked(user_id: str) -> bool:
    return user_locks.get(user_id, False)


# ===== Процессы =====
async def register_proces(user_id: str, proces_type: str, data: dict | None = None):
    if data is None:
        data = {}

    current_time = format_ukraine_time()

    async with redis:
        user_record = await redis.load(UsersInfo, key=str(user_id))

        if user_record:
            user_record.proces_type = proces_type
            user_record.proces_data = data
            user_record.proces_started = current_time
            user_record.last_activity = current_time
        else:
            user_record = UsersInfo(
                user_id=str(user_id),
                proces_type=proces_type,
                proces_data=data,
                proces_started=current_time,
                last_activity=current_time,
                timestamp=current_time
            )

        await redis.save(user_record, key=str(user_id))

    safe_log(f"Процесс '{proces_type}' зарегистрирован для пользователя {user_id}")


# ===== Извлечение пользователя =====
async def extract_user_info(event, client):
    sender = await event.get_sender()
    if sender is None:
        safe_log("Ошибка: не удалось получить отправителя")
        return None

    user_info = {
        'user_id': str(sender.id),
        'chat_id': event.chat_id,
        'phone': sender.phone or "No phone number",
        'username': sender.username or "None",
        'first_name': sender.first_name or "None",
        'last_name': sender.last_name or "None",
        'link': (
            f"https://t.me/{sender.username}"
            if sender.username else "No link"
        ),
        'message_text': event.message.text.strip() if event.message.text else "",
    }

    user_info['lang'] = await get_user_language(
        client,
        user_info['user_id'],
        user_info['message_text']
    )
    user_info['message_text_lower'] = user_info['message_text'].lower()

    return user_info


# ===== Приветствие =====
async def handle_welcome_message(client, user_info, is_reset=False):
    try:
        if os.path.exists(VIDEO_FILE):
            await client.send_file(
                user_info['chat_id'],
                VIDEO_FILE,
                caption=get_translation("welcome", user_info['lang'])
            )
        else:
            await client.send_message(
                user_info['chat_id'],
                get_translation("welcome", user_info['lang'])
            )

        await save_replied_user(
            user_id=user_info['user_id'],
            username=user_info['username'],
            first_name=user_info['first_name'],
            last_name=user_info['last_name'],
            phone=user_info['phone'],
            chat_id=user_info['chat_id'],
            link=user_info['link']
        )

        if is_reset:
            safe_log(f"Приветствие отправлено пользователю {user_info['user_id']} после команды !start")
        else:
            safe_log(f"Приветствие отправлено пользователю {user_info['user_id']}")

        return True

    except YouBlockedUserError:
        safe_log(f"Пользователь {user_info['user_id']} заблокировал бота")
        return False

    except Exception as e:
        safe_log(f"Ошибка отправки приветствия пользователю {user_info['user_id']}: {e}")
        return False


# ===== Reset =====
async def handle_user_reset(user_id: str):
    await remove_user_from_redis(user_id)
    user_locks.pop(user_id, None)
    safe_log(f"Данные пользователя {user_id} сброшены")
