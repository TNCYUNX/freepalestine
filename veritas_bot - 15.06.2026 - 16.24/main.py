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
from providers.security_manager import security

load_dotenv()
bot = telebot.TeleBot(os.getenv("TELEGRAM_TOKEN"))

# Handler'ları kayıt et
admin_panel.register_admin_handlers(bot)
admin_services.register_admin_service_handlers(bot)
payment_handler.register_payment_handlers(bot)

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
AKTIF_TAKIPLER = {} 

def user_allowed(user_id, chat_id=None, call_id=None):
    # 1. Grup Whitelist Kontrolü (Botun illegal gruplara eklenmesini önler)
    if chat_id and not security.is_group_allowed(chat_type="group" if chat_id < 0 else "private", chat_id=chat_id):
        return False
        
    # 2. Spam / Rate Limit Kontrolü (Komut ve Mesaj Spamını Engeller)
    status, msg, ban_info = security.check_rate_limit(user_id)
    if status == 'ban':
        notify_admin_of_ban(user_id, ban_info)
        if call_id: bot.answer_callback_query(call_id, msg, show_alert=True)
        elif chat_id: bot.send_message(chat_id, msg)
        return False
    elif status == 'warn':
        if call_id: bot.answer_callback_query(call_id, msg, show_alert=True)
        elif chat_id: bot.send_message(chat_id, msg)
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

def live_track_sms(chat_id, message_id, act_id, fiyat, svc_name, api_cc, phone, user_id, service_id, api_srv=None):
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
                    
                    # Ülke bilgilerini ve bayrağını çek, telefon ve gelen kodu tek bir string olarak birleştir
                    try:
                        info = database.get_country_info(api_cc)
                        ulke_numara_kod = f"{info['flag']} {info['country_name']} (+{phone}) | 🔑 Kod: `{sonuc}`"
                    except:
                        ulke_numara_kod = f"🌍 (+{phone}) | 🔑 Kod: `{sonuc}`"

                    # Log kaydını servisin yalın adı ve service_code ile at
                    database.add_to_history(user_id, 2, svc_name.capitalize(), ulke_numara_kod, fiyat, status="✅ BAŞARILI", service_code=api_srv)
                    
                    metin = f"✅ *SMS Kodu Geldi!*\n\n📱 Numara: `+{phone}`\n⚙️ Servis: {svc_name}\n🔑 *KOD:* `{sonuc}`"
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{service_id}"))
                    markup.add(types.InlineKeyboardButton(config.BUTONLAR["ana_menu"], callback_data="back_to_main"))
                    
                    try:
                        with open("veritas_sms_logo_yatay.png", "rb") as photo:
                            bot.send_photo(chat_id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
                    except:
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
        
        try:
            with open("veritas_sms_logo_yatay.png", "rb") as photo:
                bot.send_photo(chat_id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
        except:
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
    
    # Callback / Buton Spamı Koruması
    status, msg, ban_info = security.check_rate_limit(user_id)
    if status == 'ban':
        notify_admin_of_ban(user_id, ban_info)
        try: bot.answer_callback_query(call.id, msg, show_alert=True)
        except: pass
        return
    elif status == 'banned_cache':
        try: bot.answer_callback_query(call.id, msg, show_alert=True)
        except: pass
        return
    elif status == 'warn':
        try: bot.answer_callback_query(call.id, msg, show_alert=True)
        except: pass
        return

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
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Veritabanında action_type = 2 (Başarılı Alım) olan ve service_code'u belli olanları çek
            sorgu = """
                SELECT service_code, service_name, COUNT(*) as alim_sayisi 
                FROM history 
                WHERE action_type = 2 AND service_code IS NOT NULL
                GROUP BY service_code, service_name 
                ORDER BY alim_sayisi DESC 
                LIMIT 5
            """
            cursor.execute(sorgu)
            populer_listesi = cursor.fetchall()
            conn.close()
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            if not populer_listesi:
                # Eğer henüz hiç başarılı işlem yoksa, sistemde aktif olan servislerden ilk 5 tanesini göster
                aktifler = database.get_active_services()[:5]
                for srv in aktifler:
                    markup.add(types.InlineKeyboardButton(f"🔥 {srv.upper()}", callback_data=f"select_srv_{srv}"))
                metin = "🌟 *Popüler Servisler*\n\nHenüz yeterli işlem geçmişi oluşmadığı için genel servisler listelenmiştir. Satın alım yapıldıkça bu panel otomatik güncellenir!"
            else:
                # En çok işlem gören servisleri dinamik buton olarak diz
                for srv in populer_listesi:
                    srv_code = srv['service_code']
                    srv_name = srv['service_name']
                    # Butona basıldığında isme değil, güvenli API KODUNA (srv_code) göre yönlendir
                    markup.add(types.InlineKeyboardButton(f"🔥 {srv_name.upper()} ({srv['alim_sayisi']} Kez Alındı)", callback_data=f"select_srv_{srv_code}"))
                    
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back_to_main"))
            safe_edit(call, "🌟 *EN ÇOK TERCİH EDİLEN POPÜLER SERVİSLER*\n\nKullanıcıların en çok kod talep ettiği servisler canlı olarak aşağıda listelenmiştir. Doğrudan numara alma aşamasına geçmek için birine tıklayabilirsiniz:", markup)
        except Exception as e:
            safe_edit(call, "❌ Popüler servisler yüklenirken bir hata oluştu.", geri_don())

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
        mevcut_bakiye = database.get_balance(user_id)
        safe_edit(call, f"💳 *Güncel Bakiyeniz:* `{mevcut_bakiye} TL`", geri_don())

    elif data == "menu_gecmisim" or data.startswith("historypage_"):
        current_page = 1
        if data.startswith("historypage_"):
            current_page = int(data.split("_")[1])
            
        limit = 5
        offset = (current_page - 1) * limit
        
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

if __name__ == "__main__":
    database.setup_database()
    print("====================================")
    print("🚀 Veritas SMS Botu Başlatıldı!")
    print("🛡️ Sistem Aktif ve Korumalı.")
    print("====================================")
    bot.infinity_polling()
