/**
 * Ana sayfa dosya dönüştürücü — Convertio tarzı sade ve profesyonel arayüz.
 */
(function () {
    "use strict";

    var AD_MAX = 30;
    var idSay  = 0;

    /* Kategori ikonları (Sadece satır başında görünecek, sade) */
    var KOVAN_IKON = {
        arsiv:       "📦",
        cad:         "📐",
        ebook:       "📚",
        evrak:       "📄",
        goruntu:     "🖼️",
        ses:         "🎵",
        sunum:       "📑",
        vektor:      "✒️",
        video:       "🎬",
        yazi_tipi:   "🔤"
    };

    /* Format etiket bilgileri (Sadece kısa isimleri kullanacağız) */
    function formatAd(deger) {
        var map = {
            "json_pretty": "JSON",
            "json_to_csv": "CSV",
            "pdf_txt": "TXT",
            "pdf_ocr": "TXT (OCR)",
            "docx_txt": "TXT",
            "txt_normalize": "UTF-8",
            "txt_ocr": "TXT (OCR)",
            "pptx_txt": "TXT",
        };
        return map[deger] || deger.toUpperCase();
    }

    /* ──────────────────── Yardımcı fonksiyonlar ──────────────────── */
    function uzantiAl(f) {
        var n = ((f && f.name) || "").toLowerCase();
        var i = n.lastIndexOf(".");
        return i < 0 ? "" : n.slice(i);
    }
    function kovanBul(ext, K) {
        return (K.uzantiKovan && K.uzantiKovan[ext]) || null;
    }
    function kisaltAd(ad) {
        if (!ad || ad.length <= AD_MAX) return ad || "";
        var dot = ad.lastIndexOf(".");
        var ext = dot > 0 ? ad.slice(dot) : "";
        var stem = dot > 0 ? ad.slice(0, dot) : ad;
        var keep = AD_MAX - ext.length - 3;
        return keep > 0 ? stem.slice(0, keep) + "…" + ext : ad.slice(0, AD_MAX) + "…";
    }
    function boyutYazi(b) {
        if (!b) return "";
        if (b < 1024) return b + " B";
        if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
        return (b / 1048576).toFixed(2) + " MB";
    }
    function ilkUygunHedef(kovan, u0, K) {
        var liste = (K.hedefler && K.hedefler[kovan]) || [];
        for (var i = 0; i < liste.length; i++) {
            if (kovan === "sunum" && (u0 === ".ppt" || u0 === ".odp") && liste[i].value === "txt") continue;
            if (liste[i].label.indexOf("(hazır değil)") === -1) {
                return liste[i].value;
            }
        }
        return "";
    }

    /* ─────────────────── Görsel Format Seçici ─────────────────────
     * Convertio tarzı:
     * Dışarıda "şuna: [ PNG ▼ ]"
     * İçeride temiz beyaz arkaplanda gri çerçeveli format kutuları.
     * ────────────────────────────────────────────────────────────── */
    function formatSeciciOlustur(kovan, u0, K, seciliDeger, onChange) {
        var uygunlar = (K.hedefler && K.hedefler[kovan]) || [];
        var ilk      = seciliDeger || ilkUygunHedef(kovan, u0, K);
        var secilenDeger = uygunlar.length ? ilk : "";

        /* Sarmalayıcı */
        var wrap = document.createElement("div");
        wrap.className = "cv-wrap";

        /* "şuna:" kelimesi */
        var etiket = document.createElement("span");
        etiket.className = "cv-etiket";
        etiket.textContent = "şuna:";
        wrap.appendChild(etiket);

        /* Tetikleyici buton */
        var trigger = document.createElement("button");
        trigger.type = "button";
        trigger.className = "cv-trigger";

        function triggerGuncelle() {
            if (secilenDeger) {
                var lab = formatAd(secilenDeger);
                // hazır değil mi kontrol et
                var hiziDegil = false;
                uygunlar.forEach(function(u) { if(u.value === secilenDeger && u.label.indexOf("(hazır değil)") > -1) hiziDegil = true; });
                var renk = hiziDegil ? "var(--error-text)" : "var(--text)";

                trigger.innerHTML = 
                    '<span style="color:'+renk+'; padding-right: 4px;">' + lab + '</span>' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';
            } else {
                trigger.innerHTML = 
                    '<span style="color:var(--muted);font-weight:500;">Seç...</span>' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';
            }
        }
        triggerGuncelle();

        /* Açılır Menü Alanı (Popup) */
        var popupArea = document.createElement("div");
        popupArea.className = "cv-popup-area";
        popupArea.style.display = "none";
        
        /* Popup Kutu */
        var popup = document.createElement("div");
        popup.className = "cv-popup";
        
        function kartlarCiz() {
            popup.innerHTML = "";
            var baslik = document.createElement("div");
            baslik.className = "cv-popup-head";
            baslik.innerHTML = (K.kategoriEtiketleri && K.kategoriEtiketleri[kovan] ? K.kategoriEtiketleri[kovan].toUpperCase() : 'HEDEF FORMAT');
            popup.appendChild(baslik);

            var grid = document.createElement("div");
            grid.className = "cv-grid";

            uygunlar.forEach(function (it) {
                var hazirDegil = it.label.indexOf("(hazır değil)") !== -1;
                var isDisabled = (kovan === "sunum" && (u0 === ".ppt" || u0 === ".odp") && it.value === "txt");
                var btn = document.createElement("button");
                btn.type = "button";
                btn.className = "cv-btn" + (it.value === secilenDeger ? " cv-btn--aktif" : "");
                btn.disabled = isDisabled;
                
                if(hazirDegil) {
                    btn.classList.add("cv-btn--not-ready");
                    btn.title = "Bu format henüz hazır değil.";
                }

                btn.textContent = formatAd(it.value);

                btn.addEventListener("click", function () {
                    secilenDeger = it.value;
                    triggerGuncelle();
                    if (onChange) onChange(secilenDeger);
                    kapat();
                });
                grid.appendChild(btn);
            });
            popup.appendChild(grid);
        }

        function ac() {
            document.querySelectorAll(".cv-popup-area:not([style*='display: none'])").forEach(function (p) { p.style.display = 'none'; });
            kartlarCiz();
            popupArea.style.display = "block";
            trigger.classList.add("cv-trigger--open");
        }
        function kapat() {
            popupArea.style.display = "none";
            trigger.classList.remove("cv-trigger--open");
        }

        trigger.addEventListener("click", function (e) {
            e.stopPropagation();
            popupArea.style.display === "none" ? ac() : kapat();
        });

        // Dışarı tıklayınca kapat
        document.addEventListener("click", function (e) {
            if (!wrap.contains(e.target)) kapat();
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape") kapat();
        });

        popupArea.appendChild(popup);
        wrap.appendChild(trigger);
        wrap.appendChild(popupArea);

        return {
            el: wrap,
            getValue: function () { return secilenDeger; },
            setValue: function (val) {
                secilenDeger = val;
                triggerGuncelle();
            }
        };
    }

    /* ──────────────────────────────────────────────────────────────── */
    document.addEventListener("DOMContentLoaded", function () {
        var K = window.DONUSTUR_KURALLARI;
        if (!K || !K.uzantiKovan) return;

        var form      = document.getElementById("convert-form");
        var panel     = form && form.querySelector(".drop-panel");
        var input     = document.getElementById("dosya-input");
        var secBtn    = form && form.querySelector(".btn-ghost");
        var listeEl   = document.getElementById("dosya-listesi");
        var bosMetin  = document.getElementById("dosya-bos");
        var ozetEl    = document.getElementById("dosya-ozet");
        var hint      = document.getElementById("format-hint");
        var btnGonder = document.getElementById("btn-gonder");
        var dyn       = document.getElementById("dyn-inputs");

        if (!form || !panel || !input || !listeEl || !dyn) return;

        var satirlar = [];

        /* CSS enjekte et — Convertio Stili */
        if (!document.getElementById("cv-style")) {
            var s = document.createElement("style");
            s.id = "cv-style";
            s.textContent = [
                /* Satır tasarımı */
                ".cv-satir{display:grid;grid-template-columns:40px 1fr auto 40px;align-items:center;background:var(--surface);border:1px solid var(--border);border-radius:4px;padding:12px 16px;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,0.02); transition:box-shadow .2s;}",
                ".cv-satir:hover{box-shadow:0 4px 12px rgba(0,0,0,0.06);}",
                ".cv-satir-ikon{font-size:22px; width:100%; text-align:left;}",
                ".cv-satir-orta{display:flex;flex-direction:row;align-items:center;gap:12px; min-width:0; padding-right:16px;}",
                ".cv-satir-ad{font-weight:600;font-size:14px;color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}",
                ".cv-satir-boyut{color:var(--muted);font-size:13px; font-weight:500; flex-shrink:0;}",
                ".cv-satir-sag{display:flex;align-items:center;justify-content:flex-end;}",
                ".cv-kaldir{color:var(--muted);font-size:24px;cursor:pointer;background:none;border:none;padding:0;line-height:1;transition:color .15s; font-weight:300; width:100%; text-align:right; display:flex; align-items:center; justify-content:flex-end;}",
                ".cv-kaldir:hover{color:#dc2626;}",

                /* Format Seçici Araçları */
                ".cv-wrap{position:relative;display:flex;align-items:center;}",
                ".cv-etiket{color:var(--muted);font-size:13.5px;font-weight:500;margin-right:10px;}",
                
                /* Tetikleyici Buton */
                ".cv-trigger{display:inline-flex;align-items:center;justify-content:space-between;gap:12px;min-width:90px;padding:8px 12px;",
                "background:var(--surface);border:1px solid var(--border);border-radius:4px;",
                "cursor:pointer;font-family:inherit;font-size:14px;font-weight:600;color:var(--text);",
                "transition:border-color .15s;}",
                ".cv-trigger:hover,.cv-trigger--open{border-color:var(--accent);color:var(--accent);}",
                ".cv-trigger svg{width:14px;height:14px;color:var(--muted);transition:transform .2s;}",
                ".cv-trigger:hover svg,.cv-trigger--open svg{color:var(--accent);}",
                ".cv-trigger--open svg{transform:rotate(180deg);}",

                /* Popup Alanı */
                ".cv-popup-area{position:absolute;top:calc(100% + 4px);right:0;z-index:9999;}",
                ".cv-popup{background:var(--surface);border:1px solid var(--border);border-radius:6px;",
                "box-shadow:0 8px 24px rgba(0,0,0,.12);min-width:280px;padding:16px;",
                "animation:cvPop .15s cubic-bezier(.4,0,.2,1);}",
                "html[data-theme='dark'] .cv-popup{box-shadow:0 8px 32px rgba(0,0,0,.5);}",
                "@keyframes cvPop{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}",

                /* Popup İçi */
                ".cv-popup-head{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px; border-bottom:1px solid var(--border); padding-bottom:8px;}",
                ".cv-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(65px,1fr));gap:8px;}",
                
                /* Butonlar */
                ".cv-btn{padding:8px 4px;border:1px solid var(--border);border-radius:4px;background:transparent;color:var(--text);font-weight:600;font-size:13px;cursor:pointer;text-align:center;text-transform:uppercase;transition:all .15s;font-family:inherit;}",
                ".cv-btn:hover{border-color:var(--accent);color:var(--accent);}",
                ".cv-btn--aktif{border-color:var(--accent);background:var(--accent);color:#fff;}",
                ".cv-btn--aktif:hover{color:#fff;}",
                ".cv-btn:disabled{opacity:0.3;cursor:not-allowed;background:var(--bg);border-color:var(--border);}",
                
                ".cv-btn--not-ready { border-style: dashed; opacity: 0.7;}",
                ".cv-btn--not-ready:hover { border-style: solid; border-color:var(--error-text); color:var(--error-text);}",
                
                /* Toplu Seçim Üst Alanı */
                ".toplu-sec-wrap { display:none; justify-content:space-between; align-items:center; background:var(--surface); border:1px solid var(--border); padding: 12px 16px; border-radius:4px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }",
            ].join("");
            document.head.appendChild(s);
        }

        /* Toplu Seçici Oluştur */
        var globalWrap = document.createElement("div");
        globalWrap.className = "toplu-sec-wrap";
        globalWrap.innerHTML = `
            <div style="font-weight:600; color:var(--text); font-size:14px;">Tüm Dosyaları Şuna Dönüştür:</div>
            <div class="cv-wrap" id="toplu-secici-container"></div>
        `;
        listeEl.parentElement.insertBefore(globalWrap, listeEl);
        
        var globalSecili = "";
        var globalPopupAlani = null;
        
        function gonderimKontrol() {
            var gecerli = satirlar.length > 0;
            var toplamV = 0;
            var limitMB = window.MAX_MB_LIMIT || 32;
            for (var i = 0; i < satirlar.length; i++) {
                if (!satirlar[i].hedef || satirlar[i].hazirDegil) { gecerli = false; break; }
                toplamV += satirlar[i].file.size || 0;
            }
            if (toplamV > limitMB * 1024 * 1024) gecerli = false;
            if (btnGonder) btnGonder.disabled = !gecerli;
        }

        function ozetiGuncelle() {
            var toplam = 0;
            var limitMB = window.MAX_MB_LIMIT || 32;
            for (var i = 0; i < satirlar.length; i++) toplam += satirlar[i].file.size || 0;
            if (!satirlar.length) {
                if (ozetEl) { ozetEl.hidden = true; ozetEl.textContent = ""; }
                if (bosMetin) bosMetin.style.display = "";
                globalWrap.style.display = "none";
                return;
            }
            if (bosMetin) bosMetin.style.display = "none";
            if (ozetEl) {
                ozetEl.hidden = false;
                ozetEl.innerHTML = satirlar.length + " dosya &middot; toplam " + boyutYazi(toplam) + " (sınır " + limitMB + " MB)";
                
                if (toplam > limitMB * 1024 * 1024) {
                    ozetEl.innerHTML += " <br><span style='color:var(--error-text);font-weight:600;'>Limit aşıldı! Lütfen dosya sayısını veya boyutunu azaltın.</span>";
                }
            }
            
            // Generate Toplu Seçici Options dynamically based on current categories
            if(satirlar.length > 1) {
                globalWrap.style.display = "flex";
                topluSeciciRender();
            } else {
                globalWrap.style.display = "none";
            }
        }
        
        function topluSeciciRender() {
            var container = document.getElementById("toplu-secici-container");
            container.innerHTML = "";
            var trigger = document.createElement("button");
            trigger.type = "button";
            trigger.className = "cv-trigger";
            trigger.innerHTML = '<span style="color:var(--accent);font-weight:600;">Seç...</span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';
            
            var popupArea = document.createElement("div");
            popupArea.className = "cv-popup-area";
            popupArea.style.display = "none";
            var popup = document.createElement("div");
            popup.className = "cv-popup";
            popup.style.width = "400px";
            popup.style.maxHeight = "400px";
            popup.style.overflowY = "auto";
            
            // Get common kovans
            var kovanSet = {};
            satirlar.forEach(function(s) { kovanSet[s.kovan] = true; });
            
            Object.keys(kovanSet).forEach(function(kov) {
                var hedeflerLst = K.hedefler[kov] || [];
                if(hedeflerLst.length === 0) return;
                
                var g = document.createElement("div");
                g.style.marginBottom = "16px";
                var head = document.createElement("div");
                head.className = "cv-popup-head";
                head.textContent = K.kategoriEtiketleri[kov] || kov;
                g.appendChild(head);
                
                var grid = document.createElement("div");
                grid.className = "cv-grid";
                hedeflerLst.forEach(function(hd) {
                    var isHazirDegil = hd.label.indexOf("(hazır değil)") > -1;
                    var btn = document.createElement("button");
                    btn.type = "button";
                    btn.className = "cv-btn";
                    if(isHazirDegil) {
                        btn.classList.add("cv-btn--not-ready");
                    }
                    btn.textContent = hd.value.toUpperCase();
                    btn.addEventListener("click", function() {
                        // Apply this target to all valid files in this kovan!
                        satirlar.forEach(function(s) {
                            if(s.kovan === kov) {
                                // check if allowed
                                var alwd = false;
                                K.hedefler[kov].forEach(function(qq) { if(qq.value === hd.value) alwd = true; });
                                if(alwd) {
                                    s.hedef = hd.value;
                                    s.hazirDegil = isHazirDegil;
                                    if(s.secici) s.secici.setValue(hd.value);
                                }
                            }
                        });
                        trigger.innerHTML = '<span style="color:var(--accent);font-weight:600;">' + K.kategoriEtiketleri[kov] + ' -> ' + hd.value.toUpperCase() + '</span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';
                        gonderimKontrol();
                        kapat();
                    });
                    grid.appendChild(btn);
                });
                g.appendChild(grid);
                popup.appendChild(g);
            });
            
            popupArea.appendChild(popup);
            container.appendChild(trigger);
            container.appendChild(popupArea);
            
            function ac() {
                document.querySelectorAll(".cv-popup-area:not([style*='display: none'])").forEach(function (p) { p.style.display = 'none'; });
                popupArea.style.display = "block";
                trigger.classList.add("cv-trigger--open");
            }
            function kapat() {
                popupArea.style.display = "none";
                trigger.classList.remove("cv-trigger--open");
            }
            trigger.addEventListener("click", function(e) {
                e.stopPropagation();
                popupArea.style.display === "none" ? ac() : kapat();
            });
            document.addEventListener("click", function (e) {
                if (!container.contains(e.target)) kapat();
            });
        }

        function yenidenCiz() {
            listeEl.innerHTML = "";
            for (var i = 0; i < satirlar.length; i++) {
                var satir = satirlar[i];
                var ikonEmoji = KOVAN_IKON[satir.kovan] || "📄";

                var row = document.createElement("div");
                row.className = "cv-satir";
                row.dataset.rowId = String(satir.id);

                /* İkon */
                var ikonEl = document.createElement("div");
                ikonEl.className = "cv-satir-ikon";
                ikonEl.textContent = ikonEmoji;
                ikonEl.title = (K.kategoriEtiketleri && K.kategoriEtiketleri[satir.kovan]) || satir.kovan;

                /* Orta (İsim + Boyut) */
                var orta = document.createElement("div");
                orta.className = "cv-satir-orta";

                var ad = document.createElement("div");
                ad.className = "cv-satir-ad";
                ad.textContent = kisaltAd(satir.file.name);
                ad.title = satir.file.name;

                var boy = document.createElement("div");
                boy.className = "cv-satir-boyut";
                boy.textContent = boyutYazi(satir.file.size);

                orta.appendChild(ad);
                orta.appendChild(boy);

                /* Sağ (Seçici + Kapat) */
                var sag = document.createElement("div");
                sag.className = "cv-satir-sag";

                var secici = formatSeciciOlustur(satir.kovan, satir.uz, K, satir.hedef, (function(s) {
                    return function(deger) {
                        s.hedef = deger;
                        s.hazirDegil = false;
                        var arr = K.hedefler[s.kovan] || [];
                        for(var idx=0; idx<arr.length; idx++){
                            if(arr[idx].value === deger && arr[idx].label.indexOf('(hazır değil)') > -1) {
                                s.hazirDegil = true;
                            }
                        }
                        gonderimKontrol();
                    };
                })(satir));
                satir.hedef = secici.getValue();
                
                satir.hazirDegil = false;
                var arr0 = K.hedefler[satir.kovan] || [];
                for(var idx0=0; idx0<arr0.length; idx0++){
                    if(arr0[idx0].value === satir.hedef && arr0[idx0].label.indexOf('(hazır değil)') > -1) {
                        satir.hazirDegil = true;
                    }
                }
                
                satir.secici = secici;

                var kid = satir.id;
                var kaldir = document.createElement("button");
                kaldir.type = "button";
                kaldir.className = "cv-kaldir";
                kaldir.setAttribute("aria-label", "Dosyayı çıkar");
                kaldir.innerHTML = "&times;";
                kaldir.addEventListener("click", function () {
                    satirlar = satirlar.filter(function (s) { return s.id !== kid; });
                    yenidenCiz();
                });

                sag.appendChild(secici.el);
                sag.appendChild(kaldir);

                row.appendChild(ikonEl);
                row.appendChild(orta);
                row.appendChild(sag);
                listeEl.appendChild(row);
            }
            ozetiGuncelle();
            gonderimKontrol();
        }

        function dosyaEkle(dosyaListesi) {
            if (!dosyaListesi || !dosyaListesi.length) return;
            var bilinmeyen = [];
            for (var i = 0; i < dosyaListesi.length; i++) {
                var f = dosyaListesi[i];
                var uz = uzantiAl(f);
                var kov = kovanBul(uz, K);
                if (!kov) { bilinmeyen.push(f.name); continue; }
                satirlar.push({ id: ++idSay, file: f, kovan: kov, uz: uz, hedef: "", hazirDegil: false, secici: null });
            }
            if (hint) {
                hint.textContent = bilinmeyen.length
                    ? "Bazı dosyalar tanınmayan uzantı nedeniyle eklenmedi: " + bilinmeyen.slice(0, 3).join(", ") + (bilinmeyen.length > 3 ? "…" : "")
                    : "Her dosya için formatı seçip 'Dönüştür'e tıklayın. Toplu seçim aracıyla tüm formatları hedef kategori bazında ayarlayabilirsiniz.";
            }
            yenidenCiz();
        }

        /* ──── Form submit (AJAX) ──── */
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            
            // Check hazir degil
            var err = false;
            var toplamV = 0;
            for(var i=0; i<satirlar.length; i++) {
                if(satirlar[i].hazirDegil) err = true;
                toplamV += satirlar[i].file.size || 0;
            }
            if(err) {
                alert("Uyarı: (Hazır değil) olarak işaretli formatlara dönüşüm şu anda yapılamamaktadır! Sisteme daha sonra eklenecektir. Lütfen başka bir format seçin.");
                return;
            }
            
            var limitMB = window.MAX_MB_LIMIT || 32;
            if(toplamV > limitMB * 1024 * 1024) {
                alert("Uyarı: Toplam dosya boyutu limitin üzerinde! İzin verilen limit: " + limitMB + " MB.");
                return;
            }

            var progWrap = document.getElementById("prog-wrap");
            var progBar  = document.getElementById("prog-bar");
            var progText = document.getElementById("prog-text");
            var dlWrap   = document.getElementById("dl-wrap");
            var dlBtn    = document.getElementById("dl-btn");

            var data = new FormData();
            data.append("is_ajax", "1");
            for (var i = 0; i < satirlar.length; i++) {
                data.append("dosya", satirlar[i].file);
                data.append("cikti", satirlar[i].hedef);
            }

            if (btnGonder) { btnGonder.disabled = true; btnGonder.style.opacity = "0.5"; }
            if (progWrap) progWrap.style.display = "block";
            if (dlWrap)   dlWrap.style.display   = "none";
            if (progText) progText.textContent    = "Yükleniyor... %0";
            if (progBar)  { progBar.style.width = "0%"; progBar.style.background = "var(--accent)"; }

            var xhr = new XMLHttpRequest();
            xhr.open("POST", form.action, true);
            xhr.responseType = "blob";

            xhr.upload.onprogress = function (pe) {
                if (pe.lengthComputable && progBar && progText) {
                    var pct = Math.round((pe.loaded / pe.total) * 100);
                    progBar.style.width = pct + "%";
                    progText.textContent = pct < 100 ? "Yükleniyor: %" + pct : "Dönüştürülüyor…";
                }
            };

            xhr.onload = function () {
                if (btnGonder) { btnGonder.disabled = false; btnGonder.style.opacity = "1"; }
                if (xhr.status === 200) {
                    if (progText) progText.textContent = "✅ Başarıyla Tamamlandı!";
                    if (progBar)  progBar.style.background = "#10b981";

                    var blob  = xhr.response;
                    var disp  = xhr.getResponseHeader("Content-Disposition");
                    var fname = "donusturulmus_dosya.zip";
                    if (disp && disp.indexOf("filename=") !== -1) {
                        fname = disp.split("filename=")[1].split(";")[0].replace(/"/g, "");
                    }
                    var url = URL.createObjectURL(blob);
                    if (dlWrap && dlBtn) { 
                        dlWrap.style.display = "block"; 
                        dlBtn.href = url; 
                        dlBtn.download = fname;
                        // Dosya adını butona yazdır (uzunsa kısaltılmış haliyle)
                        dlBtn.textContent = "👇 " + kisaltAd(fname) + " İndir";
                    }
                } else {
                    if (progText) progText.textContent = "❌ Hata oluştu!";
                    if (progBar)  progBar.style.background = "var(--error-text)";
                    var reader = new FileReader();
                    reader.onload = function () {
                        var j = { error: "Bilinmeyen hata." };
                        try { j = JSON.parse(reader.result); } catch (e2) {}
                        alert("Hata: " + j.error);
                    };
                    reader.readAsText(xhr.response);
                }
            };

            xhr.onerror = function () {
                if (btnGonder) { btnGonder.disabled = false; btnGonder.style.opacity = "1"; }
                alert("Ağ hatası veya bağlantı kesildi.");
            };

            xhr.send(data);
        });

        /* ──── Olaylar ──── */
        function acSecici() { input.click(); }

        panel.addEventListener("click", function (e) {
            if (e.target.closest(".btn-ghost")) return;
            acSecici();
        });
        if (secBtn) {
            secBtn.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); acSecici(); });
        }
        panel.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); acSecici(); }
        });
        input.addEventListener("change", function () {
            if (input.files && input.files.length) dosyaEkle(input.files);
            input.value = "";
        });
        ["dragenter", "dragover"].forEach(function (n) {
            panel.addEventListener(n, function (e) { e.preventDefault(); e.stopPropagation(); panel.classList.add("drop-panel--active"); });
        });
        ["dragleave", "drop"].forEach(function (n) {
            panel.addEventListener(n, function (e) { e.preventDefault(); e.stopPropagation(); panel.classList.remove("drop-panel--active"); });
        });
        panel.addEventListener("drop", function (e) {
            panel.classList.remove("drop-panel--active");
            dosyaEkle(e.dataTransfer && e.dataTransfer.files);
        });
        
        yenidenCiz();
    });
})();
