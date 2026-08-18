"""
vendas/views_partner.py — a superfície do COMPRADOR (F11.6, dono 2026-08-18)
============================================================================
O acerto do F11.4 trocando de mão: quem dá o RESULTADO deixa de ser o admin da
plataforma e passa a ser o COMPRADOR, na área dele (``/partner/compras/``).
Modelo é o mesmo — ``Settlement``/``SettlementLine``/``Invoice`` +
``settle_and_invoice`` — o que muda é a superfície.

Duas telas:

1. **Compras** — as OVs de TODOS os clientes dele (lote, cliente, chips,
   ¥/US$, estágio). O laço por empresa mora no ``services.orders_for_buyer``.
2. **Compra** — a OV aberta: cabeçalho, tabela MARCA → capacidade com o campo
   de RECUSADOS por linha, observação, e o "Fechar resultado" que gera acerto
   + fatura num ato atômico. Depois de faturada, a mesma tela vira leitura,
   com o saldo a pagar.

⚠ Três coisas que esta superfície faz DIFERENTE do resto do sistema, e que a
próxima pessoa precisa saber antes de editar:

· **Escopo:** o comprador lê VÁRIAS empresas. Toda leitura/escrita passa pelo
  ``services.buyer_order``/``orders_for_buyer``, que abrem o ``company_scope``
  da empresa dona. Fora dele o RLS devolve ZERO linhas em silêncio — o bug
  apareceria como "OV sem linhas", não como erro.
· **Máscara:** aqui o rótulo é REAL (``eMMC 64GB``, não ``B-07``). O
  ``is_unmasked`` é superuser-only e o comprador não é superuser; usar os
  helpers mascarados aqui entregaria código de caixa a quem compra chip.
· **Posse:** o gate é o ``partner_required`` (vínculo ``Buyer.users``), e TODA
  query filtra por ``buyer=request.buyer``. Uma OV de outro comprador é 404,
  não 403 — não confirmamos nem que ela existe.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from pricing.views import _fx_info, partner_required

from . import services
from .models import STATUS_CONFIRMED


def _shell(request, extra=None):
    """Contexto que o ``partner_base.html`` exige (header + sidebar)."""
    ctx = {'buyer': request.buyer, 'fx_info': _fx_info(request.buyer),
           'active_pk': 'compras', 'active_kind': None, 'kind_nav': []}
    ctx.update(extra or {})
    return ctx


@partner_required
def compras_list(request):
    """As compras do comprador — todas as empresas, mais recente primeiro."""
    ordens = services.orders_for_buyer(request.buyer)
    return render(request, 'vendas/partner_compras.html',
                  _shell(request, {'ordens': ordens}))


@partner_required
def compra_detail(request, pk):
    with services.buyer_order(request.buyer, pk) as so:
        return render(request, 'vendas/partner_compra.html',
                      _shell(request, _detalhe(so)))


def _detalhe(so):
    """Tudo que a tela da compra desenha. Roda DENTRO do escopo da empresa."""
    inv = next((i for i in so.invoices.all() if i.status != 'cancelled'), None)
    return {
        'so': so,
        'grupos': services.result_rows(so),
        'stage': services.order_stage(so),
        'invoice': inv,
        # Só OV CONFIRMADA e ainda sem fatura aceita resultado. Rascunho está
        # esperando o próprio comprador completar o grid (F11.6/F1).
        'pode_acertar': so.status == STATUS_CONFIRMED and inv is None,
    }


@partner_required
@require_POST
def compra_resultado(request, pk):
    """"Fechar resultado": recusas por linha → acerto + fatura, atômico.

    Campo em branco vale ZERO (é o padrão: o comprador digita só o que
    recusou). Quantidade inválida ou maior que a enviada volta para a tela
    com o erro — o ``settle_and_invoice`` valida de novo do lado do modelo,
    então um POST forjado também não passa.
    """
    with services.buyer_order(request.buyer, pk) as so:
        ajustes = {}
        for line in so.lines.all():
            cru = (request.POST.get(f'rej_{line.pk}') or '').strip()
            if not cru:
                continue
            try:
                rej = int(cru)
            except ValueError:
                messages.error(request, _(
                    'Quantidade recusada inválida em %(cat)s.')
                    % {'cat': line.label})
                return redirect('compras:detail', pk=so.pk)
            if rej:
                ajustes[line.pk] = (rej, None)      # sem repreço no MVP
        try:
            services.settle_and_invoice(
                so, ajustes, request.user,
                notes=(request.POST.get('notes') or '').strip())
        except ValidationError as erro:
            messages.error(request, ' '.join(erro.messages))
            return redirect('compras:detail', pk=so.pk)
        messages.success(request, _('Resultado fechado — fatura emitida.'))
        return redirect('compras:detail', pk=so.pk)
