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

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('menu_bakiye', 'yukle_sec_', 'checkpay_', 'qr_show_')))
    def payment_callback_router(call):
        user_id, data = call.from_user.id, call.data
        chat_id, msg_id = call.message.chat.id, call.message.message_id
        
        if data == "menu_bakiye_yukle":
            bot.answer_callback_query(call.id)
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("🟢 USDT", callback_data="yukle_sec_USDT"),
                       types.InlineKeyboardButton("🔴 TRX", callback_data="yukle_sec_TRX"))
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back_to_main"))
            safe_payment_edit(bot, chat_id, msg_id, "💰 Lütfen ödeme yapacağınız para birimini seçin:", markup)

        elif data.startswith("yukle_sec_"):
            bot.answer_callback_query(call.id)
            kur = data.split("_")[2]
            min_limit = config.MIN_YUKLEME_LIMITI if kur == "USDT" else config.MIN_YUKLEME_TRX
            metin = f"💰 *Miktar girin (MİN: {int(min_limit)} {kur})*\n\nLütfen yüklemek istediğiniz tutarı bu sohbete yazın:"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="menu_bakiye_yukle"))
            safe_payment_edit(bot, chat_id, msg_id, metin, markup)
            bot.clear_step_handler_by_chat_id(chat_id)
            bot.register_next_step_handler(call.message, process_bakiye_miktari_al, bot=bot, photo_message_id=msg_id, kur_tipi=kur)

        elif data.startswith("qr_show_"):
            parts = data.split("_")
            kur_tipi, miktar = parts[2], parts[3]
            wallet = os.getenv('TRON_WALLET_ADDRESS')
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(wallet)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            bio = io.BytesIO()
            bio.name = 'qr.png'
            img.save(bio)
            bio.seek(0)
            caption = f"📱 *QR ile Öde*\n\n🔢 Miktar: `{miktar}` {kur_tipi}\n📩 Cüzdan: `{wallet}`"
            bot.send_photo(chat_id, bio, caption=caption, parse_mode="Markdown")
            bot.answer_callback_query(call.id)

        elif data.startswith("checkpay_"):
            parts = data.split("_")
            kur_tipi, miktar = parts[1], parts[2]
            
            siparis_anahtari = f"{kur_tipi}_{miktar}"
            siparis_bilgisi = BEKLEYEN_ODEMELER.get(siparis_anahtari)
            
            if not siparis_bilgisi or siparis_bilgisi["user_id"] != user_id:
                bot.answer_callback_query(call.id, "❌ Fatura süresi dolmuş. Lütfen yeniden fatura oluşturun.", show_alert=True)
                return

            min_time = siparis_bilgisi["time_ms"]
            bot.answer_callback_query(call.id, f"⏳ {kur_tipi} ağı taranıyor...")
            
            # 1. HATA DÜZELTİLDİ: crypto_payment.py içindeki parametre ismiyle (min_time_ms) tam eşitlendi
            transfers = crypto_payment.get_valid_incoming_transfers(min_time_ms=min_time)
            found = False
            
            for tx in transfers:
                if tx["type"] == kur_tipi and abs(tx["amount"] - float(miktar)) < 0.001:
                    if database.atomic_mark_tx_processed(tx["txid"]):
                        kurlar = crypto_payment.get_live_rates()
                        tl_eklenen = round(float(miktar) * (kurlar["usdt"] if kur_tipi == "USDT" else kurlar["trx"]), 2)
                        database.update_balance(user_id, tl_eklenen)
                        database.log_crypto_deposit(kur_tipi, float(miktar))
                        database.add_to_history(user_id, "Bakiye", "Otomatik Onay", -tl_eklenen, status="✅ BAŞARILI")
                        yeni_bakiye = database.get_balance(user_id)
                        
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
                        found = True
                        break
            
            if not found:
                bot.answer_callback_query(call.id, "⚠️ Ödeme ağda doğrulanmadı.", show_alert=False)
                
                kurlar = crypto_payment.get_live_rates()
                kur_degeri = kurlar["usdt"] if kur_tipi == "USDT" else kurlar["trx"]
                
                orijinal_miktar = round(float(miktar) - 0.1, 1)
                tl_karsiligi = round(orijinal_miktar * kur_degeri, 2)
                wallet = os.getenv('TRON_WALLET_ADDRESS')
                network = crypto_payment.NETWORK_NAME

                # 2. HATA DÜZELTİLDİ: Markdown yapısı kopyalamayı bozmayacak şekilde temizlendi
                basarisiz_metni = (
                    "💳 *Ödeme Bilgileri*\n\n"
                    f"💰 *Yüklemek istediğiniz:* `{orijinal_miktar} {kur_tipi}`\n"
                    f"🔢 *Göndermeniz gereken:* `{miktar}` *{kur_tipi}*\n"
                    f"📥 *Cüzdan:* `{wallet}`\n"
                    f"🌐 *Ağ:* {network} (TRC20)\n"
                    f"💵 *Alacağınız bakiye:* `{tl_karsiligi} TL`\n"
                    f"📊 *Kur:* 1 USDT = `{kurlar['usdt']} TL` | 1 TRX = `{kurlar['trx']} TL`\n\n"
                    f"⚠️ *ÖNEMLİ:* Tam olarak `{miktar} {kur_tipi}` gönderin!\n"
                    "Farklı miktar gönderirseniz ödeme otomatik onaylanmaz.\n\n"
                    "⏱ 30 dakika içinde ödeme yapın. Ödeme otomatik onaylanacaktır.\n"
                    "───────────────────\n"
                    f"❌ *SON SORGULAMA DURUMU ({time.strftime('%H:%M:%S')}):*\n"
                    f"Transfere ait bir kayıt henüz `{network}` üzerinde bulunamadı veya onaylanmadı.\n"
                    "Lütfen parayı gönderdiğinizden emin olun ve 1-2 dakika sonra tekrar kontrol edin."
                )
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("📱 QR Kod Göster", callback_data=f"qr_show_{kur_tipi}_{miktar}"))
                markup.add(types.InlineKeyboardButton("🔄 Ödemeyi Kontrol Et", callback_data=f"checkpay_{kur_tipi}_{miktar}"))
                markup.add(types.InlineKeyboardButton("◀️ Ana Menü", callback_data="back_to_main"))
                
                safe_payment_edit(bot, chat_id, msg_id, basarisiz_metni, markup)

def process_bakiye_miktari_al(message, bot, photo_message_id, kur_tipi):
    """Kullanıcının girdiği miktarı doğrular ve fatura oluşturur."""
    chat_id, user_id = message.chat.id, message.from_user.id
    min_limit = config.MIN_YUKLEME_LIMITI if kur_tipi == "USDT" else config.MIN_YUKLEME_TRX
    
    try:
        try: 
            bot.delete_message(chat_id, message.message_id)
        except: 
            pass

        input_text = message.text.strip().replace(',', '.')
        amt = float(input_text)
        
        if amt < min_limit:
            metin = f"⚠️ *Yetersiz Miktar!* En az `{int(min_limit)} {kur_tipi}` girmelisiniz.\n\n💰 *Miktar girin ({kur_tipi}):*"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="menu_bakiye_yukle"))
            safe_payment_edit(bot, chat_id, photo_message_id, metin, markup)
            bot.register_next_step_handler(message, process_bakiye_miktari_al, bot=bot, photo_message_id=photo_message_id, kur_tipi=kur_tipi)
            return

        kusurat = 0.1
        final_amount = round(amt + kusurat, 1)
        
        with odeme_lock:
            anlik_zaman_ms = int(time.time() * 1000)
            BEKLEYEN_ODEMELER[f"{kur_tipi}_{final_amount}"] = {
                "user_id": user_id,
                "time_ms": anlik_zaman_ms
            }
            
        kurlar = crypto_payment.get_live_rates()
        kur_degeri = kurlar["usdt"] if kur_tipi == "USDT" else kurlar["trx"]
        tl_karsiligi = round(amt * kur_degeri, 2)
        wallet = os.getenv('TRON_WALLET_ADDRESS')
        network = crypto_payment.NETWORK_NAME

        metin = (
            "💳 *Ödeme Bilgileri*\n\n"
            f"💰 *Yüklemek istediğiniz:* `{amt} {kur_tipi}`\n"
            f"🔢 *Göndermeniz gereken:* `{final_amount}` *{kur_tipi}*\n"
            f"📥 *Cüzdan:* `{wallet}`\n"
            f"🌐 *Ağ:* {network} (TRC20)\n"
            f"💵 *Alacağınız bakiye:* `{tl_karsiligi} TL`\n"
            f"📊 *Kur:* 1 USDT = `{kurlar['usdt']} TL` | 1 TRX = `{kurlar['trx']} TL`\n\n"
            f"⚠️ *ÖNEMLİ:* Tam olarak `{final_amount} {kur_tipi}` gönderin!\n"
            "Farklı miktar gönderirseniz ödeme otomatik onaylanmaz.\n\n"
            "⏱ 30 dakika içinde ödeme yapın. Ödeme otomatik onaylanacaktır."
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📱 QR Kod Göster", callback_data=f"qr_show_{kur_tipi}_{final_amount}"))
        markup.add(types.InlineKeyboardButton("🔄 Ödemeyi Kontrol Et", callback_data=f"checkpay_{kur_tipi}_{final_amount}"))
        markup.add(types.InlineKeyboardButton("◀️ Ana Menü", callback_data="back_to_main"))
        
        safe_payment_edit(bot, chat_id, photo_message_id, metin, markup)
        
    except:
        # 3. HATA DÜZELTİLDİ: Local scope dışındaki bağımlılıklar temizlendi
        metin = f"❌ *Hatalı Giriş!* Lütfen sadece rakam kullanın.\n\n💰 *Miktar girin ({kur_tipi}):*"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 İptal", callback_data="menu_bakiye_yukle"))
        safe_payment_edit(bot, chat_id, photo_message_id, metin, markup)
        bot.register_next_step_handler(message, process_bakiye_miktari_al, bot=bot, photo_message_id=photo_message_id, kur_tipi=kur_tipi)