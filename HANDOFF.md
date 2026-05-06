# WhatTheChip — Documento de Handoff para IA

> **Leia este arquivo ANTES de qualquer implementação.**
> Ele descreve em profundidade como o sistema funciona para que você possa ajudar com refinamentos sem precisar re-descobrir a arquitetura.

---

## O que é o WhatTheChip

Sistema web Django para classificação de chips de memória usados no mercado de reciclagem de eletrônicos. O usuário digita um Part Number (ex: `KMQE60013M`, `KLM8G1GETF`) e o sistema identifica: tipo do chip (eMCP, eMMC, UFS, LPDDR4, etc.), capacidade, marca, geração, e quando possível o dispositivo onde é usado.

**Stack:** Django 5.2 + PostgreSQL + HTMX + CSS puro (sem framework). Design system retro Windows 98/XP.

**Pasta do projeto (no servidor/local):** `chipdocs/` contém o Django project. Fora dela ficam assets estáticos, backups e documentação.

---

## Arquitetura do Engine (`chips/engine.py`)

Este é o arquivo mais importante. Entender ele é entender o sistema todo.

### Fluxo de `classify(pn_raw)` — ponto de entrada público

```
classify("KMQE60013M")
   │
   ├─ 1. KnownPart (banco exato, status=enriched)?
   │       ├─ SIM → _result_from_known(pn, known, fam)
   │       │         ↳ grammar_wins logic (veja abaixo)
   │       └─ NÃO → continua
   │
   ├─ 2. ChipFamily (gramática, prefixo conhecido)?
   │       ├─ SIM → _result_from_family(pn, fam)
   │       │         ↳ decode posicional do PN
   │       │         ↳ campos essenciais vazios? → _gemini_lookup()
   │       │         ↳ _gemini_emcp_followup() se eMCP sem RAM/NAND
   │       │         ↳ double-check remarked vs banco
   │       └─ NÃO → continua
   │
   ├─ 3. Gemini puro (prefixo desconhecido)
   │       ↳ _gemini_lookup() sem family_hint
   │       ↳ _gemini_emcp_followup() se necessário
   │       ↳ _save_gemini_to_db()
   │
   └─ 4. Fuzzy matching
           ↳ _fuzzy_candidates() via Levenshtein
           ↳ retorna sugestões para exibir no card
```

---

### Camada 1 — Banco de dados exato

```python
known = KnownPart.objects.get(part_number=pn, status="enriched")
fam   = _match_family(pn) or known.family  # gramática tem prioridade!
```

**IMPORTANTE:** `_match_family(pn)` vem ANTES de `known.family`. Isso é intencional: o Gemini pode ter salvo um `chip_type` errado (ex: "eMCP" quando deveria ser "uMCP"). A família pelo prefixo é sempre mais confiável.

Se família for encontrada → vai para `_result_from_known()` que aplica **grammar-wins logic** (veja abaixo).

---

### `_result_from_family(pn, fam)` — Decodificação posicional

Decodifica o PN usando os campos da `ChipFamily`:

```
ChipFamily.decode_cap_pos   → posição (0-based) do caractere de capacidade
ChipFamily.decode_cap_len   → quantos chars representam a capacidade (padrão: 1)
ChipFamily.decode_cap_map   → nome do DecodeMap que mapeia chars → capacidade
ChipFamily.decode_gen_pos   → posição do caractere de geração/tipo RAM
ChipFamily.decode_gen_map   → nome do DecodeMap que mapeia chars → geração/RAM
ChipFamily.decode_density_type → "pc" ou "mobile" para DRAM standalone
ChipFamily.suffix_rules     → JSON com regras de sufixo opcional
```

**Exemplo real (família KMQ — Samsung eMCP LPDDR3):**
```
PN:  K M Q E 6 0 0 1 3 M
idx: 0 1 2 3 4 5 6 7 8 9

decode_cap_pos=3, decode_cap_len=2, decode_cap_map="KMQ_CAP"
  → key = pn[3:5] = "E6"
  → DecodeMap("KMQ_CAP", "E6") → ("64GB", "4GB")  [nand=64GB, ram=4GB]

decode_gen_pos=2, decode_gen_map="EMCP_RAM_GEN"
  → key = pn[2] = "Q"
  → DecodeMap("EMCP_RAM_GEN", "Q") → ("LPDDR3", "")
```

Para eMCP: `val_primary` = NAND, `val_secondary` = RAM.
Para eMMC/UFS: `val_primary` = capacidade, `val_secondary` ignorado.

---

### Grammar-wins logic em `_result_from_known()`

Quando o PN existe no banco, mas a gramática consegue decodificá-lo completamente, a **gramática prevalece** sobre o banco. Isso permite corrigir classificações erradas apenas editando as regras da família — sem re-enriquecer o banco.

```python
grammar_complete = (
    # eMCP: tem número de capacidade em RAM e NAND
    (fam.is_emcp and _CAP_RE.search(r["emcp_ram"]) and _CAP_RE.search(r["emcp_nand"]))
    OR
    # Não-eMCP: tem capacidade ou densidade decodificada
    (not fam.is_emcp and _CAP_RE.search(r["capacity"] or r["dram_density"] or ""))
)
human_verified = known.confidence in ("confirmed", "manual", "distributor")
grammar_wins   = grammar_complete and not human_verified
```

- `grammar_wins = True` → valores da gramática substituem os do banco
- `human_verified = True` → banco sempre prevalece (alguém conferiu manualmente)

---

### Camada Gemini

**Quando é chamado:**
- Gramática reconhece a família mas não tem dados de capacidade completos
- PN completamente desconhecido (nenhum prefixo bate)

**Dois chamados possíveis:**
1. `_gemini_lookup(pn, family_hint)` — chamada principal com Google Search grounding
2. `_gemini_emcp_followup(pn, chip_type, brand)` — chamada cirúrgica só para obter RAM+NAND quando o primeiro retornou eMCP mas sem capacidades

**Modelos tentados em ordem:** `gemini-2.5-pro` → `gemini-2.5-flash`

**Para cada modelo:** tenta COM grounding primeiro, depois SEM grounding.

**Gate de cache:** `if specs.get("chip_type"): _save_gemini_to_db(pn, specs)`
— Salva SEMPRE que tiver chip_type, mesmo incompleto. Dados parciais no cache são melhores que re-chamar Gemini toda vez.

---

### Double-check remarked

Após classificar pela gramática, o engine compara com o banco:
```python
if _check_remarked(grammar_result, db_result):
    grammar_result["remarked_flag"] = True
```
`_check_remarked()` extrai GB de strings como "64GB", "512MB" e compara. Divergência > 0.1 GB acende o flag de "possível chip remarked".

---

## Modelos Django (`chips/models.py`)

### `Brand`
Fabricante. `name` + `code` (ex: "Samsung", "SAM").

### `Source`
Origem de um dado. `src_type` ∈ `("manual", "distributor", "ai", "datasheet")`.

### `ChipFamily`
Regras de decodificação de uma família de chips. **Campos críticos:**
```python
prefix          # ex: "KMQ", "KLM", "K4B"
chip_type       # ex: "eMCP", "eMMC", "LPDDR4"
subtype         # ex: "UFS 2.1", "DDR3 SDRAM"
is_emcp         # True para eMCP e uMCP (tem RAM+NAND juntos)
interface       # versão do padrão: "eMMC 5.1", "UFS 3.1"
pn_length       # comprimento canônico do PN (usado pela PIN UI para auto-trigger)
decode_cap_pos  # posição (0-based) do campo de capacidade
decode_cap_len  # quantos chars formam a chave de capacidade (padrão: 1)
decode_cap_map  # nome do DecodeMap com o mapa
decode_gen_pos  # posição do campo de geração/tipo RAM
decode_gen_map  # nome do DecodeMap
decode_density_type  # "pc" ou "mobile" para DRAM standalone
suffix_rules    # JSON: {"sufixo": {"note": "descrição"}}
doc_page        # FK para Page (documentação vinculada)
tip / reasoning # textos de contexto para exibição
active          # False = família ignorada na classificação
priority        # menor = verificado primeiro (0 = máxima prioridade)
```

### `DecodeMap`
Tabela de lookup. `(map_name, char_key) → (val_primary, val_secondary)`.
Um `map_name` pode ser compartilhado entre famílias (ex: `"EMCP_RAM_GEN"` usado por todas as famílias Samsung KM*).

### `KnownPart`
Chips conhecidos. `status` ∈ `("raw", "enriched", "failed")`.
`confidence` ∈ `("confirmed", "manual", "distributor", "ai_high", "ai_medium", "ai_low", "estimated")`.

### `SearchLog` / `UnknownChip`
Log de buscas e chips nunca encontrados. Usados para métricas e backlog de enriquecimento.

### `CorrectionRequest`
Erros reportados por usuários via botão "Reportar erro" no decode card.
`status` ∈ `("pending", "fixed", "rejected")`.
Admin tem actions `mark_fixed` / `mark_rejected`.

---

## UI — PIN Input (`_content/index.html`)

A barra de busca é uma UI de PIN segmentada: cada caractere é uma caixinha visual. O input real fica oculto (`position: fixed; opacity: 0; left: -9999px`) e toda interação do teclado vai para ele.

**Fluxo JS:**
```
usuário digita → render(q) chamado
  ├─ bestMatch(q)  → detecta família pelo prefixo mais longo
  ├─ renderBoxes(value, targetLen) → atualiza DOM das caixinhas
  ├─ updateHint(fam) → exibe "Samsung · eMCP · 10 chars" acima
  └─ se q.length >= fam.pn_length → callApi(q) imediato
     se não → debounce 500ms → callApi(q)
```

`callApi(q)` faz `GET /chips/decode/?pn=Q` via HTMX e o servidor retorna HTML do decode card.

**PREFIX_DATA** — injetado na página pelo servidor como JSON:
```json
[
  {"prefix": "KMQ", "chip_type": "eMCP", "brand": "Samsung", "subtype": "...", "pn_length": 10},
  ...
]
```

---

## URLs e Views

```
GET  /chips/search/?pn=XXXX  → JSON (chips/views.py :: search_api)
GET  /chips/decode/?pn=XXXX  → HTML parcial HTMX (decode_html)
POST /chips/report/           → registra CorrectionRequest (report_error)
GET  /chips/stats/            → JSON com totais do banco (stats_api)
```

---

## Testes (`chips/tests.py`)

```bash
python manage.py test chips --settings=core.settings_test
```

39 testes cobrindo: decode posicional, eMCP dual-output, grammar-wins, remarked detection, fuzzy matching, views (search_api, decode_html, report_error).

`core/settings_test.py` usa SQLite em memória e desativa Gemini (sem `GEMINI_API_KEY`).

---

## Comandos úteis

```bash
# Rodar servidor
cd chipdocs && python manage.py runserver

# Popular famílias Samsung
python manage.py populate_samsung

# Rodar testes
python manage.py test chips --settings=core.settings_test

# Aplicar migrations
python manage.py migrate

# Enriquecer chips raw com Gemini
python scripts/enrich_gemini.py
```

---

## Estado atual do sistema (maio/2026)

### O que está funcionando
- ✅ Famílias Samsung completas: KLM (eMMC), KLU (UFS), KMK/KMF/KMN/KMQ/KMS/KMR (eMCP), KMD/KMG/KML/KMV (uMCP)
- ✅ Famílias Samsung DRAM: K4B (DDR3), K4F (DDR3L), K4E (LPDDR3), K4U (LPDDR4), K3 (LPDDR5)
- ✅ Samsung NAND: K9F, K9G, K9K, K9W, K9L, K9H, K9X, K9Z
- ✅ PIN UI com auto-trigger por `pn_length`
- ✅ Grammar-wins: corrigir regras corrige resultados imediatamente
- ✅ CorrectionRequest: usuários reportam erros, admin resolve
- ✅ Cache Gemini: salva mesmo resultados parciais
- ✅ `classification_source` exibido no decode card
- ✅ Animação de loading retro (reticências)
- ✅ Botão "Reportar erro" com HTMX inline

### O que NÃO está feito (backlog)
- ❌ Famílias SK Hynix (H9TQ, H9HP, H26M, H8 NAND)
- ❌ Famílias Micron (MTFC eMMC, MT29 NAND, D9 DRAM)
- ❌ Famílias Kioxia/Toshiba (THGBM, THGAF)
- ❌ Famílias Kingston, SanDisk
- ❌ Páginas de anatomia por família (doc_page ligada à ChipFamily)
- ❌ Dashboard de métricas (buscas por dia, chips mais pesquisados)
- ❌ Busca fuzzy melhorada (Levenshtein já existe, mas threshold e UX podem melhorar)
- ❌ API pública documentada (Swagger/OpenAPI)
- ❌ Exportação CSV do banco de KnownParts
- ❌ Script de importação em massa (CSV → KnownPart)

---

## Padrão para adicionar uma nova família de chips

1. **No admin** (ou no comando `populate_*`):
   ```python
   fam = ChipFamily.objects.update_or_create(
       prefix="H9TQ",
       defaults={
           "brand":          brand_hynix,
           "chip_type":      "eMCP",
           "subtype":        "eMMC 5.1 + LPDDR3",
           "is_emcp":        True,
           "interface":      "eMMC 5.1",
           "pn_length":      14,   # comprimento canônico do PN
           "decode_cap_pos": 4,
           "decode_cap_len": 2,
           "decode_cap_map": "H9TQ_CAP",
           "active":         True,
           "priority":       10,
       }
   )
   ```

2. **DecodeMap** para a capacidade:
   ```python
   DecodeMap.objects.get_or_create(map_name="H9TQ_CAP", char_key="26", defaults={"val_primary": "32GB", "val_secondary": "2GB"})
   DecodeMap.objects.get_or_create(map_name="H9TQ_CAP", char_key="51", defaults={"val_primary": "64GB", "val_secondary": "4GB"})
   # etc.
   ```

3. **Testes:** adicionar um teste em `chips/tests.py`:
   ```python
   def test_h9tq_emcp(self):
       result = classify("H9TQ32A4GBAR")
       self.assertTrue(result["known"])
       self.assertEqual(result["chip_type"], "eMCP")
       self.assertIn("32GB", result["emcp_nand"])
   ```

---

## Dicas para depuração

**Chip classificando errado:**
1. Verificar se `ChipFamily` tem o prefixo correto e `active=True`
2. Verificar `DecodeMap` para o `map_name` da família
3. Se `grammar_wins=False` (banco prevalece), checar `KnownPart.confidence` — se for `ai_*`, a gramática deveria estar vencendo
4. Checar se `_CAP_RE` consegue extrair número do resultado da gramática (ex: "eMMC 5.1" sem GB → não extrai → gramática incompleta → banco prevalece)

**Gemini sendo chamado toda vez:**
- O `KnownPart` foi salvo? Checar no admin se existe com `status=enriched`
- Se existir mas o Gemini ainda é chamado: `_match_family(pn)` não está retornando família → prefixo errado ou família inativa

**PIN UI não auto-triggering:**
- `pn_length` está definido na família?
- `PREFIX_DATA` no HTML tem `pn_length` para aquela família? (vem de `pages/views.py`)

---

## Arquivos-chave

```
chipdocs/
├── chips/
│   ├── engine.py          ← classificação (arquivo mais importante)
│   ├── models.py          ← Brand, ChipFamily, DecodeMap, KnownPart, CorrectionRequest
│   ├── views.py           ← search_api, decode_html, report_error, stats_api
│   ├── urls.py            ← roteamento
│   ├── admin.py           ← admin Django para todos os modelos
│   ├── tests.py           ← 39 testes automatizados
│   ├── migrations/        ← histórico de migrations
│   ├── templates/
│   │   └── chips/
│   │       └── partials/
│   │           └── decode_card.html  ← card de resultado (HTMX partial)
│   └── management/
│       └── commands/
│           └── populate_samsung.py  ← popula famílias Samsung
├── pages/
│   ├── models.py          ← Page (páginas de documentação)
│   └── views.py           ← homepage + PREFIX_DATA injetado
├── _content/
│   └── index.html         ← homepage com PIN UI (JS inline)
├── static/
│   └── css/
│       └── style.css      ← CSS completo (design system retro)
├── scripts/
│   └── enrich_gemini.py   ← script standalone de enriquecimento em lote
└── core/
    ├── settings.py        ← settings principal
    └── settings_test.py   ← settings para testes (SQLite, sem Gemini)
```
