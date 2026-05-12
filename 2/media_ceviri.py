# -*- coding: utf-8 -*-
"""
Ses ve video dönüşümü — sistemde ffmpeg yüklü olmalı (PATH).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile


def ffmpeg_kurulu_mu() -> bool:
    return shutil.which("ffmpeg") is not None


def _calistir(girdi_yolu: str, cikis_yolu: str, ek_args: list[str]) -> None:
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", girdi_yolu]
    cmd.extend(ek_args)
    cmd.append(cikis_yolu)
    sonuc = subprocess.run(cmd, capture_output=True, timeout=300)
    if sonuc.returncode != 0:
        hata = (sonuc.stderr or sonuc.stdout or b"").decode("utf-8", errors="ignore")[:800]
        raise RuntimeError(hata or "ffmpeg_basarisiz")


def ses_donustur(girdi_bayt: bytes, kaynak_uzanti: str, hedef: str) -> tuple[bytes, str]:
    """
    hedef: mp3 | wav | ogg
    Dönüş: (bayt, çıktı uzantısı noktalı)
    """
    if not ffmpeg_kurulu_mu():
        raise RuntimeError("ffmpeg_bulunamadi")

    hedef = hedef.lower()
    if hedef not in {"mp3", "wav", "ogg"}:
        raise ValueError("gecersiz_ses_hedefi")

    uz = kaynak_uzanti if kaynak_uzanti.startswith(".") else f".{kaynak_uzanti}"
    cik_uz = f".{hedef}"

    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, f"kaynak{uz}")
        out = os.path.join(td, f"cikis{cik_uz}")
        with open(inp, "wb") as f:
            f.write(girdi_bayt)

        if hedef == "mp3":
            _calistir(inp, out, ["-vn", "-codec:a", "libmp3lame", "-q:a", "2"])
        elif hedef == "wav":
            _calistir(inp, out, ["-vn", "-acodec", "pcm_s16le"])
        else:
            _calistir(inp, out, ["-vn", "-c:a", "libvorbis", "-q:a", "4"])

        with open(out, "rb") as f:
            return f.read(), cik_uz.lstrip(".")


def video_donustur(girdi_bayt: bytes, kaynak_uzanti: str, hedef: str) -> tuple[bytes, str]:
    """hedef: mp4 | webm"""
    if not ffmpeg_kurulu_mu():
        raise RuntimeError("ffmpeg_bulunamadi")

    hedef = hedef.lower()
    if hedef not in {"mp4", "webm"}:
        raise ValueError("gecersiz_video_hedefi")

    uz = kaynak_uzanti if kaynak_uzanti.startswith(".") else f".{kaynak_uzanti}"
    cik_uz = f".{hedef}"

    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, f"kaynak{uz}")
        out = os.path.join(td, f"cikis{cik_uz}")
        with open(inp, "wb") as f:
            f.write(girdi_bayt)

        if hedef == "mp4":
            _calistir(
                inp,
                out,
                ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"],
            )
        else:
            _calistir(
                inp,
                out,
                ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus", "-b:a", "96k"],
            )

        with open(out, "rb") as f:
            return f.read(), cik_uz.lstrip(".")
