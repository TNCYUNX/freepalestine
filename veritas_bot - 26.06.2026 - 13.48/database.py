# -*- coding: utf-8 -*-
import mysql.connector
from mysql.connector import pooling
import os
from dotenv import load_dotenv
import math

load_dotenv()

db_pool = None

def get_db_connection(database=True):
    global db_pool
    try:
        if database:
            if not db_pool:
                db_pool = pooling.MySQLConnectionPool(
                    pool_name="veritas_pool",
                    pool_size=32,
                    pool_reset_session=True,
                    host=os.getenv("DB_HOST"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    database=os.getenv("DB_NAME")
                )
            return db_pool.get_connection()
        else:
            return mysql.connector.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD")
            )
    except Exception as e:
        print(f"❌ Kritik Veritabanı Bağlantı Hatası: {e}")
        return None

def setup_database():
    """Veritabanı ve tüm tabloları otomatik olarak oluşturur."""
    try:
        conn = get_db_connection(database=False)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {os.getenv('DB_NAME')}")
        conn.close()

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Kullanıcılar Tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT UNIQUE,
                username VARCHAR(255),
                balance FLOAT DEFAULT 0.0,
                is_banned BOOLEAN DEFAULT FALSE
            )
        """)
        
        # İşlemID Takip Tablosu (Replay Attack Önleyici)
        cursor.execute("CREATE TABLE IF NOT EXISTS processed_txs (txid VARCHAR(100) PRIMARY KEY)")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT,
                action_type INT DEFAULT 0,
                service_name VARCHAR(100),
                fake_number VARCHAR(50),
                price FLOAT,
                status VARCHAR(50) DEFAULT '✅ BAŞARILI',
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            cursor.execute("ALTER TABLE history ADD COLUMN status VARCHAR(50) DEFAULT '✅ BAŞARILI'")
            conn.commit()
        except Exception:
            pass
        
        try:
            cursor.execute("ALTER TABLE history ADD COLUMN service_code VARCHAR(50) DEFAULT NULL")
            conn.commit()
        except Exception:
            pass
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupons (
                id INT AUTO_INCREMENT PRIMARY KEY,
                code VARCHAR(50) UNIQUE,
                reward_amount FLOAT,
                usage_limit INT,
                used_count INT DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS used_coupons (
                user_id BIGINT,
                coupon_id INT,
                PRIMARY KEY (user_id, coupon_id)
            )
        """)

        # Dinamik Servisler ve Ülkeler Tablosu (Veri Koruma Zırhı)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INT AUTO_INCREMENT PRIMARY KEY,
                service_name VARCHAR(100),
                api_srv VARCHAR(50),
                country_code VARCHAR(10),
                country_name VARCHAR(100),
                api_cc VARCHAR(50),
                price FLOAT,
                flag VARCHAR(10),
                is_active BOOLEAN DEFAULT TRUE,
                api_max_price FLOAT DEFAULT NULL,
                provider INT DEFAULT 1
            )
        """)
        try: cursor.execute("ALTER TABLE services ADD COLUMN flag VARCHAR(10)")
        except: pass
        try: cursor.execute("ALTER TABLE services ADD COLUMN api_max_price FLOAT DEFAULT NULL")
        except: pass
        try:
            cursor.execute("ALTER TABLE services ADD COLUMN provider INT DEFAULT 1")
            cursor.execute("UPDATE services SET provider = 1 WHERE provider IS NULL")
            conn.commit()
        except: pass
        
        # Destek Talepleri Tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT,
                message TEXT,
                status VARCHAR(20) DEFAULT 'acik',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Kalıcı Duyurular Tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ayarlar (Sistem Kontrol) Tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key_name VARCHAR(100) UNIQUE PRIMARY KEY,
                key_value VARCHAR(255)
            )
        """)

        # API Ülkeleri Tablosu
        cursor.execute("CREATE TABLE IF NOT EXISTS api_countries (country_code VARCHAR(10) PRIMARY KEY, country_name VARCHAR(100), flag VARCHAR(10), priority INT DEFAULT 0)")
        
        # YENİ: API Servisleri Tablosu (Grizzly Platformları)
        cursor.execute("CREATE TABLE IF NOT EXISTS api_services (service_code VARCHAR(10) PRIMARY KEY, service_name VARCHAR(100))")

        conn.commit()

        # Varsayılan Servisleri Tohumla (Seed)
        seed_api_services()

        # Popüler Ülkeleri Zirveye Taşı
        populer_ulkeler = {
            "62": 100, "187": 99, "128": 98, "33": 97, "43": 96, "50": 95, 
            "13": 94, "1": 93, "4": 92, "37": 91, "6": 90, "56": 89
        }
        for code, prio in populer_ulkeler.items():
            cursor.execute("UPDATE api_countries SET priority = %s WHERE country_code = %s", (prio, code))
        
        cursor.execute("INSERT IGNORE INTO settings (key_name, key_value) VALUES ('maintenance_mode', 'off')")
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Veritabanı kurulum hatası: {e}")

def seed_api_services():
    """API Servisleri tablosunu varsayılan platformlarla doldurur."""
    services = [
        ('wa', 'WhatsApp'),
        ('tg', 'Telegram'),
        ('ig', 'Instagram'),
        ('go', 'Google'),
        ('fb', 'Facebook'),
        ('tk', 'TikTok'),
        ('ds', 'Discord'),
        ('nf', 'Netflix')
    ]
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    cursor.executemany("INSERT IGNORE INTO api_services (service_code, service_name) VALUES (%s, %s)", services)
    conn.commit()
    conn.close()

def get_api_services():
    """Tüm API platformlarını (servislerini) döndürür."""
    conn = get_db_connection()
    if not conn: return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT service_code, service_name FROM api_services ORDER BY service_name ASC")
    res = cursor.fetchall()
    conn.close()
    return res

def get_service_name_by_code(service_code):
    """Verilen servis koduna (ör. wa) karşılık gelen gerçek adı (ör. WhatsApp) döndürür."""
    conn = get_db_connection()
    if not conn: return service_code.upper()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT service_name FROM api_services WHERE service_code = %s", (service_code,))
        res = cursor.fetchone()
        return res[0] if res else service_code.upper()
    except Exception:
        return service_code.upper()
    finally:
        conn.close()


# --- ATOMİK GÜVENLİK İŞLEMLERİ ---

def atomic_mark_tx_processed(txid):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO processed_txs (txid) VALUES (%s)", (txid,))
        conn.commit()
        conn.close()
        return True
    except mysql.connector.IntegrityError:
        return False
    except Exception:
        return False

def safe_decrease_balance(user_id, amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s AND balance >= %s", (amount, user_id, amount))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def is_tx_processed(txid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT txid FROM processed_txs WHERE txid = %s", (txid,))
    res = bool(cursor.fetchone())
    conn.close()
    return res

def mark_tx_processed(txid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT IGNORE INTO processed_txs (txid) VALUES (%s)", (txid,))
    conn.commit()
    conn.close()

# --- KULLANICI & BAKİYE İŞLEMLERİ ---

def add_user(user_id, username, initial_balance=0.0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT IGNORE INTO users (user_id, username, balance) VALUES (%s, %s, %s)",
        (user_id, username, initial_balance)
    )
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0.0

def update_balance(user_id, amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id))
    conn.commit()
    conn.close()

def refund_balance(user_id, amount):
    update_balance(user_id, amount)

def add_to_history(user_id, action_type, service_name, fake_number, price, status="✅ BAŞARILI", service_code=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO history (user_id, action_type, service_name, fake_number, price, status, service_code) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (user_id, action_type, service_name, fake_number, price, status, service_code)
    )
    conn.commit()
    conn.close()

def log_crypto_deposit(crypto_type, amount):
    key = f"total_{crypto_type.lower()}_deposited"
    current = float(get_setting(key, "0.0"))
    update_setting(key, str(current + amount))

def add_new_service(srv_name, api_srv, cc_code, c_name, api_cc, price, flag, api_max_price=None, provider=1):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO services (service_name, api_srv, country_code, country_name, api_cc, price, flag, api_max_price, provider) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (srv_name, api_srv, cc_code, c_name, api_cc, price, flag, api_max_price, provider)
    )
    conn.commit()
    conn.close()

def delete_service(service_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM services WHERE id = %s", (service_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_user_history(user_id, limit=3):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT service_name, fake_number, price, date FROM history WHERE user_id = %s ORDER BY id DESC LIMIT %s",
        (user_id, limit)
    )
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, username, balance, is_banned, ban_type, ban_reason, banned_input FROM users")
    results = cursor.fetchall()
    conn.close()
    return results

# --- BAN SİSTEMİ İŞLEMLERİ ---

def is_user_banned(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM users WHERE user_id = %s", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return bool(res[0]) if res else False

def ban_user(user_id, ban_type=0, reason=None, input_data=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Eğer zaten banlıysa üzerine yazmayı reddeder (İlk ve en ağır suç logda kalır)
    cursor.execute("UPDATE users SET is_banned = TRUE, ban_type = %s, ban_reason = %s, banned_input = %s WHERE user_id = %s AND is_banned = FALSE", (ban_type, reason, input_data, user_id))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = FALSE, ban_type = 0, ban_reason = NULL, banned_input = NULL WHERE user_id = %s", (user_id,))
    conn.commit()
    conn.close()

# --- DESTEK (TICKET) SİSTEMİ ---

def can_create_ticket(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS cnt FROM support_tickets WHERE user_id = %s AND created_at >= NOW() - INTERVAL 1 DAY", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res['cnt'] == 0

def create_ticket(user_id, message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO support_tickets (user_id, message) VALUES (%s, %s)", (user_id, message))
    conn.commit()
    conn.close()

def get_open_tickets(limit=5):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, user_id, message, created_at FROM support_tickets WHERE status = 'acik' ORDER BY id ASC LIMIT %s", (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

def close_ticket_by_id(ticket_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE support_tickets SET status = 'kapali' WHERE id = %s", (ticket_id,))
    conn.commit()
    conn.close()

# --- DUYURU & AYARLAR ---

def add_announcement(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO announcements (message) VALUES (%s)", (message,))
    conn.commit()
    conn.close()

def get_latest_announcements(limit=5):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT message, date FROM announcements ORDER BY date DESC LIMIT %s", (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

def get_active_services():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT service_name FROM services WHERE is_active = TRUE")
    results = [row['service_name'] for row in cursor.fetchall()]
    conn.close()
    return results

def get_all_services():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, service_name, country_name, provider FROM services")
    results = cursor.fetchall()
    conn.close()
    return results

def get_countries_for_service(service_name):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, country_code, country_name, price, api_srv, api_cc, flag, api_max_price, provider FROM services WHERE service_name = %s AND is_active = TRUE", (service_name,))
    results = cursor.fetchall()
    conn.close()
    return results

def get_service_by_id(service_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, service_name, api_srv, country_code, country_name, api_cc, price, is_active, api_max_price, flag, provider FROM services WHERE id = %s", (service_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def update_service_price_by_id(service_id, new_price):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE services SET price = %s WHERE id = %s", (new_price, service_id))
    conn.commit()
    conn.close()

def get_maintenance_mode():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key_value FROM settings WHERE key_name = 'maintenance_mode'")
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 'off'

def toggle_maintenance_mode():
    current = get_maintenance_mode()
    new_mode = 'on' if current == 'off' else 'off'
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET key_value = %s WHERE key_name = 'maintenance_mode'", (new_mode,))
    conn.commit()
    conn.close()
    return new_mode

# --- KUPON & İSTATİSTİK ---

def create_coupon(code, reward_amount, usage_limit):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO coupons (code, reward_amount, usage_limit) VALUES (%s, %s, %s)", (code, reward_amount, usage_limit))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def delete_coupon(code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM coupons WHERE code = %s", (code,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def redeem_coupon(user_id, code):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        conn.autocommit = False
        cursor.execute("SELECT * FROM coupons WHERE code = %s FOR UPDATE", (code,))
        coupon = cursor.fetchone()
        if not coupon:
            conn.rollback()
            return False, "❌ *Kupon bulunamadı.*"
        if coupon['used_count'] >= coupon['usage_limit']:
            conn.rollback()
            return False, "❌ *Bu kuponun kullanım limiti dolmuş.*"
        cursor.execute("SELECT * FROM used_coupons WHERE user_id = %s AND coupon_id = %s", (user_id, coupon['id']))
        if cursor.fetchone():
            conn.rollback()
            return False, "❌ *Bu kuponu zaten kullandınız.*"
        cursor.execute("UPDATE coupons SET used_count = used_count + 1 WHERE id = %s", (coupon['id'],))
        cursor.execute("INSERT INTO used_coupons (user_id, coupon_id) VALUES (%s, %s)", (user_id, coupon['id']))
        cursor.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (coupon['reward_amount'], user_id))
        conn.commit()
        return True, coupon['reward_amount']
    except:
        conn.rollback()
        return False, "❌ *Sistemsel bir hata oluştu.*"
    finally:
        conn.autocommit = True
        conn.close()

def get_all_coupons():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT code, reward_amount, usage_limit, used_count FROM coupons ORDER BY id DESC")
    results = cursor.fetchall()
    conn.close()
    return results

def get_statistics():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    stats = {}
    try:
        cursor.execute("SELECT COUNT(*) AS total_users FROM users")
        stats['total_users'] = cursor.fetchone()['total_users']
        cursor.execute("SELECT SUM(balance) AS total_balance FROM users")
        stats['total_balance'] = round(cursor.fetchone()['total_balance'] or 0, 2)
        cursor.execute("SELECT COUNT(*) AS total_sold FROM history")
        stats['total_sold'] = cursor.fetchone()['total_sold']
    except:
        stats = {'total_users': 0, 'total_balance': 0, 'total_sold': 0}
    finally: conn.close()
    return stats

# --- ÜLKE & AYAR FONKSİYONLARI ---

def get_paginated_countries(page=0, limit=21):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    offset = page * limit
    cursor.execute("SELECT country_code, country_name, flag FROM api_countries ORDER BY priority DESC, country_name ASC LIMIT %s OFFSET %s", (limit, offset))
    results = cursor.fetchall()
    conn.close()
    return results

def get_country_info(code):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT country_name, flag FROM api_countries WHERE country_code = %s", (code,))
    res = cursor.fetchone()
    conn.close()
    return res if res else {"country_name": code, "flag": "🌍"}

def get_total_country_pages(limit=21):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM api_countries")
    total = cursor.fetchone()[0]
    conn.close()
    return math.ceil(total / limit)

def get_country_name(code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT country_name FROM api_countries WHERE country_code = %s", (code,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else code

def update_setting(key_name, key_value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO settings (key_name, key_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE key_value = %s", (key_name, key_value, key_value))
    conn.commit()
    conn.close()

def get_setting(key_name, default_value=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key_value FROM settings WHERE key_name = %s", (key_name,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else default_value
