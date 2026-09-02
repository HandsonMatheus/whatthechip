"""
demo_repasse_automatico
=======================
Mostra, no terminal, o que a chave ``Company.payout_on_payment`` faz — e
deixa, se você pedir, uma venda de demonstração para conferir NA TELA.

Por que existe: a chave muda o SIGNIFICADO do extrato do cliente (ligada, o
repasse é lançado sozinho quando o comprador quita), e ninguém deveria ter de
acreditar num resumo de chat para saber disso. Aqui a regra se executa na sua
frente, contra o seu banco, com os números aparecendo.

    python manage.py demo_repasse_automatico
        SIMULA os cinco cenários numa transação que é DESFEITA no fim. Não
        grava nada, nem sequer o contador de documento. Pode rodar quantas
        vezes quiser.

    python manage.py demo_repasse_automatico --commit --user <seu-usuário>
        PLANTA uma venda de demonstração (empresa nova "DEMO Repasse", fatura
        em aberto, chave LIGADA) para você pagar pela tela do comprador e ver
        o repasse nascer. Imprime os endereços.

    python manage.py demo_repasse_automatico --revert
        Remove a venda de demonstração e a empresa junto.

⚠ RECUSA banco que não seja local. É comando de laboratório: ele cria empresa
  e venda falsas, e dado falso em produção é pior que bug — é mentira no
  extrato de alguém. A trava é por HOST e por NOME do banco, não por confiança.

⚠ A simulação constrói o cenário sob `platform_scope()` (comprador é linha de
  PLATAFORMA) e roda os pagamentos sob `company_scope()`, que é como a request
  de verdade roda. Sem isso, num banco com RLS de verdade, a leitura voltaria
  vazia em silêncio — a armadilha do CLAUDE.md §7.
"""

import json
import os
from datetime import date, timedelta
from decimal import Decimal as D

from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection, transaction

from core.safe_command import SafeWriteCommand
from tenancy.scope import company_scope, platform_scope

EMPRESA_SLUG = 'demo-repasse'
EMPRESA_NOME = 'DEMO Repasse (apagar)'
REVERT = os.path.join(str(settings.BASE_DIR), 'var', 'reverts',
                      'demo_repasse_automatico_revert.json')
#: Hosts que aceitamos como "meu computador". Qualquer outro é recusado.
HOSTS_LOCAIS = {'', 'localhost', '127.0.0.1', '::1'}
TOTAL = D('1000.00')
TAXA = D('10.00')
LIQUIDO = D('900.00')
ONTEM = date.today() - timedelta(days=1)


class _Desfazer(Exception):
    """Sentinela: sobe no fim da simulação para a transação ser revertida."""


class Command(SafeWriteCommand):
    help = ('LABORATÓRIO (só banco local): mostra o que a chave '
            'payout_on_payment faz, simulando em transação revertida; com '
            '--commit planta uma venda de demonstração para conferir na tela.')

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', action='store_true')
        parser.add_argument('--user', default='',
                            help='Usuário que vai abrir as telas (recebe '
                                 'vínculo de admin na empresa de demonstração).')
        parser.add_argument('--buyer', default='',
                            help='Slug do comprador. Sem isto, o comando '
                                 'procura o comprador do --user.')

    # ── entrada ──────────────────────────────────────────────────────────
    def handle(self, *args, **o):
        self.w, self.st = self.stdout.write, self.style
        self._exigir_banco_local()
        if o['revert']:
            return self._revert()
        if o['commit']:
            return self._plantar(o)
        return self._simular()

    def _exigir_banco_local(self):
        """A trava que impede este comando de existir em produção.

        O banner do SafeWriteCommand avisa; isto RECUSA. A diferença importa:
        aviso depende de alguém estar lendo às 3 da manhã.
        """
        d = connection.settings_dict
        host = (d.get('HOST') or '').strip().lower()
        nome = (d.get('NAME') or '')
        if host not in HOSTS_LOCAIS:
            raise CommandError(
                f'Banco remoto ({host}) — este comando é de laboratório e só '
                f'roda em banco local.\nEle CRIA empresa e venda falsas; isso '
                f'não pode acontecer em produção.')
        if 'render' in host or nome == 'whatthechip_db':
            raise CommandError(f'Banco "{nome}" parece produção. Recusado.')

    # ── simulação (padrão) ───────────────────────────────────────────────
    def _simular(self):
        self.w('')
        self.w(self.st.MIGRATE_HEADING(
            '━━ repasse automático · simulação · NADA é gravado ━━'))
        self.w(f'   banco   {connection.settings_dict.get("NAME")} '
               f'@ {connection.settings_dict.get("HOST") or "local"}')
        self.w(f'   venda   US$ {TOTAL} · taxa {TAXA}% · líquido US$ {LIQUIDO}')
        try:
            with transaction.atomic():
                self._cenarios()
                raise _Desfazer
        except _Desfazer:
            pass
        self.w('')
        self.w(self.st.SUCCESS(
            '   ✓ Transação desfeita. Nada acima existe no banco — nem a '
            'empresa, nem\n     as vendas, nem os contadores de documento.'))
        self.w('')
        self.w('   Para conferir na TELA:')
        self.w('     python manage.py demo_repasse_automatico --commit '
               '--user <seu-usuário>')
        self.w('')

    def _cenarios(self):
        from vendas import services
        from vendas.models import Payout

        def repasses(inv):
            return list(Payout.all_companies.filter(invoice=inv)
                        .order_by('created_at'))

        comprador, operador = self._comprador_demo(), self._operador()

        # ── 1. chave DESLIGADA ───────────────────────────────────────────
        self._titulo('1. chave DESLIGADA (o padrão de toda empresa)')
        emp = self._empresa(ligada=False, slug=EMPRESA_SLUG + '-desligada')
        inv = self._venda(emp, comprador, 1, operador)
        with company_scope(emp.id):
            services.register_payment(inv, TOTAL, ONTEM, None,
                                      reference='TRONLINK 4471')
        inv.refresh_from_db()
        self._diz('fatura do comprador', inv.status)
        self._diz('repasses lançados', len(repasses(inv)),
                  'o WTC ainda precisa transferir e registrar à mão')

        # ── 2. chave LIGADA ──────────────────────────────────────────────
        self._titulo('2. chave LIGADA — o comprador quita a fatura')
        emp = self._empresa(ligada=True, slug=EMPRESA_SLUG + '-ligada')
        inv = self._venda(emp, comprador, 1, operador)
        with company_scope(emp.id):
            services.register_payment(inv, TOTAL, ONTEM, None,
                                      reference='TRONLINK 4471')
        inv.refresh_from_db()
        (rep,) = repasses(inv)
        self._diz('fatura do comprador', inv.status)
        self._diz('repasse — valor', f'US$ {rep.amount_usd}',
                  f'é o LÍQUIDO (bruto {TOTAL} − taxa {TAXA}%), não o total')
        self._diz('repasse — data', rep.paid_at,
                  'a do PAGAMENTO, não a de hoje')
        self._diz('repasse — autor', rep.created_by or '(vazio)',
                  'ninguém digitou: ele decorre do pagamento')
        self._diz('repasse — referência', rep.reference,
                  'a referência da wire viaja junto')
        self._diz('saldo a repassar', f'US$ {inv.payout_balance_usd}')

        # ── 3. parcelas ──────────────────────────────────────────────────
        self._titulo('3. chave LIGADA — pagamento PARCELADO')
        inv = self._venda(emp, comprador, 2, operador)
        with company_scope(emp.id):
            services.register_payment(inv, D('400.00'), ONTEM - timedelta(30),
                                      None, reference='1a parcela')
        inv.refresh_from_db()
        self._diz('depois da 1ª parcela (US$ 400)',
                  f'{inv.status} · {len(repasses(inv))} repasse(s)',
                  'metade do bruto não é metade do líquido — não se rateia')
        with company_scope(emp.id):
            services.register_payment(inv, D('600.00'), ONTEM, None,
                                      reference='2a parcela')
        inv.refresh_from_db()
        (rep,) = repasses(inv)
        self._diz('depois da 2ª parcela (US$ 600)',
                  f'{inv.status} · US$ {rep.amount_usd} em {rep.paid_at}',
                  'sai inteiro de uma vez, com a data em que a conta fechou')

        # ── 4. repasse manual anterior ───────────────────────────────────
        self._titulo('4. chave LIGADA — mas alguém já repassou À MÃO')
        inv = self._venda(emp, comprador, 3, operador)
        with company_scope(emp.id):
            services.register_payout(inv, D('300.00'), ONTEM - timedelta(10),
                                     None, reference='adiantamento manual')
            services.register_payment(inv, TOTAL, ONTEM, None,
                                      reference='TRONLINK 4599')
        inv.refresh_from_db()
        for r in repasses(inv):
            self._diz('repasse', f'US$ {r.amount_usd} · {r.reference}')
        self._diz('total repassado', f'US$ {inv.paid_out_usd:.2f}',
                  'o automático completou só o que faltava — não dobrou')

        # ── 5. a guarda do valor ─────────────────────────────────────────
        self._titulo('5. o que NÃO acontece')
        self.w('            fatura já quitada não aceita novo pagamento '
               '(portão antigo)')
        self.w('            repasse automático nunca passa do líquido — o '
               'valor É o saldo')
        self.w('            se o repasse falhar, o PAGAMENTO cai junto: '
               'mesma transação')

    # ── plantio da demonstração (--commit) ───────────────────────────────
    def _plantar(self, o):
        from django.contrib.auth import get_user_model
        from tenancy.models import Company, Membership
        if not o['user']:
            raise CommandError(
                '--user é obrigatório no --commit: é a conta que vai abrir as '
                'telas.\nEla recebe vínculo de admin na empresa de '
                'demonstração (removido no --revert).')
        User = get_user_model()
        try:
            usuario = User.objects.get(username=o['user'])
        except User.DoesNotExist:
            raise CommandError(f'Usuário "{o["user"]}" não existe neste banco.')
        if Company.objects.filter(slug=EMPRESA_SLUG).exists():
            raise CommandError(
                'A demonstração já está plantada. Rode --revert antes de '
                'plantar de novo.')

        comprador = self._achar_comprador(o, usuario)
        registro = {'empresa': None, 'membership': None, 'lot': None,
                    'so': None, 'invoice': None}
        with transaction.atomic():
            emp = self._empresa(ligada=True, slug=EMPRESA_SLUG)
            inv = self._venda(emp, comprador, 1, usuario)
            vinculo = Membership.objects.create(user=usuario, company=emp,
                                                role='admin', active=True)
            registro.update(empresa=emp.pk, membership=vinculo.pk,
                            lot=inv.order.lot_id, so=inv.order_id,
                            invoice=inv.pk)
        self._gravar_revert(registro)

        self.w('')
        self.w(self.st.SUCCESS('   ✓ Demonstração plantada.'))
        self.w(f'   empresa    {emp.name} (chave LIGADA)')
        self.w(f'   comprador  {comprador.name}')
        self.w(f'   venda      {inv.order.code} · fatura {inv.code} '
               f'· US$ {TOTAL} em aberto')
        self.w('')
        self.w('   1) TELA DO COMPRADOR — /partner/  → abra esta compra, pague')
        self.w(f'      os US$ {TOTAL} (o comprovante é obrigatório: serve '
               f'qualquer PDF ou foto).')
        self.w('   2) TELA DO CLIENTE  — /vendas/ordens/ → abra a mesma venda:')
        self.w(f'      "Repassado" tem que mostrar US$ {LIQUIDO} e o saldo a '
               f'repassar, US$ 0,00.')
        self.w(f'      O repasse aparece com a data que você digitou e sem '
               f'autor.')
        self.w('   3) Compare: com a chave DESLIGADA (admin da empresa), o '
               'mesmo pagamento')
        self.w('      deixaria "Repassado US$ 0,00" — que é o estado de hoje '
               'em produção.')
        self.w('')
        self.w(self.st.WARNING(
            '   Ao terminar: python manage.py demo_repasse_automatico --revert'))
        self.w('')

    def _achar_comprador(self, o, usuario):
        from pricing.models import Buyer
        with platform_scope():
            if o['buyer']:
                b = Buyer.all_companies.filter(slug=o['buyer']).first()
                if b is None:
                    raise CommandError(f'Comprador "{o["buyer"]}" não existe.')
                return b
            b = Buyer.all_companies.filter(users=usuario, active=True).first()
            if b is not None:
                return b
            ativos = list(Buyer.all_companies.filter(active=True)[:3])
        if len(ativos) == 1:
            return ativos[0]
        raise CommandError(
            f'O usuário "{usuario}" não está vinculado a nenhum comprador e há '
            f'{len(ativos)} compradores ativos.\nDiga qual usar: '
            f'--buyer <slug>. (A tela do comprador só abre para uma conta '
            f'vinculada.)')

    # ── construção do cenário ────────────────────────────────────────────
    def _empresa(self, ligada, slug):
        """A empresa-cliente de demonstração, com a chave no estado pedido.

        `code=''` de propósito: é o formato legado, o mesmo da eMiner, para os
        códigos de documento saírem iguais aos que você vê hoje na tela.
        """
        from tenancy.models import Company
        return Company.objects.create(
            name=f'{EMPRESA_NOME} · {"ligada" if ligada else "desligada"}',
            slug=slug, code='', service_fee_pct=TAXA,
            payout_on_payment=ligada,
            notes='Empresa de demonstração do repasse automático. '
                  'Apagar com: demo_repasse_automatico --revert')

    def _comprador_demo(self):
        """⚠ `platform_scope`: comprador é linha de PLATAFORMA (`company IS
        NULL`) e a policy de ESCRITA não é satisfeita pelo GUC de empresa —
        sem isto o INSERT é recusado (ou some em silêncio). CLAUDE.md §7."""
        from pricing.models import Buyer
        with platform_scope():
            b, _ = Buyer.all_companies.get_or_create(
                slug='demo-comprador',
                defaults=dict(company=None, name='Comprador de demonstração'))
        return b

    def _operador(self):
        """Quem "abriu" o lote. Qualquer conta serve — o lote é da EMPRESA,
        não dele. Só existe dentro da transação desfeita."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        u = User.objects.order_by('pk').first()
        return u or User.objects.create_user('demo_repasse_op')

    def _venda(self, emp, comprador, numero, operador):
        """OV despachada + fatura EM ABERTO, com a taxa congelada."""
        from estoque.models import Lot
        from vendas.models import (DocSequence, SEQ_INVOICE, SEQ_SO, Invoice,
                                   SalesOrder)
        fee = (TOTAL * TAXA / D('100')).quantize(D('0.01'))
        with company_scope(emp.id):
            lot = Lot.all_companies.create(
                company=emp, number=numero, status='closed', origin='phone',
                operator=operador,
                description='Lote de demonstração — repasse automático')
            so = SalesOrder(
                lot=lot, buyer=comprador, status='confirmed',
                fx_usd_rate=D('0.1500'), total_rmb=TOTAL, total_usd=TOTAL,
                unkeyed_units=1200, shipped_at=ONTEM - timedelta(2),
                **dict(zip(('doc_year', 'number'),
                           SalesOrder.next_for_lot(lot))))
            so.save()
            inv = Invoice(
                order=so, status='open', fx_usd_rate=D('0.1500'),
                total_rmb=TOTAL, total_usd=TOTAL,
                fee_pct=TAXA, fee_rmb=fee, fee_usd=fee,
                number=DocSequence.next_number(emp, SEQ_INVOICE))
            inv.save()
        return inv

    # ── reversão ─────────────────────────────────────────────────────────
    def _revert(self):
        from estoque.models import Lot
        from tenancy.models import Company, Membership
        from vendas.models import Invoice, Payment, Payout, SalesOrder
        if not os.path.exists(REVERT):
            raise CommandError(f'Não há {REVERT} — nada plantado a remover.')
        reg = json.load(open(REVERT))
        emp = Company.objects.filter(pk=reg['empresa']).first()
        if emp is None:
            os.remove(REVERT)
            self.w(self.st.WARNING('Empresa já não existe — registro '
                                   'descartado.'))
            return
        # Ordem inversa da criação: as FKs são PROTECT de propósito.
        with platform_scope(), transaction.atomic():
            n_out = Payout.all_companies.filter(
                invoice_id=reg['invoice']).delete()[0]
            n_pag = Payment.all_companies.filter(
                invoice_id=reg['invoice']).delete()[0]
            Invoice.all_companies.filter(pk=reg['invoice']).delete()
            SalesOrder.all_companies.filter(pk=reg['so']).delete()
            Lot.all_companies.filter(pk=reg['lot']).delete()
            Membership.objects.filter(pk=reg['membership']).delete()
            emp.delete()
        os.remove(REVERT)
        self.w(self.st.SUCCESS(
            f'Removido: {n_pag} pagamento(s), {n_out} repasse(s), a venda, o '
            f'lote e a empresa "{EMPRESA_NOME}".'))

    def _gravar_revert(self, registro):
        os.makedirs(os.path.dirname(REVERT), exist_ok=True)
        with open(REVERT, 'w') as f:
            json.dump(registro, f, indent=1)

    # ── relato ───────────────────────────────────────────────────────────
    def _titulo(self, t):
        self.w('')
        self.w(f'   ── {t} ' + '─' * max(0, 58 - len(t)))

    def _diz(self, rotulo, valor, porque=''):
        self.w(f'      {rotulo:<32} {valor}')
        if porque:
            self.w(self.st.HTTP_INFO(f'      {"":<32} ↳ {porque}'))
