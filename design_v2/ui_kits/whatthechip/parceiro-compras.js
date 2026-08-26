/* WhatTheChip — COMPRAS do parceiro: lotes que o vendedor fechou E despachou (só ENVIADO aparece).
   Transportadora e código de rastreio são campos separados — pode ser DHL, FedEx, UPS, SF Express
   ou EMS.
   Estados: transit (a caminho) → received (chegou, a conferir) → settled (FATURADO, a pagar) →
   paid (quitado). Linha do lote = [tipo, capacidade, caixa WTC, qtd, preço unit ¥]. O resultado é
   lançado por LINHA, nunca por chip individual.

   TRÊS ATORES, DUAS PERNAS DE DINHEIRO (briefing v2, 19/08):

     comprador ──paga o TOTAL CHEIO──▶ WhatTheChip ──paga o LÍQUIDO──▶ cliente
                                          (retém taxa de serviço)

   Este arquivo é só a PERNA 1. O comprador não paga o vendedor: paga o WhatTheChip, e a carteira
   de destino é do WhatTheChip. A perna 2 (repasse ao cliente, menos a taxa) vive na superfície do
   cliente e não aparece aqui — nem o valor, nem a data, nem a existência dela.
   A taxa de serviço TAMBÉM não aparece aqui: ela não encolhe o que o comprador deve, e mostrá-la
   na tela dele vazaria a margem da plataforma.

   A PERNA 1 É EM US$ — é a moeda em que ele paga. O resultado é fechado em ¥ (o preço é da tabela
   dele, em ¥) e convertido pela taxa TRAVADA do lote. Por isso o devido nasce em ¥, o pago nasce
   em US$, e o saldo se resolve em US$ com o ¥ como leitura conciliável. */
(function(){
"use strict";

/* carteira única do WhatTheChip — todo pagamento de compra sai do comprador e entra aqui.
   NÃO é a carteira do vendedor: o comprador nunca paga o cliente direto. */
var WALLET={owner:"WhatTheChip Ltd.",net:"USDT · TRC-20",addr:"TQ9fH4mVx2Kd7YbLpJs3RnAeW6cUz8gXqN",
  memo:"coloque o código da ordem (SO) no campo de memo/referência"};

/* transportadoras com página de rastreio conhecida: a LISTA mora em fx.js, porque as duas fichas
   — a da compra e a da venda — mostram o mesmo código, e duas listas divergiriam sem avisar. */
function trackUrl(b){return window.WTCFX.trackUrl(b.carrier,b.track);}

/* LINHA DO LOTE — campos nomeados, não posições.
   Era `[tipo, capacidade, caixa, qtd, preço]`, e a marca entrou no meio disso. Índice trocado não
   dá erro: dá número errado, calado. Com nome, um campo que falta aparece como undefined na hora.

   Granularidade: marca × tipo × capacidade × caixa. É a marca que abre o grupo na planilha de
   conferência, porque é por marca que o comprador separa o material na bancada — o preço continua
   vindo da CAIXA, então a mesma capacidade em duas marcas pode ter o mesmo ¥ e ainda assim ser
   conferida separada. */
var BUYS=[
 {n:49,so:142,origin:"phone",seller:"eMiner",city:"Assunção",country:"Paraguai",closed:"28/07",ship:"29/07",eta:"05/08",
  carrier:"DHL",track:"4721 8834 990",st:"transit",lock:0.1478,lockD:"28/07",
  lines:[{mk:"Samsung",t:"eMMC",cap:"32GB",box:"C-014",qty:240,unit:15},
         {mk:"SK hynix",t:"eMMC",cap:"32GB",box:"C-014",qty:180,unit:15},
         {mk:"Samsung",t:"eMMC",cap:"64GB",box:"C-014",qty:260,unit:26},
         {mk:"Kioxia",t:"eMMC",cap:"128GB",box:"C-014",qty:90,unit:44},
         {mk:"Samsung",t:"LPDDR4X",cap:"4GB",box:"C-031",qty:110,unit:40},
         {mk:"Micron",t:"LPDDR4X",cap:"4GB",box:"C-031",qty:70,unit:40},
         {mk:"Samsung",t:"LPDDR4X",cap:"6GB",box:"C-031",qty:120,unit:58},
         {mk:"Samsung",t:"eMCP",cap:"64GB",box:"C-007",qty:210,unit:68},
         {mk:"Samsung",t:"UFS 2.1",cap:"64GB",box:"C-022",qty:140,unit:34}]},
 {n:48,so:141,origin:"pcb",seller:"RecycleSur",city:"Montevidéu",country:"Uruguai",closed:"27/07",ship:"28/07",eta:"04/08",
  carrier:"FedEx",track:"7794 2210 5583",st:"transit",lock:0.1502,lockD:"27/07",
  lines:[{mk:"Samsung",t:"DDR3",cap:"2GB",box:"C-009",qty:400,unit:6},
         {mk:"Nanya",t:"DDR3",cap:"2GB",box:"C-009",qty:240,unit:6},
         {mk:"SK hynix",t:"DDR3",cap:"4GB",box:"C-009",qty:380,unit:11},
         {mk:"Samsung",t:"DDR4",cap:"4GB",box:"C-018",qty:290,unit:16},
         {mk:"Micron",t:"DDR4",cap:"8GB",box:"C-018",qty:150,unit:28},
         {mk:"Samsung",t:"eMMC",cap:"16GB",box:"C-005",qty:510,unit:11}]},
 {n:47,so:139,origin:"phone",seller:"eMiner",city:"Assunção",country:"Paraguai",closed:"25/07",ship:"26/07",eta:"02/08",
  carrier:"DHL",track:"4721 8712 407",st:"transit",lock:0.1478,lockD:"25/07",
  lines:[{mk:"Samsung",t:"eMMC",cap:"64GB",box:"C-014",qty:310,unit:26},
         {mk:"SK hynix",t:"LPDDR4",cap:"3GB",box:"C-031",qty:240,unit:26},
         {mk:"Samsung",t:"uMCP",cap:"128GB",box:"C-007",qty:95,unit:120}]},
 {n:46,so:136,origin:"pcb",seller:"Andes Metals",city:"Santiago",country:"Chile",closed:"18/07",ship:"19/07",eta:"26/07",
  carrier:"SF Express",track:"SF13 9024 7781",st:"received",got:"26/07",lock:0.1478,lockD:"18/07",
  lines:[{mk:"Samsung",t:"DDR4",cap:"4GB",box:"C-018",qty:250,unit:16},
         {mk:"SK hynix",t:"DDR4",cap:"4GB",box:"C-018",qty:170,unit:16},
         {mk:"Samsung",t:"DDR4",cap:"8GB",box:"C-018",qty:260,unit:28},
         {mk:"Samsung",t:"DDR5",cap:"8GB",box:"C-026",qty:70,unit:44},
         {mk:"Micron",t:"eMMC",cap:"32GB",box:"C-005",qty:380,unit:15},
         {mk:"Silicon Motion",t:"SSD SATA TLC",cap:"256GB",box:"C-033",qty:60,unit:108}]},
 {n:45,so:134,origin:"phone",seller:"eMiner",city:"Assunção",country:"Paraguai",closed:"15/07",ship:"16/07",eta:"23/07",
  carrier:"DHL",track:"4721 8544 771",st:"received",got:"23/07",lock:0.1478,lockD:"15/07",
  lines:[{mk:"Samsung",t:"eMMC",cap:"32GB",box:"C-014",qty:300,unit:15},
         {mk:"Kioxia",t:"eMMC",cap:"32GB",box:"C-014",qty:220,unit:15},
         {mk:"Samsung",t:"eMMC",cap:"64GB",box:"C-014",qty:340,unit:26},
         {mk:"Samsung",t:"LPDDR4X",cap:"4GB",box:"C-031",qty:210,unit:40},
         {mk:"SK hynix",t:"eMCP",cap:"64GB",box:"C-007",qty:160,unit:68}]},
 {n:44,so:131,origin:"pcb",seller:"RecycleSur",city:"Montevidéu",country:"Uruguai",closed:"04/07",ship:"05/07",eta:"12/07",
  carrier:"EMS",track:"EE4720 1183 6UY",st:"settled",got:"12/07",done:"14/07",lock:0.1502,lockD:"04/07",
  lines:[{mk:"Samsung",t:"DDR3",cap:"2GB",box:"C-009",qty:430,unit:6},
         {mk:"Nanya",t:"DDR3",cap:"2GB",box:"C-009",qty:270,unit:6},
         {mk:"SK hynix",t:"DDR3",cap:"4GB",box:"C-009",qty:410,unit:11},
         {mk:"Samsung",t:"eMMC",cap:"16GB",box:"C-005",qty:560,unit:11},
         {mk:"Micron",t:"eMMC",cap:"32GB",box:"C-005",qty:300,unit:15}],
  res:[405,247,398,502,271],
  pays:[{d:"16/07",usd:1201.60,kind:"partial",ref:"9d41c7e0f2a58b36104de927c5b81f47a2069cd3e85471b9f0c26ad83e517402",file:"usdt-so-0131-16jul.pdf",by:"Shenzhen Yuan"}],
  notes:[{d:"12/07/26",who:"Shenzhen Yuan",t:"Caixa 2 chegou com a fita rompida e 0,4 kg abaixo do manifesto. Fotos enviadas ao vendedor no mesmo dia."},
         {d:"14/07/26",who:"Shenzhen Yuan",t:"Recusas concentradas em DDR3 2GB — pinos oxidados, provável armazenagem úmida. Combinado com a RecycleSur trocar o material de embalagem no próximo lote."}]},
 {n:43,so:128,origin:"phone",seller:"eMiner",city:"Assunção",country:"Paraguai",closed:"20/06",ship:"21/06",eta:"28/06",
  carrier:"DHL",track:"4721 8288 145",st:"paid",got:"28/06",done:"30/06",lock:0.1478,lockD:"20/06",
  lines:[{mk:"Samsung",t:"eMMC",cap:"32GB",box:"C-014",qty:280,unit:15},
         {mk:"SK hynix",t:"eMMC",cap:"32GB",box:"C-014",qty:200,unit:15},
         {mk:"Samsung",t:"eMMC",cap:"64GB",box:"C-014",qty:300,unit:26},
         {mk:"Samsung",t:"LPDDR4X",cap:"4GB",box:"C-031",qty:190,unit:40}],
  res:[268,187,281,172],
  pays:[{d:"01/07",usd:1034.60,kind:"partial",ref:"2a7f19c4d05e83b761948ac2f3d60e15b8724901ce5f3a86d21b0947e6c83f5d",file:"usdt-so-0128-01jul.pdf",by:"Shenzhen Yuan"},
        {d:"08/07",usd:2070.83,kind:"full",ref:"6e03b581af297c4d0e16583b7a9024fc1d8e5730b642af91c05d38e7b2419a6c",file:"usdt-so-0128-08jul.pdf",by:"Shenzhen Yuan"}]}
];

/* o "hoje" do protótipo. Mora AQUI, e a ficha lê daqui: enquanto era declarado nos dois lados,
   o módulo de dados não tinha data para comparar e a costura de datas simplesmente não existia. */
var TODAY="01/08";
/* datas em DD/MM dentro do mesmo ano: ordenar por mês*100+dia basta */
function dnum(d){var p=String(d||"").split("/");return p.length<2?0:(+p[1])*100+(+p[0]);}
function dmin(a,z){return dnum(a)&&dnum(a)<=dnum(z)?a:z;}
/* A cadeia despacho → chegada → resultado → pagamento só faz sentido andando para a frente, e nada
   dela pode estar no futuro: um resultado datado antes da chegada é leitura impossível, e um
   recebimento datado depois de hoje é leitura impossível duas vezes. Override gravado por versão
   anterior pode conter isso e fica preso no navegador do usuário, então a cadeia é costurada na
   LEITURA — o defeito se conserta sozinho. Mesma regra do lado do cliente, em venda-data.js. */
function healDates(c){
  /* o primeiro elo é o FECHAMENTO do lote: a caixa não pode sair antes de o lote existir */
  if(c.ship&&dnum(c.ship)>dnum(TODAY))c.ship=TODAY;
  if(c.ship&&c.closed&&dnum(c.ship)<dnum(c.closed))c.ship=c.closed;
  var prev=c.ship||c.closed;
  ["got","done"].forEach(function(k){
    if(!c[k])return;
    if(dnum(c[k])>dnum(TODAY))c[k]=TODAY;
    if(prev&&dnum(c[k])<dnum(prev))c[k]=prev;
    prev=c[k];
  });
  if(c.pays&&c.pays.length){
    var p=prev;
    c.pays=c.pays.map(function(x){
      var d=x.d;
      if(dnum(d)>dnum(TODAY))d=TODAY;
      if(p&&dnum(d)<dnum(p))d=p;
      p=d;
      return d===x.d?x:Object.assign({},x,{d:d});
    });
  }
  return c;
}

/* overrides do protótipo (marcar recebido / fechar resultado / pagar) — só a nossa chave */
var K="wtc_buys";
function load(){try{return JSON.parse(localStorage.getItem(K)||"{}");}catch(e){return {};}}
function save(o){try{localStorage.setItem(K,JSON.stringify(o));}catch(e){}}
/* Override gravado por uma versão anterior pode estar num formato que já não existe, e o defeito
   fica preso no navegador do usuário — não some com um deploy. Então o formato é costurado na
   LEITURA: aqui, o pagamento em ¥ ({cny}) de antes de a perna 1 virar dólar. A conversão usa a
   taxa TRAVADA do lote, que é a que definiu o dólar daquele fechamento. O comprovante FICA — na
   perna comprador → WhatTheChip ele é obrigatório. Sem referência, a célula mostra o traço: é o
   que um registro legado honestamente tem. */
function healPays(c){
  if(!c.pays||!c.pays.length)return c;
  var lock=c.lock||0,conv=false;
  c.pays=c.pays.map(function(x){
    if(x.usd!=null||x.cny==null)return x;
    var y=Object.assign({},x,{usd:Math.round(x.cny*lock*100)/100});
    delete y.cny;
    if(y.ref==null&&y.tx!=null)y.ref=y.tx;
    delete y.tx;
    conv=true;
    return y;
  });
  /* parcela `full` quer dizer "esta fechou o saldo": convertida de ¥ arredondado, ela deixaria uma
     sobra de centavos e o lote quitado passaria a dizer "PAGO EM PARTE". Migrar preserva o que o
     lançamento significava. Só vale para lançamento convertido — valor nativo em US$ é dado. */
  var last=c.pays[c.pays.length-1];
  if(conv&&last&&last.kind==="full"){
    var gap=Math.round((dueUsd(c)-paidUsd(c))*100)/100;
    if(gap!==0&&last.usd+gap>0)last.usd=Math.round((last.usd+gap)*100)/100;
  }
  return c;
}
function all(){
  var ov=load();
  return BUYS.map(function(b){
    var o=ov[b.n];if(!o)return b;
    var c={},k;for(k in b)c[k]=b[k];
    for(k in o){if(o[k]===null)delete c[k];else c[k]=o[k];} /* null = limpar de volta ao base */
    /* O RESULTADO É POSICIONAL: res[i] pertence a lines[i]. Quando a estrutura da linha muda — e
       mudou, quando a marca entrou e algumas linhas viraram duas — um res gravado por versão
       anterior tem outro comprimento e passa a apontar para a linha errada. Isso não dá erro: dá
       número errado, calado. Lote 48 chegou a dizer resultado ¥ 25.990 sobre esperado ¥ 22.470,
       com tudo aprovado.
       Não há como remapear (não se sabe qual linha antiga virou quais novas), então o override
       inteiro é descartado e o registro volta ao dado de base — é o que uma migração faz quando o
       mapeamento não existe. Perder a edição local do protótipo é o de menos. */
    if(c.res&&c.res.length!==c.lines.length)return b;
    return healDates(healPays(c));
  });
}
function get(n){return all().filter(function(b){return b.n===+n;})[0];}
function patch(n,o){var ov=load();ov[n]=Object.assign({},ov[n]||{},o);save(ov);}
function reset(n){var ov=load();delete ov[n];save(ov);}

function code(b){return "LOT/"+("00"+b.n).slice(-3)+"/"+(b.closed.split("/")[1])+"/26";}
/* ordem de venda: nasce no FECHAMENTO do lote, com o preço da tabela do comprador e o câmbio
   travado naquele instante. É o objeto do dinheiro; o LOT é o objeto da caixa. As duas listas
   mostram os dois, e a data exibida ao lado do código é a da emissão — isto é, o fechamento. */
function soCode(b){return "SO/"+("000"+b.so).slice(-4)+"/"+(b.closed.split("/")[1])+"/26";}
function soDate(b){return b.closed;}
function rateOf(b){return b.lock||window.WTCFX.rate()||0;}
function r2(v){return Math.round(v*100)/100;}
function units(b){return b.lines.reduce(function(a,l){return a+l.qty;},0);}
function cny(b){return b.lines.reduce(function(a,l){return a+l.qty*l.unit;},0);}
function usd(b){return cny(b)*rateOf(b);}
function okUnits(b){return (b.res||[]).reduce(function(a,v){return a+(v||0);},0);}
function okCny(b){return b.lines.reduce(function(a,l,i){return a+((b.res&&b.res[i]!=null?b.res[i]:0)*l.unit);},0);}
/* PERNA 1, e as duas moedas têm papéis diferentes:
   o DEVIDO nasce em ¥ (o preço é da tabela do comprador, em ¥) e vira US$ pela taxa TRAVADA;
   o PAGO nasce em US$ (é a moeda da transferência);
   o SALDO se resolve em US$ — é em US$ que ele deve, e centavo de dólar é o que a carteira move.
   O ¥ do saldo é leitura conciliável, derivada, nunca a base da comparação.
   O devido é sempre o RESULTADO, nunca o valor declarado. */
function dueCny(b){return okCny(b);}
function dueUsd(b){return r2(okCny(b)*rateOf(b));}
function paidUsd(b){return r2((b.pays||[]).reduce(function(a,p){return a+(p.usd||0);},0));}
/* arredonda no centavo: sem isso um resto de 3,6e-12 faz um lote quitado dizer "pago em parte" */
function restUsd(b){return Math.max(0,r2(dueUsd(b)-paidUsd(b)));}
function paidCny(b){var r=rateOf(b);return r?Math.round(paidUsd(b)/r):0;}
function restCny(b){var r=rateOf(b);return r?Math.round(restUsd(b)/r):0;}
function paidPct(b){var d=dueUsd(b);return d?Math.min(100,paidUsd(b)/d*100):0;}
/* AGRUPA POR MARCA — é por marca que o material chega separado na bancada, então é por marca que
   a conferência anda. O preço continua vindo da CAIXA: duas marcas na mesma capacidade podem ter o
   mesmo ¥ e ainda assim ser conferidas em blocos diferentes, porque quem oxidou foi um fabricante.
   A ordem dos grupos é a de aparição no lote, não alfabética: é a ordem em que o vendedor separou. */
function byBrand(b){
  var m={},order=[];
  b.lines.forEach(function(l,i){
    if(!m[l.mk]){m[l.mk]={mk:l.mk,qty:0,cny:0,rows:[]};order.push(l.mk);}
    m[l.mk].qty+=l.qty;m[l.mk].cny+=l.qty*l.unit;
    m[l.mk].rows.push({i:i,t:l.t,cap:l.cap,box:l.box,qty:l.qty,unit:l.unit});
  });
  return order.map(function(k){return m[k];});
}
/* contagem de TIPOS distintos — só para os resumos ("9 linhas · 4 tipos"). Não agrupa nada. */
function types(b){
  var u={},n=0;
  b.lines.forEach(function(l){if(!u[l.t]){u[l.t]=1;n++;}});
  return n;
}
var ST={transit:["tag--info","A CAMINHO"],received:["tag--maybe","A CONFERIR"],settled:["tag--due","FATURADO"],paid:["tag--yes","PAGO"]};
/* etiqueta viva: "FATURADO" vira "PAGO EM PARTE" assim que entra a primeira parcela. O selo diz o
   ESTADO, nunca o quanto — porcentagem é dado de ficha, não de pastilha.
   Saldo em aberto manda mais que o estado: nunca dizemos PAGO com resto a pagar. */
function stTag(b){
  if((b.st==="settled"||b.st==="paid")&&restUsd(b)>0)
    return ["tag--due",paidUsd(b)>0?"PARCIAL":"FATURADO"];
  return ST[b.st];
}

/* PNs do lote — cada linha (categoria × capacidade) reúne peças de fabricantes diferentes.
   O preço é da categoria WTC, então todo PN da mesma linha vale o mesmo; o que muda é
   o part number, o fabricante e as specs com que a peça foi identificada. */
var PN={
 "eMMC":[["Samsung","KLM#G1JETD-B041","eMMC 5.1 · HS400 · BGA153"],["SK hynix","H26M#1103BMR","eMMC 5.1 · HS400 · BGA153"],
         ["Kioxia","THGBMNG#C8LBAIL","eMMC 5.1 · HS400 · BGA153"],["Micron","MTFC#GAKAJCN-1M","eMMC 5.1 · HS400 · BGA153"]],
 "LPDDR4X":[["Samsung","K4U#E3S4AB-MGCL","LPDDR4X · 4266 Mbps · FBGA200"],["SK hynix","H9HCNNN#PUMLHR","LPDDR4X · 4266 Mbps · FBGA200"],
            ["Micron","MT53E#M32D4DT-046","LPDDR4X · 4266 Mbps · FBGA200"]],
 "LPDDR4":[["Samsung","K4F#E304HB-MGCJ","LPDDR4 · 3733 Mbps · FBGA200"],["SK hynix","H9HCNNN#BPUMLHR","LPDDR4 · 3733 Mbps · FBGA200"]],
 "DDR3":[["Samsung","K4B#G1646E-BCMA","DDR3L · 1600 MT/s · FBGA96 · ×16"],["SK hynix","H5TQ#G63EFR-PBC","DDR3L · 1600 MT/s · FBGA96 · ×16"],
         ["Micron","MT41K#M16HA-125","DDR3L · 1600 MT/s · FBGA96 · ×16"],["Nanya","NT5CC#M16FP-DI","DDR3L · 1600 MT/s · FBGA96 · ×16"]],
 "DDR4":[["Samsung","K4A#G165WC-BCTD","DDR4 · 2666 MT/s · FBGA96 · ×16"],["SK hynix","H5AN#G8NAJR-VKC","DDR4 · 2666 MT/s · FBGA96 · ×16"],
         ["Micron","MT40A#M16TB-062","DDR4 · 2666 MT/s · FBGA96 · ×16"]],
 "DDR5":[["Samsung","K4RAH#56VB-BCQK","DDR5 · 4800 MT/s · FBGA · ×16"],["SK hynix","H5CG#MEBDX014","DDR5 · 4800 MT/s · FBGA · ×16"]],
 "eMCP":[["Samsung","KMDH#000DA-B425","eMCP · eMMC 5.1 + LPDDR3 · BGA221"],["SK hynix","H9TQ#ABJTMCUR","eMCP · eMMC 5.1 + LPDDR3 · BGA221"]],
 "uMCP":[["Samsung","KMDV#000DM-B426","uMCP · UFS 2.1 + LPDDR4X · BGA221"],["SK hynix","H9HQ#ANBMAD","uMCP · UFS 2.1 + LPDDR4X · BGA221"]],
 "UFS 2.1":[["Samsung","KLUDG#UHDC-B0E1","UFS 2.1 · HS-G3 · BGA153"],["Kioxia","THGJFJT#C45BAB1","UFS 2.1 · HS-G3 · BGA153"]],
 "SSD SATA TLC":[["Silicon Motion","SM2258XT-#","SATA III · TLC 3D NAND · 2,5\""],["Phison","PS3111-S11-#","SATA III · TLC 3D NAND · 2,5\""]]
};
var HEX="0123456789ABCDEF";
/* mesma semente ⇒ mesma lista de PNs em toda visita: o lote não muda de conteúdo ao recarregar */
function seeded(s){var x=s;return function(){x=(x*1103515245+12345)&0x7fffffff;return x/0x7fffffff;};}
function pns(b){
  var out=[];
  b.lines.forEach(function(l,i){
    var all=PN[l.t]||PN["eMMC"];
    /* a linha TEM marca agora, então os part numbers dela são daquele fabricante — antes a mesma
       linha sorteava PNs de marcas diferentes, o que contradiz a própria linha. Fabricante fora do
       catálogo cai no catálogo inteiro: melhor um PN plausível que nenhum. */
    var pool=all.filter(function(p){return p[0]===l.mk;});
    if(!pool.length)pool=all;
    var rnd=seeded(b.n*977+i*131+7);
    var k=Math.min(pool.length,1+Math.floor(rnd()*2)),left=l.qty,picks=[];
    for(var j=0;j<k;j++)picks.push(pool[(Math.floor(rnd()*pool.length)+j)%pool.length]);
    picks.forEach(function(p,j){
      var qty=j===k-1?left:Math.max(1,Math.round(l.qty*(0.3+rnd()*0.35)));
      if(qty>left)qty=left;left-=qty;
      if(qty<=0)return;
      var tag="";for(var h=0;h<4;h++)tag+=HEX[Math.floor(rnd()*16)];
      out.push({pn:p[1].replace("#",tag),make:p[0],spec:p[2]+" · "+l.cap,type:l.t,cap:l.cap,
        wtc:l.box,qty:qty,unit:l.unit,line:i});
    });
  });
  return out;
}

window.WTCBuys={all:all,get:get,patch:patch,reset:reset,code:code,soCode:soCode,soDate:soDate,
  TODAY:TODAY,dnum:dnum,dmin:dmin,
  units:units,cny:cny,usd:usd,pns:pns,rateOf:rateOf,trackUrl:trackUrl,
  okUnits:okUnits,okCny:okCny,byBrand:byBrand,types:types,ST:ST,stTag:stTag,WALLET:WALLET,
  dueCny:dueCny,dueUsd:dueUsd,paidCny:paidCny,paidUsd:paidUsd,restCny:restCny,restUsd:restUsd,paidPct:paidPct,
  count:function(st){return all().filter(function(b){return b.st===st;}).length;}};
})();
