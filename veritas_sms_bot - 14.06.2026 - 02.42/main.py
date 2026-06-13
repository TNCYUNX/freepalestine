import telebot
from telebot import types
import os
import random
import io
import qrcode
import threading
import time
from dotenv import load_dotenv

import config
import database
import admin_panel
from providers import crypto_payment, sms_provider

load_dotenv()
bot = telebot.TeleBot(os.getenv("TELEGRAM_TOKEN"))
admin_panel.register_admin_handlers(bot)

# --- GLOBAL DEĞİŞKENLER & KİLİTLER ---
BEKLEYEN_ODEMELER = {}
AKTIF_TAKIPLER = {} 
odeme_lock = threading.Lock() # Race condition önleyici kilit

def user_allowed(user_id, chat_id=None, call_id=None):
    admin_id = os.getenv("ADMIN_ID")
    if admin_id and str(user_id) == admin_id:
        return True

    if database.get_maintenance_mode() == 'on':
        if chat_id: bot.send_message(chat_id, "🚧 *Sistem Bakımda!* Lütfen daha sonra tekrar deneyin.", parse_mode="Markdown")
        if call_id: bot.answer_callback_query(call_id, "🚧 Sistem Bakımda!", show_alert=True)
        return False
        
    if database.is_user_banned(user_id):
        if chat_id: bot.send_message(chat_id, "🚫 *Sistemden banlandınız!* İşlem yapamazsınız.", parse_mode="Markdown")
        if call_id: bot.answer_callback_query(call_id, "🚫 Sistemden banlandınız!", show_alert=True)
        return False
        
    return True

def ana_menu_klavyesi(user_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(config.BUTONLAR["numara_al"], callback_data="menu_numara_al"),
        types.InlineKeyboardButton("🌟 Popüler", callback_data="menu_populer")
    )
    markup.add(
        types.InlineKeyboardButton(config.BUTONLAR["bakiye_yukle"], callback_data="menu_bakiye_yukle"),
        types.InlineKeyboardButton(config.BUTONLAR["bakiyem"], callback_data="menu_bakiyem"),
        types.InlineKeyboardButton(config.BUTONLAR["gecmisim"], callback_data="menu_gecmisim"),
        types.InlineKeyboardButton(config.BUTONLAR["kupon_kullan"], callback_data="menu_kupon_kullan"),
        types.InlineKeyboardButton(config.BUTONLAR["duyurular"], callback_data="menu_duyurular")
    )
    markup.add(
        types.InlineKeyboardButton(config.BUTONLAR["destek"], callback_data="menu_destek"),
        types.InlineKeyboardButton(config.BUTONLAR["kurucu"], url=config.KURUCU_URL)
    )
    
    if user_id:
        admin_id = os.getenv("ADMIN_ID")
        if str(user_id) == str(admin_id):
            markup.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="open_admin_panel"))
            
    return markup

def geri_don():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(config.BUTONLAR["ana_menu"], callback_data="back_to_main"))
    return markup

def safe_edit(call_or_chat_id, text, markup=None, message_id=None):
    try:
        if hasattr(call_or_chat_id, 'message'):
            return bot.edit_message_caption(
                chat_id=call_or_chat_id.message.chat.id,
                message_id=call_or_chat_id.message.message_id,
                caption=text,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        else:
            return bot.edit_message_caption(
                chat_id=call_or_chat_id,
                message_id=message_id,
                caption=text,
                reply_markup=markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        err_msg = str(e).lower()
        if "message to edit not found" in err_msg or "message can't be edited" in err_msg:
            raise e
        return None

def live_track_sms(chat_id, message_id, act_id, fiyat, svc_name, api_cc, phone, user_id, service_id):
    """Arka planda SMS kodunu sorgular ve geri sayımı yönetir. Yeniden al butonunu barındırır."""
    duration = 300 
    start_time = time.time()
    last_ui_update = 0
    current_msg_id = message_id
    
    while time.time() - start_time < duration:
        if not AKTIF_TAKIPLER.get(act_id, False): return

        if int(time.time()) % 3 == 0:
            sonuc = sms_provider.get_sms(act_id)
            if isinstance(sonuc, str) and sonuc != "WAIT_CODE":
                AKTIF_TAKIPLER[act_id] = False
                database.add_to_history(user_id, f"{svc_name} ({api_cc})", phone, fiyat)
                metin = f"✅ *SMS Kodu Geldi!*\n\n📱 Numara: `+{phone}`\n⚙️ Servis: {svc_name}\n🔑 *KOD:* `{sonuc}`"
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{service_id}"))
                markup.add(types.InlineKeyboardButton(config.BUTONLAR["ana_menu"], callback_data="back_to_main"))
                try: safe_edit(chat_id, metin, markup, current_msg_id)
                except: bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")
                return

        if time.time() - last_ui_update >= 10:
            remaining = int(duration - (time.time() - start_time))
            sure = f"{remaining // 60:02d}:{remaining % 60:02d}"
            info = database.get_country_info(api_cc)
            metin = f"⏳ *SMS Bekleniyor...*\n\n📱 *Numaranız:* `+{phone}`\n🌍 Ülke: {info['flag']} {info['country_name']}\n⚙️ Servis: {svc_name}\n💰 Ücret: {fiyat} TL\n⏱️ Kalan Süre: *{sure}*"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("🔄 Kontrol Et", callback_data=f"check_sms_{act_id}"),
                       types.InlineKeyboardButton("❌ İptal Et", callback_data=f"cancel_sms_{act_id}_{fiyat}"))
            markup.add(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{service_id}"))
            try: safe_edit(chat_id, metin, markup, current_msg_id)
            except Exception as e:
                err_msg = str(e).lower()
                if "bot was blocked" in err_msg or "chat not found" in err_msg:
                    AKTIF_TAKIPLER[act_id] = False; return
                try:
                    with open("veritas_sms_logo_yatay.png", "rb") as photo:
                        new_msg = bot.send_photo(chat_id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
                        current_msg_id = new_msg.message_id
                except: pass
            last_ui_update = time.time()
        time.sleep(1)

    if AKTIF_TAKIPLER.get(act_id, False):
        AKTIF_TAKIPLER[act_id] = False
        sms_provider.cancel_number(act_id)
        database.refund_balance(user_id, fiyat)
        metin = f"⏱️ *Süre Doldu!* \n\n`+{phone}` için işlem iptal edildi ve `{fiyat}` TL iade edildi."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Tekrar Dene (Yeniden Al)", callback_data=f"rebuy_{service_id}"))
        markup.add(types.InlineKeyboardButton(config.BUTONLAR["ana_menu"], callback_data="back_to_main"))
        try: safe_edit(chat_id, metin, markup, current_msg_id)
        except: bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")

def global_payment_scanner():
    """
    Sistemi yormayan Merkezi Tarayıcı (Centralized Scanner).
    Tüm bekleyen ödemeleri tek bir döngüde, 15 saniyede bir TronGrid'i sorgulayarak eşleştirir.
    DDoS ve Rate-Limit sorunlarını kökten çözer.
    """
    while True:
        try:
            if BEKLEYEN_ODEMELER: # Sadece bekleyen ödeme varsa API'yi yor
                transfers = crypto_payment.get_valid_incoming_transfers()
                
                for tx in transfers:
                    with odeme_lock:
                        # Sözlüğün kopyası üzerinde döneriz ki eşleşme anında silebilelim
                        for dict_key, user_id in list(BEKLEYEN_ODEMELER.items()):
                            kur_tipi, bekleyen_miktar = dict_key.split("_")
                            bekleyen_miktar = float(bekleyen_miktar)
                            
                            # Eşleşme (Küsürat toleranslı)
                            if tx["type"] == kur_tipi and abs(tx["amount"] - bekleyen_miktar) < 0.001:
                                database.mark_tx_processed(tx["txid"]) # Çifte harcama (Replay) Kilidi
                                
                                kurlar = crypto_payment.get_live_rates()
                                tl_miktari = round(bekleyen_miktar * (kurlar["usdt"] if kur_tipi == "USDT" else kurlar["trx"]), 2)
                                
                                database.update_balance(user_id, tl_miktari)
                                database.add_to_history(user_id, "Bakiye Yukleme (Crypto)", "Kripto Otomatik Onay", -tl_miktari)
                                
                                del BEKLEYEN_ODEMELER[dict_key]
                                
                                try:
                                    bot.send_message(user_id, f"🎉 *Ödemeniz Otomatik Algılandı!*\n\n✅ Blokzincir onayı tamamlandı.\n💰 *Hesabınıza Eklenen:* `{tl_miktari}` TL\n\n🤖 Veritas SMS'i tercih ettiğiniz için teşekkür ederiz!", parse_mode="Markdown")
                                except: pass
                                
                                break # Bu işlem kullanıldı, sonraki işleme (tx) geç
        except Exception as e:
            print(f"Global Payment Scanner Hatası: {e}")
            
        time.sleep(15) # 15 saniyede bir tarama (Rate Limit dostu)

# --- BOT KOMUTLARI VE İŞLEYİCİLERİ ---

@bot.message_handler(commands=['id'])
def id_komutu(message):
    user_id = message.from_user.id
    bot.reply_to(message, f"🆔 *Telegram ID Numaranız:* `{user_id}`", parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start_komutu(message):
    user_id = message.from_user.id
    isim = message.from_user.first_name
    
    if not user_allowed(user_id, chat_id=message.chat.id):
        return
        
    database.add_user(user_id, message.from_user.username or "Yok")
    
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

    with open("veritas_sms_logo_yatay.png", "rb") as photo:
        bot.send_photo(
            message.chat.id, photo,
            caption=config.MESAJLAR["hosgeldin"].format(isim=isim),
            reply_markup=ana_menu_klavyesi(user_id=user_id),
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: True)
def callback_yonetici(call):
    user_id, data = call.from_user.id, call.data
    if not user_allowed(user_id, call_id=call.id): return

    if data == "back_to_main":
        safe_edit(call, config.MESAJLAR["hosgeldin"].format(isim=call.from_user.first_name), ana_menu_klavyesi(user_id=user_id))

    elif data == "open_admin_panel":
        if str(user_id) != os.getenv("ADMIN_ID"): return
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("📊 İstatistikler", callback_data="admin_stats"),
                   types.InlineKeyboardButton("👥 Kullanıcılar", callback_data="admin_user_list"),
                   types.InlineKeyboardButton("🎟️ Kuponlar", callback_data="admin_create_coupon"),
                   types.InlineKeyboardButton("🚫 Ban/Kaldır", callback_data="admin_ban_menu"),
                   types.InlineKeyboardButton("💰 Bakiye Ekle", callback_data="admin_add_balance"),
                   types.InlineKeyboardButton("📢 Duyuru Yap", callback_data="admin_broadcast"),
                   types.InlineKeyboardButton("🚀 Servis Yönetimi", callback_data="admin_menu_fiyatlar"),
                   types.InlineKeyboardButton("⚙️ Sistem", callback_data="admin_system_control"),
                   types.InlineKeyboardButton("🎫 Destek", callback_data="admin_tickets"),
                   types.InlineKeyboardButton("🐻 Grizzly", callback_data="admin_grizzly"),
                   types.InlineKeyboardButton("❌ Kapat", callback_data="back_to_main"))
        safe_edit(call, "🛡️ *Yönetim Paneli*", markup)

    elif data == "menu_populer":
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT s.id, s.service_name, s.country_code, s.price, s.api_srv, s.api_cc, s.api_max_price, COUNT(h.id) as kullanim FROM services s LEFT JOIN history h ON s.service_name = h.service_name AND s.country_code = SUBSTRING_INDEX(h.service_name, '(', -1) WHERE s.is_active = TRUE GROUP BY s.id ORDER BY kullanim DESC, s.id ASC LIMIT 5")
            populerler = cursor.fetchall(); conn.close()
            markup = types.InlineKeyboardMarkup(row_width=1)
            if not populerler:
                safe_edit(call, "⚠️ Popüler servis bulunamadı.", geri_don()); return
            for op in populerler:
                stok = sms_provider.get_stock(op['api_srv'], op['api_cc'], op['api_max_price'])
                info = database.get_country_info(op['country_code'])
                alev = "🔥" if op['kullanim'] > 0 else "⭐"
                btn_text = f"{alev} {op['service_name'].upper()} | {info['flag']} {info['country_name']} - {op['price']} TL [📦 {stok}]"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"buy_num_{op['id']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back_to_main"))
            safe_edit(call, "🌟 *Popüler Numaralar*", markup)
        except: bot.answer_callback_query(call.id, "Hata oluştu.")

    elif data == "menu_numara_al":
        aktif = database.get_active_services()
        markup = types.InlineKeyboardMarkup(row_width=1)
        for srv in aktif: markup.add(types.InlineKeyboardButton(f"📱 {srv}", callback_data=f"select_srv_{srv}"))
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
        info = database.get_country_info(cc)
        markup = types.InlineKeyboardMarkup(row_width=1); c = 1
        for u in kademeler:
            if u['country_code'] == cc:
                stok = sms_provider.get_stock(u['api_srv'], u['api_cc'], u['api_max_price'])
                markup.add(types.InlineKeyboardButton(f"⚡ Seçenek #{c}: {u['price']} TL [🔥 {stok}]", callback_data=f"buy_num_{u['id']}")); c += 1
        markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data=f"select_srv_{srv}"))
        safe_edit(call, f"💰 {info['flag']} {info['country_name']} - {srv.upper()}", markup)

    elif data.startswith("buy_num_"):
        sid = int(data.replace("buy_num_", ""))
        svc = database.get_service_by_id(sid)
        if not svc or not svc['is_active']: return
        if database.safe_decrease_balance(user_id, svc['price']):
            sonuc = sms_provider.get_number(svc['api_srv'], svc['api_cc'], max_price=svc['api_max_price'])
            if isinstance(sonuc, str):
                database.refund_balance(user_id, svc['price'])
                safe_edit(call, f"❌ Hata: {sonuc}", geri_don())
            else:
                act_id, phone = sonuc["id"], sonuc["phone"]
                AKTIF_TAKIPLER[act_id] = True
                threading.Thread(target=live_track_sms, args=(call.message.chat.id, call.message.message_id, act_id, svc['price'], svc['service_name'], svc['api_cc'], phone, user_id, sid), daemon=True).start()
                metin = f"⏳ *SMS Bekleniyor...*\n\n📱 `+{phone}`\n⏱️ Kalan: *05:00*"
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(types.InlineKeyboardButton("🔄 Kontrol", callback_data=f"check_sms_{act_id}"),
                           types.InlineKeyboardButton("❌ İptal", callback_data=f"cancel_sms_{act_id}_{svc['price']}"))
                markup.add(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{sid}"))
                safe_edit(call, metin, markup)
        else: bot.answer_callback_query(call.id, "⚠️ Yetersiz bakiye!", show_alert=True)

    elif data.startswith("rebuy_"):
        sid = int(data.replace("rebuy_", ""))
        svc = database.get_service_by_id(sid)
        if not svc or not svc['is_active']: return
        if database.safe_decrease_balance(user_id, svc['price']):
            bot.answer_callback_query(call.id, "🔄 Yeni numara talebi gönderildi...", show_alert=False)
            sonuc = sms_provider.get_number(svc['api_srv'], svc['api_cc'], max_price=svc['api_max_price'])
            if isinstance(sonuc, str):
                database.refund_balance(user_id, svc['price'])
                bot.send_message(call.message.chat.id, f"❌ *Yeni Sipariş Başarısız!*\n\n{sonuc}\nBakiyeniz iade edildi.", parse_mode="Markdown")
            else:
                act_id, phone = sonuc["id"], sonuc["phone"]
                AKTIF_TAKIPLER[act_id] = True
                metin = f"⏳ *YENİ SMS Bekleniyor...*\n\n📱 *Numaranız:* `+{phone}`\n⚙️ Servis: {svc['service_name']}\n💰 Ücret: {svc['price']} TL\n⏱️ Kalan Süre: *05:00*"
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(types.InlineKeyboardButton("🔄 Kontrol Et", callback_data=f"check_sms_{act_id}"),
                           types.InlineKeyboardButton("❌ İptal Et", callback_data=f"cancel_sms_{act_id}_{svc['price']}"))
                markup.add(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{sid}"))
                try:
                    with open("veritas_sms_logo_yatay.png", "rb") as photo:
                        new_msg = bot.send_photo(call.message.chat.id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
                        new_msg_id = new_msg.message_id
                except:
                    new_msg = bot.send_message(call.message.chat.id, metin, reply_markup=markup, parse_mode="Markdown")
                    new_msg_id = new_msg.message_id
                threading.Thread(target=live_track_sms, args=(call.message.chat.id, new_msg_id, act_id, svc['price'], svc['service_name'], svc['api_cc'], phone, user_id, sid), daemon=True).start()
        else: bot.answer_callback_query(call.id, "⚠️ Yetersiz bakiye!", show_alert=True)

    elif data.startswith("check_sms_"):
        aid = data.replace("check_sms_", "")
        res = sms_provider.get_sms(aid)
        if res: bot.answer_callback_query(call.id, f"✅ Kod: {res}", show_alert=True)
        else: bot.answer_callback_query(call.id, "⏳ Bekleniyor...")

    elif data.startswith("cancel_sms_"):
        p = data.split("_"); aid, f = p[2], float(p[3])
        if sms_provider.cancel_number(aid):
            AKTIF_TAKIPLER[aid] = False; database.refund_balance(user_id, f)
            safe_edit(call, "❌ *İşlem İptal Edildi!*\n\nNumara alma işlemi sizin tarafınızdan iptal edildi. Ücretiniz bakiyenize iade edilmiştir.", geri_don())
            bot.answer_callback_query(call.id, "İşlem iptal edildi ve bakiye iade edildi.", show_alert=True)
        else: bot.answer_callback_query(call.id, "❌ İptal edilemedi, kod gelmiş olabilir!", show_alert=True)

    elif data == "menu_bakiye_yukle":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🟢 USDT", callback_data="yukle_sec_USDT"),
                   types.InlineKeyboardButton("🔴 TRX", callback_data="yukle_sec_TRX"))
        markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back_to_main"))
        safe_edit(call, "💰 Para birimi seçin:", markup)

    elif data.startswith("yukle_sec_"):
        kur = data.split("_")[2]
        safe_edit(call, f"💰 Miktar girin ({kur}):", geri_don())
        bot.register_next_step_handler(call.message, bakiye_miktari_al, photo_message_id=call.message.message_id, kur_tipi=kur)

    elif data.startswith("qr_goster_"):
        p = data.split('_'); kt, amt = p[2], p[3]
        cuz = os.getenv("TRON_WALLET_ADDRESS", "TYgYxUPzVWXW1ix9MsPUDEH4LP2Uy8UAhX")
        qr = qrcode.make(cuz); bio = io.BytesIO(); bio.name = 'qr.png'; qr.save(bio, 'PNG'); bio.seek(0)
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("🗑️ Kapat", callback_data="qr_kapat"))
        bot.send_photo(call.message.chat.id, bio, caption=f"💰 {amt} {kt}\n`{cuz}`", reply_markup=markup, parse_mode="Markdown")

    elif data == "qr_kapat":
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass

    elif data.startswith("check_pay_"):
        p = data.split("_"); kt, amt = p[2], float(p[3]); dk = f"{kt}_{amt}"
        if dk in BEKLEYEN_ODEMELER:
            if (crypto_payment.check_usdt_payment(amt) if kt == "USDT" else crypto_payment.check_trx_payment(amt)):
                with odeme_lock: del BEKLEYEN_ODEMELER[dk]
                k = crypto_payment.get_live_rates(); tl = round(amt * (k["usdt"] if kt == "USDT" else k["trx"]), 2)
                database.update_balance(user_id, tl); database.add_to_history(user_id, "Bakiye Yukleme (Crypto)", "Kripto Onay", -tl)
                safe_edit(call, f"✅ `{tl}` TL yüklendi.", geri_don())
            else: bot.answer_callback_query(call.id, "Onaylanmadı.")

    elif data == "menu_bakiyem":
        safe_edit(call, f"💳 Bakiyeniz: {database.get_balance(user_id)} TL", geri_don())

    elif data == "menu_gecmisim":
        bot.answer_callback_query(call.id)
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT service_name, fake_number, price, date FROM history WHERE user_id = %s ORDER BY id DESC LIMIT 10', (user_id,))
            islemler = cursor.fetchall()
            conn.close()
            
            if not islemler: 
                safe_edit(call, config.MESAJLAR["gecmis_bos"], geri_don())
                return
                
            metin = "📜 *RESMİ HESAP EKSTRESİ / GEÇMİŞİNİZ*\n"
            metin += "==================================\n\n"
            
            for idx, op in enumerate(islemler, 1):
                raw_srv = str(op['service_name'])
                numara = str(op['fake_number']) if op['fake_number'] else "Mevcut Değil"
                harcanan = float(op['price'])
                tarih = op['date'].strftime("%d.%m.%Y %H:%M") if hasattr(op['date'], 'strftime') else str(op['date'])
                
                ülke_adi_gösterim = "Bilinmeyen Ülke"
                bayrak = "🌍"
                temiz_srv_ismi = raw_srv
                
                if "(" in raw_srv and ")" in raw_srv:
                    try:
                        temiz_srv_ismi = raw_srv.split("(")[0].strip()
                        grizzly_cc = raw_srv.split("(")[1].replace(")", "").strip()
                        info = database.get_country_info(grizzly_cc)
                        ülke_adi_gösterim = info.get('country_name', grizzly_cc)
                        bayrak = info.get('flag', "🌍")
                    except: pass
                else:
                    ülke_adi_gösterim = "Sistem Tanımlı"
                
                alan_kodu = ""
                if numara.startswith("57"): alan_kodu = " (+57)"
                elif numara.startswith("44"): alan_kodu = " (+44)"
                elif numara.startswith("90"): alan_kodu = " (+90)"
                elif numara.startswith("1"): alan_kodu = " (+1)"
                
                if harcanan < 0:
                    pozitif_yuklenen = abs(harcanan)
                    metin += f"📥 *İşlem #{idx}* | _YÜKLEME_ | `{tarih}`\n"
                    metin += f"💳 Ödeme Tipi: *Kripto Para / Kupon*\n"
                    metin += f"💵 Hesaba Tanımlanan: *+{pozitif_yuklenen:.2f} TL*\n"
                    metin += f"📊 Durum: *✅ BAŞARILI (Onaylandı)*\n"
                else:
                    metin += f"📱 *İşlem #{idx}* | _NUMARA ALIMI_ | `{tarih}`\n"
                    metin += f"⚙️ Platform: *{temiz_srv_ismi.upper()}*\n"
                    metin += f"🌍 Hedef Ülke: {bayrak} *{ülke_adi_gösterim}*{alan_kodu}\n"
                    metin += f"🔢 Hat No: `+{numara}`\n"
                    metin += f"💸 İşlem Tutarı: *{harcanan:.2f} TL*\n"
                    metin += f"📊 Durum: *✅ BAŞARILI (SMS Alındı)*\n"
                
                metin += "----------------------------------\n"
                
            metin += f"\n💳 *Mevcut Güncel Bakiyeniz:* `{database.get_balance(user_id):.2f} TL`"
            safe_edit(call, metin, geri_don())
        except Exception as e:
            print(f"Hesap Ekstresi Hatası: {e}")
            safe_edit(call, "❌ *Geçmiş hesap hareketleriniz dökülürken sistemsel bir hata oluştu.*", geri_don())

    elif data == "menu_duyurular":
        d = database.get_latest_announcements()
        if not d: safe_edit(call, "📢 Duyuru yok.", geri_don())
        else:
            m = "📢 *Duyurular*\n\n"
            for i in d: m += f"📅 {i['date'].strftime('%d.%m %H:%M')}\n💬 {i['message']}\n\n"
            safe_edit(call, m, geri_don())

    elif data == "menu_kupon_kullan":
        safe_edit(call, "Kupon kodunu yazın:", geri_don())
        bot.register_next_step_handler(call.message, handle_coupon_redemption, photo_message_id=call.message.message_id)

    elif data == "menu_destek":
        if database.can_create_ticket(user_id):
            safe_edit(call, config.MESAJLAR["destek_istek"], geri_don())
            bot.register_next_step_handler(call.message, process_support_ticket, photo_message_id=call.message.message_id)
        else: bot.answer_callback_query(call.id, config.MESAJLAR["destek_limit"], show_alert=True)

# --- HANDLERS ---
def bakiye_miktari_al(message, photo_message_id, kur_tipi):
    chat_id, user_id = message.chat.id, message.from_user.id
    if not user_allowed(user_id, chat_id=chat_id): return
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    try:
        amt = float(message.text.strip().replace(',', '.'))
        min_l = config.MIN_YUKLEME_LIMITI if kur_tipi == "USDT" else config.MIN_YUKLEME_TRX
        if amt < min_l or amt > 9999: raise ValueError()
        final = round(amt + random.uniform(0.01, 0.99), 2)
        with odeme_lock:
            while f"{kur_tipi}_{final}" in BEKLEYEN_ODEMELER: final = round(amt + random.uniform(0.01, 0.99), 2)
            BEKLEYEN_ODEMELER[f"{kur_tipi}_{final}"] = user_id
        k = crypto_payment.get_live_rates(); tl = round(amt * (k["usdt"] if kur_tipi == "USDT" else k["trx"]), 2)
        c = os.getenv("TRON_WALLET_ADDRESS", "TYgYxUPzVWXW1ix9MsPUDEH4LP2Uy8UAhX")
        m = config.MESAJLAR["fatura_arayuzu"].format(base_amount=amt, final_amount=final, kur_tipi=kur_tipi, cuzdan=c, tl_miktari=tl, kur_usdt=k['usdt'], kur_trx=k['trx'])
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📱 QR", callback_data=f"qr_goster_{kur_tipi}_{final}"),
                   types.InlineKeyboardButton("🔄 Kontrol", callback_data=f"check_pay_{kur_tipi}_{final}"),
                   types.InlineKeyboardButton("🔙 Menü", callback_data="back_to_main"))
        safe_edit(chat_id, m, markup, photo_message_id)
        # Bireysel thread kaldırıldı, global_payment_scanner merkezi takip yapıyor.
    except: safe_edit(chat_id, "Geçersiz miktar.", geri_don(), photo_message_id)

def handle_coupon_redemption(message, photo_message_id):
    if not user_allowed(message.from_user.id, chat_id=message.chat.id): return
    kod = message.text.strip().upper(); cleanup_msg(message)
    res, val = database.redeem_coupon(message.from_user.id, kod)
    safe_edit(message.chat.id, f"✅ Yüklendi: {val} TL" if res else val, geri_don(), photo_message_id)

def process_support_ticket(message, photo_message_id):
    if not user_allowed(message.from_user.id, chat_id=message.chat.id): return
    cleanup_msg(message); database.create_ticket(message.from_user.id, message.text)
    safe_edit(message.chat.id, config.MESAJLAR["destek_basarili"], geri_don(), photo_message_id)
    admin_id = os.getenv("ADMIN_ID")
    if admin_id:
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("💬 Yanıtla", callback_data=f"admin_reply_ticket_{message.from_user.id}"))
        bot.send_message(admin_id, f"🎟️ *Yeni Destek*\n👤 @{message.from_user.username}\n💬 {message.text}", reply_markup=markup, parse_mode="Markdown")

def cleanup_msg(m):
    try: bot.delete_message(m.chat.id, m.message_id)
    except: pass

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def mesaji_temizle(m): cleanup_msg(m)

if __name__ == "__main__":
    database.setup_database()
    print("Merkezi Kripto Tarayıcı (Global Scanner) Başlatılıyor...")
    threading.Thread(target=global_payment_scanner, daemon=True).start()
    print("Veritas SMS Botu Başlatılıyor...")
    bot.infinity_polling()
