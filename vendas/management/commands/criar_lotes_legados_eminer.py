"""
criar_lotes_legados_eminer
==========================
Traz para dentro do sistema os três envios da eMiner que só existiam na
planilha mestra: CHIP-EXP012026, CHIP-EXP022026 e o K9.

Eles são anteriores ao sistema — nunca tiveram lote, ordem, fatura nem
pagamento aqui. Nascem com a cadeia inteira e já QUITADOS, e com o número que
o mapa de renumeração reserva para cada um (1, 2 e 4 — livres hoje, porque a
numeração da eMiner começa no 39).

O que cada um recebe:

  1. LOTE       fechado, com a origem legada da planilha (MIXED, PCB, K9), a
                data real de fechamento e o código carimbado com o MÊS DELE —
                não o de hoje. `LOT/EMI/001/04/26`, e não `/09/26`.
  2. ENTRADAS   só onde existem: o EXP02 tem os 20 part numbers da fatura e o
                K9 tem a sua linha única. SEM chave de preço no EXP02 — a
                fatura traz o PN na forma curta e deduzir capacidade a partir
                do preço seria inventar catálogo. O EXP01 não tem nenhuma.
  3. ORDEM      confirmada, Wu Quan, taxa e totais congelados.
  4. LINHA      só o K9: 5.507 × ¥1,00. Os outros dois carregam o valor no
                cabeçalho, como o lote 039.
  5. ACERTO     vazio — sem rejeição, o comprador ficou com tudo.
  6. FATURA     o valor da mestra, comissão de serviço congelada.
  7. PAGAMENTO  cheio, na data, com a carteira na referência. Saldo zero.

Regra de ouro: ESCREVE -> dry-run por padrão, e herda de SafeWriteCommand
(mostra o banco-alvo e exige digitar o nome dele no --commit).

Uso:
    python manage.py criar_lotes_legados_eminer            # dry-run
    python manage.py criar_lotes_legados_eminer --lote 2   # um só
    python manage.py criar_lotes_legados_eminer --commit
    python manage.py criar_lotes_legados_eminer --revert   # apaga o que criou

⚠ Só roda depois do `alinhar_vendas_eminer`, e ANTES da renumeração.
"""

import json
import os
from datetime import datetime, timezone as _tz
from decimal import ROUND_HALF_UP, Decimal as D

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from core.safe_command import SafeWriteCommand
from tenancy.models import Company
from tenancy.scope import company_scope
from vendas.alinhar_eminer_core import (COMPRADOR, EMPRESA_SLUG, LEGADOS,
                                        self_check_legados)

CENT = D('0.01')
REVERT = os.path.join(str(settings.BASE_DIR), 'var', 'reverts',
                      'criar_lotes_legados_eminer_revert.json')
MANTER_ANTIGOS = 10


class Command(SafeWriteCommand):
    help = 'Cria em produção os três lotes legados da eMiner, já quitados.'

    def add_arguments(self, parser):
        parser.add_argument('--lote', type=int, action='append', default=None)
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', action='store_true')

    def handle(self, *args, **o):
        if o['revert']:
            return self._revert()

        self_check_legados()
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        numeros = o['lote'] or sorted(LEGADOS)
        fora = [n for n in numeros if n not in LEGADOS]
        if fora:
            raise CommandError(f'Lote fora do plano legado: {fora}. '
                               f'O plano cobre {sorted(LEGADOS)}.')

        with company_scope(empresa.id):
            self._checar_espaco(numeros, empresa)
            for n in numeros:
                self._mostrar(n, empresa)

            if not o['commit']:
                self.stdout.write(self.style.WARNING(
                    '\nDRY-RUN — nada foi gravado. Use --commit para aplicar.'))
                return

            registro = {'quando': timezone.now().isoformat(), 'criados': {}}
            with transaction.atomic():
                for n in numeros:
                    registro['criados'][str(n)] = self._criar(n, empresa)
            self._gravar_revert(registro)
            self.stdout.write(self.style.SUCCESS(f'\nGravado. Reversão em {REVERT}'))

    # ── conferências que rodam ANTES de qualquer escrita ─────────────────
    def _checar_espaco(self, numeros, empresa):
        """Número livre e comprador único. Um lote com esse número já existindo
        significa que a renumeração rodou antes — pare, não sobrescreva."""
        from estoque.models import Lot
        from pricing.models import Buyer
        for n in numeros:
            if Lot.all_companies.filter(company=empresa, number=n).exists():
                raise CommandError(
                    f'Já existe lote {n} na eMiner. Este comando só cria em '
                    f'número livre — se a renumeração já rodou, o mapa mudou e '
                    f'este plano está velho.')
        if not Buyer.objects.filter(name=COMPRADOR, active=True).exists():
            raise CommandError(f'Comprador "{COMPRADOR}" não encontrado/ativo.')

    # ── mostrar ──────────────────────────────────────────────────────────
    def _mostrar(self, n, empresa):
        p = LEGADOS[n]
        w, st = self.stdout.write, self.style
        fee = empresa.service_fee_pct or D('0')
        fee_usd = (p['total_usd'] * fee / D('100')).quantize(CENT, ROUND_HALF_UP)
        codigo = self._codigo(empresa, n, p['data'])
        w('')
        w(st.MIGRATE_HEADING(f'━━ criar lote {n:03d} · {p["nome"]} ━━'))
        w(f'   {p["descricao"]}')
        w(f'   → código                 {codigo}   (mês do lote, não o de hoje)')
        w(f'   → origem                 {p["origin"]}   · fechado em {p["data"]:%d/%m/%Y}')
        w(f'   → entradas de estoque    {len(p["entradas"]):>3} part number(s) · '
          f'{sum(q for _a, q, _b, _c, _d in p["entradas"]):>6} un  '
          f'(declarado: {p["unidades"]})')
        if p['entradas'] and not p['linha_k9']:
            w(st.WARNING('     sem chave de preço — o valor fica no cabeçalho, '
                         'e a tela vai contá-las como "sem preço na tabela"'))
        w(f'   → ordem de venda         confirmada · {COMPRADOR} · taxa {p["fx"]}')
        w(f'   → linhas da ordem        {"1 (K9 plano, ¥1,00)" if p["linha_k9"] else "nenhuma"}')
        w(f'   → totais                 ¥ {p["total_rmb"]}  =  US$ {p["total_usd"]}')
        w(f'   → acerto                 vazio (sem rejeição)')
        w(f'   → fatura                 US$ {p["total_usd"]} · comissão {fee}% = '
          f'US$ {fee_usd} · líquido US$ {p["total_usd"] - fee_usd}')
        w(f'   → pagamento              US$ {p["total_usd"]} em '
          f'{p["pago_em"]:%d/%m/%Y} · {p["carteira"]}')
        if p.get('aviso'):
            w(st.WARNING(f'     ⚠ {p["aviso"]}'))

    def _codigo(self, empresa, numero, data):
        from tenancy.doc_code import doc_code
        return doc_code('LOT', empresa.code, numero, _meio_dia(data))

    # ── criar ────────────────────────────────────────────────────────────
    def _criar(self, n, empresa):
        from estoque.models import InventoryEntry, Lot
        from pricing.models import Buyer
        from vendas.models import (DocSequence, INV_OPEN, INV_PAID, Invoice,
                                   Payment, SEQ_INVOICE, SEQ_SO, SalesOrder,
                                   SalesOrderLine, STATUS_CONFIRMED, Settlement)
        p = LEGADOS[n]
        quando = _meio_dia(p['data'])
        feito = {}

        # 1. lote — código com o mês DELE, não o de hoje
        lot = Lot(company=empresa, number=n, description=p['descricao'],
                  status='closed', closed_at=quando, origin=p['origin'],
                  fx_rate=p['fx'], operator=self._operador(empresa),
                  code_str=self._codigo(empresa, n, p['data']))
        lot.save()
        # created_at é auto_now_add: só dá para corrigir DEPOIS do insert.
        Lot.all_companies.filter(pk=lot.pk).update(created_at=quando)
        feito['lot'] = lot.pk

        # 2. entradas
        feito['entradas'] = []
        for pn, qtd, marca, tipo, _y in p['entradas']:
            campos = dict(lot=lot, company=empresa, part_number=pn,
                          quantity=qtd, brand=marca, chip_type=tipo)
            if p['linha_k9']:                      # o K9 tem chave PLANA
                campos.update(price_kind=p['linha_k9']['kind'], price_gen='',
                              price_tier_value=p['linha_k9']['tier_value'],
                              price_tier_unit=p['linha_k9']['tier_unit'])
            e = InventoryEntry.all_companies.create(**campos)
            feito['entradas'].append(e.pk)

        # 3. ordem
        sem_chave = 0 if p['linha_k9'] else sum(q for _a, q, _b, _c, _d in p['entradas'])
        so = SalesOrder(
            lot=lot, buyer=Buyer.objects.get(name=COMPRADOR),
            number=DocSequence.next_number(empresa, SEQ_SO),
            status=STATUS_CONFIRMED, fx_usd_rate=p['fx'],
            total_rmb=p['total_rmb'], total_usd=p['total_usd'],
            unkeyed_units=sem_chave, confirmed_at=quando, received_at=quando)
        # code_str com o mês do LOTE, não o de hoje — o save() só carimba se
        # estiver vazio, então preencher aqui é o jeito de datar o documento
        # legado corretamente.
        so.code_str = _doc(empresa, 'SO', so.number, p['data'])
        so.save()
        SalesOrder.all_companies.filter(pk=so.pk).update(created_at=quando)
        feito['order'] = so.pk

        # 4. linha (só o K9)
        feito['linhas'] = []
        if p['linha_k9']:
            k = p['linha_k9']
            l = SalesOrderLine.all_companies.create(
                order=so, company=empresa, brand='', kind=k['kind'], gen='',
                tier_value=k['tier_value'], tier_unit=k['tier_unit'],
                quantity=p['unidades'], unit_rmb=k['unit_rmb'],
                unit_usd=(k['unit_rmb'] * p['fx']).quantize(CENT, ROUND_HALF_UP))
            feito['linhas'].append(l.pk)

        # 5. acerto
        st = Settlement(order=so, notes=(
            'Registro atrasado: envio anterior ao sistema. Sem rejeição — '
            'o comprador ficou com tudo.'))
        st.save()
        Settlement.all_companies.filter(pk=st.pk).update(created_at=quando)
        feito['settlement'] = st.pk

        # 6. fatura
        fee = empresa.service_fee_pct or D('0')
        inv = Invoice(order=so, settlement=st,
                      number=DocSequence.next_number(empresa, SEQ_INVOICE),
                      fx_usd_rate=p['fx'], total_rmb=p['total_rmb'],
                      total_usd=p['total_usd'], fee_pct=fee,
                      fee_rmb=(p['total_rmb'] * fee / D('100')).quantize(CENT, ROUND_HALF_UP),
                      fee_usd=(p['total_usd'] * fee / D('100')).quantize(CENT, ROUND_HALF_UP),
                      status=INV_OPEN)
        inv.code_str = _doc(empresa, 'INV', inv.number, p['data'])
        inv.save()
        Invoice.all_companies.filter(pk=inv.pk).update(issued_at=quando)
        feito['invoice'] = inv.pk

        # 7. pagamento
        pg = Payment(invoice=inv, amount_usd=p['total_usd'],
                     paid_at=p['pago_em'], reference=p['carteira'])
        pg.save()
        feito['payment'] = pg.pk
        inv.status = INV_PAID
        inv.save(update_fields=['status'])

        self.stdout.write(self.style.SUCCESS(
            f'   lote {n:03d} {lot.code}: {inv.code} US$ {inv.total_usd} PAGA'))
        return feito

    def _operador(self, empresa):
        """Quem 'abriu' o lote. Usa o operador dos lotes que já existem —
        inventar um usuário para carimbar passado seria pior."""
        from estoque.models import Lot
        l = Lot.all_companies.filter(company=empresa).order_by('number').first()
        if l is None:
            raise CommandError('Não há lote nesta empresa para herdar o operador.')
        return l.operator

    # ── reverter ─────────────────────────────────────────────────────────
    def _revert(self):
        if not os.path.exists(REVERT):
            raise CommandError(f'Não há {REVERT} — nada a desfazer.')
        reg = json.load(open(REVERT))
        from estoque.models import InventoryEntry, Lot
        from vendas.models import (Invoice, Payment, SalesOrder,
                                   SalesOrderLine, Settlement)
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        with company_scope(empresa.id), transaction.atomic():
            for numero, d in sorted(reg['criados'].items()):
                Payment.all_companies.filter(pk=d['payment']).delete()
                Invoice.all_companies.filter(pk=d['invoice']).delete()
                SalesOrderLine.all_companies.filter(pk__in=d['linhas']).delete()
                Settlement.all_companies.filter(pk=d['settlement']).delete()
                SalesOrder.all_companies.filter(pk=d['order']).delete()
                InventoryEntry.all_companies.filter(pk__in=d['entradas']).delete()
                Lot.all_companies.filter(pk=d['lot']).delete()
                self.stdout.write(f'   lote {numero}: apagado')
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


def _doc(empresa, tipo, numero, data):
    from tenancy.doc_code import doc_code
    return doc_code(tipo, empresa.code, numero, _meio_dia(data))


def _meio_dia(d):
    return datetime(d.year, d.month, d.day, 12, 0, tzinfo=_tz.utc)
