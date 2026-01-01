# main.py
import asyncio
import logging
from datetime import datetime
from typing import Optional, List
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import os
from dotenv import load_dotenv

from database import db
from keyboards import *


# Category emoji funksiyasini import qilamiz
def get_category_emoji(category: str) -> str:
    """Kategoriya uchun emoji tanlash"""
    category_lower = category.lower()
    emoji_map = {
        'komediya': '😂',
        'comedy': '😂',
        'drama': '🎭',
        'jangari': '⚔️',
        'action': '⚔️',
        'fantastika': '🔮',
        'fantasy': '🔮',
        'sci-fi': '🚀',
        'romantika': '💕',
        'romance': '💕',
        'qoʻrqinchli': '👻',
        'qorqinchli': '👻',
        'horror': '👻',
        'thriller': '😱',
        'detektiv': '🔍',
        'detective': '🔍',
        'sarguzasht': '🗺️',
        'adventure': '🗺️',
        'multfilm': '🎨',
        'cartoon': '🎨',
        'anime': '🎌',
        'serial': '📺',
        'documentary': '📹',
        'sport': '⚽',
        'musical': '🎵',
        'western': '🤠',
        'war': '💣',
        'biography': '📖',
        'history': '📜',
        'crime': '🚨',
        'family': '👨‍👩‍👧‍👦',
        'kids': '👶',
        'bollywood': '🇮🇳',
        'turkish': '🇹🇷',
        'korean': '🇰🇷'
    }

    for key, emoji in emoji_map.items():
        if key in category_lower:
            return emoji

    return '🎬'


# Load .env
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '2008')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '586212504').split(',')))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
bot_username = ""


# ============= STATES =============

class UserState(StatesGroup):
    waiting_code = State()
    waiting_search = State()


class AdminState(StatesGroup):
    waiting_password = State()
    waiting_movie_code = State()
    waiting_movie_title = State()
    waiting_movie_desc = State()
    waiting_movie_category = State()
    waiting_movie_file = State()
    waiting_delete_code = State()
    waiting_broadcast = State()
    waiting_user_id_block = State()
    waiting_user_id_unblock = State()
    waiting_channel_name = State()
    waiting_channel_url = State()
    waiting_channel_type = State()
    waiting_delete_channel = State()
    waiting_user_search = State()
    waiting_add_category = State()
    waiting_delete_category = State()
    waiting_add_admin = State()


# ============= HELPERS =============

async def check_telegram_sub(user_id: int, channel_url: str) -> bool:
    """Telegram kanal obunasini tekshirish"""
    if not channel_url:
        logger.info(f"Kanal URL bo'sh, obuna talab qilinmaydi")
        return True

    try:
        # URL formatni tartibga solish
        username = None

        # URL dan faqat username ni ajratib olish
        if 'https://t.me/' in channel_url:
            username = channel_url.split('https://t.me/')[-1].strip()
        elif 't.me/' in channel_url:
            username = channel_url.split('t.me/')[-1].strip()
        elif channel_url.startswith('@'):
            username = channel_url[1:].strip()
        else:
            username = channel_url.strip()

        # / dan keyingi qismlarni olib tashlash (joinchat, invite linklar uchun)
        if '/' in username:
            username = username.split('/')[0]

        # ? parametrlarni olib tashlash
        if '?' in username:
            username = username.split('?')[0]

        if not username:
            logger.error(f"Noto'g'ri channel format: {channel_url}")
            return True

        # @ qo'shish (agar yo'q bo'lsa)
        if not username.startswith('@'):
            username = f'@{username}'

        logger.info(f"Tekshirilayotgan kanal: {username}, User ID: {user_id}")

        try:
            # Kanal ma'lumotlarini olish
            chat = await bot.get_chat(username)
            logger.info(f"Kanal topildi: {chat.title} (ID: {chat.id})")

            # User obunasini tekshirish
            member = await bot.get_chat_member(chat_id=chat.id, user_id=user_id)
            logger.info(f"User holati: {member.status}")

            # Obuna holatlarini tekshirish
            if member.status in ['left', 'kicked']:
                logger.info(f"User {user_id} kanalga obuna emas")
                return False

            logger.info(f"User {user_id} kanalga obuna: {member.status}")
            return True

        except Exception as e:
            error_msg = str(e).lower()

            if "chat not found" in error_msg:
                logger.error(f"⚠️ Kanal topilmadi: {username}. Iltimos admin kanal linkini tekshiring!")
                # Kanal topilmasa ham davom ettiramiz
                return True

            elif "bot is not a member" in error_msg or "forbidden" in error_msg:
                logger.error(f"⚠️ Bot kanalda admin emas: {username}. Botni kanalga admin qiling!")
                # Bot admin bo'lmasa ham davom ettiramiz
                return True

            elif "user not found" in error_msg:
                logger.error(f"User topilmadi: {user_id}")
                return False

            else:
                logger.error(f"Obuna tekshirish xatosi ({username}): {e}")
                # Boshqa xatolar uchun ham davom ettiramiz
                return True

    except Exception as e:
        logger.error(f"Umumiy xato check_telegram_sub da: {e}")
        return True


async def check_sub(user_id: int) -> tuple[bool, list]:
    """
    Barcha majburiy kanallar uchun obunani tekshirish
    Returns: (is_subscribed, unsubscribed_channels)
    """
    channels = db.get_channels(is_mandatory=True)
    logger.info(f"Majburiy kanallar soni: {len(channels)}")

    if not channels:
        logger.info("Majburiy kanallar yo'q, obuna tekshirilmaydi")
        return True, []

    telegram_channels = [ch for ch in channels if ch.get('channel_type') == 'telegram']
    logger.info(f"Telegram kanallar soni: {len(telegram_channels)}")

    unsubscribed = []

    for ch in telegram_channels:
        url = ch.get('channel_url', '')
        logger.info(f"Kanalni tekshirish: {ch['channel_name']} - {url}")

        if not await check_telegram_sub(user_id, url):
            logger.info(f"User {user_id} kanalga obuna emas: {ch['channel_name']}")
            unsubscribed.append(ch)

    if unsubscribed:
        return False, unsubscribed

    logger.info(f"User {user_id} barcha kanallarga obuna")
    return True, []


def is_admin(user_id: int) -> bool:
    """Admin tekshirish"""
    user = db.get_user(user_id)
    if not user:
        return False
    return user_id in ADMIN_IDS or user.get('is_admin', 0) == 1


def get_categories():
    """Kategoriyalarni olish"""
    cats_str = db.get_setting('movie_categories', '')
    if cats_str:
        return [cat.strip() for cat in cats_str.split(',') if cat.strip()]
    return []


def save_categories(categories):
    """Kategoriyalarni saqlash"""
    db.update_setting('movie_categories', ','.join(categories))


def admin_categories_menu(categories: List[str]) -> ReplyKeyboardMarkup:
    """Admin uchun kategoriya tanlash"""
    kb = ReplyKeyboardBuilder()
    for cat in categories:
        kb.button(text=f"📂 {cat}")
    kb.button(text=f"{E.CANCEL} Bekor Qilish")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


async def send_movie(user_id: int, code: str) -> bool:
    """Kinoni yuborish"""
    movie = db.get_movie(code)
    if not movie:
        return False

    try:
        db.increment_views(code)
    except:
        pass

    title = movie.get('title_uz', 'Noma\'lum')
    desc = movie.get('description_uz', '')
    year = movie.get('year', '')
    views = movie.get('views', 0)
    downloads = movie.get('downloads', 0)
    rating = movie.get('rating', 0)
    category = movie.get('category', '')

    caption = f"""
🎬 <b>{title}</b> {f"({year})" if year else ""}

⭐ Reyting: {rating:.1f}/5.0
👁️ Ko'rishlar: {views:,}
🔥 Yuklanganlar: {downloads:,}

📖 {desc}

🏷️ Kategoriya: {category}
🔑 Kod: <code>{code}</code>

🤖 {bot_username}
    """.strip()

    try:
        file_id = movie.get('file_id')
        is_fav = db.is_favorite(user_id, code)
        kb = movie_actions(code, bot_username.replace('@', ''), is_fav)

        file_type = movie.get('file_type', 'video')

        if file_type == 'photo':
            await bot.send_photo(user_id, file_id, caption=caption, reply_markup=kb)
        else:
            thumbnail = movie.get('thumbnail_id')
            if thumbnail:
                await bot.send_video(user_id, file_id, caption=caption, reply_markup=kb, thumbnail=thumbnail)
            else:
                await bot.send_video(user_id, file_id, caption=caption, reply_markup=kb)

        try:
            db.increment_downloads(code)
            db.update_user_downloads(user_id)
        except:
            pass

        return True
    except Exception as e:
        logger.error(f"Send movie error: {e}")
        return False


async def broadcast(user_ids: list, msg: Message):
    """Reklama yuborish"""
    success = failed = 0

    status = await msg.answer(f"📤 Yuborilmoqda...\n✅ {success} | ❌ {failed}")

    for uid in user_ids:
        try:
            if msg.text:
                await bot.send_message(uid, msg.text)
            elif msg.photo:
                await bot.send_photo(uid, msg.photo[-1].file_id, caption=msg.caption)
            elif msg.video:
                await bot.send_video(uid, msg.video.file_id, caption=msg.caption)

            success += 1
            if success % 10 == 0:
                await status.edit_text(f"📤 Yuborilmoqda...\n✅ {success} | ❌ {failed}")

            await asyncio.sleep(0.05)
        except:
            failed += 1

    return success, failed


# ============= UNIVERSAL HANDLERS =============

@dp.message(F.text == f"{E.CANCEL} Bekor Qilish")
async def cancel_handler(msg: Message, state: FSMContext):
    """Bekor qilish handleri"""
    await state.clear()
    if is_admin(msg.from_user.id):
        await msg.answer("❌ Bekor qilindi", reply_markup=admin_panel())
    else:
        await msg.answer("❌ Bekor qilindi", reply_markup=main_menu())


@dp.message(F.text == f"{E.BACK} Orqaga")
async def back_handler(msg: Message, state: FSMContext):
    """Orqaga handleri"""
    await state.clear()
    if is_admin(msg.from_user.id):
        await msg.answer("📊 Admin panelga qaytdingiz", reply_markup=admin_panel())
    else:
        await msg.answer("🏠 Asosiy menyuga qaytdingiz", reply_markup=main_menu())


# ============= BASIC HANDLERS =============

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    """Start"""
    uid = msg.from_user.id
    db.add_user(uid, msg.from_user.username, msg.from_user.full_name)
    db.update_user_active(uid)

    # Majburiy kanallarni tekshirish
    is_subscribed, unsubscribed_channels = await check_sub(uid)

    if not is_subscribed and unsubscribed_channels:
        all_channels = db.get_channels(is_mandatory=True)
        await msg.answer(
            "📢 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
            "Obuna bo'lgach, <b>'✅ Obunani Tekshirish'</b> tugmasini bosing.",
            reply_markup=channels_sub(all_channels)
        )
        return

    await msg.answer(
        f"🎬 <b>Cinema Botga xush kelibsiz!</b>\n\n"
        f"Kino kodini yuboring yoki menyudan tanlang.",
        reply_markup=main_menu()
    )


@dp.message(Command("admin"))
async def cmd_admin(msg: Message, state: FSMContext):
    """Admin panel"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    if not is_admin(uid):
        await msg.answer("❌ Siz admin emassiz!")
        return

    user = db.get_user(uid)
    if user and user.get('is_admin'):
        stats = db.get_statistics()
        await msg.answer(
            f"📊 <b>ADMIN PANEL</b>\n\n"
            f"👥 Userlar: {stats['total_users']:,}\n"
            f"🎬 Kinolar: {stats['total_movies']:,}\n"
            f"🔥 Yuklanganlar: {stats['total_downloads']:,}\n"
            f"📢 Kanallar: {stats['mandatory_channels']:,}",
            reply_markup=admin_panel()
        )
        return

    await msg.answer("🔐 Parolni kiriting:", reply_markup=cancel())
    await state.set_state(AdminState.waiting_password)


@dp.message(Command("help"))
async def cmd_help(msg: Message):
    """Yordam"""
    uid = msg.from_user.id
    db.update_user_active(uid)
    await msg.answer(
        f"🤖 <b>CINEMA BOT YORDAM</b>\n\n"
        f"🔑 Kino kodini yuboring va kinoni oling\n"
        f"🔍 Qidirish: nomi bo'yicha\n"
        f"🏆 Top 10 kinolar\n"
        f"🏷️ Kategoriyalar\n"
        f"❤️ Sevimli kinolar\n\n"
        f"👑 Admin: /admin\n"
        f"📞 Aloqa: @mirzayyevv"
    )


@dp.message(Command("channels"))
async def check_channels_list(msg: Message):
    """Kanallar ro'yxatini ko'rish"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    channels = db.get_channels(is_mandatory=True)
    if not channels:
        await msg.answer("❌ Majburiy kanallar yo'q.")
        return

    text = "📋 <b>MAJBURIY KANALLAR</b>\n\n"
    for i, ch in enumerate(channels, 1):
        text += f"{i}. <b>{ch['channel_name']}</b>\n"
        text += f"   🔗 {ch['channel_url']}\n"
        text += f"   📱 {ch['channel_type']}\n"
        text += f"   ID: {ch['id']}\n\n"

    await msg.answer(text)


# ============= USER HANDLERS =============

@dp.message(F.text == f"{E.MOVIE} Kino Kodini Yuboring")
async def request_code(msg: Message, state: FSMContext):
    """Kod so'rash"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    # Obunani tekshirish
    is_subscribed, unsubscribed_channels = await check_sub(uid)
    if not is_subscribed:
        all_channels = db.get_channels(is_mandatory=True)
        await msg.answer(
            "❌ <b>Avval kanallarga obuna bo'ling!</b>",
            reply_markup=channels_sub(all_channels)
        )
        return

    await msg.answer("🎬 Kino kodini yuboring:", reply_markup=cancel())
    await state.set_state(UserState.waiting_code)


@dp.message(UserState.waiting_code)
async def handle_code(msg: Message, state: FSMContext):
    """Kodni qabul qilish"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    # Obunani tekshirish
    is_subscribed, unsubscribed_channels = await check_sub(uid)
    if not is_subscribed:
        all_channels = db.get_channels(is_mandatory=True)
        await msg.answer(
            "❌ <b>Avval kanallarga obuna bo'ling!</b>",
            reply_markup=channels_sub(all_channels)
        )
        await state.clear()
        return

    code = msg.text.strip().upper()
    movie = db.get_movie(code)

    if not movie:
        parts = db.get_movie_parts(code)
        if parts:
            await msg.answer(
                f"🎬 Bu kodda {len(parts)} ta qism mavjud:",
                reply_markup=movie_parts(code, parts)
            )
        else:
            await msg.answer("❌ Kod topilmadi. Qaytadan kiriting.")
        await state.clear()
        return

    if await send_movie(uid, code):
        await state.clear()
    else:
        await msg.answer("❌ Kino yuborishda xato yuz berdi.")
        await state.clear()


@dp.message(F.text == f"{E.SEARCH} Qidirish")
async def search_menu(msg: Message, state: FSMContext):
    """Qidiruv"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    # Obunani tekshirish
    is_subscribed, unsubscribed_channels = await check_sub(uid)
    if not is_subscribed:
        all_channels = db.get_channels(is_mandatory=True)
        await msg.answer(
            "❌ <b>Avval kanallarga obuna bo'ling!</b>",
            reply_markup=channels_sub(all_channels)
        )
        return

    await msg.answer("🔍 Kino nomini kiriting:", reply_markup=cancel())
    await state.set_state(UserState.waiting_search)


@dp.message(UserState.waiting_search)
async def handle_search(msg: Message, state: FSMContext):
    """Qidiruvni bajarish"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    query = msg.text
    movies, total = db.search_movies(query, limit=10, offset=0)

    if not movies:
        await msg.answer("❌ Hech narsa topilmadi")
        await state.clear()
        return

    total_pages = max(1, (total + 9) // 10)

    text = f"🔍 <b>QIDIRUV NATIJALARI</b> ({total} ta)\n\n"
    for i, m in enumerate(movies, 1):
        text += f"{i}. <b>{m['title_uz']}</b>\n"
        text += f"   🔑 <code>{m['code']}</code> | 👁️ {m['views']:,}\n\n"

    await msg.answer(text, reply_markup=movie_list(movies, page=1, total_pages=total_pages, query=query))
    await state.clear()


@dp.message(F.text == f"{E.TOP} Top Kinolar")
async def top_movies(msg: Message):
    """Top kinolar"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    # Obunani tekshirish
    is_subscribed, unsubscribed_channels = await check_sub(uid)
    if not is_subscribed:
        all_channels = db.get_channels(is_mandatory=True)
        await msg.answer(
            "❌ <b>Avval kanallarga obuna bo'ling!</b>",
            reply_markup=channels_sub(all_channels)
        )
        return

    movies = db.get_top_movies(10)

    if not movies:
        await msg.answer(
            "🎬 <b>Kinolar hali mavjud emas</b>\n\n"
            "Admin tez orada kinolar qo'shadi.",
            reply_markup=main_menu()
        )
        return

    text = "🏆 <b>TOP 10 ENG MASHHUR KINOLAR</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━\n\n"

    medals = ["🥇", "🥈", "🥉"]
    for i, m in enumerate(movies, 1):
        medal = medals[i - 1] if i <= 3 else f"{i}."
        text += f"{medal} <b>{m['title_uz']}</b>\n"
        text += f"    ⭐ {m['rating']:.1f}/5.0 • 👁️ {m['views']:,}\n"
        text += f"    🔑 <code>{m['code']}</code>\n\n"

    text += "━━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 Jami: {len(movies)} ta kino"

    await msg.answer(text)


@dp.message(F.text == f"{E.CAT} Kategoriyalar")
async def categories(msg: Message):
    """Kategoriyalar"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    # Obunani tekshirish
    is_subscribed, unsubscribed_channels = await check_sub(uid)
    if not is_subscribed:
        all_channels = db.get_channels(is_mandatory=True)
        await msg.answer(
            "❌ <b>Avval kanallarga obuna bo'ling!</b>",
            reply_markup=channels_sub(all_channels)
        )
        return

    cats = get_categories()

    if not cats:
        await msg.answer(
            "📂 <b>Kategoriyalar hali mavjud emas</b>\n\n"
            "Admin tez orada kategoriyalar qo'shadi.",
            reply_markup=main_menu()
        )
        return

    await msg.answer(
        "🎬 <b>KINO KATEGORIYALARI</b>\n\n"
        "Quyidagi kategoriyalardan birini tanlang:",
        reply_markup=categories_menu(cats)
    )


@dp.message(F.text.regexp(r'^(😂|🎭|⚔️|🔮|💕|👻|😱|🔍|🗺️|🎨|🎌|📺|🎬)'))
async def category_movies(msg: Message):
    """Kategoriya kinolari"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    # Emojilarni olib tashlash
    cat = msg.text
    for emoji in ['😂', '🎭', '⚔️', '🔮', '💕', '👻', '😱', '🔍', '🗺️', '🎨', '🎌', '📺', '🎬', '🏷️']:
        cat = cat.replace(emoji, '').strip()

    movies = db.get_movies_by_category(cat, 10)

    if not movies:
        # Kategoriya bo'yicha chiroyli xabar
        emoji = get_category_emoji(cat)
        await msg.answer(
            f"{emoji} <b>{cat.upper()}</b>\n\n"
            f"❌ Bu kategoriyada hozircha kinolar yo'q.\n\n"
            f"💡 Boshqa kategoriyalarni sinab ko'ring yoki admin kinolar qo'shishini kuting.",
            reply_markup=categories_menu(get_categories())
        )
        return

    emoji = get_category_emoji(cat)
    text = f"{emoji} <b>{cat.upper()}</b>\n\n"
    text += f"📊 Jami: {len(movies)} ta kino\n\n"

    for i, m in enumerate(movies, 1):
        text += f"{i}. 🎬 <b>{m['title_uz']}</b>\n"
        text += f"   🔑 <code>{m['code']}</code>\n"
        text += f"   ⭐ {m['rating']:.1f} | 👁️ {m['views']:,}\n\n"

    await msg.answer(text, reply_markup=movie_list(movies))


@dp.message(F.text == f"{E.FAV} Sevimlilarim")
async def favorites(msg: Message):
    """Sevimlilar"""
    uid = msg.from_user.id
    db.update_user_active(uid)
    favs = db.get_favorites(uid)

    if not favs:
        await msg.answer(
            "❤️ <b>Sevimli kinolar yo'q</b>\n\n"
            "💡 Kino sahifasida ❤️ tugmasini bosib, sevimli kinolaringizni saqlang!",
            reply_markup=main_menu()
        )
        return

    text = "❤️ <b>SEVIMLI KINOLAR</b>\n\n"
    text += f"📊 Jami: {len(favs)} ta\n\n"
    text += "━━━━━━━━━━━━━━━━━━━\n\n"

    for i, m in enumerate(favs[:10], 1):
        text += f"{i}. 🎬 <b>{m['title_uz']}</b>\n"
        text += f"    🔑 <code>{m['code']}</code>\n"
        text += f"    ⭐ {m['rating']:.1f} • 👁️ {m['views']:,}\n\n"

    if len(favs) > 10:
        text += f"... va yana {len(favs) - 10} ta kino"

    await msg.answer(text, reply_markup=movie_list(favs[:10]))


@dp.message(F.text == f"{E.DOWN} Yuklaganlarim")
async def downloads(msg: Message):
    """Yuklaganlar"""
    uid = msg.from_user.id
    db.update_user_active(uid)
    user = db.get_user(uid)
    count = user.get('total_downloads', 0) if user else 0
    await msg.answer(f"🔥 Siz <b>{count}</b> ta kino yuklagansiz")


@dp.message(F.text == f"{E.PROF} Profil")
async def profile(msg: Message):
    """Profil"""
    uid = msg.from_user.id
    db.update_user_active(uid)
    user = db.get_user(uid)
    if not user:
        await msg.answer("❌ Profil topilmadi")
        return

    join = datetime.fromtimestamp(user.get('join_date', 0)).strftime('%d.%m.%Y')

    # Status icon
    if user.get('is_premium'):
        status = "⭐ PREMIUM"
    elif user.get('is_blocked'):
        status = "🚫 BLOKLANGAN"
    else:
        status = "✅ FAOL"

    full_name = user.get('full_name', "Noma'lum")
    username = user.get('username', 'yoq')
    downloads = user.get('total_downloads', 0)

    text = f"""
👤 <b>MENING PROFILIM</b>

━━━━━━━━━━━━━━━━━━━

🆔 ID: <code>{user['user_id']}</code>
👤 Ism: {full_name}
📱 Username: @{username}
📅 Qo'shilgan: {join}
📊 Status: {status}

━━━━━━━━━━━━━━━━━━━

📈 <b>STATISTIKA</b>

🎬 Yuklaganlar: {downloads} ta
❤️ Sevimlilar: {len(db.get_favorites(uid))} ta

━━━━━━━━━━━━━━━━━━━

🤖 {bot_username}
    """.strip()

    await msg.answer(text)


@dp.message(F.text == f"{E.INFO} Ma'lumot")
async def info(msg: Message):
    """Ma'lumot"""
    uid = msg.from_user.id
    db.update_user_active(uid)
    await msg.answer(
        f"🎬 <b>CINEMA BOT</b>\n\n"
        f"✨ Kinolarni kodlar orqali yuklab oling\n"
        f"🔍 Qidiruv va top kinolar\n"
        f"❤️ Sevimli kinolar ro'yxati\n\n"
        f"👑 Admin: @mirzayyevv\n"
        f"🤖 {bot_username}"
    )


# ============= CALLBACK HANDLERS =============

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery):
    """Obunani tekshirish"""
    uid = call.from_user.id
    db.update_user_active(uid)

    is_subscribed, unsubscribed_channels = await check_sub(uid)

    if is_subscribed:
        await call.message.delete()
        await call.message.answer(
            "✅ <b>Obuna tasdiqlandi!</b>\n\n"
            "🎬 Botdan foydalanishingiz mumkin!\n"
            "Kino kodini yuboring:",
            reply_markup=main_menu()
        )
    else:
        # Qaysi kanallarga obuna bo'lmagan
        not_subscribed_text = "\n".join([f"• {ch['channel_name']}" for ch in unsubscribed_channels])
        await call.answer(
            f"❌ Siz quyidagi kanallarga obuna bo'lmagansiz:\n\n{not_subscribed_text}\n\n"
            "Iltimos, barcha kanallarga obuna bo'lib, qaytadan tekshiring.",
            show_alert=True
        )


@dp.callback_query(F.data.startswith("fav_"))
async def toggle_fav(call: CallbackQuery):
    """Sevimli qo'shish/o'chirish"""
    uid = call.from_user.id
    db.update_user_active(uid)

    code = call.data.split("_")[1]

    if db.is_favorite(uid, code):
        db.remove_favorite(uid, code)
        await call.answer("❤️ Sevimlilardan o'chirildi")
    else:
        db.add_favorite(uid, code)
        await call.answer("❤️ Sevimlilarga qo'shildi")

    is_fav = db.is_favorite(uid, code)
    kb = movie_actions(code, bot_username.replace('@', ''), is_fav)
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except:
        pass


@dp.callback_query(F.data.startswith("dl_"))
async def download_movie(call: CallbackQuery):
    """Kino yuklab olish"""
    uid = call.from_user.id
    db.update_user_active(uid)

    code = call.data.split("_")[1]
    await send_movie(uid, code)
    await call.answer("🔥 Kino yuborildi!")


@dp.callback_query(F.data.startswith("share_"))
async def share_movie(call: CallbackQuery):
    """Kino ulashish"""
    uid = call.from_user.id
    db.update_user_active(uid)

    code = call.data.split("_")[1]
    share_text = f"🎬 Kino kodi: {code}\n🤖 {bot_username}"
    await call.answer(f"Ulashish matni:\n\n{share_text}", show_alert=True)


@dp.callback_query(F.data.startswith("rate_"))
async def rate_movie(call: CallbackQuery):
    """Reyting berish"""
    uid = call.from_user.id
    db.update_user_active(uid)

    code = call.data.split("_")[1]
    await call.message.answer("⭐ Reytingni tanlang:", reply_markup=rating(code))


@dp.callback_query(F.data.startswith("r_"))
async def handle_rating(call: CallbackQuery):
    """Reytingni qabul qilish"""
    uid = call.from_user.id
    db.update_user_active(uid)

    _, rate, code = call.data.split("_")

    if db.add_rating(uid, code, int(rate)):
        await call.message.delete()
        await call.answer(f"✅ {rate} ⭐ reyting berildi!", show_alert=True)
    else:
        await call.answer("❌ Xato yuz berdi", show_alert=True)


@dp.callback_query(F.data == "cancel_rate")
async def cancel_rating(call: CallbackQuery):
    """Reytingni bekor qilish"""
    uid = call.from_user.id
    db.update_user_active(uid)

    await call.message.delete()
    await call.answer("❌ Reyting bekor qilindi")


@dp.callback_query(F.data.startswith("movie_"))
async def send_movie_callback(call: CallbackQuery):
    """Kino callback"""
    uid = call.from_user.id
    db.update_user_active(uid)

    code = call.data.split("_")[1]
    await send_movie(uid, code)
    await call.answer()


@dp.callback_query(F.data.startswith("part_"))
async def send_part(call: CallbackQuery):
    """Kino qismini yuborish"""
    uid = call.from_user.id
    db.update_user_active(uid)

    _, code, num = call.data.split("_")
    parts = db.get_movie_parts(code)

    part = next((p for p in parts if p['part_number'] == int(num)), None)
    if not part:
        await call.answer("❌ Qism topilmadi")
        return

    try:
        await bot.send_video(
            uid,
            part['file_id'],
            caption=f"🎬 {code} - Qism {num}\n\n🤖 {bot_username}"
        )
        await call.answer("✅ Yuborildi")
    except Exception as e:
        await call.answer("❌ Yuborishda xato", show_alert=True)
        logger.error(f"Send part error: {e}")


@dp.callback_query(F.data.startswith("back_to_movie_"))
async def back_to_movie(call: CallbackQuery):
    """Kinoga qaytish"""
    uid = call.from_user.id
    db.update_user_active(uid)

    code = call.data.split("_")[3]
    await send_movie(uid, code)


@dp.callback_query(F.data.startswith("page_"))
async def pagination_handler(call: CallbackQuery):
    """Sahifalash"""
    uid = call.from_user.id
    db.update_user_active(uid)

    _, page, query = call.data.split("_")
    page = int(page)

    if query == "":
        movies, total = db.get_all_movies(limit=10, offset=(page - 1) * 10)
    else:
        movies, total = db.search_movies(query, limit=10, offset=(page - 1) * 10)

    total_pages = max(1, (total + 9) // 10)

    if not movies:
        await call.answer("❌ Hech narsa topilmadi", show_alert=True)
        return

    text = f"📋 <b>KINOLAR</b> (Sahifa {page}/{total_pages})\n\n"
    for i, m in enumerate(movies, 1):
        text += f"{i}. <b>{m['title_uz']}</b>\n"
        text += f"   🔑 <code>{m['code']}</code> | 👁️ {m['views']:,}\n\n"

    try:
        await call.message.edit_text(text,
                                     reply_markup=movie_list(movies, page=page, total_pages=total_pages, query=query))
    except:
        await call.answer("✅ Yangilandi")


@dp.callback_query(F.data == "back_main")
async def back_to_main(call: CallbackQuery):
    """Asosiy menyuga qaytish"""
    uid = call.from_user.id
    db.update_user_active(uid)

    await call.message.delete()
    await call.message.answer("🏠 Asosiy menyu:", reply_markup=main_menu())


@dp.callback_query(F.data == "close")
async def close_message(call: CallbackQuery):
    """Xabarni yopish"""
    uid = call.from_user.id
    db.update_user_active(uid)

    await call.message.delete()


# ============= ADMIN HANDLERS =============

@dp.message(AdminState.waiting_password)
async def admin_password(msg: Message, state: FSMContext):
    """Admin paroli"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    if msg.text == ADMIN_PASSWORD:
        with db.get_connection() as conn:
            conn.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (uid,))
            conn.commit()

        stats = db.get_statistics()
        await msg.answer(
            f"✅ Xush kelibsiz, Admin!\n\n"
            f"📊 Statistika:\n"
            f"👥 Userlar: {stats['total_users']:,}\n"
            f"🎬 Kinolar: {stats['total_movies']:,}",
            reply_markup=admin_panel()
        )
        await state.clear()
    else:
        await msg.answer("❌ Noto'g'ri parol!")


@dp.message(F.text == "👑 Adminlar")
async def admin_management(msg: Message):
    """Admin boshqaruv"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    with db.get_connection() as conn:
        rows = conn.execute('''
            SELECT user_id, username, full_name 
            FROM users 
            WHERE is_admin = 1 
            ORDER BY user_id
        ''').fetchall()

    admins = [dict(row) for row in rows]

    text = "👑 <b>ADMINLAR BOSHQARUVI</b>\n\n"
    if admins:
        for i, admin in enumerate(admins, 1):
            text += f"{i}. ID: <code>{admin['user_id']}</code>\n"
            text += f"   👤 {admin.get('full_name', 'Nomalum')}\n"
            text += f"   📱 @{admin.get('username', 'yoq')}\n\n"
    else:
        text += "❌ Adminlar topilmadi\n\n"

    text += "Tanlang:"

    kb = ReplyKeyboardBuilder()
    kb.button(text="➕ Admin Qo'shish")
    if admins and len(admins) > 1:
        kb.button(text="🗑️ Admin O'chirish")
    kb.button(text=f"{E.BACK} Orqaga")
    kb.adjust(2, 1)

    await msg.answer(text, reply_markup=kb.as_markup(resize_keyboard=True))


@dp.message(F.text == "➕ Admin Qo'shish")
async def add_admin_start(msg: Message, state: FSMContext):
    """Yangi admin qo'shish"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    await msg.answer(
        "➕ <b>YANGI ADMIN QO'SHISH</b>\n\n"
        "Yangi admin qo'shmoqchi bo'lgan userning:\n"
        "1. User ID raqamini yoki\n"
        "2. Username ni (@ belgisiz) yoki\n"
        "3. Ismini yozing:\n\n"
        "<i>Masalan: 123456789 yoki username yoki Ism Familya</i>",
        reply_markup=cancel()
    )
    await state.set_state(AdminState.waiting_add_admin)


@dp.message(AdminState.waiting_add_admin)
async def add_admin_handler(msg: Message, state: FSMContext):
    """Admin qo'shishni qayta ishlash"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    query = msg.text.strip()

    if query.isdigit():
        target_id = int(query)
        user = db.get_user(target_id)

        if not user:
            await msg.answer(f"❌ User topilmadi (ID: {target_id})")
            await state.clear()
            return

        with db.get_connection() as conn:
            conn.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (target_id,))
            conn.commit()

        await msg.answer(
            f"✅ User admin qilindi!\n\n"
            f"🆔 ID: <code>{target_id}</code>\n"
            f"👤 Ism: {user.get('full_name', 'Nomalum')}\n"
            f"📱 Username: @{user.get('username', 'yoq')}",
            reply_markup=admin_panel()
        )

        try:
            await bot.send_message(
                target_id,
                f"🎉 Tabriklaymiz!\n\n"
                f"Siz <b>{bot_username}</b> botida admin huquqlariga ega bo'ldingiz!\n\n"
                f"Admin panelga kirish uchun /admin buyrug'ini yuboring."
            )
        except:
            pass

    else:
        users = db.search_users(query)

        if not users:
            await msg.answer(f"❌ '{query}' bo'yicha user topilmadi")
            await state.clear()
            return

        if len(users) == 1:
            user = users[0]
            target_id = user['user_id']

            with db.get_connection() as conn:
                conn.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (target_id,))
                conn.commit()

            await msg.answer(
                f"✅ User admin qilindi!\n\n"
                f"🆔 ID: <code>{target_id}</code>\n"
                f"👤 Ism: {user.get('full_name', 'Nomalum')}\n"
                f"📱 Username: @{user.get('username', 'yoq')}",
                reply_markup=admin_panel()
            )

            try:
                await bot.send_message(
                    target_id,
                    f"🎉 Tabriklaymiz!\n\n"
                    f"Siz <b>{bot_username}</b> botida admin huquqlariga ega bo'ldingiz!\n\n"
                    f"Admin panelga kirish uchun /admin buyrug'ini yuboring."
                )
            except:
                pass

        else:
            text = f"🔍 <b>'{query}' bo'yicha topilgan userlar</b> ({len(users)} ta)\n\n"
            for i, user in enumerate(users[:5], 1):
                text += f"{i}. ID: <code>{user['user_id']}</code>\n"
                text += f"   👤 {user.get('full_name', 'Nomalum')}\n"
                text += f"   📱 @{user.get('username', 'yoq')}\n\n"

            text += "Admin qilish uchun user ID raqamini yuboring:"

            await msg.answer(text, reply_markup=cancel())
            await state.update_data(admin_search_results=users)

    await state.clear()


# Admin panel keyboardini yangilash
def admin_panel() -> ReplyKeyboardMarkup:
    """Admin panel"""
    kb = ReplyKeyboardBuilder()
    kb.button(text=f"{E.ADD} Kino Qo'shish")
    kb.button(text=f"{E.DEL} Kino O'chirish")
    kb.button(text=f"{E.LIST} Kinolar")
    kb.button(text=f"{E.STATS} Statistika")
    kb.button(text=f"{E.USERS} Userlar")
    kb.button(text=f"{E.CHAN} Kanallar")
    kb.button(text=f"{E.MSG} Reklama")
    kb.button(text="👑 Adminlar")
    kb.button(text=f"{E.HOME} Chiqish")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


# Qolgan admin handlerlar davom etadi...
# [Previous admin handlers continue here - kino qo'shish, o'chirish, va hokazo]
# ============= QOLGAN ADMIN HANDLERS =============

@dp.message(F.text == f"{E.ADD} Kino Qo'shish")
async def add_movie_start(msg: Message, state: FSMContext):
    """Kino qo'shish"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    cats = get_categories()
    if not cats:
        await msg.answer("❌ Avval kategoriya qo'shing!", reply_markup=admin_panel())
        return

    await msg.answer("📝 Kino kodini kiriting:", reply_markup=cancel())
    await state.set_state(AdminState.waiting_movie_code)


@dp.message(AdminState.waiting_movie_code)
async def movie_code_input(msg: Message, state: FSMContext):
    """Kino kodi"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    code = msg.text.strip().upper()
    if db.get_movie(code):
        await msg.answer("❌ Bu kod mavjud!")
        return

    await state.update_data(code=code)
    await msg.answer("📝 Kino nomini kiriting:")
    await state.set_state(AdminState.waiting_movie_title)


@dp.message(AdminState.waiting_movie_title)
async def movie_title_input(msg: Message, state: FSMContext):
    """Kino nomi"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    await state.update_data(title=msg.text)
    await msg.answer("📖 Tavsifini kiriting:")
    await state.set_state(AdminState.waiting_movie_desc)


@dp.message(AdminState.waiting_movie_desc)
async def movie_desc_input(msg: Message, state: FSMContext):
    """Tavsif"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    await state.update_data(desc=msg.text)

    cats = get_categories()
    await msg.answer("🏷️ Kino qaysi kategoriyaga tegishli?", reply_markup=admin_categories_menu(cats))
    await state.set_state(AdminState.waiting_movie_category)


@dp.message(AdminState.waiting_movie_category)
async def movie_cat_input(msg: Message, state: FSMContext):
    """Kino qo'shishda kategoriya tanlash"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    if msg.text == f"{E.CANCEL} Bekor Qilish":
        await state.clear()
        await msg.answer("❌ Bekor qilindi", reply_markup=admin_panel())
        return

    if msg.text.startswith("📂 "):
        cat = msg.text.replace("📂 ", "")
    else:
        cat = msg.text

    cats = get_categories()
    if cat not in cats:
        cats.append(cat)
        save_categories(cats)
        logger.info(f"Yangi kategoriya qo'shildi: {cat}")

    await state.update_data(category=cat)
    await msg.answer(f"✅ Kategoriya tanlandi: <b>{cat}</b>\n\n🎥 Endi kino faylini yuboring:")
    await state.set_state(AdminState.waiting_movie_file)


@dp.message(AdminState.waiting_movie_file)
async def movie_file_input(msg: Message, state: FSMContext):
    """Kino fayli"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    data = await state.get_data()
    category = data.get('category')

    if not category:
        await msg.answer("❌ Kategoriya tanlanmagan! Qaytadan boshlang.", reply_markup=admin_panel())
        await state.clear()
        return

    file_id = None
    file_type = "video"
    thumbnail = None

    if msg.video:
        file_id = msg.video.file_id
        file_type = "video"
        if msg.video.thumbnail:
            thumbnail = msg.video.thumbnail.file_id
    elif msg.photo:
        file_id = msg.photo[-1].file_id
        file_type = "photo"
        thumbnail = file_id
    elif msg.document:
        file_id = msg.document.file_id
        file_type = "document"

    if not file_id:
        await msg.answer("❌ Video, rasm yoki fayl yuboring!")
        return

    code = data.get('code', '').upper()
    title = data.get('title', '')
    desc = data.get('desc', '')

    if not all([code, title, desc, category]):
        await msg.answer("❌ Ma'lumotlar to'liq emas! Qaytadan boshlang.", reply_markup=admin_panel())
        await state.clear()
        return

    if db.add_movie(
            code=code,
            title=title,
            description=desc,
            file_id=file_id,
            category=category,
            added_by=uid,
            file_type=file_type,
            thumbnail=thumbnail
    ):
        await msg.answer(
            f"✅ Kino qo'shildi!\n\n"
            f"🔑 Kod: <code>{code}</code>\n"
            f"🎬 Nom: {title}\n"
            f"🏷️ Kategoriya: {category}\n"
            f"📁 Turi: {'🎬 Video' if file_type == 'video' else '🖼️ Rasm' if file_type == 'photo' else '📄 Fayl'}",
            reply_markup=admin_panel()
        )
    else:
        await msg.answer("❌ Xato yuz berdi! Kino qo'shilmadi.", reply_markup=admin_panel())

    await state.clear()


@dp.message(F.text == f"{E.DEL} Kino O'chirish")
async def delete_movie_start(msg: Message, state: FSMContext):
    """Kino o'chirish"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    await msg.answer("🗑️ O'chirish uchun kodni kiriting:", reply_markup=cancel())
    await state.set_state(AdminState.waiting_delete_code)


@dp.message(AdminState.waiting_delete_code)
async def delete_movie_code(msg: Message, state: FSMContext):
    """Kino o'chirish kodi"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    code = msg.text.strip().upper()
    if db.get_movie(code):
        db.delete_movie(code)
        await msg.answer(f"✅ Kino o'chirildi: <code>{code}</code>", reply_markup=admin_panel())
    else:
        await msg.answer("❌ Kod topilmadi!", reply_markup=admin_panel())

    await state.clear()


@dp.message(F.text == f"{E.LIST} Kinolar")
async def list_movies(msg: Message):
    """Kinolar ro'yxati"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    movies, total = db.get_all_movies(limit=10)
    total_pages = max(1, (total + 9) // 10)

    if not movies:
        await msg.answer("📋 Kinolar yo'q")
        return

    text = "🎬 <b>KINOLAR</b>\n\n"
    for i, m in enumerate(movies, 1):
        text += f"{i}. <b>{m['title_uz']}</b>\n"
        text += f"   🔑 <code>{m['code']}</code> | 👁️ {m['views']:,}\n\n"

    await msg.answer(text, reply_markup=movie_list(movies, page=1, total_pages=total_pages))


@dp.message(F.text == f"{E.STATS} Statistika")
async def statistics(msg: Message):
    """Statistika"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    stats = db.get_statistics()
    text = f"""
📊 <b>STATISTIKA</b>

👥 USERLAR:
├── Jami: {stats['total_users']:,}
├── Faol: {stats['active_users']:,}
├── Bloklangan: {stats['blocked_users']:,}
└── Premium: {stats['premium_users']:,}

🎬 KINOLAR:
├── Jami: {stats['total_movies']:,}
└── Yuklanganlar: {stats['total_downloads']:,}

📢 KANALLAR: {stats['mandatory_channels']:,}

📈 BUGUN:
├── Yangi userlar: {stats['today_new_users']:,}
└── Faol userlar: {stats['today_active_users']:,}
    """.strip()

    await msg.answer(text)


@dp.message(F.text == f"{E.USERS} Userlar")
async def users_menu(msg: Message):
    """User boshqaruv"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    await msg.answer("👥 User boshqaruv:", reply_markup=user_management())


@dp.message(F.text == "🚫 Bloklash")
async def block_user_start(msg: Message, state: FSMContext):
    """User bloklash"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    await msg.answer("🚫 Bloklash uchun user ID kiriting:", reply_markup=cancel())
    await state.set_state(AdminState.waiting_user_id_block)


@dp.message(AdminState.waiting_user_id_block)
async def block_user_id(msg: Message, state: FSMContext):
    """User ID bloklash"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    try:
        target_uid = int(msg.text)
        if db.get_user(target_uid):
            db.block_user(target_uid)
            await msg.answer(f"✅ User bloklandi: {target_uid}", reply_markup=user_management())
            try:
                await bot.send_message(target_uid, "❌ Siz admin tomonidan bloklandingiz.")
            except:
                pass
        else:
            await msg.answer("❌ User topilmadi!")
    except ValueError:
        await msg.answer("❌ Noto'g'ri ID!")

    await state.clear()


@dp.message(F.text == "🔓 Blokdan Chiqarish")
async def unblock_user_start(msg: Message, state: FSMContext):
    """Blokdan chiqarish"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    await msg.answer("🔓 Blokdan chiqarish uchun user ID:", reply_markup=cancel())
    await state.set_state(AdminState.waiting_user_id_unblock)


@dp.message(AdminState.waiting_user_id_unblock)
async def unblock_user_id(msg: Message, state: FSMContext):
    """User ID blokdan chiqarish"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    try:
        target_uid = int(msg.text)
        if db.get_user(target_uid):
            db.unblock_user(target_uid)
            await msg.answer(f"✅ Blokdan chiqarildi: {target_uid}", reply_markup=user_management())
            try:
                await bot.send_message(target_uid, "✅ Siz blokdan chiqarildingiz.")
            except:
                pass
        else:
            await msg.answer("❌ User topilmadi!")
    except ValueError:
        await msg.answer("❌ Noto'g'ri ID!")

    await state.clear()


@dp.message(F.text == f"{E.SEARCH} User Qidirish")
async def search_user_start(msg: Message, state: FSMContext):
    """User qidirish"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    await msg.answer("🔍 User ID, username yoki ismini kiriting:", reply_markup=cancel())
    await state.set_state(AdminState.waiting_user_search)


@dp.message(AdminState.waiting_user_search)
async def search_user_handler(msg: Message, state: FSMContext):
    """User qidiruv"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    users = db.search_users(msg.text)

    if not users:
        await msg.answer("❌ User topilmadi!")
        await state.clear()
        return

    text = f"🔍 <b>QIDIRUV NATIJALARI</b> ({len(users)} ta)\n\n"
    for user in users[:10]:
        status = "🚫" if user['is_blocked'] else "✅"
        full_name = user.get('full_name', "Noma'lum")
        username = user.get('username', 'yoq')

        text += f"{status} ID: <code>{user['user_id']}</code>\n"
        text += f"   👤 {full_name}\n"
        text += f"   📱 @{username}\n"
        text += f"   📥 {user.get('total_downloads', 0)} ta\n\n"

    await msg.answer(text, reply_markup=user_management())
    await state.clear()


@dp.message(F.text == f"{E.LIST} Barcha Userlar")
async def all_users(msg: Message):
    """Barcha userlar"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    users = db.get_users_list(limit=20)

    if not users:
        await msg.answer("👥 Userlar yo'q")
        return

    text = "👥 <b>BARCHA USERLAR</b>\n\n"
    for i, user in enumerate(users, 1):
        status = "🚫" if user['is_blocked'] else "✅"
        full_name = user.get('full_name', "Noma'lum")[:15]

        text += f"{i}. {status} <code>{user['user_id']}</code>\n"
        text += f"   👤 {full_name}\n"
        text += f"   📥 {user.get('total_downloads', 0)} ta\n\n"

    await msg.answer(text)


@dp.message(F.text == f"{E.CHAN} Kanallar")
async def channels_menu(msg: Message):
    """Kanallar menyusi"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    await msg.answer("📢 Kanallar boshqaruv:", reply_markup=channels_management())


@dp.message(F.text == f"{E.ADD} Kanal Qo'shish")
async def add_channel_start(msg: Message, state: FSMContext):
    """Kanal qo'shish"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    await msg.answer("📝 Kanal nomini kiriting:", reply_markup=cancel())
    await state.set_state(AdminState.waiting_channel_name)


@dp.message(AdminState.waiting_channel_name)
async def channel_name_input(msg: Message, state: FSMContext):
    """Kanal nomi"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    await state.update_data(ch_name=msg.text)
    await msg.answer("🔗 Kanal havolasini kiriting:")
    await state.set_state(AdminState.waiting_channel_url)


@dp.message(AdminState.waiting_channel_url)
async def channel_url_input(msg: Message, state: FSMContext):
    """Kanal havolasi"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    url = msg.text.strip()

    # Formatni to'g'rilash
    if url.startswith('https://t.me/'):
        # https://t.me/username -> @username
        username = url.split('https://t.me/')[-1]
        if username.startswith('@'):
            url = username
        else:
            url = f"@{username}"
    elif 't.me/' in url and not url.startswith('@'):
        # t.me/username -> @username
        username = url.split('t.me/')[-1]
        if username.startswith('@'):
            url = username
        else:
            url = f"@{username}"
    elif not url.startswith('@') and not url.startswith('https://'):
        # username -> @username
        url = f"@{url}" if not url.startswith('@') else url

    await state.update_data(ch_url=url)
    await msg.answer(f"✅ Kanal havolasi saqlandi: {url}\n\n📱 Kanal turini tanlang:", reply_markup=channel_types())
    await state.set_state(AdminState.waiting_channel_type)


@dp.callback_query(F.data.startswith("ct_"))
async def channel_type_select(call: CallbackQuery, state: FSMContext):
    """Kanal turi"""
    uid = call.from_user.id
    db.update_user_active(uid)

    ch_type = call.data.replace("ct_", "")
    data = await state.get_data()

    if db.add_channel(
            name=data['ch_name'],
            url=data['ch_url'],
            channel_type=ch_type,
            added_by=uid
    ):
        await call.message.delete()
        await call.message.answer(f"✅ Kanal qo'shildi!\n\n📝 {data['ch_name']}")
        await call.message.answer("📢 Kanallar boshqaruv:", reply_markup=channels_management())
    else:
        await call.message.edit_text("❌ Xato yuz berdi!")

    await state.clear()


@dp.message(F.text == f"{E.DEL} Kanal O'chirish")
async def delete_channel_start(msg: Message, state: FSMContext):
    """Kanal o'chirish"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    channels = db.get_channels()
    if not channels:
        await msg.answer("📋 Kanallar yo'q")
        return

    text = "📋 <b>KANALLAR</b>\n\n"
    for i, ch in enumerate(channels, 1):
        text += f"{i}. <b>{ch['channel_name']}</b>\n"
        text += f"   ID: {ch['id']} | {ch['channel_type']}\n\n"

    text += "O'chirish uchun ID kiriting:"
    await msg.answer(text, reply_markup=cancel())
    await state.set_state(AdminState.waiting_delete_channel)


@dp.message(AdminState.waiting_delete_channel)
async def delete_channel_id(msg: Message, state: FSMContext):
    """Kanal o'chirish ID"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    try:
        ch_id = int(msg.text)
        if db.delete_channel(ch_id):
            await msg.answer(f"✅ Kanal o'chirildi: {ch_id}", reply_markup=channels_management())
        else:
            await msg.answer("❌ Kanal topilmadi!", reply_markup=channels_management())
    except ValueError:
        await msg.answer("❌ Noto'g'ri ID!", reply_markup=channels_management())

    await state.clear()


@dp.message(F.text == f"{E.LIST} Kanallar")
async def list_channels(msg: Message):
    """Kanallar ro'yxati"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    channels = db.get_channels()
    if not channels:
        await msg.answer("📋 Kanallar yo'q")
        return

    text = "📋 <b>MAJBURIY KANALLAR</b>\n\n"
    for i, ch in enumerate(channels, 1):
        text += f"{i}. <b>{ch['channel_name']}</b>\n"
        text += f"   🔗 {ch['channel_url']}\n"
        text += f"   📱 {ch['channel_type']}\n\n"

    await msg.answer(text)


@dp.message(F.text == f"{E.MSG} Reklama")
async def broadcast_start(msg: Message, state: FSMContext):
    """Reklama yuborish"""
    if not is_admin(msg.from_user.id):
        return

    uid = msg.from_user.id
    db.update_user_active(uid)

    await msg.answer("📢 Reklama xabarini yuboring:", reply_markup=cancel())
    await state.set_state(AdminState.waiting_broadcast)


@dp.message(AdminState.waiting_broadcast)
async def broadcast_message(msg: Message, state: FSMContext):
    """Reklama xabari"""
    uid = msg.from_user.id
    db.update_user_active(uid)

    users = db.get_all_users()
    if not users:
        await msg.answer("❌ Userlar yo'q!")
        await state.clear()
        return

    success, failed = await broadcast(users, msg)

    await msg.answer(
        f"✅ Reklama yuborildi!\n\n"
        f"📊 Jami: {len(users)}\n"
        f"✅ Yuborildi: {success}\n"
        f"❌ Xato: {failed}",
        reply_markup=admin_panel()
    )
    await state.clear()


@dp.message(F.text == f"{E.HOME} Chiqish")
async def exit_admin(msg: Message):
    """Admin paneldan chiqish"""
    uid = msg.from_user.id
    db.update_user_active(uid)
    await msg.answer("👋 Asosiy menyuga qaytdingiz", reply_markup=main_menu())


# ============= STARTUP/SHUTDOWN =============

async def on_startup():
    """Bot ishga tushganda"""
    global bot_username
    try:
        me = await bot.get_me()
        bot_username = f"@{me.username}"
        logger.info(f"✅ Bot ishga tushdi: {bot_username}")
    except Exception as e:
        logger.error(f"Startup error: {e}")


async def on_shutdown():
    """Bot to'xtaganda"""
    logger.info("🛑 Bot to'xtadi")


async def main():
    """Asosiy funksiya"""
    await on_startup()
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot to'xtatildi (Ctrl+C)")