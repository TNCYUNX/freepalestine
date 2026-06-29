# -*- coding: utf-8 -*-
import telebot
from telebot import types
import os
import threading
import time
import io
import qrcode
import database
import config
from providers import crypto_payment
from providers.security_manager import security

# --- GLOBAL DEĞİŞKENLER & KİLİTLER ---
BEKLEYEN_ODEMELER = {}
odeme_lock = threading.Lock()


def safe_payment_edit(bot, chat_id, message_id, text, markup=None):
    try: 
        bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text, reply_markup=markup, parse_mode="Markdown")
    except:
        try: 
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup, parse_mode="Markdown")
        except: 
            pass

def register_payment_handlers(bot):

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('menu_bakiye_yukle', 'yukle_sec_', 'checkpay_', 'qr_show_', 'paynet_', 'close_qr', 'cancelpay_', 'admin_ddos_banall')) )
    def payment_callback_router(call):
        user_id, data = call.from_user.id, call.data
        chat_id, msg_id = call.message.chat.id, call.message.message_id

        # FSM Durum Temizliği (State Sızıntısını önler)
        try: bot.clear_step_handler_by_chat_id(chat_id)
        except: pass

        # Anti-Spam ve Ban Koruması
        status, msg, ban_info = security.check_rate_limit(user_id, call.id)
        if status == 'ban':
            # main.py içindeki notify_admin_of_ban fonksiyonuna erişimimiz yok (circular import önlemek için)
            # Ancak TeleBot nesnesi üzerinden manuel gönderebiliriz
            admin_id = os.getenv("ADMIN_ID")
            if admin_id and ban_info:
                metin = (
                    "🚨 *SİBER GÜVENLİK ALARMI - OTOMATİK BAN (ÖDEME KANALI)* 🚨\n\n"
                    f"👤 *Hedef ID:* `{user_id}`\n"
                    f"⚠️ *Tehdit Tipi:* `Tip {ban_info['type']} ({ban_info['reason']})`\n"
                    f"📝 *Yakalanan Payload:* `{ban_info['input']}`\n"
                )
                try: bot.send_message(admin_id, metin, parse_mode="Markdown")
                except: pass
            try:
                bot.answer_callback_query(call.id, "⚠️ Çok hızlı işlem yapıyorsunuz!", show_alert=False)
                strikes = security.USER_STRIKES.get(user_id, 5)
                warn_msg = f"⚠️ Çok hızlı işlem yapıyorsunuz! (Uyarı: {strikes}/5)"
                bot.send_message(chat_id, warn_msg)
                bot.send_message(chat_id, msg)
            except: pass
            security.USER_STRIKES[user_id] = 0  # Yasaklanınca RAM uyarılarını sıfırla
            return
        elif status == 'banned_cache':
            try:
                bot.answer_callback_query(call.id)
                bot.send_message(chat_id, msg)
            except: pass
            return
        elif status == 'warn':
            try:
                bot.answer_callback_query(call.id, "⚠️ Çok hızlı işlem yapıyorsunuz!", show_alert=False)
                bot.send_message(chat_id, msg)
            except: pass
            return

        if database.is_user_banned(user_id):
            try:
                bot.answer_callback_query(call.id)
                bot.send_message(chat_id, "🚫 Sistemden banlandınız!")
            except: pass
            return

        # Ödemeler kısıtlama kontrolü (Global veya kullanıcı bazlı engelleme)
        global_deposit = database.get_global_deposit_status()
        user_info = database.get_user_info(user_id)
        is_user_blocked = user_info.get("deposit_blocked") if user_info else False
        
        admin_id = os.getenv("ADMIN_ID")
        is_admin_user = (str(user_id) == admin_id)
        
        # 'close_qr' gibi arayüz kapatma işlemlerine her zaman izin verilmeli
        if data != "close_qr" and not is_admin_user:
            if global_deposit == 'off' or is_user_blocked:
                if global_deposit == 'off':
                    bot.answer_callback_query(call.id, "⚠️ Sistem genelinde bakiye yükleme işlemleri geçici olarak kapatılmıştır!", show_alert=True)
                else:
                    bot.answer_callback_query(call.id, "❌ Bakiye yükleme yetkiniz dondurulmuştur. Lütfen destek ile iletişime geçin.", show_alert=True)
                
                # Eğer tıklanan buton doğrudan ana menüdeki "menu_bakiye_yukle" ise silip yönlendirmeye gerek yok
                if data == "menu_bakiye_yukle":
                    return
                
                # UX Reset: Mevcut alt menü mesajını sil ve ana menüye yönlendir
                from main import ana_menu_klavyesi
                try: bot.delete_message(chat_id, msg_id)
                except: pass
                
                try:
                    with open("veritas_sms_logo_yatay.png", "rb") as photo:
                        bot.send_photo(chat_id, photo, caption=config.MESAJLAR["hosgeldin"].format(isim=call.from_user.first_name), reply_markup=ana_menu_klavyesi(user_id=user_id), parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, config.MESAJLAR["hosgeldin"].format(isim=call.from_user.first_name), reply_markup=ana_menu_klavyesi(user_id=user_id), parse_mode="Markdown")
                return

        # --- QR MESAJINI KAPATMA ---
        if data == "close_qr":
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            try: bot.answer_callback_query(call.id, "QR Kod kapatıldı.")
            except: pass
            return

        # --- KRİPTO DEVRE DIŞI BIRAKMA ---


        if data == "menu_bakiye_yukle":
            bot.answer_callback_query(call.id)
            crypto_status = database.get_setting("payment_method_crypto", "on")
            shopier_status = database.get_setting("payment_method_shopier", "off")
            manual_status = database.get_setting("payment_method_manual", "on")
            
            crypto_label = "✅ Aktif" if crypto_status == "on" else "⚠️ Bakımda"
            shopier_label = "✅ Aktif" if shopier_status == "on" else "⌛ Yakında"
            manual_label = "✅ Aktif" if manual_status == "on" else "⚠️ Bakımda"

            metin = (
                "💰 *Bakiye Yükleme Paneli* 💰\n\n"
                "Lütfen tercih ettiğiniz ödeme yöntemini seçiniz:\n\n"
                f"⚡ *Kripto Ödemeleri ({crypto_payment.NETWORK_NAME} - Otomatik)*\n"
                f"└ Durum: `{crypto_label}`\n\n"
                f"🛍️ *Shopier Ödemeleri (Kredi/Banka Kartı)*\n"
                f"└ Durum: `{shopier_label}`\n\n"
                f"💳 *IBAN / EFT (Manuel)*\n"
                f"└ Durum: `{manual_label}`"
            )
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🟢 USDT (TRC20) Yükle", callback_data="paynet_trc20"),
                types.InlineKeyboardButton("🔴 TRX (TRON) Yükle", callback_data="paynet_trx")
            )
            
            # Shopier butonu
            if shopier_status == "on":
                markup.add(types.InlineKeyboardButton("🛍️ Shopier ile Öde (TEST)", callback_data="paynet_shopier_menu"))
            else:
                markup.add(types.InlineKeyboardButton("🛍️ Shopier ile Öde (Yakında)", callback_data="paynet_shopier_yakinda"))
                
            # Manuel buton
            if manual_status == "on":
                markup.add(types.InlineKeyboardButton("💬 IBAN / DM Üzerinden Yükle", url="https://t.me/nilayoff"))
            else:
                markup.add(types.InlineKeyboardButton("💬 IBAN / DM Üzerinden Yükle (Bakımda)", callback_data="paynet_manual_disabled"))
                
            markup.add(types.InlineKeyboardButton("🔙 İptal / Ana Menü", callback_data="back_to_main"))
            safe_payment_edit(bot, chat_id, msg_id, metin, markup)

        elif data == "paynet_shopier_yakinda":
            bot.answer_callback_query(call.id, "🛍️ Shopier Ödemeleri Çok Yakında Aktif Olacaktır!", show_alert=True)
            return

        elif data == "paynet_manual_disabled":
            bot.answer_callback_query(call.id, "⚠️ Bu ödeme yöntemi şu anda bakımdadır!", show_alert=True)
            return

        elif data == "paynet_shopier_menu":
            # Shopier durumunu kontrol et
            shopier_status = database.get_setting("payment_method_shopier", "off")
            if shopier_status == "off":
                bot.answer_callback_query(call.id, "🛍️ Shopier Ödemeleri Çok Yakında Aktif Olacaktır!", show_alert=True)
                return
                
            bot.answer_callback_query(call.id)
            metin = (
                "🛍️ *Shopier Ödeme Seçenekleri (TEST)* 🛍️\n\n"
                "Lütfen Shopier ödemenizi gerçekleştirmek istediğiniz yöntemi seçin:\n\n"
                "📱 *Telegram'da Öde:* Ödeme ekranını Telegram içinden çıkmadan doğrudan açar.\n"
                "└ Hızlı ve pratik bir süreç sunar.\n\n"
                "🌐 *Tarayıcıda Öde:* Ödemeyi harici tarayıcınızda (Safari, Chrome vb.) güvenli adresi görerek açar.\n"
                "└ Phishing şüphesi duyan ve güvenliğe önem verenler için önerilir."
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("📱 Telegram'da Öde (TEST)", web_app=types.WebAppInfo(url="https://wikipedia.org")),
                types.InlineKeyboardButton("🌐 Tarayıcıda Öde (TEST)", url="https://wikipedia.org"),
                types.InlineKeyboardButton("🔙 Geri Dön", callback_data="menu_bakiye_yukle")
            )
            safe_payment_edit(bot, chat_id, msg_id, metin, markup)

        elif data.startswith("paynet_"):
            net_type = data.replace("paynet_", "") # "trc20" veya "trx"
            
            # Kripto durumunu kontrol et
            crypto_status = database.get_setting("payment_method_crypto", "on")
            if crypto_status == "off":
                bot.answer_callback_query(call.id, "⚠️ Kripto ile ödeme yöntemi şu anda bakımdadır!", show_alert=True)
                return
                
            # Kripto Seçimi - Miktar Sor
            min_limit = 15.0 if net_type == "trx" else 5.0
            birim = "TRX" if net_type == "trx" else "USDT"
            
            metin = (
                f"💰 *Miktar Belirleme*\n\n"
                f"Lütfen yüklemek istediğiniz *{birim}* miktarını bu sohbete yazın.\n"
                f"⚠️ Minimum Yükleme: `{min_limit} {birim}`"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="menu_bakiye_yukle"))
            safe_payment_edit(bot, chat_id, msg_id, metin, markup)
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_crypto_amount, bot=bot, photo_message_id=msg_id, net_type=net_type, min_limit=min_limit, birim=birim)
            bot.answer_callback_query(call.id)

        elif data.startswith("qr_show_"):
            parts = data.split("_")
            net_type, miktar = parts[2], parts[3]
            
            if net_type == "trc20":
                wallet = os.getenv('TRON_WALLET_ADDRESS')
                kur_tipi = "USDT"
            else:
                wallet = os.getenv('TRON_WALLET_ADDRESS')
                kur_tipi = "TRX"
                
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(wallet)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            bio = io.BytesIO()
            bio.name = 'qr.png'
            img.save(bio)
            bio.seek(0)
            caption = f"📱 *QR ile Öde*\n\n🔢 Miktar: `{float(miktar):.1f}` {kur_tipi}\n📩 Cüzdan: `{wallet}`"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("❌ QR Kapat", callback_data="close_qr"))
            
            try:
                bot.send_photo(chat_id, bio, caption=caption, reply_markup=markup, parse_mode="Markdown")
            except: pass
            try: bot.answer_callback_query(call.id)
            except: pass

        elif data.startswith("cancelpay_"):
            parts = data.split("_")
            net_type, miktar = parts[1], parts[2]
            siparis_anahtari = f"{net_type}_{miktar}"
            
            with odeme_lock:
                BEKLEYEN_ODEMELER.pop(siparis_anahtari, None)
            
            from main import ana_menu_klavyesi
            bot.answer_callback_query(call.id, "❌ Ödeme işleminiz iptal edilmiştir.")
            safe_payment_edit(bot, chat_id, msg_id, "❌ *Ödeme işleminiz iptal edilmiştir.* \n\nSistem güvenliği ve kuruş şişmesini önlemek amacıyla fatura sonlandırıldı.", ana_menu_klavyesi(user_id=user_id))
            return

        elif data == "admin_ddos_banall":
            if not is_admin_user: return
            
            with odeme_lock:
                saldiganlar = list(set([str(v["user_id"]) for v in BEKLEYEN_ODEMELER.values()]))
                BEKLEYEN_ODEMELER.clear()
            
            ban_count = 0
            admin_id = os.getenv("ADMIN_ID")
            for uid in saldiganlar:
                if admin_id and str(uid) == str(admin_id):
                    continue # Admin kendisini asla banlayamaz!
                try:
                    database.ban_user(int(uid), 1, "Organize Ödeme Flood Saldırısı", "DDoS Kalkanı")
                    security.BANNED_CACHE.add(int(uid))
                    try: bot.send_message(int(uid), "❌ Organize saldırı şüphesiyle hesabınız KALICI olarak askıya alındı.")
                    except: pass
                    ban_count += 1
                except:
                    pass
            
            bot.answer_callback_query(call.id, "🚨 Tüm şüpheli kullanıcılar banlandı.")
            safe_payment_edit(bot, chat_id, msg_id, f"🛡️ *DDoS Kalkanı Devreye Girdi!*\n\n🚨 Toplam `{ban_count}` şüpheli kullanıcı kalıcı olarak banlandı.\n📦 Bekleyen ödeme listesi sıfırlandı.", types.InlineKeyboardMarkup())
            return

        elif data.startswith("checkpay_"):
            parts = data.split("_")
            net_type, miktar = parts[1], parts[2]
            
            # Ağ tipine göre kur tipini belirle
            kur_tipi = "TRX" if net_type == "trx" else "USDT"
            
            siparis_anahtari = f"{net_type}_{miktar}"
            with odeme_lock:
                siparis_bilgisi = BEKLEYEN_ODEMELER.get(siparis_anahtari)
            
            if not siparis_bilgisi or siparis_bilgisi["user_id"] != user_id:
                bot.answer_callback_query(call.id, "❌ Fatura süresi dolmuş. Lütfen yeniden fatura oluşturun.", show_alert=True)
                return

            min_time = siparis_bilgisi["time_ms"]
            bot.answer_callback_query(call.id, f"⏳ {net_type.upper()} ağı taranıyor...")
            
            found = False
            transfers = crypto_payment.get_valid_incoming_transfers(min_time_ms=min_time)
            for tx in transfers:
                if tx["type"] == kur_tipi and abs(tx["amount"] - float(miktar)) < 0.001:
                    if database.atomic_mark_tx_processed(tx["txid"]):
                        found = True
                        break
                            
            if found:
                # Faturadaki orijinal TL miktarını ver
                tl_eklenen = siparis_bilgisi.get("tl_amount", round(float(miktar) * 46.0, 2))
                database.update_balance(user_id, tl_eklenen)
                database.log_crypto_deposit(kur_tipi, float(miktar))
                database.add_to_history(user_id, 1, "Bakiye Yükleme", f"Kripto ({net_type.upper()})", -tl_eklenen, status="✅ BAŞARILI")
                yeni_bakiye = database.get_balance(user_id)
                
                # --- REFERANS KOMİSYONU ÖDEME SİSTEMİ ---
                process_referral_commission(bot, user_id, tl_eklenen)
                
                # --- VIP ADMİN ALARMI ---
                admin_id = os.getenv("ADMIN_ID")
                if admin_id:
                    alarm_metni = (
                        "💰 *BAKİYE YÜKLENDİ!*\n\n"
                        f"👤 Kullanıcı: `{user_id}`\n"
                        f"💵 Tutar: `{tl_eklenen} TL` ({float(miktar):.1f} {kur_tipi})"
                    )
                    try: bot.send_message(admin_id, alarm_metni, parse_mode="Markdown")
                    except: pass
                
                basari_metni = (
                    "✅ *ÖDEME BAŞARILI!*\n\n"
                    f"💰 *Yüklenen Tutar:* `{tl_eklenen} TL`\n"
                    f"💳 *Güncel Bakiyeniz:* `{yeni_bakiye} TL`\n"
                    f"📊 *İşlem Birimi:* {float(miktar):.1f} {kur_tipi}\n"
                    "───────────────────\n"
                    "İşleminiz onaylandı. Keyifli alışverişler dileriz!"
                )
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="back_to_main"))
                safe_payment_edit(bot, chat_id, msg_id, basari_metni, markup)
                
                with odeme_lock:
                    BEKLEYEN_ODEMELER.pop(siparis_anahtari, None)

            
            if not found:
                bot.answer_callback_query(call.id, "⚠️ Ödeme ağda doğrulanmadı.", show_alert=False)
                
                tl_karsiligi = siparis_bilgisi.get("tl_amount", 0)
                orijinal_miktar = siparis_bilgisi.get("crypto_amount", float(miktar))
                
                wallet = os.getenv('TRON_WALLET_ADDRESS')
                network_name = "Tron Network (TRC20)"

                basarisiz_metni = (
                    "💳 *Ödeme Bilgileri*\n\n"
                    f"💰 *Yüklemek istediğiniz:* `{orijinal_miktar:.1f} {kur_tipi}`\n"
                    f"🔢 *Göndermeniz gereken:* `{float(miktar):.1f}` *{kur_tipi}*\n"
                    f"📥 *Cüzdan:* `{wallet}`\n"
                    f"🌐 *Ağ:* {network_name}\n"
                    f"💵 *Alacağınız bakiye:* `{tl_karsiligi} TL`\n\n"
                    f"⚠️ *ÖNEMLİ:* Tam olarak `{float(miktar):.1f} {kur_tipi}` gönderin!\n"
                    "Farklı miktar gönderirseniz ödeme otomatik onaylanmaz.\n\n"
                    "⏱ 30 dakika içinde ödeme yapın. Ödeme otomatik onaylanacaktır.\n"
                    "───────────────────\n"
                    f"❌ *SON SORGULAMA DURUMU ({time.strftime('%H:%M:%S')}):*\n"
                    f"Transfere ait bir kayıt henüz ağ üzerinde bulunamadı veya onaylanmadı.\n"
                    "Lütfen parayı gönderdiğinizden emin olun ve 1-2 dakika sonra tekrar kontrol edin."
                )
                
                markup = types.InlineKeyboardMarkup()
                # QR kodunu da ağ tipine göre güncelliyoruz
                markup.add(types.InlineKeyboardButton("📱 QR Kod Göster", callback_data=f"qr_show_{net_type}_{miktar}"))
                markup.add(types.InlineKeyboardButton("🔄 Ödemeyi Kontrol Et", callback_data=f"checkpay_{net_type}_{miktar}"))
                markup.add(types.InlineKeyboardButton("◀️ Ana Menü", callback_data="back_to_main"))
                
                safe_payment_edit(bot, chat_id, msg_id, basarisiz_metni, markup)

def process_crypto_amount(message, bot, photo_message_id, net_type, min_limit, birim):
    """Seçilen kripto ağına göre miktarı alır ve ödeme faturasını oluşturur."""
    chat_id, user_id = message.chat.id, message.from_user.id
    
    # Ödemeler kısıtlama kontrolü
    global_deposit = database.get_global_deposit_status()
    user_info = database.get_user_info(user_id)
    is_user_blocked = user_info.get("deposit_blocked") if user_info else False
    
    admin_id = os.getenv("ADMIN_ID")
    is_admin_user = (str(user_id) == admin_id)
    
    if not is_admin_user:
        if global_deposit == 'off' or is_user_blocked:
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
            
            metin = "⚠️ *Ödeme İşlemleri Kısıtlanmıştır!*\n\nŞu anda bakiye yükleme işlemleriniz dondurulmuştur veya sistem genelinde kapalıdır."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="back_to_main"))
            safe_payment_edit(bot, chat_id, photo_message_id, metin, markup)
            return

    try:
        try: bot.delete_message(chat_id, message.message_id)
        except: pass

        input_text = message.text.strip().replace(',', '.')
        crypto_amount = float(input_text)
        
        if crypto_amount < min_limit:
            metin = (
                f"⚠️ *Yetersiz Miktar!*\n\n"
                f"En az `{min_limit} {birim}` girmelisiniz.\n"
                f"💰 *Lütfen yüklemek istediğiniz `{birim}` miktarını tekrar yazın:*"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="menu_bakiye_yukle"))
            safe_payment_edit(bot, chat_id, photo_message_id, metin, markup)
            bot.register_next_step_handler(message, process_crypto_amount, bot=bot, photo_message_id=photo_message_id, net_type=net_type, min_limit=min_limit, birim=birim)
            return

        # Eski faturaları temizle ve eğer aynı kullanıcı aynı miktarla tekrar geldiyse mevcut faturayı bul
        existing_final_amount = None
        current_time_ms = int(time.time() * 1000)
        
        with odeme_lock:
            # 2 saati dolmuş eski faturaları RAM'den temizle
            expired_keys = [
                k for k, v in BEKLEYEN_ODEMELER.items()
                if current_time_ms - v["time_ms"] > 7200000
            ]
            for k in expired_keys:
                BEKLEYEN_ODEMELER.pop(k, None)
                
            # Kullanıcının aktif olan aynı miktar/ağ faturası var mı kontrol et
            for key, val in BEKLEYEN_ODEMELER.items():
                if val["user_id"] == user_id and key.startswith(f"{net_type}_"):
                    if abs(val.get("crypto_amount", 0.0) - crypto_amount) < 0.001:
                        existing_final_amount = float(key.split("_")[1])
                        # Süreyi yenile (2 saat daha ver)
                        val["time_ms"] = current_time_ms
                        break
                        
        if existing_final_amount is not None:
            # Mevcut aktif faturayı tekrar kullan (Yeni session açma)
            final_amount = existing_final_amount
        else:
            # Sıfırdan benzersiz küsurat ekle (Cent bazlı: 0.10'dan başlar, çakışma varsa 0.1 artar)
            kusurat = 0.1
            with odeme_lock:
                while True:
                    candidate = round(crypto_amount + kusurat, 1)
                    key = f"{net_type}_{candidate:.1f}"
                    if key not in BEKLEYEN_ODEMELER:
                        break
                    kusurat += 0.1
            final_amount = round(crypto_amount + kusurat, 1)
        
        kurlar = crypto_payment.get_live_rates()
        kur_tipi = "TRX" if net_type == "trx" else "USDT"
        kur_degeri = kurlar["trx"] if net_type == "trx" else kurlar["usdt"]
        tl_amount = round(crypto_amount * kur_degeri, 2)
        
        wallet = os.getenv('TRON_WALLET_ADDRESS')
        network_name = "Tron Network (TRC20)"
            
        with odeme_lock:
            anlik_zaman_ms = int(time.time() * 1000)
            BEKLEYEN_ODEMELER[f"{net_type}_{final_amount:.1f}"] = {
                "user_id": user_id,
                "chat_id": chat_id,
                "message_id": photo_message_id,
                "time_ms": anlik_zaman_ms,
                "tl_amount": tl_amount, # TL miktarını da saklıyoruz
                "crypto_amount": crypto_amount, # Orijinal kripto miktarını da saklıyoruz
                "notified_10m": False,
                "notified_5m": False
            }
            
        metin = (
            "💳 *Ödeme Ekranı*\n\n"
            f"💰 *Yüklemek istediğiniz:* `{crypto_amount:.1f} {kur_tipi}`\n"
            f"🔢 *Göndermeniz gereken:* `{final_amount:.1f}` *{kur_tipi}*\n"
            f"📥 *Cüzdan:* `{wallet}`\n"
            f"🌐 *Ağ:* {network_name}\n"
            f"💵 *Alacağınız bakiye:* `{tl_amount} TL`\n"
            f"📊 *Kur:* 1 {kur_tipi} = `{kur_degeri} TL`\n\n"
            f"⚠️ *ÖNEMLİ:* Tam olarak `{final_amount:.1f} {kur_tipi}` gönderin!\n"
            "Farklı miktar gönderirseniz ödeme otomatik onaylanmaz.\n\n"
            "⏱ *2 saat* içinde ödeme yapın. Ödeme otomatik onaylanacaktır.\n\n"
            "⚠️ *KRİTİK UYARI:* Sadece bu *💳 Ödeme Ekranı* açıkken gönderim yapın! Bu ekranda değilken arkaplanda ödeme yaparsanız tüm sorumluluk size aittir. Süreniz dolarsa veya iptal ederseniz kesinlikle ödeme yapmayın, tekrar 'Bakiye Yükle' butonunu kullanarak yeni ödeme başlatın."
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📱 QR Kod Göster", callback_data=f"qr_show_{net_type}_{final_amount:.1f}"))
        markup.add(types.InlineKeyboardButton("🔄 Ödemeyi Kontrol Et", callback_data=f"checkpay_{net_type}_{final_amount:.1f}"))
        markup.add(types.InlineKeyboardButton("❌ Ödemeyi İptal Et", callback_data=f"cancelpay_{net_type}_{final_amount:.1f}"))
        markup.add(types.InlineKeyboardButton("◀️ Ana Menü", callback_data="back_to_main"))
        
        safe_payment_edit(bot, chat_id, photo_message_id, metin, markup)

        # DDoS Saldırı Alarmı: Bekleyen ödeme sayısı 10'u aşarsa admin'e bildir
        with odeme_lock:
            pending_count = len(BEKLEYEN_ODEMELER)
        
        if pending_count > 10:
            admin_id = os.getenv("ADMIN_ID")
            if admin_id:
                alarm_metni = (
                    "🚨 *DDoS / ÖDEME FLOOD ALARMI!* 🚨\n\n"
                    f"Sistemde aktif bekleyen ödeme sayısı: `{pending_count}`\n\n"
                    "Olası bir organize saldırı tespit edildi. Aşağıdaki butonu kullanarak tüm şüphelileri tek tıkla banlayabilir ve oturumları sonlandırabilirsiniz."
                )
                markup_alarm = types.InlineKeyboardMarkup()
                markup_alarm.add(types.InlineKeyboardButton("🚨 TÜMÜNÜ BANLA!", callback_data="admin_ddos_banall"))
                try: bot.send_message(admin_id, alarm_metni, reply_markup=markup_alarm, parse_mode="Markdown")
                except: pass

    except:
        metin = (
            f"❌ *Hatalı Giriş!*\n\n"
            f"Lütfen sadece rakam kullanın.\n"
            f"💰 *Lütfen yüklemek istediğiniz `{birim}` miktarını tekrar yazın:*"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="menu_bakiye_yukle"))
        safe_payment_edit(bot, chat_id, photo_message_id, metin, markup)
        bot.register_next_step_handler(message, process_crypto_amount, bot=bot, photo_message_id=photo_message_id, net_type=net_type, min_limit=min_limit, birim=birim)

def process_referral_commission(bot, referred_id, deposit_amount_tl):
    """Davet eden kişiye ödeme üzerinden komisyon aktarır (Her iki tarafın da telefon onayı şarttır)."""
    try:
        referrer_id = database.get_referrer(referred_id)
        if referrer_id:
            referred_info = database.get_user_info(referred_id)
            referrer_info = database.get_user_info(referrer_id)
            
            if referred_info and referrer_info:
                # Her iki tarafın da referans durumu 'approved' (onaylı) olmalıdır
                if referred_info.get("ref_status") == "approved" and referrer_info.get("ref_status") == "approved":
                    # Komisyon oranını sistem ayarlarından çek (Varsayılan %2.0)
                    ref_rate = float(database.get_setting("referral_percentage", "2.0"))
                    commission = round(deposit_amount_tl * (ref_rate / 100.0), 2)
                    
                    if commission > 0.01:
                        # Davet edenin bakiyesini güncelle
                        database.update_balance(referrer_id, commission)
                        
                        # Davet edenin geçmişine "Ref Bakiye" logu yaz
                        database.add_to_history(
                            referrer_id, 
                            1, 
                            "Ref Bakiye", 
                            f"Ref Oranı: %{ref_rate} | Davetli: {referred_id} | Yükleme: {deposit_amount_tl} TL", 
                            -commission, 
                            status="✅ BAŞARILI"
                        )
                        
                        # Referans istatistiklerini güncelle
                        database.update_referral_earnings(referrer_id, referred_id, commission)
                        
                        # Davet edene bildirim mesajı gönder
                        msg = (
                            "🎁 *Referans Kazancı Kazanıldı!*\n\n"
                            f" Davet ettiğiniz kullanıcı (ID: `{referred_id}`) bakiye yükledi.\n"
                            f"💰 Komisyon Oranı: *%{ref_rate}*\n"
                            f"💵 Kazancınız: *+{commission} TL*\n\n"
                            f"🛡️ _Kazancınız bakiyenize başarıyla eklenmiştir._"
                        )
                        try:
                            bot.send_message(referrer_id, msg, parse_mode="Markdown")
                        except:
                            pass
    except Exception as e:
        print(f"Error in process_referral_commission: {e}")
    except Exception as e:
        print(f"Error in process_referral_commission: {e}")