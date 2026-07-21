# Investigação — SanDisk `SDMAL` (NAND Apple-proprietária), a partir da leitura de bancada SDMALBB2C16G (2026-07-15)

> ✅ **Resultado: 1 known_part submetido, `confidence=distributor`** (tier baixo, decisão do dono
> 2026-07-15 — "aplicar essas specs pra SDMAL em tier mais baixo, já que ele é antigo mesmo").
> `SDMALBB2-016G`, NAND flash proprietária Apple (protocolo PPN, não eMMC JEDEC padrão), usada no
> **iPad Air (2013)**. Arquivo: `sandisk_sdmal_2026-07-15.yaml`.

## 0. O gatilho

Debug do estoque, 15/07/2026 14:43:43, PN lido na bancada: `SDMALBB2C16G` — **família = vazio**
(motor não reconheceu NADA, nem o fallback genérico `SDIN`), `known=false`, `fuzzy_suggestions=[]`.

## 1. Metodologia

2 buscas paralelas amplas (varredura de hipóteses de erro de leitura + mapeamento do espaço de
prefixos "SDMA*") depois que buscas diretas simples (`SDMALBB2C`, `SDMAGBB2C`, variações) não
acharam nada. Achado central me levou a apresentar a ambiguidade ao dono ANTES de decidir sozinho
(a feature `AskUserQuestion` falhou no meio da sessão — perguntei em texto puro no chat, ver
[[wtc-askuserquestion-fallback-texto]] na memória).

## 2. Achado principal: não é "SDMAG" — é `SDMAL` (ou irmã visual), NAND Apple-proprietária

Nenhuma busca (2 rodadas amplas, várias hipóteses de erro de leitura: L↔G, L↔1, B↔8, C↔O, C↔G)
achou QUALQUER evidência de "SDMAG" em lugar nenhum — nem com o sufixo do caso, nem isolado, nem em
nenhuma capacidade. **A família `SDMAG` já cadastrada no nosso yaml (desde antes desta investigação,
"PENDENTE: sem confirmação física") parece ser fantasma — zero footprint público em qualquer fonte,
em qualquer pesquisa, até hoje.** Sinalizado no tip (ver §5), **não removido** — decisão de
descadastrar é maior que o escopo de hoje, fica para o dono avaliar.

Em vez disso, as duas buscas convergiram — independentemente — num PN real e bem diferente:
**`SDMALBB2-016G`** (16GB), parte de uma família de NAND usada como storage interno em **iPads/
iPhones da era 2013-2014**, sob o protocolo proprietário da Apple ("PPN" — não é eMMC JEDEC padrão).
Confirmado (nome "SANDISK" explícito) em: Jotrin Electronics (título "SDMALBB4 032G SANDISK" e
"SDMALBB8 064G SANDISK", confirma o prefixo pela família toda, não só a capacidade do caso),
rflashdata.com, eBay, Parts4Cells, LeoParts, xfix.co.uk (guia de reballing) — **device: iPad Air**
(1ª geração, 2013, modelos A1474/A1475/A1476), **posição de placa U1600**.

**Comparação caractere a caractere** entre a leitura de bancada e o PN real (sem separador):
```
Lido:  SDMALBB2C16G
Real:  SDMALBB2016G   (de "SDMALBB2-016G")
                ^
       diverge só na posição 9: "C" (lido) vs "0" (real)
```
Hipótese mais provável (não confirmada visualmente): o hífen + zero de padding ("-0") da gravação a
laser, desgastado, foi lido como "C" — os outros 11 caracteres batem exatamente.

## 3. Ambiguidade de leitura entre 3 candidatos visualmente parecidos

A mesma capacidade (16GB) existe em pelo menos 3 prefixos de 8 caracteres quase idênticos, todos
"NAND Apple-proprietária, 16GB, era 2013-2014": `SDMALBB2`, `SDMFLBCB2`, `SDMDLBCB2`. Comparei o
nível de corroboração de cada um:
- **`SDMALBB2-016G`** — 5 fontes independentes (rflashdata, eBay, Parts4Cells, LeoParts, xfix.co.uk)
  + confirmado pela família irmã de capacidade (`SDMALBB4-032G`, `SDMALBB8-064G`, ambos no Jotrin com
  "SANDISK" explícito no título) — **mais forte dos 3**.
- `SDMFLBCB2-016G` — 3-4 fontes (EasyJTAG NANDKIT, wepro.ru, ispares.com.ua, PicClick) — usado no
  iPhone 6, não iPad Air.
- `SDMDLBCB2-016G` — mais fraco (1 menção hkinventory, 1 Alibaba, 1 anúncio Allegro arquivado).

**Decisão do dono 2026-07-15: seguir com `SDMAL`** (a opção mais corroborada). Não há confirmação
visual do chip físico — se a leitura real for outra das 3, é reconfirmação futura.

## 4. Chip_type: `NAND Flash` (não eMMC) — e a consequência de rentabilidade

Diferente da linha `SDIN`/`SDINB`/`SD5DH` (eMMC padrão JEDEC, datasheet/pinout público), a NAND
Apple-proprietária usa protocolo fechado (PPN) e normalmente exige ferramenta especializada
(JTAG/ISP, ex. EasyJTAG NANDKIT) pra ler/gravar — não é acessível via socket eMMC padrão. Por isso
classifiquei como **`chip_type: "NAND Flash"`** (categoria `nand_raw` em `chips/chip_types.py`), não
`eMMC`. **Consequência importante:** `NAND Flash` tem `profit_family="dead"` no vocabulário —
**qualquer PN desse tipo é automaticamente NÃO RENTÁVEL, independente da capacidade** (mesma regra
que já se aplica a NOR Flash/ePoP/OneNAND). Isso bate com o comentário do dono ("é antigo mesmo"),
mas é uma decisão TÉCNICA minha (não foi perguntada explicitamente) — sinalizando aqui com
transparência total pra reversão fácil se não for o que se pretendia. Tecnologia de célula (SLC/MLC/
TLC) NÃO confirmada por nenhuma fonte — deixei o campo em branco em vez de adivinhar (16GB em 2013
sugere MLC, mas é inferência, não fato).

## 5. Atualização no yaml (só a família `SDMAG`, sem mudança estrutural)

Adicionei ao `tip` da família `SDMAG` já existente (mantida `active: true`, sem mudar grammar) um
alerta: busca ampla 2026-07-15 não achou nenhuma evidência real do prefixo, e o PN que motivou a
suspeita de confirmação era na verdade `SDMAL` (família Apple-proprietária, não relacionada). Não
criei/toquei numa família `SDMAL` no yaml — é 1 PN isolado, mesma disciplina de `SD9`/`SD5DH26A`
(evidência insuficiente pra propor gramática posicional; se aparecerem siblings reais, reconsiderar).

## 6. known_part submetido (1)

| PN | Tipo | Capacidade | Confidence | Dispositivo |
|---|---|---|---|---|
| **SDMALBB2016G** (PN do caso, lido como SDMALBB2C16G) | NAND Flash | 16GB | distributor | iPad Air 2013, posição U1600 |

## 7. O que ficou de fora / limitações
- Sem datasheet Tier-1 (peça sob contrato exclusivo Apple, nunca documentada publicamente pela
  SanDisk) — teto de confiabilidade é distribuidor/loja de reparo, por isso `distributor`, não
  `manual`/`confirmed`.
- Leitura física não reconfirmada (ver §3) — se o PN real for `SDMFLBCB2`/`SDMDLBCB2`, é o mesmo
  chip_type/capacidade/rentabilidade, mas o PN exato no banco ficaria errado.
- Família `SDMAG` continua ativa no yaml, só com o alerta novo — decisão de descadastrar/investigar
  mais é do dono.
- `SDMALBB4-032G`/`SDMALBB8-064G` (siblings de capacidade, achados de bônus) — **não submetidos**
  hoje (fora do PN do caso, mesma classificação NAND Flash/dead esperada) — backlog se aparecerem na
  bancada.

## 8. Fontes completas
- https://www.jotrin.com/product/parts/SDMALBB8_064G (SANDISK explícito)
- https://www.jotrin.com/product/parts/SDMALBB4_032G (SANDISK explícito)
- https://www.rflashdata.com/sandisk-sdmalbb2-016g-50504e01数据恢复/
- https://www.ebay.com/itm/155958998411 (iPad Air, U1600, SDMALLBB2)
- https://leoparts.com/apple/ipad/ipad-air-nand-flash-emmc-ic-16gb-u1600-sdmallbb2.html
- https://parts4cells.com/ipad-air-nand-flash-emmc-ic-16gb-u1600-sdmallbb2.html
- https://xfix.co.uk/reballing-an-ipad-air-u1600-nand-ic/
- https://www.hkinventory.com/p/d/SDMALBB8064G.htm

Arquivos internos consultados: `chips/knowledge/sandisk.yaml` (família SDMAG), `chips/chip_types.py`
(vocabulário NAND Flash / profit_family="dead"), `SANDISK.md`.
