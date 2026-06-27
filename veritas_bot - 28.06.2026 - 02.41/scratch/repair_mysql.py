# -*- coding: utf-8 -*-
import os
import shutil
import time
import subprocess

def repair():
    print("====================================")
    print("   XAMPP MySQL Otomatik Onarım      ")
    print("====================================")
    
    mysql_dir = "D:/xamkk/mysql"
    data_dir = os.path.join(mysql_dir, "data")
    backup_dir = os.path.join(mysql_dir, "backup")
    
    # 1. Herhangi bir çalışan veya askıda kalmış mysqld.exe sürecini sonlandır
    print("[*] Varsa çalışan MySQL süreçleri sonlandırılıyor...")
    subprocess.run("taskkill /f /im mysqld.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    
    if not os.path.exists(data_dir):
        print("[-] Hata: D:/xamkk/mysql/data dizini bulunamadı!")
        return
        
    if not os.path.exists(backup_dir):
        print("[-] Hata: D:/xamkk/mysql/backup dizini bulunamadı!")
        return

    # 2. Mevcut data klasörünü yedekle (Zaman damgası ile benzersiz isim vererek)
    timestamp = int(time.time())
    backup_target = os.path.join(mysql_dir, f"data_old_{timestamp}")
    
    print(f"[*] Mevcut data klasörü '{backup_target}' olarak yeniden adlandırılıyor...")
    try:
        os.rename(data_dir, backup_target)
    except Exception as e:
        print(f"[-] Hata: data klasörü yeniden adlandırılamadı! Dosyalar kilitli olabilir: {e}")
        return
        
    # 3. Temiz backup klasörünü data olarak kopyala
    print("[*] Temiz yedek (backup) klasörü yeni 'data' olarak kopyalanıyor...")
    try:
        shutil.copytree(backup_dir, data_dir)
    except Exception as e:
        print(f"[-] Hata: backup klasörü data olarak kopyalanamadı: {e}")
        # Geri al
        try: os.rename(backup_target, data_dir)
        except: pass
        return

    # 4. Eski veritabanı klasörlerini yeni data klasörüne kopyala
    print("[*] Özel veritabanı klasörleri yeni data dizinine aktarılıyor...")
    ignored_folders = {"mysql", "performance_schema", "phpmyadmin", "test"}
    
    for item in os.listdir(backup_target):
        item_path = os.path.join(backup_target, item)
        if os.path.isdir(item_path):
            if item.lower() not in ignored_folders:
                dst_path = os.path.join(data_dir, item)
                print(f" -> Veritabanı kopyalanıyor: {item}")
                try:
                    shutil.copytree(item_path, dst_path)
                except Exception as e:
                    print(f"  [!] Hata: {item} veritabanı kopyalanamadı: {e}")

    # 5. Ana veri dosyası ibdata1'i eski klasörden yeni klasöre taşı (üzerine yaz)
    src_ibdata = os.path.join(backup_target, "ibdata1")
    dst_ibdata = os.path.join(data_dir, "ibdata1")
    
    if os.path.exists(src_ibdata):
        print("[*] ibdata1 dosyası aktarılıyor...")
        try:
            shutil.copy2(src_ibdata, dst_ibdata)
        except Exception as e:
            print(f"[-] Hata: ibdata1 dosyası kopyalanamadı: {e}")
    else:
        print("[!] Uyarı: Eski data klasöründe ibdata1 dosyası bulunamadı!")

    print("\n====================================")
    print("✅ MySQL Onarım İşlemi Tamamlandı!")
    print("Lütfen XAMPP Control Panel'i açıp MySQL'i tekrar 'Start' edin.")
    print("====================================")

if __name__ == "__main__":
    repair()
