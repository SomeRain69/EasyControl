from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import delete

from database.database import async_session_maker
from database.models import ItemModel
from handlers.start import get_main_menu_keyboard

router = Router()


@router.callback_query(F.data == "btn_clear")
async def clear_confirm(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, очистить всё", callback_data="confirm_clear")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="btn_back_to_menu")]
    ])
    await callback.message.answer("⚠️ Вы уверены, что хотите полностью очистить весь список товаров?",
                                  reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "confirm_clear")
async def clear_execute(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with async_session_maker() as session:
        await session.execute(delete(ItemModel).where(ItemModel.user_id == user_id))
        await session.commit()

    await callback.message.answer("🗑 Весь список товаров успешно очищен!", reply_markup=get_main_menu_keyboard())
    await callback.answer()