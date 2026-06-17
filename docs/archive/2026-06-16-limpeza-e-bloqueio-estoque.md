# 2026-06-16 — Limpeza do lote #039 + bloqueio "só confirmados" no estoque

> **Documento operacional / histórico.** O código é a fonte da verdade
> (`estoque/`, `chips/engine.py`). Confirme antes de agir.

## Contexto
O operador, ao popular o estoque pelo site, digitou alguns PNs errados e adicionou
chips que não estavam na base. Diagnóstico do export `lote_039_20260616_2201.xlsx`:
a contaminação são **PNs novos não confirmados criados em 16/06** — 39 deles com
Qtd 1 (≈25 são typos óbvios de chips reais, ex.: `KMGD6001MB`↔`KMGD6001BM`,
`KMQN100063`↔`KMQN10006B`). A planilha exporta `last_updated`, que não distingue
restock de PN novo; por isso a limpeza precisa usa `added_at` (data real de
criação), que só existe no banco.

## O que foi entregue (código)
- **`estoque/management/commands/clean_lote.py`** — remove de um lote os PNs
  criados a partir de `--since` que **não** são confirmados (`classification_source`
  != "banco de dados" e confidence != confirmed/manual). Dry-run por padrão,
  `--keep` para poupar, `--commit` aplica, `--revert` desfaz (snapshot JSON).
- **`estoque/management/commands/bless_base.py`** — "abençoa" a base: promove os
  PNs já lançados **antes** de `--since` a `KnownPart` `confidence="manual"`,
  `status="enriched"`. Ponte para o bloqueio não travar a reposição dos comuns.
  Dry-run por padrão, reversível. **Reinicie o servidor após `--commit`** (cache
  do engine, regra de ouro #3).
- **Bloqueio "só confirmados"** em `estoque/views.py::add_chip`: reclassifica no
  servidor (não confia no `hidden` do form). Se o PN não é confirmado, **não entra
  no estoque** — vai para `PendingEntry` (fila de conferência). UI: o botão vira
  "⏳ Enviar para conferência" (`confirm_card.html`) e o operador recebe
  `pending_feedback.html` ("separe fisicamente e avise o gestor").
- **`PendingEntry`** (novo modelo + migration `0007_pendingentry.py`) e
  **`PendingEntryAdmin`** com ações **Aprovar** (move ao estoque + cria KnownPart
  manual → vira confirmado) e **Reprovar** (descarta). Fila em
  `/admin/estoque/pendingentry/`.

## Ordem de execução (você roda; o agente só edita — regra de ouro #1)

Tudo abaixo apontando para o Postgres do Render. **Conectar:** Render → seu
Postgres → aba *Connections* → copie a **External Database URL** e, no projeto
local com o venv ativo:

```bash
export DATABASE_URL="postgresql://...@...render.com/...?sslmode=require"
# ⚠ a partir daqui, qualquer manage.py escreve na PRODUÇÃO
```

1. **Backup primeiro.** No Render, tire um snapshot do Postgres.
2. **Limpar a contaminação (dry-run → conferir → aplicar):**
   ```bash
   python manage.py clean_lote --lot 39 --since 2026-06-16            # só lista
   python manage.py clean_lote --lot 39 --since 2026-06-16 --keep PNX,PNY   # poupa legítimos
   python manage.py clean_lote --lot 39 --since 2026-06-16 --commit   # remove
   # desfazer: python manage.py clean_lote --lot 39 --revert
   ```
3. **Criar a tabela da fila** (migration aditiva, segura):
   ```bash
   python manage.py migrate estoque
   ```
4. **Abençoar a base** (para o bloqueio não barrar reposição dos comuns):
   ```bash
   python manage.py bless_base --lot 39 --since 2026-06-16            # dry-run
   python manage.py bless_base --lot 39 --since 2026-06-16 --commit   # aplica
   # depois: REINICIE o servidor (cache do engine)
   ```
5. **Subir o código** (gate + admin + templates): commit + push para `main`
   → Render faz auto-deploy e reinicia (limpa o cache). Garanta que o deploy
   aplica as migrations (ver `DEPLOY_RENDER.md`).
6. **Verificar:** busque um chip da base (deve **adicionar**); um typo
   (ex.: `KMQN100063`) deve ir para **conferência**. Revise a fila em
   `/admin/estoque/pendingentry/` e use **Aprovar**/**Reprovar**.

## Manutenção contínua
A fila é o seu funil de curadoria: cada **Aprovar** cria um `KnownPart` manual e
expande o banco de confirmados (o objetivo do produto). Com o tempo, menos chips
caem na fila. Reinicie o servidor após aprovar em lote (novos confirmados no cache).
