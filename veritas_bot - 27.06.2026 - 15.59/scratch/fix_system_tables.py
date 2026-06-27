# -*- coding: utf-8 -*-
import os
import shutil
import time
import subprocess

def fix_system_tables():
    print("====================================")
    print("   MySQL Sistem Tabloları Onarımı   ")
    print("====================================")
    
    mysql_dir = "D:/xamkk/mysql"
    data_dir = os.path.join(mysql_dir, "data")
    backup_dir = os.path.join(mysql_dir, "backup")
    
    # 1. Herhangi bir çalışan mysqld.exe sürecini durdur
    print("[*] MySQL süreci sonlandırılıyor...")
    subprocess.run("taskkill /f /im mysqld.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    
    if not os.path.exists(data_dir) or not os.path.exists(backup_dir):
        print("[-] Dizin bulunamadı!")
        return

    # 2. Sistem veritabanlarını yedekle ve sil
    system_dbs = ["mysql", "performance_schema", "phpmyadmin"]
    for db in system_dbs:
        src = os.path.join(data_dir, db)
        backup_src = os.path.join(data_dir, f"{db}_corrupt")
        if os.path.exists(src):
            print(f"[*] Eski '{db}' klasörü yedekleniyor ve siliniyor...")
            if os.path.exists(backup_src):
                try: shutil.rmtree(backup_src)
                except: pass
            try:
                os.rename(src, backup_src)
            except Exception as e:
                print(f"[-] Hata: {db} klasörü yedeklenemedi, siliniyor... {e}")
                try: shutil.rmtree(src)
                except: pass

        # 3. Temiz olanları backup klasöründen kopyala
        clean_src = os.path.join(backup_dir, db)
        if os.path.exists(clean_src):
            print(f"[*] Temiz '{db}' klasörü kopyalanıyor...")
            try:
                shutil.copytree(clean_src, src)
            except Exception as e:
                print(f"[-] Hata: {db} kopyalanamadı: {e}")

    # 4. ib_logfile'ları tekrar kontrol et ve varsa sil (sıfırlansınlar)
    logfile0 = os.path.join(data_dir, "ib_logfile0")
    logfile1 = os.path.join(data_dir, "ib_logfile1")
    try:
        if os.path.exists(logfile0): os.remove(logfile0)
        if os.path.exists(logfile1): os.remove(logfile1)
        print("[*] ib_logfile dosyaları temizlendi.")
    except Exception as e:
        print(f"[!] Log temizleme uyarısı: {e}")

    print("\n====================================")
    print("✅ Sistem tabloları başarıyla temizlendi!")
    print("Lütfen şimdi XAMPP panelinden MySQL'i tekrar 'Start' edin.")
    print("====================================")

if __name__ == "__main__":
    fix_system_tables()
