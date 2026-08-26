/* WhatTheChip — FICHA DA VENDA (cliente). Mesma convenção da ficha da compra, do outro lado:
   barra de ação (voltar · etapas · a ação da vez) · folha (identidade, indicadores, campos)
   · abas com as linhas do registro. Nada muda de lugar entre etapas — os campos e as abas só
   acendem quando a etapa que os produz acontece.

   O cliente nunca vê o comprador. A contraparte é sempre a plataforma.
   O repasse é em US$ (o preço congelado no fechamento é em US$, e travar o câmbio é o ato de
   definir esse dólar), e não tem comprovante: data, valor e referência, e mais nada. */
(function(){
"use strict";
var $=function(i){return document.getElementById(i);},S=window.WTCSales,FX=window.WTCFX;
var n=(location.search.match(/[?&]v=(\d+)/)||[])[1];
var s=S.get(n)||S.all().filter(function(x){return S.todo(x);})[0]||S.all()[0];
var tab=null;
var tT;function say(m){$("toast-txt").textContent=m;$("toast").classList.add("is-on");clearTimeout(tT);tT=setTimeout(function(){$("toast").classList.remove("is-on");},3000);}
function fmt(v){return Number(v).toLocaleString("pt-BR");}
function esc(v){return String(v==null?"":v).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
var TODAY="02/08";
function rate(){return s.lock||FX.rate()||0;}
/* antes de a ordem ser emitida o câmbio NÃO está travado: lock é null e a leitura é a taxa do dia.
   Sem este intermediário, s.lock.toFixed(4) derruba a ficha inteira nos dois estados novos. */
function lockTxt(){return s.lock?("US$ "+s.lock.toFixed(4)):"a travar";}
function lockLine(){return s.lock?("1 ¥ = US$ "+s.lock.toFixed(4)+" · "+s.lockD):"câmbio ainda não travado";}
/* conta de repasse: quem informa é o cliente, e o pagamento sai pela Binance. Duas formas valem —
   usuário Binance (Pay ID ou e-mail da conta) ou endereço USDT na TRC-20. Enquanto não houver
   conta, o dinheiro não tem para onde ir, e é isso que a ficha precisa dizer. */
var PKIND={binance:["Binance Pay","Usuário Binance","Pay ID ou e-mail da conta Binance"],
           usdt:["USDT · TRC-20","Endereço USDT","Endereço da carteira na rede TRC-20"]};
function payee(){var w=s.payee;return (w&&w.v)?{k:w.k,net:PKIND[w.k][0],v:w.v}:null;}
var pkPick="binance";
function done(){return S.hasRes(s);}
/* DINHEIRO É PAPEL, NÃO TELA. Gerente e operador acompanham o lote sem ver preço: o registro
   continua inteiro — volume, aprovados, recusados, transportadora, datas, laudo — e só as cifras
   somem. Nada é substituído por "•••": uma célula tapada anuncia o que esconde. O que não é dele
   simplesmente não existe na tela, e as colunas fecham em cima. */
function M(){var a=window.WTCAccess&&window.WTCAccess.access();return !a||a.can_see_price;}
/* o rótulo do serviço sai do FEE DESTE registro — a taxa é por empresa e congela na emissão,
   então nunca se lê do padrão global nem se escreve à mão em texto */
var FEEPCT=S.feePct(s);
var CHK='<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
var I_COPY='<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11"/><path d="M5 15V4h11"/></svg>';
var I_WARN='<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5L22 20H2z"/><path d="M12 10v4M12 17h.01"/></svg>';
var I_DOC='<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7v18h10V6z"/><path d="M14 3v3h3"/></svg>';
var I_TRK='<svg viewBox="0 0 24 24" stroke-linecap="round"><rect x="3" y="7" width="13" height="10"/><path d="M16 10h3.5l1.5 3v4h-5"/><circle cx="7" cy="18.5" r="1.6"/><circle cx="17.5" cy="18.5" r="1.6"/></svg>';
var I_SHIP='<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 6.5h11v11h-11z"/><path d="M14.5 10H18l2.5 3.5v4h-6"/><circle cx="7" cy="19" r="1.7"/><circle cx="17" cy="19" r="1.7"/></svg>';
function copyTxt(t,m){try{navigator.clipboard.writeText(t);}catch(e){}say(m);}

/* ---------- cabeçalho do registro ---------- */
/* a convenção é a mesma do lote: utilitários, identidade, descrição, heróis, detalhe.
   Aqui os heróis são três números de dinheiro e o detalhe são as quatro etapas. */
function statusbar(){
  /* sem etiqueta de estado aqui: o trilho de etapas, uma linha abaixo, diz a mesma coisa com mais
     precisão (qual etapa, desde quando). Duas afirmações de estado a 40px uma da outra é eco. */
  $("vbar").innerHTML='<span class="rhead__code">'+S.code(s)+'</span>'+FX.origin(s.origin);
  $("vdesc").textContent=s.desc||"vendido à WhatTheChip";
  steps();
}
/* trilho de etapas: o mesmo da ficha do lote, no lugar do resumo — as caixas de etapa
   abaixo continuam sendo o detalhe; aqui só se lê, de um relance, onde o registro está */
function steps(){
  /* a etapa acesa é a última ALCANÇADA, não a próxima a fazer: despachar leva o registro para
     "Enviado" (é onde ele está, a caminho), não para "Recebido", que ainda não aconteceu. */
  /* noprice e tofreeze ficam na PRIMEIRA célula: o lote está fechado, a ordem ainda não existe.
     A próxima etapa não é do cliente, e por isso ele não tem botão nenhum nesses dois. */
  var AT={noprice:0,tofreeze:0,draft:1,transit:2,check:3,result:4,topay:5,paid:6};
  var at=AT[s.st]!=null?AT[s.st]:1;
  var ps=s.pays||[],last=ps[ps.length-1];
  var payv=s.st==="paid"?(last?last.d:"repassado"):s.st==="topay"?(ps.length?"parcial":"pendente"):"—";
  /* o terceiro item é o título longo: na célula cabe "Recebido", mas o que aconteceu ali foi o
     comprador marcar a chegada — e é isso que o cliente precisa ler ao passar o mouse. */
  var L=[["Fechado",s.st==="noprice"?"falta preço":(s.st==="tofreeze"?"a congelar":s.closed)],
         ["A despachar",""],["Enviado",s.ship||"—"],
         ["Recebido",s.got||(s.eta?"prev. "+s.eta:"—"),"Recebida pelo comprador"],
         ["Resultado",s.done||(s.st==="check"?"em conferência":"pendente")],["Pagamento",payv]];
  $("stat").innerHTML='<div class="stat">'+L.map(function(x,i){
    var k=i<at?"is-done":i===at?"is-now":"is-next",lb=x[2]||x[0];
    return '<span class="stat__s '+k+'" title="'+esc(x[1]?lb+" · "+x[1]:lb)+'">'
      +(i<at?CHK:'<i></i>')+x[0]+(i===at&&x[1]?'<small>'+esc(x[1])+'</small>':'')+'</span>';
  }).join("")+'</div>';
}
/* o lote no Estoque é o outro lado deste mesmo registro. O atalho mora na faixa de utilitários,
   em terciário e antes da ação da vez — leva, não decide. O código do lote nasce no próprio lote,
   então esta tela não o escreve: o rótulo é genérico. */
/* quando a bola está com a plataforma, o lugar do botão vira um aviso de espera —
   mesmo lugar, mesmo tamanho, sem convidar a clicar */
function lotBtn(){
  return s.lot?'<a class="btn btn--ter btn--sm" data-lot-link href="triagem.html?lot='+s.lot+'" title="Abrir o lote deste registro no Estoque" aria-label="Abrir o lote deste registro no Estoque"><span>Ver no estoque</span></a>':"";
}
function actions(){
  var h=lotBtn();
  /* mesmo lugar, mesmo tamanho, sem convidar a clicar: quando a bola é do comprador ou do
     sistema, o lugar do botão vira o aviso de espera — e diz o que está sendo esperado. */
  if(s.st==="noprice"||s.st==="tofreeze"){
    var w=s.st==="noprice"
      ?"O comprador ainda não cotou "+S.noPrice(s)+(S.noPrice(s)===1?" caixa":" caixas")+" deste lote"
      :"Cotação completa · o câmbio será travado e a ordem emitida automaticamente";
    $("act").innerHTML=h+'<span class="wait">'+I_WARN+w+'</span>';
    $("act").style.display="";
    return;
  }
  if(s.st==="draft")h+='<button class="btn btn--pri btn--sm" id="go" type="button">Despachar lote'+I_SHIP+'</button>';
  /* a caixa a caminho ainda admite correção: código digitado errado tem que ser corrigível, e o
     número às vezes só sai horas depois do despacho. Depois que o comprador marca a chegada o
     despacho trava — dali em diante o registro é o que foi conferido. */
  else if(s.st==="transit")h+='<button class="btn btn--ter btn--sm" id="edship" type="button">Editar despacho</button>';
  /* em trânsito não há ação nem aviso: o trilho de etapas já diz "Enviado" com a data, e a caixa
     Recebido carrega a previsão de chegada — um terceiro lugar dizendo o mesmo era eco */
  else if(s.st==="result")h+='<button class="btn btn--ghost btn--sm" id="dis" type="button">Contestar</button>'
    +'<button class="btn btn--pri btn--sm" id="go" type="button">Aceitar resultado'+CHK+'</button>';
  /* em "a receber" sobra o atalho do lote e mais nada: a etiqueta de status e a caixa Pagamento
     já dizem que o repasse está pendente — um terceiro aviso seria eco */
  else h+="";
  $("act").innerHTML=h;
  $("act").style.display=h?"":"none";
  if($("go"))$("go").onclick=s.st==="draft"?openShip:openAccept;
  if($("edship"))$("edship").onclick=openShip;
  if($("dis"))$("dis").onclick=function(){
    var has=(s.notes||[]).length;
    if(has)tab="notes";
    paint();
    say(has?"A plataforma foi notificada · resposta em até 2 dias úteis. As observações da conferência estão abaixo."
           :"A plataforma foi notificada da contestação · resposta em até 2 dias úteis.");
  };
}
/* ---------- heróis: os três números que respondem "quanto isso rendeu" ---------- */
function sheetHd(){
  var c=S.cny(s),g=S.grossCny(s),rest=S.restUsd(s),pd=S.paidUsd(s),un=S.units(s);
  var r=S.rateOf(s),R={rate:r},dash='<span class="m">\u2014</span>';
  function hero(l,v,d,cls){
    return '<div class="rmx rmx--hero '+(cls||"")+'"><div class="rmx__l">'+l+'</div>'
      +'<div class="rmx__v">'+v+'</div>'
      +'<div class="rmx__d">'+d+'</div></div>';
  }
  /* Estimado é sempre real; Resultado e A receber só existem depois da conferência — antes
     dela a célula mostra o traço e diz o que falta, em vez de fingir um número */
  /* sem dinheiro, os três heróis passam a ser o FÍSICO do lote — é o que sobra de decisivo:
     quanto foi, quanto passou, quanto voltou. Mesma forma, mesma gramática de "—" antes da hora. */
  if(!M()){
    var oku2=S.okUnits(s),rj2=un-oku2;
    $("rmx").innerHTML=
       hero("Volume",fmt(un)+" un.",S.byType(s).length+" tipos","rmx--est")
      +hero("Aprovados",done()?fmt(oku2)+" un.":"—",
          done()?Math.round(oku2/un*100)+"% do lote"
                :(s.st==="check"?"em conferência na plataforma":"depois do resultado"),
          done()?"rmx--res":"rmx--off")
      +hero("Recusados",done()?(rj2?"−"+fmt(rj2)+" un.":"nenhum"):"—",
          done()?(rj2?Math.round(rj2/un*100)+"% do lote":"lote inteiro aprovado")
                :"depois do resultado",
          done()?(rj2?"rmx--due":"rmx--ok"):"rmx--off");
    return;
  }
  /* CINCO números em sequência não são cinco KPIs: bruto · taxa · líquido · recebido · falta
     cabem em três heróis sem esconder nada, porque dois deles são a CONTA de outro.
       1º bruto, e embaixo dele o esperado com a diferença — o par que o briefing pede;
       2º líquido, e embaixo dele a dedução, com percentual E valor (nunca só um dos dois);
       3º o que falta, e embaixo dele o quanto já caiu.
     Assim nenhum número virou detalhe escondido: virou legenda do número que ele explica. */
  var d=g-c,fee=S.feeUsd(s),net=S.netUsd(s);
  $("rmx").innerHTML=
     hero(done()?"Resultado bruto":"Estimado",
        done()?FX.dual(g,"kpi",R):FX.dual(c,"kpi",{rate:r,est:true}),
        done()?("esperado "+FX.cny(c)+(d?" · diferença "+(d<0?"−":"+")+FX.cny(Math.abs(d)):" · sem diferença"))
              :(S.noPrice(s)?fmt(un)+" un. · parcial: "+S.noPrice(s)+(S.noPrice(s)===1?" caixa sem preço":" caixas sem preço")
                            :fmt(un)+" un. · "+(s.lock?"na taxa travada de "+s.lockD:"na taxa do dia, ainda não travada")),
        done()?"rmx--res":"rmx--est")
    +hero("Líquido",done()?FX.dualU(net,"kpi",R):dash,
        done()?("menos serviço de "+FEEPCT+" · −"+FX.usd(fee))
              :(s.st==="check"?"em conferência na plataforma":"já sem o serviço de "+FEEPCT),
        done()?"rmx--res":"rmx--off")
    +hero(done()&&!rest?"Recebido":"Falta receber",
        done()?FX.dualU(rest||pd,"kpi",{rate:r,mod:rest?"mvd--due":"mvd--ok"}):dash,
        done()?(rest?(pd?Math.round(S.paidPct(s))+"% repassado · "+FX.usd(pd)+" já na conta":"nada repassado ainda")
                    :"repasse concluído")
              :"depois do resultado",
        done()?(rest?"rmx--due":"rmx--ok"):"rmx--off");
}
/* ---------- as quatro etapas ---------- */
function fields(){
  function fld(l,v,c){return '<div class="fld2"><span>'+l+'</span><b class="'+(c||"")+'">'+v+'</b></div>';}
  /* k: done | now | next — o estado da etapa, que é também o avanço do registro */
  function grp(l,k,when,rows,extra){
    return '<div class="rgrp rgrp--'+k+'">'
      +'<div class="rgrp__h"><span class="rgrp__i">'+(k==="done"?CHK:'')+'</span>'
        +'<span class="rgrp__n">'+l+'</span><span class="rgrp__w">'+esc(when)+'</span></div>'
      +'<div class="rgrp__b">'+rows+(extra||"")+'</div></div>';
  }
  function why(t){return '<p class="rgrp__why">'+t+'</p>';}
  function xbtn(id,ico,t,full){return '<button class="rgrp__x" id="'+id+'" type="button" title="'+esc(full||t)+'">'+ico+'<span>'+esc(t)+'</span></button>';}
  /* identificador longo em célula estreita: corta no MEIO, nunca no fim — a cauda é justamente
     o que se confere contra a carteira. Mesma convenção dos hashes na aba Pagamentos. */
  function mid(v,a,b){return v.length<=a+b+1?v:v.slice(0,a)+"…"+v.slice(-b);}
  function xlink(id,ico,t,full,href){return '<a class="rgrp__x" id="'+id+'" href="'+esc(href)+'" target="_blank" rel="noopener" title="'+esc(full||t)+'">'+ico+'<span>'+esc(t)+'</span></a>';}
  var un=S.units(s),c=S.cny(s),ty=S.byType(s),sent=!!s.carrier,got=!!s.got;
  var oku=S.okUnits(s),g=S.grossCny(s),d=g-c,fee=S.feeUsd(s),net=S.netUsd(s);
  var ps=s.pays||[],last=ps[ps.length-1],pd=S.paidUsd(s),rest=S.restUsd(s),P=S.PAYEE;
  var turl=FX.trackUrl(s.carrier,s.track);
  /* o estado de cada etapa vem do que ela PRODUZIU, não de um índice: cumprida quando a
     saída existe, corrente quando é a que está sendo trabalhada, futura quando nada há */
  var kShip=got?"done":"now";
  var kRes=s.done?"done":(s.st==="check"?"now":"next");
  var kPay=done()?(rest<=0&&pd>0?"done":"now"):"next";
  var $m=M();
  $("rgrp").innerHTML=
    grp("Lote","done",s.closed,
      fld("Ordem",S.soCode(s),"m")
      +fld("Origem",s.origin==="pcb"?"Placa (PCB)":"Celular")
      +fld("Volume",fmt(un)+" un.","m")
      /* sem preço, a quarta linha é a outra medida do lote: quantos PNs distintos */
      +($m?fld("Preço médio",FX.cny(c/un),"m"):fld("Part numbers",fmt(S.pns(s).length),"m")))
    +grp("Despacho",kShip,sent?(got?s.got:s.ship):"pendente",
      fld("Transportadora",sent?esc(s.carrier):"—",sent?"":"off")
      +fld("Enviado",s.ship||"—",sent?"m":"m off")
      +fld("Recebido",s.got||(s.eta?"prev. "+s.eta:"—"),got?"m":"m off")
      /* a taxa travada é dado de preço: fx.js já a esconde do cabeçalho para estes papéis */
      +($m?fld("Câmbio",lockTxt(),s.lock?"m":"m off"):fld("Rastreio",sent?esc(s.track):"—",sent?"m":"m off")),
      /* o botão-dado só entra quando o código NÃO está nas linhas acima: para quem vê preço a
         quarta linha é o câmbio, então o rastreio precisa de um lugar. Para os demais ele já
         está listado — repeti-lo logo abaixo era dizer duas vezes a mesma coisa. */
      sent?($m?(s.track?(turl?xlink("trk",I_TRK,mid(s.track,10,6),s.carrier+" · "+s.track+" · abrir rastreio",turl)
                              :xbtn("trk",I_TRK,mid(s.track,10,6),s.carrier+" · "+s.track))
                        :why("Despachado sem código. O rastreio pode entrar depois — use Editar despacho."))
                :"")
          :why("Acende quando você informar a transportadora e a data de envio."))
    +grp("Resultado",kRes,s.done||(s.st==="check"?"conferindo":"—"),
      fld("Conferido em",s.done||(s.st==="check"?"em curso":"—"),s.done?"m":"m off")
      +fld("Aprovados",done()?fmt(oku)+" / "+fmt(un):"—",done()?"m":"m off")
      +fld("Recusados",done()?(un-oku?"−"+fmt(un-oku):"0"):"—",done()?(un-oku?"m bad":"m"):"m off")
      +($m?fld("Diferença",done()?(d?(d<0?"−":"+")+FX.cny(Math.abs(d)):"sem diferença"):"—",done()?(d?"m bad":"m good"):"m off")
          :fld("Aproveitamento",done()?Math.round(oku/un*100)+"%":"—",done()?"m good":"m off")),
      done()?"":why("A plataforma confere capacidade por capacidade e publica o resultado aqui."))
    /* a etapa Pagamento é dinheiro de ponta a ponta: para quem não vê preço ela não fica vazia
       nem tapada — simplesmente não está lá, e a faixa de etapas continua marcando o repasse. */
    +($m?grp("Pagamento",kPay,last?last.d:(done()?"a receber":"—"),
      fld("Bruto",done()?FX.usd(S.grossUsd(s)):"—",done()?"m":"m off")
      +fld("Serviço "+FEEPCT,done()?"−"+FX.usd(fee):"—",done()?"m":"m off")
      +fld("Líquido",done()?FX.usd(net):"—",done()?"m good":"m off")
      +fld("Recebido",pd?FX.usd(pd):(done()?"nada ainda":"—"),pd?"m":"m off"),
      done()?(payee()?xbtn("pcopy",I_COPY,mid(payee().v,9,7),P.owner+" · "+payee().net+" · "+payee().v)
                     /* o pedido de conta só faz sentido enquanto há dinheiro para receber: com o
                        repasse concluído, "sem ela o repasse não sai" contradiz o valor recebido
                        impresso duas linhas acima, na mesma caixa. */
                     :(rest>0?why("Informe sua conta Binance na aba Pagamentos — sem ela o repasse não sai."):""))
            :why("O serviço e o líquido aparecem quando o resultado for publicado.")):"");
  if($("trk")&&!turl)$("trk").onclick=function(){copyTxt(s.track,"Rastreio "+s.carrier+" copiado: "+s.track);};
  if($("pcopy"))$("pcopy").onclick=function(){copyTxt(payee().v,"Conta de repasse copiada.");};
}

/* ---------- abas ---------- */
var TIC={
  lines:'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h9M4 12h9M4 19h9"/><path d="M16.5 6.5l1.8 1.8 3.2-3.6M16.5 13.5l1.8 1.8 3.2-3.6"/></svg>',
  chips:'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><rect x="7" y="7" width="10" height="10"/><path d="M10 3.5V7M14 3.5V7M10 17v3.5M14 17v3.5M3.5 10H7M3.5 14H7M17 10h3.5M17 14h3.5"/></svg>',
  pays:'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 7.5h17v11h-17z"/><path d="M3.5 11h17M6.5 15h4"/></svg>',
  notes:'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3.5h14v17H5z"/><path d="M8.5 8h7M8.5 12h7M8.5 16h4"/></svg>'
};
var TABS=[["lines","Resultado",function(){return s.lines.length;},function(){return true;}],
          ["chips","Chips",function(){return S.pns(s).length;},function(){return true;}],
          ["pays","Pagamentos",function(){return (s.pays||[]).length;},function(){return done()&&M();}],
          ["notes","Observações",function(){return (s.notes||[]).length;},function(){return true;}]];
function nb(){
  var avail=TABS.filter(function(t){return t[3]();}).map(function(t){return t[0];});
  if(!tab||avail.indexOf(tab)<0)tab="lines";
  /* aba de dinheiro não fica cinza para quem não vê preço: sai da barra. Desabilitada, ela
     anunciaria a existência de um dado negado — que é o oposto de esconder. */
  $("nb").innerHTML=TABS.filter(function(t){return t[0]!=="pays"||M();}).map(function(t){
    var on=t[3]();
    return '<button type="button" data-t="'+t[0]+'"'+(t[0]===tab?' class="on"':'')+(on?'':' disabled title="disponível quando o resultado for publicado"')+'>'
      +TIC[t[0]]+t[1]+'<em>'+(on?t[2]():"—")+'</em></button>';
  }).join("")
  +(tab==="lines"||tab==="chips"?'<span class="nb__tool"><input class="flt" id="flt" type="text" placeholder="'+(tab==="chips"?(M()?"Filtrar PN, fabricante ou C-…":"Filtrar PN ou C-…"):"Filtrar capacidade, tipo ou C-…")+'" autocomplete="off" /></span>':'')
  +'<span class="nb__sp"></span>'
  +'<span class="nb__tool">'
    +'<button class="xbtn" id="prs" type="button"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 6.5h11v11h-11z"/><path d="M14.5 10H18l2.5 3.5v4h-6"/><circle cx="7" cy="19" r="1.7"/><circle cx="17" cy="19" r="1.7"/></svg>Folha de embarque</button>'
    +'<button class="xbtn" id="pr" type="button"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M7 9V3.5h10V9"/><path d="M4 9h16v7h-3M7 16H4V9"/><path d="M7 14h10v6.5H7z"/></svg>Imprimir</button>'
    +'<button class="xbtn" id="xp" type="button"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5v11M8 11l4 4 4-4"/><path d="M4 16v4.5h16V16"/></svg>Exportar</button></span>';
  Array.prototype.forEach.call($("nb").querySelectorAll("[data-t]"),function(el){
    el.onclick=function(){tab=el.getAttribute("data-t");nb();body();};
  });
  $("xp").onclick=xport;$("pr").onclick=printDoc;$("prs").onclick=printShip;
  if($("flt"))$("flt").oninput=filter;
}
function body(){
  $("nbb").innerHTML=tab==="lines"?linesTab():tab==="chips"?chipsTab():tab==="notes"?notesTab():paysTab();
  if(tab==="lines"||tab==="chips"){
    Array.prototype.forEach.call(document.querySelectorAll("#nbb [data-s]"),function(el){
      el.onclick=function(){
        var k=el.getAttribute("data-s"),o=srt[tab];
        if(o.k===k)o.d=-o.d;else{o.k=k;o.d=TXTK[k]?1:-1;}
        body();
      };
    });
    if($("flt")&&$("flt").value)filter();
  }
  if(tab==="pays"){
    if($("pcopy2"))$("pcopy2").onclick=function(){copyTxt(payee().v,"Conta de repasse copiada.");};
    if($("pedit"))$("pedit").onclick=function(){S.patch(s.n,{payee:null});s=S.get(s.n);paint();};
    Array.prototype.forEach.call(document.querySelectorAll("[data-pk]"),function(b){
      b.onclick=function(){pkPick=b.getAttribute("data-pk");paint();};
    });
    if($("psave"))$("psave").onclick=function(){
      var v=$("pval").value.trim();
      if(!v){$("pval").focus();return;}
      S.patch(s.n,{payee:{k:pkPick,v:v}});s=S.get(s.n);paint();
      say(PKIND[pkPick][1]+" salvo · o repasse desta venda vai para "+v+".");
    };
    Array.prototype.forEach.call(document.querySelectorAll("[data-rf]"),function(el){
      el.onclick=function(){copyTxt(el.getAttribute("data-rf"),"Referência do repasse copiada.");};
    });
  }
  if(tab==="notes"){
    /* leitura apenas: quem escreve as observações é a plataforma, na conferência */
  }
}

/* ---------- PLANILHA PADRÃO ----------
   As duas abas de conteúdo desenham a MESMA tabela do Estoque e de Vendas: cabeçalho escuro grudado
   no topo, linha de 56px, dinheiro em .v, a coluna que decide em .key, colunas secundárias saindo
   por largura (.hide-md, .hide-lg, .d) e a linha virando cartão no telefone.
   Duas coisas saíram no caminho. As FAIXAS DE TIPO (com bolinha de cor e subtotal) viraram uma
   coluna Categoria — é assim que o lote fechado do Estoque mostra chips, e o que a faixa dava,
   ordem por tipo, agora é clique no cabeçalho, que ainda ordena por qualquer outra coluna. E as
   COLUNAS TINGIDAS de verde/vermelho/azul saíram: no padrão a cor mora no número (recusa em
   vermelho, zero apagado), não no fundo da coluna — três faixas de cor numa tabela de dinheiro
   competiam com os selos e com o próprio valor.
   O total de cada coluna virou o rodapé de soma (.tfoot--sum), o mesmo do Estoque. */
/* a ordem inicial é sempre pela coluna que DECIDE (maior dinheiro primeiro) — e depois do
   resultado publicado quem decide é o resultado, não a estimativa, que ali já sai da tabela */
var srt={lines:{k:"val",d:-1},chips:{k:"val",d:-1}},srt0=0;
var TXTK={wtc:1,item:1,pn:1,make:1};
function th(k,lb,cls){
  var o=srt[tab],on=o.k===k;
  return '<th class="s'+(cls?" "+cls:"")+(on?" is-sort":"")+'" data-s="'+k+'">'+lb
    +'<span class="ar">'+(on&&o.d>0?"▲":"▼")+'</span></th>';
}
function srtRows(rows){
  var k=srt[tab].k,dr=srt[tab].d;
  rows.sort(function(a,b){
    var x=a[k],y=b[k];
    return typeof x==="string"?dr*x.localeCompare(y,"pt-BR"):dr*(x-y);
  });
  return rows;
}
function tbl(head,rows,ft){
  return '<div class="dtab__wrap"><table class="dtab dtab--static">'
    +'<thead><tr>'+head+'</tr></thead><tbody id="rtb">'+rows+'</tbody></table></div>'
    +'<div class="tfoot tfoot--sum">'+ft+'</div>';
}

/* aba Resultado: o que foi enviado e o que a plataforma aprovou, capacidade por capacidade */
function linesTab(){
  var ty=S.byType(s),un=S.units(s),c=S.cny(s),oku=S.okUnits(s),g=S.grossCny(s),res=s.res||[],D=done(),$m=M();
  /* sem dinheiro a coluna que decide é o VOLUME — ordenar por um valor invisível não se explica */
  if(!srt0){srt0=1;srt.lines.k=$m?(D?"got":"val"):(D?"ok":"qty");}
  var rows=[];
  ty.forEach(function(gr){gr.rows.forEach(function(r){
    var ok=res[r.i]||0;
    rows.push({wtc:r.wtc,item:gr.t+" "+r.cap,qty:r.qty,unit:r.unit,val:r.qty*(r.unit||0),
      ok:ok,rj:r.qty-ok,got:ok*r.unit,lost:(r.qty-ok)*r.unit,
      k:(gr.t+" "+r.cap+" "+r.wtc).toLowerCase()});
  });});
  srtRows(rows);
  var head=th("item","Item")+th("wtc","Caixa WTC")+th("qty","Enviados",D&&$m?"hide-sm":"")
    +($m?th("unit","Unitário","hide-md")+th("val","Estimado",D?"hide-lg":""):"")
    +(D?th("rj","Recusados","hide-md hr")+th("ok","Aprovados","hg")+($m?th("got","Resultado","hb"):""):"");
  var body=rows.map(function(r){
    return '<tr data-row data-k="'+esc(r.k)+'">'
      +'<td class="c" data-label="Item">'+esc(r.item)+'</td>'
      +'<td data-label="Caixa WTC"><span class="wtc">'+esc(r.wtc)+'</span></td>'
      /* no cartão do telefone, depois do resultado, Enviados sai: ele e Aprovados cairiam juntos
         na 2ª linha com a mesma forma e o mesmo sufixo — dois números indistinguíveis. Quem decide
         ali é aprovados + resultado, e o total enviado está no rodapé de soma. */
      +'<td class="n'+(D&&$m?' hide-sm':'')+(!D&&!$m?' key':'')+'" data-label="Enviados" data-suffix="un.">'+fmt(r.qty)+'</td>'
      +($m?'<td class="n hide-md" data-label="Unitário">'+(r.unit==null?'<span class="none">sem preço</span>':FX.cny(r.unit))+'</td>'
        +'<td class="v'+(D?' hide-lg':' key')+'" data-label="Estimado">'+(r.unit==null
            ?'<span class="none">—</span><span class="miss">aguarda cotação</span>'
            :FX.cny(r.val)+'<span>'+(s.lock?'':'≈ ')+FX.usd(r.val*rate())+'</span>')+'</td>':'')
      +(D?'<td class="n rej hr hide-md '+(r.rj?"some":"zero")+'" data-label="Recusados">'+(r.rj?"−"+fmt(r.rj):"0")+'</td>'
        +'<td class="n hg'+($m?'':' key')+'" data-label="Aprovados" data-suffix="un.">'+fmt(r.ok)+'</td>'
        +($m?'<td class="v key hb" data-label="Resultado">'+FX.cny(r.got)+'<span>≈ '+FX.usd(r.got*rate())+'</span></td>':''):'')
    +'</tr>';
  }).join("");
  var ft='<span><b id="ftn">'+rows.length+'</b> linhas · <b>'+ty.length+'</b> tipos</span>'
    +(D?'<span><b>'+fmt(oku)+'</b> de <b>'+fmt(un)+'</b> un.'+($m?' · <b>'+FX.cny(g)+'</b>':'')+'</span>'
       :'<span><b>'+fmt(un)+'</b> un.'+($m?' · <b>'+FX.cny(c)+'</b> estimados':' enviadas')+'</span>');
  /* o aviso de "ainda é estimativa" fala de preço travado: sem cifra na tela ele não tem objeto,
     e o que resta a dizer (a conferência é da plataforma) já está na caixa Resultado */
  return (D||!$m?'':'<div class="rhint"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>'
      +'<span>Ainda é <b>estimativa</b> — os valores vêm da tabela de preços na taxa travada em '+s.lockD+'. O resultado final aparece aqui quando a conferência terminar.</span></div>')
    +tbl(head,body,ft);
}
/* aba Chips: um part number por linha — a identidade da linha é o PN, então ele é a primeira coluna */
function chipsTab(){
  var list=S.pns(s),un=S.units(s),c=S.cny(s),cat={},$m=M();
  if(!$m&&srt.chips.k==="val")srt.chips.k="qty";
  var rows=list.map(function(p){
    cat[p.wtc]=1;
    return {pn:p.pn,wtc:p.wtc,make:p.make,spec:p.spec,qty:p.qty,unit:p.unit,val:p.qty*p.unit,
      k:($m?p.pn+" "+p.make+" "+p.wtc+" "+p.cap+" "+p.type:p.pn+" "+p.wtc).toLowerCase()};
  });
  srtRows(rows);
  /* fabricante e identificação são o DECODE do chip — quem lê o lote sem preço lê o registro
     (que PN, qual categoria, quantos), não a ficha técnica. Mesma linha de corte do dinheiro. */
  var head=th("pn","Part number")+th("wtc","Caixa WTC")
    +($m?th("make","Fabricante","hide-md")+'<th class="d">Identificação</th>':"")
    +th("qty","Chips")+($m?th("unit","Unitário","hide-md")+th("val","Valor"):"");
  var body=rows.map(function(r){
    return '<tr data-row data-k="'+esc(r.k)+'">'
      +'<td class="c" data-label="Part number">'+esc(r.pn)+'</td>'
      +'<td data-label="Caixa WTC"><span class="wtc">'+esc(r.wtc)+'</span></td>'
      +($m?'<td class="hide-md" data-label="Fabricante">'+esc(r.make)+'</td>'
        +'<td class="d" data-label="Identificação">'+esc(r.spec)+'</td>':'')
      +'<td class="n'+($m?'':' key')+'" data-label="Chips" data-suffix="un.">'+fmt(r.qty)+'</td>'
      +($m?'<td class="n hide-md" data-label="Unitário">'+FX.cny(r.unit)+'</td>'
        +'<td class="v key" data-label="Valor">'+FX.cny(r.val)+'<span>≈ '+FX.usd(r.val*rate())+'</span></td>':'')
    +'</tr>';
  }).join("");
  var ft='<span><b id="ftn">'+rows.length+'</b> PNs · <b>'+Object.keys(cat).length+'</b> caixas</span>'
    +'<span><b>'+fmt(un)+'</b> un.'+($m?' · <b>'+FX.cny(c)+'</b>':'')+'</span>';
  return tbl(head,body,ft);
}
/* o filtro mora na barra de abas (é a busca desta tabela) e reescreve a contagem do rodapé:
   sem isso o rodapé continuava afirmando 112 linhas com 6 na tela */
function filter(){
  var q=$("flt").value.trim().toLowerCase(),n=0,all=0;
  Array.prototype.forEach.call(document.querySelectorAll("#rtb [data-row]"),function(tr){
    all++;
    var on=!q||tr.getAttribute("data-k").indexOf(q)>=0;
    tr.style.display=on?"":"none";
    if(on)n++;
  });
  if($("ftn"))$("ftn").textContent=q?n+" de "+all:all;
}

/* aba Pagamentos: para onde o dinheiro vai, quanto já caiu e o que falta */
/* O repasse do cliente tem data, valor e REFERÊNCIA — e não tem comprovante. Comprovante é
   prova de transferência da outra perna (comprador → WhatTheChip), e essa perna o cliente não vê:
   nem valor, nem data, nem existência. Aqui o que autentica o repasse é a referência em cadeia. */
function paysTab(){
  var P=S.PAYEE,g=S.grossUsd(s),fee=S.feeUsd(s),net=S.netUsd(s),pd=S.paidUsd(s),rest=S.restUsd(s),pct=S.paidPct(s),ps=s.pays||[];
  var r=S.rateOf(s),R={rate:r};
  var rows=ps.map(function(p,i){
    var lb=p.kind==="full"?(i?"QUITAÇÃO":"INTEGRAL"):"PARCIAL";
    return '<tr><td class="c" data-label="Data">'+esc(p.d)+'</td>'
      +'<td data-label="Registro"><span class="tag '+(p.kind==="full"?"tag--yes":"tag--info")+'"><span class="dot"></span>'+lb+'</span></td>'
      +'<td class="v key" data-label="Recebido">'+FX.dualU(p.usd,"xs",{rate:r,mod:"mvd--stack"})+'</td>'
      +'<td class="n hide-md" data-label="Referência">'+(p.ref?'<button class="rcpt" type="button" data-rf="'+esc(p.ref)+'" title="'+esc(p.ref)+'">'+esc(p.ref.slice(0,8))+'…'+esc(p.ref.slice(-6))+'</button>':'—')+'</td></tr>';
  }).join("");
  var tbl=ps.length
    ?'<div class="dtab__wrap"><table class="dtab dtab--static">'
      +'<thead><tr><th>Data</th><th>Registro</th><th>Recebido</th><th class="hide-md">Referência</th></tr></thead>'
      +'<tbody>'+rows+'</tbody></table></div>'
      +'<div class="tfoot tfoot--sum"><span><b>'+ps.length+'</b>'+(ps.length===1?' repasse':' repasses')+'</span>'
      +'<span><b>'+FX.usd(pd)+'</b> recebidos'+(rest?' · faltam <b class="due">'+FX.usd(rest)+'</b>':' · <b class="got">tudo recebido</b>')+'</span></div>'
    :'<div class="pempty">Nenhum repasse ainda. Assim que a plataforma liberar o pagamento, cada parcela aparece aqui com a data e a referência da transferência.</div>';
  var W=payee();
  var wcard=W
    ?'<div class="wal"><span class="wal__n">'+esc(P.owner)+'</span><span class="wal__net">'+esc(W.net)+'</span></div>'
     +'<div class="wadr"><code>'+esc(W.v)+'</code><button id="pcopy2" type="button" aria-label="Copiar conta">'+I_COPY+'</button></div>'
     +'<div class="pay__ed"><button class="btn btn--ter btn--sm" id="pedit" type="button">Alterar conta</button></div>'
     +'<div class="paynote">'+I_WARN+'<span>Todo repasse desta venda cai nesta conta. Altere antes de aceitar o resultado — depois do aceite o destino fica travado.</span></div>'
    :'<div class="pick" id="ppick">'
       +'<button type="button" data-pk="binance"'+(pkPick==="binance"?' class="on"':'')+'>Usuário Binance</button>'
       +'<button type="button" data-pk="usdt"'+(pkPick==="usdt"?' class="on"':'')+'>Endereço USDT</button>'
     +'</div>'
     +'<div class="fld"><div class="fld__l">'+PKIND[pkPick][1]+'<em class="req">obrigatório</em></div>'
       +'<input class="minput" id="pval" type="text" placeholder="'+esc(PKIND[pkPick][2])+'" autocomplete="off" /></div>'
     +'<div class="pay__ed"><button class="btn btn--pri btn--sm" id="psave" type="button">Salvar conta'+CHK+'</button></div>'
     +'<div class="paynote">'+I_WARN+'<span>O repasse é feito pela Binance. Informe o usuário da sua conta ou o endereço USDT — sem isso a plataforma não tem para onde mandar o dinheiro.</span></div>';
  return '<div class="pay">'
      +'<div class="pay__c pay__c--w">'
        +'<div class="pay__k">Sua conta de repasse</div>'+wcard
      +'</div>'
      +'<div class="pay__c pay__c--m">'
        +'<div class="pay__k">Conta desta venda</div>'
        +'<div class="pmet">'
          /* aqui os cinco números ficam em sequência de propósito: esta é a caixa do DETALHE, e é
             onde a subtração tem que poder ser lida linha a linha. A hierarquia mora nos heróis. */
          +'<div class="pmet__r"><span>Resultado bruto</span>'+FX.dual(S.grossCny(s),"sm",R)+'</div>'
          +'<div class="pmet__r"><span>Nosso serviço · '+FEEPCT+'</span><b>−'+FX.usd(fee)+'</b></div>'
          +'<div class="pmet__r big"><span>Líquido</span>'+FX.dualU(net,"sm",R)+'</div>'
          +'<div class="pmet__r done"><span>Já recebido</span>'+FX.dualU(pd,"sm",R)+'</div>'
          +'<div class="pmet__r '+(rest?"rest":"done")+'"><span>'+(rest?"Falta receber":"Saldo")+'</span>'+FX.dualU(rest,"sm",R)+'</div>'
        +'</div>'
        +'<div class="pbar__l"><span>Serviço de '+FEEPCT+' e câmbio de '+r.toFixed(4)+' congelados na emissão desta ordem, em '+esc(s.closed)+'.</span></div>'
        +'<div class="pbar"><i style="width:'+pct+'%"></i></div>'
        +'<div class="pbar__l"><span>'+Math.round(pct)+'% repassado</span><span>'+(rest?FX.usd(rest)+' a caminho':FX.usd(pd)+' liquidados')+'</span></div>'
      +'</div>'
    +'</div>'+tbl;
}
/* aba Observações: quem escreve é a plataforma, na conferência. Do lado do cliente é leitura —
   é o laudo que acompanha o resultado e sai junto no PDF. */
function notesTab(){
  var ns=s.notes||[];
  return ns.length
    ?ns.map(function(x){
        return '<div class="nt"><div class="nt__h"><b>'+esc(x.who)+'</b><span>'+esc(x.d)+'</span></div>'
          +'<p>'+esc(x.t)+'</p></div>';
      }).join("")
    :'<div class="pempty">Nenhuma observação nesta venda. A plataforma anota aqui o que encontrou na conferência — divergências, lotes fora do padrão e o que motivou cada recusa.</div>';
}

/* ---------- despachar ----------
   Despacho é LOGÍSTICA, não dinheiro: frete não entra aqui. Uma caixa por lote, e três campos.
   A DATA é obrigatória (é ela que confirma a venda e faz o registro aparecer para o comprador);
   o RASTREIO é opcional, porque o número às vezes só sai horas depois de a caixa ser postada.
   O mesmo diálogo serve para despachar e para corrigir: em trânsito ele reabre com os valores
   preenchidos, e o botão muda de nome. */
var CARRIERS=["DHL","FedEx","UPS","SF Express","EMS","Correios"];
function iso(d){var p=String(d||"").split("/");return p.length<2?"":"2026-"+p[1]+"-"+p[0];}
function br(v){var p=String(v||"").split("-");return p.length<3?"":p[2]+"/"+p[1];}
function openShip(){
  var ed=s.st!=="draft",car=s.carrier||CARRIERS[0];
  $("ship-b").innerHTML='<div class="msum">'
    +'<div class="msum__r"><span>Ordem</span><b>'+S.soCode(s)+'</b></div>'
    +'<div class="msum__r"><span>Conteúdo</span><b>'+fmt(S.units(s))+' un. · '+S.byType(s).length+' tipos</b></div>'
    +(M()?'<div class="msum__r rest"><span>Estimado</span><b>'+FX.cny(S.cny(s))+'</b></div>':'')+'</div>'
    +'<div class="fld"><div class="fld__l">Transportadora<em class="req">obrigatório</em></div>'
      +'<div class="pick" id="pick">'+CARRIERS.map(function(c){
        return '<button type="button" data-c="'+c+'"'+(c===car?' class="on"':'')+'>'+c+'</button>';
      }).join("")+'</div></div>'
    +'<div class="fld"><div class="fld__l">Data de envio<em class="req">obrigatório</em></div>'
      +'<input class="minput" id="sdt" type="date" value="'+esc(iso(s.ship)||iso(TODAY))+'" max="2026-08-02" /></div>'
    +'<div class="fld"><div class="fld__l">Código de rastreio<em>pode entrar depois</em></div>'
      +'<input class="minput" id="stk" type="text" value="'+esc(s.track||"")+'" placeholder="ex.: 4721 8834 990" autocomplete="off" /></div>'
    +'<div class="gnote">'+I_WARN+'<span>'+(ed
      ?'O conteúdo do lote já está travado — aqui você corrige só transportadora, data e código. Depois que a caixa for recebida, o despacho também trava.'
      :'Despachar <b>confirma a venda</b>: a partir daqui o registro aparece para o comprador e o conteúdo do lote fica travado — nenhuma peça pode ser adicionada ou retirada.')+'</span></div>';
  Array.prototype.forEach.call($("pick").querySelectorAll("[data-c]"),function(el){
    el.onclick=function(){
      car=el.getAttribute("data-c");
      Array.prototype.forEach.call($("pick").querySelectorAll("[data-c]"),function(o){o.className=o===el?"on":"";});
    };
  });
  var val=function(){
    $("ship-ok").disabled=!$("sdt").value;
    $("ship-ok").innerHTML=(ed?"Salvar despacho":"Despachar lote")+CHK;
  };
  $("sdt").oninput=val;val();
  $("ship-ok").onclick=function(){
    var dt=br($("sdt").value);if(!dt)return;
    var t=$("stk").value.trim();
    S.patch(s.n,{st:"transit",carrier:car,track:t||null,ship:dt,eta:s.eta||"09/08"});
    s=S.get(s.n);closeShip();paint();
    say(ed?("Despacho atualizado · "+car+(t?" · "+t:" · sem código de rastreio ainda"))
          :("Lote despachado por "+car+(t?" · a plataforma acompanha o rastreio.":" · informe o código quando a transportadora emitir.")));
  };
  $("ship-scrim").classList.add("is-on");
  setTimeout(function(){$("sdt").focus();},60);
}
function closeShip(){$("ship-scrim").classList.remove("is-on");}

/* ---------- aceitar resultado ---------- */
function openAccept(){
  var un=S.units(s),c=S.cny(s),oku=S.okUnits(s),g=S.grossCny(s),d=g-c,net=S.netUsd(s),$m=M();
  /* o aceite continua sendo do gerente — o que muda é o que o diálogo mostra: sem preço, ele
     confirma o que foi CONFERIDO (enviado, aprovado, recusado), que é o que se contesta. */
  $("acc-b").innerHTML='<div class="msum">'
    +'<div class="msum__r"><span>Enviados</span><b>'+fmt(un)+' un.</b></div>'
    +'<div class="msum__r"><span>Aprovados</span><b>'+fmt(oku)+' un.</b></div>'
    +($m?'<div class="msum__r"><span>Resultado bruto</span><b>'+FX.cny(g)+' = '+FX.usd(S.grossUsd(s))+'</b></div>'
      +'<div class="msum__r"><span>Nosso serviço · '+FEEPCT+'</span><b>−'+FX.usd(S.feeUsd(s))+'</b></div>'
      +'<div class="msum__r rest"><span>Você recebe</span><b>'+FX.usd(S.netUsd(s))+'</b></div>'
      :'<div class="msum__r"><span>Recusados</span><b>'+(un-oku?"−"+fmt(un-oku)+" un.":"nenhum")+'</b></div>'
      +'<div class="msum__r rest"><span>Aproveitamento</span><b>'+Math.round(oku/un*100)+'%</b></div>')+'</div>'
    +($m?'<div class="dlt"><span>Estimado '+FX.cny(c)+'</span><b class="'+(d?"neg":"ok")+'">'
      +(d?(d<0?"−":"+")+FX.cny(Math.abs(d))+" ("+(d/c*100).toFixed(1)+"%)":"sem diferença")+'</b></div>':'')
    +'<div class="gnote">'+I_WARN+'<span>Aceitar libera o repasse'+($m?' de <b>'+FX.usd(net)+'</b>':'')+' para a conta da empresa. Depois disso o resultado não pode mais ser contestado — se algum número não bate, use <b>Contestar</b> antes de aceitar.</span></div>';
  $("acc-scrim").classList.add("is-on");
  setTimeout(function(){$("acc-ok").focus();},60);
}
function closeAcc(){$("acc-scrim").classList.remove("is-on");}

/* ---------- exportar e imprimir ---------- */
function xport(){
  var rows=[],q=function(v){v=String(v==null?"":v);return /[";,\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;},res=s.res||[];
  var $m=M();
  if(tab==="chips"){
    rows.push(["Part number"].concat($m?["Fabricante"]:[]).concat(["Caixa WTC"])
      .concat($m?["Identificação"]:[]).concat(["Chips"]).concat($m?["CNY unit.","CNY total"]:[]));
    S.pns(s).forEach(function(p){rows.push([p.pn].concat($m?[p.make]:[]).concat([p.wtc])
      .concat($m?[p.spec]:[]).concat([p.qty]).concat($m?[p.unit,p.qty*p.unit]:[]));});
  }else if(tab==="pays"){
    rows.push(["Data","Registro","USD recebido","CNY equivalente","Referência"]);
    (s.pays||[]).forEach(function(p,i){rows.push([p.d,p.kind==="full"?(i?"Quitação":"Integral"):"Parcial",
      p.usd,Math.round(p.usd/rate()),p.ref||""]);});
  }else if(tab==="notes"){
    rows.push(["Data","Autor","Observação"]);
    (s.notes||[]).forEach(function(x){rows.push([x.d,x.who,x.t]);});
  }else{
    rows.push(["Tipo","Capacidade","Caixa WTC","Enviados"].concat($m?["CNY unit.","CNY estimado"]:[])
      .concat(done()?["Recusados","Aprovados"].concat($m?["CNY resultado"]:[]):[]));
    S.byType(s).forEach(function(g){g.rows.forEach(function(r){
      var o=res[r.i]||0;
      rows.push([g.t,r.cap,r.wtc,r.qty].concat($m?[r.unit,r.qty*r.unit]:[])
        .concat(done()?[r.qty-o,o].concat($m?[o*r.unit]:[]):[]));
    });});
  }
  var csv="\ufeff"+rows.map(function(r){return r.map(q).join(";");}).join("\r\n");
  var f=S.code(s).replace(/\//g,"-")+"-"+tab+".csv";
  var a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  a.download=f;document.body.appendChild(a);a.click();
  setTimeout(function(){URL.revokeObjectURL(a.href);a.remove();},400);
  say("Exportado · "+f+" · "+(rows.length-1)+" linhas");
}
function buildPrint(){
  var ty=S.byType(s),un=S.units(s),c=S.cny(s),oku=S.okUnits(s),g=S.grossCny(s),res=s.res||[];
  var rj=un-oku,d=g-c,fee=S.feeUsd(s),net=S.netUsd(s),ps=s.pays||[],ns=s.notes||[],pd=S.paidUsd(s),rest=S.restUsd(s);
  /* a folha impressa segue o mesmo gate da tela: sem preço ela é o LAUDO do lote (o que foi, o
     que passou, o que voltou, com as observações da plataforma), não um documento financeiro.
     Papel circula mais que tela — deixar a cifra só no PDF anularia o gate inteiro. */
  var $m=M();
  function row(l,v){return '<div class="pr__r"><span>'+l+'</span><b>'+v+'</b></div>';}
  var lines=ty.map(function(gr){
    var ok=gr.rows.reduce(function(a,r){return a+(res[r.i]||0);},0);
    return '<tr class="pr__g"><td colspan="2">'+esc(gr.t)+'</td><td class="n">'+fmt(gr.qty)+'</td>'
      +($m?'<td></td><td class="n">'+FX.cny(gr.cny)+'</td>':'')
      +(done()?'<td class="n">'+(gr.qty-ok?"−"+fmt(gr.qty-ok):"0")+'</td><td class="n">'+fmt(ok)+'</td>'
        +($m?'<td class="n">'+FX.cny(gr.rows.reduce(function(a,r){return a+(res[r.i]||0)*r.unit;},0))+'</td>':''):'')+'</tr>'
      +gr.rows.map(function(r){
        var o=res[r.i]||0,x=r.qty-o;
        return '<tr><td>'+esc(r.cap)+'</td><td>'+esc(r.wtc)+'</td><td class="n">'+fmt(r.qty)+'</td>'
          +($m?'<td class="n">'+FX.cny(r.unit)+'</td><td class="n">'+FX.cny(r.qty*r.unit)+'</td>':'')
          +(done()?'<td class="n">'+(x?"−"+fmt(x):"0")+'</td><td class="n">'+fmt(o)+'</td>'
            +($m?'<td class="n">'+FX.cny(o*r.unit)+'</td>':''):'')+'</tr>';
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
  prt.innerHTML='<div class="pr__hd"><div><div class="pr__k">'+($m?"Resultado da venda":"Laudo da venda")+'</div><h1>'+S.code(s)+'</h1>'
      +'<p>eMiner S.A. · vendido à WhatTheChip</p></div>'
      +'<div class="pr__st">'+S.stTag(s)[1]+'<span>emitido em '+TODAY+'/26</span></div></div>'
    +'<div class="pr__cols">'
      +'<div>'+row("Ordem",S.soCode(s))+row("Origem",s.origin==="pcb"?"Placa (PCB)":"Celular")+row("Transportadora",esc(s.carrier||"—"))
        +row("Rastreio",esc(s.track||"—"))+row("Fechado",s.closed)+row("Recebido",s.got||"—")+'</div>'
      +'<div>'+($m?row("Câmbio travado",lockLine()):row("Part numbers",fmt(S.pns(s).length)))
        +row("Enviados",fmt(un)+" un.")+row("Recusados",done()?(rj?"−"+fmt(rj)+" un.":"nenhum"):"—")
        +row("Aprovados",done()?fmt(oku)+" un.":"—")
        +($m?row("Diferença",done()?(d?(d<0?"−":"+")+FX.cny(Math.abs(d)):"sem diferença"):"—")
           :row("Aproveitamento",done()?Math.round(oku/un*100)+"%":"—"))+'</div>'
    +'</div>'
    +($m?'<div class="pr__tot"><div><span>Resultado bruto</span><b>'+(done()?FX.usd(S.grossUsd(s)):"—")+'</b></div>'
      +'<div><span>Serviço '+FEEPCT+'</span><b>'+(done()?"−"+FX.usd(fee):"—")+'</b></div>'
      +'<div class="hi"><span>Líquido</span><b>'+(done()?FX.usd(net):"—")+'</b></div></div>':'')
    +'<h2>'+(done()?"Resultado":"Conteúdo")+' por categoria e capacidade</h2>'
    +'<table class="pr__t"><thead><tr><th>Capacidade</th><th>Caixa WTC</th><th class="n">Enviados</th>'
      +($m?'<th class="n">¥ unit.</th><th class="n">¥ estimado</th>':'')
      +(done()?'<th class="n">Recusados</th><th class="n">Aprovados</th>'+($m?'<th class="n">¥ resultado</th>':''):'')+'</tr></thead>'
      +'<tbody>'+lines+'</tbody>'
      +'<tfoot><tr><td colspan="2">Total</td><td class="n">'+fmt(un)+'</td>'+($m?'<td></td><td class="n">'+FX.cny(c)+'</td>':'')
        +(done()?'<td class="n">'+(rj?"−"+fmt(rj):"0")+'</td><td class="n">'+fmt(oku)+'</td>'+($m?'<td class="n">'+FX.cny(g)+'</td>':''):'')+'</tr></tfoot></table>'
    +($m&&ps.length?'<h2>Repasses</h2><table class="pr__t"><thead><tr><th>Data</th><th>Registro</th><th class="n">US$ recebido</th><th>Referência</th></tr></thead><tbody>'
      +ps.map(function(p,i){return '<tr><td>'+esc(p.d)+'</td><td>'+(p.kind==="full"?(i?"Quitação":"Integral"):"Parcial")+'</td>'
        +'<td class="n">'+FX.usd(p.usd)+'</td><td>'+(p.ref?esc(p.ref.slice(0,10))+"…"+esc(p.ref.slice(-8)):"—")+'</td></tr>';}).join("")
      +'</tbody><tfoot><tr><td colspan="2">Total recebido</td><td class="n">'+FX.usd(pd)+'</td>'
      +'<td>'+(rest?"faltam "+FX.usd(rest):"tudo recebido")+'</td></tr></tfoot></table>':'')
    +(ns.length?'<h2>Observações</h2>'+ns.map(function(x){
        return '<div class="pr__n"><div class="pr__nh">'+esc(x.who)+' · '+esc(x.d)+'</div><p>'+esc(x.t)+'</p></div>';
      }).join(""):'')
    +'<div class="pr__ft">WhatTheChip · '+S.code(s)+($m?' · valores em ¥ (RMB) na taxa travada de '+s.lockD:'')+' · documento gerado em '+TODAY+'/26</div>';
}
/* DOIS DOCUMENTOS, UM CONTÊINER. `prMode` decide qual é montado em #prt, e o beforeprint remonta
   o que estiver selecionado — imprimir pelo atalho do navegador tem de sair igual ao do botão. */
var prMode="result";
function paintPrint(){if(prMode==="ship")buildShip();else buildPrint();}
function printDoc(){prMode="result";paintPrint();window.print();say("Folha da venda pronta para impressão ou PDF.");}
function printShip(){prMode="ship";paintPrint();window.print();
  say(M()?"Folha de embarque pronta — com preço unitário e totais."
        :"Folha de embarque pronta — é a folha que viaja com a caixa.");}
window.addEventListener("beforeprint",paintPrint);

/* ---------- FOLHA DE EMBARQUE ----------
   O que VIAJA COM A CAIXA. Não é a folha do resultado: aqui o assunto é logística e alfândega, e a
   contagem é por CAIXA WTC, que é como o material viaja e como a alfândega conta.

   É UM documento com um gate, não dois: sem preço é a folha do gerente (quantidade, caixas, tipos,
   quem fechou, embarque, declaração aduaneira); com preço é a mesma folha mais ¥ unitário e totais.
   A alternativa — dois documentos — divergiria no primeiro campo novo que alguém acrescentasse. */
function buildShip(){
  var un=S.units(s),c=S.cny(s),boxes=S.byBox(s),$m=M();
  var F=S.SHIPPER,T=S.CONSIGNEE,K=S.CUSTOMS,r=S.rateOf(s);
  function row(l,v){return '<div class="pr__r"><span>'+l+'</span><b>'+v+'</b></div>';}
  function addr(k,a){
    return '<div class="pr__ad"><div class="pr__adk">'+k+'</div>'
      +'<b>'+esc(a.name)+'</b><p>'+esc(a.line1)+'<br/>'+esc(a.city)+' · '+esc(a.country)
      +'<br/>'+esc(a.tax)+'<br/>'+esc(a.contact)+'</p></div>';
  }
  var rows=boxes.map(function(g){
    return '<tr><td>'+esc(g.box)+'</td><td>'+esc(g.typeList.join(" · "))+'</td>'
      +'<td class="n">'+g.rows.length+'</td><td class="n">'+fmt(g.qty)+'</td>'
      +($m?'<td class="n">'+FX.cny(g.cny)+'</td>':'')+'</tr>';
  }).join("");
  /* o valor declarado é o do lote na taxa TRAVADA, e sai em US$ porque é a moeda do documento
     aduaneiro. Sem preço na tela ele continua saindo: declaração aduaneira sem valor não passa na
     alfândega, e este número é obrigação legal, não informação de negócio. */
  var prt=$("prt");
  /* A FOLHA TEM DE SER FILHA DIRETA DO BODY. A regra de impressão esconde tudo com
     `body>*{display:none}` e reabre só `.prt` — mas o viewport.js do protótipo embrulha a página
     em dois divs, então .prt virou neta do body e o !important dela não salvava um descendente de
     ancestral escondido: os três PDFs saíam EM BRANCO. Reancorar aqui, e não na folha de estilo,
     porque CSS não seleciona ancestral — e reancorar a cada montagem, porque o embrulho pode
     voltar quando o enquadramento muda. */
  if(prt.parentElement!==document.body)document.body.appendChild(prt);
  prt.innerHTML='<div class="pr__hd"><div><div class="pr__k">Folha de embarque</div><h1>'+S.code(s)+'</h1>'
      +'<p>'+esc(S.soCode(s))+' · '+(s.origin==="pcb"?"Placa (PCB)":"Celular")+'</p></div>'
      +'<div class="pr__st">'+(s.carrier?"DESPACHADO":"A DESPACHAR")+'<span>emitido em '+TODAY+'/26</span></div></div>'
    +'<div class="pr__two">'+addr("Ship from",F)+addr("Ship to",T)+'</div>'
    +'<div class="pr__cols">'
      +'<div>'+row("Transportadora",esc(s.carrier||"—"))+row("Rastreio",esc(s.track||"—"))
        +row("Enviado",s.ship||"—")+row("Volumes","1 caixa")+'</div>'
      +'<div>'+row("Lote fechado em",s.closed)+row("Caixas WTC",String(boxes.length))
        +row("Peças",fmt(un)+" un.")
        +($m?row("Câmbio travado",lockLine()):row("Part numbers",fmt(S.pns(s).length)))+'</div>'
    +'</div>'
    +'<h2>Declaração aduaneira</h2>'
    +'<div class="pr__cust"><div class="pr__custd">'+esc(K.desc)+'</div>'
      +'<div class="pr__cols">'
        +'<div>'+row("Posição tarifária (HS)",esc(K.hs))+row("Incoterm",esc(K.terms))+'</div>'
        +'<div>'+row("Peças declaradas",fmt(un)+" un.")
          +row("Valor declarado",r?FX.usd(c*r):"sem taxa do dia")+'</div>'
      +'</div>'
      +'<p class="pr__custn">'+esc(K.note)+'</p></div>'
    +'<h2>Conteúdo por caixa WTC</h2>'
    +'<table class="pr__t"><thead><tr><th>Caixa</th><th>Tipos</th><th class="n">Linhas</th>'
      +'<th class="n">Peças</th>'+($m?'<th class="n">¥ estimado</th>':'')+'</tr></thead>'
      +'<tbody>'+rows+'</tbody>'
      +'<tfoot><tr><td colspan="2">Total · '+boxes.length+' caixas</td>'
        +'<td class="n">'+s.lines.length+'</td><td class="n">'+fmt(un)+'</td>'
        +($m?'<td class="n">'+FX.cny(c)+'</td>':'')+'</tr></tfoot></table>'
    +'<div class="pr__sign"><div><span>Fechado por</span><b>'+esc(A_USER())+'</b></div>'
      +'<div><span>Conferido na origem</span><b></b></div>'
      +'<div><span>Recebido no destino</span><b></b></div></div>'
    +'<div class="pr__ft">WhatTheChip · '+S.code(s)+' · '+S.soCode(s)
      +($m?' · valores em ¥ (RMB) na taxa travada de '+s.lockD:'')
      +' · folha de embarque emitida em '+TODAY+'/26</div>';
}
/* quem fechou o lote: vem do papel logado, não de um nome escrito à mão */
function A_USER(){var a=window.WTCAccess&&window.WTCAccess.access();return (a&&a.user)||"—";}

/* ---------- demonstração ---------- */
var DEMO=[["noprice","Falta preço"],["tofreeze","A congelar"],["draft","A despachar"],["transit","A caminho"],
          ["check","A conferir"],["result","Resultado"],["partial","Parcial"],["paid","Recebido"]];
var OKF=[0.94,0.91,0.97,0.88,0.95,0.92,0.96,0.9];
/* datas em DD/MM dentro do mesmo ano: ordenar por mês*100+dia basta */
function dnum(d){var p=String(d||"").split("/");return p.length<2?0:(+p[1])*100+(+p[0]);}
function dadd(d,n){
  var p=String(d).split("/"),t=new Date(2026,+p[1]-1,+p[0]+n);
  return ("0"+t.getDate()).slice(-2)+"/"+("0"+(t.getMonth()+1)).slice(-2);
}
function dmin(a,b){return dnum(a)<=dnum(b)?a:b;}
function dmax(a,b){return dnum(a)>=dnum(b)?a:b;}
/* A cadeia de datas precisa andar sempre para a frente e nunca cair no futuro. A ETA é uma
   promessa, não um fato — usar "chegada prevista" como "recebido em" data o resultado antes
   da chegada. Então: aproveita as datas do registro só quando a cadeia inteira já é coerente;
   caso contrário sintetiza tudo a partir de hoje, para trás. */
var DOFF={transit:{ship:2},check:{ship:7,got:1},result:{ship:9,got:3,done:1},
          partial:{ship:11,got:5,done:3,ok:2},paid:{ship:13,got:7,done:5,ok:4}};
function demoDates(k){
  var o=DOFF[k];if(!o)return {};
  var have={ship:s.ship,got:s.got,done:s.done,ok:s.ok},prev=0,good=true,key;
  ["ship","got","done","ok"].forEach(function(key){
    if(!(key in o)||!good)return;
    var v=have[key];
    if(!v||dnum(v)>dnum(TODAY)||dnum(v)<prev){good=false;return;}
    prev=dnum(v);
  });
  var out={};
  for(key in o)out[key]=good?have[key]:dadd(TODAY,-o[key]);
  /* a data sintetizada conta para trás a partir de hoje e pode cair antes do fechamento do lote.
     O despacho nunca antecede o fechamento — e o resto da cadeia é costurado na leitura. */
  if(out.ship&&s.closed)out.ship=dmax(out.ship,s.closed);
  return out;
}
function demoState(){
  if(s.st==="noprice"||s.st==="tofreeze")return s.st;
  if(s.st==="draft"||s.st==="transit"||s.st==="check"||s.st==="result")return s.st;
  return S.restUsd(s)<=0?"paid":"partial";
}
function applyDemo(k){
  /* Toda etapa a partir de "a despachar" exige lote COTADO e câmbio TRAVADO — é o que a emissão da
     ordem produz. A demo pode saltar de "falta preço" direto para "recebido", então o lote é
     normalizado aqui, uma vez, antes de qualquer conta: sem isso seed[i]*l[4] com preço null dá
     NaN e as parcelas do repasse nascem quebradas. */
  var priced=s.lines.map(function(l){return l[4]==null?[l[0],l[1],l[2],l[3],16]:l;});
  var lk=s.lock||0.1478,lkD=s.lockD||s.closed;
  var seed=(s.res&&s.res.length===priced.length)?s.res:priced.map(function(l,i){return Math.round(l[3]*OKF[i%OKF.length]);});
  /* o repasse é em US$: o bruto em ¥ é congelado em dólar pela taxa travada, e a taxa de serviço
     desta ordem (não a padrão) é descontada ali. As duas parcelas somam o líquido exato. */
  var grossU=Math.round(priced.reduce(function(a,l,i){return a+seed[i]*l[4];},0)*lk*100)/100;
  var net=Math.round((grossU-Math.round(grossU*S.feeOf(s)*100)/100)*100)/100;
  var D=demoDates(k);
  /* repasses saem depois do aceite, nunca antes — e a parcial precisa anteceder a quitação */
  var p1d=D.ok?dmin(dadd(D.ok,2),dadd(TODAY,-1)):dadd(TODAY,-1);
  if(dnum(p1d)<dnum(D.ok||p1d))p1d=D.ok;
  var p1=Math.round(net*0.45*100)/100;
  var pay1={d:p1d,usd:p1,kind:"partial",ref:"6b1f8d3a29c74e05af83b6d1904ce27fa5183bd0e964c7a2318fd54be07a29c6"};
  var pay2={d:TODAY,usd:Math.round((net-p1)*100)/100,kind:"full",ref:"18d5c93b6072af41e8b3560c92d7ae14fb039c85217de6a4903bf172c5d840e9"};
  var car=s.carrier||"DHL",trk=s.track||"4721 8899 001";
  /* base comum: lote cotado e câmbio travado. Os dois primeiros estados a DESFAZEM — é justamente
     isso que eles são: a ordem ainda não foi emitida. */
  var ok={lines:priced,lock:lk,lockD:lkD};
  function st(o){var r={},k2;for(k2 in ok)r[k2]=ok[k2];for(k2 in o)r[k2]=o[k2];return r;}
  var P={
    noprice:{st:"noprice",lock:null,lockD:"",carrier:null,track:null,ship:null,eta:null,got:null,done:null,ok:null,res:null,pays:null,
      /* o preço de uma caixa é apagado: sem isso o estado existiria sem a sua causa */
      lines:priced.map(function(l,i){return i===1?[l[0],l[1],l[2],l[3],null]:l;})},
    tofreeze:{st:"tofreeze",lock:null,lockD:"",lines:priced,carrier:null,track:null,ship:null,eta:null,got:null,done:null,ok:null,res:null,pays:null},
    draft:st({st:"draft",carrier:null,track:null,ship:null,eta:null,got:null,done:null,ok:null,res:null,pays:null}),
    transit:st({st:"transit",carrier:car,track:trk,ship:D.ship,eta:dadd(TODAY,5),got:null,done:null,ok:null,res:null,pays:null}),
    check:st({st:"check",carrier:car,track:trk,ship:D.ship,eta:D.got,got:D.got,done:null,ok:null,res:null,pays:null}),
    result:st({st:"result",carrier:car,track:trk,ship:D.ship,eta:D.got,got:D.got,done:D.done,ok:null,res:seed,pays:null}),
    partial:st({st:"topay",carrier:car,track:trk,ship:D.ship,eta:D.got,got:D.got,done:D.done,ok:D.ok,res:seed,pays:[pay1]}),
    paid:st({st:"paid",carrier:car,track:trk,ship:D.ship,eta:D.got,got:D.got,done:D.done,ok:D.ok,res:seed,pays:[pay1,pay2]})
  };
  S.patch(s.n,P[k]);s=S.get(s.n);tab=null;paint();
  say("Demo · venda "+S.code(s)+" agora está em “"+DEMO.filter(function(x){return x[0]===k;})[0][1]+"”.");
}
function demobar(){
  var cur=demoState();
  $("demobar").innerHTML='<span class="demobar__l"><i></i>Demo · estado da venda</span>'
    +DEMO.map(function(x){return '<button type="button" data-d="'+x[0]+'"'+(x[0]===cur?' class="on"':'')+'>'+x[1]+'</button>';}).join("")
    +'<span class="demobar__sp"></span><button type="button" id="demo-r" class="demobar__r">Restaurar dados originais</button>';
  Array.prototype.forEach.call($("demobar").querySelectorAll("[data-d]"),function(el){
    el.onclick=function(){applyDemo(el.getAttribute("data-d"));};
  });
  $("demo-r").onclick=function(){S.reset(s.n);s=S.get(s.n);tab=null;paint();say("Dados originais restaurados.");};
}

function paint(){statusbar();actions();sheetHd();fields();nb();body();demobar();paintPrint();}

$("ship-x").onclick=closeShip;
$("ship-scrim").onclick=function(e){if(e.target===$("ship-scrim"))closeShip();};
$("acc-x").onclick=closeAcc;
$("acc-scrim").onclick=function(e){if(e.target===$("acc-scrim"))closeAcc();};
$("acc-ok").onclick=function(){
  S.patch(s.n,{st:"topay",ok:TODAY});s=S.get(s.n);tab=M()?"pays":"lines";closeAcc();paint();
  say(M()?"Resultado aceito · "+FX.usd(S.netUsd(s))+" liberados para repasse."
        :"Resultado aceito · repasse liberado para a conta da empresa.");
};
document.addEventListener("keydown",function(e){if(e.key==="Escape"){closeShip();closeAcc();}});

function fx(){
  var st=FX.state();
  if($("fxr"))$("fxr").textContent=st.has?("1 ¥ ≈ US$ "+st.rate.toFixed(4)):"sem taxa do dia";
  paint();
}
FX.onChange(fx);paint();
})();
