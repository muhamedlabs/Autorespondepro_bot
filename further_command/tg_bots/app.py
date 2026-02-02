import asyncio
import os
import importlib
import sys
from pathlib import Path
from telegram.ext import ApplicationBuilder
from telegram.error import TimedOut, NetworkError
from BANNED_FILES.config import telegram_bots

def create_app():
    """Создает приложение бота"""
    return ApplicationBuilder().token(telegram_bots).build()

def load_commands_from_terminal(app):
    """Загружает все команды из папки terminal (находится в той же директории)"""
    current_dir = Path(__file__).parent  # Директория tg_bots
    terminal_dir = current_dir / "terminal"
    
    if not terminal_dir.exists():
        return app
    
    # Получаем все Python файлы в папке terminal
    for filename in os.listdir(terminal_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            module_name = filename[:-3]  # Убираем .py
            
            try:
                # Создаем полный путь к файлу
                file_path = terminal_dir / filename
                
                # Динамически импортируем модуль
                spec = importlib.util.spec_from_file_location(
                    module_name,
                    file_path
                )
                module = importlib.util.module_from_spec(spec)
                
                # Добавляем модуль в sys.modules для возможности импорта
                sys.modules[f"terminal_{module_name}"] = module
                
                # Выполняем загрузку
                spec.loader.exec_module(module)
                
                # Проверяем наличие функции command_handler
                if hasattr(module, 'command_handler'):
                    handler = module.command_handler()
                    app.add_handler(handler)
                else:
                    print(f"Файл {filename} не содержит функцию command_handler")
                    
            except Exception as e:
                print(f"Ошибка загрузки {filename}: {e}")
                import traceback
                traceback.print_exc()
    
    return app

async def start_mini_bot():
    """Запуск мини-бота с повторными попытками подключения"""
    max_retries = 5
    base_delay = 3  # начальная задержка в секундах
    
    for attempt in range(max_retries):
        try:
            # Создаем приложение с увеличенными таймаутами
            app = ApplicationBuilder() \
                .token(telegram_bots) \
                .connect_timeout(30.0) \
                .read_timeout(30.0) \
                .write_timeout(30.0) \
                .pool_timeout(30.0) \
                .build()
            
            # Загружаем команды из папки terminal
            load_commands_from_terminal(app)
            
            # Инициализируем и запускаем бота
            await app.initialize()
            await app.start()
            
            # Запускаем polling
            await app.updater.start_polling()
            
            print("MiniBot is already operating asynchronously!")
            return app
            
        except (TimedOut, NetworkError) as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Экспоненциальная задержка
                print(f"Ошибка подключения: {e}. Повтор через {delay} секунд...")
                await asyncio.sleep(delay)
            else:
                print(f"Все {max_retries} попыток подключения провалились: {e}")
                raise
        except Exception as e:
            print(f"Неожиданная ошибка при запуске бота: {e}")
            raise
    
    return None

# Если файл запускается отдельно
if __name__ == "__main__":
    async def main():
        try:
            app = await start_mini_bot()
            if not app:
                print("Не удалось запустить бота")
                return
                
            try:
                # Бесконечный цикл с периодической проверкой
                while True:
                    # Проверяем, что бот все еще работает
                    await asyncio.sleep(300)  # Проверка каждые 5 минут
                    
            except KeyboardInterrupt:
                print("\nОстановка мини-бота...")
            except Exception as e:
                print(f"Ошибка в основном цикле: {e}")
            finally:
                # Корректное завершение
                if app:
                    try:
                        await app.updater.stop()
                        await app.stop()
                        await app.shutdown()
                    except Exception as e:
                        print(f"Ошибка при завершении: {e}")
                print("Бот остановлен")
                
        except Exception as e:
            print(f"Критическая ошибка: {e}")
    
    asyncio.run(main())