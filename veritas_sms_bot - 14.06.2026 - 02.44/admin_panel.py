import telebot
from telebot import types
import os
import database
from providers import sms_provider

def register_admin_handlers(bot):
    """Gelişmiş Masterclass Admin Panelini entegre eder."""

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
            types.InlineKeyboardButton("🛑 Kapat (Sunucudan Kapat)", callback_data="admin_sys_shutdown"),
            types.InlineKeyboardButton("🔙 Admin Menü", callback_data="admin_main")
        )
        return markup

    def safe_admin_edit(chat_id, message_id, text, markup=None):
        try:
            bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup, parse_mode="Markdown")
                except: pass

    @bot.message_handler(commands=['admin'])
    def admin_panel_komutu(message):
        if not is_admin(message.from_user.id): return
            
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass

        metin = "🛡️ *Veritas SMS Yönetim Paneli (Masterclass)*\n\nLütfen işlem seçin:"
        try:
            with open("veritas_sms_logo_yatay.png", "rb") as photo:
                bot.send_photo(message.chat.id, photo, caption=metin, reply_markup=admin_klavyesi(), parse_mode="Markdown")
        except FileNotFoundError:
            bot.send_message(message.chat.id, metin, reply_markup=admin_klavyesi(), parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
    def admin_callback_yonetici(call):
        if not is_admin(call.from_user.id): return

        chat_id = call.message.chat.id
        msg_id = call.message.message_id
        data = call.data

        if data == "admin_close":
            bot.delete_message(chat_id, msg_id)
            
        elif data == "admin_main":
            safe_admin_edit(chat_id, msg_id, "🛡️ *Veritas SMS Yönetim Paneli (Masterclass)*\n\nLütfen işlem seçin:", admin_klavyesi())
            bot.answer_callback_query(call.id)

        elif data == "admin_stats":
            stats = database.get_statistics()
            m = database.get_maintenance_mode()
            metin = (
                "📊 *Sistem İstatistikleri*\n\n"
                f"👥 *Toplam Kullanıcı:* {stats['total_users']}\n"
                f"💰 *Toplam Bakiyeler:* {stats['total_balance']} TL\n"
                f"📱 *Satılan Numara:* {stats['total_sold']}\n"
                f"🚧 *Bakım Modu:* {'Açık' if m == 'on' else 'Kapalı'}"
            )
            safe_admin_edit(chat_id, msg_id, metin, admin_klavyesi())
            bot.answer_callback_query(call.id)
            
        elif data == "admin_user_list":
            users = database.get_all_users()
            markup = types.InlineKeyboardMarkup(row_width=1)
            for u in users[-10:]:
                username = u['username'] or "Yok"
                btn_text = f"👤 @{username} ({u['balance']} TL)"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"admin_usrdet_{u['user_id']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_main"))
            safe_admin_edit(chat_id, msg_id, "👥 *Kullanıcı İnceleme Listesi*\n\nDetay görmek için tıklayın:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_usrdet_"):
            target_uid = int(data.replace("admin_usrdet_", ""))
            user = next((u for u in database.get_all_users() if u['user_id'] == target_uid), None)
            if not user: return
            drm = "🚫 Yasaklı" if user['is_banned'] else "✅ Aktif"
            metin = f"🕵️‍♂️ *Profil: @{user['username']}*\n🆔 ID: `{user['user_id']}`\n💳 Bakiye: {user['balance']} TL\n🛡️ Durum: {drm}"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("📱 Satın Alımları", callback_data=f"admin_usrhis_num_{target_uid}"),
                       types.InlineKeyboardButton("❌ İptal/İadeleri", callback_data=f"admin_usrhis_cnl_{target_uid}"))
            markup.add(types.InlineKeyboardButton("🔙 Kullanıcı Listesi", callback_data="admin_user_list"))
            safe_admin_edit(chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_usrhis_"):
            parts = data.split("_")
            action, target_uid = parts[2], int(parts[3])
            if action == "num":
                history = database.get_user_history(target_uid, limit=5)
                metin = "📱 *Son 5 Satın Alım*\n\n"
                if not history: metin += "_İşlem yok._"
                else:
                    for i in history: metin += f"🔹 {i[0]} | `{i[1]}`\n💰 {i[2]} TL | 📅 {i[3].strftime('%d.%m %H:%M')}\n\n"
            else: metin = "❌ *İptal/İade Kaydı Bulunmuyor.*"
            markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("🔙 Profil", callback_data=f"admin_usrdet_{target_uid}"))
            safe_admin_edit(chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

        elif data == "admin_create_coupon":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("📋 Aktif Kuponlar", callback_data="admin_list_coupons"),
                       types.InlineKeyboardButton("➕ Yeni Kupon", callback_data="admin_trigger_create_coupon"),
                       types.InlineKeyboardButton("🔙 Menü", callback_data="admin_main"))
            safe_admin_edit(chat_id, msg_id, "🎟️ *Kupon Yönetimi*", markup)
            bot.answer_callback_query(call.id)

        elif data == "admin_list_coupons":
            kuponlar = database.get_all_coupons()
            markup = types.InlineKeyboardMarkup(row_width=2)
            if not kuponlar:
                markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_create_coupon"))
                safe_admin_edit(chat_id, msg_id, "🎟️ Kupon bulunmuyor.", markup)
            else:
                metin = "🎟️ *Aktif Kuponlar*\n\n"
                for k in kuponlar:
                    metin += f"🔹 `{k['code']}` | 💰 {k['reward_amount']} TL | 📊 {k['used_count']}/{k['usage_limit']}\n"
                    markup.add(types.InlineKeyboardButton(f"🗑️ Sil: {k['code']}", callback_data=f"admin_del_coupon_{k['code']}"))
                markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_create_coupon"))
                safe_admin_edit(chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_del_coupon_"):
            code = data.replace("admin_del_coupon_", "")
            database.delete_coupon(code)
            bot.answer_callback_query(call.id, f"✅ Silindi: {code}", show_alert=True)
            call.data = "admin_list_coupons"; admin_callback_yonetici(call)

        elif data == "admin_trigger_create_coupon":
            safe_admin_edit(chat_id, msg_id, "🎟️ *Yeni Kupon*\nFormat: `KOD ÖDÜL LİMİT`\nÖrn: `YENI 50 100`", admin_klavyesi())
            bot.register_next_step_handler(call.message, process_create_coupon, photo_message_id=msg_id)
            bot.answer_callback_query(call.id)

        elif data == "admin_add_balance":
            safe_admin_edit(chat_id, msg_id, "💰 *Bakiye Ekle*\nFormat: `USER_ID MİKTAR`\nÖrn: `12345 100`", admin_klavyesi())
            bot.register_next_step_handler(call.message, process_add_balance, photo_message_id=msg_id)
            bot.answer_callback_query(call.id)

        elif data == "admin_broadcast":
            safe_admin_edit(chat_id, msg_id, "📢 *Duyuru Yap*\nMesajınızı yazın. Tüm kullanıcılara gönderilecektir.", admin_klavyesi())
            bot.register_next_step_handler(call.message, process_broadcast, photo_message_id=msg_id)
            bot.answer_callback_query(call.id)

        elif data == "admin_ban_menu":
            safe_admin_edit(chat_id, msg_id, "🚫 *Ban Yönetimi*\n`BAN USER_ID` veya `UNBAN USER_ID`", admin_klavyesi())
            bot.register_next_step_handler(call.message, process_ban, photo_message_id=msg_id)
            bot.answer_callback_query(call.id)

        elif data == "admin_grizzly":
            bakiye, cuzdan = sms_provider.get_balance(), sms_provider.get_crypto_wallet()
            metin = f"🐻 *Grizzly Durumu*\n\n💰 Bakiye: `{bakiye}` USD\n📥 Cüzdan: `{cuzdan}`"
            safe_admin_edit(chat_id, msg_id, metin, admin_klavyesi())
            bot.answer_callback_query(call.id)

        elif data == "admin_menu_fiyatlar":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("➕ Servis Ekle", callback_data="admin_add_service"),
                       types.InlineKeyboardButton("🗑️ Servis Sil", callback_data="admin_delete_service_menu"),
                       types.InlineKeyboardButton("💲 Fiyat Güncelle", callback_data="admin_edit_price_menu"),
                       types.InlineKeyboardButton("🔙 Menü", callback_data="admin_main"))
            safe_admin_edit(chat_id, msg_id, "🚀 *Servis Yönetim Merkezi*", markup)
            bot.answer_callback_query(call.id)

        elif data == "admin_add_service":
            import config
            markup = types.InlineKeyboardMarkup(row_width=2)
            for api_kodu, servis_adi in config.GRIZZLY_SERVICES.items():
                markup.add(types.InlineKeyboardButton(f"📱 {servis_adi}", callback_data=f"admin_addsrv_{api_kodu}_0"))
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_menu_fiyatlar"))
            safe_admin_edit(chat_id, msg_id, "➕ *Servis Ekleme Asistanı*", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_addsrv_"):
            import config
            parts = data.split('_')
            api_srv, page = parts[2], int(parts[3]) if len(parts) > 3 else 0
            srv_name = config.GRIZZLY_SERVICES.get(api_srv, api_srv)
            items = database.get_paginated_countries(page=page, limit=21)
            total = database.get_total_country_pages(limit=21)
            markup = types.InlineKeyboardMarkup(row_width=3)
            buttons = [types.InlineKeyboardButton(f"{c['flag']} {c['country_name'][:12]}", callback_data=f"admin_selcc_{api_srv}_{c['country_code']}") for c in items]
            markup.add(*buttons)
            nav = [types.InlineKeyboardButton("⬅️" if page > 0 else "🚫", callback_data=f"admin_addsrv_{api_srv}_{page-1}" if page > 0 else "ignore"),
                   types.InlineKeyboardButton(f"📄 {page+1}/{total}", callback_data="ignore"),
                   types.InlineKeyboardButton("➡️" if page < total-1 else "🚫", callback_data=f"admin_addsrv_{api_srv}_{page+1}" if page < total-1 else "ignore")]
            markup.row(*nav); markup.row(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_menu_fiyatlar"))
            safe_admin_edit(chat_id, msg_id, f"📱 Servis: *{srv_name}*\n🌍 Ülke seçin (S: {page+1}):", markup)
            bot.answer_callback_query(call.id)

        elif data == "ignore": bot.answer_callback_query(call.id)

        elif data.startswith("admin_selcc_"):
            import config
            parts = data.split('_')
            api_srv, api_cc = parts[2], parts[3]
            srv_name = config.GRIZZLY_SERVICES.get(api_srv, api_srv)
            info = database.get_country_info(api_cc)
            canli = sms_provider.get_all_prices_and_stocks(api_srv, api_cc)
            f_metni = "\n📊 *Envanter:*\n" + "".join([f"🔹 `${float(f):.2f}` ➔ {a} Adet\n" for f, a in canli.items()]) if canli else "\n⚠️ Stok yok.\n"
            metin = f"✅ Seçilen: *{srv_name} - {info['flag']} {info['country_name']}*\n{f_metni}\n🛒 Maks Alış ($) yazın:"
            markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_cancel_step"))
            safe_admin_edit(chat_id, msg_id, metin, markup)
            bot.register_next_step_handler(call.message, process_wizard_api_price, api_srv=api_srv, srv_name=srv_name, api_cc=api_cc, country_name=info['country_name'], msg_id=msg_id)
            bot.answer_callback_query(call.id)

        elif data == "admin_cancel_step":
            bot.clear_step_handler_by_chat_id(chat_id)
            call.data = "admin_menu_fiyatlar"; admin_callback_yonetici(call)

        elif data == "admin_delete_service_menu":
            aktif = database.get_active_services()
            markup = types.InlineKeyboardMarkup(row_width=2)
            for s in set(aktif): markup.add(types.InlineKeyboardButton(s.upper(), callback_data=f"admin_delsrv_{s}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_menu_fiyatlar"))
            safe_admin_edit(chat_id, msg_id, "🗑 *Servis Silme*\nKategori seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_delsrv_"):
            srv = data.replace("admin_delsrv_", "")
            ulkeler = database.get_countries_for_service(srv)
            markup = types.InlineKeyboardMarkup(row_width=2)
            görülen = set()
            for u in ulkeler:
                if u['country_code'] not in görülen:
                    görülen.add(u['country_code'])
                    info = database.get_country_info(u['country_code'])
                    markup.add(types.InlineKeyboardButton(f"{info['flag']} {u['country_name']}", callback_data=f"admin_delcc_{srv}_{u['country_code']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_delete_service_menu"))
            safe_admin_edit(chat_id, msg_id, f"🌍 *{srv.upper()}* için ülke seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_delcc_"):
            parts = data.split('_')
            srv, cc = parts[2], parts[3]
            kademeler = database.get_countries_for_service(srv)
            info = database.get_country_info(cc)
            markup = types.InlineKeyboardMarkup(row_width=1)
            for u in kademeler:
                if u['country_code'] == cc:
                    markup.add(types.InlineKeyboardButton(f"🗑 Sil: {u['price']} TL (Maliyet: ${u['api_max_price']})", callback_data=f"admin_del_srv_{u['id']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data=f"admin_delsrv_{srv}"))
            safe_admin_edit(chat_id, msg_id, f"🗑 *SİLME:* {info['flag']} {info['country_name']}", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_del_srv_"):
            sid = int(data.replace("admin_del_srv_", ""))
            svc = database.get_service_by_id(sid)
            if svc:
                database.delete_service(sid)
                bot.answer_callback_query(call.id, "✅ Silindi.", show_alert=True)
                call.data = f"admin_delcc_{svc['service_name']}_{svc['country_code']}"
            else: call.data = "admin_delete_service_menu"
            admin_callback_yonetici(call)

        elif data == "admin_edit_price_menu":
            aktif = database.get_active_services()
            markup = types.InlineKeyboardMarkup(row_width=1)
            for s in aktif: markup.add(types.InlineKeyboardButton(f"📱 {s}", callback_data=f"admin_srv_{s}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_menu_fiyatlar"))
            safe_admin_edit(chat_id, msg_id, "💲 *Fiyat Güncelleme*", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_srv_"):
            srv = data.replace("admin_srv_", "")
            ulkeler = database.get_countries_for_service(srv)
            markup = types.InlineKeyboardMarkup(row_width=2)
            görülen = set()
            for u in ulkeler:
                if u['country_code'] not in görülen:
                    görülen.add(u['country_code'])
                    info = database.get_country_info(u['country_code'])
                    markup.add(types.InlineKeyboardButton(f"{info['flag']} {u['country_name']}", callback_data=f"admin_tier_edit_{srv}_{u['country_code']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_menu_fiyatlar"))
            safe_admin_edit(chat_id, msg_id, f"📱 *Kategori: {srv}*", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_tier_edit_"):
            parts = data.split('_')
            srv, cc = parts[3], parts[4]
            kademeler, info = database.get_countries_for_service(srv), database.get_country_info(cc)
            canli = sms_provider.get_all_prices_and_stocks(srv, cc)
            f_metni = "\n📊 *Grizzly Havuz:*\n" + "".join([f"🔹 `${float(f):.2f}` ➔ {a} Adet\n" for f, a in canli.items()]) if canli else "\n⚠️ Veri yok.\n"
            markup = types.InlineKeyboardMarkup(row_width=1)
            for u in kademeler:
                if u['country_code'] == cc:
                    markup.add(types.InlineKeyboardButton(f"✏️ {u['price']} TL (Maliyet: ${u['api_max_price']})", callback_data=f"admin_prc_{u['id']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data=f"admin_srv_{srv}"))
            safe_admin_edit(chat_id, msg_id, f"{info['flag']} *Fiyat Düzenle: {cc}*\n{f_metni}", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_prc_"):
            sid = int(data.replace("admin_prc_", ""))
            svc = database.get_service_by_id(sid)
            if svc:
                metin = f"{svc['flag']} *{svc['service_name']} - {svc['country_name']}*\n\n🏷️ *YENİ SATIŞ FİYATINI (TL)* yazın:"
                safe_admin_edit(chat_id, msg_id, metin, admin_klavyesi())
                bot.register_next_step_handler(call.message, process_nested_service_price, photo_message_id=msg_id, service_id=sid)
            bot.answer_callback_query(call.id)

        elif data == "admin_system_control":
            safe_admin_edit(chat_id, msg_id, "⚙️ *Sistem Kontrol Paneli*", system_control_klavyesi())
            bot.answer_callback_query(call.id)

        elif data == "admin_sys_toggle_maint":
            yeni = database.toggle_maintenance_mode()
            bot.answer_callback_query(call.id, f"Bakım Modu: {yeni.upper()}", show_alert=True)
            safe_admin_edit(chat_id, msg_id, "⚙️ *Sistem Kontrol Paneli*", system_control_klavyesi())

    # --- NEXT STEP HANDLERS (ZIRHLI) ---
    def cleanup_msg(message):
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass

    def process_ticket_reply(message, photo_message_id, hedef_id):
        if not is_admin(message.from_user.id): return
        cleanup_msg(message)
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("💬 Yanıtla", callback_data="user_reply_ticket"))
        bot.send_message(hedef_id, f"📩 *Destek Yanıtı:* \n\n{message.text}", reply_markup=markup, parse_mode="Markdown")
        bot.send_message(message.chat.id, "✅ İletildi.")

    def process_create_coupon(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        cleanup_msg(message)
        try:
            p = message.text.split(); kod, odul, limit = p[0].upper(), float(p[1]), int(p[2])
            if database.create_coupon(kod, odul, limit): safe_admin_edit(message.chat.id, photo_message_id, f"✅ Kupon: `{kod}`", admin_klavyesi())
        except: safe_admin_edit(message.chat.id, photo_message_id, "❌ Hata!", admin_klavyesi())

    def process_add_balance(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        cleanup_msg(message)
        try:
            p = message.text.split(); uid, mkt = int(p[0]), float(p[1])
            database.update_balance(uid, mkt)
            safe_admin_edit(message.chat.id, photo_message_id, "✅ Bakiye Eklendi.", admin_klavyesi())
            try: bot.send_message(uid, f"🎉 Hesabınıza {mkt} TL tanımlandı.")
            except: pass
        except: safe_admin_edit(message.chat.id, photo_message_id, "❌ Hata!", admin_klavyesi())

    def process_broadcast(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        cleanup_msg(message)
        database.add_announcement(message.text)
        users = database.get_all_users()
        for k in users:
            try: bot.send_message(k['user_id'], f"📢 *Duyuru*\n\n{message.text}", parse_mode="Markdown")
            except: pass
        safe_admin_edit(message.chat.id, photo_message_id, "✅ Duyuru bitti.", admin_klavyesi())

    def process_ban(message, photo_message_id):
        if not is_admin(message.from_user.id): return
        cleanup_msg(message)
        try:
            p = message.text.split(); islem, uid = p[0].upper(), int(p[1])
            if islem == "BAN": database.ban_user(uid)
            elif islem == "UNBAN": database.unban_user(uid)
            safe_admin_edit(message.chat.id, photo_message_id, f"✅ İşlem Tamam: {uid}", admin_klavyesi())
        except: safe_admin_edit(message.chat.id, photo_message_id, "❌ Hata!", admin_klavyesi())

    def process_nested_service_price(message, photo_message_id, service_id):
        if not is_admin(message.from_user.id): return
        cleanup_msg(message)
        try:
            f = float(message.text.replace(',', '.'))
            database.update_service_price_by_id(service_id, f)
            safe_admin_edit(message.chat.id, photo_message_id, f"✅ Yeni Fiyat: `{f}` TL", admin_klavyesi())
        except: safe_admin_edit(message.chat.id, photo_message_id, "❌ Sayı girin.", admin_klavyesi())

    def process_wizard_api_price(message, api_srv, srv_name, api_cc, country_name, msg_id):
        if not is_admin(message.from_user.id): return
        try:
            api_cost = float(message.text.replace('$', '').replace(',', '.').strip()); cleanup_msg(message)
            metin = f"💰 Maks Alış: `${api_cost}`\nŞimdi *Satış Fiyatını (TL)* yazın:"
            markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_cancel_step"))
            safe_admin_edit(message.chat.id, msg_id, metin, markup)
            bot.register_next_step_handler(message, process_wizard_sell_price, api_srv=api_srv, srv_name=srv_name, api_cc=api_cc, country_name=country_name, msg_id=msg_id, api_cost=api_cost)
        except: bot.register_next_step_handler(message, process_wizard_api_price, api_srv=api_srv, srv_name=srv_name, api_cc=api_cc, country_name=country_name, msg_id=msg_id)

    def process_wizard_sell_price(message, api_srv, srv_name, api_cc, country_name, msg_id, api_cost):
        if not is_admin(message.from_user.id): return
        try:
            price = float(message.text.replace(',', '.')); cleanup_msg(message)
            info = database.get_country_info(api_cc)
            database.add_new_service(srv_name, api_srv, api_cc, country_name, api_cc, price, info['flag'], api_cost)
            safe_admin_edit(message.chat.id, msg_id, f"✅ Eklendi: {info['flag']} {country_name}", admin_klavyesi())
        except: bot.register_next_step_handler(message, process_wizard_sell_price, api_srv=api_srv, srv_name=srv_name, api_cc=api_cc, country_name=country_name, msg_id=msg_id, api_cost=api_cost)
