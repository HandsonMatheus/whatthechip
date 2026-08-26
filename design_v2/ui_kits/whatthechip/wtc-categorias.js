/* WhatTheChip — DICIONÁRIO DA CONVENÇÃO WTC.

   Duas coisas diferentes que o sistema inteiro precisa não confundir:

     CAIXA (C-###)     — o recipiente físico da bancada. É o que a linha do lote carrega, e é o que
                         define o PREÇO: todo part number dentro da mesma caixa vale o mesmo.
     CATEGORIA (L-##)  — a classificação. LETRA = tipo de chip, NÚMERO = a categoria.

   O NÚMERO É O MESMO NOS DOIS. Caixa 14 ⇒ categoria E-14. Isso é decisão de projeto, não
   coincidência: quem está com a caixa 14 na mão lê o código da categoria direto do rótulo dela,
   e os dois nunca divergem. Um mapa com numeração própria exigiria uma tabela de tradução na
   cabeça de quem separa material.

   ATENÇÃO — AS LETRAS SÃO PROVISÓRIAS. Foram inventadas para o protótipo (autorizado em 19/08:
   "pode inventar, na aplicação o claude corrige"). Elas moram todas neste arquivo, em LETTER,
   justamente para que trocá-las seja uma edição de um lugar só. */
(function(){
"use strict";

/* letra por tipo de chip. Trocar aqui muda todos os códigos do sistema. */
var LETTER={eMMC:"E",eMCP:"M",uMCP:"M",LPDDR:"L",UFS:"F",DDR:"D",K9:"K",SSD:"S"};

/* caixa → tipo + o que entra nela. A ordem é a do fluxo de triagem, igual à barra de tipos do
   parceiro: memória de celular, memória de PCB, NAND avulsa, SSD — nunca alfabética. */
var BOXES=[
  {box:"C-014",type:"eMMC",  desc:"eMMC de celular — preço unificado, vale para todas as marcas"},
  {box:"C-005",type:"eMMC",  desc:"eMMC de PCB — matriz por marca"},
  {box:"C-007",type:"eMCP",  desc:"multichip de celular (eMCP e uMCP), por armazenamento"},
  {box:"C-031",type:"LPDDR", desc:"memória de celular, por geração"},
  {box:"C-022",type:"UFS",   desc:"armazenamento de celular"},
  {box:"C-009",type:"DDR",   desc:"DDR3 de PCB — matriz por marca"},
  {box:"C-018",type:"DDR",   desc:"DDR4 de PCB — matriz por marca"},
  {box:"C-026",type:"DDR",   desc:"DDR5 de PCB — matriz por marca"},
  {box:"C-041",type:"K9",    desc:"NAND Samsung avulsa — preço único, independe do part number"},
  {box:"C-033",type:"SSD",   desc:"SSD — preço linear ¥/GB, com piso por peça"}
];

/* o número da CATEGORIA tem duas casas; o da caixa tem três porque a bancada numera até centenas.
   Reaproveitar o número é a decisão de projeto — arrastar o zero de preenchimento dela não é: daria
   "E-014" onde a convenção diz "E-14". */
function num(box){var m=/(\d+)/.exec(box||"");return m?("0"+parseInt(m[1],10)).slice(-2):"";}
function code(box,type){
  var l=LETTER[type]||"?";
  return l+"-"+num(box);
}
var BY={};
var ALL=BOXES.map(function(x){
  var o={box:x.box,type:x.type,desc:x.desc,code:code(x.box,x.type),n:num(x.box)};
  BY[x.box]=o;
  return o;
});
/* caixa que aparece num lote e não está no dicionário não pode sumir da tela: devolve um registro
   sintético, marcado, em vez de undefined. Uma caixa desconhecida é notícia, não ausência. */
function get(box){
  return BY[box]||{box:box,type:"—",desc:"caixa fora do dicionário — verificar com a plataforma",
    code:"?-"+num(box),n:num(box),unknown:true};
}

window.WTCCat={all:function(){return ALL.slice();},get:get,LETTER:LETTER};
})();
