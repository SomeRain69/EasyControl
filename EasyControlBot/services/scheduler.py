from datetime import datetime
from aiogram import Bot
from sqlalchemy import select
from database.database import async_session_maker
from database.models import ItemModel


async def check_expiring_items(bot: Bot, admin_id: int):
    now = datetime.now().date()

    async with async_session_maker() as session:
        result = await session.execute(select(ItemModel))
        items = result.scalars().all()

        for item in items:
            if not item.expires_at:
                continue

            try:
                exp_date = datetime.strptime(item.expires_at, "%d.%m.%Y").date()
            except ValueError:
                continue

            if exp_date < now:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"❌ Срок годности товара «{item.name}» (истекал {item.expires_at}) вышел! Товар удален из базы."
                )
                await session.delete(item)
                await session.commit()
                continue

            delta_days = (exp_date - now).days
            if delta_days <= 14 and item.notified_14_days == 0:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"⚠️ Внимание! У товара «{item.name}» истекает срок годности через {delta_days} дн. (годен до {item.expires_at})."
                )
                item.notified_14_days = 1
                await session.commit()