from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from typing import List, Dict


# ============= EMOJI =============
class E:
    """Emoji shortcuts"""
    HOME, BACK, CANCEL, CHECK, CLOSE = "🏠", "🔙", "❌", "✅", "✖️"
    MOVIE, SEARCH, TOP, CAT, FAV = "🎬", "🔍", "🏆", "🏷️", "❤️"
    DOWN, SHARE, LIKE, STAR, VIEW = "📥", "📤", "👍", "⭐", "👁️"
    USER, USERS, PROF, STATS = "👤", "👥", "👤", "📊"
    ADMIN, ADD, DEL, EDIT, LIST = "👑", "➕", "🗑️", "✏️", "📋"
    CHAN, SET, INFO, CONT, MSG = "📢", "⚙️", "ℹ️", "📞", "📨"


# ============= REPLY KEYBOARDS =============

def main_menu() -> ReplyKeyboardMarkup:
    """Asosiy menyu"""
    kb = ReplyKeyboardBuilder()
    kb.button(text=f"{E.MOVIE} Kino Kodini Yuboring")
    kb.button(text=f"{E.SEARCH} Qidirish")
    kb.button(text=f"{E.TOP} Top Kinolar")
    kb.button(text=f"{E.CAT} Kategoriyalar")
    kb.button(text=f"{E.FAV} Sevimlilarim")
    kb.button(text=f"{E.DOWN} Yuklaganlarim")
    kb.button(text=f"{E.PROF} Profil")
    kb.button(text=f"{E.INFO} Ma'lumot")
    kb.adjust(1, 2, 2, 2, 1)
    return kb.as_markup(resize_keyboard=True, input_field_placeholder="Tanlang...")


def categories_menu(categories: List[str]) -> ReplyKeyboardMarkup:
    """Kategoriyalar"""
    kb = ReplyKeyboardBuilder()
    for cat in categories:
        kb.button(text=f"{E.CAT} {cat}")
    kb.button(text=f"{E.BACK} Orqaga")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


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


def user_management() -> ReplyKeyboardMarkup:
    """User boshqaruv"""
    kb = ReplyKeyboardBuilder()
    kb.button(text="🚫 Bloklash")
    kb.button(text="🔓 Blokdan Chiqarish")
    kb.button(text=f"{E.SEARCH} User Qidirish")
    kb.button(text=f"{E.LIST} Barcha Userlar")
    kb.button(text=f"{E.BACK} Orqaga")
    kb.adjust(2, 2, 1)
    return kb.as_markup(resize_keyboard=True)


def channels_management() -> ReplyKeyboardMarkup:
    """Kanallar boshqaruv"""
    kb = ReplyKeyboardBuilder()
    kb.button(text=f"{E.ADD} Kanal Qo'shish")
    kb.button(text=f"{E.DEL} Kanal O'chirish")
    kb.button(text=f"{E.LIST} Kanallar")
    kb.button(text=f"{E.BACK} Orqaga")
    kb.adjust(2, 2)
    return kb.as_markup(resize_keyboard=True)


def cancel() -> ReplyKeyboardMarkup:
    """Bekor qilish"""
    kb = ReplyKeyboardBuilder()
    kb.button(text=f"{E.CANCEL} Bekor Qilish")
    return kb.as_markup(resize_keyboard=True)


def back_only() -> ReplyKeyboardMarkup:
    """Faqat orqaga tugmasi"""
    kb = ReplyKeyboardBuilder()
    kb.button(text=f"{E.BACK} Orqaga")
    return kb.as_markup(resize_keyboard=True)


# ============= INLINE KEYBOARDS =============

def movie_actions(code: str, bot_user: str = "", is_fav: bool = False) -> InlineKeyboardMarkup:
    """Kino amallar"""
    kb = InlineKeyboardBuilder()

    fav_text = f"{E.FAV} Olib Tashlash" if is_fav else f"{E.FAV} Sevimli"
    kb.button(text=f"{E.DOWN} Yuklab Olish", callback_data=f"dl_{code}")
    kb.button(text=fav_text, callback_data=f"fav_{code}")
    kb.button(text=f"{E.SHARE} Ulashish", callback_data=f"share_{code}")
    kb.button(text=f"{E.STAR} Reyting", callback_data=f"rate_{code}")

    if bot_user:
        share_url = f"https://t.me/share/url?url=t.me/{bot_user}&text=🎬 Kod: {code}"
        kb.button(text=f"📲 Ulashing", url=share_url)

    kb.adjust(2, 2, 1)
    return kb.as_markup()


def format_channel_url(url: str) -> str:
    """Kanal URL ni to'g'ri formatga keltirish"""
    if not url:
        return ""

    # Agar allaqachon to'liq URL bo'lsa
    if url.startswith('https://t.me/') or url.startswith('http://t.me/'):
        return url

    # Agar t.me/ bilan boshlansa
    if url.startswith('t.me/'):
        return f"https://{url}"

    # Agar @ bilan boshlansa
    if url.startswith('@'):
        username = url[1:]  # @ ni olib tashlash
        return f"https://t.me/{username}"

    # Oddiy username
    return f"https://t.me/{url}"


def channels_sub(channels: List[Dict]) -> InlineKeyboardMarkup:
    """Majburiy obuna"""
    kb = InlineKeyboardBuilder()

    for ch in channels:
        name = ch.get('channel_name', 'Kanal')
        url = ch.get('channel_url', '')
        ch_type = ch.get('channel_type', 'telegram')

        # URL ni to'g'ri formatga keltirish
        formatted_url = format_channel_url(url)

        # Icon tanlash
        icon = {"telegram": "📱", "instagram": "📸", "youtube": "🎥"}.get(ch_type, "🌐")

        # Tugma qo'shish
        kb.button(text=f"{icon} {name}", url=formatted_url)

    kb.button(text=f"{E.CHECK} Obunani Tekshirish", callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()


def movie_parts(code: str, parts: List[Dict]) -> InlineKeyboardMarkup:
    """Kino qismlari"""
    kb = InlineKeyboardBuilder()

    for p in parts:
        num = p.get('part_number', 1)
        title = p.get('title', f'Qism {num}')
        kb.button(text=f"📺 {num}: {title}", callback_data=f"part_{code}_{num}")

    kb.button(text=f"{E.BACK} Orqaga", callback_data=f"back_to_movie_{code}")
    kb.adjust(1)
    return kb.as_markup()


def rating(code: str) -> InlineKeyboardMarkup:
    """Reyting berish"""
    kb = InlineKeyboardBuilder()

    for i in range(1, 6):
        kb.button(text=f"{i} {E.STAR}", callback_data=f"r_{i}_{code}")

    kb.button(text=f"{E.CANCEL} Bekor", callback_data=f"cancel_rate")
    kb.adjust(5, 1)
    return kb.as_markup()


def movie_list(movies: List[Dict], page: int = 1, total_pages: int = 1, query: str = "") -> InlineKeyboardMarkup:
    """Kino ro'yxati"""
    kb = InlineKeyboardBuilder()

    for m in movies:
        code = m.get('code', '')
        title = m.get('title_uz', 'Kino')[:25]
        views = m.get('views', 0)
        kb.button(text=f"🎬 {title} ({views}👁️)", callback_data=f"movie_{code}")

    # Pagination
    if total_pages > 1:
        pagination = []
        if page > 1:
            pagination.append(("◀️ Oldingi", f"page_{page - 1}_{query}"))

        pagination.append((f"{page}/{total_pages}", "current_page"))

        if page < total_pages:
            pagination.append(("Keyingi ▶️", f"page_{page + 1}_{query}"))

        for text, data in pagination:
            kb.button(text=text, callback_data=data)

    kb.button(text=f"{E.BACK} Orqaga", callback_data="back_main")
    kb.adjust(1, 3, 1)
    return kb.as_markup()


def channel_types() -> InlineKeyboardMarkup:
    """Kanal turlari"""
    kb = InlineKeyboardBuilder()
    types = [
        ("📱 Telegram", "telegram"),
        ("📸 Instagram", "instagram"),
        ("🎥 YouTube", "youtube"),
        ("🌐 Boshqa", "website")
    ]
    for text, data in types:
        kb.button(text=text, callback_data=f"ct_{data}")
    kb.adjust(2)
    return kb.as_markup()


def close_msg() -> InlineKeyboardMarkup:
    """Yopish"""
    kb = InlineKeyboardBuilder()
    kb.button(text=f"{E.CLOSE} Yopish", callback_data="close")
    return kb.as_markup()