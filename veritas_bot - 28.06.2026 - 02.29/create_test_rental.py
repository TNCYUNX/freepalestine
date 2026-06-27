# -*- coding: utf-8 -*-
import database
import time
import os
from dotenv import load_dotenv

load_dotenv()

print("====================================")
print("[TEST] VERITAS SMS: AUTO-RECOVERY TEST ARACI")
print("====================================")

# Varsayılan olarak .env'deki ADMIN_ID'yi önerelim
varsayilan_id = os.getenv("ADMIN_ID", "")
user_id_input = input(f"Lutfen Telegram ID'nizi girin [Varsayilan: {varsayilan_id}]: ").strip()
if not user_id_input:
    user_id_input = varsayilan_id

if not user_id_input.isdigit():
    print("[ERR] Hata: Gecersiz Telegram ID!")
    exit()

user_id = int(user_id_input)

print("\n--- TEST EDILEBILIR SENARYOLAR ---")
print("1) Senaryo A: Bot kapaliyken SMS kodu gelmis ve 20+ dakika dolmus (Basarili Kurtarma)")
print("2) Senaryo B: Bot kapaliyken 20+ dakika dolmus ve SMS kodu gelmemis (Bakiye Iade & Iptal)")
print("3) Senaryo C: Henuz 20 dakika dolmamis (SMS bekleme thread'inin kaldigi yerden devam etmesi)")

secim = input("\nLutfen test etmek istediginiz senaryoyu secin (1-3): ").strip()
if secim not in ('1', '2', '3'):
    print("[ERR] Hata: Gecersiz secim!")
    exit()

message_id = 999999  # Test icin hayali mesaj ID

if secim == '1':
    activation_id = "test_success_123"
    start_time = time.time() - 1500  # 25 dakika once (sure dolmus)
    phone_number = "905551112233"
    senaryo_adi = "Senaryo A (SMS Gelmis & Sure Dolmus)"
elif secim == '2':
    activation_id = "test_timeout_123"
    start_time = time.time() - 1500  # 25 dakika once (sure dolmus)
    phone_number = "905551112244"
    senaryo_adi = "Senaryo B (SMS Yok & Sure Dolmuş)"
else:
    activation_id = "test_active_123"
    start_time = time.time() - 300   # 5 dakika once (kalan sure: 15 dakika)
    phone_number = "905551112255"
    senaryo_adi = "Senaryo C (Aktif Kiralama - Kalan Sure: 15 dk)"

# active_rentals tablosuna test verisini yazalim
success = database.add_active_rental(
    user_id=user_id,
    chat_id=user_id,
    message_id=message_id,
    activation_id=activation_id,
    phone_number=phone_number,
    service_id=1,
    service_code="wa",
    service_name="WhatsApp",
    api_srv="wa",
    api_cc="90",
    price=15.0,
    provider=1,
    start_time=start_time
)

if success:
    print(f"\n[OK] {senaryo_adi} verisi veritabanina basariyla eklendi!")
    print("────────────────────────────────────")
    print("Lutfen Testi Gerceklestirmek Icin:")
    print("1. Botunuzu baslatin: `python main.py`")
    print("2. Bot basladigi an veritabanini tarayacak ve Telegram'dan size ilgili bildirimi gonderecektir.")
    print("3. Test tamamlandiginda botu kapatip diger senaryolari deneyebilirsiniz.")
    print("────────────────────────────────────")
else:
    print("\n[ERR] Hata: Test verisi eklenirken bir sorun olustu.")
