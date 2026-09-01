"""
despachar_lote007_eminer
========================
Registra o despacho da SO/004 (LOT/007) — o que congela a venda dela.

Contexto (2026-09-01). O LOT/007 fechou em 18/08 às 00:30, o packing list saiu,
a caixa viajou na remessa DHL 2486463965 junto com o LOT/010 — e a ordem de
venda ficou em RASCUNHO: sem total congelado, sem despacho, invisível como
venda. Pelo sistema, aquele envio não tinha acontecido.

O dono corrigiu isso PELA TELA às 03:27 de 01/09, registrando o despacho.
Ação de tela não se reproduz em produção, e é por isso que este comando
existe: para os dois bancos terminarem idênticos, e para o passo estar na
mesma corrente auditável que o resto — com dry-run, reversão e teste.

⚠ Ele NÃO reimplementa nada: chama o mesmo `services.mark_shipped()` que o
  botão da tela chama. Reescrever a regra aqui criaria uma segunda verdade,
  e é o despacho que CONGELA a venda (`mark_shipped` → `confirm`): o ¥ para
  de andar e a ordem aparece para o comprador.

⚠ CONFERE O RESULTADO E ABORTA se não bater. O `confirm()` lê o grid VIVO do
  comprador na hora — se a tabela de preços de produção não for a mesma que
  a daqui, os totais saem diferentes e a venda ficaria com outro número sem
  ninguém perceber. Por isso os valores esperados estão escritos abaixo: o
  comando congela dentro de uma transação, compara, e desfaz tudo se divergir.
  É a diferença entre "reproduzir" e "torcer".

Uso:
    python manage.py despachar_lote007_eminer                        # dry-run
    python manage.py despachar_lote007_eminer --commit --user raphaelbastos
    python manage.py despachar_lote007_eminer --revert
"""

import json
import os
from datetime import date
from decimal import Decimal as D

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from core.safe_command import SafeWriteCommand
from tenancy.models import Company
from tenancy.scope import company_scope

EMPRESA_SLUG = 'eminer'
ORDEM = 'SO/004/08/26'
#: O que o dono registrou na tela, e o que produção tem de receber igual.
DESPACHO = dict(carrier='DHL', tracking='2486463965', data=date(2026, 8, 18))
#: O que o congelamento TEM de produzir. Não é decoração: é o portão.
ESPERADO = dict(fx=D('0.1482'), total_rmb=D('79102.00'),
                total_usd=D('11694.91'))
REVERT = os.path.join(str(settings.BASE_DIR), 'var', 'reverts',
                      'despachar_lote007_eminer_revert.json')
MANTER_ANTIGOS = 10


class Command(SafeWriteCommand):
    help = ('Registra o despacho da SO/004 (LOT/007), que congela a venda — '
            'o mesmo que o dono fez pela tela em 01/09.')

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', action='store_true')
        parser.add_argument('--user', default=None,
                            help='username que assina o despacho '
                                 '(shipped_by). Em 01/09 foi raphaelbastos.')

    # ── plano ────────────────────────────────────────────────────────────
    def handle(self, *args, **o):
        if o['revert']:
            return self._revert()

        from vendas.models import SalesOrder
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        w, st = self.stdout.write, self.style

        with company_scope(empresa.id):
            so = next((x for x in SalesOrder.objects.all() if x.code == ORDEM),
                      None)
            if so is None:
                raise CommandError(f'Ordem {ORDEM} não encontrada.')

            w('')
            w(st.MIGRATE_HEADING('━━ despacho do LOT/007 (congela a venda) ━━'))
            w(f'   ordem      {so.code}   ·   lote {so.lot.code}')
            w(f'   hoje       status={so.status}  despacho='
              f'{so.shipped_at or "—"}  total US$ {so.total_usd or "—"}')
            w(f'   a gravar   {DESPACHO["carrier"]} {DESPACHO["tracking"]}  '
              f'em {DESPACHO["data"]:%d/%m/%Y}')
            w(f'   esperado   ¥ {ESPERADO["total_rmb"]}  ·  '
              f'US$ {ESPERADO["total_usd"]}  ·  fx {ESPERADO["fx"]}')
            w('')

            if self._ja_bate(so):
                w(st.SUCCESS('   Nada a fazer: já despachada e congelada '
                             'nos valores esperados.'))
                return
            if so.status == 'confirmed' and so.shipped_at:
                raise CommandError(
                    f'{so.code} já está confirmada e despachada, mas com '
                    f'outros valores (US$ {so.total_usd}, despacho '
                    f'{so.shipped_at}). Não sobrescrevo venda congelada — '
                    f'isso é decisão sua, não conserto de comando.')

            if not o['commit']:
                w(st.WARNING('\nDRY-RUN — nada foi gravado. Use --commit para aplicar.'))
                return

            registro = {'quando': timezone.now().isoformat()}
            with transaction.atomic():
                registro['antes'] = self._antes(so)
                self._despachar(so, o['user'])
                self._conferir_ou_abortar(so)
            self._gravar_revert(registro)
            w(st.SUCCESS(
                f'\n   {so.code}: despachada e CONGELADA — ¥ {so.total_rmb} · '
                f'US$ {so.total_usd} · fx {so.fx_usd_rate}'))
            w(st.SUCCESS(f'Gravado. Reversão em {REVERT}'))

    @staticmethod
    def _ja_bate(so):
        return (so.status == 'confirmed'
                and so.shipped_at == DESPACHO['data']
                and so.total_rmb == ESPERADO['total_rmb']
                and so.total_usd == ESPERADO['total_usd'])

    # ── escrita ──────────────────────────────────────────────────────────
    @staticmethod
    def _antes(so):
        return {
            'pk': so.pk, 'code': so.code, 'status': so.status,
            'fx': str(so.fx_usd_rate) if so.fx_usd_rate is not None else None,
            'total_rmb': str(so.total_rmb) if so.total_rmb is not None else None,
            'total_usd': str(so.total_usd) if so.total_usd is not None else None,
            'carrier': so.carrier, 'tracking': so.tracking,
            'shipped_at': so.shipped_at.isoformat() if so.shipped_at else None,
            'shipped_by_id': so.shipped_by_id,
            'confirmed_at': (so.confirmed_at.isoformat()
                             if so.confirmed_at else None),
            'confirmed_by_id': so.confirmed_by_id,
            'linhas': [{'pk': l.pk,
                        'unit_rmb': str(l.unit_rmb) if l.unit_rmb is not None else None,
                        'unit_usd': str(l.unit_usd) if l.unit_usd is not None else None}
                       for l in so.lines.all()],
        }

    def _despachar(self, so, username):
        from django.contrib.auth import get_user_model
        from vendas import services
        user = None
        if username:
            user = get_user_model().objects.filter(username=username).first()
            if user is None:
                raise CommandError(f'Usuário "{username}" não existe.')
        services.mark_shipped(so, DESPACHO['carrier'], DESPACHO['tracking'],
                              DESPACHO['data'], user)
        so.refresh_from_db()

    def _conferir_ou_abortar(self, so):
        """O portão. Congelou com outro número? Desfaz tudo e explica."""
        erros = []
        if so.status != 'confirmed':
            erros.append(
                f'ficou em "{so.status}" — o congelamento falhou, quase '
                f'sempre por categoria sem preço no grid do comprador')
        if so.fx_usd_rate != ESPERADO['fx']:
            erros.append(f'fx {so.fx_usd_rate} ≠ {ESPERADO["fx"]}')
        if so.total_rmb != ESPERADO['total_rmb']:
            erros.append(f'¥ {so.total_rmb} ≠ {ESPERADO["total_rmb"]}')
        if so.total_usd != ESPERADO['total_usd']:
            erros.append(f'US$ {so.total_usd} ≠ {ESPERADO["total_usd"]}')
        if erros:
            raise CommandError(
                'O congelamento não bateu com o esperado, e NADA foi '
                'gravado:\n   · ' + '\n   · '.join(erros) +
                '\n   A tabela de preços deste banco não é a mesma de onde '
                'os valores\n   esperados vieram. Compare os dois grids '
                'antes de insistir.')

    # ── reversão ─────────────────────────────────────────────────────────
    def _revert(self):
        from datetime import date as _date, datetime
        from vendas.models import SalesOrder, SalesOrderLine
        if not os.path.exists(REVERT):
            raise CommandError(f'Não há {REVERT} — nada a desfazer.')
        d = json.load(open(REVERT))['antes']
        empresa = Company.objects.get(slug=EMPRESA_SLUG)

        with company_scope(empresa.id), transaction.atomic():
            SalesOrder.all_companies.filter(pk=d['pk']).update(
                status=d['status'],
                fx_usd_rate=self._dec(d['fx']),
                total_rmb=self._dec(d['total_rmb']),
                total_usd=self._dec(d['total_usd']),
                carrier=d['carrier'], tracking=d['tracking'],
                shipped_at=(_date.fromisoformat(d['shipped_at'])
                            if d['shipped_at'] else None),
                shipped_by_id=d['shipped_by_id'],
                confirmed_at=(datetime.fromisoformat(d['confirmed_at'])
                              if d['confirmed_at'] else None),
                confirmed_by_id=d['confirmed_by_id'])
            for ld in d['linhas']:
                SalesOrderLine.all_companies.filter(pk=ld['pk']).update(
                    unit_rmb=self._dec(ld['unit_rmb']),
                    unit_usd=self._dec(ld['unit_usd']))
        self.stdout.write(
            f'   {d["code"]}: volta a "{d["status"]}", '
            f'{len(d["linhas"])} linha(s) descongelada(s)')
        os.rename(REVERT, REVERT + '.' +
                  timezone.now().strftime('%Y%m%d_%H%M%S') + '.usado')
        self._podar()
        self.stdout.write(self.style.SUCCESS('Revertido.'))

    @staticmethod
    def _dec(v):
        return None if v is None else D(v)

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
