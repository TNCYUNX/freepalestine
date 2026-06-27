# Veritas Bot - Kritik Sorunlar Raporu

Bu rapor, Veritas SMS Telegram Botu projesinin prodüksiyon (canlı) ortamına geçişi öncesinde tespit edilen ve sistemin tamamen durmasına, hatalı çalışmasına veya kilitlenmesine neden olabilecek kritik/önemli sorunları ve bunların çözüm kodlarını içermektedir.

---

## 1. `process_crypto_amount` Fonksiyonundaki `NameError` Çalışma Zamanı Hatası

- **Dosya Adı ve Fonksiyon:** `handlers/payment_handler.py` -> `process_crypto_amount()` (Satır ~280)
- **Sorunun Kısa Açıklaması:** Fonksiyon içerisinde `user_id` ve `chat_id` değişkenleri doğrudan kullanılmaktadır, ancak bu değişkenler fonksiyon kapsamında (scope) tanımlanmamıştır. Bir kullanıcı bakiye yüklemek için herhangi bir sayısal miktar girdiğinde bot `NameError` vererek çökecek ve ödeme arayüzü kilitlenecektir.
- **Düzeltilmiş Kod Örneği:**

```python
def process_crypto_amount(message, bot, photo_message_id, net_type, min_limit, birim):
    """Seçilen kripto ağına göre miktarı alır ve ödeme faturasını oluşturur."""
    # ÇÖZÜM: user_id ve chat_id message nesnesinden güvenli bir şekilde alınır
    user_id = message.from_user.id
    chat_id = message.chat.id
    
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
    # Fonksiyonun geri kalanı...
```

---

## 2. Eşzamanlı Numara Takiplerinin Thread Havuzunu Tıkaması (DDoS & Kilitlenme Riski)

- **Dosya Adı ve Fonksiyon:** `handlers/number_handler.py` -> `live_track_sms()` (Satır ~260)
- **Sorunun Kısa Açıklaması:** Her numara satın alımında arka planda çalışan `live_track_sms` fonksiyonu, 20 dakika boyunca `time.sleep(1)` barındıran aktif bir `while` döngüsünü thread üzerinde tutar. Bot `TeleBot(..., num_threads=50)` ile 50 thread'e kadar çalışmaktadır. Eşzamanlı 50 kullanıcı numara alıp beklediğinde tüm thread havuzu dolacak, bot yeni komutlara ve callback butonlarına tamamen cevapsız kalacaktır.
- **Düzeltilmiş Kod Örneği:**
  *Kısa vadede thread tıkanmasını engellemek için thread havuzu limitini artırmak geçici bir çözümdür, ancak kesin çözüm tüm aktif kiralamaları tek bir merkezi arka plan thread'i üzerinden topluca tarayan bir kontrol yapısına geçmektir. Örnek arka plan tarayıcı yapısı:*

```python
# number_handler.py veya main.py içinde merkezi bir sorgulama işçisi (worker)
def central_sms_tracking_worker(bot):
    """Her kullanıcı için ayrı thread açmak yerine tüm aktif kiralamaları tek bir thread ile sorgular."""
    while True:
        try:
            with tracking_lock:
                active_ids = list(AKTIF_TAKIPLER.keys())
            
            for act_id in active_ids:
                with tracking_lock:
                    track_info = AKTIF_TAKIPLER.get(act_id)
                if not track_info or not track_info.get("status"):
                    continue
                
                # Sağlayıcıdan durumu sorgula
                # Eğer kod geldiyse veya iptal edildiyse kullanıcıya bildirim gönder ve durumunu güncelle.
                # (live_track_sms içindeki durum sorgulama ve UI güncelleme kodları buraya entegre edilir)
                pass
        except Exception as e:
            print(f"Tracking worker error: {e}")
        time.sleep(4) # Tüm havuzu 4 saniyede bir tarar
```

---

## 3. Veritabanı Bağlantı Kesintilerinde AttributeError ile Çökme Riski

- **Dosya Adı ve Fonksiyon:** `database.py` -> Tüm CRUD fonksiyonları (`get_balance`, `update_balance`, `get_all_users` vb.)
- **Sorunun Kısa Açıklaması:** MySQL sunucusu çöktüğünde veya maksimum bağlantı sınırına ulaşıldığında `get_db_connection()` fonksiyonu `None` döndürmektedir. Ancak CRUD fonksiyonlarında `conn` nesnesinin `None` olup olmadığı kontrol edilmeden doğrudan `conn.cursor()` çağrılmaktadır. Bu durum botun çalışma zamanında çökmesine ve işlemin yarıda kalmasına sebep olur.
- **Düzeltilmiş Kod Örneği:**

```python
def get_balance(user_id):
    conn = get_db_connection()
    if conn is None:
        print("[-] Kritik Hata: Veritabanı bağlantısı kurulamadı (get_balance)")
        return 0.0
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0.0
    except Exception as e:
        print(f"[-] get_balance SQL hatası: {e}")
        return 0.0
    finally:
        conn.close()
```

---

## 4. Admin Fiyat Güncelleme Sihirbazında Döngü Kırılması (Zaman Aşımı / State Machine Bozulması)

- **Dosya Adı ve Fonksiyon:** `handlers/admin_services.py` -> `process_wizard_edit_price()` (Satır ~436)
- **Sorunun Kısa Açıklaması:** Admin sayısal olmayan veya hatalı bir fiyat girdiğinde hata yakalanmakta fakat `register_next_step_handler` çağrılmamaktadır. Bu durum sihirbazı sonlandırır ve admini botla etkileşimsiz, askıda bırakır. Girdi hatalı olduğunda yeniden girdi istenmelidir.
- **Düzeltilmiş Kod Örneği:**

```python
def process_wizard_edit_price(message, bot, service_id, photo_message_id):
    if not is_admin(message.from_user.id): return
    chat_id = message.chat.id
    try:
        new_price = float(message.text.replace(",", "."))
        if new_price <= 0:
            raise ValueError("Fiyat sıfırdan büyük olmalıdır.")
        database.update_service_price_by_id(service_id, new_price)
        cleanup_msg(bot, message)
        bot.send_message(chat_id, f"✅ *FİYAT GÜNCELLENDİ*\n\nYeni satış fiyatı: `{new_price} TL`")
    except Exception:
        cleanup_msg(bot, message)
        bot.send_message(chat_id, "❌ Hata: Geçersiz fiyat formatı. Lütfen geçerli bir fiyat yazın (Örn: 25.50):")
        # DÜZELTME: Girdi hatalıysa handler'ı tekrar bağla
        bot.register_next_step_handler(
            message, 
            process_wizard_edit_price, 
            bot=bot, 
            service_id=service_id, 
            photo_message_id=photo_message_id
        )
```
