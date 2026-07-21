# Investigação — FBGA JW500, família MT29C (2026-07-09)

> ✅ **RESOLVIDO 2026-07-09 (tarde) — os dois pontos em aberto fecharam.**
> (1) Capacidade: o dono trouxe o link do DigiKey do PN-irmão
> `MT29C8G96MAZBADJV-5 IT` (mesma densidade `8G96M`), confirmando via
> categoria paramétrica estruturada "8Gbit (NAND), 4Gbit (LPDRAM)" a
> capacidade que antes era só extrapolação. (2) `chip_type`: o dono
> apontou que **já existe** `chip_type="MCP"` em `chips/chip_types.py`
> (category `catalog`, `profit_family="dead"`, `commercial=False`,
> descrito no código como "NAND raw + mDDR1 pré-eMCP, sem liquidez B2B")
> — testado por ele, resulta em NÃO RENTÁVEL + descarte por geração
> direto no gateway. Recategorizado de `eMCP`(minha tentativa inicial,
> por aproximação) → `MCP`. JW500 entrou em
> `micron_jw500_family_2026-07-09.yaml` (confirmed, chip_type=MCP,
> subtype descritivo "Raw MCP — NAND 1GB + mDDR1 512MB") e o MICRON.md
> foi corrigido (§4 armadilhas + §7 histórico + intro) com autorização
> do dono. Pendência residual: recategorizar eventuais MT29C já
> confirmados no banco de eMCP→MCP — fora do meu acesso, fica pro dono.
>
> Texto original da investigação preservado abaixo para histórico.

## O PN

API FBGA oficial da Micron (fetch direto, 2026-07-09): **JW500 → `MT29C8G96MAZAPDJA-5 IT`**.

## Achado 1 — MT29C NÃO é "NAND raw sem RAM" (contraria MICRON.md linhas 96/134)

`MICRON.md` diz hoje, duas vezes:
- L.96: `⚠ MT29C ≠ eMCP — a letra "C" é barramento paralelo, não "Combo". É NAND Flash raw (TSOP/parallel), sem RAM → resíduo.`
- L.134: `MT29C = NAND raw, não "eMCP LPDDR2": "C" = barramento paralelo.`

Achei o **datasheet oficial da Micron** pro PN citado como exemplo no próprio
`CLAUDE.md` (seção "Armadilhas comuns", o exemplo de PN-raw-vs-normalizado):
`MT29C4G48MAZAPAKD-5 IT` → indexado no Alldatasheet.com, arquivo Micron
genuíno (`152ball_nand_lpdram_j4xx_omap.fm - Rev. E 4/09`):

> **"NAND Flash and Mobile LPDRAM 152-Ball Package-on-Package (PoP)
> Combination Memory (TI OMAP™) — MT29C Family"**

E a página 2 (Part Numbering Information) confirma no próprio legend do
part number: **"29C = NAND + LPDRAM MCP"** — é a definição do prefixo,
não uma exceção pontual. A página 3 ("Table 1: Production Part Numbers")
lista 12 PNs de produção reais, cada um cross-referenciado a um NAND
standalone (ex.: `MT29F4G16ABCWC-ET`) **e** um LPDRAM standalone (ex.:
`MT46H32M32LFJG-6 IT`) — ou seja, o pacote FISICAMENTE contém as duas coisas
empilhadas (PoP = Package-on-Package), com **interfaces separadas** (não é
um controller eMMC unificado como o eMCP Samsung/SK Hynix que já
conhecemos — mais parecido com "dois chips discretos, um em cima do
outro, mesmo encapsulamento").

**Conclusão:** a frase do MICRON.md ("sem RAM → resíduo") parece **errada**
pelo menos pra este subconjunto do MT29C (o cluster de PNs com "AP" na
posição logo após a densidade — ver achado 2). Not: não auditei se
existe OUTRO subconjunto do MT29C que seja de fato raw-sem-RAM — só
confirmei que o que o CLAUDE.md cita como exemplo (e por extensão o nosso
alvo JW500, mesma estrutura) é combo NAND+LPDRAM.

Fonte: https://www.alldatasheet.com/datasheet-pdf/pdf/519880/MICRON/MT29C4G48MAZAPAKD-5IT.html
(páginas 1-3, texto extraído integralmente, ©2008/2009 Micron Technology).

## Achado 2 — a capacidade exata do JW500 é extrapolação, não leitura direta

O part-numbering chart oficial (página 2 do datasheet acima) documenta
densidades NAND `1G/2G/4G` (Gbit) e LPDRAM `12M/24M/48M` (=512Mb/1Gb/2Gb) —
sempre dobrando. Nosso alvo tem **`8G96M`**: seguindo a MESMA progressão
geométrica (dobrar de novo), seria NAND=8Gb(1GB) + LPDRAM=96M=4Gb(512MB).
**Mas isso é extrapolação minha** — nenhum dos 12 PNs na "Table 1" (a lista
de produção real) usa densidade `8G96M`, então não tenho uma linha da
tabela confirmando isso, só o padrão da fórmula.

Também não consegui achar o PN exato `MT29C8G96MAZAPDJA-5 IT` (nem seus
"irmãos" de mesmo bloco `AZAP*`/`AAF*`/`AAE*`) em NENHUM distribuidor
(Octopart: "no listings"; Mouser: sem resultado; DigiKey: sem retorno
útil) nem no catálogo de partes obsoletas da própria Micron (a página
`obsolete-nand-mcp-catalog` só tem dados pros PNs com "BA"/"BB" na mesma
posição — ver achado 3). WebSearch geral também não achou nada
específico pra `MT29C8G96M`.

**Por isso NÃO incluí o JW500 na submissão** (`micron_jw500_family_2026-07-09.yaml`)
— capacidade em branco/estimada violaria a regra "NADA de capacidade em
branco" (CLAUDE.md) e "nunca adivinhe/estime/infira" (AUTORIA.md).

## Achado 3 — dentro do MT29C, "AP" e "BA/BB" parecem ser sub-famílias DIFERENTES

Ao varrer a família via forward-lookup (prefixos `MT29C8G96M` e `MT29C4G48M`,
2026-07-09), percebi um padrão estrutural nítido, em DUAS densidades
diferentes:

| Padrão na posição pós-densidade | Exemplo | part-name/sub-category na API |
|---|---|---|
| `AP` (ex.: AZAP-, AAF-AP-, AAE-AP-) | `MT29C8G96MAZAPDJA-5 IT` (**nosso alvo**) | **vazio** em TODOS os ~15 PNs deste padrão, nas duas densidades |
| `BA`/`BB` (ex.: AZBAD-, AYBAD-, AZBBD-) | `MT29C8G96MAZBADJV-5 WT` (FBGA JW758) | **"MASSFLASH/MOBILE DDR 12G VFBGA"**, sub-category `obsolete-nand-mcp-catalog` (ou `nand-based-mcp` p/ variantes ativas) |

O cluster "BA/BB" é confirmado pela própria API da Micron como combo
NAND+LPDRAM (bate com o achado 1). O cluster "AP" (nosso alvo) nunca
aparece com part-name preenchido — nem no `8G96M` nem no `4G48M` — em
nenhuma das ~25 variantes que achei. Isso é consistente com "AP" ser uma
variante/revisão mais antiga ou rara que a Micron não manteve indexada
no sistema atual, mas **não tenho certeza do porquê** — só documentando o
padrão pra quem for investigar mais.

## O que precisa de decisão do dono antes de prosseguir

1. **Corrigir MICRON.md?** As linhas 96/134 ("MT29C = NAND raw, sem RAM")
   parecem desatualizadas/erradas pelo menos pro cluster "AP" — isso pode
   ter afetado classificações anteriores de outros PNs MT29C já no banco
   (não investiguei o banco, não tenho acesso).
2. **Como classificar JW500 no schema do WTC?** A arquitetura do MT29C
   (NAND raw + LPDRAM raw, **interfaces separadas**, sem controller eMMC
   unificado) é estruturalmente diferente do eMCP que já conhecemos
   (Samsung/SK Hynix/MT29T/MT29P — que usam controller eMMC + LPDDR).
   `chip_type: eMCP` capturaria a ideia geral (flash+RAM co-empacotados)
   mas pode estar semanticamente errado pro gateway/rentabilidade — não
   decidi isso sozinho.
3. **Vale a pena confirmar `8G96M` = 8Gb+4Gb via outra fonte** (talvez
   contato direto Micron, ou achar um datasheet de revisão mais nova que
   cubra densidades maiores) antes de submeter o JW500? Ou o dono prefere
   que eu registre como `PendingEntry`/deixe fora do banco até aparecer
   de novo na bancada com mais dados?

Assim que houver uma decisão, volto e completo o known_part do JW500 (ou
registro a decisão de não submeter por falta de fonte).
