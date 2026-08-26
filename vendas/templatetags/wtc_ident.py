"""Filtros de IDENTIFICADOR LONGO — endereço de carteira, rastreio, hash.

Um só filtro, e ele existe por causa de uma regra da spec v2 do comprador
(§6.2) que parece detalhe de layout e é de conferência:

    "Identificador longo em célula estreita corta no MEIO, nunca no fim
     (`TQ9fH4mVx…z8gXqN`): a cauda é justamente o que se confere contra a
     carteira."

Cortar no fim (que é o que `truncatechars` e o `text-overflow` do CSS fazem)
entrega os primeiros caracteres — e ninguém confere endereço de blockchain
pelo começo, porque é o começo que os golpes imitam. O valor inteiro vai no
`title`, e o botão de copiar copia o inteiro.
"""

from django import template

register = template.Library()


@register.filter
def meio(valor, tamanho=16):
    """``TQ9fH4mVx2Kd7YbLpJs3RnAeW6cUz8gXqN`` → ``TQ9fH4mV…z8gXqN``.

    ``tamanho`` é quantos caracteres SOBRAM, somando as duas pontas. Valor
    curto demais volta inteiro — cortar o que já cabe só tira informação.
    """
    texto = str(valor or '')
    try:
        tamanho = int(tamanho)
    except (TypeError, ValueError):
        tamanho = 16
    if tamanho < 4 or len(texto) <= tamanho:
        return texto
    cabeca = (tamanho + 1) // 2
    return f'{texto[:cabeca]}…{texto[-(tamanho - cabeca):]}'
