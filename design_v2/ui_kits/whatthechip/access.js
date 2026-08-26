/* WhatTheChip — SINGLE SOURCE OF TRUTH for tenancy/masking (prototype mirror of tenancy.access).
   No screen invents its own rule: every surface reads window.WTCAccess.access().
   In Django this maps to tenancy.access.is_unmasked (+ price / sales / debug gates). */
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
  var ROLES = {
    operador:   { label:"Operador",         company:"eMiner",      avatar:"eM", user:"Rafael S.",  me:"RS",  is_platform:false, price:false, sales:false, superuser:false, lots:false, notices:false },
    gerente:    { label:"Gerente",          company:"eMiner",      avatar:"eM", user:"Matheus G.", me:"MG",  is_platform:false, price:false, sales:true,  superuser:false, lots:true,  notices:false },
    admin:      { label:"Admin da empresa",  company:"eMiner",      avatar:"eM", user:"Matheus G.", me:"MG",  is_platform:false, price:true,  sales:true,  superuser:false, lots:true,  notices:true },
    plataforma: { label:"Plataforma",        company:"WhatTheChip", avatar:"WTC",user:"Equipe WTC",  me:"WTC", is_platform:true,  price:true,  sales:false, superuser:true,  lots:true,  notices:true }
  };
  var ORDER = ["operador","gerente","admin","plataforma"];
  function currentKey(){ try{ return localStorage.getItem("wtc_role") || "gerente"; }catch(e){ return "gerente"; } }
  function access(){
    var r = ROLES[currentKey()] || ROLES.gerente;
    return {
      role: currentKey(), label: r.label, company: r.company, avatar: r.avatar,
      user: r.user, me: r.me,            /* quem está logado — usado na atribuição de lotes */
      is_unmasked:   r.is_platform,   /* ← the one rule: only the platform sees the real decode */
      can_see_price: r.price,         /* preço em ¥ E em US$ — a máscara "US$-only" do admin foi revogada */
      can_sales:     r.sales,
      can_lots:      r.lots !== false,   /* operador não vê a lista completa de lotes */
      can_notices:   !!r.notices,     /* avisos da plataforma: assunto de quem responde pela conta */
      can_debug:     r.superuser,
      can_reopen:    r.superuser,     /* fechou, tá fechado: só a plataforma reabre (auditado) */
      superuser:     r.superuser,
      roleTag: r.superuser ? "Plataforma" : (r.price ? "Admin" : r.label)
    };
  }
  function set(k){ try{ localStorage.setItem("wtc_role", k); }catch(e){} location.reload(); }

  /* Apply access to shared shell hooks so every screen reflects the role without per-page logic. */
  function apply(){
    var a = access();
    document.querySelectorAll("[data-wtc-company]").forEach(function(el){ el.textContent = a.company; });
    document.querySelectorAll("[data-wtc-avatar]").forEach(function(el){ el.textContent = a.avatar; });
    document.querySelectorAll("[data-wtc-role]").forEach(function(el){ el.textContent = a.roleTag; });
    document.querySelectorAll("[data-wtc-user]").forEach(function(el){ el.textContent = a.user; });
    document.querySelectorAll("[data-wtc-initials]").forEach(function(el){ el.textContent = a.me; });
    document.querySelectorAll('[data-wtc-needs="sales"]').forEach(function(el){ el.style.display = a.can_sales ? "" : "none"; });
    document.querySelectorAll('[data-wtc-needs="lots"]').forEach(function(el){ el.style.display = a.can_lots ? "" : "none"; });
    document.querySelectorAll('[data-wtc-needs="notices"]').forEach(function(el){ el.style.display = a.can_notices ? "" : "none"; });
    document.querySelectorAll('[data-wtc-needs="nolots"]').forEach(function(el){ el.style.display = a.can_lots ? "none" : ""; });
    document.querySelectorAll('[data-wtc-needs="debug"]').forEach(function(el){ el.style.display = a.can_debug ? "" : "none"; });
    document.querySelectorAll('[data-wtc-needs="superuser"]').forEach(function(el){ el.style.display = a.superuser ? "" : "none"; });
    document.querySelectorAll('[data-wtc-needs="nosuperuser"]').forEach(function(el){ el.style.display = a.superuser ? "none" : ""; });
    document.querySelectorAll('[data-wtc-needs="price"]').forEach(function(el){ el.style.display = a.can_see_price ? "" : "none"; });
    document.querySelectorAll('[data-wtc-needs="noprice"]').forEach(function(el){ el.style.display = a.can_see_price ? "none" : ""; });
    document.querySelectorAll('[data-wtc-needs="unmasked"]').forEach(function(el){ el.style.display = a.is_unmasked ? "" : "none"; });
    document.querySelectorAll('[data-wtc-needs="masked"]').forEach(function(el){ el.style.display = a.is_unmasked ? "none" : ""; });
    document.documentElement.setAttribute("data-wtc-unmasked", a.is_unmasked ? "1" : "0");
  }

  /* Prototype-only role switcher (floating). Not part of the product chrome. */
  function mountSwitcher(){
    var a = access();
    var bar = document.createElement("div");
    bar.setAttribute("data-wtc-switcher","");
    bar.style.cssText = "position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:120;display:flex;align-items:center;gap:8px;background:#101317;border:1px solid #3a4249;border-radius:999px;padding:6px 6px 6px 14px;box-shadow:0 10px 30px -8px rgba(0,0,0,.5);font-family:'Helvetica Neue',Helvetica,Arial,sans-serif";
    var lbl = document.createElement("span");
    lbl.textContent = "PROTÓTIPO · ver como";
    lbl.style.cssText = "font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#697077;white-space:nowrap";
    bar.appendChild(lbl);
    ORDER.forEach(function(k){
      var b = document.createElement("button");
      b.textContent = ROLES[k].label;
      var on = k === a.role;
      b.style.cssText = "border:0;cursor:pointer;font-size:12px;font-weight:600;padding:6px 12px;border-radius:999px;white-space:nowrap;font-family:inherit;transition:all 120ms;"
        + (on ? "background:#0f62fe;color:#fff" : "background:transparent;color:#a2a9b0");
      b.onmouseenter = function(){ if(!on) b.style.color = "#f2f4f8"; };
      b.onmouseleave = function(){ if(!on) b.style.color = "#a2a9b0"; };
      b.onclick = function(){ set(k); };
      bar.appendChild(b);
    });
    var p = document.createElement("a");
    p.href = "parceiro-compras.html"; p.textContent = "Parceiro →";
    p.style.cssText = "margin-left:4px;padding:6px 12px;border-left:1px solid #3a4249;font-size:12px;font-weight:600;color:#78a9ff;text-decoration:none;white-space:nowrap";
    bar.appendChild(p);
    document.body.appendChild(bar);
  }

  window.WTCAccess = { ROLES: ROLES, order: ORDER, current: currentKey, access: access, set: set, apply: apply };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function(){ apply(); mountSwitcher(); });
  else { apply(); mountSwitcher(); }
})();
