/* WhatTheChip — barra de tipos de chip do parceiro.

   Navegação obrigatória: sem ela não se chega a nenhuma tabela de preço. Por isso ela vive num
   arquivo só e é carregada por TODAS as telas de preço, inclusive o Resumo — que antes era a única
   sem a barra, então a tela de entrada da seção era justamente a que não sabia navegar.
   Estar em toda tela é o que faz a barra ser confiável: a posição do item aceso é a única coisa
   que muda de página para página. */
(function(){
  "use strict";
  var host=document.getElementById("types");
  if(!host)return;
  var P=window.WTCPartner;if(!P)return;
  /* a chave da página: cravada (WTC_TYPE), vinda da query (tipo=), ou nenhuma — e nenhuma é o
     Resumo, não um estado inválido. [a-z0-9]+ porque chave de chip tem dígito (k9): com [a-z]+ o
     "k9" virava "k", não batia com nenhum tipo E não caía no Resumo — barra sem nada aceso. */
  var key=window.WTC_TYPE||(location.search.match(/[?&]tipo=([a-z0-9]+)/)||[])[1]||null;
  host.innerHTML='<a class="ptype'+(key?"":" on")+'" href="parceiro.html">'
      +'<span><span class="ptype__t">Resumo</span><span class="ptype__d">visão geral da grade</span></span></a>'
    +P.TYPES.map(function(x){
      /* DUAS CONTAGENS DIFERENTES, e por isso duas marcas. A âmbar conta lacuna: célula sem
         cotação, que pode esperar. A vermelha conta PEDIDO TRAVADO: lote já fechado que a
         plataforma não consegue precificar sem esta tabela — é fila de trabalho, não pendência
         de cadastro. Uma marca só somaria as duas e apagaria justamente a diferença. */
      return '<a class="ptype'+(x.k===key?" on":"")+'" href="'+x.href+'">'
        +'<span><span class="ptype__t">'+x.n+'</span><span class="ptype__d">'+x.d+'</span></span>'
        +(x.block?'<span class="ptype__b ptype__b--block" title="'+x.block.orders
            +(x.block.orders===1?' pedido travado':' pedidos travados')+' esperando a sua cotação">'+x.block.orders+'</span>':'')
        +(x.miss?'<span class="ptype__b">'+x.miss+'</span>':'')+'</a>';
    }).join("");
})();
