# -*- coding: utf-8 -*-
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def get_live_rates():
    """Binance API üzerinden USDT ve TRX kurunu güvenli şekilde çeker."""
    import database
    url_usdt = "https://api.binance.com/api/v3/ticker/price?symbol=USDTTRY"
    url_trx = "https://api.binance.com/api/v3/ticker/price?symbol=TRXTRY"
    kurlar = {"usdt": 46.0, "trx": 4.5}
    
    try:
        res_usdt = requests.get(url_usdt, timeout=5)
        if res_usdt.status_code == 200:
            kurlar["usdt"] = round(float(res_usdt.json().get("price", 46.0)), 2)
            database.update_setting("last_usdt_rate", str(kurlar["usdt"]))
            
        res_trx = requests.get(url_trx, timeout=5)
        if res_trx.status_code == 200:
            kurlar["trx"] = round(float(res_trx.json().get("price", 4.5)), 2)
            database.update_setting("last_trx_rate", str(kurlar["trx"]))
            
    except Exception:
        # Hata mesajında URL veya API Anahtarı sızdırılmaz.
        print("Binance API Hatası: Veritabanı yedeği devreye giriyor.")
        db_usdt = float(database.get_setting("last_usdt_rate", "46.0"))
        db_trx = float(database.get_setting("last_trx_rate", "4.5"))
        kurlar["usdt"] = round(db_usdt + 1.0, 2)
        kurlar["trx"] = round(db_trx + 1.0, 2)
        
    return kurlar

def get_valid_incoming_transfers():
    """TRON MAINNET üzerinden SCAM korumalı, Dust Attack filtreli tarama yapar."""
    import database
    
    # GÜVENLİK: .env dosyasından gelen verileri temizle (tırnak işaretlerini kaldır)
    def clean_env(key, default=""):
        val = os.getenv(key, default)
        if val:
            return val.strip().strip('"').strip("'")
        return default

    cuzdan_usdt = clean_env("USDT_WALLET_ADDRESS", clean_env("TRON_WALLET_ADDRESS"))
    cuzdan_trx = clean_env("TRX_WALLET_ADDRESS", clean_env("TRON_WALLET_ADDRESS"))
    api_key = clean_env("TRON_PRO_API_KEY")

    valid_transfers = []
    headers = {"Accept": "application/json"}
    if api_key:
        headers["TRON-PRO-API-KEY"] = api_key

    # GÜVENLİK: Resmi TRC20 USDT Smart Contract Adresi
    USDT_CONTRACT_ADDRESS = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

    # --- 1. MAINNET USDT (TRC20) TARAMASI ---
    if cuzdan_usdt:
        # URL: /transactions/trc20 endpointi sadece TRC20 transferlerini döner.
        # contract_address parametresi ile sadece USDT filtreliyoruz (daha güvenli ve hızlı)
        url_trc20 = f"https://api.trongrid.io/v1/accounts/{cuzdan_usdt}/transactions/trc20"
        params = {
            "limit": 50,
            "contract_address": USDT_CONTRACT_ADDRESS,
            "only_to": "true" # Bazı TronGrid sürümleri için ek filtre
        }
        try:
            res = requests.get(url_trc20, params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json().get("data", [])
                for tx in data:
                    # Teyit: Alıcı biz miyiz?
                    to_address = tx.get("to", "")
                    if to_address == cuzdan_usdt:
                        decimals = int(tx.get("token_info", {}).get("decimals", 6))
                        value_raw = tx.get("value", "0")
                        tx_amount = float(value_raw) / (10 ** decimals)
                        
                        # DUST ATTACK FİLTRESİ
                        if tx_amount >= 1.0: 
                            txid = tx.get("transaction_id")
                            if txid and not database.is_tx_processed(txid):
                                valid_transfers.append({"type": "USDT", "amount": tx_amount, "txid": txid})
            else:
                print(f"TronGrid USDT API Hatası: {res.status_code}")
        except Exception:
            print("TronGrid API Bağlantı Hatası (USDT)")

    # --- 2. MAINNET TRX TARAMASI ---
    if cuzdan_trx:
        url_trx = f"https://api.trongrid.io/v1/accounts/{cuzdan_trx}/transactions"
        try:
            res = requests.get(url_trx, params={"limit": 50, "only_to": "true"}, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json().get("data", [])
                for tx in data:
                    # TRX transferleri 'TransferContract' tipindedir.
                    contracts = tx.get("raw_data", {}).get("contract", [])
                    if contracts and contracts[0].get("type") == "TransferContract":
                        # İşlem başarılı mı? (ret listesi içindeki code kontrolü)
                        ret = tx.get("ret", [])
                        if ret and ret[0].get("contractRet") != "SUCCESS":
                            continue
                            
                        amount_sun = float(contracts[0].get("parameter", {}).get("value", {}).get("amount", 0))
                        tx_amount = amount_sun / 1_000_000.0
                        
                        # DUST ATTACK FİLTRESİ
                        if tx_amount >= 1.0: 
                            txid = tx.get("txID")
                            if txid and not database.is_tx_processed(txid):
                                valid_transfers.append({"type": "TRX", "amount": tx_amount, "txid": txid})
            else:
                print(f"TronGrid TRX API Hatası: {res.status_code}")
        except Exception:
            print("TronGrid API Bağlantı Hatası (TRX)")

    return valid_transfers

def check_usdt_payment(expected_amount):
    """Manuel kontrol butonu için USDT ödemesini doğrular ve TXID döner."""
    transfers = get_valid_incoming_transfers()
    for tx in transfers:
        if tx["type"] == "USDT" and abs(tx["amount"] - float(expected_amount)) < 0.001:
            return tx["txid"]
    return False

def check_trx_payment(expected_amount):
    """Manuel kontrol butonu için TRX ödemesini doğrular ve TXID döner."""
    transfers = get_valid_incoming_transfers()
    for tx in transfers:
        if tx["type"] == "TRX" and abs(tx["amount"] - float(expected_amount)) < 0.001:
            return tx["txid"]
    return False
