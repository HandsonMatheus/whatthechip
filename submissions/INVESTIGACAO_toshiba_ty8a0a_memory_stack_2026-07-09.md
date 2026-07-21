# Investigação — TY8A0A111173KC (e família "TY_A0A111...") — 2026-07-09

> **RESOLVIDO (3ª rodada, ver final do arquivo):** tabela rf-china.com confirma tipo **eMCP** e dá
> capacidade explícita pra 2 PNs (TY8A0A111173KC, TYAB0A111128KC) — submetidos em
> `toshiba-kioxia_ty_family_2026-07-09.yaml`, confidence=distributor (permissão do dono p/ Tier-3
> nesta família), validado: `assess_profitability` = NÃO RENTÁVEL nos dois, mesmo sem confirmar
> geração exata da RAM.

## PN de origem

`TY8A0A111173KC` — buscado na bancada, `known: false`, sem família nenhuma no engine (nem
fuzzy), caiu em `in_review_queue`. Prefixo "TY" não bate com TYC/TYD (já mapeadas, mas essas têm
3-char prefix + estrutura diferente).

## Padrão estrutural identificado (comparando 5 PNs)

Todos de 14 caracteres, formato **`TY` + [variante, 4 chars] + `111` (constante) + [lote, 3
dígitos] + [sufixo, 2 letras]**:

| PN | Variante (pos. 2-5) | Lote | Sufixo | Fonte |
|---|---|---|---|---|
| TY8A0A111173KC | 8A0A | 173 | KC | PN da bancada (este) |
| TY8A0A111503KC | 8A0A | 503 | KC | Worldway Electronics (bloqueado por bot-check) |
| TYAB0A111127KC | AB0A | 127 | KC | Alibaba (listado junto com o PN acima) |
| TY9A0A111308LA¹ | 9A0A | 308 | LA | iFixit, Motorola Droid RAZR Teardown — rotulado **"Memory Stack"** |
| TY9A0A111527KA¹ | 9A0A | 527 | KA | IC-Components.com (TAEC — Toshiba America) |

¹ iFixit/fonte grafou sem o "T" inicial ("Y9A0A...") — tratado aqui como o mesmo esquema.

**Achado à parte (família DIFERENTE, mesmo super-prefixo "TY9", SEM o "A0A"):** `TY90HH131439RC`,
`TY90GH131451RC`, `TYA0HH131570RC` aparecem juntos num anúncio AliExpress/imall.com como
**"EMMC16G Font library"** — ou seja, eMMC 16GB, mas com estrutura `TY9`+`0H`/`0G`+`H`+`13`+lote+
sufixo (o MESMO padrão já mapeado da família TYC/TYD, só com prefixo "TY9"/"TYA0" em vez de
"TYC"/"TYD"). **Isso é uma pista separada e não confirma nada sobre o padrão "A0A111" do PN
buscado** — são famílias com estrutura visivelmente diferente, não posso misturar as duas.

## O que NÃO consegui confirmar (apesar de busca ampla)

- **chip_type**: iFixit rotulou o único achado com contexto ("Y9A0A111308LA") como **"Memory
  Stack"** — termo deliberadamente vago que a própria iFixit usa quando NÃO consegue identificar
  o conteúdo exato (RAM? Flash? MCP combinado?) sem decapsular o chip. Nenhuma outra fonte
  (distribuidor, datasheet) confirma o tipo.
- **capacidade**: nenhuma fonte, nem para o PN buscado nem para nenhum irmão estrutural, cita
  densidade/capacidade.
- **fabricante/linha exata**: "TY" aparece em MÚLTIPLAS linhas de produto Toshiba distintas (ex.:
  achei também `TY58FVM7T2B/7B2B`, um NOR flash MCP totalmente não relacionado, via EE Times
  2004) — ou seja "TY" não é uma família única, é só "Toshiba" + código arbitrário. Não dá pra
  assumir que o padrão "A0A111" é eMCP/eMMC só por analogia com TYC/TYD.

## Fontes tentadas e por que bloquearam

- Worldway Electronics (tinha "Datasheet" no título) → bot-check "Verify you are human", texto
  não veio.
- Alibaba (listava o PN exato + irmão TYAB0A111127KC) → página client-rendered, sem conteúdo no
  fetch direto.
- Kynix, HKInventory (inclusive a página que agrupa vários `TY8A0A1111xx`) → vazias no fetch.
- Octopart → confirma só existência + 1 distribuidor (Run Hong Electronics, 3.968 em estoque),
  sem campo Description/Specification renderizado no fetch estático.
- Chrome (Claude in Chrome) → extensão não conectada nesta sessão (tentei 2x), não consegui
  escalar pra ver as páginas renderizadas via JS.

## Conclusão — NÃO submeto nada agora

Regra do dono ("nunca adivinhar known_part", memória `wtc-excluir-nao-adivinhar-known-part`):
sem confirmar nem TIPO nem CAPACIDADE em nenhuma fonte, este PN e seus 4 irmãos estruturais
ficam **fora** de qualquer submissão — nem gramática (nem magra, porque magra ainda exige
`chip_type` declarado) nem known_part. Continuam em `in_review_queue` no WhatTheChip até
aparecer uma fonte melhor.

## Como desbloquear no futuro

- Datasheet real da Toshiba/TAEC para a linha "TY_A0A111..." (não achei nenhum indexado).
- Acesso ao Worldway Electronics ou Alibaba via navegador real (bot-check bloqueou o fetch
  automatizado nesta sessão).
- Inspeção física do chip na bancada (contagem de pinos/BGA, medição, ou teste elétrico) — fora
  do escopo deste chat, mas é a fonte mais confiável se aparecer de novo.

## 2ª rodada (2026-07-09, a pedido do dono) — mais irmãos + hipótese de tipo (ainda NÃO confirmada)

### Mais irmãos estruturais encontrados (via ic37.com, snippet de busca — página em si não abriu)
- `TY8A0A111176LA` (lote "176", bem perto do PN da bancada "173")
- `TY9A0A111300KA`
- `TYAB0A111127KC(FH)`
- `TY9A0A111418L8` — achado via TechSpot: **substituiu o Hynix H90H1GH51JMP na MESMA posição**
  (PoP em cima do TI OMAP4430) em revisões posteriores do Droid RAZR. Isso é uma pista forte de
  COMPATIBILIDADE FUNCIONAL (mesmo soquete/interface), não confirmação de specs.

### Hipótese de tipo — LPDDR2 RAM PoP (NÃO Tier-1, é inferência arquitetural)
Duas pistas convergentes, nenhuma delas um datasheet do próprio chip:
1. **Posição física**: o chip "Memory Stack" fica em cima do TI OMAP4430 — essa é a posição PoP
   padrão desse SoC, e a família OMAP44xx usa PoP JEDEC LPDDR2 nessa posição (TI confirma PoP de
   4Gbit/die LPDDR2-S4B pro OMAP4460/4470 — não achei o dado exato pro 4430, mas é a mesma família
   de package).
2. **Naming convention**: o chip que SUBSTITUIU o Toshiba nessa posição (Hynix H90H1GH51JMP) usa
   prefixo "H9" — a MESMA convenção de prefixo que as famílias Hynix já mapeadas neste projeto
   pra RAM móvel PoP (H9TQ, H9HQ, H9TA, H9HCN — todas LPDDR3/LPDDR4). Reforça que a posição/função
   é RAM, não flash — mas não achei datasheet nem do H90H1GH51JMP (também sem documentação
   pública, textbook de PN semi-custom vendido direto pro fabricante do celular).

**Isto NÃO é confirmação Tier-1** — é inferência por posição+convenção, categoricamente mais fraca
que um datasheet ou teardown que cite o tipo diretamente. Capacidade continua zero confirmada.
Decisão de como proceder (submeter como `estimated` com essa ressalva, ou continuar excluindo até
prova melhor) fica com o dono — ver conversa no chat 2026-07-09.
