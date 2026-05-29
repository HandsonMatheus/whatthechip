# Plano de Enriquecimento — Capacity dos 441 Registros Micron Incompletos

> Situação após imports de Maio 2026  
> Banco: 2407 KnownParts Micron · 441 sem `capacity` (~18%)

---

## Visão Geral por Família

| Família       | Sem capacity | Estratégia principal       | Confiança |
|---------------|-------------|----------------------------|-----------|
| LPDDR4X       | ~142        | Reimportar com CSV correto | Alta      |
| LPDDR3        | 52          | PN decoder                 | Alta      |
| DDR2          | 42          | PN decoder + scraping      | Média     |
| LPDDR5 DC     | 82          | PN decoder                 | Alta      |
| LPDDR2        | 28          | PN decoder + scraping      | Média     |
| LPDDR4 DC     | 19          | PN decoder                 | Alta      |
| eMCP          | 29          | Scraping página do produto | Média     |
| UFS           | 7           | Já no CSV (gap pontual)    | Alta      |
| uMCP          | 11          | Scraping página do produto | Média     |
| MT53B LPDDR4  | ~24         | PN decoder (script pronto) | Alta      |

---

## Estratégia 1 — PN Decoder (confiança alta, sem scraping)

Aplicável a qualquer família RAM Micron onde o part number codifica a organização
de memória no próprio PN.

### Convenção Micron LPDDR/DDR

```
MT{family}{speed}{rows}M{bus}D{dies}{suffix}
  └─ rows em milhões (base-2)
  └─ bus em bits
  └─ dies = número de dies empilhados

density_gbit = rows × bus × dies / 1024
capacity_gb  = density_gbit / 8
```

**Exemplos verificados:**

| PN                   | rows | bus | dies | density_gbit | capacity |
|----------------------|------|-----|------|--------------|----------|
| MT53B128M32D1DT      | 128  | 32  | 1    | 4            | 512MB    |
| MT53B256M32D1NP      | 256  | 32  | 1    | 8            | 1GB      |
| MT53B512M32D2NP      | 512  | 32  | 2    | 32           | 4GB      |
| MT53B512M64D4NK      | 512  | 64  | 4    | 128          | 16GB     |

**Script pronto:** `scripts/fill_mt53b_density.py` (cobre família MT53B)

### Ação — Generalizar o decoder

Criar `scripts/fill_ram_density_from_pn.py` que aplica a mesma lógica para
todos os prefixos RAM Micron sem capacity:

- `MT52` → LPDDR3/DDR3  
- `MT41` → DDR3  
- `MT47` → DDR2  
- `MT53` → LPDDR4  
- `MT62` → LPDDR5  

> ⚠ Atenção: alguns PNs mais antigos (DDR2/LPDDR2) podem usar convenção
> diferente. Validar contra 5–10 datasheets antes de aplicar em massa.

---

## Estratégia 2 — Reimportar LPDDR4X do CSV correto

**Problema identificado:** A Micron não tem CSV separado para LPDDR4X — os
produtos LPDDR4X estão listados no mesmo CSV de LPDDR4, mas com TECHNOLOGY = 
"LPDDR4X" (ou similar). O `TECH_MAP` atual pode não estar capturando esses
registros.

**Ação:**
1. Abrir o CSV LPDDR4 atual e verificar os valores exatos da coluna TECHNOLOGY
   para PNs que começam com padrões associados a LPDDR4X (ex: MT53E, MT53D).
2. Adicionar entrada no `TECH_MAP` se necessário:
   ```python
   "LPDDR4X": ("RAM", "LPDDR4X"),
   ```
3. Re-executar `import_micron_catalog.py` com o CSV de LPDDR4 — o PASSO 1
   atualizará os registros existentes que têm campos vazios.

---

## Estratégia 3 — Scraping Micron Product Pages (MCP / UFS)

Para famílias que **não têm PN com estrutura decodificável** e também não estão
cobertas por CSVs (eMCP, uMCP, UFS pontuais):

**Abordagem:**
1. Para cada KnownPart sem capacity, construir a URL do produto Micron:
   ```
   https://www.micron.com/products/.../part-catalog/part-detail/{part_number}
   ```
2. Usar Claude in Chrome para extrair o campo "Capacity" ou "Component Density"
   da página de detalhe.
3. Atualizar o banco via script com os valores coletados.

**Script sugerido:** `scripts/scrape_missing_capacities.py`
- Lê KnownParts com `capacity__isnull=True` por chip_type
- Para cada PN, tenta URL `/part-detail/{pn}` na CDN Micron
- Faz parse do JSON de resposta ou HTML para extrair capacity
- Registra source_url e atualiza o campo

> Esta abordagem também pode preencher `interface` para eMMC (protocolo MMC)
> e UFS (protocolo UFS 3.1 / 4.0).

---

## Estratégia 4 — CSVs Alternativos para Legacy (DDR2/LPDDR2/LPDDR3)

As famílias DDR2, LPDDR2, LPDDR3 têm 0% de capacity preenchida. Essas famílias
estão descontinuadas (obsolete) na Micron — os CSVs do site atual não as cobrem.

**Fontes alternativas:**
- **Micron Obsolete Parts pages:** A Micron mantém páginas de partes obsoletas
  com PDFs de catálogos históricos. URL padrão:
  ```
  https://www.micron.com/products/obsolete/obsolete-{family}/part-catalog
  ```
- **Datasheets:** Para os ~120 registros legacy, os datasheets em PDF contêm
  a organização de memória no título/cabeçalho (ex: "4Gb × 16"). Podem ser
  extraídos em lote com a tool de PDF.
- **PN Decoder:** A convenção Micron é relativamente estável entre gerações.
  Após validar 5-10 PNs contra datasheets, o decoder pode cobrir DDR2/LPDDR2/LPDDR3
  com alta confiança.

---

## Ordem de Execução Recomendada

```
[1] python scripts/fix_mt53b_misclassified.py          # já feito (dry-run OK)
[2] python scripts/fill_mt53b_density.py --dry-run     # validar MT53B
[3] python scripts/fill_mt53b_density.py               # aplicar MT53B

[4] Verificar LPDDR4X no CSV → ajustar TECH_MAP → re-importar LPDDR4 CSV
    (cobre ~142 registros de uma vez)

[5] Criar scripts/fill_ram_density_from_pn.py          # generaliza decoder
    python scripts/fill_ram_density_from_pn.py --dry-run --families LPDDR3,DDR2,LPDDR5
    python scripts/fill_ram_density_from_pn.py         # aplica

[6] Investigar pages Micron obsolete para DDR2/LPDDR2/LPDDR3
    (baixar CSVs históricos se disponíveis)

[7] Scraping pontual para eMCP/uMCP/UFS sem capacity
```

---

## Métricas de Progresso

Após cada etapa, rodar:
```
python scripts/audit_micron_completeness.py
```

**Meta:** capacity ≥ 95% preenchida em todas as famílias ativas (LPDDR4, LPDDR4X,
LPDDR5, eMMC, UFS). Para DDR2/LPDDR2/LPDDR3 (legacy/obsolete), meta de 80%.
