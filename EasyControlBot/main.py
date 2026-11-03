import asyncio
import os
from aiogram import Bot, Dispatcher
from aiohttp import web
from config import config
from database.database import init_db, async_session_maker
from handlers import start, items, clear
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from database.models import ItemModel
from datetime import datetime


# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (чтобы бот не засыпал) ---
async def handle(request):
    return web.Response(text="Bot is running!")


async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# --- ФОНОВАЯ ПРОВЕРКА СРОКОВ ГОДНОСТИ ---
async def check_expiring_items(bot: Bot):
    async with async_session_maker() as session:
        result = await session.execute(select(ItemModel))
        items_list = result.scalars().all()

        today = datetime.now().date()
        for item in items_list:
            if item.expires_at:
                try:
                    exp_date = datetime.strptime(item.expires_at, "%d.%m.%Y").date()
                    delta = (exp_date - today).days

                    if delta == 14 and item.notified_14_days == 0:
                        await bot.send_message(
                            item.user_id,
                            f"⚠️ <b>Внимание!</b> У товара <b>«{item.name}»</b> истекает срок годности через 14 дн. (годен до {item.expires_at}).",
                            parse_mode="HTML"
                        )
                        item.notified_14_days = 1
                        await session.commit()
                except Exception:
                    pass


# --- ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА ---
async def main():
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()

    # Подключаем роутеры
    dp.include_router(start.router)
    dp.include_router(items.router)
    dp.include_router(clear.router)

    # Инициализация базы данных
    await init_db()

    # Настройка планировщика
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(check_expiring_items, "interval", seconds=30, args=(bot,))
    scheduler.start()

    # Запускаем веб-сервер в фоне для Render
    await web_server()

    # Запуск поллинга бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())