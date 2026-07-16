# FORESEE.md — Bíblia Técnica e de Negócio

> ✅ **MARCA CONSTRUÍDA (jul/2026) — COMPLETA.** `chips/knowledge/foresee.yaml` existe com as
> **9 categorias / 17 famílias** do catálogo; os known_parts confirmados das categorias RENTÁVEIS
> vivem no banco (submetidos via `submissions/foresee_*.yaml`). Este `.md` é a **camada humana**
> (anatomia do PN, convenção, armadilhas, fontes) — não substitui o yaml nem os known_parts.
> Em conflito, o **código é a fonte da verdade** (`chips/engine.py`), depois `foresee.yaml`.
> Duas trilhas (detalhe em **`AUTORIA.md`**; índice em `CLAUDE.md §5`): **gramática** → editar
> `foresee.yaml` → `load_brands --brand foresee` (dry-run = portão) → o **dono** roda `--commit`;
> **known_parts** → arquivo de submissão → `submit_known_parts` (dry-run) → o **dono** `--commit` + aprova.

---

**FORESEE** é a marca de armazenamento da **Longsys Electronics** (Shenzhen, China; fundada em 2011,
`longsys.com`). Cobre **NAND raw** (paralela e SPI), **eMMC**, **UFS**, os combos **eMCP / uMCP /
ePOP / nMCP** (NAND ou UFS + LPDDR no mesmo pacote) e **DRAM discreta** (LPDDR4X + DDR3L). Foco em
automotivo/industrial/IoT/consumo — roteadores, STBs, TVs, wearables, dashcams, smartphones de entrada.
⚠ A Longsys também é dona da marca **Lexar** (2017) — marca **separada**, não fundir com a Foresee
(chips FLXC de LPDDR4X aparecem rotulados "Lexar Enterprise" na DigiKey; ainda são a pastilha Foresee).

**Cobertura atual no WTC:** 17 famílias (`code=FRS`), 34 known_parts confirmados (categorias RENTÁVEIS).

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/foresee.yaml           ← GRAMÁTICA (17 famílias, 9 categorias). Opção 2: só famílias+mapas.
banco (submit_known_parts→aprovação)   ← known_parts confirmados = autoridade. submissions/foresee_*.yaml.
AUTORIA.md / CLAUDE.md §5              ← o processo OBRIGATÓRIO das duas trilhas + convenção + comandos
```

⚠ **Família nova → PN-âncora no golden é OBRIGATÓRIO** (`_FORESEE_GOLDEN` em `chips/tests.py`;
`GoldenObrigatorioTests` falha sem). **NÃO tocar sem revisão:** `chips/engine.py`, `estoque/views.py`,
yamls/known_parts de outras marcas, mapas globais (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung).

### 0.2 Regras de ouro — nunca violar

1. **Claude edita arquivos. O usuário roda os comandos.** Nunca `load_brands --commit`/`migrate` sem confirmação.
2. **⚠️ "G" no PN da Foresee é AMBÍGUO — confira a LINHA antes de assumir a unidade.** A mesma letra
   fecha unidades diferentes conforme o produto:
   - **eMMC/UFS** (`FEMD*`/`FEUD*`): "G" fecha número **já em GB, por extenso** (`FEMDNN032G` = **32GB**).
   - **LPDDR4X standalone** (`FLXC*`): o dígito **antes** do "G" (`pn[7]`) = **GB do pacote** (`FLXC2004G` = **4GB**).
   - **NAND raw** (`F35*`/`FS3*`/`FSN*`): "G" fecha densidade em **Gbit** (`F35SQA002G` = **2Gbit** = 256MB).
   - **DDR3L standalone** (`F60C*`): número em **Gbit** por die (`F60C1A0002` = **2Gb** = 256MB).

   É a mesma classe de armadilha "Gb×GB" documentada pra Micron/SK Hynix no `CLAUDE.md §7`.
3. **eMCP/uMCP/ePOP/nMCP: o lado NAND vem em GB, o lado DRAM vem em Gb — no MESMO PN.** O catálogo
   oficial rotula `"64GB+32Gb"`. Ao gravar `emcp_ram`, **converta** Gb→GB (÷8): `"LPDDR4X 4GB"` (nunca
   `"LPDDR4X 32GB"`; convenção `CLAUDE.md §6`). Ex.: `FEPRF6432` = eMMC 64GB + LPDDR4X 32Gb → 4GB.
4. **Capacidade eMMC/UFS é literal, sem tabela char-a-char** (`FEMDNN128G` = 128GB por extenso). Ainda
   assim registre cada código só depois de ver um PN-âncora real — **não extrapole o range**. ⚠ Exceção
   do catálogo: o industrial 128GB é `FEMDRM0128G` (**4 dígitos** `0128`, um one-off) — quebra o decode
   posicional (`pn[6:9]="012"`); coberto por **known_part exato**, não por chave no mapa.
5. **`chip_type` da Foresee não precisa de token novo.** Toda linha (`eMMC`, `UFS`, `eMCP`, `uMCP`,
   `ePoP`, `MCP`, `NAND Flash`, `LPDDR4X`, `DDR3L`) já existe em `chips/chip_types.py` — o handshake de
   rentabilidade já está satisfeito por construção. **4 tipos são dead-by-type** (sempre NÃO RENTÁVEL,
   independente de capacidade): `ePoP`, `NAND Flash`, `MCP` (`profit_family="dead"`). Para esses, a
   gramática magra já basta — **sem known_parts** (capacidade irrelevante; ver §4).
6. **Não confie em distribuidor/IA sem verificar** (confundem Gb/GB, alucinam capacidade). Cruzar com
   `longsys.com` ou o datasheet original hospedado em LCSC/DigiKey/community.nxp.com (mesmo documento,
   espelhado → ainda Tier-1). DigiKey serve de **cross-check** de capacidade literal (2 anchors FLXC).
7. **Esquemas de nomenclatura ANTIGOS existem** — `FSEIASLD-xxG` é eMMC industrial pré-`FEMD*` (a Longsys
   cross-referencia `FSEIASLD-32G/64G/128G` = `FEMDRM032G/064G/0128G`). `NCLDXC1MG256M32` é LPDDR4X 1GB de
   nomenclatura legada `NCLD` (fora da família `FLXC`). Chip de bancada velho pode vir com prefixo antigo.

### 0.3 Hierarquia de fontes (imutável)

```
1. longsys.com (site + catálogo oficial + datasheet original) → Tier 1
2. Datasheet Foresee espelhado em LCSC / DigiKey / community.nxp.com → MESMO documento → Tier 1
3. DigiKey/LCSC como cross-check de capacidade LITERAL (campo estruturado "XGByte") → Tier 1 auxiliar
4. Octopart / distribuidor B2B rastreável com datasheet linkado → Tier 2
5. IA externa → ÚLTIMO RECURSO; verificar SEMPRE
```
Nunca fonte primária: fóruns, catálogos genéricos sem datasheet, eBay, distribuidor sem rastreabilidade.

---

## 1. Convenção Canônica de Campos

> Fonte única: `chips/chip_types.py`. Contexto geral: `CLAUDE.md §6`. Nenhum tipo novo é necessário.

| Linha Foresee | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| eMMC (`FEMD*`/`FEMK*`/`FEMJ*`) | `"eMMC"` | `""` | `"eMMC 5.1"` | `capacity` (GB — literal `pn[6:9]`) |
| UFS (`FEUDNN*`/`FEUDME*`) | `"UFS"` | `""` | `"UFS 2.2"`/`"UFS 2.1"` | `capacity` (GB — literal `pn[6:9]`) |
| eMCP (`FEPR*`/`FEPN*`) | `"eMCP"` | LPDDR4X (FEPR, **datasheet**) · LPDDR3 (FEPN, **inferido do ePOP**) | `""` | `emcp_nand` (GB) + `emcp_ram` (Gb→GB) — dos known_parts |
| uMCP (`FUPR*`) | `"uMCP"` | `"LPDDR4X"` (**confirmado**) | `"UFS 2.2"` (**obrigatório** — engine deriva versão NAND daqui) | `emcp_nand` + `emcp_ram` — dos known_parts |
| ePOP (`FAPU*`/`FAPE*`) | `"ePoP"` | descritivo (categoria `catalog`) | `""` | **dead-by-type** — sem known_parts |
| nMCP (`F70M*`, legado) | `"MCP"` | descritivo | `""` | **dead-by-type** — sem known_parts |
| NAND raw (`F35*`/`FS35*`/`FS33*`/`FSN*`) | `"NAND Flash"` | `"SLC NAND"` | `"SPI"` / `"Async/ONFI"` | **dead-by-type** — família magra sem capacidade |
| LPDDR4X standalone (`FLXC*`) | `"LPDDR4X"` | `"LPDDR4X"` | `""` | `capacity` (GB do pacote — `pn[7]`, **confirmado DigiKey**) |
| DDR3L standalone (`F60C*`) | `"DDR3L"` | `"DDR3L"` | `"x16"` | `density_gbit` (Gb/die — literal `pn[6:10]`) |

**Regras absolutas** (`CLAUDE.md §6`): `subtype` = só geração/célula. `emcp_ram` = `"LPDDR{n} {cap}GB"`,
tipo antes, capacidade **já em GB**. `tip`/`notes` = tensão/grade/temperatura/package (a Foresee documenta
grade comercial explicitamente — vale preservar).

---

## 2. Anatomia do PN — como LER um chip Foresee

> Estrutura confirmada em PNs reais do **catálogo oficial** + datasheets originais. Três "famílias de
> prefixo" distintas — não force um esquema único. O decode completo vive no `foresee.yaml`; aqui é o mapa.

**Grupo 1 — Storage embarcado (`FE_`/`FU_`/`FA_`/`F7_`):** `pn[0]`=`F` (marca). Leia o **par `pn[1:3]`**:
`EM`=eMMC puro · `EU`=UFS puro · `EP`=eMCP · `UP`=uMCP · `AP`=ePOP. Legado `F70M`=nMCP.
- **eMMC** (`FEMD*`/`FEMK*`/`FEMJ*`): `pn[3]`=pacote (`D`=padrão 11.5×13 · `K`/`J`=subsize) · `pn[4:6]`=grade
  (`NN`=comercial · `ME`=auto G2 · `RM`=industrial · `RW`=industrial wide-temp · `MW`=auto G3) · `pn[6:9]`=
  **capacidade GB, 3 dígitos, literal** (`032`=32GB) · `G` · sufixo de 5 chars. ⚠ one-off: `FEMDRM0128G`
  (industrial 128GB, 4 dígitos) — known_part exato. Âncoras: `FEMDNN032G-A3A55`, `FEMKNN004G-58A42`.
- **UFS** (`FEUD*`): mesmo esquema, `pn[2]`=`U`. `NN`=comercial UFS 2.2 · `ME`=automotivo UFS 2.1 Gear3.
  Âncoras: `FEUDNN064G-C2A56`, `FEUDME064G-B8A19`.
- **eMCP** (`FEP*`): `pn[2:4]` distingue a geração — `PR`=eMCP4x (LPDDR4X) vs `PN`=eMCP3 (LPDDR3). Capacidade
  NÃO é decode posicional confiável (o código do NAND não é literal: `6432`→64GB mas `A832`→128GB via "A8") —
  vem dos **known_parts**. LPDDR4X **confirmado no datasheet** `FEPRF6432-58A1930` (seção "LPDDR4X Functional
  Description", 32Gb=4GB). LPDDR3 do FEPN **inferido** do ePOP (ver §3). Âncoras: `FEPRF6432-58A1930`, `FEPNA1608-58A4302`.
- **uMCP** (`FUP*`): `FUPR`=uMCP4x (UFS 2.2 + LPDDR4X). **Confirmado no catálogo** (2 PNs: `FUPRB6432-C2A56N1`
  64GB+32Gb, `FUPRFA832-C2A56N1` 128GB+32Gb) — LPDDR4X confirmado pela linha "uMCP4x" + voltagem 0.6V + página
  oficial `umcp-memory.html`. Capacidade dos known_parts (mesmo motivo do eMCP). `interface="UFS 2.2"` é
  **obrigatório**: o engine deriva a versão do NAND desse campo (vazio sairia "eMMC"). Estrutura análoga ao eMCP.
- **ePOP** (`FAP*`): `pn[3]` = geração — `FAPU`=ePOP3 (+1.2V) vs `FAPE`=ePOP4x (+0.6V), mesma lógica `PN`/`PR`.
  Dead-by-type (memória empilhada em SoC). Âncoras: `FAPUA0804-58C2948`, `FAPEA3216-58C29N3`.
- **nMCP** (`F70M*`, legado): NAND SLC + LPDDR2 empilhados (pré-eMCP). Dead-by-type. `F70ME0101D-RDWA` (1Gb+1Gb).

**Grupo 2 — NAND raw (`F3_`/`FS_`):** esquema **totalmente diferente**, confirmado char-a-char no datasheet do
`F35SQA002G-WWT`: `F`=marca · `35`=SPI SLC (`33`=paralela SLC; `S35`=SPI 3.3V série ND) · `S`/`U`=tensão (3,3V/1,8V)
· `Q`=I/O SPI · `A`=versão · **`002G`=densidade Gbit, literal** (⚠ aqui "G"=Gbit) · sufixo pacote/temp. **Todas
dead-by-type** → famílias MAGRAS (sem decode de capacidade: irrelevante p/ triagem + evita a armadilha Gb/MB).
Prefixos: `F35` (SPI), `FS35` (SPI ND), `FS33` (paralela TSOP), `FSN` (paralela BGA). Âncoras: `F35UQA512M-WWT`,
`FS35ND04G-S2Y2QWFI000`, `FS33ND01GS108TFI0`, `FSNU8A001G-TWT`.

**Grupo 3 — DRAM standalone (`F6_`/`FL_`):**
- **DDR3L** (`F60C*`): `F60C1A` · `pn[6:10]` = **densidade Gbit, 4 dígitos, literal** (`0002`=2Gb, `0004`=4Gb) ·
  sufixo temp/tensão (`R`=0~95C, `W`=-40~95C wide). Bus `x16`, FBGA96, 1.35/1.5V. Convenção DDR: o mapa guarda
  **MB/die** e o engine deriva "XGb = YMB por die". Âncoras: `F60C1A0002-M6AR`, `F60C1A0004-M79R`.
- **LPDDR4X** (`FLXC*`): **código de capacidade DECIFRADO** — o dígito **antes do "G"** (`pn[7]`) = **GB do
  pacote** (`FLXC2004G`=4GB, `FLXC2002G`=2GB, `FLXC4008G`=8GB). O `2`/`4` **após** `FLXC` é config de canal,
  NÃO capacidade. **Confirmado Tier-1** por 2 anchors DigiKey (`FLXC2004G-30`=4GByte, `FLXC2002G-N2`=2GB) +
  a lista de densidades do catálogo (16/24/32/48/64Gb) que casa 1-a-1. Chaves vistas: 2/3/4/6/8. `NCLDXC1MG256M32`
  (1GB, nomenclatura legada NCLD) fica **fora** desta família.

---

## 3. Armadilhas e Decisões Arquiteturais

- **"G" muda de unidade por linha** (regra #2) — o erro mais provável. eMMC/UFS/LPDDR4X = GB; NAND raw/DDR3L = Gbit.
- **eMCP/uMCP/ePOP misturam GB (NAND/UFS) e Gb (DRAM) no MESMO PN** — dígitos crus lado a lado (`6432` = 64GB + 32Gb),
  unidades diferentes, sem separador. Confirmado pelo catálogo (`"64GB+32Gb"`).
- **eMCP3/FEPN → LPDDR3 é INFERIDO, não confirmado por datasheet FEPNA aberto.** A inferência vem da nomenclatura
  do próprio catálogo (ePOP3=+1.2V=core LPDDR3 vs ePOP4x=+0.6V=LPDDR4X → "3"=LPDDR3). Aceita pelo dono (2026-07-15),
  marcada `confidence=manual` nos known_parts. Contrasta com o eMCP4x/FEPR (LPDDR4X confirmado no Ordering Information).
- **`FEMDRM0128G` é um one-off de 4 dígitos** (industrial 128GB) — NÃO é typo (a Longsys o lista e cross-referencia
  `FSEIASLD-128G`), mas quebra o decode posicional. Coberto por known_part exato, não por chave no mapa.
- **FLXC: o dígito logo após `FLXC` (`2`/`4`) NÃO é capacidade** — é config de canal. A capacidade é só `pn[7]`.
  Fácil errar e ler "2002G"→2GB por engano (o certo é o `4` de "2004G").
- **NAND raw / ePOP / nMCP são dead-by-type** (`profit_family="dead"`) — sempre NÃO RENTÁVEL, independente de
  capacidade. Famílias **magras** de propósito: a triagem já está resolvida pela gramática; capacidade seria só
  cosmética no rótulo e traria a armadilha Gb/MB. Sem known_parts (não gasta aprovação do dono).
- **Longsys ≠ só Foresee** — a mesma empresa vende sob **Lexar**. Um chip "Lexar" é OUTRA marca no catálogo. Os
  FLXC aparecem rotulados "Lexar Enterprise" na DigiKey, mas a pastilha é Foresee (FORESEE LPCAMM2/DRAM da Lexar Ent.).

---

## 4. Rentabilidade — princípio (os valores NÃO ficam aqui)

**Fonte única: `assess_profitability`** (`chips/engine.py`); limiares em **`ProfitabilityConfig`** (admin).
Duráveis: `NAND Flash`, `ePoP`, `MCP` são **sempre NÃO RENTÁVEL por tipo** (dead-by-type, capacidade
irrelevante). `eMMC`/`UFS`/`eMCP`/`uMCP`/`LPDDR4X`/`DDR3L` seguem os limiares normais da família — os valores
mudam com o mercado, não citar aqui. Observado na construção: LPDDR4X 2–8GB e DDR3L 2Gb/4Gb todos **RENTÁVEL**.

---

## 5. Status e Gaps

**Construído (9 categorias / 17 famílias, suíte verde):** eMMC · UFS · eMCP · uMCP · LPDDR4X · DDR3L (RENTÁVEIS,
com known_parts confirmados) + ePOP · NAND raw · nMCP (dead-by-type, só gramática). Golden por família em `_FORESEE_GOLDEN`.

**Gaps deixados p/ o dono decidir:**
1. **`NCLDXC1MG256M32`** (LPDDR4X 1GB, nomenclatura legada NCLD, fora da família FLXC) — adicionar como known_part
   avulso se aparecer na bancada (1GB provavelmente abaixo do limiar → NÃO RENTÁVEL de todo jeito).
2. **Decode de capacidade do NAND raw** — hoje omitido de propósito (dead-by-type + armadilha Gb/MB). Só faria
   sentido por rótulo mais rico ("SLC NAND 512MB"), nunca por rentabilidade.
3. **Sufixos após o "-"** (revisão/velocidade/temperatura) não decodificados em nenhuma linha — não bloqueiam tipo/capacidade.
4. **Prefixos legados** `FSEIASLD*`/`NCEMASLD*` — avaliar se ganham família própria ou ficam como known_parts avulsos.

---

## 6. Fontes de pesquisa

Tier 1: `longsys.com` (site + catálogo `BP_FORESEE_Embedded-Storage-Product-Catalogue` + datasheets). Tier 1
(espelho): LCSC, DigiKey, community.nxp.com. DigiKey/LCSC também servem de **cross-check** de capacidade literal
(campo "XGByte"). Tier 2: Octopart, agregadores. **Evitar como primária:** distribuidor sem datasheet, fóruns,
IA sem verificação. Sempre conferir a unidade antes de gravar: `Xbit ÷ 8 = YB` — e **qual linha** está lendo (§0.2 #2).

---

## 7. Histórico (o *porquê* — durável)

- **2026-07-15/16:** Marca construída DO ZERO por este chat de infra (o chat Foresee não tinha capacidade técnica),
  Tier-1, categoria por categoria. Levantados o catálogo oficial completo, o datasheet eMCP `FEPRF6432-58A1930`
  (community.nxp.com) e 2 anchors DigiKey (FLXC `2002G`/`2004G`) que decifraram o código de capacidade LPDDR4X
  (`pn[7]`=GB). 9 categorias, 17 famílias, 34 known_parts confirmados. Decisões: eMCP3=LPDDR3 inferido do ePOP
  (aceito pelo dono); ePOP/NAND raw/nMCP dead-by-type sem known_parts; `FEMDRM0128G` (4 dígitos) coberto por
  known_part exato. Suíte 273 verde a cada passo.

> Inventário de famílias/mapas → **`foresee.yaml`** (Trilha A). known_parts confirmados (proveniência Tier-1 na
> `notes`) → **banco** (Opção 2), via `submit_known_parts`. Cross-marca (comandos/convenção/rentabilidade) → **`CLAUDE.md`**.
