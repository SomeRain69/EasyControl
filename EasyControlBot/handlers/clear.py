from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import delete

from database.database import async_session_maker
from database.models import ItemModel

router = Router()


# 1. ЗАПРОС ПОДТВЕРЖДЕНИЯ ОЧИСТКИ
@router.callback_query(F.data == "btn_clear")
async def confirm_clear_items(callback: CallbackQuery):
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить всё", callback_data="confirm_yes")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main")]
        ]
    )

    text = "⚠️ <b>Ты действительно хочешь удалить все свои товары?</b>\nЭто действие нельзя отменить."
    await callback.message.edit_text(text, reply_markup=confirm_keyboard, parse_mode="HTML")
    await callback.answer()


# 2. УДАЛЕНИЕ ПОСЛЕ ПОДТВЕРЖДЕНИЯ
@router.callback_query(F.data == "confirm_yes")
async def execute_clear_items(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Удаляем из базы данных только товары этого пользователя
    async with async_session_maker() as session:
        await session.execute(delete(ItemModel).where(ItemModel.user_id == user_id))
        await session.commit()

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_main")]
        ]
    )

    text = "🗑 <b>Твой список товаров полностью очищен!</b>"
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()