# Investigação — SanDisk `SDINBDA6` (eMMC 5.1, sub-linha nova da família SDINB), a partir do PN SDINBDA616G (2026-07-14)

> ✅ **Resultado: 6 known_parts submetidos, todos `confirmed`.** `SDINBDA6` é uma sub-linha REAL e
> bem documentada da família `SDINB` (já conhecida) — sucessora do `SDINBDA4` ("iNAND 7550
> SmartSLC"), agora batizada **"iNAND EM132"**, eMMC 5.1 HS400, 3D NAND (BiCS3, 64 camadas).
> Achei **2 product briefs oficiais SanDisk/WD em PDF** com tabela de "Ordering Information"
> completa. Arquivo: `sandisk_sdinbda6_2026-07-14.yaml`.

## 0. O gatilho

Debug do estoque, 14/07/2026 14:05:19, PN `SDINBDA616G`: família `SDINB` (já conhecida, priority
40, eMMC 5.1) reconheceu o TIPO/interface corretamente pela gramática, mas `known_exact=false` e
`profitable=INDETERMINADO` — a sub-linha "DA6" não estava documentada no tip da família (que só
listava DG4/DD4/DA4), então não há known_part que confirme a capacidade.

## 1. Metodologia

Pesquisa direta (não precisei do fan-out de agentes desta vez — os 2 primeiros resultados de busca
já bateram direto em páginas oficiais `sandisk.com`) + verifiquei pessoalmente por fetch direto
**2 product briefs oficiais SanDisk/Western Digital em PDF**: o brochure "Advanced Flash Storage
Solutions for Automotive Applications" (ago/2025, cobre 5 famílias eMMC/UFS de uma vez) e o
product brief dedicado "iNAND AT EM132 Automotive Embedded Flash Drive" (jul/2025).

## 2. Achado principal: `SDINBDA6` = "iNAND EM132", sucessora do `SDINBDA4` ("iNAND 7550")

A família `SDINB` já tinha 3 sub-linhas documentadas no tip: `SDINBDG4`=iNAND7250,
`SDINBDD4`=iNAND7350(3D), `SDINBDA4`=iNAND7550(SmartSLC). `SDINBDA6` é uma **quarta sub-linha**,
mais nova, com nomenclatura de produto diferente (esquema "EM1xx" em vez do antigo "72xx/73xx/75xx"):

- **Nome de produto confirmado: "iNAND® AT EM132"** (grade automotivo) / **"iNAND® IX EM132"**
  (grade industrial) — official product briefs SanDisk/WD.
- **Tecnologia: 3D NAND, BiCS3 (64 camadas)** — confirmado no brief industrial (achado só no
  snippet de busca, o fetch direto do PDF industrial não retornou conteúdo — ver §6).
- **Interface: eMMC 5.1, HS400** — igual ao resto da família `SDINB`.
- ⚠ Uma fonte (snippet de busca) menciona **"iNAND CL EM132: Commercial grade... eMLC flash
  storage"** — ou seja, possivelmente a variante COMERCIAL usa eMLC (pseudo-SLC) em vez de TLC
  puro, diferente das variantes automotiva/industrial. **NÃO confirmei isso com o PDF completo**
  (não consegui abrir o brief comercial) — fica sinalizado, não assumido nos known_parts (o campo
  de tecnologia NAND não é obrigatório no nosso schema, então não bloqueia a submissão, mas é
  relevante se algum dia formos diferenciar SmartSLC/eMLC/TLC no `device`/`notes`).
- **`SDINBDA5` não existe** — busquei explicitamente, zero resultado. Confirma o padrão já visto
  ontem no cluster `SDIN9DW4/5`: a numeração das sub-linhas SanDisk pula (DE1→DE2→DE4,
  DA4→**DA6**, sem DA5).

## 3. Capacidades confirmadas (6, cobrindo 8GB–256GB)

**A) 32GB, 64GB, 128GB, 256GB — confirmadas por 2 product briefs oficiais em PDF, com tabela
"Ordering Information" completa** (capacidade, pacote, temperatura, PN exato):

| PN (grade automotivo) | Capacidade | Pacote | Temp. |
|---|---|---|---|
| SDINBDA6-32G-XA1 / -ZA1 | 32GB | 11.5×13×1.0mm | -40 a 85°C / -40 a 105°C |
| SDINBDA6-64G-XA1 / -ZA1 | 64GB | 11.5×13×1.0mm | -40 a 85°C / -40 a 105°C |
| SDINBDA6-128G-XA1 / -ZA1 | 128GB | 11.5×13×1.0mm | -40 a 85°C / -40 a 105°C |
| SDINBDA6-256G-XA1 / -ZA1 | 256GB | 11.5×13×1.2mm | -40 a 85°C / -40 a 105°C |

Fontes (2 documentos, mesmo conteúdo pra estas 4 capacidades, cabeçalho/copyright/rodapé SanDisk
Corporation ©2025 idênticos):
- `https://documents.sandisk.com/content/dam/asset-library/en_us/assets/public/sandisk/product/embedded-flash/brochure/brochure-sandisk-automotive-family-brochure.pdf`
  (brochure com 5 famílias — a tabela "Ordering Information" pg.6 cobre `SDINBDA6` junto com
  `SDINDDH`/`SDINFDQ6`/`SDINHDL6`/`SDINBDG4`, todas grade automotivo)
- `https://documents.sandisk.com/content/dam/asset-library/en_us/assets/public/western-digital/collateral/product-brief/product-brief-automotive-inand-at-em132.pdf`
  (product brief dedicado só ao EM132 — confirma a mesma tabela, PN por PN)

**B) 8GB e 16GB — confirmadas por página oficial `sandisk.com` (configurador comercial, hit direto
por SKU) + corroboração de distribuidor:**

- `sandisk.com/products/embedded-flash/mobile-inand-emmc-drives?sku=SDINBDA6-8G` (título indexado:
  "8GB 3D NAND Commercial e.MMC | Sandisk")
- `sandisk.com/products/embedded-flash/mobile-inand-emmc-drives?sku=SDINBDA6-16G` (título indexado:
  "16GB 3D NAND Commercial e.MMC | Sandisk") — **este é o PN do caso original** (`SDINBDA616G`).
- Corroborado por múltiplos distribuidores independentes (rtxchips, censtry, trustedparts,
  lovechip, kynix, xonelec) para a variante industrial `SDINBDA6-16G-I`, todos convergindo em
  eMMC 5.1 HS400, TFBGA153, 11.5×13mm.
- ⚠ Não consegui abrir o conteúdo renderizado completo dessas 2 páginas (JS pesado, o fetch retornou
  conteúdo grande demais / vazio) — a confirmação vem do TÍTULO indexado pelo buscador (que reflete
  metadado real da página oficial) + convergência de distribuidor, não da leitura literal do corpo
  da página. Tratado como `confirmed` mesmo assim por ser domínio oficial `sandisk.com` com URL
  específica por SKU — mas é uma evidência ligeiramente mais fraca que o PDF com tabela explícita
  do item A.

## 4. Variantes de grade — mesma decisão de ontem (não submetidas separadamente)

`SDINBDA6` existe em 3 grades: **comercial** (sem sufixo, ex. `SDINBDA6-64G`), **industrial**
(`-I1`/`-I`/`-XI1`, temp. -25/-40 a 85°C) e **automotivo** (`-XA1`/`-ZA1`, temp. -40 a 85/105°C).
Mesma capacidade física, qualificação/temperatura diferente. Igual à decisão de ontem pro cluster
SDIN: submeti só o PN BASE (sem sufixo de grade) por capacidade — **não** criei um known_part
separado pra cada combinação capacidade×grade (inflaria o catálogo sem ganho real pra
tipo/capacidade/rentabilidade, que é o que o WTC precifica). ⚠ Diferença importante pro PN
específico: o normalizador do WTC remove hífen mas MANTÉM letras — então um chip físico com sufixo
de grade (ex. `SDINBDA6-16G-I` → normaliza pra `SDINBDA616GI`) **não** vai casar com o known_part
base `SDINBDA616G` (strings diferentes). Se aparecer um PN com sufixo de grade na bancada, vai
precisar de known_part próprio — fica pro backlog se/quando aparecer.

## 5. known_parts submetidos (6)

| PN | Capacidade | Confidence | Fonte |
|---|---|---|---|
| SDINBDA68G | 8GB | confirmed | sandisk.com oficial (SKU) + distribuidor |
| **SDINBDA616G** (PN do caso) | 16GB | confirmed | sandisk.com oficial (SKU) + distribuidor |
| SDINBDA632G | 32GB | confirmed | 2 product briefs oficiais PDF |
| SDINBDA664G | 64GB | confirmed | 2 product briefs oficiais PDF |
| SDINBDA6128G | 128GB | confirmed | 2 product briefs oficiais PDF |
| SDINBDA6256G | 256GB | confirmed | 2 product briefs oficiais PDF |

## 6. O que ficou de fora / limitações

- **Product brief industrial dedicado** (`product-brief-inand-ix-em132-industrial-embedded-flash-devices.pdf`)
  — o fetch direto não retornou conteúdo (possível bloqueio/erro silencioso do lado do servidor).
  As specs industriais usadas vieram só do snippet de busca (BiCS3 64L, faixa 16-256GB, pacote) —
  não li o PDF na íntegra desta vez. Não bloqueia a submissão (capacidade já confirmada por outras
  2 fontes), mas registro a limitação por transparência.
- **`SDINHDL6`** (UFS 4.1, "iNAND AT EU752") — prefixo **totalmente novo**, achado de relance na
  tabela do brochure automotivo, não existe no nosso yaml. Fora do escopo de hoje (família UFS,
  não eMMC) — candidato a investigação futura.
- **`SDINFDQ6`** (UFS 3.1, "iNAND AT EU552", grade automotivo) — variante automotiva da família
  `SDINFD` que já existe no yaml; não pesquisei se o yaml já cobre esse sufixo/grade — backlog.
- **Ambiguidade eMLC vs. TLC** na variante comercial — ver §2, não resolvida.

## 7. Fontes completas
- https://documents.sandisk.com/content/dam/asset-library/en_us/assets/public/sandisk/product/embedded-flash/brochure/brochure-sandisk-automotive-family-brochure.pdf
- https://documents.sandisk.com/content/dam/asset-library/en_us/assets/public/western-digital/collateral/product-brief/product-brief-automotive-inand-at-em132.pdf
- https://www.sandisk.com/products/embedded-flash/mobile-inand-emmc-drives?sku=SDINBDA6-8G
- https://www.sandisk.com/products/embedded-flash/mobile-inand-emmc-drives?sku=SDINBDA6-16G
- https://www.sandisk.com/products/embedded-flash/mobile-inand-emmc-drives?sku=SDINBDA6-64G
- https://www.sandisk.com/products/embedded-flash/mobile-inand-emmc-drives?sku=SDINBDA6-128G
- https://www.sandisk.com/products/embedded-flash/mobile-inand-emmc-drives?sku=SDINBDA6-256G
- https://www.rtxchips.com/product/sandisk-sdinbda6-16g-i / -64g-i
- https://www.trustedparts.com/en/part/sandisk/SDINBDA6-256G-ZA

Arquivos internos consultados: `chips/knowledge/sandisk.yaml` (família SDINB), `SANDISK.md`,
`chips/tests.py` (sem âncora golden pra `SDINBDA` — sem heads-up necessário).
