/* WhatTheChip — REGRAS DE DINHEIRO (fonte única do protótipo).
   ¥ inteiro · US$ com 2 casas · taxa com 4 casas. Em produção a formatação é server-side
   (Python); aqui é o espelho do contexto wtc_fx {rate_disp, date, is_market, is_fallback}.

   DUAS HIERARQUIAS DE DINHEIRO, e elas não são a mesma coisa:

   1. .mval — ¥ primário, US$ abaixo, menor e cinza. Para telas onde o dinheiro é CONSEQUÊNCIA:
      estoque, triagem, painel. Ali o ¥ é o dado do negócio e o dólar é leitura de contexto.
   2. .mvd (pair dual) — ¥ e US$ no MESMO corpo, lado a lado. Para o ciclo de venda, onde o
      dinheiro é o ARGUMENTO da tela: o comprador fecha o resultado em ¥ e paga em US$, e nenhum
      dos dois é nota de rodapé do outro.

   O "≈" mudou de significado (briefing v2, 19/08): antes marcava "US$ é tradução do ¥"; agora
   marca ESTIMATIVA. Rascunho tem valor vivo, re-resolvido contra a tabela do comprador, e leva
   til nos dois lados. Valor com câmbio travado sai EXATO, sem til — a conversão é aritmética,
   não palpite. Por isso dual() recebe {est:true} e não deduz o til do estado do câmbio.
   A TAXA no cabeçalho é restrita: só admin da empresa e superuser (plataforma) veem —
   operador e gerente não. PREÇO segue os mesmos gates de access.js (can_see_price). */
(function(){
"use strict";
var MARKET=0.1478,CONTRACT=0.1502,DATE="01/08",STALE="29/07";
var ORDER=["market","fallback","bootstrap","none"];
var LABEL={market:"taxa do dia",fallback:"taxa defasada",bootstrap:"taxa de contrato",none:"sem taxa"};

function key(){try{return localStorage.getItem("wtc_fx")||"market";}catch(e){return "market";}}
function state(){
  var k=key();
  if(k==="none")     return {key:k,rate:null,date:DATE,is_market:false,is_fallback:false,has:false};
  if(k==="bootstrap")return {key:k,rate:CONTRACT,date:DATE,is_market:false,is_fallback:false,has:true};
  if(k==="fallback") return {key:k,rate:MARKET,date:STALE,is_market:true,is_fallback:true,has:true};
  return {key:"market",rate:MARKET,date:DATE,is_market:true,is_fallback:false,has:true};
}
function setState(k){try{localStorage.setItem("wtc_fx",k);}catch(e){} render(); paintAll(); fire("state");}

/* ---------- formatação ---------- */
function nf(v,d){return Number(v).toLocaleString("pt-BR",{minimumFractionDigits:d,maximumFractionDigits:d});}
function cny(v){return "¥ "+nf(Math.round(v),0);}
function usd(v){return "US$ "+nf(v,2);}
function usd0(v){return "US$ "+nf(Math.round(v),0);}
function toUsd(v){var s=state();return s.has?v*s.rate:null;}
function approx(v){var u=toUsd(v);return u==null?"≈ sem taxa do dia":"≈ "+usd(u);}
function rateDisp(){var s=state();return s.has?s.rate.toFixed(4):"—";}
function rateLine(){var s=state();return s.has?("1 ¥ ≈ US$ "+s.rate.toFixed(4)):"sem taxa do dia";}
function lockLine(){var s=state();return s.has?("1 ¥ = US$ "+s.rate.toFixed(4)+" · "+s.date):"fechado sem taxa travada";}
function stamp(quoted){
  var s=state();
  return "cotado "+quoted+(s.has?(" · taxa mid-market "+s.date+": 1 ¥ ≈ US$ "+s.rate.toFixed(4)):" · sem taxa do dia");
}
/* par de moeda: ¥ grande + US$ menor em cinza */
function pair(v,size,mod){
  return '<span class="mval mval--'+(size||"md")+(mod?" "+mod:"")+'"><b class="mval__c">'+cny(v)+'</b>'
    +'<span class="mval__u">'+approx(v)+'</span></span>';
}
/* par de moeda EM PÉ DE IGUALDADE — o mesmo valor nas duas moedas, no mesmo corpo.
   opt: {rate} taxa a usar (a TRAVADA do lote, quando existe — não a de hoje);
        {est}  o valor ainda pode mudar ⇒ um único ≈ na frente do par, não um por moeda;
        {mod}  modificador de classe (mvd--stack, mvd--due…).
   Sem taxa não inventa número: o lado do dólar diz "sem taxa". */
/* valor ausente ou não-numérico imprime TRAÇO, nunca "NaN": um par de moeda é afirmação sobre
   dinheiro, e "¥ NaN" afirma com a mesma confiança de um número certo. */
function nodata(size,mod){
  return '<span class="mvd mvd--'+(size||"md")+(mod?" "+mod:"")+'"><b class="mvd__a">—</b></span>';
}
function dual(v,size,opt){
  opt=opt||{};
  if(v==null||!isFinite(v))return nodata(size,opt.mod);
  var r=opt.rate!=null?opt.rate:(state().has?state().rate:null);
  var u=r?v*r:null;
  /* o ≈ vive DENTRO do primeiro valor, não como irmão dele: empilhado (herói, célula estreita) o
     irmão virava uma linha própria do flex, e um til flutuando acima do número lê como erro de
     digitação. Dentro, ele viaja com a moeda em qualquer direção do layout. */
  return '<span class="mvd mvd--'+(size||"md")+(opt.mod?" "+opt.mod:"")+'">'
    +'<b class="mvd__a">'+(opt.est?'<i class="mvd__e">\u2248</i>':'')+cny(v)+'</b><i class="mvd__x">=</i>'
    +'<b class="mvd__b">'+(u==null?"sem taxa":usd(u))+'</b></span>';
}
/* idem, partindo do DÓLAR — é a moeda nativa do pagamento do comprador ao WhatTheChip.
   Converter de volta a ¥ pela taxa travada mantém as duas colunas conciliáveis com o resultado. */
function dualU(v,size,opt){
  opt=opt||{};
  if(v==null||!isFinite(v))return nodata(size,opt.mod);
  var r=opt.rate!=null?opt.rate:(state().has?state().rate:null);
  var c=r?v/r:null;
  return '<span class="mvd mvd--'+(size||"md")+(opt.mod?" "+opt.mod:"")+'">'
    +'<b class="mvd__a">'+(opt.est?'<i class="mvd__e">\u2248</i>':'')+(c==null?"sem taxa":cny(c))+'</b><i class="mvd__x">=</i>'
    +'<b class="mvd__b">'+usd(v)+'</b></span>';
}
/* lote fechado antes do câmbio travado: só US$, congelado */
function frozen(v,size){
  return '<span class="mval mval--'+(size||"md")+' mval--froz"><b class="mval__c">'+usd0(v)+'</b>'
    +'<span class="mval__u">(congelado)</span></span>';
}

/* ---------- rastreio: transportadoras com página conhecida ---------- */
/* mora aqui e não em um dos dois lados do balcão porque as duas fichas mostram o mesmo código.
   Fora desta lista o código fica em texto puro, copiável: melhor sem link do que com link quebrado. */
var TRACK={
  "DHL":"https://www.dhl.com/br-pt/home/tracking.html?tracking-id=",
  "FedEx":"https://www.fedex.com/fedextrack/?trknbr=",
  "UPS":"https://www.ups.com/track?tracknum=",
  "SF Express":"https://www.sf-express.com/we/ow/chn/en/waybill/list/",
  "EMS":"https://www.ems.post/en/global-network/tracking?id=",
  "Correios":"https://rastreamento.correios.com.br/app/index.php?objetos="
};
function trackUrl(carrier,track){
  var u=TRACK[carrier];
  return u&&track?u+String(track).replace(/\s+/g,""):null;
}

/* ---------- selo de origem do lote ---------- */
var ICO={
  phone:'<svg viewBox="0 0 24 24"><rect x="7" y="2.5" width="10" height="19"/><path d="M10.5 18.6h3"/></svg>',
  pcb:'<svg viewBox="0 0 24 24"><rect x="3.5" y="3.5" width="17" height="17"/><rect x="9" y="9" width="6" height="6"/><path d="M9 3.5v2M15 3.5v2M9 18.5v2M15 18.5v2M3.5 9h2M3.5 15h2M18.5 9h2M18.5 15h2"/></svg>'
};
var ONAME={phone:"Celular",pcb:"PCB"};
function origin(k,mod){
  k=(k==="phone"||k==="pcb")?k:"pcb";
  return '<span class="otag otag--'+(mod==="ghost"?"ghost":k)+(mod==="sm"?" otag--sm":"")+'">'+ICO[k]+ONAME[k]+'</span>';
}

/* ---------- nós vivos: [data-fx-cny] / [data-fx-usd] ---------- */
function paintAll(root){
  (root||document).querySelectorAll("[data-fx-cny]").forEach(function(el){
    var v=parseFloat(el.getAttribute("data-fx-cny"));if(isNaN(v))return;
    if(el.hasAttribute("data-fx-frozen")){el.innerHTML=frozen(v*(state().rate||MARKET),el.getAttribute("data-fx-size"));return;}
    el.innerHTML=pair(v,el.getAttribute("data-fx-size"),el.getAttribute("data-fx-mod"));
  });
  (root||document).querySelectorAll("[data-fx-rate]").forEach(function(el){el.textContent=rateLine();});
  (root||document).querySelectorAll("[data-fx-lock]").forEach(function(el){el.textContent=lockLine();});
}

/* ---------- widget do cabeçalho ---------- */
var W=null;
/* quem pode ver a taxa no cabeçalho: admin da empresa + plataforma. Sem access.js, esconde. */
function canSeeRate(){
  try{var a=window.WTCAccess&&window.WTCAccess.access();return !!(a&&(a.can_see_price||a.superuser));}catch(e){return false;}
}
function mount(){
  var shell=document.querySelector(".shell");if(!shell||document.querySelector("[data-fx-widget]"))return;
  if(!canSeeRate())return;
  W=document.createElement("button");
  W.type="button";W.setAttribute("data-fx-widget","");W.className="fx";
  var anchor=shell.querySelector(".shell__spacer");
  if(anchor&&anchor.nextSibling)shell.insertBefore(W,anchor.nextSibling);else shell.appendChild(W);
  W.addEventListener("click",function(){setState(ORDER[(ORDER.indexOf(key())+1)%ORDER.length]);});
  render();
}
function render(){
  if(!W)return;
  var s=state();
  W.className="fx"+(s.is_fallback?" fx--fallback":"")+(s.has?"":" fx--none");
  W.title="PROTÓTIPO · "+LABEL[s.key]+" — clique para ver os outros estados do câmbio";
  var warn='<span class="fx__ic"><svg viewBox="0 0 24 24" stroke-linecap="round"><path d="M12 3.5L21.5 20h-19z"/><path d="M12 10v4M12 17h.01"/></svg></span>';
  W.innerHTML=(s.has?(s.is_fallback?warn:"")
      +'<span class="fx__t"><span class="fx__r">1 ¥ ≈ US$ '+s.rate.toFixed(4)+'</span>'
      +'<span class="fx__s">'+(s.is_market?(s.is_fallback?"defasada · última de "+s.date:"mid-market "+s.date):"taxa de contrato")+'</span></span>'
    :warn+'<span class="fx__t"><span class="fx__r">sem taxa do dia</span><span class="fx__s">rode fetch_fx_rate</span></span>')
    +'<span class="fx__live"></span>';
}

/* ---------- auto-refresh: polling de 60s + evento est:added (HX-Trigger) ---------- */
function fire(why){document.dispatchEvent(new CustomEvent("wtc:fx",{detail:{why:why,state:state()}}));}
function tick(why){
  paintAll();
  if(W){W.classList.add("is-fresh");setTimeout(function(){W.classList.remove("is-fresh");},1600);}
  fire(why);
}
function boot(){mount();paintAll();
  setInterval(function(){tick("poll");},60000);
  document.addEventListener("est:added",function(){tick("est:added");});
}

window.WTCFX={
  state:state,set:setState,order:ORDER,
  cny:cny,usd:usd,usd0:usd0,toUsd:toUsd,approx:approx,
  rate:function(){return state().rate;},rateDisp:rateDisp,rateLine:rateLine,lockLine:lockLine,stamp:stamp,
  pair:pair,dual:dual,dualU:dualU,frozen:frozen,origin:origin,originName:function(k){return ONAME[k]||"PCB";},
  TRACK:TRACK,trackUrl:trackUrl,
  paint:paintAll,refresh:tick,
  onChange:function(fn){document.addEventListener("wtc:fx",fn);}
};
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();
