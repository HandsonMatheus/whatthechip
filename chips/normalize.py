"""
chips/normalize.py
==================
Normalização canônica de Part Number — UMA função só, usada na ESCRITA (a coluna
`KnownPart.part_number_norm`, via `save()`) e na BUSCA (`chips/engine.py`). É o
passo 1A do `docs/PLANO_IMPLEMENTACAO_ESCALABILIDADE.md`: acaba com a classe de bug
de PN duplicado / não-encontrado (3898 PNs com `:`/`.` no banco, ~1908 caindo em
"tipo vazio" na bancada — `docs/CARACTERIZACAO_BASELINE.md §4.1`).

Espelha EXATAMENTE o que o `classify()` já faz com o input (maiúsculas + remove
tudo que não é A-Z0-9), acrescido de NFKC (junta formas full-width/compatibilidade,
ex.: 'ＭＴ２９' → 'MT29'). Para PN ASCII — todos os existentes — NFKC é no-op, então
o comportamento é idêntico ao de hoje.
"""

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^A-Z0-9]")


def normalize_pn(value: str) -> str:
    """Forma canônica do PN: NFKC → MAIÚSCULAS → só A-Z0-9 (sem `-`, espaço, `:`, `.`…)."""
    if not value:
        return ""
    return _NON_ALNUM.sub("", unicodedata.normalize("NFKC", value).upper())
