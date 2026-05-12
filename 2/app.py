# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false
# pyright: reportArgumentType=false
# pyright: reportAssignmentType=false
"""
Ana Flask uygulaması.
"""

from __future__ import annotations

import io
import os
from pathlib import PurePath
import zipfile
from datetime import timedelta
from pypdf import PdfWriter, PdfReader
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from donustur_kurallari import frontend_kurallari
from tek_donustur import DonusturHatasi, donustur_tek_dosya
from models import db, Kullanici, Donusum, HataLogu, DosyaPaylasim
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from flask import abort

app = Flask(__name__)
app.config["SECRET_KEY"] = "geliştirme-için-değiştirin"
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

# MySQL bağlantı yapılandırması
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'MYSQL_URL', 
    'mysql+pymysql://root:sooioSqVWrMJjwFTFSqdLFSmvuauinRn@mysql.railway.internal/railway'
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# VirusTotal API Anahtarı
app.config["VIRUSTOTAL_API_KEY"] = os.environ.get("VIRUSTOTAL_API_KEY", "")

# E-posta Ayarları
app.config["SMTP_SERVER"] = "smtp.gmail.com"
app.config["SMTP_PORT"] = 587
app.config["SMTP_USER"] = "sizin_eposta@gmail.com"
app.config["SMTP_PASS"] = "uygulama_sifreniz"

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'giris'
login_manager.login_message = 'Lütfen giriş yapın.'
login_manager.login_message_category = 'hata'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return Kullanici.query.get(int(user_id))

from flask import session

# Admin PIN (ortam değişkeninden alınır; default güvenli bir değere ayarla)
ADMIN_PIN = os.environ.get("ADMIN_PIN", "admin1234")

def admin_required(f):
    """Hem is_admin hem de session PIN kontrolü yapar."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            flash("Bu sayfaya erişim yetkiniz yok.", "hata")
            return redirect(url_for('ana_sayfa'))
        if not session.get('admin_pin_dogrulandi'):
            return redirect(url_for('admin_giris'))
        if getattr(current_user, 'bantli', False):
            flash("Hesabınız askıya alınmıştır.", "hata")
            return redirect(url_for('ana_sayfa'))
        return f(*args, **kwargs)
    return decorated_function

# ── Admin Giriş (PIN) ────────────────────────────────────────────

@app.route("/admin/giris", methods=["GET", "POST"])
@login_required
def admin_giris():
    if not getattr(current_user, 'is_admin', False):
        flash("Bu sayfaya erişim yetkiniz yok.", "hata")
        return redirect(url_for('ana_sayfa'))
    if session.get('admin_pin_dogrulandi'):
        return redirect(url_for('admin_dashboard'))
    if request.method == "POST":
        girilen_pin = request.form.get("pin", "").strip()
        if girilen_pin == ADMIN_PIN:
            session['admin_pin_dogrulandi'] = True
            session.permanent = True
            app.logger.info(f"[ADMIN] {current_user.kullanici_adi} admin paneline giriş yaptı.")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Hatalı PIN kodu. Tekrar deneyin.", "hata")
            app.logger.warning(f"[ADMIN] {current_user.kullanici_adi} yanlış PIN girdi.")
    return render_template("admin/giris.html")

@app.route("/admin/cikis", methods=["POST"])
@login_required
def admin_cikis():
    session.pop('admin_pin_dogrulandi', None)
    return redirect(url_for('ana_sayfa'))

# ── Admin Dashboard ───────────────────────────────────────────────

@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    from datetime import datetime as _dt, timedelta as _td
    bugun = _dt.utcnow().date()

    toplam_user    = Kullanici.query.filter(Kullanici.sifre_hash != None).count()
    aktif_user     = Kullanici.query.filter(Kullanici.sifre_hash != None, Kullanici.bantli == False).count()
    bantli_user    = Kullanici.query.filter(Kullanici.bantli == True).count()
    toplam_dosya   = DosyaPaylasim.query.filter_by(silindi=False).count()
    bugun_dosya    = DosyaPaylasim.query.filter(
        db.func.date(DosyaPaylasim.tarih) == bugun
    ).count()
    premium_pro    = Kullanici.query.filter(Kullanici.plan.in_(['premium', 'pro'])).count()
    karantina      = DosyaPaylasim.query.filter_by(vt_tarama_sonucu='tehlikeli', silindi=False).count()
    toplam_donusum = Donusum.query.count()

    # Toplam veri boyutu
    toplam_boyut_bayt = db.session.query(db.func.sum(Donusum.dosya_boyutu)).scalar() or 0
    toplam_gb = round(toplam_boyut_bayt / (1024**3), 3)

    # Son 7 günlük yükleme trafiği (gerçek DB verisi)
    gun_labels, gun_counts = [], []
    for i in range(6, -1, -1):
        gun = bugun - _td(days=i)
        sayi = DosyaPaylasim.query.filter(db.func.date(DosyaPaylasim.tarih) == gun).count()
        gun_labels.append(gun.strftime('%d %b'))
        gun_counts.append(sayi)

    # Plan dağılımı
    normal_sayi  = Kullanici.query.filter(Kullanici.plan == 'normal',  Kullanici.sifre_hash != None).count()
    premium_sayi = Kullanici.query.filter(Kullanici.plan == 'premium', Kullanici.sifre_hash != None).count()
    pro_sayi     = Kullanici.query.filter(Kullanici.plan == 'pro',     Kullanici.sifre_hash != None).count()

    # Son dönüşümler
    son_donusumler = Donusum.query.order_by(Donusum.tarih.desc()).limit(8).all()

    return render_template(
        "admin/dashboard.html",
        toplam_user=toplam_user,
        aktif_user=aktif_user,
        bantli_user=bantli_user,
        toplam_dosya=toplam_dosya,
        bugun_dosya=bugun_dosya,
        premium_pro=premium_pro,
        karantina=karantina,
        toplam_donusum=toplam_donusum,
        toplam_gb=toplam_gb,
        gun_labels=gun_labels,
        gun_counts=gun_counts,
        normal_sayi=normal_sayi,
        premium_sayi=premium_sayi,
        pro_sayi=pro_sayi,
        son_donusumler=son_donusumler,
    )

# ── Admin Kullanıcı Yönetimi ──────────────────────────────────────

@app.route("/admin/kullanicilar")
@login_required
@admin_required
def admin_kullanicilar():
    arama = request.args.get("q", "").strip()
    plan_filtre = request.args.get("plan", "")
    sorgu = Kullanici.query.filter(Kullanici.sifre_hash != None)
    if arama:
        sorgu = sorgu.filter(
            db.or_(Kullanici.kullanici_adi.contains(arama), Kullanici.eposta.contains(arama))
        )
    if plan_filtre in ('normal', 'premium', 'pro'):
        sorgu = sorgu.filter(Kullanici.plan == plan_filtre)
    kullanicilar = sorgu.order_by(Kullanici.olusturulma_tarihi.desc()).all()
    return render_template("admin/kullanicilar.html", kullanicilar=kullanicilar, arama=arama, plan_filtre=plan_filtre)

@app.route("/admin/kullanici/<int:uid>/ban", methods=["POST"])
@login_required
@admin_required
def admin_kullanici_ban(uid):
    u = Kullanici.query.get_or_404(uid)
    if u.is_admin:
        flash("Bir admin kullanıcısı banlanamaz.", "hata")
        return redirect(url_for('admin_kullanicilar'))
    u.bantli = not u.bantli
    db.session.commit()
    durum = "askıya alındı" if u.bantli else "aktifleştirildi"
    flash(f"'{u.kullanici_adi}' kullanıcısı {durum}.", "basari")
    app.logger.info(f"[ADMIN] {current_user.kullanici_adi} → Kullanıcı {u.kullanici_adi} {durum}.")
    return redirect(url_for('admin_kullanicilar'))

@app.route("/admin/kullanici/<int:uid>/plan", methods=["POST"])
@login_required
@admin_required
def admin_kullanici_plan(uid):
    u = Kullanici.query.get_or_404(uid)
    yeni_plan = request.form.get("plan", "")
    if yeni_plan not in ('normal', 'premium', 'pro'):
        flash("Geçersiz plan.", "hata")
        return redirect(url_for('admin_kullanicilar'))
    eski_plan = u.plan
    u.plan = yeni_plan
    db.session.commit()
    flash(f"'{u.kullanici_adi}' planı {eski_plan} → {yeni_plan} olarak güncellendi.", "basari")
    app.logger.info(f"[ADMIN] {current_user.kullanici_adi} → {u.kullanici_adi} planı {eski_plan}→{yeni_plan}.")
    return redirect(url_for('admin_kullanicilar'))

# ── Admin Dosya Denetimi ──────────────────────────────────────────

@app.route("/admin/dosyalar")
@login_required
@admin_required
def admin_dosyalar():
    vt_filtre = request.args.get("vt", "")
    sorgu = DosyaPaylasim.query
    if vt_filtre == "tehlikeli":
        sorgu = sorgu.filter_by(vt_tarama_sonucu='tehlikeli')
    elif vt_filtre == "temiz":
        sorgu = sorgu.filter_by(vt_tarama_sonucu='temiz')
    elif vt_filtre == "silinmis":
        sorgu = sorgu.filter_by(silindi=True)
    else:
        sorgu = sorgu.filter_by(silindi=False)
    dosyalar = sorgu.order_by(DosyaPaylasim.tarih.desc()).all()
    return render_template("admin/dosyalar.html", dosyalar=dosyalar, vt_filtre=vt_filtre)

@app.route("/admin/dosya/<int:did>/sil", methods=["POST"])
@login_required
@admin_required
def admin_dosya_sil(did):
    d = DosyaPaylasim.query.get_or_404(did)
    zip_path = os.path.join(UPLOAD_DIR, f"{d.link_id}.zip")
    if os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except OSError as e:
            app.logger.warning(f"[ADMIN] Dosya silinemedi: {zip_path} — {e}")
    d.silindi = True
    d.aktif = False
    db.session.commit()
    flash(f"'{d.dosya_adi}' başarıyla silindi.", "basari")
    app.logger.info(f"[ADMIN] {current_user.kullanici_adi} → Dosya #{did} silindi.")
    return redirect(url_for('admin_dosyalar'))

@app.route("/admin/dosya/<int:did>/karantina-istisna", methods=["POST"])
@login_required
@admin_required
def admin_dosya_istisna(did):
    d = DosyaPaylasim.query.get_or_404(did)
    d.vt_tarama_sonucu = 'istisna'
    db.session.commit()
    flash(f"'{d.dosya_adi}' istisna olarak işaretlendi.", "basari")
    return redirect(url_for('admin_dosyalar', vt='tehlikeli'))




with app.app_context():
    db.create_all()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.uploads')
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Bellekte tutulan paylaşım verileri {link_id: bytes}
_paylasim_bellegi: dict[str, bytes] = {}

# Saklama süresi → minimum gerekli plan eşleme
SAKLAMA_PLAN_ESLESME = {
    1: 'normal',
    3: 'normal',
    7: 'premium',
    30: 'premium',
    60: 'pro',
    None: 'pro',   # sonsuz
}


@app.context_processor
def _kurallar_context():
    return {"kurallar_dict": frontend_kurallari()}


def arsivde_benzersiz_ad(istenen_ad: str, kullanilan: set[str]) -> str:
    if istenen_ad not in kullanilan:
        kullanilan.add(istenen_ad)
        return istenen_ad
    yol = PurePath(istenen_ad)
    kok, uz = yol.stem, yol.suffix
    n = 2
    while True:
        aday = f"{kok}_{n}{uz}"
        if aday not in kullanilan:
            kullanilan.add(aday)
            return aday
        n += 1


def zip_dosyasi_olustur(girdiler: list[tuple[str, bytes]]) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as arsiv:
        for ad, veri in girdiler:
            arsiv.writestr(ad, veri)
    return tampon.getvalue()

import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email_async(to_email, link, mesaj, dosya_adi):
    def send():
        SMTP_SERVER = app.config.get("SMTP_SERVER")
        SMTP_PORT = app.config.get("SMTP_PORT")
        SMTP_USER = app.config.get("SMTP_USER")
        SMTP_PASS = app.config.get("SMTP_PASS")
        
        if SMTP_USER == "sizin_eposta@gmail.com":
            app.logger.warning(f"[E-POSTA SİMÜLASYONU] Alıcı: {to_email}, Link: {link}")
            return
            
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = f"Size bir dosya paylaşıldı: {dosya_adi}"
        
        body = f"Merhaba,\n\nSize '{dosya_adi}' adlı dosya(lar) paylaşıldı.\n\nİndirme bağlantısı: {link}\n\n"
        if mesaj:
            body += f"Gönderenin mesajı: {mesaj}\n\n"
        body += "Dosya Paylaşım Sistemi."
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        try:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            server.quit()
            app.logger.info(f"[BAŞARILI] E-posta gönderildi: {to_email}")
        except Exception as e:
            app.logger.error(f"[E-POSTA HATASI] {str(e)}")
            
    thread = threading.Thread(target=send)
    thread.daemon = True
    thread.start()


def vt_tara_async(paylasim_id: int, zip_bytes: bytes):
    """Pro kullanıcıların paylaşımını arka planda VirusTotal ile tarar."""
    def tara():
        import requests as _req
        import base64
        from datetime import datetime as _dt

        VT_API_KEY = app.config.get("VIRUSTOTAL_API_KEY", "")
        if not VT_API_KEY:
            app.logger.warning("[VT] API anahtarı tanımlı değil — tarama atlandı.")
            return

        with app.app_context():
            try:
                # Dosyayı VT'ye yükle
                upload_url = "https://www.virustotal.com/api/v3/files"
                headers = {"x-apikey": VT_API_KEY}
                files_payload = {"file": ("paylasim.zip", zip_bytes, "application/zip")}
                resp = _req.post(upload_url, headers=headers, files=files_payload, timeout=60)
                resp.raise_for_status()
                analysis_id = resp.json()["data"]["id"]
                app.logger.info(f"[VT] Tarama başlatıldı — analysis_id: {analysis_id}")

                # Sonucu bekle (max 90 saniye, 10'ar saniyede bir kontrol)
                import time as _time
                for _ in range(9):
                    _time.sleep(10)
                    analysis_url = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
                    a_resp = _req.get(analysis_url, headers=headers, timeout=30)
                    a_resp.raise_for_status()
                    a_data = a_resp.json()["data"]["attributes"]
                    if a_data["status"] == "completed":
                        stats = a_data.get("stats", {})
                        malicious = stats.get("malicious", 0)
                        suspicious = stats.get("suspicious", 0)
                        if malicious > 0 or suspicious > 0:
                            # Tehdit adını bul
                            results = a_data.get("results", {})
                            tehdit_adi = None
                            for engine, sonuc in results.items():
                                if sonuc.get("category") in ("malicious", "suspicious"):
                                    tehdit_adi = sonuc.get("result") or engine
                                    break
                            vt_sonuc = "tehlikeli"
                        else:
                            tehdit_adi = None
                            vt_sonuc = "temiz"

                        p = DosyaPaylasim.query.get(paylasim_id)
                        if p:
                            p.vt_tarama_sonucu = vt_sonuc
                            p.vt_tehdit_adi = tehdit_adi
                            p.vt_tarama_tarihi = _dt.utcnow()
                            db.session.commit()
                            app.logger.info(f"[VT] Paylaşım #{paylasim_id} — Sonuç: {vt_sonuc} | Tehdit: {tehdit_adi}")
                        return

                # Zaman aşımı
                p = DosyaPaylasim.query.get(paylasim_id)
                if p:
                    p.vt_tarama_sonucu = "hata"
                    p.vt_tarama_tarihi = _dt.utcnow()
                    db.session.commit()
                app.logger.warning(f"[VT] Paylaşım #{paylasim_id} — Tarama zaman aşımına uğradı.")

            except Exception as exc:
                app.logger.error(f"[VT HATA] Paylaşım #{paylasim_id}: {exc}")
                try:
                    p = DosyaPaylasim.query.get(paylasim_id)
                    if p:
                        p.vt_tarama_sonucu = "hata"
                        p.vt_tarama_tarihi = _dt.utcnow()
                        db.session.commit()
                except Exception:
                    pass

    thread = threading.Thread(target=tara)
    thread.daemon = True
    thread.start()


@app.route("/")
def ana_sayfa():
    app.logger.info(f"[SAYFA] Ana sayfa görüntülendi. IP: {request.remote_addr}")
    return render_template(
        "index.html",
        baslik="Dosyalarınızı Kolayca Dönüştürün",
        aciklama="Gelişmiş ve hızlı dosya dönüştürücümüz ile her formattaki dosyayı saniyeler içinde istediğiniz formata çevirin.",
    )


@app.route("/donustur", methods=["POST"])
def donustur():
    yuklenenler = [f for f in request.files.getlist("dosya") if f and f.filename]
    cikti_listesi = request.form.getlist("cikti")

    kullanici = getattr(current_user, "is_authenticated", False) and current_user or None
    
    if not yuklenenler:
        if request.form.get("is_ajax") == "1": return {"error": "En az bir dosya ekleyin."}, 400
        flash("En az bir dosya ekleyin.", "hata")
        return redirect(url_for("ana_sayfa"))
    if len(yuklenenler) != len(cikti_listesi):
        if request.form.get("is_ajax") == "1": return {"error": "Her dosya için dönüşüm seçimi gerekli."}, 400
        flash("Her dosya için bir dönüşüm seçimi gerekli.", "hata")
        return redirect(url_for("ana_sayfa"))

    sonuclar = []
    kullanilan: set[str] = set()

    is_ajax = request.form.get("is_ajax") == "1"

    if not kullanici:
        ip_adresi = request.remote_addr
        kullanici = Kullanici.query.filter_by(ip_adresi=ip_adresi, sifre_hash=None).first()  # type: ignore
        if not kullanici:
            kullanici = Kullanici(ip_adresi=ip_adresi)
            db.session.add(kullanici)  # type: ignore
            db.session.commit()  # type: ignore

    max_mb = 100 if current_user.is_authenticated else 10
    toplam_bayt = 0
    for y in yuklenenler:
        y.seek(0, io.SEEK_END)
        toplam_bayt += y.tell()
        y.seek(0)
        
    if toplam_bayt > max_mb * 1024 * 1024:
        msg = f"Toplam dosya boyutu limitin üzerinde! İzin verilen: {max_mb} MB"
        app.logger.warning(f"[LİMİT] {kullanici.id} ID'li kullanıcı limiti aştı. ({toplam_bayt} > {max_mb*1024*1024})")
        if is_ajax: return {"error": msg}, 413
        flash(msg, "hata")
        return redirect(url_for("ana_sayfa"))

    for idx, (yuklenen, ck) in enumerate(zip(yuklenenler, cikti_listesi)):
        ck = (ck or "").strip()
        
        if not ck:
            app.logger.warning(f"[UYARI] Boş dönüşüm formatı gönderildi: {yuklenen.filename}")
            if is_ajax: return {"error": f"Boş dönüşüm: {yuklenen.filename}"}, 400
            flash(f"Boş dönüşüm: {yuklenen.filename}", "hata")
            return redirect(url_for("ana_sayfa"))
            
        kaynak_uzanti = PurePath(yuklenen.filename).suffix.lstrip(".").lower() or "bilinmiyor"
        
        yuklenen.seek(0, io.SEEK_END)
        dosya_boyutu = yuklenen.tell()
        yuklenen.seek(0)
        
        yeni_donusum = Donusum(
            kullanici_id=kullanici.id,
            kaynak_format=kaynak_uzanti,
            hedef_format=ck,
            dosya_boyutu=dosya_boyutu,
        )
        db.session.add(yeni_donusum)

        app.logger.info(f"[İŞLEM] Kullanıcı ID {kullanici.id} | İstek: '{yuklenen.filename}' ({dosya_boyutu} bayt) -> Hedef Format: '{ck}'")

        try:
            ad, veri, mime = donustur_tek_dosya(yuklenen, ck)
            yeni_donusum.basari_durumu = True
            db.session.commit()  # type: ignore
            app.logger.info(f"[BAŞARILI] '{yuklenen.filename}' başarıyla '{ad}' olarak dönüştürüldü. (Çıktı boyutu: {len(veri)} bayt)")
        except DonusturHatasi as e:
            yeni_donusum.basari_durumu = False
            yeni_donusum.hata_mesaji = e.mesaj
            hata_log = HataLogu(donusum_id=yeni_donusum.id, hata_mesaji=e.mesaj)
            db.session.add(hata_log)  # type: ignore
            db.session.commit()  # type: ignore
            
            app.logger.error(f"[HATA] Dönüşüm başarısız: '{yuklenen.filename}' -> '{ck}'. Sebep: {e.mesaj}")
            if is_ajax: return {"error": e.mesaj}, 400
            flash(e.mesaj, "hata")
            return redirect(url_for("ana_sayfa"))
            
        ad2 = arsivde_benzersiz_ad(ad, kullanilan)
        sonuclar.append((ad2, veri, mime))

    if len(sonuclar) == 1:
        ad, veri, mime = sonuclar[0]
        resp = send_file(io.BytesIO(veri), as_attachment=True, download_name=ad, mimetype=mime)
        resp.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        return resp

    zip_ic = [(a[0], a[1]) for a in sonuclar]
    zip_veri = zip_dosyasi_olustur(zip_ic)
    resp2 = send_file(io.BytesIO(zip_veri), as_attachment=True, download_name="cikti.zip", mimetype="application/zip")
    resp2.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
    return resp2


@app.route("/iletisim", methods=["GET", "POST"])
def iletisim():
    if request.method == "POST":
        ad = (request.form.get("ad") or "").strip()
        eposta = (request.form.get("eposta") or "").strip()
        mesaj = (request.form.get("mesaj") or "").strip()
        if not ad or not eposta or not mesaj:
            flash("Lütfen tüm alanları doldurun.", "hata")
            return redirect(url_for("iletisim"))
        flash(f"Teşekkürler {ad}! Mesajınız alındı (demo: kayıt yapılmadı).", "basari")
        return redirect(url_for("iletisim"))
    return render_template("iletisim.html", baslik="İletişim")


@app.route("/kayit", methods=["GET", "POST"])
def kayit():
    if current_user.is_authenticated:
        return redirect(url_for('ana_sayfa'))
    if request.method == "POST":
        kullanici_adi = request.form.get("kullanici_adi", "").strip()
        eposta = request.form.get("eposta", "").strip()
        sifre = request.form.get("sifre", "")
        
        if not kullanici_adi or not eposta or not sifre:
            flash("Lütfen tüm alanları doldurun.", "hata")
            return redirect(url_for("kayit"))
            
        mevcut_kullanici = Kullanici.query.filter_by(kullanici_adi=kullanici_adi).first()
        mevcut_eposta = Kullanici.query.filter_by(eposta=eposta).first()
        
        if mevcut_kullanici and mevcut_kullanici.sifre_hash:
            flash("Bu kullanıcı adı zaten alınmış.", "hata")
            return redirect(url_for("kayit"))
        if mevcut_eposta and mevcut_eposta.sifre_hash:
            flash("Bu e-posta adresi zaten kullanımda.", "hata")
            return redirect(url_for("kayit"))
            
        sifre_hash = generate_password_hash(sifre)
        yeni_kullanici = Kullanici(
            kullanici_adi=kullanici_adi, 
            eposta=eposta, 
            sifre_hash=sifre_hash, 
            ip_adresi=request.remote_addr
        )
        db.session.add(yeni_kullanici)
        db.session.commit()
        flash("Kayıt başarılı! Şimdi giriş yapabilirsiniz.", "basari")
        return redirect(url_for("giris"))
        
    return render_template("kayit.html", baslik="Kayıt Ol")


@app.route("/giris", methods=["GET", "POST"])
def giris():
    if current_user.is_authenticated:
        return redirect(url_for('ana_sayfa'))
    if request.method == "POST":
        kullanici_adi = request.form.get("kullanici_adi", "").strip()
        sifre = request.form.get("sifre", "")
        user = Kullanici.query.filter_by(kullanici_adi=kullanici_adi).first()
        if user and user.sifre_hash and check_password_hash(user.sifre_hash, sifre):
            if getattr(user, 'bantli', False):
                flash("Hesabınız askıya alınmıştır. Destek için iletişime geçin.", "hata")
                return redirect(url_for("giris"))
            from datetime import datetime as _dt
            user.son_giris = _dt.utcnow()
            db.session.commit()
            login_user(user)
            flash("Başarıyla giriş yaptınız.", "basari")
            return redirect(url_for("ana_sayfa"))
        else:
            flash("Geçersiz kullanıcı adı veya şifre.", "hata")
    return render_template("giris.html", baslik="Giriş Yap")


@app.route("/cikis")
@login_required
def cikis():
    logout_user()
    flash("Başarıyla çıkış yaptınız.", "basari")
    return redirect(url_for("ana_sayfa"))


@app.route("/profil")
@login_required
def profil():
    donusumler = Donusum.query.filter_by(kullanici_id=current_user.id).order_by(Donusum.tarih.desc()).limit(20).all()
    
    toplam_islem = Donusum.query.filter_by(kullanici_id=current_user.id).count()
    basarili_islem = Donusum.query.filter_by(kullanici_id=current_user.id, basari_durumu=True).count()
    
    # SQLAlchemy SUM(dosya_boyutu) kullanımı
    toplam_boyut_db = db.session.query(db.func.sum(Donusum.dosya_boyutu)).filter_by(kullanici_id=current_user.id, basari_durumu=True).scalar()
    toplam_boyut_mb = round((toplam_boyut_db or 0) / (1024 * 1024), 2)

    # Format dagilim istatistigi — hedef_format None olanları atla
    format_sayilari = {}
    for d in Donusum.query.filter(
        Donusum.kullanici_id == current_user.id,
        Donusum.basari_durumu == True,
        Donusum.hedef_format != None
    ).all():
        fmt = (d.hedef_format or '').upper()
        if fmt:
            format_sayilari[fmt] = format_sayilari.get(fmt, 0) + 1
    format_labels = list(format_sayilari.keys())
    format_values = list(format_sayilari.values())

    # Paylasimlar — silindi sutunu olmayan eski satırları da kapsayacak şekilde
    try:
        paylasimlar = DosyaPaylasim.query.filter_by(
            kullanici_id=current_user.id, silindi=False
        ).order_by(DosyaPaylasim.tarih.desc()).all()
        silinmis_paylasimlar = DosyaPaylasim.query.filter_by(
            kullanici_id=current_user.id, silindi=True
        ).order_by(DosyaPaylasim.tarih.desc()).all()
    except Exception:
        paylasimlar = DosyaPaylasim.query.filter_by(
            kullanici_id=current_user.id
        ).order_by(DosyaPaylasim.tarih.desc()).all()
        silinmis_paylasimlar = []

    return render_template(
        "profil.html",
        baslik="Profilim",
        donusumler=donusumler,
        toplam_islem=toplam_islem,
        basarili_islem=basarili_islem,
        toplam_boyut_mb=toplam_boyut_mb,
        format_labels=format_labels,
        format_values=format_values,
        paylasimlar=paylasimlar,
        silinmis_paylasimlar=silinmis_paylasimlar,
        kullanici_plan=current_user.plan,
    )


@app.route("/planlar")
def planlar():
    kullanici_plan = None
    if current_user.is_authenticated:
        kullanici_plan = current_user.plan
    return render_template("planlar.html", baslik="Planlar",
                           kullanici_plan=kullanici_plan)



@app.route("/dosya-paylas", methods=["GET", "POST"])
def dosya_paylas():
    if request.method == "POST":
        yuklenenler = [f for f in request.files.getlist("dosyalar") if f and f.filename]
        gonderim_tipi = request.form.get("gonderim_tipi", "link")
        alici_email = request.form.get("alici_email", "").strip()
        baslik = request.form.get("baslik", "").strip()[:120]
        mesaj = request.form.get("mesaj", "").strip()
        indirme_sifresi = request.form.get("indirme_sifresi", "")
        saklama_gun_str = request.form.get("saklama_gun", "7")
        saklama_gun = int(saklama_gun_str) if saklama_gun_str and saklama_gun_str != "0" else None

        if not yuklenenler:
            if request.form.get("is_ajax") == "1":
                return {"error": "Lütfen paylaşmak için en az 1 adet dosya seçin."}, 400
            flash("Lütfen paylaşmak için en az 1 adet dosya seçin.", "hata")
            return redirect(url_for("dosya_paylas"))

        # Plan kontrolü
        if current_user.is_authenticated:
            # Kayıtlı kullanıcılar
            kullanici_plan = current_user.plan
            gereken_plan = SAKLAMA_PLAN_ESLESME.get(saklama_gun, 'pro')
            plan_sirasi = {'normal': 0, 'premium': 1, 'pro': 2}
            if plan_sirasi.get(kullanici_plan, 0) < plan_sirasi.get(gereken_plan, 0):
                if request.form.get("is_ajax") == "1":
                    return {"error": f"Bu saklama süresi için {gereken_plan.capitalize()} plan gerekli."}, 403
                flash(f"Bu saklama süresi için {gereken_plan.capitalize()} plan gerekli.", "hata")
                return redirect(url_for("dosya_paylas"))
        else:
            # Guest (Kayıtlı olmayan) kullanıcılar sadece 1 veya 3 günlük seçebilir
            if saklama_gun not in [1, 3]:
                if request.form.get("is_ajax") == "1":
                    return {"error": "Kayıtlı olmayan kullanıcılar en fazla 3 günlük paylaşım yapabilir."}, 403
                flash("Kayıtlı olmayan kullanıcılar en fazla 3 günlük paylaşım yapabilir. Uzun süreler için giriş yapın.", "hata")
                return redirect(url_for("dosya_paylas"))

        import uuid
        link_id = str(uuid.uuid4()).replace('-', '')[:12]
        tam_link = url_for('paylasim_goster', link_id=link_id, _external=True)
        dosya_adi = ', '.join([f.filename for f in yuklenenler])

        # expire_at hesapla
        expire_at = None
        if saklama_gun is not None:
            expire_at = db.func.now()  # placeholder — datetime ile hesaplıyoruz
            from datetime import datetime as _dt
            expire_at = _dt.utcnow() + timedelta(days=saklama_gun)

        # Dosyaları zip yapıp önce bellekte tut, sonra diske kaydet
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zipf:
            for f in yuklenenler:
                f.seek(0)
                zipf.writestr(f.filename, f.read())
        zip_bytes = zip_buf.getvalue()

        _paylasim_bellegi[link_id] = zip_bytes

        zip_path = os.path.join(UPLOAD_DIR, f"{link_id}.zip")
        try:
            with open(zip_path, "wb") as fp:
                fp.write(zip_bytes)
        except Exception as disk_err:
            app.logger.warning(f"[DİSK] ZIP diske yazılamadı: {disk_err}")

        # DB kaydı
        if current_user.is_authenticated:
            kullanici_id = current_user.id
        else:
            kullanici = Kullanici.query.filter_by(ip_adresi=request.remote_addr, sifre_hash=None).first()
            if not kullanici:
                kullanici = Kullanici(ip_adresi=request.remote_addr)
                db.session.add(kullanici)
                db.session.commit()
            kullanici_id = kullanici.id

        yeni_paylasim = DosyaPaylasim(
            kullanici_id=kullanici_id,
            link_id=link_id,
            baslik=baslik if baslik else None,
            dosya_adi=dosya_adi,
            mesaj=mesaj,
            indirme_sifresi=indirme_sifresi if indirme_sifresi else None,
            gonderim_tipi=gonderim_tipi,
            alici_email=alici_email if gonderim_tipi == 'email' else None,
            saklama_gun=saklama_gun,
            expire_at=expire_at,
            aktif=True
        )
        db.session.add(yeni_paylasim)
        db.session.commit()

        # Pro kullanıcılar için VirusTotal taraması (arka planda)
        if current_user.is_authenticated and current_user.plan == 'pro':
            vt_tara_async(yeni_paylasim.id, zip_bytes)

        if gonderim_tipi == "email" and alici_email:
            send_email_async(alici_email, tam_link, mesaj, dosya_adi)

        sifre_bilgisi = " (🔒 Şifre Korumalı)" if indirme_sifresi else ""

        if request.form.get("is_ajax") == "1":
            return {
                "success": True,
                "tam_link": tam_link,
                "sifre_bilgisi": sifre_bilgisi,
                "gonderim_tipi": gonderim_tipi,
                "alici_email": alici_email,
                "dosya_adi": dosya_adi
            }

        if gonderim_tipi == "email" and alici_email:
            flash(f"'{dosya_adi}' dosyası '{alici_email}' adresine başarıyla iletildi.{sifre_bilgisi}", "basari")
        else:
            flash(f"Paylaşım linkiniz: {tam_link}{sifre_bilgisi}", "basari")
        return redirect(url_for("dosya_paylas"))

    # Kullanıcı planına göre izin verilen saklama seçeneklerini belirle
    if current_user.is_authenticated:
        kullanici_plan = current_user.plan
    else:
        kullanici_plan = 'normal'
        
    return render_template("dosya_paylas.html", baslik="Dosya Paylaş", 
                           kullanici_plan=kullanici_plan)

@app.route("/paylasim/<link_id>", methods=["GET", "POST"])
def paylasim_goster(link_id):
    paylasim = DosyaPaylasim.query.filter_by(link_id=link_id, aktif=True, silindi=False).first_or_404()

    # Süre dolmuş mu?
    if paylasim.suresi_dolmus_mu:
        flash("Bu paylaşım linkinin süresi dolmuştur.", "hata")
        return redirect(url_for('ana_sayfa'))

    # Önce bellekte ara, yoksa diskten oku
    zip_bytes = _paylasim_bellegi.get(link_id)
    if zip_bytes is None:
        zip_path = os.path.join(UPLOAD_DIR, f"{link_id}.zip")
        if os.path.exists(zip_path):
            with open(zip_path, "rb") as fp:
                zip_bytes = fp.read()
            _paylasim_bellegi[link_id] = zip_bytes

    if zip_bytes is None:
        flash("Bu dosya sunucudan silinmiş veya bulunamıyor.", "hata")
        return redirect(url_for('ana_sayfa'))

    sifre_dogru = False
    if request.method == "POST":
        girilen_sifre = request.form.get("sifre", "")
        if paylasim.indirme_sifresi and paylasim.indirme_sifresi != girilen_sifre:
            flash("Hatalı şifre girdiniz.", "hata")
            return redirect(url_for('paylasim_goster', link_id=link_id))
        sifre_dogru = True
        app.logger.info(f"[PAYLAŞIM] '{link_id}' indirildi. Boyut: {len(zip_bytes)} bayt.")
        return send_file(io.BytesIO(zip_bytes), as_attachment=True,
                         download_name=f"Paylasilan_Dosyalar_{link_id}.zip",
                         mimetype="application/zip")

    # GET: şifre yoksa içerik göster, şifre varsa sadece başlık göster
    sifreli = bool(paylasim.indirme_sifresi)
    return render_template("paylasim_indir.html", baslik="Paylaşılan Dosya",
                           paylasim=paylasim, sifreli=sifreli, zip_boyut=len(zip_bytes))

@app.route("/paylasim-sil/<int:pid>", methods=["POST"])
@login_required
def paylasim_sil(pid):
    p = DosyaPaylasim.query.filter_by(id=pid, kullanici_id=current_user.id).first_or_404()
    p.silindi = True  # soft-delete
    p.aktif = False
    db.session.commit()
    flash("Paylaşım linki silindi (geçmişte görmeye devam edebilirsiniz).", "basari")
    return redirect(url_for("profil"))

@app.route("/paylasim-toggle/<int:pid>", methods=["POST"])
@login_required
def paylasim_toggle(pid):
    p = DosyaPaylasim.query.filter_by(id=pid, kullanici_id=current_user.id).first_or_404()
    p.aktif = not p.aktif
    db.session.commit()
    flash(f"Paylaşım {'aktifleştirildi' if p.aktif else 'durduruldu'}.", "basari")
    return redirect(url_for("profil"))

@app.route("/pdf-islemleri", methods=["GET", "POST"])
def pdf_islemleri():
    if request.method == "POST":
        yuklenenler = [f for f in request.files.getlist("dosyalar") if f and f.filename and f.filename.lower().endswith('.pdf')]
        islem_turu = request.form.get("islem_turu")
        parola = request.form.get("parola", "")
        
        if not yuklenenler or not islem_turu:
            flash("Lütfen eksik alan bırakmayın.", "hata")
            return redirect(url_for("pdf_islemleri"))
            
        sonuclar = []
        for pdf_file in yuklenenler:
            try:
                reader = PdfReader(pdf_file)
                writer = PdfWriter()
                
                if islem_turu == "sifre_kaldir":
                    if reader.is_encrypted:
                        reader.decrypt(parola)
                
                for page in reader.pages:
                    writer.add_page(page)
                
                if islem_turu == "sifrele":
                    writer.encrypt(parola)
                elif islem_turu == "sikistir":
                    for page in writer.pages:
                        page.compress_content_streams()
                
                buffer = io.BytesIO()
                writer.write(buffer)
                
                prefix = {"sikistir": "sikistirilmis_", "sifrele": "sifreli_", "sifre_kaldir": "sifresiz_"}.get(islem_turu, "islem_")
                sonuclar.append((f"{prefix}{PurePath(pdf_file.filename).name}", buffer.getvalue()))
                
            except Exception as e:
                flash(f"{pdf_file.filename} işlenemedi: {str(e)}", "hata")
                return redirect(url_for("pdf_islemleri"))
        
        if len(sonuclar) == 1:
            return send_file(io.BytesIO(sonuclar[0][1]), as_attachment=True, download_name=sonuclar[0][0], mimetype="application/pdf")
            
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for ad, veri in sonuclar:
                zf.writestr(ad, veri)
        return send_file(io.BytesIO(zip_buf.getvalue()), as_attachment=True, download_name="Islem_Gormus_PDFler.zip", mimetype="application/zip")
        
    return render_template("pdf_araclari.html", baslik="PDF İşlemleri")

@app.route("/pdf-birlestirme", methods=["GET", "POST"])
def pdf_birlestir():
    if request.method == "POST":
        yuklenen_pdf_listesi = [f for f in request.files.getlist("dosyalar") if f and f.filename and f.filename.lower().endswith('.pdf')]
        
        if not yuklenen_pdf_listesi or len(yuklenen_pdf_listesi) < 2:
            flash("Lütfen birleştirmek için en az 2 adet PDF dosyası seçin.", "hata")
            return redirect(url_for("pdf_birlestir"))
            
        try:
            birlestirici = PdfWriter()
            toplam_boyut = 0

            for pdf_dosya in yuklenen_pdf_listesi:
                pdf_dosya.seek(0, io.SEEK_END)
                toplam_boyut += pdf_dosya.tell()
                pdf_dosya.seek(0)
                birlestirici.append(pdf_dosya)
                
            tampon = io.BytesIO()
            birlestirici.write(tampon)
            birlestirici.close()
            
            app.logger.info(f"[İŞLEM] {len(yuklenen_pdf_listesi)} adet PDF başarıyla birleştirildi. Toplam boyut: {toplam_boyut} bayt.")
            
            # Veritabanına PDF Birleştirme logu kaydetme
            if current_user.is_authenticated:
                kullanici = current_user
            else:
                kullanici = Kullanici.query.filter_by(ip_adresi=request.remote_addr, sifre_hash=None).first()
                if not kullanici:
                    kullanici = Kullanici(ip_adresi=request.remote_addr)
                    db.session.add(kullanici)
                    db.session.commit()
            
            yeni_donusum = Donusum(
                kullanici_id=kullanici.id,
                kaynak_format="pdf",
                hedef_format="birlestirme",
                dosya_boyutu=toplam_boyut,
                basari_durumu=True
            )
            db.session.add(yeni_donusum)
            db.session.commit()
            
            return send_file(
                io.BytesIO(tampon.getvalue()),
                as_attachment=True,
                download_name="Birlestirilmis_Dosya.pdf",
                mimetype="application/pdf"
            )
        except Exception as e:
            flash(f"Birleştirme sırasında hata oluştu: {str(e)}", "hata")
            return redirect(url_for("pdf_birlestir"))
            
    return render_template("pdf_birlestir.html", baslik="PDF Birleştirme")

@app.route("/pdf-bolme", methods=["GET", "POST"])
def pdf_bol():
    if request.method == "POST":
        yuklenen_pdf_listesi = [f for f in request.files.getlist("dosyalar") if f and f.filename and f.filename.lower().endswith('.pdf')]
        
        if not yuklenen_pdf_listesi:
            flash("Lütfen bölmek için en az 1 adet PDF dosyası seçin.", "hata")
            return redirect(url_for("pdf_bol"))
            
        try:
            zip_buffer = io.BytesIO()
            toplam_boyut = 0
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_dosya:
                for idx, pdf_file in enumerate(yuklenen_pdf_listesi):
                    pdf_file.seek(0, io.SEEK_END)
                    toplam_boyut += pdf_file.tell()
                    pdf_file.seek(0)
                    
                    okuyucu = PdfReader(pdf_file)
                    orijinal_isim = PurePath(pdf_file.filename).stem
                    
                    for sayfa_no in range(len(okuyucu.pages)):
                        yazici = PdfWriter()
                        yazici.add_page(okuyucu.pages[sayfa_no])
                        
                        sayfa_buffer = io.BytesIO()
                        yazici.write(sayfa_buffer)
                        
                        dosya_adi = f"{idx+1}_{orijinal_isim}_Sayfa_{sayfa_no+1}.pdf"
                        zip_dosya.writestr(dosya_adi, sayfa_buffer.getvalue())
            
            zip_buffer.seek(0)
            
            app.logger.info(f"[İŞLEM] {len(yuklenen_pdf_listesi)} adet PDF dosyası başarıyla sayfalarına bölündü ve ZIP'lendi.")
            
            # Veritabanına PDF Bölme logu kaydetme
            if current_user.is_authenticated:
                kullanici = current_user
            else:
                kullanici = Kullanici.query.filter_by(ip_adresi=request.remote_addr, sifre_hash=None).first()
                if not kullanici:
                    kullanici = Kullanici(ip_adresi=request.remote_addr)
                    db.session.add(kullanici)
                    db.session.commit()
            
            yeni_donusum = Donusum(
                kullanici_id=kullanici.id,
                kaynak_format="pdf",
                hedef_format="bolme",
                dosya_boyutu=toplam_boyut,
                basari_durumu=True
            )
            db.session.add(yeni_donusum)
            db.session.commit()
            
            return send_file(
                zip_buffer,
                as_attachment=True,
                download_name="Bolunmus_PDFler.zip",
                mimetype="application/zip"
            )
            
        except Exception as e:
            flash(f"Bölme sırasında hata oluştu: {str(e)}", "hata")
            return redirect(url_for("pdf_bol"))
            
    return render_template("pdf_bol.html", baslik="PDF Bölme")


@app.errorhandler(413)
def cok_buyuk(_e):
    if request.path.startswith("/donustur") and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return {"error": "Sunucu limiti aşıldı! (Maksimum 100 MB)"}, 413
    flash("Yükleme çok büyük (Yükleme boyutu sunucu limitinin üzerinde. Maksimum: 100 MB).", "hata")
    return redirect(url_for("ana_sayfa"))

@app.errorhandler(404)
def sayfa_bulunamadi(e):
    return render_template('404.html', baslik="404 - Sayfa Bulunamadı"), 404


if __name__ == "__main__":
    import logging
    app.logger.setLevel(logging.INFO)
    app.logger.info("="*60)
    app.logger.info("[BAŞLATILDI] Dosya Dönüştürücü Uygulaması Aktif!")
    app.logger.info("[SİSTEM] Maksimum Yükleme Boyutu: 100 MB")
    app.logger.info("="*60)
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
