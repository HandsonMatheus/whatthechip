# Plano de Desenvolvimento — Micron FBGA & Cobertura Total

> ⚠️ HISTÓRICO — menções a Gemini e ao campo `status` estão obsoletas (removidos jun/2026). Ver CLAUDE.md §4 e docs/archive/2026-06-26-remocao-gemini-status.md.

**WhatTheChip — documento de acompanhamento interno**
Criado: 2026-05-26 | Responsável: Claude + eMiner

---

## Estado atual do projeto

### Já implementado no código (aguardando execução no servidor)

| Arquivo | Mudança | Comando necessário |
|---|---|---|
| `chips/management/commands/add_chip_families.py` | Família `MT53B` (LPDDR4, 1.1V) adicionada | `manage.py add_chip_families --overwrite` |
| `chips/management/commands/fix_known_parts.py` | `MT53B512M64D4TX` (D9VFC, 4GB LPDDR4) adicionado | `manage.py fix_known_parts` |

> ⚠️ Estes dois comandos precisam rodar no servidor antes de qualquer outra fase.

### Decisões arquiteturais fechadas

- **FBGA codes** ficam em `KnownPart.fbga_code` — mesma estrutura de Samsung/Hynix, sem tabela separada.
- **Engine** não tenta decodificar gramática de FBGA — só lookup de banco. Se não estiver cadastrado, cai no `UnknownChip`.
- **Enriquecimento** de FBGAs desconhecidos via **job noturno** (não em runtime), para não adicionar latência na esteira.
- **Claude in Chrome** é a via para todos os acessos a conteúdo JS-rendered (Micron catalog, FBGA decoder).
- **Preduo** é a fonte Tier 4 para bulk de PNs base — sem FBGA codes, mas com capacity + package + interface.

---

## Hierarquia de fontes (imutável)

```
Micron oficial (micron.com, datasheet, FBGA cross-reference)
  > Octopart (PN confirmado com especificações)
    > Distribuidor B2B rastreável (Puris, ssfkg, Win Source, Veswin)
      > Preduo (preduo.com — catálogo de reciclagem)
        > IA externa
          > Especulação
```

---

## Fase 0 — Deploy do que já está pronto

**Pré-requisito de tudo. Sem essa fase, o banco não reflete o código.**

- [ ] `python manage.py add_chip_families --overwrite`
  - Adiciona família `MT53B` (prefix, chip_type RAM, subtype LPDDR4 standalone, interface LPDDR4, priority 50)
  - Verificar: `ChipFamily.objects.filter(prefix='MT53B').exists()` → True

- [ ] `python manage.py fix_known_parts`
  - Cria `KnownPart(part_number='MT53B512M64D4TX', capacity='4GB', confidence='confirmed', status='enriched')`
  - Verificar: buscar `MT53B512M64D4TX` no site → deve retornar resultado

- [ ] Smoke test: buscar `MT53B512M64D4TX` no WhatTheChip → confirmar que retorna "4GB LPDDR4 Micron"

---

## Fase 1 — Campo `fbga_code` no modelo + engine

**Bloqueador**: nada. Pode rodar em paralelo com qualquer fase.

### 1.1 — Migration: adicionar `fbga_code` a `KnownPart`

Arquivo: `chips/models.py`

```python
# Adicionar no modelo KnownPart, após o campo `interface`:
fbga_code = models.CharField(
    max_length=10,
    blank=True,
    default="",
    db_index=True,
    help_text="Código FBGA gravado no chip (ex: D9VFC). "
              "Micron DRAM: padrão D9XXX. "
              "Permite lookup direto pelo código que o operador lê na esteira."
)
```

- [ ] Adicionar campo `fbga_code` em `KnownPart`
- [ ] Gerar migration: `python manage.py makemigrations chips`
- [ ] Aplicar: `python manage.py migrate`
- [ ] Atualizar `fix_known_parts.py`: adicionar `"fbga_code": "D9VFC"` no bloco do `MT53B512M64D4TX`
- [ ] Rodar `fix_known_parts` novamente para preencher o D9VFC

### 1.2 — Engine: detecção de padrão FBGA + lookup

Arquivo: `chips/engine.py`

**Padrão FBGA Micron**: 5 caracteres alfanuméricos, segundo char numérico.
- DRAM mobile: `D9[A-Z0-9]{3}` (ex: D9VFC, D9TBH, D9WFJ, D9SHD)
- NAND: `D8[A-Z0-9]{3}` (ex: D8TXF)
- Detector seguro: `r'^[A-Z]\d[A-Z0-9]{3}$'`

```python
# Em classify(), após o bloco de exact match por part_number:

_FBGA_RE = re.compile(r'^[A-Z]\d[A-Z0-9]{3}$')

def _is_fbga(pn: str) -> bool:
    return bool(_FBGA_RE.match(pn))

# No fluxo do classify():
if _is_fbga(pn):
    known = KnownPart.objects.filter(fbga_code=pn).first()
    if known:
        result = _result_from_known(known, source="db_fbga")
        _log_search(pn_raw, found=True, source="db_fbga")
        return result
    else:
        # FBGA não cadastrado → enfilera para enriquecimento noturno
        UnknownChip.objects.get_or_create(
            part_number=pn,
            defaults={"notes": "FBGA code — pendente resolução noturna"}
        )
        _log_search(pn_raw, found=False, source="fbga_unknown")
        return {"found": False, "source": "fbga_unknown", "pn": pn}
```

- [ ] Adicionar constante `_FBGA_RE` no engine
- [ ] Adicionar função `_is_fbga()`
- [ ] Inserir bloco FBGA no fluxo do `classify()` (após exact match, antes da grammar)
- [ ] Atualizar `SearchLog.source_used` para aceitar `"db_fbga"` e `"fbga_unknown"`
- [ ] Testes manuais: `D9VFC` → deve retornar o MT53B512M64D4TX; `D9ZZZ` → deve cair no UnknownChip

### 1.3 — Admin: expor `fbga_code` no admin Django

- [ ] Adicionar `fbga_code` ao `list_display` e `search_fields` do `KnownPartAdmin`
- [ ] Adicionar filtro por `fbga_code__isnull=False` para ver quais PNs já têm FBGA mapeado

---

## Fase 2 — Scraper Preduo (cobertura base, todas as marcas)

**Bloqueador**: Fase 1 concluída (precisa do campo `fbga_code` no modelo para o scraper poder preenchê-lo quando disponível).

### Escopo do scraper

Preduo cobre: LPDDR (1-5T/5x), UFS (2.0-4.0), uMCP, eMMC (4.41-5.1), eMCP (eMMC+LPDDR1 a 4x), DRAM (DDR2-5), GDDR (5/6), HBM (2-3E), NORFLASH.

Dados disponíveis por página: Part Number, Manufacturer, Type, Sub-Type, Package (ball count), Density.
**Não disponível**: FBGA code (nenhuma página Preduo exibe isso).

### Arquitetura do comando

Arquivo: `chips/management/commands/scrape_preduo.py`

```
Opções:
  --dry-run         Mostra o que seria importado sem salvar
  --brand MICRON    Filtra por fabricante (nome como aparece no Preduo)
  --type lpddr4     Filtra por tipo de chip
  --overwrite       Atualiza KnownParts existentes (default: skip se já existe)
  --limit N         Limita N produtos por execução (para testes)

Fluxo:
  1. Carrega mapa de categorias Preduo → URLs de listagem
  2. Para cada URL de listagem, pagina até o fim coletando URLs de produtos
  3. Para cada URL de produto, fetch + parse da tabela de specs
  4. Mapeia Manufacturer → Brand (Samsung/SKhynix/Micron/Spectek/KIOXIA/Sandisk)
  5. Extrai chip_type, subtype, interface do Type/Sub-Type/Package
  6. Converte Density (ex: "32Gbit") → capacity (ex: "4GB")
  7. Tenta casar com ChipFamily existente pelo prefixo do PN
  8. Cria/atualiza KnownPart com confidence="distributor", status="enriched"
  9. source_url = URL da página Preduo
```

**Mapa de categorias Preduo** (URLs a iterar):

| Categoria | URL base |
|---|---|
| LPDDR4 | preduo.com/list/lpddr/lpddr4 |
| LPDDR4x | preduo.com/list/lpddr/lpddr4x |
| LPDDR5 | preduo.com/list/lpddr/lpddr5-lpddr |
| LPDDR5x | preduo.com/list/lpddr/lpddr5x-lpddr |
| LPDDR3 | preduo.com/list/lpddr/lpddr3 |
| LPDDR2 | preduo.com/list/lpddr/lpddr2 |
| eMMC 5.1 | preduo.com/list/emmc/emmc-5-1 |
| eMMC 5.0 | preduo.com/list/emmc/emmc-5-0 |
| eMMC 4.51 | preduo.com/list/emmc/emmc-4-51 |
| eMMC 4.5 | preduo.com/list/emmc/emmc-4-5 |
| eMMC 4.41a | preduo.com/list/emmc/emmc-4-41a |
| eMCP eMMC+LPDDR4x | preduo.com/list/emcp/emmc-lpddr4x |
| eMCP eMMC+LPDDR3 | preduo.com/list/emcp/emmc-lpddr3 |
| eMCP eMMC+LPDDR2 | preduo.com/list/emcp/emmc-lpddr2 |
| UFS 4.0 | preduo.com/list/ufs/ufs-4-0 |
| UFS 3.1 | preduo.com/list/ufs/ufs-3-1 |
| UFS 3.0 | preduo.com/list/ufs/ufs-3-0 |
| UFS 2.2 | preduo.com/list/ufs/ufs-2-2 |
| UFS 2.1 | preduo.com/list/ufs/ufs-2-1 |
| DDR4 | preduo.com/list/dram/ddr4 |
| DDR3 | preduo.com/list/dram/ddr3-ddr |
| GDDR6 | preduo.com/list/gddr/gddr6 |
| GDDR5 | preduo.com/list/gddr/gddr5 |
| HBM3E | preduo.com/list/hbm/hbm3e |
| uMCP UFS+LPDDR5 | preduo.com/list/umcp/ufslpddr5 |
| uMCP UFS+LPDDR4x | preduo.com/list/umcp/ufs-lpddr4x |

**Conversão de Density → capacity**:
```python
# Regra geral: Gbit ÷ 8 = GB (para chips standalone)
# Para eMCP: val_primary = NAND, val_secondary = RAM (extrair do Sub-Type)
# "32Gbit" → "4GB"
# "64Gbit" → "8GB"
# "16Gbit" → "2GB"
# "128Gbit" → "16GB"
```

**Tratamento de marcas**:
```python
BRAND_MAP = {
    "Micron":   "Micron",
    "Samsung":  "Samsung",
    "SKhynix":  "SK Hynix",  # verificar nome exato no banco
    "Spectek":  "Spectek",   # criar se não existir
    "KIOXIA":   "KIOXIA",    # criar se não existir
    "Sandisk":  "Sandisk",   # criar se não existir
    "Toshiba":  "Toshiba",   # criar se não existir
}
```

- [ ] Criar `scrape_preduo.py` com estrutura base + opções de CLI
- [ ] Implementar paginação das listagens por categoria
- [ ] Implementar parser da tabela de specs de produto
- [ ] Implementar mapeamento Brand/ChipFamily
- [ ] Implementar conversão Density → capacity
- [ ] Rodar `--dry-run` completo e revisar output
- [ ] Rodar real para Micron LPDDR4 primeiro (menor risco)
- [ ] Rodar para todas as categorias após validação
- [ ] Verificar cobertura: quantos KnownParts novos foram criados por marca

---

## Fase 3 — Export Full Catalog Micron via Claude in Chrome

**Bloqueador**: Claude in Chrome habilitado no Cowork (Settings → Desktop app → Computer use).

**Objetivo**: obter CSV/Excel com TODOS os PNs Micron ativos e obsoletos, incluindo campos de densidade, speed grade, package, status de ciclo de vida. Este export não inclui FBGA codes — esses vêm na Fase 4.

### Catálogos a exportar

| Família | URL |
|---|---|
| LPDDR4/4x (ativo) | micron.com/products/memory/lpddr-components/lpddr4/part-catalog |
| LPDDR5/5x (ativo) | micron.com/products/memory/lpddr-components/lpddr5/part-catalog |
| LPDDR3 (ativo) | micron.com/products/memory/lpddr-components/lpddr3/part-catalog |
| eMMC (managed NAND) | micron.com/products/storage/managed-nand/part-catalog |
| NAND flash | micron.com/products/storage/nand-flash/part-catalog |
| DRAM components | micron.com/products/memory/dram-components/part-catalog |
| Obsoletos (todos) | micron.com/products/obsolete |

### Fluxo Claude in Chrome por catálogo

```
1. Navegar para a URL do catálogo
2. Aguardar tabela carregar (JS render)
3. Aplicar filtros se necessário (ex: "Mobile" para LPDDR)
4. Clicar "Export Full Catalog" → baixar CSV/Excel
5. Salvar arquivo em /chipdocs/micron_exports/[tipo]_[data].csv
6. Repetir para próxima família
```

### Comando de importação

Arquivo: `chips/management/commands/import_micron_catalog.py`

```
Opções:
  --file PATH       CSV/Excel exportado do micron.com
  --type lpddr4     Tipo de chip (para inferir chip_type se não estiver no CSV)
  --dry-run
  --overwrite       Atualiza PNs existentes (default: skip)

Colunas esperadas no CSV:
  Part number, Density, Parts status, Depth, Width, OP. Temp, Speed

Mapeamento:
  Part number → KnownPart.part_number (base, sem sufixo de velocidade)
  Density     → capacity (32Gb → 4GB)
  Parts status → notes ("Active", "NRND", "Discontinued")
  Speed       → interface (ex: 3733MT/s → LPDDR4)
  confidence  = "confirmed" (fonte primária: micron.com)
  status      = "enriched"
```

- [ ] Habilitar Claude in Chrome no Cowork
- [ ] Exportar catálogo LPDDR4/4x (primeiro, validar estrutura do CSV)
- [ ] Criar `import_micron_catalog.py`
- [ ] Testar import com LPDDR4 CSV
- [ ] Exportar catálogos restantes (LPDDR5, LPDDR3, eMMC, NAND, DRAM, Obsoletos)
- [ ] Rodar import para todos os catálogos
- [ ] Verificar total de KnownParts Micron criados/atualizados

---

## Fase 4 — FBGA Batch Decode via Claude in Chrome

**Bloqueador**: Fase 1 (campo `fbga_code` no modelo) + Fase 3 (PNs Micron no banco).

**Objetivo**: para cada `KnownPart` Micron que ainda não tem `fbga_code`, usar o decoder da Micron para obter o código FBGA correspondente. Isso pré-popula o mapeamento FBGA→PN antes de qualquer chip chegar na esteira.

**Ferramenta**: `micron.com/sales-support/design-tools/fbga-parts-decoder`
O decoder aceita busca **nos dois sentidos**: por FBGA code → PN, e por PN → FBGA code.

### Estratégia de batch

Claude in Chrome opera o decoder em loop:

```
Para cada KnownPart onde brand="Micron" AND fbga_code="":
  1. Navegar para micron.com/sales-support/design-tools/fbga-parts-decoder
  2. Digitar part_number no campo de busca
  3. Aguardar resultado
  4. Extrair FBGA code do resultado
  5. Atualizar KnownPart.fbga_code via API ou management command
  6. Aguardar 2s (rate limit cortesia)
  7. Próximo PN
```

### Comando auxiliar para receber os resultados

Arquivo: `chips/management/commands/import_fbga_codes.py`

```
Formato de entrada: CSV simples
  part_number,fbga_code
  MT53B512M64D4TX,D9VFC
  MT53E512M64D4NW,D9TBH
  ...

Flags:
  --file PATH
  --dry-run
```

- [ ] Criar planilha de PNs Micron sem `fbga_code` (query: `KnownPart.objects.filter(brand__name='Micron', fbga_code='')`)
- [ ] Criar `import_fbga_codes.py`
- [ ] Rodar Claude in Chrome no FBGA decoder para os top-50 PNs mais frequentes (validação)
- [ ] Revisar CSV gerado, importar
- [ ] Rodar para todos os PNs Micron sem FBGA
- [ ] Meta: >80% dos KnownParts Micron com `fbga_code` preenchido

---

## Fase 5 — Job Noturno de Enriquecimento FBGA

**Bloqueador**: Fase 1 + servidor com Celery ou cron configurado.

**Objetivo**: processar automaticamente FBGAs desconhecidos que chegaram na esteira durante o dia. Roda às 3h, não interfere com a esteira de produção.

### Arquitetura

Arquivo: `chips/management/commands/enrich_unknown_fbga.py`

```
Fluxo:
  1. Busca UnknownChip onde notes contém "FBGA code" e logged_at > (agora - 24h)
  2. Para cada entrada:
     a. Verifica se já foi resolvido em KnownPart.fbga_code (skip se sim)
     b. Chama resolução FBGA (ver abaixo)
     c. Se resolvido: cria KnownPart, remove do UnknownChip, loga
     d. Se não resolvido: incrementa tentativas no campo notes, skip
  3. Gera relatório: N resolvidos, N pendentes, N falhas

Resolução FBGA — opções (em ordem de preferência):
  Opção A: Claude API com tool_use + navegação Chrome (mais automático)
  Opção B: Claude in Chrome operado manualmente em batch (mais confiável)
  Opção C: Fila para revisão manual (fallback final)
```

### Agendamento

```python
# crontab: 3h todo dia
0 3 * * * cd /path/to/project && python manage.py enrich_unknown_fbga >> /var/log/wtc/fbga_enrich.log 2>&1
```

- [ ] Criar `enrich_unknown_fbga.py`
- [ ] Implementar detecção de FBGA no UnknownChip
- [ ] Implementar integração com Claude API para resolução
- [ ] Testar com um lote de 10 FBGAs conhecidos
- [ ] Configurar cron no servidor
- [ ] Monitorar primeiras 3 execuções

---

## Fase 6 — populate_micron.py (decode maps de gramática)

**Bloqueador**: Fase 0 + Fase 1.

**Objetivo**: adicionar regras de decodificação por gramática para famílias Micron — para que o engine consiga decodificar PNs novos mesmo que não estejam no KnownPart. Complementa (não substitui) o banco de KnownPart.

**Desafio técnico**: Micron usa blocos de densidade variável no PN (ex: `512M64` = 6 chars vs `1G32` = 4 chars), incompatível com o `decode_cap_pos` fixo do modelo atual. Estratégia: definir `decode_cap_pos=None` para famílias MT53x e usar regex no engine para extrair o bloco `\d+[MG]\d+`.

### Famílias a cobrir

| Prefixo | Tipo | Decode | Notas |
|---|---|---|---|
| `MT53B` | LPDDR4 | density block → GB | VDDQ 1.1V |
| `MT53E` | LPDDR4x | density block → GB | VDDQ 0.6V |
| `MT53D` | LPDDR4 | density block → GB | variante |
| `MT52L` | LPDDR4 | density block → GB | package menor |
| `MTFC` | eMMC | posição fixa | já parcialmente mapeado |
| `MT29F` | NAND | decode diferente | pendente pesquisa |
| `MT29T` | eMCP | decode duplo | pendente pesquisa |

### Decode da densidade Micron (MT53x)

```
Padrão: MT53[B/E/D][DEPTH][WIDTH][CONFIG]
Exemplos:
  MT53B 512M 64 D4TX  → Depth=512M, Width=64bit → 512M×64=32Gb ÷ 8 = 4GB
  MT53E   1G 32 D2DS  → Depth=1G,   Width=32bit → 1G×32=32Gb  ÷ 8 = 4GB
  MT53B 256M 64 D2NK  → Depth=256M, Width=64bit → 256M×64=16Gb ÷ 8 = 2GB
  MT53E   2G 32 D4DE  → Depth=2G,   Width=32bit → 2G×32=64Gb  ÷ 8 = 8GB
  MT53B1024M 32 D4    → Depth=1024M,Width=32bit → 1024M×32=32Gb ÷ 8 = 4GB

Fórmula: capacity_GB = (depth_M * width_bits) / (8 * 1024)
  onde depth pode ser em M (megabytes) ou G (gigabytes)
```

- [ ] Pesquisar e documentar decode completo para MTFC (eMMC)
- [ ] Criar `populate_micron.py` com estrutura base (igual populate_samsung.py)
- [ ] Implementar decode density para MT53x via regex no engine (mudança no engine.py)
- [ ] Adicionar DecodeMap entries para MT53B, MT53E, MT53D
- [ ] Implementar decode para MT52L
- [ ] Pesquisar MT29F e MT29T (NAND/eMCP — requer fonte primária antes de implementar)
- [ ] Rodar `--dry-run` e validar resultados
- [ ] Rodar real

---

## Fase 7 — Monitoramento e métricas

**Objetivo**: visibilidade sobre o estado da cobertura.

- [ ] Query de cobertura FBGA: `KnownPart.objects.filter(brand__name='Micron').values('fbga_code').annotate(n=Count('id'))`
- [ ] Admin view: KnownParts Micron sem FBGA code
- [ ] Alerta automático quando UnknownChip acumular >50 FBGAs não resolvidos
- [ ] Dashboard simples: total KnownParts por brand, % com fbga_code, % enriched

---

## Dependências entre fases

```
Fase 0 ─────────────────────────────────────────────────────┐
                                                             │
Fase 1 (model + engine) ──────────────────────────────────┐ │
                                                           │ │
Fase 2 (Preduo scraper) ──── depende de: Fase 1 ──────────┤ │
                                                           │ │
Fase 3 (Micron catalog Chrome) ── depende de: Fase 1 ─────┤ │
                                                           │ │
Fase 4 (FBGA batch Chrome) ─── depende de: Fase 1 + 3 ────┤ │
                                                           │ │
Fase 5 (job noturno) ──────── depende de: Fase 1 ─────────┤ │
                                                           │ │
Fase 6 (populate_micron.py) ── depende de: Fase 0 + 1 ────┤ │
                                                           │ │
Fase 7 (métricas) ──────────── depende de: todas ─────────┘ │
                                                             │
                                           Tudo depende de: ┘
```

---

## Checklist de execução atual

### Fase 0
- [ ] `manage.py add_chip_families --overwrite`
- [ ] `manage.py fix_known_parts`
- [ ] Smoke test D9VFC no site

### Fase 1
- [ ] `models.py`: adicionar `fbga_code`
- [ ] `makemigrations && migrate`
- [ ] `engine.py`: `_FBGA_RE`, `_is_fbga()`, bloco FBGA no `classify()`
- [ ] `fix_known_parts.py`: adicionar `fbga_code: "D9VFC"` ao MT53B512M64D4TX
- [ ] Admin: expor `fbga_code`

### Fase 2
- [ ] `scrape_preduo.py`: estrutura + paginação
- [ ] Parser de produto
- [ ] Mapeamento brand/family/capacity
- [ ] Dry-run + revisão
- [ ] Run completo

### Fase 3
- [ ] Habilitar Chrome
- [ ] Export LPDDR4 catalog → CSV
- [ ] `import_micron_catalog.py`
- [ ] Import LPDDR4
- [ ] Export + import demais famílias

### Fase 4
- [ ] `import_fbga_codes.py`
- [ ] Batch Chrome top-50 PNs
- [ ] Batch Chrome todos PNs Micron

### Fase 5
- [ ] `enrich_unknown_fbga.py`
- [ ] Integração Claude API
- [ ] Cron no servidor

### Fase 6
- [ ] Pesquisa decode MT53x (density block regex)
- [ ] `populate_micron.py`
- [ ] Decode completo + testes

### Fase 7
- [ ] Queries de cobertura
- [ ] Admin views
- [ ] Alertas

---

## Log de chips processados na esteira

| Data | FBGA | PN completo | Fonte | Capacity | Interface | Status | Obs |
|---|---|---|---|---|---|---|---|
| 2026-05-26 | D9VFC | MT53B512M64D4TX | Octopart | 4GB | LPDDR4 | ✅ implementado | VDDQ 1.1V, 1866MHz |

---

*Este documento é atualizado a cada sessão de desenvolvimento.*
