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
   ⚠ **Teoria unificadora da raiz legada `NC`** (2026-08-19): a raiz `NC` sempre é seguida por um código de
   TIPO de 2 chars — `LD`=LPDDR (`NCLD*`) · `EM`/`EF`=eMMC (`NCEM*`/`NCEF*`, ex. `NCEMASLD-32G/64G/128G`,
   `NCEMBSF9-16G/32G`, `NCEFEH58-08G/16G/32G`) · **`EP`=eMCP (`NCEP*`, achado 2026-08-26 via
   `NCEPNCCM4-1608`)** — 3ª categoria confirmada nesta raiz, espelhando o mesmo par `pn[1:3]`
   (`EM`/`EU`/`EP`/`UP`/`AP`) já usado no prefixo moderno `FE_` (`EP`=eMCP em `FEPR`/`FEPN` também).
   Útil pra prever prefixo desconhecido na bancada: `NCUF...` seria hipoteticamente UFS, `NCUP...`
   uMCP, `NCAP...` ePOP — por analogia (não confirmado, é só teoria, exceto EP que já foi confirmado).
   `NCEMASLD` pode ser um estágio ainda mais antigo do MESMO produto físico que `FSEIASLD` (mesmo sufixo
   `ASLD`, mesmas 3 capacidades, mesmo pacote) — nota histórica, não muda a classificação.
   ⚠ **Dois códigos de vendor dentro de `NCEM*` NÃO são a mesma geração eMMC** — `NCEMASLD*` é eMMC 5.1
   (JEDEC v5.1, confirmado no test report), `NCEMBSF9*` é eMMC 5.0 (JEDEC eMMC 5.0, confirmado no
   datasheet oficial próprio, Rev A0 2015) — datasheets DIFERENTES, não presumir a interface de um
   código de vendor a partir de outro dentro da mesma raiz `NC`/`EM`.

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
  pacote** (`FLXC2004G`=4GB, `FLXC2002G`=2GB, `FLXC4008G`=8GB). O `2`/`4` **após** `FLXC` é config/reserved
  (rótulo exato no Ordering Information oficial, datasheet `D-00246`), NÃO capacidade. **Confirmado Tier-1**
  por 2 anchors DigiKey (`FLXC2004G-30`=4GByte, `FLXC2002G-N2`=2GB) + a lista de densidades do catálogo
  (16/24/32/48/64Gb) que casa 1-a-1 + a seção "4 Ordering Information" do datasheet oficial `D-00246`
  (`FLXC2002G-N2`, aberto na íntegra 2026-08-19) que documenta capacidade/pacote/geração campo a campo.
  Chaves vistas: 2/3/4/6/8.
- **LPDDR4 padrão** (`FL4C*`, irmã de `FLXC*`): mesmíssimo esqueleto posicional, só troca o dígito de
  geração — `X`→`4` (`FLXC2002G`↔`FL4C2001GD9`). Achado 2026-08-19 via PN de bancada `FL4C2001GD9`
  (1GB); confirmado por analogia estrutural ao Ordering Information oficial da `FLXC2002G-N2` (a mesma
  plataforma lista opção de voltagem COM e SEM o modo 0.6V — exatamente o par LPDDR4/LPDDR4X já visto em
  `NCLD4C`/`NCLDXC`) + existência em 2 distribuidores reais (DigiPart). **Terceira ocorrência** do padrão
  "dígito=padrão vs `X`=baixa-voltagem" nesta marca (depois de `NCLD4C`/`NCLDXC` e do próprio `FLXC`) —
  já é uma convenção consolidada da Foresee/Longsys, não coincidência. Só a capacidade 1GB confirmada até
  agora; outras capacidades da linha `FL4C` não localizadas (gap, ver §5).
- **LPDDR5 standalone (`FL5P*`) — CATEGORIA NOVA, achada 2026-08-19.** Mesmo esqueleto posicional
  (`FL`+geração+pacote+config+capacidade+`G`+sufixo), geração=`5` (LPDDR5), mas pacote=`P` (não `C`) —
  **pacote físico diferente**: TFBGA315 (vs VFBGA200 do FLXC/FL4C, mais pinos, geração mais nova).
  Capacidade pela MESMA regra posicional (`pn[7]`). Achada via portfólio estruturado da distribuidora
  RESTAR FRAMOS (campo "Density" próprio por PN — a mesma tabela cross-valida 100% dos PNs FLXC/F60C/
  NCLDXC já confirmados, o que dá confiança na fonte). 5 known_parts confirmados: `FL5P4008G-60`=8GB
  (Density 64Gbit, página própria + DigiPart), `FL5P2004G-60`=4GB (**DigiKey, 5 fontes independentes** —
  a capacidade mais bem confirmada da marca), `FL5P4006G-62`/`FL5P4006G-51`=6GB, `FL5P4004G-N5`=4GB
  (manual, só a tabela). Rótulo "Lexar Enterprise" na DigiKey de novo (mesma pastilha Foresee, regra
  já documentada em §3). `chip_type="LPDDR5"` já existe em `chips/chip_types.py`, nenhuma declaração
  nova necessária. Golden novo necessário se a família ganhar `ChipFamily` própria (hoje é só known_part
  avulso, como FL4C/FLXC).
- **Legado `NCLD*`** (fora da família `FLXC`, fora do yaml — só known_parts avulsos): estrutura **decifrada
  via datasheet oficial** (`NCLD4CXMAXXXM32` Rev B2 2017, die Micron) — `NC`(Longsys) + `LD`+geração
  (`4`=LPDDR4 · `X`=LPDDR4X · `3`=LPDDR3) + pacote (`C`=200-ball, LPDDR4/4X · `B`=178-ball, LPDDR3) +
  CS-count (`1`/`2`) + opcional 2 chars de código de die/fornecedor (`MA`=die Micron; a subfamília `3B`
  costuma vir SEM esse par) + `{profundidade}M{largura}` = capacidade por `profundidade×largura÷8`.
  **TRÊS subfamílias, TIPO diferente:** `NCLD4C*` (datasheet SEM opção 0.6V) = **LPDDR4 padrão**;
  `NCLDXC*` (catálogo oficial lista COM opção 0.6V, seção "LPDDR4x") = **LPDDR4X** — inclui
  `NCLDXC1MG256M32` (1GB); `NCLD3B*` (datasheet próprio `D-00151`, mirror Scribd, + página oficial
  `longsys.com/.../lpddr.html` confirma a linha "FORESEE LPDDR3") = **LPDDR3**, pacote 178-ball
  (fisicamente menor/mais antigo que o 200-ball das outras duas). Confirmado p/ 9 PNs no total (4 do
  datasheet NCLD4C + 1 do catálogo NCLDXC + 1 do datasheet NCLD3B + 3 por fórmula/existência forte em
  distribuidor), submissões `foresee_ncld_legacy_2026-07-16.yaml` (2026-07-16, duas rodadas).

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
1. ~~`NCLDXC1MG256M32` avulso~~ — **RESOLVIDO 2026-07-16**: PN buscado na bancada (`NCDLXC4MJ512M32`,
   provável erro de transcrição — ver notes do known_part `NCLDXC1MJ512M32`) disparou pesquisa do cluster
   `NCLD*` inteiro. 11 known_parts submetidos (`foresee_ncld_legacy_2026-07-16.yaml`): 5 `confirmed`
   (datasheet oficial `NCLD4CXMAXXXM32` + catálogo) + 6 `manual` (fórmula validada + existência em
   distribuidor). **Pendente confirmação do dono:** qual é o PN físico real na bancada (o match
   `NCLDXC1MJ512M32` é hipótese bem fundamentada, não 100% certa — recomendo reconferir o laser-marking).
2. ~~`NCLD3B*`~~ — **RESOLVIDO 2026-07-16 (2ª rodada)**: PN buscado na bancada foi exatamente
   `NCLD3B2256M32` (string real, sem erro de transcrição desta vez). Achado o datasheet próprio
   `D-00151 FORESEE - LPDDR3 - NCLD3B1256M32 - 178ball` (mirror Scribd) + a página oficial de produto
   LPDDR3 da Longsys — resolve a geração como **LPDDR3** (não era ambiguidade 4/4X). 4 known_parts
   submetidos no mesmo arquivo (`NCLD3B1256M32` confirmed; `2256M32`/`1128M32`/`2512M32` manual,
   fórmula + existência forte em distribuidor — 50k/309k/22k unidades agregadas respectivamente).
3. **Decode de capacidade do NAND raw** — hoje omitido de propósito (dead-by-type + armadilha Gb/MB). Só faria
   sentido por rótulo mais rico ("SLC NAND 512MB"), nunca por rentabilidade.
4. **Sufixos após o "-"** (revisão/velocidade/temperatura) não decodificados em nenhuma linha — não bloqueiam tipo/capacidade.
5. ~~**Prefixos legados** `FSEIASLD*`/`NCEMASLD*`~~ — **`NCEMASLD*` parcialmente resolvido 2026-08-19**: PN
   de bancada `NCEMASLD32G` puxou os 3 known_parts da linha (`-32G` confirmed via test report oficial
   Longsys/Radxa; `-64G`/`-128G` confirmed via datasheet LCSC próprio + convenção literal + aritmética de
   die consistente). **`NCEMBSF9*` resolvido 2026-08-19 (2ª rodada)**: PN de bancada `NCEMBSF916G` —
   código de vendor NOVO dentro da mesma raiz `NCEM*` (não estava na lista de irmãos não-perseguidos
   abaixo). Datasheet oficial próprio (Pine64, Rev A0 2015, eMMC 5.0 — geração DIFERENTE do `NCEMASLD`
   que é 5.1) documenta a família completa em 2 SKUs: `-16G`/`-32G`, ambos confirmed. `-64G` visto só em
   revenda genérica (sem datasheet/distribuidor estruturado) — não submetido, gap residual.
   **`NCEMAD7B*`/`NCEMAD9D*` resolvidos 2026-08-26**: PN de bancada `NCEMAD7B08G` levou a uma fonte
   nova de peso — "Rockchip Solutions eMMC Support List" v1.63 (documento oficial de validação de SoC
   vendor, mesma força de um test report). `NCEMAD9D-16G`/`NCEMAD9D-08G` confirmed (linha viva da
   tabela: NAND/processo/versão/pacote completos). `NCEMAD7B-08G` manual (só no histórico de revisão
   do documento — "Add 2017-07-28", provável EOL depois — + 5 distribuidores convergentes; versão
   eMMC 5.0/5.1 NÃO confirmada em fonte própria, deixada em branco). **`NCEMBS99*` resolvido
   2026-08-26 (2ª rodada, mesmo dia)**: PN de bancada `NCEMBS9916G` — a 1 char de distância do
   `NCEMBSF9-16G` já confirmado (F↔9), sinalizei como possível transcrição; **o dono confirmou que o
   código está correto** — é um vendor-code DISTINTO e real. Sem datasheet oficial próprio achado,
   mas evidência hands-on forte: blog de reparo ripitapart.com (relato próprio de troca do chip +
   comentário do autor citando "the datasheet" pro pacote BGA169 + um 2º leitor confirmando o mesmo PN
   em outro tablet, anos depois). `-16G` manual (evidência forte); `-32G` manual (só revenda,
   evidência mais fraca, sinalizado como tal). Lição: nem toda suspeita de transcrição procede — o
   fuzzy match de 1-char de distância é um bom PONTO DE PARTIDA pra perguntar, nunca uma conclusão.
   **`NCEMAD6B-16G` resolvido 2026-08-26 (3ª rodada, mesmo dia)**: PN de bancada `NCEMAD6B16G`, o
   mesmo lead flagrado horas antes. Peguei a versão MAIS NOVA do documento Rockchip — renomeado
   "EMMC Approved Vendor List" v1.95 (2026-03-31) — confirma "Add 2017-11-27", também sem linha viva
   (EOL, mesmo padrão do AD7B). Corroborado por Alibaba (explicita pacote "153bga"), AliExpress
   (kit de reposição com AD7B/ASD9), OMO Electronic. manual. **Achado estrutural:** pacote 153-ball
   (11.5x13mm, família ASLD/ASD9/AD9D/AD6B) é FISICAMENTE DIFERENTE do 169-ball (12x16mm, família
   BSF9/BS99) — duas famílias de pacote convivem dentro do mesmo cluster `NCEM*`. **Ampliado no mesmo
   arquivo** (pedido do dono, "continue procurando da mesma família"): achado o irmão
   `NCEMAD6B-32G` (2 fontes de revenda independentes, manual) — descartada de propósito uma alegação
   de "`NCEMAD6B-08G`" de um resumo de busca que, ao conferir os links reais, citava
   `NCEMAD7B-08G`/`NCEMAM6G-08G` (códigos diferentes) — mais uma alucinação catalogada. **Correção
   importante:** a v1.95 confirma que `NCEMAD9D-16G`/`NCEMAD9D-08G` (que eu tinha achado `confirmed`
   na tabela viva do v1.63/2022) e `FSEIASOD-16G` foram REMOVIDOS oficialmente em 2023-03-03 (rev
   1.73) — ou seja, EOL agora. Não muda a classificação (specs continuam válidas), só o status
   comercial; registrado aqui pra quem olhar o histórico não estranhar.
   **`NCEFEH58*` resolvido 2026-08-26 (4ª rodada, mesmo dia)** — PN de bancada `NCEFEH5816G`. Raiz
   `NCEF`, não `NCEM` (4º char "F" em vez de "M") — refina a teoria da raiz `NC` (só o "E" parece
   fixo pra eMMC). Evidência mais forte já vista nesta marca pra um vendor-code sem datasheet
   próprio: `NCEFEH58-08G` tem **8 distribuidores independentes** no DigiPart (um deles, YIC
   International, confirma pacote BGA153 direto no campo estruturado — mesma família 153-ball do
   ASLD/ASD9/AD9D/AD6B); `-16G` (o PN de bancada) 1 distribuidor + yoycart + kit AliExpress; `-32G`
   2 distribuidores. As 3 capacidades manual. DigiPart revelou via "See Also" um sub-cluster `NCEF*`
   AINDA maior: `NCEFES78-08G`, `NCEFES88-04G`, `NCEFESA8-08G`, `NCEFESE8-04G`, `NCEFES86-04G`,
   `NCEFES76-08G` — não pesquisados, registrados como lead.
   Outros vendor-codes ainda só no histórico Rockchip, sem linha viva nem distribuidor pesquisado a
   fundo: `NCEMAH59-16G`, `NCEFBS98-16G`, `NCEMBS41-04G/08G`, `NCEMBS61-08G/16G`, `NCEMBD39-16G`.
   `NCEMAHBD*`/`NCEMASKG*`/`NCEMAM59*` do gap original ainda não confirmados em nenhuma fonte nova.
   Cluster grande demais pra uma rodada só — próxima sessão se o dono quiser esgotar via o mesmo
   documento Rockchip + DigiPart "See Also".
   `FSEIASLD*` (o "elo intermediário" pré-`FEMD*`) segue não
   pesquisado diretamente — só known_parts de irmãos (`FEMDRM*`) citam a correspondência no catálogo.
7. **`NCEP*` — CATEGORIA NOVA (eMCP na raiz legada `NC`), achada 2026-08-26. ✅ RESOLVIDA no
   mesmo dia (7ª busca) — capacidade confirmada em Tier-1.** PN de bancada `NCEPNCCM41608` →
   `NCEPNCCM4-1608`, tipo "EP"=eMCP (3ª categoria do root `NC`, depois de LD/EM-EF). Existência
   fortíssima (7 distribuidores DigiPart). Capacidade CONFIRMADA via dois documentos oficiais
   Longsys: o catálogo atual (longsys.com PDF) lista a família eMCP3 com P/N `FEPNA1608-*`,
   Density="16GB+8Gb" (mesmo sufixo "1608", mesmo pacote FBGA221/11.5x13mm); o datasheet E-00784
   confirma a gramática geral [NAND GB][RAM Gb] do sufixo eMCP Foresee. `emcp_nand="16GB"`,
   `emcp_ram="LPDDR3 1GB"` (LPDDR3 por analogia forte ao irmão `NCEPNA6M4-0808`, não documento
   direto do NCCM4 — ver submissão). confidence=manual. Submissão corrigida:
   `submissions/foresee_ncep_emcp_2026-08-26.yaml` (2ª versão). Sub-cluster `NCEP*` mais amplo
   (vendor-codes vistos de relance: `NA6M4`, `N35X`) segue não mapeado além destes dois.
6. **Possível família `NCLD` (Trilha A)?** A estrutura já está decifrada (§2) com **3 subfamílias/9 âncoras**
   Tier-1 (4C=LPDDR4, XC=LPDDR4X, 3B=LPDDR3) — caso mais forte do que quando o gap #1 original foi escrito.
   Não propus a família sozinho (decisão arquitetural do dono); sinalizo a possibilidade caso mais PNs
   `NCLD*` apareçam na bancada. Variantes com código de die/vendor de 2 chars (`NCLD3B1M7256M32` etc.) vistas
   mas não submetidas — mesma capacidade das versões "limpas". **1ª do "lote extra" pedida e submetida
   2026-08-28** (`NCLD3B2M5256M32`, PN de bancada real — ver `submissions/foresee_ncld3b2m5256m32_2026-08-28.yaml`
   e histórico). **Restam `NCLD3B1M7256M32`/`NCLD3B2M7512M32`** — busca dedicada 2026-08-28 (DigiPart
   ×2, netComponents ×2 — JS-bloqueado pro fetch, mesmo problema técnico de sempre —, WebSearch ×5,
   Upverter ×2, Preduo index 178ball LPDDR3 — 82 resultados, Foresee não apareceu nas primeiras 24)
   NÃO achou nada re-verificável hoje além da nota antiga deste próprio arquivo (16/07, "vistas no
   netComponents", não reproduzível agora). Diferente do M5-256M32 (que teve um irmão M5 REAL
   confirmado hoje), estes dois ficam sem confirmação fresca — não submetidos, por decisão de manter
   o padrão "sem capacidade/existência confirmada não submete". Bônus do lado: achado datasheet
   oficial real (`linux-sunxi.org`, mirror Longsys) pras versões LIMPAS `NCLD3B1256M32`/`NCLD3B2512M32`
   — já `confirmed`/`manual` no banco, não precisa reabrir.
7. **`FL4C*` — só 1GB confirmado.** Achada 2026-08-19 (PN de bancada `FL4C2001GD9`), irmã LPDDR4-padrão da
   `FLXC*` (LPDDR4X). Tentei `FL4C2002G`/`FL4C2004G` (sem sufixo) no DigiPart, sem resultado — o agregador
   parece exigir o sufixo completo (`-D9` etc.), que não dá pra adivinhar sem PN-âncora real. A tabela
   RESTAR FRAMOS que resolveu o `FL5P` (item 8) NÃO lista nenhum `FL4C*` — parece genuinely mais raro/menos
   distribuído que os irmãos `FLXC`/`FL5P`. Se mais PNs `FL4C*` aparecerem na bancada, mesma pesquisa.
8. ~~`FL5P*` (LPDDR5)~~ — **RESOLVIDO 2026-08-19**: categoria nova inteira, 5 known_parts confirmados
   (8/6/4GB) via portfólio estruturado RESTAR FRAMOS + DigiKey. Ver §2. Capacidades ainda não vistas:
   2GB (`FL5P2002G`, tentei sem sufixo no DigiPart, sem resultado) e 3GB — mesma limitação do item 7
   (agregador exige sufixo completo). Gap residual pequeno, próxima rodada se aparecer PN novo.
9. **`FL3B1001G` — existência confirmada pelo dono, specs SEM fonte externa.** PN de bancada
   2026-08-19; buscas em DigiPart/netComponents/RESTAR FRAMOS/web geral não acharam nenhuma fonte
   confiável (só páginas suspeitas de alucinação de busca, descartadas). O dono confirmou por
   observação física direta que o PN existe. Decode estrutural via gramática já validada do root
   `FL` (pn[2]='3'→LPDDR3 por analogia a `4`/`X`/`5`; pn[3]='B'→pacote, mesma combinação "3B" já
   provada LPDDR3 no root legado `NCLD3B*`; pn[7]='1'→1GB) dá LPDDR3 1GB — mas SEM datasheet/
   distribuidor independente. Submetido como `estimated` (não `manual`) em
   `submissions/foresee_fl3b_lpddr3_2026-08-19.yaml`, oculto até revisão manual. Se aparecer PN
   irmão (`FL3B*` outra capacidade) ou fonte documental, promover.

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

- **2026-07-16:** PN buscado na bancada (`NCDLXC4MJ512M32`, não encontrado, 0 fuzzy) puxou pesquisa do
  cluster legado `NCLD*` (pré-`FLXC`). Achado o datasheet oficial `NCLD4CXMAXXXM32` (Micron die, 2017) que
  decifra a estrutura completa (§2) e confirma `NCLD4C*`=LPDDR4 padrão (sem opção 0.6V) vs `NCLDXC*`
  (catálogo)=LPDDR4X. 11 known_parts submetidos (5 confirmed + 6 manual), 3 `NCLD3B*` deixados de fora
  (tipo não confirmado). HardDiskDirect flagrado rotulando `NCLDXC1MJ512M32` como "(16GB)" — errado, o
  correto é 2GB (mesma armadilha Gb/GB já catalogada no `SK_HYNIX.md`). Match do PN da bancada é hipótese
  (transcrição `DL`↔`LD` + `4`↔`1`), não certeza — pendente confirmação do dono.

- **2026-07-16 (2ª rodada, mesmo dia):** Novo PN de bancada, `NCLD3B2256M32` — desta vez string exata,
  sem erro de transcrição, fechando o gap `NCLD3B*` deixado aberto na rodada anterior. Achado o datasheet
  próprio (`D-00151`, mirror Scribd) que resolve a geração como **LPDDR3** (pacote 178-ball, diferente do
  200-ball de `NCLD4C`/`NCLDXC`) — não era a ambiguidade 4-vs-4X que eu tinha suposto antes. Mais 4
  known_parts no mesmo arquivo de submissão. Duas lições de processo registradas na memória do projeto:
  (a) antes de descartar um candidato por "evidência fraca", cruzar com fontes Tier-1 já coletadas
  nesta mesma sessão (aconteceu com `FEMDRM008G-A3A55`, ver submissão eMMC); (b) 3ª captura de alucinação
  de resumo de busca automático nesta marca (desta vez a página HQonline de `NCLD3B2512M32`) — sempre
  abrir a página e olhar os campos estruturados de verdade antes de citar como fonte.

- **2026-08-19:** PN de bancada `NCEMASLD32G` (eMMC industrial legado, fora do `FEMD*`) resolvido. Achado
  um Test Report OFICIAL da Longsys (papel timbrado, hospedado pela Radxa como qualificação do Rock Pi) —
  a fonte mais forte já vista nesta marca, com capacidade/dimensões/interface lidas diretamente do
  documento. 3 known_parts submetidos (`-32G`/`-64G`/`-128G`, todos confirmed). Insight estrutural novo:
  a raiz legada `NC` sempre é seguida por um código de tipo de 2 chars (`LD`=LPDDR, `EM`=eMMC), espelhando
  o par `pn[1:3]` do prefixo moderno `FE_` — une os dois clusters legados (`NCLD`/`NCEM`) numa só teoria.
  Achado um cluster maior de irmãos `NCEM*` (códigos de vendor diferentes de "ASLD") não perseguido agora.

- **2026-08-19 (7ª busca, mesmo dia) — `NCEMBSF9`, 2º código de vendor confirmado dentro de `NCEM*`.**
  PN de bancada `NCEMBSF916G`. Achado datasheet oficial próprio da Shenzhen Longsys Electronics
  ("NCEMBSF9-xxG Specification" Rev A0, 2015, JEDEC eMMC 5.0) hospedado pela Pine64 — mesmo padrão de
  mirror confiável (fabricante de SBC hospedando doc. de qualificação) já usado no test report
  `NCEMASLD` via Radxa. A Seção 2 "Product List" documenta a família completa numa tabela só: 2 SKUs,
  `-16G` (bate exato com o PN de bancada) e `-32G`. Achado importante: `NCEMBSF9*` é eMMC **5.0**, não
  5.1 como o `NCEMASLD*` — apesar de ambos começarem com a mesma raiz `NCEM`, são datasheets/gerações
  diferentes; corrigi a suposição implícita de que todo `NCEM*` seria 5.1. 2 known_parts confirmed
  submetidos. Um `-64G` aparece em revenda genérica (grandado/Alibaba) mas sem datasheet ou distribuidor
  estruturado por trás — sinalizado no gap, não submetido (evidência fraca demais mesmo pra `estimated`
  com specs decididas).

- **2026-08-19 (2ª busca, mesmo dia):** PN de bancada `FL4C2001GD9` — irmã LPDDR4-**padrão** (não-X) da
  `FLXC*` já confirmada, achada por analogia estrutural direta ao par `NCLD4C`/`NCLDXC` (mesma marca, 2
  gerações de nomenclatura, mesmo padrão "dígito=padrão vs `X`=baixa-voltagem"). Abri o datasheet oficial
  da irmã `FLXC2002G-N2` (`D-00246`) e a seção "Ordering Information" confirma a mesma plataforma tem
  opção de voltagem com/sem o modo 0.6V — é a 3ª vez que esse padrão aparece nesta marca, já uma
  convenção consolidada, não coincidência. Existência do PN exato confirmada em 2 distribuidores
  (DigiPart). 1 known_part `manual` submetido; só a capacidade 1GB confirmada, outras da linha `FL4C`
  não localizadas (gap).

- **2026-08-19 (3ª busca, mesmo dia) — categoria `FL5P`/LPDDR5 inteira, a pedido do dono ("achar o
  máximo de chips possível").** Achado o portfólio DDR estruturado da distribuidora RESTAR FRAMOS
  Technologies (campo "Density" por PN, taxonomy) — a mesma tabela cross-validou 100% dos PNs FLXC/
  F60C/NCLDXC já confirmados nesta marca, dando confiança pra usá-la como fonte pros novos. Achada uma
  categoria **inteiramente nova**: `FL5P*` = LPDDR5 standalone, pacote TFBGA315 (físico diferente do
  VFBGA200 do FLXC/FL4C). 5 known_parts confirmados (8/6/4GB), incluindo `FL5P2004G-60` com **5 fontes
  independentes** (DigiKey + Enrgtech + SemiKart + 2x Alibaba) — a capacidade mais bem confirmada da
  marca até hoje. De quebra, achei e submeti 3 PNs novos de sufixo pra `FLXC` já confirmada (mesmas
  capacidades, SKUs distintos). `chip_type="LPDDR5"` já existia em `chips/chip_types.py`, zero atrito
  no portão.

- **2026-08-19 (4ª busca, mesmo dia) — `FL3B1001G`, existência sem fonte documental.** Busca
  exaustiva (DigiPart, netComponents, tabela RESTAR FRAMOS, web geral) não achou NENHUMA fonte
  confiável — cheguei a concluir que o PN podia não existir. O dono corrigiu por observação física
  direta na bancada ("estou vendo ele na minha frente"). Aceito a existência como fato; as specs
  (LPDDR3 1GB) vêm só de decode estrutural (mesma gramática do root `FL` já usada em FL4C/FLXC/FL5P,
  reforçada pela combinação "3B" já provada = LPDDR3+pacote-B no root legado `NCLD3B*`). Sem fonte
  externa, o known_part foi submetido como `estimated` (não `manual`) — primeira vez nesta marca que
  uma submissão se apoia SÓ em confirmação física + inferência estrutural, sem nenhum documento ou
  distribuidor por trás. Lição: confirmação física direta do dono resolve a dúvida de EXISTÊNCIA, mas
  não substitui fonte Tier-1/2 pra SPECS — as duas perguntas são independentes.

- **2026-08-26 — `NCEMAD7B`/`NCEMAD9D`, e um documento novo de peso: Rockchip eMMC Support List.** PN
  de bancada `NCEMAD7B08G`, um dos irmãos `NCEM*` já flagrados no gap desde 2026-08-19 mas nunca
  pesquisado a fundo. Achei uma fonte NOVA e forte: a "Rockchip Solutions eMMC Support List" v1.63 —
  documento oficial de um fabricante de SoC listando todo eMMC validado/testado nas plataformas deles,
  mesma categoria de força que o test report Radxa usado no `NCEMASLD`. A tabela VIVA (v1.63) tinha,
  de bônus, 2 irmãos `NCEMAD9D-16G`/`NCEMAD9D-08G` com detalhe completo (NAND/processo/versão/pacote)
  — confirmed. O `NCEMAD7B-08G` da bancada só aparece no HISTÓRICO DE REVISÃO do mesmo documento
  ("Add 2017-07-28", provável EOL depois) — ainda assim, 5+ distribuidores independentes convergem em
  8GB/eMMC/FORESEE, então submeti como `manual` (não `confirmed` — versão eMMC 5.0 vs 5.1 não veio de
  fonte própria, um resumo de busca alegou "5.0" mas não abri documento primário que confirme isso
  especificamente, então deixei o campo em branco em vez de copiar a alegação). O MESMO documento
  revelou um cluster BEM maior de vendor-codes `NCEM*`/`NCEF*` nunca antes vistos (só no histórico de
  revisão, sem linha viva — capacidade legível mas sem versão/processo confirmados): `NCEMAD6B-16G`,
  `NCEMAH59-16G`, `NCEFEH58-08G/16G/32G`, `NCEFES88-04G`, `NCEFES78-08G`, `NCEFBS98-16G`,
  `NCEMBS41-04G/08G`, `NCEMBS61-08G/16G`, `NCEMBD39-16G`, `FSEIASOD-16G`. Achado estrutural: o prefixo
  `NCEF` (não `NCEM`) aparece nesse cluster — a teoria "raiz `NC`+2 chars fixos de tipo" pode precisar
  de refinamento (só o 3º char `E` parece fixo pra eMMC, o 4º varia: `M` ou `F`). Não submetidos agora
  — cluster grande demais pra uma rodada, registrado no gap pra quando o dono quiser esgotar a fonte.
  **Lição reforçada:** documento de validação de SoC vendor (Rockchip/Radxa/Pine64, todos hospedando
  spec de fabricante) é uma categoria de fonte tão forte quanto datasheet, e frequentemente revela
  cluster inteiro de uma vez — mesma lição da tabela RESTAR FRAMOS, um padrão que já se repete 3x
  nesta marca.

- **2026-08-26 (2ª busca, mesmo dia) — `NCEMBS99`, suspeita de transcrição REFUTADA pelo dono.** PN
  de bancada `NCEMBS9916G`, a 1 caractere do já-confirmado `NCEMBSF9-16G` (vendor-code: "F" vs "9").
  Segui o protocolo padrão desta marca — sinalizei a suspeita e pedi reconfirmação física em vez de
  assumir — mas desta vez o dono respondeu "o código está correto": é um vendor-code DISTINTO e real,
  não erro de leitura. Sem datasheet oficial próprio (busca dedicada não achou), mas evidência
  hands-on sólida lida na íntegra (não resumo de IA): blog de reparo eletrônico ripitapart.com —
  relato próprio do autor trocando um "Foresee NCEMBS99-16G" defeituoso, e um comentário do MESMO
  autor citando "the datasheet" pra confirmar pacote BGA169; um leitor diferente, num comentário de
  2023, relata ter achado o mesmo PN desmontando outro tablet — 2ª pessoa independente com o chip
  físico em mãos. `-16G` manual (evidência forte); `-32G` manual, mais fraco (achado só em revenda
  chinahao.com, sinalizado como tal na nota). **Lição de processo:** a suspeita de transcrição por
  1-char de distância (mesmo com o fuzzy match do engine sugerindo) é sempre um PONTO DE PARTIDA pra
  perguntar ao dono, nunca uma conclusão a assumir sozinho — desta vez a leitura da bancada estava
  certa, e o `NCEMBSF9` "parecido" era só coincidência dentro do mesmo cluster de nomenclatura.

- **2026-08-26 (3ª busca, mesmo dia) — `NCEMAD6B`, mesmo lead da 1ª busca de hoje, agora com PN de
  bancada real.** `NCEMAD6B16G`. Peguei a versão MAIS NOVA do documento Rockchip (renomeado "EMMC
  Approved Vendor List" v1.95, 2026-03-31) — confirma a adição oficial de 2017-11-27, ainda sem linha
  viva (EOL). Corroborado por Alibaba/AliExpress/OMO Electronic. manual. Achado estrutural relevante:
  o cluster `NCEM*` tem DUAS famílias físicas de pacote — 153-ball 11.5x13mm (ASLD/ASD9/AD9D/AD6B) e
  169-ball 12x16mm (BSF9/BS99) — vale a pena ter isso em mente ao decodificar o próximo vendor-code.
  Bônus: a v1.95 revelou que `NCEMAD9D-16G`/`08G` e `FSEIASOD-16G`, que eu tinha marcado `confirmed`
  numa rodada anterior via a tabela viva do v1.63 (2022), foram removidos oficialmente em 2023 — EOL,
  não invalida a spec, só o status comercial (documentado pra não confundir quem olhar depois).

- **2026-08-26 (4ª busca, mesmo dia) — `NCEFEH58`, raiz `NCEF` (não `NCEM`), evidência mais forte do
  dia.** PN de bancada `NCEFEH5816G`, o lead já flagrado desde a 1ª rodada de hoje. DigiPart revelou
  a convergência mais forte já vista nesta marca pra um vendor-code sem datasheet próprio: a
  capacidade `-08G` tem 8 distribuidores independentes concordando (YIC International confirma
  pacote BGA153 direto num campo estruturado, não texto solto). `-16G` (o PN de bancada) e `-32G`
  também confirmados, com menos distribuidores cada. 3 known_parts manual submetidos. Achado
  estrutural: o 4º caractere da raiz `NC` varia entre "M" (`NCEM*`) e "F" (`NCEF*`) — a teoria de
  "2 chars fixos de tipo" precisa de ajuste, só o 3º char "E" parece realmente fixo pra eMMC. Bônus:
  as páginas DigiPart do `NCEFEH58` linkam um sub-cluster `NCEF*` ainda maior via "See Also" — não
  perseguido agora, registrado como lead.

- **2026-08-26 (5ª busca, mesmo dia) — `NCEP*`, categoria eMCP INTEIRAMENTE NOVA na raiz legada `NC`.**
  PN de bancada `NCEPNCCM41608`. Até hoje a raiz `NC` só tinha dado LPDDR-standalone (`NCLD`) e eMMC
  (`NCEM`/`NCEF`) — "EP" é o mesmo código de eMCP já confirmado no prefixo moderno `FEPR`/`FEPN`, e um
  documento achado no Scribd se chama literalmente "Emcp Specification: NCEPNA6M4-xxxx" (título do
  documento, não resumo de IA) pra um vendor-code irmão — confirma a categoria. Existência
  fortíssima: 7 distribuidores independentes no DigiPart. A capacidade, porém, ficou só como
  INFERÊNCIA posicional (sufixo "1608" ≈ 16GB NAND + 8Gb RAM, batendo com um combo oficial já
  documentado da linha eMCP Foresee e com a convenção de sufixo do irmão `NA6M4-0808`) — sem
  datasheet Tier-1 aberto pra confirmar a geração da RAM, segui a regra "capacidade eMCP só Tier-1" e
  deixei `emcp_nand`/`emcp_ram` em branco, submetendo como `estimated` identity-only. Acender um
  sub-cluster `NCEP*` inteiro (vendor-codes `NA6M4`, `N35X` vistos de relance) fica de lead pra
  próxima rodada.

- **2026-08-26 (6ª busca, mesmo dia) — CORREÇÃO/RETRATAÇÃO: `NCEPNCCM4-1608` não deveria ter sido
  submetido.** O dono aprovou o registro no admin, buscou de novo na bancada e o PN continuou não
  reconhecido — porque `estimated` + specs em branco nunca passa no gate `_USABLE` do engine
  (regra de ouro #2), aprovado ou não. Reação do dono: submeter known_part sem capacidade nenhuma
  não serve pra nada, mesmo identity-only — **nunca mais fazer isso**. Fui checar Tier-2
  (Octopart + Nexar) como autorizado: busquei `NCEPNCCM4-1608`, `NCEPNCCM4` e `NCEPNCCM41608` —
  "No exact matches found" nos três, confirmado via fetch direto (não resumo de busca). LCSC
  também vazio. Sem Tier-1 nem Tier-2, não há capacidade pra confirmar — a submissão original foi
  um erro, fica só como gap (item 7 acima) até aparecer fonte real. Nova regra permanente: known_part
  só se submete com capacidade confirmada (Tier-1 ou, autorizado explicitamente pelo dono, Tier-2);
  sem isso, não submete — registra como gap e segue.

- **2026-08-26 (7ª busca, mesmo dia) — RESOLUÇÃO: capacidade de `NCEPNCCM4-1608` achada em
  Tier-1 oficial, depois de o dono colar resultados de busca (DigiPart/Allelco/Ariat-Tech) que
  não tinham nada de novo (confirmei — só existência/estoque, zero spec) e perguntar sobre uma
  alegação de OUTRA IA ("1608 = 16GB eMMC + 08 convertido de Gb→GB = 1GB RAM"). Fui verificar a
  fonte por trás da alegação, não aceitei de cara: achei o catálogo oficial Longsys
  (`longsys.com/uploads/BP_FORESEE_Embedded-Storage-Product-Catalogue_20230423...pdf`, Tier-1
  direto do fabricante) — a família **eMCP3** lista `FEPNA1608-58A4302`/`-58A4324` com
  **Density="16GB+8Gb"**, mesmo sufixo numérico, mesmo pacote FBGA221/11.5x13mm da nossa peça.
  Confirma a alegação da outra IA no NÚMERO (16GB+8Gb=1GB), mas a JUSTIFICATIVA dela ("Part
  Number Decoder" genérico, sem fonte citável) era hallucination de forma — a fundamentação real
  é essa tabela oficial + o datasheet E-00784 (Part Number Decoder de verdade, confirma a
  gramática [NAND GB][RAM Gb] com outro produto real, FEPRF6432). Geração LPDDR3 segue sendo
  analogia de família (censtry.com, vendor-code irmão `NCEPNA6M4-0808`), não documento direto —
  registrado como o elo mais fraco da cadeia nas notes da submissão. Submissão reescrita com
  `emcp_nand`/`emcp_ram` preenchidos, `confidence: manual`. Lição: quando outra IA (ou resumo de
  busca) alega um número específico, a resposta certa não é aceitar nem rejeitar de cara — é ir
  atrás da fonte real por trás da alegação; às vezes ela existe e é melhor que a IA soube achar,
  só errou em como justificou.

- **2026-08-27 — `NCEMAM6G-08G` (eMMC, raiz legada `NC*`), fill-empty com CONFLITO ensinou uma
  regra nova do comando: reenviar submissão corrigida com `notes`/`source_url` DIFERENTES do que
  já está aprovado trava o registro INTEIRO (nem os campos vazios de verdade são preenchidos) —
  ver `submissions/foresee_ncep_emcp_2026-08-26.yaml` (3ª versão, revertida pra bater com o banco).
  Também descoberto: o gateway de triagem do estoque (`_is_confirmed`) só aceita `confidence` ∈
  {confirmed, manual, distributor} — `estimated` cai na fila mesmo com capacidade real e
  `profitable` calculado certo, e o badge mostra "Indeterminado" (default de `profitable=''`, não
  um veredito real). `NCEMAM6G-08G`: 7 distribuidores DigiPart + pacote TFBGA153 (Besen) + 3
  listagens Alibaba, `manual`. Sem siblings encontrados (só -08G). Ver
  `submissions/foresee_ncemam6g_2026-08-27.yaml`.

- **2026-08-28 — `NCLD3B2M5256M32`, 1ª peça do "lote extra" de variantes com código de die/vendor
  (gap §5 item 6, antecipado 2026-07-16).** PN de bancada real. Sem listagem direta pra esta
  combinação exata (CS=2+M5+256M32) em DigiPart/netComponents/114ic — mas capacidade confirmada por
  DOIS pontos de dado independentes já validados nesta família: (a) mesmo CS("2")+sufixo("256M32")
  do irmão já aprovado `NCLD3B2256M32` (1GB) — o código de die/vendor não afeta capacidade, regra
  vinda do datasheet oficial `NCLD4CXMAXXXM32` e já confirmada 7x nesta família; (b) "M5" é código
  real em circulação nesta sub-família, achado combinado com outro CS/sufixo em
  `NCLD3B1M5128M32` (DigiPart, Green Light Electronics). `confidence=manual`, mesmo padrão já usado
  nesta família pro `NCLD3B2512M32` (capacidade só por fórmula, sem fonte que leia a string exata).

> Inventário de famílias/mapas → **`foresee.yaml`** (Trilha A). known_parts confirmados (proveniência Tier-1 na
> `notes`) → **banco** (Opção 2), via `submit_known_parts`. Cross-marca (comandos/convenção/rentabilidade) → **`CLAUDE.md`**.
