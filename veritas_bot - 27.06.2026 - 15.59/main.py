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

# Handler'ları kayıt et
admin_services.register_admin_service_handlers(bot)
admin_panel.register_admin_handlers(bot)
payment_handler.register_payment_handlers(bot)
number_handler.register_number_handlers(bot)

def notify_admin_of_ban(user_id, ban_info):
    if not ban_info: return
    admin_id = os.getenv("ADMIN_ID")
    if not admin_id: return
    metin = (
        "🚨 *SİBER GÜVENLİK ALARMI - OTOMATİK BAN* 🚨\n\n"
        f"👤 *Hedef ID:* `{user_id}`\n"
        f"⚠️ *Tehdit Tipi:* `Tip {ban_info['type']} ({ban_info['reason']})`\n"
        f"📝 *Yakalanan Payload:* `{ban_info['input']}`\n\n"
        "🛡️ _Bot savunma kalkanı saldırganı anında tespit edip kalıcı olarak banladı._\n"
        "🛑 _Eğer organize bir saldırı seziyorsanız, Admin Panel > Sistem Kontrol > Sunucuyu Kapat butonunu kullanarak botu dondurabilirsiniz._"
    )
    try: bot.send_message(admin_id, metin, parse_mode="Markdown")
    except: pass

# --- GLOBAL DEĞİŞKENLER ---
# AKTIF_TAKIPLER ve ilgili takip mantığı handlers/number_handler.py içerisindedir.
PENDING_VERIFICATION_MSG_IDS = {}

def user_allowed(user_id, chat_id=None, call_id=None):
    # 1. Grup Whitelist Kontrolü (Botun illegal gruplara eklenmesini önler)
    if chat_id and not security.is_group_allowed(chat_type="group" if chat_id < 0 else "private", chat_id=chat_id):
        return False
        
    # 2. Spam / Rate Limit Kontrolü (Komut ve Mesaj Spamını Engeller)
    status, msg, ban_info = security.check_rate_limit(user_id, call_id)
    if status == 'ban':
        notify_admin_of_ban(user_id, ban_info)
        if call_id:
            try: bot.answer_callback_query(call_id)
            except: pass
        if chat_id:
            try: bot.send_message(chat_id, msg)
            except: pass
        return False
    elif status == 'warn':
        if call_id:
            try: bot.answer_callback_query(call_id)
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
    referrer_id = None
    
    print(f"[TRACE start_komutu] user_id: {user_id}, is_new_user: {is_new_user}, args: {args}, has_ref: {has_ref}")
    
    if has_ref:
        try:
            ref_param = args[1].replace("ref_", "")
            print(f"[TRACE start_komutu] ref_param: {ref_param}")
            if ref_param.isdigit():
                potential_referrer = int(ref_param)
                if potential_referrer == user_id:
                    print(f"[TRACE start_komutu] Self-referral attempt detected.")
                    # Kendi kendine referans olma uyarısı
                    admin_id = os.getenv("ADMIN_ID")
                    if admin_id:
                        try: bot.send_message(admin_id, f"⚠️ *ŞÜPHELİ ETKİNLİK:* Kullanıcı `{user_id}` kendi kendine referans olmaya çalıştı!", parse_mode="Markdown")
                        except: pass
                    has_ref = False
                else:
                    # Referans verenin doğruluğunu kontrol et
                    ref_info = database.get_user_info(potential_referrer)
                    print(f"[TRACE start_komutu] potential_referrer: {potential_referrer}, ref_info: {ref_info}")
                    if ref_info is not None:
                        referrer_id = potential_referrer
                    else:
                        print(f"[TRACE start_komutu] Referrer X not found in DB!")
                        has_ref = False
            else:
                has_ref = False
        except Exception as e:
            print(f"[TRACE start_komutu] Exception in parsing ref: {e}")
            has_ref = False

    print(f"[TRACE start_komutu] Final variables -> has_ref: {has_ref}, is_new_user: {is_new_user}, referrer_id: {referrer_id}")

    # EĞER YENİ BİR KULLANICI REFERANS LİNKİYLE GELDİYSE -> DOĞRUDAN TELEFON DOĞRULAT!
    if has_ref and is_new_user:
        # Kullanıcıyı referred_by ile kaydet
        database.add_user(user_id, message.from_user.username or "Yok", referred_by=referrer_id)
        
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
        PENDING_VERIFICATION_MSG_IDS[user_id] = sent_msg.message_id
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
    
    # Silinecek uyarı mesajı ID'sini al ve sil
    warning_msg_id = PENDING_VERIFICATION_MSG_IDS.pop(user_id, None)
    if warning_msg_id:
        try: bot.delete_message(message.chat.id, warning_msg_id)
        except: pass
    
    if contact.user_id != user_id:
        bot.send_message(message.chat.id, "❌ Sadece kendi telefon numaranızı doğrulayabilirsiniz!")
        return
        
    phone = contact.phone_number
    # Normalize phone: ensure starts with +
    if not phone.startswith("+"):
        phone = "+" + phone
        
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
            "👥 Referans kaydınız tamamlanmıştır! Aşağıdaki butona tıklayarak ana menüye dönebilir ve referans linkinizi alabilirsiniz."
        )
        # Eğer kullanıcının referans vereni varsa, davet ilişkisini veritabanına yaz ve bildirim gönder
        user_info = database.get_user_info(user_id)
        if user_info and user_info.get("referred_by"):
            referrer_id = user_info.get("referred_by")
            database.add_referral(referrer_id, user_id)
            try:
                bot.send_message(
                    referrer_id, 
                    f"👥 *Yeni Davetli!* Davet linkinizle kayıt olan yeni bir kullanıcı telefon numarasını doğruladı. (ID: `{user_id}`)\n"
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
                bot.send_message(
                    referrer_id, 
                    f"👥 *Yeni Davetli!* Davet linkinizle kayıt olan kullanıcı (ID: `{uid}`) yönetici tarafından onaylandı.\n"
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
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, msg)
        except: pass
        return
    elif status == 'banned_cache':
        try:
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, msg)
        except: pass
        return
    elif status == 'warn':
        try:
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, msg)
        except: pass
        return

    admin_id = str(os.getenv("ADMIN_ID"))
    
    # MODÜLER PREFIX KONTROLÜ (Başka modülün işine karışma)
    MODULER_PREFIXES = ('menu_bakiye_yukle', 'yukle_sec_', 'checkpay_', 'qr_show_', 'admin_', 'paynet_', 'menu_numara_al', 'menu_populer', 'select_srv_', 'select_tier_', 'buy_num_', 'rebuy_', 'cancel_sms_', 'check_sms_', 'close_qr')
    if data.startswith(MODULER_PREFIXES):
        return

    try: bot.answer_callback_query(call.id)
    except: pass
    
    # --- ADMIN PANEL TETİKLEYİCİ ---
    if data == "open_admin_panel":
        if str(user_id) == admin_id:
            markup = admin_panel.admin_klavyesi()
            safe_edit(call, "🛡️ *Yönetim Paneli (Masterclass)*", markup)
        return

    if not user_allowed(user_id, chat_id=call.message.chat.id, call_id=call.id): return

    if data == "back_to_main":
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        safe_edit(call, config.MESAJLAR["hosgeldin"].format(isim=call.from_user.first_name), ana_menu_klavyesi(user_id=user_id))

    elif data == "menu_kupon_kullan":
        safe_edit(call, "🎟️ Kupon Kullanımı\n\nLütfen kupon kodunuzu bu sohbete yazın:", geri_don())
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        bot.register_next_step_handler(call.message, process_kupon_kullan_alim, photo_message_id=call.message.message_id)

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
            PENDING_VERIFICATION_MSG_IDS[user_id] = sent_msg.message_id
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

        # approved (onaylı) ise referans panelini göster
        bot_info = bot.get_me()
        bot_username = bot_info.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        stats = database.get_referral_stats(user_id)
        ref_rate = database.get_setting("referral_percentage", "2.0")
        if not ref_rate:
            ref_rate = "2.0"
            
        metin = (
            "👥 *Referans Sistemi* 👥\n\n"
            "Bota yeni kullanıcılar davet ederek kazanç elde edebilirsiniz! "
            "Davet ettiğiniz kullanıcılar bota bakiye yüklediklerinde, "
            f"yükledikleri tutarın *%{ref_rate}*'i anında sizin bakiyenize eklenir.\n\n"
            f"📊 *İstatistikleriniz:*\n"
            f"├ 👥 Davet Edilen Kişi: `{stats['count']}`\n"
            f"└ 💰 Toplam Kazanç: `{stats['total_earnings']} TL`\n\n"
            f"🔗 *Davet Linkiniz:*\n"
            f"`{ref_link}`\n\n"
            "💡 _Üstteki linke tıklayarak kopyalayabilir ve arkadaşlarınızla paylaşabilirsiniz._"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="back_to_main"))
        safe_edit(call, metin, markup)
        bot.answer_callback_query(call.id)

    elif data == "menu_destek":
        if database.can_create_ticket(user_id):
            safe_edit(call, config.MESAJLAR["destek_istek"], geri_don())
            bot.clear_step_handler_by_chat_id(call.message.chat.id)
            bot.register_next_step_handler(call.message, process_support_ticket, photo_message_id=call.message.message_id)
        else: bot.answer_callback_query(call.id, config.MESAJLAR["destek_limit"], show_alert=True)

    elif data == "menu_bakiyem":
        mevcut_bakiye = database.get_balance(user_id)
        safe_edit(call, f"💳 *Güncel Bakiyeniz:* `{mevcut_bakiye} TL`", geri_don())

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
                safe_edit(call, config.MESAJLAR["gecmis_bos"], geri_don())
                return

            metin = (
                "╔═══════════════════╗\n"
                "       💎 *İŞLEM GEÇMİŞİNİZ* 💎\n"
                "╚═══════════════════╝\n\n"
            )
            
            for idx, op in enumerate(islemler, 1):
                gercek_idx = offset + idx
                tarih = op['date'].strftime("%d.%m.%Y | %H:%M") if hasattr(op['date'], 'strftime') else str(op['date'])
                status = str(op.get('status', '✅ BAŞARILI'))
                
                if "BAŞARILI" in status: icon = "🟢"
                elif "İPTAL" in status: icon = "🟡"
                else: icon = "🔴"
                
                islem_kodu = op.get('action_type', 0)
                islem_adi = config.ISLEM_TIPLERI.get(islem_kodu, op['service_name'])
                
                # --- GÖRSEL VE PSİKOLOJİK EMBELLISHMENT KATMANI ---
                ham_fiyat = float(op['price'])
                
                # İşlem tipine göre başlığa eklenecek kurumsal emoji tespiti
                if islem_kodu in (1, 5, 6): # Kripto, Admin Yüklemesi, Kupon -> Para Girişi
                    islem_ikonu = "💰"
                    gosterilecek_fiyat = f"+{abs(ham_fiyat)}"
                elif islem_kodu == 2: # Başarılı Numara Alımı -> Telefon
                    islem_ikonu = "📱"
                    gosterilecek_fiyat = f"-{abs(ham_fiyat)}"
                elif islem_kodu in (3, 4): # İptaller ve Zaman Aşımı -> Çarpı/Geri İade
                    islem_ikonu = "❌"
                    gosterilecek_fiyat = f"+{abs(ham_fiyat)}"
                else:
                    islem_ikonu = "ℹ️"
                    gosterilecek_fiyat = f"+{abs(ham_fiyat)}"
                
                # Detaylı, Ülke Bayraklı ve Gelen Kod Dahil Premium Format
                metin += (
                    f"{icon} *#{gercek_idx} — {islem_ikonu} {islem_adi}*\n"
                    f"├ 🛒 *Servis:* `{op['service_name']}`\n"
                    f"├ 📱 *Detaylar:* {op['fake_number']}\n"
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
            
            safe_edit(call, metin, markup)
        except Exception as e:
            safe_edit(call, f"❌ İşlem geçmişi yüklenirken bir hata oluştu.", geri_don())
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
    else:
        safe_edit(chat_id, sonuc, geri_don(), photo_message_id)

def backup_worker(bot):
    """Her 12 saatte bir veritabanını yedekleyen arka plan iş parçacığı."""
    import glob
    import subprocess
    
    # 10 saniye bekle ki bot tam olarak başlasın
    time.sleep(10)
    
    while True:
        try:
            # En son yedekleme zamanını ayarlar tablosundan çek
            last_backup_str = database.get_setting("last_backup_time", "0.0")
            last_backup_time = float(last_backup_str)
            current_time = time.time()
            
            # 12 saat = 43200 saniye
            if current_time - last_backup_time >= 43200:
                print("[*] Otomatik veritabanı yedekleme zamanı geldi. Yedekleniyor...")
                
                # Yedek dizinini oluştur
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
                
                # Komutu oluştur
                cmd = f'"{mysqldump_path}" -u{db_user}'
                if db_password:
                    cmd += f" -p{db_password}"
                cmd += f" {db_name} > \"{filepath}\""
                
                result = subprocess.run(cmd, shell=True)
                if result.returncode == 0:
                    print(f"[+] Veritabanı yedeği alındı: {filepath}")
                    database.update_setting("last_backup_time", str(current_time))
                    
                    # Admin Telegram ID'sine dosyayı gönder (Bulut Güvenliği)
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
        except Exception as e:
            print(f"[-] Yedekleme iş parçacığı hatası: {e}")
            
        # Saatte bir kontrol et
        time.sleep(3600)

if __name__ == "__main__":
    database.setup_database()
    number_handler.recover_active_rentals(bot)
    
    # Otomatik Yedekleme İş Parçacığını Başlat
    threading.Thread(target=backup_worker, args=(bot,), daemon=True).start()
    
    print("====================================")
    print(" [URL] Veritas SMS Botu Baslatildi!")
    print(" [SEC] Sistem Aktif ve Korumali.")
    print("====================================")
    bot.infinity_polling()
