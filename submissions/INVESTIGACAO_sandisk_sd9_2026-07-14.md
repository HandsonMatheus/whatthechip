# Investigação — SanDisk `SD9DS28K-8G` (eMCP isolado) + cluster `SDIN9xx` (eMMC), a partir do PN SD9DS28K8G (2026-07-14)

> ✅ **Resultado FINAL (após precheck no `--commit`): 4 known_parts submetidos**, todos `manual`.
> Pesquisa original achou 11 candidatos (7 `confirmed`, 4 `manual`); a 1ª tentativa de `--commit`
> quebrou com `IntegrityError` em `SDIN9DW416G` (mesmo mecanismo do incidente `SDADB48K16G` de
> ontem — lookup por `part_number` exato, não normalizado). O precheck rodado pelo dono revelou que
> **7 dos 11 já existiam no banco local, todos `approved`**: os 4 `SDIN9DS2-*` e o `SDIN9DW4-64G`
> já estavam idênticos ao que eu ia submeter; `SDIN9DW4-16G` e `SDIN9DW4-32G` já existiam, mas como
> `manual` e com traço no `part_number` (por isso a colisão) — ver §6 pra oportunidade de
> upgrade desses 2. **Arquivo final:** `sandisk_sd9_2026-07-14.yaml`, só com o que era genuinamente
> novo: `SD9DS28K-8G` (eMCP isolado) + `SDIN9DW5-16G/32G/64G`. **Nenhuma família nova foi criada no
> yaml para o prefixo SD9 — ver §3 para o porquê.**

## 0. O gatilho

Debug do estoque, 14/07/2026 13:30:55, PN `SD9DS28K8G`: **família = vazio** (`—` em todos os campos
do motor — nem o fallback genérico `SDIN` capturou), `known_exact=false`, `in_review_queue=true`,
`fuzzy_suggestions=[]`. Diferente dos dois casos anteriores (SDAD, SDIN), aqui o motor não reconheceu
NADA — sinal de que o prefixo real não é `SDIN` (senão a família genérica teria batido).

## 1. Metodologia

3 buscas paralelas independentes (cluster `SD9`, resolução da ambiguidade "8+8", cluster `SDIN9xx`)
— mesma disciplina de ontem: proibição explícita de Edit/Write em cada prompt, checklist de fonte
Tier-1 antes de qualquer `confidence` alto.

## 2. Achado principal: `SD9DS28K-8G` é eMCP, não eMMC — e é um PN ISOLADO, não uma família

A busca literal pelo PN (com hífen) bateu direto num anúncio eBay: **"SANDISK SD9DS28K-8G SOLID
STATE DRIVE (SSD) EMCP 8+8 LPDDR3 FW 1.1"**. Ou seja: o prefixo `SD9` não tem relação com a família
`SDIN` (que é só eMMC) — é uma família **eMCP** própria, tipo o `SDAD`/`SDEM` já catalogados.

**Mas, depois de varredura exaustiva em ~25 distribuidores/agregadores + GitHub + fóruns de firmware
+ bancos de programador de chip, só existe ESSE UM PN.** Nenhum sibling de capacidade (`-4G`, `-16G`,
`-32G`, `-64G`) nem de die-code (`SD9DS3`, `SD9DW`, etc.) foi encontrado em lugar nenhum.

**Identidade resolvida com confiança alta — via manual oficial de HARDWARE (não SanDisk, mas do
fabricante da placa que usa o chip), fonte tão forte quanto um datasheet:**
- **Manual oficial de hardware do 96Boards DragonBoard 410c** (placa de desenvolvimento Qualcomm
  Snapdragon 410, programa Linaro/96Boards): *"The 410c uses a single embedded Multi Chip Package
  (eMCP)... The installed chip provides 8Gbyte of solid state storage and 1Gbyte of LPDDR3. The
  LPDDR3 is a 32bit width bus... The eMMC is an 8bit implementation... eMMC 4.5"*.
  `https://www.96boards.org/documentation/consumer/dragonboard/dragonboard410c/hardware-docs/hardware-user-manual.md.html`
- **Fórum oficial 96Boards, post de engenheiro da Qualcomm Canadá**, listando substitutos drop-in
  qualificados pro `SD9DS28K-8G` — todos descritos como "8GB eMMC, 1GB DRAM" (Kingston
  08EMCP08-NL3DT227, Micron MT29TZZZ8D5JKEZB-107/JKEPD-125). O MESMO post confirma
  textualmente: *"SanDisk doesn't post their datasheets on the web, you need to talk to SanDisk to
  get a copy of the datasheet"* — explica por que não existe datasheet público, sem ser
  especulação nossa. `https://discuss.96boards.org/t/dragonboard-ddr-swap/2302`

**"8+8" resolvido: é 8GB NAND + 8Gb (Gigabit) RAM = 1GB real**, não 8GB+8GB — triangulado por 3
linhas independentes:
1. Um revendedor eBay **diferente** do anúncio original já converteu e escreveu **"8+1"** pro
   MESMO PN (`https://www.ebay.com/itm/124056680022`) — confirma textualmente a conversão.
2. Datasheet oficial Nanya (mesma classe de produto — eMCP 221-ball + LPDDR3) tem tabela "Ordering
   Information" explícita: NAND em GB, RAM em **Gb** ("LPDDR3 4Gb(X32,SDP)") — mesma convenção do
   setor, não peculiaridade SanDisk.
   `https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/imx-processors/221114/1/4GB_LPDDR3_A_Die_eMCP_(4_4)_221b_Datasheet.pdf`
3. Checagem de plausibilidade em todo o "balde" 221-ball eMCP-D3 da Puris (mesma notação "X+X" em
   Samsung/SK Hynix/Toshiba concorrentes): GB+GB seria fisicamente/comercialmente absurdo pra RAM
   móvel dessa era (ex.: "32+32" viraria 32GB de LPDDR3), GB+Gb bate com o que existia no mercado.

**Package:** 221-ball FBGA (Preduo + Puris, convergente) — mesma classe da família irmã `SDAD`
(regra já documentada: 221-ball → LPDDR3). **Status:** obsoleto/EOL (Datasheets.com + fórum
96Boards). **FW:** só a revisão "1.1" apareceu em toda fonte — sem sinal de FW 1.0/1.2/2.0 irmãos.

## 3. Por que NÃO criei família nova no yaml

Com só 1 PN confirmável, não há como inferir com segurança onde o prefixo da "família" termina
(`SD9`? `SD9D`? `SD9DS`?) — e **arriscar isso é especialmente perigoso aqui**: confirmei que o
prefixo curto `SD9` sozinho já é reusado pela SanDisk numa linha **totalmente não relacionada** de
SSD SATA de consumo (`SD9SN8W-*`/`SD9SB8W-*`, produto final, não die eMCP) — uma gramática
posicional em `SD9` colidiria as duas famílias. Decisão: **tratar como known_part isolado** (Trilha
B), sem tocar no yaml. Se aparecerem PNs irmãos no futuro, a família pode ser criada então, com
evidência real de onde o prefixo corta — não antes.

## 4. Cluster `SDIN9xx` (backlog de ontem, resolvido hoje) — 2 datasheets técnicos oficiais

Na investigação anterior desta mesma família (`INVESTIGACAO_sandisk_sdin_2026-07-14.md`, mesmo dia,
rodada do PN `SDIN4C24G`) eu tinha sinalizado `SDIN9DW4/5`/`SDIN9DS2` como backlog "só broker".
Voltando ao cluster agora (porque o sufixo "9DS2" é visualmente parecido com o `SD9DS2` do caso de
hoje, mas são famílias DIFERENTES — `SDIN9DS2` tem o prefixo completo `SDIN`), achei:

**A) Product brief oficial SanDisk (© 2015), "SanDisk Commercial Embedded Storage Solutions"** —
`SDIN9DS2` = nome de produto **"iNAND 5130"**, eMMC 5.0 HS400, tabela com as 4 capacidades:

| PN | Capacidade | Seq R/W (MB/s) | Random R/W (IOPS) |
|---|---|---|---|
| SDIN9DS2-8G | 8GB | 250/13 | 3300/1000 |
| SDIN9DS2-16G | 16GB | 280/24 | 3300/1400 |
| SDIN9DS2-32G | 32GB | 280/40 | 3300/1700 |
| SDIN9DS2-64G | 64GB | 220/36 | 3300/1600 |

`https://www.mouser.com/datasheet/2/669/sandisk_12282015_Commercial%20Embedded%20Product%20Brief-792691.pdf`
(mesmo conteúdo hospedado em Arrow e pccomponents — 3 cópias idênticas).

**B) Datasheet técnico completo, doc. 80-36-03680 Rev 1.11 (fev/2015, © 2016 Western Digital)** —
`SDIN9DW4` = **"iNAND Extreme"**, eMMC 5.0 HS400, TFBGA153 11.5×13×1.0mm, tabela "Ordering
Information" com capacidade exata em bytes:

| PN | Bytes exatos | Write MB/s (cache on/off) | Read MB/s |
|---|---|---|---|
| SDIN9DW4-16G | 15.758.000.128 | 45/40 | 300 |
| SDIN9DW4-32G | 31.268.536.320 | — | — |
| SDIN9DW4-64G | 62.537.072.640 | 80/75 | 300 |

`https://www.mouser.com/datasheet/2/669/sandisk_sand-s-a0002571728-1-1747548.pdf` (mirror:
`file.elecfans.com/web2/M00/72/E3/pYYBAGNVUESAWgCnABxrTf4tSGM159.pdf`). **`SDIN9DW4-128G` aparece só
no Octopart, NÃO consta na tabela de ordering deste datasheet** — excluído da submissão por falta de
confirmação (pode ser revisão posterior do documento).

**C) `SDIN9DW5`** — sem datasheet oficial localizado, mas **5 fontes de mercado convergentes**
(Alibaba ×2, AliExpress, eBay, Worldway) confirmam `-16G`/`-32G`/`-64G`, pacote 153-ball FBGA,
"eMMC 5.0". Specs de performance não confirmadas. Submetido como `manual` (mesmo padrão de ontem
pro cluster `SDIN4C2`: convergência forte sem datasheet formal).

**Bônus — cronologia de geração confirmada** (mesmo product brief, tabela comparativa de "Interface
Family"): `SDIN7` (4.51) < `SDIN8` (4.51 HS200) < **`SDIN9` (5.0 HS400)** < `SDINADB` (5.0+) <
`SDINADF` (5.1) — estende a cronologia já documentada ontem no tip da família. `SDINADB`/`SDINADF`
ficam fora do escopo de hoje (prefixo `SDINA`, ainda não mapeado no yaml — próxima rodada).

## 5. known_parts pesquisados (11) vs. submetidos de fato (4)

| PN | Tipo | Capacidade | Confidence pesquisado | Situação real no banco |
|---|---|---|---|---|
| **SD9DS28K8G** (PN do caso) | eMCP | NAND 8GB / RAM LPDDR3 1GB | manual | **livre — submetido** |
| SDIN9DS28G | eMMC 5.0 HS400 | 8GB | confirmed | já existia, `approved`/`confirmed` idêntico — não resubmetido |
| SDIN9DS216G | eMMC 5.0 HS400 | 16GB | confirmed | já existia, `approved`/`confirmed` idêntico — não resubmetido |
| SDIN9DS232G | eMMC 5.0 HS400 | 32GB | confirmed | já existia, `approved`/`confirmed` idêntico — não resubmetido |
| SDIN9DS264G | eMMC 5.0 HS400 | 64GB | confirmed | já existia, `approved`/`confirmed` idêntico — não resubmetido |
| SDIN9DW416G | eMMC 5.0 HS400 | 16GB | confirmed | já existia como `SDIN9DW4-16G` (com traço), `approved`/**`manual`** — ver §6 |
| SDIN9DW432G | eMMC 5.0 HS400 | 32GB | confirmed | já existia como `SDIN9DW4-32G` (com traço), `approved`/**`manual`** — ver §6 |
| SDIN9DW464G | eMMC 5.0 HS400 | 64GB | confirmed | já existia, `approved`/`confirmed` idêntico — não resubmetido |
| SDIN9DW516G | eMMC 5.0 | 16GB | manual | livre — **submetido** |
| SDIN9DW532G | eMMC 5.0 | 32GB | manual | livre — **submetido** |
| SDIN9DW564G | eMMC 5.0 | 64GB | manual | livre — **submetido** |

(Nota de digitação: o PN correto normalizado do caso é `SD9DS28K8G`, sem "AD".)

## 6. Achado do precheck: 7/11 já cobertos, 2 com oportunidade de upgrade

O precheck (rodado pelo dono antes do `--commit`, depois do primeiro `IntegrityError`) revelou que
7 dos 11 PNs pesquisados **já estavam no catálogo antes desta investigação** — provavelmente de uma
sessão SanDisk anterior que eu não tinha visibilidade (o repositório é compartilhado entre sessões
concorrentes). 5 deles batem exatamente (mesma capacidade, mesmo confidence) — pesquisa redundante,
sem ação necessária. **2 são uma oportunidade real:** `SDIN9DW4-16G` e `SDIN9DW4-32G` já estão
`approved` mas como `confidence=manual`; a pesquisa de hoje achou o **datasheet técnico oficial
completo** (doc 80-36-03680 Rev 1.11, Western Digital) que cobre exatamente esses 2 PNs numa tabela
"Ordering Information" explícita — evidência mais forte que o que os classificou como `manual`
originalmente. `submit_known_parts` nunca faz esse upgrade sozinho (por desenho, pula qualquer PN
já `approved` em vez de sobrescrever) — fica registrado aqui para o dono decidir se vale editar os 2
registros no admin (id=10636, id=10637) para `confirmed`, citando esta fonte.

## 7. O que ficou de fora (backlog)

- **`SDIN9DW4-128G`** — só Octopart, sem confirmação na tabela oficial. Backlog.
- **Siblings de `SD9DS28K-8G`** — busca exaustiva não achou nenhum. Se aparecer outro PN `SD9...` na
  bancada, pesquisar de novo antes de assumir que é da mesma família (risco de colisão com a linha
  de SSD `SD9SN8W`/`SD9SB8W`, ver §3).
- **`SDINADB`/`SDINADF`** (gerações mais novas que a 9, achadas só de relance na tabela comparativa
  do product brief) — prefixo `SDINA`, fora do escopo desta rodada.

## 8. Fontes completas
- https://www.96boards.org/documentation/consumer/dragonboard/dragonboard410c/hardware-docs/hardware-user-manual.md.html
- https://discuss.96boards.org/t/dragonboard-ddr-swap/2302
- https://www.ebay.com/itm/184022333565 (anúncio original "8+8")
- https://www.ebay.com/itm/124056680022 (conversão "8+1")
- https://www.preduo.com/product/emcp/emmc-lpddr3/221ball/sd9ds28k-8g
- https://www.puris.net/archives/2975 e https://www.puris.net/emcplist
- https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/imx-processors/221114/1/4GB_LPDDR3_A_Die_eMCP_(4_4)_221b_Datasheet.pdf
- https://www.mouser.com/datasheet/2/669/sandisk_12282015_Commercial%20Embedded%20Product%20Brief-792691.pdf
- https://www.mouser.com/datasheet/2/669/sandisk_sand-s-a0002571728-1-1747548.pdf
- https://www.alibaba.com/product-detail/MSMWTRPM-SDIN9DW5-32G-153FBGA-EMMC-5_1600768284342.html

Arquivos internos consultados: `chips/knowledge/sandisk.yaml`, `SANDISK.md`, `chips/tests.py` (sem
âncora golden pra nenhum PN desta rodada — sem heads-up necessário desta vez).
