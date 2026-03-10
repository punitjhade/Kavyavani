from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3, os, json
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = "sukhanSarai_secret_2024_!@#"
DATABASE = "sukhan.db"
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─── DB ───────────────────────────────────────────────────────────────────────

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, '_database', None)
    if db is not None: db.close()

def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rv  = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def execute(sql, args=()):
    db  = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid

def allowed_file(f):
    return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

# ─── INIT DB ──────────────────────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                bio TEXT DEFAULT '',
                profile_pic TEXT DEFAULT '',
                cover_pic TEXT DEFAULT '',
                role TEXT DEFAULT 'user',
                is_banned INTEGER DEFAULT 0,
                poet_of_week INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS poems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'सामान्य',
                language TEXT DEFAULT 'Hindi',
                theme TEXT DEFAULT 'default',
                font TEXT DEFAULT 'garamond',
                dedicated_to TEXT DEFAULT '',
                user_id INTEGER NOT NULL,
                views INTEGER DEFAULT 0,
                is_featured INTEGER DEFAULT 0,
                is_draft INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                poem_id INTEGER NOT NULL,
                UNIQUE(user_id, poem_id)
            );
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                poem_id INTEGER NOT NULL,
                parent_id INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS follows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                follower_id INTEGER NOT NULL,
                following_id INTEGER NOT NULL,
                UNIQUE(follower_id, following_id)
            );
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                poem_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, poem_id)
            );
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS collection_poems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER NOT NULL,
                poem_id INTEGER NOT NULL,
                UNIQUE(collection_id, poem_id)
            );
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                link TEXT DEFAULT '',
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER NOT NULL,
                poem_id INTEGER,
                reason TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                admin_id INTEGER NOT NULL,
                schedule_at TIMESTAMP DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                badge_key TEXT NOT NULL,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, badge_key)
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                file_path TEXT DEFAULT '',
                file_type TEXT DEFAULT '',
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS poem_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poem_id INTEGER NOT NULL,
                viewer_id INTEGER,
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        db.commit()

        # Safe migrations for existing DBs
        for migration in [
            "ALTER TABLE comments ADD COLUMN parent_id INTEGER DEFAULT NULL",
            "ALTER TABLE poems    ADD COLUMN theme TEXT DEFAULT 'default'",
            "ALTER TABLE poems    ADD COLUMN font TEXT DEFAULT 'garamond'",
            "ALTER TABLE poems    ADD COLUMN dedicated_to TEXT DEFAULT ''",
            "ALTER TABLE poems    ADD COLUMN is_featured INTEGER DEFAULT 0",
            "ALTER TABLE poems    ADD COLUMN is_draft INTEGER DEFAULT 0",
            "ALTER TABLE users    ADD COLUMN profile_pic TEXT DEFAULT ''",
            "ALTER TABLE users    ADD COLUMN cover_pic TEXT DEFAULT ''",
            "ALTER TABLE users    ADD COLUMN is_banned INTEGER DEFAULT 0",
            "ALTER TABLE users    ADD COLUMN poet_of_week INTEGER DEFAULT 0",
            "ALTER TABLE messages ADD COLUMN file_path TEXT DEFAULT ''",
            "ALTER TABLE messages ADD COLUMN file_type TEXT DEFAULT ''",
            "ALTER TABLE users    ADD COLUMN language_pref TEXT DEFAULT 'hi'",
        ]:
            try: db.execute(migration)
            except: pass
        db.commit()

        for cat in ['प्रेम','सूफ़ी','दर्शन','प्रकृति','उदासी','क्रांति','आध्यात्म','सामान्य']:
            try: db.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
            except: pass
        db.commit()

        if not query("SELECT id FROM users WHERE username='admin'", one=True):
            db.execute("INSERT INTO users (username,email,password_hash,role) VALUES (?,?,?,?)",
                       ('admin','admin@sukhan.com',generate_password_hash('admin123'),'admin'))
            db.commit()
        print("✅ Database ready.")

# ─── BADGES ───────────────────────────────────────────────────────────────────

BADGES = {
    'first_poem':    {'label':'✍️ पहली कविता',   'desc':'पहली कविता publish की'},
    'ten_poems':     {'label':'📜 10 कविताएँ',    'desc':'10 कविताएँ publish कीं'},
    'fifty_poems':   {'label':'🌟 50 कविताएँ',    'desc':'50 कविताएँ publish कीं'},
    'first_like':    {'label':'❤️ पहला Like',     'desc':'पहला like मिला'},
    'hundred_likes': {'label':'🔥 100 Likes',      'desc':'100 total likes मिले'},
    'first_follow':  {'label':'👥 पहला Follower', 'desc':'पहला follower मिला'},
    'poet_of_week':  {'label':'👑 Poet of Week',   'desc':'Poet of the Week चुने गए'},
    'commentator':   {'label':'💬 Commentator',    'desc':'10 comments किए'},
    'social':        {'label':'🤝 Social Poet',    'desc':'10 लोगों को follow किया'},
}



# ══════════════════════════════════════════════
# KAVYAVANI — काव्यवाणी — Full Translation System
# ══════════════════════════════════════════════
TRANSLATIONS = {
    'hi': {
        'site_name': 'काव्यवाणी', 'site_tagline': 'शब्दों का घर', 'site_desc': 'हिंदी और उर्दू कविता का संसार',
        'home': 'होम', 'poems': 'कविताएँ', 'trending': 'ट्रेंडिंग', 'leaderboard': 'लीडरबोर्ड',
        'search': 'खोजें', 'write': 'लिखें', 'login': 'लॉगिन', 'logout': 'लॉगआउट',
        'register': 'पंजीकरण', 'profile': 'प्रोफाइल', 'feed': 'फीड', 'notifications': 'सूचनाएँ',
        'messages': 'संदेश', 'bookmarks': 'बुकमार्क', 'collections': 'संग्रह',
        'categories': 'विषय', 'settings': 'सेटिंग',
        'hero_title': 'काव्यवाणी', 'hero_devnagri': 'शब्दों का संसार',
        'hero_urdu': 'کاویاوانی — جہاں ہر لفظ دل سے نکلتا ہے',
        'hero_tagline': 'जहाँ हर दर्द को आवाज़ मिलती है, हर ख़्वाब को शब्द मिलते हैं',
        'start_writing': '✍ लिखना शुरू करें', 'join_now': '✨ शामिल हों',
        'my_feed': '📩 मेरा फीड', 'login_btn': '🔑 लॉगिन',
        'featured': '⭐ चुनी हुई कविताएँ', 'latest_poems': '✨ नई कविताएँ',
        'trending_kalam': '🔥 ट्रेंडिंग', 'top_shayar': '🏆 टॉप शायर',
        'potw_label': '👑 शायर ऑफ द वीक',
        'write_poem': '✍ नई कविता लिखें', 'edit_poem': '✏ कविता सुधारें',
        'title_label': 'शीर्षक', 'content_label': 'कविता',
        'category_label': 'विषय', 'language_label': 'भाषा',
        'theme_label': '🎨 थीम', 'font_label': '🖋 फ़ॉन्ट',
        'dedication_label': '💌 समर्पित', 'publish': '🚀 प्रकाशित करें',
        'save_draft': '💾 ड्राफ्ट सेव', 'preview': '👁 लाइव प्रीव्यू',
        'comment': 'टिप्पणी', 'reply': '↩ जवाब', 'delete': '🗑 हटाएँ',
        'follow': '➕ फॉलो', 'following': '✓ फॉलोइंग', 'followers': 'फॉलोअर',
        'mutual': '🤝 म्यूचुअल', 'send_message': '💌 संदेश भेजें',
        'edit_profile': '✏ प्रोफाइल सुधारें', 'poems_count': 'कविताएँ',
        'likes_count': 'लाइक्स', 'share_wa': '📲 व्हाट्सएप', 'share_tw': '🐦 शेयर',
        'copy_link': '🔗 लिंक कॉपी', 'download_card': '🖼 कार्ड डाउनलोड',
        'report': '🚨 रिपोर्ट', 'no_poems': 'अभी कोई कविता नहीं',
        'no_poems_sub': 'पहली कविता लिखने का सम्मान आपका है!',
        'empty_feed': 'फीड खाली है', 'empty_feed_sub': 'जिन शायरों को फॉलो करें उनकी कविताएँ यहाँ आएंगी',
        'search_poets': 'शायर खोजें', 'read_more': 'पूरी कविता →', 'back': '← वापस',
        'terms': 'नियम एवं शर्तें', 'privacy': 'गोपनीयता नीति', 'about': 'हमारे बारे में',
        'contact': 'संपर्क',
    },
    'en': {
        'site_name': 'Kavyavani', 'site_tagline': 'Home of Words', 'site_desc': 'A world of Hindi & Urdu poetry',
        'home': 'Home', 'poems': 'Poems', 'trending': 'Trending', 'leaderboard': 'Top Poets',
        'search': 'Search', 'write': 'Write', 'login': 'Login', 'logout': 'Logout',
        'register': 'Register', 'profile': 'Profile', 'feed': 'Feed', 'notifications': 'Notifications',
        'messages': 'Messages', 'bookmarks': 'Bookmarks', 'collections': 'Collections',
        'categories': 'Categories', 'settings': 'Settings',
        'hero_title': 'Kavyavani', 'hero_devnagri': 'काव्यवाणी',
        'hero_urdu': 'کاویاوانی — جہاں ہر لفظ دل سے نکلتا ہے',
        'hero_tagline': 'Where every pain finds a voice, every dream finds its words',
        'start_writing': '✍ Start Writing', 'join_now': '✨ Join Now',
        'my_feed': '📩 My Feed', 'login_btn': '🔑 Login',
        'featured': '⭐ Featured Poems', 'latest_poems': '✨ Latest Poems',
        'trending_kalam': '🔥 Trending', 'top_shayar': '🏆 Top Poets',
        'potw_label': '👑 Poet of the Week',
        'write_poem': '✍ Write New Poem', 'edit_poem': '✏ Edit Poem',
        'title_label': 'Title', 'content_label': 'Poem',
        'category_label': 'Category', 'language_label': 'Language',
        'theme_label': '🎨 Theme', 'font_label': '🖋 Font',
        'dedication_label': '💌 Dedicated To', 'publish': '🚀 Publish',
        'save_draft': '💾 Save Draft', 'preview': '👁 Live Preview',
        'comment': 'Comment', 'reply': '↩ Reply', 'delete': '🗑 Delete',
        'follow': '➕ Follow', 'following': '✓ Following', 'followers': 'Followers',
        'mutual': '🤝 Mutual', 'send_message': '💌 Message',
        'edit_profile': '✏ Edit Profile', 'poems_count': 'Poems',
        'likes_count': 'Likes', 'share_wa': '📲 WhatsApp', 'share_tw': '🐦 Share',
        'copy_link': '🔗 Copy Link', 'download_card': '🖼 Download Card',
        'report': '🚨 Report', 'no_poems': 'No poems yet',
        'no_poems_sub': 'Be the first to write a poem!',
        'empty_feed': 'Your feed is empty', 'empty_feed_sub': 'Follow poets to see their poems here',
        'search_poets': 'Find Poets', 'read_more': 'Read More →', 'back': '← Back',
        'terms': 'Terms & Conditions', 'privacy': 'Privacy Policy', 'about': 'About Us',
        'contact': 'Contact',
    },
    'ur': {
        'site_name': 'کاویاوانی', 'site_tagline': 'الفاظ کا گھر', 'site_desc': 'ہندی اور اردو شاعری کی دنیا',
        'home': 'ہوم', 'poems': 'اشعار', 'trending': 'ٹرینڈنگ', 'leaderboard': 'سرفہرست',
        'search': 'تلاش', 'write': 'لکھیں', 'login': 'لاگ ان', 'logout': 'لاگ آؤٹ',
        'register': 'رجسٹر', 'profile': 'پروفائل', 'feed': 'فیڈ', 'notifications': 'اطلاعات',
        'messages': 'پیغامات', 'bookmarks': 'بک مارک', 'collections': 'مجموعے',
        'categories': 'موضوعات', 'settings': 'ترتیبات',
        'hero_title': 'کاویاوانی', 'hero_devnagri': 'काव्यवाणी',
        'hero_urdu': 'جہاں ہر لفظ دل سے نکلتا ہے',
        'hero_tagline': 'جہاں ہر درد کو آواز ملتی ہے، ہر خواب کو الفاظ ملتے ہیں',
        'start_writing': '✍ لکھنا شروع کریں', 'join_now': '✨ شامل ہوں',
        'my_feed': '📩 میری فیڈ', 'login_btn': '🔑 لاگ ان',
        'featured': '⭐ منتخب اشعار', 'latest_poems': '✨ نئے اشعار',
        'trending_kalam': '🔥 ٹرینڈنگ', 'top_shayar': '🏆 سرفہرست شاعر',
        'potw_label': '👑 شاعر آف دی ویک',
        'write_poem': '✍ نئی نظم لکھیں', 'edit_poem': '✏ نظم ترمیم کریں',
        'title_label': 'عنوان', 'content_label': 'نظم',
        'category_label': 'موضوع', 'language_label': 'زبان',
        'theme_label': '🎨 تھیم', 'font_label': '🖋 فونٹ',
        'dedication_label': '💌 انتساب', 'publish': '🚀 شائع کریں',
        'save_draft': '💾 مسودہ', 'preview': '👁 پیش نظارہ',
        'comment': 'تبصرہ', 'reply': '↩ جواب', 'delete': '🗑 حذف',
        'follow': '➕ فالو', 'following': '✓ فالو کر رہے ہیں', 'followers': 'فالوئرز',
        'mutual': '🤝 باہمی', 'send_message': '💌 پیغام',
        'edit_profile': '✏ پروفائل ترمیم', 'poems_count': 'اشعار',
        'likes_count': 'پسند', 'share_wa': '📲 واٹس ایپ', 'share_tw': '🐦 شیئر',
        'copy_link': '🔗 لنک کاپی', 'download_card': '🖼 کارڈ ڈاؤنلوڈ',
        'report': '🚨 رپورٹ', 'no_poems': 'ابھی کوئی نظم نہیں',
        'no_poems_sub': 'پہلی نظم لکھنے کا اعزاز آپ کا ہے!',
        'empty_feed': 'فیڈ خالی ہے', 'empty_feed_sub': 'شاعروں کو فالو کریں',
        'search_poets': 'شاعر تلاش کریں', 'read_more': 'پوری نظم ←', 'back': '← واپس',
        'terms': 'شرائط و ضوابط', 'privacy': 'رازداری', 'about': 'ہمارے بارے میں',
        'contact': 'رابطہ',
    },
    'pa': {
        'site_name': 'ਕਾਵਿਆਵਾਣੀ', 'site_tagline': 'ਸ਼ਬਦਾਂ ਦਾ ਘਰ', 'site_desc': 'ਪੰਜਾਬੀ ਕਵਿਤਾ ਦੀ ਦੁਨੀਆ',
        'home': 'ਹੋਮ', 'poems': 'ਕਵਿਤਾਵਾਂ', 'trending': 'ਟ੍ਰੈਂਡਿੰਗ', 'leaderboard': 'ਚੋਟੀ',
        'search': 'ਖੋਜੋ', 'write': 'ਲਿਖੋ', 'login': 'ਲਾਗਇਨ', 'logout': 'ਲਾਗਆਉਟ',
        'register': 'ਰਜਿਸਟਰ', 'profile': 'ਪ੍ਰੋਫਾਈਲ', 'feed': 'ਫੀਡ', 'notifications': 'ਸੂਚਨਾਵਾਂ',
        'messages': 'ਸੁਨੇਹੇ', 'bookmarks': 'ਬੁੱਕਮਾਰਕ', 'collections': 'ਸੰਗ੍ਰਹਿ',
        'categories': 'ਵਿਸ਼ੇ', 'settings': 'ਸੈਟਿੰਗ',
        'hero_title': 'ਕਾਵਿਆਵਾਣੀ', 'hero_devnagri': 'काव्यवाणी',
        'hero_urdu': 'جہاں ہر لفظ دل سے نکلتا ہے',
        'hero_tagline': 'ਜਿੱਥੇ ਹਰ ਦਰਦ ਨੂੰ ਆਵਾਜ਼ ਮਿਲਦੀ ਹੈ',
        'start_writing': '✍ ਲਿਖਣਾ ਸ਼ੁਰੂ ਕਰੋ', 'join_now': '✨ ਸ਼ਾਮਲ ਹੋਵੋ',
        'my_feed': '📩 ਮੇਰੀ ਫੀਡ', 'login_btn': '🔑 ਲਾਗਇਨ',
        'featured': '⭐ ਚੁਣੀਆਂ ਕਵਿਤਾਵਾਂ', 'latest_poems': '✨ ਨਵੀਆਂ ਕਵਿਤਾਵਾਂ',
        'trending_kalam': '🔥 ਟ੍ਰੈਂਡਿੰਗ', 'top_shayar': '🏆 ਚੋਟੀ ਦੇ ਕਵੀ',
        'potw_label': '👑 ਕਵੀ ਆਫ਼ ਦੀ ਵੀਕ',
        'write_poem': '✍ ਨਵੀਂ ਕਵਿਤਾ', 'edit_poem': '✏ ਕਵਿਤਾ ਸੋਧੋ',
        'title_label': 'ਸਿਰਲੇਖ', 'content_label': 'ਕਵਿਤਾ',
        'category_label': 'ਵਿਸ਼ਾ', 'language_label': 'ਭਾਸ਼ਾ',
        'theme_label': '🎨 ਥੀਮ', 'font_label': '🖋 ਫੌਂਟ',
        'dedication_label': '💌 ਸਮਰਪਿਤ', 'publish': '🚀 ਪ੍ਰਕਾਸ਼ਿਤ ਕਰੋ',
        'save_draft': '💾 ਡਰਾਫਟ', 'preview': '👁 ਪ੍ਰੀਵਿਊ',
        'comment': 'ਟਿੱਪਣੀ', 'reply': '↩ ਜਵਾਬ', 'delete': '🗑 ਮਿਟਾਓ',
        'follow': '➕ ਫਾਲੋ', 'following': '✓ ਫਾਲੋਇੰਗ', 'followers': 'ਫਾਲੋਅਰ',
        'mutual': '🤝 ਆਪਸੀ', 'send_message': '💌 ਸੁਨੇਹਾ',
        'edit_profile': '✏ ਪ੍ਰੋਫਾਈਲ ਸੋਧੋ', 'poems_count': 'ਕਵਿਤਾਵਾਂ',
        'likes_count': 'ਲਾਈਕਸ', 'share_wa': '📲 ਵਟਸਐਪ', 'share_tw': '🐦 ਸ਼ੇਅਰ',
        'copy_link': '🔗 ਲਿੰਕ ਕਾਪੀ', 'download_card': '🖼 ਕਾਰਡ',
        'report': '🚨 ਰਿਪੋਰਟ', 'no_poems': 'ਕੋਈ ਕਵਿਤਾ ਨਹੀਂ',
        'no_poems_sub': 'ਪਹਿਲੀ ਕਵਿਤਾ ਲਿਖੋ!',
        'empty_feed': 'ਫੀਡ ਖਾਲੀ ਹੈ', 'empty_feed_sub': 'ਕਵੀਆਂ ਨੂੰ ਫਾਲੋ ਕਰੋ',
        'search_poets': 'ਕਵੀ ਲੱਭੋ', 'read_more': 'ਪੂਰੀ ਕਵਿਤਾ →', 'back': '← ਵਾਪਸ',
        'terms': 'ਨਿਯਮ', 'privacy': 'ਗੋਪਨੀਯਤਾ', 'about': 'ਸਾਡੇ ਬਾਰੇ',
        'contact': 'ਸੰਪਰਕ',
    },
}

def get_t():
    """Get translations for current language."""
    lang = session.get('lang', 'hi')
    return TRANSLATIONS.get(lang, TRANSLATIONS['hi'])

def check_and_award_badges(user_id):
    poem_count    = query("SELECT COUNT(*) as c FROM poems WHERE user_id=? AND is_draft=0", (user_id,), one=True)['c']
    like_count    = query("SELECT COUNT(*) as c FROM likes l JOIN poems p ON l.poem_id=p.id WHERE p.user_id=?", (user_id,), one=True)['c']
    follower_count= query("SELECT COUNT(*) as c FROM follows WHERE following_id=?", (user_id,), one=True)['c']
    comment_count = query("SELECT COUNT(*) as c FROM comments WHERE user_id=?", (user_id,), one=True)['c']
    following_count=query("SELECT COUNT(*) as c FROM follows WHERE follower_id=?", (user_id,), one=True)['c']
    def award(key):
        try: execute("INSERT OR IGNORE INTO badges (user_id,badge_key) VALUES (?,?)", (user_id, key))
        except: pass
    if poem_count >= 1:  award('first_poem')
    if poem_count >= 10: award('ten_poems')
    if poem_count >= 50: award('fifty_poems')
    if like_count >= 1:  award('first_like')
    if like_count >= 100:award('hundred_likes')
    if follower_count >= 1: award('first_follow')
    if comment_count >= 10: award('commentator')
    if following_count >= 10: award('social')

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def add_notification(user_id, message, link=''):
    execute("INSERT INTO notifications (user_id,message,link) VALUES (?,?,?)", (user_id, message, link))

def get_unread_notif_count():
    if 'user_id' not in session: return 0
    r = query("SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND is_read=0", (session['user_id'],), one=True)
    return r['c'] if r else 0

def get_unread_msg_count():
    if 'user_id' not in session: return 0
    r = query("SELECT COUNT(*) as c FROM messages WHERE receiver_id=? AND is_read=0", (session['user_id'],), one=True)
    return r['c'] if r else 0

def get_active_announcement():
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return query("SELECT * FROM announcements WHERE schedule_at IS NULL OR schedule_at <= ? ORDER BY created_at DESC LIMIT 1", (now,), one=True)

def get_poet_of_week():
    return query("SELECT * FROM users WHERE poet_of_week=1 LIMIT 1", one=True)

def time_ago(dt_str):
    try:
        dt   = datetime.strptime(dt_str[:19], '%Y-%m-%d %H:%M:%S')
        diff = datetime.now() - dt
        s    = int(diff.total_seconds())
        if s < 60:   return f"{s}s ago"
        if s < 3600: return f"{s//60}m ago"
        if s < 86400:return f"{s//3600}h ago"
        return f"{s//86400}d ago"
    except: return dt_str[:10]

app.jinja_env.globals['get_unread_notif_count'] = get_unread_notif_count
app.jinja_env.globals['get_unread_msg_count']   = get_unread_msg_count
app.jinja_env.globals['get_active_announcement']= get_active_announcement
app.jinja_env.globals['get_t']                   = get_t
app.jinja_env.globals['TRANSLATIONS']             = TRANSLATIONS
app.jinja_env.globals['get_poet_of_week']       = get_poet_of_week
app.jinja_env.filters['time_ago']               = time_ago

def _delete_poem_cascade(pid):
    for t,col in [('likes','poem_id'),('comments','poem_id'),('bookmarks','poem_id'),
                  ('collection_poems','poem_id'),('reports','poem_id'),('poem_views','poem_id')]:
        try: execute(f"DELETE FROM {t} WHERE {col}=?", (pid,))
        except: pass
    execute("DELETE FROM poems WHERE id=?", (pid,))

# ─── DECORATORS ───────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if 'user_id' not in session:
            flash('पहले लॉगिन करें।','warning'); return redirect(url_for('login'))
        return f(*a, **kw)
    return dec

def admin_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if 'admin_id' not in session: return redirect(url_for('admin_login'))
        u = query("SELECT role FROM users WHERE id=?", (session['admin_id'],), one=True)
        if not u or u['role'] != 'admin': session.clear(); return redirect(url_for('admin_login'))
        return f(*a, **kw)
    return dec

# ══════════════════════════════════════════════════════════════════════════════
# USER ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    cats     = [c['name'] for c in query("SELECT name FROM categories ORDER BY name")]
    featured = query("""SELECT p.*, u.username, u.profile_pic,
        (SELECT COUNT(*) FROM likes WHERE poem_id=p.id) as like_count
        FROM poems p JOIN users u ON p.user_id=u.id
        WHERE p.is_featured=1 AND p.is_draft=0 ORDER BY p.created_at DESC LIMIT 3""")
    poems = query("""SELECT p.*, u.username, u.profile_pic,
        (SELECT COUNT(*) FROM likes    WHERE poem_id=p.id) as like_count,
        (SELECT COUNT(*) FROM comments WHERE poem_id=p.id) as comment_count
        FROM poems p JOIN users u ON p.user_id=u.id
        WHERE p.is_draft=0 ORDER BY p.created_at DESC LIMIT 30""")
    trending = query("""SELECT p.*, u.username,
        (SELECT COUNT(*) FROM likes WHERE poem_id=p.id) as like_count
        FROM poems p JOIN users u ON p.user_id=u.id
        WHERE p.is_draft=0 ORDER BY like_count DESC, p.views DESC LIMIT 8""")
    top_poets = query("""SELECT u.*,
        COALESCE((SELECT COUNT(*) FROM likes l JOIN poems pp ON l.poem_id=pp.id WHERE pp.user_id=u.id),0) as total_likes
        FROM users u WHERE u.role='user' ORDER BY total_likes DESC LIMIT 5""")
    liked_set = set()
    bm_set = set()
    if session.get('user_id'):
        uid = session['user_id']
        liked_set = {r['poem_id'] for r in query("SELECT poem_id FROM likes WHERE user_id=?", (uid,))}
        bm_set    = {r['poem_id'] for r in query("SELECT poem_id FROM bookmarks WHERE user_id=?", (uid,))}
    stats = {
        'poems':    (query("SELECT COUNT(*) as c FROM poems WHERE is_draft=0", one=True) or {'c':0})['c'],
        'users':    (query("SELECT COUNT(*) as c FROM users", one=True) or {'c':0})['c'],
        'poets':    (query("SELECT COUNT(*) as c FROM users WHERE role='user'", one=True) or {'c':0})['c'],
        'likes':    (query("SELECT COUNT(*) as c FROM likes", one=True) or {'c':0})['c'],
        'comments': (query("SELECT COUNT(*) as c FROM comments", one=True) or {'c':0})['c'],
    }
    hero_poem = query("""SELECT p.*, u.username, (SELECT COUNT(*) FROM likes WHERE poem_id=p.id) as like_count FROM poems p JOIN users u ON p.user_id=u.id WHERE p.is_draft=0 AND length(p.content)>80 ORDER BY like_count DESC LIMIT 3""")
    hero_poem = hero_poem[0] if hero_poem else None
    return render_template('user/index.html', poems=poems, trending=trending,
                           categories=cats, featured=featured, top_poets=top_poets,
                           liked_set=liked_set, bm_set=bm_set, stats=stats, hero_poem=hero_poem)

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        u,e,p = request.form['username'].strip(), request.form['email'].strip(), request.form['password']
        if query("SELECT id FROM users WHERE username=?", (u,), one=True):
            flash('Username पहले से लिया जा चुका है।','error'); return redirect(url_for('signup'))
        if query("SELECT id FROM users WHERE email=?", (e,), one=True):
            flash('Email पहले से registered है।','error'); return redirect(url_for('signup'))
        uid = execute("INSERT INTO users (username,email,password_hash) VALUES (?,?,?)",
                      (u, e, generate_password_hash(p)))
        session['user_id'] = uid; session['username'] = u
        flash('शायरी की दुनिया में आपका स्वागत है! ✨','success')
        return redirect(url_for('index'))
    return render_template('user/signup.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u,p = request.form['username'].strip(), request.form['password']
        user = query("SELECT * FROM users WHERE username=?", (u,), one=True)
        if user and user['is_banned']:
            flash('आपका account ban है।','error'); return redirect(url_for('login'))
        if user and check_password_hash(user['password_hash'], p):
            session['user_id'] = user['id']; session['username'] = user['username']
            flash(f'वापसी पर स्वागत है, {u}! 🌙','success')
            return redirect(url_for('index'))
        flash('गलत username या password।','error')
    return render_template('user/login.html')

@app.route('/logout')
def logout():
    session.clear(); flash('Logout हो गए।','info'); return redirect(url_for('index'))

# ─── POEMS ────────────────────────────────────────────────────────────────────

@app.route('/write', methods=['GET','POST'])
@login_required
def write():
    cats = query("SELECT name FROM categories ORDER BY name")
    if request.method == 'POST':
        title       = request.form['title'].strip()
        content     = request.form['content'].strip()
        category    = request.form.get('category','सामान्य')
        language    = request.form.get('language','Hindi')
        theme       = request.form.get('theme','default')
        font        = request.form.get('font','garamond')
        dedicated_to= request.form.get('dedicated_to','').strip()
        is_draft    = 1 if request.form.get('save_draft') else 0
        if not title or not content:
            flash('Title और content ज़रूरी हैं।','error'); return redirect(url_for('write'))
        pid = execute("INSERT INTO poems (title,content,category,language,theme,font,dedicated_to,user_id,is_draft) VALUES (?,?,?,?,?,?,?,?,?)",
                      (title,content,category,language,theme,font,dedicated_to,session['user_id'],is_draft))
        if not is_draft: check_and_award_badges(session['user_id'])
        flash('Draft सेव हो गया! ✏️' if is_draft else 'कविता publish हो गई! ✨', 'info' if is_draft else 'success')
        return redirect(url_for('profile', username=session['username']) if is_draft else url_for('poem', poem_id=pid))
    return render_template('user/write.html', cats=cats, poem=None)

@app.route('/poem/<int:poem_id>')
def poem(poem_id):
    p = query("""SELECT p.*, u.username, u.bio, u.profile_pic,
        (SELECT COUNT(*) FROM likes WHERE poem_id=p.id) as like_count
        FROM poems p JOIN users u ON p.user_id=u.id WHERE p.id=?""", (poem_id,), one=True)
    if not p:
        flash('कविता नहीं मिली।','error'); return redirect(url_for('index'))

    # Count view only once per user/session, never for owner
    viewer_id = session.get('user_id')
    if viewer_id != p['user_id']:
        vkey = f'v_{poem_id}'
        if not session.get(vkey):
            execute("UPDATE poems SET views=views+1 WHERE id=?", (poem_id,))
            try: execute("INSERT INTO poem_views (poem_id,viewer_id) VALUES (?,?)", (poem_id, viewer_id))
            except: pass
            session[vkey] = True

    # All comments (both top-level and replies) — visible to everyone
    all_comments = query("""SELECT c.*, u.username, u.profile_pic
        FROM comments c JOIN users u ON c.user_id=u.id
        WHERE c.poem_id=? ORDER BY c.created_at ASC""", (poem_id,))

    top_comments = [c for c in all_comments if c['parent_id'] is None]
    replies_map  = {}
    for r in all_comments:
        if r['parent_id'] is not None:
            replies_map.setdefault(r['parent_id'], []).append(r)

    liked = bookmarked = False
    my_collections = []
    if viewer_id:
        liked      = bool(query("SELECT id FROM likes WHERE user_id=? AND poem_id=?", (viewer_id, poem_id), one=True))
        bookmarked = bool(query("SELECT id FROM bookmarks WHERE user_id=? AND poem_id=?", (viewer_id, poem_id), one=True))
        my_collections = query("SELECT * FROM collections WHERE user_id=? ORDER BY name", (viewer_id,))

    is_following = False
    if viewer_id and viewer_id != p['user_id']:
        is_following = bool(query("SELECT id FROM follows WHERE follower_id=? AND following_id=?",
                                  (viewer_id, p['user_id']), one=True))
    return render_template('user/poem.html', poem=p, top_comments=top_comments,
                           all_comments=all_comments, replies_map=replies_map,
                           liked=liked, is_following=is_following,
                           bookmarked=bookmarked, my_collections=my_collections)

@app.route('/poem/<int:poem_id>/edit', methods=['GET','POST'])
@login_required
def edit_poem(poem_id):
    p    = query("SELECT * FROM poems WHERE id=? AND user_id=?", (poem_id, session['user_id']), one=True)
    cats = query("SELECT name FROM categories ORDER BY name")
    if not p: flash('अनुमति नहीं।','error'); return redirect(url_for('index'))
    if request.method == 'POST':
        is_draft = 1 if request.form.get('save_draft') else 0
        execute("""UPDATE poems SET title=?,content=?,category=?,language=?,
                   theme=?,font=?,dedicated_to=?,is_draft=? WHERE id=?""",
                (request.form['title'], request.form['content'],
                 request.form.get('category','सामान्य'), request.form.get('language','Hindi'),
                 request.form.get('theme','default'), request.form.get('font','garamond'),
                 request.form.get('dedicated_to','').strip(), is_draft, poem_id))
        flash('कविता update हो गई!','success')
        return redirect(url_for('poem', poem_id=poem_id))
    return render_template('user/write.html', poem=p, cats=cats)

@app.route('/poem/<int:poem_id>/delete', methods=['POST'])
@login_required
def delete_poem(poem_id):
    p = query("SELECT * FROM poems WHERE id=? AND user_id=?", (poem_id, session['user_id']), one=True)
    if not p: flash('अनुमति नहीं।','error'); return redirect(url_for('index'))
    _delete_poem_cascade(poem_id)
    flash('कविता delete हो गई।','info')
    return redirect(url_for('profile', username=session['username']))

@app.route('/like/<int:poem_id>', methods=['POST'])
@login_required
def like(poem_id):
    p = query("SELECT user_id, title FROM poems WHERE id=?", (poem_id,), one=True)
    if query("SELECT id FROM likes WHERE user_id=? AND poem_id=?", (session['user_id'], poem_id), one=True):
        execute("DELETE FROM likes WHERE user_id=? AND poem_id=?", (session['user_id'], poem_id))
    else:
        execute("INSERT OR IGNORE INTO likes (user_id,poem_id) VALUES (?,?)", (session['user_id'], poem_id))
        if p and p['user_id'] != session['user_id']:
            add_notification(p['user_id'], f"{session['username']} ने '{p['title']}' को ❤️ like किया",
                             url_for('poem', poem_id=poem_id))
        check_and_award_badges(p['user_id'] if p else session['user_id'])
    return redirect(request.referrer or url_for('poem', poem_id=poem_id))

# ─── COMMENTS ─────────────────────────────────────────────────────────────────

@app.route('/comment/<int:poem_id>', methods=['POST'])
@login_required
def comment(poem_id):
    content   = request.form['content'].strip()
    parent_id = request.form.get('parent_id') or None
    if parent_id: parent_id = int(parent_id)
    if content:
        execute("INSERT INTO comments (content,user_id,poem_id,parent_id) VALUES (?,?,?,?)",
                (content, session['user_id'], poem_id, parent_id))
        p = query("SELECT user_id, title FROM poems WHERE id=?", (poem_id,), one=True)
        if p and p['user_id'] != session['user_id']:
            add_notification(p['user_id'], f"{session['username']} ने '{p['title']}' पर comment किया",
                             url_for('poem', poem_id=poem_id))
        check_and_award_badges(session['user_id'])
    return redirect(url_for('poem', poem_id=poem_id))

@app.route('/comment/<int:cid>/delete', methods=['POST'])
@login_required
def delete_comment(cid):
    c = query("SELECT * FROM comments WHERE id=?", (cid,), one=True)
    if c and c['user_id'] == session['user_id']:
        execute("DELETE FROM comments WHERE parent_id=?", (cid,))
        execute("DELETE FROM comments WHERE id=?", (cid,))
    return redirect(request.referrer or url_for('index'))

# ─── BOOKMARK ─────────────────────────────────────────────────────────────────

@app.route('/bookmark/<int:poem_id>', methods=['POST'])
@login_required
def bookmark(poem_id):
    if query("SELECT id FROM bookmarks WHERE user_id=? AND poem_id=?", (session['user_id'], poem_id), one=True):
        execute("DELETE FROM bookmarks WHERE user_id=? AND poem_id=?", (session['user_id'], poem_id))
        flash('Bookmark हटा दिया।','info')
    else:
        execute("INSERT OR IGNORE INTO bookmarks (user_id,poem_id) VALUES (?,?)", (session['user_id'], poem_id))
        flash('Bookmark हो गया! 🔖','success')
    return redirect(request.referrer or url_for('poem', poem_id=poem_id))

@app.route('/bookmarks')
@login_required
def bookmarks():
    poems = query("""SELECT p.*, u.username,
        (SELECT COUNT(*) FROM likes WHERE poem_id=p.id) as like_count
        FROM bookmarks b JOIN poems p ON b.poem_id=p.id JOIN users u ON p.user_id=u.id
        WHERE b.user_id=? ORDER BY b.created_at DESC""", (session['user_id'],))
    return render_template('user/bookmarks.html', poems=poems)

# ─── COLLECTIONS ──────────────────────────────────────────────────────────────

@app.route('/collections')
@login_required
def collections():
    cols = query("""SELECT c.*, COUNT(cp.poem_id) as poem_count
        FROM collections c LEFT JOIN collection_poems cp ON c.id=cp.collection_id
        WHERE c.user_id=? GROUP BY c.id ORDER BY c.created_at DESC""", (session['user_id'],))
    return render_template('user/collections.html', collections=cols)

@app.route('/collections/create', methods=['POST'])
@login_required
def create_collection():
    name = request.form['name'].strip()
    if name:
        execute("INSERT INTO collections (name,user_id) VALUES (?,?)", (name, session['user_id']))
        flash(f'Collection "{name}" बन गया! 📂','success')
    return redirect(url_for('collections'))

@app.route('/collections/<int:col_id>')
@login_required
def view_collection(col_id):
    col = query("SELECT * FROM collections WHERE id=? AND user_id=?", (col_id, session['user_id']), one=True)
    if not col: flash('Collection नहीं मिला।','error'); return redirect(url_for('collections'))
    poems = query("""SELECT p.*, u.username,
        (SELECT COUNT(*) FROM likes WHERE poem_id=p.id) as like_count
        FROM collection_poems cp JOIN poems p ON cp.poem_id=p.id JOIN users u ON p.user_id=u.id
        WHERE cp.collection_id=? ORDER BY cp.id DESC""", (col_id,))
    return render_template('user/collection_detail.html', collection=col, poems=poems)

@app.route('/collections/<int:col_id>/add/<int:poem_id>', methods=['POST'])
@login_required
def add_to_collection(col_id, poem_id):
    col = query("SELECT * FROM collections WHERE id=? AND user_id=?", (col_id, session['user_id']), one=True)
    if col:
        execute("INSERT OR IGNORE INTO collection_poems (collection_id,poem_id) VALUES (?,?)", (col_id, poem_id))
        flash('Collection में जोड़ी गई! ✅','success')
    return redirect(request.referrer or url_for('index'))

@app.route('/collections/<int:col_id>/delete', methods=['POST'])
@login_required
def delete_collection(col_id):
    execute("DELETE FROM collection_poems WHERE collection_id=?", (col_id,))
    execute("DELETE FROM collections WHERE id=? AND user_id=?", (col_id, session['user_id']))
    flash('Collection delete हो गया।','info')
    return redirect(url_for('collections'))

# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────

@app.route('/notifications')
@login_required
def notifications():
    notifs = query("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (session['user_id'],))
    execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (session['user_id'],))
    return render_template('user/notifications.html', notifications=notifs)

# ─── FEED ─────────────────────────────────────────────────────────────────────

@app.route('/feed')
@login_required
def feed():
    poems = query("""SELECT p.*, u.username, u.profile_pic,
        (SELECT COUNT(*) FROM likes    WHERE poem_id=p.id) as like_count,
        (SELECT COUNT(*) FROM comments WHERE poem_id=p.id) as comment_count
        FROM poems p JOIN users u ON p.user_id=u.id
        JOIN follows f ON f.following_id=p.user_id
        WHERE f.follower_id=? AND p.is_draft=0
        ORDER BY p.created_at DESC LIMIT 30""", (session['user_id'],))
    return render_template('user/feed.html', poems=poems)

# ─── MESSAGES ─────────────────────────────────────────────────────────────────

@app.route('/messages')
@login_required
def messages():
    convos = query("""SELECT DISTINCT
        CASE WHEN m.sender_id=? THEN m.receiver_id ELSE m.sender_id END as other_id,
        u.username, u.profile_pic,
        MAX(m.created_at) as last_time,
        SUM(CASE WHEN m.receiver_id=? AND m.is_read=0 THEN 1 ELSE 0 END) as unread
        FROM messages m
        JOIN users u ON u.id=CASE WHEN m.sender_id=? THEN m.receiver_id ELSE m.sender_id END
        WHERE m.sender_id=? OR m.receiver_id=?
        GROUP BY other_id ORDER BY last_time DESC""",
        (session['user_id'],)*5)
    return render_template('user/messages.html', convos=convos)

@app.route('/messages/<int:other_id>', methods=['GET','POST'])
@login_required
def conversation(other_id):
    other = query("SELECT * FROM users WHERE id=?", (other_id,), one=True)
    if not other: flash('User नहीं मिला।','error'); return redirect(url_for('messages'))
    if request.method == 'POST':
        content = request.form.get('content','').strip()
        file_path = ''
        file_type = ''
        f = request.files.get('msg_file')
        if f and f.filename and allowed_file(f.filename):
            import uuid
            ext = f.filename.rsplit('.',1)[1].lower()
            fname = str(uuid.uuid4())[:8] + '_msg.' + ext
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            file_path = fname
            file_type = 'image' if ext in ['jpg','jpeg','png','gif','webp'] else 'file'
        if content or file_path:
            execute("INSERT INTO messages (sender_id,receiver_id,content,file_path,file_type) VALUES (?,?,?,?,?)",
                    (session['user_id'], other_id, content, file_path, file_type))
            add_notification(other_id, f"{session['username']} ने आपको message किया 💌",
                             url_for('conversation', other_id=session['user_id']))
        return redirect(url_for('conversation', other_id=other_id))
    msgs = query("""SELECT m.*, u.username, u.profile_pic FROM messages m
        JOIN users u ON m.sender_id=u.id
        WHERE (m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?)
        ORDER BY m.created_at""", (session['user_id'], other_id, other_id, session['user_id']))
    execute("UPDATE messages SET is_read=1 WHERE receiver_id=? AND sender_id=?",
            (session['user_id'], other_id))
    return render_template('user/conversation.html', other=other, msgs=msgs)

# ─── PROFILE ──────────────────────────────────────────────────────────────────

@app.route('/profile/<username>')
def profile(username):
    user = query("SELECT * FROM users WHERE username=?", (username,), one=True)
    if not user: flash('शायर नहीं मिला।','error'); return redirect(url_for('index'))
    poems = query("""SELECT p.*,(SELECT COUNT(*) FROM likes WHERE poem_id=p.id) as like_count
        FROM poems p WHERE p.user_id=? AND p.is_draft=0 ORDER BY p.created_at DESC""", (user['id'],))
    drafts = []
    if session.get('user_id') == user['id']:
        drafts = query("SELECT * FROM poems WHERE user_id=? AND is_draft=1 ORDER BY created_at DESC", (user['id'],))
    total_likes     = sum(p['like_count'] for p in poems)
    followers_count = query("SELECT COUNT(*) as c FROM follows WHERE following_id=?", (user['id'],), one=True)['c']
    following_count = query("SELECT COUNT(*) as c FROM follows WHERE follower_id=?",  (user['id'],), one=True)['c']
    is_following = False
    is_mutual    = False
    if 'user_id' in session and session['user_id'] != user['id']:
        is_following = bool(query("SELECT id FROM follows WHERE follower_id=? AND following_id=?",
                                  (session['user_id'], user['id']), one=True))
        they_follow  = bool(query("SELECT id FROM follows WHERE follower_id=? AND following_id=?",
                                  (user['id'], session['user_id']), one=True))
        is_mutual = is_following and they_follow
    cols = query("""SELECT c.*, COUNT(cp.poem_id) as poem_count FROM collections c
        LEFT JOIN collection_poems cp ON c.id=cp.collection_id
        WHERE c.user_id=? GROUP BY c.id ORDER BY c.created_at DESC""", (user['id'],))
    user_badges = query("SELECT badge_key, earned_at FROM badges WHERE user_id=? ORDER BY earned_at", (user['id'],))
    mutual_count = query("""SELECT COUNT(*) as c FROM follows f1
        JOIN follows f2 ON f1.following_id=f2.follower_id AND f1.follower_id=f2.following_id
        WHERE f1.follower_id=?""", (user['id'],), one=True)['c']
    return render_template('user/profile.html', user=user, poems=poems, drafts=drafts,
                           total_likes=total_likes, followers_count=followers_count,
                           following_count=following_count, is_following=is_following,
                           is_mutual=is_mutual, mutual_count=mutual_count, collections=cols,
                           user_badges=user_badges, BADGES=BADGES)

@app.route('/profile/<username>/edit', methods=['GET','POST'])
@login_required
def edit_profile(username):
    if session['username'] != username:
        flash('अनुमति नहीं।','error'); return redirect(url_for('profile', username=username))
    user = query("SELECT * FROM users WHERE username=?", (username,), one=True)
    if request.method == 'POST':
        bio = request.form.get('bio','').strip()
        pic = user['profile_pic']
        cover = user['cover_pic']
        for field, colname in [('profile_pic', 'profile_pic'), ('cover_pic', 'cover_pic')]:
            f = request.files.get(field)
            if f and f.filename and allowed_file(f.filename):
                fname = secure_filename(f"{session['user_id']}_{field}_{f.filename}")
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                if field == 'profile_pic': pic = fname
                else: cover = fname
        execute("UPDATE users SET bio=?,profile_pic=?,cover_pic=? WHERE id=?",
                (bio, pic, cover, session['user_id']))
        flash('Profile update हो गई! ✅','success')
        return redirect(url_for('profile', username=username))
    return render_template('user/edit_profile.html', user=user)

@app.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    if user_id == session['user_id']: return redirect(request.referrer)
    if query("SELECT id FROM follows WHERE follower_id=? AND following_id=?", (session['user_id'], user_id), one=True):
        execute("DELETE FROM follows WHERE follower_id=? AND following_id=?", (session['user_id'], user_id))
    else:
        execute("INSERT OR IGNORE INTO follows (follower_id,following_id) VALUES (?,?)", (session['user_id'], user_id))
        add_notification(user_id, f"{session['username']} ने आपको follow किया! 🌟",
                         url_for('profile', username=session['username']))
        check_and_award_badges(user_id)
    return redirect(request.referrer)

@app.route('/profile/<username>/followers')
def followers_page(username):
    user = query("SELECT * FROM users WHERE username=?", (username,), one=True)
    if not user: return redirect(url_for('index'))
    followers = query("""SELECT u.id, u.username, u.bio, u.profile_pic, u.poet_of_week,
        (SELECT COUNT(*) FROM poems WHERE user_id=u.id AND is_draft=0) as poem_count
        FROM follows f JOIN users u ON f.follower_id=u.id
        WHERE f.following_id=? ORDER BY u.username""", (user['id'],))
    return render_template('user/follow_list.html', users=followers,
                           title=f"Followers of {username}", back=username, list_type='followers')

@app.route('/profile/<username>/following')
def following_page(username):
    user = query("SELECT * FROM users WHERE username=?", (username,), one=True)
    if not user: return redirect(url_for('index'))
    following = query("""SELECT u.id, u.username, u.bio, u.profile_pic, u.poet_of_week,
        (SELECT COUNT(*) FROM poems WHERE user_id=u.id AND is_draft=0) as poem_count
        FROM follows f JOIN users u ON f.following_id=u.id
        WHERE f.follower_id=? ORDER BY u.username""", (user['id'],))
    return render_template('user/follow_list.html', users=following,
                           title=f"{username} is Following", back=username, list_type='following')

@app.route('/mutual/<username>')
@login_required
def mutual_page(username):
    user = query("SELECT * FROM users WHERE username=?", (username,), one=True)
    if not user: return redirect(url_for('index'))
    mutuals = query("""SELECT u.* FROM follows f1
        JOIN follows f2 ON f1.following_id=f2.follower_id AND f1.follower_id=f2.following_id
        JOIN users u ON u.id=f1.following_id
        WHERE f1.follower_id=?""", (user['id'],))
    return render_template('user/follow_list.html', users=mutuals,
                           title=f"{username} के Mutual Friends", back=username)

# ─── POEM STATS ───────────────────────────────────────────────────────────────

@app.route('/poem/<int:poem_id>/stats')
@login_required
def poem_stats(poem_id):
    p = query("SELECT * FROM poems WHERE id=? AND user_id=?", (poem_id, session['user_id']), one=True)
    if not p: flash('अनुमति नहीं।','error'); return redirect(url_for('index'))
    likers = query("""SELECT u.username, u.profile_pic FROM likes l
        JOIN users u ON l.user_id=u.id WHERE l.poem_id=?""", (poem_id,))
    return render_template('user/poem_stats.html', poem=p, likers=likers)

# ─── DISCOVERY ────────────────────────────────────────────────────────────────

@app.route('/trending')
def trending():
    poems = query("""SELECT p.*, u.username, u.profile_pic,
        (SELECT COUNT(*) FROM likes    WHERE poem_id=p.id) as like_count,
        (SELECT COUNT(*) FROM comments WHERE poem_id=p.id) as comment_count
        FROM poems p JOIN users u ON p.user_id=u.id WHERE p.is_draft=0
        ORDER BY (like_count*2 + p.views + comment_count*3) DESC LIMIT 30""")
    return render_template('user/trending.html', poems=poems)

@app.route('/leaderboard')
def leaderboard():
    poets = query("""SELECT u.*,
        COUNT(DISTINCT p.id) as poem_count,
        COALESCE((SELECT COUNT(*) FROM likes l JOIN poems pp ON l.poem_id=pp.id WHERE pp.user_id=u.id),0) as total_likes,
        (SELECT COUNT(*) FROM follows WHERE following_id=u.id) as followers
        FROM users u LEFT JOIN poems p ON u.id=p.user_id AND p.is_draft=0
        WHERE u.role='user' GROUP BY u.id ORDER BY total_likes DESC, poem_count DESC LIMIT 20""")
    return render_template('user/leaderboard.html', poets=poets)

@app.route('/category/<cat>')
def category(cat):
    poems = query("""SELECT p.*, u.username,
        (SELECT COUNT(*) FROM likes WHERE poem_id=p.id) as like_count
        FROM poems p JOIN users u ON p.user_id=u.id
        WHERE p.category=? AND p.is_draft=0 ORDER BY p.created_at DESC""", (cat,))
    return render_template('user/category.html', poems=poems, category=cat)

@app.route('/categories')
def categories_page():
    cats = query("""SELECT c.name, c.description, COUNT(p.id) as poem_count
        FROM categories c LEFT JOIN poems p ON p.category=c.name AND p.is_draft=0
        GROUP BY c.name ORDER BY poem_count DESC""")
    return render_template('user/categories_page.html', categories=cats)

@app.route('/search')
def search():
    q    = request.args.get('q','').strip()
    lang = request.args.get('lang','')
    cat  = request.args.get('cat','')
    sort = request.args.get('sort','new')
    cats = query("SELECT name FROM categories ORDER BY name")
    poems, poets = [], []
    if q or lang or cat:
        sql  = """SELECT p.*, u.username,
            (SELECT COUNT(*) FROM likes WHERE poem_id=p.id) as like_count
            FROM poems p JOIN users u ON p.user_id=u.id WHERE p.is_draft=0"""
        args = []
        if q:    sql += " AND (p.title LIKE ? OR p.content LIKE ?)"; args += [f'%{q}%',f'%{q}%']
        if lang: sql += " AND p.language=?"; args.append(lang)
        if cat:  sql += " AND p.category=?"; args.append(cat)
        sql += {'likes':' ORDER BY like_count DESC','views':' ORDER BY p.views DESC'}.get(sort,' ORDER BY p.created_at DESC')
        poems = query(sql, args)
        if q: poets = query("SELECT * FROM users WHERE username LIKE ? AND role='user'", (f'%{q}%',))
    return render_template('user/search.html', poems=poems, poets=poets,
                           query=q, lang_filter=lang, cat_filter=cat, sort=sort, cats=cats)

@app.route('/report/poem/<int:poem_id>', methods=['POST'])
@login_required
def report_poem(poem_id):
    reason = request.form.get('reason','').strip()
    if reason:
        execute("INSERT INTO reports (reporter_id,poem_id,reason) VALUES (?,?,?)",
                (session['user_id'], poem_id, reason))
        flash('Report भेज दी गई। ✅','success')
    return redirect(request.referrer or url_for('poem', poem_id=poem_id))

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin-login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        u,p  = request.form['username'].strip(), request.form['password']
        user = query("SELECT * FROM users WHERE username=? AND role='admin'", (u,), one=True)
        if user and check_password_hash(user['password_hash'], p):
            session['admin_id'] = user['id']; session['admin_name'] = user['username']
            return redirect(url_for('admin_dashboard'))
        flash('गलत admin credentials।','error')
    return render_template('admin/login.html')

@app.route('/admin-logout')
def admin_logout():
    session.pop('admin_id',None); session.pop('admin_name',None)
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    stats = {
        'users':     query("SELECT COUNT(*) as c FROM users WHERE role='user'", one=True)['c'],
        'poems':     query("SELECT COUNT(*) as c FROM poems WHERE is_draft=0",  one=True)['c'],
        'likes':     query("SELECT COUNT(*) as c FROM likes",                   one=True)['c'],
        'comments':  query("SELECT COUNT(*) as c FROM comments",                one=True)['c'],
        'reports':   query("SELECT COUNT(*) as c FROM reports WHERE status='pending'", one=True)['c'],
        'bookmarks': query("SELECT COUNT(*) as c FROM bookmarks",               one=True)['c'],
    }
    chart_poems = [dict(r) for r in reversed(query(
        "SELECT DATE(created_at) as day, COUNT(*) as count FROM poems WHERE is_draft=0 GROUP BY day ORDER BY day DESC LIMIT 7"))]
    chart_users = [dict(r) for r in reversed(query(
        "SELECT DATE(joined_at) as day, COUNT(*) as count FROM users GROUP BY day ORDER BY day DESC LIMIT 7"))]
    top_poems = query("""SELECT p.*, u.username,
        (SELECT COUNT(*) FROM likes WHERE poem_id=p.id) as like_count
        FROM poems p JOIN users u ON p.user_id=u.id WHERE p.is_draft=0
        ORDER BY like_count DESC LIMIT 5""")
    top_poets = query("""SELECT u.username,
        COALESCE((SELECT COUNT(*) FROM likes l JOIN poems pp ON l.poem_id=pp.id WHERE pp.user_id=u.id),0) as total_likes
        FROM users u WHERE u.role='user' ORDER BY total_likes DESC LIMIT 5""")
    recent_poems = query("SELECT p.*, u.username FROM poems p JOIN users u ON p.user_id=u.id WHERE p.is_draft=0 ORDER BY p.created_at DESC LIMIT 5")
    recent_users = query("SELECT * FROM users ORDER BY joined_at DESC LIMIT 5")
    return render_template('admin/dashboard.html', stats=stats,
                           chart_poems=chart_poems, chart_users=chart_users,
                           top_poems=top_poems, top_poets=top_poets,
                           recent_poems=recent_poems, recent_users=recent_users)

@app.route('/admin/users')
@admin_required
def admin_users():
    users = query("""SELECT u.*, COUNT(DISTINCT p.id) as poem_count
        FROM users u LEFT JOIN poems p ON u.id=p.user_id
        GROUP BY u.id ORDER BY u.joined_at DESC""")
    return render_template('admin/users.html', users=users)

@app.route('/admin/user/<int:uid>/delete', methods=['POST'])
@admin_required
def admin_delete_user(uid):
    for p in query("SELECT id FROM poems WHERE user_id=?", (uid,)):
        _delete_poem_cascade(p['id'])
    for t in ['follows','bookmarks','collections','notifications','badges']:
        execute(f"DELETE FROM {t} WHERE {'follower_id=? OR following_id=?' if t=='follows' else 'user_id=?'}",
                (uid,uid) if t=='follows' else (uid,))
    execute("DELETE FROM messages WHERE sender_id=? OR receiver_id=?", (uid,uid))
    execute("DELETE FROM users WHERE id=?", (uid,))
    flash('User delete हो गया।','info')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:uid>/promote', methods=['POST'])
@admin_required
def admin_promote(uid):
    execute("UPDATE users SET role='admin' WHERE id=?", (uid,))
    flash('User admin बन गया।','success'); return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:uid>/ban', methods=['POST'])
@admin_required
def admin_ban(uid):
    u = query("SELECT is_banned FROM users WHERE id=?", (uid,), one=True)
    execute("UPDATE users SET is_banned=? WHERE id=?", (0 if u['is_banned'] else 1, uid))
    flash('Ban status बदल गई।','info'); return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:uid>/poet_of_week', methods=['POST'])
@admin_required
def admin_poet_of_week(uid):
    execute("UPDATE users SET poet_of_week=0")
    execute("UPDATE users SET poet_of_week=1 WHERE id=?", (uid,))
    try: execute("INSERT OR IGNORE INTO badges (user_id,badge_key) VALUES (?,?)", (uid,'poet_of_week'))
    except: pass
    u = query("SELECT username FROM users WHERE id=?", (uid,), one=True)
    add_notification(uid, "🎉 आप इस हफ्ते के Poet of the Week हैं! 👑",
                     url_for('profile', username=u['username']))
    flash(f'{u["username"]} को Poet of the Week बनाया! 👑','success')
    return redirect(url_for('admin_users'))

@app.route('/admin/poems')
@admin_required
def admin_poems():
    poems = query("""SELECT p.*, u.username,
        (SELECT COUNT(*) FROM likes    WHERE poem_id=p.id) as like_count,
        (SELECT COUNT(*) FROM comments WHERE poem_id=p.id) as comment_count
        FROM poems p JOIN users u ON p.user_id=u.id ORDER BY p.created_at DESC""")
    return render_template('admin/poems.html', poems=poems)

@app.route('/admin/poem/<int:pid>/delete', methods=['POST'])
@admin_required
def admin_delete_poem(pid):
    _delete_poem_cascade(pid); flash('Poem delete हो गई।','info')
    return redirect(url_for('admin_poems'))

@app.route('/admin/poem/<int:pid>/feature', methods=['POST'])
@admin_required
def admin_feature_poem(pid):
    p = query("SELECT is_featured FROM poems WHERE id=?", (pid,), one=True)
    execute("UPDATE poems SET is_featured=? WHERE id=?", (0 if p['is_featured'] else 1, pid))
    flash('Feature status बदल गई।','success'); return redirect(url_for('admin_poems'))

@app.route('/admin/bulk_delete', methods=['POST'])
@admin_required
def admin_bulk_delete():
    kind = request.form.get('kind'); ids = request.form.getlist('selected_ids')
    if not ids: flash('कोई item select नहीं।','warning'); return redirect(request.referrer)
    for i in ids:
        try:
            iid = int(i)
            if kind == 'poems': _delete_poem_cascade(iid)
            elif kind == 'users':
                for p in query("SELECT id FROM poems WHERE user_id=?", (iid,)): _delete_poem_cascade(p['id'])
                execute("DELETE FROM users WHERE id=?", (iid,))
        except: pass
    flash(f'{len(ids)} items delete हो गए।','success')
    return redirect(url_for('admin_poems') if kind=='poems' else url_for('admin_users'))

@app.route('/admin/comments')
@admin_required
def admin_comments():
    comments = query("""SELECT c.*, u.username, p.title as poem_title
        FROM comments c JOIN users u ON c.user_id=u.id JOIN poems p ON c.poem_id=p.id
        ORDER BY c.created_at DESC""")
    return render_template('admin/comments.html', comments=comments)

@app.route('/admin/comment/<int:cid>/delete', methods=['POST'])
@admin_required
def admin_delete_comment(cid):
    execute("DELETE FROM comments WHERE parent_id=?", (cid,))
    execute("DELETE FROM comments WHERE id=?", (cid,))
    flash('Comment delete हो गई।','info'); return redirect(url_for('admin_comments'))

@app.route('/admin/reports')
@admin_required
def admin_reports():
    reports = query("""SELECT r.*, u.username as reporter, p.title as poem_title
        FROM reports r JOIN users u ON r.reporter_id=u.id
        LEFT JOIN poems p ON r.poem_id=p.id ORDER BY r.created_at DESC""")
    return render_template('admin/reports.html', reports=reports)

@app.route('/admin/report/<int:rid>/resolve', methods=['POST'])
@admin_required
def admin_resolve_report(rid):
    execute("UPDATE reports SET status='resolved' WHERE id=?", (rid,))
    flash('Report resolve हो गई।','success'); return redirect(url_for('admin_reports'))

@app.route('/admin/report/<int:rid>/delete_poem', methods=['POST'])
@admin_required
def admin_report_delete_poem(rid):
    r = query("SELECT poem_id FROM reports WHERE id=?", (rid,), one=True)
    if r and r['poem_id']: _delete_poem_cascade(r['poem_id'])
    execute("UPDATE reports SET status='resolved' WHERE id=?", (rid,))
    flash('Poem delete और report resolve हो गई।','success'); return redirect(url_for('admin_reports'))

@app.route('/admin/announcements', methods=['GET','POST'])
@admin_required
def admin_announcements():
    if request.method == 'POST':
        t,m  = request.form['title'].strip(), request.form['message'].strip()
        sched= request.form.get('schedule_at','').strip() or None
        if t and m:
            execute("INSERT INTO announcements (title,message,admin_id,schedule_at) VALUES (?,?,?,?)",
                    (t,m,session['admin_id'],sched))
            flash('Announcement भेज दी गई! 📢','success')
        return redirect(url_for('admin_announcements'))
    ann = query("SELECT a.*, u.username FROM announcements a JOIN users u ON a.admin_id=u.id ORDER BY a.created_at DESC")
    return render_template('admin/announcements.html', announcements=ann)

@app.route('/admin/announcement/<int:aid>/delete', methods=['POST'])
@admin_required
def admin_delete_announcement(aid):
    execute("DELETE FROM announcements WHERE id=?", (aid,))
    flash('Announcement delete हो गई।','info'); return redirect(url_for('admin_announcements'))

@app.route('/admin/categories', methods=['GET','POST'])
@admin_required
def admin_categories():
    if request.method == 'POST':
        name = request.form['name'].strip(); desc = request.form.get('description','').strip()
        if name:
            try: execute("INSERT INTO categories (name,description) VALUES (?,?)", (name,desc)); flash(f'Category "{name}" जोड़ी गई!','success')
            except: flash('यह category पहले से मौजूद है।','error')
        return redirect(url_for('admin_categories'))
    cats = query("""SELECT c.*, COUNT(p.id) as poem_count
        FROM categories c LEFT JOIN poems p ON p.category=c.name AND p.is_draft=0
        GROUP BY c.id ORDER BY poem_count DESC""")
    return render_template('admin/categories.html', categories=cats)

@app.route('/admin/category/<int:cid>/delete', methods=['POST'])
@admin_required
def admin_delete_category(cid):
    execute("DELETE FROM categories WHERE id=?", (cid,))
    flash('Category delete हो गई।','info'); return redirect(url_for('admin_categories'))

@app.route('/admin/change_password', methods=['GET','POST'])
@admin_required
def admin_change_password():
    if request.method == 'POST':
        cur, new, con = request.form['current'], request.form['new_pass'], request.form['confirm']
        user = query("SELECT * FROM users WHERE id=?", (session['admin_id'],), one=True)
        if not check_password_hash(user['password_hash'], cur): flash('Current password गलत है।','error')
        elif new != con: flash('Passwords match नहीं हुए।','error')
        elif len(new) < 6: flash('Min 6 characters चाहिए।','error')
        else:
            execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new), session['admin_id']))
            flash('Password बदल गया! ✅','success'); return redirect(url_for('admin_dashboard'))
    return render_template('admin/change_password.html')

@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    top_poems  = query("""SELECT p.*, u.username,
        (SELECT COUNT(*) FROM likes    WHERE poem_id=p.id) as like_count,
        (SELECT COUNT(*) FROM comments WHERE poem_id=p.id) as comment_count
        FROM poems p JOIN users u ON p.user_id=u.id WHERE p.is_draft=0
        ORDER BY like_count DESC LIMIT 10""")
    top_poets  = query("""SELECT u.*,
        COUNT(DISTINCT p.id) as poem_count,
        COALESCE((SELECT COUNT(*) FROM likes l JOIN poems pp ON l.poem_id=pp.id WHERE pp.user_id=u.id),0) as total_likes,
        (SELECT COUNT(*) FROM follows WHERE following_id=u.id) as followers
        FROM users u LEFT JOIN poems p ON u.id=p.user_id AND p.is_draft=0
        WHERE u.role='user' GROUP BY u.id ORDER BY total_likes DESC LIMIT 10""")
    daily_poems = [dict(r) for r in reversed(query(
        "SELECT DATE(created_at) as day, COUNT(*) as count FROM poems WHERE is_draft=0 GROUP BY day ORDER BY day DESC LIMIT 30"))]
    daily_users = [dict(r) for r in reversed(query(
        "SELECT DATE(joined_at) as day, COUNT(*) as count FROM users GROUP BY day ORDER BY day DESC LIMIT 30"))]
    cat_stats   = [dict(r) for r in query(
        "SELECT category, COUNT(*) as count FROM poems WHERE is_draft=0 GROUP BY category ORDER BY count DESC")]
    return render_template('admin/analytics.html', top_poems=top_poems, top_poets=top_poets,
                           daily_poems=daily_poems, daily_users=daily_users, cat_stats=cat_stats)


@app.route('/terms')
def terms(): return render_template('user/terms.html')

@app.route('/privacy')
def privacy(): return render_template('user/privacy.html')

@app.route('/about')
def about(): return render_template('user/about.html')

@app.route('/set-language', methods=['POST'])
def set_language():
    lang = request.form.get('lang', 'hi')
    session['lang'] = lang
    if session.get('user_id'):
        execute("UPDATE users SET language_pref=? WHERE id=?", (lang, session['user_id']))
    return redirect(request.referrer or url_for('index'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
else:
    init_db()
