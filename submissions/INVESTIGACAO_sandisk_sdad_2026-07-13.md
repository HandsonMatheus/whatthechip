# Investigação — família SanDisk SDAD (eMCP), a partir do PN SDADL2BP32G (2026-07-13)

> ✅ **RESOLVIDO 2026-07-13.** O dono decidiu (pergunta no chat, ver §6): aceitar convergência de
> distribuidor como EXCEÇÃO DE SOURCING para esta família específica (sem datasheet público). 5 PNs
> submetidos em `sandisk_sdad_2026-07-13.yaml`: **1 confidence=manual** (`SDADA4CR128G`, coreboot) +
> **4 confidence=distributor** (`SDADL2BP32G` — o PN do caso original —, `SDADF4AP16G`,
> `SDADB48K16G`, `SDADA4CR64G`), cada um com 3+ fontes convergentes citadas nas notes. ~8 PNs
> continuam de fora (menos de 3 fontes, ou identidade ambígua — ver §3.2/§4). Texto original da
> investigação preservado abaixo.

## 0. O gatilho

Debug do estoque, 13/07/2026 19:26:26, PN `SDADL2BP32G`: família `SDAD` bate pela gramática,
`known_exact=false`, `profitable=INDETERMINADO` — exatamente o padrão já documentado no
`SANDISK.md` (marca declarativa, sem known_part não há capacidade). Objetivo: pesquisar o PN e
todo o cluster/família SDAD em fontes Tier-1, não só o PN isolado.

## 1. Metodologia

5 buscas paralelas independentes (fontes oficiais SanDisk/WD; distribuidores Tier-1/2; busca
direta do PN âncora; package/ball-count técnico; catálogos secundários/chineses) + verificação
direta minha (fetch) das duas evidências mais fortes que cada frente reportou, + 2 buscas diretas
adicionais minhas tentando achar datasheet oficial. Total: 6 frentes de pesquisa independentes.

## 2. Achado principal (durável): SDAD provavelmente é linha OEM-only, sem datasheet público

**Nenhuma das 6 frentes encontrou um datasheet, product brief ou página oficial SanDisk/Western
Digital que cite "SDAD" ou qualquer PN da família.** Isso inclui busca dedicada em
`sandisk.com`/`westerndigital.com`/`documents.sandisk.com` e busca por `filetype:pdf`. A linha
"iNAND" (prefixo `SDIN`, bem documentada nesses domínios) é eMMC/UFS puro — **não** é a família
eMCP. O brochure industrial/IoT mais recente da SanDisk (set/2025) nem lista eMCP como categoria
atual — só eMMC, UFS, NVMe, SATA, SD/microSD.

**Interpretação:** SKUs eMCP móveis da SanDisk desse tipo parecem ser vendidos direto a OEMs de
celular sob NDA, sem datasheet público — padrão comum no setor pra memória embarcada mobile
(mesma razão pela qual boa parte da concorrência também não documenta certas famílias mobile
publicamente). Não é evidência de PN falso — os PNs existem de verdade (ver §3) — só não há
literatura pública para citar como Tier-1 no sentido datasheet-do-fabricante.

## 3. Mapa do cluster (todos os PNs reais encontrados)

### 3.1 Confirmado — vai na submissão

| PN | Specs | Confiança | Fonte |
|---|---|---|---|
| **SDADA4CR-128G** | eMCP, NAND 128GB (sufixo declarativo), RAM **LPDDR4X 4GB** | **Manual** (evidência de engenharia testada, não datasheet) | [coreboot commit 640ca69](https://github.com/coreboot/coreboot/commit/640ca69c0589b2337d2f319c59dd937767be6036) — firmware Google ChromeOS, board "kukui" (MediaTek MT8183). Arquivo `sdram-lpddr4x-SDADA4CR-128G-4GB.c` com parâmetros REAIS de init de DDR (impedância, write-leveling), mensagem do commit *"Support SANDISK SDADA4CR-128G... EMCP LPDDR4X DDR bootup... TEST=Boots correctly on EMCP DRAM"*. Verifiquei o commit diretamente (fetch) — real, mergeado, revisado por engenheiro Google/Chromium. |

Por que confio nisto apesar de não ser datasheet SanDisk: é evidência de terceiro **testada
funcionalmente** (o device não bootaria com parâmetros de DDR errados), não uma alegação de
marketing/revenda. Trato como equivalente a Tier-1 pela natureza da fonte, mas **sinalizo para
sua revisão** por ser um tipo de fonte fora da hierarquia tradicional do projeto.

### 3.2 Candidatos reais, SEM fonte Tier-1 — ficaram de fora da submissão

Todos existem de verdade (múltiplas fontes independentes confirmam o PN), mas a geração/
capacidade da RAM só aparece em título de anúncio de distribuidor/marketplace (nunca campo
estruturado, nunca datasheet) — por isso violam a regra "excluir, não adivinhar" e ficaram fora.

**Sub-família 221-ball (presumivelmente LPDDR3 pela convenção geral do setor — não confirmado
especificamente para SanDisk):**

| PN | Notação de mercado | Fontes (não-Tier1) |
|---|---|---|
| **SDADL2BP-32G** ← PN do caso (`SDADL2BP32G`) | "32+3", 221FBGA | Censtry, Jotrin, Win-Source, Arrow (sob marca Western Digital), OMO. Uso cruzado: `SDADL2BP-32G = FIG-LA1` (lista de técnico, serviceemmc.com) — FIG-LA1 é o Huawei P Smart (2017), que segundo o GSMArena tem variante 32GB/3GB RAM. Duas fontes independentes (lista de reparo + GSMArena) convergem, mas nenhuma é o chip em si. |
| SDADL28P-32G | mesma notação "32+3 221balls" | eBay, ChinaHao, Worldway — ⚠ pode ser o MESMO PN que o de cima com grafia B↔8 divergente entre bases de distribuidor (o tipo de confusão visual que o `FUZZY.md` existe para tratar), ou um SKU realmente distinto. Não resolvido. |
| SDADL2AP-16G (+ variante de lote `-1225T`) | "16+2", 221-ball | HKInventory, OMO |
| SDADF4AP-16G | "16+2", 221-ball, "3rd generation" | Octopart (existência confirmada, sem tabela de specs), ChinaHao, HKInventory. Cross-ref: `SDADF4AP-16G = DRA-LX2` (Huawei Y5 Prime 2018, MT6739 2GB/16GB conforme specs públicas do aparelho — consistente, não confirmatório). |
| SDADF4AP-64G | capacidade 64GB (sufixo) | Só OMO |
| SDADB48K-16G | "16+2", 221-ball, aparece pareado ao SDADF4AP-16G no mesmo lote | ChinaHao, Yoycart, OMO |
| SDADB48-16G (sem "K") | capacidade 16GB (sufixo) | Só OMO — pode ser truncamento do anterior |

**Sub-família 254-ball (LPDDR4/4X pela mesma convenção geral, exceto onde já confirmado acima):**

| PN | Notação de mercado | Fontes (não-Tier1) |
|---|---|---|
| SDADA4DR-64G | **NAND 64GB + pacote BGA-254(11.5×13mm) + interface eMMC 5.1 confirmados via LCSC** (base paramétrica estruturada, não título de anúncio) — RAM não aparece em nenhum campo estruturado do LCSC | [LCSC C2830407](https://lcsc.com/product-detail/EMMC_SANDISK-SDADA4DR-64G_C2830407.html) (verifiquei diretamente); Octopart, JLCPCB, netCOMPONENTS confirmam existência |
| SDADA4CR-64G | "64+32"→4GB LPDDR4 (título de anúncio) | AliExpress, Yoycart, rlitl.com, Alibaba — ⚠ ball-count CONFLITANTE entre fontes (153 vs 254 conforme o anúncio); Lisleapex (specs claramente templated/erradas de SSD/cartão SD — ignorado) |
| SDADA4DR-128G | capacidade 128GB (sufixo) | Só Alibaba, baixa confiança |

**Variantes de lote/data-code (mesmo chip, não nova capacidade):** `SDADL2BP-32G-1209P`,
`SDADL2AP-16G-1225T`.

**Ruído, não perseguir sem mais corroboração:** `SDAD5W497` (não segue o padrão da família,
descrição vazia, só 1 fonte).

### 3.3 ⚠️ Armadilha nova descoberta: "SDAD" colide com uma linha de ADAPTADORES FÍSICOS

O prefixo "SDAD" também é usado pela SanDisk para **adaptadores físicos de cartão** (produto de
varejo, não silício): `SDAD-38-A10`/`SDAD-38-E10` (CompactFlash→PC Card), `SDAD-67`/`SDAD-67-A10`
(adaptador PCMCIA 6-em-1), `SDAD-109`/`SDAD-109-A11`, `SDADP-01`/`SDADP-02`/`SDADP-04`
(microSD↔SD/miniSD). Aparecem misturados nos mesmos distribuidores/tags que os chips eMCP reais.
**Não são chips — excluir de qualquer busca/catálogo.** Já registrei isso no `tip` da família no
yaml e no `SANDISK.md` (armadilha durável, vai se repetir em buscas futuras).

## 4. O que eu NÃO fiz (disciplina)

Não assumi geração de RAM por ball-count reportado só em título de anúncio (mesmo quando 4+
fontes concordam) como `confirmed`/`manual`. Não completei nenhum campo `emcp_ram` com valor
adivinhado. Não juntei SDADL2BP-32G e SDADL28P-32G como "certamente o mesmo PN" sem fonte — deixei
a ambiguidade registrada. Não persegui o PN de ruído `SDAD5W497` além do que apareceu na primeira
busca.

## 5. Arquivo de submissão

`submissions/sandisk_sdad_2026-07-13.yaml` — 5 PNs: `SDADA4CR128G` (manual) + `SDADL2BP32G`,
`SDADF4AP16G`, `SDADB48K16G`, `SDADA4CR64G` (distributor, exceção de sourcing). Comandos no final
da entrega no chat.

## 6. Decisão do dono (resolvida 2026-07-13)

Pergunta feita no chat: os ~13 candidatos do §3.2 são PNs reais (existência bem corroborada), mas
a família parece ser estruturalmente sem datasheet público (NDA-only) — "esperar Tier-1" pode
significar "esperar para sempre", a menos que a confirmação venha por **ball count físico na
bancada** em vez de literatura. Três opções oferecidas: excluir tudo por ora / aceitar convergência
de distribuidor como exceção / aceitar só o PN do caso.

**Escolha: aceitar convergência de distribuidor como exceção.** Apliquei a barra "3+ domínios de
distribuidor independentes concordando" a cada candidato do §3.2:

- **Passaram (submetidos, confidence=distributor):** `SDADL2BP-32G` (5 domínios), `SDADF4AP-16G`
  (4 domínios), `SDADB48K-16G` (3 domínios, mas ver ressalva de listing-pareado), `SDADA4CR-64G`
  (5 domínios, mas com conflito de ball-count não resolvido — flagado nas notes).
- **Não passaram (< 3 domínios independentes ou sem nenhuma menção a RAM) — continuam de fora:**
  `SDADL2AP-16G` (2), `SDADL2AP-16G-1225T`/`SDADL2BP-32G-1209P` (variantes de lote, não PNs
  distintos), `SDADF4AP-64G` (1, sem notação de RAM), `SDADB48-16G` (1), `SDADA4DR-128G` (1),
  `SDAD5W497` (ruído).
- **Excluído por AMBIGUIDADE DE IDENTIDADE, não por falta de fonte:** `SDADL28P-32G` — specs
  idênticas ao `SDADL2BP-32G` já submetido, em 3 fontes independentes, mas pode ser o mesmo chip
  com grafia B/8 divergente entre bases de distribuidor. Submeter os dois como PNs distintos sem
  resolver isso arrisca duplicar (ou pior, um dos dois ser puro erro de digitação virando
  "confirmado" no catálogo). Fica pendente de confirmação física.
- **Excluído por falta TOTAL de dado de RAM (mesmo em fonte fraca):** `SDADA4DR-64G` — o mais bem
  documentado de todo o cluster (NAND 64GB + pacote BGA-254 confirmados via LCSC, base
  estruturada, verificado por fetch direto), mas ZERO fonte — nem título de anúncio — menciona a
  RAM para esse sufixo específico (`DR`, diferente do `CR` que tem "LPDDR4" em vários anúncios).
  Mesmo a exceção de sourcing aprovada precisa de ALGUM dado sobre o campo, não permite herdar a
  spec de um PN-irmão de sufixo diferente.

## 7. Fontes completas (todas verificadas por fetch direto ou pelos agentes de pesquisa, URL citada)

- https://github.com/coreboot/coreboot/commit/640ca69c0589b2337d2f319c59dd937767be6036 (verificado direto)
- https://lcsc.com/product-detail/EMMC_SANDISK-SDADA4DR-64G_C2830407.html (verificado direto)
- https://www.censtry.com/product/sandisk/sdadl2bp-32g.html
- https://www.serviceemmc.com/2020/08/support-ic-emmcufs-all-brandnew-update.html
- https://www.gsmarena.com/huawei_p_smart-8961.php
- https://octopart.com/part/sandisk/SDADF4AP-16G · https://octopart.com/sdadf4ap-16g-sandisk-84695914
- https://www.omo-ic.com/tags/SDAD.html (+ páginas individuais de PN, ver relatórios dos agentes)
- https://www.win-source.net/products/detail/sandisk/sdadl2bp-32g.html
- https://www.jotrin.com/product/parts/SDADL2BP-32G
- https://www.arrow.com/en/products/sdadl2bp-32g/western-digital
- https://www.hkinventory.com/p/d/SDADL2AP16G.htm
- http://www.rlitl.com/product/showproduct.php?id=1744
- https://www.lisleapex.com/product/compare-s/sdada4cr-64g_sdada4dr-128g_sdada4cr-128g (⚠ specs templated/erradas — só usado como contraexemplo)
- https://www.alibaba.com/product-detail/SDADA4DR-128G-SDB0805100MZF-SDB0602H-8R2M-SDADA4CR_1601495470474.html
- Mouser (adaptadores): https://www.mouser.com/ProductDetail/SanDisk/SDADP-01

Arquivos internos consultados: `chips/knowledge/sandisk.yaml` (família SDAD), `SANDISK.md` (§2/§3),
`chips/tests.py` (`_SD_GOLDEN`).
