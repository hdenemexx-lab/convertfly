# -*- coding: utf-8 -*-
"""
Veritabanı migrasyon scripti — eksik sütunları güvenli biçimde ekler.
Çalıştır: python migrate_db.py
"""
import sys

try:
    import pymysql
except ImportError:
    print("pymysql bulunamadı, pip install pymysql")
    sys.exit(1)

DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = ""
DB_NAME = "file_converter"

conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset="utf8mb4")
cur  = conn.cursor()

EKLEMELER = [
    # (tablo, sütun, tanım)
    ("donusum", "dosya_adi",  "VARCHAR(255) NULL"),
    ("dosya_paylasim", "silindi", "TINYINT(1) NOT NULL DEFAULT 0"),
    ("kullanici", "plan", "VARCHAR(10) NOT NULL DEFAULT 'normal'"),
    ("dosya_paylasim", "baslik", "VARCHAR(120) NULL"),
    ("dosya_paylasim", "saklama_gun", "INT NULL"),
    ("dosya_paylasim", "expire_at", "DATETIME NULL"),
    # VirusTotal tarama alanları (Pro kullanıcılar)
    ("dosya_paylasim", "vt_tarama_sonucu", "VARCHAR(20) NULL"),
    ("dosya_paylasim", "vt_tehdit_adi",    "VARCHAR(255) NULL"),
    ("dosya_paylasim", "vt_tarama_tarihi", "DATETIME NULL"),
    # Admin yetkisi
    ("kullanici", "is_admin", "TINYINT(1) NOT NULL DEFAULT 0"),
    # Ban durumu ve son giriş
    ("kullanici", "bantli", "TINYINT(1) NOT NULL DEFAULT 0"),
    ("kullanici", "son_giris", "DATETIME NULL"),
]

print("Migrasyon başlatılıyor...\n")

for tablo, sutun, tanim in EKLEMELER:
    # Sütun var mı kontrol et
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
        (DB_NAME, tablo, sutun)
    )
    var = cur.fetchone()[0]
    if var:
        print(f"  [ZATEN VAR]  {tablo}.{sutun}")
    else:
        try:
            sql = f"ALTER TABLE `{tablo}` ADD COLUMN `{sutun}` {tanim}"
            cur.execute(sql)
            conn.commit()
            print(f"  [EKLENDI]    {tablo}.{sutun}")
        except Exception as e:
            print(f"  [HATA]       {tablo}.{sutun}: {str(e)}")

cur.close()
conn.close()
print("\nMigrasyon tamamlandı.")
