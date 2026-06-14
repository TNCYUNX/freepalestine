# -*- coding: utf-8 -*-
import telebot
from telebot import types
import os
import database
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
    """Admin işlemlerini ve wizard akışlarını yönetir. (TAM SÜRÜM - DİNAMİK)"""

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
            
            metin = (
                "📊 *Sistem İstatistikleri*\n\n"
                f"👥 *Kullanıcı:* {stats['total_users']}\n"
                f"💰 *Toplam Bakiyeler:* {stats['total_balance']} TL\n"
                f"📱 *Satılan Numara:* {stats['total_sold']}\n"
                "--------------------\n"
                f"🟢 *Toplam USDT:* {t_usdt:.2f} $\n"
                f"🔴 *Toplam TRX:* {t_trx:.2f} TRX\n"
                "--------------------\n"
                f"🚧 *Bakım Modu:* {'Açık' if m == 'on' else 'Kapalı'}"
            )
            safe_admin_edit(bot, chat_id, msg_id, metin, admin_klavyesi())
            bot.answer_callback_query(call.id)

        elif data == "admin_user_list":
            users = database.get_all_users()
            markup = types.InlineKeyboardMarkup(row_width=1)
            for u in users[-12:]:
                markup.add(types.InlineKeyboardButton(f"👤 @{u['username'] or 'Yok'} ({u['balance']} TL)", callback_data=f"admin_usrdet_{u['user_id']}"))
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
            markup.add(types.InlineKeyboardButton("📱 Alımlar", callback_data=f"admin_usrhis_num_{uid}"),
                       types.InlineKeyboardButton("💳 Ödemeler", callback_data=f"admin_usrhis_pay_{uid}"))
            if user['is_banned']: markup.add(types.InlineKeyboardButton("✅ Yasağı Kaldır", callback_data=f"admin_setban_0_{uid}"))
            else: markup.add(types.InlineKeyboardButton("🚫 Yasakla", callback_data=f"admin_setban_1_{uid}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_user_list"))
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

        # --- DİNAMİK SERVİS YÖNETİMİ (3-ADIMLI AKIŞ) ---
        elif data == "admin_menu_fiyatlar":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("➕ Servis Ekle", callback_data="admin_wiz_step1_add"),
                       types.InlineKeyboardButton("🗑️ Servis Sil", callback_data="admin_delete_service_menu"),
                       types.InlineKeyboardButton("💲 Fiyat Güncelle", callback_data="admin_wiz_step1_edit"),
                       types.InlineKeyboardButton("🔙 Ana Menü", callback_data="admin_main"))
            safe_admin_edit(bot, chat_id, msg_id, "🚀 *Servis ve Fiyat Yönetimi*", markup)
            bot.answer_callback_query(call.id)

        # ADIM 1: Platform Seçimi
        elif data.startswith("admin_wiz_step1_"):
            mode = data.split("_")[3] # 'add' veya 'edit'
            platforms = database.get_api_services()
            markup = types.InlineKeyboardMarkup(row_width=2)
            for p in platforms:
                markup.add(types.InlineKeyboardButton(p['service_name'], callback_data=f"admin_wiz_step2_{mode}_{p['service_code']}"))
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_menu_fiyatlar"))
            safe_admin_edit(bot, chat_id, msg_id, "🔍 *Adım 1: Platform Seçin*", markup)
            bot.answer_callback_query(call.id)

        # ADIM 2: Ülke Seçimi
        elif data.startswith("admin_wiz_step2_"):
            parts = data.split("_")
            mode, srv_code = parts[3], parts[4]
            countries = database.get_paginated_countries(page=0, limit=40)
            markup = types.InlineKeyboardMarkup(row_width=2)
            for c in countries:
                markup.add(types.InlineKeyboardButton(f"{c['flag']} {c['country_name']}", callback_data=f"admin_wiz_step3_{mode}_{srv_code}_{c['country_code']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data=f"admin_wiz_step1_{mode}"))
            safe_admin_edit(bot, chat_id, msg_id, f"🌍 *Adım 2: {srv_code.upper()} İçin Ülke Seçin*", markup)
            bot.answer_callback_query(call.id)

        # ADIM 3: API Maliyet Analizi ve Fiyat Belirleme
        elif data.startswith("admin_wiz_step3_"):
            parts = data.split("_")
            mode, srv_code, cc = parts[3], parts[4], parts[5]
            c_info = database.get_country_info(cc)
            safe_admin_edit(bot, chat_id, msg_id, "⏳ *Grizzly API'den canlı veriler çekiliyor...*", None)
            
            live_data = sms_provider.get_all_prices_and_stocks(srv_code, cc)
            
            metin = f"💲 *Adım 3: Analiz ve Fiyatlandırma*\n\n"
            metin += f"🚀 Servis: `{srv_code.upper()}`\n🌍 Ülke: {c_info['flag']} {c_info['country_name']}\n\n"
            metin += "🐻 *Grizzly Toptan Maliyetler (En Ucuz 5):*\n"
            
            first_cost = "0.0"
            if live_data and isinstance(live_data, dict):
                sorted_prices = sorted(live_data.items(), key=lambda x: float(x[0]))
                for price, stock in sorted_prices[:5]:
                    metin += f"💵 Maliyet: `{price} $` ➡️ Stok: `{stock}`\n"
                if sorted_prices: first_cost = sorted_prices[0][0]
            else:
                metin += "❌ Stok bulunamadı veya API hatası.\n"
            
            metin += "\n💰 Lütfen botun **TL satış fiyatını** yazın:"
            markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_menu_fiyatlar"))
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.clear_step_handler_by_chat_id(chat_id)
            
            if mode == "add":
                bot.register_next_step_handler(call.message, process_wizard_add_service, srv_code=srv_code, cc=cc, c_name=c_info['country_name'], flag=c_info['flag'], cost=first_cost, msg_id=msg_id)
            else:
                bot.register_next_step_handler(call.message, process_wizard_edit_price, srv_code=srv_code, cc=cc, msg_id=msg_id)
            bot.answer_callback_query(call.id)

        # --- DİĞER STANDART CALLBACKLER ---
        elif data == "admin_delete_service_menu":
            srvs = database.get_all_services()
            markup = types.InlineKeyboardMarkup(row_width=2)
            for s in srvs: markup.add(types.InlineKeyboardButton(f"🗑️ {s['service_name']} ({s['country_name']})", callback_data=f"admin_delsrv_{s['id']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_menu_fiyatlar"))
            safe_admin_edit(bot, chat_id, msg_id, "🗑️ Silmek istediğiniz servisi seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_delsrv_"):
            sid = int(data.replace("admin_delsrv_", ""))
            database.delete_service(sid)
            bot.answer_callback_query(call.id, "✅ Servis silindi!", show_alert=True)
            call.data = "admin_delete_service_menu"; admin_callback_yonetici(call)

        elif data == "admin_tickets":
            tickets = database.get_open_tickets(limit=10)
            markup = types.InlineKeyboardMarkup(row_width=1)
            if not tickets:
                markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_main"))
                safe_admin_edit(bot, chat_id, msg_id, "🎫 Açık talep yok.", markup)
            else:
                for t in tickets: markup.add(types.InlineKeyboardButton(f"📩 Talep #{t['id']} (User: {t['user_id']})", callback_data=f"admin_reply_ticket_{t['user_id']}_{t['id']}"))
                markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_main"))
                safe_admin_edit(bot, chat_id, msg_id, "🎫 *Açık Destek Talepleri*", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_reply_ticket_"):
            p = data.split("_"); uid, tid = int(p[3]), int(p[4])
            safe_admin_edit(bot, chat_id, msg_id, f"💬 #{tid} nolu talebe yanıtınızı yazın:", admin_klavyesi())
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_ticket_reply, photo_message_id=msg_id, hedef_id=uid, ticket_id=tid)
            bot.answer_callback_query(call.id)

        elif data == "admin_grizzly":
            b, c = sms_provider.get_balance(), sms_provider.get_crypto_wallet()
            metin = f"🐻 *Grizzly API Bilgisi*\n\n💰 Bakiye: `{b}` USD\n📥 Cüzdan: `{c}`\n\n⚠️ Not: Admin paneline bakiye yüklerken 50 USDT altı işlem yapmayınız."
            safe_admin_edit(bot, chat_id, msg_id, metin, admin_klavyesi())
            bot.answer_callback_query(call.id)

        elif data == "admin_system_control":
            safe_admin_edit(bot, chat_id, msg_id, "⚙️ *Sistem Kontrol Paneli*", system_control_klavyesi())
            bot.answer_callback_query(call.id)

        elif data == "admin_sys_toggle_maint":
            yeni = database.toggle_maintenance_mode()
            bot.answer_callback_query(call.id, f"Bakım Modu: {yeni.upper()}", show_alert=True)
            safe_admin_edit(bot, chat_id, msg_id, "⚙️ *Sistem Kontrol Paneli*", system_control_klavyesi())

        elif data == "admin_create_coupon":
            safe_admin_edit(bot, chat_id, msg_id, "🎟️ *Yeni Kupon*\nFormat: `KOD ÖDÜL LİMİT`\nÖrn: `YENI 50 100`", admin_klavyesi())
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_create_coupon, photo_message_id=msg_id)
            bot.answer_callback_query(call.id)

        elif data == "admin_add_balance":
            safe_admin_edit(bot, chat_id, msg_id, "💰 *Bakiye Ekle*\nFormat: `USER_ID MİKTAR`\nÖrn: `12345 100`", admin_klavyesi())
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_add_balance, photo_message_id=msg_id)
            bot.answer_callback_query(call.id)

        elif data == "admin_broadcast":
            safe_admin_edit(bot, chat_id, msg_id, "📢 *Duyuru Yap*\nMesajınızı yazın. Tüm kullanıcılara gönderilecektir.", admin_klavyesi())
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_broadcast, photo_message_id=msg_id)
            bot.answer_callback_query(call.id)

    # --- NEXT STEP HANDLERS (ZIRHLI) ---
    def process_wizard_add_service(message, srv_code, cc, c_name, flag, cost, msg_id):
        if not is_admin(message.from_user.id): return
        try:
            sell_price = float(message.text.replace(",", "."))
            database.add_new_service(srv_code.upper(), srv_code, cc, c_name, cc, sell_price, flag, cost)
            cleanup_msg(message)
            bot.send_message(message.chat.id, f"✅ *BAŞARILI*\n\n{flag} {c_name} {srv_code.upper()} servisi `{sell_price} TL` fiyatıyla eklendi.", parse_mode="Markdown")
        except:
            bot.send_message(message.chat.id, "❌ Hata: Lütfen sadece sayı giriniz (Örn: 45.5)")

    def process_wizard_edit_price(message, srv_code, cc, msg_id):
        if not is_admin(message.from_user.id): return
        try:
            new_price = float(message.text.replace(",", "."))
            # Mevcut servisi bul
            conn = database.get_db_connection(); cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id FROM services WHERE api_srv = %s AND api_cc = %s", (srv_code, cc))
            srv = cur.fetchone(); conn.close()
            if srv:
                database.update_service_price_by_id(srv['id'], new_price)
                cleanup_msg(message)
                bot.send_message(message.chat.id, f"✅ *FİYAT GÜNCELLENDİ*\n\n{srv_code.upper()} yeni fiyatı: `{new_price} TL`", parse_mode="Markdown")
            else:
                bot.send_message(message.chat.id, "❌ Bu servis sistemde kayıtlı değil.")
        except:
            bot.send_message(message.chat.id, "❌ Hata: Geçersiz fiyat formatı.")

    def process_ticket_reply(message, photo_message_id, hedef_id, ticket_id):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id); cleanup_msg(message)
        try:
            bot.send_message(hedef_id, f"📩 *Destek Yanıtı:* \n\n{message.text}", parse_mode="Markdown")
            database.close_ticket_by_id(ticket_id)
            bot.send_message(message.chat.id, f"✅ Talep #{ticket_id} yanıtlandı ve kapatıldı.")
        except: bot.send_message(message.chat.id, "❌ Kullanıcıya ulaşılamadı.")

    def process_create_coupon(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id); cleanup_msg(message)
        try:
            p = message.text.split(); kod, odul, limit = p[0].upper(), float(p[1]), int(p[2])
            if database.create_coupon(kod, odul, limit): bot.send_message(message.chat.id, f"✅ Kupon Oluşturuldu: `{kod}`")
        except: bot.send_message(message.chat.id, "❌ Hata! Format: `KOD ÖDÜL LİMİT`")

    def process_add_balance(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id); cleanup_msg(message)
        try:
            p = message.text.split(); uid, mkt = int(p[0]), float(p[1])
            database.update_balance(uid, mkt)
            bot.send_message(message.chat.id, f"✅ {uid} ID'li hesaba {mkt} TL eklendi.")
            try: bot.send_message(uid, f"🎉 Hesabınıza {mkt} TL tanımlandı.")
            except: pass
        except: bot.send_message(message.chat.id, "❌ Hata! Format: `USER_ID MİKTAR`")

    def process_broadcast(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id); cleanup_msg(message)
        users = database.get_all_users()
        for k in users:
            try: bot.send_message(k['user_id'], f"📢 *Duyuru*\n\n{message.text}", parse_mode="Markdown")
            except: pass
        bot.send_message(message.chat.id, "✅ Duyuru tüm kullanıcılara gönderildi.")
