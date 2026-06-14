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
from handlers import admin_services, payment_handler
from providers import grizzly_provider

load_dotenv()
bot = telebot.TeleBot(os.getenv("TELEGRAM_TOKEN"))

# Handler'ları kayıt et
admin_panel.register_admin_handlers(bot)
admin_services.register_admin_service_handlers(bot)
payment_handler.register_payment_handlers(bot)

# --- GLOBAL DEĞİŞKENLER ---
AKTIF_TAKIPLER = {} 

def user_allowed(user_id, chat_id=None, call_id=None):
    admin_id = str(os.getenv("ADMIN_ID"))
    try: m_mode = database.get_maintenance_mode()
    except: return False
    
    if admin_id and str(user_id) == admin_id: return True
    
    if m_mode == 'on':
        if chat_id: bot.send_message(chat_id, "🚧 *Sistem Bakımda!* Lütfen daha sonra tekrar deneyin.", parse_mode="Markdown")
        if call_id: bot.answer_callback_query(call_id, "🚧 Sistem Bakımda!", show_alert=True)
        return False
        
    if database.is_user_banned(user_id):
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
    
    # Satır 4: [ Duyurular Gör ] (TAM SATIR)
    markup.row(
        types.InlineKeyboardButton(config.BUTONLAR["duyurular"], callback_data="menu_duyurular")
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

def live_track_sms(chat_id, message_id, act_id, fiyat, svc_name, api_cc, phone, user_id, service_id):
    """SMS kodunu sorgulayan ana döngü."""
    act_id = str(act_id)
    duration = 1200 
    start_time = time.time()
    last_ui_update = 0
    current_msg_id = message_id
    hata_sayisi = 0
    
    while time.time() - start_time < duration:
        track_info = AKTIF_TAKIPLER.get(act_id)
        if not isinstance(track_info, dict) or not track_info.get("status"):
            return 

        if int(time.time()) % 4 == 0:
            try:
                sonuc = grizzly_provider.get_sms(act_id)
                if isinstance(sonuc, str) and sonuc != "WAIT_CODE":
                    AKTIF_TAKIPLER[act_id] = {"status": False}
                    database.add_to_history(user_id, 2, svc_name, phone, fiyat, status="✅ BAŞARILI")
                    metin = f"✅ *SMS Kodu Geldi!*\n\n📱 Numara: `+{phone}`\n⚙️ Servis: {svc_name}\n🔑 *KOD:* `{sonuc}`"
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{service_id}"))
                    markup.add(types.InlineKeyboardButton(config.BUTONLAR["ana_menu"], callback_data="back_to_main"))
                    bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")
                    return
            except: pass

        if time.time() - last_ui_update >= 10:
            remaining = int(duration - (time.time() - start_time))
            sure = f"{remaining // 60:02d}:{remaining % 60:02d}"
            info = database.get_country_info(api_cc)
            metin = f"⏳ *SMS Bekleniyor...*\n\n📱 *Numaranız:* `+{phone}`\n🌍 Ülke: {info['flag']} {info['country_name']}\n⚙️ Servis: {svc_name}\n💰 Ücret: {fiyat} TL\n⏱️ Kalan Süre: *{sure}*"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("🔄 Kontrol Et", callback_data=f"check_sms_{act_id}"),
                       types.InlineKeyboardButton("❌ İptal Et", callback_data=f"cancel_sms_{act_id}_{fiyat}"))
            
            edit_res = safe_edit(chat_id, metin, markup, current_msg_id)
            if edit_res is None:
                hata_sayisi += 1
                if hata_sayisi >= 5: return
            else: hata_sayisi = 0
            last_ui_update = time.time()
        time.sleep(1)

    if AKTIF_TAKIPLER.get(act_id, {}).get("status"):
        AKTIF_TAKIPLER[act_id] = {"status": False}
        grizzly_provider.cancel_number(act_id)
        database.refund_balance(user_id, fiyat)
        database.add_to_history(user_id, 3, svc_name, phone, fiyat, status="❌ ZAMAN AŞIMI")
        metin = f"⏱️ *Süre Doldu!* \n\n`+{phone}` için kod gelmedi. Bakiyeniz iade edildi."
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton(config.BUTONLAR["ana_menu"], callback_data="back_to_main"))
        bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")

# --- BOT KOMUTLARI ---
@bot.message_handler(commands=['start'])
def start_komutu(message):
    user_id = message.from_user.id
    if not user_allowed(user_id, chat_id=message.chat.id): return
    database.add_user(user_id, message.from_user.username or "Yok")
    bot.clear_step_handler_by_chat_id(message.chat.id)
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    with open("veritas_sms_logo_yatay.png", "rb") as photo:
        bot.send_photo(message.chat.id, photo, caption=config.MESAJLAR["hosgeldin"].format(isim=message.from_user.first_name), reply_markup=ana_menu_klavyesi(user_id=user_id), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_yonetici(call):
    user_id, data = call.from_user.id, call.data
    admin_id = str(os.getenv("ADMIN_ID"))
    
    # MODÜLER PREFIX KONTROLÜ (Başka modülün işine karışma)
    MODULER_PREFIXES = ('menu_bakiye_yukle', 'yukle_sec_', 'checkpay_', 'qr_show_', 'admin_')
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

    if not user_allowed(user_id, call_id=call.id): return

    if data == "back_to_main":
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        safe_edit(call, config.MESAJLAR["hosgeldin"].format(isim=call.from_user.first_name), ana_menu_klavyesi(user_id=user_id))

    elif data == "menu_populer":
        safe_edit(call, "🌟 Popüler Servisler\n\nBu bölüm çok yakında aktif edilecektir!", geri_don())

    elif data == "menu_kupon_kullan":
        safe_edit(call, "🎟️ Kupon Kullanımı\n\nLütfen kupon kodunuzu bu sohbete yazın:", geri_don())
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        bot.register_next_step_handler(call.message, process_kupon_kullan_alim, photo_message_id=call.message.message_id)

    elif data.startswith("check_sms_"):
        bot.answer_callback_query(call.id, "⏳ Sistem arka planda numarayı tarıyor...", show_alert=False)

    elif data == "menu_numara_al":
        aktif = database.get_active_services()
        markup = types.InlineKeyboardMarkup(row_width=1)
        for srv in aktif: markup.add(types.InlineKeyboardButton(f"📱 {srv.upper()}", callback_data=f"select_srv_{srv}"))
        markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back_to_main"))
        safe_edit(call, config.MESAJLAR["servis_sec"], markup)

    elif data.startswith("select_srv_"):
        srv = data.replace("select_srv_", "")
        ulkeler = database.get_countries_for_service(srv)
        markup = types.InlineKeyboardMarkup(row_width=2); görülen = set()
        for u in ulkeler:
            if u['country_code'] not in görülen:
                görülen.add(u['country_code']); info = database.get_country_info(u['country_code'])
                markup.add(types.InlineKeyboardButton(f"{info['flag']} {u['country_name']}", callback_data=f"select_tier_{srv}_{u['country_code']}"))
        markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="menu_numara_al"))
        safe_edit(call, config.MESAJLAR["ulke_sec"], markup)

    elif data.startswith("select_tier_"):
        p = data.split("_"); srv, cc = p[2], p[3]
        kademeler = database.get_countries_for_service(srv)
        markup = types.InlineKeyboardMarkup(row_width=1); c = 1
        for u in kademeler:
            if u['country_code'] == cc:
                stok = grizzly_provider.get_stock(u['api_srv'], u['api_cc'], u['api_max_price'])
                markup.add(types.InlineKeyboardButton(f"⚡ Seçenek #{c}: {u['price']} TL [Stok: {stok}]", callback_data=f"buy_num_{u['id']}")); c += 1
        markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data=f"select_srv_{srv}"))
        safe_edit(call, f"💰 Kategori: {srv.upper()}", markup)

    elif data.startswith("buy_num_"):
        sid = int(data.replace("buy_num_", ""))
        svc = database.get_service_by_id(sid)
        if not svc: return
        active_count = sum(1 for v in AKTIF_TAKIPLER.values() if isinstance(v, dict) and v.get("status") and v.get("user_id") == user_id)
        if active_count >= 3:
            bot.answer_callback_query(call.id, "⚠️ Aynı anda max 3 aktif işlem yapılabilir!", show_alert=True); return
        if database.safe_decrease_balance(user_id, svc['price']):
            sonuc = grizzly_provider.get_number(svc['api_srv'], svc['api_cc'], max_price=svc['api_max_price'])
            if isinstance(sonuc, str):
                database.refund_balance(user_id, svc['price'])
                safe_edit(call, f"❌ Hata: {sonuc}", geri_don())
            else:
                act_id = str(sonuc["id"])
                AKTIF_TAKIPLER[act_id] = {"status": True, "user_id": user_id, "start": time.time()}
                threading.Thread(target=live_track_sms, args=(call.message.chat.id, call.message.message_id, act_id, svc['price'], svc['service_name'], svc['api_cc'], sonuc["phone"], user_id, sid), daemon=True).start()
        else: bot.answer_callback_query(call.id, "⚠️ Yetersiz bakiye!", show_alert=True)

    elif data.startswith("rebuy_"):
        sid = int(data.replace("rebuy_", ""))
        svc = database.get_service_by_id(sid)
        if not svc: return
        if database.safe_decrease_balance(user_id, svc['price']):
            bot.answer_callback_query(call.id, "🔄 Yeni talep gönderildi...")
            sonuc = grizzly_provider.get_number(svc['api_srv'], svc['api_cc'], max_price=svc['api_max_price'])
            if isinstance(sonuc, str):
                database.refund_balance(user_id, svc['price'])
                bot.send_message(call.message.chat.id, f"❌ Hata: {sonuc}")
            else:
                act_id = str(sonuc["id"])
                AKTIF_TAKIPLER[act_id] = {"status": True, "user_id": user_id, "start": time.time()}
                threading.Thread(target=live_track_sms, args=(call.message.chat.id, call.message.message_id, act_id, svc['price'], svc['service_name'], svc['api_cc'], sonuc["phone"], user_id, sid), daemon=True).start()
        else: bot.answer_callback_query(call.id, "⚠️ Yetersiz bakiye!", show_alert=True)

    elif data.startswith("cancel_sms_"):
        p = data.split("_"); aid = str(p[2]); f = float(p[3])
        if grizzly_provider.cancel_number(aid):
            AKTIF_TAKIPLER[aid] = {"status": False}
            database.refund_balance(user_id, f)
            database.add_to_history(user_id, 4, "Numara İptali", "Kullanıcı", f, status="❌ İPTAL")
            safe_edit(call, "❌ *İşlem İptal Edildi!* Ücret iade edildi.", geri_don())
        else: bot.answer_callback_query(call.id, "İptal başarısız!", show_alert=True)

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

    elif data == "menu_destek":
        if database.can_create_ticket(user_id):
            safe_edit(call, config.MESAJLAR["destek_istek"], geri_don())
            bot.clear_step_handler_by_chat_id(call.message.chat.id)
            bot.register_next_step_handler(call.message, process_support_ticket, photo_message_id=call.message.message_id)
        else: bot.answer_callback_query(call.id, config.MESAJLAR["destek_limit"], show_alert=True)

    elif data == "menu_bakiyem":
        safe_edit(call, f"💳 Bakiyeniz: {database.get_balance(user_id)} TL", geri_don())

    elif data == "menu_gecmisim":
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT action_type, service_name, fake_number, price, date, status FROM history WHERE user_id = %s ORDER BY id DESC LIMIT 8', (user_id,))
            islemler = cursor.fetchall()
            conn.close()
            
            if not islemler: 
                safe_edit(call, config.MESAJLAR["gecmis_bos"], geri_don())
                return

            metin = (
                "╔═══════════════════╗\n"
                "       💎 *İŞLEM GEÇMİŞİNİZ* 💎\n"
                "╚═══════════════════╝\n\n"
            )
            
            for idx, op in enumerate(islemler, 1):
                tarih = op['date'].strftime("%d.%m.%Y | %H:%M") if hasattr(op['date'], 'strftime') else str(op['date'])
                status = str(op.get('status', '✅ BAŞARILI'))
                if "BAŞARILI" in status: icon = "🟢"
                elif "İPTAL" in status: icon = "🟡"
                else: icon = "🔴"

                islem_kodu = op.get('action_type', 0)
                islem_adi = config.ISLEM_TIPLERI.get(islem_kodu, op['service_name'])

                metin += (
                    f"{icon} *#{idx} — {islem_adi}*\n"
                    f"└ 🛒 `{op['service_name']}` | ℹ️ `{op['fake_number']}`\n"
                    f"└ 💰 `{op['price']} TL` | 📅 {tarih}\n"
                    "───────────────────\n"
                )
            
            metin += "\n✨ _Son 8 işleminiz listelenmiştir._"
            safe_edit(call, metin, geri_don())
        except:
            safe_edit(call, "❌ İşlem geçmişi yüklenirken bir hata oluştu.", geri_don())

def process_support_ticket(message, photo_message_id):
    if not user_allowed(message.from_user.id, chat_id=message.chat.id): return
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    database.create_ticket(message.from_user.id, message.text)
    safe_edit(message.chat.id, config.MESAJLAR["destek_basarili"], geri_don(), photo_message_id)

def process_kupon_kullan_alim(message, photo_message_id):
    chat_id, user_id = message.chat.id, message.from_user.id
    if not user_allowed(user_id, chat_id=chat_id): return
    kod = message.text.strip().upper()
    try: bot.delete_message(chat_id, message.message_id)
    except: pass

    basarili, sonuc = database.redeem_coupon(user_id, kod)
    if basarili:
        database.add_to_history(user_id, 6, "Kupon", kod, -sonuc, status="✅ BAŞARILI")
        safe_edit(chat_id, f"🎉 Tebrikler!\n\n{kod} kuponunu başarıyla kullandınız.\nHesabınıza {sonuc} TL eklendi.", geri_don(), photo_message_id)
    else:
        safe_edit(chat_id, sonuc, geri_don(), photo_message_id)

if __name__ == "__main__":
    database.setup_database()
    print("====================================")
    print("🚀 Veritas SMS Botu Başlatıldı!")
    print("🛡️ Sistem Aktif ve Korumalı.")
    print("====================================")
    bot.infinity_polling()
