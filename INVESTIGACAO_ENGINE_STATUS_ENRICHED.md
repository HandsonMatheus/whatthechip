# Investigação: Bug de Classificação — `fix_known_parts` não sobrescreve resultado da gramática

**Data:** 2026-05-14  
**PN afetado:** `KMR310001M`  
**Sintoma:** Após rodar `fix_known_parts --pn KMR310001M` e reiniciar o servidor, o chip continua sendo classificado pela gramática com valores errados (`LPDDR4/4X 1GB`) em vez dos valores confirmados do banco (`LPDDR3 2GB`).

---

## 1. O que o debug revela

```
Fonte:         gramática
known_exact:   false
raw_in_db:     false
emcp_source:   gramática
confidence:    estimated
grammar_complete: true
```

Os campos `known_exact: false` e `raw_in_db: false` são o diagnóstico definitivo: **o registro não existe no banco**, ou existe mas com `status != "enriched"`. O engine nunca chegou a consultar o `KnownPart` salvo pelo `fix_known_parts`.

---

## 2. Fluxo do engine — onde a decisão acontece

### Camada 1: Busca exata no banco (`engine.py`, linha ~1042)

```python
if not pn_short:
    try:
        known = KnownPart.objects.select_related(...).get(
            part_number=pn, status="enriched"   # <-- filtra status
        )
        ...
        return result  # retorna aqui se encontrou
    except KnownPart.DoesNotExist:
        pass
```

**Ponto crítico:** o engine só encontra o registro se `status="enriched"`. Se o `fix_known_parts` criou o registro com `status="raw"` por algum motivo (campo padrão do modelo), ou se o registro simplesmente não foi criado (erro silencioso), a execução cai direto na Camada 2.

### Camada 2: Gramática da família (`engine.py`, linha ~1082)

```python
fam = fam_early
if fam:
    grammar_result = _result_from_family(pn, fam)
    ...
    grammar_complete = _grammar_emcp_ok or _grammar_cap_ok
```

Para `KMR310001M`:
- `fam.prefix = "KMR"`
- `decode_gen_map = "SAM_EMCP_GEN"` → `R → LPDDR4/4X`
- `decode_cap_map = "SAM_EMCP_CAP"` → chave `"31"` → `16GB NAND + 1GB RAM`
- `grammar_complete = True` (NAND e RAM decodificados com sucesso)

Como `grammar_complete = True`, o engine **não chama o Gemini** e retorna o resultado da gramática diretamente.

### Auto-persistência: `_persist_grammar_result` (`engine.py`, linha ~885)

```python
def _persist_grammar_result(pn, fam, result):
    _CONF_PRIORITY = {
        "confirmed": 7, "manual": 6, "distributor": 5,
        "ai_high": 4, "ai_medium": 3, "ai_low": 2, "estimated": 1,
    }
    
    part, created = KnownPart.objects.get_or_create(
        part_number=pn,
        defaults={
            "status":     "enriched",
            "confidence": "estimated",   # <-- cria com "estimated"
            **new_fields,
        },
    )

    if not created:
        existing_priority = _CONF_PRIORITY.get(part.confidence, 0)
        if existing_priority > _CONF_PRIORITY["estimated"]:
            return part  # <-- skip: não sobrescreve confirmed
        ...
```

Se o registro `confirmed` foi criado corretamente pelo `fix_known_parts`, a lógica de prioridade aqui está **correta** — `_persist_grammar_result` não sobrescreveria. O problema está antes disso.

---

## 3. Hipóteses para o `fix_known_parts` não ter criado o registro

### Hipótese A: Erro silencioso na criação

O `fix_known_parts` usa `try/except` com `continue` em caso de erro:

```python
try:
    with transaction.atomic():
        obj.save()
except Exception as e:
    self.stdout.write(self.style.ERROR(f"  ✗ Erro ao criar {pn}: {e}"))
    continue
```

Se houve uma violação de constraint (ex: `part_number` unique já existia com status diferente), o erro é impresso mas a execução continua. **Você precisa ver a saída completa do terminal** quando rodar o comando.

### Hipótese B: Registro criado com `status="raw"` herdado

Se o engine tinha rodado antes do `fix_known_parts` e criado um registro `raw` via a fila de revisão (Camada 2, linha ~1192):

```python
if not _gemini_saved_now and not grammar_complete:
    KnownPart.objects.get_or_create(
        part_number=pn,
        defaults={"status": "raw", ...}
    )
```

Para `KMR310001M` com `grammar_complete=True`, esse bloco **não executa** — correto. Mas se o PN foi buscado antes desta correção existir, pode haver um registro `raw` no banco. O `fix_known_parts` com `create=True` tenta `KnownPart.objects.get(part_number=pn)` primeiro — se encontra o `raw`, **atualiza** em vez de criar. Mas se os `fields` do fix não incluem `status`, o registro fica `raw` e o engine nunca o encontra (filtra por `status="enriched"`).

### Hipótese C: Registro criado mas sem `status="enriched"`

O `create_defaults` do `fix_known_parts` inclui `"status": "enriched"` — mas isso só é usado quando o registro **não existe** (`was_created=True`). Se o registro já existe como `raw` (criado por busca anterior ou pelo admin), o código entra no branch de atualização de campos (`changed_fields`), que só atualiza os `fields` listados, **não o `status`**.

---

## 4. O problema estrutural real: `status="enriched"` como gatekeeper

O engine usa `status="enriched"` como filtro absoluto na Camada 1. Isso foi desenhado para a época em que o Gemini existia e criava registros `raw` automaticamente para enfileiramento manual. Sem o Gemini:

- Todo chip com `grammar_complete=True` gera resultado da gramática
- `_persist_grammar_result` salva como `enriched + estimated`
- `fix_known_parts` cria/atualiza para `enriched + confirmed`
- **Tudo funciona** — desde que não haja um registro `raw` bloqueando

O risco real em 2026 (sem Gemini):

```
Fluxo problemático:
1. Operador busca KMR310001M antes do fix_known_parts existir
2. grammar_complete=True → _persist_grammar_result cria enriched+estimated com valores errados
3. fix_known_parts roda → encontra o registro existente → atualiza só os fields
4. _persist_grammar_result (na próxima busca) verifica priority:
   confirmed(7) > estimated(1) → skip → registro correto preservado ✓

Fluxo OK: este caminho na verdade funciona.

Fluxo problemático real:
1. Algum processo criou KMR310001M com status="raw"
2. engine.py linha 1044: filtra status="enriched" → não encontra → vai para gramática
3. grammar_complete=True → _persist_grammar_result → get_or_create → encontra o raw existente
4. raw.confidence não é "estimated" → update parcial sem mudar status
5. Status permanece "raw" → engine nunca usa o banco para este PN
```

---

## 5. O que investigar no novo chat

### 5.1 Verificar se o registro foi criado e qual é seu status

```python
# No Django shell
from chips.models import KnownPart
obj = KnownPart.objects.filter(part_number="KMR310001M").values(
    "part_number", "status", "confidence", "emcp_ram", "emcp_nand"
)
print(list(obj))
```

**Resultado esperado se o fix funcionou:** `status="enriched"`, `confidence="confirmed"`, `emcp_ram="LPDDR3 2GB"`

**Resultado se o registro não existe:** `[]`

**Resultado se o bug da hipótese C:** `status="raw"` ou `status="enriched"` mas com valores da gramática

### 5.2 Rodar o fix com saída completa

```bash
python manage.py fix_known_parts --pn KMR310001M
```

Observar se a saída diz:
- `✚ KMR310001M — registro CRIADO` → registro foi criado agora
- `— KMR310001M: já correto, sem alterações` → registro existe mas igual
- `⚠ Não encontrado no banco` → create=False (bug na entrada)
- `✗ Erro ao criar` → exception na criação

### 5.3 Verificar se `_persist_grammar_result` está sendo chamado

Procurar no `engine.py` onde `_persist_grammar_result` é invocado:

```python
# Verificar se há condição que impede a chamada para grammar_complete=True
if grammar_complete and not pn_short:
    _persist_grammar_result(pn, fam, grammar_result)
```

Se essa chamada acontece **antes** do `fix_known_parts` ter criado o registro com `confirmed`, ela cria o registro com `estimated`. Aí o `fix_known_parts` roda, encontra `estimated`, e pela lógica de `changed_fields` deve atualizar. Mas se os `fields` do fix incluem apenas `emcp_nand` e `emcp_ram` e não incluem `confidence`, o registro fica `enriched+estimated` com os valores corretos — o engine o encontra mas `_result_from_known` decide que `grammar_wins=True` (grammar_complete + not human_verified) e ignora os valores do banco.

### 5.4 O verdadeiro bug de `grammar_wins`

```python
# engine.py linha ~426-429
human_verified = known.confidence in ("confirmed", "manual")
grammar_wins = grammar_complete and not human_verified
```

Se o `fix_known_parts` atualiza `emcp_ram` e `emcp_nand` mas **não atualiza `confidence`**, o registro fica com `confidence="estimated"` → `human_verified=False` → `grammar_wins=True` → gramática vence → banco ignorado.

**Conclusão mais provável:** o `fix_known_parts` está atualizando os campos de capacidade mas não está atualizando `confidence` para `confirmed` em registros que já existiam com `estimated`. O fix só define `confidence` no `create_defaults` (usado apenas na criação), não nos `fields` (usados na atualização).

---

## 6. Correção proposta

### Opção A: Adicionar `confidence` nos `fields` do fix (solução pontual)

```python
{
    "pn": "KMR310001M",
    "create": True,
    "create_defaults": { ... },
    "fields": {
        "emcp_nand":  "eMMC 5.1 16GB",
        "emcp_ram":   "LPDDR3 2GB",
        "confidence": "confirmed",   # <-- ADICIONAR AQUI
        "status":     "enriched",   # <-- E AQUI para cobrir registros raw
    },
}
```

### Opção B: Corrigir o `fix_known_parts` para sempre promover `status` e `confidence` (correção sistêmica)

No loop de atualização do `fix_known_parts`, forçar `status="enriched"` e `confidence` do `create_defaults` sempre que o registro existir:

```python
# Após aplicar changed_fields:
if do_create:
    target_confidence = entry.get("create_defaults", {}).get("confidence", "confirmed")
    if obj.confidence != target_confidence:
        obj.confidence = target_confidence
        changed = True
    if obj.status != "enriched":
        obj.status = "enriched"
        changed = True
```

### Opção C: Revisar a lógica `grammar_wins` para checar `status` além de `confidence`

```python
# Considerar um registro "human_verified" também quando status="enriched"
# e os campos de capacidade foram preenchidos manualmente
human_verified = known.confidence in ("confirmed", "manual")
```

Esta opção não resolve o problema raiz mas documenta a intenção.

---

## 7. Contexto: fim do Gemini e impacto no engine

O engine foi desenhado em três camadas:

| Camada | Mecanismo | Status atual |
|--------|-----------|--------------|
| 1 | Banco exato (`status=enriched`) | Ativo |
| 2 | Gramática da família | Ativo |
| 3 | Gemini (IA externa) | **Removido** |

Com o Gemini removido, chips com `grammar_complete=False` (cap_key ausente do mapa) ficam sem resultado de capacidade — `emcp_ram` e `emcp_nand` aparecem vazios. A fila de revisão (`status=raw`) criada automaticamente na Camada 2 nunca será enriquecida por ninguém — esse mecanismo era o "pipeline Gemini → revisão manual → enriched".

**Recomendação para o novo chat:**

1. Auditar todos os registros `status=raw` no banco — eles são resquícios da era Gemini e nunca serão promovidos
2. Decidir se `_persist_grammar_result` deve criar registros como `enriched+estimated` (comportamento atual) ou se deve haver uma flag `GEMINI_ENABLED` que desativa a criação automática
3. Garantir que `fix_known_parts` sempre force `confidence` e `status` nos registros existentes, não só na criação

---

## 8. Arquivos relevantes

| Arquivo | Função |
|---------|--------|
| `chips/engine.py` | Motor de classificação — camadas 1, 2, lógica `grammar_wins`, `_persist_grammar_result` |
| `chips/management/commands/fix_known_parts.py` | Correções manuais — `create_defaults` vs `fields` (bug aqui) |
| `chips/management/commands/populate_samsung.py` | Mapas de decodificação (`SAM_EMCP_CAP`, `SAM_EMCP_GEN`) |
| `chips/models.py` | Modelo `KnownPart` — campo `status` (raw/enriched) é o gatekeeper |

---

*Relatório gerado em 2026-05-14 — sessão de investigação KMR310001M*
