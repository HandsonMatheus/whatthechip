"""
Camada de APRESENTAÇÃO dos rótulos traduzíveis do engine (i18n).

Por quê este arquivo existe
---------------------------
O engine (`assess_profitability`, decode, gateway) é **lógica** e continua
falando em VALORES CANÔNICOS — "RENTÁVEL" / "NÃO RENTÁVEL" / "INDETERMINADO".
Esses valores são a **chave de decisão** em todo o sistema: `is_dead_by_generation`,
o gateway do estoque (`estoque/views.py`) e os testes comparam contra eles. Traduzir
o retorno do engine quebraria essa lógica (e a filosofia de fonte única).

A separação é a mesma do `profitable_key` que as views já derivam:
  - **VALOR CANÔNICO** (ex.: "NÃO RENTÁVEL")  → lógica / comparação (NUNCA traduzir)
  - **CHAVE** (ex.: "nao-rentavel")             → classe CSS
  - **RÓTULO** (ex.: "NO RENTABLE" em ES)       → exibição traduzida (AQUI)

Regra de ouro: **na lógica, compare contra o valor canônico ou a chave — nunca
contra o rótulo exibido.** O rótulo é só pixel. Ver I18N.md.

O valor canônico em português dobra como `msgid` do gettext (o idioma-fonte do
projeto é pt-br), então o catálogo `es` mapeia "NÃO RENTÁVEL" → "NO RENTABLE".
"""
from django.utils.translation import gettext_lazy as _

# Veredito de rentabilidade: valor canônico do engine → rótulo exibível (traduzível).
PROFITABILITY_LABELS = {
    "RENTÁVEL":      _("RENTÁVEL"),
    "NÃO RENTÁVEL":  _("NÃO RENTÁVEL"),
    "INDETERMINADO": _("INDETERMINADO"),
}


def profitability_label(value: str) -> str:
    """Rótulo traduzido do veredito de rentabilidade (a partir do valor canônico).

    Fail-open: valor desconhecido volta como veio (não estoura a UI).
    """
    return PROFITABILITY_LABELS.get(value, value)


# Fonte da classificação: valor canônico do engine → rótulo exibível.
# ⚠ O valor canônico é COMPARADO na lógica (estoque/views.py::CONFIRMED_SOURCES
# = {"banco de dados"}) — por isso o engine NÃO muda; só a exibição traduz.
# Vocabulário fechado (chips/engine.py): gramática · gramática+db · banco de dados.
SOURCE_LABELS = {
    "gramática":      _("gramática"),
    "gramática+db":   _("gramática+db"),
    "banco de dados": _("banco de dados"),
}


def source_label(value: str) -> str:
    """Rótulo traduzido da fonte de classificação (fail-open, igual acima)."""
    return SOURCE_LABELS.get(value, value)
