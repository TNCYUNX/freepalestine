# -*- coding: utf-8 -*-
import telebot
from telebot import types
import os
import database
import math
from providers import sms_provider

# --- YARDIMCI FONKSİYONLAR ---

def is_admin(user_id):
    admin_id_str = os.getenv("ADMIN_ID")
    return str(user_id) == admin_id_str if admin_id_str else False

def safe_admin_edit(bot, chat_id, message_id, text, markup=None):
    """Admin mesajlarını caption veya text olarak güvenli bir şekilde günceller."""
    try:
        bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup, parse_mode="Markdown")
            except: pass

def cleanup_msg(bot, message):
    """Adminin gönderdiği komut veya veri mesajlarını temizler."""
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

# --- HANDLER KAYIT FONKSİYONU ---

def register_admin_service_handlers(bot):
    """Servis yönetimi ve akıllı fiyatlandırma döngüsünü yöneten bağımsız handler."""

    @bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
    def admin_service_callback_router(call):
        if not is_admin(call.from_user.id): return
        chat_id, msg_id, data = call.message.chat.id, call.message.message_id, call.data

        # --- ADIM 1: Platform Seçimi (TEK SIRA) ---
        if data == "admin_add_srv_start":
            all_srvs = database.get_api_services()
            
            # Özel Sıralama: wa, tg, ig, go en üstte
            priority_codes = ['wa', 'tg', 'ig', 'go']
            priority_list = [s for code in priority_codes for s in all_srvs if s['service_code'] == code]
            other_list = sorted([s for s in all_srvs if s['service_code'] not in priority_codes], key=lambda x: x['service_name'])
            sorted_srvs = priority_list + other_list

            markup = types.InlineKeyboardMarkup(row_width=1) # TEK SIRA ERGONOMİSİ
            for s in sorted_srvs:
                markup.add(types.InlineKeyboardButton(s['service_name'], callback_data=f"admin_adds_srv_{s['service_code']}"))
            
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="admin_menu_fiyatlar"))
            
            safe_admin_edit(bot, chat_id, msg_id, "🔍 *Adım 1: Platform Seçin*\n\nLütfen eklemek istediğiniz ana şirketi seçin:", markup)
            bot.answer_callback_query(call.id)

        elif data.startswith("admin_adds_srv_"):
            srv_code = data.replace("admin_adds_srv_", "")
            # Sayfa 0'dan navigasyonu başlat
            new_call_data = f"admin_pagnat_{srv_code}_0"
            call.data = new_call_data
            admin_service_callback_router(call)

        # --- ADIM 2: Ülke Seçimi (3'LÜ SÜTUN & GELİŞMİŞ SAYFALAMA) ---
        elif data.startswith("admin_pagnat_"):
            parts = data.split("_")
            srv_code, page = parts[2], int(parts[3])
            limit = 12 # 3 sütun x 4 satır
            countries = database.get_paginated_countries(page=page, limit=limit)
            total_pages = database.get_total_country_pages(limit=limit)
            
            markup = types.InlineKeyboardMarkup(row_width=3) # 3'ERLİ SÜTUN
            btns = [types.InlineKeyboardButton(f"{c['flag']} {c['country_name']}", callback_data=f"admin_adds_cc_{srv_code}_{c['country_code']}") for c in countries]
            markup.add(*btns)
            
            # Navigasyon Barı: [ Geri | Sayfa X | İleri ]
            prev_btn = types.InlineKeyboardButton("◀️ Geri", callback_data=f"admin_pagnat_{srv_code}_{page-1}") if page > 0 else types.InlineKeyboardButton("❌", callback_data="disabled")
            page_btn = types.InlineKeyboardButton(f"ℹ️ Sayfa {page+1}", callback_data="disabled")
            next_btn = types.InlineKeyboardButton("Sonraki ▶️", callback_data=f"admin_pagnat_{srv_code}_{page+1}") if len(countries) == limit else types.InlineKeyboardButton("❌", callback_data="disabled")
            
            markup.row(prev_btn, page_btn, next_btn)
            markup.add(types.InlineKeyboardButton("🔙 Servis Seçimine Dön", callback_data="admin_add_srv_start"))
            
            safe_admin_edit(bot, chat_id, msg_id, f"🌍 *Adım 2: Ülke Seçin*\n\n{srv_code.upper()} servisi için hedef ülkeyi seçin:", markup)
            bot.answer_callback_query(call.id)

        # --- ADIM 3: Maliyet Analizi & Akıllı Fiyat Döngüsü ---
        elif data.startswith("admin_adds_cc_"):
            parts = data.split("_"); srv, cc = parts[3], parts[4]
            c_info = database.get_country_info(cc)
            
            safe_admin_edit(bot, chat_id, msg_id, "⏳ *Grizzly Toptancı Maliyet Havuzu Sorgulanıyor...*", None)
            stok_verisi = sms_provider.get_all_prices_and_stocks(srv, cc)
            
            metin = f"💲 *Adım 3: Analiz ve Fiyatlandırma*\n\n"
            metin += f"🚀 Servis: `{srv.upper()}`\n🌍 Ülke: {c_info['flag']} {c_info['country_name']}\n\n"
            metin += "🐻 *Grizzly Toptan Maliyetler (En Ucuz 5):*\n"
            
            if stok_verisi and isinstance(stok_verisi, dict):
                sorted_prices = sorted(stok_verisi.items(), key=lambda x: float(x[0]))
                for fyt, stk in sorted_prices[:5]: 
                    # Markdown 'code' formatı sayesinde admine tıklayıp kopyalama imkanı tanınır
                    metin += f"💵 Maliyet: `{fyt}` $ ➡️ Stok: `{stk}`\n"
            else: 
                metin += "_Şu an canlı stok/maliyet bilgisi alınamadı._\n"
            
            metin += "\n💡 *AKILLI OTOMASYON:* Yukarıdaki dolar maliyetlerinden birini kopyalayıp buraya yapıştırıp gönderin. Bot otomatik olarak TL satış fiyatını soracaktır."
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Ülke Seçimine Dön", callback_data=f"admin_adds_srv_{srv}"))
            safe_admin_edit(bot, chat_id, msg_id, metin, markup)
            
            # ADIM 4'E GEÇİŞ: Maliyeti Yakala
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_maliyet_yakala, bot=bot, api_srv=srv, api_cc=cc, msg_id=msg_id)
            bot.answer_callback_query(call.id)

# --- STEP HANDLER DÖNGÜLERİ ---

def process_maliyet_yakala(message, bot, api_srv, api_cc, msg_id):
    """Adminin kopyalayıp gönderdiği maliyet rakamını yakalar."""
    if not is_admin(message.from_user.id): return
    try:
        # Gelen mesajdan rakamı temizle (nokta/virgül uyumu)
        api_cost = message.text.strip().replace(",", ".")
        float(api_cost) # Doğrulama
        
        cleanup_msg(bot, message)
        
        # Admini bilgilendir ve TL fiyatı sor
        metin = f"✅ *Maliyet Yakalandı:* `{api_cost} $` \n\n✍️ Şimdi bu paket için kullanıcıların göreceği **TL Satış Fiyatını** yazın:"
        safe_admin_edit(bot, message.chat.id, msg_id, metin, None)
        
        # ADIM 5: Final Kayıt
        bot.register_next_step_handler(message, process_final_tl_kaydet, bot=bot, api_srv=api_srv, api_cc=api_cc, api_cost=api_cost, msg_id=msg_id)
    except:
        bot.send_message(message.chat.id, "❌ Hata: Geçersiz maliyet rakamı. Lütfen listedeki rakamı kopyalayıp yapıştırın.")
        # Hata durumunda tekrar dinlemeye devam et
        bot.register_next_step_handler(message, process_maliyet_yakala, bot=bot, api_srv=api_srv, api_cc=api_cc, msg_id=msg_id)

def process_final_tl_kaydet(message, bot, api_srv, api_cc, api_cost, msg_id):
    """TL Satış fiyatını alır ve veritabanına kalıcı kaydı yapar."""
    if not is_admin(message.from_user.id): return
    try:
        tl_price = float(message.text.strip().replace(",", "."))
        cleanup_msg(bot, message)
        
        c_info = database.get_country_info(api_cc)
        
        # Veritabanına kayıt (services tablosuna)
        # srv_name, api_srv, cc_code, c_name, api_cc, price, flag, api_max_price
        database.add_new_service(
            srv_name=api_srv.upper(),
            api_srv=api_srv,
            cc_code=api_cc,
            c_name=c_info['country_name'],
            api_cc=api_cc,
            price=tl_price,
            flag=c_info['flag'],
            api_max_price=api_cost
        )
        
        final_metin = (
            "✅ *Yeni Servis Başarıyla Eklendi!*\n\n"
            f"🚀 Servis: `{api_srv.upper()}`\n"
            f"🌍 Ülke: {c_info['flag']} {c_info['country_name']}\n"
            f"💵 Maliyet: `{api_cost} $` \n"
            f"💰 Satış Fiyatı: `{tl_price} TL` \n\n"
            "Servis şu an tüm kullanıcılar için aktif hale getirildi."
        )
        
        # Ana menüye dönen klavye
        from admin_panel import admin_klavyesi
        safe_admin_edit(bot, message.chat.id, msg_id, final_metin, admin_klavyesi())
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Kayıt Hatası: {e}\nLütfen sadece rakam giriniz (Örn: 250).")
        bot.register_next_step_handler(message, process_final_tl_kaydet, bot=bot, api_srv=api_srv, api_cc=api_cc, api_cost=api_cost, msg_id=msg_id)
