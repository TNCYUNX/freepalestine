# -*- coding: utf-8 -*-
import telebot
from telebot import types
import os
import database
import math
from providers import grizzly_provider, tigersms_provider

# --- GLOBAL DEĞİŞKENLER ---
PENDING_SVC_DATA = {}
ADMIN_SERVICE_CALLBACK_ROUTER_REF = None

# --- YARDIMCI FONKSİYONLAR ---

def is_admin(user_id):
    admin_id_str = os.getenv("ADMIN_ID")
    return str(user_id) == admin_id_str if admin_id_str else False

def safe_admin_edit(bot, chat_id, message_id, text, markup=None):
    try:
        bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup, parse_mode="Markdown")
            except: pass

def cleanup_msg(bot, message):
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

def format_price_list(stok_verisi):
    """API'den dönen karmaşık fiyat/stok JSON verisini temiz listeye çevirir."""
    if not stok_verisi or not isinstance(stok_verisi, dict):
        return "└ _Şu an canlı stok/maliyet bilgisi alınamadı._\n"
    
    valid_data = {}
    for k, v in stok_verisi.items():
        try:
            float(k)
            valid_data[k] = v
        except ValueError:
            if k == "cost" and "count" in stok_verisi:
                valid_data[str(v)] = stok_verisi["count"]
                
    if not valid_data:
        return "└ _Şu an canlı stok/maliyet bilgisi alınamadı._\n"
        
    sorted_prices = sorted(valid_data.items(), key=lambda x: float(x[0]))
    metin = ""
    for fyt, stk in sorted_prices:
        metin += f"└ 💵 Maliyet: `{fyt}` $ | 📦 Stok: `{stk}` Adet\n"
    return metin

# --- HANDLER KAYIT FONKSİYONU ---

def register_admin_service_handlers(bot):
    global ADMIN_SERVICE_CALLBACK_ROUTER_REF

    @bot.callback_query_handler(func=lambda call: call.data.startswith('addsvc_prov_'))
    def admin_provider_callback_router(call):
        if not is_admin(call.from_user.id): return
        chat_id, msg_id, data = call.message.chat.id, call.message.message_id, call.data
        provider = int(data.replace("addsvc_prov_", ""))
        
        pending_data = PENDING_SVC_DATA.get(chat_id)
        if not pending_data:
            bot.answer_callback_query(call.id, "❌ Hata: İşlem zaman aşımına uğradı.", show_alert=True)
            return
            
        finalize_service_save(bot, chat_id, msg_id, provider, **pending_data)
        PENDING_SVC_DATA.pop(chat_id, None)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('admin_menu_fiyatlar', 'admin_add_srv_', 'admin_adds_', 'admin_pagnat_', 'admin_del_price_start', 'admin_del_srv_', 'admin_del_id_', 'admin_edit_price_start', 'admin_edit_srv_', 'admin_edit_cc_', 'admin_edit_id_', 'admin_compare_start', 'admin_comp_', 'admin_del_cc_', 'admin_edit_type_')))
    def admin_service_callback_router(call):
        if not is_admin(call.from_user.id): return
        chat_id, msg_id, data = call.message.chat.id, call.message.message_id, call.data

        # FSM Durum Temizliği (State Sızıntısını önler)
        try: bot.clear_step_handler_by_chat_id(chat_id)
        except: pass

        if data == "admin_menu_fiyatlar":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("➕ Servis Ekle", callback_data="admin_add_srv_start"),
                       types.InlineKeyboardButton("🗑️ Servis Sil", callback_data="admin_del_price_start"),
                       types.InlineKeyboardButton("💲 Fiyat Güncelle", callback_data="admin_edit_price_start"),
                       types.InlineKeyboardButton("📊 Fiyat/Stok Karşılaştır", callback_data="admin_compare_start"),
                       types.InlineKeyboardButton("🔙 Ana Menü", callback_data="admin_main"))
            safe_admin_edit(bot, chat_id, msg_id, "🚀 *Servis ve Fiyat Yönetimi*", markup)
            bot.answer_callback_query(call.id)

        # --- ADIM 1: Platform Seçimi ---
        elif data == "admin_add_srv_start":
            all_srvs = database.get_api_services()
            priority_codes = ['wa', 'tg', 'ig', 'go']
            priority_list = [s for code in priority_codes for s in all_srvs if s['service_code'] == code]
            other_list = sorted([s for s in all_srvs if s['service_code'] not in priority_codes], key=lambda x: x['service_name'])
            sorted_srvs = priority_list + other_list

            markup = types.InlineKeyboardMarkup(row_width=1)
            for s in sorted_srvs:
                markup.add(types.InlineKeyboardButton(s['service_name'], callback_data=f"admin_adds_srv_{s['service_code']}"))
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_menu_fiyatlar"))
            
            safe_admin_edit(bot, chat_id, msg_id, "🔍 *Adım 1: Platform Seçin*\n\nLütfen eklemek istediğiniz ana şirketi seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_adds_srv_"):
            srv_code = data.replace("admin_adds_srv_", "")
            call.data = f"admin_pagnat_{srv_code}_0"
            admin_service_callback_router(call)

        # --- ADIM 2: Ülke Seçimi (SAYFALAMA) ---
        elif data.startswith("admin_pagnat_"):
            parts = data.split("_")
            srv_code, page = parts[2], int(parts[3])
            limit = 12 
            countries = database.get_paginated_countries(page=page, limit=limit)
            
            markup = types.InlineKeyboardMarkup(row_width=3)
            btns = [types.InlineKeyboardButton(f"{c['flag']} {c['country_name']}", callback_data=f"admin_adds_cc_{srv_code}_{c['country_code']}") for c in countries]
            markup.add(*btns)
            
            prev_btn = types.InlineKeyboardButton("◀️ Geri", callback_data=f"admin_pagnat_{srv_code}_{page-1}") if page > 0 else types.InlineKeyboardButton("❌", callback_data="disabled")
            page_btn = types.InlineKeyboardButton(f"ℹ️ Sayfa {page+1}", callback_data="disabled")
            next_btn = types.InlineKeyboardButton("Sonraki ▶️", callback_data=f"admin_pagnat_{srv_code}_{page+1}") if len(countries) == limit else types.InlineKeyboardButton("❌", callback_data="disabled")
            
            markup.row(prev_btn, page_btn, next_btn)
            markup.add(types.InlineKeyboardButton("🔙 Servis Seçimine Dön", callback_data="admin_add_srv_start"))
            
            safe_admin_edit(bot, chat_id, msg_id, f"🌍 *Adım 2: Ülke Seçin*\n\n{srv_code.upper()} servisi için hedef ülkeyi seçin:", markup)
            bot.answer_callback_query(call.id)

        # --- ADIM 3: ÇİFT MOTORLU MALİYET ANALİZİ ---
        elif data.startswith("admin_adds_cc_"):
            parts = data.split("_"); srv, cc = parts[3], parts[4]
            c_info = database.get_country_info(cc)
            
            safe_admin_edit(bot, chat_id, msg_id, "⏳ *Toptancı Maliyet Havuzları Sorgulanıyor...*", None)
            
            g_data = grizzly_provider.get_all_prices_and_stocks(srv, cc)
            t_data = tigersms_provider.get_all_prices_and_stocks(srv, cc)
            
            metin = f"💲 *Adım 3: Analiz ve Fiyatlandırma*\n\n"
            metin += f"🚀 Servis: `{srv.upper()}`\n🌍 Ülke: {c_info['flag']} {c_info['country_name']}\n\n"
            
            metin += "🔥 *Sunucu 1 (Grizzly) Maliyetleri:*\n"
            metin += format_price_list(g_data) + "\n"
            
            metin += "⚡ *Sunucu 2 (TigerSMS) Maliyetleri:*\n"
            metin += format_price_list(t_data) + "\n"
            
            metin += "💡 *AKILLI OTOMASYON:* Yukarıdaki dolar maliyetlerinden (Örn: 0.88) birini kopyalayıp buraya yazın. Bot otomatik olarak TL satış fiyatını soracaktır."
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Ülke Seçimine Dön", callback_data=f"admin_adds_srv_{srv}"))
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_maliyet_yakala, bot=bot, api_srv=srv, api_cc=cc, msg_id=msg_id)
            bot.answer_callback_query(call.id)

        # --- SERVİS SİLME ---
        elif data == "admin_del_price_start":
            conn = database.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT DISTINCT api_srv, service_name FROM services ORDER BY service_name")
            srvs = cursor.fetchall()
            conn.close()
            
            priority_codes = ['wa', 'tg', 'ig', 'go']
            priority_list = [s for code in priority_codes for s in srvs if s['api_srv'] == code]
            other_list = sorted([s for s in srvs if s['api_srv'] not in priority_codes], key=lambda x: x['service_name'])
            sorted_srvs = priority_list + other_list
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            for s in sorted_srvs:
                markup.add(types.InlineKeyboardButton(f"🗑️ {s['service_name']}", callback_data=f"admin_del_srv_{s['api_srv']}"))
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_menu_fiyatlar"))
            safe_admin_edit(bot, chat_id, msg_id, "🗑️ *Servis Sil - Adım 1*\n\nSilmek istediğiniz servisin kategorisini seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_del_srv_"):
            api_srv = data.replace("admin_del_srv_", "")
            conn = database.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT DISTINCT s.country_code, s.country_name, s.flag
                FROM services s
                LEFT JOIN api_countries c ON s.country_code = c.country_code
                WHERE s.api_srv = %s
                ORDER BY COALESCE(c.priority, 0) DESC, s.country_name ASC
            """, (api_srv,))
            countries = cursor.fetchall()
            conn.close()
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            for c in countries:
                markup.add(types.InlineKeyboardButton(f"{c['flag']} {c['country_name']}", callback_data=f"admin_del_cc_{api_srv}_{c['country_code']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_del_price_start"))
            safe_admin_edit(bot, chat_id, msg_id, f"🗑️ *Servis Sil - Adım 2*\n\n`{api_srv.upper()}` için silmek istediğiniz ülkeyi seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_del_cc_"):
            parts = data.split("_")
            api_srv = parts[3]
            cc_code = parts[4]
            
            conn = database.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, price, api_max_price, api_srv, api_cc, provider FROM services WHERE api_srv = %s AND country_code = %s", (api_srv, cc_code))
            packages = cursor.fetchall()
            conn.close()
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            for c in packages:
                prov = int(c.get('provider', 1))
                if prov == 1:
                    stok = grizzly_provider.get_stock(c['api_srv'], c['api_cc'], c['api_max_price'])
                else:
                    stok = tigersms_provider.get_stock(c['api_srv'], c['api_cc'], c['api_max_price'])
                
                btn_text = f"💰 {c['price']} TL | 💵 Alış: {c['api_max_price']} $ | 📦 Stok: {stok} | 🖥️ S{prov}"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"admin_del_id_{c['id']}"))
            
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data=f"admin_del_srv_{api_srv}"))
            safe_admin_edit(bot, chat_id, msg_id, f"🗑️ *Servis Sil - Adım 2.5*\n\nLütfen silmek istediğiniz paketi seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_del_id_"):
            sid = int(data.replace("admin_del_id_", ""))
            svc = database.get_service_by_id(sid)
            api_srv = svc['api_srv'] if svc else None
            cc_code = svc['country_code'] if svc else None
            
            if database.delete_service(sid):
                bot.answer_callback_query(call.id, "✅ Servis başarıyla silindi.", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "❌ Servis silinirken hata oluştu.", show_alert=True)
            
            if api_srv and cc_code:
                call.data = f"admin_del_cc_{api_srv}_{cc_code}"
                admin_service_callback_router(call)
            elif api_srv:
                call.data = f"admin_del_srv_{api_srv}"
                admin_service_callback_router(call)
            else:
                call.data = "admin_del_price_start"
                admin_service_callback_router(call)

        # --- FİYAT GÜNCELLEME (Sağlayıcıya Duyarlı) ---
        elif data == "admin_edit_price_start":
            conn = database.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT DISTINCT api_srv, service_name FROM services ORDER BY service_name")
            srvs = cursor.fetchall()
            conn.close()
            
            priority_codes = ['wa', 'tg', 'ig', 'go']
            priority_list = [s for code in priority_codes for s in srvs if s['api_srv'] == code]
            other_list = sorted([s for s in srvs if s['api_srv'] not in priority_codes], key=lambda x: x['service_name'])
            sorted_srvs = priority_list + other_list
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            for s in sorted_srvs:
                markup.add(types.InlineKeyboardButton(f"💲 {s['service_name']}", callback_data=f"admin_edit_srv_{s['api_srv']}"))
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_menu_fiyatlar"))
            safe_admin_edit(bot, chat_id, msg_id, "💲 *Fiyat Güncelle - Adım 1*\n\nFiyatını güncellemek istediğiniz servisi seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_edit_srv_"):
            api_srv = data.replace("admin_edit_srv_", "")
            conn = database.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT DISTINCT s.country_code, s.country_name, s.flag
                FROM services s
                LEFT JOIN api_countries c ON s.country_code = c.country_code
                WHERE s.api_srv = %s
                ORDER BY COALESCE(c.priority, 0) DESC, s.country_name ASC
            """, (api_srv,))
            countries = cursor.fetchall()
            conn.close()
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            for c in countries:
                markup.add(types.InlineKeyboardButton(f"{c['flag']} {c['country_name']}", callback_data=f"admin_edit_cc_{api_srv}_{c['country_code']}"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="admin_edit_price_start"))
            safe_admin_edit(bot, chat_id, msg_id, f"💲 *Fiyat Güncelle - Adım 2*\n\n`{api_srv.upper()}` için fiyatını güncellemek istediğiniz ülkeyi seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_edit_cc_"):
            parts = data.split("_")
            api_srv = parts[3]
            cc_code = parts[4]
            
            conn = database.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, price, api_max_price, api_srv, api_cc, provider FROM services WHERE api_srv = %s AND country_code = %s", (api_srv, cc_code))
            packages = cursor.fetchall()
            conn.close()
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            for c in packages:
                prov = int(c.get('provider', 1))
                if prov == 1:
                    stok = grizzly_provider.get_stock(c['api_srv'], c['api_cc'], c['api_max_price'])
                else:
                    stok = tigersms_provider.get_stock(c['api_srv'], c['api_cc'], c['api_max_price'])
                
                btn_text = f"💰 {c['price']} TL | 💵 Alış: {c['api_max_price']} $ | 📦 Stok: {stok} | 🖥️ S{prov}"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"admin_edit_id_{c['id']}"))
            
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data=f"admin_edit_srv_{api_srv}"))
            safe_admin_edit(bot, chat_id, msg_id, f"💲 *Fiyat Güncelle - Adım 2.5*\n\nLütfen düzenlemek istediğiniz paketi (fiyat seçeneğini) seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_edit_id_"):
            sid = int(data.replace("admin_edit_id_", ""))
            svc = database.get_service_by_id(sid)
            if not svc: return
            
            safe_admin_edit(bot, chat_id, msg_id, "⏳ *Bağlı Sunucu Canlı Fiyat/Stok Sorgulanıyor...*", None)
            
            provider = int(svc.get('provider', 1))
            if provider == 1:
                stok_verisi = grizzly_provider.get_all_prices_and_stocks(svc['api_srv'], svc['api_cc'])
                prov_name = "🔥 Sunucu 1 (Grizzly)"
            else:
                stok_verisi = tigersms_provider.get_all_prices_and_stocks(svc['api_srv'], svc['api_cc'])
                prov_name = "⚡ Sunucu 2 (TigerSMS)"
            
            metin = f"💲 *Fiyat Güncelle - Adım 3*\n\n"
            metin += f"🚀 Servis: `{svc['service_name']}`\n"
            metin += f"🌍 Ülke: {svc['flag']} {svc['country_name']}\n"
            metin += f"🖥️ Aktif Sağlayıcı: {prov_name}\n"
            metin += f"💵 Kayıtlı Alış Fiyatı (Maliyet): `{svc['api_max_price']}` $\n"
            metin += f"💰 Mevcut Satış Fiyatı: `{svc['price']} TL`\n\n"
            
            metin += f"{prov_name} Canlı Maliyetler:\n"
            metin += format_price_list(stok_verisi) + "\n"
            
            metin += "Lütfen güncellemek istediğiniz fiyat türünü seçin:"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("💵 Alış Fiyatını (Maliyet) Güncelle ($)", callback_data=f"admin_edit_type_cost_{sid}"),
                types.InlineKeyboardButton("💰 Satış Fiyatını Güncelle (TL)", callback_data=f"admin_edit_type_price_{sid}"),
                types.InlineKeyboardButton("🔙 Geri", callback_data=f"admin_edit_cc_{svc['api_srv']}_{svc['country_code']}")
            )
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_edit_type_"):
            parts = data.split("_")
            edit_type = parts[3] # "cost" veya "price"
            sid = int(parts[4])
            svc = database.get_service_by_id(sid)
            if not svc: return
            
            if edit_type == "cost":
                metin = (
                    "💵 *Alış Fiyatını Güncelle (Maliyet)* 💵\n\n"
                    f"🚀 Servis: `{svc['service_name']}`\n"
                    f"🌍 Ülke: {svc['flag']} {svc['country_name']}\n"
                    f"💵 Mevcut Alış Fiyatı (Maliyet): `{svc['api_max_price']}` $\n\n"
                    "✍️ Lütfen yeni **USD Alış Fiyatını** yazın (Örn: 0.85):"
                )
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data=f"admin_edit_id_{sid}"))
                safe_admin_edit(bot, chat_id, msg_id, metin, markup)
                bot.clear_step_handler_by_chat_id(chat_id)
                bot.register_next_step_handler(call.message, process_wizard_edit_cost, bot=bot, service_id=sid, photo_message_id=msg_id)
            else:
                metin = (
                    "💰 *Satış Fiyatını Güncelle (Kullanıcı Fiyatı)* 💰\n\n"
                    f"🚀 Servis: `{svc['service_name']}`\n"
                    f"🌍 Ülke: {svc['flag']} {svc['country_name']}\n"
                    f"💰 Mevcut Satış Fiyatı: `{svc['price']} TL`\n\n"
                    "✍️ Lütfen yeni **TL Satış Fiyatını** yazın (Örn: 25.50):"
                )
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data=f"admin_edit_id_{sid}"))
                safe_admin_edit(bot, chat_id, msg_id, metin, markup)
                bot.clear_step_handler_by_chat_id(chat_id)
                bot.register_next_step_handler(call.message, process_wizard_edit_price, bot=bot, service_id=sid, photo_message_id=msg_id)
            
            bot.answer_callback_query(call.id)

        # --- FİYAT / STOK KARŞILAŞTIRMA MODÜLÜ ---
        elif data == "admin_compare_start":
            all_srvs = database.get_api_services()
            priority_codes = ['wa', 'tg', 'ig', 'go']
            priority_list = [s for code in priority_codes for s in all_srvs if s['service_code'] == code]
            other_list = sorted([s for s in all_srvs if s['service_code'] not in priority_codes], key=lambda x: x['service_name'])
            sorted_srvs = priority_list + other_list

            markup = types.InlineKeyboardMarkup(row_width=1)
            for s in sorted_srvs:
                markup.add(types.InlineKeyboardButton(s['service_name'], callback_data=f"admin_comp_srv_{s['service_code']}"))
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_menu_fiyatlar"))
            
            safe_admin_edit(bot, chat_id, msg_id, "📊 *Adım 1: Platform Seçin*\n\nKarşılaştırmak istediğiniz servisi seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_comp_srv_"):
            srv_code = data.replace("admin_comp_srv_", "")
            call.data = f"admin_comp_pg_{srv_code}_0"
            admin_service_callback_router(call)

        elif data.startswith("admin_comp_pg_"):
            parts = data.split("_")
            srv_code, page = parts[3], int(parts[4])
            limit = 12
            countries = database.get_paginated_countries(page=page, limit=limit)
            
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
            
            safe_admin_edit(bot, chat_id, msg_id, "⏳ *Her İki API Motoru Sorgulanıyor...*", None)
            
            g_data = grizzly_provider.get_all_prices_and_stocks(srv, cc)
            t_data = tigersms_provider.get_all_prices_and_stocks(srv, cc)
            
            metin = (
                "📊 *Fiyat ve Stok Karşılaştırma Raporu*\n"
                f"📱 Servis: `{srv.upper()}` | 🌍 Ülke: {c_info['flag']} {c_info['country_name']}\n"
                "----------------------------------\n"
                "🔥 *Sunucu 1 (Grizzly):*\n"
                f"{format_price_list(g_data)}\n"
                "⚡ *Sunucu 2 (Tiger-SMS):*\n"
                f"{format_price_list(t_data)}"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Ülke Seçimine Dön", callback_data=f"admin_comp_srv_{srv}"))
            markup.add(types.InlineKeyboardButton("🔙 Servis Menüsü", callback_data="admin_menu_fiyatlar"))
            
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            bot.answer_callback_query(call.id)

    ADMIN_SERVICE_CALLBACK_ROUTER_REF = admin_service_callback_router

# --- STEP HANDLER DÖNGÜLERİ ---

def process_maliyet_yakala(message, bot, api_srv, api_cc, msg_id):
    if not is_admin(message.from_user.id): return
    try:
        api_cost = message.text.strip().replace(",", ".")
        float(api_cost)
        parts = api_cost.split('.')
        if len(parts) > 1 and len(parts[1]) > 4:
            raise ValueError("Maliyet en fazla 4 ondalık basamak içerebilir! (Örn: 0.0850)")
            
        cleanup_msg(bot, message)
        metin = f"✅ *Maliyet Yakalandı:* `{api_cost} $` \n\n✍️ Şimdi bu paket için kullanıcıların göreceği **TL Satış Fiyatını** yazın:"
        safe_admin_edit(bot, message.chat.id, msg_id, metin, None)
        
        bot.register_next_step_handler(message, process_final_tl_kaydet, bot=bot, api_srv=api_srv, api_cc=api_cc, api_cost=api_cost, msg_id=msg_id)
    except Exception as e:
        err_msg = str(e) if "basamak" in str(e) else "Geçersiz maliyet. Lütfen listedeki rakamı (Örn: 0.88) kopyalayıp yapıştırın."
        bot.send_message(message.chat.id, f"❌ Hata: {err_msg}")
        bot.register_next_step_handler(message, process_maliyet_yakala, bot=bot, api_srv=api_srv, api_cc=api_cc, msg_id=msg_id)

def process_final_tl_kaydet(message, bot, api_srv, api_cc, api_cost, msg_id):
    if not is_admin(message.from_user.id): return
    try:
        txt = message.text.strip().replace(",", ".")
        tl_price = float(txt)
        parts = txt.split('.')
        if len(parts) > 1 and len(parts[1]) > 4:
            raise ValueError("Fiyat en fazla 4 ondalık basamak içerebilir! (Örn: 25.5000)")
            
        cleanup_msg(bot, message)
        
        c_info = database.get_country_info(api_cc)
        PENDING_SVC_DATA[message.chat.id] = {
            "api_srv": api_srv, "api_cc": api_cc, "api_cost": api_cost, "tl_price": tl_price
        }
        
        metin = (
            "⚙️ *Adım 4: Sunucu Seçimi*\n\n"
            f"🚀 Servis: `{api_srv.upper()}`\n"
            f"🌍 Ülke: {c_info['flag']} {c_info['country_name']}\n"
            f"💰 Satış Fiyatı: `{tl_price} TL` \n\n"
            "Lütfen bu servisin hangi sunucu üzerinden çalışacağını seçin:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔥 Sunucu 1 (Grizzly)", callback_data="addsvc_prov_1"),
            types.InlineKeyboardButton("⚡ Sunucu 2 (TigerSMS)", callback_data="addsvc_prov_2"),
            types.InlineKeyboardButton("🔙 İptal", callback_data="admin_menu_fiyatlar")
        )
        safe_admin_edit(bot, message.chat.id, msg_id, metin, markup)
        
    except Exception as e:
        err_msg = str(e) if "basamak" in str(e) else "Lütfen sadece TL cinsinden rakam giriniz (Örn: 25.5)."
        bot.send_message(message.chat.id, f"❌ Hata: {err_msg}")
        bot.register_next_step_handler(message, process_final_tl_kaydet, bot=bot, api_srv=api_srv, api_cc=api_cc, api_cost=api_cost, msg_id=msg_id)

def finalize_service_save(bot, chat_id, msg_id, provider, api_srv, api_cc, api_cost, tl_price):
    try:
        c_info = database.get_country_info(api_cc)
        real_service_name = database.get_service_name_by_code(api_srv)
        database.add_new_service(
            srv_name=real_service_name, api_srv=api_srv, cc_code=api_cc, c_name=c_info['country_name'],
            api_cc=api_cc, price=float(tl_price), flag=c_info['flag'], api_max_price=api_cost, provider=int(provider)
        )
        prov_name = "🔥 Sunucu 1" if int(provider) == 1 else "⚡ Sunucu 2"
        final_metin = (
            "✅ *Yeni Servis Başarıyla Eklendi!*\n\n"
            f"🚀 Servis: `{real_service_name}`\n"
            f"🌍 Ülke: {c_info['flag']} {c_info['country_name']}\n"
            f"🖥️ Sunucu: {prov_name}\n"
            f"💵 Maliyet: `{api_cost} $` \n"
            f"💰 Satış Fiyatı: `{tl_price} TL` \n\n"
            "Servis şu an tüm kullanıcılar için aktif hale getirildi."
        )
        
        from admin_panel import admin_klavyesi
        safe_admin_edit(bot, chat_id, msg_id, final_metin, admin_klavyesi())
    except Exception as e: bot.send_message(chat_id, f"❌ Kritik Kayıt Hatası: {e}")

def process_wizard_edit_price(message, bot, service_id, photo_message_id):
    if not is_admin(message.from_user.id): return
    try:
        txt = message.text.replace(",", ".")
        new_price = float(txt)
        if new_price <= 0:
            raise ValueError("Fiyat sıfırdan büyük olmalıdır.")
        parts = txt.split('.')
        if len(parts) > 1 and len(parts[1]) > 4:
            raise ValueError("Fiyat en fazla 4 ondalık basamak içerebilir! (Örn: 25.5000)")
            
        database.update_service_price_by_id(service_id, new_price)
        cleanup_msg(bot, message)
        bot.send_message(message.chat.id, f"✅ *SATIŞ FİYATI GÜNCELLENDİ*\n\nYeni satış fiyatı: `{new_price} TL`")
    except Exception as e:
        cleanup_msg(bot, message)
        err_msg = str(e) if "basamak" in str(e) or "büyük" in str(e) else "Geçersiz fiyat formatı. Lütfen geçerli bir fiyat yazın (Örn: 25.50):"
        bot.send_message(message.chat.id, f"❌ Hata: {err_msg}")
        bot.register_next_step_handler(message, process_wizard_edit_price, bot=bot, service_id=service_id, photo_message_id=photo_message_id)

def process_wizard_edit_cost(message, bot, service_id, photo_message_id):
    if not is_admin(message.from_user.id): return
    try:
        txt = message.text.replace(",", ".")
        new_cost = float(txt)
        if new_cost <= 0:
            raise ValueError("Fiyat sıfırdan büyük olmalıdır.")
        parts = txt.split('.')
        if len(parts) > 1 and len(parts[1]) > 4:
            raise ValueError("Fiyat en fazla 4 ondalık basamak içerebilir! (Örn: 0.8500)")
            
        database.update_service_cost_by_id(service_id, new_cost)
        cleanup_msg(bot, message)
        bot.send_message(message.chat.id, f"✅ *ALIŞ FİYATI GÜNCELLENDİ*\n\nYeni maliyet (alış fiyatı): `{new_cost} $`")
    except Exception as e:
        cleanup_msg(bot, message)
        err_msg = str(e) if "basamak" in str(e) or "büyük" in str(e) else "Geçersiz fiyat formatı. Lütfen geçerli bir fiyat yazın (Örn: 0.85):"
        bot.send_message(message.chat.id, f"❌ Hata: {err_msg}")
        bot.register_next_step_handler(message, process_wizard_edit_cost, bot=bot, service_id=service_id, photo_message_id=photo_message_id)
