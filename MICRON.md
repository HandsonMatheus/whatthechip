> ⚠️ **DUAS FONTES, DUAS TRILHAS** (Opção 2, jul/2026). A **gramática** da Micron (famílias + mapas) vive
> em **`chips/knowledge/micron.yaml`**, carregada por `load_brands`. Os **known_parts** vivem **no banco**
> (revisão in-DB): os curados por `submit_known_parts <arq> --commit` → **aprovação no admin**; a massa,
> pelos pipelines locais da Micron (§2), que gravam `approved` direto. Para **corrigir a gramática, edite
> o yaml**; para **um PN, use o `submit_known_parts`/os pipelines** (nunca o yaml). Contrato: `AUTORIA.md`.
>
> ⚠ **Micron é HÍBRIDA — a exceção entre as marcas.** Além do yaml, ela tem comandos LOCAIS
> (`import_micron_catalog`, `fill_capacity_from_micron_api`, `enrich_micron_fbga`, `fix_micron_*`,
> `collect/analyze_micron_*`) que **AINDA EXISTEM** e enchem o catálogo (known_parts **no banco**) com
> massa de CSV + specs de FBGA (§2). Não são os aposentados `populate_*`/`fix_known_parts`.
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados do catálogo (decode key→valor, known_parts,
> formato de campos) nem valores mutáveis (rentabilidade). Aqui: **o modelo híbrido, anatomia/nomenclatura,
> FBGA, armadilhas, bugs (o *porquê*)**. **`CLAUDE.md`** é o único `.md` cross-marca mantido (convenção,
> comandos §5 com flags, arquitetura + aponta pro contrato de autoria).

---

# MICRON.md — Bíblia Técnica e de Negócio

**Micron** (code WTC `MIC`) — 2º fabricante mundial de DRAM e NAND (depois da Samsung). Na bancada eMiner
aparece como eMCP/uMCP (MT29TZZZ LPDDR3, MT29VZZZ LPDDR4, MT30AZZZ LPDDR5), LPDDR standalone (MT53x/MT52L),
DDR3/4 (MT41J/K, MT40A), eMMC (MTFC), NAND raw (MT29F) e NAND+LPDRAM MCP legado PoP (MT29C — ver §4).
**O operador vê o PN completo OU o FBGA
code de 5 chars** gravado a laser (ex.: `D9VFC`, `JWA60`) — a busca aceita os dois.

## ⚠ Modelo híbrido (a exceção da Micron)

A `micron.yaml` tem a **gramática** (famílias + mapas MIC_MCP_CAP / MIC_TZZZ_GEN); os **known_parts** vivem
no banco (Opção 2). A **cobertura de massa** vem de comandos LOCAIS (local-only, não rodam no Render) que
gravam known_parts **direto no banco** (pipeline de máquina, `approved`) — o traço durável que distingue a Micron:

- `import_micron_catalog <csv>` — CSVs Micron → known_parts DDR/eMMC (`density_gbit`/`density_gb`/`capacity`).
- `fill_capacity_from_micron_api` / `enrich_micron_fbga` / `lookup_fbga` — API FBGA → part-name + specs, por FBGA code.
- `fix_micron_capacity` / `_lpddr_specs` / `_mcp_classification` — normalizam specs (fórmula sem dies, geração, eMMC×uMCP).
- `collect_micron_catalog` / `analyze_micron_mcp_keys` — descoberta de famílias/chaves.

Para a **gramática**: edite a `micron.yaml` (`load_brands`). Para **known_parts curados**: `submit_known_parts`
→ admin. Para **massa DDR/eMMC/FBGA**: os comandos acima (gravam no banco). As flags e a ordem de deploy estão
no **CLAUDE.md §5**. Tudo roda pelo usuário (sempre `--dry-run` antes).

---

## 1. Convenção (OPÇÃO 1 — regras estáveis)

Fonte única: `chips/chip_types.py`. **DRAM discreta:** geração no `chip_type` (`DDR3`/`LPDDR4X`/…),
espelhada no `subtype` — ❌ **NUNCA `chip_type="RAM"`/`"DDR"`**. **Gerenciada:** eMCP/uMCP `subtype`=geração
RAM + `interface=""` + `emcp_nand`/`emcp_ram` (**tipo ANTES da capacidade**: `"LPDDR4 6GB"`); eMMC/UFS
`subtype=""` + `capacity` em GB; NAND raw `chip_type="NAND Flash"` + `subtype`=célula.

**Regra absoluta do `subtype`:** só a geração/célula (1–3 palavras) — nunca `"LPDDR3 Mobile"`, `"SLC NAND
paralela industrial"`. O label é protegido por `canonical_gen` (fail-open), mas escreva limpo. Campos:
`density_gbit`=Gb por die (DDR) · `capacity`=pacote · `interface`=barramento (`x16`, nunca a geração) ·
`tip`=voltagem/organização/velocidade. Detalhes gerais: CLAUDE.md.

---

## 2. Anatomia e nomenclatura Micron (o durável)

**Nomenclatura de geração LPDDR (tier-1 — DigiKey/Micron):**

- **`MT52`x** (MT52L/MT52H) = **LPDDR3** — ⚠ **"52"=LPDDR3, não LPDDR4** (corrigido 2026-06-27; tier-1 pegou antes de o bulk corromper ~151 registros).
- **`MT53B` / `MT53D`** = **LPDDR4** (VDDQ 1.1V). **`MT53E`** = **LPDDR4X** (VDDQ 0.6V — **incompatível** com MT53B/D, separar). `MT42L` = LPDDR2; `MT62F`/`MT63G` = LPDDR5/5X.

**Capacidade LPDDR standalone (MT5x) — fórmula JEDEC:** `profundidade × largura ÷ 8 = GB`. Ex.:
`MT53E768M32D4` → 768M × 32 ÷ 8 = **3GB**; `MT52L128M32D1` → 128M × 32 ÷ 8 = 512MB (LPDDR3).

> ⚠ **O sufixo `D{N}` (D2/D4/D8) é dies/canais no encapsulamento — NÃO multiplica a densidade.**
> `profundidade × largura` já é o dispositivo inteiro. Multiplicar por dies foi o **bug de dies**
> (2026-06-27): inflava ×N (MT53E768M32**D4** virava 12GB em vez de 3GB). Hoje o engine decodifica via
> `ChipFamily.decode_density_type='micron'` (sem dies); os valores das chaves vivem no yaml.

**eMCP/uMCP (MT29xZZZ):** prefixo fixo de 8 chars + chave de capacidade em `pn[8:11]` → mapa MIC_MCP_CAP.
⚠ **`pn[8]`=código RAM, `pn[10]`=código NAND** (não reverter). Toda a família **MT29TZZZ é LPDDR3**
(BUG-8); MT29VZZZ=LPDDR4; MT30AZZZ=LPDDR5. As tabelas de chave→capacidade estão no yaml.

---

## 3. FBGA codes — o que o operador lê

**Formato:** 5 chars, `^[A-Z][A-Z0-9]{4}$` (ex.: `D9VFC`, `JWA60`, `JW464`). Prefixos: `D9xxx`=DRAM
standalone · `JWxxx`/`JYxxx`=eMCP · `NWxxx`=uMCP. **Engine:** detecta o padrão → busca
`KnownPart.fbga_code` → se tem família, decode completo; senão, dict manual (`density_gbit`/`density_gb`);
desconhecido → enfileira em `UnknownChip`. Duplicatas: prefere o registro com `chip_type` preenchido.

> **Princípio-raiz (durável):** num FBGA `confidence="confirmed"`, **o ouro é só a IDENTIDADE** (o par
> PN↔FBGA da API). `capacity`/`subtype`/`density` são **calculados localmente e podem estar errados** —
> **atestar sempre em tier-1** (datasheet/DigiKey/Octopart), nunca confiar na suposição. Foi a causa-raiz
> do BUG-8 e do bug de dies.

---

## 4. Armadilhas específicas (o ouro)

- ⚠ **`"G"` no nome Micron = Gbit, não GB** — `MTFC8G`=8Gbit=1GB; `"72G VFBGA"`=72Gbit total. `÷8` sempre. DDR → `density_gbit`; LPDDR → `capacity`; **MCP → NÃO** usar o total como `capacity` (é NAND+RAM somado; preencher `capacity` num eMCP gera o bug clássico `"68GB"`).
- ⚠ **`part-name` da API FBGA NÃO é fonte pra tipo de RAM** — a API retornava `"…/LPDDR2…"` pra chips LPDDR3 (**BUG-8**). O **prefixo do PN** define (MT29TZZZ=LPDDR3, MT29PZZZ=LPDDR2). Confirmar via datasheet/DigiKey.
- ⚠ **CORRIGIDO 2026-07-09 — `MT29C` TEM RAM, sim.** Esta linha dizia "NAND raw, sem RAM, resíduo" — **estava errada**. Datasheet oficial Micron (`152ball_nand_lpdram_j4xx_omap.fm`, achado via Alldatasheet a partir do PN de exemplo já citado em CLAUDE.md) confirma no próprio legend do part number: **"29C = NAND + LPDRAM MCP"** — Package-on-Package combinando um NAND raw (ex.: `MT29F4G16ABCWC-ET`) + uma Mobile LPDRAM raw (ex.: `MT46H32M32LFJG-6`) no mesmo encapsulamento. ⚠ Arquitetura diferente do eMCP Samsung/SK Hynix/MT29T/MT29P (que usam controller eMMC unificado): aqui as **interfaces são separadas** (NAND e LPDRAM endereçados como dois chips discretos empilhados, não um controller único) — mais perto de "PoP raw" que "eMCP gerenciado". Capacidade: densidade no PN (`{N}G{M}M`) dobra a cada passo — NAND `1G/2G/4G/8G` (Gb) e LPDRAM `12M/24M/48M/96M` (Gb) — confirmado via DigiKey (categoria paramétrica "8Gbit (NAND), 4Gbit (LPDRAM)" pro tier `8G96M`, PN irmão `MT29C8G96MAZBADJV-5 IT`). `chip_type` = **`MCP`** (já existe em `chips/chip_types.py` — category `catalog`, `profit_family="dead"`, `commercial=False`; descrito lá como "NAND raw + mDDR1 pré-eMCP, sem liquidez B2B"). Sempre NÃO RENTÁVEL + descarte por geração no gateway, independente de capacidade. `subtype` carrega a spec no formato descritivo do próprio código: `"Raw MCP — NAND {X} + mDDR1 {Y}"` — não usa `emcp_nand`/`emcp_ram`/`capacity` (esses são da categoria `managed_mcp`, diferente). Caso-fonte: FBGA JW500 → `MT29C8G96MAZAPDJA-5 IT` = NAND 1GB + mDDR1 512MB, capacidade confirmada via DigiKey (categoria paramétrica "8Gbit (NAND), 4Gbit (LPDRAM)" do PN-irmão `MT29C8G96MAZBADJV-5 IT`, mesma densidade), 2026-07-09.
- ⚠ **`MT53B` ≠ `MT53E`** — LPDDR4 1.1V vs LPDDR4X 0.6V; misturar **danifica hardware**.
- **eMMC vs uMCP em MT29VZZZ:** a distinção vem do `source_url` da API FBGA (`emmc-based` vs `ufs-based`); `fix_micron_mcp_classification` aplica.
- **`COMPONENT DENSITY` do CSV é total NAND+RAM** pra MCP (não separa) — usar API FBGA / MIC_MCP_CAP, nunca como `capacity`.
- **`"por die"` no `val_secondary` de mapa de densidade:** não escrever — o engine já acrescenta (senão vira `"por die por die"`).
- **Só `confidence` ∈ (`confirmed`,`manual`) vence a gramática;** `distributor`/`estimated` só complementam. Ao corrigir um campo, **preserve o `confidence`** (não rebaixar).
- **Formato abreviado `-DC`** (ex.: `MT53E1BAD4DB-DC`): não traz o bloco `[depth][M|G][width]` → sem decode posicional; resolver via FBGA/datasheet.
- **Não inventar chave MCP por "padrão matemático"** sem PN âncora + fonte Tier-2+.

---

## 5. Rentabilidade — princípio (sem valores)

Fonte única: `assess_profitability` + `ProfitabilityConfig` (admin, market-variable). Padrão durável:
eMCP/uMCP e LPDDR4+/DDR3+/eMMC rentáveis acima do limiar de capacidade; **LPDDR2 e NAND/NOR/MCP raw =
NÃO RENTÁVEL** (bloco no topo de `assess_profitability`; `is_dead_by_generation` manda ao descarte sem
confirmar). **Sem o campo de capacidade certo → INDETERMINADO** (bloqueador — sempre preencher
`emcp_nand`+`emcp_ram` p/ MCP, `density_gbit` p/ DDR, `capacity` p/ LPDDR/eMMC). Sem números aqui.

---

## 6. Fontes de pesquisa

Hierarquia (Tier-1→baixo): **datasheet oficial Micron (PDF)** → **API FBGA** (`micron.com/fbga?fbga=CODE`)
→ **DigiKey** → Octopart/Nexar (⚠ **inverte Gb/GB** — sempre cruzar) → distribuidor B2B rastreável (Puris,
Win Source; nunca rebaixa `confirmed`) → IA (último recurso, sempre verificar). Nunca fonte primária:
AliExpress, catálogo genérico, `part-name` da API FBGA (pra tipo de RAM), distribuidor sem rastreio.

**Unidades na API/CSV Micron:** part-name MCP `"72G VFBGA"` = 72 **Gbit**; DDR `"2Gb DDR3"` = 2 Gigabit =
256MB. CSV `COMPONENT DENSITY`: DDR = por die em Gbit; eMCP/uMCP = total NAND+RAM (não usar como capacity).

---

## 7. Histórico de bugs — as lições que não podem voltar

- **BUG-8 (2026-06-19):** API FBGA dizia `LPDDR2` pra MT29TZZZ, que é **toda LPDDR3** (datasheet + DigiKey). Lição: o prefixo do PN define o tipo de RAM, não o part-name da API.
- **Bug de dies (2026-06-27):** LPDDR inflada ×N por multiplicar `depth×width` pelos dies `D{N}`. Lição: a fórmula é `depth×width÷8`, sem dies.
- **MT52L = LPDDR3, não LPDDR4 (2026-06-27):** "52"=LPDDR3. Tier-1 pegou antes de ~151 registros serem corrompidos em massa.
- **MT29C = NAND+LPDRAM MCP (PoP), CORRIGIDO 2026-07-09:** a entrada aqui dizia "NAND raw, não eMCP LPDDR2" e estava errada — datasheet oficial confirma "29C = NAND + LPDRAM MCP", combo real (interfaces separadas, não eMMC unificado). Ver §4 pra fonte, detalhe e o caso JW500.
- **`chip_type="RAM"` → geração:** DRAM discreta usa a geração no `chip_type` (`DDR3`/`LPDDR4`), nunca `"RAM"` (convenção OPÇÃO 1).
- **eMMC×uMCP trocados (BUG-3)** e **gramática ignorada p/ eMCP distributor (BUG-6):** resolvidos por `source_url` e pela regra "gramática completa vence distributor/estimated".

> Provenância por-PN e o inventário de FBGAs confirmados vivem nas `notes` dos known_parts (no banco — Opção 2).

> Inventário de famílias/chaves de decode: **`micron.yaml`**; os known_parts vivem no banco (Opção 2).
> Comandos (com flags), convenção completa, rentabilidade, contrato de autoria: **CLAUDE.md** / **AUTORIA.md**.
