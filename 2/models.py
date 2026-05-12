from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Kullanici(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(50), unique=True, nullable=True)
    eposta = db.Column(db.String(100), unique=True, nullable=True)
    sifre_hash = db.Column(db.String(255), nullable=True)
    ip_adresi = db.Column(db.String(50))
    # 'normal' | 'premium' | 'pro'
    plan = db.Column(db.String(10), default='normal', nullable=False, server_default='normal')
    is_admin = db.Column(db.Boolean, default=False, nullable=False, server_default='0')
    bantli = db.Column(db.Boolean, default=False, nullable=False, server_default='0')
    son_giris = db.Column(db.DateTime, nullable=True)
    olusturulma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    donusumler = db.relationship('Donusum', backref='kullanici', lazy=True)
    paylasimlar = db.relationship('DosyaPaylasim', backref='kullanici', lazy=True)

    @property
    def plan_label(self):
        return {'normal': 'Normal', 'premium': 'Premium', 'pro': 'Pro'}.get(self.plan, 'Normal')

    @property
    def plan_emoji(self):
        return {'normal': '', 'premium': '⭐', 'pro': '🚀'}.get(self.plan, '')

class Donusum(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kullanici_id = db.Column(db.Integer, db.ForeignKey('kullanici.id'), nullable=True)
    kaynak_format = db.Column(db.String(20))
    hedef_format = db.Column(db.String(20))
    dosya_adi = db.Column(db.String(255), nullable=True)
    dosya_boyutu = db.Column(db.Integer)
    basari_durumu = db.Column(db.Boolean)
    hata_mesaji = db.Column(db.Text, nullable=True)
    islem_suresi = db.Column(db.Float, nullable=True)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)

class DosyaPaylasim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kullanici_id = db.Column(db.Integer, db.ForeignKey('kullanici.id'), nullable=True)
    link_id = db.Column(db.String(16), unique=True, nullable=False)
    baslik = db.Column(db.String(120), nullable=True)           # kısa başlık — şifresiz önizleme için
    dosya_adi = db.Column(db.String(255))
    mesaj = db.Column(db.Text, nullable=True)
    indirme_sifresi = db.Column(db.String(255), nullable=True)
    gonderim_tipi = db.Column(db.String(10), default='link')
    alici_email = db.Column(db.String(100), nullable=True)
    aktif = db.Column(db.Boolean, default=True)
    silindi = db.Column(db.Boolean, default=False)
    saklama_gun = db.Column(db.Integer, nullable=True)          # 1/3/7/30/60/None=sonsuz
    expire_at = db.Column(db.DateTime, nullable=True)           # None = hiç silinmez (sonsuz)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    # VirusTotal tarama sonuçları (yalnızca Pro kullanıcılar için)
    vt_tarama_sonucu = db.Column(db.String(20), nullable=True)  # 'temiz' | 'tehlikeli' | 'hata' | None=taranmadı
    vt_tehdit_adi = db.Column(db.String(255), nullable=True)    # Tehdit adı (varsa)
    vt_tarama_tarihi = db.Column(db.DateTime, nullable=True)    # Tarama zamanı

    @property
    def suresi_dolmus_mu(self):
        if self.expire_at is None:
            return False
        return datetime.utcnow() > self.expire_at

    @property
    def kalan_saniye(self):
        if self.expire_at is None:
            return None
        delta = self.expire_at - datetime.utcnow()
        return max(0, int(delta.total_seconds()))

class HataLogu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donusum_id = db.Column(db.Integer, db.ForeignKey('donusum.id'))
    hata_mesaji = db.Column(db.Text)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
