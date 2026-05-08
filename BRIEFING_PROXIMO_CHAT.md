# Briefing — WhatTheChip: Gabaritos Samsung (Backend)

> **Leia este arquivo inteiro antes de qualquer ação.**
> O objetivo desta sessão é popular/corrigir os gabaritos de decodificação de PN (Part Number)
> para os tipos de chip Samsung que ainda não estão completos no backend.
> O usuário vai testar cada família. Depois de aprovado, o frontend em `_content/fab-samsung.html`
> será atualizado (isso fica para outra sessão).

---

## 1. Contexto do Projeto

**WhatTheChip** é um classificador de chips IC para o mercado de reciclagem eletrônica.
Stack: Django 5.2 + PostgreSQL.

O operador na bancada escaneia o código a laser do chip e o sistema retorna:
- Tipo exato (eMCP / DDR4 / eMMC / etc.)
- Capacidade ou densidade
- Interface
- Destino operacional (qual caixa/bancada)

---

## 2. Arquitetura de Decodificação

### 2.1 Modelos-chave

**`chips/models.py`** — ler antes de editar qualquer gabarito.

```
Brand            → fabricante (ex: Samsung, code="SAM")
ChipFamily       → família de chip (prefix, chip_type, decode_*)
DecodeMap        → tabela de lookup (map_name, char_key → val_primary, val_secondary)
Chip             → instância de chip específico (PN + resultado enriquecido)
```

**Campos relevantes de `ChipFamily`:**

| Campo | Uso |
|---|---|
| `prefix` | Prefixo do PN (ex: "KMR", "K4A") |
| `chip_type` | Tipo resumido (ex: "eMCP", "DDR4") |
| `subtype` | Descrição detalhada |
| `interface` | Ex: "eMMC 5.1", "UFS 3.1" |
| `priority` | Menor número = maior prioridade (prefixos mais longos = prioridade maior) |
| `pn_length` | Comprimento esperado do PN (sem sufixo) |
| `is_emcp` | True = fluxo dual (NAND + RAM); False = fluxo simples |
| `decode_gen_pos` | Posição (0-indexed) do char de geração RAM |
| `decode_gen_map` | Nome do mapa DecodeMap para geração RAM |
| `decode_cap_pos` | Posição do início do código de capacidade |
| `decode_cap_len` | Comprimento do código de capacidade (chars) |
| `decode_cap_map` | Nome do mapa DecodeMap para capacidade |
| `decode_density_type` | `"pc"` ou `"mobile"` — ativa lógica de densidade DRAM no engine |
| `tip` | Texto exibido ao operador no decode card |
| `active` | Se False, família é ignorada na classificação |

**`DecodeMap` — estrutura:**
```
map_name   → nome do mapa (ex: "SAM_EMCP_CAP")
char_key   → chave de lookup (1 ou 2 chars)
val_primary   → resultado principal (ex: "64GB" ou "LPDDR4/4X")
val_secondary → resultado secundário (ex: capacidade RAM no eMCP)
```

### 2.2 Lógica do Engine (`chips/engine.py`)

O engine lê o PN e aplica as regras da ChipFamily nesta ordem:
1. Prefixo → família (prioridade mais alta ganha)
2. **Geração/RAM** (`decode_gen_pos` + `decode_gen_map`) → `r["interface"]` ou tipo RAM
3. **Capacidade simples** (`decode_cap_pos` + `decode_cap_map`, `is_emcp=False`) → `r["capacity"]`
4. **eMCP/uMCP dual** (`is_emcp=True`) → `r["emcp_nand"]` + `r["emcp_ram"]`
5. **Densidade DRAM** (`decode_density_type`) → `r["dram_density"]`
   - `"pc"`: lê `pn[3:5]` (2 chars), busca no mapa `DRAM_PC`
   - `"mobile"`: lê `pn[3]` (1 char), busca no mapa `DRAM_MOBILE`
6. Se nada decodificado → Gemini / banco de dados

**Campos do resultado (`r`):**
- `r["chip_type"]`, `r["subtype"]`
- `r["capacity"]` — eMMC/UFS/NOR/BGA SSD
- `r["dram_density"]` — DDR/LPDDR die density
- `r["interface"]` — tecnologia principal
- `r["emcp_nand"]`, `r["emcp_ram"]`, `r["emcp_device"]` — eMCP/uMCP
- `r["tip"]` — instrução operacional
- `r["classification_source"]` — "gramática" / "banco de dados" / "gramática+db"

---

## 3. O Que Já Está Funcionando (NÃO MEXER)

| Família | Prefixos | Status |
|---|---|---|
| eMCP Samsung | KMD, KMF, KMK, KMN, KMQ, KMR, KMS, KMV | ✅ Completo — SAM_EMCP_GEN + SAM_EMCP_CAP (28 códigos) |
| uMCP Samsung | KMG, KML, KMV2, KMV3 | ✅ Completo — mesmo SAM_EMCP_CAP |
| KM genérico | KM | ✅ Fallback priority=90 |
| eMMC | KLM | ✅ SAM_FLASH_CAP (4ª letra: A=16GB…G=1TB) |
| UFS | KLU | ✅ SAM_FLASH_CAP |
| DDR density | K4H/K4T/K4B/K4A/K4R | ✅ decode_density_type="pc" → mapa DRAM_PC (pos 3-4) |
| LPDDR density | K4P/K3Q/K4F/K4U/K3U/K3KL/K3LK | ✅ decode_density_type="mobile" → mapa DRAM_MOBILE (pos 3) |
| NAND Flash | K9F/G/H/K/L/W/X/Z | ✅ famílias ativas, tip funciona (sem decode de cap — complexo) |
| Outros | K4N,K4J,K4G,K4Z,KAT,K5,K8,KUS... | ✅ ativos com tip — ver tarefas abaixo |

---

## 4. Tarefas a Executar (Prioridade Decrescente)

### TAREFA 1 — Bug: `KUS_CAP` não definido ⚠️ (bug real — KUS silently broken)

`prefix="KUS"` tem `decode_cap_map="KUS_CAP"` mas o mapa **não existe** em `populate_samsung.py`.
Resultado atual: decode de capacidade do BGA SSD Samsung falha silenciosamente.

**O que fazer:**
Adicionar o mapa `KUS_CAP` em `populate_samsung.py` (método `_run`, junto aos outros `_bulk_map`).

PN real de BGA SSD Samsung: `KLUS5WEBBF-B0E1` (512GB), `KLUS5WECD-B0E1` (1TB)
Mas KUS usa formato diferente. Verificar na documentação `_content/fab-samsung.html`
seção `id="sam-kus"` para ver os exemplos de PN.

**Formato do mapa:**
```python
kus_cap = [
    # (char_key_2chars, capacidade, "")
    # ler fab-samsung.html seção sam-kus para obter os pares corretos
]
self._bulk_map("KUS_CAP", kus_cap, samsung, dry, overwrite)
```

---

### TAREFA 2 — DRAM_PC: completar mapa de densidade DDR

**Mapa atual** (`DRAM_PC` em `populate_samsung.py`):
```python
dram_pc = [
    ("28",  "256Mb", "32MB por die"),
    ("51",  "512Mb", "64MB por die"),
    ("1G",  "1Gb",   "128MB por die"),
    ("2G",  "2Gb",   "256MB por die"),
    ("4G",  "4Gb",   "512MB por die"),
    ("8G",  "8Gb",   "1GB por die"),
    ("AG",  "16Gb",  "2GB por die"),
    ("AH",  "16Gb",  "2GB por die"),   # DDR5
]
```

**Possíveis lacunas** para verificar nos exemplos de PN do `fab-samsung.html`:
- Olhar seções `sam-ddr1`, `sam-ddr2`, `sam-ddr3`, `sam-ddr4`, `sam-ddr5`
- Cada seção tem exemplos de PN completos — extrair o char 3-4 e mapear

O engine usa `pn[3:5]` para a chave. Ex: `K4B8G0461B-MCRC` → key = "8G" → 8Gb ✅

**Testar:** digitar PNs reais da seção DDR no WhatTheChip e verificar se `dram_density` aparece.

---

### TAREFA 3 — DRAM_MOBILE: completar mapa de densidade LPDDR

**Mapa atual** (`DRAM_MOBILE`):
```python
dram_mob = [
    ("P",  "512Mb", "64MB por die"),
    ("1",  "1Gb",   "128MB por die"),
    ("2",  "2Gb",   "256MB por die"),
    ("4",  "4Gb",   "512MB por die"),
    ("6",  "6Gb",   "768MB por die"),
    ("8",  "8Gb",   "1GB por die"),
    ("G",  "16Gb",  "2GB por die"),
    ("H",  "32Gb",  "4GB por die"),
]
```

O engine usa `pn[3]` (1 char) para mobile. Verificar seções `sam-lpddr4` e `sam-lpddr5`
do `fab-samsung.html` para ver se há PNs com chars não mapeados.

---

### TAREFA 4 — GDDR: melhorar tips com densidade

Atualmente K4N/K4J/K4G/K4Z só têm `tip` básico. Não precisam de decode de PN
(chips gráficos são identificados pelo contexto da placa, não pelo PN isolado).

Se quiser, adicionar `decode_density_type="pc"` em K4G/K4Z — esses reusam o mesmo
padrão posicional do DRAM Samsung (K4G8325ER → pos 3-4 = "83" — provavelmente
não está no mapa, ver se é útil).

**Prioridade baixa** — confirmar com o usuário se há volume de GDDR no lote antes de investir.

---

### TAREFA 5 — ePoP (KAT): avaliar se precisa decode

`prefix="KAT"` é o Package-on-Package Samsung (eMMC + LPDDR empilhados sobre SoC).
É um caso especial: o KAT vai para bancada especializada, não precisa de decode fino.
O tip atual é adequado.

**Avaliar:** se há volume de KAT no lote → se sim, pode receber decode similar ao eMCP
(pois internamente é eMMC + LPDDR). Perguntar ao usuário.

---

### TAREFA 6 — NOR Flash (K5/K8): tip mais completo

Atualmente:
```python
prefix="K5", tip="NOR Flash Samsung. Verificar demanda semanal antes de direcionar.",
prefix="K8", tip="Mask ROM / NOR Flash Samsung. Verificar demanda.",
```

Adicionar informação de capacidade na tip, se o formato do PN permitir.
Exemplos de K5: K5N2G31NCA, K5A2G165UB. Ver `_content/fab-samsung.html` seção `sam-nand`
(NOR é documentado junto ou em seção própria).

---

## 5. Como Rodar e Testar

### Rodar o populate após edições:
```bash
# Direto no diretório do projeto:
python manage.py populate_samsung --dry-run   # ver o que vai mudar
python manage.py populate_samsung --overwrite  # aplicar (atualiza existentes)
```

### Testar decodificação:
Abrir o WhatTheChip no browser e digitar PNs reais da documentação.
Clicar em "📋 Debug" no resultado para ver campos internos (emcp_source, classification_source, etc.)

PNs de referência por família:
- DDR3: `K4B8G0446Q-HYK0` (8Gb), `K4B4G0846B-HCH9` (4Gb)
- DDR4: `K4A8G085WC-BCTD` (8Gb), `K4AAG085WA-BCTD` (16Gb)
- DDR5: `K4R8G085VF-MMTD` (8Gb)
- LPDDR4: `K4F6E304HB-MCCH` (6Gb per die)
- LPDDR5: `K3KL8H80BM-BGCP` (8Gb per die)
- eMMC: `KLMAG1JETD-B041` (16GB), `KLMBG4JETD-B041` (32GB)
- UFS: `KLUEG8U1EM-B0B1` (256GB)
- BGA SSD: ler seção `sam-kus` do fab-samsung.html

---

## 6. Arquivos Principais

```
chips/
  engine.py                   # lógica de decode — ler inteiro antes de editar
  models.py                   # ChipFamily, DecodeMap, Brand, Chip
  management/commands/
    populate_samsung.py       # gabaritos backend — o arquivo principal desta tarefa
    sync_index_page.py        # sincroniza _content/index.html com o banco

_content/
  fab-samsung.html            # documentação frontend (fonte da verdade para gabaritos)
                              # ler as seções sam-* para obter os exemplos de PN

scripts/
  nexar_validate.py           # validador de gabaritos via Nexar API (opcional)
```

---

## 7. Regras e Cautelas

1. **`populate_samsung` é idempotente** — use `--overwrite` para atualizar entradas existentes.
   Sem `--overwrite`, famílias já existentes no banco NÃO são atualizadas.

2. **Prioridade de família** — prefixo mais longo = número menor = ganha.
   - KMV2/KMV3 (4 chars) → `priority=30`
   - KMR/KMQ/KMG etc. (3 chars) → `priority=40`
   - KLM/KLU/KAT/KUS (3 chars) → `priority=50`
   - K4A/K4B/K4R etc. (3 chars) → `priority=100`
   - KM (2 chars, fallback) → `priority=90`

3. **`is_emcp=True` ativa o fluxo dual** (emcp_nand + emcp_ram). Usar `True` APENAS
   para famílias que realmente misturam eMMC/UFS + LPDDR (KM*). Todo o resto usa `False`.

4. **`decode_density_type` vs `decode_cap_map`** — são mecanismos mutuamente exclusivos:
   - `decode_density_type="pc"/"mobile"` → usa mapas `DRAM_PC` / `DRAM_MOBILE` → campo `dram_density`
   - `decode_cap_pos` + `decode_cap_map` → usa mapa customizado → campo `capacity`
   Não colocar os dois na mesma família.

5. **Nunca remover** famílias do populate — só adicionar ou corrigir. Remoção deve ser
   via Django admin (ativar `active=False`).

6. **`grammar_wins`** — lógica em `_result_from_known()` no engine: quando a gramática
   decodifica o PN completamente E não existe registro humano-verificado no banco,
   a gramática prevalece. Para DDR/LPDDR simples isso significa que o campo
   `dram_density` é sempre da gramática, sem conflito com o banco.

---

## 8. O Que NÃO Fazer Nesta Sessão

- ❌ Não editar `_content/fab-samsung.html` — frontend fica para depois do teste
- ❌ Não editar `engine.py` (exceto se descobrir bug crítico que impeça o decode)
- ❌ Não criar novos modelos ou migrações Django
- ❌ Não popular chips de outros fabricantes (Micron, SK Hynix, etc.)
