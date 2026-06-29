# -*- coding: utf-8 -*-
import telebot
from telebot import types
import os
import threading
import time
from dotenv import load_dotenv

import config
import database
import admin_panel
from handlers import admin_services, payment_handler, number_handler
from providers import grizzly_provider, tigersms_provider
from providers.security_manager import security

load_dotenv()
bot = telebot.TeleBot(os.getenv("TELEGRAM_TOKEN"), num_threads=50)

# Botun sol alt köşesindeki mavi "Menü" butonuna /start komutunu tanımla
try:
    bot.set_my_commands([
        telebot.types.BotCommand("start", "🤖 Ana Menüyü Aç / Başlat")
    ])
except Exception as e:
    print(f"⚠️ Bot menü komutu tanımlanamadı: {e}")

# Handler'ları kayıt et
admin_services.register_admin_service_handlers(bot)
admin_panel.register_admin_handlers(bot)
payment_handler.register_payment_handlers(bot)
number_handler.register_number_handlers(bot)

def notify_admin_of_ban(user_id, ban_info):
    if not ban_info: return
    admin_id = os.getenv("ADMIN_ID")
    if not admin_id: return
    try:
        chat_info = bot.get_chat(user_id)
        full_name = f"{chat_info.first_name or ''} {chat_info.last_name or ''}".strip() or "Kullanıcı"
        username_mention = f"@{chat_info.username}" if chat_info.username else "Yok"
    except:
        full_name = "Kullanıcı"
        username_mention = "Yok"
    metin = (
        "🚨 *SİBER GÜVENLİK ALARMI - OTOMATİK BAN* 🚨\n\n"
        f"👤 *Hedef Kullanıcı:* [{full_name}](tg://user?id={user_id}) ({username_mention})\n"
        f"🆔 *Hedef ID:* `{user_id}`\n"
        f"⚠️ *Tehdit Tipi:* `Tip {ban_info['type']} ({ban_info['reason']})`\n"
        f"📝 *Yakalanan Payload:* `{ban_info['input']}`\n\n"
        "🛡️ _Bot savunma kalkanı saldırganı anında tespit edip kalıcı olarak banladı._\n"
        "🛑 _Eğer organize bir saldırı seziyorsanız, Admin Panel > Sistem Kontrol > Sunucuyu Kapat butonunu kullanarak botu dondurabilirsiniz._"
    )
    try: bot.send_message(admin_id, metin, parse_mode="Markdown")
    except: pass

def send_coupon_redeemed_notification_to_admin(bot, user_id, coupon_code, reward_amount):
    admin_id = os.getenv("ADMIN_ID")
    if not admin_id: return
    
    user_info = database.get_user_info(user_id)
    username = user_info.get("username") if user_info else None
    
    # Profil linki oluştur
    if username and username != "Yok":
        profile_link = f"https://t.me/{username}"
        username_mention = f"@{username}"
    else:
        profile_link = f"tg://user?id={user_id}"
        username_mention = "Yok"
        
    phone = user_info.get("phone_number", "Doğrulanmamış") if user_info else "Bilinmiyor"
    warnings = user_info.get("warnings", 0) if user_info else 0
    balance = user_info.get("balance", 0.0) if user_info else 0.0
    referred_by = user_info.get("referred_by") if user_info else None
    ref_str = f"`{referred_by}`" if referred_by else "Yok"
    
    metin = (
        "🎟️ *KUPON KULLANIM BİLDİRİMİ* 🎟️\n\n"
        f"🎫 *Kullanılan Kupon:* `{coupon_code}`\n"
        f"💰 *Kupon Ödülü:* `{reward_amount} TL`\n\n"
        "👤 *Kullanıcı Profil Bilgileri:*\n"
        f"├ *Telegram ID:* `{user_id}`\n"
        f"├ *Kullanıcı Adı:* {username_mention}\n"
        f"├ *Telefon:* `{phone}`\n"
        f"├ *Mevcut Bakiye:* `{balance} TL`\n"
        f"├ *Uyarı Sayısı:* `{warnings}/5`\n"
        f"├ *Referans Eden:* {ref_str}\n"
        f"└ 🔗 *Profil Linki:* [Tıkla Git]({profile_link})\n"
    )
    
    try:
        # Profil resmini çek (ilk resmi gönder)
        photos = bot.get_user_profile_photos(user_id, limit=1)
        if photos and photos.total_count > 0:
            file_id = photos.photos[0][-1].file_id
            bot.send_photo(admin_id, file_id, caption=metin, parse_mode="Markdown")
        else:
            bot.send_message(admin_id, metin, parse_mode="Markdown")
    except Exception as e:
        try: bot.send_message(admin_id, metin, parse_mode="Markdown")
        except: pass

# --- GLOBAL DEĞİŞKENLER ---
# AKTIF_TAKIPLER ve ilgili takip mantığı handlers/number_handler.py içerisindedir.
PENDING_VERIFICATION_MSG_IDS = {}
verification_lock = threading.Lock()

def user_allowed(user_id, chat_id=None, call_id=None):
    # 1. Grup Whitelist Kontrolü (Botun illegal gruplara eklenmesini önler)
    if chat_id and not security.is_group_allowed(chat_type="group" if chat_id < 0 else "private", chat_id=chat_id):
        return False
        
    # 2. Spam / Rate Limit Kontrolü (Komut ve Mesaj Spamını Engeller)
    status, msg, ban_info = security.check_rate_limit(user_id, call_id)
    if status == 'ban':
        notify_admin_of_ban(user_id, ban_info)
        if call_id:
            try: bot.answer_callback_query(call_id, "⚠️ Çok hızlı işlem yapıyorsunuz!", show_alert=False)
            except: pass
        if chat_id:
            try:
                strikes = security.USER_STRIKES.get(user_id, 5)
                warn_msg = f"⚠️ Çok hızlı işlem yapıyorsunuz! (Uyarı: {strikes}/5)"
                bot.send_message(chat_id, warn_msg)
                bot.send_message(chat_id, msg)
            except: pass
        security.USER_STRIKES[user_id] = 0  # Yasaklanınca RAM uyarılarını sıfırla
        return False
    elif status == 'warn':
        if call_id:
            try: bot.answer_callback_query(call_id, "⚠️ Çok hızlı işlem yapıyorsunuz!", show_alert=False)
            except: pass
        if chat_id:
            try: bot.send_message(chat_id, msg)
            except: pass
        return False

    admin_id = str(os.getenv("ADMIN_ID"))
    try: m_mode = database.get_maintenance_mode()
    except: return False
    
    if admin_id and str(user_id) == admin_id: return True
    
    if m_mode == 'on':
        if chat_id: bot.send_message(chat_id, "🚧 *Sistem Bakımda!* Lütfen daha sonra tekrar deneyin.", parse_mode="Markdown")
        if call_id: bot.answer_callback_query(call_id, "🚧 Sistem Bakımda!", show_alert=True)
        return False
        
    if database.is_user_banned(user_id):
        security.BANNED_CACHE.add(user_id) # Veritabanından banlı olduğu teyit edilince RAM'e al
        if chat_id: bot.send_message(chat_id, "🚫 *Sistemden banlandınız!*", parse_mode="Markdown")
        if call_id: bot.answer_callback_query(call_id, "🚫 Sistemden banlandınız!", show_alert=True)
        return False
    return True

def ana_menu_klavyesi(user_id=None):
    markup = types.InlineKeyboardMarkup()
    
    # Satır 1: [ Numara Al ] - [ Popüler ]
    markup.row(
        types.InlineKeyboardButton(config.BUTONLAR["numara_al"], callback_data="menu_numara_al"),
        types.InlineKeyboardButton("🌟 Popüler", callback_data="menu_populer")
    )
    
    # Satır 2: [ Bakiye Yükle ] - [ Bakiyem ]
    markup.row(
        types.InlineKeyboardButton(config.BUTONLAR["bakiye_yukle"], callback_data="menu_bakiye_yukle"),
        types.InlineKeyboardButton(config.BUTONLAR["bakiyem"], callback_data="menu_bakiyem")
    )
    
    # Satır 3: [ Geçmişim ] - [ Kupon Kullan ]
    markup.row(
        types.InlineKeyboardButton(config.BUTONLAR["gecmisim"], callback_data="menu_gecmisim"),
        types.InlineKeyboardButton(config.BUTONLAR["kupon_kullan"], callback_data="menu_kupon_kullan")
    )
    
    # Satır 4: [ Duyurular Gör ] - [ Referans ]
    markup.row(
        types.InlineKeyboardButton(config.BUTONLAR["duyurular"], callback_data="menu_duyurular"),
        types.InlineKeyboardButton(config.BUTONLAR["referans"], callback_data="menu_referans")
    )
    
    # Satır 5: [ Destek ] - [ Kurucu ]
    markup.row(
        types.InlineKeyboardButton(config.BUTONLAR["destek"], callback_data="menu_destek"),
        types.InlineKeyboardButton(config.BUTONLAR["kurucu"], url=config.KURUCU_URL)
    )
    
    # Admin Paneli Butonu (EN ALT - TAM SATIR)
    if user_id:
        admin_id = str(os.getenv("ADMIN_ID"))
        if str(user_id) == admin_id:
            markup.row(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="open_admin_panel"))
            
    return markup

def geri_don():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(config.BUTONLAR["ana_menu"], callback_data="back_to_main"))
    return markup

def safe_edit(call_or_chat_id, text, markup=None, message_id=None):
    """Hem caption hem de text mesajlarını destekleyen gelişmiş düzenleyici."""
    try:
        if hasattr(call_or_chat_id, 'message'):
            cid = call_or_chat_id.message.chat.id
            mid = call_or_chat_id.message.message_id
        else:
            cid = call_or_chat_id
            mid = message_id

        try:
            return bot.edit_message_caption(chat_id=cid, message_id=mid, caption=text, reply_markup=markup, parse_mode="Markdown")
        except:
            return bot.edit_message_text(chat_id=cid, message_id=mid, text=text, reply_markup=markup, parse_mode="Markdown")
    except:
        return None

# --- BOT KOMUTLARI ---
@bot.message_handler(commands=['start'])
def start_komutu(message):
    user_id = message.from_user.id
    if not user_allowed(user_id, chat_id=message.chat.id): return
    
    # Kullanıcının kayıt durumunu kontrol et
    user_info = database.get_user_info(user_id)
    is_new_user = user_info is None
    
    args = message.text.split()
    has_ref = len(args) > 1 and args[1].startswith("ref_")
    has_cpn = len(args) > 1 and args[1].startswith("cpn_")
    referrer_id = None
    
    print(f"[TRACE start_komutu] user_id: {user_id}, is_new_user: {is_new_user}, args: {args}, has_ref: {has_ref}, has_cpn: {has_cpn}")
    
    if has_cpn:
        coupon_code = args[1].replace("cpn_", "").upper()
        # Güvenlik Kontrolü
        is_valid, sec_msg, ban_info = security.validate_input(user_id, coupon_code, input_type="coupon")
        if not is_valid:
            if ban_info: notify_admin_of_ban(user_id, ban_info)
            has_cpn = False
        else:
            # Kullanıcı onaylı mı?
            if not is_new_user and user_info.get("phone_number") is not None:
                # Doğrulanmış kullanıcı, hemen kuponu kullandır
                basarili, sonuc = database.redeem_coupon(user_id, coupon_code)
                try: bot.delete_message(message.chat.id, message.message_id)
                except: pass
                
                if basarili:
                    database.add_to_history(user_id, 6, "Kupon", coupon_code, -sonuc, status="✅ BAŞARILI")
                    hosgeldin_text = f"🎁 *KUPON AKTİF EDİLDİ!* 🎁\n\n`{coupon_code}` kuponu başarıyla kullanıldı ve hesabınıza *+{sonuc} TL* tanımlandı!"
                    send_coupon_redeemed_notification_to_admin(bot, user_id, coupon_code, sonuc)
                else:
                    hosgeldin_text = f"❌ *Kupon Kullanılamadı:*\n\n{sonuc}"
                
                with open("veritas_sms_logo_yatay.png", "rb") as photo:
                    bot.send_photo(message.chat.id, photo, caption=hosgeldin_text, reply_markup=ana_menu_klavyesi(user_id=user_id), parse_mode="Markdown")
                return
            else:
                # Onaylanmamış veya yeni kullanıcı, telefon doğrulamasına yönlendir ve kuponu beklemeye al
                if is_new_user:
                    database.add_user(user_id, message.from_user.username or "Yok")
                
                metin = (
                    "⚠️ *Telefon Doğrulaması Gerekli* ⚠️\n\n"
                    f"Link üzerinden gelen `{coupon_code}` kupon kodunu hesabınıza aktifleştirmek için güvenlik amacıyla tek seferlik telefon numarası onayı gerekmektedir.\n\n"
                    "🔒 *Güvenlik & Gizlilik:* Telefon numaranız sadece sistem doğrulaması için kullanılır, 3. şahıslarla asla paylaşılmaz.\n\n"
                    "👇 Lütfen aşağıdaki *📱 Numaramı Paylaş* butonunu kullanarak numaranızı doğrulayın."
                )
                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                markup.add(types.KeyboardButton("📱 Numaramı Paylaş", request_contact=True))
                
                try: bot.delete_message(message.chat.id, message.message_id)
                except: pass
                
                sent_msg = bot.send_message(message.chat.id, metin, reply_markup=markup, parse_mode="Markdown")
                with verification_lock:
                    PENDING_VERIFICATION_MSG_IDS[user_id] = {
                        "message_id": sent_msg.message_id, 
                        "timestamp": time.time(),
                        "pending_coupon": coupon_code
                    }
                return

    if has_ref:
        try:
            ref_param = args[1].replace("ref_", "")
            print(f"[TRACE start_komutu] ref_param: {ref_param}")
            
            is_fraud = False
            fraud_reason = ""
            warn_penalty = 0
            
            if len(ref_param) == 16 and ref_param.isalnum():
                ref_info = database.get_user_by_ref_token(ref_param)
                print(f"[TRACE start_komutu] ref_info: {ref_info}")
                
                if ref_info is not None:
                    potential_referrer = ref_info.get("user_id")
                    if potential_referrer == user_id:
                        print(f"[TRACE start_komutu] Self-referral attempt detected via token.")
                        is_fraud = True
                        fraud_reason = "Kendi kendine referans olma girişimi (Merak/Suiistimal)"
                        warn_penalty = 1
                    else:
                        if ref_info.get("ref_status") == "approved":
                            referrer_id = potential_referrer
                            has_ref = True
                        else:
                            is_fraud = True
                            fraud_reason = f"Onaylanmamış/Geçersiz referans kodu ({ref_param}) kullanımı"
                            warn_penalty = 3
                else:
                    is_fraud = True
                    fraud_reason = f"Sistemde kayıtlı olmayan referans kodu ({ref_param}) kullanımı"
                    warn_penalty = 3
            else:
                is_fraud = True
                fraud_reason = f"Geçersiz formatta referans kodu ({ref_param}) kullanımı"
                warn_penalty = 3
                
            if is_fraud:
                has_ref = False
                
                # Kullanıcı veritabanında yoksa önce ekle (uyarıları yazabilmek için)
                if is_new_user:
                    database.add_user(user_id, message.from_user.username or "Yok")
                    user_info = database.get_user_info(user_id)
                    is_new_user = False
                
                # Dinamik uyarı ver (+1 veya +3)
                current_warnings = database.get_user_warnings(user_id)
                new_warnings = current_warnings + warn_penalty
                database.update_user_warnings(user_id, new_warnings)
                
                # Admin'e bildir
                admin_id = os.getenv("ADMIN_ID")
                username = message.from_user.username or "Yok"
                if admin_id:
                    admin_msg = (
                        "🚨 *SİSTEM UYARISI: REFERANS MANİPÜLASYONU* 🚨\n\n"
                        f"👤 *Kullanıcı:* `{user_id}` (@{username})\n"
                        f"⚠️ *Eylem:* {fraud_reason}\n"
                        f"📊 *Ceza:* +{warn_penalty} Uyarı verildi. Toplam Uyarı: `{new_warnings}/5`"
                    )
                    if new_warnings >= 5:
                        admin_msg += " -> **KALICI BAN!**"
                    try: bot.send_message(admin_id, admin_msg, parse_mode="Markdown")
                    except: pass
                    
                if new_warnings >= 5:
                    # Kalıcı banla
                    database.ban_user(user_id, 1, "Referans Manipülasyonu (Limit Aşımı)", fraud_reason)
                    security.BANNED_CACHE.add(user_id)
                    
                    # Kullanıcıya ban mesajı gönder
                    user_msg = (
                        "❌ *SİSTEM CEZASI: Referans Sahteciliği!*\n\n"
                        "Bot üzerinde kendi kendinizi davet etmeye veya sistemde olmayan hesaplar üzerinden referans sahteciliği yapmaya çalıştığınız tespit edildi.\n"
                        f"Bu ihlal nedeniyle hesabınıza +{warn_penalty} uyarı verilmiş ve limit aşımı (Toplam: `{new_warnings}/5`) sebebiyle hesabınız **KALICI OLARAK BANLANMIŞTIR.**"
                    )
                    bot.send_message(message.chat.id, user_msg, parse_mode="Markdown")
                    return
                else:
                    # Birinci mesaj: Uyarı Başlığı ve Seviyesi
                    title_msg = f"⚠️ *UYARI! ({new_warnings}/5) - Referans Sahteciliği Girişimi!*"
                    bot.send_message(message.chat.id, title_msg, parse_mode="Markdown")
                    
                    # İkinci mesaj: Detay ve Bilgilendirme
                    detail_msg = (
                        "Sistemde doğrulanmamış hesaplar üzerinden referans bağı kurmaya çalıştığınız tespit edildi.\n\n"
                        "❗️ *DİKKAT:* Bu tür manipülasyon girişimleri kesinlikle yasaktır. Tekrarı durumunda hesabınız *KALICI OLARAK BANLANACAKTIR!*"
                    )
                    bot.send_message(message.chat.id, detail_msg, parse_mode="Markdown")
        except Exception as e:
            print(f"[TRACE start_komutu] Exception in parsing ref: {e}")
            has_ref = False

    print(f"[TRACE start_komutu] Final variables -> has_ref: {has_ref}, is_new_user: {is_new_user}, referrer_id: {referrer_id}")

    # EĞER YENİ BİR KULLANICI REFERANS LİNKİYLE GELDİYSE VEYA MEVCUT KULLANICI ONAYSIZKEN LİNKLE GELDİYSE:
    is_not_verified = (not is_new_user and user_info.get("phone_number") is None)
    if has_ref and (is_new_user or is_not_verified):
        if is_new_user:
            # Kullanıcıyı referred_by ile kaydet
            database.add_user(user_id, message.from_user.username or "Yok", referred_by=referrer_id)
        else:
            # Mevcut onaylanmamış kullanıcının referans sahibini güncelle
            database.update_referred_by(user_id, referrer_id)
        
        metin = (
            "⚠️ *Telefon Doğrulaması Gerekli* ⚠️\n\n"
            "Davet linkiyle giriş yaptığınız için referans kaydınızın doğrulanması amacıyla tek seferlik telefon numarası onayı gerekmektedir.\n\n"
            "🔒 *Güvenlik & Gizlilik:* Telefon numaranız sadece sistem doğrulaması için kullanılır, 3. şahıslarla asla paylaşılmaz. Paylaştığınız numara mesajı doğrulama biter bitmez sohbet geçmişinizden anında silinecektir.\n\n"
            "👇 Lütfen aşağıdaki *📱 Numaramı Paylaş* butonunu kullanarak numaranızı doğrulayın."
        )
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add(types.KeyboardButton("📱 Numaramı Paylaş", request_contact=True))
        
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass
        
        sent_msg = bot.send_message(message.chat.id, metin, reply_markup=markup, parse_mode="Markdown")
        with verification_lock:
            PENDING_VERIFICATION_MSG_IDS[user_id] = {"message_id": sent_msg.message_id, "timestamp": time.time()}
        return

    # Normal /start veya zaten kayıtlı kullanıcı ise normal hoş geldin menüsünü aç
    if is_new_user:
        database.add_user(user_id, message.from_user.username or "Yok")
        
    bot.clear_step_handler_by_chat_id(message.chat.id)
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    with open("veritas_sms_logo_yatay.png", "rb") as photo:
        bot.send_photo(message.chat.id, photo, caption=config.MESAJLAR["hosgeldin"].format(isim=message.from_user.first_name), reply_markup=ana_menu_klavyesi(user_id=user_id), parse_mode="Markdown")

@bot.message_handler(content_types=['contact'])
def contact_handler(message):
    user_id = message.from_user.id
    contact = message.contact
    
    # Kullanıcının gönderdiği ham rehber mesajını hemen sil
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    
    pending_coupon = None
    with verification_lock:
        msg_info = PENDING_VERIFICATION_MSG_IDS.pop(user_id, None)
    if msg_info:
        if isinstance(msg_info, dict):
            warning_msg_id = msg_info.get("message_id")
            pending_coupon = msg_info.get("pending_coupon")
        else:
            warning_msg_id = msg_info
        try: bot.delete_message(message.chat.id, warning_msg_id)
        except: pass
    
    if contact.user_id != user_id:
        # 1. Referans bağını iptal et (referred_by ve referrals tablosundaki verileri sil)
        database.remove_referral(user_id)
        
        # 2. Uyarı sayısını arttır (+2 Warn)
        current_warnings = database.get_user_warnings(user_id)
        new_warnings = current_warnings + 2
        database.update_user_warnings(user_id, new_warnings)
        
        admin_id = os.getenv("ADMIN_ID")
        username = message.from_user.username or "Yok"
        
        # 3. Ceza durumunu belirle
        if new_warnings >= 5:
            # Kalıcı banla
            database.ban_user(user_id, 1, "Hileli Referans Girişimi (Limit Aşımı)", f"Başkasına ait numara: {contact.phone_number}")
            security.BANNED_CACHE.add(user_id)
            
            # Kullanıcıya ban mesajı gönder
            user_msg = (
                "❌ *SİSTEM CEZASI: Hileli Referans Girişimi!*\n\n"
                "Başka bir kullanıcıya ait telefon numarası kartı paylaştığınız tespit edildi.\n\n"
                f"Sistem uyarı limitinizi (`{new_warnings}/5`) aştığınız için **KALICI OLARAK BANLANDINIZ!**"
            )
            bot.send_message(message.chat.id, user_msg, parse_mode="Markdown")
            
            # Admin'e ban bildirimi gönder
            if admin_id:
                admin_msg = (
                    "🚨 *REFERANS HİLESİ - KALICI BAN* 🚨\n\n"
                    f"👤 *Kullanıcı:* `{user_id}` (@{username})\n"
                    f"⚠️ *Sebep:* Başkasının numarasını ({contact.phone_number}) göndererek referans hilesi yapmaya çalıştı.\n"
                    f"📊 *Ceza:* +2 Uyarı verildi. Toplam Uyarı: `{new_warnings}/5` -> **KALICI BAN!**"
                )
                try: bot.send_message(admin_id, admin_msg, parse_mode="Markdown")
                except: pass
        else:
            # 2 Uyarı ver
            user_msg = (
                f"⚠️ *UYARI! ({new_warnings}/5) — Hileli Referans Girişimi!*\n\n"
                "Başka bir kullanıcıya ait telefon numarası kartı paylaştığınız tespit edildi.\n\n"
                "❗️ *DİKKAT:* Bu tür bir hile girişimine tekrar kalkışırsanız hesabınız **KALICI OLARAK BANLANACAKTIR!**"
            )
            bot.send_message(message.chat.id, user_msg, parse_mode="Markdown")
            
            # Admin'e uyarı bildirimi gönder
            if admin_id:
                admin_msg = (
                    "🚨 *REFERANS HİLESİ - ŞÜPHELİ ETKİNLİK* 🚨\n\n"
                    f"👤 *Kullanıcı:* `{user_id}` (@{username})\n"
                    f"⚠️ *Eylem:* Başkasının numarasını ({contact.phone_number}) göndererek referans doğrulaması yapmaya çalıştı.\n"
                    f"📊 *Ceza:* +2 Uyarı verildi. Toplam Uyarı: `{new_warnings}/5` (Kritik Eşik)"
                )
                try: bot.send_message(admin_id, admin_msg, parse_mode="Markdown")
                except: pass
        return
        
    phone = database.normalize_phone_number(contact.phone_number)
        
    # Benzersizlik (Unique) Kontrolü - Bu numara başka biri tarafından doğrulanmış mı?
    if database.is_phone_number_taken(phone, user_id):
        # Klavye kaldırma kartı gönder-sil
        temp_msg = bot.send_message(message.chat.id, "⏳ İşlem yapılıyor...", reply_markup=types.ReplyKeyboardRemove())
        try: bot.delete_message(message.chat.id, temp_msg.message_id)
        except: pass
        bot.send_message(message.chat.id, "❌ *HATA:* Bu telefon numarası zaten başka bir hesap tarafından doğrulanmış! Her telefon numarası yalnızca bir kez doğrulanabilir.", parse_mode="Markdown")
        return
        
    # Verify in DB
    status = database.verify_user_phone(user_id, phone)
    
    # Reply klavyesini (aşağıdaki buton) kapatmak için geçici görünmez mesaj gönder-sil yap
    temp_msg = bot.send_message(message.chat.id, "⏳ Doğrulanıyor...", reply_markup=types.ReplyKeyboardRemove())
    try: bot.delete_message(message.chat.id, temp_msg.message_id)
    except: pass
    
    # Sansürlü numara formatı (+90******11)
    masked_phone = phone[:3] + "******" + phone[-2:] if len(phone) > 5 else phone
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="back_to_main"))
    
    if status == 'approved':
        metin = (
            f"✅ *Telefon numaranız başarıyla doğrulandı:* `{masked_phone}`\n\n"
            "👥 Referans kaydınız tamamlanmıştır!"
        )
        
        # Eğer kuyrukta bekleyen kupon varsa aktifleştir
        if pending_coupon:
            basarili, sonuc = database.redeem_coupon(user_id, pending_coupon)
            if basarili:
                database.add_to_history(user_id, 6, "Kupon", pending_coupon, -sonuc, status="✅ BAŞARILI")
                metin += f"\n\n🎁 *HEDİYE KUPON KAZANDINIZ!* 🎁\nLink üzerinden gelen `{pending_coupon}` kuponu başarıyla hesabınıza tanımlandı ve bakiyenize *+{sonuc} TL* eklendi!"
                send_coupon_redeemed_notification_to_admin(bot, user_id, pending_coupon, sonuc)
            else:
                metin += f"\n\n❌ *Kupon Aktifleştirilemedi:* {sonuc}"
        else:
            metin += " Aşağıdaki butona tıklayarak ana menüye dönebilir ve işlemlerinize devam edebilirsiniz."
            
        # Eğer kullanıcının referans vereni varsa, davet ilişkisini veritabanına yaz ve bildirim gönder
        user_info = database.get_user_info(user_id)
        if user_info and user_info.get("referred_by"):
            referrer_id = user_info.get("referred_by")
            database.add_referral(referrer_id, user_id)
            try:
                chat_info = bot.get_chat(user_id)
                full_name = f"{chat_info.first_name or ''} {chat_info.last_name or ''}".strip() or "Kullanıcı"
                username_mention = f"@{chat_info.username}" if chat_info.username else "Yok"
            except:
                full_name = "Kullanıcı"
                username_mention = "Yok"
            try:
                bot.send_message(
                    referrer_id, 
                    f"👥 *Yeni Davetli!* Davet linkinizle kayıt olan yeni bir kullanıcı telefon numarasını doğruladı.\n\n"
                    f"👤 *Kullanıcı:* [{full_name}](tg://user?id={user_id}) ({username_mention})\n"
                    f"🆔 *ID:* `{user_id}`\n\n"
                    "Kullanıcı bakiye yükledikçe hesabınıza komisyon yansıyacaktır.",
                    parse_mode="Markdown"
                )
            except:
                pass
        bot.send_message(message.chat.id, metin, reply_markup=markup, parse_mode="Markdown")
        
    elif status == 'pending':
        metin = (
            f"✅ *Telefon numaranız alındı:* `{masked_phone}`\n\n"
            "⏳ Numaranız Türkiye (+90) olmadığı için referans kaydınız **yönetici onayına** gönderilmiştir. Onaylandıktan sonra bilgilendirileceksiniz."
        )
        bot.send_message(message.chat.id, metin, reply_markup=markup, parse_mode="Markdown")
        
        # Notify Admin
        admin_id = os.getenv("ADMIN_ID")
        if admin_id:
            adm_markup = types.InlineKeyboardMarkup()
            adm_markup.row(
                types.InlineKeyboardButton("✅ Onayla", callback_data=f"ref_approve_{user_id}"),
                types.InlineKeyboardButton("❌ Reddet", callback_data=f"ref_reject_{user_id}")
            )
            try:
                bot.send_message(
                    admin_id,
                    f"👤 *Yabancı Numara Referans Onayı*\n\n"
                    f"🆔 Kullanıcı ID: `{user_id}`\n"
                    f"👤 Kullanıcı Adı: @{message.from_user.username or 'Yok'}\n"
                    f"📱 Telefon No: `{phone}`\n\n"
                    f"Bu kullanıcının referans işlemlerini onaylıyor musunuz?",
                    reply_markup=adm_markup,
                    parse_mode="Markdown"
                )
            except:
                pass

@bot.callback_query_handler(func=lambda call: call.data.startswith(('ref_approve_', 'ref_reject_')))
def ref_admin_action_handler(call):
    admin_id = str(os.getenv("ADMIN_ID"))
    if str(call.from_user.id) != admin_id:
        bot.answer_callback_query(call.id, "🚫 Yetkiniz yok!", show_alert=True)
        return
        
    data = call.data
    if data.startswith("ref_approve_"):
        uid = int(data.replace("ref_approve_", ""))
        database.approve_referral(uid)
        
        # Kullanıcının referans vereni varsa ilişkileri kur ve X'e bildirim at
        user_info = database.get_user_info(uid)
        if user_info and user_info.get("referred_by"):
            referrer_id = user_info.get("referred_by")
            database.add_referral(referrer_id, uid)
            try:
                chat_info = bot.get_chat(uid)
                full_name = f"{chat_info.first_name or ''} {chat_info.last_name or ''}".strip() or "Kullanıcı"
                username_mention = f"@{chat_info.username}" if chat_info.username else "Yok"
            except:
                full_name = "Kullanıcı"
                username_mention = "Yok"
            try:
                bot.send_message(
                    referrer_id, 
                    f"👥 *Yeni Davetli!* Davet linkinizle kayıt olan kullanıcı yönetici tarafından onaylandı.\n\n"
                    f"👤 *Kullanıcı:* [{full_name}](tg://user?id={uid}) ({username_mention})\n"
                    f"🆔 *ID:* `{uid}`\n\n"
                    "Kullanıcı bakiye yükledikçe hesabınıza komisyon yansıyacaktır.",
                    parse_mode="Markdown"
                )
            except: pass
            
        try:
            bot.send_message(
                uid, 
                "🎉 *Tebrikler!* Referans hesabınız yönetici tarafından onaylandı. Davet linkinizi alıp paylaşmaya başlayabilirsiniz!", 
                parse_mode="Markdown"
            )
        except: pass
        try: bot.edit_message_text(f"✅ Kullanıcı `{uid}` referans durumu ONAYLANDI.", call.message.chat.id, call.message.message_id)
        except: pass
        bot.answer_callback_query(call.id, "Kullanıcı onaylandı.")
        
    elif data.startswith("ref_reject_"):
        uid = int(data.replace("ref_reject_", ""))
        database.reject_referral(uid)
        try:
            bot.send_message(
                uid, 
                "❌ Referans hesabınız yönetici tarafından onaylanmadı veya reddedildi.", 
                parse_mode="Markdown"
            )
        except: pass
        try: bot.edit_message_text(f"❌ Kullanıcı `{uid}` referans durumu REDDEDİLDİ.", call.message.chat.id, call.message.message_id)
        except: pass
        bot.answer_callback_query(call.id, "Kullanıcı reddedildi.")

@bot.callback_query_handler(func=lambda call: True)
def callback_yonetici(call):
    user_id, data = call.from_user.id, call.data
    
    # Callback / Buton Spamı Koruması
    status, msg, ban_info = security.check_rate_limit(user_id, call.id)
    if status == 'ban':
        notify_admin_of_ban(user_id, ban_info)
        try:
            bot.answer_callback_query(call.id, "⚠️ Çok hızlı işlem yapıyorsunuz!", show_alert=False)
            strikes = security.USER_STRIKES.get(user_id, 5)
            warn_msg = f"⚠️ Çok hızlı işlem yapıyorsunuz! (Uyarı: {strikes}/5)"
            bot.send_message(call.message.chat.id, warn_msg)
            bot.send_message(call.message.chat.id, msg)
        except: pass
        security.USER_STRIKES[user_id] = 0  # Yasaklanınca RAM uyarılarını sıfırla
        return
    elif status == 'banned_cache':
        try:
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, msg)
        except: pass
        return
    elif status == 'warn':
        try:
            bot.answer_callback_query(call.id, "⚠️ Çok hızlı işlem yapıyorsunuz!", show_alert=False)
            bot.send_message(call.message.chat.id, msg)
        except: pass
        return

    admin_id = str(os.getenv("ADMIN_ID"))
    
    # MODÜLER PREFIX KONTROLÜ (Başka modülün işine karışma)
    MODULER_PREFIXES = ('menu_bakiye_yukle', 'yukle_sec_', 'checkpay_', 'qr_show_', 'admin_', 'paynet_', 'menu_numara_al', 'menu_populer', 'select_srv_', 'select_tier_', 'buy_num_', 'rebuy_', 'cancel_sms_', 'check_sms_', 'close_qr', 'cancelpay_', 'admin_ddos_banall')
    if data.startswith(MODULER_PREFIXES):
        return

    # --- ADMIN PANEL TETİKLEYİCİ ---
    if data == "open_admin_panel":
        if str(user_id) == admin_id:
            markup = admin_panel.admin_klavyesi()
            safe_edit(call, "🛡️ *Yönetim Paneli (Masterclass)*", markup)
            try: bot.answer_callback_query(call.id)
            except: pass
        return

    if not user_allowed(user_id, chat_id=call.message.chat.id, call_id=call.id): return

    if data == "back_to_main":
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        if call.message.content_type == "photo":
            safe_edit(call, config.MESAJLAR["hosgeldin"].format(isim=call.from_user.first_name), ana_menu_klavyesi(user_id=user_id))
        else:
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
            with open("veritas_sms_logo_yatay.png", "rb") as photo:
                bot.send_photo(
                    call.message.chat.id,
                    photo,
                    caption=config.MESAJLAR["hosgeldin"].format(isim=call.from_user.first_name),
                    reply_markup=ana_menu_klavyesi(user_id=user_id),
                    parse_mode="Markdown"
                )
        try: bot.answer_callback_query(call.id)
        except: pass

    elif data == "menu_kupon_kullan":
        safe_edit(call, "🎟️ Kupon Kullanımı\n\nLütfen kupon kodunuzu bu sohbete yazın:", geri_don())
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        bot.register_next_step_handler(call.message, process_kupon_kullan_alim, photo_message_id=call.message.message_id)
        try: bot.answer_callback_query(call.id)
        except: pass

    elif data == "menu_duyurular":
        d = database.get_latest_announcements()
        markup = ana_menu_klavyesi(user_id=user_id) 
        if not d: 
            safe_edit(call, "📢 *Duyuru bulunmuyor.*", markup)
        else:
            metin = "📢 *Duyurular*\n\n"
            for i in d:
                tarih = i['date'].strftime('%d.%m %H:%M') if hasattr(i['date'], 'strftime') else str(i['date'])
                msg = i['message'].replace('*', '').replace('_', '').replace('`', '').replace('[', '').replace(']', '')
                metin += f"📅 `{tarih}`\n💬 {msg}\n\n"
            safe_edit(call, metin, markup)
        try: bot.answer_callback_query(call.id)
        except: pass
            
    elif data == "menu_referans":
        user_info = database.get_user_info(user_id)
        if not user_info or user_info.get("phone_number") is None:
            metin = (
                "⚠️ *Telefon Doğrulaması Gerekli* ⚠️\n\n"
                "Sahte hesapların referans sistemini kötüye kullanmasını önlemek amacıyla tek seferlik doğrulama yapılması gerekmektedir.\n\n"
                "🔒 *Güvenlik & Gizlilik:* Telefon numaranız sadece sistem doğrulaması için kullanılır, 3. şahıslarla asla paylaşılmaz. Paylaştığınız numara mesajı doğrulama biter bitmez sohbet geçmişinizden anında silinecektir.\n\n"
                "👇 Lütfen aşağıdaki *📱 Numaramı Paylaş* butonunu kullanarak numaranızı doğrulayın."
            )
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add(types.KeyboardButton("📱 Numaramı Paylaş", request_contact=True))
            
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
            
            sent_msg = bot.send_message(call.message.chat.id, metin, reply_markup=markup, parse_mode="Markdown")
            with verification_lock:
                PENDING_VERIFICATION_MSG_IDS[user_id] = {"message_id": sent_msg.message_id, "timestamp": time.time()}
            bot.answer_callback_query(call.id)
            return

        ref_status = user_info.get("ref_status")
        phone = user_info.get("phone_number")
        
        if ref_status == "pending":
            metin = (
                "⏳ *Referans Hesabınız Onay Bekliyor* ⏳\n\n"
                f"Telefon numaranız (`{phone}`) başarıyla kaydedildi.\n\n"
                "⚠️ Numaranız Türkiye (+90) olmadığı için referans hesabınız şu an **yönetici onayında** beklemektedir.\n"
                "Yönetici onayından sonra davet linkiniz aktif edilecektir."
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="back_to_main"))
            safe_edit(call, metin, markup)
            bot.answer_callback_query(call.id)
            return
            
        elif ref_status == "rejected":
            metin = (
                "🚫 *Referans Hesabınız Reddedildi* 🚫\n\n"
                "Yönetici, referans hesabınızın kullanımını askıya aldı veya reddetti. Detaylı bilgi için destekle iletişime geçebilirsiniz."
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="back_to_main"))
            safe_edit(call, metin, markup)
            bot.answer_callback_query(call.id)
            return

        # Get or generate ref_token dynamically
        ref_token = user_info.get("ref_token")
        if not ref_token:
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            conn = database.get_db_connection()
            cursor = conn.cursor()
            while True:
                token = ''.join(secrets.choice(alphabet) for _ in range(16))
                cursor.execute("SELECT user_id FROM users WHERE ref_token = %s", (token,))
                if cursor.fetchone() is None:
                    ref_token = token
                    break
            cursor.execute("UPDATE users SET ref_token = %s WHERE user_id = %s", (ref_token, user_id))
            conn.commit()
            conn.close()

        bot_info = bot.get_me()
        bot_username = bot_info.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{ref_token}"
        
        stats = database.get_referral_stats(user_id)
        ref_rate = database.get_setting("referral_percentage", "2.0")
        if not ref_rate:
            ref_rate = "2.0"
            
        ref_details = database.get_referred_users_detail(user_id)
        details_text = ""
        if ref_details:
            details_text = "\n\n👥 *Davet Ettiğiniz Kişiler & Kazançlarınız:*\n"
            for r in ref_details:
                username = f"@{r['username']}" if r['username'] and r['username'] != "Yok" else f"Kullanıcı (`{r['referred_id']}`)"
                details_text += f"├ {username} (ID: `{r['referred_id']}`) — `{r['total_earnings']:.2f} TL`\n"
            if details_text.endswith("\n"):
                # Göz estetiği için son satırı düzeltelim
                lines = details_text.strip().split("\n")
                if lines:
                    lines[-1] = lines[-1].replace("├", "└")
                    details_text = "\n" + "\n".join(lines) + "\n"
        else:
            details_text = "\n\n👥 *Davet Ettiğiniz Kişiler:*\n_Henüz davet ettiğiniz onaylı bir kullanıcı bulunmamaktadır._"
            
        metin = (
            "👥 *Referans Sistemi* 👥\n\n"
            "Bota yeni kullanıcılar davet ederek kazanç elde edebilirsiniz! "
            "Davet ettiğiniz kullanıcılar bota bakiye yüklediklerinde, "
            f"yükledikleri tutarın *%{ref_rate}*'i anında sizin bakiyenize eklenir.\n\n"
            f"📊 *İstatistikleriniz:*\n"
            f"├ 👥 Davet Edilen Kişi: `{stats['count']}`\n"
            f"└ 💰 Toplam Kazanç: `{stats['total_earnings']} TL`"
            f"{details_text}\n"
            f"🔗 *Davet Linkiniz:*\n"
            f"`{ref_link}`\n\n"
            "💡 _Üstteki linke tıklayarak kopyalayabilir ve arkadaşlarınızla paylaşabilirsiniz._"
        )
        markup = types.InlineKeyboardMarkup()
        
        # Eğer kullanıcı birinin referansı ise bağı iptal etme butonu göster
        referred_by = database.get_referrer(user_id)
        if referred_by:
            markup.add(types.InlineKeyboardButton("🚫 Referans Bağını İptal Et", callback_data="cancel_my_referral"))
            
        markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="back_to_main"))
        safe_edit(call, metin, markup)
        bot.answer_callback_query(call.id)
        return

    elif data == "cancel_my_referral":
        database.remove_referral(user_id)
        bot.answer_callback_query(call.id, "✅ Referans bağınız başarıyla silindi.", show_alert=True)
        # Referans menüsünü yenile
        call.data = "menu_referans"
        callback_yonetici(call)
        return

    elif data == "menu_destek":
        if database.can_create_ticket(user_id):
            safe_edit(call, config.MESAJLAR["destek_istek"], geri_don())
            bot.clear_step_handler_by_chat_id(call.message.chat.id)
            bot.register_next_step_handler(call.message, process_support_ticket, photo_message_id=call.message.message_id)
            try: bot.answer_callback_query(call.id)
            except: pass
        else:
            try: bot.answer_callback_query(call.id, config.MESAJLAR["destek_limit"], show_alert=True)
            except: pass

    elif data == "menu_bakiyem":
        mevcut_bakiye = database.get_balance(user_id)
        safe_edit(call, f"💳 *Güncel Bakiyeniz:* `{mevcut_bakiye} TL`", geri_don())
        try: bot.answer_callback_query(call.id)
        except: pass

    elif data == "menu_gecmisim" or data.startswith("historypage_"):
        current_page = 1
        if data.startswith("historypage_"):
            current_page = int(data.split("_")[1])
            
        limit = 5
        offset = (current_page - 1) * limit
        
        conn = None
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Toplam işlem sayısını al
            cursor.execute('SELECT COUNT(*) as toplam FROM history WHERE user_id = %s', (user_id,))
            total_count = cursor.fetchone()['toplam']
            
            # Toplam sayfa sayısını yukarı yuvarlayarak hesapla (Math kütüphanesine bağımlı olmadan)
            total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
            
            # Sayfaya ait 5 kaydı çek
            cursor.execute('SELECT action_type, service_name, fake_number, price, date, status FROM history WHERE user_id = %s ORDER BY id DESC LIMIT %s OFFSET %s', (user_id, limit, offset))
            islemler = cursor.fetchall()
            
            if not islemler: 
                if call.message.content_type == "photo":
                    try: bot.delete_message(call.message.chat.id, call.message.message_id)
                    except: pass
                    bot.send_message(call.message.chat.id, config.MESAJLAR["gecmis_bos"], reply_markup=geri_don(), parse_mode="Markdown")
                else:
                    safe_edit(call, config.MESAJLAR["gecmis_bos"], geri_don())
                try: bot.answer_callback_query(call.id)
                except: pass
                return

            metin = (
                "╔═══════════════════╗\n"
                "       💎 *İŞLEM GEÇMİŞİNİZ* 💎\n"
                "╚═══════════════════╝\n\n"
            )
            
            for idx, op in enumerate(islemler, 1):
                gercek_idx = offset + idx
                tarih = op['date'].strftime("%d.%m.%Y | %H:%M") if hasattr(op['date'], 'strftime') else str(op.get('date', 'Bilinmiyor'))
                status = str(op.get('status') or '✅ BAŞARILI')
                
                if "BAŞARILI" in status: icon = "🟢"
                elif "İPTAL" in status: icon = "🟡"
                else: icon = "🔴"
                
                islem_kodu = op.get('action_type') or 0
                service_name_val = (op.get('service_name') or "Bilinmeyen").replace("`", "")
                islem_adi = (config.ISLEM_TIPLERI.get(islem_kodu) or service_name_val).replace('_', ' ').replace('*', '')
                
                ham_fiyat = float(op['price']) if op.get('price') is not None else 0.0
                
                # İşlem tipine göre başlığa eklenecek kurumsal emoji tespiti
                if islem_kodu in (1, 5, 6): # Kripto, Admin Yüklemesi, Kupon -> Para Girişi
                    islem_ikonu = "💰"
                    gosterilecek_fiyat = f"+{abs(ham_fiyat):.2f}"
                elif islem_kodu == 2: # Başarılı Numara Alımı -> Telefon
                    islem_ikonu = "📱"
                    gosterilecek_fiyat = f"-{abs(ham_fiyat):.2f}"
                elif islem_kodu in (3, 4): # İptaller ve Zaman Aşımı -> Çarpı/Geri İade
                    islem_ikonu = "❌"
                    gosterilecek_fiyat = f"+{abs(ham_fiyat):.2f}"
                else:
                    islem_ikonu = "ℹ️"
                    gosterilecek_fiyat = f"+{abs(ham_fiyat):.2f}"
                
                fake_num_val = (op.get('fake_number') or "Yok").replace("`", "")
                
                # Detaylı, Ülke Bayraklı ve Gelen Kod Dahil Premium Format
                metin += (
                    f"{icon} *#{gercek_idx} — {islem_ikonu} {islem_adi}*\n"
                    f"├ 🛒 *Servis:* `{service_name_val}`\n"
                    f"├ 📱 *Detaylar:* `{fake_num_val}`\n"
                    f"├ 💰 *İşlem Tutarı:* `{gosterilecek_fiyat} TL`\n"
                    f"└ 📅 *Tarih ve Saat:* {tarih}\n"
                    "───────────────────\n"
                )
            
            # Klavye Navigasyon Butonları
            markup = types.InlineKeyboardMarkup()
            nav_buttons = []
            
            if current_page > 1:
                nav_buttons.append(types.InlineKeyboardButton("◀️ Geri", callback_data=f"historypage_{current_page - 1}"))
                
            if offset + limit < total_count:
                nav_buttons.append(types.InlineKeyboardButton("İleri ▶️", callback_data=f"historypage_{current_page + 1}"))
                
            if nav_buttons:
                markup.row(*nav_buttons)
                
            markup.add(types.InlineKeyboardButton(config.BUTONLAR["ana_menu"], callback_data="back_to_main"))
            
            # Ortalanmış ve toplam sayfayı gösteren sayaç (Örn: 📄 Sayfa 1/3)
            metin += f"\n📄 _Sayfa {current_page}/{total_pages}_"
            
            if call.message.content_type == "photo":
                try: bot.delete_message(call.message.chat.id, call.message.message_id)
                except: pass
                try:
                    bot.send_message(call.message.chat.id, metin, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(call.message.chat.id, metin, reply_markup=markup)
            else:
                safe_edit(call, metin, markup)
            try: bot.answer_callback_query(call.id)
            except: pass
        except Exception as e:
            print(f"[ERROR] menu_gecmisim exception: {repr(e)}")
            try:
                if call.message.content_type == "photo":
                    try: bot.delete_message(call.message.chat.id, call.message.message_id)
                    except: pass
                    bot.send_message(call.message.chat.id, f"❌ İşlem geçmişi yüklenirken bir hata oluştu.", reply_markup=geri_don())
                else:
                    safe_edit(call, f"❌ İşlem geçmişi yüklenirken bir hata oluştu.", geri_don())
            except: pass
            try: bot.answer_callback_query(call.id)
            except: pass
        finally:
            if conn:
                try: conn.close()
                except: pass

def process_support_ticket(message, photo_message_id):
    chat_id, user_id = message.chat.id, message.from_user.id
    if not user_allowed(user_id, chat_id=chat_id): return
    
    # --- GÜVENLİK KALKANI: ZARARLI GİRDİ KONTROLÜ ---
    is_valid, sec_msg, ban_info = security.validate_input(user_id, message.text, input_type="general")
    if not is_valid:
        if ban_info: notify_admin_of_ban(user_id, ban_info)
        safe_edit(chat_id, f"⚠️ *{sec_msg}*", geri_don(), photo_message_id)
        return

    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    database.create_ticket(user_id, message.text)
    safe_edit(chat_id, config.MESAJLAR["destek_basarili"], geri_don(), photo_message_id)

def process_kupon_kullan_alim(message, photo_message_id):
    chat_id, user_id = message.chat.id, message.from_user.id
    if not user_allowed(user_id, chat_id=chat_id): return
    
    # Girdi Tipi Kontrolü: Metin dışı veriler (sticker, resim vs.) engellenir
    if not message.text:
        try: bot.delete_message(chat_id, message.message_id)
        except: pass
        safe_edit(chat_id, "❌ *HATA:* Lütfen sadece kupon kodunu metin olarak gönderin! Çıkartma, resim vb. girdiler kabul edilmez.", geri_don(), photo_message_id)
        return
        
    kod = message.text.strip().upper()
    
    # --- GÜVENLİK KALKANI: ZARARLI GİRDİ (SQLi/XSS) KONTROLÜ ---
    is_valid, sec_msg, ban_info = security.validate_input(user_id, kod, input_type="coupon")
    if not is_valid:
        if ban_info: notify_admin_of_ban(user_id, ban_info)
        safe_edit(chat_id, f"⚠️ *{sec_msg}*", geri_don(), photo_message_id)
        return

    try: bot.delete_message(chat_id, message.message_id)
    except: pass

    basarili, sonuc = database.redeem_coupon(user_id, kod)
    if basarili:
        database.add_to_history(user_id, 6, "Kupon", kod, -sonuc, status="✅ BAŞARILI")
        safe_edit(chat_id, f"🎉 Tebrikler!\n\n`{kod}` kuponunu başarıyla kullandınız.\nHesabınıza {sonuc} TL eklendi.", geri_don(), photo_message_id)
        send_coupon_redeemed_notification_to_admin(bot, user_id, kod, sonuc)
    else:
        safe_edit(chat_id, sonuc, geri_don(), photo_message_id)

def backup_worker(bot):
    """Yedekleme, FSM temizliği ve kripto ödeme zaman aşımı/uyarı yönetimini yapan merkezi arka plan thread'i."""
    import glob
    import subprocess
    from handlers.payment_handler import BEKLEYEN_ODEMELER, odeme_lock
    
    # 10 saniye bekle ki bot tam olarak başlasın
    time.sleep(10)
    
    last_fsm_cleanup = 0
    
    while True:
        try:
            current_time = time.time()
            
            # --- 1. OTOMATİK VERİTABANI YEDEKLEME (12 Saatte Bir) ---
            try:
                last_backup_str = database.get_setting("last_backup_time", "0.0")
                last_backup_time = float(last_backup_str)
                if current_time - last_backup_time >= 43200:
                    print("[*] Otomatik veritabanı yedekleme zamanı geldi. Yedekleniyor...")
                    
                    backup_dir = "D:/xamkk/mysql/backups_veritas"
                    if not os.path.exists(backup_dir):
                        os.makedirs(backup_dir)
                        
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"veritas_backup_{timestamp}.sql"
                    filepath = os.path.join(backup_dir, filename)
                    
                    mysqldump_path = "D:/xamkk/mysql/bin/mysqldump.exe"
                    db_name = os.getenv("DB_NAME", "veritas_sms")
                    db_user = os.getenv("DB_USER", "root")
                    db_password = os.getenv("DB_PASSWORD", "")
                    
                    args = [mysqldump_path, f"-u{db_user}"]
                    if db_password:
                        args.append(f"-p{db_password}")
                    args.append(db_name)
                    
                    with open(filepath, "w", encoding="utf-8") as outfile:
                        result = subprocess.run(args, stdout=outfile, shell=False)
                    
                    if result.returncode == 0:
                        print(f"[+] Veritabanı yedeği alındı: {filepath}")
                        database.update_setting("last_backup_time", str(current_time))
                        
                        admin_id = os.getenv("ADMIN_ID")
                        if admin_id:
                            try:
                                with open(filepath, "rb") as doc:
                                    bot.send_document(
                                        admin_id, 
                                        doc, 
                                        caption=f"📋 *Otomatik Veritabanı Yedeği*\n\n📅 Tarih: `{time.strftime('%d.%m.%Y %H:%M')}`\n💾 Dosya: `{filename}`\n🛡️ _Yedekleme 12 saatlik döngü ile tamamlandı ve buluta yüklendi._",
                                        parse_mode="Markdown"
                                    )
                            except Exception as te:
                                print(f"[-] Telegram yedek iletim hatası: {te}")
                                
                        # 7 günden (604800 saniye) eski yedekleri sil
                        now = time.time()
                        for f in glob.glob(os.path.join(backup_dir, "veritas_backup_*.sql")):
                            if os.stat(f).st_mtime < now - 604800:
                                try:
                                    os.remove(f)
                                    print(f" -> Eski yedek dosya temizlendi: {f}")
                                except:
                                    pass
                    else:
                        print(f"[-] Hata: mysqldump çalıştırılamadı (Kod: {result.returncode})")
            except Exception as be:
                print(f"[-] Yedekleme hatası: {be}")
                
            # --- 2. FSM TELEFON DOĞRULAMA TEMİZLİĞİ (Saatte Bir) ---
            if current_time - last_fsm_cleanup >= 3600:
                try:
                    with verification_lock:
                        expired_users = [
                            uid for uid, info in PENDING_VERIFICATION_MSG_IDS.items()
                            if isinstance(info, dict) and current_time - info.get("timestamp", 0) > 86400
                        ]
                        for uid in expired_users:
                            PENDING_VERIFICATION_MSG_IDS.pop(uid, None)
                    if expired_users:
                        print(f"[+] Otomatik Temizlik: {len(expired_users)} adet eski telefon doğrulama oturumu temizlendi.")
                    last_fsm_cleanup = current_time
                except Exception as cle:
                    print(f"[-] FSM temizlik hatası: {cle}")
                    
            # --- 3. KRİPTO ÖDEME ZAMAN AŞIMI VE UYARI YÖNETİMİ (Her Dakika) ---
            try:
                # Eşzamanlılığı korumak için bekleyen ödeme kayıtlarının kopyasını al
                with odeme_lock:
                    pending_invoices = list(BEKLEYEN_ODEMELER.items())
                
                for key, info in pending_invoices:
                    user_id = info["user_id"]
                    chat_id = info.get("chat_id")
                    msg_id = info.get("message_id")
                    start_time_ms = info["time_ms"]
                    
                    elapsed_seconds = current_time - (start_time_ms / 1000.0)
                    remaining_seconds = 7200 - elapsed_seconds # 2 saat limit
                    
                    # A. 2 Saatlik Zaman Aşımı (Timeout)
                    if remaining_seconds <= 0:
                        with odeme_lock:
                            BEKLEYEN_ODEMELER.pop(key, None)
                        
                        if chat_id and msg_id:
                            # Mevcut ödeme ekranı mesajını düzenle
                            from handlers.payment_handler import safe_payment_edit
                            try:
                                safe_payment_edit(bot, chat_id, msg_id, "❌ *Ödeme işleminiz hiçbir işlem yapılmadığı için iptal edildi.* \n\nSüresi dolan faturalara kesinlikle ödeme göndermeyiniz.", types.InlineKeyboardMarkup())
                            except:
                                pass
                        continue
                    
                    # B. Son 5 Dakika Uyarısı
                    elif remaining_seconds <= 300: # 5 dakika
                        if not info.get("notified_5m", False):
                            with odeme_lock:
                                if key in BEKLEYEN_ODEMELER:
                                    BEKLEYEN_ODEMELER[key]["notified_5m"] = True
                            if chat_id:
                                try:
                                    bot.send_message(chat_id, f"⚠️ *Ödeme Faturası Zaman Aşımı Riski!*\n\nYüklemek istediğiniz `{key.split('_')[1]} {key.split('_')[0].upper()}` faturasının süresi dolmak üzere!\n\n⏳ Kalan Süre: *5 dakika*")
                                except:
                                    pass
                                    
                    # C. Son 10 Dakika Uyarısı
                    elif remaining_seconds <= 600: # 10 dakika
                        if not info.get("notified_10m", False):
                            with odeme_lock:
                                if key in BEKLEYEN_ODEMELER:
                                    BEKLEYEN_ODEMELER[key]["notified_10m"] = True
                            if chat_id:
                                try:
                                    bot.send_message(chat_id, f"⚠️ *Ödeme Faturası Zaman Aşımı Riski!*\n\nYüklemek istediğiniz `{key.split('_')[1]} {key.split('_')[0].upper()}` faturasının süresi dolmak üzere!\n\n⏳ Kalan Süre: *10 dakika*")
                                except:
                                    pass
                                    
            except Exception as pe:
                print(f"[-] Kripto ödeme zaman aşımı kontrol hatası: {pe}")
                
        except Exception as e:
            print(f"[-] Merkezi yedekleme / temizlik worker hatası: {e}")
            
        time.sleep(60)

if __name__ == "__main__":
    database.setup_database()
    number_handler.recover_active_rentals(bot)
    number_handler.start_central_sms_tracking_worker(bot)
    
    # Otomatik Yedekleme İş Parçacığını Başlat
    threading.Thread(target=backup_worker, args=(bot,), daemon=True).start()
    
    print("====================================")
    print(" [URL] Veritas SMS Botu Baslatildi!")
    print(" [SEC] Sistem Aktif ve Korumali.")
    print("====================================")
    bot.infinity_polling()
