# MICRON.md — Bíblia Técnica e de Negócio
**WhatTheChip — documento vivo de referência**
Criado: 2026-06-19 | Atualizado: 2026-06-19
> Leia antes de tocar em qualquer arquivo relacionado à Micron.
> Em conflito com qualquer outro doc, o **código é a fonte da verdade**
> (`chips/engine.py`, `populate_micron_mcp.py`).
> Atualize este arquivo quando aprender algo duradouro.

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
| **MT29C***  | eMCP LPDDR2 | ⚠️ MÍNIMO | Família cadastrada via `add_chip_families`; só JW464 confirmado |
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

As famílias MT53B, MT53E, MT53D, MT52L **não têm decode posicional** no WhatTheChip.
A capacidade é obtida por:
1. FBGA code → `KnownPart.fbga_code` → `fill_capacity_from_micron_api`
2. Manualmente via `fix_known_parts.py` para chips confirmados

**Regra matemática do PN** (não implementada no engine, mas útil para confirmar manualmente):
```
MT53B512M64D4TX → 512M × 64 bits = 32 Gbit ÷ 8 = 4GB LPDDR4
MT53E1G32D4NQ   → 1G × 32 bits   = 32 Gbit ÷ 8 = 4GB LPDDR4X
MT53D768M32D4BD → 768M × 32 bits = 24 Gbit ÷ 8 = 3GB LPDDR4
```

**MT53B vs MT53E — tensão diferente, INCOMPATÍVEIS:**
- `MT53B` = LPDDR4, VDDQ 1.1V
- `MT53E` = LPDDR4X, VDDQ 0.6V
Não misturar no estoque. Separar fisicamente.

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
interface    = "x16 @ 800MHz (1600MTPS)"
```
→ caixa estoque: **`DDR3+2G`** ✓

---

## 7. Convenção de campos KnownPart — REGRAS CRÍTICAS

> Esta é a causa raiz de todos os bugs de exibição no estoque.
> O gateway do estoque está correto — ele só lê os campos.
> A responsabilidade é popular os campos certos.

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
| `emcp_ram` | (eMCP/uMCP) RAM em GB: `"6GB"` | — |
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
#                 status="enriched", + o campo de capacidade correto
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

5. IA externa (Gemini, GPT)
   → ÚLTIMO recurso; frequentemente erra capacidade e tipo
   → confidence="ai_low" no máximo; sempre verificar depois
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
2. Busca em `KnownPart.fbga_code` (status=enriched)
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

### `confidence="distributor"` ou `"ai_*"` não sobrepõe a gramática
Só `confirmed` e `manual` vencem. Se o banco tem dado errado com `confidence="distributor"`,
o engine usa a gramática (e ignora o banco). Não confie em dado de distribuidor/IA sem confirmar.

### MT53B ≠ MT53E — tensões incompatíveis
MT53B = LPDDR4, 1.1V. MT53E = LPDDR4X, 0.6V. Misturar no estoque danifica hardware.

### Reiniciar servidor após populate --overwrite
O engine usa `lru_cache` para `ChipFamily` e `DecodeMap`. O comando chama
`clear_engine_cache()` no seu processo, mas o servidor web mantém cache antigo.
**Sempre reiniciar após populate --overwrite** (regra de ouro #3 do CLAUDE.md).

### `status="raw"` = invisível para o engine
Chip com dados corretos mas `status="raw"` não é classificado. Promover para `enriched`:
```bash
python manage.py shell -c "
from chips.models import KnownPart
KnownPart.objects.filter(part_number='MT...').update(status='enriched')
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
| 2026-06 | engine ignorava gramática para eMCP com dado de distribuidor (BUG-6) | `engine.py` | Lógica `grammar_wins` corrigida — gramática completa vence `distributor`/`ai_*` |
| 2026-06 | `subtype` não sincronizado após decode do gen map (ex: "LPDDR3" família vs "LPDDR2" decode) | `engine.py` | Adicionado sync `r["subtype"] = _decoded_gen` após `r["interface"] = ""` no bloco eMCP |
| 2026-06-19 | **BUG-8**: MIC_TZZZ_GEN mapeava `'8'→LPDDR2` baseado em API Micron errada; chip é LPDDR3 | `populate_micron_mcp.py` + `fix_known_parts.py` | Corrigido: `'8'→LPDDR3`; fontes: datasheet oficial Micron (MT29TZZZ8D5JKEZB, NXP community) + DigiKey |
| 2026-05 | `populate_micron_mcp.py` comentário dizia pn[8]=NAND | `populate_micron_mcp.py` | Corrigido: pn[8]=RAM, pn[10]=NAND (confirmado por 5 pontos de dados API) |
| 2026-05 | Engine usava decode Samsung para Micron em Path 3 | `engine.py` | Corrigido: Path 3 verifica prefixo antes de usar mapa legado |

---

## 15. Lacunas conhecidas — próximo trabalho

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

**Task #53 (pendente desde 2026-06-19):**
```bash
python manage.py populate_micron_mcp --overwrite
python manage.py fix_known_parts
# reiniciar servidor
# verificar JWA60, JY941, JW464 na UI
```

**MT41J vs MT41K sem decode posicional:**
Chips DDR3/DDR3L são cobertos só via FBGA. Se um chip DDR3 chega sem FBGA legível,
o engine não consegue decodificar pelo PN. Avaliar adicionar `DRAM_PC` decode para essas famílias.

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
