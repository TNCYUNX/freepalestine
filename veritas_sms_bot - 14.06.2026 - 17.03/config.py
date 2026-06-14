# -*- coding: utf-8 -*-

# Yükleme Ayarları ve Kurlar
MIN_YUKLEME_LIMITI = 5.0
MIN_YUKLEME_TRX = 16.0
MAX_YUKLEME_LIMITI = 9999.0
KUR_USDT = 35.00
KUR_TRX = 4.50

# Kurucu İletişim
KURUCU_URL = "https://t.me/nilayoff"

# Grizzly SMS Katalogları
GRIZZLY_SERVICES = {"tg": "Telegram", "wa": "WhatsApp", "go": "Google", "ig": "Instagram", "ds": "Discord", "mt": "Steam", "lf": "TikTok", "dl": "ChatGPT", "oi": "Tinder", "tw": "Twitter", "fb": "Facebook", "mm": "Microsoft", "nf": "Netflix"}
GRIZZLY_COUNTRIES = {"62": "Turkey", "187": "USA", "16": "United Kingdom", "43": "Germany", "78": "France", "182": "Japan", "3": "China", "22": "India", "73": "Brazil", "54": "Mexico", "36": "Canada", "56": "Spain", "86": "Italy", "48": "Netherlands"}

# Bot Mesajları (Telegram Bold kuralı: *metin*)
MESAJLAR = {
    "hosgeldin": (
        "🎉 *Merhaba {isim}! Veritas SMS Sistemine Hoş Geldin!*\n\n"
        "Dünya genelindeki popüler platformlar için saniyeler içinde onay kodu "
        "alabileceğiniz kurumsal altyapımıza giriş yaptınız.\n\n"
        "🛡️ İşlemleriniz *%100 otomatik* ve şifrelenmiştir.\n\n"
        "Aşağıdaki menüyü kullanarak işleminize başlayabilirsiniz:"
    ),
    "miktar_girin": "Lütfen yüklemek istediğiniz miktarı {para_birimi} olarak yazın (Min *{min_limit}* {para_birimi}):",
    "fatura_arayuzu": (
        "💳 *Ödeme Bilgileri*\n\n"
        "💰 *Yüklemek istediğiniz:* `{base_amount}` {kur_tipi}\n"
        "🔢 *Göndermeniz gereken:* `{final_amount}` {kur_tipi}\n"
        "📥 *Cüzdan:* `{cuzdan}`\n"
        "🌐 *Ağ:* Tron Nile Testnet (TRC20)\n"
        "💵 *Alacağınız bakiye:* `{tl_miktari}` TL\n"
        "📊 *Kur:* 1 USDT = `{kur_usdt}` TL | 1 TRX = `{kur_trx}` TL\n\n"
        "⚠️ *ÖNEMLİ:* Tam olarak `{final_amount}` {kur_tipi} gönderin!\n"
        "Farklı miktar gönderirseniz ödeme otomatik onaylanmaz.\n\n"
        "⏱ 30 dakika içinde ödeme yapın. Ödeme otomatik onaylanacaktır."
    ),
    "qr_mesaji": (
        "📱 *QR ile Öde*\n\n"
        "🔢 *Miktar:* `{final_amount}` {kur_tipi}\n"
        "📥 *Cüzdan:* `{cuzdan}`\n"
        "🌐 *Ağ:* Tron Nile Testnet\n"
    ),
    "gecersiz_kupon": "❌ *Geçersiz kupon kodu.*",
    "yetersiz_bakiye": "❌ *Yetersiz bakiye!* Lütfen bakiye yükleyiniz.",
    "servis_sec": "📱 Lütfen bir *Servis* seçiniz:",
    "ulke_sec": "🌍 Lütfen bir *Ülke* seçiniz:",
    "odeme_onay": "✅ *Ödemeniz onaylandı!* Bakiyeniz başarıyla güncellendi.",
    "destek_istek": "📝 *Lütfen destek talebinizi (sorununuzu) bu sohbete yazın.*\n\n*(Not: Günde sadece 1 kez destek talebi oluşturabilirsiniz.)*",
    "destek_basarili": "✅ *Destek talebiniz başarıyla alındı!*\nEn kısa sürede incelenecektir.",
    "destek_limit": "⏳ Günlük limit! Günde sadece 1 kez destek talebi oluşturabilirsiniz.",
    "gecmis_bos": "📋 *Henüz bir işlem geçmişiniz bulunmamaktadır.*"
}

BUTONLAR = {
    "numara_al": "📱 Numara Al",
    "bakiye_yukle": "💰 Bakiye Yükle",
    "bakiyem": "💳 Bakiyem",
    "gecmisim": "📋 Geçmişim",
    "kupon_kullan": "🎟️ Kupon Kullan",
    "duyurular": "📢 Duyuruları Gör",
    "destek": "🆘 Destek",
    "kurucu": "👑 Kurucu",
    "ana_menu": "🔙 Ana Menü"
}
