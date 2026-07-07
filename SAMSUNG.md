> ⚠️ **O CONHECIMENTO É YAML** (desde jul/2026). As famílias, decode maps e PNs confirmados da Samsung
> vivem em **`chips/knowledge/samsung.yaml`**, carregado por `load_brands`. Para **adicionar ou corrigir
> um chip, edite o yaml** seguindo o contrato de autoria (via `CLAUDE.md`).
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados do yaml (decode key→valor, inventário de
> famílias, listas de known_parts) nem valores mutáveis (limiares de rentabilidade): esses **vivem só no
> yaml / no código / no admin** (se duplicados aqui, apodrecem). Aqui ficam: **convenções, anatomia do PN,
> armadilhas, o *porquê*, fontes** e ponteiros. **O único `.md` cross-marca é o CLAUDE.md** (hub mantido).

---

# SAMSUNG.md — Bíblia Técnica e de Negócio

> Em conflito, o **código + o yaml são a fonte da verdade** (`chips/engine.py`,
> `chips/knowledge/samsung.yaml`). Regras gerais do WTC: `CLAUDE.md`.

Samsung é o **maior fornecedor** no catálogo WTC — cobre toda a linha: DRAM móvel, eMCP/uMCP, eMMC, UFS,
DDR PC, GDDR, NAND Flash e "catálogo" (NOR/OneNAND/SoC/PMIC/Sensor). O yaml tem **~87 famílias** + os
mapas — a lista viva está no yaml.

> **⚠ Fato arquitetural durável:** a Samsung **define os mapas GLOBAIS `DRAM_PC` e `DRAM_MOBILE`**
> (`brand=None`), compartilhados com outras marcas. Por isso a Samsung é a **1ª** no `deploy_catalog`.
> Alterar esses mapas afeta todas as marcas que os referenciam — mexer com cuidado.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/samsung.yaml   ← gramática (famílias + decode maps, incl. os globais DRAM_PC/DRAM_MOBILE) + known_parts
CLAUDE.md                       ← hub mantido: convenção, comandos, arquitetura + aponta pro contrato de autoria
```

Para adicionar/corrigir: **edite o yaml**, valide no portão (`load_brands --brand samsung`, dry-run), grave
com `--commit`. Os CSVs do Samsung PSG (`import_samsung_psg`) **complementam** o yaml (não são a gramática).
**NÃO tocar sem revisão do usuário:** `chips/engine.py`, `estoque/views.py` (globais), yamls de outras marcas.

### 0.2 Regras de ouro — nunca violar

1. **Claude edita arquivos. O usuário roda os comandos.** Nunca `load_brands --commit`/`import_*`/`migrate` sem confirmação.
2. **`load_brands --brand samsung` (dry-run) é o portão** — valida a convenção, nada gravado. Depois `--commit` (recarrega o cache sozinho, sem restart).
3. **OPÇÃO 1: a GERAÇÃO vai no `chip_type` para todo DRAM discreto** — K4H→`DDR1`, K4T→`DDR2`, K4B→`DDR3`/`DDR3L`,
   K4A→`DDR4`, K4RA/K4RB→`DDR5`, K4S→`SDRAM`, K4R→`RDRAM`, K4J/K4W→`GDDR3`, K4G→`GDDR5`, K4Z→`GDDR6`, LPDDR standalone→a geração —
   sempre espelhada no `subtype`. ❌ NUNCA `chip_type="RAM"`/`"DDR"` genérico. Fonte única: `chips/chip_types.py`.
4. **`subtype` = SÓ a geração/célula** (1–3 palavras). ❌ `"DDR3 PC DRAM 8Gb x8"`, `"LPDDR4X Mobile"`, `"SLC NAND paralela industrial"`,
   densidade, bus width, tensão. (Qualificador vaza pro card; o label é protegido por `canonical_gen`, mas escreva limpo.)
   **Exceção `catalog`** (NOR/OneNAND/MCP/ePoP/SoC/PMIC/SRAM/Sensor/RDRAM): o subtype é DESCRITIVO e preservado.
5. **`interface=""` para LPDDR standalone e eMCP/uMCP.** Nunca a geração de RAM no `interface`. Para DDR/GDDR, `interface` = bus width (`x8`/`x16`/`x4`).
6. **`emcp_ram` = tipo ANTES da capacidade** (`"LPDDR3 1GB"`, nunca `"1GB LPDDR3"`). `emcp_nand` = só GB.
7. **Nunca inverta `val_primary`/`val_secondary` nos decode maps.** Em `SAM_EMCP_CAP`: primary=NAND(GB), secondary=RAM(GB). Em
   `DRAM_PC`/`DRAM_MOBILE`: primary=densidade(Gb/Mb), secondary=MB/die. Siga o padrão das linhas existentes. Nunca escreva `"por die"` no secondary (o engine anexa).
8. **`decode_density_type` e `decode_cap_map` são mutuamente exclusivos** — K4F/K4U/K3U DEVEM ter `decode_density_type: ''`.
9. **Famílias KM com dígito na 3ª posição** (KM1/2/4/5/8, KMV numérico): `decode_gen_pos: null` — senão o engine gera texto Frankenstein ("tipo 'X' — consultar datasheet"). O engine usa o `subtype` fixo da família.
10. **Não confie em distribuidor/IA sem verificar** (Jotrin/WinSource/Shenzhen/Preduo/Puris/Alibaba/LLM confundem Gb/GB, invertem primary/secondary, alucinam). Cruzar com `semiconductor.samsung.com` / datasheet.
11. **Capacidade de eMCP/uMCP (NAND/RAM) só confirma via Octopart (categorização própria, não a descrição do distribuidor dentro da página) ou datasheet — distribuidor é só pista, nunca a fonte final.** Incidente real: distribuidor fez o dono shipar 6GB errado num KM3 — o Octopart já tinha 4GB certo.
12. **Nunca reaproveite o valor de uma chave de posição (ex.: `X6`, `V8`) de uma família em outra.** A mesma chave pode decodificar RAM diferente conforme a família (ver armadilha do "bug X6" em §3). Cada família eMCP/uMCP tem sua própria tabela de RAM — confirme por família, sempre.

### 0.3 Hierarquia de fontes (imutável)

```
1. semiconductor.samsung.com (Tier 1) → busca por PN; o título traz "(X Gb)" ou "(X GB)"
2. Datasheet Samsung (download.semiconductor.samsung.com) → timing, tensão, package
3. Octopart com fonte Samsung → ⚠ inverte Gb/GB; sempre cruzar
4. Distribuidor B2B (SBiT, Puris) — só apoio; nunca rebaixa um confirmed
5. IA externa — ÚLTIMO RECURSO; verificar SEMPRE
```
Nunca fonte primária: Flash64Box, fóruns de reparo, WinSource sem rastreio, catálogos genéricos, IA sem verificação.

---

## 1. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

> **OPÇÃO 1. Fonte única da convenção: `chips/chip_types.py` (código).** Contexto geral: CLAUDE.md.
> DRAM discreta: geração no `chip_type`, espelhada no `subtype`. Gerenciada: `subtype` = geração LPDDR (eMCP/uMCP)
> · célula NAND · vazio (eMMC/UFS). Catálogo (NOR/SoC/PMIC…): subtype descritivo. Unidade: die em `Gb`, pacote em `GB`.

| Tipo | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| DDR1–5 / SDRAM / RDRAM / GDDR3/5/6 | a geração | espelha | bus width (`x8`/`x16`/`x4`) | `density_gbit` (Gb/die) |
| LPDDR1–5X standalone | a geração (`LPDDR4X`…) | espelha | `""` | `capacity` (pacote, bytes) |
| eMMC | `"eMMC"` | `""` | `"eMMC 5.1"` | `capacity` (GB) |
| UFS | `"UFS"` | `""` | `"UFS 3.1"` | `capacity` (GB) |
| eMCP / uMCP | `"eMCP"`/`"uMCP"` | geração RAM (`"LPDDR3"`/`"LPDDR5"`) | `""` | `emcp_nand` (GB) + `emcp_ram` (tipo+GB) |
| Catálogo (NOR/OneNAND/MCP/ePoP/SoC/PMIC/SRAM/Sensor) | o tipo (`"NOR Flash"`…) | **descritivo** (preservado) | — | — |

**Regras absolutas:** `subtype` = só a geração/célula (nunca `"8Gb"`, `"x8"`, `"1.35V"`, `"PC DRAM"`, `"Mobile"`,
`"Graphics"`, `"Multi-Channel"`). `density_gbit` = Gb por die (DDR/GDDR). `capacity` = pacote em bytes (nunca Gbit).
`emcp_ram` = `"LPDDR{n} {cap}GB"` (tipo antes). `tip` = tudo o resto.

**Label da caixa:** DDR `{subtype}+{density_gbit}G` (`DDR3+8G`) · LPDDR `{chip_type}+{cap GB}G` (`LPDDR4X+4G`)
· eMCP/uMCP `EMCP{nand}+{ram}` / `UMCP{nand}+{ram}` · eMMC `EMMC{cap}GB` · UFS `UFS{cap}GB`. ⚠ subtype verboso →
label truncado (`"DDR3 PC DRAM 8Gb x8+8G"`); por isso a regra #4.

---

## 2. Anatomia do PN — como LER um chip Samsung

> As posições e o mapa que cada uma referencia. **Os valores das chaves vivem nos decode maps do yaml**
> (`maps:` em `samsung.yaml`) — aqui fica a ESTRUTURA (durável) + as pegadinhas.

**PC DRAM (`K4[letra]…`):** a **letra da família = geração** — `S`=SDRAM · `H`=DDR1 · `T`=DDR2 · `B`=DDR3/3L ·
`A`=DDR4 · `RA`/`RB`=DDR5 · `R`=RDRAM · `J`/`W`=GDDR3 · `G`=GDDR5 · `Z`=GDDR6. Densidade em `pn[3:5]` → mapa `DRAM_PC`;
bus width em `pn[5:7]` (`08`=x8 · `16`=x16 · `04`/`46`=x4) → `interface`; `pn[7]` = revisão de die; sufixo = velocidade/tensão.
- ⚠ **K4B: o sufixo distingue DDR3 (`BC`, 1.5V) de DDR3L (`BY`/`MY`/`MM`, 1.35V)** — o `chip_type`/`subtype` muda com ele.

**LPDDR mobile:** posição da capacidade varia por família — `pn[3]` (K4P, K3/K3R/K3Q → `DRAM_MOBILE`), `pn[3:5]`
(K4E→`K4E_CAP`, K4F/K4U/K3U→`LPDDR4_CAP`, K4X→`DRAM_PC`), `pn[4]` (K3QF→`K3QF_CAP`), `pn[4:6]` (K3KL/K3LK/K3L→`LPDDR5_CAP`).
- ⚠ **K4F/K4U/K3U** usam `decode_cap_map`, então `decode_density_type: ''` (regra #8).
- ⚠ **`K4EBE304EB` (10 chars) é PN base ARTIFICIAL** — os LPDDR3 reais têm 14 chars (`K4EBE304EB-EGCE`). Não recriar; use UPDATE-ONLY.

**eMMC (`KLM…`):** capacidade em `pn[3]` (→ `SAM_FLASH_CAP`), geração em `pn[6]` (→ `SAM_EMMC_GEN`: `F`=4.5 · `E`=5.0 · `J`=5.1).
**UFS (`KLU…`):** capacidade em `pn[3]` (→ `SAM_FLASH_CAP`); sub-prefixos mais longos têm prioridade (`KLUDG`=UFS2.1, `KLUCG`=UFS2.0, `KLUFG`=UFS3.1).

**eMCP/uMCP (`KM…`):** geração RAM em `pn[2]` (→ `SAM_EMCP_GEN`), capacidade em `pn[3:5]` (→ `SAM_EMCP_CAP`, primary=NAND, secondary=RAM).
- ⚠ **KM numéricos (KM1/2/4/5/8, KMV numérico):** `pn[2]` é o dígito da série, **não** geração → `decode_gen_pos: null` (regra #9).

---

## 3. Armadilhas e Decisões Arquiteturais

- **K4R — bifurcação:** `K4RA`/`K4RB` (priority menor, prefixo mais longo) = **DDR5**; `K4R` = **RDRAM** (legado). O mais longo vence — correto.
- **KMV — bifurcação:** `KMV2…`/`KMV3…` = uMCP LPDDR5X flagship (2022+, priority 30); `KMV`+LETRA = eMCP LPDDR2 legado (2010-13, priority 40). Prefixo mais longo vence.
- **K4Z = GDDR6/GDDR6X** (não LPDDR4X — isso seria SK Hynix). Erro comum em docs antigas; resolvido.
- **`decode_gen_pos: null` nos KM numéricos** (KM1/2/4/5/8, KMV) — pn[2] é dígito de série, não geração. Sem isso → texto Frankenstein no engine (regra #9).
- **`decode_density_type` × `decode_cap_map` são exclusivos** — K4F/K4U/K3U com `decode_density_type: ''` (regra #8).
- **`DRAM_PC`/`DRAM_MOBILE` são GLOBAIS** (`brand=None`) — K3/K3R/K3Q/K4P/K4X Samsung os usam; outras marcas também. Colisão de chave entre marcas afeta todas — monitorar ao expandir.
- **subtype verboso quebra o label** (`"DDR3 PC DRAM 8Gb x8"` → `"…+8G"` truncado). Só a geração (regra #4).
- **interface=`"LPDDR*"` = bug** (erro histórico corrigido em 2026-06 em 61 lugares). Se achar, corrija.
- **Dados externos:** Gb×GB (IA sempre confunde: `32Gb LPDDR4X` = 32÷8 = 4GB); IA inventa cap_keys (sugeriu "KBKB" quando era "BK"); IA troca primary/secondary; distribuidores (Jotrin/Censtry/Wolfchip) erram; `"Galaxy MX6432"` é código interno Samsung (64=eMMC, 32=Gb RAM), **não** nome de celular — limpar `device`.
- **Página individual de SKU pode sumir do site da Samsung — link vira hub genérico.** Parts antigos/legados
  (ex.: LPDDR4 K4F de ~2015-2018) às vezes têm a página específica descontinuada: o link direto
  (`/dram/lpddr/lpddr4/<pn>/`) redireciona pro hub da linha (`/dram/lpddr/lpddr4/`) em vez de mostrar o
  produto. **A confirmação Tier-1 continua válida** — o **título indexado pelo buscador** no momento da
  pesquisa (ex.: `"K4FBE3D4HM-GHCL(32 Gb) | DRAM | Samsung Semiconductor Global"`) já é a fonte (Samsung,
  não distribuidor); o link só deixa de ser **clicável/re-verificável depois**. Sempre que isso acontecer,
  registre no `notes` do known_part que o link pode redirecionar — evita parecer fonte fraca só porque o
  clique não bate mais. Achado em 2026-07-06 pesquisando a família K4F (as 6 páginas oficiais citadas já
  redirecionavam ao hub; mesmo assim os títulos bateram exatamente com a gramática — dono cross-checou via
  Google e confirmou).
- **Mapa de capacidade eMCP NÃO pode ser 100% compartilhado entre famílias — "bug X6" (2026-07):** a mesma chave de posição de 2 chars (ex.: `X6`, `V8`) decodificava RAM **diferente** conforme a família — `X6` = 3GB em KMD/KMG mas 2GB em KM4; `V8` = 6GB em KM2, 4GB em KM5, 8GB em KM8. Achado pesquisando KMDD6001BM (known_part), confirmado cruzando Octopart de 3 famílias. Corrigido separando **NAND** (family-independent, `SAM_EMCP_NAND`) de **RAM** (por família, `SAM_EMCP_RAM_<FAM>`/`SAM_EMCP_CAP_<FAM>` — ver CLAUDE.md, seção "eMCP: RAM decodificada POR-FAMÍLIA"). Famílias já corrigidas: KMD, KMG, KM4, KM5, KM8, KM2/KM2L/KM2P, KMAG, KMAS. Pendente: KMF/KMQ/KMR (LPDDR3 legado) e outras legadas. **Nunca reaproveite o valor de uma chave de outra família só porque a string é igual** — cada família tem sua própria tabela agora.

---

## 4. Rentabilidade — princípio (os valores NÃO ficam aqui)

**Fonte única: `assess_profitability`** (`chips/engine.py`); os limiares vivem no **`ProfitabilityConfig`** (admin,
você edita). ⚠ **É dado mutável** — limiares E quais gerações são rentáveis **mudam com o mercado** — por isso este doc
**NÃO cita valores nem veredictos por família**. Regras duráveis: nunca reimplementar/hardcodar a regra; `capacity`/`density_gbit`
sempre em MB/GB/Gb corretos (nunca Gbit no `capacity`) senão → **INDETERMINADO** = bloqueador; `is_dead_by_generation` manda
geração morta ao descarte mesmo sem banco (a lista vive no código/config). Como o engine lê: `dram_density` (DDR/GDDR) → Gb;
senão `capacity` → GB; eMCP/uMCP → `emcp_nand`/`emcp_ram`.

---

## 5. Gaps e Roadmap (o durável — o resto está no yaml)

- **NAND Flash K9** — 8 famílias sem decode de capacidade; criar `NAND_FLASH_CAP` (`pn[3:5]`) confirmando por datasheet.
- **GDDR5 (K4G) / GDDR6 (K4Z)** — sem decode de capacidade; confirmar chaves `pn[3:5]` em Octopart antes de criar o mapa.
- **NÃO adicionar** chave por padrão numérico sem PN âncora + fonte Tier 1.

---

## 6. Fontes de pesquisa

Tier 1: `semiconductor.samsung.com` (título com "(X Gb)"/"(X GB)"), datasheet Samsung. Tier 2: Octopart — a
**categorização própria** do Octopart (título do produto) é confiável pra capacidade; ⚠ a descrição de
distribuidor **dentro** da página do Octopart não é (inverte Gb/GB, erra).
Tier 3: SBiT, Puris — só apoio/corroboração, nunca a fonte decisiva de capacidade (ver §0.2 regra 11).
**Sempre conferir:** `Xbit ÷ 8 = YB`.

---

## 7. Histórico (o *porquê* — durável)

- **2026-06:** convenção OPÇÃO 1 — a geração passou a viver no `chip_type` (era `"RAM"`/`"DDR"` genérico); interface LPDDR corrigida (`""`); subtypes verbosos limpos.
- **K4Z** reclassificado LPDDR4X→GDDR6; **K4R/KMV** bifurcações resolvidas por prioridade de prefixo.
- **`canonical_gen`** protege o label de subtype verboso (fonte única da convenção no consumo).
- **2026-07:** bug do mapa compartilhado `SAM_EMCP_CAP` (mesma chave de posição → RAM diferente por família — `X6`/`V8`) corrigido com mapas por-família: `SAM_EMCP_NAND` (compartilhado) + `SAM_EMCP_RAM_<FAM>`/`SAM_EMCP_CAP_<FAM>` (por família). Achado pesquisando known_part de KMDD6001BM; corrigido em KMD, KMG, KM4, KM5, KM8, KM2/KM2L/KM2P, KMAG, KMAS — KMF/KMQ/KMR (legado LPDDR3) pendentes. Lição fixada: capacidade de eMCP/uMCP só confirma via Octopart (categorização própria) ou datasheet, nunca distribuidor sozinho (§0.2 regras 11-12).

> Inventário de chaves, famílias e provenância por-PN vivem nos `maps`/`known_parts` do **`samsung.yaml`**.
> Tudo cross-marca (comandos, convenção, rentabilidade, arquitetura, deploy) está no **CLAUDE.md** — o único
> `.md` mantido, e é quem aponta pro contrato de autoria do yaml.

---

> **Regra de trabalho:** Claude edita a `samsung.yaml`. O usuário roda `load_brands` (sempre `--brand samsung`
> dry-run antes do `--commit`). **Pontos mais críticos da Samsung:** ela define os mapas GLOBAIS (cuidado ao mexer)
> e tem as famílias KM numéricas que exigem `decode_gen_pos: null` (regra #9).
