/* WhatTheChip — fonte única das notificações (protótipo).
   Uma lista, três consumidores: o sino de qualquer tela, a página notificacoes.html e o contador.
   Máscara por papel: item com needs:"price"/"sales" só aparece para quem tem o gate (window.WTCAccess). */
(function(){
"use strict";

/* day: "hoje" | "ontem" | "semana" — agrupamento da página */
var ITEMS = [
  { id:"n7", kind:"risk", day:"hoje",   when:"há 12 min",
    title:"C-026 parado há 21 dias",
    body:"380 un. · <span class=\"m\">US$ 1.140</span> sem saída desde 25/06.",
    bodyMasked:"380 un. sem saída desde 25/06.",
    href:"estoque.html", unread:true },
  { id:"n6", kind:"warn", day:"hoje",   when:"há 2 h",
    title:"LOT/041 sem movimento há 6 dias",
    body:"12 PNs aguardando conferência da plataforma.",
    href:"triagem.html", unread:true },
  { id:"n5", kind:"info", day:"hoje",   when:"há 3 h",
    title:"24 chips foram para conferência",
    body:"Rafael S. marcou 24 un. como indeterminadas no <span class=\"m\">LOT/042</span>.",
    href:"triagem.html", unread:true },
  { id:"n4", kind:"good", day:"ontem",  when:"ontem · 17:40",
    title:"Envio ENV/018 aceito pelo comprador",
    body:"1.180 un. conferidas na chegada · resultado disponível em Vendas.",
    href:"vendas-lista.html", needs:"sales" },
  { id:"n3", kind:"good", day:"ontem",  when:"ontem · 09:12",
    title:"Repasse confirmado para 22/07",
    body:"<span class=\"m\">US$ 12.480</span> líquidos do LOT/039 · etapa 3 de 4.",
    href:"vendas-lista.html", needs:"price" },
  { id:"n2", kind:"info", day:"semana", when:"14/07",
    title:"Catálogo atualizado pela plataforma",
    body:"37 categorias do <span class=\"m\">LOT/042</span> revisadas — preços por unidade em dia.",
    href:"estoque.html" },
  { id:"n1", kind:"warn", day:"semana", when:"14/07",
    title:"Ritmo abaixo da média",
    body:"Joana P. em 180 un./h contra 412 un./h da média da equipe.",
    href:"painel.html", needs:"sales" }
];

var KEY = "wtc_notif_read";
function readSet(){ try{ return JSON.parse(localStorage.getItem(KEY) || "[]") || []; }catch(e){ return []; } }
function saveSet(a){ try{ localStorage.setItem(KEY, JSON.stringify(a)); }catch(e){} }
function isRead(it){ return !it.unread || readSet().indexOf(it.id) >= 0; }
function markAll(){ saveSet(ITEMS.map(function(i){ return i.id; })); }
function markOne(id){ var s = readSet(); if(s.indexOf(id)<0){ s.push(id); saveSet(s); } }

function gate(){
  var a = (window.WTCAccess && window.WTCAccess.access) ? window.WTCAccess.access() : { can_see_price:true, can_sales:true };
  return a;
}
function visible(){
  var a = gate();
  return ITEMS.filter(function(it){
    if(it.needs === "price" && !a.can_see_price) return false;
    if(it.needs === "sales" && !a.can_sales) return false;
    return true;
  });
}
function bodyOf(it){
  var a = gate();
  return (!a.can_see_price && it.bodyMasked) ? it.bodyMasked : it.body;
}
function unreadCount(){ return visible().filter(function(it){ return !isRead(it); }).length; }

function el(tag, cls, html){
  var n = document.createElement(tag);
  if(cls) n.className = cls;
  if(html != null) n.innerHTML = html;
  return n;
}
var ARROW = '<svg viewBox="0 0 24 24" stroke-linecap="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';

/* ---------- sino: dropdown ---------- */
function mountBell(){
  var bell = document.getElementById("bell");
  if(!bell || bell.parentNode.classList.contains("nbell")) return;

  var wrap = el("div","nbell");
  bell.parentNode.insertBefore(wrap, bell);
  wrap.appendChild(bell);
  bell.setAttribute("aria-haspopup","true");
  bell.setAttribute("aria-expanded","false");

  var drop = el("div","ndrop");
  drop.setAttribute("role","dialog");
  drop.setAttribute("aria-label","Notificações");
  var head = el("div","ndrop__h");
  var t = el("div","ndrop__t",'Notificações');
  var n = el("span","ndrop__n");
  t.appendChild(n);
  var mark = el("button","ndrop__mark","Marcar como lidas");
  mark.type = "button";
  head.appendChild(t); head.appendChild(mark);
  var list = el("div","ndrop__list");
  var all = el("a","ndrop__all",'Ver todas as notificações' + ARROW);
  all.href = "notificacoes.html";
  drop.appendChild(head); drop.appendChild(list); drop.appendChild(all);
  wrap.appendChild(drop);

  function paint(){
    var items = visible();
    var u = unreadCount();
    n.textContent = u;
    n.style.display = u ? "" : "none";
    mark.style.display = u ? "" : "none";
    var dot = bell.querySelector(".dot");
    if(dot) dot.style.display = u ? "" : "none";
    list.innerHTML = "";
    if(!items.length){ list.appendChild(el("div","ndrop__empty","Nada novo por aqui.")); return; }
    items.slice(0,5).forEach(function(it){
      var a = el("a","nitem nitem--" + it.kind + (isRead(it) ? "" : " nitem--new"));
      a.href = it.href;
      a.appendChild(el("span","nitem__d"));
      a.appendChild(el("span","nitem__t", it.title));
      a.appendChild(el("span","nitem__w", it.when));
      a.appendChild(el("span","nitem__b", bodyOf(it)));
      a.addEventListener("click", function(){ markOne(it.id); });
      list.appendChild(a);
    });
  }
  function open(v){
    wrap.classList.toggle("on", v);
    bell.setAttribute("aria-expanded", v ? "true" : "false");
    if(v) paint();
  }
  bell.onclick = function(e){ e.preventDefault(); e.stopPropagation(); open(!wrap.classList.contains("on")); };
  mark.onclick = function(e){ e.stopPropagation(); markAll(); paint(); };
  document.addEventListener("click", function(e){ if(!wrap.contains(e.target)) open(false); });
  document.addEventListener("keydown", function(e){ if(e.key === "Escape") open(false); });
  paint();
}

/* ---------- página: lista completa ---------- */
var GROUPS = [["hoje","Hoje"],["ontem","Ontem"],["semana","Esta semana"]];
function renderPage(host, filter){
  if(!host) return;
  var items = visible().filter(function(it){ return filter === "unread" ? !isRead(it) : true; });
  host.innerHTML = "";
  if(!items.length){
    host.appendChild(el("div","nempty", filter === "unread" ? "Nenhuma notificação não lida." : "Nenhuma notificação."));
    return;
  }
  GROUPS.forEach(function(g){
    var rows = items.filter(function(it){ return it.day === g[0]; });
    if(!rows.length) return;
    var sec = el("section","ngroup");
    sec.appendChild(el("div","ngroup__h",'<span>' + g[1] + '</span><i></i><span class="ngroup__c">' + rows.length + '</span>'));
    rows.forEach(function(it){
      var a = el("a","nrow nrow--" + it.kind + (isRead(it) ? "" : " nrow--new"));
      a.href = it.href;
      a.innerHTML =
        '<span class="nrow__d"></span>' +
        '<span class="nrow__main"><span class="nrow__t">' + it.title + '</span>' +
        '<span class="nrow__b">' + bodyOf(it) + '</span></span>' +
        '<span class="nrow__meta"><span class="nrow__w">' + it.when + '</span>' +
        (isRead(it) ? '' : '<span class="nrow__new">NOVA</span>') + '</span>' +
        '<span class="nrow__go">' + ARROW + '</span>';
      a.addEventListener("click", function(){ markOne(it.id); });
      sec.appendChild(a);
    });
    host.appendChild(sec);
  });
}

window.WTCNotif = {
  items: ITEMS, visible: visible, unread: unreadCount, markAll: markAll,
  mountBell: mountBell, renderPage: renderPage, isRead: isRead
};
if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountBell);
else mountBell();
})();
