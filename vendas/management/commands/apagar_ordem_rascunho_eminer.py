"""
apagar_ordem_rascunho_eminer
============================
Apaga a ordem de venda que ficou em RASCUNHO no LOT/007 (a SO/004/08/26).

Decisão do dono em 2026-09-01: *"a ordem em rascunho deleta"*.

A história dela: o lote 42 fechou em 08/08 e gerou a SO/003. Em 17/08 às 22:25
alguém reabriu o lote pela conta `admin` — e reabrir cancela automaticamente a
cotação em rascunho, então a SO/003 morreu ali. Às 00:30 de 18/08 a Rayssa
fechou o lote de novo e nasceu a SO/004. Essa nunca foi confirmada: sem total
congelado, sem fatura, sem despacho. O packing list saiu, a caixa viajou, e
pelo sistema aquele envio nunca existiu.

⚠ O que fica DEPOIS: o LOT/007 passa a não ter NENHUMA ordem de venda. Ele
  some da lista do comprador e da tela de Vendas. Para ter uma ordem outra
  vez o lote precisa ser reaberto e fechado de novo — e fechar dispara um
  `LotPricing` novo, que é o "resnapshot" que o dono pediu para evitar em
  lote fechado. Não é efeito colateral escondido: é o preço de apagar, e
  está aqui escrito para quem ler depois.

⚠ RECUSA se a ordem não estiver em rascunho. Ordem confirmada é documento —
  o caminho dela é cancelar, que deixa rastro, não apagar.
⚠ RECUSA se houver acerto, fatura ou nota do comprador pendurados. O banco já
  barraria (FK PROTECT), mas errar cedo com uma frase clara é melhor do que
  um IntegrityError.

A reversão guarda a ordem INTEIRA — cabeçalho e as 105 linhas — e recria
tudo com os mesmos valores. O `pk` muda; o resto não.

Uso:
    python manage.py apagar_ordem_rascunho_eminer            # dry-run
    python manage.py apagar_ordem_rascunho_eminer --commit
    python manage.py apagar_ordem_rascunho_eminer --revert
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
#: A ordem a apagar, pelo CÓDIGO — nunca pelo pk, que não diz nada a ninguém.
ORDEM = 'SO/004/08/26'
REVERT = os.path.join(str(settings.BASE_DIR), 'var', 'reverts',
                      'apagar_ordem_rascunho_eminer_revert.json')
MANTER_ANTIGOS = 10

#: Campos do cabeçalho que a reversão precisa devolver. Explícito de
#: propósito: um `model_to_dict` traria o que existe HOJE e calaria sobre
#: campo novo amanhã — a lista escrita quebra visível quando o modelo muda.
CAMPOS = ('number', 'status', 'code_str', 'fx_usd_rate', 'total_rmb',
          'total_usd', 'unkeyed_units', 'notes', 'carrier', 'tracking',
          'shipped_at', 'received_at')
CAMPOS_LINHA = ('brand', 'kind', 'gen', 'tier_value', 'tier_unit',
                'quantity', 'unit_rmb', 'unit_usd')


def _txt(v):
    return None if v is None else str(v)


class Command(SafeWriteCommand):
    help = 'Apaga a ordem de venda em rascunho do LOT/007 (SO/004/08/26).'

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', action='store_true')

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
                w(st.SUCCESS(f'\n   {ORDEM} não existe — nada a fazer.'))
                return

            self._recusar_se_nao_for_rascunho(so)

            linhas = list(so.lines.all())
            unidades = sum(l.quantity for l in linhas)
            w('')
            w(st.MIGRATE_HEADING('━━ apagar ordem em rascunho ━━'))
            w(f'   ordem      {so.code}')
            w(f'   lote       {so.lot.code}')
            w(f'   criada     {timezone.localtime(so.created_at):%d/%m/%Y %H:%M}')
            w(f'   linhas     {len(linhas)}  ·  {unidades} unidade(s) '
              f'(+{so.unkeyed_units} sem chave)')
            w(f'   valor      nenhum — rascunho não tem total congelado')
            w('')
            w(st.WARNING(
                f'   ⚠ Depois disto o {so.lot.code} fica SEM ordem de venda: '
                f'some da lista\n     do comprador e da tela de Vendas. Para '
                f'ter outra, o lote precisa ser\n     reaberto e fechado de '
                f'novo — e isso cria uma valoração nova.'))

            if not o['commit']:
                w(st.WARNING('\nDRY-RUN — nada foi gravado. Use --commit para aplicar.'))
                return

            registro = {'quando': timezone.now().isoformat()}
            with transaction.atomic():
                registro['ordem'] = self._serializar(so, linhas)
                so.lines.all().delete()
                so.delete()
            self._gravar_revert(registro)
            w(st.SUCCESS(f'\n   {ORDEM} apagada, com {len(linhas)} linha(s).'))
            w(st.SUCCESS(f'Gravado. Reversão em {REVERT}'))

    @staticmethod
    def _recusar_se_nao_for_rascunho(so):
        if so.status != 'draft':
            raise CommandError(
                f'{so.code} está "{so.status}", não em rascunho. Ordem '
                f'confirmada é documento: o caminho dela é CANCELAR, que '
                f'deixa rastro — não apagar.')
        pendurado = []
        if so.invoices.exists():
            pendurado.append('fatura')
        if so.settlements.exists():
            pendurado.append('acerto')
        if so.order_notes.exists():
            pendurado.append('nota do comprador')
        if pendurado:
            raise CommandError(
                f'{so.code} tem {", ".join(pendurado)} pendurado(s). Apagar '
                f'levaria junto (ou o banco recusaria) — resolva primeiro.')

    # ── serialização ─────────────────────────────────────────────────────
    def _serializar(self, so, linhas):
        return {
            'code': so.code,
            'lot_id': so.lot_id, 'buyer_id': so.buyer_id,
            'company_id': so.company_id,
            'created_at': so.created_at.isoformat(),
            'campos': {c: _txt(getattr(so, c)) for c in CAMPOS},
            'linhas': [{c: _txt(getattr(l, c)) for c in CAMPOS_LINHA}
                       for l in linhas],
        }

    # ── reversão ─────────────────────────────────────────────────────────
    def _revert(self):
        from datetime import date, datetime
        from vendas.models import SalesOrder, SalesOrderLine
        if not os.path.exists(REVERT):
            raise CommandError(f'Não há {REVERT} — nada a desfazer.')
        reg = json.load(open(REVERT))
        d = reg['ordem']
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        w = self.stdout.write

        with company_scope(empresa.id), transaction.atomic():
            campos = dict(d['campos'])
            so = SalesOrder(
                lot_id=d['lot_id'], buyer_id=d['buyer_id'],
                company_id=d['company_id'],
                number=int(campos.pop('number')),
                status=campos.pop('status'),
                code_str=campos.pop('code_str') or '',
                unkeyed_units=int(campos.pop('unkeyed_units') or 0),
                notes=campos.pop('notes') or '',
                carrier=campos.pop('carrier') or '',
                tracking=campos.pop('tracking') or '',
                shipped_at=(date.fromisoformat(campos.pop('shipped_at'))
                            if campos.get('shipped_at') else
                            campos.pop('shipped_at', None)),
                received_at=(datetime.fromisoformat(campos.pop('received_at'))
                             if campos.get('received_at') else
                             campos.pop('received_at', None)),
                fx_usd_rate=self._dec(campos.pop('fx_usd_rate')),
                total_rmb=self._dec(campos.pop('total_rmb')),
                total_usd=self._dec(campos.pop('total_usd')),
            )
            so.save()
            # `created_at` é auto_now_add: só volta ao original por update.
            SalesOrder.all_companies.filter(pk=so.pk).update(
                created_at=datetime.fromisoformat(d['created_at']))
            for ld in d['linhas']:
                SalesOrderLine.all_companies.create(
                    order=so, company_id=d['company_id'],
                    brand=ld['brand'] or '', kind=ld['kind'],
                    gen=ld['gen'] or '',
                    tier_value=self._dec(ld['tier_value']),
                    tier_unit=ld['tier_unit'] or '',
                    quantity=int(ld['quantity']),
                    unit_rmb=self._dec(ld['unit_rmb']),
                    unit_usd=self._dec(ld['unit_usd']))
            w(f'   {d["code"]} recriada com {len(d["linhas"])} linha(s) '
              f'(pk novo: {so.pk})')

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
