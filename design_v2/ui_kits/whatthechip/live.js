/* WhatTheChip — valores ao vivo. Onde a bancada está lançando chip agora, o número sobe sozinho:
   o dado cresce, a tela repinta e um marcador "+n" salta ao lado do valor.

   Regra de uso: só sobe o que ainda está em triagem. Lote fechado, enviado ou apurado é número
   final — mover isso mentiria. E nunca aplicamos na tela do próprio operador (triagem), onde é
   ELE quem lança: dois autores no mesmo número confundem quem digita.

   API — cada item descreve o que cresce e onde o marcador aparece:
     WTCLive.drive([{ key, bump:function(n){...}, el:function(){return node}, mode:"above"|"side",
                      flashEl:function(){return node} }], repaint)
     WTCLive.pop(node, n)   marcador solto
     WTCLive.stop()         encerra os laços da página
*/
(function(){
"use strict";
/* camadas do sistema: shell 40 · painel lateral 60 · modal 95. O marcador pertence ao conteúdo
   da página, então fica abaixo de tudo isso — nunca sobre uma janela aberta. */
var CSS=".wtc-pop{position:fixed;z-index:30;transform:translate(-100%,0);display:block;"
  +"font-family:var(--mono,ui-monospace),monospace;font-size:11px;font-weight:700;line-height:1;"
  +"color:#fff;background:var(--green-60,#198038);padding:3px 6px 4px;"
  +"box-shadow:0 2px 8px -2px rgba(0,0,0,.4);pointer-events:none;white-space:nowrap;"
  +"animation:wtcpop 1.05s cubic-bezier(.2,.8,.2,1) forwards}"
  /* nenhum quadro com Y positivo: a entrada é por opacidade e escala, nunca descendo sobre o valor */
  +"@keyframes wtcpop{0%{opacity:0;transform:translate(-100%,0) scale(.86)}"
  +"22%{opacity:1;transform:translate(-100%,-3px) scale(1)}"
  +"100%{opacity:0;transform:translate(-100%,-18px) scale(1)}}"
  +".wtc-pop--still{animation:none;opacity:1}"
  /* na folga horizontal o marcador não desloca para a esquerda nem sobe */
  +".wtc-pop--side{transform:none;animation:wtcpopside 1.05s cubic-bezier(.2,.8,.2,1) forwards}"
  +"@keyframes wtcpopside{0%{opacity:0;transform:translateX(-5px) scale(.86)}"
  +"22%{opacity:1;transform:translateX(0) scale(1)}"
  +"100%{opacity:0;transform:translateX(9px) scale(1)}}"
  +".wtc-pop--side.wtc-pop--still{animation:none;transform:none;opacity:1}"
  /* dentro de uma célula: o marcador é filho do próprio elemento, então rola e some junto com a
     linha — nunca fica flutuando sobre a página */
  +".wtc-pop--in{position:absolute;left:6px;top:50%;z-index:1;transform:translateY(-50%);"
  +"animation:wtcpopin 1.05s cubic-bezier(.2,.8,.2,1) forwards}"
  +"@keyframes wtcpopin{0%{opacity:0;transform:translateY(-50%) translateX(-4px) scale(.86)}"
  +"22%{opacity:1;transform:translateY(-50%) translateX(0) scale(1)}"
  +"100%{opacity:0;transform:translateY(-50%) translateX(7px) scale(1)}}"
  +".wtc-pop--in.wtc-pop--still{animation:none;transform:translateY(-50%);opacity:1}"
  +".wtc-lit{animation:wtclit .7s ease-out}"
  +"@keyframes wtclit{0%,32%{color:var(--blue-60,#0f62fe)}100%{color:inherit}}";
var slow=window.matchMedia&&window.matchMedia("(prefers-reduced-motion:reduce)").matches;
var timers=[];

function css(){
  if(document.getElementById("wtc-live-css"))return;
  var s=document.createElement("style");s.id="wtc-live-css";s.textContent=CSS;
  document.head.appendChild(s);
}
/* o marcador vive no <body> em posição fixa: assim nenhum overflow:hidden de card o corta.
   mode "above": nasce acima da linha do valor, alinhado à direita dele.
   mode "side":  nasce à direita da âncora, centrado na altura dela — para quando o espaço livre
                 do layout é uma folga horizontal, não o topo.
   mode "inline": entra DENTRO do elemento (position:relative), no vazio à esquerda de um número
                 alinhado à direita — rola com a linha e não depende de coordenada de tela. */
function pop(el,n,mode){
  if(!el)return;
  css();
  var p=document.createElement("span");
  p.textContent="+"+n;
  /* inline: entra como filho da célula (que precisa ser position:relative) */
  if(mode==="inline"){
    p.className="wtc-pop wtc-pop--in"+(slow?" wtc-pop--still":"");
    el.appendChild(p);
    setTimeout(function(){p.remove();},slow?900:1100);
    return;
  }
  var r=el.getBoundingClientRect();
  if(!r.width&&!r.height)return;
  p.className="wtc-pop"+(mode==="side"?" wtc-pop--side":"")+(slow?" wtc-pop--still":"");
  if(mode==="side"){
    p.style.left=(r.right+6)+"px";
    p.style.top=Math.max(2,r.top+r.height/2-9)+"px";
  }else{
    p.style.left=(r.right+1)+"px";
    p.style.top=Math.max(2,r.top-24)+"px";
  }
  document.body.appendChild(p);
  setTimeout(function(){p.remove();},slow?900:1100);
}
function flash(el){
  if(!el||slow)return;
  css();el.classList.remove("wtc-lit");
  void el.offsetWidth;
  el.classList.add("wtc-lit");
  setTimeout(function(){el.classList.remove("wtc-lit");},760);
}

/* um laço por item, cadência sorteada a cada volta — dois lotes nunca pulsam em sincronia */
function drive(items,repaint){
  css();
  items.forEach(function(it,i){
    var run=function(){
      if(!document.hidden){
        var n=1+Math.floor(Math.random()*3);
        it.bump(n);
        if(repaint)repaint();
        var node=it.el&&it.el();
        if(node)pop(node,n,it.mode);
        var lit=it.flashEl?it.flashEl():node;
        if(lit)flash(lit);
      }
      timers.push(setTimeout(run,1000+Math.random()*2000));
    };
    timers.push(setTimeout(run,600+i*800+Math.random()*900));
  });
}
function stop(){timers.forEach(clearTimeout);timers=[];}

window.WTCLive={drive:drive,pop:pop,flash:flash,stop:stop,reduced:slow};
})();
