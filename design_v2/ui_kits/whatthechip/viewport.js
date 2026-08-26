/* WhatTheChip — controle de viewport do protótipo. Enquadra a página em celular, tablet ou desktop
   dentro da própria janela. O frame é um container CSS, então as regras responsivas da página
   (escritas como @container) leem a largura do frame — o layout reage como reagiria numa tela real.
   Os controles do protótipo ficam FORA do frame, presos à janela. */
(function(){
"use strict";
/* chrome de protótipo: não roda quando este arquivo chega pelo bundle compilado do design system.
   O compilador empilha os .js do projeto em _ds_bundle.js, e ali dentro isto se auto-executava em
   páginas que não são telas — cards de especificação, projetos consumidores — estampando
   data-theme/data-wtc-* no <html> delas.
   A condição é a PRESENÇA do bundle, não a ausência de uma folha: "carrega wtc-carbon.css" não é
   assinatura de tela do kit (a landing declara os tokens inline e não carrega folha nenhuma), e
   inferir de um link deixava justamente ela sem os controles. */
if(document.querySelector('script[src*="_ds_bundle"]'))return;
var K="wtc_vp";
var VP={
  desktop:{label:"Desktop",w:null,ico:'<rect x="2.5" y="4" width="19" height="13"/><path d="M9 20h6M12 17v3"/>'},
  tablet: {label:"Tablet", w:834, ico:'<rect x="5" y="2.5" width="14" height="19"/><path d="M10.5 19.5h3"/>'},
  phone:  {label:"Celular",w:390, ico:'<rect x="7" y="2.5" width="10" height="19"/><path d="M10.5 5h3"/>'}
};
var ORDER=["desktop","tablet","phone"];
function cur(){try{var v=localStorage.getItem(K);return VP[v]?v:"desktop";}catch(e){return "desktop";}}

/* embrulha o conteúdo da página uma única vez; os controles do protótipo ficam de fora */
/* DOIS elementos, não um: o de fora é a moldura (bloco contentor, não rola), o de dentro é o
   conteúdo que rola. Quando o mesmo elemento acumulava os dois papéis, todo position:fixed da
   página se resolvia contra a CAIXA DE CONTEÚDO do rolador — então o diálogo subia junto com a
   rolagem e saía da tela. Separados, o fixed se ancora na moldura parada e fica preso à "tela". */
function frame(){
  var f=document.querySelector("[data-wtc-frame]");
  if(f)return f;
  f=document.createElement("div");
  f.setAttribute("data-wtc-frame","");
  var sc=document.createElement("div");
  sc.setAttribute("data-wtc-scroll","");
  f.appendChild(sc);
  var kids=[],i;
  for(i=0;i<document.body.children.length;i++){
    var c=document.body.children[i];
    if(c.hasAttribute("data-wtc-switcher")||c.hasAttribute("data-wtc-vpbar"))continue;
    kids.push(c);
  }
  document.body.insertBefore(f,document.body.firstChild);
  kids.forEach(function(c){sc.appendChild(c);});
  return f;
}

function apply(){
  var k=cur(),v=VP[k],f=frame();
  var st=document.getElementById("wtc-vp-style");
  if(!st){st=document.createElement("style");st.id="wtc-vp-style";document.head.appendChild(st);}
  document.documentElement.setAttribute("data-wtc-vp",k);
  /* container-type sempre ligado: em desktop o frame tem a largura da janela, então as
     @container da página se comportam igual a @media — e no celular leem o frame. */
  st.textContent="[data-wtc-frame]{container-type:inline-size;container-name:vp}"
    +(v.w
      ?"html[data-wtc-vp]{background:#21272a}"
      +"html[data-wtc-vp],html[data-wtc-vp] body{height:100%;overflow:hidden}"
      +"body{background:#21272a}"
      /* a moldura é a JANELA do aparelho: altura fixa, transform (para o fixed da página se
         ancorar nela, e não na janela do navegador) e overflow:hidden — ela NÃO rola. Quem rola é
         a caixa de dentro. É essa divisão que faz o diálogo ficar preso à tela mesmo com a página
         rolada; com o rolador acumulando os dois papéis, o overlay subia junto com o conteúdo. */
      +"[data-wtc-frame]{width:"+v.w+"px;margin:0 auto;height:100vh;background:var(--bg,#fff);"
        +"box-shadow:0 0 0 1px #3a4249;overflow:hidden;position:relative;transform:translate(0)}"
      +"[data-wtc-scroll]{height:100%;overflow-y:auto;overflow-x:hidden}"
      :"");
}
function set(k){try{localStorage.setItem(K,k);}catch(e){}apply();paint();}

function paint(){
  var bar=document.querySelector("[data-wtc-vpbar]");if(!bar)return;
  var k=cur();
  Array.prototype.forEach.call(bar.querySelectorAll("[data-vp]"),function(b){
    var on=b.getAttribute("data-vp")===k;
    b.style.background=on?"#0f62fe":"transparent";
    b.style.color=on?"#fff":"#a2a9b0";
    b.setAttribute("aria-pressed",on?"true":"false");
  });
  var w=bar.querySelector("[data-vpw]");
  if(w)w.textContent=VP[k].w?VP[k].w+"px":"livre";
}

function mount(){
  var bar=document.createElement("div");
  bar.setAttribute("data-wtc-vpbar","");
  bar.style.cssText="position:fixed;right:14px;bottom:14px;z-index:120;display:flex;align-items:center;gap:4px;"
    +"background:#101317;border:1px solid #3a4249;border-radius:999px;padding:6px;"
    +"box-shadow:0 10px 30px -8px rgba(0,0,0,.5);font-family:'Manrope',system-ui,sans-serif";
  ORDER.forEach(function(k){
    var v=VP[k],b=document.createElement("button");
    b.type="button";b.setAttribute("data-vp",k);b.title=v.label+(v.w?" · "+v.w+"px":"");
    b.setAttribute("aria-label",v.label);
    b.style.cssText="border:0;cursor:pointer;width:34px;height:30px;border-radius:999px;display:grid;place-items:center;transition:background 120ms,color 120ms";
    b.innerHTML='<svg viewBox="0 0 24 24" style="width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round">'+v.ico+'</svg>';
    b.onclick=function(){set(k);};
    bar.appendChild(b);
  });
  var w=document.createElement("span");
  w.setAttribute("data-vpw","");
  w.style.cssText="font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:10px;font-weight:600;color:#697077;padding:0 10px 0 8px;border-left:1px solid #3a4249;white-space:nowrap";
  bar.appendChild(w);
  document.body.appendChild(bar);
  dock(bar);
  paint();
}

/* A barra flutuante MEDE o que já está ancorado no rodapé e se empilha acima. Antes eram dois
   números cravados (14px, ou 64px quando havia o alternador de papéis): aí uma tela com barra de
   ação própria — .pfoot, 73px, com "Enviar para revisão" — recebia os controles POR CIMA do botão,
   e o clique ia para o alternador de tamanho. Adivinhar a altura do vizinho não escala: cada tela
   nova com rodapé fixo reabriria o mesmo defeito. Medir escala.
   Só conta quem está REALMENTE encostado no fundo (a menos de 24px), para um diálogo centrado ou um
   toast a meia altura não empurrar a barra sem motivo. */
function dock(bar){
  var gap=14,floor=0;
  [].forEach.call(document.querySelectorAll("body *"),function(el){
    if(el===bar||bar.contains(el))return;
    var c=getComputedStyle(el);
    if(c.position!=="fixed"||c.display==="none"||c.visibility==="hidden")return;
    var r=el.getBoundingClientRect();
    if(!r.height||r.bottom<innerHeight-24)return;
    floor=Math.max(floor,r.height+(innerHeight-r.bottom));
  });
  bar.style.bottom=(floor?floor+gap:gap)+"px";
}

window.WTCViewport={current:cur,set:set,apply:apply};
/* re-mede depois que o resto da página montou (o alternador de papéis e o .pfoot podem nascer
   depois deste script) e a cada resize, porque o rodapé reflui e muda de altura. */
function redock(){var b=document.querySelector("[data-wtc-vpbar]");if(b)dock(b);}
function boot(){apply();mount();requestAnimationFrame(redock);addEventListener("resize",redock);}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);
else boot();
})();
