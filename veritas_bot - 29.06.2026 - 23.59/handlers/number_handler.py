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

        if not user_allowed(user_id, chat_id=chat_id, call_id=call.id): return
        
        # FSM Durum Temizliği (State Sızıntısını önler)
        try: bot.clear_step_handler_by_chat_id(chat_id)
        except: pass
        
        # Numara alımları kısıtlama kontrolü (Global veya kullanıcı bazlı engelleme)
        global_num_buy = database.get_global_number_buy_status()
        user_info = database.get_user_info(user_id)
        is_user_blocked = user_info.get("number_buy_blocked") if user_info else False
        
        admin_id = str(os.getenv("ADMIN_ID"))
        is_admin_user = (str(user_id) == admin_id)
        
        # 'leave_tracking_menu' ve 'cancel_sms_' gibi geri dönüş veya iptal işlemlerine her zaman izin verilmeli
        if not data.startswith(('leave_tracking_menu', 'cancel_sms_')) and not is_admin_user:
            if global_num_buy == 'off' or is_user_blocked:
                if global_num_buy == 'off':
                    bot.answer_callback_query(call.id, "⚠️ Sistem genelinde numara alımları geçici olarak kapatılmıştır!", show_alert=True)
                else:
                    bot.answer_callback_query(call.id, "❌ Numara satın alma yetkiniz dondurulmuştur. Lütfen destek ile iletişime geçin.", show_alert=True)
                
                # Eğer tıklanan buton doğrudan ana menüdeki "menu_numara_al" ise silip yönlendirmeye gerek yok
                if data == "menu_numara_al":
                    return
                
                # UX Reset: Mevcut alt menü mesajını sil ve ana menüye yönlendir
                try: bot.delete_message(chat_id, msg_id)
                except: pass
                
                try:
                    with open("veritas_sms_logo_yatay.png", "rb") as photo:
                        bot.send_photo(chat_id, photo, caption=config.MESAJLAR["hosgeldin"].format(isim=call.from_user.first_name), reply_markup=ana_menu_klavyesi(user_id=user_id), parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, config.MESAJLAR["hosgeldin"].format(isim=call.from_user.first_name), reply_markup=ana_menu_klavyesi(user_id=user_id), parse_mode="Markdown")
                return

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

        elif data == "menu_populer":
            aktif = database.get_active_services()
            populer_list = ['wa', 'tg', 'go', 'ig', 'fb', 'tk', 'ds']
            srv_names = {
                'wa': 'WhatsApp', 'tg': 'Telegram', 'go': 'Google / Gmail', 
                'ig': 'Instagram', 'fb': 'Facebook', 'tk': 'TikTok', 'ds': 'Discord'
            }
            markup = types.InlineKeyboardMarkup(row_width=1)
            for code in populer_list:
                if code in aktif:
                    name = srv_names.get(code, code.upper())
                    markup.add(types.InlineKeyboardButton(f"🌟 {name}", callback_data=f"select_srv_{code}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back_to_main"))
            safe_edit(call, "🌟 *Popüler Servisler* 🌟\n\nEn çok tercih edilen platformlardan birini seçebilirsiniz:", markup)

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
            
            # Kademeleri de en ucuzdan en pahalıya sıralayalım
            kademeler = sorted(kademeler, key=lambda x: float(x['price']) if x['price'] is not None else 999999.0)
            
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
                    start_time_now = time.time()
                    
                    with tracking_lock:
                        AKTIF_TAKIPLER[act_id] = {
                            "status": True,
                            "user_id": user_id,
                            "chat_id": chat_id,
                            "message_id": None, # Will be set below
                            "price": svc['price'],
                            "service_name": svc['service_name'],
                            "api_cc": svc['api_cc'],
                            "phone": sonuc["phone"],
                            "service_id": sid,
                            "api_srv": svc['api_srv'],
                            "provider": prov,
                            "start": start_time_now,
                            "last_ui_update": start_time_now,
                            "last_query_time": 0
                        }
                    
                    if data.startswith("buy_num_"):
                        try: bot.delete_message(chat_id, msg_id)
                        except: pass
                    
                    info = database.get_country_info(svc['api_cc'])
                    prov_name = "🔥 Sunucu 1" if prov == 1 else "⚡ Sunucu 2"
                    metin = f"⏳ *SMS Bekleniyor...*\n\n📱 *Numaranız:* `+{sonuc['phone']}`\n🌍 Ülke: {info['flag']} {info['country_name']}\n⚙️ Servis: {svc['service_name']}\n🖥️ Kaynak: {prov_name}\n💰 Ücret: {svc['price']} TL\n⏱️ Kalan Süre: *20:00*"
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.row(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{sid}"),
                               types.InlineKeyboardButton("❌ İptal Et", callback_data=f"cancel_sms_{act_id}_{svc['price']}_{prov}"))
                    markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
                    
                    # LOGOLU YENİ MESAJ
                    try:
                        with open("veritas_sms_logo_yatay.png", "rb") as photo:
                            new_msg = bot.send_photo(chat_id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
                    except:
                        new_msg = bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")
                    
                    # message_id'yi AKTIF_TAKIPLER'e yaz
                    with tracking_lock:
                        if act_id in AKTIF_TAKIPLER:
                            AKTIF_TAKIPLER[act_id]["message_id"] = new_msg.message_id
                            
                    # Veritabanına aktif kiralamayı kaydet (Auto-Recovery için)
                    database.add_active_rental(
                        user_id=user_id,
                        chat_id=chat_id,
                        message_id=new_msg.message_id,
                        activation_id=act_id,
                        phone_number=sonuc["phone"],
                        service_id=sid,
                        service_code=svc['api_srv'],
                        service_name=svc['service_name'],
                        api_srv=svc['api_srv'],
                        api_cc=svc['api_cc'],
                        price=svc['price'],
                        provider=prov,
                        start_time=start_time_now
                    )
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
            
            # Eğer API iptali başarısız olduysa (ör. zaten sağlayıcı tarafında iptal edilmişse BAD_ACTION döner),
            # sağlayıcı tarafındaki durumunu sorgulayalım:
            if not success:
                st = grizzly_provider.get_sms(aid) if prov == 1 else tigersms_provider.get_sms(aid)
                if st == "STATUS_CANCEL":
                    success = True
                
            if success:
                with tracking_lock:
                    if aid in AKTIF_TAKIPLER:
                        AKTIF_TAKIPLER.pop(aid, None)
                database.refund_balance(user_id, f)
                database.add_to_history(user_id, 4, "Numara İptali", "Kullanıcı", f, status="❌ İPTAL", activation_id=aid)
                database.delete_active_rental(aid)
                safe_payment_edit(bot, chat_id, msg_id, "❌ *İşlem İptal Edildi!* Ücret hesabınıza iade edildi.", ana_menu_klavyesi(user_id))
            else: 
                bot.answer_callback_query(call.id, "İptal başarısız! Kod gelmiş veya süre dolmuş olabilir.", show_alert=True)

        elif data.startswith("check_sms_"):
            bot.answer_callback_query(call.id, "⏳ Döngü arka planda otomatik tarıyor, manuel basmanıza gerek yok.", show_alert=False)


def live_track_sms(bot, chat_id, message_id, act_id, fiyat, svc_name, api_cc, phone, user_id, service_id, api_srv=None, provider=1, custom_start_time=None):
    """SMS kodunu sorgulayan ve silinen mesajı otomatik yeniden gönderen siber zırhlı izole döngü."""
    act_id = str(act_id)
    duration = 1200 
    start_time = custom_start_time if custom_start_time is not None else time.time()
    last_ui_update = 0
    last_query_time = 0
    current_message_id = message_id  
    prov_name = "🔥 Sunucu 1" if int(provider) == 1 else "⚡ Sunucu 2"
    
    admin_id = os.getenv("ADMIN_ID")

    while time.time() - start_time < duration:
        with tracking_lock:
            track_info = AKTIF_TAKIPLER.get(act_id)
            if not isinstance(track_info, dict) or not track_info.get("status"): return 

        if time.time() - last_query_time >= 4.0:
            last_query_time = time.time()
            try:
                sonuc = grizzly_provider.get_sms(act_id) if int(provider) == 1 else tigersms_provider.get_sms(act_id)
                if sonuc == "STATUS_CANCEL":
                    with tracking_lock: AKTIF_TAKIPLER[act_id]["status"] = False
                    database.refund_balance(user_id, fiyat)
                    database.add_to_history(user_id, 4, "Numara İptali", "Sağlayıcı", fiyat, status="❌ İPTAL", activation_id=act_id)
                    database.delete_active_rental(act_id)
                    
                    metin = f"❌ *İşlem İptal Edildi!*\n\nNumaranız (`+{phone}`) sağlayıcı veya süre aşımı nedeniyle iptal edildi. Ücret hesabınıza iade edildi."
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
                    
                    try: bot.delete_message(chat_id, current_message_id)
                    except: pass
                    
                    try:
                        with open("veritas_sms_logo_yatay.png", "rb") as photo:
                            bot.send_photo(chat_id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
                    except:
                        bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")
                    return
                
                elif isinstance(sonuc, str) and sonuc != "WAIT_CODE":
                    with tracking_lock: AKTIF_TAKIPLER[act_id]["status"] = False
                    
                    try:
                        info = database.get_country_info(api_cc)
                        ulke_numara_kod = f"{info['flag']} {info['country_name']} (+{phone}) | 🔑 Kod: `{sonuc}`"
                    except:
                        ulke_numara_kod = f"🌍 (+{phone}) | 🔑 Kod: `{sonuc}`"

                    # 1. Anlık USDT kurunu ve maliyeti çekip hesapla
                    usd_rate = database.get_live_usdt_rate()
                    service_info = database.get_service_by_id(service_id)
                    cost_usd = float(service_info.get('api_max_price') or 0.0) if service_info else 0.0
                    cost_tl = round(cost_usd * usd_rate, 4)
                    profit_tl = round(fiyat - cost_tl, 4)
                    
                    # 2. İşlem geçmişini maliyet ve kâr detaylarıyla kaydet
                    database.add_to_history_with_profit(
                        user_id=user_id,
                        action_type=2,
                        service_name=svc_name.capitalize(),
                        fake_number=ulke_numara_kod,
                        price=fiyat,
                        cost_tl=cost_tl,
                        profit_tl=profit_tl,
                        service_code=api_srv,
                        activation_id=act_id
                    )
                    
                    # 3. Finansal havuzları güncelle ve aktifi temizle
                    database.update_financial_pools(cost_tl, profit_tl)
                    database.delete_active_rental(act_id)
                    
                    if admin_id:
                        try:
                            chat_info = bot.get_chat(user_id)
                            full_name = f"{chat_info.first_name or ''} {chat_info.last_name or ''}".strip() or "Kullanıcı"
                            username_mention = f"@{chat_info.username}" if chat_info.username else "Yok"
                        except:
                            full_name = "Kullanıcı"
                            username_mention = "Yok"
                        try: bot.send_message(admin_id, f"📱 *BAŞARILI NUMARA SATIŞI!* \n\n👤 Kullanıcı: [{full_name}](tg://user?id={user_id}) ({username_mention})\n🆔 ID: `{user_id}`\n⚙️ Servis: `{svc_name}`\n💰 Kazanılan: `{fiyat} TL`", parse_mode="Markdown")
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
            database.add_to_history(user_id, 3, svc_name, phone, fiyat, status="❌ ZAMAN AŞIMI", activation_id=act_id)
            database.delete_active_rental(act_id)
            
            try: bot.delete_message(chat_id, current_message_id)
            except: pass
            
            metin_za = f"⏱️ *Süre Doldu!* \n\n`+{phone}` için kod gelmedi. Bakiyeniz iade edildi."
            markup_za = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
            
            try:
                with open("veritas_sms_logo_yatay.png", "rb") as photo:
                    bot.send_photo(chat_id, photo, caption=metin_za, reply_markup=markup_za, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, metin_za, reply_markup=markup_za, parse_mode="Markdown")

def recover_active_rentals(bot):
    """Bot başlatıldığında yarım kalan veya süresi dolan SMS işlemlerini veritabanından kurtarır."""
    print("[*] Aktif kiralamalar kurtarılıyor...")
    try:
        rentals = database.get_active_rentals()
    except Exception as e:
        print(f"[-] Veritabanından aktif kiralamalar alınamadı: {e}")
        return
        
    if not rentals:
        print("[*] Kurtarılacak aktif kiralama bulunmadı.")
        return

    print(f"[*] Toplam {len(rentals)} aktif kiralama tespit edildi. Durumlar kontrol ediliyor...")
    for r in rentals:
        user_id = r["user_id"]
        chat_id = r["chat_id"]
        msg_id = r["message_id"]
        act_id = r["activation_id"]
        phone = r["phone_number"]
        price = r["price"]
        svc_name = r["service_name"]
        api_srv = r["api_srv"]
        api_cc = r["api_cc"]
        prov = r["provider"]
        start_time = r["start_time"]
        sid = r["service_id"]
        
        current_time = time.time()
        elapsed = current_time - start_time
        remaining = 1200 - elapsed  # 20 dakika = 1200 saniye
        
        # 1. Sağlayıcıdan SMS gelip gelmediğini kontrol et (Zaafiyet Koruması)
        try:
            sms_code = grizzly_provider.get_sms(act_id) if prov == 1 else tigersms_provider.get_sms(act_id)
        except Exception as e:
            print(f"[-] Kurtarma sirasinda SMS kontrol hatasi ({act_id}): {e}")
            sms_code = None
            
        # Eğer bot kapalıyken SMS sağlayıcı tarafında iptal edildiyse:
        if sms_code == "STATUS_CANCEL":
            print(f"[-] Kurtarma: Numaraya ulaşılamadı veya sağlayıcı iptal etti (User: {user_id})")
            database.refund_balance(user_id, price)
            database.add_to_history(user_id, 4, "Numara İptali", "Sağlayıcı", price, status="❌ İPTAL", activation_id=act_id)
            database.delete_active_rental(act_id)
            
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            
            metin_za = f"❌ *Kiralama İptal Edildi!*\n\n`+{phone}` numaralı kiralama sağlayıcı tarafından iptal edilmiştir. Bakiyeniz iade edilmiştir."
            markup_za = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
            
            try:
                with open("veritas_sms_logo_yatay.png", "rb") as photo:
                    bot.send_photo(chat_id, photo, caption=metin_za, reply_markup=markup_za, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, metin_za, reply_markup=markup_za, parse_mode="Markdown")
                
            continue

        # Eğer bot kapalıyken SMS kodu ulaştıysa:
        if isinstance(sms_code, str) and sms_code != "WAIT_CODE":
            print(f"[+] Kurtarma: Numaraya SMS geldi! Kod: {sms_code} (User: {user_id})")
            try:
                info = database.get_country_info(api_cc)
                ulke_numara_kod = f"{info['flag']} {info['country_name']} (+{phone}) | 🔑 Kod: `{sms_code}`"
            except:
                ulke_numara_kod = f"🌍 (+{phone}) | 🔑 Kod: `{sms_code}`"
                
            # 1. Anlık USDT kurunu ve maliyeti çekip hesapla
            usd_rate = database.get_live_usdt_rate()
            service_info = database.get_service_by_id(sid)
            cost_usd = float(service_info.get('api_max_price') or 0.0) if service_info else 0.0
            cost_tl = round(cost_usd * usd_rate, 4)
            profit_tl = round(price - cost_tl, 4)
            
            # 2. İşlem geçmişini maliyet ve kâr detaylarıyla kaydet
            database.add_to_history_with_profit(
                user_id=user_id,
                action_type=2,
                service_name=svc_name.capitalize(),
                fake_number=ulke_numara_kod,
                price=price,
                cost_tl=cost_tl,
                profit_tl=profit_tl,
                service_code=api_srv,
                activation_id=act_id
            )
            
            # 3. Finansal havuzları güncelle ve aktifi temizle
            database.update_financial_pools(cost_tl, profit_tl)
            database.delete_active_rental(act_id)
            
            # Eski takip mesajını sil ve kodu gösteren yeni mesaj gönder
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            
            prov_name = "🔥 Sunucu 1" if prov == 1 else "⚡ Sunucu 2"
            metin = (
                "✅ *SMS Kodu Yakalandı (Kurtarıldı)!*\n\n"
                f"📱 Numara: `+{phone}`\n"
                f"⚙️ Servis: {svc_name}\n"
                f"🖥️ Kaynak: {prov_name}\n"
                f"🔑 *KOD:* `{sms_code}`\n\n"
                f"💡 _Bot çevrimdışıyken gelen SMS başarıyla kurtarılmıştır._"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{sid}"))
            markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
            
            try:
                with open("veritas_sms_logo_yatay.png", "rb") as photo:
                    bot.send_photo(chat_id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")
                
            continue

        # Eğer SMS gelmemiş ve süre dolmuşsa:
        if remaining <= 0:
            print(f"[-] Kurtarma: Süre dolmuş, SMS yok. İptal ediliyor (User: {user_id})")
            database.refund_balance(user_id, price)
            database.add_to_history(user_id, 3, svc_name, phone, price, status="❌ ZAMAN AŞIMI", activation_id=act_id)
            database.delete_active_rental(act_id)
            
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            
            metin_za = f"⏱️ *Bot Çevrimdışıyken Süre Doldu!*\n\n`+{phone}` numarasına süre boyunca kod gelmedi. Bakiyeniz iade edilmiştir."
            markup_za = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
            
            try:
                with open("veritas_sms_logo_yatay.png", "rb") as photo:
                    bot.send_photo(chat_id, photo, caption=metin_za, reply_markup=markup_za, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, metin_za, reply_markup=markup_za, parse_mode="Markdown")
                
            continue

        # Eğer hala süre varsa, merkezi takip listesine ekle!
        print(f"[+] Kurtarma: Kiralama aktif, kalan süre: {int(remaining)} sn. Takip listesine ekleniyor...")
        
        with tracking_lock:
            AKTIF_TAKIPLER[act_id] = {
                "status": True,
                "user_id": user_id,
                "chat_id": chat_id,
                "message_id": msg_id,
                "price": price,
                "service_name": svc_name,
                "api_cc": api_cc,
                "phone": phone,
                "service_id": sid,
                "api_srv": api_srv,
                "provider": prov,
                "start": start_time,
                "last_ui_update": 0,
                "last_query_time": 0
            }

def start_central_sms_tracking_worker(bot):
    """Sistemin tüm aktif SMS kiralamalarını eşzamanlı ve paralel bir şekilde
    (Thread Pool kullanarak) yöneten, API yavaşlıklarının bot geneline yansımasını önleyen motor."""
    from main import ana_menu_klavyesi
    from providers import grizzly_provider, tigersms_provider
    from concurrent.futures import ThreadPoolExecutor
    
    # Maksimum 20 eşzamanlı API / UI güncelleme işçisi
    executor = ThreadPoolExecutor(max_workers=20)
    
    def process_single_tracking(act_id, info, now):
        try:
            # Değişkenleri al
            user_id = info["user_id"]
            chat_id = info["chat_id"]
            msg_id = info["message_id"]
            price = info["price"]
            svc_name = info["service_name"]
            api_cc = info["api_cc"]
            phone = info["phone"]
            service_id = info["service_id"]
            api_srv = info["api_srv"]
            provider = info["provider"]
            start_time = info["start"]
            last_ui_update = info.get("last_ui_update", 0)
            last_query_time = info.get("last_query_time", 0)
            
            elapsed = now - start_time
            duration = 1200 # 20 dakika
            
            # 1. ZAMAN AŞIMI KONTROLÜ
            if elapsed >= duration:
                with tracking_lock:
                    if act_id in AKTIF_TAKIPLER:
                        AKTIF_TAKIPLER[act_id]["status"] = False
                        AKTIF_TAKIPLER.pop(act_id, None)
                        
                if int(provider) == 1: grizzly_provider.cancel_number(act_id)
                else: tigersms_provider.cancel_number(act_id)
                
                database.refund_balance(user_id, price)
                database.add_to_history(user_id, 3, svc_name, phone, price, status="❌ ZAMAN AŞIMI", activation_id=act_id)
                database.delete_active_rental(act_id)
                
                try: bot.delete_message(chat_id, msg_id)
                except: pass
                
                metin_za = f"⏱️ *Süre Doldu!* \n\n`+{phone}` için kod gelmedi. Bakiyeniz iade edildi."
                markup_za = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
                
                try:
                    with open("veritas_sms_logo_yatay.png", "rb") as photo:
                        bot.send_photo(chat_id, photo, caption=metin_za, reply_markup=markup_za, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, metin_za, reply_markup=markup_za, parse_mode="Markdown")
                return
                
            # 2. SAĞLAYICIDAN SMS SORGULAMA KONTROLÜ (4 saniyede bir)
            if now - last_query_time >= 4.0:
                with tracking_lock:
                    if act_id in AKTIF_TAKIPLER:
                        AKTIF_TAKIPLER[act_id]["last_query_time"] = now
                        
                try:
                    sonuc = grizzly_provider.get_sms(act_id) if int(provider) == 1 else tigersms_provider.get_sms(act_id)
                    
                    if sonuc == "STATUS_CANCEL":
                        with tracking_lock:
                            if act_id in AKTIF_TAKIPLER:
                                AKTIF_TAKIPLER[act_id]["status"] = False
                                AKTIF_TAKIPLER.pop(act_id, None)
                                
                        database.refund_balance(user_id, price)
                        database.add_to_history(user_id, 4, "Numara İptali", "Sağlayıcı", price, status="❌ İPTAL", activation_id=act_id)
                        database.delete_active_rental(act_id)
                        
                        metin = f"❌ *İşlem İptal Edildi!*\n\nNumaranız (`+{phone}`) sağlayıcı veya süre aşımı nedeniyle iptal edildi. Ücret hesabınıza iade edildi."
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
                        
                        try: bot.delete_message(chat_id, msg_id)
                        except: pass
                        
                        try:
                            with open("veritas_sms_logo_yatay.png", "rb") as photo:
                                bot.send_photo(chat_id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
                        except:
                            bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")
                        return
                        
                    elif isinstance(sonuc, str) and sonuc != "WAIT_CODE":
                        with tracking_lock:
                            if act_id in AKTIF_TAKIPLER:
                                AKTIF_TAKIPLER[act_id]["status"] = False
                                AKTIF_TAKIPLER.pop(act_id, None)
                                
                        try:
                            c_info = database.get_country_info(api_cc)
                            ulke_numara_kod = f"{c_info['flag']} {c_info['country_name']} (+{phone}) | 🔑 Kod: `{sonuc}`"
                        except:
                            ulke_numara_kod = f"🌍 (+{phone}) | 🔑 Kod: `{sonuc}`"
                            
                        # 1. Anlık USDT kurunu ve maliyeti çekip hesapla
                        usd_rate = database.get_live_usdt_rate()
                        service_info = database.get_service_by_id(service_id)
                        cost_usd = float(service_info.get('api_max_price') or 0.0) if service_info else 0.0
                        cost_tl = round(cost_usd * usd_rate, 4)
                        profit_tl = round(price - cost_tl, 4)
                        
                        # 2. İşlem geçmişini maliyet ve kâr detaylarıyla kaydet
                        database.add_to_history_with_profit(
                            user_id=user_id,
                            action_type=2,
                            service_name=svc_name.capitalize(),
                            fake_number=ulke_numara_kod,
                            price=price,
                            cost_tl=cost_tl,
                            profit_tl=profit_tl,
                            service_code=api_srv,
                            activation_id=act_id
                        )
                        
                        # 3. Finansal havuzları güncelle ve aktifi temizle
                        database.update_financial_pools(cost_tl, profit_tl)
                        database.delete_active_rental(act_id)
                        
                        admin_id = os.getenv("ADMIN_ID")
                        if admin_id:
                            try:
                                chat_info = bot.get_chat(user_id)
                                full_name = f"{chat_info.first_name or ''} {chat_info.last_name or ''}".strip() or "Kullanıcı"
                                username_mention = f"@{chat_info.username}" if chat_info.username else "Yok"
                            except:
                                full_name = "Kullanıcı"
                                username_mention = "Yok"
                            try: bot.send_message(admin_id, f"📱 *BAŞARILI NUMARA SATIŞI!* \n\n👤 Kullanıcı: [{full_name}](tg://user?id={user_id}) ({username_mention})\n🆔 ID: `{user_id}`\n⚙️ Servis: `{svc_name}`\n💰 Kazanılan: `{price} TL`", parse_mode="Markdown")
                            except: pass
                            
                        prov_name = "🔥 Sunucu 1" if int(provider) == 1 else "⚡ Sunucu 2"
                        metin = f"✅ *SMS Kodu Geldi!*\n\n📱 Numara: `+{phone}`\n⚙️ Servis: {svc_name}\n🖥️ Kaynak: {prov_name}\n🔑 *KOD:* `{sonuc}`"
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{service_id}"))
                        markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
                        
                        try: bot.delete_message(chat_id, msg_id)
                        except: pass
                        
                        try:
                            with open("veritas_sms_logo_yatay.png", "rb") as photo:
                                bot.send_photo(chat_id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
                        except:
                            bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")
                        return
                except Exception as e:
                    print(f"[-] Central SMS query exception for {act_id}: {e}")
                    
            # 3. KULLANICI ARAYÜZÜ SÜRE SAYACINI GÜNCELLEME (10 saniyede bir)
            if now - last_ui_update >= 10.0:
                with tracking_lock:
                    if act_id in AKTIF_TAKIPLER:
                        AKTIF_TAKIPLER[act_id]["last_ui_update"] = now
                        
                remaining = int(duration - elapsed)
                sure = f"{remaining // 60:02d}:{remaining % 60:02d}"
                prov_name = "🔥 Sunucu 1" if int(provider) == 1 else "⚡ Sunucu 2"
                
                try:
                    c_info = database.get_country_info(api_cc)
                    metin = f"⏳ *SMS Bekleniyor...*\n\n📱 *Numaranız:* `+{phone}`\n🌍 Ülke: {c_info['flag']} {c_info['country_name']}\n⚙️ Servis: {svc_name}\n🖥️ Kaynak: {prov_name}\n💰 Ücret: {price} TL\n⏱️ Kalan Süre: *{sure}*"
                except:
                    metin = f"⏳ *SMS Bekleniyor...*\n\n📱 *Numaranız:* `+{phone}`\n🌍 Ülke: 🌍 Bilinmeyen\n⚙️ Servis: {svc_name}\n🖥️ Kaynak: {prov_name}\n💰 Ücret: {price} TL\n⏱️ Kalan Süre: *{sure}*"
                    
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton("🔄 Aynısından Yeniden Al", callback_data=f"rebuy_{service_id}"),
                           types.InlineKeyboardButton("❌ İptal Et", callback_data=f"cancel_sms_{act_id}_{price}_{provider}"))
                markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="leave_tracking_menu"))
                
                try:
                    try:
                        bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=metin, reply_markup=markup, parse_mode="Markdown")
                    except telebot.apihelper.ApiTelegramException as e:
                        if "message is not modified" in str(e).lower():
                            pass
                        elif "there is no caption" in str(e).lower() or "can't edit message" in str(e).lower():
                            bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=metin, reply_markup=markup, parse_mode="Markdown")
                        else:
                            raise e
                except Exception as e:
                    if "message to edit not found" in str(e).lower() or "message id invalid" in str(e).lower():
                        try:
                            with open("veritas_sms_logo_yatay.png", "rb") as photo:
                                yeni_mesaj = bot.send_photo(chat_id, photo, caption=metin, reply_markup=markup, parse_mode="Markdown")
                                new_msg_id = yeni_mesaj.message_id 
                        except:
                            try:
                                yeni_mesaj = bot.send_message(chat_id, metin, reply_markup=markup, parse_mode="Markdown")
                                new_msg_id = yeni_mesaj.message_id
                            except:
                                new_msg_id = None
                                
                        if new_msg_id:
                            with tracking_lock:
                                if act_id in AKTIF_TAKIPLER:
                                    AKTIF_TAKIPLER[act_id]["message_id"] = new_msg_id
        except Exception as ex:
            print(f"[-] Thread task failed for {act_id}: {ex}")

    def worker():
        print("[+] Eşzamanlı SMS Takip Havuzu (Thread Pool) başlatıldı.")
        while True:
            try:
                with tracking_lock:
                    active_items = {k: v for k, v in AKTIF_TAKIPLER.items() if v.get("status")}
                
                now = time.time()
                for act_id, info in active_items.items():
                    executor.submit(process_single_tracking, act_id, info, now)
            except Exception as e:
                print(f"[-] SMS Takip döngüsü hatası: {e}")
            time.sleep(1.0)
            
    threading.Thread(target=worker, daemon=True).start()