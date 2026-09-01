"""
alinhar_vendas_eminer
=====================
Põe as vendas FECHADAS da eMiner no estado que a planilha mestra
(`VENDAS EMINER.xlsx`) diz que elas têm na vida real: preço nas linhas, taxa
certa, conferência, fatura e pagamento — tudo já quitado.

Esses lotes rodaram ANTES de a cadeia de conferência existir no sistema. Não é
achado a investigar; é registro atrasado a lançar.

O que cada lote recebe:

  1. ORDEM      taxa ¥→US$ correta, total ¥ e US$ congelados, `received_at`
                (se estiver vazio) na data de fechamento do lote.
  2. LINHAS     040 e 041 ganham ¥ unitário vindo do detalhe do lote; o 039
                tem as suas LIMPAS — o preço dele foi repactuado depois da
                cotação e ninguém guardou a quebra por categoria.
  3. ACERTO     um `Settlement` vazio: sem rejeição, o comprador ficou com
                tudo. É o registro de "resultado sem diferenças". O 039 já tem
                o seu, e ele é mantido.
  4. FATURA     no valor da mestra, com a comissão de serviço congelada. Se já
                houver fatura ATIVA com outro valor, ela é cancelada e uma nova
                é emitida — que é o caminho de re-acerto que o modelo prevê.
  5. PAGAMENTO  o valor cheio, na data de fechamento, com a carteira na
                referência. Saldo zero, fatura PAGA.

Regra de ouro: este comando ESCREVE -> roda em --dry-run por padrão, e herda de
SafeWriteCommand (imprime o banco-alvo e exige digitar o nome dele no --commit).

Uso:
    python manage.py alinhar_vendas_eminer                 # dry-run
    python manage.py alinhar_vendas_eminer --lote 40       # um lote só
    python manage.py alinhar_vendas_eminer --commit        # grava
    python manage.py alinhar_vendas_eminer --revert        # desfaz o último

Reversível: o --commit grava `var/reverts/alinhar_vendas_eminer_revert.json`
com o estado ANTERIOR de cada campo tocado e o id de tudo que foi criado;
--revert restaura os campos e apaga o que nasceu.
"""

import json
import os
from datetime import datetime, timezone as _tz
from decimal import ROUND_HALF_UP, Decimal as D

from django.core.management.base import CommandError
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.safe_command import SafeWriteCommand
from tenancy.models import Company
from tenancy.scope import company_scope
from vendas.alinhar_eminer_core import COMPRADOR, EMPRESA_SLUG, PLANO, chave, self_check


def _precos():
    """Import tardio de propósito: assim o teste consegue trocar a tabela."""
    from vendas.alinhar_eminer_core import PRECOS
    return PRECOS

CENT = D('0.01')
REVERT = os.path.join(str(settings.BASE_DIR), 'var', 'reverts',
                      'alinhar_vendas_eminer_revert.json')


class Command(SafeWriteCommand):
    help = ('Alinha as vendas fechadas da eMiner à planilha mestra: preço, '
            'taxa, acerto, fatura e pagamento — tudo quitado.')

    def add_arguments(self, parser):
        parser.add_argument('--lote', type=int, action='append', default=None,
                            help='Só este lote (pode repetir). Padrão: todos do plano.')
        parser.add_argument('--commit', action='store_true',
                            help='Grava. Sem isto, só mostra o que faria.')
        parser.add_argument('--revert', action='store_true',
                            help='Desfaz o último --commit.')

    # ─────────────────────────────────────────────────────────────────────
    def handle(self, *args, **o):
        if o['revert']:
            return self._revert()

        self_check(PLANO, _precos())
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        lotes = o['lote'] or sorted(PLANO)
        desconhecidos = [n for n in lotes if n not in PLANO]
        if desconhecidos:
            raise CommandError(f'Lote fora do plano: {desconhecidos}. '
                               f'O plano cobre {sorted(PLANO)}.')

        with company_scope(empresa.id):
            planos = [self._planejar(n, empresa) for n in lotes]

            for p in planos:
                self._mostrar(p)

            if not o['commit']:
                self.stdout.write(self.style.WARNING(
                    '\nDRY-RUN — nada foi gravado. Use --commit para aplicar.'))
                return

            registro = {'quando': timezone.now().isoformat(), 'lotes': {}}
            with transaction.atomic():
                for p in planos:
                    registro['lotes'][str(p['lote'])] = self._aplicar(p, empresa)
            self._gravar_revert(registro)
            self.stdout.write(self.style.SUCCESS(
                f'\nGravado. Reversão em {REVERT}'))

    # ─── planejar (não toca no banco) ────────────────────────────────────
    def _planejar(self, numero, empresa):
        from estoque.models import Lot
        from vendas.models import INV_CANCELLED, STATUS_CONFIRMED, Invoice

        alvo = PLANO[numero]
        try:
            lot = Lot.objects.get(number=numero)
        except Lot.DoesNotExist:
            raise CommandError(f'Lote {numero} não existe nesta base.')
        ovs = list(lot.sales_orders.filter(status=STATUS_CONFIRMED))
        if len(ovs) != 1:
            raise CommandError(
                f'Lote {numero}: esperava 1 OV confirmada, achei {len(ovs)}.')
        ov = ovs[0]
        if ov.number != alvo['ov']:
            raise CommandError(
                f'Lote {numero}: o plano fala da OV {alvo["ov"]}, mas a '
                f'confirmada é a {ov.number} ({ov.code}). Recuso mexer.')
        if ov.buyer.name != COMPRADOR:
            raise CommandError(
                f'Lote {numero}: comprador é "{ov.buyer.name}", esperava '
                f'"{COMPRADOR}".')

        linhas = list(ov.lines.all())
        precos = {}
        if alvo['precos']:
            tab = _precos()[numero]
            faltando = [chave(l) for l in linhas if chave(l) not in tab]
            if faltando:
                raise CommandError(
                    f'Lote {numero}: {len(faltando)} linha(s) sem preço na '
                    f'tabela — a primeira é {faltando[0]}. Recuso gravar '
                    f'fatura a menos.')
            soma = D('0.00')
            for l in linhas:
                u = D(tab[chave(l)])
                precos[l.pk] = u
                soma += u * l.quantity
            if soma != alvo['total_rmb']:
                raise CommandError(
                    f'Lote {numero}: a tabela soma ¥{soma}, o plano diz '
                    f'¥{alvo["total_rmb"]}. Diferença de ¥{soma - alvo["total_rmb"]}.')

        fatura_ativa = Invoice.objects.filter(order=ov).exclude(
            status=INV_CANCELLED).first()

        return dict(lote=numero, lot=lot, ov=ov, linhas=linhas, precos=precos,
                    fatura_ativa=fatura_ativa, alvo=alvo, empresa=empresa)

    # ─── mostrar ─────────────────────────────────────────────────────────
    def _mostrar(self, p):
        a, ov = p['alvo'], p['ov']
        w, st = self.stdout.write, self.style
        w('')
        w(st.MIGRATE_HEADING(
            f'━━ lote {p["lote"]:03d} · {ov.code} · {len(p["linhas"])} linhas '
            f'· {sum(l.quantity for l in p["linhas"])} un ━━'))
        w(f'   {a["nota"]}')

        def campo(rot, de, para):
            marca = '  ' if str(de) == str(para) else '→ '
            w(f'   {marca}{rot:<22} {str(de):>14}   →  {str(para):>14}')

        campo('taxa ¥→US$', ov.fx_usd_rate, a['fx'])
        campo('total ¥', ov.total_rmb, a['total_rmb'])
        campo('total US$', ov.total_usd, a['total_usd'])
        campo('recebido em', ov.received_at.date() if ov.received_at else '—',
              a['data'] if not ov.received_at else ov.received_at.date())
        # O `received_at` só é preenchido se estiver vazio — mexer numa data que
        # alguém pôs de propósito seria passar por cima de fato. Mas quando a
        # data existente é POSTERIOR ao fechamento do lote, ela não é fato: é
        # efeito colateral do settle_and_invoice, que carimba o recebimento na
        # hora em que o acerto nasce. Aviso em vez de decidir.
        if ov.received_at and ov.received_at.date() > a['data']:
            w(st.WARNING(
                f'     ⚠ o recebimento diz {ov.received_at.date():%d/%m/%Y}, '
                f'{(ov.received_at.date() - a["data"]).days} dias DEPOIS de o lote '
                f'fechar ({a["data"]:%d/%m/%Y}). Isso é carimbo do acerto de '
                f'30/08, não a data em que a caixa chegou. Não vou mexer sem '
                f'você mandar.'))

        com_preco = sum(1 for l in p['linhas'] if l.unit_rmb is not None)
        if a['precos']:
            w(f'   → preço por linha        {com_preco:>3} com preço hoje   '
              f'→  {len(p["linhas"])} com preço')
            derivado = (a['total_rmb'] * a['fx']).quantize(CENT, ROUND_HALF_UP)
            if derivado != a['total_usd']:
                w(st.WARNING(
                    f'     nota: ¥{a["total_rmb"]} × {a["fx"]} = US$ {derivado}, '
                    f'e a mestra diz US$ {a["total_usd"]}. Fica o da mestra — '
                    f'senão o pagamento não zera o saldo e a fatura nunca fica PAGA.'))
        else:
            w(f'   → preço por linha        {com_preco:>3} com preço hoje   '
              f'→  0 (limpo; valor no cabeçalho)')

        w(f'   → acerto                 '
          + ('já existe, mantido' if p['ov'].settlements.exists() else 'criar, vazio (sem rejeição)'))

        fee = (p['empresa'].service_fee_pct or D('0'))
        fee_usd = (a['total_usd'] * fee / D('100')).quantize(CENT, ROUND_HALF_UP)
        if p['fatura_ativa']:
            f = p['fatura_ativa']
            w(f'   → fatura                 {f.code} US$ {f.total_usd} ({f.status})'
              f'  →  CANCELAR e reemitir US$ {a["total_usd"]}')
        else:
            w(f'   → fatura                 nenhuma          →  emitir US$ {a["total_usd"]}')
        w(f'     comissão {fee}%          US$ {fee_usd}   ·  líquido US$ '
          f'{a["total_usd"] - fee_usd}')
        pago = a.get('pago_em') or a['data']
        extra = '' if pago == a['data'] else f'  (fechou em {a["data"]:%d/%m})'
        w(f'   → pagamento              nenhum           →  US$ {a["total_usd"]} '
          f'em {pago:%d/%m/%Y} · {a["carteira"]}{extra}')

    # ─── aplicar ─────────────────────────────────────────────────────────
    def _aplicar(self, p, empresa):
        from vendas.models import (DocSequence, INV_CANCELLED, INV_OPEN,
                                   INV_PAID, Invoice, Payment, SEQ_INVOICE,
                                   Settlement)
        a, ov = p['alvo'], p['ov']
        antes = {'ov': {'pk': ov.pk,
                        'fx_usd_rate': _s(ov.fx_usd_rate),
                        'total_rmb': _s(ov.total_rmb),
                        'total_usd': _s(ov.total_usd),
                        'received_at': _s(ov.received_at)},
                 'linhas': {}, 'criados': {}, 'fatura_cancelada': None}

        # 1+2. ordem e linhas
        ov.fx_usd_rate, ov.total_rmb, ov.total_usd = a['fx'], a['total_rmb'], a['total_usd']
        if ov.received_at is None:
            ov.received_at = _meio_dia(a['data'])
        ov.save(update_fields=['fx_usd_rate', 'total_rmb', 'total_usd', 'received_at'])

        for l in p['linhas']:
            antes['linhas'][str(l.pk)] = {'unit_rmb': _s(l.unit_rmb),
                                          'unit_usd': _s(l.unit_usd)}
            if a['precos']:
                l.unit_rmb = p['precos'][l.pk]
                l.unit_usd = (l.unit_rmb * a['fx']).quantize(CENT, ROUND_HALF_UP)
            else:
                l.unit_rmb = l.unit_usd = None
            l.save(update_fields=['unit_rmb', 'unit_usd'])

        # 3. acerto
        st = ov.settlements.first()
        if st is None:
            st = Settlement(order=ov, notes=(
                'Registro atrasado: este lote rodou antes de a conferência '
                'existir no sistema. Sem rejeição — o comprador ficou com tudo.'))
            st.save()
            antes['criados']['settlement'] = st.pk

        # 4. fatura
        if p['fatura_ativa'] is not None:
            f = p['fatura_ativa']
            if f.payments.exists():
                raise CommandError(
                    f'Lote {p["lote"]}: a fatura {f.code} já tem pagamento — '
                    f'não se cancela. Pare e trate à mão.')
            f.status, f.cancelled_at = INV_CANCELLED, timezone.now()
            f.save()
            antes['fatura_cancelada'] = f.pk

        fee = (empresa.service_fee_pct or D('0'))
        inv = Invoice(
            order=ov, settlement=st,
            number=DocSequence.next_number(empresa, SEQ_INVOICE),
            fx_usd_rate=a['fx'], total_rmb=a['total_rmb'], total_usd=a['total_usd'],
            fee_pct=fee,
            fee_rmb=(a['total_rmb'] * fee / D('100')).quantize(CENT, ROUND_HALF_UP),
            fee_usd=(a['total_usd'] * fee / D('100')).quantize(CENT, ROUND_HALF_UP),
            status=INV_OPEN)
        inv.save()
        antes['criados']['invoice'] = inv.pk

        # 5. pagamento
        pg = Payment(invoice=inv, amount_usd=a['total_usd'],
                     paid_at=a.get('pago_em') or a['data'],
                     reference=a['carteira'])
        pg.save()
        antes['criados']['payment'] = pg.pk
        inv.status = INV_PAID
        inv.save(update_fields=['status'])

        self.stdout.write(self.style.SUCCESS(
            f'   lote {p["lote"]:03d}: {inv.code} US$ {inv.total_usd} PAGA'))
        return antes

    # ─── reverter ────────────────────────────────────────────────────────
    def _revert(self):
        if not os.path.exists(REVERT):
            raise CommandError(f'Não há {REVERT} — nada a desfazer.')
        reg = json.load(open(REVERT))
        from vendas.models import (Invoice, Payment, SalesOrder,
                                   SalesOrderLine, Settlement)
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        with company_scope(empresa.id), transaction.atomic():
            for numero, d in sorted(reg['lotes'].items()):
                for modelo, campo in ((Payment, 'payment'), (Invoice, 'invoice'),
                                      (Settlement, 'settlement')):
                    pk = d['criados'].get(campo)
                    if pk:
                        modelo.all_companies.filter(pk=pk).delete()
                if d['fatura_cancelada']:
                    f = Invoice.all_companies.get(pk=d['fatura_cancelada'])
                    f.status, f.cancelled_at = 'open', None
                    f.save()
                ov = SalesOrder.all_companies.get(pk=d['ov']['pk'])
                ov.fx_usd_rate = _d(d['ov']['fx_usd_rate'])
                ov.total_rmb = _d(d['ov']['total_rmb'])
                ov.total_usd = _d(d['ov']['total_usd'])
                ov.received_at = _dt(d['ov']['received_at'])
                ov.save(update_fields=['fx_usd_rate', 'total_rmb', 'total_usd',
                                       'received_at'])
                for pk, v in d['linhas'].items():
                    l = SalesOrderLine.all_companies.get(pk=int(pk))
                    l.unit_rmb, l.unit_usd = _d(v['unit_rmb']), _d(v['unit_usd'])
                    l.save(update_fields=['unit_rmb', 'unit_usd'])
                self.stdout.write(f'   lote {numero}: desfeito')
        os.rename(REVERT, REVERT + '.' + timezone.now().strftime('%Y%m%d_%H%M%S') + '.usado')
        self._podar()
        self.stdout.write(self.style.SUCCESS('Revertido.'))

    #: Quantos reverts antigos guardar. O `refresh_lote` não tem teto e
    #: acumulou 231 arquivos entre julho e agosto — histórico que ninguém lê e
    #: que esconde o único que importa, o mais recente.
    MANTER_ANTIGOS = 10

    def _gravar_revert(self, registro):
        os.makedirs(os.path.dirname(REVERT), exist_ok=True)
        if os.path.exists(REVERT):
            os.rename(REVERT, REVERT + '.' +
                      timezone.now().strftime('%Y%m%d_%H%M%S') + '.bak')
        with open(REVERT, 'w') as f:
            json.dump(registro, f, indent=1, ensure_ascii=False)
        self._podar()

    def _podar(self):
        """Deixa só os MANTER_ANTIGOS mais recentes."""
        pasta, base = os.path.dirname(REVERT), os.path.basename(REVERT)
        antigos = sorted(f for f in os.listdir(pasta)
                         if f.startswith(base + '.'))
        for f in antigos[:-self.MANTER_ANTIGOS]:
            os.remove(os.path.join(pasta, f))


def _s(v):
    return None if v is None else (v.isoformat() if hasattr(v, 'isoformat') else str(v))


def _d(v):
    return None if v is None else D(v)


def _dt(v):
    return None if v is None else datetime.fromisoformat(v)


def _meio_dia(d):
    """Meio-dia UTC do dia — evita que fuso empurre a data para a véspera."""
    return datetime(d.year, d.month, d.day, 12, 0, tzinfo=_tz.utc)
