# Investigação — SanDisk `SDIN7DU2` + `SDINADF4-...-H` (backlog resolvido, 2ª passada 2026-08-24)

> ⚠ **CORRIGIDO 2026-08-24 (revisão do dono, ver SANDISK.md §0):** a 1ª versão desta investigação
> classificou o cluster `SDIN7DU2` como `confidence=manual` com raciocínio ERRADO — "citei o número
> do datasheet mas o PDF não abriu, por isso manual". Isso não fecha a barra do `manual`: a regra é
> TRÊS fontes de engenharia convergentes (fórum + programador de chip + teardown/manual de placa),
> não a citação de um número de documento não lido. `manual` e `confirmed` são IGUALMENTE
> autoritativos sobre a gramática — rebaixar de confirmed pra manual não reduz risco nenhum.
> **Corrigido para `confidence=distributor`** nos 4 PNs `SDIN7DU2` (§1/§4 abaixo já refletem a
> correção). Os 4 `SDINADF4-...-H` NÃO mudam — leitura direta e completa do product brief oficial é
> exatamente a barra do `confirmed`.

> Contexto: depois de submeter `SDIN4E2-32G` (ver `INVESTIGACAO_sandisk_sdin4e2_2026-08-24.md`), o
> dono pediu para coletar mais fontes e confirmar. Usei isso para também resolver 2 achados de
> bônus flagados como backlog na mesma investigação: `SDIN7DU2` e `SDINADF4-...-H`. Um terceiro
> (`SDIN4D2`) foi buscado a fundo e **permanece sem evidência suficiente** — não vira known_part.
>
> ✅ **Resultado: 8 known_parts novos.** 4 `distributor` (cluster `SDIN7DU2`: 8/16/32/64G) + 4
> `confirmed` (cluster `SDINADF4-...-H`: 16/32/64/128G). Arquivo:
> `sandisk_sdin7du2_sdinadf4h_2026-08-24.yaml`.

## 1. `SDIN7DU2` — uma 2ª sub-linha "Ultra" dentro da geração 7, mais antiga que a SDIN7DP2 já confirmada

O tip da família já registrava `SDIN7DP2` = e.MMC 4.51 "Ultra" (doc oficial 80-36-03494, fev/2013).
A busca pelo achado de bônus `SDIN7DU2` revelou uma **segunda linha "Ultra"**, mais antiga:

- **Identidade:** confirmada por **Mouser** (distribuidor autorizado; "eMMC 8GB 4.41+ Ind. eMMC -25C
  a 85C", Series: SDIN7DU2, Tradename: iNAND, Product Type: eMMC) e **Avnet** (via Octopart, "SSD
  eMMC Seq. 70/11 IOPS 2000/200"). Package: 153-pin TFBGA, 2.7-3.6V (nominal 3.3V).
- **Datasheet oficial CITADO:** "Ultra e.MMC 4.41 I/F Released Data Sheet 80-36-03666 V1.2 May
  2012" — mesmo padrão de numeração `80-36-XXXXX` dos 3 datasheets já verificados em rodadas
  anteriores (00592/03433/03494). ⚠ **Não consegui renderizar o PDF** (2 tentativas de fetch direto
  na URL do Octopart, ambas vazias — possível bloqueio/formato não extraível). **Tier =
  `distributor`, NÃO `manual`** (corrigido — ver banner no topo): citar o número do doc sem ler não
  é uma das 3 fontes de engenharia que a barra do `manual` exige (§0.3 do SANDISK.md); a evidência
  real aqui é distribuidor autorizado (Mouser/Avnet) + dado técnico estruturado (Octopart), que é
  suficiente pra identidade/capacidade mas não pra autoridade sobre a gramática.
- **Capacidade — aritmética Gb→GB mostrada nas 4 (regra do projeto, nunca só declarar):**
  - `SDIN7DU2-8G`: Octopart "Technical Specifications → Density: 64 Gb". 64 ÷ 8 = **8 GB** ✓ bate
    com o sufixo. Descrição Vericalcal: "Flash Card 8G-**byte**".
  - `SDIN7DU2-16G`: Density 128 Gb. 128 ÷ 8 = **16 GB** ✓. Vericalcal: "16G-byte".
  - `SDIN7DU2-32G`: descrição "256G-bit 256G/64G/32G". 256 ÷ 8 = **32 GB** ✓. Vericalcal: "32G-byte".
  - `SDIN7DU2-64G`: descrição "512G-bit 512G/128G/64G". 512 ÷ 8 = **64 GB** ✓.
  - As 4 capacidades convergem exatamente na mesma regra (÷8) — não é 1 caso isolado, é o padrão
    inteiro do cluster, o que reforça a confiança apesar de eu não ter lido o PDF.
- **Metadados de supply-chain reais** (Octopart): HTS 8542.31.00.30, Introduction Date 2013-05-08,
  Lifecycle Obsolete, LTB 2019-12-31, LTD 2020-12-31 — dado concreto que só existe pra peça real
  distribuída de verdade, não um PN inventado.
- **Não busquei/achei `SDIN7DU2-4G`** (só 8/16/32/64G têm página própria no Octopart).

## 2. `SDINADF4-...-H` — "iNAND 7232", CONFIRMADO via product brief oficial WD 2017

A página do TrustedParts para `SDINADF4-16G-H` linkava um PDF hospedado em `mouser.com`:
"SanDisk_10092017_iNAND-Family-Brochure-for-M_C_022-1217148.pdf". **Consegui buscar e ler o PDF
completo** (diferente do caso SDIN7DU2 acima) — documento oficial Western Digital/SanDisk, título
interno **"BR07-iNAND-Embedded-Integrated-Solutions-US-0217-02"**, ©2017 Western Digital Corporation.

Tabela "Ordering Information" (lida na íntegra, não resumida por ferramenta de busca):

| Produto | Capacidade | Interface | Ordering |
|---|---|---|---|
| **iNAND 7350** | 32GB-256GB | e.MMC 5.1 HS400 | SDINBDD4-32G/64G/128G/256G |
| **iNAND 7232** | 16GB-128GB | e.MMC 5.1 HS400 | SDINADF4-16G-L/H, -32G-L/H, -64G-L/H, -128G-L/H |
| **iNAND 7250** | 8GB-64GB | e.MMC 5.1 HS400 | SDINBDG4-8G/16G/32G/64G |

`SDINADF4` = **iNAND 7232**, "2nd generation SmartSLC technology, boosting sequential write speeds
for smooth recording of 4K and UHD video" (texto do próprio brief). Confirma e detalha o que o tip
já registrava de forma genérica ("SDINADF = e.MMC 5.1", inferido do product brief 2015).

**Por que só `-H`, não `-L`:** a tabela oficial lista cada capacidade como par "`-L/H`", mas em TODA
a pesquisa de mercado (TrustedParts, Jotrin, electronicsdatasheets.com, Octopart, Mouser) **só
apareceu o sufixo `-H`** para 16G/32G/64G/128G — nunca `-L`. Não submeto `-L` (regra: excluir, não
adivinhar) — fica registrado como par oficial sem evidência de mercado, backlog.

**Achado de bônus dentro do mesmo PDF (backlog, não pesquisado hoje):** `SDINBDG4` = iNAND 7250
(8-64GB) e `SDINBDD4` = iNAND 7350 (32-256GB) — linhas irmãs no mesmo brief, mesma tabela. O tip já
citava os 3 prefixos de relance ("Sub-famílias") mas nenhum tinha known_part até hoje (`SDINADF4`
resolvido agora; `SDINBDG4`/`SDINBDD4` seguem backlog).

## 3. `SDIN4D2` — buscado a fundo, permanece SEM evidência suficiente

Diferente do 4E2, `SDIN4D2` **não apareceu em nenhum distribuidor autorizado** (Mouser, Octopart,
TrustedParts todos vazios) — só existe a 1 menção de cross-ref no veswin.com já registrada na
investigação de ontem. Busca adicional hoje não achou nada novo. **Não vira known_part** — fica
como backlog "não confirmável", categoria diferente de "não pesquisado ainda".

## 4. known_parts submetidos (8)

| PN | Tipo | Capacidade | Confidence | Cluster |
|---|---|---|---|---|
| SDIN7DU28G | eMMC | 8GB | distributor | SDIN7DU2 |
| SDIN7DU216G | eMMC | 16GB | distributor | SDIN7DU2 |
| SDIN7DU232G | eMMC | 32GB | distributor | SDIN7DU2 |
| SDIN7DU264G | eMMC | 64GB | distributor | SDIN7DU2 |
| SDINADF416GH | eMMC | 16GB | confirmed | SDINADF4-H (iNAND 7232) |
| SDINADF432GH | eMMC | 32GB | confirmed | SDINADF4-H (iNAND 7232) |
| SDINADF464GH | eMMC | 64GB | confirmed | SDINADF4-H (iNAND 7232) |
| SDINADF4128GH | eMMC | 128GB | confirmed | SDINADF4-H (iNAND 7232) |

## 5. O que ficou de fora / limitações

- `SDIN7DU2`: PDF do datasheet oficial citado mas não renderizado por mim — `distributor`, não
  `manual`/`confirmed` (citação sem leitura não fecha a barra do manual, §0.3). `-4G` não
  encontrado (só 8/16/32/64G têm página própria nos distribuidores).
- `SDINADF4-...-L`: existe na tabela oficial, zero evidência de mercado — não submetido.
- `SDIN4D2`: continua sem evidência suficiente mesmo após busca dedicada em distribuidores
  autorizados — não submetido.
- `SDINBDG4` (iNAND 7250) / `SDINBDD4` (iNAND 7350): achados no mesmo PDF oficial, capacidades e
  ordering já conhecidos (tabela acima), mas **não pesquisados/submetidos hoje** — ficam como
  backlog de alta confiança pra próxima rodada (já tenho a tabela oficial completa).

## 6. Fontes completas

- https://www.mouser.com/en/ProductDetail/SanDisk/SDIN7DU2-8G-I (Mouser, autorizado)
- https://octopart.com/part/sandisk/SDIN7DU2-8G (Density 64Gb, HTS, datas)
- https://octopart.com/part/sandisk/SDIN7DU2-16G (Density 128Gb)
- https://octopart.com/part/sandisk/SDIN7DU2-32G (256G-bit na descrição)
- https://datasheet.octopart.com/SDIN7DU2-8G-SanDisk-datasheet-41210172.pdf (citação do doc
  80-36-03666, PDF não renderizou)
- https://www.trustedparts.com/en/part/sandisk/SDINADF4-16G-H (autorizado: Mouser + Avnet)
- https://www.mouser.com/datasheet/2/669/SanDisk_10092017_iNAND-Family-Brochure-for-M_C_022-1217148.pdf
  (PDF oficial completo, lido na íntegra — fonte primária desta investigação)
- https://octopart.com/part/sandisk/SDINADF4-32G-H / SDINADF4-64G-H

Arquivos internos consultados: `chips/knowledge/sandisk.yaml` (família SDIN, tip atualizado 2x
hoje), `chips/tests.py` (grep "SDIN7DU2|SDINADF4|SDIN4D2" — sem golden anchor, sem conflito),
`SANDISK.md`, `submissions/INVESTIGACAO_sandisk_sdin4e2_2026-08-24.md` (origem do backlog de hoje).
