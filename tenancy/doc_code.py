"""
tenancy/doc_code.py — o identificador CANÔNICO de documento (dono, 2026-09-02)
=============================================================================
``LOT-2026-0041`` · ``EMIN-SO-2026-0004`` · ``INV/EMI/003/08/26`` (legado)

Fonte ÚNICA do código de documento, usada por Lot, SalesOrder e Invoice. O
formato é um **MAPA POR TIPO** (``FORMATOS``), não um `if`: mesma forma do
``Lot.ORIGIN_ICONS``. Tipo novo de documento = uma linha aqui, e nenhum ramo
existente muda — que é justamente a classe de bug que já mordeu o selo de
origem do painel do comprador quatro vezes.

A gramática, para LOT e SO (CONVENCAO_IDENTIFICADORES.md §1)::

    [CÓDIGO-EMPRESA-]TIPO-AAAA-NNNN

  CÓDIGO-EMPRESA  4 letras de `Company.code`. **Só na SO** — o lote não leva
                  prefixo, porque o número do lote é interno (§2.5). Empresa
                  sem código sai `SO-2026-0004`, nunca `-SO-2026-0004` (§3).
  AAAA            ano com QUATRO dígitos, e ANTES do número. `LOT/041/08/26`
                  exigia saber que `08/26` é mês/ano nessa ordem — ambiguidade
                  que já custou uma confirmação manual de data com o dono, e o
                  comprador é chinês. O ano antes do número é o que faz o
                  código ORDENAR como texto (`LOT-0001-2027` viria ANTES de
                  `LOT-0041-2026`; é por isso que o Odoo escreve INV/2026/00001).
  NNNN            zero-padding 4, **reiniciando a cada ano** (§2.3).

⚠ O ANO NÃO SAI DAQUI SOZINHO NA SO. Ele é ARGUMENTO (`ano=`), porque a ordem
de venda HERDA o ano do LOTE, não o da própria criação (§2.2): um lote de 2026
vendido em janeiro não virou campanha de 2027. Consequência que parece bug e
não é (§2.4): em fevereiro de 2027 uma SO pode consumir o próximo número de
2026 — o do ano do lote dela.

⚠ `timezone.localtime`, nunca `now()` cru. Um lote aberto 31/dez 21:00 em
Assunção (UTC−3) já é 1º de janeiro em UTC: derivar o ano do horário do banco
carimbaria o documento com o ANO ERRADO exatamente na fronteira que esta
convenção existe para acertar. (O código antigo tinha esse defeito em `%m/%y`,
onde ele errava só o mês.)

⚠ A FATURA (INV) NÃO ENTROU na convenção — decisão do dono de 2026-09-02: ela
é aposentada em entrega separada. O formatador dela é o LEGADO, byte a byte
como era, UTC inclusive: mexer nele seria mudar um documento que está de saída.

O resultado é CONGELADO no ``code_str`` do documento na criação, e o passado é
reescrito por `manage.py backfill_doc_codes` — o dono decidiu em 2026-08-18 que
quer a tela e o papel na mesma grafia, mesmo ao custo de divergir de impresso
antigo.

**Canônico: NUNCA traduz.** É o mesmo texto que o gerente digita no
type-to-confirm do fechamento e da exclusão do lote.
"""

from django.utils import timezone


def _ano_de(quando):
    """Ano do documento a partir de um instante, no fuso do NEGÓCIO.

    ``localtime`` só se aplica a datetime AWARE; date e naive passam direto
    (é o que chega de comando/fixture)."""
    if quando is None:
        return None
    if getattr(quando, 'tzinfo', None) is not None:
        quando = timezone.localtime(quando)
    return quando.year


def _lote(company_code, number, ano, quando):
    """``LOT-2026-0041``. SEM prefixo de empresa, de propósito (§2.5): o número
    do lote é interno, e o lote saiu da tabela do comprador — que era o único
    lugar onde dois clientes se cruzavam."""
    return f'LOT-{ano}-{number:04d}'


def _ordem(company_code, number, ano, quando):
    """``EMIN-SO-2026-0004``; sem código de empresa, ``SO-2026-0004`` (§3)."""
    return f'{company_code}-SO-{ano}-{number:04d}' if company_code \
        else f'SO-{ano}-{number:04d}'


def _fatura_legado(company_code, number, ano, quando):
    """``INV/EMI/003/08/26`` — o formato ANTIGO, preservado byte a byte.

    ⚠ Não "modernizar": a INV está sendo aposentada (dono, 2026-09-02) e
    qualquer mudança aqui altera um documento de saída. Inclusive o fuso: fica
    como sempre foi."""
    partes = ['INV']
    if company_code:
        partes.append(company_code)
    partes.append(f'{number:03d}')
    if quando is not None:
        partes += [f'{quando:%m}', f'{quando:%y}']
    return '/'.join(partes)


#: Vocabulário FECHADO de tipos de documento. Cada valor recebe sempre
#: ``(company_code, number, ano, quando)`` — assinatura uniforme para que somar
#: um tipo seja somar UMA LINHA, sem tocar em ramo nenhum.
FORMATOS = {
    'LOT': _lote,
    'SO':  _ordem,
    'INV': _fatura_legado,
}


def doc_code(prefixo: str, company_code: str, number: int, quando=None,
             *, ano=None) -> str:
    """O código canônico do documento.

    ``prefixo``      tipo do documento: 'LOT', 'SO' ou 'INV' (vocabulário fechado).
    ``company_code`` ``Company.code``; vazio = empresa legada, documento sem prefixo.
    ``number``       o número da sequência do ANO (ou perpétua, na INV).
    ``quando``       instante do documento — de onde o ano é derivado quando não
                     é passado, e o mês/ano do formato legado da INV.
    ``ano``          **explícito**, e é assim que a SO herda o ano do LOTE (§2.2).
                     Sem ele, cai no ano de ``quando`` (é o caso do lote).

    Tipo desconhecido levanta ``ValueError`` de propósito: um documento novo
    tem de ganhar sua linha no ``FORMATOS``, não sair com uma grafia inventada.
    """
    formato = FORMATOS.get(prefixo)
    if formato is None:
        raise ValueError(
            f'Tipo de documento desconhecido: {prefixo!r}. '
            f'Válidos: {", ".join(sorted(FORMATOS))} — some o novo ao FORMATOS.')
    if ano is None:
        ano = _ano_de(quando)
    return formato(company_code, number, ano, quando)
