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

def show_ban_warning_list_panel(bot, chat_id, photo_message_id, page=1):
    users = database.get_banned_and_warned_users()
    
    per_page = 5
    total_pages = math.ceil(len(users) / per_page) if users else 1
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx] if users else []
    
    metin = "🛡️ *Uyarı & Ban Yönetim Paneli*\n\n"
    if not users:
        metin += "Şu anda uyarısı olan veya yasaklanmış kullanıcı bulunmuyor."
    else:
        metin += f"Uyarısı veya Yasağı olan kullanıcılar (Sayfa {page}/{total_pages}):\n\n"
        for u in page_users:
            status = "🚫 Yasaklı" if u['is_banned'] else f"⚠️ Uyarı: {u['warnings']}/3"
            username_str = f"@{u['username']}" if u['username'] else "Kullanıcı adı yok"
            metin += f"👤 {username_str} (`{u['user_id']}`)\n└ Durum: {status}\n\n"
            
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Kullanıcılar için butonlar ekleyelim
    for u in page_users:
        label = f"👤 @{u['username'] or u['user_id']} ({'Ban' if u['is_banned'] else f'Warn:{u['warnings']}'})"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"admin_manage_user_{u['user_id']}"))
        
    # Sayfalama Butonları
    nav_buttons = []
    if page > 1:
        nav_buttons.append(types.InlineKeyboardButton("◀️ Geri", callback_data=f"admin_ban_list_page_{page-1}"))
    if page < total_pages:
        nav_buttons.append(types.InlineKeyboardButton("İleri ▶️", callback_data=f"admin_ban_list_page_{page+1}"))
    if nav_buttons:
        markup.row(*nav_buttons)
        
    markup.add(types.InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_main"))
    
    safe_admin_edit(bot, chat_id, photo_message_id, metin, markup)

def show_user_ban_management_panel(bot, chat_id, photo_message_id, uid):
    # Kullanıcı verilerini veritabanından çekelim (Güvenli)
    conn = database.get_db_connection()
    if not conn: return
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username, balance, is_banned, ban_reason, warnings FROM users WHERE user_id = %s", (uid,))
        user = cursor.fetchone()
    except Exception:
        user = None
    finally:
        conn.close()
    
    if not user:
        safe_admin_edit(bot, chat_id, photo_message_id, f"❌ Hata: `{uid}` ID'li kullanıcı veritabanında bulunamadı.", admin_klavyesi())
        return
        
    status_label = "🚫 YASAKLI" if user['is_banned'] else "✅ AKTİF"
    reason_label = f"\n└ 📝 Sebep: `{user['ban_reason']}`" if user['is_banned'] else ""
    
    metin = (
        "🛡️ *Uyarı ve Ban Kontrol Paneli*\n\n"
        f"👤 *Kullanıcı:* @{user['username'] or 'Yok'}\n"
        f"🆔 *Telegram ID:* `{uid}`\n"
        f"💳 *Bakiye:* `{user['balance']} TL`\n"
        f"⚠️ *Uyarı Sayısı:* `{user['warnings']} / 3`\n"
        f"🛡️ *Durum:* {status_label}{reason_label}"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Uyarı Ekle", callback_data=f"admin_warn_add_{uid}"),
        types.InlineKeyboardButton("➖ Uyarı Sıfırla", callback_data=f"admin_warn_reset_{uid}")
    )
    if user['is_banned']:
        markup.add(types.InlineKeyboardButton("✅ Yasağı Kaldır (Unban)", callback_data=f"admin_unban_user_{uid}"))
    else:
        markup.add(types.InlineKeyboardButton("🚫 Kullanıcıyı Yasakla (Ban)", callback_data=f"admin_ban_user_{uid}"))
        
    markup.row(
        types.InlineKeyboardButton("🔙 Liste", callback_data="admin_ban_menu"),
        types.InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_main")
    )
    safe_admin_edit(bot, chat_id, photo_message_id, metin, markup)

def admin_klavyesi():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 İstatistikler", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 Kullanıcı Listesi", callback_data="admin_user_list")
    )
    markup.add(
        types.InlineKeyboardButton("🎟️ Kupon Yönetimi", callback_data="admin_coupon_menu"),
        types.InlineKeyboardButton("🛡️ Uyarı/Ban Yönetimi", callback_data="admin_ban_menu")
    )
    markup.add(
        types.InlineKeyboardButton("💰 Bakiye Ekle", callback_data="admin_add_balance"),
        types.InlineKeyboardButton("📢 Duyuru Yap", callback_data="admin_broadcast")
    )
    markup.row(
        types.InlineKeyboardButton("🚀 Servis Yönetimi", callback_data="admin_menu_fiyatlar"),
        types.InlineKeyboardButton("📊 Fiyat/Stok Karşılaştır", callback_data="admin_compare_start")
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ Sistem Kontrol", callback_data="admin_system_control"),
        types.InlineKeyboardButton("🎫 Destek Talepleri", callback_data="admin_tickets")
    )
    markup.add(
        types.InlineKeyboardButton("🐻 Grizzly Durumu", callback_data="admin_grizzly"),
        types.InlineKeyboardButton("❌ Kapat", callback_data="back_to_main")
    )
    return markup


def system_control_klavyesi():
    m_mode = database.get_maintenance_mode()
    m_text = "▶️ Sistemi Başlat" if m_mode == 'on' else "⏸️ Durdur (Bakım Modu)"
    
    # Global durumları sorgula
    dep_status = database.get_global_deposit_status()
    num_status = database.get_global_number_buy_status()
    
    dep_btn_text = "💰 Ödemeleri Kapat" if dep_status == "on" else "💰 Ödemeleri Aç"
    num_btn_text = "📱 Numara Alımlarını Kapat" if num_status == "on" else "📱 Numara Alımlarını Aç"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(m_text, callback_data="admin_sys_toggle_maint"),
        types.InlineKeyboardButton(dep_btn_text, callback_data="admin_sys_toggle_deposit"),
        types.InlineKeyboardButton(num_btn_text, callback_data="admin_sys_toggle_numbuy"),
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

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('admin_main', 'admin_stats', 'admin_user_list', 'admin_usrdet_', 'admin_usrhis_', 'admin_setban_', 'admin_coupon_menu', 'admin_create_coupon_start', 'admin_list_coupons', 'admin_del_cpn_', 'admin_add_balance', 'admin_broadcast', 'admin_tickets', 'admin_ticket_', 'admin_reply_ticket_', 'admin_grizzly', 'admin_system_control', 'admin_sys_', 'admin_menu_fiyatlar', 'admin_ban_menu', 'admin_warn_add_', 'admin_warn_reset_', 'admin_unban_user_', 'admin_ban_user_', 'admin_manage_user_', 'admin_ban_list_page_', 'admin_usrblock_', 'admin_usrdelete_')))
    def admin_main_callback_router(call):
        if not is_admin(call.from_user.id): return
        chat_id, msg_id, data = call.message.chat.id, call.message.message_id, call.data

        if data == "admin_menu_fiyatlar":
            import handlers.admin_services as admin_services_mod
            if admin_services_mod.ADMIN_SERVICE_CALLBACK_ROUTER_REF:
                admin_services_mod.ADMIN_SERVICE_CALLBACK_ROUTER_REF(call)
            return

        elif data == "admin_main":
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
                
            n_status = "❌ Engelli" if user.get('number_buy_blocked') else "✅ Serbest"
            d_status = "❌ Engelli" if user.get('deposit_blocked') else "✅ Serbest"
            
            # Referans verilerini sorgula
            ref_stats = database.get_referral_stats(uid)
            ref_owner = user.get('referred_by')
            ref_owner_str = f"`{ref_owner}`" if ref_owner else "Yok"
            
            metin = (
                f"🕵️‍♂️ *Profil: @{user['username']}*\n"
                f"🆔 ID: `{user['user_id']}`\n"
                f"💳 Bakiye: {user['balance']} TL\n"
                f"🛡️ Durum: {drm}\n"
                f"📱 Numara Alımı: {n_status}\n"
                f"💰 Ödeme Yapma: {d_status}\n\n"
                f"👥 *Referans Bilgileri:*\n"
                f"├ 👤 Davet Eden (Referans): {ref_owner_str}\n"
                f"├ 👥 Davet Ettiği Toplam Kişi: `{ref_stats['count']}`\n"
                f"└ 💰 Kazandığı Ref Geliri: `{ref_stats['total_earnings']} TL`"
            )
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("📱 Alımlar", callback_data=f"admin_usrhis_num_{uid}"),
                       types.InlineKeyboardButton("💳 Ödemeler", callback_data=f"admin_usrhis_pay_{uid}"))
            
            buy_btn_text = "📱 Alımı Engelle" if not user.get('number_buy_blocked') else "📱 Alımı Aç"
            dep_btn_text = "💰 Ödemeyi Engelle" if not user.get('deposit_blocked') else "💰 Ödemeyi Aç"
            markup.row(types.InlineKeyboardButton(buy_btn_text, callback_data=f"admin_usrblock_buy_{uid}"),
                       types.InlineKeyboardButton(dep_btn_text, callback_data=f"admin_usrblock_dep_{uid}"))
            
            if user['is_banned']: markup.add(types.InlineKeyboardButton("✅ Yasağı Kaldır", callback_data=f"admin_setban_0_{uid}"))
            else: markup.add(types.InlineKeyboardButton("🚫 Yasakla", callback_data=f"admin_setban_1_{uid}"))
            
            markup.add(types.InlineKeyboardButton("🗑️ Kullanıcıyı Sil (Kaldır)", callback_data=f"admin_usrdelete_confirm_{uid}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_user_list"))
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_usrblock_buy_"):
            uid = int(data.replace("admin_usrblock_buy_", ""))
            database.toggle_user_number_buy_blocked(uid)
            call.data = f"admin_usrdet_{uid}"
            admin_main_callback_router(call)
            bot.answer_callback_query(call.id, "Numara alım durumu güncellendi.")

        elif data.startswith("admin_usrblock_dep_"):
            uid = int(data.replace("admin_usrblock_dep_", ""))
            database.toggle_user_deposit_blocked(uid)
            call.data = f"admin_usrdet_{uid}"
            admin_main_callback_router(call)
            bot.answer_callback_query(call.id, "Ödeme yapma durumu güncellendi.")

        elif data.startswith("admin_usrdelete_confirm_"):
            uid = int(data.replace("admin_usrdelete_confirm_", ""))
            user = database.get_user_info(uid)
            if not user: return
            username = f"@{user['username']}" if user['username'] and user['username'] != "Yok" else f"Kullanıcı ({uid})"
            
            metin = (
                f"❓ *{username} (ID: {uid})* kullanıcısını gerçekten silmek istediğinize emin misiniz?\n\n"
                f"⚠️ *ÖNEMLİ:* Kullanıcının bakiye ve referans bilgileri tamamen kaldırılacak, ancak işlem geçmişi (history) tablosunda korunacaktır."
            )
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("✅ Evet, Sil", callback_data=f"admin_usrdelete_execute_{uid}"),
                types.InlineKeyboardButton("❌ Hayır, İptal", callback_data=f"admin_usrdet_{uid}")
            )
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_usrdelete_execute_"):
            uid = int(data.replace("admin_usrdelete_execute_", ""))
            database.remove_user_from_db(uid)
            bot.answer_callback_query(call.id, "⚠️ Kullanıcı veritabanından silindi.", show_alert=True)
            call.data = "admin_user_list"
            admin_main_callback_router(call)
            return

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
                cursor.execute("SELECT action_type, service_name, fake_number, price, date, status, activation_id FROM history WHERE user_id = %s ORDER BY id DESC LIMIT 20", (uid,))
                hist = cursor.fetchall()
                conn.close()
            except: hist = []

            metin = "📜 *Kullanıcı Geçmişi*\n\n"
            logs = []
            if act == "num":
                metin += "📱 *Satın Alınan Numaralar (Son 20):*\n"
                logs = [i for i in hist if i['action_type'] in (2, 3, 4) or i['price'] > 0]
                for i in logs:
                    drm = i.get('status', '✅')
                    act_id_str = f"\n   └ 🔑 ID: `{i['activation_id']}`" if i.get('activation_id') else ""
                    metin += f"🔹 {i['service_name']} | `+{i['fake_number']}` | {i['price']} TL | {drm}{act_id_str}\n"
            else:
                metin += "💳 *Yükleme ve Ödeme Kayıtları (Son 20):*\n"
                logs = [i for i in hist if i['action_type'] not in (2, 3, 4) and i['price'] <= 0]
                for i in logs:
                    metin += f"📥 {i['service_name']} | {abs(i['price'])} TL | 📅 {i['date'].strftime('%d.%m %H:%M')}\n"

            if not logs: metin += "_Henüz bir kayıt bulunmamaktadır._"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Profil Ekranına Dön", callback_data=f"admin_usrdet_{uid}"))
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
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
            
            # Destek talebi mesajını veritabanından çekelim (Güvenli)
            t_msg = "Mesaj okunamadı."
            try:
                conn = database.get_db_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT message FROM support_tickets WHERE id = %s", (tid,))
                res = cursor.fetchone()
                if res: t_msg = res['message']
                conn.close()
            except: pass
            
            metin = (
                f"🎫 *Destek Talebi #{tid}*\n\n"
                f"📝 *Kullanıcı Mesajı:*\n`{t_msg}`\n\n"
                f"✍️ Lütfen bu talebe yanıtınızı yazın:"
            )
            safe_admin_edit(bot, chat_id, msg_id, metin, admin_klavyesi())
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

        elif data == "admin_sys_toggle_deposit":
            yeni = database.toggle_global_deposit_status()
            bot.answer_callback_query(call.id, f"Ödemeler: {yeni.upper()}", show_alert=True)
            safe_admin_edit(bot, chat_id, msg_id, "⚙️ *Sistem Kontrol Paneli*", system_control_klavyesi())

        elif data == "admin_sys_toggle_numbuy":
            yeni = database.toggle_global_number_buy_status()
            bot.answer_callback_query(call.id, f"Numara Alımları: {yeni.upper()}", show_alert=True)
            safe_admin_edit(bot, chat_id, msg_id, "⚙️ *Sistem Kontrol Paneli*", system_control_klavyesi())

        elif data == "admin_sys_shutdown":
            bot.answer_callback_query(call.id, "🛑 Sunucu kapatılıyor...", show_alert=True)
            try: bot.send_message(chat_id, "💤 Sunucu çevrimdışı yapıldı.")
            except: pass
            import os
            os._exit(0)

        elif data == "admin_compare_start":
            all_srvs = database.get_api_services()
            priority_codes = ['wa', 'tg', 'ig', 'go']
            priority_list = [s for code in priority_codes for s in all_srvs if s['service_code'] == code]
            other_list = sorted([s for s in all_srvs if s['service_code'] not in priority_codes], key=lambda x: x['service_name'])
            sorted_srvs = priority_list + other_list

            markup = types.InlineKeyboardMarkup(row_width=1)
            for s in sorted_srvs:
                markup.add(types.InlineKeyboardButton(s['service_name'], callback_data=f"admin_comp_srv_{s['service_code']}"))
            
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_main"))
            
            safe_admin_edit(bot, chat_id, msg_id, "📊 *Adım 1: Platform Seçin*\n\nLütfen karşılaştırmak istediğiniz servisi seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_comp_srv_"):
            srv_code = data.replace("admin_comp_srv_", "")
            call.data = f"admin_comp_pg_{srv_code}_0"
            admin_main_callback_router(call)

        elif data.startswith("admin_comp_pg_"):
            parts = data.split("_")
            srv_code, page = parts[3], int(parts[4])
            limit = 12
            countries = database.get_paginated_countries(page=page, limit=limit)
            total_pages = database.get_total_country_pages(limit=limit)
            
            markup = types.InlineKeyboardMarkup(row_width=3)
            btns = [types.InlineKeyboardButton(f"{c['flag']} {c['country_name']}", callback_data=f"admin_comp_cc_{srv_code}_{c['country_code']}") for c in countries]
            markup.add(*btns)
            
            prev_btn = types.InlineKeyboardButton("◀️ Geri", callback_data=f"admin_comp_pg_{srv_code}_{page-1}") if page > 0 else types.InlineKeyboardButton("❌", callback_data="disabled")
            page_btn = types.InlineKeyboardButton(f"ℹ️ Sayfa {page+1}", callback_data="disabled")
            next_btn = types.InlineKeyboardButton("Sonraki ▶️", callback_data=f"admin_comp_pg_{srv_code}_{page+1}") if len(countries) == limit else types.InlineKeyboardButton("❌", callback_data="disabled")
            
            markup.row(prev_btn, page_btn, next_btn)
            markup.add(types.InlineKeyboardButton("🔙 Servis Seçimine Dön", callback_data="admin_compare_start"))
            
            safe_admin_edit(bot, chat_id, msg_id, f"🌍 *Adım 2: Ülke Seçin*\n\n{srv_code.upper()} servisi için karşılaştırılacak ülkeyi seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_comp_cc_"):
            parts = data.split("_"); srv, cc = parts[3], parts[4]
            c_info = database.get_country_info(cc)
            
            safe_admin_edit(bot, chat_id, msg_id, "⏳ *API Motorları Sorgulanıyor... Lütfen bekleyin.*", None)
            
            from providers import tigersms_provider
            
            # Fetch Grizzly data
            g_data = grizzly_provider.get_all_prices_and_stocks(srv, cc)
            g_text = ""
            if g_data and isinstance(g_data, dict):
                valid_g_data = {}
                for k, v in g_data.items():
                    try:
                        float(k)
                        valid_g_data[k] = v
                    except ValueError:
                        if k == "cost" and "count" in g_data:
                            valid_g_data[str(v)] = g_data["count"]
                
                if valid_g_data:
                    sorted_g = sorted(valid_g_data.items(), key=lambda x: float(x[0]))
                    for price, stock in sorted_g:
                        g_text += f"└ 💵 Fiyat: `{price}` $ | 📦 Stok: `{stock}` Adet\n"
                else:
                    g_text = "└ _Şu an stok veya fiyat bilgisi bulunamadı._\n"
            else:
                g_text = "└ _Şu an stok veya fiyat bilgisi bulunamadı._\n"
            
            # Fetch Tiger data
            t_data = tigersms_provider.get_all_prices_and_stocks(srv, cc)
            t_text = ""
            if t_data and isinstance(t_data, dict):
                valid_t_data = {}
                for k, v in t_data.items():
                    try:
                        float(k)
                        valid_t_data[k] = v
                    except ValueError:
                        if k == "cost" and "count" in t_data:
                            valid_t_data[str(v)] = t_data["count"]
                
                if valid_t_data:
                    sorted_t = sorted(valid_t_data.items(), key=lambda x: float(x[0]))
                    for price, stock in sorted_t:
                        t_text += f"└ 💵 Fiyat: `{price}` $ | 📦 Stok: `{stock}` Adet\n"
                else:
                    t_text = "└ _Şu an stok veya fiyat bilgisi bulunamadı._\n"
            else:
                t_text = "└ _Şu an stok veya fiyat bilgisi bulunamadı._\n"
            
            metin = (
                "📊 *Fiyat ve Stok Karşılaştırma Raporu*\n"
                f"📱 Servis: `{srv.upper()}` | 🌍 Ülke: {c_info['flag']} {c_info['country_name']}\n"
                "----------------------------------\n"
                "🔥 *Sunucu 1 (Grizzly):*\n"
                f"{g_text}"
                " \n"
                "⚡ *Sunucu 2 (Tiger-SMS):*\n"
                f"{t_text}"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Ülke Seçimine Dön", callback_data=f"admin_comp_srv_{srv}"))
            markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="admin_main"))
            
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

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
            show_ban_warning_list_panel(bot, chat_id, msg_id, 1)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_ban_list_page_"):
            p = int(data.replace("admin_ban_list_page_", ""))
            show_ban_warning_list_panel(bot, chat_id, msg_id, p)
            bot.answer_callback_query(call.id)


        elif data.startswith("admin_manage_user_"):
            uid = int(data.replace("admin_manage_user_", ""))
            show_user_ban_management_panel(bot, chat_id, msg_id, uid)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_warn_add_"):
            uid = int(data.replace("admin_warn_add_", ""))
            warnings = database.get_user_warnings(uid)
            if warnings < 3:
                warnings += 1
                database.update_user_warnings(uid, warnings)
                if warnings >= 3:
                    database.ban_user(uid, 1, "Admin Manuel Uyarı Sınırı", "Limit Aşımı")
                    database.update_user_warnings(uid, 0)
                    from providers.security_manager import security
                    security.BANNED_CACHE.add(uid)
                    try:
                        bot.send_message(uid, "🚫 *UYARI SINIRI AŞILDI!*\n\n3 adet uyarı aldığınız için hesabınız sistem tarafından süresiz olarak yasaklanmıştır.", parse_mode="Markdown")
                    except:
                        pass
                else:
                    try:
                        bot.send_message(uid, f"⚠️ *UYARI ALDINIZ!*\n\nYönetici tarafından uyarıldınız.\n\n*Mevcut Uyarı:* `{warnings} / 3`\n\n_Lütfen kurallara uyunuz. 3. uyarıda hesabınız yasaklanacaktır!_", parse_mode="Markdown")
                    except:
                        pass
            bot.answer_callback_query(call.id, f"Kullanıcıya uyarı eklendi ({warnings}/3)")
            show_user_ban_management_panel(bot, chat_id, msg_id, uid)

        elif data.startswith("admin_warn_reset_"):
            uid = int(data.replace("admin_warn_reset_", ""))
            database.update_user_warnings(uid, 0)
            try:
                bot.send_message(uid, "✅ *UYARILARINIZ SIFIRLANDI!*\n\nYönetici tarafından uyarı sayacınız sıfırlanmıştır. İşlemlerinize devam edebilirsiniz.", parse_mode="Markdown")
            except:
                pass
            bot.answer_callback_query(call.id, "Kullanıcının uyarıları sıfırlandı.")
            show_user_ban_management_panel(bot, chat_id, msg_id, uid)

        elif data.startswith("admin_unban_user_"):
            uid = int(data.replace("admin_unban_user_", ""))
            database.unban_user(uid)
            database.update_user_warnings(uid, 0)
            from providers.security_manager import security
            security.BANNED_CACHE.discard(uid)
            try:
                bot.send_message(uid, "✅ *ENGELİNİZ KALDIRILDI!*\n\nYönetici tarafından hesabınızın engeli kaldırılmıştır. Yeniden işlem yapmaya başlayabilirsiniz.", parse_mode="Markdown")
            except:
                pass
            bot.answer_callback_query(call.id, "Kullanıcının yasağı kaldırıldı.")
            show_user_ban_management_panel(bot, chat_id, msg_id, uid)

        elif data.startswith("admin_ban_user_"):
            uid = int(data.replace("admin_ban_user_", ""))
            database.ban_user(uid, 2, "Admin Manuel Engelleme", "Yönetici Kararı")
            database.update_user_warnings(uid, 0)
            from providers.security_manager import security
            security.BANNED_CACHE.add(uid)
            try:
                bot.send_message(uid, "🚫 *HESABINIZ ENGELLENDİ!*\n\nYönetici kararıyla hesabınız süresiz olarak yasaklanmıştır.", parse_mode="Markdown")
            except:
                pass
            bot.answer_callback_query(call.id, "Kullanıcı yasaklandı.")
            show_user_ban_management_panel(bot, chat_id, msg_id, uid)

    # --- NEXT STEP HANDLERS ---
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
