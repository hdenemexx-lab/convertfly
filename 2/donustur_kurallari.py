# -*- coding: utf-8 -*-
"""
Dönüştürme kuralları: uzantı → kategori (kovan), kovan → izin verilen çıktılar.
Sunucu ve istemci aynı mantığı paylaşır (istemciye JSON olarak aktarılır).
"""

from __future__ import annotations

# Arayüzde gösterilecek kategori başlıkları (kovan anahtarı → Türkçe etiket)
KATEGORI_ETIKET: dict[str, str] = {
    "arsiv": "Arşiv",
    "cad": "CAD",
    "ebook": "E-kitap",
    "evrak": "Evraklar",
    "goruntu": "Görüntüler",
    "ses": "Sesli",
    "sunum": "Sunumlar",
    "vektor": "Vektörler",
    "video": "Videolar",
    "yazi_tipi": "Yazı tipleri",
}

# Dosya uzantısı (küçük harf, noktalı) → iç mantık kovanı
UZANTI_KOVAN: dict[str, str] = {
    # Arşiv
    ".7z": "arsiv", ".zip": "arsiv", ".rar": "arsiv", ".tar": "arsiv",
    ".gz": "arsiv", ".tgz": "arsiv", ".bz2": "arsiv", ".lz": "arsiv",
    # CAD
    ".dxf": "cad", ".dwg": "cad",
    # E-kitap
    ".epub": "ebook", ".mobi": "ebook", ".azw3": "ebook", ".fb2": "ebook",
    # Evraklar
    ".pdf": "evrak", ".doc": "evrak", ".docx": "evrak", ".txt": "evrak",
    ".rtf": "evrak", ".csv": "evrak", ".xls": "evrak", ".xlsx": "evrak",
    ".html": "evrak", ".json": "evrak", ".tsv": "evrak", ".md": "evrak",
    ".log": "evrak",
    # Görüntüler
    ".png": "goruntu", ".jpg": "goruntu", ".jpeg": "goruntu", ".webp": "goruntu",
    ".gif": "goruntu", ".bmp": "goruntu", ".tiff": "goruntu", ".tif": "goruntu",
    ".ico": "goruntu", ".avif": "goruntu", ".heic": "goruntu",
    # Ses
    ".mp3": "ses", ".wav": "ses", ".ogg": "ses", ".flac": "ses",
    ".m4a": "ses", ".aac": "ses", ".wma": "ses", ".opus": "ses",
    # Sunum
    ".ppt": "sunum", ".pptx": "sunum", ".odp": "sunum", ".pps": "sunum",
    # Vektörler
    ".svg": "vektor", ".eps": "vektor", ".ai": "vektor", ".cdr": "vektor",
    # Videolar
    ".mp4": "video", ".mkv": "video", ".avi": "video", ".mov": "video",
    ".webm": "video", ".flv": "video", ".wmv": "video", ".m4v": "video",
    ".3gp": "video", ".mpeg": "video", ".mpg": "video",
    # Yazı tipleri
    ".ttf": "yazi_tipi", ".otf": "yazi_tipi", ".woff": "yazi_tipi",
}

# Kovan → (çıktı_kodu, kullanıcı etiketi); yalnızca bu hedeflere dönüşüm izni var
CIKTI_SECENEKLERI: dict[str, list[tuple[str, str]]] = {
    "arsiv": [
        ("zip", "ZIP (hazır değil)"),
        ("rar", "RAR (hazır değil)"),
        ("7z", "7Z (hazır değil)"),
        ("tar", "TAR (hazır değil)")
    ],
    "cad": [
        ("dxf", "DXF (hazır değil)"),
        ("dwg", "DWG (hazır değil)")
    ],
    "ebook": [
        ("epub", "EPUB (hazır değil)"),
        ("mobi", "MOBI (hazır değil)"),
        ("azw3", "AZW3 (hazır değil)")
    ],
    "evrak": [
        ("txt", "TXT"),
        ("pdf", "PDF (hazır değil)"),
        ("docx", "DOCX (hazır değil)"),
        ("csv", "CSV"),
        ("json", "JSON"),
        ("tsv", "TSV"),
        ("txt_ocr", "TXT (OCR)")
    ],
    "goruntu": [
        ("png", "PNG"),
        ("jpeg", "JPEG"),
        ("webp", "WEBP"),
        ("bmp", "BMP"),
        ("tiff", "TIFF"),
        ("gif", "GIF"),
        ("ico", "ICO (hazır değil)")
    ],
    "ses": [
        ("mp3", "MP3"),
        ("wav", "WAV"),
        ("ogg", "OGG"),
        ("flac", "FLAC (hazır değil)"),
        ("m4a", "M4A (hazır değil)"),
        ("aac", "AAC (hazır değil)")
    ],
    "sunum": [
        ("txt", "TXT"),
        ("pptx", "PPTX (hazır değil)"),
        ("ppt", "PPT (hazır değil)")
    ],
    "vektor": [
        ("svg", "SVG (hazır değil)"),
        ("eps", "EPS (hazır değil)"),
        ("ai", "AI (hazır değil)")
    ],
    "video": [
        ("mp4", "MP4"),
        ("webm", "WEBM"),
        ("avi", "AVI (hazır değil)"),
        ("mkv", "MKV (hazır değil)"),
        ("mov", "MOV (hazır değil)"),
        ("flv", "FLV (hazır değil)")
    ],
    "yazi_tipi": [
        ("ttf", "TTF (hazır değil)"),
        ("otf", "OTF (hazır değil)"),
        ("woff", "WOFF (hazır değil)")
    ]
}


def kovan_bul(uzanti: str) -> str | None:
    """Uzantıyı küçük harf noktalı bekler; bilinmiyorsa None."""
    u = uzanti.lower().strip()
    if not u.startswith("."):
        u = f".{u}" if u else ""
    return UZANTI_KOVAN.get(u)


def izinli_hedef(kovan: str | None, hedef_kod: str) -> bool:
    """Bu kovan için hedef çıktı koduna izin var mı?"""
    if not kovan:
        return False
    hedef_kod = hedef_kod.strip().lower()
    return any(v == hedef_kod for v, _ in CIKTI_SECENEKLERI.get(kovan, []))


def hedef_utku_ayni_mi(kaynak_uzanti: str, hedef_kod: str) -> bool:
    """Kaynak zaten hedef formattaysa anlamsız dönüşümü engellemek için (isteğe bağlı)."""
    h = hedef_kod.lower()
    u = kaynak_uzanti.lower()
    goruntu_map = {
        "png": ".png",
        "jpeg": {".jpg", ".jpeg"},
        "webp": ".webp",
        "bmp": ".bmp",
        "tiff": {".tif", ".tiff"},
        "gif": ".gif",
    }
    if h in goruntu_map:
        beklenen = goruntu_map[h]
        if isinstance(beklenen, set):
            return u in beklenen
        return u == beklenen
    if h == "mp3" and u == ".mp3": return True
    if h == "wav" and u == ".wav": return True
    if h == "ogg" and u == ".ogg": return True
    if h == "mp4" and u == ".mp4": return True
    if h == "webm" and u == ".webm": return True
    if h == "json" and u == ".json": return True
    if h == "csv" and u == ".csv": return True
    if h == "tsv" and u == ".tsv": return True
    if h == "txt" and u == ".txt": return True
    return False


KATEGORI_SIRASI: list[str] = [
    "arsiv",
    "cad",
    "ebook",
    "evrak",
    "goruntu",
    "ses",
    "sunum",
    "vektor",
    "video",
    "yazi_tipi",
]


def frontend_kurallari() -> dict:
    """Tarayıcıya verilecek tek JSON nesnesi."""
    hedefler: dict[str, list[dict[str, str]]] = {}
    for kovan, lst in CIKTI_SECENEKLERI.items():
        hedefler[kovan] = [{"value": v, "label": lbl} for v, lbl in lst]
    return {
        "kategoriEtiketleri": KATEGORI_ETIKET,
        "kategoriSirasi": KATEGORI_SIRASI,
        "uzantiKovan": UZANTI_KOVAN,
        "hedefler": hedefler,
    }


# Sunucuda: hangi uzantılar sunumda metin çıkarma için destekleniyor
SUNUM_METIN_UZANTILAR = frozenset({".pptx"})
