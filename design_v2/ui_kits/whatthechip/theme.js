/* WhatTheChip — alternância de tema da barra interna.
   Por enquanto só guarda a preferência e troca o ícone; as regras do modo escuro ainda não existem. */
(function(){
  "use strict";
  /* chrome de protótipo: não roda quando este arquivo chega pelo bundle compilado do design
     system. O compilador empilha os .js do projeto em _ds_bundle.js, e ali dentro isto se
     auto-executava em páginas que não são telas — cards de especificação, projetos consumidores —
     estampando data-theme/data-wtc-* no <html> delas.
     A condição é a PRESENÇA do bundle, não a ausência de uma folha: "carrega wtc-carbon.css" não é
     assinatura de tela do kit (a landing declara os tokens inline e não carrega folha nenhuma), e
     inferir de um link deixava justamente ela sem os controles. */
  if(document.querySelector('script[src*="_ds_bundle"]'))return;
  var KEY="wtc_theme";
  function saved(){try{return localStorage.getItem(KEY);}catch(e){return null;}}
  function set(t){
    document.documentElement.setAttribute("data-theme",t);
    try{localStorage.setItem(KEY,t);}catch(e){}
    var b=document.getElementById("theme-btn");
    if(b)b.setAttribute("aria-pressed",t==="dark"?"true":"false");
  }
  function init(){
    set(saved()==="dark"?"dark":"light");
    var b=document.getElementById("theme-btn");
    if(!b)return;
    b.onclick=function(){
      set(document.documentElement.getAttribute("data-theme")==="dark"?"light":"dark");
    };
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
