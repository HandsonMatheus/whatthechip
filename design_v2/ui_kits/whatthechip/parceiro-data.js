/* WhatTheChip — grade de preços do parceiro (protótipo).
   Convenção da célula: número = preço em ¥ · "x" = não compro · "" = sem cotação · null = não fabricado.
   eMCP/uMCP são os únicos com FAIXA (par [mín,máx]). Canônicos nunca traduzem: eMMC, LPDDR, UFS, DDR, PHONE/PCB. */
(function(){
"use strict";
var BR_DDR=["Samsung","SK hynix","Micron","Nanya","Winbond","Outras"];
var BR_EMMC=["Samsung","SK hynix","Micron","Kioxia","YMTC","Outras"];

var D={
 emcp:{k:"emcp",n:"eMCP",d:"categorizado pelo armazenamento em GB",form:"uni",range:true,
   rows:[["eMCP 16GB","",[24,30]],["eMCP 32GB","",[44,52]],
         ["eMCP 64GB","",[62,74]],["eMCP 128GB","",[90,100]],
         ["eMCP 256GB","",""],["eMCP 512GB","","x"]]},
 umcp:{k:"umcp",n:"uMCP",d:"categorizado pelo armazenamento em GB",form:"uni",range:true,
   rows:[["uMCP 32GB","",[64,72]],["uMCP 64GB","",[86,98]],
         ["uMCP 128GB","",[112,128]],["uMCP 256GB","",[176,196]],
         ["uMCP 512GB","",[228,252]]]},
 lpddr:{k:"lpddr",n:"LPDDR",d:"memória de celular, por geração",form:"uni",groups:true,
   rows:[["§","LPDDR3"],["LPDDR3 1GB","",8],["LPDDR3 2GB","",14],
         ["§","LPDDR4"],["LPDDR4 2GB","",18],["LPDDR4 3GB","",26],["LPDDR4 4GB","",34],
         ["§","LPDDR4X"],["LPDDR4X 4GB","",40],["LPDDR4X 6GB","",""],["LPDDR4X 8GB","",""],
         ["§","LPDDR5"],["LPDDR5 8GB","",92],["LPDDR5 12GB","",""]]},
 ufs:{k:"ufs",n:"UFS",d:"armazenamento de celular",form:"uni",
   rows:[["UFS 2.1 32GB","",22],["UFS 2.1 64GB","",34],["UFS 2.2 128GB","",58],
         ["UFS 3.1 128GB","",72],["UFS 3.1 256GB","",118]]},
 emmc:{k:"emmc",n:"eMMC",d:"celular unificado × PCB por marca",form:"dual",brands:BR_EMMC,
   phone:[["eMMC 8GB","",6],["eMMC 16GB","",9],["eMMC 32GB","",15],["eMMC 64GB","",26],["eMMC 128GB","",44],["eMMC 256GB","",""]],
   pcb:[["eMMC 4GB",[4,3,3,"x",null,2]],["eMMC 8GB",[7,6,6,5,null,4]],["eMMC 16GB",[11,10,9,9,8,6]],
        ["eMMC 32GB",[17,16,"",15,13,10]],["eMMC 64GB",[29,27,"","",22,16]],["eMMC 128GB",[48,"","","",38,"x"]]]},
 ddr:{k:"ddr",n:"DDR",d:"memória de PCB, matriz por marca",form:"brand",brands:BR_DDR,
   rows:[["§","DDR3"],["DDR3 1GB",[3,3,2,2,"x",2]],["DDR3 2GB",[6,5,5,4,"x",3]],["DDR3 4GB",[11,10,9,8,null,6]],
         ["§","DDR4"],["DDR4 2GB",[9,8,8,7,null,5]],["DDR4 4GB",[16,15,14,"",null,9]],["DDR4 8GB",[28,26,"","",null,16]],
         ["§","DDR5"],["DDR5 8GB",[44,41,"",null,null,""]],["DDR5 16GB",[78,"","",null,null,""]]]},
 /* K9 é o único tipo com UMA linha só: o preço é único, não varia com o part number, a densidade
    nem a marca. Nada aqui ordena uma grade — nem densidade, nem faixa, nem marca —, então a
    tabela tem exatamente uma linha e um campo. */
 k9:{k:"k9",n:"K9",d:"NAND Samsung avulsa — preço único",form:"uni",by:"pn",
   rows:[["K9","qualquer part number · qualquer densidade",7]]},
 /* SSD não tem grade por densidade: o preço é linear em ¥/GB, com piso por peça. */
 ssd:{k:"ssd",n:"SSD",d:"preço linear ¥/GB — sem grade",form:"linear",
   caps:[128,256,512,1024],
   rows:[["SATA 2.5\" TLC","3D NAND · recondicionado",0.42,18],
         ["SATA 2.5\" QLC","3D NAND · recondicionado",0.31,14],
         ["M.2 SATA TLC","2280 / 2242",0.46,20],
         ["M.2 NVMe TLC","PCIe 3.0",0.62,26],
         ["M.2 NVMe QLC","PCIe 3.0",0.48,22],
         ["M.2 NVMe PCIe 4.0","TLC · alta densidade","",""]]}
};

/* linhas em revisão (moderação): pedido pendente, vale o preço antigo */
var REVIEW={"lpddr:LPDDR4 4GB":[34,40],"emcp:eMCP 64GB":[62,74],"ufs:UFS 3.1 256GB":[118]};

/* PEDIDOS TRAVADOS POR FALTA DE COTAÇÃO.
   É o estado "falta preço" da lista do cliente, visto do lado de quem pode resolver. A diferença
   entre isto e uma lacuna comum é a única que importa aqui: lacuna numa caixa que ninguém está
   vendendo pode esperar; lacuna que trava um lote já fechado é a fila de trabalho do comprador.
   Por isso não basta contar células vazias — a barra lateral conta as duas coisas, separadas. */
var BLOCK={
  ddr:  {box:"C-026",row:"DDR5 16GB",   orders:2,units:110,since:"01/08"},
  lpddr:{box:"C-031",row:"LPDDR4X 6GB", orders:1,units:140,since:"31/07"},
  emmc: {box:"C-005",row:"eMMC 256GB",  orders:1,units:90, since:"30/07"}
};
function blockOf(k){return BLOCK[k]||null;}
function blockTotal(){
  var o=0,u=0,n=0,k;
  for(k in BLOCK){n++;o+=BLOCK[k].orders;u+=BLOCK[k].units;}
  return {types:n,orders:o,units:u};
}

function isMiss(v){return v==="";}
function count(t){
  var lines=0,miss=0;
  function cell(v){if(v===null)return;lines++;if(isMiss(v))miss++;}
  if(t.form==="brand"){t.rows.forEach(function(r){if(r[0]==="§")return;r[1].forEach(cell);});}
  else if(t.form==="dual"){t.phone.forEach(function(r){cell(r[2]);});t.pcb.forEach(function(r){r[1].forEach(cell);});}
  else{t.rows.forEach(function(r){if(r[0]==="§")return;cell(r[2]);});}
  return {lines:lines,miss:miss};
}
var HREF={emcp:"parceiro-emcp.html",emmc:"parceiro-emmc.html",ssd:"parceiro-ssd.html"};
/* a ordem da barra é a do fluxo de triagem: memória de celular, memória de PCB, processador, NAND
   avulsa, SSD — não alfabética. */
var TYPES=["emcp","umcp","lpddr","emmc","ufs","ddr","k9","ssd"].map(function(k){
  var t=D[k],c=count(t);
  return {k:k,n:t.n,d:t.d,form:t.form,by:t.by||null,lines:c.lines,miss:c.miss,
    block:BLOCK[k]||null,href:HREF[k]||("parceiro-precos.html?tipo="+k)};
});
window.WTCPartner={DATA:D,TYPES:TYPES,REVIEW:REVIEW,BLOCK:BLOCK,blockOf:blockOf,blockTotal:blockTotal};
})();
