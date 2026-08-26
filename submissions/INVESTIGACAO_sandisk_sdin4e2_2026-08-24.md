# Investigação — SanDisk `SDIN4E2` (cluster SDIN geração 4, indocumentada), PN SDIN4E232G (2026-08-24)

> ✅ **Resultado FINAL (atualizado 2026-08-24, 2ª decisão): 1 known_part, `confidence=manual`.**
> 1ª rodada: submetido `distributor` (evidência só de catálogo/Octopart, mesmo bucket documental
> "SDIN4xx" do cluster `SDIN4C2`, mas mais fraca — ver §1-§3 abaixo, ainda válidos como registro do
> processo). 2ª rodada: o dono deu instrução direta — **"confirmar o SDIN4E232G com as mesmas specs
> do SDIN5B232G"** (known_part `confirmed` desde 2026-07-14, e.MMC 4.41/X2/32GB). Apliquei
> interface+device de SDIN5B232G e subi pra `manual` (não `confirmed` — a fonte da equivalência é o
> dono, não uma leitura minha de datasheet/cross-ref pra ESTE PN; ver §8 novo). Arquivo:
> `sandisk_sdin4e2_2026-08-24.yaml`.

## 0. O gatilho

Debug do estoque, 24/08/2026 09:48:41, PN: `SDIN4E232G`. Família = `SDIN` (fallback genérico,
priority 80), `known_exact=false`, `confidence=estimated`, `profitable=INDETERMINADO`,
`pn_not_in_db=true`. Fuzzy sugeriu `SDIN5B232G`/`SDIN5E132G`/`SDIN8DE232G` — nenhum é o PN real.

## 1. Identidade — SDIN4E2-32G é real, mas o bucket 4xx segue sem datasheet

Confirmado como parte real, catalogada, SanDisk, eMMC, BGA, em **7+ catálogos independentes**:
Octopart/Avnet (autorizado) + ICPartonline/Worldway/Shengyu (não-autorizados), Kynix, Jotrin,
Preduo (campo "Type: eMMC" explícito), veswin.com (aparece como cross-ref em **5 páginas
distintas** de outros PNs — sinal de catálogo real, não PN inventado), alldatasheet.com (reconhece
o PN na busca, mas confirma — pela ausência — que não existe NENHUM datasheet indexado para
qualquer coisa começando com "SDIN4": o facet "Start with" da busca "SDIN" lista SDIN2/5/7/8/9/A/B,
**sem bucket SDIN4** — o mesmo buraco documental já registrado no tip para o cluster `SDIN4C2`
(ver `INVESTIGACAO_sandisk_sdin_2026-07-14.md` §4) se confirma para `SDIN4E2` também.

Pacote: TFBGA-169, faixa estendida -40°C~105°C, segundo a sumarização do Octopart (não reconfirmado
por leitura direta minha do HTML bruto — sinalizado como menos certo que o resto).

## 2. Cluster — só a capacidade -32G foi encontrada

Busquei explicitamente `SDIN4E2-4G`, `-8G`, `-16G`, `-64G` (regra de pesquisar o cluster inteiro,
não só o PN do caso) — **zero resultado** em qualquer capacidade além de -32G, em nenhuma fonte.
Ou é uma SKU de capacidade única, ou as outras simplesmente não circulam/não foram indexadas pelos
distribuidores pesquisados. Não submeto capacidades não encontradas (regra: excluir, não adivinhar).

## 3. Por que `distributor`, não `manual` (diferença chave vs. o cluster SDIN4C2)

O cluster `SDIN4C2` (rodada 2026-07-14) recebeu `confidence=manual` porque a evidência ia além de
catálogo de revenda: fórum TI E2E (engenheiro real citando datasheet do fabricante em mãos),
Elnec (fabricante de programador de chip, pinout real, hardware de adaptador dedicado) e iFixit
(prosa técnica de teardown de 2 aparelhos reais distintos). Para `SDIN4E2`, busquei especificamente
por essas 3 categorias de evidência mais forte — **nenhuma apareceu**:
- DigiKey/Mouser/Arrow: sem listagem.
- Fórum (TI E2E, Chromebook/coreboot, EEVblog): sem menção a `SDIN4E2` em nenhum resultado.
- Programador de chip (Elnec): sem listagem para este PN especificamente.
- Teardown (iFixit ou similar): sem menção.

Ou seja: tenho certeza razoável de que o PN **existe** (7+ catálogos independentes convergindo,
incluindo Octopart que tem hierarquia de confiança acima de distribuidor puro — ver CLAUDE.md
§6 "Hierarquia de fontes"), mas não tenho a mesma qualidade de evidência técnica que justificou
`manual` no 4C2. Sigo o mesmo princípio já aplicado em `SDMALBB2016G` (2026-07-15): consenso amplo
de distribuidor confirma identidade, mas não eleva o tier sozinho.

## 4. Achados de bônus (backlog, não pesquisados a fundo)

Durante a busca de cross-referências no veswin.com, apareceram repetidamente (mas fora do escopo de
hoje, sem verificação própria):
- **`SDIN4D2-2G`** — mesmo padrão "4 + letra + dígito" do bucket 4xx, só 1 menção, capacidade única
  vista.
- **`SDIN7DU2-8G` / `SDIN7DU2-16G`** — código "DU" dentro da geração 7, distinto do já confirmado
  `SDIN7DP2` ("Ultra", e.MMC 4.51). Pode ser uma sub-variante irmã não documentada no tip atual.
- **`SDINADF4-32G-H`** — sufixo "-H" adicional ao já conhecido SDINADF4 (geração e.MMC 5.1).

Nenhum desses foi pesquisado a fundo hoje (iam além do escopo do PN do caso) — ficam registrados
aqui e no tip da família como backlog para rodada futura.

## 5. known_part submetido (1) — histórico da 1ª rodada (ver §8 pra specs finais)

| PN | Tipo | Capacidade | Confidence | Fonte principal |
|---|---|---|---|---|
| ~~SDIN4E232G~~ | eMMC | 32GB | ~~distributor~~ → `manual` (§8) | Octopart + 6 outros catálogos independentes |

## 6. O que ficou de fora / limitações (1ª rodada)

- Sem datasheet, fórum, programador ou teardown para `SDIN4E2` especificamente — teto de
  confiabilidade PRÓPRIO era `distributor` (isso não mudou: o que mudou no §8 foi uma instrução do
  dono aplicando specs de OUTRO PN já confirmado, não uma fonte nova pra este PN).
- Pacote TFBGA-169/-40~105°C vem de sumarização de busca, não de leitura direta do HTML — por isso
  não entrou no known_part (só type+capacity, os dois com consenso mais amplo).
- Cluster de capacidades: só -32G confirmado, apesar de busca ativa por -4G/-8G/-16G/-64G.
- `SDIN4D2`, `SDIN7DU2`, `SDINADF4-...-H` — achados de bônus, resolvidos numa rodada separada, ver
  `submissions/INVESTIGACAO_sandisk_sdin7du2_sdinadf4h_2026-08-24.md`.

## 8. Resolução final — instrução direta do dono (2ª decisão, mesmo dia)

O dono pediu: **"pode confirmar o SDIN4E232G com as mesmas specs do SDIN5B232G"**.
`SDIN5B232G` é known_part `confirmed` desde 2026-07-14 (`submissions/sandisk_sdin_2026-07-14.yaml`),
fonte: datasheet oficial SanDisk 80-36-03433 Rev 1.3 (dez/2010), Tabela 12 "Ordering Information",
variante "5B2": `interface="e.MMC 4.41 (JESD84-A441)"`, `device="X2 (2 bits/célula)"`, 32GB.

Apliquei os mesmos `interface`/`device` ao `SDIN4E232G` (capacidade e chip_type já batiam). Busquei
por conta própria uma cross-referência de distribuidor que declarasse os dois PNs equivalentes —
**não achei nenhuma** (aparecem juntos nos mesmos catálogos/páginas várias vezes, mas nenhuma fonte
os declara como o mesmo produto ou substituto direto). Por isso a submissão final é
`confidence=manual`, não `confirmed`: a fonte real da equivalência é a instrução do dono, não uma
leitura minha de datasheet ou cross-ref específica pra este PN — mesmo padrão do override
`KMDL6001DA` (Samsung, fonte não-Tier-1 aceita caso a caso pelo dono).

**Isto NÃO generaliza pro resto do bucket `SDIN4xx`** — é uma resolução pontual deste PN exato.
`SDIN4C2` continua `manual` pela tríade fórum/programador/teardown já documentada; `SDIN4D2`
continua sem known_part (zero evidência, ver investigação irmã de hoje). Se aparecer outro PN do
bucket 4xx, não presumir e.MMC 4.41/X2 por analogia — investigar de novo.

## 9. Fontes completas

- https://octopart.com/part/sandisk/SDIN4E2-32G
- https://www.kynix.com/productdetails/23916280/sandisk/sdin4e232g.html
- https://www.jotrin.com/product/parts/SDIN4E2_32G
- https://www.preduo.com/product/emmc/sdin4e2-32g
- https://www.veswin.com/product-SDIN4E2-32G.html (+ 4 outras páginas de cross-ref no mesmo site)
- https://www.alldatasheet.com/view_datasheet.jsp?Searchword=SDIN4E2-32G (confirma AUSÊNCIA de
  datasheet, reforça o buraco documental)

Arquivos internos consultados: `chips/knowledge/sandisk.yaml` (família SDIN), `chips/tests.py`
(grep "SDIN4" — sem golden anchor, sem conflito), `SANDISK.md`,
`submissions/INVESTIGACAO_sandisk_sdin_2026-07-14.md` (precedente do cluster 4C2, base da
comparação de tier no §3).
