"""
corrigir_recebimento_eminer
===========================
Registra o REPASSE ao cliente nas seis vendas da reconciliação, para o painel
"Pagamento" da tela da venda parar de mostrar em aberto o que já foi recebido.

Achado do dono em 2026-09-01, conferindo o primeiro envio (LOT/001/04/26): na
tela do comprador a compra está PAGA, e na tela da venda a etapa "Pagamento"
está com ✓ — mas logo abaixo, no painel Pagamento, "Falta US$ …" em vermelho.

Não são telas brigando: são as DUAS PERNAS do modelo (docstring de `Payout`
em vendas/models.py):

  · perna 1 — COMPRADOR → WhatTheChip: `Invoice.paid_usd` / `balance_usd`.
    É a que a tela do comprador e a barra de etapas leem. Está paga.
  · perna 2 — WhatTheChip → CLIENTE: `net_usd` (bruto − taxa), `paid_out_usd`
    e `payout_balance_usd`. É a que o painel "Pagamento" da OV lê. Nunca
    existiu um `Payout` nesta operação — a tabela está VAZIA em produção —
    então esse painel mostra o líquido inteiro em aberto, e mostraria para
    sempre, em todo lote que fosse pago.

A taxa de serviço de 10% está CERTA (dono, 2026-09-01: "a taxa tem que ter em
tudo mesmo, sempre os 10%"). Este comando NÃO toca nela — nem em `Invoice.
fee_*`, nem em `Company.service_fee_pct`. O que faltava era só o outro lado.

O que ele faz, por fatura da reconciliação:

    repassa  =  net_usd  −  paid_out_usd

criando um `Payout` desse valor com a DATA e a REFERÊNCIA do pagamento do
comprador. É o mesmo dinheiro, no mesmo dia, na mesma carteira: o Wu Quan
paga direto nas carteiras da operação (BINANCE HANDSON, TRONLINK são as
referências gravadas nos pagamentos), então "o comprador pagou" e "o cliente
recebeu" são o mesmo evento. Os 10% ficam retidos pelo WhatTheChip, que é
exatamente o que o painel passa a mostrar: bruto, taxa, líquido, recebido =
líquido, falta = zero.

⚠ Só as seis ordens da reconciliação. Venda corrente não é tocada.
⚠ Fatura que NÃO está integralmente paga na perna do comprador é PULADA — não
  se inventa recibo de dinheiro que não entrou.
⚠ Idempotente: fatura cujo repasse já cobre o líquido não recebe outro.

Uso:
    python manage.py corrigir_recebimento_eminer            # dry-run
    python manage.py corrigir_recebimento_eminer --commit
    python manage.py corrigir_recebimento_eminer --revert
"""

import json
import os
from decimal import Decimal as D

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from core.safe_command import SafeWriteCommand
from tenancy.models import Company
from tenancy.scope import company_scope

EMPRESA_SLUG = 'eminer'
#: As seis da reconciliação, pelo CÓDIGO DA ORDEM — que não muda com a
#: renumeração de lote, ao contrário do número (mesma escolha do
#: `sincronizar_valoracao_eminer`).
ORDENS = ('SO/009/04/26', 'SO/010/06/26', 'SO/011/07/26',
          'SO/005/08/26', 'SO/001/07/26', 'SO/002/07/26')
REVERT = os.path.join(str(settings.BASE_DIR), 'var', 'reverts',
                      'corrigir_recebimento_eminer_revert.json')
MANTER_ANTIGOS = 10
ZERO = D('0.00')


class Command(SafeWriteCommand):
    help = ('Registra o repasse ao cliente nas faturas já pagas da '
            'reconciliação, para o painel de pagamento da venda parar de '
            'mostrar saldo em aberto no que já foi recebido.')

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', action='store_true')

    # ── plano ────────────────────────────────────────────────────────────
    def handle(self, *args, **o):
        if o['revert']:
            return self._revert()

        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        w, st = self.stdout.write, self.style

        with company_scope(empresa.id):
            plano = [self._ler(codigo) for codigo in ORDENS]

            w('')
            w(st.MIGRATE_HEADING(
                '━━ painel de pagamento da venda: as duas pernas ━━'))
            w(f'   {"fatura":<16}{"bruto":>11}{"taxa":>10}{"líquido":>11}'
              f'{"pago":>11}{"repassado":>11}   ação')
            mexer = [p for p in plano if p['muda']]
            for p in plano:
                inv = p['inv']
                w(f'   {inv.code:<16}{str(inv.total_usd):>11}'
                  f'{str(inv.fee_usd):>10}{str(inv.net_usd):>11}'
                  f'{str(p["pago"]):>11}{str(p["repassado"]):>11}   '
                  f'{p["acao"]}')
            w('')

            if not mexer:
                w(st.SUCCESS('   Nada a fazer: as duas pernas já batem.'))
                return

            total = sum((p['a_repassar'] for p in mexer), ZERO)
            taxa = sum((p['inv'].fee_usd for p in mexer), ZERO)
            w(f'   {len(mexer)} repasse(s) a registrar, somando US$ {total}.')
            w(f'   Cada um leva a data e a referência do pagamento do '
              f'comprador — é o\n   mesmo dinheiro, na mesma carteira.')
            w(f'   Taxa de serviço RETIDA pelo WhatTheChip: US$ {taxa}. '
              f'Não é tocada.')

            if not o['commit']:
                w(st.WARNING('\nDRY-RUN — nada foi gravado. Use --commit para aplicar.'))
                return

            registro = {'quando': timezone.now().isoformat(), 'repasses': []}
            with transaction.atomic():
                for p in mexer:
                    self._repassar(p, registro)
            self._gravar_revert(registro)
            w(st.SUCCESS(f'\nGravado. Reversão em {REVERT}'))

    def _ler(self, codigo):
        """Lê a fatura ativa da ordem e decide se cabe repasse."""
        from vendas.models import SalesOrder
        so = next((x for x in SalesOrder.objects.filter(status='confirmed')
                   if x.code == codigo), None)
        if so is None:
            raise CommandError(
                f'Ordem {codigo} não encontrada ou não confirmada. '
                f'Rode a reconciliação antes desta correção.')
        inv = next((i for i in so.invoices.all() if i.status != 'cancelled'),
                   None)
        if inv is None:
            raise CommandError(
                f'Ordem {codigo} não tem fatura ativa — nada a corrigir aqui, '
                f'e isso não era esperado nas seis da reconciliação.')

        pago = inv.paid_usd
        repassado = inv.paid_out_usd
        a_repassar = inv.net_usd - repassado

        if pago < inv.total_usd:
            # Não se repassa o que não entrou. A perna 2 nunca pode correr
            # à frente da perna 1.
            acao, muda, a_repassar = (
                f'PULA — comprador ainda deve US$ {inv.total_usd - pago}',
                False, ZERO)
        elif a_repassar <= ZERO:
            acao, muda = 'já bate — não toco', False
        else:
            acao, muda = f'repassar US$ {a_repassar}', True

        return dict(so=so, inv=inv, pago=pago, repassado=repassado,
                    a_repassar=a_repassar, acao=acao, muda=muda)

    # ── escrita ──────────────────────────────────────────────────────────
    def _repassar(self, p, registro):
        from vendas.models import Payout
        inv = p['inv']
        pag = inv.payments.order_by('-paid_at', '-id').first()
        if pag is None:                          # defensivo: _ler já barra
            raise CommandError(f'{inv.code}: sem pagamento do comprador.')
        po = Payout(invoice=inv, amount_usd=p['a_repassar'],
                    paid_at=pag.paid_at, reference=pag.reference)
        po.save()
        registro['repasses'].append({
            'pk': po.pk, 'fatura': inv.code, 'valor': str(po.amount_usd)})
        self.stdout.write(self.style.SUCCESS(
            f'   {inv.code}: repasse US$ {po.amount_usd} em '
            f'{po.paid_at:%d/%m/%Y} ({po.reference or "—"}) · '
            f'taxa US$ {inv.fee_usd} retida'))

    # ── reversão ─────────────────────────────────────────────────────────
    def _revert(self):
        from vendas.models import Payout
        if not os.path.exists(REVERT):
            raise CommandError(f'Não há {REVERT} — nada a desfazer.')
        reg = json.load(open(REVERT))
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        w = self.stdout.write
        with company_scope(empresa.id), transaction.atomic():
            for d in reg['repasses']:
                Payout.all_companies.filter(pk=d['pk']).delete()
                w(f'   {d["fatura"]}: repasse US$ {d["valor"]} removido')
        os.rename(REVERT, REVERT + '.' +
                  timezone.now().strftime('%Y%m%d_%H%M%S') + '.usado')
        self._podar()
        self.stdout.write(self.style.SUCCESS('Revertido.'))

    def _gravar_revert(self, registro):
        os.makedirs(os.path.dirname(REVERT), exist_ok=True)
        if os.path.exists(REVERT):
            os.rename(REVERT, REVERT + '.' +
                      timezone.now().strftime('%Y%m%d_%H%M%S') + '.bak')
        with open(REVERT, 'w') as f:
            json.dump(registro, f, indent=1, ensure_ascii=False)
        self._podar()

    def _podar(self):
        pasta, base = os.path.dirname(REVERT), os.path.basename(REVERT)
        antigos = sorted(f for f in os.listdir(pasta) if f.startswith(base + '.'))
        for f in antigos[:-MANTER_ANTIGOS]:
            os.remove(os.path.join(pasta, f))
