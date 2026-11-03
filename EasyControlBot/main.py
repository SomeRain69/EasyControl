import asyncio
import os
from aiogram import Bot, Dispatcher
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from datetime import datetime

from EasyControlBot.config import config
from EasyControlBot.database.database import init_db, async_session_maker
from EasyControlBot.handlers import start, items, clear
from EasyControlBot.database.models import ItemModel


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

                    # Если осталось 14 дней или меньше (и уведомление еще не уходило)
                    if delta <= 14 and item.notified_14_days == 0:
                        if delta > 0:
                            msg = f"⚠️ <b>Внимание!</b> У товара <b>«{item.name}»</b> истекает срок годности через {delta} дн. (годен до {item.expires_at})."
                        elif delta == 0:
                            msg = f"🚨 <b>Внимание!</b> У товара <b>«{item.name}»</b> срок годности истекает <b>сегодня</b> ({item.expires_at})!"
                        else:
                            msg = f"❌ <b>Просрочка!</b> У товара <b>«{item.name}»</b> истек срок годности {item.expires_at}!"

                        await bot.send_message(
                            item.user_id,
                            msg,
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

    # Настройка планировщика (проверка каждые 30 секунд)
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