
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from core.config import BOT_TOKEN
from handlers.quiz_handler import router as quiz_router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')


async def set_default_commands(bot: Bot):
    """Устанавливает команды для меню бота."""
    commands = [
        BotCommand(command="start", description="Запустить приветствие и викторину"),
        BotCommand(command="help", description="Помощь по боту"),
    ]
    await bot.set_my_commands(commands)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(quiz_router)

    await set_default_commands(bot)

    logging.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
    except Exception as e:
        logging.error(f"Bot failed to start: {e}")