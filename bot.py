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

# --- RENDER WEB SERVICE PORT FIX ---
app = Flask('')
@app.route('/')
def home(): 
    return "MarketMaster System is Online!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- CONFIGURATION & DATABASE ---
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

# --- ASSET CATEGORIES ---
CATEGORIES = ["🆔 Telegram IDs", "📢 Channels", "👥 Groups", "📦 Other Assets"]

# --- FINITE STATE MACHINE (FSM) ---
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

# --- UNIVERSAL HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    await message.reply(
        "✨ **Welcome to the Whitelabel Asset Market**\n\nThe most secure platform to trade Telegram IDs, Channels, and Groups.\n\n"
        "Please select your role below:",
        reply_markup=main_menu(), 
        parse_mode="Markdown"
    )

# --- CLONING LOGIC ---
@dp.callback_query_handler(text="clone_start")
async def start_cloning(call: types.CallbackQuery):
    await CloneBot.waiting_for_token.set()
    await call.message.answer(
        "🆕 **Create Your Personal Clone**\n\n"
        "1. Go to @BotFather and create a new bot.\n"
        "2. Copy the **API Token** provided.\n"
        "3. Paste the token here below:"
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
        
        await message.answer(f"✅ **Clone Active!**\nYour bot @{me.username} is now part of the market network.")
        
        # Launch clone instance
        new_dp = Dispatcher(temp_bot, storage=storage)
        register_shared_handlers(new_dp)
        asyncio.create_task(new_dp.start_polling())
        
    except Exception as e:
        await message.answer("❌ **Error:** Invalid Token. Please try again.")
    await state.finish()

# --- BUYER LOGIC (CATEGORY SYSTEM) ---
@dp.callback_query_handler(text="role_buyer")
async def buyer_categories(call: types.CallbackQuery):
    await call.message.edit_text("📂 **Choose a Category to Browse:**", reply_markup=category_keyboard())

@dp.callback_query_handler(lambda c: c.data.startswith('cat_'))
async def show_category_listings(call: types.CallbackQuery):
    selected_cat = call.data.replace("cat_", "")
    items = await products_col.find({"category": selected_cat}).to_list(length=15)
    
    if not items:
        await call.message.answer(f"❌ No listings found in {selected_cat}.")
        return

    for item in items:
        # Build Direct Contact Link
        try:
            seller = await bot.get_chat(item['seller_id'])
            seller_url = f"https://t.me/{seller.username}" if seller.username else f"tg://user?id={item['seller_id']}"
        except:
            seller_url = f"tg://user?id={item['seller_id']}"

        buy_kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🤝 Buy / Contact Seller", url=seller_url)
        )
        
        await bot.send_photo(
            call.from_user.id, item['photo'],
            caption=f"📂 **Category:** {item['category']}\n📦 **Asset:** {item['name']}\n💰 **Price:** {item['price']}",
            reply_markup=buy_kb, 
            parse_mode="Markdown"
        )

# --- SELLER LOGIC ---
@dp.callback_query_handler(text="role_seller")
async def seller_dashboard(call: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("➕ List New Asset", callback_data="add_item"))
    await call.message.edit_text("👨‍💼 **Seller Dashboard**\nPost your Telegram assets for sale:", reply_markup=kb)

@dp.callback_query_handler(text="add_item")
async def product_init(call: types.CallbackQuery):
    await AddProduct.waiting_for_category.set()
    await call.message.answer("📁 Select the **Category** for your asset:", reply_markup=category_keyboard())

@dp.callback_query_handler(state=AddProduct.waiting_for_category)
async def product_cat(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(category=call.data.replace("cat_", ""))
    await AddProduct.next()
    await call.message.answer("📸 Send a **Screenshot/Photo** of the asset:")

@dp.message_handler(content_types=['photo'], state=AddProduct.waiting_for_photo)
async def product_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await AddProduct.next()
    await message.answer("📝 Enter **Description** (e.g., 10k Subs Channel):")

@dp.message_handler(state=AddProduct.waiting_for_name)
async def product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await AddProduct.next()
    await message.answer("💰 Enter your **Asking Price**:")

@dp.message_handler(state=AddProduct.waiting_for_price)
async def product_final(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await products_col.insert_one({
        "seller_id": message.from_user.id,
        "category": data['category'],
        "photo": data['photo'],
        "name": data['name'],
        "price": message.text
    })
    await message.answer("✅ **Success!** Your asset is now live in the global marketplace.")
    await state.finish()

# --- MULTI-INSTANCE REGISTRATION ---
def register_shared_handlers(target_dp: Dispatcher):
    target_dp.register_message_handler(cmd_start, commands=['start'], state="*")
    target_dp.register_callback_query_handler(start_cloning, text="clone_start")
    target_dp.register_callback_query_handler(buyer_categories, text="role_buyer")
    target_dp.register_callback_query_handler(seller_dashboard, text="role_seller")
    target_dp.register_callback_query_handler(product_init, text="add_item")

# --- STARTUP & POLLING ---
async def on_startup(_):
    await bot.delete_webhook()
    # Start all saved clones
    clones = await clones_col.find().to_list(length=100)
    for c in clones:
        try:
            c_bot = Bot(token=c['token'])
            await c_bot.delete_webhook()
            c_dp = Dispatcher(c_bot, storage=storage)
            register_shared_handlers(c_dp)
            asyncio.create_task(c_dp.start_polling())
            logging.info(f"Bot @{c['username']} is running.")
        except: continue

if __name__ == '__main__':
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    
