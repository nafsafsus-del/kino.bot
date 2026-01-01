import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import threading


class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_file='cinema_bot.db'):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_file='kino.db'):
        if not hasattr(self, 'initialized'):
            self.db_file = db_file
            self.local = threading.local()
            self.create_tables()
            self.init_default_data()
            self.initialized = True

    @contextmanager
    def get_connection(self):
        """Thread-safe connection pool"""
        if not hasattr(self.local, 'connection'):
            self.local.connection = sqlite3.connect(self.db_file, check_same_thread=False)
            self.local.connection.row_factory = sqlite3.Row
            self.local.connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield self.local.connection
        except Exception as e:
            self.local.connection.rollback()
            raise e

    def create_tables(self):
        """Barcha jadvallarni yaratish"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Users jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    language TEXT DEFAULT 'uz',
                    join_date INTEGER,
                    last_active INTEGER,
                    total_downloads INTEGER DEFAULT 0,
                    is_blocked INTEGER DEFAULT 0,
                    is_admin INTEGER DEFAULT 0,
                    is_premium INTEGER DEFAULT 0
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_blocked, last_active)')

            # Movies jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS movies (
                    code TEXT PRIMARY KEY,
                    title_uz TEXT NOT NULL,
                    description_uz TEXT,
                    year INTEGER,
                    duration TEXT,
                    category TEXT,
                    file_id TEXT NOT NULL,
                    thumbnail_id TEXT,
                    file_type TEXT DEFAULT 'video',
                    added_by INTEGER,
                    added_date INTEGER,
                    views INTEGER DEFAULT 0,
                    downloads INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    rating REAL DEFAULT 0.0,
                    rating_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_movies_category ON movies(category, is_active)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_movies_views ON movies(views DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title_uz)')

            # Movie parts
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS movie_parts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    movie_code TEXT NOT NULL,
                    part_number INTEGER NOT NULL,
                    title TEXT,
                    file_id TEXT NOT NULL,
                    added_date INTEGER,
                    FOREIGN KEY (movie_code) REFERENCES movies(code) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_parts_movie ON movie_parts(movie_code, part_number)')

            # Channels
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_name TEXT NOT NULL,
                    channel_url TEXT NOT NULL,
                    channel_type TEXT DEFAULT 'telegram',
                    is_mandatory INTEGER DEFAULT 1,
                    added_date INTEGER,
                    added_by INTEGER,
                    is_active INTEGER DEFAULT 1
                )
            ''')

            # Favorites
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id INTEGER,
                    movie_code TEXT,
                    added_date INTEGER,
                    PRIMARY KEY (user_id, movie_code),
                    FOREIGN KEY (movie_code) REFERENCES movies(code) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, added_date DESC)')

            # Ratings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ratings (
                    user_id INTEGER,
                    movie_code TEXT,
                    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                    added_date INTEGER,
                    PRIMARY KEY (user_id, movie_code),
                    FOREIGN KEY (movie_code) REFERENCES movies(code) ON DELETE CASCADE
                )
            ''')

            # Settings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            conn.commit()

    def init_default_data(self):
        """Default ma'lumotlarni qo'shish"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            defaults = [
                ('admin_password', '2008'),
                ('bot_username', '@your_cinema_bot'),
                ('welcome_message', '🎬 Cinema Botga xush kelibsiz!'),
                # Yangilangan kategoriyalar - emoji bilan
                ('movie_categories',
                 'Komediya,Drama,Jangari,Fantastika,Romantika,Qoʻrqinchli,Sarguzasht,Multfilm,Detektiv,Thriller'),
            ]

            cursor.executemany('''
                INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)
            ''', defaults)
            conn.commit()

            # Agar kanallar yo'q bo'lsa, demo kanal qo'shish
            channels_exist = cursor.execute('SELECT COUNT(*) FROM channels WHERE is_mandatory = 1').fetchone()[0]
            if channels_exist == 0:
                now = int(datetime.now().timestamp())
                cursor.execute('''
                    INSERT INTO channels (channel_name, channel_url, channel_type, is_mandatory, added_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', ('Cinema Kanal', '@cinema_kanal_uz', 'telegram', 1, now))
                conn.commit()
    def add_user(self, user_id: int, username: str = None, full_name: str = None) -> bool:
        """Yangi foydalanuvchi qo'shish"""
        try:
            with self.get_connection() as conn:
                now = int(datetime.now().timestamp())
                conn.execute('''
                    INSERT OR IGNORE INTO users (user_id, username, full_name, join_date, last_active)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, username, full_name, now, now))
                conn.commit()
                return True
        except Exception as e:
            print(f"Add user error: {e}")
            return False

    def get_user(self, user_id: int) -> Optional[Dict]:
        """Foydalanuvchi ma'lumotlarini olish"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
            return dict(row) if row else None

    def update_user_active(self, user_id: int):
        """Oxirgi faollikni yangilash"""
        with self.get_connection() as conn:
            now = int(datetime.now().timestamp())
            conn.execute('UPDATE users SET last_active = ? WHERE user_id = ?', (now, user_id))
            conn.commit()

    def block_user(self, user_id: int):
        """User bloklash"""
        with self.get_connection() as conn:
            conn.execute('UPDATE users SET is_blocked = 1 WHERE user_id = ?', (user_id,))
            conn.commit()

    def unblock_user(self, user_id: int):
        """User blokdan chiqarish"""
        with self.get_connection() as conn:
            conn.execute('UPDATE users SET is_blocked = 0 WHERE user_id = ?', (user_id,))
            conn.commit()

    def get_all_users(self) -> List[int]:
        """Barcha userlarni olish"""
        with self.get_connection() as conn:
            rows = conn.execute('SELECT user_id FROM users WHERE is_blocked = 0').fetchall()
            return [row[0] for row in rows]

    def get_users_list(self, limit: int = 50) -> List[Dict]:
        """Userlar ro'yxati"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT user_id, username, full_name, total_downloads, is_blocked 
                FROM users 
                ORDER BY join_date DESC 
                LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in rows]

    def search_users(self, query: str) -> List[Dict]:
        """Userlarni qidirish"""
        with self.get_connection() as conn:
            search = f'%{query}%'
            rows = conn.execute('''
                SELECT * FROM users 
                WHERE username LIKE ? OR full_name LIKE ? 
                ORDER BY last_active DESC
            ''', (search, search)).fetchall()
            return [dict(row) for row in rows]

    def update_user_downloads(self, user_id: int):
        """Yuklab olishlarni oshirish"""
        with self.get_connection() as conn:
            conn.execute('UPDATE users SET total_downloads = total_downloads + 1 WHERE user_id = ?', (user_id,))
            conn.commit()

    # ==================== MOVIE FUNCTIONS ====================

    def add_movie(self, code: str, title: str, description: str, file_id: str,
                  category: str = 'Umumiy', **kwargs) -> bool:
        """Yangi kino qo'shish"""
        try:
            with self.get_connection() as conn:
                now = int(datetime.now().timestamp())

                file_type = kwargs.get('file_type', 'video')
                thumbnail = kwargs.get('thumbnail')

                if file_type == 'photo' and not thumbnail:
                    thumbnail = file_id

                conn.execute('''
                    INSERT INTO movies (code, title_uz, description_uz, file_id, category, 
                                      year, duration, thumbnail_id, file_type, added_by, added_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (code, title, description, file_id, category,
                      kwargs.get('year'), kwargs.get('duration'), thumbnail,
                      file_type, kwargs.get('added_by'), now))
                conn.commit()
                return True
        except Exception as e:
            print(f"Add movie error: {e}")
            return False

    def get_movie(self, code: str) -> Optional[Dict]:
        """Kino ma'lumotlarini olish"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM movies WHERE code = ? AND is_active = 1', (code,)).fetchone()
            return dict(row) if row else None

    def search_movies(self, query: str, limit: int = 20, offset: int = 0) -> Tuple[List[Dict], int]:
        """Kinolarni qidirish"""
        with self.get_connection() as conn:
            search = f'%{query}%'

            # Total count
            count_row = conn.execute('''
                SELECT COUNT(*) FROM movies 
                WHERE (title_uz LIKE ? OR code LIKE ?) AND is_active = 1
            ''', (search, search)).fetchone()
            total = count_row[0] if count_row else 0

            # Results
            rows = conn.execute('''
                SELECT * FROM movies 
                WHERE (title_uz LIKE ? OR code LIKE ?) AND is_active = 1
                ORDER BY views DESC LIMIT ? OFFSET ?
            ''', (search, search, limit, offset)).fetchall()

            return [dict(row) for row in rows], total

    def get_all_movies(self, limit: int = 20, offset: int = 0) -> Tuple[List[Dict], int]:
        """Barcha kinolarni olish"""
        with self.get_connection() as conn:
            # Total count
            count_row = conn.execute('SELECT COUNT(*) FROM movies WHERE is_active = 1').fetchone()
            total = count_row[0] if count_row else 0

            # Results
            rows = conn.execute('''
                SELECT * FROM movies WHERE is_active = 1
                ORDER BY added_date DESC LIMIT ? OFFSET ?
            ''', (limit, offset)).fetchall()
            return [dict(row) for row in rows], total

    def get_movies_by_category(self, category: str, limit: int = 20) -> List[Dict]:
        """Kategoriya bo'yicha kinolar"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM movies 
                WHERE category LIKE ? AND is_active = 1
                ORDER BY views DESC LIMIT ?
            ''', (f'%{category}%', limit)).fetchall()
            return [dict(row) for row in rows]

    def get_top_movies(self, limit: int = 10) -> List[Dict]:
        """Top kinolar"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM movies WHERE is_active = 1
                ORDER BY views DESC, downloads DESC LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in rows]

    def delete_movie(self, code: str) -> bool:
        """Kinoni o'chirish"""
        try:
            with self.get_connection() as conn:
                conn.execute('DELETE FROM movies WHERE code = ?', (code,))
                conn.commit()
                return True
        except:
            return False

    def increment_views(self, code: str):
        """Ko'rishlarni oshirish"""
        with self.get_connection() as conn:
            conn.execute('UPDATE movies SET views = views + 1 WHERE code = ?', (code,))
            conn.commit()

    def increment_downloads(self, code: str):
        """Yuklab olishlarni oshirish"""
        with self.get_connection() as conn:
            conn.execute('UPDATE movies SET downloads = downloads + 1 WHERE code = ?', (code,))
            conn.commit()

    def increment_likes(self, code: str):
        """Like larni oshirish"""
        with self.get_connection() as conn:
            conn.execute('UPDATE movies SET likes = likes + 1 WHERE code = ?', (code,))
            conn.commit()

    def add_rating(self, user_id: int, movie_code: str, rating: int) -> bool:
        """Reyting qo'shish"""
        try:
            with self.get_connection() as conn:
                now = int(datetime.now().timestamp())
                conn.execute('''
                    INSERT OR REPLACE INTO ratings (user_id, movie_code, rating, added_date)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, movie_code, rating, now))

                # O'rtacha reytingni hisoblash
                avg_rating, count = conn.execute(
                    'SELECT AVG(rating), COUNT(*) FROM ratings WHERE movie_code = ?',
                    (movie_code,)
                ).fetchone()

                conn.execute('''
                    UPDATE movies SET rating = ?, rating_count = ? WHERE code = ?
                ''', (avg_rating or 0, count or 0, movie_code))
                conn.commit()
                return True
        except Exception as e:
            print(f"Add rating error: {e}")
            return False

    # ==================== MOVIE PARTS ====================

    def add_movie_part(self, movie_code: str, part_number: int, title: str, file_id: str) -> bool:
        """Kino qismini qo'shish"""
        try:
            with self.get_connection() as conn:
                now = int(datetime.now().timestamp())
                conn.execute('''
                    INSERT INTO movie_parts (movie_code, part_number, title, file_id, added_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (movie_code, part_number, title, file_id, now))
                conn.commit()
                return True
        except:
            return False

    def get_movie_parts(self, movie_code: str) -> List[Dict]:
        """Kino qismlarini olish"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM movie_parts WHERE movie_code = ? ORDER BY part_number
            ''', (movie_code,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== FAVORITES ====================

    def add_favorite(self, user_id: int, movie_code: str) -> bool:
        """Sevimlilarga qo'shish"""
        try:
            with self.get_connection() as conn:
                now = int(datetime.now().timestamp())
                conn.execute('''
                    INSERT OR IGNORE INTO favorites (user_id, movie_code, added_date)
                    VALUES (?, ?, ?)
                ''', (user_id, movie_code, now))
                conn.commit()
                return True
        except:
            return False

    def remove_favorite(self, user_id: int, movie_code: str) -> bool:
        """Sevimlilardan o'chirish"""
        try:
            with self.get_connection() as conn:
                conn.execute('DELETE FROM favorites WHERE user_id = ? AND movie_code = ?',
                             (user_id, movie_code))
                conn.commit()
                return True
        except:
            return False

    def get_favorites(self, user_id: int) -> List[Dict]:
        """Sevimlilarni olish"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT m.* FROM movies m
                JOIN favorites f ON m.code = f.movie_code
                WHERE f.user_id = ? AND m.is_active = 1
                ORDER BY f.added_date DESC
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    def is_favorite(self, user_id: int, movie_code: str) -> bool:
        """Sevimli ekanligini tekshirish"""
        with self.get_connection() as conn:
            row = conn.execute('''
                SELECT 1 FROM favorites WHERE user_id = ? AND movie_code = ?
            ''', (user_id, movie_code)).fetchone()
            return row is not None

    # ==================== CHANNELS ====================

    def add_channel(self, name: str, url: str, channel_type: str = 'telegram', **kwargs) -> bool:
        """Kanal qo'shish"""
        try:
            with self.get_connection() as conn:
                now = int(datetime.now().timestamp())
                conn.execute('''
                    INSERT INTO channels (channel_name, channel_url, channel_type, 
                                        is_mandatory, added_date, added_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, url, channel_type, kwargs.get('is_mandatory', 1), now,
                      kwargs.get('added_by', 0)))
                conn.commit()
                return True
        except Exception as e:
            print(f"Add channel error: {e}")
            return False

    def delete_channel(self, channel_id: int) -> bool:
        """Kanalni o'chirish"""
        try:
            with self.get_connection() as conn:
                conn.execute('DELETE FROM channels WHERE id = ?', (channel_id,))
                conn.commit()
                return True
        except:
            return False

    def get_channels(self, is_mandatory: bool = True) -> List[Dict]:
        """Kanallarni olish"""
        with self.get_connection() as conn:
            if is_mandatory:
                rows = conn.execute('''
                    SELECT * FROM channels WHERE is_mandatory = 1 AND is_active = 1
                    ORDER BY added_date DESC
                ''').fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM channels WHERE is_active = 1 
                    ORDER BY added_date DESC
                ''').fetchall()
            return [dict(row) for row in rows]

    def get_channel_by_id(self, channel_id: int) -> Optional[Dict]:
        """Kanalni ID bo'yicha olish"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM channels WHERE id = ?', (channel_id,)).fetchone()
            return dict(row) if row else None

    # ==================== STATISTICS ====================

    def get_statistics(self) -> Dict[str, int]:
        """Statistika olish"""
        with self.get_connection() as conn:
            stats = {}

            # Users
            stats['total_users'] = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            stats['active_users'] = conn.execute(
                'SELECT COUNT(*) FROM users WHERE is_blocked = 0'
            ).fetchone()[0]
            stats['blocked_users'] = conn.execute(
                'SELECT COUNT(*) FROM users WHERE is_blocked = 1'
            ).fetchone()[0]
            stats['premium_users'] = conn.execute(
                'SELECT COUNT(*) FROM users WHERE is_premium = 1'
            ).fetchone()[0]

            # Movies
            stats['total_movies'] = conn.execute(
                'SELECT COUNT(*) FROM movies WHERE is_active = 1'
            ).fetchone()[0]
            stats['total_downloads'] = conn.execute(
                'SELECT COALESCE(SUM(downloads), 0) FROM movies'
            ).fetchone()[0]
            stats['total_views'] = conn.execute(
                'SELECT COALESCE(SUM(views), 0) FROM movies'
            ).fetchone()[0]

            # Channels
            stats['mandatory_channels'] = conn.execute(
                'SELECT COUNT(*) FROM channels WHERE is_mandatory = 1 AND is_active = 1'
            ).fetchone()[0]

            # Bugungi statistika
            today_start = int(datetime.now().replace(hour=0, minute=0, second=0).timestamp())
            stats['today_new_users'] = conn.execute(
                'SELECT COUNT(*) FROM users WHERE join_date >= ?', (today_start,)
            ).fetchone()[0]
            stats['today_active_users'] = conn.execute(
                'SELECT COUNT(*) FROM users WHERE last_active >= ?', (today_start,)
            ).fetchone()[0]

            return stats

    # ==================== SETTINGS ====================

    def get_setting(self, key: str, default: str = None) -> str:
        """Sozlamani olish"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
            return row[0] if row else default

    def update_setting(self, key: str, value: str):
        """Sozlamani yangilash"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', (key, value))
            conn.commit()

            # database.py (qo'shimcha funksiyalar)
            # Database classiga quyidagi funksiyalarni qo'shing:

            def get_admins(self) -> List[Dict]:
                """Barcha adminlarni olish"""
                with self.get_connection() as conn:
                    rows = conn.execute('''
                            SELECT user_id, username, full_name 
                            FROM users 
                            WHERE is_admin = 1 
                            ORDER BY user_id
                        ''').fetchall()
                    return [dict(row) for row in rows]

            def remove_admin(self, user_id: int) -> bool:
                """Admindan huquqlarni olib tashlash"""
                try:
                    with self.get_connection() as conn:
                        conn.execute('UPDATE users SET is_admin = 0 WHERE user_id = ?', (user_id,))
                        conn.commit()
                        return True
                except Exception as e:
                    print(f"Remove admin error: {e}")
                    return False


# Singleton instance
db = Database()
