<!--
Comunicado para enviar a CADA chat de marca (Samsung, SK Hynix, Micron, SanDisk,
PieceMakers, GigaDevice, Nanya, Toshiba/Kioxia, etc.). Cole o bloco abaixo no chat
da marca; ele é genérico ("sua marca") e não precisa de substituição.
-->

# Comunicado: remoção do Gemini e do campo `status` (jun/2026)

Houve uma mudança estrutural no WhatTheChip, **já aplicada no código**. Antes de
continuar com qualquer entrada da sua marca, leia e ajuste o que for seu.

## O que mudou

1. **Gemini REMOVIDO** por completo — sem fallback de IA, sem `scripts/enrich_gemini.py`,
   sem `GEMINI_*` em `settings`. Specs entram só por confirmação manual/datasheet.
2. **Campo `KnownPart.status` REMOVIDO** — acabaram `raw` / `enriched` / `failed`.
3. **Níveis de IA removidos** — `ai_high` / `ai_medium` / `ai_low` e o `Source` tipo
   `"ai"` não existem mais.
4. **Novo gate do engine:** um `KnownPart` é *reconhecido* (`known_exact=True`)
   quando tem **specs reais** (`capacity` / `emcp_ram` / `emcp_nand` / `density_gbit`)
   **OU** `confidence ∈ (confirmed, manual)`. Ele *vence a gramática* (vira
   autoridade) **só** quando `confidence ∈ (confirmed, manual)`.
   Escada de confiança: `confirmed > manual > distributor > estimated`.

## Por que te afeta

Qualquer entrada sua com `"status": "enriched"` (ou `"raw"`) ou
`"confidence": "ai_*"` em `create_defaults` / `fields` do `fix_known_parts.py`
está **obsoleta**. Antes, isso fazia a criação do `KnownPart` falhar de forma
quase silenciosa (`TypeError`). Hoje o `fix_known_parts` **ignora o campo inválido
e avisa** (`⚠ campo inválido ignorado…`), mas você deve limpar mesmo assim e nunca
mais usar.

## O que fazer — SÓ na sua marca

1. **`fix_known_parts.py`** (suas entradas):
   - Remova todo `"status": "..."` de `create_defaults` **e** `fields`.
   - Troque todo `"confidence": "ai_high"/"ai_medium"/"ai_low"` por `"confirmed"`
     ou `"manual"` (o que for verdade).
   - Para um chip ser **confirmado** (vencer a gramática e entrar no estoque sem
     cair na fila), use `confidence="confirmed"` (datasheet/Octopart) ou
     `"manual"` (você avalizou).
2. **`populate_<suamarca>.py`** (se existir): remova qualquer kwarg `status=`.
3. **Sua bíblia `<SUAMARCA>.md`**: apague templates/instruções que mostrem
   `status="enriched"`. A convenção correta está em
   `docs/CONVENCAO_CAMPOS_ESTOQUE.md` / `docs/CONVENCAO_MICRON_ESTOQUE.md`.

## Template correto de entrada (`fix_known_parts`)

```python
{
    "pn": "SEUPN123",
    "create_defaults": {
        "brand_name": "SuaMarca",
        "chip_type": "eMMC",          # eMCP / uMCP / UFS / LPDDR / DDR / NAND...
        "subtype": "...",
        "capacity": "16GB",           # eMCP/uMCP: use emcp_ram + emcp_nand
        "confidence": "confirmed",    # ou "manual"  — NUNCA status, NUNCA ai_*
        "source_url": "https://...",
    },
    "fields": {"capacity": "16GB", "confidence": "confirmed"},
    "reason": "Confirmado via datasheet X.",
}
```

**Proibido:** `"status": ...` · `"confidence": "ai_*"` · qualquer referência a
Gemini / `enrich_gemini.py`.

## Como verificar que ficou certo

```bash
# 1) Suíte de testes — DEVE passar. O teste FixKnownPartsEntriesTests barra
#    qualquer 'status' reintroduzido em create_defaults.
python manage.py test chips --settings=core.settings_test

# 2) Dry-run do fix da sua marca — NÃO pode aparecer "⚠ campo inválido ignorado"
#    nas suas entradas.
python manage.py fix_known_parts --dry-run

# 3) (opcional) confirme um PN seu: deve vir known_exact=True + confidence
python manage.py diag_pn SEUPN123
```

Quando os 3 passarem limpos, sua marca está alinhada. Dúvida sobre a convenção de
campos por tipo de chip: `docs/CONVENCAO_CAMPOS_ESTOQUE.md`.
