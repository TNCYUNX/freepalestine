# -*- coding: utf-8 -*-
import telebot
from telebot import types
import os
import database
import math
from providers import grizzly_provider

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
        types.InlineKeyboardButton("🎟️ Kupon Yönetimi", callback_data="admin_coupon_menu"),
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
    """Admin ana menü ve temel yönetim işlemlerini yönetir. (MODÜLER ALTYAPI)"""

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
    def admin_main_callback_router(call):
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
            
            # Canlı Kur Çekimi ve TL Hesaplama
            try:
                import requests
                # Varsayılan (yedek) kurlar
                k_usdt = 46.0
                k_trx = 15.0
                
                # Binance üzerinden canlı kurlar
                r_u = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=USDTTRY", timeout=3)
                if r_u.status_code == 200: k_usdt = float(r_u.json().get("price", 46.0))
                
                r_t = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=TRXTRY", timeout=3)
                if r_t.status_code == 200: k_trx = float(r_t.json().get("price", 15.0))
                
                t_yuklenen_tl = (t_usdt * k_usdt) + (t_trx * k_trx)
            except:
                t_yuklenen_tl = 0.0

            metin = (
                "📊 *Sistem İstatistikleri*\n\n"
                f"👥 *Kullanıcı:* {stats['total_users']}\n"
                f"💰 *Kullanıcı Bakiyeleri:* {stats['total_balance']} TL\n"
                f"📱 *Satılan Numara:* {stats['total_sold']}\n"
                "--------------------\n"
                f"🟢 *Toplam USDT:* {t_usdt:.2f} $\n"
                f"🔴 *Toplam TRX:* {t_trx:.2f} TRX\n"
                f"💳 *Toplam Yüklenen:* {t_yuklenen_tl:.2f} TL\n"
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
            
            if user['is_banned']:
                drm = f"🚫 Yasaklı\n└ Tip {user.get('ban_type', 0)}: {user.get('ban_reason', 'Belirsiz')}\n└ Girdi: `{user.get('banned_input', 'Yok')}`"
            else:
                drm = "✅ Aktif"
                
            metin = f"🕵️‍♂️ *Profil: @{user['username']}*\n🆔 ID: `{user['user_id']}`\n💳 Bakiye: {user['balance']} TL\n🛡️ Durum: {drm}"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("📱 Alımlar", callback_data=f"admin_usrhis_num_{uid}"),
                       types.InlineKeyboardButton("💳 Ödemeler", callback_data=f"admin_usrhis_pay_{uid}"))
            if user['is_banned']: markup.add(types.InlineKeyboardButton("✅ Yasağı Kaldır", callback_data=f"admin_setban_0_{uid}"))
            else: markup.add(types.InlineKeyboardButton("🚫 Yasakla", callback_data=f"admin_setban_1_{uid}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_user_list"))
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_setban_"):
            p = data.split("_"); act, uid = p[2], int(p[3])
            if act == "1": database.ban_user(uid, ban_type=2, reason="Admin Paneli Manuel Ban", input_data="Admin İşlemi")
            else:
                database.unban_user(uid)
                from providers.security_manager import security
                security.BANNED_CACHE.discard(uid)
            # Detay ekranını yenilemek için callback'i tekrar tetikle
            call.data = f"admin_usrdet_{uid}"
            admin_main_callback_router(call)
            bot.answer_callback_query(call.id, "Kullanıcı durumu güncellendi.")

        elif data.startswith("admin_usrhis_"):
            p = data.split("_"); act, uid = p[2], int(p[3])
            try:
                # database.py içindeki get_user_history'den genişletilmiş veri alalım
                conn = database.get_db_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT action_type, service_name, fake_number, price, date, status FROM history WHERE user_id = %s ORDER BY id DESC LIMIT 20", (uid,))
                hist = cursor.fetchall()
                conn.close()
            except: hist = []

            metin = "📜 *Kullanıcı Geçmişi*\n\n"
            logs = []
            if act == "num":
                metin += "📱 *Satın Alınan Numaralar (Son 20):*\n"
                logs = [i for i in hist if i['price'] > 0]
                for i in logs:
                    drm = i.get('status', '✅')
                    metin += f"🔹 {i['service_name']} | `+{i['fake_number']}` | {i['price']} TL | {drm}\n"
            else:
                metin += "💳 *Yükleme ve Ödeme Kayıtları (Son 20):*\n"
                logs = [i for i in hist if i['price'] <= 0]
                for i in logs:
                    metin += f"📥 {i['service_name']} | {abs(i['price'])} TL | 📅 {i['date'].strftime('%d.%m %H:%M')}\n"

            if not logs: metin += "_Henüz bir kayıt bulunmamaktadır._"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Profil Ekranına Dön", callback_data=f"admin_usrdet_{uid}"))
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

        elif data == "admin_menu_fiyatlar":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("➕ Servis Ekle", callback_data="admin_add_srv_start"),
                       types.InlineKeyboardButton("🗑️ Servis Sil", callback_data="admin_del_price_start"),
                       types.InlineKeyboardButton("💲 Fiyat Güncelle", callback_data="admin_edit_price_start"),
                       types.InlineKeyboardButton("🔙 Ana Menü", callback_data="admin_main"))
            safe_admin_edit(bot, chat_id, msg_id, "🚀 *Servis ve Fiyat Yönetimi*", markup)
            bot.answer_callback_query(call.id)

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
            b, c = grizzly_provider.get_balance(), grizzly_provider.get_crypto_wallet()
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

        elif data == "admin_coupon_menu":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("➕ Yeni Kupon Oluştur", callback_data="admin_create_coupon_start"),
                types.InlineKeyboardButton("📋 Mevcut Kuponları Listele", callback_data="admin_list_coupons"),
                types.InlineKeyboardButton("🔙 Admin Menü", callback_data="admin_main")
            )
            safe_admin_edit(bot, chat_id, msg_id, "🎟️ *Kupon Yönetim Merkezi*\n\nLütfen yapmak istediğiniz işlemi seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data == "admin_create_coupon_start":
            safe_admin_edit(bot, chat_id, msg_id, "🎟️ *Yeni Kupon Oluşturma Sihirbazı*\n\nFormat: `KOD ÖDÜL LİMİT`\nÖrn: `YENI30 30 100`\n\n✍️ Lütfen oluşturmak istediğiniz kupon bilgilerini bu sohbete yazın:", admin_klavyesi())
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_create_coupon, photo_message_id=msg_id)
            bot.answer_callback_query(call.id)

        elif data == "admin_list_coupons":
            coupons = database.get_all_coupons()
            metin = "📋 *Sistemde Kayıtlı Kuponlar*\n\n"
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            if not coupons:
                metin += "_Henüz hiç kupon oluşturulmamış._"
            else:
                for c in coupons:
                    # Metin listesine detayları ekle
                    metin += f"🎟️ *Kod:* `{c['code']}`\n└ 💰 Ödül: {c['reward_amount']} TL | 📊 Limit: {c['used_count']}/{c['usage_limit']}\n───────────────────\n"
                    # Her kupon için silme butonu ekle
                    markup.add(types.InlineKeyboardButton(f"🗑️ {c['code']} Sil", callback_data=f"admin_del_cpn_{c['code']}"))
            
            markup.add(types.InlineKeyboardButton("🔙 Kupon Menüsüne Dön", callback_data="admin_coupon_menu"))
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_del_cpn_"):
            code = data.replace("admin_del_cpn_", "")
            if database.delete_coupon(code):
                bot.answer_callback_query(call.id, f"✅ {code} kuponu başarıyla silindi.", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "❌ Kupon silinirken bir hata oluştu.", show_alert=True)
            
            # Listeyi yenilemek için aynı callback'i tetikle
            call.data = "admin_list_coupons"
            admin_main_callback_router(call)

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

        elif data == "admin_ban_menu":
            safe_admin_edit(bot, chat_id, msg_id, "🚫 *Ban Yönetimi*\n`BAN USER_ID` veya `UNBAN USER_ID`", admin_klavyesi())
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_ban, photo_message_id=msg_id)
            bot.answer_callback_query(call.id)

    # --- NEXT STEP HANDLERS ---
    def process_wizard_edit_price(message, service_id, photo_message_id):
        if not is_admin(message.from_user.id): return
        try:
            new_price = float(message.text.replace(",", "."))
            database.update_service_price_by_id(service_id, new_price)
            cleanup_msg(message)
            bot.send_message(message.chat.id, f"✅ *FİYAT GÜNCELLENDİ*\n\nYeni satış fiyatı: `{new_price} TL`")
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
            if database.create_coupon(kod, odul, limit):
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 Kupon Menüsüne Dön", callback_data="admin_coupon_menu"))
                safe_admin_edit(bot, message.chat.id, photo_message_id, f"✅ Kupon Başarıyla Oluşturuldu: `{kod}`", markup)
        except: 
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Kupon Menüsüne Dön", callback_data="admin_coupon_menu"))
            safe_admin_edit(bot, message.chat.id, photo_message_id, "❌ Hata! Format: `KOD ÖDÜL LİMİT`", markup)

    def process_add_balance(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id); cleanup_msg(message)
        try:
            p = message.text.split(); uid, mkt = int(p[0]), float(p[1])
            database.update_balance(uid, mkt)
            database.add_to_history(uid, 5, "Bakiye", "Admin Paneli", -mkt, status="✅ BAŞARILI")
            safe_admin_edit(bot, message.chat.id, photo_message_id, f"✅ {uid} ID'li hesaba {mkt} TL eklendi.", admin_klavyesi())
            try: bot.send_message(uid, f"🎉 Hesabınıza {mkt} TL tanımlandı.")
            except: pass
        except: safe_admin_edit(bot, message.chat.id, photo_message_id, "❌ Hata! Format: `USER_ID MİKTAR`", admin_klavyesi())

    def process_broadcast(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id); cleanup_msg(message)
        database.add_announcement(message.text)
        users = database.get_all_users()
        for k in users:
            try: bot.send_message(k['user_id'], f"📢 *Duyuru*\n\n{message.text}", parse_mode="Markdown")
            except: pass
        safe_admin_edit(bot, message.chat.id, photo_message_id, "✅ Duyuru gönderildi.", admin_klavyesi())

    def process_ban(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        bot.clear_step_handler_by_chat_id(message.chat.id); cleanup_msg(message)
        try:
            p = message.text.split(); islem, uid = p[0].upper(), int(p[1])
            if islem == "BAN": database.ban_user(uid, ban_type=2, reason="Admin Paneli Manuel Ban", input_data="Admin İşlemi")
            elif islem == "UNBAN":
                database.unban_user(uid)
                from providers.security_manager import security
                security.BANNED_CACHE.discard(uid)
            safe_admin_edit(bot, message.chat.id, photo_message_id, f"✅ İşlem Başarılı: {islem} {uid}", admin_klavyesi())
        except: safe_admin_edit(bot, message.chat.id, photo_message_id, "❌ Hata! Format: `BAN/UNBAN ID`", admin_klavyesi())