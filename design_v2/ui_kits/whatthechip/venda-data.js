/* WhatTheChip — VENDAS do cliente. É a mesma ficha da compra, vista do outro lado do balcão:
   o cliente fecha o lote, despacha e espera um RESULTADO. Quem confere é a plataforma — o
   cliente nunca vê o comprador, nunca vê para quem foi revendido, nunca vê a margem. Ele vê
   o que mandou, o que passou, quanto rendeu e quando cai na conta.

   Etapas: Fechado → Enviado → Recebido → Resultado → Pagamento
   Estados: draft (fechado, a despachar) → transit → check (recebida pelo comprador, em
            conferência) → result (resultado publicado, a aceitar) → topay (aceito, a receber)
            → paid (repassado).
   Linha = [tipo, capacidade, caixa WTC, qtd, preço unit ¥ da tabela].
   `lot` é o número do lote que este registro vira no Estoque. O vínculo existe desde o começo,
   mas só vale depois que a caixa CHEGA (`got`): antes disso não há bancada para abrir.

   PERNA 2 DO DINHEIRO (briefing v2, 19/08): o WhatTheChip paga o cliente, retendo a taxa de
   serviço. O repasse é em **US$** — o preço congelado no fechamento é em US$, e travar o câmbio
   é justamente o ato de definir esse dólar. O ¥ continua sendo a origem (a tabela do comprador),
   e por isso os dois aparecem no mesmo corpo.
   O que o cliente NÃO vê, nunca: o nome do comprador, a perna 1 (comprador → WhatTheChip), e
   comprovante de repasse — repasse tem data, valor e referência, e mais nada. */
(function(){
"use strict";

/* a taxa de serviço é por EMPRESA (o contrato é por cliente e dá para negociar outro percentual)
   e CONGELA na emissão, como o câmbio: mudar o cadastro não reescreve venda já acertada. Por isso
   cada registro carrega o seu `fee`; este é só o padrão de quem não tem contrato próprio. */
var FEE=0.10;
function feeOf(s){return s&&s.fee!=null?s.fee:FEE;}
function feePct(s){return Math.round(feeOf(s)*1000)/10+"%";}

/* conta de repasse do cliente: para onde a plataforma manda o dinheiro */
var PAYEE={owner:"eMiner S.A.",net:"USDT · TRC-20",addr:"TJ7kR2nVc8Ld5XbMpQs4WnFeA9uZy3GxHt"};

/* ---------- DOCUMENTO DE EMBARQUE ----------
   Remetente e destinatário da caixa. O SHIP TO é a única exceção sancionada ao segredo de mercado:
   ele mostra o DESTINATÁRIO logístico — armazém alfandegado da plataforma —, nunca o comprador.
   A caixa precisa de um endereço para viajar; o cliente não precisa de um nome para saber a quem
   vendeu, e continua não sabendo. */
var SHIPPER={name:"eMiner S.A.",line1:"Av. Artigas 3120, Galpão 4",city:"Assunção",
  country:"Paraguai",tax:"RUC 80012345-7",contact:"logistica@eminer.com.py"};
var CONSIGNEE={name:"WhatTheChip Logistics",line1:"Bonded Warehouse 3, Futian Free Trade Zone",
  city:"Shenzhen",country:"China",tax:"USCI 91440300MA5F1K2X8N",contact:"inbound@whatthechip.com"};
/* declaração aduaneira: a descrição é fixa e é ela que classifica a carga na alfândega — não é
   texto de tela, é o que vai no formulário. O valor declarado é o do lote na taxa travada. */
var CUSTOMS={desc:"PCB CHIPS FOR DISPOSAL",hs:"8548.10",terms:"DAP",
  note:"Recovered electronic components for material reclamation. No commercial resale value declared beyond stated amount."};

var SALES=[
 /* ANTES DA CONFIRMAÇÃO existem dois estados que o cliente vê e não pode resolver. Nos dois o
    câmbio ainda NÃO está travado (lock null), então o valor é estimativa viva, com ≈ — é
    re-resolvido contra a tabela do comprador a cada leitura.
      falta preço → o comprador não cotou uma das caixas do lote; sem preço não há ordem.
      a congelar  → tudo cotado, o sistema fecha o câmbio e emite a ordem sozinho. */
 {n:134,so:146,fee:0.10,desc:"Placas mistas — coleta Assunção",origin:"pcb",closed:"01/08",st:"noprice",lot:45,lock:null,lockD:"",
  lines:[["DDR4","4GB","C-018",280,16],["DDR5","16GB","C-026",40,null],["eMMC","64GB","C-005",190,26]]},
 {n:133,so:145,fee:0.10,desc:"Celulares recolhidos — turno tarde",origin:"phone",closed:"01/08",st:"tofreeze",lot:46,lock:null,lockD:"",
  lines:[["eMMC","32GB","C-014",340,15],["LPDDR4X","4GB","C-031",140,40],["eMCP","64GB","C-007",90,68]]},
 {n:132,so:144,fee:0.10,desc:"Celulares recolhidos — coleta Assunção",origin:"phone",closed:"31/07",st:"draft",lot:44,lock:0.1478,lockD:"31/07",
  lines:[["eMMC","32GB","C-014",380,15],["eMMC","64GB","C-014",240,26],["LPDDR4X","4GB","C-031",160,40],["eMCP","64GB","C-007",120,68]]},
 {n:131,so:143,fee:0.10,desc:"Placas de servidor — sucata Jul/2026",origin:"pcb",closed:"29/07",carrier:"DHL",track:"4721 8901 233",ship:"30/07",eta:"06/08",st:"transit",lot:43,lock:0.1478,lockD:"29/07",
  lines:[["DDR4","4GB","C-018",320,16],["DDR4","8GB","C-018",180,28],["DDR5","8GB","C-026",60,44],["eMMC","16GB","C-005",440,11]]},
 {n:130,so:140,fee:0.10,desc:"Celulares recolhidos — lote misto",origin:"phone",closed:"26/07",carrier:"FedEx",track:"7794 2255 1180",ship:"27/07",eta:"03/08",st:"check",got:"02/08",lot:42,lock:0.1478,lockD:"26/07",
  lines:[["eMMC","64GB","C-014",290,26],["LPDDR4","3GB","C-031",210,26],["uMCP","128GB","C-007",80,120]]},
 {n:129,so:137,fee:0.10,desc:"Recuperação placas — memória DDR3",origin:"pcb",closed:"21/07",carrier:"DHL",track:"4721 8776 049",ship:"22/07",eta:"29/07",st:"result",got:"29/07",done:"31/07",lot:40,lock:0.1502,lockD:"21/07",
  lines:[["DDR3","2GB","C-009",620,6],["DDR3","4GB","C-009",360,11],["DDR4","4GB","C-018",280,16],["eMMC","32GB","C-005",340,15]],
  res:[571,338,271,318],
  notes:[{d:"31/07/26",who:"WhatTheChip · Conferência",t:"Diferença de 1.010 ¥ sobre o estimado, concentrada em DDR3 4GB (22 recusas por corrosão de contato). Fotos das peças recusadas disponíveis mediante pedido."}]},
 {n:128,so:133,fee:0.10,desc:"Celulares recolhidos — turno noite",origin:"phone",closed:"14/07",carrier:"SF Express",track:"SF13 9088 2140",ship:"15/07",eta:"22/07",st:"topay",got:"22/07",done:"24/07",ok:"25/07",lot:39,lock:0.1478,lockD:"14/07",
  lines:[["eMMC","32GB","C-014",460,15],["eMMC","128GB","C-014",110,44],["LPDDR4X","6GB","C-031",150,58]],
  res:[441,101,138],
  pays:[{d:"28/07",usd:739.00,kind:"partial",ref:"6b1f8d3a29c74e05af83b6d1904ce27fa5183bd0e964c7a2318fd54be07a29c6"}],
  notes:[{d:"24/07/26",who:"WhatTheChip · Conferência",t:"LPDDR4X 6GB com 12 peças fora de especificação — velocidade abaixo do declarado na leitura de bancada. Recusadas."}]},
 {n:127,so:130,fee:0.10,desc:"Compra Jun/2026 — Lote B",origin:"pcb",closed:"03/07",carrier:"EMS",track:"EE4720 1204 8BR",ship:"04/07",eta:"11/07",st:"paid",got:"11/07",done:"13/07",ok:"14/07",lot:38,lock:0.1502,lockD:"03/07",
  lines:[["DDR3","4GB","C-009",520,11],["eMMC","16GB","C-005",610,11],["eMMC","32GB","C-005",280,15]],
  res:[489,566,266],
  pays:[{d:"16/07",usd:901.20,kind:"partial",ref:"c07e4a195d2b83f6017ae94c3b52d8016fe7a2394cb15d80e6f293a7b41c5d02"},
        {d:"23/07",usd:1206.93,kind:"full",ref:"18d5c93b6072af41e8b3560c92d7ae14fb039c85217de6a4903bf172c5d840e9"}],
  notes:[{d:"13/07/26",who:"WhatTheChip · Conferência",t:"Recusas concentradas em DDR3 2GB: 31 peças com pinos oxidados e 18 com marcação ilegível após limpeza. As demais capacidades vieram dentro do padrão do fornecedor."},
         {d:"13/07/26",who:"WhatTheChip · Conferência",t:"eMMC 16GB acima da média histórica de aproveitamento — 93% aprovadas. Lote bem separado na origem."}]},
 {n:126,so:127,fee:0.10,desc:"Celulares recolhidos — coleta junho",origin:"phone",closed:"18/06",carrier:"DHL",track:"4721 8302 667",ship:"19/06",eta:"26/06",st:"paid",got:"26/06",done:"28/06",ok:"28/06",lot:41,lock:0.1478,lockD:"18/06",
  lines:[["eMMC","32GB","C-014",400,15],["LPDDR4X","4GB","C-031",180,40]],
  res:[382,171],
  pays:[{d:"02/07",usd:1672.06,kind:"full",ref:"3f92a7c15be804d63927ca0f81b5d4e720ac6913f85b2d07e491c3a6708db245"}]}
];

/* PNs do lote: o que a triagem do próprio cliente identificou, peça por peça */
var PN={
 "eMMC":[["Samsung","KLM#G1JETD-B041","eMMC 5.1 · HS400 · BGA153"],["SK hynix","H26M#1103BMR","eMMC 5.1 · HS400 · BGA153"],
         ["Kioxia","THGBMNG#C8LBAIL","eMMC 5.1 · HS400 · BGA153"],["Micron","MTFC#GAKAJCN-1M","eMMC 5.1 · HS400 · BGA153"]],
 "LPDDR4X":[["Samsung","K4U#E3S4AB-MGCL","LPDDR4X · 4266 Mbps · FBGA200"],["SK hynix","H9HCNNN#PUMLHR","LPDDR4X · 4266 Mbps · FBGA200"]],
 "LPDDR4":[["Samsung","K4F#E304HB-MGCJ","LPDDR4 · 3733 Mbps · FBGA200"],["SK hynix","H9HCNNN#BPUMLHR","LPDDR4 · 3733 Mbps · FBGA200"]],
 "DDR3":[["Samsung","K4B#G1646E-BCMA","DDR3L · 1600 MT/s · FBGA96 · ×16"],["SK hynix","H5TQ#G63EFR-PBC","DDR3L · 1600 MT/s · FBGA96 · ×16"],
         ["Nanya","NT5CC#M16FP-DI","DDR3L · 1600 MT/s · FBGA96 · ×16"]],
 "DDR4":[["Samsung","K4A#G165WC-BCTD","DDR4 · 2666 MT/s · FBGA96 · ×16"],["SK hynix","H5AN#G8NAJR-VKC","DDR4 · 2666 MT/s · FBGA96 · ×16"],
         ["Micron","MT40A#M16TB-062","DDR4 · 2666 MT/s · FBGA96 · ×16"]],
 "DDR5":[["Samsung","K4RAH#56VB-BCQK","DDR5 · 4800 MT/s · FBGA · ×16"],["SK hynix","H5CG#MEBDX014","DDR5 · 4800 MT/s · FBGA · ×16"]],
 "eMCP":[["Samsung","KMDH#000DA-B425","eMCP · eMMC 5.1 + LPDDR3 · BGA221"],["SK hynix","H9TQ#ABJTMCUR","eMCP · eMMC 5.1 + LPDDR3 · BGA221"]],
 "uMCP":[["Samsung","KMDV#000DM-B426","uMCP · UFS 2.1 + LPDDR4X · BGA221"],["SK hynix","H9HQ#ANBMAD","uMCP · UFS 2.1 + LPDDR4X · BGA221"]]
};
var HEX="0123456789ABCDEF";
function seeded(s){var x=s;return function(){x=(x*1103515245+12345)&0x7fffffff;return x/0x7fffffff;};}
function pns(s){
  var out=[];
  s.lines.forEach(function(l,i){
    var pool=PN[l[0]]||PN["eMMC"],rnd=seeded(s.n*811+i*137+3);
    var k=Math.min(pool.length,1+Math.floor(rnd()*3)),left=l[3];
    for(var j=0;j<k;j++){
      var p=pool[(Math.floor(rnd()*pool.length)+j)%pool.length];
      var qty=j===k-1?left:Math.max(1,Math.round(l[3]*(0.24+rnd()*0.38)));
      if(qty>left)qty=left;left-=qty;
      if(qty<=0)continue;
      var tag="";for(var h=0;h<4;h++)tag+=HEX[Math.floor(rnd()*16)];
      out.push({pn:p[1].replace("#",tag),make:p[0],spec:p[2]+" · "+l[1],type:l[0],cap:l[1],wtc:l[2],qty:qty,unit:l[4],line:i});
    }
  });
  return out;
}

var K="wtc_sales";
function load(){try{return JSON.parse(localStorage.getItem(K)||"{}");}catch(e){return {};}}
function save(o){try{localStorage.setItem(K,JSON.stringify(o));}catch(e){}}
var TODAY="02/08";
function dnum(d){var p=String(d||"").split("/");return p.length<2?0:(+p[1])*100+(+p[0]);}
/* A cadeia despacho → chegada → resultado → aceite → repasse só faz sentido andando para a
   frente, e nada dela pode estar no futuro: um resultado datado antes da chegada é leitura
   impossível. Overrides gravados por versões anteriores podem conter isso, então a cadeia é
   costurada na leitura — o defeito se conserta sozinho em vez de ficar preso no navegador. */
function heal(c){
  /* ESTADO ANTES DA CONFIRMAÇÃO NÃO TEM DESPACHO: a ordem não foi emitida, então a caixa não saiu.
     Override gravado antes destes dois estados existirem pode ter transportadora e data de envio
     junto com "falta preço" — e aí o trilho mostra "Enviado" num registro que ainda espera cotação. */
  if(c.st==="noprice"||c.st==="tofreeze"){c.carrier=null;c.track=null;c.ship=null;c.eta=null;}
  /* O PRIMEIRO ELO É O FECHAMENTO, não o despacho: quatro vendas apareciam despachadas ANTES de
     serem fechadas (lote 01/08, envio 31/07), porque a costura começava em `ship` e nunca olhava
     `closed`. Um lote que sai antes de existir é leitura impossível como qualquer outra. */
  if(c.ship&&dnum(c.ship)>dnum(TODAY))c.ship=TODAY;
  if(c.ship&&c.closed&&dnum(c.ship)<dnum(c.closed))c.ship=c.closed;
  var prev=c.ship||c.closed;
  ["got","done","ok"].forEach(function(k){
    if(!c[k])return;
    if(dnum(c[k])>dnum(TODAY))c[k]=TODAY;
    if(prev&&dnum(c[k])<dnum(prev))c[k]=prev;
    prev=c[k];
  });
  if(c.pays&&c.pays.length){
    var p=prev,lock=c.lock||0;
    c.pays=c.pays.map(function(x){
      var y={},k;
      for(k in x)y[k]=x[k];
      if(dnum(y.d)>dnum(TODAY))y.d=TODAY;
      if(p&&dnum(y.d)<dnum(p))y.d=p;
      p=y.d;
      /* FORMATO do lançamento, não só a data: versões anteriores gravaram o repasse em ¥
         ({cny, tx, file}) e o saldo passou a ser em US$ ({usd, ref}). Sem costurar isto na
         leitura, paidUsd soma undefined — a aba imprime NaN, o rodapé diz "US$ 0,00 recebidos"
         e uma venda quitada volta a dizer "RECEBIDO EM PARTE". Converte pela taxa TRAVADA do
         registro (é ela que definiu o dólar), renomeia tx→ref e descarta o comprovante, que na
         perna do cliente não existe. */
      if(y.usd==null&&y.cny!=null){y.usd=Math.round(y.cny*lock*100)/100;y.conv=1;}
      if(y.ref==null&&y.tx!=null)y.ref=y.tx;
      delete y.cny;delete y.tx;delete y.file;
      return y;
    });
    /* uma parcela marcada `full` significa "esta fechou o saldo". As parcelas legadas foram
       gravadas em ¥ arredondado, então a conversão para dólar deixa uma sobra de centavos e o
       registro passa a dizer "RECEBIDO EM PARTE" faltando US$ 47,90. Migrar é preservar o que o
       lançamento SIGNIFICAVA, não só a aritmética: a última parcela integral absorve a sobra.
       Só mexe em lançamento convertido (`conv`) — parcela nativa em US$ é dado, e dado não se
       ajusta para caber. */
    var lastC=c.pays[c.pays.length-1];
    if(lastC&&lastC.conv&&lastC.kind==="full"){
      var gap=Math.round((netUsd(c)-paidUsd(c))*100)/100;
      if(gap!==0&&lastC.usd+gap>0)lastC.usd=Math.round((lastC.usd+gap)*100)/100;
    }
    c.pays.forEach(function(x){delete x.conv;});
  }
  return c;
}
function all(){
  var ov=load();
  return SALES.map(function(s){
    var o=ov[s.n];if(!o)return s;
    var c={},k;for(k in s)c[k]=s[k];
    for(k in o){if(o[k]===null)delete c[k];else c[k]=o[k];}
    return heal(c);
  });
}
function get(n){return all().filter(function(s){return s.n===+n;})[0];}
function patch(n,o){var ov=load();ov[n]=Object.assign({},ov[n]||{},o);save(ov);}
function reset(n){var ov=load();delete ov[n];save(ov);}

function code(s){return "LOT/"+("00"+s.n).slice(-3)+"/"+(s.closed.split("/")[1])+"/26";}
/* ordem de venda: nasce no fechamento, com o preço da tabela do comprador e o câmbio travado
   naquele instante. O LOT é o objeto da caixa; a OV é o objeto do dinheiro. */
function soCode(s){return "SO/"+("000"+s.so).slice(-4)+"/"+(s.closed.split("/")[1])+"/26";}
function soDate(s){return s.closed;}
function rateOf(s){return s.lock||window.WTCFX.rate()||0;}
function r2(v){return Math.round(v*100)/100;}
function units(s){return s.lines.reduce(function(a,l){return a+l[3];},0);}
/* preço unitário null = a caixa não foi cotada. Some como zero na conta (não há o que somar) mas
   NUNCA silenciosamente: noPrice() é o que faz a tela dizer que o total está incompleto. Tratar
   null como 0 sem contar as linhas transformaria uma estimativa furada num número confiante. */
function cny(s){return s.lines.reduce(function(a,l){return a+l[3]*(l[4]||0);},0);}
function noPrice(s){return s.lines.filter(function(l){return l[4]==null;}).length;}
/* a ordem só existe depois de tudo cotado e do câmbio travado */
function confirmed(s){return s.st!=="noprice"&&s.st!=="tofreeze";}
/* o resultado só existe depois da conferência; antes dela o que há é estimativa */
function hasRes(s){return s.st==="result"||s.st==="topay"||s.st==="paid";}
function okUnits(s){return (s.res||[]).reduce(function(a,v){return a+(v||0);},0);}
function grossCny(s){return s.lines.reduce(function(a,l,i){return a+((s.res&&s.res[i]!=null?s.res[i]:0)*l[4]);},0);}
function feeCny(s){return grossCny(s)*feeOf(s);}
function netCny(s){return grossCny(s)-feeCny(s);}
/* o repasse é em US$: o resultado nasce em ¥ (tabela do comprador) e é congelado em dólar pela
   taxa travada no fechamento. O ¥ segue como leitura conciliável; o saldo se resolve em US$,
   porque é em US$ que o dinheiro sai da conta do WhatTheChip. */
function grossUsd(s){return r2(grossCny(s)*rateOf(s));}
function feeUsd(s){return r2(grossUsd(s)*feeOf(s));}
function netUsd(s){return r2(grossUsd(s)-feeUsd(s));}
function paidUsd(s){return r2((s.pays||[]).reduce(function(a,p){return a+(p.usd||0);},0));}
/* arredonda no centavo: sem isso um resto de 3,6e-12 faz uma venda quitada dizer "em parte" */
function restUsd(s){return Math.max(0,r2(netUsd(s)-paidUsd(s)));}
function paidCny(s){var r=rateOf(s);return r?Math.round(paidUsd(s)/r):0;}
function restCny(s){var r=rateOf(s);return r?Math.round(restUsd(s)/r):0;}
function paidPct(s){var d=netUsd(s);return d?Math.min(100,paidUsd(s)/d*100):0;}
/* agrupa por CAIXA WTC — é assim que o material viaja e é assim que a alfândega conta: uma caixa,
   uma linha, com os tipos que ela contém. A folha de embarque não é a planilha do resultado. */
function byBox(s){
  var m={},order=[];
  s.lines.forEach(function(l,i){
    if(!m[l[2]]){m[l[2]]={box:l[2],qty:0,cny:0,types:{},rows:[]};order.push(l[2]);}
    var g=m[l[2]];
    g.qty+=l[3];g.cny+=l[3]*(l[4]||0);g.types[l[0]]=1;
    g.rows.push({i:i,t:l[0],cap:l[1],qty:l[3],unit:l[4]});
  });
  return order.map(function(k){
    var g=m[k];g.typeList=Object.keys(g.types);return g;
  });
}
function byType(s){
  var m={},order=[];
  s.lines.forEach(function(l,i){
    if(!m[l[0]]){m[l[0]]={t:l[0],qty:0,cny:0,rows:[]};order.push(l[0]);}
    m[l[0]].qty+=l[3];m[l[0]].cny+=l[3]*l[4];m[l[0]].rows.push({i:i,cap:l[1],wtc:l[2],qty:l[3],unit:l[4]});
  });
  return order.map(function(k){return m[k];});
}
/* "A CONFERIR" e não "EM CONFERÊNCIA": é o mesmo vocabulário dos seis estados da lista, e é o
   que o crachá do cliente passa a dizer quando o comprador marca o recebimento. A frase inteira
   — "recebida pelo comprador" — vive no trilho e na caixa de etapa, onde há largura para ela;
   a pastilha fica com uma ou duas palavras, como todas as outras do sistema. */
var ST={noprice:["tag--maybe","FALTA PREÇO"],tofreeze:["tag--info","A CONGELAR"],
        draft:["tag--mute","A DESPACHAR"],transit:["tag--info","A CAMINHO"],check:["tag--maybe","A CONFERIR"],
        result:["tag--due","A ACEITAR"],topay:["tag--due","A RECEBER"],paid:["tag--yes","RECEBIDO"]};
/* QUEM deve o próximo passo. É isto que decide se a linha da lista chama ou não: a pastilha de
   chamada vale só para quem está OLHANDO. Ato do outro lado do balcão é ESTADO, e estado é
   neutro — a mesma linha não pode gritar para os dois lados.
   'kind' é a natureza do ato, não quem o faz: box = ato sobre a caixa (azul), money = ato sobre
   dinheiro (âmbar, o mesmo de todo saldo em aberto). */
var ACT={
  noprice: {who:"comprador",  kind:"",      label:""},
  tofreeze:{who:"sistema",    kind:"",      label:""},
  draft:   {who:"cliente",    kind:"box",   label:"DESPACHAR"},
  transit: {who:"comprador",  kind:"",      label:""},
  check:   {who:"comprador",  kind:"",      label:""},
  result:  {who:"cliente",    kind:"money", label:"ACEITAR"},
  topay:   {who:"plataforma", kind:"",      label:""},
  paid:    {who:"",           kind:"",      label:""}
};
function actor(s){return (ACT[s.st]||ACT.paid).who;}
/* devolve o ato SÓ quando é do cliente — quem olha esta lista. Nos outros casos a linha fica com
   a pastilha de estado, e o `title` dela diz de quem é a bola. */
function act(s){var a=ACT[s.st];return a&&a.who==="cliente"&&a.label?a:null;}
var WAIT={comprador:"aguardando o comprador",sistema:"o sistema resolve sozinho",
          plataforma:"aguardando o repasse da plataforma",cliente:"sua vez","":"encerrado"};
function waiting(s){return WAIT[actor(s)]||"";}
function stTag(s){
  /* a etiqueta diz o ESTADO, nunca o quanto: porcentagem é dado de ficha, não de selo.
     E saldo em aberto manda mais que o estado: nunca dizemos RECEBIDO com repasse faltando. */
  /* uma ou duas palavras, como toda pastilha deste sistema: "RECEBIDO EM PARTE" fazia a coluna
     Status medir 181px e empurrava a si mesma para fora da tela nas telas médias. */
  if(s.st==="topay"&&paidUsd(s)>0)return ["tag--due","PARCIAL"];
  if(s.st==="paid"&&restUsd(s)>0)return ["tag--due","PARCIAL"];
  return ST[s.st];
}
/* o que o cliente precisa fazer agora — vazio quando a bola está com a plataforma */
function todo(s){
  if(s.st==="draft")return "despachar";
  if(s.st==="result")return "aceitar";
  /* falta preço e a congelar NÃO entram: a bola é do comprador e do sistema. Contá-las como
     pendência do cliente encheria a badge dele de coisa que ele não pode fazer. */
  return "";
}

window.WTCSales={all:all,get:get,patch:patch,reset:reset,code:code,soCode:soCode,soDate:soDate,
  units:units,cny:cny,pns:pns,rateOf:rateOf,
  byType:byType,hasRes:hasRes,okUnits:okUnits,grossCny:grossCny,feeCny:feeCny,netCny:netCny,
  grossUsd:grossUsd,feeUsd:feeUsd,netUsd:netUsd,paidUsd:paidUsd,restUsd:restUsd,
  noPrice:noPrice,confirmed:confirmed,actor:actor,act:act,waiting:waiting,ACT:ACT,
  byBox:byBox,SHIPPER:SHIPPER,CONSIGNEE:CONSIGNEE,CUSTOMS:CUSTOMS,
  paidCny:paidCny,restCny:restCny,paidPct:paidPct,ST:ST,stTag:stTag,todo:todo,
  FEE:FEE,feeOf:feeOf,feePct:feePct,PAYEE:PAYEE,
  pending:function(){return all().filter(function(s){return todo(s);}).length;}};
})();
