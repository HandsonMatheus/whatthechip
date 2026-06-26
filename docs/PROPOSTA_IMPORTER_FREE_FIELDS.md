# PROPOSTA: `import_samsung_psg` — Campos livres para registros `confirmed`

> ⚠️ HISTÓRICO — menções a Gemini e ao campo `status` estão obsoletas (removidos jun/2026). Ver CLAUDE.md §4 e docs/archive/2026-06-26-remocao-gemini-status.md.

> **Status:** aguardando revisão e aprovação  
> **Data:** 2026-06-19  
> **Arquivo a modificar:** `chips/management/commands/import_samsung_psg.py`  
> **Impacto estimado:** baixo — mudança cirúrgica em ~15 linhas, sem toque no engine

---

## 1. Contexto do projeto

**WhatTheChip** é um classificador Django de chips de memória (eMCP, eMMC, UFS, LPDDR, DDR) para o mercado de reciclagem. O sistema tem dois mecanismos centrais:

1. **`KnownPart` (banco confirmado):** cada chip cadastrado com specs, type, subtype e rentabilidade.
2. **`ChipFamily` + `DecodeMap` (gramática):** decodificação posicional de qualquer PN não confirmado.

A classificação usa `classify(pn)` em `chips/engine.py`. O engine prefere o banco sobre a gramática quando `confidence in ("confirmed", "manual")`.

O **`subtype`** de um `KnownPart` alimenta diretamente o label da caixa física no estoque. O gateway `estoque/views.py::_compute_destination` constrói o label assim:

```python
gen = (result.get('subtype') or result.get('interface') or '').strip()
label = f"{gen}+{size}G"   # ex.: "LPDDR4+4G"
```

Se `subtype = "LPDDR4 Mobile"`, o label vira **`"LPDDR4 Mobile+4G"`** — texto que aparece na etiqueta física da caixa, que é lida por operadores de bancada. Isso é o problema que esta proposta resolve de forma escalável.

---

## 2. O pipeline de dados atual

Os Part Numbers Samsung entram no banco via:

```
data/psg/*.csv
    ↓
python manage.py import_samsung_psg --all
    ↓
KnownPart com confidence="confirmed", status="enriched"
```

Os CSVs são a **fonte primária Tier 1** (Samsung PSG e Samsung Semiconductor Global). Cada linha tem colunas como `pn`, `chip_type`, `subtype`, `capacity`, `interface`, `confidence`, `status`.

A **convenção de `subtype`** exige apenas a geração, sem qualificadores:
- ✅ `"LPDDR4"` — correto
- ❌ `"LPDDR4 Mobile"` — errado (vaza para label da caixa)
- ❌ `"LPDDR4X Multi-Channel"` — errado (idem)
- ❌ `"LPDDR5 8GB"` — errado (capacidade não é parte do subtype)

Vários CSVs foram importados historicamente com esses qualificadores verbosos. Ao detectar o problema, os CSVs foram corrigidos manualmente. Mas **a correção dos CSVs não propagou para o banco** — e este é o problema central.

---

## 3. O mecanismo de proteção atual — e por que ele trava as correções

### Código relevante: `_import_row()` em `import_samsung_psg.py`

```python
# Linha 36-48
_CONF_PRIORITY = {
    "estimated":   0,
    "ai_low":      1,
    "ai_medium":   2,
    "ai_high":     3,
    "distributor": 4,
    "manual":      5,
    "confirmed":   6,
}

# Confidence máxima que pode ser sobrescrita por este import.
_MAX_OVERWRITABLE = _CONF_PRIORITY["distributor"]   # = 4
```

```python
# Linha 266-269 — a linha que bloqueia TUDO
existing_prio = _CONF_PRIORITY.get(existing.confidence, 0)
if existing_prio > _MAX_OVERWRITABLE:
    # Registro protegido (manual ou confirmed) — não sobrescreve
    return "protected", f"{pn}: confidence={existing.confidence} protegida"
```

**Tradução:** qualquer registro com `confidence in ("manual", "confirmed")` retorna `"protected"` imediatamente, **sem nem tentar atualizar nenhum campo**. É um bloqueio total.

### Por que essa proteção existe (e faz sentido para specs)

A intenção original é correta: proteger dados de spec verificados por humano (`confirmed`) ou inseridos manualmente (`manual`) contra sobrescrita por fontes automatizadas de menor confiança (AI, distribuidor, scraping). Se um humano confirmou que `capacity="4GB"`, nenhum script deve poder alterar isso sem revisão.

### Por que ela é problemática para campos descritivos

O problema surge porque **`subtype` não é uma spec técnica do chip** — é uma **convenção de exibição** definida por regra interna (`CLAUDE.md §6`). A spec técnica real do chip (tipo de RAM, geração) é capturada por `chip_type`. O `subtype` é apenas como esse tipo aparece no label da caixa.

Portanto: proteger `subtype = "LPDDR4 Mobile"` contra uma correção legítima de `subtype = "LPDDR4"` **não está protegendo nenhum dado técnico**. Está apenas travando uma convenção de formatação errada no banco para sempre.

---

## 4. O workaround atual — e por que não escala

Para corrigir `subtype` em registros protegidos, o projeto usa `fix_known_parts.py`:

```bash
python manage.py fix_known_parts
```

Esse comando tem uma lista `CORRECTIONS` de entradas manuais. Cada entrada especifica um PN e os campos a corrigir. Funciona porque `fix_known_parts` faz `setattr` diretamente no objeto, sem passar pelo filtro de proteção do importer.

### O problema de escala

Na sessão de 2026-06-19 foram adicionadas **51 entradas** ao `fix_known_parts.py` só para corrigir `subtype` de registros já no banco:

| Grupo | PNs | Fix |
|---|---|---|
| K3LK* LPDDR5 (base PNs do k3lk_v2.csv) | 7 | `"LPDDR5 8GB"` → `"LPDDR5"` |
| K3UH* Multi-Channel | 5 | `"LPDDR4X Multi-Channel"` → `"LPDDR4X"` |
| K4EBE304EBEGCF | 1 | `"LPDDR3 Mobile"` → `"LPDDR3"` |
| K4F*/K4FBE* LPDDR4 Mobile | 28 | `"LPDDR4 Mobile"` → `"LPDDR4"` |
| K4P*/K3PE* LPDDR2 Mobile | 10 | `"LPDDR2 Mobile"` → `"LPDDR2"` |

O `fix_known_parts.py` já tinha ~7.800 linhas antes dessas adições. Cada PN novo precisa de uma entrada manual. Isso é insustentável:

- **Toda nova importação de CSV com subtype errado** vai requerer N entradas novas
- **CSVs já corrigidos não têm efeito** — a correção fica apenas no arquivo CSV, não no banco
- **Risco de divergência** entre CSV (fonte) e banco (realidade): dois lugares para manter
- O `fix_known_parts.py` cresceu para um arquivo de configuração gigante quando devia ser pequeno e cirúrgico

---

## 5. A proposta de solução

### Conceito central: campos descritivos vs. campos de especificação

Dividir os campos de `KnownPart` em duas categorias para fins do importer:

**Campos de especificação** — não tocar se `confirmed`/`manual` (risco real de sobrescrever dado humano):
- `chip_type`, `capacity`, `density_gbit`, `density_gb`, `fbga_code`, `emcp_nand`, `emcp_ram`, `confidence`

**Campos de convenção** — sempre permitir atualização por CSVs Tier 1, mesmo se `confirmed`:
- `subtype`, `interface`, `notes`

O raciocínio: `subtype` e `interface` são **convenções de exibição internas**, não specs do chip. A regra que define o que é um `subtype` válido (`CLAUDE.md §6`) pode mudar, e quando muda, os CSVs são a fonte correta de atualização.

### Opção A — Abordagem `_CONVENTION_FIELDS` (recomendada)

**Mudança mínima:** introduzir uma constante e um branch na lógica de proteção.

```python
# ADICIONAR após _MAX_OVERWRITABLE (linha ~48 do arquivo atual):

# Campos de convenção de exibição — sempre sobrescrevíveis pelo importer PSG,
# mesmo em registros confident/manual. Esses campos não carregam specs técnicas
# do chip; seguem a convenção interna definida em CLAUDE.md §6.
# NÃO incluir campos de spec: chip_type, capacity, density_*, fbga_code, etc.
_CONVENTION_FIELDS = frozenset({"subtype", "interface", "notes"})
```

```python
# SUBSTITUIR as linhas 266-269 (bloco "protegido"):

existing_prio = _CONF_PRIORITY.get(existing.confidence, 0)
if existing_prio > _MAX_OVERWRITABLE:
    # Registro protegido (manual ou confirmed).
    # Campos de spec: bloqueado total.
    # Campos de convenção (_CONVENTION_FIELDS): permitido atualizar.
    convention_changes = {}
    for field in _CONVENTION_FIELDS:
        csv_val = locals().get(field, "")   # não funciona assim — ver código completo abaixo
        ...
    if not convention_changes:
        return "protected", f"{pn}: confidence={existing.confidence} protegida"
    # aplica só os campos de convenção e retorna "updated"
    ...
```

O trecho acima é simplificado. A implementação completa está na seção 6.

### Opção B — Flag `--update-convention` (alternativa conservadora)

Adicionar uma flag CLI que, quando presente, permite atualizar campos de convenção em registros protegidos:

```bash
python manage.py import_samsung_psg --all --update-convention
```

**Vantagem:** comportamento padrão inalterado; a flag é opt-in explícito.  
**Desvantagem:** requer memória operacional — o operador tem que lembrar de usar a flag.

---

## 6. Implementação completa — Opção A

### 6.1 Diff exato do arquivo `import_samsung_psg.py`

#### Bloco 1 — adicionar constante `_CONVENTION_FIELDS` após `_MAX_OVERWRITABLE`

```python
# ANTES (linha 47-48):
_MAX_OVERWRITABLE = _CONF_PRIORITY["distributor"]

# DEPOIS:
_MAX_OVERWRITABLE = _CONF_PRIORITY["distributor"]

# Campos de convenção de exibição — sempre sobrescrevíveis por CSVs PSG,
# mesmo em registros com confidence="confirmed" ou "manual".
# Esses campos seguem regras internas de formatação (CLAUDE.md §6) e não
# carregam especificações técnicas do chip.
# ⚠ NÃO adicionar: chip_type, capacity, density_*, fbga_code, emcp_*.
_CONVENTION_FIELDS = frozenset({"subtype", "interface", "notes"})
```

#### Bloco 2 — substituir o bloco "protegido" em `_import_row()`

**ANTES** (linhas 266-270):

```python
    existing_prio = _CONF_PRIORITY.get(existing.confidence, 0)
    if existing_prio > _MAX_OVERWRITABLE:
        # Registro protegido (manual ou confirmed) — não sobrescreve
        return "protected", f"{pn}: confidence={existing.confidence} protegida"

    new_prio = _CONF_PRIORITY.get(confidence, 0)
```

**DEPOIS**:

```python
    existing_prio = _CONF_PRIORITY.get(existing.confidence, 0)
    if existing_prio > _MAX_OVERWRITABLE:
        # Registro protegido (manual ou confirmed).
        # Campos de spec: bloqueados. Campos de convenção: permitidos.
        conv_vals = {
            "subtype":   subtype,
            "interface": interface,
            "notes":     notes_csv,
        }
        conv_changed = {}
        for field, new_val in conv_vals.items():
            if new_val:  # só atualiza se o CSV tem valor não-vazio
                old_val = getattr(existing, field, None) or ""
                if old_val != new_val:
                    conv_changed[field] = new_val

        if not conv_changed:
            return "protected", f"{pn}: confidence={existing.confidence} protegida"

        # Aplica apenas campos de convenção
        if not dry:
            try:
                with transaction.atomic():
                    for field, val in conv_changed.items():
                        setattr(existing, field, val)
                    existing.save(update_fields=list(conv_changed.keys()) + ["last_updated"])
            except Exception as e:
                return "error", f"{pn}: {e}"

        return "updated", f"{pn}: convenção atualizada {list(conv_changed.keys())}"

    new_prio = _CONF_PRIORITY.get(confidence, 0)
```

**Nota sobre `notes_csv`:** a variável `notes_csv` já é construída no código atual (linha ~221) como string composta de dados técnicos do CSV. Para a atualização de convenção, **não** devemos sobrescrever `notes` com esse valor composto — seria destrutivo. Portanto, para o campo `notes`, a atualização só deve acontecer se o registro existente tiver `notes` vazio. Ajuste:

```python
        conv_vals = {
            "subtype":   subtype,
            "interface": interface,
            # notes: só preenche se vazio no banco (nunca sobrescreve nota existente)
        }
        conv_changed = {}
        for field, new_val in conv_vals.items():
            if new_val:
                old_val = getattr(existing, field, None) or ""
                if old_val != new_val:
                    conv_changed[field] = new_val
        # notes: comportamento conservador (preenche só se vazio)
        if notes_csv and not (getattr(existing, "notes", None) or "").strip():
            conv_changed["notes"] = notes_csv
```

### 6.2 Impacto no output do comando

**Antes:**
```
📄 samsung_global_lpddr4_2017_2020.csv
  criados=0 atualizados=0 pulados=0 protegidos=53 erros=0
```

**Depois** (exemplo esperado, todos os 25 K4F* LPDDR4 Mobile sendo corrigidos):
```
📄 samsung_global_lpddr4_2017_2020.csv
  criados=0 atualizados=25 pulados=28 protegidos=0 erros=0
```

O contador `atualizados` vai capturar as atualizações de convenção. Os 28 restantes (`pulados`) são os K4U*/K3UH* e K4F* que já tinham `subtype` correto.

### 6.3 Docstring do arquivo — atualizar o cabeçalho

A docstring atual tem uma afirmação errada:

```
# ANTES (linha 13):
O comando NUNCA sobrescreve registros com confidence acima de "estimated".
```

Substituir por:

```
# DEPOIS:
O comando NUNCA sobrescreve campos de spec (chip_type, capacity, density_*, fbga_code)
em registros com confidence="confirmed" ou "manual". Campos de convenção de exibição
(subtype, interface) são sempre atualizáveis, pois seguem regras internas — não specs
técnicas do chip. Ver _CONVENTION_FIELDS para a lista completa.
```

---

## 7. Análise de riscos

### 7.1 Risco: sobrescrever subtype correto com valor errado do CSV

**Cenário:** um registro foi corrigido manualmente no admin (subtype confirmado por humano), mas o CSV correspondente ainda tem um valor desatualizado.

**Mitigação:** os CSVs são a fonte primária. Se um humano corrigiu via admin, a correção deve ser propagada de volta ao CSV — essa é a regra de higiene do projeto. A alternativa (proteger subtype mesmo para confirmed) perpetua exatamente o bug que estamos resolvendo.

**Severidade:** baixa. `subtype` não afeta o decode técnico do chip — afeta apenas o label da caixa. Se o label ficar errado temporariamente, é corrigido na próxima rodada de import.

### 7.2 Risco: `interface` sobrescrita indevidamente

**Cenário:** campo `interface` tem valor técnico importante (ex.: `"x16"` para DDR) e o CSV tem string diferente.

**Análise:** a coluna `interface` nos CSVs Samsung contém valores como `"LPDDR4"` (nome do protocolo, não bus width). Para LPDDR standalone, o campo correto de bus width em `KnownPart` é vazio — o interface no sentido de bus width não se aplica. Portanto atualizar `interface` a partir do CSV é seguro para os CSVs Samsung.

**Mitigação adicional:** se houver dúvida, pode-se remover `interface` de `_CONVENTION_FIELDS` e incluir apenas `subtype`. O impacto ainda resolve 90% dos casos (subtype é o campo que vaza para o label).

### 7.3 Risco: performance — o importer agora faz `save()` para campos de convenção

**Análise:** o importer já fazia `save()` para updates normais. A mudança apenas cria um path adicional que, em vez de retornar `"protected"` imediatamente, verifica ~3 campos e opcionalmente salva. Para 380 PNs, isso é insignificante.

### 7.4 Risco: `fix_known_parts.py` e o importer entram em conflito

**Cenário:** `fix_known_parts` seta `subtype="LPDDR4"`, depois o importer lê CSV com `subtype="LPDDR4 Mobile"` e sobrescreve.

**Análise:** isso é o comportamento CORRETO esperado. Se o CSV ainda tiver valor errado, ele deve ser corrigido no CSV — não protegido no banco. A ordem certa é: corrigir CSV → rodar importer → campo correto no banco. O `fix_known_parts` é para correções manuais que não têm fonte CSV.

**Mitigação:** os 4 CSVs já foram corrigidos nesta sessão (2026-06-19). O `fix_known_parts` com as 51 entradas adicionadas pode — e deve — ser removido gradualmente à medida que o importer passe a funcionar corretamente para esses PNs.

---

## 8. Plano de testes

### 8.1 Dry-run antes de qualquer mudança real

```bash
# Verificar o que seria atualizado ANTES de implementar a mudança
python manage.py import_samsung_psg --all --dry-run
# Deve mostrar: protegidos=380, atualizados=0

# Após implementar a mudança, dry-run mostra o que SERIA corrigido:
python manage.py import_samsung_psg --all --dry-run
# Deve mostrar: protegidos≈0, atualizados≈53 (os de subtype errado)
```

### 8.2 Verificação pontual pré e pós

```bash
# Verificar estado antes
python manage.py shell -c "
from chips.models import KnownPart
problematicos = KnownPart.objects.filter(
    subtype__in=['LPDDR4 Mobile', 'LPDDR4X Multi-Channel', 'LPDDR2 Mobile', 'LPDDR3 Mobile']
).values_list('part_number', 'subtype')
print(f'PNs com subtype errado: {problematicos.count()}')
for pn, st in problematicos[:10]:
    print(f'  {pn}: {st}')
"

# Rodar o importer (real)
python manage.py import_samsung_psg --all

# Verificar estado depois
python manage.py shell -c "
from chips.models import KnownPart
restantes = KnownPart.objects.filter(
    subtype__in=['LPDDR4 Mobile', 'LPDDR4X Multi-Channel', 'LPDDR2 Mobile', 'LPDDR3 Mobile']
).count()
print(f'PNs com subtype errado restantes: {restantes}')
# Deve ser 0
"
```

### 8.3 Verificar que campos de spec NÃO foram alterados

```bash
python manage.py shell -c "
from chips.models import KnownPart
# Spot check: K4FBE3D4HBKHCL deve continuar capacity=4GB, chip_type=LPDDR4
kp = KnownPart.objects.get(part_number='K4FBE3D4HBKHCL')
print(f'chip_type: {kp.chip_type}')   # deve ser LPDDR4
print(f'capacity: {kp.capacity}')     # deve ser 4GB
print(f'subtype: {kp.subtype}')       # deve ser LPDDR4 (corrigido)
print(f'confidence: {kp.confidence}') # deve ser confirmed (intocado)
"
```

### 8.4 Teste de regressão do engine

```bash
python manage.py test chips --settings=core.settings_test
```

---

## 9. Plano de rollback

Se a mudança causar problema:

1. **Reverter `import_samsung_psg.py`** para a versão anterior (git revert do commit específico)
2. **As 51 entradas de `fix_known_parts.py`** permanecem como fallback — elas ainda funcionam independentemente do importer
3. Rodar `python manage.py fix_known_parts` para restaurar os valores corretos no banco

O rollback é seguro porque `fix_known_parts` e o importer são independentes.

---

## 10. Limpeza futura (pós-aprovação e testes)

Após a mudança do importer estar em produção e funcionando:

1. **Remover as 51 entradas de `fix_known_parts.py`** adicionadas em 2026-06-19 (K3LK*, K3UH*, K4EBE304EBEGCF, K4F*/K4FBE*, K4P*/K3PE*)
2. O `fix_known_parts.py` deve volcar ao papel original: correções manuais pontuais com plena documentação — não batch fixes de convenção
3. Qualquer novo CSV com subtype errado terá o CSV corrigido e o importer propagará automaticamente

---

## 11. O que o próximo chat deve fazer

### Passo 1: Revisar esta proposta
Ler este documento e o código atual de `import_samsung_psg.py` (especialmente as linhas 36-48 e 260-280).

### Passo 2: Implementar a mudança
Editar `chips/management/commands/import_samsung_psg.py`:

1. Adicionar constante `_CONVENTION_FIELDS = frozenset({"subtype", "interface"})` após `_MAX_OVERWRITABLE` (linha ~48)
2. Substituir o bloco `if existing_prio > _MAX_OVERWRITABLE:` pelo código da seção 6.2
3. Atualizar a docstring do arquivo (seção 6.3)

### Passo 3: Testar localmente
```bash
python manage.py import_samsung_psg --all --dry-run   # verificar o que muda
python manage.py import_samsung_psg --all              # aplicar
python manage.py test chips --settings=core.settings_test
```

### Passo 4: Verificar K4EBE304EBEGCF especificamente
```bash
python manage.py shell -c "
from chips.engine import classify
r = classify('K4EBE304EBEGCF')
print(r.get('subtype'))   # deve ser 'LPDDR3', não 'LPDDR3 Mobile'
"
```

### Passo 5: Commit
```bash
git add chips/management/commands/import_samsung_psg.py
git commit -m "feat: import_samsung_psg — campos de convenção sempre atualizáveis

Introduz _CONVENTION_FIELDS (subtype, interface) — campos que seguem
convenção interna de exibição (CLAUDE.md §6), não specs técnicas.

Registros com confidence=confirmed/manual continuam protegidos para
campos de spec (capacity, chip_type, density_*, fbga_code). Mas subtype
e interface são sempre atualizados pelo importer PSG, pois:
- Não carregam dados técnicos do chip
- Seguem regras internas que podem mudar sem alterar o chip
- 'LPDDR4 Mobile' no label da caixa é erro de exibição, não dado técnico

Antes: import_samsung_psg mostrava protegidos=380, atualizados=0
Depois: subtype/interface verbosos são corrigidos automaticamente

Resolve necessidade de adicionar entradas manuais em fix_known_parts.py
para cada PN com subtype errado (51 entradas adicionadas em 2026-06-19)."
```

### Passo 6 (opcional, após validação em produção): limpar fix_known_parts.py
Remover as 51 entradas adicionadas em 2026-06-19 que corrigem apenas `subtype`.

---

## Apêndice A: mapa de arquivos relevantes

```
chips/management/commands/import_samsung_psg.py  ← arquivo a modificar
chips/management/commands/fix_known_parts.py     ← workaround atual
chips/engine.py                                  ← classify(), NÃO tocar
chips/models.py                                  ← KnownPart model
estoque/views.py                                 ← _compute_destination (usa subtype)
data/psg/*.csv                                   ← fontes de dados (já corrigidas)
```

## Apêndice B: campos de KnownPart e classificação

| Campo | Tipo | Pode atualizar se confirmed? |
|---|---|---|
| `chip_type` | spec | ❌ nunca |
| `capacity` | spec | ❌ nunca |
| `density_gbit` | spec | ❌ nunca |
| `density_gb` | spec | ❌ nunca |
| `fbga_code` | spec | ❌ nunca |
| `emcp_nand` | spec | ❌ nunca |
| `emcp_ram` | spec | ❌ nunca |
| `confidence` | meta | ❌ nunca (pelo importer) |
| `subtype` | **convenção** | ✅ sim (proposta) |
| `interface` | **convenção** | ✅ sim (proposta) |
| `notes` | informativo | ⚠ só se vazio |

## Apêndice C: estado do banco antes desta proposta

Levantamento feito em 2026-06-19 — PNs com `subtype` verboso no banco:

| subtype errado | count | CSVs de origem |
|---|---|---|
| `"LPDDR4 Mobile"` | ~28 | samsung_global_lpddr4_2017_2020.csv + psg_1h2017 |
| `"LPDDR4X Multi-Channel"` | ~5 | idem |
| `"LPDDR2 Mobile"` | ~10 | psg_2h2014_mobile_dram.csv |
| `"LPDDR3 Mobile"` | ~1 | psg_1h2017_mobile_dram.csv (versão antiga) |
| `"LPDDR5 8GB"` / `"LPDDR5 12GB"` etc. | ~7 | samsung_global_lpddr5_k3lk_v2.csv |

Todos os CSVs listados já foram corrigidos em 2026-06-19. O banco ainda tem os valores errados porque o importer protege registros `confirmed`. Esta proposta resolve isso estruturalmente.
