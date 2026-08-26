/* WhatTheChip — grade de preços do parceiro. Página inteira = um formulário; o servidor faz o diff. */
(function(){
"use strict";
var $=function(i){return document.getElementById(i);};
var P=window.WTCPartner,D=P.DATA,REVIEW=P.REVIEW;
/* "tipo", nunca "t": a query da página servida já usa t para o token de sessão, e um param de
   uma letra colide com o do host sem avisar.
   [a-z0-9]+ e não [a-z]+: chave de chip tem dígito (k9, e amanhã lpddr5). Com [a-z]+ o "k9" era
   lido como "k", D["k"] não existia e a página caía no tipo padrão sem erro nenhum — a rota
   errava calada. */
var key=window.WTC_TYPE||(location.search.match(/[?&]tipo=([a-z0-9]+)/)||[])[1];
/* sem tipo na query esta tela não tem o que mostrar: quem responde por "nenhum tipo" é o Resumo, e
   é o que a barra já acende. O fallback antigo (key="emcp") fazia a página virar uma duplicata
   fantasma do eMCP — que tem tela própria — e discordar da própria navegação. */
if(!D[key]){location.replace("parceiro.html"+window.WTCShell.sessionQuery());return;}
/* a base dos nomes de campo vem do ÍNDICE do tipo na lista canónica, não de um mapa literal: um
   mapa exige lembrar cada tipo novo em dois lugares, e quando soc/cpu/k9 entraram sem entrada a
   base virou undefined — todo pk++ deu NaN, os 14 campos da tabela colapsaram em dois nomes e o
   rastreio de alteração passou a comparar a linha errada, sem erro no console. */
var t=D[key],pk=1200+P.TYPES.map(function(x){return x.k;}).indexOf(key)*100;
var BLK=P.blockOf(key);
var init={},dirty={};
var toast=$("toast"),tT;
function say(m){$("toast-txt").textContent=m;toast.classList.add("is-on");clearTimeout(tT);tT=setTimeout(function(){toast.classList.remove("is-on");},3000);}
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}

/* a barra de tipos mora em parceiro-side.js — é navegação de TODA a seção, inclusive do Resumo,
   que não carrega esta folha. */

/* ---------- cabeçalho e selos ---------- */
var CK='<svg viewBox="0 0 24 24" stroke-linecap="round"><path d="M20 6L9 17l-5-5"/></svg>';
$("tt").textContent=t.n;
/* a frase do subtítulo não CONTA formatos: "o único com faixa" era verdade com dois tipos e virou
   mentira em três páginas quando o K9 entrou. Uma tela não deve afirmar nada sobre as outras. */
$("td").textContent=t.d+(t.range?" · faixa: mínimo e máximo por linha.":"");
/* o selo diz o que ORDENA a linha, e por isso vem do dado (t.by) e não só da forma da tabela:
   SoC, CPU e K9 têm a mesma forma "uni" das memórias, mas a linha é um modelo ou um part number —
   dizer "vale para todas as marcas" numa tabela cujas seções SÃO marcas é falso. */
var BY={pn:"PREÇO ÚNICO — exclusivo Samsung, independe do part number"};
$("seals").innerHTML='<span class="seal seal--rmb">'+CK+'Todos os preços em ¥ (RMB)</span>'
 +(t.form==="dual"?'<span class="seal seal--dual">DUAS TABELAS — celular (unificado) × PCB (por marca)</span>'
  :t.form==="brand"?'<span class="seal seal--brand">MATRIZ POR MARCA</span>'
  :t.form==="linear"?'<span class="seal seal--brand">LINEAR ¥/GB — sem grade por densidade</span>'
  :t.by?'<span class="seal seal--brand">'+BY[t.by]+'</span>'
  :'<span class="seal seal--uni">PREÇO UNIFICADO — vale para todas as marcas</span>');

/* ---------- células ---------- */
/* o selo de estado é o .tag do sistema — caixa alta, ponto de cor, mesma casca de todo estado do
   produto. Havia aqui uma paleta paralela (.s-ok/.s-no/.s-x…) dizendo o mesmo com outra roupa. */
function state(v){return v===null?["tag--mute","não fabricado"]:v==="x"?["tag--no","não compro"]:v===""?["tag--mute","não cotado"]:["tag--yes","cotado"];}
function cell(v,name,ph){
  if(v===null)return '<span style="display:grid;place-items:center;height:52px;color:var(--ink-30);font-family:var(--mono);font-size:15px">—</span>';
  var val=v==="x"?"x":(v===""?"":String(v));
  init[name]=val;
  return '<input class="cell'+(v==="x"?" nox":v===""?"":" has")+'" name="'+name+'" value="'+val+'" '
    +'inputmode="text" autocomplete="off" spellcheck="false" aria-label="'+esc(name)+'" placeholder="'+(ph||"sem cotação")+'" />';
}
/* o estado da linha mora em COLUNA PRÓPRIA, não pendurado no fim do nome. Enfiado no rótulo ele
   empurrava o selo para a borda direita da 1ª célula e abria uma segunda margem dentro dela — e um
   estado é dado, com direito a cabeçalho, como em toda lista do sistema. */
/* a linha que TRAVA PEDIDO diz isso na própria coluna de status, e vence "não cotado": as duas
   afirmações são verdade, mas só uma explica por que esta linha é urgente. */
function rowSeal(k,v){
  var r=REVIEW[key+":"+k],s=state(v);
  if(r)return '<span class="tag tag--maybe"><span class="dot"></span>em revisão · ¥ '+r.join("–")+'</span>';
  /* casa pela LINHA, não pelo estado agregado: em matriz por marca o agregado é 1 quando
     qualquer marca tem cotação, e DDR5 16GB ([78,"","",null,null,""]) saía marcada como cotada —
     o furo atingia justo dois dos três tipos travados. Quem sabe que a linha trava pedido é a
     plataforma, e ela já disse. */
  if(BLK&&BLK.row===k)
    return '<span class="tag tag--no"><span class="dot"></span>travando '+BLK.orders
      +(BLK.orders===1?' pedido':' pedidos')+'</span>';
  return '<span class="tag '+s[0]+'"><span class="dot"></span>'+s[1]+'</span>';
}
/* data-label em TODO td: no telefone a .dtab esconde o cabeçalho e a linha colapsa em cartão —
   sem o rótulo, dois campos de preço lado a lado não dizem qual é mínimo e qual é máximo. */
function sealTd(k,v){return '<td data-label="Status">'+rowSeal(k,v)+'</td>';}
/* matriz por marca: a linha não tem UM valor, tem um por marca — então o estado é a soma delas.
   Tudo x = não compro; nada cotado = não cotado; qualquer cotação = cotado. */
function rowState(vals){
  var v=vals.filter(function(x){return x!==null;});
  if(!v.length)return null;
  if(v.every(function(x){return x==="x";}))return "x";
  if(v.every(function(x){return x==="";}))return "";
  return 1;
}
var TH_ST='<th style="min-width:132px">Status</th>';
function label(n,sub){
  return '<div class="gl"><span class="gl__n">'+esc(n)+(sub?'<span>'+esc(sub)+'</span>':'')+'</span></div>';
}

/* ---------- blocos ---------- */
/* o rótulo da 1ª coluna é onde a tabela se identifica: sem a barra de título acima, é ele que
   diz de que material esta grade fala. Só as páginas com DUAS grades precisam dizer — nas de uma
   só o título da página já respondeu, e "Linha" basta. */
function single(rows,range,lead){
  var head='<tr><th>'+esc(lead||"Linha")+'</th>'+TH_ST+(range?'<th style="min-width:200px">Preço ¥ — mínimo</th><th style="min-width:200px">Preço ¥ — máximo</th>'
    :'<th style="min-width:220px">Preço ¥ por unidade</th>')+'</tr>';
  var body=rows.map(function(r){
    if(r[0]==="§")return '<tr class="g"><td colspan="'+(range?4:3)+'">'+esc(r[1])+'</td></tr>';
    var v=r[2],id=pk++;
    if(range){
      var a=Array.isArray(v)?v[0]:v,b=Array.isArray(v)?v[1]:v;
      return '<tr><td>'+label(r[0],r[1])+'</td>'+sealTd(r[0],Array.isArray(v)?a:v)
        +'<td data-label="Preço ¥ — mínimo">'+cell(a,"p"+id,"sem cotação")+'</td>'
        +'<td data-label="Preço ¥ — máximo">'+cell(b,"pmax"+id,"sem cotação")+'</td></tr>';
    }
    return '<tr><td>'+label(r[0],r[1])+'</td>'+sealTd(r[0],v)+'<td data-label="Preço ¥ por unidade">'+cell(v,"p"+id)+'</td></tr>';
  }).join("");
  return block(head,body);
}
function matrix(rows,brands,lead){
  var head='<tr><th>'+esc(lead||"Linha")+'</th>'+TH_ST+brands.map(function(b){return '<th style="min-width:112px">'+esc(b)+'</th>';}).join("")+'</tr>';
  var body=rows.map(function(r){
    if(r[0]==="§")return '<tr class="g"><td colspan="'+(brands.length+2)+'">'+esc(r[1])+'</td></tr>';
    return '<tr><td>'+label(r[0],"")+'</td>'+sealTd(r[0],rowState(r[1]))
      +r[1].map(function(v,bi){return '<td data-label="'+esc(brands[bi])+'">'+cell(v,"p"+(pk++))+'</td>';}).join("")+'</tr>';
  }).join("");
  return block(head,body,true);
}
/* SSD: preço linear — ¥/GB + piso por peça, com a conta feita na frente do comprador */
function linear(t){
  var head='<tr><th>Classe</th>'+TH_ST+'<th style="min-width:130px">¥ por GB</th><th style="min-width:130px">¥ mínimo/peça</th>'
    +t.caps.map(function(c){return '<th style="min-width:100px">'+(c>=1024?(c/1024)+" TB":c+" GB");}).join("</th>")+'</th></tr>';
  var body=t.rows.map(function(r){
    var id=pk++;
    return '<tr data-lin="'+id+'"><td>'+label(r[0],r[1])+'</td>'+sealTd(r[0],r[2])
      +'<td data-label="¥ por GB">'+cell(r[2],"p"+id,"sem cotação")+'</td>'
      +'<td data-label="¥ mínimo/peça">'+cell(r[3],"pmin"+id,"sem piso")+'</td>'
      +t.caps.map(function(c){return '<td data-label="'+(c>=1024?(c/1024)+" TB":c+" GB")+'"><span class="calc" data-cap="'+c+'">—</span></td>';}).join("")+'</tr>';
  }).join("");
  return block(head,body,true);
}
function calcLinear(){
  Array.prototype.forEach.call(document.querySelectorAll("[data-lin]"),function(tr){
    var id=tr.getAttribute("data-lin");
    var gb=parseFloat((document.getElementsByName("p"+id)[0]||{}).value)||0;
    var mn=parseFloat((document.getElementsByName("pmin"+id)[0]||{}).value)||0;
    Array.prototype.forEach.call(tr.querySelectorAll(".calc"),function(el){
      var c=+el.getAttribute("data-cap");
      if(!gb){el.textContent="—";el.className="calc";return;}
      var v=Math.max(Math.round(gb*c),mn);
      el.textContent="¥ "+v.toLocaleString("pt-BR");
      el.className="calc"+(mn&&gb*c<mn?" calc--floor":"");
    });
  });
}
/* x = a grade rola de lado (marcas, capacidades). Sem ele a tabela cabe e não rola nada. */
function block(head,body,x){
  return '<section class="grid2" style="margin-bottom:20px">'
    +'<div class="dtab__wrap'+(x?" dtab__wrap--x":"")+'"><table class="dtab dtab--static"><thead>'+head+'</thead><tbody>'+body+'</tbody></table></div></section>';
}
var html="";
if(t.form==="dual"){
  html=single(t.phone,false,"Linha · de CELULAR")
      +matrix(t.pcb,t.brands,"Linha · de PCB, por marca");
}else if(t.form==="brand"){
  html=matrix(t.rows,t.brands);
}else if(t.form==="linear"){
  html=linear(t);
}else{
  html=single(t.rows,!!t.range);
}
/* quem chega pela barra de tipos não passou pela faixa do Resumo, então o aviso se repete aqui —
   uma vez, no topo da tabela que resolve o problema. */
$("blocks").innerHTML=(BLK?'<div class="gnote gnote--blk">'
    +'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5L22 20H2z"/><path d="M12 10v4M12 17h.01"/></svg>'
    +'<span><b>'+BLK.orders+(BLK.orders===1?' pedido está travado':' pedidos estão travados')+'</b> desde '+BLK.since
    +' esperando o preço de <b>'+esc(BLK.row)+'</b> (caixa '+esc(BLK.box)+') \u2014 '
    +BLK.units.toLocaleString("pt-BR")+' un. que a plataforma não consegue precificar sem você.</span></div>':'')
  +html;

/* ---------- edição: um input por célula ---------- */
function repaint(el){
  var v=el.value.trim().toLowerCase();
  el.classList.toggle("nox",v==="x");
  el.classList.toggle("has",v!==""&&v!=="x");
  var d=v!==(init[el.name]||"");
  el.classList.toggle("dirty",d);
  if(d)dirty[el.name]=1;else delete dirty[el.name];
  var n=Object.keys(dirty).length;
  $("dirty").textContent=n?(n+(n===1?" célula alterada":" células alteradas")):"nenhuma alteração";
  $("send").disabled=!n;
  if(t.form==="linear")calcLinear();
}
Array.prototype.forEach.call(document.querySelectorAll(".cell"),function(el){
  el.addEventListener("input",function(){
    var v=el.value;
    var re=t.form==="linear"?/^(|x|X|\d{0,4}([.,]\d{0,2})?)$/:/^(|x|X|\d{0,6})$/;
    if(!re.test(v))el.value=t.form==="linear"?v.replace(/[^\d.,xX]/g,"").slice(0,7):v.replace(/[^\dxX]/g,"").slice(0,6);
    repaint(el);
  });
  el.addEventListener("blur",function(){if(el.value.trim().toLowerCase()==="x")el.value="x";repaint(el);});
});
$("send").onclick=function(){
  var n=Object.keys(dirty).length;
  say(n+" linha(s) enviada(s) para revisão · viram pedido pendente com a tag ⏳ até a plataforma aprovar");
  Array.prototype.forEach.call(document.querySelectorAll(".cell.dirty"),function(el){el.classList.remove("dirty");init[el.name]=el.value.trim().toLowerCase();});
  dirty={};$("dirty").textContent="nenhuma alteração";$("send").disabled=true;
};

/* ---------- taxa viva no cabeçalho ---------- */
function fx(){
  var s=window.WTCFX.state();
  $("fxr").textContent=s.has?("1 ¥ ≈ US$ "+s.rate.toFixed(4)):"sem taxa do dia";
  $("fxd").textContent=s.has?("\u00b7 "+(s.is_market?"mid-market ":"contrato ")+s.date):"\u00b7 rode fetch_fx_rate";
  var lv=document.querySelector(".pshell__sub");if(lv)lv.classList.toggle("off",!s.has);
}
window.WTCFX.onChange(fx);fx();
if(t.form==="linear"){
  calcLinear();
  document.querySelector(".pfoot__lg").innerHTML='<b>¥/GB</b> aceita 2 casas (ex.: 0,42) · <b>x</b> = não compro · <b>vazio</b> = sem cotação. As colunas de capacidade são calculadas — o âmbar marca onde o piso por peça manda.';
}
})();
