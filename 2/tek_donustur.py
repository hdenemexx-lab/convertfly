# -*- coding: utf-8 -*-
"""Tek bir yükleme + çıktı kodu için dönüşüm; (indirme_adı, bayt, mime) döner."""

from __future__ import annotations

from pathlib import PurePath

from werkzeug.utils import secure_filename

import converters as donusturucu
import media_ceviri
from donustur_kurallari import SUNUM_METIN_UZANTILAR, izinli_hedef, kovan_bul

_GORUNTU_UZANTI = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".ico", ".avif", ".heic"}
)
_RESIM_HEDEF = frozenset({"png", "jpeg", "webp", "bmp", "tiff", "gif", "ico"})
_SES_HEDEF = frozenset({"mp3", "wav", "ogg", "flac", "m4a", "aac"})
_VIDEO_HEDEF = frozenset({"mp4", "webm", "avi", "mkv", "mov", "flv"})

_RESIM_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "gif": "image/gif",
    "ico": "image/x-icon",
}

_SES_MIME = {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg", "flac": "audio/flac", "m4a": "audio/mp4", "aac": "audio/aac"}
_VIDEO_MIME = {"mp4": "video/mp4", "webm": "video/webm", "avi": "video/x-msvideo", "mkv": "video/x-matroska", "mov": "video/quicktime", "flv": "video/x-flv"}


class DonusturHatasi(Exception):
    """Kullanıcıya gösterilecek Türkçe mesaj."""

    def __init__(self, mesaj: str) -> None:
        super().__init__(mesaj)
        self.mesaj = mesaj


def _uzanti(dosya_adi: str) -> str:
    return PurePath(dosya_adi or "").suffix.lower()


def donustur_tek_dosya(yuklenen, cikti: str) -> tuple[str, bytes, str]:
    """
    FileStorage benzeri nesne (.filename, .read()).
    Dönüş: (indirme_dosyasi, veri, mime_tipi).
    """
    cikti = (cikti or "").strip().lower()
    fname = yuklenen.filename or ""
    uz = _uzanti(fname)
    kov = kovan_bul(uz)

    if not kov:
        raise DonusturHatasi(f"Tanınmayan dosya türü: {fname}")
    if not izinli_hedef(kov, cikti):
        raise DonusturHatasi(f"Bu dosya için “{cikti}” çıktısı kullanılamaz: {fname}")

    if "(hazır değil)" in donustur_hedef_ozeti(kov, cikti):
        raise DonusturHatasi(f"“{cikti}” formatı kodlaması henüz hazır değil!")

    if kov == "sunum" and uz not in SUNUM_METIN_UZANTILAR:
        raise DonusturHatasi("PPT henüz desteklenmiyor; PPTX kullanın.")

    guvenli = secure_filename(fname) or "dosya"

    if cikti in _RESIM_HEDEF:
        if uz not in _GORUNTU_UZANTI:
            raise DonusturHatasi(f"Desteklenmeyen görüntü: {fname}")
        try:
            cikis, yeni_uz = donusturucu.resim_bytes_donustur(yuklenen.read(), cikti.upper())
        except ValueError as e:
            raise DonusturHatasi(str(e)) from e
        except Exception as e:  # noqa: BLE001
            raise DonusturHatasi(f"Resim dönüştürülemedi: {fname}") from e
        ad = donusturucu.resim_cikis_dosya_adi(guvenli, yeni_uz)
        mime = _RESIM_MIME.get(yeni_uz, "application/octet-stream")
        return ad, cikis, mime

    if cikti in _SES_HEDEF:
        try:
            bayt, ext = media_ceviri.ses_donustur(yuklenen.read(), uz, cikti)
        except RuntimeError as err:
            msg = str(err).lower()
            if "ffmpeg" in msg or "bulunamadi" in msg:
                raise DonusturHatasi("Ses dönüşümü için ffmpeg gerekli (PATH).") from err
            raise DonusturHatasi(f"Ses hatası: {fname}") from err
        except Exception as err:  # noqa: BLE001
            raise DonusturHatasi(f"Ses dönüştürülemedi: {fname}") from err
        kok = PurePath(guvenli).stem
        return f"{kok}.{ext}", bayt, _SES_MIME.get(cikti, "application/octet-stream")

    if cikti in _VIDEO_HEDEF:
        try:
            bayt, ext = media_ceviri.video_donustur(yuklenen.read(), uz, cikti)
        except RuntimeError as err:
            msg = str(err).lower()
            if "ffmpeg" in msg or "bulunamadi" in msg:
                raise DonusturHatasi("Video dönüşümü için ffmpeg gerekli (PATH).") from err
            raise DonusturHatasi(f"Video hatası ({fname}): dönüşüm başarısız.") from err
        except Exception as err:  # noqa: BLE001
            raise DonusturHatasi(f"Video dönüştürülemedi: {fname}") from err
        kok = PurePath(guvenli).stem
        return f"{kok}.{ext}", bayt, _VIDEO_MIME.get(cikti, "application/octet-stream")

    if cikti == "json":
        if uz == ".csv":
            try:
                veri = donusturucu.csv_bytes_to_json_bytes(yuklenen.read())
            except Exception as err:
                raise DonusturHatasi(f"CSV işlenemedi: {fname}") from err
            return donusturucu.json_cikis_dosya_adi(guvenli), veri, "application/json; charset=utf-8"
        elif uz == ".json":
            try:
                veri = donusturucu.json_bytes_prettify(yuklenen.read())
            except Exception as err:
                raise DonusturHatasi(f"JSON işlenemedi: {fname}") from err
            return donusturucu.json_cikis_dosya_adi(guvenli), veri, "application/json; charset=utf-8"
        raise DonusturHatasi(f"JSON çıktısı bu uzantı için desteklenmiyor: {uz}")

    if cikti == "tsv":
        if uz != ".csv":
            raise DonusturHatasi(f"TSV çıktısı yalnızca CSV için: {fname}")
        try:
            veri = donusturucu.csv_bytes_to_tsv_bytes(yuklenen.read())
        except Exception as err:
            raise DonusturHatasi(f"CSV işlenemedi: {fname}") from err
        return donusturucu.tsv_cikis_dosya_adi(guvenli), veri, "text/tab-separated-values; charset=utf-8"

    if cikti == "csv":
        if uz == ".json":
            try:
                veri = donusturucu.json_bytes_to_csv_bytes(yuklenen.read())
            except Exception as err:
                raise DonusturHatasi(f"JSON→CSV için aynı anahtarlı nesne dizisi gerekir: {fname}") from err
            return donusturucu.csv_cikis_json_to_csv_ad(guvenli), veri, "text/csv; charset=utf-8"
        raise DonusturHatasi(f"CSV çıktısı bu uzantı için desteklenmiyor: {uz}")

    if cikti == "txt":
        if uz == ".pdf":
            try:
                veri = donusturucu.pdf_bytes_to_txt(yuklenen.read())
            except Exception as err:
                raise DonusturHatasi(f"PDF okunamadı: {fname}") from err
            return donusturucu.txt_cikis_dosya_adi(guvenli), veri, "text/plain; charset=utf-8"
        elif uz == ".docx":
            try:
                veri = donusturucu.docx_bytes_to_txt(yuklenen.read())
            except Exception as err:
                raise DonusturHatasi(f"DOCX okunamadı: {fname}") from err
            return donusturucu.txt_cikis_dosya_adi(guvenli), veri, "text/plain; charset=utf-8"
        elif uz == ".pptx":
            try:
                veri = donusturucu.pptx_bytes_to_txt(yuklenen.read())
            except Exception as err:
                raise DonusturHatasi(f"Sunum işlenemedi: {fname}") from err
            return donusturucu.txt_cikis_dosya_adi(guvenli), veri, "text/plain; charset=utf-8"
        elif uz in frozenset({".txt", ".md", ".log"}):
            try:
                veri = donusturucu.metin_bytes_normalize(yuklenen.read())
            except Exception as err:
                raise DonusturHatasi(f"Metin işlemi başarısız: {fname}") from err
            return guvenli or "metin.txt", veri, "text/plain; charset=utf-8"
        raise DonusturHatasi(f"TXT çıktısı bu uzantı için desteklenmiyor: {uz}")

    if cikti == "txt_ocr":
        if uz != ".pdf":
            raise DonusturHatasi(f"OCR yalnızca .pdf için: {fname}")
        try:
            veri = donusturucu.pdf_bytes_to_ocr_txt(yuklenen.read())
        except Exception as err:
            raise DonusturHatasi(f"PDF OCR başarısız: {err}") from err
        return donusturucu.txt_cikis_dosya_adi(guvenli), veri, "text/plain; charset=utf-8"

    raise DonusturHatasi("Geçersiz çıktı kodu.")


def donustur_hedef_ozeti(kovan: str, hedef_kod: str) -> str:
    from donustur_kurallari import CIKTI_SECENEKLERI
    for v, lbl in CIKTI_SECENEKLERI.get(kovan, []):
        if v == hedef_kod:
            return lbl
    return ""
