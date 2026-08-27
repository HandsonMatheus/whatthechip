/* WhatTheChip — alternância de tema da barra do comprador.
   Adaptado de `design_v2/ui_kits/whatthechip/theme.js` em 2026-08-27.

   Duas diferenças em relação ao arquivo do protótipo, ambas por causa do
   Django e nenhuma por gosto:

   1. Sai a guarda `script[src*="_ds_bundle"]`. Ela existe no kit porque lá o
      compilador empilha os .js num bundle único que roda em páginas que não
      são telas (cards de especificação), e o script se auto-executava nelas.
      Aqui cada template carrega o que precisa; não há bundle para detectar.

   2. O tema é gravado ANTES da primeira pintura por um trecho inline no
      `<head>` do `partner_base.html`. Sem isso a página abre clara e pisca
      para escura no primeiro frame — o "flash of unstyled theme". Este
      arquivo cuida só do CLIQUE; quem decide o estado inicial é o inline.

   O estado mora em localStorage e no atributo `data-theme` do <html>, que é
   onde o pacote (`components.css`, `patterns/*.css`) procura por ele. */
(function () {
  "use strict";
  var KEY = "wtc_theme";

  function set(t) {
    document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem(KEY, t); } catch (e) {}
    var b = document.getElementById("theme-btn");
    if (b) b.setAttribute("aria-pressed", t === "dark" ? "true" : "false");
  }

  function init() {
    var b = document.getElementById("theme-btn");
    if (!b) return;
    /* O inline do <head> já pôs o atributo; aqui só sincronizamos o botão. */
    b.setAttribute("aria-pressed",
      document.documentElement.getAttribute("data-theme") === "dark" ? "true" : "false");
    b.onclick = function () {
      set(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else { init(); }
})();
