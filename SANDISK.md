> ⚠️ **DUAS FONTES, DUAS TRILHAS** (Opção 2, jul/2026). A **gramática** da SanDisk (famílias) vive em
> **`chips/knowledge/sandisk.yaml`**, carregada por `load_brands`. Os **known_parts** (PNs confirmados, a
> autoridade — e na SanDisk a **única fonte de capacidade**, §2) vivem **no banco**, com revisão in-DB:
> autoria por `submit_known_parts <arq> --commit` → **aprovação no admin**. Para **corrigir a gramática de
> uma família, edite o yaml**; para **adicionar/corrigir um PN, use o `submit_known_parts`** (nunca no
> yaml). Contrato completo: `AUTORIA.md`.
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados do catálogo (inventário de famílias, known_parts,
> formato de campos) nem valores mutáveis (rentabilidade). Aqui: **anatomia do PN, armadilhas, a história
> SanDisk×WD, convenção, fontes**. **`CLAUDE.md`** é o único `.md` cross-marca mantido (convenção,
> comandos §5, arquitetura + aponta pro contrato de autoria).

---

# SANDISK.md — Bíblia Técnica e de Negócio

**SanDisk** (code WTC `SDK`) — armazenamento embarcado (eMMC, eMCP, UFS) pra smartphone/tablet. Na
bancada eMiner aparece com frequência moderada, predominando **eMMC standalone** (gerações 4.41–5.1).
A **gramática** viva (famílias) está na **`sandisk.yaml`** (11 famílias, **sem DecodeMaps**); os **known_parts** vivem no banco (Opção 2).

> **É uma marca só — ver §5.1 (SanDisk × Western Digital).** O PN gravado no chip sempre foi `SD…`;
> só a documentação levou marca WD por um período (2016–2025).

---

## 1. Convenção (OPÇÃO 1 — regras estáveis)

Fonte única: `chips/chip_types.py`. Para os tipos gerenciados da SanDisk:

- **eMMC:** `chip_type="eMMC"`, `subtype=""`, `interface`=versão (`"eMMC 5.1"`), `capacity` em GB.
- **UFS:** `chip_type="UFS"`, `subtype=""`, `interface`=versão (`"UFS 2.1"`), `capacity` em GB.
- **eMCP:** `chip_type="eMCP"`, `subtype`=geração RAM (`"LPDDR3"`/`"LPDDR4"`), `interface=""` (sempre vazio), capacidade via `emcp_nand` (só GB) + `emcp_ram` (**tipo ANTES da capacidade**: `"LPDDR3 2GB"`, nunca `"2GB LPDDR3"`).

`subtype` = **só** a geração da RAM (eMCP) ou vazio (eMMC/UFS) — nunca "iNAND", "standalone", velocidade,
tensão. O label é protegido por `canonical_gen` (fail-open). Detalhes gerais: CLAUDE.md.

---

## 2. Anatomia do PN — SanDisk é DECLARATIVO (a chave da marca)

**Diferença fundamental vs Samsung/Hynix/Micron:** a capacidade **não** está numa posição fixa — está
sempre no **sufixo após o traço** (declaração de fábrica):

```
[Prefixo Família] [Die Code / variante] - [Capacidade]
                                            -8G=8GB · -16G · -32G · -64G · -128G  (G = Gigabyte, não Gigabit)
```

⚠ **Decode posicional é IMPOSSÍVEL** — o die code intermediário tem **comprimento variável**
(`SD7DP24C-4G`=10 chars, `SD7DP24C-16G`=11, `SD7DP25F-128G`=12), então não há posição fixa pra
capacidade. Por isso **todas** as famílias SanDisk têm `decode_cap_pos: null` e **`sandisk.yaml` não tem
DecodeMaps**. Consequência crítica:

> **Chip SanDisk sem `known_part` no banco → `profitable="INDETERMINADO"`.** O engine classifica a
> família (tipo + interface) mas **não tem como extrair a capacidade** pela gramática. `known_parts` é a
> **única** fonte de capacidade da marca. A missão contínua é confirmar PNs à medida que aparecem.

**Normalização:** o engine faz `re.sub(r"[^A-Z0-9]", "", pn)` → o traço some (`SDIN9DW4-16G` →
`SDIN9DW416G`). Grave o PN normalizado no known_part (o `submit_known_parts`/portão aceita com traço, mas o padrão é sem).

**Famílias (orientação — inventário completo na `sandisk.yaml`):** eMMC = `SD5DH`/`SD7DP`/`SDINB`/`SDMAG` +
`SDIN` (fallback genérico, priority 80); UFS = `SDINDDH`/`SDINEDK`/`SDINFD`/`SDHQB`; eMCP = `SDAD`/`SDEM`.
O engine casa o prefixo mais específico primeiro (`SDINB` eMMC vence `SDIN` genérico; UFS vence ambos).

---

## 3. Armadilhas específicas (o durável)

- ⚠ **`SDINB` é eMMC, NÃO UFS** (reclassificado jun/2026). Começa com `SDIN` mas é eMMC 5.1 — sub-linhas SDINBDG4 (iNAND 7250) / SDINBDD4 (7350) / SDINBDA4 (7550), confirmadas nos product briefs oficiais. As **UFS reais** são `SDINDDH`/`SDINEDK`/`SDINFD`. `SDINB` (priority 40) vence `SDIN` (80).
- ⚠ **UFS e eMMC compartilham BGA 153-ball visualmente idêntico** mas são **eletricamente incompatíveis**. Triar SEMPRE pelo prefixo do PN antes de encostar no socket.
- ⚠ **eMCP `SDAD`: a geração da RAM NÃO está no PN** — vem do **ball count físico**: **221-ball = LPDDR3 (presumido), 254-ball = LPDDR4/4X (confirmado)** (regra de ouro; ex.: `SDADA4CR-128G`=254-ball LPDDR4X 4GB). Nunca assumir geração RAM sem ball count ou fonte Tier 1.
- ⚠ **"16+2" vs "16+16":** Preduo escreve `"16+16"` = 16GB NAND + 16**Gbit** LPDDR3; mercado BR/PY usa `"16+2"` = ambos em GB (16Gbit ÷ 8 = 2GB). No banco: `emcp_nand="16GB"`, `emcp_ram="LPDDR3 2GB"`.
- O sufixo `-16G` de um eMCP refere-se ao **NAND** (não à soma).
- ⚠ **`SDAD` provavelmente não tem datasheet público** (investigado 2026-07-13, 6 frentes de pesquisa independentes — nenhuma achou documento oficial SanDisk/WD): parece linha vendida só sob NDA direto a OEMs de celular. "Esperar Tier-1" pode ser esperar pra sempre nessa família — a via prática é **ball count físico na bancada** ou evidência de engenharia de terceiro testada (ver bullet seguinte). Ver `submissions/INVESTIGACAO_sandisk_sdad_2026-07-13.md`.
- ⚠ **Prefixo `SDAD` colide com uma linha de ADAPTADORES FÍSICOS** da SanDisk (PCMCIA/CompactFlash/microSD: `SDAD-67-A10`, `SDAD-38-A10`, `SDADP-01`...) — mesma tag nos distribuidores, produto totalmente diferente (não é chip). Filtrar antes de pesquisar/catalogar.
- ⚠ **`SDIN` (o fallback genérico, priority 80) NÃO é uma única geração "eMMC 4.5/5.0/5.1"** — cobre **3 protocolos/gerações históricas** distintas (investigado 2026-07-14, 3 datasheets oficiais lidos na íntegra): **`SDIN2xx`** (jul/2007) é **SD 1.1/2.0 + SPI, nem é eMMC de verdade** — anterior ao padrão MMC; **`SDIN4xx`** (~2008-2009, inclui o clássico `SDIN4C2`) é eMMC mas **sem datasheet público localizado** (buraco documental real — usar triangulação, ver bullet seguinte); **`SDIN5xx`** (dez/2010) é **e.MMC 4.41** de fato; **`SDIN7DP2`** (fev/2013, "Ultra") é **e.MMC 4.51**. Não assuma a geração pelo 1º dígito sem checar essa tabela — ver `submissions/INVESTIGACAO_sandisk_sdin_2026-07-14.md`.
- ⚠ **`SDIN4C2` (e clusters "sem geração confirmada" parecidos) — triangulação de engenharia real vale como `manual`, mesmo sem datasheet:** fórum de engenharia (TI E2E, engenheiro citando o datasheet do fabricante em mãos), banco de dispositivos suportados de fabricante de programador de chip (Elnec, exige pinout real), e teardown técnico (iFixit, prosa de desmontagem — não título de anúncio) juntos formam evidência mais forte que qualquer distribuidor isolado. Cross-ref de compatibilidade de reparo (ex. serviceemmc.com) é só apoio (não é Tier-1 nem substitui as três fontes acima).
- ⚠ **Sufixo de GRADE (`-I1`/`-XI1` industrial, `-XA1`/`-ZA1` automotivo) sobrevive à normalização** —
  o normalizador só remove traço/espaço, mantém letras. Um known_part base (`SDINBDA6-16G` →
  `SDINBDA616G`) **não** casa com o mesmo chip em grade industrial/automotiva (`SDINBDA6-16G-I` →
  `SDINBDA616GI`, string diferente). Mesma capacidade física, PN normalizado diferente — se aparecer
  um PN com sufixo de grade na bancada, precisa de known_part próprio (achado 2026-07-14, sub-linha
  `SDINBDA6`, ver `submissions/INVESTIGACAO_sandisk_sdinbda6_2026-07-14.md`). Não crie known_part
  pra cada grade por precaução — só quando o PN com sufixo aparecer de verdade.
- ⚠ **Uma família "eMMC puro" pode ter UM die-code que na verdade é eMCP** — achado 2026-07-14,
  família `SD5DH` (`is_emcp=false` no yaml, era 2012-2013): die-codes `24A`/`24C` são eMMC puro
  confirmado, mas `26A` (`SD5DH26A-4G`) é **eMCP** (NAND 4GB + LPDDR1 768MB) segundo triangulação
  (substituto Samsung pino-a-pino confirmado + RAM total do aparelho batendo exatamente com a
  aritmética Gb→GB) — sem datasheet pra confirmar 100%, decisão registrada como `manual` com o
  dono ciente da incerteza. Não mude `is_emcp` da família por causa de 1 exceção — o known_part
  específico já sobrepõe a gramática pra esse PN exato. Ver
  `submissions/INVESTIGACAO_sandisk_sd5dh_2026-07-14.md`.
- ⚠ **`SD5D` (SEM o H) é uma família IRMÃ do `SD5DH`, totalmente separada e ainda fora do yaml** —
  mesmo padrão de confusão do `SD9`/`SDIN9`: prefixo parecido, produto diferente. `SD5D` é eMCP
  confirmado (die-codes 14/28, pelo menos 1 membro com ball-count diferente — FBGA162 vs FBGA153 do
  `SD5DH`). Achado de relance 2026-07-14, não pesquisado a fundo — se aparecer um PN `SD5D` (sem H
  logo depois) na bancada, não presuma que é `SD5DH` mal-digitado; é família de verdade, precisa de
  investigação própria.
- ⚠ **`SD9...` (SEM "IN") é uma família eMCP TOTALMENTE DIFERENTE de `SDIN9...`** — não é a mesma geração com prefixo truncado, são dois produtos SanDisk não relacionados que só coincidem no sufixo numérico (achado 2026-07-14, PN `SD9DS28K-8G`). `SDIN9xx` = eMMC (dentro da mega-família `SDIN`, eMMC 5.0 HS400, "iNAND 5130"/"iNAND Extreme"). `SD9xx` = eMCP isolado (NAND+LPDDR3), **sem família própria no yaml** — só 1 PN confirmado (`SD9DS28K-8G`) depois de busca exaustiva, sem nenhum sibling; parece peça semicustomizada de baixo volume (usada no Qualcomm/Arrow DragonBoard 410c). ⚠ **Nunca crie gramática posicional pro prefixo curto `SD9` sozinho** — colide com uma linha de SSD SATA de consumo totalmente não relacionada (`SD9SN8W-*`/`SD9SB8W-*`, produto final, não die). Se aparecer outro PN `SD9...` na bancada, tratar como candidato a known_part isolado até achar sibling real — não assumir família. Ver `submissions/INVESTIGACAO_sandisk_sd9_2026-07-14.md`.

---

## 4. Rentabilidade — princípio (sem valores)

Fonte única: `assess_profitability` + `ProfitabilityConfig` (admin, market-variable). SanDisk usa as
mesmas regras de eMMC/eMCP/UFS das outras marcas — **sem parâmetro SanDisk-específico**. Padrão durável:
UFS e eMMC/eMCP de boa capacidade = rentável; **sem capacidade no banco → INDETERMINADO** (bloqueador de
triagem, resolvido só confirmando o PN). Sem números aqui.

---

## 5. Contexto de negócio

### 5.1 SanDisk × Western Digital — o "mix" foi só na doc, nunca no PN

Linha do tempo: SanDisk foi **comprada pela Western Digital em 2016** e **voltou a ser independente em
fev/2025** (spin-off distribuído 21/fev; negociação independente na Nasdaq como **SNDK** a partir de
24/fev/2025), ficando com todo o negócio de flash/NAND. A WD hoje é **só HDD**
(fora do domínio do WTC). Regras imutáveis pro operador:

- O **PN gravado no chip sempre teve prefixo `SD`** (`SDIN…`, `SD7DP…`, `SDAD…`). A WD **nunca** criou chip de memória com prefixo "WD". O código que o operador lê é sempre SanDisk.
- O logo "WD" aparece nos produtos de **consumo** (SSD/HDD), **não** no die de memória embarcada.
- Só a **documentação** (datasheets, product briefs) de 2016–2025 saiu com marca WD (westerndigital.com). Um PDF "Western Digital" pra um PN `SD…` é o **mesmo produto** — não outra marca. Pós-split a doc volta a sandisk.com (westerndigital.com ainda hospeda os legados).

**No WTC: uma marca só, `SanDisk` (SDK).** Não existe marca "Western Digital" de chip de memória pra catalogar.

---

## 6. Fontes de pesquisa

Hierarquia (Tier-1→baixo): **sandisk.com / westerndigital.com** (product briefs, datasheets — mesmo
produto, ver §5.1) → datasheet SanDisk histórico (ex.: doc# 80-36-03462, iNAND eMMC 4.41) →
Octopart/Mouser/Avnet (distribuidor autorizado) → distribuidor B2B rastreável (só apoio, nunca rebaixa
`confirmed`) → **Preduo** (confiável pra tipo/ball count, **não** pra specs elétricos) → IA (último recurso,
sempre verificar). **Nunca fonte única:** yoycart/chinahao sem cruzamento, eBay, catálogo Shenzhen sem rastreio.

**Fonte extra descoberta (2026-07-13), tratar como equivalente a Tier-1 quando existir:** firmware
open-source de dispositivo real (ex.: **coreboot**, board Google ChromeOS) — quando um PN eMCP é usado
num Chromebook, o código-fonte de inicialização de DDR (`sdram_params/*.c`) é testado em produção e
costuma nomear o PN + geração LPDDR explicitamente no arquivo/commit. Mais confiável que qualquer
distribuidor (é evidência funcional, não alegação de revenda), mas não é datasheet do fabricante —
sinalizar como fonte atípica na submissão. Buscar por: `site:github.com/coreboot/coreboot "<PN>"`.

**Mais duas fontes atípicas confirmadas úteis (2026-07-14, família SDIN, PN sem datasheet):**
fórum de engenharia de fabricante de SoC (ex.: **TI E2E**) — post de engenheiro integrando o chip
numa placa real, frequentemente citando o datasheet do fabricante que ele tem em mãos (mesmo que o
PDF em si não esteja público); e banco de dispositivos de **fabricante de programador de chip** (ex.:
**Elnec**) — listar um PN como suportado exige pinout físico real, não é alegação de revenda. Junto
com teardown técnico (iFixit, ler a prosa da desmontagem, não o título do anúncio), essas 3 fontes
convergentes valem `confidence=manual` mesmo sem datasheet oficial. Cross-ref de compatibilidade de
reparo (serviceemmc.com e afins) é sempre só apoio.

**Mais uma (2026-07-14, PN `SD9DS28K-8G`, eMCP isolado sem nenhum datasheet SanDisk público):**
**manual de hardware oficial de uma placa/dispositivo real** que usa o chip (ex.: 96Boards
DragonBoard 410c) — quando o fabricante da PLACA (não do chip) documenta especificações exatas de
memória (capacidade NAND, geração+capacidade RAM, largura de barramento) porque o produto final
depende delas, é evidência tão forte quanto um datasheet, mesmo não sendo documento SanDisk-branded.
Reforçada por post de fórum oficial do fabricante do SoC confirmando explicitamente que "a SanDisk
não publica datasheet desta peça" — o que trata a ausência de doc oficial como esperada, não como
sinal de fonte fraca. Buscar por: `"<PN>" hardware manual` / `"<PN>" datasheet` em fóruns oficiais de
placas de desenvolvimento (96Boards, Raspberry Pi, Beagleboard, Qualcomm/TI/NXP dev forums).

> Inventário de famílias (gramática): **`sandisk.yaml`**; os known_parts e a provenância por-PN (nas
> `notes`) vivem **no banco** (Opção 2). Comandos, convenção completa, rentabilidade, contrato de autoria:
> **CLAUDE.md** / **AUTORIA.md**.
