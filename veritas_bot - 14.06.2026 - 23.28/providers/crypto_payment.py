# -*- coding: utf-8 -*-
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# --- AĞ AYARLARI (TESTNET - NILE) ---
TRON_NETWORK = os.getenv("TRON_NETWORK", "nile").lower()

if TRON_NETWORK == "mainnet":
    BASE_URL = "https://api.trongrid.io"
    NETWORK_NAME = "Tron Mainnet"
else:
    BASE_URL = "https://nile.trongrid.io"
    NETWORK_NAME = "Tron Nile Testnet"

def get_live_rates():
    import database
    url_usdt = "https://api.binance.com/api/v3/ticker/price?symbol=USDTTRY"
    url_trx = "https://api.binance.com/api/v3/ticker/price?symbol=TRXTRY"
    kurlar = {"usdt": 46.0, "trx": 15.0}
    
    try:
        res_usdt = requests.get(url_usdt, timeout=5)
        if res_usdt.status_code == 200:
            kurlar["usdt"] = round(float(res_usdt.json().get("price", 46.0)), 2)
            database.update_setting("last_usdt_rate", str(kurlar["usdt"]))
            
        res_trx = requests.get(url_trx, timeout=5)
        if res_trx.status_code == 200:
            kurlar["trx"] = round(float(res_trx.json().get("price", 15.0)), 2)
            database.update_setting("last_trx_rate", str(kurlar["trx"]))
    except Exception:
        db_usdt = float(database.get_setting("last_usdt_rate", "46.0"))
        db_trx = float(database.get_setting("last_trx_rate", "15.0"))
        kurlar["usdt"] = round(db_usdt, 2)
        kurlar["trx"] = round(db_trx, 2)
        
    return kurlar

def get_valid_incoming_transfers():
    import database
    cuzdan = os.getenv("TRON_WALLET_ADDRESS", "").strip()
    api_key = os.getenv("TRON_PRO_API_KEY", "").strip()

    valid_transfers = []
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    if TRON_NETWORK == "mainnet" and api_key: 
        headers["TRON-PRO-API-KEY"] = api_key

    if cuzdan:
        # 1. USDT (TRC20) Taraması
        url_usdt = f"{BASE_URL}/v1/accounts/{cuzdan}/transactions/trc20"
        # 400 HATASI ÇÖZÜMÜ: contract_address parametresini tamamen kaldırdık. 
        # Artık cüzdana gelen tüm TRC20'leri çekecek, Python ile filtreleyeceğiz.
        params = {"limit": 30, "only_to": "true"}
        try:
            res = requests.get(url_usdt, params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json().get("data", [])
                for tx in data:
                    # Token sembolü USDT ise işleme al (Büyük/küçük harf duyarsız)
                    if tx.get("to") == cuzdan and tx.get("token_info", {}).get("symbol", "").upper() == "USDT":
                        decimals = int(tx.get("token_info", {}).get("decimals", 6))
                        tx_amount = float(tx.get("value", "0")) / (10 ** decimals)
                        if tx_amount >= 1.0: 
                            txid = tx.get("transaction_id")
                            if txid and not database.is_tx_processed(txid):
                                valid_transfers.append({"type": "USDT", "amount": tx_amount, "txid": txid})
            else:
                print(f"USDT Tarama Hatası ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"USDT Tarama İstek Hatası: {e}")

        # 2. TRX Taraması
        url_trx = f"{BASE_URL}/v1/accounts/{cuzdan}/transactions"
        params_trx = {"limit": 30, "only_to": "true"}
        try:
            res = requests.get(url_trx, params=params_trx, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json().get("data", [])
                for tx in data:
                    contracts = tx.get("raw_data", {}).get("contract", [])
                    if contracts and contracts[0].get("type") == "TransferContract":
                        ret = tx.get("ret", [])
                        if ret and ret[0].get("contractRet") == "SUCCESS":
                            amount_sun = float(contracts[0].get("parameter", {}).get("value", {}).get("amount", 0))
                            tx_amount = amount_sun / 1_000_000.0
                            if tx_amount >= 1.0: 
                                txid = tx.get("txID")
                                if txid and not database.is_tx_processed(txid):
                                    valid_transfers.append({"type": "TRX", "amount": tx_amount, "txid": txid})
            else:
                print(f"TRX Tarama Hatası ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"TRX Tarama İstek Hatası: {e}")

    return valid_transfers