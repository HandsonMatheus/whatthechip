/* WhatTheChip — AVISOS DA PLATAFORMA. Comunicação de mão única: quem publica é a plataforma,
   quem lê é o cliente. Não confundir com notificações (eventos do próprio registro do cliente):
   aviso é política — mudança de preço, de regra, de prazo. Curto no painel, inteiro na página.

   Os dados moram aqui para que o quadro do painel e o histórico nunca divirjam. */
(function(){
"use strict";

var KIND={
  precos:   {tag:"tag--info",  label:"PREÇOS"},
  operacao: {tag:"tag--maybe", label:"OPERAÇÃO"},
  sistema:  {tag:"tag--mute",  label:"SISTEMA"}
};

/* mais recente primeiro — a ordem da lista é a ordem de publicação */
var LIST=[
 {id:12,d:"02/08",kind:"precos",
  t:"LPDDR4X 4GB e 6GB sobem 6% a partir de 05/08",
  lead:"O reajuste vale para lotes fechados a partir de segunda-feira. Lotes já despachados mantêm a taxa travada no fechamento.",
  body:[
   "A demanda por LPDDR4X de 4GB e 6GB subiu de forma consistente nas últimas seis semanas e a nossa tabela ficou defasada em relação ao mercado de Shenzhen. A partir de <b>05/08</b> os dois preços sobem 6%:",
   "<ul><li>LPDDR4X 4GB — de ¥ 40 para <b>¥ 42,40</b> por chip</li><li>LPDDR4X 6GB — de ¥ 58 para <b>¥ 61,50</b> por chip</li></ul>",
   "O reajuste é aplicado no <b>fechamento do lote</b>, não no despacho. Se o seu lote já foi fechado antes de 05/08, ele mantém o preço e o câmbio travados naquele dia — inclusive se a caixa ainda estiver a caminho.",
   "As demais capacidades de LPDDR4X e toda a linha LPDDR4 seguem sem alteração."]},

 {id:11,d:"28/07",kind:"operacao",
  t:"Volume mínimo de envio passa a 10.000 chips",
  lead:"Lote com menos de 10.000 unidades não fecha. A régua vale para todos os lotes abertos a partir de 01/08.",
  body:[
   "O custo de recebimento e conferência é praticamente o mesmo para uma caixa de 2.000 chips e uma de 12.000. Para manter o preço por chip onde está, o volume mínimo de envio sobe para <b>10.000 unidades</b> por lote.",
   "Não há exceção: o botão de fechar lote só libera a partir de <b>10.000 unidades</b>. Abaixo disso o lote continua aberto, recebendo lançamentos normalmente — o que muda é só o momento em que ele pode virar venda.",
   "A régua de progresso na tela do lote mostra quanto falta para as 10.000. Se você costuma trabalhar com volumes menores, acumule dois ou três recolhimentos no mesmo lote antes de fechar."]},

 {id:10,d:"21/07",kind:"precos",
  t:"DDR3 2GB sai da tabela e passa a avaliação por peça",
  lead:"O mercado de DDR3 2GB ficou irregular demais para um preço fixo. A capacidade continua sendo aceita, agora avaliada individualmente.",
  body:[
   "Os últimos lotes de DDR3 2GB tiveram variação de mais de 40% no valor de revenda dependendo do fabricante e do estado da peça. Um preço único de tabela deixou de fazer sentido — estava punindo lote bom e premiando lote ruim.",
   "A partir de agora a DDR3 2GB é classificada como <b>avaliação individual</b>. Na triagem ela vai para a caixa geral, e o valor sai na conferência, peça por peça. O resultado detalha cada PN na aba Chips.",
   "As demais capacidades de DDR3 seguem com preço de tabela normalmente."]},

 {id:9,d:"14/07",kind:"sistema",
  t:"Resultado da conferência agora sai em até 3 dias úteis",
  lead:"A segunda bancada de conferência entrou em operação e o prazo caiu de 7 para 3 dias úteis a partir do recebimento.",
  body:[
   "Montamos uma segunda bancada de conferência dedicada a lotes de placa (PCB), que eram os mais demorados. Com ela, o prazo entre <b>Recebido</b> e <b>Resultado</b> cai de 7 para <b>3 dias úteis</b>.",
   "O prazo conta a partir da chegada da caixa, não do despacho. O status na tela da venda mostra em que etapa o seu lote está a qualquer momento.",
   "O prazo de repasse não muda: até 5 dias úteis depois de você aceitar o resultado."]},

 {id:8,d:"03/07",kind:"precos",
  t:"eMMC 128GB entra na tabela",
  lead:"A capacidade que antes ia para avaliação individual agora tem preço fixo de ¥ 44 por chip.",
  body:[
   "Com volume suficiente nos últimos meses, conseguimos fechar um preço estável para <b>eMMC 128GB: ¥ 44 por chip</b>.",
   "Na prática isso significa que você já sabe quanto vale a peça no momento da triagem, em vez de esperar a conferência. A capacidade sai da caixa geral e passa a ter destino próprio.",
   "eMMC de 256GB e acima continuam em avaliação individual."]}
];

var K="wtc_avisos_read";
function readSet(){
  try{var v=JSON.parse(localStorage.getItem(K)||"[]");return Array.isArray(v)?v:[];}catch(e){return [];}
}
function isRead(id){return readSet().indexOf(id)>=0;}
function markRead(id){
  var s=readSet();
  if(s.indexOf(id)<0){s.push(id);try{localStorage.setItem(K,JSON.stringify(s));}catch(e){}}
}
function unread(){return LIST.filter(function(a){return !isRead(a.id);}).length;}
function get(id){return LIST.filter(function(a){return a.id===+id;})[0];}

window.WTCAvisos={all:function(){return LIST;},get:get,kind:function(k){return KIND[k]||KIND.sistema;},
  isRead:isRead,markRead:markRead,unread:unread};
})();
