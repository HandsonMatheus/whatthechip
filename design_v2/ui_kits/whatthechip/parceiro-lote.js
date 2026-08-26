/* WhatTheChip — FICHA DO LOTE. Uma única UI para todas as etapas da compra.
   A folha do registro (identidade, indicadores, campos) e as abas nunca mudam de forma:
   o que muda é o que está aceso. Campos do resultado acendem quando a caixa chega;
   os do pagamento acendem quando o resultado fecha. A ação da vez fica sempre no
   mesmo lugar, no canto direito da barra de ação.

   O comprador paga o WhatTheChip, não o vendedor — e paga em US$, pela taxa TRAVADA do lote.
   O resultado é fechado em ¥ (a tabela dele é em ¥). As duas moedas aparecem no mesmo corpo
   (.mvd): ele fecha em uma e paga na outra, e nenhuma das duas é nota de rodapé. */
(function(){
"use strict";
var $=function(i){return document.getElementById(i);},B=window.WTCBuys,FX=window.WTCFX;
var n=(location.search.match(/[?&]l=(\d+)/)||[])[1];
var b=B.get(n)||B.all().filter(function(x){return x.st==="received";})[0]||B.all()[0];
var res=(b.res||b.lines.map(function(l){return l.qty;})).slice();
var tab=null,pfile=null;
var tT;function say(m){$("toast-txt").textContent=m;$("toast").classList.add("is-on");clearTimeout(tT);tT=setTimeout(function(){$("toast").classList.remove("is-on");},3000);}
function fmt(v){return Number(v).toLocaleString("pt-BR");}
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
/* identificador longo em célula estreita: corta no MEIO, nunca no fim — a cauda é justamente o que
   se confere, contra a carteira ou contra o extrato da blockchain. */
function midv(v,a,z){v=String(v==null?"":v);return v.length<=a+z+1?v:v.slice(0,a)+"\u2026"+v.slice(-z);}
var MIX=["var(--blue-60)","var(--ink-80)","var(--green-50)","var(--amber-40)","var(--blue-40)","var(--ink-40)"];
var rate=function(){return b.lock||FX.rate()||0;};
var edit=function(){return b.st==="received";};
var showRes=function(){return b.st!=="transit";};
var payable=function(){return b.st==="settled"||b.st==="paid";};
var TODAY=B.TODAY;
var CHK='<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
var I_COPY='<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11"/><path d="M5 15V4h11"/></svg>';
var I_WARN='<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5L22 20H2z"/><path d="M12 10v4M12 17h.01"/></svg>';
var I_DOC='<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7v18h10V6z"/><path d="M14 3v3h3"/></svg>';
var I_PAY='<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 7.5h17v11h-17z"/><path d="M3.5 11h17M6.5 15h4"/></svg>';
var I_TRK='<svg viewBox="0 0 24 24" stroke-linecap="round"><rect x="3" y="7" width="13" height="10"/><path d="M16 10h3.5l1.5 3v4h-5"/><circle cx="7" cy="18.5" r="1.6"/><circle cx="17.5" cy="18.5" r="1.6"/></svg>';
function copyTxt(t,m){try{navigator.clipboard.writeText(t);}catch(e){}say(m);}
function okUn(){return res.reduce(function(a,v){return a+(v||0);},0);}
function okCny(){return b.lines.reduce(function(a,l,i){return a+(res[i]||0)*l.unit;},0);}

/* ---------- cabeçalho do registro ---------- */
/* mesma convenção da ficha da venda, do outro lado do balcão: utilitários, identidade + trilho +
   ação na MESMA linha, descrição, heróis. Sem etiqueta de estado na identidade — o trilho ao lado
   diz a mesma coisa com mais precisão (qual etapa, desde quando), e duas afirmações a 40px uma da
   outra é eco. */
function statusbar(){
  $("pbar").innerHTML='<span class="rhead__code">'+B.code(b)+'</span>'+FX.origin(b.origin);
  $("pdesc").innerHTML='de <b>'+esc(b.seller)+'</b> · '+esc(b.city)+' · '+esc(b.country);
  steps();
}
/* trilho de etapas: a etapa acesa é a última ALCANÇADA, não a próxima a fazer. O comprador não tem
   "a despachar" (é ação do vendedor), então o trilho tem cinco células, não seis. */
function steps(){
  var at=b.st==="paid"?5:b.st==="settled"?4:b.st==="received"?2:1;
  var ps=b.pays||[],last=ps[ps.length-1];
  var payv=b.st==="paid"?(last?last.d:"quitado"):b.st==="settled"?(ps.length?"parcial":"pendente"):"—";
  var L=[["Fechado",b.closed],["Enviado",b.ship],["Recebido",b.got||"prev. "+b.eta],["Resultado",b.done||"pendente"],["Pagamento",payv]];
  $("stat").innerHTML='<div class="stat">'+L.map(function(x,i){
    var k=i<at?"is-done":i===at?"is-now":"is-next";
    return '<span class="stat__s '+k+'" title="'+esc(x[1]?x[0]+" · "+x[1]:x[0])+'">'
      +(i<at?CHK:'<i></i>')+x[0]+(i===at&&x[1]?'<small>'+esc(x[1])+'</small>':'')+'</span>';
  }).join("")+'</div>';
}
function actions(){
  var btn;
  if(b.st==="transit")btn='<button class="btn btn--pri btn--sm" id="go" type="button">Marcar como recebido'+CHK+'</button>';
  else if(edit())btn='<button class="btn btn--pri btn--sm" id="go" type="button">Fechar resultado'+CHK+'</button>';
  else if(b.st==="settled")btn='<button class="btn btn--pri btn--sm" id="go" type="button">Registrar pagamento'+I_PAY+'</button>';
  else btn='';
  $("act").innerHTML=btn;
  $("act").style.display=btn?"":"none";
  if($("go"))$("go").onclick=advance;
}
function hint(){}
function advance(){
  if(b.st==="transit"){openGot();}
  else if(edit()){openDone();}
  else if(b.st==="settled"){openPay();}
}

/* ---------- confirmar recebimento: abre o resultado e trava o lote, então pede confirmação ---------- */
function openGot(){
  var un=B.units(b),nt=B.types(b);
  $("got-b").innerHTML='<div class="msum">'
    +'<div class="msum__r"><span>Lote</span><b>'+B.code(b)+'</b></div>'
    +'<div class="msum__r"><span>Vendedor</span><b>'+esc(b.seller)+'</b></div>'
    +'<div class="msum__r"><span>Transportadora</span><b>'+esc(b.carrier)+'</b></div>'
    +'<div class="msum__r"><span>Rastreio</span><b>'+esc(b.track)+'</b></div>'
    +'<div class="msum__r"><span>Declarado</span><b>'+fmt(un)+' un. · '+nt+' tipos</b></div>'
    +'<div class="msum__r rest"><span>Data do recebimento</span><b>'+TODAY+'/26</b></div></div>'
    +'<div class="gnote">'+I_WARN+'<span>Confirmar a chegada abre a aba <b>Resultado</b> para você lançar o que recusou, capacidade por capacidade. A partir daqui o vendedor não pode mais alterar o conteúdo do lote.</span></div>';
  $("got-scrim").classList.add("is-on");
  setTimeout(function(){$("got-ok").focus();},60);
}
function closeGot(){$("got-scrim").classList.remove("is-on");}

/* ---------- fechar resultado: número final da compra, então mostra o que será gravado ---------- */
function openDone(){
  var un=B.units(b),c=B.cny(b),oku=okUn(),okc=okCny(),rej=un-oku,d=okc-c;
  var bad=B.byBrand(b).map(function(g){
    var r=g.qty-g.rows.reduce(function(a,x){return a+(res[x.i]||0);},0);
    return r?{t:g.mk,r:r}:null;
  }).filter(Boolean);
  $("done-b").innerHTML='<div class="msum">'
    +'<div class="msum__r"><span>Lote</span><b>'+B.code(b)+'</b></div>'
    +'<div class="msum__r"><span>Enviados</span><b>'+fmt(un)+' un.</b></div>'
    +'<div class="msum__r"><span>Recusados</span><b class="'+(rej?"neg":"")+'">'+(rej?"−"+fmt(rej)+" un.":"nenhum")+'</b></div>'
    +'<div class="msum__r"><span>Aprovados</span><b>'+fmt(oku)+' un.</b></div>'
    +'<div class="msum__r rest"><span>Resultado</span><b>'+FX.cny(okc)+'</b></div></div>'
    +'<div class="dlt"><span>Esperado '+FX.cny(c)+'</span><b class="'+(d?"neg":"ok")+'">'+(d?"acerto de −"+FX.cny(Math.abs(d)):"sem acerto")+'</b></div>'
    +(bad.length?'<div class="blist"><div class="blist__l">Recusas por marca</div>'
        +bad.map(function(x){return '<div class="blist__r"><span>'+esc(x.t)+'</span><b>−'+fmt(x.r)+'</b></div>';}).join("")+'</div>':'')
    +'<div class="fld"><div class="fld__l">Observação<em>opcional</em></div>'
      +'<textarea class="nts__ta" id="dnote" rows="2" placeholder="Ex.: recusas concentradas em DDR3 2GB — pinos oxidados, provável armazenagem úmida."></textarea>'
      +'<div class="nts__f"><span class="nts__h">'+I_DOC+'Fica registrada com data e autor, e sai na folha do resultado que vai ao vendedor.</span></div></div>'
    +'<div class="gnote">'+I_WARN+'<span>'+(rej
        ?'O acerto de <b>'+FX.cny(Math.abs(d))+'</b> será lançado contra o vendedor e o pagamento passa a correr sobre o resultado, não sobre o valor declarado.'
        :'Nenhuma recusa lançada — o lote inteiro será aprovado pelo valor declarado.')
      +' Depois de fechar, os números não podem mais ser alterados.</span></div>';
  $("done-scrim").classList.add("is-on");
  setTimeout(function(){$("done-ok").focus();},60);
}
function closeDone(){$("done-scrim").classList.remove("is-on");}

/* ---------- heróis: os três números que respondem "quanto essa caixa me custa" ---------- */
/* Valor do lote é sempre real; Resultado e Saldo só existem depois do recebimento — antes deles a
   célula mostra o traço e diz o que falta, em vez de fingir um número. */
/* O PAR QUE MANDA na tela é ESPERADO × FINAL, e a diferença entre eles é explícita.
   Esperado é imutável: é o preço fechado com o cliente, o número que ele tinha na mão quando a
   caixa saiu. Final se move enquanto o comprador digita e congela na fatura. Um número só,
   mudando, apagaria a referência — e é contra a referência que se discute uma recusa. */
function sheetHd(){
  var c=B.cny(b),due=okCny(),rest=B.restUsd(b),un=B.units(b),oku=okUn();
  var dif=due-c,R={rate:rate()};
  function hero(l,v,d,cls){
    return '<div class="rmx rmx--hero '+(cls||"")+'"><div class="rmx__l">'+l+'</div>'
      +'<div class="rmx__v">'+v+'</div>'
      +'<div class="rmx__d">'+d+'</div></div>';
  }
  var dash='<span class="m">\u2014</span>';
  $("rmx").innerHTML=
     hero("Resultado esperado",FX.dual(c,"kpi",R),
        fmt(un)+" un. · fechado em "+b.closed,"rmx--est")
    +hero("Resultado final",showRes()?FX.dual(due,"kpi",R):dash,
        showRes()?(dif?'<b class="dif dif--neg">−'+FX.cny(Math.abs(dif))+'</b> contra o esperado'
                      :'<b class="dif dif--ok">sem diferença</b> · lote inteiro aprovado')
                 :"depois do recebimento",
        showRes()?"rmx--res":"rmx--off")
    +hero(payable()&&!rest?"Quitado":"Saldo a pagar",
        payable()?FX.dualU(rest,"kpi",{rate:rate(),mod:rest?"mvd--due":"mvd--ok"}):dash,
        payable()?(rest?"pago "+FX.usd(B.paidUsd(b)):"nada em aberto"):"depois do resultado",
        payable()?(rest?"rmx--due":"rmx--ok"):"rmx--off");
}

/* ---------- etapas: as quatro caixas que dizem o que cada etapa produziu ---------- */
/* mesma faixa de grupos da ficha da venda — o trilho acima é o RESUMO (onde estou), estas caixas
   são o DETALHE. O estado de cada uma vem do que ela PRODUZIU, nunca de um índice. */
function rgrp(){
  function fld(l,v,c){return '<div class="fld2"><span>'+l+'</span><b class="'+(c||"")+'">'+v+'</b></div>';}
  function grp(l,k,when,rows,extra){
    return '<div class="rgrp rgrp--'+k+'">'
      +'<div class="rgrp__h"><span class="rgrp__i">'+(k==="done"?CHK:'')+'</span>'
        +'<span class="rgrp__n">'+l+'</span><span class="rgrp__w">'+esc(when)+'</span></div>'
      +'<div class="rgrp__b">'+rows+(extra||"")+'</div></div>';
  }
  function why(t){return '<p class="rgrp__why">'+t+'</p>';}
  function xbtn(id,ico,t,full){return '<button class="rgrp__x" id="'+id+'" type="button" title="'+esc(full||t)+'">'+ico+'<span>'+esc(t)+'</span></button>';}
  /* transportadora conhecida ⇒ o código é link para o rastreio dela; desconhecida fica botão de
     copiar. Melhor sem link do que com link quebrado. */
  function xlink(id,ico,t,full,href){return '<a class="rgrp__x" id="'+id+'" href="'+esc(href)+'" target="_blank" rel="noopener" title="'+esc(full||t)+'">'+ico+'<span>'+esc(t)+'</span></a>';}
  /* identificador longo em célula estreita: corta no MEIO, nunca no fim — a cauda é justamente o
     que se confere contra a carteira. Mesma convenção da ficha da venda. */
  function mid(v,a,z){return v.length<=a+z+1?v:v.slice(0,a)+"\u2026"+v.slice(-z);}
  var un=B.units(b),c=B.cny(b),got=!!b.got;
  var oku=okUn(),okc=okCny(),d=okc-c;
  var ps=b.pays||[],last=ps[ps.length-1],pd=B.paidUsd(b),rest=B.restUsd(b),W=B.WALLET;
  var turl=B.trackUrl(b);
  var kGot=got?"done":"now";
  var kRes=b.done?"done":(got?"now":"next");
  var kPay=payable()?(rest<=0&&pd>0?"done":"now"):"next";
  $("rgrp").innerHTML=
    grp("Lote","done",b.closed,
      fld("Ordem",B.soCode(b),"m")
      +fld("Origem",b.origin==="pcb"?"Placa (PCB)":"Celular")
      +fld("Volume",fmt(un)+" un.","m")
      +fld("Conteúdo",B.types(b)+" tipos · "+b.lines.length+" linhas"))
    +grp("Despacho",kGot,got?b.got:b.ship,
      fld("Transportadora",esc(b.carrier))
      +fld("Enviado",b.ship,"m")
      +fld("Recebido",b.got||"prev. "+b.eta,got?"m":"m off")
      +fld("Câmbio","US$ "+b.lock.toFixed(4),"m"),
      turl?xlink("trk",I_TRK,mid(b.track,10,6),b.carrier+" · "+b.track+" · abrir rastreio",turl)
          :xbtn("trk",I_TRK,mid(b.track,10,6),b.carrier+" · "+b.track))
    +grp("Resultado",kRes,b.done||(got?"em curso":"—"),
      fld("Fechado em",b.done||(edit()?"em aberto":"—"),b.done?"m":"m off")
      +fld("Aprovados",showRes()?fmt(oku)+" / "+fmt(un):"—",showRes()?"m":"m off")
      +fld("Recusados",showRes()?(un-oku?"−"+fmt(un-oku):"0"):"—",showRes()?(un-oku?"m bad":"m"):"m off")
      +fld("Acerto",showRes()?(d?(d<0?"−":"+")+FX.cny(Math.abs(d)):"sem acerto"):"—",showRes()?(d?"m bad":"m good"):"m off"),
      showRes()?"":why("Acende quando a caixa for marcada como recebida — o resultado é lançado capacidade por capacidade."))
    +grp("Pagamento",kPay,last?last.d:(payable()?"a pagar":"—"),
      fld("Resultado",showRes()?FX.cny(okc):"—",showRes()?"m":"m off")
      +fld("Pago",payable()?FX.usd(pd):"—",payable()?"m good":"m off")
      +fld("Saldo",payable()?FX.usd(rest):"—",payable()?(rest?"m due":"m good"):"m off")
      +fld("Registros",payable()?String(ps.length):"—",payable()?"m":"m off"),
      payable()?xbtn("wcopy",I_COPY,mid(W.addr,9,7),W.owner+" · "+W.net+" · "+W.addr)
               :why("A carteira do WhatTheChip aparece aqui quando o resultado fechar."));
  if($("trk")&&!turl)$("trk").onclick=function(){copyTxt(b.track,"Rastreio "+b.carrier+" copiado: "+b.track);};
  if($("wcopy"))$("wcopy").onclick=function(){copyTxt(W.addr,"Endereço da carteira copiado.");};
}

/* ---------- abas ---------- */
/* ícones das abas: um desenho por conteúdo — resultado, composição, peças, dinheiro */
var TIC={
  lines:'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h9M4 12h9M4 19h9"/><path d="M16.5 6.5l1.8 1.8 3.2-3.6M16.5 13.5l1.8 1.8 3.2-3.6"/></svg>',
  chips:'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><rect x="7" y="7" width="10" height="10"/><path d="M10 3.5V7M14 3.5V7M10 17v3.5M14 17v3.5M3.5 10H7M3.5 14H7M17 10h3.5M17 14h3.5"/></svg>',
  pays:'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 7.5h17v11h-17z"/><path d="M3.5 11h17M6.5 15h4"/></svg>',
  notes:'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3.5h14v17H5z"/><path d="M8.5 8h7M8.5 12h7M8.5 16h4"/></svg>',
  cats:'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 6.5h7v7h-7zM13.5 6.5h7v7h-7zM3.5 16.5h7v4h-7zM13.5 16.5h7v4h-7z"/></svg>'
};
function usedBoxes(){
  var u={},n=0;
  b.lines.forEach(function(l){if(!u[l.box]){u[l.box]=0;n++;}u[l.box]+=l.qty;});
  return {map:u,n:n};
}
var TABS=[["lines","Resultado",function(){return b.lines.length;},function(){return true;}],
          ["chips","Chips",function(){return B.pns(b).length;},function(){return true;}],
          ["cats","Categorias",function(){return usedBoxes().n;},function(){return true;}],
          ["pays","Pagamentos",function(){return (b.pays||[]).length;},payable],
          ["notes","Observações",function(){return (b.notes||[]).length;},function(){return true;}]];
function defTab(){return "lines";}
function nb(){
  var avail=TABS.filter(function(t){return t[3]();}).map(function(t){return t[0];});
  if(!tab||avail.indexOf(tab)<0)tab=avail.indexOf(defTab())>=0?defTab():avail[0];
  $("nb").innerHTML=TABS.map(function(t){
    var on=t[3]();
    return '<button type="button" data-t="'+t[0]+'"'+(t[0]===tab?' class="on"':'')+(on?'':' disabled title="disponível quando o resultado fechar"')+'>'
      +TIC[t[0]]+t[1]+'<em>'+(on?t[2]():"—")+'</em></button>';
  }).join("")
  +(tab==="lines"||tab==="chips"?'<span class="nb__tool"><input class="flt" id="flt" type="text" placeholder="'+(tab==="chips"?"Filtrar PN, fabricante ou C-\u2026":"Filtrar marca, tipo, capacidade ou C-\u2026")+'" autocomplete="off" /></span>':'')
  +'<span class="nb__sp"></span>'
  +'<span class="nb__tool">'
    +'<button class="xbtn" id="pr" type="button">'
      +'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M7 9V3.5h10V9"/><path d="M4 9h16v7h-3M7 16H4V9"/><path d="M7 14h10v6.5H7z"/></svg>Imprimir resultado</button>'
    +'<button class="xbtn" id="xp" type="button">'
    +'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5v11M8 11l4 4 4-4"/><path d="M4 16v4.5h16V16"/></svg>Exportar</button></span>';
  Array.prototype.forEach.call($("nb").querySelectorAll("[data-t]"),function(el){
    el.onclick=function(){tab=el.getAttribute("data-t");nb();body();};
  });
  $("xp").onclick=xport;
  $("pr").onclick=printDoc;
  if($("flt"))$("flt").oninput=filter;
}
/* conteúdo da barra viva, num lugar só: ela é montada no PRIMEIRO render e reescrita a cada
   tecla. Antes só o live() a preenchia, e live() só roda no input — o comprador abria a aba e via
   uma faixa preta vazia grudada no rodapé até tocar o primeiro campo. */
function confliveHtml(){
  var okc=okCny(),dif=okc-B.cny(b),rj=B.units(b)-okUn();
  return '<span class="conflive__l">Resultado final</span>'
    +'<b class="conflive__v">'+FX.cny(okc)+'</b>'
    +'<span class="conflive__d'+(dif?" is-dif":"")+'">'
      +(dif?"−"+FX.cny(Math.abs(dif))+" \u00b7 "+fmt(rj)+" recusadas":"sem recusa")+'</span>';
}
function filterOn(){return $("flt")&&$("flt").value.trim();}
/* A FOLHA DO RESULTADO — o documento que o comprador gera e o CLIENTE recebe. É por isso que ela
   não é a tela impressa: três coisas que a tela mostra não podem estar aqui.

     1. PAGAMENTOS. São a perna comprador → WhatTheChip, e o cliente não vê nem que ela existe.
        Ficaram só na aba e no CSV, que são internos do comprador.
     2. NOME DO COMPRADOR. Some da autoria das observações: no papel elas são da "Conferência".
        O cliente sabe que alguém conferiu; não pode saber quem comprou.
     3. LINGUAGEM DE FATURA. O selo de estado da tela diz FATURADO/PARCIAL — estado de cobrança.
        Aqui o estado é do DOCUMENTO: em conferência ou conferido.

   E o que a folha tem de ter, e a tela não tinha: a caixa ESPERADO × FINAL × DIFERENÇA, que é o
   argumento inteiro do documento em três números. */
function buildPrint(){
  var ty=B.byBrand(b),un=B.units(b),c=B.cny(b),oku=okUn(),okc=okCny(),rej=un-oku,d=okc-c;
  var ns=b.notes||[];
  function row(l,v){return '<div class="pr__r"><span>'+l+'</span><b>'+v+'</b></div>';}
  var lines=ty.map(function(g){
    var gok=g.rows.reduce(function(a,r){return a+(res[r.i]||0);},0);
    return '<tr class="pr__g"><td colspan="3">'+esc(g.mk)+'</td><td class="n">'+fmt(g.qty)+'</td><td></td>'
        +'<td class="n">'+FX.cny(g.cny)+'</td>'
        +(showRes()?'<td class="n">'+(g.qty-gok?"−"+fmt(g.qty-gok):"0")+'</td><td class="n">'+fmt(gok)+'</td>'
          +'<td class="n">'+FX.cny(g.rows.reduce(function(a,r){return a+(res[r.i]||0)*r.unit;},0))+'</td>':'')+'</tr>'
      +g.rows.map(function(r){
        var ok=res[r.i],rj=r.qty-ok;
        return '<tr><td>'+esc(r.t)+'</td><td>'+esc(r.cap)+'</td><td>'+esc(r.box)+'</td><td class="n">'+fmt(r.qty)+'</td>'
          +'<td class="n">'+FX.cny(r.unit)+'</td><td class="n">'+FX.cny(r.qty*r.unit)+'</td>'
          +(showRes()?'<td class="n">'+(rj?"−"+fmt(rj):"0")+'</td><td class="n">'+fmt(ok)+'</td>'
            +'<td class="n">'+FX.cny(ok*r.unit)+'</td>':'')+'</tr>';
      }).join("");
  }).join("");
  var prt=$("prt");
  /* A FOLHA TEM DE SER FILHA DIRETA DO BODY. A regra de impressão esconde tudo com
     `body>*{display:none}` e reabre só `.prt` — mas o viewport.js do protótipo embrulha a página
     em dois divs, então .prt virou neta do body e o !important dela não salvava um descendente de
     ancestral escondido: os três PDFs saíam EM BRANCO. Reancorar aqui, e não na folha de estilo,
     porque CSS não seleciona ancestral — e reancorar a cada montagem, porque o embrulho pode
     voltar quando o enquadramento muda. */
  if(prt.parentElement!==document.body)document.body.appendChild(prt);
  prt.innerHTML='<div class="pr__hd"><div><div class="pr__k">Resultado do lote</div><h1>'+B.code(b)+'</h1>'
      +'<p>'+esc(b.seller)+' · '+esc(b.city)+' · '+esc(b.country)+'</p></div>'
      +'<div class="pr__st">'+(b.done?"CONFERIDO":"EM CONFERÊNCIA")+'<span>emitido em '+TODAY+'/26</span></div></div>'
    +'<div class="pr__cols">'
      +'<div>'+row("Ordem",B.soCode(b))+row("Origem",b.origin==="pcb"?"Placa (PCB)":"Celular")+row("Transportadora",esc(b.carrier))
        +row("Rastreio",esc(b.track))+row("Fechado",b.closed)+row("Recebido",b.got||"—")+'</div>'
      +'<div>'+row("Câmbio travado","1 ¥ = US$ "+b.lock.toFixed(4)+" · "+b.lockD)
        +row("Enviados",fmt(un)+" un.")+row("Recusados",rej?"−"+fmt(rej)+" un.":"nenhum")
        +row("Aprovados",fmt(oku)+" un.")+row("Acerto",d?"−"+FX.cny(Math.abs(d)):"sem acerto")+'</div>'
    +'</div>'
    /* os três números que são o documento. Esperado é a referência (o preço fechado quando a caixa
       saiu), Final é o que a conferência apurou, e a Diferença é a conta entre eles — em célula
       própria AQUI, ao contrário da tela: no papel não há legenda para pendurar, e é a diferença
       que o cliente vai querer discutir. */
    +'<div class="pr__tot"><div><span>Resultado esperado</span><b>'+FX.cny(c)+'</b></div>'
      +'<div class="hi pr--fin"><span>Resultado final</span><b>'+(showRes()?FX.cny(okc):"—")+'</b></div>'
      +'<div class="pr--dif"><span>Diferença</span><b>'
        +(showRes()?(d?"−"+FX.cny(Math.abs(d)):"sem diferença"):"—")+'</b></div></div>'
    +'<h2>Resultado por marca, tipo e capacidade</h2>'
    +'<table class="pr__t"><thead><tr><th>Tipo</th><th>Capacidade</th><th>Caixa WTC</th><th class="n">Enviados</th>'
      +'<th class="n">¥ unit.</th><th class="n">¥ esperado</th>'
      +(showRes()?'<th class="n">Recusados</th><th class="n">Aprovados</th><th class="n">¥ resultado</th>':'')+'</tr></thead>'
      +'<tbody>'+lines+'</tbody>'
      +'<tfoot><tr><td colspan="3">Total</td><td class="n">'+fmt(un)+'</td><td></td><td class="n">'+FX.cny(c)+'</td>'
        +(showRes()?'<td class="n">'+(rej?"−"+fmt(rej):"0")+'</td><td class="n">'+fmt(oku)+'</td><td class="n">'+FX.cny(okc)+'</td>':'')+'</tr></tfoot></table>'
    +(ns.length?'<h2>Observações da conferência</h2>'+ns.map(function(x){
        /* a autoria vira o PAPEL, não a pessoa: o cliente lê "Conferência", nunca o nome de quem
           comprou. Na tela do comprador o nome fica, porque ali ele é o autor e o leitor. */
        return '<div class="pr__n"><div class="pr__nh">Conferência · '+esc(x.d)+'</div><p>'+esc(x.t)+'</p></div>';
      }).join(""):'')
    +'<div class="pr__ft">WhatTheChip · '+B.code(b)+' · '+B.soCode(b)+' · valores em ¥ (RMB) na taxa travada de '+b.lockD
      +' · documento de conferência emitido em '+TODAY+'/26</div>';
}
function printDoc(){buildPrint();window.print();say("Folha do resultado pronta para impressão ou PDF.");}
window.addEventListener("beforeprint",buildPrint);

/* exportar: CSV do que está na aba aberta — o recorte que o comprador está olhando */
function xport(){
  var rows=[],name=tab,q=function(v){v=String(v==null?"":v);return /[";,\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;};
  if(tab==="chips"){
    rows.push(["Part number","Fabricante","Caixa WTC","Identificação","Chips","CNY unit.","CNY total"]);
    B.pns(b).forEach(function(p){rows.push([p.pn,p.make,p.wtc,p.spec,p.qty,p.unit,p.qty*p.unit]);});
  }else if(tab==="notes"){
    rows.push(["Data","Autor","Observação"]);
    (b.notes||[]).forEach(function(x){rows.push([x.d,x.who,x.t]);});
  }else if(tab==="pays"){
    rows.push(["Data","Registro","USD pago","CNY equivalente","Referência","Registrado por","Comprovante"]);
    (b.pays||[]).forEach(function(p,i){rows.push([p.d,p.kind==="full"?(i?"Quitação":"Integral"):"Parcial",
      p.usd,Math.round(p.usd/rate()),p.ref||"",p.by||"",p.file]);});
  }else{
    rows.push(["Marca","Tipo","Capacidade","Caixa WTC","Enviados","CNY unit.","CNY esperado"].concat(showRes()?["Recusados","Aprovados","CNY resultado"]:[]));
    B.byBrand(b).forEach(function(g){
      g.rows.forEach(function(r){
        var ok=res[r.i]||0;
        rows.push([g.mk,r.t,r.cap,r.box,r.qty,r.unit,r.qty*r.unit].concat(showRes()?[r.qty-ok,ok,ok*r.unit]:[]));
      });
    });
  }
  var csv="\ufeff"+rows.map(function(r){return r.map(q).join(";");}).join("\r\n");
  var f=B.code(b).replace(/\//g,"-")+"-"+name+".csv";
  var a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  a.download=f;document.body.appendChild(a);a.click();
  setTimeout(function(){URL.revokeObjectURL(a.href);a.remove();},400);
  say("Exportado · "+f+" · "+(rows.length-1)+" linhas");
}

function body(){
  $("nbb").innerHTML=tab==="lines"?linesTab():tab==="chips"?chipsTab():tab==="cats"?catsTab()
    :tab==="notes"?notesTab():paysTab();
  if(tab==="notes"){
    var ta=$("ntx"),bt=$("nadd");
    var sync=function(){bt.disabled=!ta.value.trim();};
    ta.oninput=sync;sync();
    ta.onkeydown=function(e){if((e.metaKey||e.ctrlKey)&&e.key==="Enter")bt.click();};
    bt.onclick=function(){
      var t=ta.value.trim();if(!t)return;
      B.patch(b.n,{notes:(b.notes||[]).concat([{d:TODAY+"/26",who:"Shenzhen Yuan",t:t}])});
      b=B.get(b.n);nb();body();say("Observação registrada · sai no PDF do resultado.");
    };
    Array.prototype.forEach.call(document.querySelectorAll("[data-nx]"),function(el){
      el.onclick=function(){
        var i=+el.getAttribute("data-nx"),l=(b.notes||[]).slice();l.splice(i,1);
        B.patch(b.n,{notes:l});b=B.get(b.n);nb();body();say("Observação removida.");
      };
    });
  }
  if(tab==="lines"&&edit()){
    var ins=[].slice.call(document.querySelectorAll("[data-rj]"));
    var jump=function(el,d){var j=+el.getAttribute("data-i")+d,t=ins[j];if(t){t.focus();t.select();}};
    ins.forEach(function(el){
      el.addEventListener("focus",function(){el.select();el.closest("tr").classList.add("on");});
      el.addEventListener("blur",function(){
        el.closest("tr").classList.remove("on");
        var i=+el.getAttribute("data-rj"),q=+el.getAttribute("max"),rej=q-(res[i]||0);
        el.value=rej||"";el.classList.remove("bad");live();
      });
      el.addEventListener("keydown",function(e){
        if(e.key==="Enter"||e.key==="ArrowDown"){e.preventDefault();jump(el,1);}
        else if(e.key==="ArrowUp"){e.preventDefault();jump(el,-1);}
      });
      el.addEventListener("input",function(){
        var i=+el.getAttribute("data-rj"),q=+el.getAttribute("max");
        el.value=el.value.replace(/\D/g,"").slice(0,7);
        var rej=parseInt(el.value||"0",10);
        el.classList.toggle("bad",rej>q);
        res[i]=q-Math.min(rej,q);live();
      });
    });
    $("rz").onclick=function(){
      res=b.lines.map(function(l){return l.qty;});
      ins.forEach(function(el){el.value="";el.classList.remove("bad");});
      live();say("Recusas zeradas · lote inteiro aprovado.");
    };
  }
  if(tab==="pays"){
    if($("wcopy2"))$("wcopy2").onclick=function(){copyTxt(B.WALLET.addr,"Endereço da carteira copiado.");};
    Array.prototype.forEach.call(document.querySelectorAll("[data-rf]"),function(el){
      el.onclick=function(){copyTxt(el.getAttribute("data-rf"),"Referência da transação copiada.");};
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-rc]"),function(el){
      el.onclick=function(){say("Comprovante "+(b.pays||[])[+el.getAttribute("data-rc")].file+" · abrindo o arquivo anexado.");};
    });
  }
}

/* aba Observações: o que não cabe em número — avaria na caixa, peso divergente, combinado com o
   vendedor. Tudo o que está aqui é impresso no PDF do resultado, então vale como registro. */
function notesTab(){
  var ns=b.notes||[];
  return '<div class="nts">'
    +'<div class="nts__new">'
      +'<div class="nts__l">Nova observação</div>'
      +'<textarea class="nts__ta" id="ntx" rows="3" placeholder="Ex.: caixa 2 chegou com a fita rompida — fotos enviadas ao vendedor em '+TODAY+'."></textarea>'
      +'<div class="nts__f"><span class="nts__h">'+I_DOC+'Sai impressa no PDF do resultado, com data e autor. <kbd>⌘</kbd>+<kbd>Enter</kbd> para registrar.</span>'
        +'<button class="btn btn--pri" id="nadd" type="button" disabled>Registrar observação'+CHK+'</button></div>'
    +'</div>'
    +(ns.length
      ?'<div class="nts__list">'+ns.map(function(x,i){
          return '<div class="nt"><div class="nt__h"><b>'+esc(x.who)+'</b><span>'+esc(x.d)+'</span>'
            +'<button class="nt__x" type="button" data-nx="'+i+'" aria-label="Remover observação">'
            +'<svg viewBox="0 0 24 24" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>'
            +'<p>'+esc(x.t)+'</p></div>';
        }).join("")+'</div>'
      :'<div class="pempty">Nenhuma observação neste lote. O que você escrever aqui acompanha o PDF do resultado — use para avarias, divergências de peso e combinados com o vendedor.</div>')
  +'</div>';
}

/* aba Categorias: o dicionário da convenção WTC — a caixa física e o código da categoria, com o
   que veio NESTA compra marcado pela quantidade. Quantidade e não um visto: dizer "veio" é menos
   do que dizer quanto veio, e é a quantidade que o comprador confere contra a bancada.
   Leitura apenas — a convenção é da plataforma, não do comprador. */
function catsTab(){
  var C=window.WTCCat,U=usedBoxes(),list=C.all(),seen={};
  list.forEach(function(x){seen[x.box]=1;});
  /* caixa do lote que não está no dicionário entra no fim, marcada: uma caixa desconhecida num
     lote é notícia para a plataforma, não uma linha a menos na tabela. */
  Object.keys(U.map).forEach(function(k){if(!seen[k])list.push(C.get(k));});
  var rows=list.map(function(x){
    var q=U.map[x.box];
    return '<tr'+(q?' class="sel"':'')+'>'
      +'<td class="c">'+esc(x.code)+'</td>'
      +'<td data-label="Caixa WTC"><span class="wtc">'+esc(x.box)+'</span></td>'
      +'<td data-label="Tipo">'+esc(x.type)+(x.unknown?' <span class="miss">fora do dicionário</span>':'')+'</td>'
      /* coluna comum, NÃO .d: "descrição" é a primeira a sair quando falta largura, e nesta tabela
         não falta — são cinco colunas de código curto e sobra espaço. Com .d o dicionário só
         mostrava a explicação acima de 1100px, justamente onde ela é menos necessária. */
      +'<td data-label="O que entra">'+esc(x.desc)+'</td>'
      +'<td class="n" data-label="Nesta compra">'+(q?fmt(q)+' un.':'<span class="none">—</span>')+'</td></tr>';
  }).join("");
  return '<div class="rhint"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>'
      +'<span>Na convenção WTC a <b>letra é o tipo</b> de chip e o <b>número é a categoria</b> — e o número é o mesmo da caixa física, então quem está com a caixa na mão lê o código direto do rótulo.</span></div>'
    +'<div class="dtab__wrap"><div class="dtab__sc"><table class="dtab dtab--static">'
    +'<thead><tr><th>Categoria</th><th>Caixa WTC</th><th>Tipo</th><th>O que entra</th>'
    +'<th class="num">Nesta compra</th></tr></thead><tbody>'+rows+'</tbody></table></div></div>';
}

/* aba Chips: o detalhado de verdade — cada part number do lote, com o fabricante,
   as specs com que foi identificado, a categoria WTC que definiu o preço, quantidade e valor. */
function chipsTab(){
  var list=B.pns(b),un=B.units(b),c=B.cny(b),by={},order=[];
  list.forEach(function(p){if(!by[p.type]){by[p.type]={qty:0,cny:0,rows:[]};order.push(p.type);}
    by[p.type].qty+=p.qty;by[p.type].cny+=p.qty*p.unit;by[p.type].rows.push(p);});
  var head='<tr><th>Part number</th><th>Fabricante</th><th>Caixa WTC</th><th class="d">Identificação</th>'
    +'<th>Chips</th><th>¥ unit.</th><th>¥ total</th></tr>';
  var rows=order.map(function(t,gi){
    var g=by[t];
    return '<tr class="g" data-sec="'+gi+'">'
        +'<td colspan="3"><span class="g__n"><i style="background:'+MIX[gi%MIX.length]+'"></i>'+esc(t)
          +'<em>'+g.rows.length+(g.rows.length===1?' PN':' PNs')+'</em></span></td>'
        +'<td class="d"></td><td class="n">'+fmt(g.qty)+'</td><td class="n"></td><td class="v">'+FX.cny(g.cny)+'</td>'
      +'</tr>'
      +g.rows.map(function(p){
        return '<tr data-row data-g="'+gi+'" data-k="'+esc((p.pn+" "+p.make+" "+p.wtc+" "+p.cap).toLowerCase())+'">'
          +'<td class="c">'+esc(p.pn)+'</td>'
          +'<td>'+esc(p.make)+'</td>'
          +'<td><span class="wtc">'+esc(p.wtc)+'</span></td>'
          +'<td class="d">'+esc(p.spec)+'</td>'
          +'<td class="n">'+fmt(p.qty)+'</td><td class="n">'+FX.cny(p.unit)+'</td>'
          +'<td class="v">'+FX.cny(p.qty*p.unit)+'</td></tr>';
      }).join("");
  }).join("");
  var foot='<tr><td class="lbl" colspan="3">Total · '+list.length+' PNs · '+order.length+' tipos</td>'
    +'<td class="d"></td><td><small>Chips</small>'+fmt(un)+'</td><td></td>'
    +'<td><small>Valor</small>'+FX.cny(c)+'</td></tr>';
  return '<div class="dtab__wrap"><div class="dtab__sc"><table class="dtab dtab--static">'
    +'<thead>'+head+'</thead><tbody id="rtb">'+rows+'</tbody><tfoot>'+foot+'</tfoot></table></div></div>';
}

/* aba Resultado: planilha — uma linha por categoria × capacidade, agrupada por tipo de chip,
   com subtotal em cada faixa de tipo e o total de cada coluna no rodapé fixo.
   O comprador digita SEMPRE o que recusou — a exceção, quase sempre zero — e o aprovado
   se calcula sozinho. Lote perfeito = nenhuma tecla digitada. */
function linesTab(){
  var ty=B.byBrand(b),un=B.units(b),c=B.cny(b),oku=okUn(),okc=okCny();
  /* ¥ unit. é uma TAXA, e taxa cede antes do valor: o que decide a conferência é esperado,
     aprovado e resultado. Sai a 1100px, junto com toda descrição do sistema. */
  var head='<tr><th>Tipo</th><th>Capacidade</th><th>Caixa WTC</th><th>Enviados</th>'
    +'<th class="hide-lg">¥ unit.</th><th>¥ esperado</th>'
    +(showRes()?'<th class="hr">Recusados'+(edit()?'<i class="pen"></i>':'')+'</th><th class="hg">Aprovados</th><th class="hb">¥ resultado</th>':'')+'</tr>';
  var k=0;
  var rows=ty.map(function(g,gi){
    var okg=g.rows.reduce(function(a,r){return a+(res[r.i]||0);},0);
    var rejg=g.qty-okg,okcg=g.rows.reduce(function(a,r){return a+(res[r.i]||0)*r.unit;},0);
    return '<tr class="g" data-sec="'+gi+'">'
        +'<td colspan="3"><span class="g__n"><i style="background:'+MIX[gi%MIX.length]+'"></i>'+esc(g.mk)
          +'<em>'+g.rows.length+(g.rows.length===1?' linha':' linhas')+'</em></span></td>'
        +'<td class="n" data-gq="'+gi+'">'+fmt(g.qty)+'</td><td class="n hide-lg"></td>'
        +'<td class="v">'+FX.cny(g.cny)+'</td>'
        +(showRes()?'<td class="n hr rej '+(rejg?"some":"zero")+'" data-grej="'+gi+'">'+(rejg?"−"+fmt(rejg):"0")+'</td>'
          +'<td class="n hg" data-gok="'+gi+'">'+fmt(okg)+'</td>'
          +'<td class="v hb" data-gval="'+gi+'">'+FX.cny(okcg)+'</td>':'')
      +'</tr>'
      +g.rows.map(function(r){
        var exp=r.qty*r.unit,ok=res[r.i],rej=r.qty-ok;
        return '<tr data-row="'+r.i+'" data-g="'+gi+'" data-k="'+esc((g.mk+" "+r.t+" "+r.cap+" "+r.box).toLowerCase())+'">'
          +'<td class="cap c-t">'+esc(r.t)+'</td><td class="c-cap">'+esc(r.cap)+'</td>'
          +'<td class="c-box"><span class="wtc">'+esc(r.box)+'</span></td>'
          +'<td class="n c-qty"><i class="c-lbl">enviados</i>'+fmt(r.qty)+'</td>'
          +'<td class="n hide-lg c-unit" data-label="¥ unit.">'+FX.cny(r.unit)+'</td>'
          +'<td class="v c-exp" data-label="¥ esperado">'+FX.cny(exp)+'</td>'
          
          +(showRes()
            ?'<td class="n hr c-rej"><i class="c-lbl c-lbl--rej">Recusados</i>'+(edit()
                ?'<input class="rjin" type="text" inputmode="numeric" value="'+(rej||"")+'" placeholder="0" data-rj="'+r.i+'" data-i="'+(k++)+'" max="'+r.qty+'" aria-label="Recusados '+esc(g.mk)+' '+esc(r.t)+' '+esc(r.cap)+'" />'
                :'<b class="rej '+(rej?"some":"zero")+'" data-rej="'+r.i+'">'+(rej?"−"+fmt(rej):"0")+'</b>')+'</td>'
              +'<td class="n hg c-ok" data-ok="'+r.i+'"><i class="c-lbl">aprovados</i><b>'+fmt(ok)+'</b></td>'
              +'<td class="v hb c-val" data-label="¥ resultado" data-val="'+r.i+'">'+FX.cny(ok*r.unit)+(rej?' <span class="dl2">−'+FX.cny(rej*r.unit)+'</span>':'')+'</td>'
            :'')
        +'</tr>';
      }).join("");
  }).join("");
  var foot='<tr><td class="lbl" colspan="3">Total · '+ty.length+' marcas · '+B.types(b)+' tipos · '+b.lines.length+' linhas</td>'
    +'<td><small>Enviados</small>'+fmt(un)+'</td><td class="hide-lg"></td>'
    +'<td><small>Esperado</small>'+FX.cny(c)+'</td>'
    
    +(showRes()?'<td class="hr" id="t-rej"><small>Recusados</small>'+(un-oku?"−"+fmt(un-oku):"0")+'</td>'
      +'<td class="hg" id="t-ok"><small>Aprovados</small>'+fmt(oku)+'</td>'
      +'<td class="hb" id="t-val"><small>Resultado</small>'+FX.cny(okc)+'</td>':'')+'</tr>';
  return (edit()?'<div class="rhint"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19.5 8.5a2.8 2.8 0 0 0-4-4L4 16z"/></svg>'
      +'<span>Digite só o que <b>recusou</b> — o campo em branco vale zero e o aprovado se calcula sozinho. <kbd>Enter</kbd> desce para a próxima linha.</span>'
      +'<button class="rhint__z" id="rz" type="button">Limpar recusas</button></div>':'')
    /* a classe vai no .dtab__sc, que é o PAI da tabela: no telefone é ele que precisa soltar
       max-height e overflow. Marcar a tabela não solta a caixa de rolagem que a contém. */
    +'<div class="dtab__wrap"><div class="dtab__sc dtab__sc--conf"><table class="dtab dtab--static dtab--conf">'
    +'<thead>'+head+'</thead><tbody id="rtb">'+rows+'</tbody><tfoot>'+foot+'</tfoot></table></div></div>'
    /* BARRA VIVA — só existe no telefone (o CSS a esconde acima de 600px).
       O briefing pede o resultado "no topo da tela" enquanto ele digita. No telefone o topo já
       rolou: os heróis estão a mil pixels de distância e o rodapé de soma está no fim de uma lista
       longa. Então o número que se move acompanha o dedo, colado embaixo. */
    +(edit()?'<div class="conflive" id="conflive">'+confliveHtml()+'</div>':'');
}
function filter(){
  var q=$("flt").value.trim().toLowerCase(),seen={};
  Array.prototype.forEach.call(document.querySelectorAll("#rtb [data-row]"),function(tr){
    var on=!q||tr.getAttribute("data-k").indexOf(q)>=0;
    tr.style.display=on?"":"none";
    if(on)seen[tr.getAttribute("data-g")]=1;
  });
  Array.prototype.forEach.call(document.querySelectorAll("#rtb [data-sec]"),function(tr){
    tr.style.display=(!q||seen[tr.getAttribute("data-sec")])?"":"none";
  });
}

/* aba Pagamentos: carteira, saldo e as parcelas.
   O comprador paga o WhatTheChip em US$. O devido nasce em ¥ (resultado) e vira US$ pela taxa
   travada; por isso todo valor aqui aparece nas duas moedas, no mesmo corpo. */
function paysTab(){
  var W=B.WALLET,due=okCny(),pd=B.paidUsd(b),rest=B.restUsd(b),pct=B.paidPct(b),ps=b.pays||[];
  var R={rate:rate()};
  function refCell(v){
    return v?'<button class="rcpt" type="button" data-rf="'+esc(v)+'" title="'+esc(v)+'">'+midv(v,8,6)+'</button>'
            :'<span class="dim">\u2014</span>';
  }
  var rows=ps.map(function(p,i){
    var lb=p.kind==="full"?(i?"QUITAÇÃO":"INTEGRAL"):"PARCIAL";
    return '<tr><td class="m">'+esc(p.d)+'</td>'
      +'<td><span class="tag '+(p.kind==="full"?"tag--yes":"tag--info")+'"><span class="dot"></span>'+lb+'</span></td>'
      +'<td class="n">'+FX.dualU(p.usd,"xs",{rate:rate(),mod:"mvd--stack"})+'</td>'
      +'<td>'+refCell(p.ref)+'</td>'
      +'<td class="dim">'+esc(p.by||"\u2014")+'</td>'
      +'<td><button class="rcpt" type="button" data-rc="'+i+'">'+I_DOC+esc(p.file)+'</button></td></tr>';
  }).join("");
  var tbl=ps.length
    ?'<table class="ptab"><thead><tr><th>Data</th><th>Registro</th><th class="n">Valor pago</th>'
      +'<th>Referência</th><th>Registrado por</th><th>Comprovante</th></tr></thead>'
      +'<tbody>'+rows+'</tbody>'
      +'<tfoot><tr><td colspan="2">Total pago · '+ps.length+(ps.length===1?' registro':' registros')+'</td>'
      +'<td class="n">'+FX.dualU(pd,"xs",{rate:rate(),mod:"mvd--stack"})+'</td>'
      +'<td colspan="2"></td>'
      +'<td>'+(rest?'<span style="color:var(--amber-70);font-family:var(--mono);font-size:13px">restam '+FX.usd(rest)+'</span>':'<span style="color:var(--green-70)">saldo zerado</span>')+'</td></tr></tfoot></table>'
    :'<div class="pempty">Nenhum pagamento registrado. Envie o valor em US$ para a carteira acima e lance aqui — parcial ou integral, sempre com o comprovante anexado.</div>';
  return '<div class="pay">'
      +'<div class="pay__c pay__c--w">'
        +'<div class="pay__k">Carteira de destino</div>'
        +'<div class="wal"><span class="wal__n">'+esc(W.owner)+'</span><span class="wal__net">'+esc(W.net)+'</span></div>'
        +'<div class="wadr"><code>'+esc(W.addr)+'</code><button id="wcopy2" type="button" aria-label="Copiar endereço da carteira">'+I_COPY+'</button></div>'
        +'<div class="paynote">'+I_WARN+'<span>Você paga o <b>WhatTheChip</b>, nunca o vendedor direto — e todo pagamento desta compra vai para este endereço. Confira os seis primeiros e os seis últimos caracteres antes de enviar: transferência em blockchain não volta. E '+esc(W.memo)+'.</span></div>'
      +'</div>'
      +'<div class="pay__c pay__c--m">'
        +'<div class="pay__k">Saldo desta compra</div>'
        +'<div class="pmet">'
          +'<div class="pmet__r big"><span>Resultado do lote</span>'+FX.dual(due,"sm",R)+'</div>'
          +'<div class="pmet__r done"><span>Já pago</span>'+FX.dualU(pd,"sm",R)+'</div>'
          +'<div class="pmet__r '+(rest?"rest":"done")+'"><span>'+(rest?"Restante":"Saldo")+'</span>'+FX.dualU(rest,"sm",R)+'</div>'
        +'</div>'
        +'<div class="pbar"><i style="width:'+pct+'%"></i></div>'
        +'<div class="pbar__l"><span>'+Math.round(pct)+'% pago</span><span>'+(rest?FX.usd(rest)+' em aberto':FX.usd(pd)+' liquidados')+'</span></div>'
      +'</div>'
    +'</div>'+tbl;
}

/* ---------- edição viva: só o que mudou ---------- */
function live(){
  var un=B.units(b),oku=okUn(),okc=okCny();
  b.lines.forEach(function(l,i){
    var ok=res[i]||0,rej=l.qty-ok;
    var el=document.querySelector('[data-rej="'+i+'"]'),o=document.querySelector('[data-ok="'+i+'"]'),va=document.querySelector('[data-val="'+i+'"]');
    if(el){el.textContent=rej?"−"+fmt(rej):"0";el.className="rej "+(rej?"some":"zero");}
    if(o)o.innerHTML='<i class="c-lbl">aprovados</i><b>'+fmt(ok)+'</b>';
    if(va)va.innerHTML=FX.cny(ok*l.unit)+(rej?' <span class="dl2">−'+FX.cny(rej*l.unit)+'</span>':'');
  });
  B.byBrand(b).forEach(function(g,gi){
    var ok=g.rows.reduce(function(a,r){return a+(res[r.i]||0);},0),rej=g.qty-ok;
    var e=document.querySelector('[data-gok="'+gi+'"]'),r=document.querySelector('[data-grej="'+gi+'"]'),v=document.querySelector('[data-gval="'+gi+'"]');
    if(e)e.textContent=fmt(ok);
    if(r){r.textContent=rej?"−"+fmt(rej):"0";r.className="n hr rej "+(rej?"some":"zero");}
    if(v)v.textContent=FX.cny(g.rows.reduce(function(a,x){return a+(res[x.i]||0)*x.unit;},0));
  });
  if($("t-ok"))$("t-ok").innerHTML='<small>Aprovados</small>'+fmt(oku);
  if($("t-rej")){$("t-rej").innerHTML='<small>Recusados</small>'+((un-oku)?"−"+fmt(un-oku):"0");$("t-rej").className="hr";}
  if($("t-val"))$("t-val").innerHTML='<small>Resultado</small>'+FX.cny(okc);
  var cl=$("conflive");
  if(cl)cl.innerHTML=confliveHtml();
  sheetHd();fields();
}

/* ---------- modal: registrar pagamento (US$ — a moeda em que o comprador paga) ---------- */
/* referência da transferência: no produto vem da blockchain. Aqui é determinística a partir do
   lote e do índice, para o mesmo pagamento não trocar de hash a cada recarga.
   Math.imul e não `x*A`: o produto de dois inteiros de 32 bits estoura 2^53 e o double perde os
   bits BAIXOS — exatamente os que `% 16` lia. Sem isso o hash saía com 62 dos 64 dígitos em zero.
   E lê-se o nibble deslocado (>>>8), não o último: num LCG os bits baixos têm período curto. */
function fakeRef(s){var h="",x=(s*2654435761)>>>0;for(var i=0;i<64;i++){x=(Math.imul(x,1103515245)+12345)>>>0;h+="0123456789abcdef"[(x>>>8)&15];}return h;}
function pnum(){return parseFloat(String($("pv").value||"").replace(/[^\d.]/g,""))||0;}
function pval(){
  var rest=B.restUsd(b),v=pnum(),over=v>rest+0.004,full=v>0&&!over&&v>=rest-0.004;
  $("pv").classList.toggle("bad",over);
  /* o ¥ aqui é EXATO, não ≈: a taxa está travada, então a conversão é aritmética */
  $("pconv").innerHTML=v?('= <b>'+FX.cny(v/rate())+'</b>'):'= ¥ —';
  $("pover").innerHTML=over?'<span class="over">acima do saldo · máx '+FX.usd(rest)+'</span>':'taxa travada <b>'+b.lock.toFixed(4)+'</b>';
  $("pay-ok").disabled=!(v>0&&!over&&pfile);
  $("pay-ok").innerHTML=(full?"Registrar quitação":"Registrar pagamento parcial")+CHK;
}
function pdrop(){
  var d=$("pdrop");
  d.className="drop"+(pfile?" has":"");
  d.innerHTML=(pfile?CHK:'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12.5l-7.8 7.8a4.6 4.6 0 0 1-6.5-6.5l8.3-8.3a3 3 0 0 1 4.3 4.3l-8.2 8.2a1.5 1.5 0 0 1-2.1-2.1l7.6-7.6"/></svg>')
    +'<span class="drop__t"><b>'+(pfile?esc(pfile):'Anexar comprovante')+'</b><i>'+(pfile?'trocar ou remover o arquivo':'PDF, PNG ou JPG até 10 MB — sem comprovante o pagamento não entra')+'</i></span>'
    +(pfile?'<button class="drop__x" type="button" id="pdrop-x" aria-label="Remover comprovante"><svg viewBox="0 0 24 24" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>':'')
    +'<input type="file" id="pfile" accept=".pdf,.png,.jpg,.jpeg" />';
  $("pfile").onchange=function(){var f=this.files&&this.files[0];if(f){pfile=f.name;pdrop();pval();}};
  if($("pdrop-x"))$("pdrop-x").onclick=function(e){e.preventDefault();e.stopPropagation();pfile=null;pdrop();pval();};
}
function openPay(){
  var W=B.WALLET,due=B.dueCny(b),pd=B.paidUsd(b),rest=B.restUsd(b);
  pfile=null;
  $("pay-b").innerHTML='<div class="msum">'
    +'<div class="msum__r"><span>Ordem</span><b>'+B.soCode(b)+'</b></div>'
    +'<div class="msum__r"><span>Resultado do lote</span><b>'+FX.cny(due)+' = '+FX.usd(B.dueUsd(b))+'</b></div>'
    +'<div class="msum__r"><span>Já pago</span><b>'+FX.usd(pd)+'</b></div>'
    +'<div class="msum__r rest"><span>Restante</span><b>'+FX.usd(rest)+'</b></div></div>'
    +'<div class="fld"><div class="fld__l">Carteira do WhatTheChip<em>'+esc(W.net)+'</em></div>'
      +'<div class="wadr"><code>'+esc(W.addr)+'</code><button id="wcopy3" type="button" aria-label="Copiar endereço">'+I_COPY+'</button></div></div>'
    +'<div class="fld"><div class="fld__l">Valor deste pagamento<em class="req">obrigatório</em></div>'
      +'<div class="amt"><span class="amt__cur">US$</span><input class="minput" id="pv" type="text" inputmode="decimal" placeholder="0,00" autocomplete="off" /></div>'
      +'<div class="quick"><button type="button" data-q="0.25">25%</button><button type="button" data-q="0.5">50%</button>'
      +'<button type="button" data-q="1">Restante · '+FX.usd(rest)+'</button></div>'
      +'<div class="conv"><span id="pconv">= ¥ —</span><span id="pover">taxa travada <b>'+b.lock.toFixed(4)+'</b></span></div></div>'
    +'<div class="fld"><div class="fld__l">Comprovante<em class="req">obrigatório</em></div>'
      +'<label class="drop" id="pdrop"></label></div>';
  pdrop();
  $("wcopy3").onclick=function(){copyTxt(W.addr,"Endereço da carteira copiado.");};
  $("pv").oninput=function(){this.value=this.value.replace(/,/g,".").replace(/[^\d.]/g,"").replace(/(\..*)\./g,"$1").slice(0,12);pval();};
  Array.prototype.forEach.call($("pay-b").querySelectorAll("[data-q]"),function(q){
    q.onclick=function(){$("pv").value=Math.round(B.restUsd(b)*parseFloat(q.getAttribute("data-q"))*100)/100;pval();};
  });
  pval();
  $("pay-scrim").classList.add("is-on");
  setTimeout(function(){$("pv").focus();},60);
}
function closePay(){$("pay-scrim").classList.remove("is-on");}
$("got-x").onclick=closeGot;
$("got-scrim").onclick=function(e){if(e.target===$("got-scrim"))closeGot();};
$("got-ok").onclick=function(){
  B.patch(b.n,{st:"received",got:TODAY});b=B.get(b.n);
  res=b.lines.map(function(l){return l.qty;});tab="lines";closeGot();paint();
  say("Lote recebido · a aba Resultado abriu para você lançar o que recusou.");
};
$("done-x").onclick=closeDone;
$("done-scrim").onclick=function(e){if(e.target===$("done-scrim"))closeDone();};
$("done-ok").onclick=function(){
  var d=okCny()-B.cny(b);
  var nt=$("dnote")?$("dnote").value.trim():"";
  var patch={st:"settled",done:TODAY,res:res};
  /* a observação do diálogo não é um campo do fechamento: é uma OBSERVAÇÃO, e vai para o mesmo
     lugar de todas as outras — a aba, e daí para a folha do resultado. Guardá-la num campo
     próprio criaria dois lugares onde procurar o que o comprador escreveu. */
  if(nt)patch.notes=(b.notes||[]).concat([{d:TODAY+"/26",who:"Shenzhen Yuan",t:nt}]);
  B.patch(b.n,patch);b=B.get(b.n);tab="pays";closeDone();paint();
  say("Resultado fechado · "+fmt(okUn())+" un. aprovados"+(d?" · acerto de −"+FX.cny(Math.abs(d)):"")
    +" · folha do resultado gerada e pagamento liberado.");
};
$("pay-x").onclick=closePay;
$("pay-scrim").onclick=function(e){if(e.target===$("pay-scrim"))closePay();};
document.addEventListener("keydown",function(e){if(e.key==="Escape"){closePay();closeGot();closeDone();}});
$("pay-ok").onclick=function(){
  var v=pnum(),rest=B.restUsd(b),full=v>=rest-0.004;
  if(!(v>0)||!pfile||v>rest+0.004)return;
  B.patch(b.n,{pays:(b.pays||[]).concat([{d:TODAY,usd:v,kind:full?"full":"partial",
    ref:fakeRef(b.n*7+(b.pays||[]).length+1),file:pfile,by:"Shenzhen Yuan"}]),st:full?"paid":"settled"});
  b=B.get(b.n);closePay();paint();
  say(full?("Quitado · "+FX.usd(B.dueUsd(b))+" pagos para a carteira do WhatTheChip")
          :("Pagamento parcial de "+FX.usd(v)+" registrado · restam "+FX.usd(B.restUsd(b))));
};

/* ---------- barra de demonstração: leva o mesmo registro por todas as etapas ---------- */
var DEMO=[["transit","A caminho"],["received","A conferir"],["due","Faturado"],["partial","Pago em parte"],["paid","Quitado"]];
var OKF=[0.94,0.91,0.97,0.88,0.95,0.92,0.96,0.9];
function demoState(){
  if(b.st==="transit")return "transit";
  if(b.st==="received")return "received";
  if(B.restUsd(b)<=0)return "paid";
  return B.paidUsd(b)>0?"partial":"due";
}
function applyDemo(k){
  var declared=b.lines.map(function(l){return l.qty;});
  var kept=(b.res&&b.res.length===b.lines.length)&&b.res.some(function(v,i){return v!==declared[i];});
  var seed=kept?b.res:b.lines.map(function(l,i){return Math.round(l.qty*OKF[i%OKF.length]);});
  var due=b.lines.reduce(function(a,l,i){return a+seed[i]*l.unit;},0);
  /* A ETA É UMA PROMESSA, NÃO UM FATO. Usar "chegada prevista" como "recebido em" datava o
     recebimento no futuro — o lote 49 (eta 05/08) aparecia "Recebido 05/08" com o hoje em 01/08.
     A costura de datas na leitura conserta de todo jeito, mas gerar certo é melhor que consertar. */
  var got=B.dmin(b.got||b.eta,TODAY),done=B.dmin(b.done||b.eta,TODAY);
  /* o pagamento é em US$: o devido em ¥ vira dólar pela taxa travada, e as parcelas somam exato */
  var dueU=Math.round(due*rate()*100)/100;
  var p1=Math.round(dueU*0.45*100)/100,slug="usdt-"+B.soCode(b).replace(/\//g,"-").toLowerCase();
  var pay1={d:done,usd:p1,kind:"partial",ref:fakeRef(b.n*7+1),file:slug+"-p1.pdf",by:"Shenzhen Yuan"};
  var pay2={d:TODAY,usd:Math.round((dueU-p1)*100)/100,kind:"full",ref:fakeRef(b.n*7+2),file:slug+"-p2.pdf",by:"Shenzhen Yuan"};
  var P={
    transit:{st:"transit",got:null,done:null,res:null,pays:null},
    received:{st:"received",got:got,done:null,res:declared,pays:null},
    due:{st:"settled",got:got,done:done,res:seed,pays:null},
    partial:{st:"settled",got:got,done:done,res:seed,pays:[pay1]},
    paid:{st:"paid",got:got,done:done,res:seed,pays:[pay1,pay2]}
  };
  B.patch(b.n,P[k]);
  b=B.get(b.n);res=(b.res||declared).slice();tab=null;paint();
  say("Demo · lote "+B.code(b)+" agora está em “"+DEMO.filter(function(d){return d[0]===k;})[0][1]+"”.");
}
function demobar(){
  var cur=demoState();
  $("demobar").innerHTML='<span class="demobar__l"><i></i>Demo · estado do lote</span>'
    +DEMO.map(function(d){
      return '<button type="button" data-d="'+d[0]+'"'+(d[0]===cur?' class="on"':'')+'><i class="dq dq--'+d[0]+'"></i>'+d[1]+'</button>';
    }).join("")
    +'<span class="demobar__sp"></span>';
  Array.prototype.forEach.call($("demobar").querySelectorAll("[data-d]"),function(el){
    el.onclick=function(){applyDemo(el.getAttribute("data-d"));};
  });
}

function paint(){
  statusbar();actions();sheetHd();rgrp();nb();body();demobar();buildPrint();
  var pend=B.all().filter(function(x){return x.st==="received"||((x.st==="settled"||x.st==="paid")&&B.restCny(x)>0);}).length;
  Array.prototype.forEach.call(document.querySelectorAll("[data-buys-badge]"),function(e){e.textContent=pend||"";});
}
function fx(){
  var s=FX.state();
  $("fxr").textContent=s.has?("1 ¥ ≈ US$ "+s.rate.toFixed(4)):"sem taxa do dia";
  $("fxd").textContent=s.has?("\u00b7 "+(s.is_market?"mid-market ":"contrato ")+s.date):"\u00b7 rode fetch_fx_rate";
  var lv=document.querySelector(".pshell__sub");if(lv)lv.classList.toggle("off",!s.has);
}
FX.onChange(fx);fx();paint();
})();
