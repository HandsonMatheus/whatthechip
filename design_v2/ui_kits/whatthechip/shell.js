/* WhatTheChip — consolidação do cabeçalho.

   O cabeçalho vinha com oito células disputando largura: marca, nav, empresa, usuário, sino,
   tema, idioma e sair — e o widget de câmbio ainda entrava entre a nav e a empresa. A nav, sendo
   a única com `flex-shrink`, era quem cedia: o último link ("Vendas") ficava recortado atrás do
   câmbio. Não era bug de z-index, era falta de espaço.

   Aqui empresa, usuário, tema, idioma e sair passam a viver num único botão de perfil com gaveta.
   A barra fica com cinco zonas: marca · nav · câmbio · sino · perfil.

   Os elementos originais são MOVIDOS, não recriados — access.js continua achando
   [data-wtc-company]/[data-wtc-initials]/… e theme.js continua ligado ao #theme-btn. */
(function(){
"use strict";
var LANGS=[["PT","Português"],["EN","English"],["ES","Español"],["ZH","中文"]];

/* fechamento único do cabeçalho: dois menus abertos ao mesmo tempo sempre acabam com um
   enterrado atrás do outro. Qualquer gatilho novo só precisa chamar isto antes de abrir. */
var POPS=[".me",".nbell"];
function closeAll(except){
  POPS.forEach(function(sel){
    document.querySelectorAll(sel+".on").forEach(function(n){
      if(n===except)return;
      n.classList.remove("on");
      var t=n.querySelector("[aria-expanded]");
      if(t)t.setAttribute("aria-expanded","false");
    });
  });
}
/* ---------- navegação entre as telas do kit ----------
   Os protótipos são servidos com parâmetros de sessão na query (token, srcmap). Um link relativo
   comum descarta a query INTEIRA, então a próxima tela abre sem eles e não carrega — de dentro do
   protótipo parece simplesmente que "o link não funciona". Aqui todo link .html do próprio kit
   reaproveita a query da página atual, e os parâmetros do PRÓPRIO link vencem os herdados (é o
   link que sabe para onde vai). Em produção a query é vazia e nada disto altera um href.

   O que NÃO se herda: parâmetros que pertencem a uma tela, não à sessão. "tipo" identifica a
   tabela de preço aberta; herdado por parceiro.html ele fazia o Resumo abrir com a barra acesa no
   tipo anterior — a tela discordando da própria navegação. A lista é de exclusão, não de inclusão:
   um parâmetro de sessão novo do host continua viajando sozinho, que é o defeito que este handler
   existe para consertar. */
var OWN=["tipo"];
/* a query de sessão da página atual, sem os parâmetros de tela — quem redireciona também precisa
   dela, então mora aqui e não duplicada em cada folha. */
function sessionQuery(){
  var q=new URLSearchParams(location.search);
  OWN.forEach(function(k){q.delete(k);});
  var s=q.toString();
  return s?"?"+s:"";
}
window.WTCShell={closeAll:closeAll,sessionQuery:sessionQuery};
(function(){
  if(!location.search||location.search==="?")return;
  document.addEventListener("click",function(e){
    if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
    var a=e.target&&e.target.closest&&e.target.closest("a[href]");
    if(!a||a.target==="_blank"||a.hasAttribute("download"))return;
    var h=a.getAttribute("href");
    if(!h||/^([a-z][a-z0-9+.-]*:|\/\/|#)/i.test(h))return;
    var u;
    try{u=new URL(h,location.href);}catch(err){return;}
    if(u.origin!==location.origin||!/\.html$/i.test(u.pathname))return;
    var q=new URLSearchParams(sessionQuery());
    u.searchParams.forEach(function(v,k){q.set(k,v);});
    e.preventDefault();
    var s=q.toString();
    location.href=u.pathname+(s?"?"+s:"")+u.hash;
  },true);
})();

function boot(){
  var shell=document.querySelector(".shell")||document.querySelector(".pshell");
  if(!shell)return;
  /* a gaveta vale para OS DOIS cabeçalhos: .shell do app e .pshell do parceiro. Estava travada em
     isApp, então o cabeçalho do parceiro nunca recebia o burger nem o [data-shell] que o CSS de
     tablet/telefone precisa — a barra ficava numa linha só e a navegação saía da tela. */
  if(shell.querySelector(".me")){drawer(shell);return;}
  var p=shell.classList.contains("pshell");
  var org=shell.querySelector(p?".pshell__org":".shell__org"),
      who=shell.querySelector(p?".pshell__who":".shell__who"),
      lang=shell.querySelector(".shell__ico--lang"),
      out=shell.querySelector(".shell__ico--out");
  if(!who&&!org){drawer(shell);return;}

  var me=document.createElement("div");
  me.className="me";
  var btn=document.createElement("button");
  btn.type="button";btn.className="me__btn";
  btn.setAttribute("aria-expanded","false");
  btn.setAttribute("aria-label","Conta e preferências");
  var pop=document.createElement("div");
  pop.className="me__pop";
  me.appendChild(btn);me.appendChild(pop);

  /* o botão guarda só o avatar; nome, cargo e empresa moram na gaveta — assim a barra não
     disputa largura com a nav e a identidade fica sempre legível ao abrir */
  var av=who&&who.querySelector(p?".pshell__av":".shell__avatar"),
      usr=who&&who.querySelector(p?".pshell__u":".shell__user");
  if(av)btn.appendChild(av);
  var chev=document.createElement("span");
  chev.className="me__chev";
  chev.innerHTML='<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>';
  btn.appendChild(chev);

  if(org)pop.appendChild(org);            /* identidade da empresa abre a gaveta */
  if(usr){
    var hd=document.createElement("div");
    hd.className="me__hd";
    hd.appendChild(usr);
    pop.insertBefore(hd,pop.firstChild);
  }
  if(who)who.remove();

  var sec=document.createElement("div");
  sec.className="me__sec";
  /* o tema NÃO desce para a gaveta: ele fica na barra, ao lado do sino. É ação de um toque,
     usada a qualquer momento — enterrá-la em dois toques dentro do perfil custava mais que valia. */
  var ll=document.createElement("div");ll.className="me__l";ll.textContent="Idioma";
  sec.appendChild(ll);
  var box=document.createElement("div");box.className="me__langs";
  var cur=(lang&&lang.textContent.trim().toUpperCase())||"PT";
  LANGS.forEach(function(l){
    var b=document.createElement("button");
    b.type="button";b.textContent=l[0]==="ZH"?"中文":l[0];b.title=l[1];
    if(l[0]===cur)b.className="on";
    b.onclick=function(){
      Array.prototype.forEach.call(box.children,function(o){o.className=o===b?"on":"";});
    };
    box.appendChild(b);
  });
  sec.appendChild(box);
  pop.appendChild(sec);
  if(lang)lang.remove();
  if(out)pop.appendChild(out);

  /* o perfil entra no fim da barra; o câmbio (inserido por fx.js após o spacer) fica antes */
  shell.appendChild(me);

  function close(){me.classList.remove("on");btn.setAttribute("aria-expanded","false");}
  btn.onclick=function(e){
    e.stopPropagation();
    var willOpen=!me.classList.contains("on");
    closeAll(me);
    me.classList.toggle("on",willOpen);
    btn.setAttribute("aria-expanded",willOpen?"true":"false");
  };
  pop.onclick=function(e){e.stopPropagation();};
  document.addEventListener("click",close);
  document.addEventListener("keydown",function(e){if(e.key==="Escape")closeAll();});

  /* o sino é montado por notifications.js e tem stopPropagation próprio, então o listener de
     documento não o alcança: interceptamos na fase de captura para fechar o perfil antes. */
  document.addEventListener("click",function(e){
    var b=e.target.closest&&e.target.closest(".nbell #bell, .nbell button");
    if(b)closeAll(b.closest(".nbell"));
  },true);

  drawer(shell);
}

/* ---------- MODELO: menu mobile/tablet ----------
   A barra mede a si mesma e classifica a largura em desktop/tablet/phone. Medir o elemento
   (e não a janela) faz a mesma regra valer no aparelho real e dentro do enquadramento do
   protótipo. O CSS da gaveta vive em wtc-carbon.css — aqui é só o botão e a abertura. */
var BP={phone:600,tablet:880};
function drawer(shell){
  if(shell.querySelector(".shell__burger"))return;
  var b=document.createElement("button");
  b.type="button";b.className="shell__burger";
  b.setAttribute("aria-label","Abrir menu");
  b.setAttribute("aria-expanded","false");
  b.innerHTML="<i></i><i></i><i></i>";
  var bell=shell.querySelector(".nbell"),anchor=bell||shell.querySelector(".shell__spacer");
  if(anchor&&anchor.nextSibling)shell.insertBefore(b,anchor.nextSibling);else shell.appendChild(b);

  function close(){shell.classList.remove("is-open");b.setAttribute("aria-expanded","false");}
  b.onclick=function(e){
    e.stopPropagation();
    var open=!shell.classList.contains("is-open");
    shell.classList.toggle("is-open",open);
    b.setAttribute("aria-expanded",open?"true":"false");
    if(!open)closeAll();
  };
  /* escolher um destino fecha a gaveta; clicar fora e Esc também */
  shell.querySelectorAll(".shell__nav a,.shell__nav button").forEach(function(a){a.addEventListener("click",close);});
  document.addEventListener("click",function(e){if(!shell.contains(e.target))close();});
  document.addEventListener("keydown",function(e){if(e.key==="Escape")close();});

  var last="";
  function measure(){
    var w=shell.clientWidth||window.innerWidth;
    var k=w<=BP.phone?"phone":(w<=BP.tablet?"tablet":"desktop");
    if(k===last)return;
    last=k;shell.setAttribute("data-shell",k);
    if(k==="desktop")close();
  }
  /* o observer NÃO pode escrever no elemento observado dentro do próprio callback: as regras de
     [data-shell] mudam a altura do shell, o observer se reenfileira na mesma entrega e o Chrome
     acusa "ResizeObserver loop completed with undelivered notifications". Um quadro de espera
     tira a mutação da entrega. */
  var pending=false;
  function schedule(){
    if(pending)return;
    pending=true;
    requestAnimationFrame(function(){pending=false;measure();});
  }
  if(window.ResizeObserver)new ResizeObserver(schedule).observe(shell);
  window.addEventListener("resize",measure);
  measure();
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();
