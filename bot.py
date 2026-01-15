import os
import logging
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Logging setup
logging.basicConfig(level=logging.INFO)

# Token from Render Environment Variables
API_TOKEN = os.getenv('MOTHER_BOT_TOKEN')

bot = Bot(token=API_TOKEN)
storage = MemoryStorage() # Zaroori hai states ke liye
dp = Dispatcher(bot, storage=storage)

# --- MAIN START COMMAND ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🛍️ I am a Buyer", callback_data="role_buyer"),
        types.InlineKeyboardButton("⚙️ I am a Seller", callback_data="role_seller")
    )
    
    welcome_text = (
        "👋 **Welcome to MarketMaster!**\n\n"
        "This is a Whitelabel bot. You can browse products or "
        "clone this bot to start your own business.\n\n"
        "**Please choose your role:**"
    )
    await message.reply(welcome_text, reply_markup=kb, parse_mode="Markdown")

# --- SELLER SIDE ---
@dp.callback_query_handler(text="role_seller")
async def seller_main(call: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🚀 Clone My Bot", callback_data="clone_bot"),
        types.InlineKeyboardButton("➕ List New Product", callback_data="add_item"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")
    )
    await call.message.edit_text("👨‍💼 **Seller Dashboard**\nWhat would you like to do?", reply_markup=kb)

# --- BUYER SIDE ---
@dp.callback_query_handler(text="role_buyer")
async def buyer_main(call: types.CallbackQuery):
    await call.answer("Fetching products...", show_alert=False)
    # Yahan hum baad mein database se product list dikhayenge
    await call.message.edit_text("🛒 **Marketplace**\n\nCurrently, there are no products available. Check back later!")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
