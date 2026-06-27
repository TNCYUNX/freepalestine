# -*- coding: utf-8 -*-
import os
import shutil
import time
import subprocess

def restore_and_fix():
    print("====================================")
    print("   MySQL Hızlı Geri Yükleme & Onarım ")
    print("====================================")
    
    mysql_dir = "D:/xamkk/mysql"
    data_dir = os.path.join(mysql_dir, "data")
    old_data_dir = os.path.join(mysql_dir, "data_old_1782556291")
    
    # 1. MySQL durdurulduğundan emin ol
    print("[*] MySQL süreci sonlandırılıyor...")
    subprocess.run("taskkill /f /im mysqld.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    
    if not os.path.exists(old_data_dir):
        print("[-] Hata: Orijinal yedek klasörü (data_old_1782556291) bulunamadı!")
        return

    # 2. Hatalı/eksik kopyalanan yeni 'data' klasörünü sil
    if os.path.exists(data_dir):
        print("[*] Eksik kopyalanan geçici 'data' klasörü siliniyor...")
        try:
            shutil.rmtree(data_dir)
        except Exception as e:
            print(f"[-] Hata: Geçici 'data' klasörü silinemedi: {e}")
            return

    # 3. Orijinal klasörü geri adlandır
    print("[*] Orijinal 150 GB yedek klasörü 'data' olarak geri yükleniyor...")
    try:
        os.rename(old_data_dir, data_dir)
    except Exception as e:
        print(f"[-] Hata: Klasör geri yüklenemedi: {e}")
        return

    # 4. Hata veren log dosyalarını temizle
    logfile0 = os.path.join(data_dir, "ib_logfile0")
    logfile1 = os.path.join(data_dir, "ib_logfile1")
    
    removed = False
    if os.path.exists(logfile0):
        print("[*] Hatalı ib_logfile0 siliniyor...")
        try:
            os.remove(logfile0)
            removed = True
        except Exception as e:
            print(f"[-] Hata: ib_logfile0 silinemedi: {e}")
            
    if os.path.exists(logfile1):
        print("[*] Hatalı ib_logfile1 siliniyor...")
        try:
            os.remove(logfile1)
            removed = True
        except Exception as e:
            print(f"[-] Hata: ib_logfile1 silinemedi: {e}")

    print("\n====================================")
    print("✅ Klasörler başarıyla eski haline getirildi ve loglar temizlendi!")
    print("Lütfen şimdi XAMPP panelinden MySQL'i 'Start' edin.")
    print("MySQL açılırken temiz log dosyalarını otomatik oluşturacaktır.")
    print("====================================")

if __name__ == "__main__":
    restore_and_fix()
