# Status — Correção do lote #039 — 2026-06-17

> Tracker da limpeza/correção da contaminação do lote #039 (typos do operador em
> 16/06). Atualizar conforme as confirmações por marca chegam. Código é a fonte
> da verdade.

## ✅ Concluído

- **SK Hynix (3):** `H26T87001CMB→H26T87001CMR` (merge), `H26M78103CCR` e
  `H9HP16AECMMD` (refresh). KnownParts confirmados via `add_confirmed_part.py`.
- **Samsung — 11 merges fuzzy em alvo confirmado** (`correcoes_samsung_confirmados.csv`):
  aplicados. `KLM8G1GETF` fechou em **97** após o fix do bug de merge acumulado.

## ⏳ Pendente — correções de estoque

### A. Merges fuzzy aguardando confirmação do alvo (8) — `correcoes_samsung_pendentes.csv`
Alvos a confirmar primeiro: **KMQX60013M, KMQN10006M, KMQN1000GB, KMFN10012M,
KMGX6001BM, KLM8G1GETP** (5 são `raw` → só promover a `enriched`). Confirmar →
`audit_targets` (ver virar CONFIRMADO) → `fix_pns --commit`.

### B. Correções de specs no banco (5) — do chat Samsung, ação `fix_known_parts`
Depois de corrigir o KnownPart, **refresh** da entrada no estoque (`fix_pns`):
- KMR820001M → **2GB** LPDDR3 (⚠ no estoque está como `KMR820001M-B609` — decidir se renomeia para `KMR820001M`)
- KMQ820013M → eMMC 5.1 16GB + 2GB LPDDR3 (não estava no DB)
- KMFJ20007M → eMMC **4GB + 512MB** LPDDR3 (corrige erro grande: mostrava 128GB+6GB)
- KMFJ20005A → eMMC **4GB + 512MB** LPDDR3
- KMFE10012M → eMMC 5.1 16GB + **1GB** LPDDR3

### C. Merges para alvo diferente do fuzzy (5) — verificar alvo, depois merge
- KMF720013M → KMF720012M
- K4FBE3D → K4F8E3D · K4EBE30 → K4F8E3D (alvo é gramática-correta)
- KMFN6612B → KMFN60012B (alvo confirmado)
- KLMBD4WEBD → KLMBG4WEBD (alvo confirmado / já correto no DB)

### D. PN já correto, só confirmar specs (1)
- KMF310012M (fuzzy tinha errado; PN está certo)

### E. Sem ação de specs — gramática/já correta (6)
K4W2G1646S, K4E6E304ED, K4B4G1646B, K4B2G0446D, K4B2G0446C, K3QF7F70DM.
Corretos, mas ainda com fonte **"gramática"** → serão cobertos pelo `bless_base`
para o bloqueio "só confirmados" não travar a reposição deles.

### F. Perdido (1)
KML7U00HM — decidir: deixar a 1 unidade como está, ou removê-la do estoque.

## ⏳ Pendente — infraestrutura

1. **Commit + push do fix do `fix_pns.py`** (bug de merge acumulado) — produção ainda tem a versão antiga.
2. **`migrate` na Render** (tabela `PendingEntry`) — senão o bloqueio "só confirmados" quebra ao barrar um chip.
3. **`bless_base`** — abençoar a base para o gate não travar reposição dos comuns (inclui os 6 do item E).
4. **Reiniciar/redeploy** após mudanças de dados/gramática (cache `lru` do engine — regra de ouro #3).
5. **Chat SK:** fix do `H9HP` (família `pn_length=14` faz o engine pular PN de 12 chars) + re-refresh.

## Ordem recomendada

1. `fix_known_parts` com as specs do item **B** (você / chat Samsung).
2. Confirmar os 6 alvos do **A** + o `KMF720012M` do **C**.
3. `audit_targets` nos CSVs pendentes para ver tudo virar CONFIRMADO.
4. `fix_pns --commit`: **A** (pendentes) + **B** (refresh) + **C** (merges) + **D**.
5. `bless_base` (item E + base) → commit/push do fix → `migrate` → restart.
