# -*- coding: utf-8 -*-
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def get_live_rates():
    """
    Binance API'sini kullanarak USDT/TRY ve TRX/TRY canlı kurlarını çeker ve veritabanına kaydeder.
    API'de bir sorun olursa, veritabanındaki son kura 1 TL (güvenlik marjı) ekleyerek döndürür.
    """
    import database
    url_usdt = "https://api.binance.com/api/v3/ticker/price?symbol=USDTTRY"
    url_trx = "https://api.binance.com/api/v3/ticker/price?symbol=TRXTRY"
    
    # Varsayılan kurlar (Veritabanında da yoksa kullanılır)
    kurlar = {"usdt": 46.0, "trx": 4.5}
    
    try:
        res_usdt = requests.get(url_usdt, timeout=5)
        if res_usdt.status_code == 200:
            usdt_fiyat = float(res_usdt.json().get("price", 46.0))
            kurlar["usdt"] = round(usdt_fiyat, 2)
            database.update_setting("last_usdt_rate", str(kurlar["usdt"]))
            
        res_trx = requests.get(url_trx, timeout=5)
        if res_trx.status_code == 200:
            trx_fiyat = float(res_trx.json().get("price", 4.5))
            kurlar["trx"] = round(trx_fiyat, 2)
            database.update_setting("last_trx_rate", str(kurlar["trx"]))
            
    except Exception as e:
        print(f"Binance API Çöktü! Veritabanı yedeği devreye giriyor: {e}")
        # API çökerse DB'den son kuru al ve zarar etmemek için 1 TL ekle
        db_usdt = float(database.get_setting("last_usdt_rate", "46.0"))
        db_trx = float(database.get_setting("last_trx_rate", "4.5"))
        kurlar["usdt"] = round(db_usdt + 1.0, 2)
        kurlar["trx"] = round(db_trx + 1.0, 2)
        
    return kurlar

def get_valid_incoming_transfers():
    """
    TRON MAINNET üzerinden son işlemleri çeker. Merkezi Tarayıcı (Global Scanner) için tasarlanmıştır.
    Sahte USDT (Spoofing) ve Dust (Toz) saldırılarını KRİTİK seviyede engeller.
    """
    import database
    cuzdan = os.getenv("TRON_WALLET_ADDRESS")
    api_key = os.getenv("TRON_PRO_API_KEY", "")
    if not cuzdan: return []

    valid_transfers = []
    headers = {"TRON-PRO-API-KEY": api_key, "Accept": "application/json"} if api_key else {"Accept": "application/json"}

    # --- 1. USDT (TRC20) KONTROLÜ (SMART CONTRACT KORUMALI) ---
    url_trc20 = f"https://api.trongrid.io/v1/accounts/{cuzdan}/transactions/trc20"
    try:
        res = requests.get(url_trc20, params={"limit": 50, "only_to": "true"}, headers=headers, timeout=10)
        if res.status_code == 200:
            for tx in res.json().get("data", []):
                token_address = tx.get("token_info", {}).get("address")
                # KRİTİK GÜVENLİK: SADECE VE SADECE GERÇEK USDT KONTRATI KABUL EDİLİR! SAHTE TOKENLER REDDEDİLİR!
                if token_address == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":
                    decimals = int(tx["token_info"].get("decimals", 6))
                    tx_amount = float(tx["value"]) / (10 ** decimals)
                    # DUST (TOZ) SALDIRISI FİLTRESİ: 1 Dolar altı çöp işlemleri yoksay
                    if tx_amount >= 1.0: 
                        txid = tx.get("transaction_id")
                        if txid and not database.is_tx_processed(txid):
                            valid_transfers.append({"type": "USDT", "amount": tx_amount, "txid": txid})
    except Exception as e:
        print(f"Mainnet USDT Scanner Hatası: {e}")

    # --- 2. YEREL TRX KONTROLÜ ---
    url_trx = f"https://api.trongrid.io/v1/accounts/{cuzdan}/transactions"
    try:
        res = requests.get(url_trx, params={"limit": 50, "only_to": "true"}, headers=headers, timeout=10)
        if res.status_code == 200:
            for tx in res.json().get("data", []):
                contracts = tx.get("raw_data", {}).get("contract", [])
                if contracts and contracts[0].get("type") == "TransferContract":
                    amount_sun = float(contracts[0].get("parameter", {}).get("value", {}).get("amount", 0))
                    tx_amount = amount_sun / 1_000_000.0
                    # DUST (TOZ) SALDIRISI FİLTRESİ: 1 TRX altı işlemleri yoksay
                    if tx_amount >= 1.0: 
                        txid = tx.get("txID")
                        if txid and not database.is_tx_processed(txid):
                            valid_transfers.append({"type": "TRX", "amount": tx_amount, "txid": txid})
    except Exception as e:
        print(f"Mainnet TRX Scanner Hatası: {e}")

    return valid_transfers
