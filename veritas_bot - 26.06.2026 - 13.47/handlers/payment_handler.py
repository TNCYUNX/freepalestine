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

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('menu_bakiye_yukle', 'yukle_sec_', 'checkpay_', 'qr_show_', 'paynet_')))
    def payment_callback_router(call):
        # Anti-Spam ve Ban Koruması
        status, msg, ban_info = security.check_rate_limit(call.from_user.id)
        if status == 'ban':
            # main.py içindeki notify_admin_of_ban fonksiyonuna erişimimiz yok (circular import önlemek için)
            # Ancak TeleBot nesnesi üzerinden manuel gönderebiliriz
            admin_id = os.getenv("ADMIN_ID")
            if admin_id and ban_info:
                metin = (
                    "🚨 *SİBER GÜVENLİK ALARMI - OTOMATİK BAN (ÖDEME KANALI)* 🚨\n\n"
                    f"👤 *Hedef ID:* `{call.from_user.id}`\n"
                    f"⚠️ *Tehdit Tipi:* `Tip {ban_info['type']} ({ban_info['reason']})`\n"
                    f"📝 *Yakalanan Payload:* `{ban_info['input']}`\n"
                )
                try: bot.send_message(admin_id, metin, parse_mode="Markdown")
                except: pass
            try: bot.answer_callback_query(call.id, msg, show_alert=True)
            except: pass
            return
        elif status == 'banned_cache':
            try: bot.answer_callback_query(call.id, msg, show_alert=True)
            except: pass
            return
        elif status == 'warn':
            try: bot.answer_callback_query(call.id, msg, show_alert=True)
            except: pass
            return

        if database.is_user_banned(call.from_user.id):
            try: bot.answer_callback_query(call.id, "🚫 Sistemden banlandınız!", show_alert=True)
            except: pass
            return
            
        user_id, data = call.from_user.id, call.data
        chat_id, msg_id = call.message.chat.id, call.message.message_id

        # --- KRİPTO DEVRE DIŞI BIRAKMA ---
        if data.startswith(("paynet_bep20", "paynet_trc20", "paynet_trx", "checkpay_")):
            bot.answer_callback_query(call.id, "⚠️ Bu yöntem şu an bakımdadır. Lütfen IBAN kullanın.", show_alert=True)
            return

        if data == "menu_bakiye_yukle":
            bot.answer_callback_query(call.id)
            metin = (
                "💰 *Bakiye Yükleme Paneli* 💰\n\n"
                "🛠️ _Kripto işlemlerimiz şu an bakımdadır, anlayışınız için teşekkürler._ 😊\n\n"
                "💎 Tüm yükleme işlemleriniz için lütfen **DM üzerinden** iletişime geçiniz!"
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("💬 DM ÜZERİNDEN İLETİŞİME GEÇ", url="https://t.me/nilayoff"),
                types.InlineKeyboardButton("🔙 İptal / Ana Menü", callback_data="back_to_main")
            )
            safe_payment_edit(bot, chat_id, msg_id, metin, markup)

        elif data.startswith("paynet_"):
            # Herhangi bir paynet_ (IBAN dahil) tıklandığında da aynı sade menüyü gösterir veya engeller
            bot.answer_callback_query(call.id)
            return
            
            # Kripto Seçimi - Miktar Sor
            min_limit = 15.0 if net_type == "trx" else 5.0
            birim = "TRX" if net_type == "trx" else "USDT"
            
            metin = (
                f"💰 *Miktar Belirleme*\n\n"
                f"Lütfen yüklemek istediğiniz `{birim}` miktarını bu sohbete yazın.\n"
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
            
            if net_type == "bep20":
                wallet = os.getenv('BSC_WALLET_ADDRESS')
                kur_tipi = "USDT"
            elif net_type == "trc20":
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
            caption = f"📱 *QR ile Öde*\n\n🔢 Miktar: `{miktar}` {kur_tipi}\n📩 Cüzdan: `{wallet}`"
            try:
                bot.send_photo(chat_id, bio, caption=caption, parse_mode="Markdown")
            except: pass
            try: bot.answer_callback_query(call.id)
            except: pass

        elif data.startswith("checkpay_"):
            parts = data.split("_")
            net_type, miktar = parts[1], parts[2]
            
            # Ağ tipine göre kur tipini belirle
            kur_tipi = "TRX" if net_type == "trx" else "USDT"
            
            siparis_anahtari = f"{net_type}_{miktar}"
            siparis_bilgisi = BEKLEYEN_ODEMELER.get(siparis_anahtari)
            
            if not siparis_bilgisi or siparis_bilgisi["user_id"] != user_id:
                bot.answer_callback_query(call.id, "❌ Fatura süresi dolmuş. Lütfen yeniden fatura oluşturun.", show_alert=True)
                return

            min_time = siparis_bilgisi["time_ms"]
            bot.answer_callback_query(call.id, f"⏳ {net_type.upper()} ağı taranıyor...")
            
            found = False
            
            if net_type == "bep20":
                is_valid, amount = crypto_payment.check_bsc_usdt_transfer(beklenen_tutar=float(miktar), min_time_ms=min_time)
                if is_valid:
                    found = True
            else:
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
                
                # --- VIP ADMİN ALARMI ---
                admin_id = os.getenv("ADMIN_ID")
                if admin_id:
                    alarm_metni = (
                        "💰 *BAKİYE YÜKLENDİ!*\n\n"
                        f"👤 Kullanıcı: `{user_id}`\n"
                        f"💵 Tutar: `{tl_eklenen} TL` ({miktar} {kur_tipi})"
                    )
                    try: bot.send_message(admin_id, alarm_metni, parse_mode="Markdown")
                    except: pass
                
                basari_metni = (
                    "✅ *ÖDEME BAŞARILI!*\n\n"
                    f"💰 *Yüklenen Tutar:* `{tl_eklenen} TL`\n"
                    f"💳 *Güncel Bakiyeniz:* `{yeni_bakiye} TL`\n"
                    f"📊 *İşlem Birimi:* {miktar} {kur_tipi}\n"
                    "───────────────────\n"
                    "İşleminiz onaylandı. Keyifli alışverişler dileriz!"
                )
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="back_to_main"))
                safe_payment_edit(bot, chat_id, msg_id, basari_metni, markup)
                
                del BEKLEYEN_ODEMELER[siparis_anahtari]

            
            if not found:
                bot.answer_callback_query(call.id, "⚠️ Ödeme ağda doğrulanmadı.", show_alert=False)
                
                tl_karsiligi = siparis_bilgisi.get("tl_amount", 0)
                orijinal_miktar = round(float(miktar) - 0.1, 1)
                
                if net_type == "trx":
                    wallet = os.getenv('TRON_WALLET_ADDRESS')
                    network_name = "Tron Network (TRC20)"
                elif net_type == "trc20":
                    wallet = os.getenv('TRON_WALLET_ADDRESS')
                    network_name = "Tron Network (TRC20)"
                else: # bep20
                    wallet = os.getenv('BSC_WALLET_ADDRESS')
                    network_name = "BNB Smart Chain (BEP20)"

                basarisiz_metni = (
                    "💳 *Ödeme Bilgileri*\n\n"
                    f"💰 *Yüklemek istediğiniz:* `{orijinal_miktar} {kur_tipi}`\n"
                    f"🔢 *Göndermeniz gereken:* `{miktar}` *{kur_tipi}*\n"
                    f"📥 *Cüzdan:* `{wallet}`\n"
                    f"🌐 *Ağ:* {network_name}\n"
                    f"💵 *Alacağınız bakiye:* `{tl_karsiligi} TL`\n\n"
                    f"⚠️ *ÖNEMLİ:* Tam olarak `{miktar} {kur_tipi}` gönderin!\n"
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

        kusurat = 0.1
        final_amount = round(crypto_amount + kusurat, 1)
        
        kurlar = crypto_payment.get_live_rates()
        kur_tipi = "TRX" if net_type == "trx" else "USDT"
        kur_degeri = kurlar["trx"] if net_type == "trx" else kurlar["usdt"]
        tl_amount = round(crypto_amount * kur_degeri, 2)
        
        if net_type == "trx":
            wallet = os.getenv('TRON_WALLET_ADDRESS')
            network_name = "Tron Network (TRC20)"
        elif net_type == "trc20":
            wallet = os.getenv('TRON_WALLET_ADDRESS')
            network_name = "Tron Network (TRC20)"
        else: # bep20
            wallet = os.getenv('BSC_WALLET_ADDRESS')
            network_name = "BNB Smart Chain (BEP20)"
            
        with odeme_lock:
            anlik_zaman_ms = int(time.time() * 1000)
            BEKLEYEN_ODEMELER[f"{net_type}_{final_amount}"] = {
                "user_id": user_id,
                "time_ms": anlik_zaman_ms,
                "tl_amount": tl_amount # TL miktarını da saklıyoruz
            }
            
        metin = (
            "💳 *Ödeme Bilgileri*\n\n"
            f"💰 *Yüklemek istediğiniz:* `{crypto_amount} {kur_tipi}`\n"
            f"🔢 *Göndermeniz gereken:* `{final_amount}` *{kur_tipi}*\n"
            f"📥 *Cüzdan:* `{wallet}`\n"
            f"🌐 *Ağ:* {network_name}\n"
            f"💵 *Alacağınız bakiye:* `{tl_amount} TL`\n"
            f"📊 *Kur:* 1 {kur_tipi} = `{kur_degeri} TL`\n\n"
            f"⚠️ *ÖNEMLİ:* Tam olarak `{final_amount} {kur_tipi}` gönderin!\n"
            "Farklı miktar gönderirseniz ödeme otomatik onaylanmaz.\n\n"
            "⏱ 30 dakika içinde ödeme yapın. Ödeme otomatik onaylanacaktır."
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📱 QR Kod Göster", callback_data=f"qr_show_{net_type}_{final_amount}"))
        markup.add(types.InlineKeyboardButton("🔄 Ödemeyi Kontrol Et", callback_data=f"checkpay_{net_type}_{final_amount}"))
        markup.add(types.InlineKeyboardButton("◀️ Ana Menü", callback_data="back_to_main"))
        
        safe_payment_edit(bot, chat_id, photo_message_id, metin, markup)

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