# Plano de implementação — Gateway do Estoque (3 fases)

> **Status:** PLANO — nada implementado ainda. Documento de handoff para a sessão
> que vai codar (Claude implementa 100%).
> **Data:** 17/06/2026.
> **Leia antes:** `CLAUDE.md` (regras de ouro) e o briefing-fonte
> `docs/archive/2026-06-17-brainstorm-gateway-4etapas.md`. Este plano **corrige**
> dois pontos do briefing (ver abaixo) — onde houver conflito, **este plano vence**.

---

## Decisões travadas (não reabrir)

1. **Conservador:** `INDETERMINADO` → **APROVADO**. Melhor deixar entrar do que perder material.
2. **NÃO RENTÁVEL → bloqueio DURO no backend** (não é só UI): o chip confirmado e
   não-rentável é desviado para `RejectedEntry` e **não** entra no estoque.
3. **3 etapas de funil + banner de digitação separado** (o typo não é uma 4ª etapa).
4. **Não mexer no gate "só confirmados" que já roda** (`_is_confirmed`, desvio para
   `PendingEntry`). A gramática→fila continua como está.

## Correções aplicadas vs o briefing

- **Ordem do funil invertida.** O briefing checava *Fonte* antes de *Specs*, o que
  mandaria **todo PN não identificado para a FILA** (em vez de DESCONHECIDO) e
  inundaria a fila do gestor com lixo. Ordem correta: **1) Identificação (specs) →
  2) Fonte (confirmado) → 3) Rentabilidade.**
- **REPROVADO precisa de um botão que faz POST.** No briefing o card reprovado não
  tinha submit, então o `RejectedEntry` nunca seria gravado (código morto). Aqui o
  card reprovado ganha um botão **"Registrar descarte"** que posta — e o backend
  (Fase 1) já desvia para `RejectedEntry`. Auditoria passa a funcionar de fato.

## Achado: botão de debug (📋) — incremento confirmado

Investigado o botão "📋" que copia o diagnóstico/JSON da classificação. Como funciona:

- O handler usa **event delegation** no `document` (sobrevive a swaps do HTMX): clica
  em `.est-debug-btn` → acha o ancestral `[data-debug]` → faz `JSON.parse` do atributo
  `data-debug` → monta um relatório rico (`buildDebugText`) e copia para o clipboard.
- Hoje o `data-debug="{{ result_json }}"` e o botão **só existem no card identificado**
  (`has_cap`); o card de "não identificado" não tem nenhum dos dois.
- **`preview_chip` já injeta `result_json` em todos os caminhos** — o dado é de graça.

**Incremento (Fase 2):** colocar `data-debug="{{ result_json }}"` no **root único** do
card (vale para os 4 destinos) e renderizar o **📋 em todos os destinos** — em especial
no **DESCONHECIDO**, onde diagnosticar "por que não reconheceu?" é o caso de maior valor.
**O JS não muda** (delegation + lookup `[data-debug]` já são genéricos). Custo ~zero,
ganho de diagnóstico em toda a triagem.

## Fora de escopo (não fazer agora)

- Interface de triagem de `UnknownChip` (briefing §8) — fica para depois.
- Qualquer coisa com `remarked_flag` — ignorado neste refactor.
- **Não** apertar a semântica de `_is_confirmed` (fonte vs confiança) — manter como
  está; é comportamento de produção que já funciona.

## Pré-requisitos para testar no localhost

- **Branch:** trabalhar em `feature/gateway-estoque`, testar local, só então `push`
  → merge em `main` (Render publica sozinho). Não codar direto na `main`.
- **Dados:** o engine só enxerga `KnownPart status="enriched"`. Para exercitar os 4
  destinos é preciso ter no Postgres **local** alguns PNs confirmados de perfis
  variados (rentável, não-rentável, indeterminado). Rodar o pipeline curado local
  (`populate_*` + `import_*` + `fix_known_parts`) basta; réplica exata da produção
  só com `pg_dump` (o **usuário** roda — agente não acessa o banco de produção).
- **Migrations:** `makemigrations`/`migrate` são executados pelo **usuário**
  (regra de ouro #1). O agente edita; o usuário roda e confirma.
- **Testes:** sempre com `--settings=core.settings_test` (SQLite em memória, Gemini off).

---

## FASE 1 — Fundação no backend (aditivo, testável "headless")

**Objetivo:** ter o "cérebro" do gateway e o bloqueio duro funcionando, **sem ainda
mexer no visual do card**. Tudo que muda no fluxo vivo é: *chip confirmado e
não-rentável passa a ser barrado e auditado* — exatamente o alvo.

**Arquivos:**
- `estoque/models.py` — novo modelo `RejectedEntry` (ver briefing §5 para os campos).
- `estoque/admin.py` — registrar `RejectedEntryAdmin` (ver briefing §5).
- `estoque/views.py` — adicionar `_compute_gateway()` (versão **corrigida**, apêndice
  A) e inserir o bloqueio duro em `add_chip`.
- `estoque/templates/estoque/partials/rejected_feedback.html` — novo (ver briefing §6).
- `estoque/tests.py` (ou `estoque/tests/`) — testes do gateway e do desvio.

**O que muda em `add_chip`:** após o bloco que já existe do `_is_confirmed`
(desvio para `PendingEntry`) e **antes** de criar o `InventoryEntry`, inserir:

```python
profitable_check = assess_profitability(server_result)
if profitable_check == "NÃO RENTÁVEL":
    RejectedEntry.objects.create(... snapshot ..., rejection_reason="NÃO RENTÁVEL",
                                 operator=request.user)
    return render(request, "estoque/partials/rejected_feedback.html",
                  {"pn": pn, "qty": qty, "chip_type": ..., "capacity": ...})
```

Nada mais em `add_chip` muda. Confirmado+rentável → estoque (como hoje);
confirmado+indeterminado → estoque (regra conservadora, pois não é "NÃO RENTÁVEL");
não-confirmado → `PendingEntry` (inalterado); `has_cap=false` → `UnknownChip` (inalterado).

**Critério de aceite (como você testa a Fase 1):**
1. `python manage.py test estoque --settings=core.settings_test` — verde. Os testes
   afirmam o destino de `_compute_gateway(classify(pn), has_cap)` para a matriz:
   confirmado+rentável→`aprovado`; confirmado+não-rentável→`reprovado`;
   confirmado+indeterminado→`aprovado`; só-gramática→`fila`; lixo→`desconhecido`.
2. No **card atual** (sem redesign), adicionar um confirmado **não-rentável** →
   aparece `rejected_feedback`, **nada** entra no estoque, e o registro surge em
   `/admin/estoque/rejectedentry/`.
3. Regressão rápida: confirmado **rentável** ainda entra; gramática ainda vai para a
   fila; lixo ainda vira desconhecido.

---

## FASE 2 — UI do card (o porteiro visível)

**Objetivo:** trocar o card de "tela de informação" por um **semáforo que já decidiu**,
mostrando destino + barra de 3 etapas + botão certo, com o banner de typo separado.

**Arquivos:**
- `estoque/views.py` — `preview_chip` passa o `gateway` no contexto (`gateway_dest`,
  `gateway_steps`, `typo`; manter `profitable`/`profitable_key` por retrocompat).
- `estoque/templates/estoque/partials/confirm_card.html` — reescrita (estrutura no
  briefing §4.3, **com a ordem/rótulos corrigidos** do apêndice A).
- `estoque/templates/estoque/estoque.html` — CSS da barra e dos destinos.

**O que muda:**
- **Barra de 3 etapas** (não 4): `1 · Reconheci` · `2 · Confirmado` · `3 · Rentável`.
  Estados `pass`/`fail`/`skip` (sem `warn` — o typo saiu da barra).
- **Bloco de destino condicional** por `gateway_dest`: `aprovado` (caixa colorida por
  tecnologia), `fila` (laranja), `desconhecido` (cinza/?), `reprovado` (vermelho).
- **Botões condicionais:** aprovado→"+ Adicionar ao estoque"; fila→"⏳ Enviar para
  conferência"; desconhecido→"Registrar como desconhecido"; **reprovado→"Registrar
  descarte" (submit)** + Cancelar/📋.
- **`has_cap` correto em cada form** para o backend rotear: aprovado/fila/reprovado
  postam `has_cap=true`; desconhecido posta `has_cap=false`. (O reprovado posta
  `true` e o backend da Fase 1 já o desvia para `RejectedEntry`.)
- **Banner de typo separado:** bloco "Você quis dizer?" com `typo.suggestions`,
  exibido **fora** da barra, em qualquer destino que tenha sugestões.
- **Debug (📋):** `data-debug="{{ result_json }}"` no root único do card e o botão
  `.est-debug-btn` presente em **todos** os destinos (inclusive desconhecido). JS intocado.
- **Estética:** `border-radius: 0` (IBM Carbon White) — não introduzir cantos
  arredondados novos.

**Critério de aceite (como você testa a Fase 2):** digitar um PN de cada caso e
conferir, visualmente, cor do destino + estados da barra + botão correto:
confirmado rentável (verde, Adicionar) · confirmado não-rentável (vermelho, Registrar
descarte) · indeterminado confirmado (verde) · só-gramática (laranja, Enviar p/
conferência) · lixo (cinza, Registrar desconhecido) · PN com typo (banner "Você quis
dizer?" aparecendo junto). Clicar cada botão e confirmar que o backend responde
coerente (estoque / fila / reprovado / desconhecido).

---

## FASE 3 — Acabamento e verificação

**Objetivo:** fechar arestas de UX e provar que nada regrediu.

**Escopo:**
- **Banner de typo:** garantir que não duplica com avisos antigos e que a cópia está
  clara; aparece em todos os destinos quando há `fuzzy_suggestions`.
- **Lote fechado:** no card, ocultar/desabilitar o botão de adicionar quando
  `not lot.is_open` (hoje o erro só aparece no submit) — melhoria barata já que
  estamos no card.
- **Edge cases conscientes:** eMCP meio-decodificado (NAND sem RAM) → `INDETERMINADO`
  → aprovado; exibir sem dar falsa confiança. `known_exact` sem `chip_type` →
  desconhecido.
- **Verificação final:**
  - `python manage.py test chips --settings=core.settings_test` + os testes de
    regressão do engine (`test_samsung_*.py`, `test_psg_*.py`).
  - `python manage.py test estoque --settings=core.settings_test`.
  - Matriz manual do briefing §9 ponta a ponta; screenshots dos 4 destinos.
  - Conferir que `export_xls` e `remove_entry` seguem intactos.
  - Revisar o diff completo (idealmente um subagente de verificação) antes do merge.

**Critério de aceite:** suíte verde, matriz §9 ok nos prints, diff revisado, sem
regressão no fluxo confirmado/rentável nem na fila de gramática.

---

## Apêndice A — `_compute_gateway()` (versão corrigida: identificação → fonte → rentabilidade)

```python
def _compute_gateway(result: dict, has_cap: bool) -> dict:
    """3 etapas de funil + typo separado. Ordem: identificação → fonte → rentabilidade.
    INDETERMINADO conta como aprovado (regra conservadora)."""
    fuzzy = result.get("fuzzy_suggestions") or []
    steps = [
        {"id": "identificacao", "label": "Reconheci",  "status": "skip", "detail": ""},
        {"id": "fonte",         "label": "Confirmado",  "status": "skip", "detail": ""},
        {"id": "rentabilidade", "label": "Rentável",    "status": "skip", "detail": ""},
    ]
    typo = {"has": bool(fuzzy), "suggestions": fuzzy}

    # 1) Identificação (specs reais)
    if not has_cap:
        steps[0].update(status="fail", detail="specs ausentes")
        return {"destination": "desconhecido", "steps": steps, "typo": typo,
                "profitable": "", "profitable_key": "indeterminado"}
    steps[0].update(status="pass", detail="specs reais")

    # 2) Fonte (confirmado no banco) — NÃO altera _is_confirmed
    if not _is_confirmed(result):
        steps[1].update(status="fail",
                        detail=result.get("classification_source", "gramática"))
        return {"destination": "fila", "steps": steps, "typo": typo,
                "profitable": "", "profitable_key": "indeterminado"}
    steps[1].update(status="pass", detail="banco de dados")

    # 3) Rentabilidade (conservador: INDETERMINADO -> aprovado)
    profitable = assess_profitability(result)
    prof_key = {"RENTÁVEL": "rentavel", "NÃO RENTÁVEL": "nao_rentavel",
                "INDETERMINADO": "indeterminado"}.get(profitable, "indeterminado")
    if profitable == "NÃO RENTÁVEL":
        steps[2].update(status="fail", detail="Não rentável")
        return {"destination": "reprovado", "steps": steps, "typo": typo,
                "profitable": profitable, "profitable_key": prof_key}
    steps[2].update(status="pass",
                    detail="Rentável" if profitable == "RENTÁVEL" else "Indeterminado (aprovado)")
    return {"destination": "aprovado", "steps": steps, "typo": typo,
            "profitable": profitable, "profitable_key": prof_key}
```

> Nota: o `assess_profitability` é recomputado aqui e de novo em `add_chip` (Fase 1).
> É barato e necessário — o caminho de banco exato nem sempre seta `result["profitable"]`,
> então não dá para confiar nesse campo. Não adicionar chamadas extras de `classify()`.
