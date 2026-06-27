# MICRON.md — Bíblia Técnica e de Negócio
**WhatTheChip — documento vivo de referência**
Criado: 2026-06-19 | Atualizado: 2026-06-19
> Leia antes de tocar em qualquer arquivo relacionado à Micron.
> Em conflito com qualquer outro doc, o **código é a fonte da verdade**
> (`chips/engine.py`, `populate_micron_mcp.py`).
> Atualize este arquivo quando aprender algo duradouro.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro e limites de escopo

### 0.1 Arquivos que PODE editar (escopo Micron)

```
chips/management/commands/populate_micron_mcp.py   ← gramática MCP Micron
chips/management/commands/add_chip_families.py      ← famílias standalone Micron
chips/management/commands/fix_known_parts.py        ← entradas com brand_name="Micron"
chips/management/commands/fill_capacity_from_micron_api.py
chips/management/commands/collect_micron_catalog.py
chips/management/commands/analyze_micron_mcp_keys.py
chips/management/commands/import_micron_catalog.py
```

### 0.2 Arquivos que NÃO PODE tocar sem revisão explícita do usuário

```
chips/engine.py              ← motor global — mudança afeta TODAS as marcas
estoque/views.py             ← gateway global — mudança afeta TODAS as marcas
chips/management/commands/populate_samsung.py
chips/management/commands/populate_hynix.py
chips/management/commands/populate_kingston.py
chips/management/commands/populate_rayson.py
chips/management/commands/fix_known_parts.py  ← seções de outras marcas (Samsung, SK Hynix…)
```

> Se precisar de mudança em `engine.py` ou `estoque/views.py`, **proponha ao usuário**
> com justificativa e impacto — nunca edite silenciosamente.

### 0.3 Regras de ouro — nunca violar

1. **Claude edita arquivos. O usuário roda os comandos.** Nunca execute `populate_*`,
   `import_*`, `fix_*`, `migrate` sem confirmação explícita do usuário.

2. **`--dry-run` antes de qualquer comando que escreve no banco.** Sempre.

3. **Reiniciar o servidor após `populate --overwrite`.** O `lru_cache` do engine não
   invalida automaticamente no processo do servidor web.

4. **Não confie em IAs externas para classificação de chips Micron.** IAs generalistas
   erram prefixos de família (ex.: "MT29C = Combo" — ERRADO, é NAND raw), confundem
   Gb/GB e alucinam specs. A fonte é sempre Micron oficial → DigiKey → datasheet.
   Se uma IA externa sugerir uma correção de classificação, **ignore e verifique na fonte**.

5. **Não confie no `part-name` da API Micron FBGA para tipo de RAM.** A API retorna
   strings como `"MLC EMMC/LPDDR2 72G VFBGA"` que podem ser de famílias relacionadas.
   O **prefixo do PN** define o tipo (MT29TZZZ = LPDDR3, MT29PZZZ = LPDDR2). Confirme
   via datasheet oficial ou DigiKey — nunca pelo campo `part-name` da API.

6. **`subtype` = só a geração — sem mais nada.** `"LPDDR3"` sim. `"LPDDR3 + eMMC 5.1"`,
   `"LPDDR3 Mobile"`, `"SLC NAND paralela industrial"` — ERRADO. Todo qualificador além
   da geração vaza para o label da caixa física e trunca o display na esteira.

7. **LPDDR standalone: `chip_type = geração`, não `"RAM"`.** `"LPDDR4"`, `"LPDDR5"` — não o
   genérico `"RAM"` (que é para DDR/GDDR de PC). Afeta o branch do gateway e a UI.

8. **`emcp_ram` = tipo ANTES da capacidade.** `"LPDDR3 1GB"` — nunca `"1GB LPDDR3"`.
   O campo `emcp_nand` é só GB: `"8GB"`, `"16GB"`, sem prefixo de tipo.

9. **Não rebaixe `confirmed`/`manual`.** Ao corrigir um campo, preserve o
   `confidence`. Nunca mude para `"distributor"` ou `"estimated"`.

10. **Só `confidence` ∈ (`confirmed`, `manual`) é autoritativo para o engine.** Um
    registro com `confidence="distributor"` ou `"estimated"` **não** vence a gramática:
    o engine cai no decode posicional. Sempre terminar com `confidence="confirmed"`
    (ou `"manual"`) nos registros corrigidos. *(O campo `status` foi removido em jun/2026;
    a única pergunta é "o confidence é confirmed/manual?".)*

### 0.4 Hierarquia de fontes (imutável)

```
1. Datasheet oficial Micron (PDF) ← fonte definitiva
2. API FBGA Micron: micron.com/fbga?fbga={CODE}
3. DigiKey (produto listado com specs)
4. Octopart / Nexar  ← frequentemente inverte Gb/GB; sempre cruzar
5. Distribuidor B2B rastreável (Puris, Win Source)
6. IA externa (qualquer LLM) ← ÚLTIMO RECURSO; nunca fonte primária; verificar SEMPRE
```

Nunca use como fonte primária: AliExpress, catálogos genéricos, `part-name` da API FBGA,
dados de distribuidor sem rastreabilidade, output de IA sem verificação.

---

## 1. Contexto de negócio

A Micron é o **segundo fabricante de DRAM e NAND do mundo** (depois da Samsung).
Na bancada de reciclagem da eMiner, os chips Micron mais comuns são:

| Tipo | Família | Frequência na bancada | Rentabilidade típica |
|------|---------|-----------------------|----------------------|
| eMCP (eMMC+LPDDR3) | MT29TZZZ | Alta — geração 2014–2018 | Depende da capacidade |
| eMCP/uMCP (eMMC/UFS+LPDDR4) | MT29VZZZ | Alta — geração 2018–2022 | Rentável ≥ 32GB NAND |
| uMCP (UFS+LPDDR5) | MT30AZZZ | Média — geração 2022+ | Rentável |
| LPDDR4/4X standalone | MT53B/E/D | Média | Rentável ≥ 4GB |
| DDR3 standalone | MT41J/K | Média — PCs/servidores usados | Depende do Gbit |
| eMMC standalone | MTFC | Baixa | Depende da capacidade |

**O que o operador vê no chip:** ou o **PN completo** gravado (ex: `MT29VZZZ...`)
ou o **FBGA code de 5 chars** gravado a laser (ex: `D9PRW`, `JWA60`).
O sistema suporta os dois como entrada na busca.

---

## 2. Mapa de famílias — status atual

| Família | Tipo | Decode | Observação |
|---------|------|--------|-----------|
| **MT29VZZZ** | eMCP / uMCP LPDDR4 | ✅ COMPLETO | 13 chaves MIC_MCP_CAP; eMMC 5.1 ou UFS 2.2 (detectado por source_url) |
| **MT30AZZZ** | uMCP LPDDR5 | ✅ COMPLETO | Compartilha MIC_MCP_CAP; UFS 3.1 |
| **MT29TZZZ** | eMCP **LPDDR3** | ⚠️ PARCIAL | 5 chaves Gen A + chaves Gen B compartilhadas; 7 chaves sem dados API. **Toda família é LPDDR3** (BUG-8 corrigido 2026-06-19) |
| **MT29C***  | **NAND Flash paralela industrial** (raw, sem controlador) | ✅ 5 chips confirmados | TSOP1 48-pin — NÃO é MCP. Sem RAM empilhada. Interface paralela x8. Incompat. com programadores eMMC/UFS. Destino: resíduo industrial. JW454/JW464/JW699/JY454/JY464 confirmados. |
| **MTFC****  | eMMC standalone | ✅ FUNCIONAL | Sem decode posicional — cobertura via FBGA/KnownPart |
| **MT53B**   | LPDDR4 standalone | ✅ FUNCIONAL | D9VFC confirmado (4GB); decode manual pelo PN |
| **MT53E**   | LPDDR4X standalone | ✅ FUNCIONAL | Cobertura via FBGA; decode: `[M][bits] ÷ 8 = GB` |
| **MT53D**   | LPDDR4 standalone | ✅ FUNCIONAL | Cobertura via FBGA; decode: `[M][bits] ÷ 8 = GB` |
| **MT52L**   | LPDDR4 SDRAM | ⚠️ MÍNIMO | Família cadastrada; sem decode posicional |
| **MT41J**   | DDR3 standalone | ✅ FUNCIONAL | Cobertura via FBGA; density_gbit preenchido pelo CSV |
| **MT41K**   | DDR3L standalone | ✅ FUNCIONAL | Idem MT41J |
| **MT40A**   | DDR4 standalone | ⚠️ MÍNIMO | Família cadastrada; sem decode posicional sistemático |
| **MT29F**   | Raw NAND Flash | ⚠️ MÍNIMO | Família cadastrada; raramente aparece na bancada eMCP |

**Arquivos que definem as famílias:**
- `chips/management/commands/populate_micron_mcp.py` — MT29VZZZ, MT29TZZZ, MT30AZZZ
- `chips/management/commands/add_chip_families.py` — todas as demais (MTFC, MT53x, MT41x, MT40A…)

---

## 3. DecodeMap MIC_MCP_CAP — inventário completo

**Arquivo:** `populate_micron_mcp.py`
**Posição no PN:** `pn[8:11]` (3 chars)
**Convenção:** `val_primary = NAND (GB)`, `val_secondary = RAM (GB)`

### 3.1 MT29VZZZ / MT30AZZZ (LPDDR4 / LPDDR5) — Gen B

Estrutura: `pn[8]` = código RAM (letra); `pn[9:11]` = código NAND (2 chars)

```
Código RAM:  7=3GB · A=4GB · B=6GB · C=8GB · D=12GB · E=16GB
Código NAND: D8=64GB · D9=128GB · DA=256GB · DB=512GB
```

| Chave | NAND | RAM | Total Gb | Evidência | Status |
|-------|------|-----|---------|-----------|--------|
| 7D8 | 64GB | 3GB | 536 | MT29VZZZ7D8x ✓ | ✅ CONFIRMADO |
| AD8 | 64GB | 4GB | 544 | MT29VZZZAD8x (chip do bug "68GB") ✓ | ✅ CONFIRMADO |
| BD8 | 64GB | 6GB | 560 | MT29VZZZBD81SLSL ✓ | ✅ CONFIRMADO |
| AD9 | 128GB | 4GB | 1056 | MT29VZZZAD9GUFSM ✓ | ✅ CONFIRMADO |
| BD9 | 128GB | 6GB | 1072 | MT29VZZZBD91 / MT30AZZZBD9x ✓ | ✅ CONFIRMADO |
| CD9 | 128GB | 8GB | 1088 | MT29VZZZCD9x / MT30AZZZCD9x ✓ | ✅ CONFIRMADO |
| BDA | 256GB | 6GB | 2096 | MT29VZZZBDA1 ✓ | ✅ CONFIRMADO |
| CDA | 256GB | 8GB | 2112 | MT30AZZZCDA0 ✓ | ✅ CONFIRMADO |
| DDA | 256GB | 12GB | 2144 | MT29VZZZDDA2 / MT30AZZZDDA0 ✓ | ✅ CONFIRMADO |
| EDA | 256GB | 16GB | 2176 | MT30AZZZEDA0 ✓ | ✅ CONFIRMADO |
| CDB | 512GB | 8GB | 4160 | MT30AZZZCDB0 ✓ | ✅ CONFIRMADO |
| DDB | 512GB | 12GB | 4192 | MT30AZZZDDB0 ✓ | ✅ CONFIRMADO |
| EDB | 512GB | 16GB | 4224 | MT30AZZZEDB0 ✓ | ✅ CONFIRMADO |

**Como verificar total:** NAND(GB)×8 + RAM(GB)×8 = total em Gbit. Ex: AD8 = 64×8 + 4×8 = 512+32 = 544 Gb ✓

### 3.2 MT29TZZZ Gen A — TODA família é LPDDR3 ⚠️ BUG-8 corrigido

> **BUG-8 (corrigido 2026-06-19):** A API Micron FBGA retornava `"MLC EMMC/LPDDR2"` para chips
> 8D4 e 8D5. Fontes primárias (datasheet oficial Micron via NXP community + DigiKey) contradizem:
> toda a família MT29**T**ZZZ é **LPDDR3**. A família **LPDDR2** equivalente é MT29**P**ZZZ
> (prefixo diferente, 162-ball vs 221-ball). O populate e o fix_known_parts foram corrigidos.

**Convenção confirmada (Micron FBGA API + datasheet, 2026-05/06):**
```
pn[8]  = código RAM (dígito): '4'→512MB(4Gb) · '5'→2GB(16Gb) · '8'→1GB(8Gb)
pn[9]  = 'D' (constante na maioria dos Gen A)
pn[10] = código NAND (dígito): '4'→4GB(32Gb) · '5'→8GB(64Gb) · '6'→16GB(128Gb)
```

**Regra D-code NAND (confirmada):** D4=4GB · D5=8GB · D6=16GB · D7=32GB · D8=64GB

| Chave | NAND | RAM | Total Gb | Part-name API Micron | Tipo RAM real | Status |
|-------|------|-----|---------|----------------------|---------------|--------|
| 4D4 | 4GB | 512MB | 36 | "EMCP 36G VFBGA" | LPDDR3 (família) | ✅ CONFIRMADO |
| 8D4 | 4GB | 1GB | 40 | "MLC EMMC/LPDDR**2** 40G" ← API errada | **LPDDR3** | ✅ CORRIGIDO |
| 8D5 | 8GB | 1GB | 72 | "MLC EMMC/LPDDR**2** 72G" ← API errada | **LPDDR3** | ✅ CORRIGIDO ← JWA60/JY941 |
| 5D6 | 16GB | 2GB | 144 | "EMCP 144G VFBGA" | LPDDR3 (família) | ✅ CONFIRMADO |
| 8D6 | 16GB | 1GB | 136 | "MLC EMMC/LPDDR3 136G" ← API correta | **LPDDR3** | ✅ CONFIRMADO |

**Fontes primárias para o BUG-8:**
- Datasheet oficial Micron (NXP community PDF): `MT29TZZZ8D5JKEZB` = "MLC e·MMC™ and Mobile **LPDDR3** 221-Ball MCP" — data rate 1866 Mb/s → inequivocamente LPDDR3
- DigiKey: `MT29TZZZ8D5BKFAH-125` = "DRAM - **LPDDR3** Memory IC, 8Gbit (LPDDR3)"
- MT29PZZZ8D5BKFTF = "MLC e·MMC™ and Mobile **LPDDR2** 162-Ball MCP" ← família DIFERENTE

**Chaves sem dados API — aguardam pesquisa:**
`5D7 · 7C7 · 7D6 · 7D7 · 9D5 · 9D6 · AD7`
Não adicionar ao populate sem confirmar via `fill_capacity_from_micron_api` + `analyze_micron_mcp_keys`.

---

## 4. DecodeMap MIC_TZZZ_GEN — tipo RAM (sempre LPDDR3)

**Posição no PN:** `pn[8]` (1 char)
**Propósito:** registrar o tipo RAM da família MT29TZZZ — toda ela LPDDR3.

| Char | Tipo RAM | Evidência | Status |
|------|----------|-----------|--------|
| `8` | **LPDDR3** | Datasheet Micron oficial (MT29TZZZ8D5JKEZB) + DigiKey (MT29TZZZ8D5BKFAH) | ✅ CORRIGIDO (era LPDDR2 — BUG-8) |

> ~~Ambiguidade anteriormente documentada~~ — **resolvida**: `pn[8]='8'` → LPDDR3 para 8D5 E 8D6.
> A API Micron estava errada para 8D5; o datasheet oficial prevalece.

**Política:** só adicionar após verificação via datasheet oficial ou DigiKey (não confiar na API Micron para tipo RAM). Não inferir de outras famílias.

---

## 5. Decode standalone LPDDR — família MT53x

> **Atualizado 2026-06-27.** Estas famílias AGORA decodificam no engine — antes
> eram "sem decode posicional" e dependiam só de FBGA/manual.

A capacidade é decodificada pela FÓRMULA `depth × width ÷ 8` (nomenclatura JEDEC),
via `ChipFamily.decode_density_type='micron'` no engine (`chips/engine.py`, bloco do
`_result_from_family`). Configurado por DADO no `add_chip_families.py` — não é código
por marca, é o mesmo padrão de `'pc'/'mobile'`. Cobre toda a cauda no `classify()`.

**A capacidade TOTAL do dispositivo = profundidade × largura:**
```
MT53E768M32D4DT → 768M × 32 = 24 Gbit ÷ 8 = 3GB
MT53E1G32D4NQ   → 1G × 32   = 32 Gbit ÷ 8 = 4GB
MT53B512M64D4TX → 512M × 64 = 32 Gbit ÷ 8 = 4GB   (D9VFC confirmado Octopart)
MT52L128M32D1EL → 128M × 32 = 4 Gbit  ÷ 8 = 512MB  (LPDDR3!)
```

⚠️ **O sufixo `D{N}` (D2/D4/D8) é configuração de DIES/CANAIS no encapsulamento —
NÃO multiplica a densidade.** `depth × width` já é o dispositivo inteiro. Multiplicar
por dies foi o **bug de dies** (§14, 2026-06-27): o `fill_mt53b_density.py` (REMOVIDO)
calculava `× dies`, inflando ×N — MT53E768M32**D4** virava 12GB (24Gb×4) em vez de 3GB.
Datasheet/DigiKey confirmam: total = `depth × width`, dies só aparece no encapsulamento.

**Nomenclatura oficial Micron (atestada tier-1 — DigiKey/Newark/Micron, 2026-06-27):**

| Prefixo | Geração | Obs |
|---|---|---|
| **MT52**x (MT52L, MT52H) | **LPDDR3** | "52" = LPDDR3 |
| **MT53B / MT53D** | **LPDDR4** | VDDQ 1.1V |
| **MT53E** | **LPDDR4X** | VDDQ 0.6V — INCOMPATÍVEL com MT53B/D, separar no estoque |
| MT62F / MT63G | LPDDR5 / 5X | — |
| MT42L | LPDDR2 | — |

⚠️ **"52" = LPDDR3, "53" = LPDDR4.** `MT52L` é **LPDDR3** (NÃO LPDDR4 — erro comum,
corrigido 2026-06-27 depois que o tier-1 pegou antes do bulk corromper o banco).

**Ferramentas (rodar só com `--dry-run` primeiro; usuário aplica):**
- `fix_micron_capacity --overwrite --family lpddr` → preenche/corrige `capacity` (fórmula sem dies).
- `fix_micron_lpddr_specs` → normaliza os confirmados MT5x: recalcula `capacity`, seta
  `chip_type`/`subtype` canônicos pelo prefixo (LPDDR3/LPDDR4/LPDDR4X) e limpa `density_gbit`/`density_gb`.
  **Guard:** pula eMCP real (`emcp_nand`/`emcp_ram` não-vazios). Mantém `confidence`/`part_number`/`fbga_code`.
- `chip_type`/`subtype` das famílias vêm de `add_chip_families --overwrite` (o engine usa o da família).

**Princípio (causa raiz de tudo):** num registro FBGA `confidence="confirmed"`, o **ouro é só a
IDENTIDADE** (PN ↔ FBGA, que veio da API oficial). `capacity`/`subtype`/`density` são **calculados
localmente** e PODEM estar errados (foi o que aconteceu). Sempre atestar contra **tier-1**
(datasheet/DigiKey/Octopart) — nunca confiar na gramática/suposição como verdade.

---

## 6. Decode standalone DDR — famílias MT41J/K, MT40A

Também **sem decode posicional** — cobertura via FBGA code.
O `import_micron_catalog` preenche `density_gbit` e `density_gb` a partir dos CSVs.
O engine FBGA path lê esses campos para montar `dram_density`.

**Exemplo verificado:** `D9PRW` → `MT41J128M16JT-093:K` → 2Gb DDR3 = 256MB
```
chip_type    = "RAM"
subtype      = "DDR3"
dram_density = "2Gb = 256MB por die [✓]"
capacity     = "256MB"
density_gbit = "2Gb"
density_gb   = "256MB"
interface    = "x16"                      # só o barramento — velocidade vai no tip
tip          = "800MHz (1600MTPS)"        # frequência → tip, não interface
```
→ caixa estoque: **`DDR3+2G`** ✓

---

## 7. Convenção de campos KnownPart — REGRAS CRÍTICAS

> Esta é a causa raiz de todos os bugs de exibição no estoque.
> O gateway do estoque lê os campos e, desde 2026-06-19, **normaliza o `subtype` no
> label** via `canonical_gen` (ver callout na §7.0). Ainda assim, a responsabilidade é
> popular os campos certos — a normalização é só uma rede de segurança no consumo.

### 7.0 Tabela canônica por tipo — valores a preencher

| Tipo Micron | `chip_type` | `subtype` | `interface` | Campo de capacidade |
|---|---|---|---|---|
| eMCP (MT29TZZZ, MT29VZZZ) | `"eMCP"` | geração RAM: `"LPDDR3"` / `"LPDDR4"` | `""` vazio | `emcp_nand` (GB) + `emcp_ram` (tipo + GB) |
| uMCP (MT30AZZZ) | `"uMCP"` | geração RAM: `"LPDDR5"` | `""` vazio | `emcp_nand` (GB) + `emcp_ram` (tipo + GB) |
| eMMC standalone (MTFC) | `"eMMC"` | `""` vazio | `"eMMC 5.1"` / `"eMMC 4.5"` | `capacity` em GB (`"16GB"`) |
| UFS standalone | `"UFS"` | `""` vazio | `"UFS 2.2"` / `"UFS 3.1"` | `capacity` em GB |
| LPDDR4 standalone (MT53B) | `"LPDDR4"` | `"LPDDR4"` | `""` vazio | `capacity` em GB (`"4GB"`) |
| LPDDR4X standalone (MT53E) | `"LPDDR4X"` | `"LPDDR4X"` | `""` vazio | `capacity` em GB |
| LPDDR5 standalone | `"LPDDR5"` | `"LPDDR5"` | `""` vazio | `capacity` em GB |
| DDR3 standalone (MT41J) | `"RAM"` | `"DDR3"` | `"x16"` / `"x8"` | `density_gbit` (Gb por die) |
| DDR3L standalone (MT41K) | `"RAM"` | `"DDR3L"` | `"x16"` / `"x8"` | `density_gbit` (Gb por die) |
| DDR4 standalone (MT40A) | `"RAM"` | `"DDR4"` | `"x16"` / `"x8"` | `density_gbit` (Gb por die) |
| NAND Flash raw (MT29C, MT29F) | `"NAND Flash"` | `"SLC NAND"` / `"MLC NAND"` / `"TLC NAND"` | `"Parallel NAND (8-bit)"` | `capacity` em bytes (`"512MB"`, `"4GB"`) |

> **Regra absoluta do `subtype`:** só a geração (1–3 palavras). `"LPDDR3"` — nunca
> `"LPDDR3 Mobile"`, `"SLC NAND paralela industrial"`, `"DDR3 PC DRAM"`. Qualificadores
> extra vazariam para o label da caixa física — hoje **mitigado no consumo** por
> `canonical_gen` (ver callout abaixo). A regra de escrita continua valendo.

> **Label protegido por `canonical_gen` (2026-06-19) — FONTE ÚNICA da convenção.**
> O label da caixa é montado em `estoque/views.py::_compute_destination`, que passa o
> `subtype` por `chips/conventions.py::canonical_gen()`. Ela reduz qualquer subtype ao
> token canônico por **whitelist** (`"LPDDR4 Mobile"`→`"LPDDR4"`, `"DDR3 SDRAM"`→`"DDR3"`,
> `"SLC NAND paralela industrial"`→`"SLC NAND"`). **Consequência:** subtype verboso **não
> trunca mais a etiqueta** — para todas as marcas, banco e gramática, retroativamente.
>
> **Mas continue escrevendo `subtype` limpo (só a geração) ao popular PNs:** a normalização
> é aplicada só no label; o card de busca ainda mostra o subtype cru; e a função é fail-open
> (token não reconhecido passa intacto). A regra "subtype = só a geração" segue valendo no
> write-time.
>
> **Micron:** subtypes vindos do `import_micron_catalog` (CSV) e do `fix_known_parts`
> passam pela mesma normalização no label — sem ação adicional necessária.

### 7.1 Campos — o que vai e o que não vai

| Campo | O que vai | O que NÃO vai |
|-------|-----------|---------------|
| `chip_type` | `RAM`, `eMMC`, `UFS`, `eMCP`, `uMCP`, `NAND` | specs, densidades, voltagem |
| `subtype` | **só a geração**: `DDR3`, `DDR3L`, `LPDDR2`, `LPDDR3`, `LPDDR4`, `LPDDR4X`, `LPDDR5`, `DDR4` | densidade (`4Gb`), barramento (`x16`), voltagem, `SDRAM` |
| `dram_density` | densidade do **die** em Gb: `"4Gb"`, `"2Gb"` (DDR/GDDR standalone) | bytes; capacidade de pacote |
| `density_gbit` | mesmo que dram_density, campo no DB: `"2Gb"` | — |
| `density_gb` | densidade por die em bytes: `"256MB"` | capacidade total do pacote |
| `capacity` | capacidade total do **pacote** em bytes: `"512MB"`, `"4GB"` | gigabits |
| `interface` | barramento elétrico: `"x16"`, `"x32 @ 1866MHz"`, `"eMMC 5.1"` | a geração RAM (não repetir "DDR3" aqui) |
| `emcp_nand` | (eMCP/uMCP) NAND em GB: `"128GB"` | — |
| `emcp_ram` | (eMCP/uMCP) **tipo + RAM em GB**: `"LPDDR4 6GB"`, `"LPDDR3 1GB"` — o tipo vem ANTES da capacidade | só o número (`"6GB"`) — perde a geração de RAM |
| `tip` | **tudo que não couber acima**: voltagem, organização, avisos, notas de densidade, observações de uso | — |

**Como o estoque monta o rótulo da caixa física:**
- LPDDR (pacote): `{subtype}+{capacity em GB}G` → `LPDDR4+4G`
- DDR (componente): `{subtype}+{dram_density em Gb}G` → `DDR3+2G`
- eMCP: `EMCP{nand_GB}+{ram_GB}` → `EMCP64+4`
- eMMC: `EMMC{cap_GB}GB` → `EMMC64GB`
- UFS: `UFS{cap_GB}GB` → `UFS128GB`

**Regra de ouro:** `subtype` = só a geração. Sem números, sem `x16`, sem voltagem.

---

## 8. Rentabilidade — regras do engine

A rentabilidade é calculada em `chips/engine.py::assess_profitability()`.
Os limiares vivem em `ProfitabilityConfig` (singleton no banco, editável no admin).

**Para chips Micron:**

| Tipo | Regra | Campo usado | Rentável quando |
|------|-------|-------------|-----------------|
| eMCP/uMCP | LPDDR gen + capacidade | `emcp_ram` + `emcp_nand` | LPDDR4+ ≥ limiar de capacidade |
| LPDDR standalone | gen + capacidade do pacote | `capacity` | LPDDR4+ ≥ cfg.lpddr4plus_min_cap_gb |
| LPDDR2/3 | gen abaixo do limiar | `capacity` | Geralmente NÃO RENTÁVEL |
| DDR3 standalone | densidade por die | `dram_density` (Gb) | ≥ cfg.ddr3_min_gbit Gb |
| DDR4+ standalone | densidade por die | `dram_density` (Gb) | ≥ cfg.ddr4plus_min_gbit Gb |
| eMMC standalone | capacidade | `capacity` | Depende do limiar eMMC |

**Sem `dram_density`** (ou sem `capacity` para LPDDR) → `assess_profitability` retorna `INDETERMINADO`.
Isso significa chip não triado — **bloqueador de produção**. Sempre preencher o campo certo.

> **✅ CORRIGIDO 2026-06-19 — NAND Flash raw:** `assess_profitability()` agora tem bloco
> unificado no topo que retorna `NÃO RENTÁVEL` para `chip_type in ("nand flash", "nor flash", "mcp")`.
> `is_dead_by_generation()` também retorna `True` automaticamente — gateway descarta sem confirmar.
> Verificação de pré-requisito: Samsung K9* usa `chip_type="NAND Flash"` ✓; Toshiba TH58 NAND
> está BLOQUEADA no populate_toshiba.py (família não ativa) ✓ — sem risco assimétrico.

---

## 9. Pipeline de trabalho — ordem de execução

### Para nova família MCP (descoberta de chaves)

```bash
# 1. Coletar chips da família (sementes FBGA ou varredura de prefixo)
python manage.py collect_micron_catalog --strategy seed
# ou
python manage.py collect_micron_catalog --strategy prefix --prefix MT29TZZZ

# 2. Buscar part-names oficiais via API FBGA (rate-limited; ~2h para 5.500 chips)
python manage.py fill_capacity_from_micron_api --force --verbose

# 3. Analisar chaves e gerar relatório de CONFIRMADO / REQUER PESQUISA
python manage.py analyze_micron_mcp_keys --prefix MT29TZZZ

# 4. REVISAR O RELATÓRIO MANUALMENTE
# Entradas "CONFIRMADO ✓" → prontas para populate_micron_mcp.py
# Entradas sem API data → NÃO adicionar sem verificação adicional

# 5. Editar populate_micron_mcp.py (seção mcp_cap[] ou tzzz_gen[])

# 6. Propor ao usuário (que roda):
python manage.py populate_micron_mcp --dry-run   # revisar primeiro
python manage.py populate_micron_mcp --overwrite  # usuário roda
python manage.py fix_known_parts                  # usuário roda

# 7. REINICIAR O SERVIDOR (obrigatório — lru_cache não invalida automaticamente)
```

### Para chips DDR standalone (catálogo CSV)

```bash
# Atualizar density_gbit + density_gb + capacity + interface dos registros existentes
python manage.py import_micron_catalog ddr3-sdram_full-catalog.csv --only-update
# Não precisa reiniciar — não altera gramática, só KnownParts
```

### Para chip individual desconhecido (confirmação manual)

```bash
# Adicionar via fix_known_parts.py (editar o arquivo, propor ao usuário rodar)
# ou via admin Django: /admin/chips/knownpart/add/
# Campos mínimos: part_number, brand, chip_type, subtype, confidence="confirmed",
#                 + o campo de capacidade correto
```

### 9.4 Templates `fix_known_parts.py` por tipo Micron

Use estes blocos como modelo. Sempre incluir `fbga_code` quando conhecido.

```python
# eMCP — ex.: MT29TZZZ8D5BKFAH (JWA60, 8GB NAND + LPDDR3 1GB)
{
    "pn": "MT29TZZZ8D5BKFAH",
    "fbga_code": "JWA60",            # FBGA conhecido → link FBGA→PN no engine
    "create": True,
    "create_defaults": {
        "brand_name": "Micron",
        "chip_type":  "eMCP",
        "subtype":    "LPDDR3",      # geração RAM — SOMENTE a geração
        "confidence": "confirmed",
    },
    "fields": {
        "chip_type":  "eMCP",
        "subtype":    "LPDDR3",
        "interface":  "",            # SEMPRE vazio para eMCP/uMCP
        "emcp_nand":  "8GB",         # NAND em GB — sem prefixo de tipo
        "emcp_ram":   "LPDDR3 1GB",  # tipo ANTES da capacidade — SEMPRE
        "confidence": "confirmed",
    },
    "reason": "DigiKey: MT29TZZZ8D5BKFAH-125 LPDDR3 8Gbit(1GB). BUG-8: API dizia LPDDR2 — errada.",
},
```

```python
# LPDDR standalone — ex.: MT53B512M64D4TX (D9VFC, 4GB LPDDR4)
{
    "pn": "MT53B512M64D4TX",
    "fbga_code": "D9VFC",
    "create": True,
    "create_defaults": {
        "brand_name": "Micron",
        "chip_type":  "LPDDR4",     # LPDDR standalone: chip_type = geração — NUNCA "RAM"
        "subtype":    "LPDDR4",
        "confidence": "confirmed",
    },
    "fields": {
        "chip_type":  "LPDDR4",
        "subtype":    "LPDDR4",
        "interface":  "",           # SEMPRE vazio para LPDDR standalone
        "capacity":   "4GB",        # GB do pacote completo (512M × 64bit ÷ 8 = 4GB)
        "confidence": "confirmed",
    },
    "reason": "Math: 512M × 64bit = 32Gbit ÷ 8 = 4GB LPDDR4. Micron FBGA API: D9VFC.",
},
```

```python
# DDR3 standalone — ex.: MT41J128M16JT-093:K (D9PRW, 2Gb = 256MB/die)
{
    "pn": "MT41J128M16JT-093:K",
    "fbga_code": "D9PRW",
    "create": True,
    "create_defaults": {
        "brand_name": "Micron",
        "chip_type":  "RAM",         # DDR standalone: chip_type="RAM" (não "DDR3")
        "subtype":    "DDR3",
        "confidence": "confirmed",
    },
    "fields": {
        "chip_type":    "RAM",
        "subtype":      "DDR3",
        "interface":    "x16",       # bus width do chip
        "capacity":     "256MB",     # por die: density_Gbit ÷ 8 = GB (2Gb ÷ 8 = 256MB)
        "density_gbit": "2Gb",       # por die em Gb — campo para profitability
        "density_gb":   "256MB",
        "confidence":   "confirmed",
    },
    "reason": "Micron FBGA API: D9PRW → MT41J128M16JT-093:K, 2Gb DDR3 SDRAM x16.",
},
```

```python
# NAND Flash raw — ex.: MT29C4G48MAZAPAKD5IT (JW464, SLC 512MB)
{
    "pn": "MT29C4G48MAZAPAKD5IT",
    "fbga_code": "JW464",
    "create": True,
    "create_defaults": {
        "brand_name": "Micron",
        "chip_type":  "NAND Flash",
        "subtype":    "SLC NAND",   # célula — SOMENTE (SLC/MLC/TLC)
        "confidence": "confirmed",
    },
    "fields": {
        "chip_type":  "NAND Flash",
        "subtype":    "SLC NAND",   # NUNCA "SLC NAND paralela industrial" — vaza para label
        "interface":  "Parallel NAND (8-bit)",
        "capacity":   "512MB",      # em bytes — "512MB" (4Gbit ÷ 8 = 512MB)
        "confidence": "confirmed",
    },
    "reason": "Micron FBGA: JW464 = MT29C4G48MAZAPAKD5IT. 4Gbit SLC NAND = 512MB. NÃO é eMCP.",
},
```

```python
# eMMC standalone — ex.: MTFC16GAPALBH (16GB eMMC 5.1)
{
    "pn": "MTFC16GAPALBH",
    "create": True,
    "create_defaults": {
        "brand_name": "Micron",
        "chip_type":  "eMMC",
        "subtype":    "",            # eMMC standalone: subtype VAZIO
        "confidence": "confirmed",
    },
    "fields": {
        "chip_type":  "eMMC",
        "subtype":    "",
        "interface":  "eMMC 5.1",   # padrão/versão da interface
        "capacity":   "16GB",        # total em GB
        "confidence": "confirmed",
    },
    "reason": "Micron catálogo: MTFC16GAPALBH = 16GB eMMC 5.1.",
},
```

```python
# UPDATE-ONLY (sem "create": True) — corrigir campos sem criar novo registro
{
    "pn": "MT29TZZZ8D5BKFAH",
    # SEM "create": True — só atualiza se existir no banco
    "fields": {
        "chip_type":  "eMCP",
        "subtype":    "LPDDR3",
        "emcp_nand":  "8GB",
        "emcp_ram":   "LPDDR3 1GB",
        "confidence": "confirmed",
    },
    "reason": "Defesa-em-profundidade: garante chip_type/emcp_nand se fill_capacity não preencheu.",
},
```

---

## 10. Fontes de dados — hierarquia

```
1. Micron oficial
   ├── API FBGA: https://www.micron.com/support/tools-and-utilities/fbga?fbga={CODE}
   │   → retorna part-name oficial (ex: "MT41J128M16JT-093:K 2Gb DDR3 SDRAM")
   │   → comando: fill_capacity_from_micron_api
   ├── Catálogo CSV: micron.com → Products → Export Full Catalog
   │   → comando: import_micron_catalog <csv>
   └── Datasheet: micron.com → Documents & Downloads
       → fonte final para specs não cobertas por API/CSV

2. Octopart / Nexar
   → script: scripts/nexar_validate.py --validate <PN>
   ⚠️ Frequentemente inverte GB/Gb, confunde subtype — sempre cruzar com Micron oficial

3. Distribuidor B2B rastreável (Puris, Win Source, Veswin, ssfkg)
   → só como apoio; nunca rebaixa um "confirmed" com dado de distribuidor

4. Preduo (preduo.com)
   → atrás de Cloudflare — precisa Playwright local
   → script: scripts/collect_pns.py --brand Micron
   → NÃO roda no Render (produção sem Playwright)

5. IA externa (qualquer LLM)
   → ÚLTIMO recurso; frequentemente erra capacidade e tipo
   → nunca fonte primária; sempre verificar na fonte oficial antes de gravar
```

**Nota sobre unidades na API Micron:**
- Part-name MCP: `"72G VFBGA"` = 72 **Gbit** (não GB!)
- Part-name DDR: `"2Gb DDR3 SDRAM"` = 2 Gigabit = 256MB
- CSV COMPONENT DENSITY para DDR: `"2Gb"` = por die em Gbit
- CSV COMPONENT DENSITY para eMCP/uMCP: total NAND+RAM em Gbit (NÃO usar diretamente)

---

## 11. FBGA codes Micron

**Formato:** 5 chars, começa com letra maiúscula, alfanumérico (`^[A-Z][A-Z0-9]{4}$`)
**Exemplos:** `D9PRW`, `D9VFC`, `JWA60`, `JY941`, `JW464`

**Prefixos comuns Micron:**
- `D9XXX` — DRAM DDR3/DDR4 standalone (Micron padrão)
- `JWxxx` / `JYxxx` — eMCP (MT29TZZZ/MT29VZZZ)
- `NWxxx` — uMCP (MT30AZZZ)

**Como o engine trata:**
1. Detecta padrão FBGA (`^[A-Z][A-Z0-9]{4}$`)
2. Busca em `KnownPart.fbga_code`
3. Se tem família → `_result_from_known(PN, kp, family)` — decode completo
4. Se sem família → dict manual com `density_gbit`/`density_gb` do KnownPart
5. Se desconhecido → enfileira em `UnknownChip` para enriquecimento noturno

**Para consultar manualmente:**
```bash
python manage.py shell -c "
from chips.models import KnownPart
kp = KnownPart.objects.filter(fbga_code='D9PRW').first()
print(kp.part_number, kp.chip_type, kp.subtype, kp.density_gbit, kp.capacity)
"
```

---

## 12. Armadilhas e pegadinhas

### Tabela de consulta rápida

| Armadilha | Detalhe |
|-----------|---------|
| **`"G"` no PN Micron = Gbit, não GB** | `MTFC8G` = 8Gbit = 1GB. `"72G VFBGA"` = 72Gbit total. Sempre ÷8. Para DDR standalone → vai em `density_gbit`. Para LPDDR standalone → vai em `capacity`. Para MCP: **NÃO** usar como `capacity` — usar `emcp_nand`/`emcp_ram` (o `"G"` do MCP é soma NAND+RAM, não NAND sozinho). |
| **`part-name` da API FBGA = fonte fraca para tipo de RAM** | `"LPDDR2"` na API pode ser LPDDR3 (BUG-8). O prefixo do PN define o tipo. |
| **eMCP/uMCP: `capacity` deixar vazio** | Para MCP, `capacity=""`. Usar `emcp_nand` + `emcp_ram`. Preencher `capacity` gera bug `"68GB"`. |
| **COMPONENT DENSITY do CSV = total NAND+RAM** | Para MCP, o CSV soma tudo em Gbit. Não usar como `capacity`. |
| **Só `confidence` confirmed/manual é autoritativo** | Dados certos com `confidence="distributor"`/`"estimated"` perdem para a gramática. Promover para `confirmed`/`manual` para o banco vencer. (Não há mais campo `status`.) |
| **`lru_cache` após `populate --overwrite`** | Engine continua servindo gramática antiga até reiniciar o servidor. |
| **FBGA com duplicatas** | Engine prefere registro com `chip_type` preenchido (`.exclude(chip_type="").first()`). |
| **`"por die"` duplicado no `val_secondary`** | Não colocar `"por die"` — engine já acrescenta. Resultado: `"por die por die"`. |
| **MT29C ≠ eMCP** | `"C"` no prefixo = configuração de barramento paralelo, **não** "Combo". NAND raw sem RAM. |
| **IA externa inventando chaves** | IAs sugerem chaves com 4 chars quando são 2 chars, trocam LPDDR2/3, invertem primary/secondary. Verificar SEMPRE na fonte. |

---

### "G" no PN eMMC Micron = Gbit, não GB
`MTFC8G` = 8 Gbit = **1GB**. `MTFC64G` = 64 Gbit = 8GB.
O `import_micron_catalog` já trata isso: para eMCP/uMCP, `capacity` fica vazio (engine decodifica).
Se construir manualmente: converter sempre.

### COMPONENT DENSITY do CSV para eMCP/uMCP = total NAND+RAM (não usar para capacity)
Ex: `AD8` → CSV mostra 544Gb. **Não colocar 544Gb como capacity do eMCP.**
Deixar `capacity=""` para eMCP/uMCP; o engine decodifica via `MIC_MCP_CAP`.
Burlar isso gera o bug clássico `"68GB"` em vez de `"64GB NAND + 4GB RAM"`.

### pn[8] em MT29TZZZ Gen A = RAM (não NAND)
O comentário antigo dizia `pn[8]=NAND`. **ERRADO** — comprovado por 5 pontos de dados.
`pn[8]=RAM`, `pn[10]=NAND`. Não reverter esse entendimento.

### COMPONENT DENSITY do CSV para eMCP/uMCP não distingue NAND de RAM
A Micron não separa NAND e RAM no CSV de eMCP/uMCP. Use a API FBGA ou o decode do MIC_MCP_CAP.

### `confidence="distributor"` ou `"estimated"` não sobrepõe a gramática
Só `confirmed` e `manual` vencem. Se o banco tem dado errado com `confidence="distributor"`,
o engine usa a gramática (e ignora o banco). Não confie em dado de distribuidor/IA sem confirmar.

### MT53B ≠ MT53E — tensões incompatíveis
MT53B = LPDDR4, 1.1V. MT53E = LPDDR4X, 0.6V. Misturar no estoque danifica hardware.

### Reiniciar servidor após populate --overwrite
O engine usa `lru_cache` para `ChipFamily` e `DecodeMap`. O comando chama
`clear_engine_cache()` no seu processo, mas o servidor web mantém cache antigo.
**Sempre reiniciar após populate --overwrite** (regra de ouro #3 do CLAUDE.md).

### Só `confidence` ∈ (confirmed, manual) torna o registro autoritativo
Chip com dados corretos mas `confidence="distributor"`/`"estimated"` não vence a
gramática — o engine cai no decode posicional. Promover para `confirmed`/`manual`
(o campo `status` foi removido em jun/2026):
```bash
python manage.py shell -c "
from chips.models import KnownPart
KnownPart.objects.filter(part_number='MT...').update(confidence='confirmed')
"
```

### eMMC vs uMCP — detectado por source_url, não por chip_type
Para chips MT29VZZZ, a distinção eMMC-based (eMCP) vs UFS-based (uMCP) vem do
`source_url` retornado pela API FBGA: `emmc-based-mcp` vs `ufs-based-mcp`.
O `fix_micron_mcp_classification.py` aplica essa correção em lote.

### Limite da API FBGA da Micron
A API tem rate limiting. Com `--force --verbose` no `fill_capacity_from_micron_api`,
esperar ~2 horas para percorrer 5.500 chips. Não rodar em loop apertado.

---

## 13. Como verificar se um chip está correto

```bash
# Busca via PN completo
python manage.py shell -c "
from chips.engine import classify
import json
r = classify('MT29VZZZAD8GQFSL')
print(json.dumps(r, indent=2, ensure_ascii=False))
"
# Esperado: chip_type='eMCP', emcp_nand='eMMC 5.1 64GB', emcp_ram='LPDDR4 4GB',
#           confidence='confirmed', profitable='RENTÁVEL'

# Busca via FBGA
python manage.py shell -c "
from chips.engine import classify
import json
r = classify('D9PRW')
print(json.dumps(r, indent=2, ensure_ascii=False))
"
# Esperado: chip_type='RAM', subtype='DDR3', dram_density='2Gb = 256MB por die [✓]'

# Debug na UI: /chips/decode/?pn=<PN>
# No estoque: botão "Debug" → JSON completo + fonte de cada campo

# Checklist de chip correto:
# [ ] known=true
# [ ] confidence="confirmed" ou "manual"
# [ ] chip_type e subtype corretos (subtype = só a geração)
# [ ] Campo de capacidade preenchido (emcp_nand+emcp_ram para MCP, dram_density para DDR, capacity para LPDDR/eMMC)
# [ ] profitable != "INDETERMINADO"
# [ ] dram_density = "XGb = YMB por die [✓]" (não None, não vazio) — para DDR standalone
```

---

## 14. Histórico de bugs corrigidos

| Data | Bug | Arquivo | Correção |
|------|-----|---------|---------|
| 2026-06-19 | CAIXA FÍSICA mostrava `interface` em vez de `subtype` para DDR | `estoque/views.py:195` | Invertida prioridade: `subtype` before `interface` em `_compute_destination` |
| 2026-06-19 | `dram_density` sempre null no path FBGA | `engine.py:~1600,1629` | FBGA paths agora leem `density_gbit`/`density_gb` do KnownPart |
| 2026-06-19 | `density_gb` nunca gravado pelo importador | `import_micron_catalog.py` | Adicionado `density_gb = _density_to_capacity(density)` no info dict, `_maybe_update` e `create` |
| 2026-06 | eMMC classificado como uMCP e vice-versa (BUG-3) | `fix_micron_mcp_classification.py` | Corrigido via source_url da API FBGA |
| 2026-06 | engine ignorava gramática para eMCP com dado de distribuidor (BUG-6) | `engine.py` | Lógica `grammar_wins` corrigida — gramática completa vence `distributor`/`estimated` |
| 2026-06 | `subtype` não sincronizado após decode do gen map (ex: "LPDDR3" família vs "LPDDR2" decode) | `engine.py` | Adicionado sync `r["subtype"] = _decoded_gen` após `r["interface"] = ""` no bloco eMCP |
| 2026-06-19 | **BUG-8**: MIC_TZZZ_GEN mapeava `'8'→LPDDR2` baseado em API Micron errada; chip é LPDDR3 | `populate_micron_mcp.py` + `fix_known_parts.py` | Corrigido: `'8'→LPDDR3`; fontes: datasheet oficial Micron (MT29TZZZ8D5JKEZB, NXP community) + DigiKey |
| 2026-05 | `populate_micron_mcp.py` comentário dizia pn[8]=NAND | `populate_micron_mcp.py` | Corrigido: pn[8]=RAM, pn[10]=NAND (confirmado por 5 pontos de dados API) |
| 2026-05 | Engine usava decode Samsung para Micron em Path 3 | `engine.py` | Corrigido: Path 3 verifica prefixo antes de usar mapa legado |
| 2026-06-19 | CAIXA FÍSICA NAND mostrava só "NAND" (sem subtype nem capacidade) | `estoque/views.py` | Branch NAND agora usa `subtype` + `_format_cap()` (lê MB e GB). Corrige: "NAND" → "SLC NAND 512MB" |
| 2026-06-19 | Engine FBGA com duplicatas pegava registro antigo com `chip_type=""` | `engine.py` (`MultipleObjectsReturned`) | Handler agora faz `.exclude(chip_type="").first() or .first()` — prefere registros com tipo preenchido |
| 2026-06-19 | MT53B512M64D4TX tinha `chip_type="RAM"` em vez de `"LPDDR4"` | `fix_known_parts.py` | Corrigido: LPDDR standalone deve ter `chip_type=geração`, não "RAM" genérico |
| 2026-06-19 | MT29TZZZ8D5BKFAH sem `chip_type` e `emcp_nand` no bloco `fields` | `fix_known_parts.py` | Adicionados `chip_type="eMCP"` e `emcp_nand="8GB"` como defesa-em-profundidade |
| 2026-06-19 | **MICRON.md §2 dizia MT29C = "eMCP LPDDR2"** | `MICRON.md` | ERRADO: MT29C é NAND Flash paralela industrial (TSOP1 48-pin, raw, sem RAM). Corrigido. |
| 2026-06-27 | **Bug de dies — capacidade Micron LPDDR inflada ×N** | `scripts/fill_mt53b_density.py` (REMOVIDO) + dados | `fill_mt53b_density`/`fill_capacity_from_micron_api` calculavam `depth × width × **dies** ÷ 8` (D2→2×, D4→4×, D8→8×). Ex.: MT53E768M32D4 (D9WRQ) → 12GB em vez de 3GB; MT53E2G64D8 → 128GB em vez de 16GB. **Correto: `depth × width ÷ 8` (sem dies).** Fix: `decode_density_type='micron'` no engine + `fix_micron_lpddr_specs` para os dados gravados. Atestado tier-1 (6 PNs). Varredura dos 5507 PNs confirmou o bug confinado a MT53x. |
| 2026-06-27 | **MT52L classificado como LPDDR4 (é LPDDR3)** | `add_chip_families.py` + `fix_micron_lpddr_specs.py` | Nomenclatura oficial Micron: **"52"=LPDDR3, "53"=LPDDR4**. MT52L é LPDDR3. PREFIX_GEN e família corrigidos LPDDR4→LPDDR3. Tier-1 (DigiKey/Newark: MT52L256M32 = 8Gbit LPDDR3) pegou antes do bulk corromper ~151 registros — lição: atestar geração em tier-1, não assumir. |

### Chips Micron confirmados individualmente

| FBGA | PN | Tipo | Capacidade | Fonte | Observação |
|------|----|------|-----------|-------|-----------|
| `JW464` | MT29C4G48MAZAPAKD5IT | NAND Flash SLC | 512MB | Micron FBGA API | 4Gbit SLC, x8, industrial |
| `JW454` | MT29C4G88MAZAPAKD-5IT | NAND Flash SLC | 512MB | Micron FBGA API | variante x8 wide |
| `JW699` | MT29C4G96MAZAPAKC-5WT | NAND Flash SLC | 512MB | Micron FBGA API | industrial temp |
| `JY464` | MT29C2G48MAZAPAKD5IT | NAND Flash SLC | 256MB | Micron FBGA API | 2Gbit SLC |
| `JY454` | MT29C2G88MAZAPAKD-5IT | NAND Flash SLC | 256MB | Micron FBGA API | variante |
| `JWA60` | MT29TZZZ8D5BKFAH | eMCP | 8GB NAND + LPDDR3 1GB | DigiKey | BUG-8: API dizia LPDDR2 — é LPDDR3 |
| `JY941` | MT29TZZZ8D5BKFAH variant | eMCP | 8GB NAND + LPDDR3 1GB | DigiKey | mesmo decode que JWA60 |
| `D9VFC` | MT53B512M64D4TX | LPDDR4 | 4GB | Octopart | 512M×64bit=32Gbit÷8=4GB; chip_type="LPDDR4" |
| `D9PRW` | MT41J128M16JT-093:K | DDR3 | 2Gb por die = 256MB | Micron FBGA API | x16, 800MHz |

---

## 15. Lacunas conhecidas — próximo trabalho

### Status de completude por categoria

```
CATEGORIA                        COMPLETUDE    PRÓXIMO PASSO
──────────────────────────────────────────────────────────────────────
MT29VZZZ (eMCP/uMCP LPDDR4)     ██████████100%   completo (13 chaves confirmadas)
MT30AZZZ (uMCP LPDDR5)          ██████████100%   completo (compartilha MIC_MCP_CAP)
MT29TZZZ (eMCP LPDDR3)          ████████░░  80%   7 chaves sem dados API
MT29C (NAND raw paralela)        █████████░  90%   5 FBGA confirmados; mais chegam
MTFC (eMMC standalone)           █████░░░░░  50%   só via FBGA; sem decode posicional
MT53B/E/D (LPDDR4/4X standalone) █████████░  90%   decode no engine ✅ (micron); falta 251 PNs -DC
MT41J/K (DDR3/3L standalone)     ███████░░░  70%   FBGA/CSV; fórmula funciona, falta flag micron
MT40A (DDR4 standalone)          ███████░░░  70%   capacity OK no banco; falta flag micron no engine
MT29F (NAND Flash raw)           ██░░░░░░░░  20%   família cadastrada; raramente aparece
MT52L (LPDDR3 SDRAM)             █████████░  90%   decode no engine ✅; LPDDR3 (corrigido 2026-06-27)
MT62F (LPDDR5 standalone)        ████████░░  80%   capacity OK (atestado, sem bug); falta flag micron
MT63G (LPDDR5 1P3G48)            ███░░░░░░░  30%   formato abreviado; decode próprio pendente
```

### Backlog do bug de dies (2026-06-27) — o que falta preencher na Micron

> Contexto pra quem pegar: o bug de dies está **encerrado** (engine + dados, MT53x/MT52L,
> atestado tier-1). Resta a cauda de COMPLETUDE/decode abaixo. Filosofia: **tier-1 manda**
> (datasheet/DigiKey/Octopart), `depth × width ÷ 8` sem dies, e "confirmed" de FBGA é só a
> identidade — atestar as specs derivadas.

1. **251 PNs MT53E/MT52L em formato abreviado `-DC`** (ex.: `MT53E1BAD4DB-DC`, `MT52L2DALR-DC`,
   `MT53E4DANQ-DC`). NÃO têm o bloco `[depth][M|G][width]` → `decode_density_type='micron'` não
   decodifica (o `fix_micron_lpddr_specs` os pula, ver "sem decode"). **Tarefa:** mapear o código
   abreviado (`1B`/`2D`/`4D`/`8D` = densidade?) OU resolver via FBGA/datasheet. Esses são a maior
   lacuna de completude do MT53x.
2. **Estender `decode_density_type='micron'` às DDR/LPDDR5** (a fórmula `depth × width` já vale —
   atestada: MT40A1G16=2GB, MT41K128M16=256MB, MT62F1280M64=10GB, MT60B1536M16=3GB). Hoje só MT5x
   LPDDR4/4X têm o flag. **Tarefa:** setar `decode_density_type='micron'` em MT40A, MT41J/K, MT47H,
   MT42L, MT62F, MT63xx, MT60B no `add_chip_families` (1 linha cada). Confirmar geração tier-1 de
   cada prefixo antes (MT40A=DDR4, MT41=DDR3, MT47H=DDR2, MT60B=DDR5, MT62/63=LPDDR5).
3. **Vazios de completude (capacidade FALTANDO, não errada):** MT47H (~42 DDR2, 64MB), MT63G
   (~60, formato `1P3G48`), e ~137 eMCP (MT29V/T/P/MT30A) decodáveis. Para os eMCP, rodar
   `fix_micron_capacity --overwrite --family emcp` preenche.
4. **Auditoria de correção do eMCP** (não foi atestado tier-1 ainda — só capacidade DRAM foi):
   comparar `capacity`/`emcp_nand`/`emcp_ram` gravados vs decode `MIC_MCP_CAP` para MT29V/T/P/MT30A;
   os legados MT29C/MT29G (sem DecodeMap) precisam datasheet caso-a-caso.
5. **Famílias tiny fora do PREFIX_GEN** do `fix_micron_lpddr_specs`: MT52H (LPDDR3), MT53T —
   verificar geração tier-1 e incluir se houver volume.

### Alta prioridade

**MT29TZZZ — 7 chaves sem dados da API:**
`5D7 · 7C7 · 7D6 · 7D7 · 9D5 · 9D6 · AD7`
Chips no banco sem `[Micron FBGA API]` nas notes. Pipeline:
```bash
python manage.py fill_capacity_from_micron_api --force
python manage.py analyze_micron_mcp_keys --prefix MT29TZZZ
```
Só adicionar ao populate após confirmação.

**~~MIC_TZZZ_GEN — ambiguidade `'8'` para 8D6~~:** ✅ RESOLVIDA (BUG-8)
Toda família MT29TZZZ é LPDDR3. O mapa agora mapeia `'8'→LPDDR3` uniformemente.
Não há mais ambiguidade entre 8D5 e 8D6.

**4D4 e 5D6 — confirmar tipo via datasheet:**
Part-names `"EMCP 36G VFBGA"` e `"EMCP 144G VFBGA"` não especificam o tipo na API Micron.
Pela lógica de família (MT29TZZZ = LPDDR3 uniforme), assume-se LPDDR3 — mas confirmar
com datasheet se possível, especialmente para o chip 4D4 (512MB RAM, raro).

### Média prioridade

**228 chips MCP sem decode entry** (relatório do `fill_capacity_from_micron_api`):
Têm part-name nas notes mas nenhuma entrada MIC_MCP_CAP correspondente.
Rodar `analyze_micron_mcp_keys` para identificar as chaves faltantes.

**Task #53 — comandos pendentes de execução:**
```bash
python manage.py populate_micron_mcp --overwrite   # BUG-8 LPDDR3
python manage.py populate_samsung --overwrite       # subtype verbose
python manage.py fix_known_parts                    # MT29C subtype + MT53B chip_type + MT29TZZZ8D5 emcp_nand
# reiniciar servidor
# verificar: JW464 → "SLC NAND 512MB" | JWA60/JY941 → EMCP8+1 LPDDR3 | D9VFC → LPDDR4+4G
```

**MT29C — convenção a manter:**
`chip_type = "NAND Flash"`, `subtype = "SLC NAND"` (ou MLC/TLC), `capacity = bytes`.
Não é eMCP — não tem RAM. Qualquer catálogo que diga "LPDDR2 Combo" para MT29C está errado.
A letra "C" no prefixo é configuração de barramento paralelo, NÃO "Combo".

**MT41J vs MT41K sem decode posicional:**
Chips DDR3/DDR3L são cobertos só via FBGA. Se um chip DDR3 chega sem FBGA legível,
o engine não consegue decodificar pelo PN. Avaliar adicionar `DRAM_PC` decode para essas famílias.

**~~NAND Flash raw → `NÃO RENTÁVEL`~~:** ✅ CORRIGIDO 2026-06-19 em `chips/engine.py`.
Bloco unificado no topo de `assess_profitability()` cobre `("nand flash", "nor flash", "mcp")`.
`is_dead_by_generation()` retorna `True` automaticamente — gateway descarta na esteira sem banco.

### Baixa prioridade

**MT40A, MT52L** — famílias cadastradas mas sem cobertura real. Aguardam chips físicos
chegarem na bancada para justificar investimento em decode.

---

## 16. Arquivos-chave Micron

```
chips/management/commands/
  populate_micron_mcp.py          ← GRAMÁTICA: ChipFamilies + DecodeMap MIC_MCP_CAP/MIC_TZZZ_GEN
                                     Editar para adicionar novas chaves confirmadas
  add_chip_families.py            ← famílias standalone (MTFC, MT53x, MT41x, MT40A, MT29F…)
  import_micron_catalog.py        ← importa CSVs Micron; preenche density_gbit/density_gb/capacity/interface
  fill_capacity_from_micron_api.py← consulta API FBGA; grava part-name em notes com tag [Micron FBGA API]
  collect_micron_catalog.py       ← enumera famílias por sementes FBGA ou varredura de prefixo
  analyze_micron_mcp_keys.py      ← analisa chaves descobertas; propõe split NAND/RAM; relatório CONFIRMADO/REQUER PESQUISA
  fix_micron_mcp_classification.py← corrige eMCP vs uMCP via source_url da API
  enrich_micron_fbga.py           ← enriquece chips com dados FBGA
  fix_micron_capacity.py          ← preenche capacity para chips sem decode (legado)

scripts/ (local-only — não rodam no Render)
  nexar_validate.py               ← consulta Nexar/Octopart
  collect_pns.py --brand Micron   ← coleta PNs do Preduo (requer Playwright)

Referências cruzadas:
  CLAUDE.md §2         ← regras de ouro (não violar)
  CLAUDE.md §4         ← arquitetura do engine
  CLAUDE.md §5         ← pipeline de comandos completo do projeto
  HANDOFF.md (BUG-1..6)← histórico de decisões arquiteturais
  docs/CONVENCAO_CAMPOS_ESTOQUE.md ← convenção de campos por tipo de chip (projeto inteiro)
  docs/CONTRATO_RENTABILIDADE_GATEWAY.md ← regras de rentabilidade completas
```

---

> **Regra de trabalho:** Claude edita arquivos. O usuário roda os comandos.
> Nunca execute `populate_*`, `import_*`, `fix_*`, `migrate` sem o usuário confirmar.
> Sempre `--dry-run` antes de qualquer comando destrutivo.
