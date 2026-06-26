# Handoff — Remoção do Gemini e do campo `status` (2026-06-26)

> **HISTÓRICO / changelog de sessão.** Registro do que foi feito. A fonte da
> verdade é o código (`chips/engine.py`, `chips/models.py`) e o `CLAUDE.md`.

## O que mudou

1. **Gemini REMOVIDO por completo.** Saíram do engine todas as funções
   (`_gemini_lookup`, `_gemini_emcp_followup`, `_save_gemini_to_db`,
   `_build_result_from_gemini`, `_get_api_key`, `_gemini_api_call`,
   `_extract_json_from_text`, `_specs_are_complete`, prompts e a lista de
   modelos) e os dois call-sites em `classify()`. As flags `GEMINI_ENABLED` /
   `GEMINI_API_KEY` saíram de `core/settings.py`. O script
   `scripts/enrich_gemini.py` foi **deletado**. Função morta
   `_persist_grammar_result` também removida.

2. **Campo `KnownPart.status` REMOVIDO** (raw/enriched/failed). O engine não usa
   mais o gate `status="enriched"`. **Novo gate:** um KnownPart é autoritativo
   (vence a gramática, entra no estoque como confirmado) **só quando
   `confidence` ∈ (`confirmed`, `manual`)**. Isso já era a precedência real em
   `_result_from_known`; o `status` era redundante.

3. **Níveis de IA removidos** de `KnownPart.confidence` (`ai_high`/`ai_medium`/
   `ai_low`) e o tipo `"ai"` de `Source.SOURCE_TYPES`. Ladder agora:
   `confirmed` > `manual` > `distributor` > `estimated`.

4. **Fila de revisão raw removida.** `classify()` não cria mais
   `KnownPart(status="raw")` a cada busca. Rastreamento de buscas fica em
   `SearchLog`; PNs que o operador tenta lançar e não são confirmados vão para
   `PendingEntry` (fila de conferência do estoque). O double-check de chip
   remarked foi preservado.

## Implicações verificadas (o que o usuário pediu para checar)

- **Rentabilidade intacta.** `assess_profitability` / `is_dead_by_generation`
  dependem só do `result` dict — nunca tocavam `status`. Cobertas por testes
  novos (eMCP, LPDDR2 por geração, eMMC pequeno, ePoP, GDDR2, DDR3, e a
  derivação geração × capacidade do `is_dead_by_generation`).
- **Fuzzy intacto.** As três queries fuzzy filtravam `status="enriched"` mas já
  restringiam a `confidence ∈ confirmed/manual`; só o `status` saiu do filtro.
  Coberto por teste de sugestão.

## Arquivos tocados (resumo)

- `chips/engine.py` — Gemini removido; lookups e fuzzy passam a filtrar por
  `_CONFIRMED_CONFIDENCE = ("confirmed","manual")`; fila raw removida.
- `chips/models.py` — campo `status`, `STATUS_CHOICES`, `is_enriched`, `ai_*`,
  Source `"ai"` removidos.
- `chips/migrations/0012_remove_knownpart_status_alter_knownpart_confidence_and_more.py`
  — RemoveField status + AlterField das choices.
- `chips/admin.py`, `chips/views.py` — sem status/ai/gemini.
- `estoque/admin.py`, `estoque/management/commands/{bless_base,audit_targets,list_unconfirmed}.py`.
- `chips/management/commands/*` e `scripts/*` — `status=` removido (≈490 linhas
  de templates em `fix_known_parts.py`).
- Templates `decode_card.html` e `estoque.html` — ramos Gemini removidos.
- `chips/tests.py` — reescrito (53 testes, todos verdes).
- `chips/management/commands/purge_enriched.py` — virou o comando de limpeza
  pós-migração.

## Passos de deploy (executar nesta ordem — o agente NÃO roda no banco)

```bash
git push origin main                      # auto-deploy no Render
python manage.py migrate                  # aplica 0012 (dropa a coluna status)
python manage.py purge_enriched           # DRY-RUN: confira o que será apagado
python manage.py purge_enriched --commit  # apaga ai_*/estimated/fila raw (backup JSON antes)
# reiniciar o serviço web no Render (cache lru do engine — regra de ouro #3)
```

`purge_enriched` mantém `confirmed`/`manual` (e `distributor`, salvo
`--include-distributor`). Backup JSON é gravado antes de apagar.

## Correção do gate (mesma data) — regressão de reconhecimento

A primeira versão estreitou o gate de visibilidade da camada 1 para
`confidence ∈ (confirmed, manual)`. Isso escondeu os MUITOS registros que eram
`status="enriched"` mas `confidence="distributor"`/`"estimated"` (imports de
distribuidor Micron/Samsung, preduo/wayback, import_chipid, auto-persist antigo):
eles deixaram de ser reconhecidos (`known_exact` virou `false`, caíam em gramática
pura) — em todas as marcas.

**Causa:** o antigo `status="enriched"` casava QUALQUER confidence desde que o
registro tivesse dados; trocar por confidence-only foi estreito demais.

**Correção (`chips/engine.py`, gate `_USABLE`):** um registro é *reconhecido* na
camada 1 quando tem **specs reais** (capacity/emcp_ram/emcp_nand/density) **OU** é
`confirmed`/`manual`. Placeholders vazios (a antiga fila raw) ficam de fora.
**Visibilidade ≠ autoridade:** distribuidor/estimado com specs voltam a aparecer
(`known_exact=True`), mas só `confirmed`/`manual` vencem a gramática completa
(`_result_from_known` inalterado).

**`purge_enriched` endurecido:** por padrão apaga só `ai_*` (Gemini) e `estimated`
SEM specs (fila raw vazia). **Mantém** `distributor` e `estimated` COM specs (são
dados usados pelo engine). `--include-estimated`/`--include-distributor` para nuke
explícito. ⚠ Se você rodou a versão anterior do `purge_enriched --commit`, há um
`purge_enriched_backup_*.json` para restaurar.

**Diagnóstico:** `python manage.py diag_pn KMFN10012M SDIN7DU2-8G H9CKNNNDJTMP`
mostra, por PN, o KnownPart no banco (confidence + specs), se o gate casa, e a
saída do `classify()`.

## Testes

`python manage.py test chips --settings=core.settings_test` → **54 testes OK**
(inclui: distribuidor/estimado com specs reconhecidos mas gramática vence;
placeholder vazio não reconhecido).
