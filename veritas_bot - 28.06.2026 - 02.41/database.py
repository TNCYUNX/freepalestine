# -*- coding: utf-8 -*-
import mysql.connector
from mysql.connector import pooling
import os
from dotenv import load_dotenv
import math

load_dotenv()

class FallbackCursor:
    def __init__(self, dictionary=False):
        self.dictionary = dictionary
        self.rowcount = 0
        self.lastrowid = None

    def execute(self, *args, **kwargs):
        pass

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        pass

    def __getattr__(self, name):
        def dummy_method(*args, **kwargs):
            return None
        return dummy_method


class FallbackConnectionWrapper:
    def cursor(self, *args, **kwargs):
        dictionary = kwargs.get("dictionary", False)
        return FallbackCursor(dictionary=dictionary)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def __getattr__(self, name):
        def dummy_method(*args, **kwargs):
            return None
        return dummy_method


class SafeConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn
        self._closed = False

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        if not self._closed:
            try:
                self._conn.close()
            except:
                pass
            self._closed = True

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __del__(self):
        self.close()

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
            raw_conn = db_pool.get_connection()
            return SafeConnectionWrapper(raw_conn) if raw_conn else FallbackConnectionWrapper()
        else:
            raw_conn = mysql.connector.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD")
            )
            return SafeConnectionWrapper(raw_conn) if raw_conn else FallbackConnectionWrapper()
    except Exception as e:
        print(f"❌ Kritik Veritabanı Bağlantı Hatası: {e}")
        return FallbackConnectionWrapper()

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
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN warnings INT DEFAULT 0")
            conn.commit()
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN ban_type INT DEFAULT 0")
            conn.commit()
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN ban_reason VARCHAR(255) DEFAULT NULL")
            conn.commit()
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN banned_input TEXT DEFAULT NULL")
            conn.commit()
        except Exception:
            pass
            
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN referred_by BIGINT DEFAULT NULL")
            conn.commit()
        except Exception:
            pass
            
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN phone_number VARCHAR(20) DEFAULT NULL")
            conn.commit()
        except Exception:
            pass
            
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN ref_status VARCHAR(20) DEFAULT 'unverified'")
            conn.commit()
        except Exception:
            pass
        
        
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
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activation_id VARCHAR(50) DEFAULT NULL
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

        try:
            cursor.execute("ALTER TABLE history ADD COLUMN activation_id VARCHAR(50) DEFAULT NULL")
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_rentals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT,
                chat_id BIGINT,
                message_id INT,
                activation_id VARCHAR(50) UNIQUE,
                phone_number VARCHAR(30),
                service_id INT,
                service_code VARCHAR(10),
                service_name VARCHAR(100),
                api_srv VARCHAR(50),
                api_cc VARCHAR(10),
                price FLOAT,
                provider INT,
                start_time DOUBLE
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
        
        # YENİ: Referanslar Tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                referrer_id BIGINT,
                referred_id BIGINT,
                total_earnings FLOAT DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_ref (referrer_id, referred_id)
            )
        """)

        conn.commit()

        # Varsayılan Servisleri Tohumla (Seed)
        seed_api_services()

        # Rusya'yı ekle (Eğer yoksa)
        cursor.execute("INSERT IGNORE INTO api_countries (country_code, country_name, flag) VALUES ('0', 'Russia', '🇷🇺')")
        
        # Tüm öncelikleri sıfırla
        cursor.execute("UPDATE api_countries SET priority = 0")
        
        # Popüler Ülkeleri Zirveye Taşı (Kullanıcı Talebi Sırasıyla)
        populer_ulkeler = {
            "62": 100,   # Türkiye
            "6": 99,     # Endonezya
            "22": 98,    # Hindistan
            "0": 97,     # Rusya
            "16": 96,    # İngiltere
            "187": 95,   # ABD
            "2": 94,     # Kazakistan
            "10": 93,    # Vietnam
            "4": 92,     # Filipinler
            "73": 91,    # Brezilya
            "1": 90,     # Ukrayna
            "11": 89,    # Kırgızistan
            "40": 88,    # Özbekistan
            "60": 87,    # Bangladeş
            "24": 86,    # Kamboçya
            "69": 85,    # Mali
            "37": 84,    # Fas
            "21": 83,    # Mısır
            "19": 82,    # Nijerya
            "8": 81,     # Kenya
            "33": 80,    # Kolombiya
            "54": 79,    # Meksika
            "52": 78,    # Tayland
            "7": 77,     # Malezya
            "36": 76,    # Kanada
            "32": 75,    # Romanya
            "15": 74,    # Polonya
            "31": 73,    # Güney Afrika
            "66": 72,    # Pakistan
            "39": 71     # Arjantin
        }
        for code, prio in populer_ulkeler.items():
            cursor.execute("UPDATE api_countries SET priority = %s WHERE country_code = %s", (prio, code))
        
        cursor.execute("INSERT IGNORE INTO settings (key_name, key_value) VALUES ('maintenance_mode', 'off')")
        cursor.execute("INSERT IGNORE INTO settings (key_name, key_value) VALUES ('global_deposit_status', 'on')")
        cursor.execute("INSERT IGNORE INTO settings (key_name, key_value) VALUES ('global_number_buy_status', 'on')")
        
        # Kullanıcı tablosuna yeni engelleme sütunlarını ekle (Hata almamak için try-except içinde)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN number_buy_blocked TINYINT DEFAULT 0")
        except: pass
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN deposit_blocked TINYINT DEFAULT 0")
        except: pass
        
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

def is_phone_number_taken(phone_number, user_id):
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM users WHERE phone_number = %s AND user_id != %s AND ref_status != 'unverified'",
            (phone_number, user_id)
        )
        res = cursor.fetchone()
        return res is not None
    except:
        return False
    finally:
        conn.close()

# --- KULLANICI & BAKİYE İŞLEMLERİ ---

def add_user(user_id, username, initial_balance=0.0, referred_by=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT IGNORE INTO users (user_id, username, balance, referred_by) VALUES (%s, %s, %s, %s)",
        (user_id, username, initial_balance, referred_by)
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

def add_to_history(user_id, action_type, service_name, fake_number, price, status="✅ BAŞARILI", service_code=None, activation_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO history (user_id, action_type, service_name, fake_number, price, status, service_code, activation_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (user_id, action_type, service_name, fake_number, price, status, service_code, activation_id)
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
    cursor.execute("SELECT user_id, username, balance, is_banned, ban_type, ban_reason, banned_input, referred_by, phone_number, ref_status, number_buy_blocked, deposit_blocked FROM users")
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
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.id, s.country_code, s.country_name, s.price, s.api_srv, s.api_cc, s.flag, s.api_max_price, s.provider 
            FROM services s 
            LEFT JOIN api_countries c ON s.country_code = c.country_code 
            WHERE s.service_name = %s AND s.is_active = TRUE 
            ORDER BY COALESCE(c.priority, 0) DESC, s.country_name ASC
        """, (service_name,))
        results = cursor.fetchall()
        return results
    except:
        return []
    finally:
        conn.close()

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

def get_user_warnings(user_id):
    """Kullanıcının veritabanındaki aktif uyarı sayısını getirir (Güvenli)."""
    conn = get_db_connection()
    if not conn: return 0
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT warnings FROM users WHERE user_id = %s", (user_id,))
        res = cursor.fetchone()
        return res[0] if res else 0
    except Exception:
        return 0
    finally:
        conn.close()

def update_user_warnings(user_id, count):
    """Kullanıcının veritabanındaki aktif uyarı sayısını günceller (Güvenli)."""
    conn = get_db_connection()
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET warnings = %s WHERE user_id = %s", (count, user_id))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def find_user_by_id_or_username(search_term):
    """Kullanıcıyı ID veya kullanıcı adına göre bulup user_id döndürür."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        term = search_term.strip().replace("@", "")
        if term.isdigit():
            # Önce sayısal ID olarak sorgula
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s OR username = %s", (int(term), term))
        else:
            cursor.execute("SELECT user_id FROM users WHERE username = %s", (term,))
        res = cursor.fetchone()
        return res['user_id'] if res else None
    except Exception:
        return None
    finally:
        conn.close()

def get_banned_and_warned_users():
    """Uyarısı olan veya yasaklı olan kullanıcıların listesini getirir."""
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT user_id, username, is_banned, warnings FROM users WHERE is_banned = TRUE OR warnings > 0 ORDER BY is_banned DESC, warnings DESC")
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        conn.close()

def add_active_rental(user_id, chat_id, message_id, activation_id, phone_number, service_id, service_code, service_name, api_srv, api_cc, price, provider, start_time):
    """Aktif kiralamayı veritabanına kaydeder."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO active_rentals (user_id, chat_id, message_id, activation_id, phone_number, service_id, service_code, service_name, api_srv, api_cc, price, provider, start_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE chat_id = %s, message_id = %s
        """, (user_id, chat_id, message_id, activation_id, phone_number, service_id, service_code, service_name, api_srv, api_cc, price, provider, start_time, chat_id, message_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in add_active_rental: {e}")
        return False
    finally:
        conn.close()

def delete_active_rental(activation_id):
    """Aktif kiralamayı veritabanından siler."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_rentals WHERE activation_id = %s", (activation_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in delete_active_rental: {e}")
        return False
    finally:
        conn.close()

def get_active_rentals():
    """Tüm aktif kiralamaları veritabanından çeker."""
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, user_id, chat_id, message_id, activation_id, phone_number, service_id, service_code, service_name, api_srv, api_cc, price, provider, start_time FROM active_rentals")
        return cursor.fetchall()
    except Exception as e:
        print(f"Error in get_active_rentals: {e}")
        return []
    finally:
        conn.close()

def add_referral(referrer_id, referred_id):
    """Kullanıcılar arasındaki referans ilişkisini kaydeder."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET referred_by = %s WHERE user_id = %s AND referred_by IS NULL", (referrer_id, referred_id))
        cursor.execute("INSERT IGNORE INTO referrals (referrer_id, referred_id) VALUES (%s, %s)", (referrer_id, referred_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in add_referral: {e}")
        return False
    finally:
        conn.close()

def get_referred_users_detail(referrer_id):
    """Davet edilen kullanıcıların listesini, kullanıcı adlarını ve kazançlarını getirir."""
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.referred_id, u.username, r.total_earnings 
            FROM referrals r
            LEFT JOIN users u ON r.referred_id = u.user_id
            WHERE r.referrer_id = %s
        """, (referrer_id,))
        return cursor.fetchall()
    except Exception as e:
        print(f"Error in get_referred_users_detail: {e}")
        return []
    finally:
        conn.close()

def remove_referral(referred_id):
    """Bir kullanıcının referans bağını siler."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET referred_by = NULL WHERE user_id = %s", (referred_id,))
        cursor.execute("DELETE FROM referrals WHERE referred_id = %s", (referred_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in remove_referral: {e}")
        return False
    finally:
        conn.close()

def get_referrer(user_id):
    """Kullanıcının kimin referansı olduğunu getirir."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT referred_by FROM users WHERE user_id = %s", (user_id,))
        res = cursor.fetchone()
        return res[0] if res else None
    except Exception as e:
        print(f"Error in get_referrer: {e}")
        return None
    finally:
        conn.close()

def get_referral_stats(user_id):
    """Kullanıcının referans istatistiklerini getirir (toplam davetli ve kazanç)."""
    conn = get_db_connection()
    if not conn: return {"count": 0, "total_earnings": 0.0}
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count, IFNULL(SUM(total_earnings), 0.0) as total_earnings FROM referrals WHERE referrer_id = %s", (user_id,))
        res = cursor.fetchone()
        return {"count": res[0], "total_earnings": round(res[1], 2)}
    except Exception as e:
        print(f"Error in get_referral_stats: {e}")
        return {"count": 0, "total_earnings": 0.0}
    finally:
        conn.close()

def update_referral_earnings(referrer_id, referred_id, amount):
    """Referans kazancını günceller."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE referrals SET total_earnings = total_earnings + %s WHERE referrer_id = %s AND referred_id = %s", (amount, referrer_id, referred_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in update_referral_earnings: {e}")
        return False
    finally:
        conn.close()

def verify_user_phone(user_id, phone):
    """Kullanıcının telefon numarasını doğrular ve referans onay durumunu belirler."""
    if not phone.startswith("+"):
        phone = "+" + phone
        
    # Eğer numara +90 ile başlıyorsa otomatik onay, aksi takdirde onay bekliyor durumuna al
    status = "approved" if (phone.startswith("+90") or phone.startswith("90")) else "pending"
    
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET phone_number = %s, ref_status = %s WHERE user_id = %s", (phone, status, user_id))
        conn.commit()
        return status
    except Exception as e:
        print(f"Error in verify_user_phone: {e}")
        return None
    finally:
        conn.close()

def approve_referral(user_id):
    """Kullanıcının referans durumunu onaylar."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET ref_status = 'approved' WHERE user_id = %s", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in approve_referral: {e}")
        return False
    finally:
        conn.close()

def reject_referral(user_id):
    """Kullanıcının referans durumunu reddeder."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET ref_status = 'rejected' WHERE user_id = %s", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in reject_referral: {e}")
        return False
    finally:
        conn.close()

def get_user_info(user_id):
    """Kullanıcının tüm bilgilerini veritabanından çeker."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT user_id, username, balance, is_banned, referred_by, phone_number, ref_status, number_buy_blocked, deposit_blocked FROM users WHERE user_id = %s", (user_id,))
        return cursor.fetchone()
    except Exception as e:
        print(f"Error in get_user_info: {e}")
        return None
    finally:
        conn.close()

def update_referred_by(user_id, referrer_id):
    """Kullanıcının henüz onaylanmamış referans bağını günceller."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET referred_by = %s WHERE user_id = %s AND phone_number IS NULL", (referrer_id, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in update_referred_by: {e}")
        return False
    finally:
        conn.close()

def get_global_deposit_status():
    """Sistem genelinde ödeme yapma durumunu döndürür."""
    return get_setting("global_deposit_status", "on")

def toggle_global_deposit_status():
    """Sistem genelinde ödeme yapma durumunu açıp kapatır."""
    current = get_global_deposit_status()
    new_val = "off" if current == "on" else "on"
    update_setting("global_deposit_status", new_val)
    return new_val

def get_global_number_buy_status():
    """Sistem genelinde numara alma durumunu döndürür."""
    return get_setting("global_number_buy_status", "on")

def toggle_global_number_buy_status():
    """Sistem genelinde numara alma durumunu açıp kapatır."""
    current = get_global_number_buy_status()
    new_val = "off" if current == "on" else "on"
    update_setting("global_number_buy_status", new_val)
    return new_val

def toggle_user_number_buy_blocked(user_id):
    """Kullanıcı bazlı numara alım kısıtlamasını açıp kapatır."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET number_buy_blocked = 1 - number_buy_blocked WHERE user_id = %s", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in toggle_user_number_buy_blocked: {e}")
        return False
    finally:
        conn.close()

def toggle_user_deposit_blocked(user_id):
    """Kullanıcı bazlı bakiye yükleme kısıtlamasını açıp kapatır."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET deposit_blocked = 1 - deposit_blocked WHERE user_id = %s", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in toggle_user_deposit_blocked: {e}")
        return False
    finally:
        conn.close()

def remove_user_from_db(user_id):
    """Kullanıcıyı users tablosundan tamamen kaldırır (history tablosundaki geçmişi korunur)."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM referrals WHERE referrer_id = %s OR referred_id = %s", (user_id, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in remove_user_from_db: {e}")
        return False
    finally:
        conn.close()

