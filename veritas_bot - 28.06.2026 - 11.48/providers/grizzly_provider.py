# -*- coding: utf-8 -*-
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Grizzly SMS API URL'leri
BASE_URL = "https://api.grizzlysms.com/stubs/handler_api.php"
CRYPTO_URL = "https://api.grizzlysms.com/public/crypto/wallet"

def get_api_key():
    return os.getenv("GRIZZLY_API_KEY", "")

def get_balance():
    """Grizzly SMS hesabındaki mevcut bakiyeyi (USD/RUB) çeker."""
    api_key = get_api_key()
    if not api_key: return 0.0
    url = f"{BASE_URL}?api_key={api_key}&action=getBalance"
    try:
        response = requests.get(url, timeout=15)
        text = response.text
        if "ACCESS_BALANCE:" in text:
            return float(text.split(":")[1])
        return 0.0
    except Exception as e:
        print(f"Grizzly API get_balance Hatası: {e}")
        return 0.0

def get_crypto_wallet():
    """Bakiye yüklemek için TRC-20 (USDT) kripto cüzdan adresini çeker."""
    api_key = get_api_key()
    if not api_key: return "API_KEY_EKSIK"
    url = f"{CRYPTO_URL}?api_key={api_key}&coin=usdt&network=tron"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        if "wallet_address" in data:
            return data["wallet_address"]
        return "CÜZDAN_ALINAMADI"
    except Exception as e:
        print(f"Grizzly API get_crypto_wallet Hatası: {e}")
        return "BAĞLANTI_HATASI"

def get_number(service_code, country_code, max_price=None):
    """Grizzly SMS üzerinden numara satın alır ve ref_id ile %5 komisyon biriktirir."""
    api_key = get_api_key()
    ref_id = os.getenv("GRIZZLY_REF_ID", "") 
    if not api_key: return "API_KEY_EKSIK"
    
    url = f"{BASE_URL}?api_key={api_key}&action=getNumberV2&service={service_code}&country={country_code}"
    if ref_id: url += f"&ref={ref_id}&ref_id={ref_id}" 
    if max_price: url += f"&maxPrice={max_price}"
    
    try:
        response = requests.get(url, timeout=15)
        if "NO_BALANCE" in response.text: return "Sistemde bakiye yetersiz."
        if "NO_NUMBERS" in response.text: return "Bu servis için numara kalmadı."
        if "BAD_SERVICE" in response.text or "BAD_KEY" in response.text: return "Sistemsel bir API hatası oluştu."
        data = response.json()
        act_id, phone = data.get("activationId"), data.get("phoneNumber")
        return {"id": act_id, "phone": phone} if act_id and phone else "Numara alınamadı."
    except Exception as e:
        print(f"Grizzly API get_number Hatası: {e}")
        return "Bağlantı hatası oluştu."

def get_sms(activation_id):
    """Aktivasyon ID'si için SMS kodunu kontrol eder."""
    # --- SIMULASYON VE TEST KANCASI ---
    if str(activation_id) == "test_success_123":
        return "99988"  # Taklit SMS Kodu
    if str(activation_id) == "test_timeout_123":
        return "WAIT_CODE"
    if str(activation_id) == "test_active_123":
        return "WAIT_CODE"

    api_key = get_api_key()
    url = f"{BASE_URL}?api_key={api_key}&action=getStatus&id={activation_id}"
    try:
        response = requests.get(url, timeout=15)
        text = response.text
        if "STATUS_OK:" in text:
            return text.split(":")[1]
        elif "STATUS_WAIT_CODE" in text:
            return "WAIT_CODE"
        elif "STATUS_CANCEL" in text:
            return "STATUS_CANCEL"
        return None
    except Exception as e:
        print(f"Grizzly API get_sms Hatası: {e}")
        return None

def cancel_number(activation_id):
    """Aktivasyonu iptal eder."""
    api_key = get_api_key()
    url = f"{BASE_URL}?api_key={api_key}&action=setStatus&status=8&id={activation_id}"
    try:
        response = requests.get(url, timeout=15)
        resp_text = response.text.upper()
        if "CANCEL" in resp_text or "SUCCESS" in resp_text:
            return True
        print(f"Grizzly Iptal Reddedildi. Yanıt: {response.text}")
        return False
    except Exception as e:
        print(f"Grizzly API cancel_number Hatası: {e}")
        return False

def get_stock(service_code, country_code, max_price):
    """Grizzly getPricesV2 ile kesin stok adedini döndürür."""
    api_key = get_api_key()
    if not api_key: return 0
    url = f"{BASE_URL}?api_key={api_key}&action=getPricesV2&service={service_code}&country={country_code}"
    try:
        response = requests.get(url, timeout=15)
        if not response.text.startswith('{'): return 0 # JSON değilse (örn BAD_KEY) 0 dön
        data = response.json()
        c_key, s_key = str(country_code), str(service_code)
        if c_key in data and s_key in data[c_key]:
            fiyat_havuzu = data[c_key][s_key]
            target_price = float(str(max_price).replace(',', '.'))
            if isinstance(fiyat_havuzu, dict):
                for api_fiyat, stok_adedi in fiyat_havuzu.items():
                    if abs(float(api_fiyat) - target_price) < 0.01: return int(stok_adedi)
        return 0
    except: return 0

def get_all_prices_and_stocks(service_code, country_code):
    """Tüm fiyat ve stok kırılımlarını döndürür (Admin için)."""
    api_key = get_api_key()
    if not api_key: return {}
    url = f"{BASE_URL}?api_key={api_key}&action=getPricesV2&service={service_code}&country={country_code}"
    try:
        response = requests.get(url, timeout=15)
        if not response.text.startswith('{'): return {} # JSON değilse boş dön
        data = response.json()
        c_key, s_key = str(country_code), str(service_code)
        if c_key in data and s_key in data[c_key]: return data[c_key][s_key]
        return {}
    except Exception as e:
        print(f"Grizzly get_all_prices_and_stocks Hatası: {e}")
        return {}
