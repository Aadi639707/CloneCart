import os
import logging
import asyncio
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId

# --- RENDER WEB SERVICE PORT BINDING ---
app = Flask('')
@app.route('/')
def home():
    return "MarketMaster Mother & Clones are Online!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- CONFIGURATION ---
API_TOKEN = os.getenv('MOTHER_BOT_TOKEN')
MONGO_URL = os.getenv('MONGO_URL')

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()

# Database Connection
client = AsyncIOMotorClient(MONGO_URL)
db = client["market_database"]
products_col = db["products"]
clones_col = db["clones"]

# Initialize Mother Bot
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

# --- TELEGRAM ASSET CATEGORIES ---
CATEGORIES = ["🆔 Telegram IDs", "📢 Channels", "👥 Groups", "📦 Other Assets"]

# --- STATES (FSM) ---
class AddProduct(StatesGroup):
    waiting_for_category = State()
    waiting_for_photo = State()
    waiting_for_name = State()
    waiting_for_price = State()

class CloneBot(StatesGroup):
    waiting_for_token = State()

# --- KEYBOARDS ---
def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🛍️ Browse Market", callback_data="role_buyer"),
        types.InlineKeyboardButton("⚙️ Seller Panel", callback_data="role_seller")
    )
    kb.add(types.InlineKeyboardButton("🚀 Clone This Bot", callback_data="clone_start"))
    return kb

def category_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIES:
        kb.insert(types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
    return kb

# --- HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    await message.reply(
        "✨ **Welcome to the Whitelabel Asset Market**\n\nThe most secure platform to trade Telegram IDs, Channels, and Groups.\n\n"
        "Please select your role below:",
        reply_markup=main_menu(), 
        parse_mode="Markdown"
    )

# --- CLONING FEATURE ---
@dp.callback_query_handler(text="clone_start")
async def start_cloning(call: types.CallbackQuery):
    await CloneBot.waiting_for_token.set()
    await call.message.answer(
        "🆕 **Create Your Personal Clone**\n\n"
        "1. Go to @BotFather and create a new bot.\n"
        "2. Copy the **API Token** provided.\n"
        "3. Send the token here below:"
    )

@dp.message_handler(state=CloneBot.waiting_for_token)
async def process_clone_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    try:
        temp_bot = Bot(token=token)
        me = await temp_bot.get_me()
        
        await clones_col.update_one(
            {"token": token},
            {"$set": {"owner_id": message.from_user.id, "username": me.username}},
            upsert=True
        )
        
        await message.answer(f"✅ **Clone Active!**\nYour bot @{me.username} is now running.")
        
        new_dp = Dispatcher(temp_bot, storage=storage)
        register_handlers(new_dp)
        asyncio.create_task(new_dp.start_polling())
        
    except Exception:
        await message.answer("❌ **Error:** Invalid Token. Please try again.")
    await state.finish()

# --- BUYER LOGIC (BY CATEGORY) ---
@dp.callback_query_handler(text="role_buyer")
async def buyer_categories(call: types.CallbackQuery):
    await call.message.edit_text("📂 **Select a Category to Browse:**", reply_markup=category_keyboard())

@dp.callback_query_handler(lambda c: c.data.startswith('cat_'))
async def show_category_items(call: types.CallbackQuery):
    cat_name = call.data.replace("cat_", "")
    items = await products_col.find({"category": cat_name}).to_list(length=15)
    
    if not items:
        await call.message.answer(f"❌ No listings found in {cat_name}.")
        return

    for item in items:
        try:
            seller = await bot.get_chat(item['seller_id'])
            seller_link = f"https://t.me/{seller.username}" if seller.username else f"tg://user?id={item['seller_id']}"
        except:
            seller_link = f"tg://user?id={item['seller_id']}"

        deal_kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🤝 Buy / Contact Seller", url=seller_link)
        )
        
        await bot.send_photo(
            call.from_user.id, item['photo'],
            caption=f"📂 **Category:** {item['category']}\n📦 **Asset:** {item['name']}\n💰 **Price:** {item['price']}",
            reply_markup=deal_kb, 
            parse_mode="Markdown"
        )

# --- SELLER LOGIC & MY LISTINGS ---
@dp.callback_query_handler(text="role_seller")
async def seller_home(call: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("➕ List New Asset", callback_data="add_item"),
        types.InlineKeyboardButton("📦 My Listings (Delete Items)", callback_data="my_listings"),
        types.InlineKeyboardButton("🔙 Back to Main", callback_data="back_main")
    )
    await call.message.edit_text("👨‍💼 **Seller Dashboard**\nManage your assets for sale:", reply_markup=kb)

@dp.callback_query_handler(text="back_main")
async def back_to_main(call: types.CallbackQuery):
    await call.message.edit_text("✨ **Welcome Back!**\nSelect your role:", reply_markup=main_menu())

@dp.callback_query_handler(text="my_listings")
async def my_listings(call: types.CallbackQuery):
    user_id = call.from_user.id
    items = await products_col.find({"seller_id": user_id}).to_list(length=50)

    if not items:
        await call.message.answer("❌ You have no active listings.")
        return

    await call.message.answer("📦 **Your Active Listings:**\n(Click 'Delete' to remove sold items)")

    for item in items:
        del_kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🗑️ Delete Listing", callback_data=f"del_{item['_id']}")
        )
        await bot.send_photo(
            user_id, item['photo'],
            caption=f"📝 **Name:** {item['name']}\n💰 **Price:** {item['price']}\n📂 **Category:** {item['category']}",
            reply_markup=del_kb
        )

@dp.callback_query_handler(lambda c: c.data.startswith('del_'))
async def delete_item(call: types.CallbackQuery):
    item_id = call.data.replace("del_", "")
    result = await products_col.delete_one({"_id": ObjectId(item_id), "seller_id": call.from_user.id})
    
    if result.deleted_count > 0:
        await call.answer("✅ Item Deleted Successfully!")
        await call.message.delete()
    else:
        await call.answer("❌ Error: Could not delete item.")

# --- ADD PRODUCT LOGIC ---
@dp.callback_query_handler(text="add_item")
async def add_init(call: types.CallbackQuery):
    await AddProduct.waiting_for_category.set()
    await call.message.answer("📁 Choose Asset Category:", reply_markup=category_keyboard())

@dp.callback_query_handler(state=AddProduct.waiting_for_category)
async def add_category(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(category=call.data.replace("cat_", ""))
    await AddProduct.next()
    await call.message.answer("📸 Send a **Screenshot/Photo** of the asset:")

@dp.message_handler(content_types=['photo'], state=AddProduct.waiting_for_photo)
async def add_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await AddProduct.next()
    await message.answer("📝 Enter **Description** (e.g. 5k Channel with OG Email):")

@dp.message_handler(state=AddProduct.waiting_for_name)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await AddProduct.next()
    await message.answer("💰 Enter **Asking Price**:")

@dp.message_handler(state=AddProduct.waiting_for_price)
async def add_final(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await products_col.insert_one({
        "seller_id": message.from_user.id,
        "category": data['category'],
        "photo": data['photo'],
        "name": data['name'],
        "price": message.text
    })
    await message.answer("✅ **Asset Listed!** It is now visible in the marketplace.")
    await state.finish()

# --- MULTI-BOT REGISTRATION ---
def register_handlers(target_dp: Dispatcher):
    target_dp.register_message_handler(cmd_start, commands=['start'], state="*")
    target_dp.register_callback_query_handler(start_cloning, text="clone_start")
    target_dp.register_callback_query_handler(buyer_categories, text="role_buyer")
    target_dp.register_callback_query_handler(seller_home, text="role_seller")
    target_dp.register_callback_query_handler(add_init, text="add_item")
    target_dp.register_callback_query_handler(my_listings, text="my_listings")
    target_dp.register_callback_query_handler(delete_item, lambda c: c.data.startswith('del_'))
    target_dp.register_callback_query_handler(back_to_main, text="back_main")

# --- STARTUP LOGIC ---
async def on_startup(dispatcher: Dispatcher):
    await bot.delete_webhook()
    clones = await clones_col.find().to_list(length=100)
    for c in clones:
        try:
            c_bot = Bot(token=c['token'])
            await c_bot.delete_webhook()
            c_dp = Dispatcher(c_bot, storage=storage)
            register_handlers(c_dp)
            asyncio.create_task(c_dp.start_polling())
            logging.info(f"Bot @{c['username']} is online.")
        except Exception: continue

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    
