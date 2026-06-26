# -*- coding: utf-8 -*-
import telebot
from telebot import types
import os
import threading
import time
import database
import config
from providers import grizzly_provider, tigersms_provider
from handlers.payment_handler import safe_payment_edit

# --- GLOBAL AKTİF TAKİPLER LİSTESİ ---
AKTIF_TAKIPLER = {}
tracking_lock = threading.Lock()

def register_number_handlers(bot):
    """Numara kiralama, katmanlı menüler ve eşzamanlı siber zırhlı takip mekanizması."""

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('menu_numara_al', 'menu_populer', 'select_srv_', 'select_tier_', 'buy_num_', 'rebuy_', 'cancel_sms_', 'check_sms_', 'leave_tracking_menu')))
    def number_callback_router(call):
        from main import user_allowed, ana_menu_klavyesi, geri_don, safe_edit
        user_id, data = call.from_user.id, call.data
        chat_id, msg_id = call.message.chat.id, call.message.message_id

        if not user_allowed(user_id, call_id=call.id): return

        if data == "leave_tracking_menu":
            bot.answer_callback_query(call.id, "⬇️ Ana menü aşağıya gönderildi.", show_alert=False)
            try:
                with open("veritas_sms_logo_yatay.png", "rb") as photo:
                    bot.send_photo(chat_id, photo, caption=config.MESAJLAR["hosgeldin"].format(isim=call.from_user.first_name), reply_markup=ana_menu_klavyesi(user_id=user_id), parse_mode="Markdown")
            except:
                bot.send_message(chat_id, config.MESAJLAR["hosgeldin"].format(isim=call.from_user.first_name), reply_markup=ana_menu_klavyesi(user_id=user_id), parse_mode="Markdown")
            return

        if data == "menu_numara_al":
            aktif = database.get_active_services()
            markup = types.InlineKeyboardMarkup(row_width=1)
            for srv in aktif: 
                markup.add(types.InlineKeyboardButton(f"📱 {srv.upper()}", callback_data=f"select_srv_{srv}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back_to_main"))
            safe_edit(call, config.MESAJLAR["servis_sec"], markup)

        elif data.startswith("select_srv_"):
            srv = data.replace("select_srv_", "")
            ulkeler = database.get_countries_for_service(srv)
            markup = types.InlineKeyboardMarkup(row_width=2)
            görülen = set()
            for u in ulkeler:
                if u['country_code'] not in görülen:
                    görülen.add(u['country_code'])
                    info = database.get_country_info(u['country_code'])
                    markup.add(types.InlineKeyboardButton(f"{info['flag']} {u['country_name']}", callback_data=f"select_tier_{srv}_{u['country_code']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="menu_numara_al"))
            safe_edit(call, config.MESAJLAR["ulke_sec"], markup)

        elif data.startswith("select_tier_"):
            p = data.split("_")
            srv, cc = p[2], p[3]
            kademeler = database.get_countries_for_service(srv)
            
            c_info = database.get_country_info(cc)
            country_full_name = c_info.get('country_name', cc)
            country_flag = c_info.get('flag', '🌍')
            human_service_name = config.GRIZZLY_SERVICES.get(srv, srv.upper())

            markup = types.InlineKeyboardMarkup(row_width=1)
            for u in kademeler:
                if u['country_code'] == cc:
                    prov = int(u.get('provider', 1))
                    if prov == 1:
                        stok = grizzly_provider.get_stock(u['api_srv'], u['api_cc'], u['api_max_price'])
                        prov_label = "🔥 Sunucu 1"
                    else:
                        stok = tigersms_provider.get_stock(u['api_srv'], u['api_cc'], u['api_max_price'])
                        prov_label = "⚡ Sunucu 2"
                        
                    button_text = f"{country_flag} {country_full_name} — {u['price']} TL [📦 Stok: {stok}] ({prov_label})"
                    markup.add(types.InlineKeyboardButton(button_text, callback_data=f"buy_num_{u['id']}"))
                    
            markup.add(types.InlineKeyboardButton("🔙 Ülke Seçimine Dön", callback_data=f"select_srv_{srv}"))
            
            rapor_metni = (
                "🛒 *Numara Satın Alma Paneli*\n\n"
                f"📱 *Platform:* `{human_service_name}`\n"
                f"🌍 *Seçilen Ülke:* {country_flag} *{country_full_name}*\n\n"
                "💡 Lütfen kullanmak istediğiniz bakiye seçeneğine tıklayın. Numaranız saniyeler içinde üretilecektir."
            )
            safe_edit(call, rapor_metni, markup)

        elif data.startswith("buy_num_") or data.startswith("rebuy_"):
            # INDEX ERROR SİBER ÇÖZÜMÜ: Veri formatına göre id yakalama
            if data.startswith("buy_num_"):
                sid = int(data.split("_")[2])
            else:
                sid = int(data.split("_")[1])
                
            svc = database.get_service_by_id(sid)
            if not svc: return

            with tracking_lock:
                active_count = sum(1 for v in AKTIF_TAKIPLER.values() if isinstance(v, dict) and v.get("status") is True and v.get("user_id") == user_id)
            
            if active_count >= 3:
                bot.answer_callback_query(call.id, "⚠️ Zaafiyet Önleyici: Aynı anda en fazla 3 aktif numara bekletebilirsiniz!", show_alert=True)
                return

            if database.safe_decrease_balance(user_id, svc['price']):
                if data.startswith("rebuy_"):
                    bot.answer_callback_query(call.id, "🔄 Yeni bağımsız numara siparişi veriliyor...")

                prov = int(svc.get('provider', 1))
                if prov == 1:
                    sonuc = grizzly_provider.get_number(svc['api_srv'], svc['api_cc'], max_price=svc['api_max_price'])
                else:
                    sonuc = tigersms_provider.get_number(svc['api_srv'], svc['api_cc'], max_price=svc['api_max_price'])
                    
                if isinstance(sonuc, str):
                    database.refund_balance(user_id, svc['price'])
                    if data.startswith("rebuy_"):
                        bot.send_message(chat_id, f"❌ Hata: {sonuc}")
                    else:
                        safe_edit(call, f"❌ Hata: {sonuc}", geri_don())
                else:
                    act_id = str(sonuc["id"])
                    with tracking_lock:
                        AKTIF_TAKIPLER[act_id] = {"status": True, "user_id": user_id, "start": time.time()}
                    
                    if data.startswith("buy_num_"):
                        try: bot.delete_message(chat_id, msg_id)
                        except: pass
                    
                    info = database.get_country_info(svc['api_cc'])
                    prov_name = "🔥 Sunucu 1" if prov == 1 else "⚡ Sunucu 2"
                    metin = f"⏳ *SMS Bekleniyor...*\n\n📱 *Numaranız:* `+{sonuc['phone']}`\n🌍 Ülke: {info['flag']} {info['country_name']}\n⚙️ Servis: {svc['service_name']}\n🖥️ Kaynak: {prov_name}\n💰 Ücret: {svc['price']} TL\n⏱️ Kalan Süre: *20:00*"
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.row(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{sid}"),
                               types.InlineKeyboardButton("❌ İptal Et", callback_data=f"cancel_sms_{act_id}_{svc['price']}_{prov}"))
                    # ANA MENÜ YÖNLENDİRMESİ
                    markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
                    
                    # LOGOLU YENİ MESAJ
                    try:
                        with open("veritas_sms_logo_yatay.png", "rb") as photo:
                            new_msg = bot.send_photo(chat_id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
                    except:
                        new_msg = bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")
                    
                    threading.Thread(target=live_track_sms, args=(bot, chat_id, new_msg.message_id, act_id, svc['price'], svc['service_name'], svc['api_cc'], sonuc["phone"], user_id, sid, svc['api_srv'], prov), daemon=True).start()
            else: 
                bot.answer_callback_query(call.id, "⚠️ Yetersiz bakiye!", show_alert=True)

        elif data.startswith("cancel_sms_"):
            p = data.split("_"); aid = str(p[2]); f = float(p[3]); prov = int(p[4]) if len(p) > 4 else 1
            
            with tracking_lock:
                track_info = AKTIF_TAKIPLER.get(aid)
                
            if track_info and isinstance(track_info, dict) and "start" in track_info:
                gecen_sure = time.time() - track_info["start"]
                if gecen_sure < 300:
                    kalan_sn = int(300 - gecen_sure)
                    kalan_dk = kalan_sn // 60
                    kalan_sn_kalan = kalan_sn % 60
                    
                    bot.answer_callback_query(
                        call.id, 
                        f"⚠️ Güvenlik Kilidi: Numarayı iptal edebilmek için en az 5 dakika beklemeniz gerekmektedir!\n\n⏳ Kalan Süre: {kalan_dk:02d}:{kalan_sn_kalan:02d}", 
                        show_alert=True
                    )
                    return

            success = grizzly_provider.cancel_number(aid) if prov == 1 else tigersms_provider.cancel_number(aid)
                
            if success:
                with tracking_lock:
                    if aid in AKTIF_TAKIPLER: AKTIF_TAKIPLER[aid]["status"] = False
                database.refund_balance(user_id, f)
                database.add_to_history(user_id, 4, "Numara İptali", "Kullanıcı", f, status="❌ İPTAL")
                safe_payment_edit(bot, chat_id, msg_id, "❌ *İşlem İptal Edildi!* Ücret hesabınıza iade edildi.", ana_menu_klavyesi(user_id))
            else: 
                bot.answer_callback_query(call.id, "İptal başarısız! Kod gelmiş veya süre dolmuş olabilir.", show_alert=True)

        elif data.startswith("check_sms_"):
            bot.answer_callback_query(call.id, "⏳ Döngü arka planda otomatik tarıyor, manuel basmanıza gerek yok.", show_alert=False)


def live_track_sms(bot, chat_id, message_id, act_id, fiyat, svc_name, api_cc, phone, user_id, service_id, api_srv=None, provider=1):
    """SMS kodunu sorgulayan ve silinen mesajı otomatik yeniden gönderen siber zırhlı izole döngü."""
    act_id = str(act_id)
    duration = 1200 
    start_time = time.time()
    last_ui_update = 0
    current_message_id = message_id  
    prov_name = "🔥 Sunucu 1" if int(provider) == 1 else "⚡ Sunucu 2"
    
    admin_id = os.getenv("ADMIN_ID")

    while time.time() - start_time < duration:
        with tracking_lock:
            track_info = AKTIF_TAKIPLER.get(act_id)
            if not isinstance(track_info, dict) or not track_info.get("status"): return 

        if int(time.time()) % 4 == 0:
            try:
                sonuc = grizzly_provider.get_sms(act_id) if int(provider) == 1 else tigersms_provider.get_sms(act_id)
                if isinstance(sonuc, str) and sonuc != "WAIT_CODE":
                    with tracking_lock: AKTIF_TAKIPLER[act_id]["status"] = False
                    
                    try:
                        info = database.get_country_info(api_cc)
                        ulke_numara_kod = f"{info['flag']} {info['country_name']} (+{phone}) | 🔑 Kod: `{sonuc}`"
                    except:
                        ulke_numara_kod = f"🌍 (+{phone}) | 🔑 Kod: `{sonuc}`"

                    database.add_to_history(user_id, 2, svc_name.capitalize(), ulke_numara_kod, fiyat, status="✅ BAŞARILI", service_code=api_srv)
                    
                    if admin_id:
                        try: bot.send_message(admin_id, f"📱 *BAŞARILI NUMARA SATIŞI!* \n\n👤 Kullanıcı: `{user_id}`\n⚙️ Servis: `{svc_name}`\n💰 Kazanılan: `{fiyat} TL`", parse_mode="Markdown")
                        except: pass

                    metin = f"✅ *SMS Kodu Geldi!*\n\n📱 Numara: `+{phone}`\n⚙️ Servis: {svc_name}\n🖥️ Kaynak: {prov_name}\n🔑 *KOD:* `{sonuc}`"
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{service_id}"))
                    markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
                    
                    try: bot.delete_message(chat_id, current_message_id)
                    except: pass
                    
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
            metin = f"⏳ *SMS Bekleniyor...*\n\n📱 *Numaranız:* `+{phone}`\n🌍 Ülke: {info['flag']} {info['country_name']}\n⚙️ Servis: {svc_name}\n🖥️ Kaynak: {prov_name}\n💰 Ücret: {fiyat} TL\n⏱️ Kalan Süre: *{sure}*"
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{service_id}"),
                       types.InlineKeyboardButton("❌ İptal Et", callback_data=f"cancel_sms_{act_id}_{fiyat}_{provider}"))
            markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))

            try:
                try:
                    bot.edit_message_caption(chat_id=chat_id, message_id=current_message_id, caption=metin, reply_markup=markup, parse_mode="Markdown")
                except telebot.apihelper.ApiTelegramException as e:
                    if "message is not modified" in str(e).lower():
                        pass
                    elif "there is no caption" in str(e).lower() or "can't edit message" in str(e).lower():
                        bot.edit_message_text(chat_id=chat_id, message_id=current_message_id, text=metin, reply_markup=markup, parse_mode="Markdown")
                    else:
                        raise e
            except Exception as e:
                if "message to edit not found" in str(e).lower() or "message id invalid" in str(e).lower():
                    try:
                        with open("veritas_sms_logo_yatay.png", "rb") as photo:
                            yeni_mesaj = bot.send_photo(chat_id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
                            current_message_id = yeni_mesaj.message_id 
                    except:
                        try:
                            yeni_mesaj = bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")
                            current_message_id = yeni_mesaj.message_id
                        except: pass
            last_ui_update = time.time()
        time.sleep(1)

    with tracking_lock:
        if AKTIF_TAKIPLER.get(act_id, {}).get("status"):
            AKTIF_TAKIPLER[act_id]["status"] = False
            if int(provider) == 1: grizzly_provider.cancel_number(act_id)
            else: tigersms_provider.cancel_number(act_id)
            database.refund_balance(user_id, fiyat)
            database.add_to_history(user_id, 3, svc_name, phone, fiyat, status="❌ ZAMAN AŞIMI")
            
            try: bot.delete_message(chat_id, current_message_id)
            except: pass
            
            metin_za = f"⏱️ *Süre Doldu!* \n\n`+{phone}` için kod gelmedi. Bakiyeniz iade edildi."
            markup_za = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
            
            try:
                with open("veritas_sms_logo_yatay.png", "rb") as photo:
                    bot.send_photo(chat_id, photo, caption=metin_za, reply_markup=markup_za, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, metin_za, reply_markup=markup_za, parse_mode="Markdown")