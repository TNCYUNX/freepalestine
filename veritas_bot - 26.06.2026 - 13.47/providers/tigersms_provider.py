# -*- coding: utf-8 -*-
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Tiger-SMS API URL'leri (Örnek URL, gerçek API'ye göre güncellenmelidir)
BASE_URL = "https://api.tiger-sms.com/stubs/handler_api.php"

def get_api_key():
    return os.getenv("TIGERSMS_API_KEY", "")

def get_balance():
    """Tiger-SMS hesabındaki mevcut bakiyeyi çeker."""
    api_key = get_api_key()
    if not api_key: return 0.0
    url = f"{BASE_URL}?api_key={api_key}&action=getBalance"
    try:
        response = requests.get(url, timeout=60)
        if "ACCESS_BALANCE:" in response.text:
            return float(response.text.split(":")[1])
        return 0.0
    except: return 0.0

def get_number(service_code, country_code, max_price=None):
    """Tiger-SMS üzerinden numara satın alır."""
    api_key = get_api_key()
    if not api_key: return "API_KEY_EKSIK"
    url = f"{BASE_URL}?api_key={api_key}&action=getNumber&service={service_code}&country={country_code}"
    try:
        response = requests.get(url, timeout=60)
        if "ACCESS_NUMBER:" in response.text:
            res = response.text.split(":")
            return {"id": res[1], "phone": res[2]}
        return response.text
    except: return "Bağlantı hatası."

def get_sms(activation_id):
    """SMS kodunu kontrol eder."""
    api_key = get_api_key()
    url = f"{BASE_URL}?api_key={api_key}&action=getStatus&id={activation_id}"
    try:
        response = requests.get(url, timeout=60)
        if "STATUS_OK:" in response.text:
            return response.text.split(":")[1]
        elif "STATUS_WAIT_CODE" in response.text:
            return "WAIT_CODE"
        return None
    except: return None

def cancel_number(activation_id):
    """Aktivasyonu iptal eder."""
    api_key = get_api_key()
    url = f"{BASE_URL}?api_key={api_key}&action=setStatus&status=8&id={activation_id}"
    try:
        response = requests.get(url, timeout=60)
        return "ACCESS_CANCEL" in response.text
    except: return False

def get_stock(service_code, country_code, max_price=None):
    """Tiger-SMS stok sorgulama."""
    api_key = get_api_key()
    url = f"{BASE_URL}?api_key={api_key}&action=getPrices&service={service_code}&country={country_code}"
    try:
        # Basit bir placeholder, gerçek API dönen veriye göre düzenlenmeli
        return 99
    except: return 0

def get_all_prices_and_stocks(service_code, country_code):
    """Admin için tüm fiyatları ve stok adetlerini Tiger-SMS API'sinden getirir."""
    api_key = get_api_key()
    if not api_key: return {}
    url = f"{BASE_URL}?api_key={api_key}&action=getPrices&service={service_code}&country={country_code}"
    try:
        response = requests.get(url, timeout=60)
        if not response.text.startswith('{'): return {} # JSON değilse boş dön
        data = response.json()
        c_key, s_key = str(country_code), str(service_code)
        if c_key in data and s_key in data[c_key]: 
            return data[c_key][s_key]
        return {}
    except Exception as e:
        print(f"Tiger-SMS get_all_prices_and_stocks Hatası: {e}")
        return {}
