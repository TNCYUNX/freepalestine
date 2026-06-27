# -*- coding: utf-8 -*-
import os
import shutil
import time
import subprocess

def isolate():
    print("====================================")
    print("   Veritas_SMS Izolasyon & Kurtarma ")
    print("====================================")
    
    mysql_dir = "D:/xamkk/mysql"
    data_dir = os.path.join(mysql_dir, "data")
    backup_target = os.path.join(mysql_dir, "other_dbs_backup")
    
    # 1. Herhangi bir çalışan veya askıda kalmış mysqld.exe sürecini sonlandır
    print("[*] MySQL süreçleri sonlandırılıyor...")
    subprocess.run("taskkill /f /im mysqld.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    
    if not os.path.exists(data_dir):
        print("[-] Hata: data dizini bulunamadı!")
        return

    # 2. other_dbs_backup klasörünü oluştur
    if not os.path.exists(backup_target):
        os.makedirs(backup_target)
        print(f"[*] Yedek klasörü oluşturuldu: {backup_target}")

    # 3. Veritas_SMS dışındaki veritabanlarını other_dbs_backup klasörüne taşı
    keep_folders = {"mysql", "performance_schema", "phpmyadmin", "test", "veritas_sms"}
    
    print("[*] Diğer 150 GB veritabanı klasörleri taşınıyor...")
    for item in os.listdir(data_dir):
        item_path = os.path.join(data_dir, item)
        if os.path.isdir(item_path):
            if item.lower() not in keep_folders and not item.endswith("_corrupt"):
                dst = os.path.join(backup_target, item)
                print(f" -> Taşınıyor: {item}")
                try:
                    # Hedefte varsa önce temizle
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.move(item_path, dst)
                except Exception as e:
                    print(f"  [!] Hata: {item} taşınamadı: {e}")

    # 4. Tüm logları ve geçici dosyaları (Aria logları dahil) tamamen temizle
    print("[*] Eski loglar ve kontrol dosyaları temizleniyor...")
    files_to_remove = [
        "ib_logfile0", "ib_logfile1", "ibtmp1",
        "aria_log.00000001", "aria_log.00000002", "aria_log.00000003",
        "aria_log.00000004", "aria_log.00000005", "aria_log.00000006",
        "aria_log.00000007", "aria_log.00000008", "aria_log.00000009",
        "aria_log_control"
    ]
    
    for f in files_to_remove:
        f_path = os.path.join(data_dir, f)
        if os.path.exists(f_path):
            try:
                os.remove(f_path)
                print(f"  -> Silindi: {f}")
            except Exception as e:
                print(f"  [!] Hata: {f} silinemedi: {e}")

    print("\n====================================")
    print("✅ İzolyasyon işlemi tamamlandı!")
    print("Diğer veritabanlarınız 'other_dbs_backup' klasöründe güvende.")
    print("Lütfen şimdi XAMPP panelinden MySQL'i tekrar 'Start' edin.")
    print("====================================")

if __name__ == "__main__":
    isolate()
