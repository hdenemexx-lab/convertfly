/**
 * Tema değiştirici (açık / koyu) ve giriş-kayıt modalları — yer tutucu formlar.
 */
(function () {
    "use strict";

    var root = document.documentElement;
    var THEME_KEY = "theme";

    function temaUygula(mode) {
        if (mode === "dark") {
            root.setAttribute("data-theme", "dark");
        } else {
            root.removeAttribute("data-theme");
        }
        try {
            localStorage.setItem(THEME_KEY, mode === "dark" ? "dark" : "light");
        } catch (e) {
            /* ignore */
        }
    }

    function modalAc(id) {
        var el = document.getElementById(id);
        if (!el) return;
        el.hidden = false;
        document.body.classList.add("modal-open");
        var foc = el.querySelector("input, button");
        if (foc) foc.focus();
    }

    function modalKapat() {
        document.querySelectorAll(".modal").forEach(function (m) {
            m.hidden = true;
        });
        document.body.classList.remove("modal-open");
    }

    document.addEventListener("DOMContentLoaded", function () {
        var themeBtn = document.getElementById("theme-toggle");
        if (themeBtn) {
            themeBtn.addEventListener("click", function () {
                var koyu = root.getAttribute("data-theme") === "dark";
                temaUygula(koyu ? "light" : "dark");
            });
        }

        document.querySelectorAll("[data-modal-open]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                modalAc(btn.getAttribute("data-modal-open"));
            });
        });

        document.addEventListener("click", function (e) {
            if (e.target.getAttribute("data-modal-close") != null) modalKapat();
        });

        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape") modalKapat();
        });

    });
})();
