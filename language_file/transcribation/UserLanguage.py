from langdetect import detect, DetectorFactory
from ashredis import MISSING
from BANNED_FILES.config import RedisManager
from redis_storage.users_contest import UsersContest

# Фиксируем случайность определения языка
DetectorFactory.seed = 0

# Инициализация Redis
redis = RedisManager()

async def get_user_language(client, user_id: str, message_text: str):
    """
    Определяет язык пользователя, сохраняет его в Redis
    и записывает первые 5 сообщений.
    """

    # Если текст пустой или слишком короткий — считаем, что язык русский
    if not message_text or len(message_text.strip()) < 3:
        message_text = ""
        lang_code = "ru"
    else:
        # Определяем язык через langdetect
        try:
            detected_lang = detect(message_text)
        except Exception:
            detected_lang = "unknown"

        # Если язык русский, английский или украинский — используем его, иначе русский
        lang_code = detected_lang if detected_lang in ["ru", "en", "uk"] else "ru"

    # Загружаем запись пользователя из Redis
    async with redis:
        record = await redis.load(UsersContest, key=str(user_id))

        if record is None:
            # Если пользователь новый — создаём запись
            record = UsersContest(
                user_id=str(user_id),
                language=lang_code,
                first_name=None
            )
        else:
            # Если язык ещё не сохранён — обновляем его
            if not record.language:
                record.language = lang_code

        # Сохраняем первые 5 сообщений
        for i in range(1, 6):
            field_name = f"first_message_{i}"
            current_value = getattr(record, field_name, MISSING)
            if current_value in [None, "", MISSING]:
                setattr(record, field_name, message_text)
                break

        # Сохраняем запись обратно в Redis
        await redis.save(record, key=str(user_id))

    return record.language
