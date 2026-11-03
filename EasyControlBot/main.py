import asyncio
import logging
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web

from config import config
from database.database import init_db
from handlers import start, items, clear
from services.scheduler import check_expiring_items

# Настройка логирования для консоли Render
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


# ==========================================
# 1. ВЕБ-СЕРВЕР ДЛЯ RENDER (Health Check)
# ==========================================
async def handle_ping(request):
    """Простейший обработчик, чтобы Render видел открытый порт и не усыплял сервис."""
    return web.Response(text="Bot is running and alive!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)

    # Render автоматически передает нужный порт в переменную окружения PORT
    port = int(os.environ.get("PORT", 10000))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server successfully started on port {port}")


# ==========================================
# 2. ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА БОТА
# ==========================================
async def main():
    if not config.bot_token:
        logging.error("Не найден bot_token в конфигурации!")
        return

    # Инициализация бота и диспетчера
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Инициализируем базу данных при старте
    await init_db()

    # Подключаем твои роутеры из папки handlers
    dp.include_router(start.router)
    dp.include_router(items.router)
    dp.include_router(clear.router)

    # Настраиваем фоновый планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_expiring_items, "interval", seconds=30, args=[bot, config.admin_id])
    scheduler.start()

    # Сначала запускаем веб-сервер для Render, чтобы порт занялся мгновенно
    await start_web_server()

    # Удаляем вебхуки и стартуем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот успешно запущен и ожидает сообщения...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")