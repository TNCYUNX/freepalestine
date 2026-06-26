# -*- coding: utf-8 -*-
import time
import os
import re
import database

class SecurityManager:
    def __init__(self):
        self.USER_REQUESTS = {}
        self.USER_STRIKES = {}
        self.BANNED_CACHE = set()  # Banlı kullanıcıları RAM'de tutan kara delik
        self.RATE_LIMIT_WINDOW = 1.0
        self.MAX_REQUESTS_PER_WINDOW = 3
        self.MAX_INPUT_LENGTH = 500
        
    def check_rate_limit(self, user_id):
        if user_id in self.BANNED_CACHE:
            return 'banned_cache', "🚫 Sistemden banlandınız!", None

        current_time = time.time()
        requests = self.USER_REQUESTS.get(user_id, [])
        requests = [req for req in requests if current_time - req < self.RATE_LIMIT_WINDOW]
        requests.append(current_time)
        self.USER_REQUESTS[user_id] = requests
        
        if len(requests) > self.MAX_REQUESTS_PER_WINDOW:
            strikes = self.USER_STRIKES.get(user_id, 0) + 1
            self.USER_STRIKES[user_id] = strikes
            
            # --- KRİTİK DÜZELTME: Hafızayı Sıfırla ---
            # Kullanıcının arka arkaya saliseler içinde banlanmasını önlemek için sayacı sıfırlıyoruz.
            self.USER_REQUESTS[user_id] = []
            
            if strikes >= 3:
                import database
                database.ban_user(user_id, 1, "Rate Limit (3 Uyarı)", "Saniyede 3'ten fazla tıklama (Spam)")
                self.BANNED_CACHE.add(user_id)
                return 'ban', "🚫 SPAM KORUMASI: Sistem tarafından kalıcı olarak banlandınız!", {"type": 1, "reason": "Buton Spamı", "input": "Seri Tıklama"}
            else:
                return 'warn', f"⚠️ Çok hızlı işlem yapıyorsunuz! (Uyarı: {strikes}/3)", None
        return 'ok', "", None

    def validate_input(self, user_id, text, input_type="general"):
        if user_id in self.BANNED_CACHE:
            return False, "Sistemden banlandınız.", None

        if not text: return False, "Boş girdi.", None
        text_str = str(text).strip()
        
        if len(text_str) > self.MAX_INPUT_LENGTH:
            return False, "Maksimum karakter sınırını aştınız.", None

        malicious_patterns = [
            r"<script.*?>", r"javascript:", r"drop\s+table", r"delete\s+from", 
            r"insert\s+into", r"update\s+.*set", r"--", r";\s*$"
        ]
        is_malicious = any(re.search(p, text_str, re.IGNORECASE) for p in malicious_patterns)
        
        if input_type == "coupon":
            if not re.match(r"^[A-Z0-9_-]+$", text_str.upper()):
                if is_malicious or "'" in text_str or ";" in text_str or '"' in text_str:
                    database.ban_user(user_id, 3, "Zararlı Girdi (XSS/SQLi)", text_str)
                    self.BANNED_CACHE.add(user_id)
                    return False, "🚫 SİSTEME SALDIRI TESPİT EDİLDİ! Kalıcı olarak kapatıldınız.", {"type": 3, "reason": "XSS/SQLi Saldırısı", "input": text_str}
                return False, "Geçersiz karakterler kullandınız.", None

        if is_malicious:
            database.ban_user(user_id, 3, "Zararlı Girdi (XSS/SQLi)", text_str)
            self.BANNED_CACHE.add(user_id)
            return False, "🚫 SİSTEME SALDIRI TESPİT EDİLDİ! Kalıcı olarak kapatıldınız.", {"type": 3, "reason": "XSS/SQLi Saldırısı", "input": text_str}
            
        return True, "ok", None

    def is_group_allowed(self, chat_type, chat_id):
        if chat_type == "private": return True
        allowed_group_id = os.getenv("ALLOWED_GROUP_ID")
        return bool(allowed_group_id and str(chat_id) == str(allowed_group_id))

security = SecurityManager()
