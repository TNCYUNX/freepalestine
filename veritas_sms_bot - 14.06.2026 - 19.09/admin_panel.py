# -*- coding: utf-8 -*-
import telebot
from telebot import types
import os
import database
import math
from providers import sms_provider

def is_admin(user_id):
    admin_id_str = os.getenv("ADMIN_ID")
    return str(user_id) == admin_id_str if admin_id_str else False

def admin_klavyesi():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 İstatistikler", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 Kullanıcı Listesi", callback_data="admin_user_list")
    )
    markup.add(
        types.InlineKeyboardButton("🎟️ Kupon Yönetimi", callback_data="admin_create_coupon"),
        types.InlineKeyboardButton("🚫 Ban/Kaldır", callback_data="admin_ban_menu")
    )
    markup.add(
        types.InlineKeyboardButton("💰 Bakiye Ekle", callback_data="admin_add_balance"),
        types.InlineKeyboardButton("📢 Duyuru Yap", callback_data="admin_broadcast")
    )
    markup.add(
        types.InlineKeyboardButton("🚀 Servis Yönetimi", callback_data="admin_menu_fiyatlar"),
        types.InlineKeyboardButton("⚙️ Sistem Kontrol", callback_data="admin_system_control")
    )
    markup.add(
        types.InlineKeyboardButton("🎫 Destek Talepleri", callback_data="admin_tickets"),
        types.InlineKeyboardButton("🐻 Grizzly Durumu", callback_data="admin_grizzly")
    )
    markup.add(types.InlineKeyboardButton("❌ Kapat", callback_data="back_to_main"))
    return markup

def system_control_klavyesi():
    m_mode = database.get_maintenance_mode()
    m_text = "▶️ Sistemi Başlat" if m_mode == 'on' else "⏸️ Durdur (Bakım Modu)"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(m_text, callback_data="admin_sys_toggle_maint"),
        types.InlineKeyboardButton("🛑 Sunucuyu Kapat", callback_data="admin_sys_shutdown"),
        types.InlineKeyboardButton("🔙 Admin Menü", callback_data="admin_main")
    )
    return markup

def safe_admin_edit(bot, chat_id, message_id, text, markup=None):
    try:
        bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup, parse_mode="Markdown")
            except: pass

def register_admin_handlers(bot):
    """Admin işlemlerini ve wizard akışlarını yönetir. (FINAL HİYERARŞİK UX)"""

    def cleanup_msg(message):
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass

    @bot.message_handler(commands=['admin'])
    def admin_panel_komutu(message):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id)
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass
        metin = "🛡️ *Veritas SMS Yönetim Paneli*\n\nLütfen işlem seçin:"
        try:
            with open("veritas_sms_logo_yatay.png", "rb") as photo:
                bot.send_photo(message.chat.id, photo, caption=metin, reply_markup=admin_klavyesi(), parse_mode="Markdown")
        except:
            bot.send_message(message.chat.id, metin, reply_markup=admin_klavyesi(), parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
    def admin_callback_yonetici(call):
        if not is_admin(call.from_user.id): return
        chat_id, msg_id, data = call.message.chat.id, call.message.message_id, call.data

        if data == "admin_main":
            bot.clear_step_handler_by_chat_id(chat_id)
            safe_admin_edit(bot, chat_id, msg_id, "🛡️ *Yönetim Paneli Ana Menü*", admin_klavyesi())
            bot.answer_callback_query(call.id)

        elif data == "admin_stats":
            stats = database.get_statistics()
            m = database.get_maintenance_mode()
            t_usdt = float(database.get_setting("total_usdt_deposited", "0.0"))
            t_trx = float(database.get_setting("total_trx_deposited", "0.0"))
            metin = f"📊 *Sistem İstatistikleri*\n\n👥 Kullanıcı: {stats['total_users']}\n💰 Bakiyeler: {stats['total_balance']} TL\n📱 Satışlar: {stats['total_sold']}\n--------------------\n🟢 USDT: {t_usdt:.2f} $\n🔴 TRX: {t_trx:.2f} TRX\n🚧 Bakım: {'Açık' if m == 'on' else 'Kapalı'}"
            safe_admin_edit(bot, chat_id, msg_id, metin, admin_klavyesi())
            bot.answer_callback_query(call.id)

        elif data == "admin_user_list":
            users = database.get_all_users()
            markup = types.InlineKeyboardMarkup(row_width=1)
            for u in users[-12:]: markup.add(types.InlineKeyboardButton(f"👤 @{u['username'] or 'Yok'} ({u['balance']} TL)", callback_data=f"admin_usrdet_{u['user_id']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_main"))
            safe_admin_edit(bot, chat_id, msg_id, "👥 *Kullanıcı Listesi*", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_usrdet_"):
            uid = int(data.replace("admin_usrdet_", ""))
            user = next((u for u in database.get_all_users() if u['user_id'] == uid), None)
            if not user: return
            drm = "🚫 Yasaklı" if user['is_banned'] else "✅ Aktif"
            metin = f"🕵️‍♂️ *Profil: @{user['username']}*\n🆔 ID: `{user['user_id']}`\n💳 Bakiye: {user['balance']} TL\n🛡️ Durum: {drm}"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("📱 Alımlar", callback_data=f"admin_usrhis_num_{uid}"), types.InlineKeyboardButton("💳 Ödemeler", callback_data=f"admin_usrhis_pay_{uid}"))
            if user['is_banned']: markup.add(types.InlineKeyboardButton("✅ Yasağı Kaldır", callback_data=f"admin_setban_0_{uid}"))
            else: markup.add(types.InlineKeyboardButton("🚫 Yasakla", callback_data=f"admin_setban_1_{uid}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_user_list"))
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

        # --- DİNAMİK SERVİS YÖNETİMİ ---
        elif data == "admin_menu_fiyatlar":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("➕ Servis Ekle", callback_data="admin_add_srv_start"),
                       types.InlineKeyboardButton("🗑️ Servis Sil", callback_data="admin_del_price_start"),
                       types.InlineKeyboardButton("💲 Fiyat Güncelle", callback_data="admin_edit_price_start"),
                       types.InlineKeyboardButton("🔙 Ana Menü", callback_data="admin_main"))
            safe_admin_edit(bot, chat_id, msg_id, "🚀 *Servis ve Fiyat Yönetimi*", markup)
            bot.answer_callback_query(call.id)

        # ADIM 1: Platform Seçimi (Özel Sıralama & Tek Sütun)
        elif data in ["admin_add_srv_start", "admin_del_price_start", "admin_edit_price_start"]:
            mode = "adds" if "add_srv" in data else ("dels" if "del_price" in data else "edts")
            conn = database.get_db_connection(); cursor = conn.cursor(dictionary=True)
            if mode == "adds": cursor.execute("SELECT service_code, service_name FROM api_services")
            else: cursor.execute("SELECT DISTINCT api_srv AS service_code, service_name FROM services")
            all_srvs = cursor.fetchall(); conn.close()
            
            p_codes = ['wa', 'tg', 'ig', 'go']
            p_list = [s for c in p_codes for s in all_srvs if s['service_code'] == c]
            o_list = sorted([s for s in all_srvs if s['service_code'] not in p_codes], key=lambda x: x['service_name'])
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            for s in (p_list + o_list): markup.add(types.InlineKeyboardButton(s['service_name'], callback_data=f"admin_{mode}_p_{s['service_code']}"))
            if mode == "adds": markup.add(types.InlineKeyboardButton("✍️ Manuel Kod Gir", callback_data="admin_adds_srv_manual"))
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_menu_fiyatlar"))
            safe_admin_edit(bot, chat_id, msg_id, "🔍 *Platform Seçin*", markup)
            bot.answer_callback_query(call.id)

        # ADIM 2: Ülke Seçimi (3'lü Sütun & Özel Navigasyon)
        elif data.startswith("admin_adds_p_") or data.startswith("admin_dels_p_") or data.startswith("admin_edts_p_"):
            parts = data.split("_"); mode, srv_code = parts[1], parts[3]
            call.data = f"admin_pagnat_{mode}_{srv_code}_0"; admin_callback_yonetici(call)

        elif data.startswith("admin_pagnat_"):
            parts = data.split("_"); mode, srv_code, page = parts[2], parts[3], int(parts[4])
            limit = 12
            if mode == "adds":
                countries = database.get_paginated_countries(page=page, limit=limit)
                total_pages = database.get_total_country_pages(limit=limit)
            else:
                conn = database.get_db_connection(); cur = conn.cursor(dictionary=True); offset = page * limit
                cur.execute("SELECT DISTINCT country_name, country_code, flag FROM services WHERE api_srv = %s LIMIT %s OFFSET %s", (srv_code, limit, offset))
                countries = cur.fetchall()
                cur.execute("SELECT COUNT(DISTINCT country_code) AS total FROM services WHERE api_srv = %s", (srv_code,))
                res_count = cur.fetchone(); total_count = res_count['total'] if res_count else 0
                total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
                conn.close()

            markup = types.InlineKeyboardMarkup(row_width=3)
            btns = [types.InlineKeyboardButton(f"{c['flag']} {c['country_name']}", callback_data=f"admin_{mode}_cc_{srv_code}_{c['country_code']}") for c in countries]
            markup.add(*btns)
            
            # [ Geri | Sayfa X/Y | İleri ] Navigasyonu
            p_text = "◀️ Geri" if page > 0 else "❌"
            n_text = "İleri ▶️" if len(countries) == limit else "❌"
            mid_text = f"{p_text} | Sayfa {page+1}/{max(1, total_pages)} | {n_text}"
            
            nav_row = [
                types.InlineKeyboardButton("◀️ Geri" if page > 0 else "❌", callback_data=f"admin_pagnat_{mode}_{srv_code}_{page-1}" if page > 0 else "disabled"),
                types.InlineKeyboardButton(mid_text, callback_data="disabled"),
                types.InlineKeyboardButton("İleri ▶️" if len(countries) == limit else "❌", callback_data=f"admin_pagnat_{mode}_{srv_code}_{page+1}" if len(countries) == limit else "disabled")
            ]
            markup.row(*nav_row)
            back_cb = "admin_add_srv_start" if mode == "adds" else ("admin_del_price_start" if mode == "dels" else "admin_edit_price_start")
            markup.add(types.InlineKeyboardButton("🔙 Platform Seçimine Dön", callback_data=back_cb))
            safe_admin_edit(bot, chat_id, msg_id, f"🌍 *Ülke Seçin ({srv_code.upper()})*", markup)
            bot.answer_callback_query(call.id)

        # ADIM 3: Aksiyon (Ekleme / Silme Listesi / Güncelleme Listesi)
        elif data.startswith("admin_adds_cc_"):
            parts = data.split("_"); srv, cc = parts[3], parts[4]; c_info = database.get_country_info(cc)
            safe_admin_edit(bot, chat_id, msg_id, "⏳ *Grizzly Toptancı Maliyetleri Sorgulanıyor...*", None)
            stok_verisi = sms_provider.get_all_prices_and_stocks(srv, cc)
            metin = f"💲 *Analiz ve Fiyatlandırma*\n\n🚀 Servis: `{srv.upper()}`\n🌍 Ülke: {c_info['flag']} {c_info['country_name']}\n\n🐻 *Grizzly Toptan Maliyetler:*\n"
            if stok_verisi and isinstance(stok_verisi, dict):
                sorted_prices = sorted(stok_verisi.items(), key=lambda x: float(x[0]))
                for fyt, stk in sorted_prices[:5]: metin += f"💵 Maliyet: `{fyt}` $ ➡️ Stok: `{stk}`\n"
            else: metin += "_Canlı stok bilgisi alınamadı._\n"
            metin += "\n💡 *Talimat:* Maliyetlerden birini kopyalayıp buraya yapıştırın. Bot TL satış fiyatını soracaktır."
            markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("🔙 Ülke Seçimine Dön", callback_data=f"admin_adds_p_{srv}"))
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_wizard_capture_cost, api_srv=srv, api_cc=cc, msg_id=msg_id)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_dels_cc_") or data.startswith("admin_edts_cc_"):
            parts = data.split("_"); mode, srv_code, cc = parts[1], parts[3], parts[4]
            conn = database.get_db_connection(); cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id, service_name, price FROM services WHERE api_srv = %s AND api_cc = %s", (srv_code, cc))
            srvs = cur.fetchall(); conn.close()
            markup = types.InlineKeyboardMarkup(row_width=1)
            for s in srvs:
                prefix = "🗑️ Sil:" if mode == "dels" else "💲 Güncelle:"
                cb = f"admin_confirm_del_{s['id']}" if mode == "dels" else f"admin_edit_trigger_{s['id']}"
                markup.add(types.InlineKeyboardButton(f"{prefix} {s['service_name']} ({s['price']} TL)", callback_data=cb))
            markup.add(types.InlineKeyboardButton("🔙 Ülke Seçimine Dön", callback_data=f"admin_{mode}_p_{srv_code}"))
            safe_admin_edit(bot, chat_id, msg_id, f"🛠️ *İşlem Yapılacak Kaydı Seçin*\n\n{srv_code.upper()} - {cc} için kayıtlı hizmetler:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_confirm_del_"):
            sid = int(data.replace("admin_confirm_del_", "")); database.delete_service(sid)
            bot.answer_callback_query(call.id, "✅ Servis silindi!", show_alert=True)
            admin_callback_yonetici(call)

        elif data.startswith("admin_edit_trigger_"):
            sid = int(data.replace("admin_edit_trigger_", "")); srv = database.get_service_by_id(sid)
            if not srv: return
            safe_admin_edit(bot, chat_id, msg_id, f"💲 *{srv['service_name']}* için yeni **TL Satış Fiyatını** yazın:", admin_klavyesi())
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_wizard_edit_price, service_id=sid, photo_message_id=msg_id)
            bot.answer_callback_query(call.id)

        elif data == "admin_tickets":
            tickets = database.get_open_tickets(limit=10); markup = types.InlineKeyboardMarkup(row_width=1)
            if not tickets: markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_main")); safe_admin_edit(bot, chat_id, msg_id, "🎫 Açık talep yok.", markup)
            else:
                for t in tickets: markup.add(types.InlineKeyboardButton(f"📩 Talep #{t['id']} (User: {t['user_id']})", callback_data=f"admin_reply_ticket_{t['user_id']}_{t['id']}"))
                markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_main")); safe_admin_edit(bot, chat_id, msg_id, "🎫 *Açık Destek Talepleri*", markup)
            bot.answer_callback_query(call.id)

    # --- NEXT STEP HANDLERS ---
    def process_wizard_capture_cost(message, api_srv, api_cc, msg_id):
        if not is_admin(message.from_user.id): return
        try:
            cost = float(message.text.strip().replace(",", "."))
            cleanup_msg(message)
            safe_admin_edit(bot, message.chat.id, msg_id, f"✅ Maliyet Yakalandı: `{cost} $`\n\n✍️ Şimdi bu paket için kullanıcıların göreceği **TL Satış Fiyatını** yazın:", admin_klavyesi())
            bot.register_next_step_handler(message, process_wizard_final_price, api_srv=api_srv, api_cc=api_cc, api_cost=cost, msg_id=msg_id)
        except:
            bot.send_message(message.chat.id, "❌ Hata: Geçersiz maliyet formatı. Lütfen rakam gönderin.")
            bot.register_next_step_handler(message, process_wizard_capture_cost, api_srv=api_srv, api_cc=api_cc, msg_id=msg_id)

    def process_wizard_final_price(message, api_srv, api_cc, api_cost, msg_id):
        if not is_admin(message.from_user.id): return
        try:
            sell_price = float(message.text.strip().replace(",", "."))
            c_info = database.get_country_info(api_cc)
            database.add_new_service(api_srv.upper(), api_srv, api_cc, c_info['country_name'], api_cc, sell_price, c_info['flag'], api_cost)
            cleanup_msg(message)
            bot.send_message(message.chat.id, f"✅ *İŞLEM BAŞARILI*\n\n{c_info['flag']} {c_info['country_name']} - {api_srv.upper()}\n💵 Maliyet: `{api_cost} $` \n💰 Satış: `{sell_price} TL` \n\nSistem başarıyla güncellendi.", parse_mode="Markdown")
        except:
            bot.send_message(message.chat.id, "❌ Hata: Rakam giriniz.")
            bot.register_next_step_handler(message, process_wizard_final_price, api_srv=api_srv, api_cc=api_cc, api_cost=api_cost, msg_id=msg_id)

    def process_wizard_edit_price(message, service_id, photo_message_id):
        if not is_admin(message.from_user.id): return
        try:
            new_price = float(message.text.replace(",", ".")); database.update_service_price_by_id(service_id, new_price)
            cleanup_msg(message); bot.send_message(message.chat.id, f"✅ Fiyat `{new_price} TL` olarak güncellendi.")
        except: bot.send_message(message.chat.id, "❌ Hata: Geçersiz fiyat.")

    def process_ticket_reply(message, photo_message_id, hedef_id, ticket_id):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id); cleanup_msg(message)
        try:
            bot.send_message(hedef_id, f"📩 *Destek Yanıtı:* \n\n{message.text}", parse_mode="Markdown")
            database.close_ticket_by_id(ticket_id); bot.send_message(message.chat.id, f"✅ Talep #{ticket_id} yanıtlandı.")
        except: bot.send_message(message.chat.id, "❌ Kullanıcıya ulaşılamadı.")

    def process_create_coupon(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id); cleanup_msg(message)
        try:
            p = message.text.split(); kod, odul, limit = p[0].upper(), float(p[1]), int(p[2])
            if database.create_coupon(kod, odul, limit): bot.send_message(message.chat.id, f"✅ Kupon Oluşturuldu: `{kod}`")
        except: bot.send_message(message.chat.id, "❌ Hata: `KOD ÖDÜL LİMİT` formatında giriniz.")

    def process_add_balance(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id); cleanup_msg(message)
        try:
            p = message.text.split(); uid, mkt = int(p[0]), float(p[1]); database.update_balance(uid, mkt)
            bot.send_message(message.chat.id, f"✅ {uid} ID'li hesaba {mkt} TL eklendi.")
            try: bot.send_message(uid, f"🎉 Hesabınıza {mkt} TL tanımlandı.")
            except: pass
        except: bot.send_message(message.chat.id, "❌ Hata: `USER_ID MİKTAR` formatında giriniz.")

    def process_broadcast(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id); cleanup_msg(message)
        users = database.get_all_users()
        for k in users:
            try: bot.send_message(k['user_id'], f"📢 *Duyuru*\n\n{message.text}", parse_mode="Markdown")
            except: pass
        bot.send_message(message.chat.id, "✅ Duyuru tüm kullanıcılara gönderildi.")
