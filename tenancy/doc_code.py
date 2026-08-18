"""
tenancy/doc_code.py — o identificador CANÔNICO de documento (dono, 2026-08-18)
=============================================================================
``LOT/EMI/041/08/26`` · ``SO/EMI/012/08/26`` · ``INV/EMI/003/08/26``

Uma função só, usada por Lot, SalesOrder e Invoice, porque os três têm o mesmo
problema: a numeração é POR EMPRESA (decisão de julho — "o lote 41 continua
sendo o 41"), então o código COLIDE entre clientes. O comprador, que lê ordens
de várias empresas, via dois ``LOT/001/08/26`` na lista dele.

⚠ Recusado de propósito o código de PAÍS (PY/VE): duas recicladoras do mesmo
país voltariam a colidir — e é exatamente esse o caminho de crescimento. País é
metadado de EMBARQUE e já viaja no endereço do SHIP FROM; não pertence ao
identificador.

O resultado é CONGELADO no ``code_str`` do documento na criação. Duas razões:
o dono quis o formato novo só em documento NOVO (papel já impresso não pode
divergir da tela), e um número de documento não deve mudar quando alguém
renomeia o código da empresa.

**Canônico: NUNCA traduz.** É o mesmo texto que o gerente digita no
type-to-confirm do fechamento do lote.
"""


def doc_code(prefixo: str, company_code: str, number: int, quando) -> str:
    """``LOT/EMI/041/08/26``. Empresa sem código sai no formato antigo,
    ``LOT/041/08/26`` — é o legado, e ele continua válido."""
    partes = [prefixo]
    if company_code:
        partes.append(company_code)
    partes.append(f'{number:03d}')
    if quando is not None:
        partes += [f'{quando:%m}', f'{quando:%y}']
    return '/'.join(partes)
