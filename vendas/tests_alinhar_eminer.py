"""
Testes do `alinhar_vendas_eminer` — o comando que põe as vendas fechadas da
eMiner no estado que a planilha mestra diz que elas têm.

Duas camadas, como a casa exige:

  SCRIPT     a aritmética do plano (sem banco) e o comando de ponta a ponta —
             dry-run não grava, --commit grava o esperado, --revert devolve o
             estado byte a byte, e cada recusa recusa mesmo.
  INTERFACE  a tela do comprador depois da correção: o valor que ele vê é o
             que foi pago, e a compra aparece quitada.

O plano real fala dos lotes 39/40/41 da eMiner em produção. Aqui ele é
trocado por um plano de brinquedo (lote 900) para que o teste monte o cenário
inteiro — inclusive os casos que têm que EXPLODIR.
"""

import os
import tempfile
from decimal import Decimal as D
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from estoque.models import InventoryEntry, Lot
from pricing.models import Buyer
from tenancy.models import Company, Membership
from tenancy.scope import company_scope
from vendas import alinhar_eminer_core as core
from vendas.models import (DocSequence, INV_CANCELLED, INV_OPEN, INV_PAID,
                           Invoice, Payment, SEQ_SO, STATUS_CONFIRMED,
                           SalesOrder, SalesOrderLine, Settlement)

User = get_user_model()

CMD = 'vendas.management.commands.alinhar_vendas_eminer'

# ── plano de brinquedo ───────────────────────────────────────────────────
# Duas linhas: 10 × ¥12 + 5 × ¥8 = ¥160. A ¥160 × 0,15 = US$ 24,00 — e a
# "mestra" diz 24,00 redondo, o caso feliz. Casos de borda mudam isto.
PLANO_TESTE = {
    900: dict(ov=1, fx=D('0.15'), total_rmb=D('160.00'), total_usd=D('24.00'),
              precos=True, data=date(2026, 7, 11), pago_em=date(2026, 7, 18),
              carteira='TRONLINK', nota='plano de teste'),
}
PRECOS_TESTE = {
    900: {('Samsung', 'emmc', '', '16.0', 'GB'): '12',
          ('Samsung', 'emmc', '', '8.0', 'GB'): '8'},
}


#: Onde os testes escrevem o JSON de reversão. ⚠ NUNCA o var/reverts/ de
#: verdade: rodar a suíte encheria a pasta do dono de lixo (foi o que
#: aconteceu na primeira execução — 38 arquivos). O tmpdir é por processo.
_REVERT_TESTE = os.path.join(tempfile.mkdtemp(prefix='alinhar-revert-'),
                             'alinhar_vendas_eminer_revert.json')


def _rodar(*args, **kw):
    out = StringIO()
    with patch(f'{CMD}.REVERT', _REVERT_TESTE):
        call_command('alinhar_vendas_eminer', *args, stdout=out, stderr=out, **kw)
    return out.getvalue()


class _Cenario(TestCase):
    """Empresa eMiner + Wu Quan + lote 900 fechado com OV confirmada."""

    def setUp(self):
        self.empresa = Company.objects.create(
            name='eMiner', slug='eminer', code='EMI',
            service_fee_pct=D('10.00'))
        self.buyer = Buyer.all_companies.create(
            company=None, name='Wu Quan', slug='wu-quan')
        self.op = User.objects.create_user('op_alinhar', password='x')
        with company_scope(self.empresa.id):
            self.lot = Lot.all_companies.create(
                company=self.empresa, number=900, description='lote de teste',
                status='closed', operator=self.op, origin='phone')
            for pn, cap, qtd in (('PN16', D('16'), 10), ('PN8', D('8'), 5)):
                InventoryEntry.all_companies.create(
                    lot=self.lot, company=self.empresa, part_number=pn,
                    quantity=qtd, brand='Samsung', chip_type='eMMC',
                    price_kind='emmc', price_gen='',
                    price_tier_value=cap, price_tier_unit='GB')
            # ⚠ `so_confirmed_is_frozen` exige taxa + totais numa OV
            # confirmada. Nasce com os valores ERRADOS de propósito: é o
            # estado que os lotes 040/041 têm hoje em produção (taxa 0,15 e
            # um total de cabeçalho que as linhas não produzem).
            self.ov = SalesOrder(lot=self.lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                                 fx_usd_rate=D('0.1484'), total_rmb=D('999.00'),
                                 total_usd=D('148.25'),
                                 number=DocSequence.next_number(self.empresa, SEQ_SO))
            self.ov.save()
            for cap, qtd in ((D('16'), 10), (D('8'), 5)):
                SalesOrderLine.all_companies.create(
                    order=self.ov, company=self.empresa, brand='Samsung',
                    kind='emmc', gen='', tier_value=cap, tier_unit='GB',
                    quantity=qtd)

    def _patch(self, plano=None, precos=None):
        return (patch(f'{CMD}.PLANO', plano or PLANO_TESTE),
                patch.object(core, 'PRECOS', precos or PRECOS_TESTE))


# ═════════════════════ camada 1 — a aritmética do plano ═══════════════════

class PlanoRealTests(TestCase):
    """O plano de VERDADE (lotes 39/40/41). Não toca no banco."""

    def test_self_check_passa(self):
        self.assertTrue(core.self_check())

    def test_todo_lote_do_plano_tem_o_que_precisa(self):
        for lote, p in core.PLANO.items():
            with self.subTest(lote=lote):
                for campo in ('ov', 'fx', 'total_rmb', 'total_usd', 'precos',
                              'data', 'carteira', 'nota'):
                    self.assertIn(campo, p)
                self.assertGreater(p['total_usd'], 0)
                self.assertGreater(p['total_rmb'], 0)

    def test_tabela_de_precos_existe_e_esta_cheia_onde_precos_e_true(self):
        for lote, p in core.PLANO.items():
            if not p['precos']:
                self.assertNotIn(lote, core.PRECOS,
                                 f'lote {lote} não usa preço por linha')
                continue
            tab = core.PRECOS[lote]
            self.assertTrue(tab, f'lote {lote} sem tabela')
            vazios = [k for k, v in tab.items() if v in (None, '', '0')]
            self.assertEqual(vazios, [], f'lote {lote}: chaves sem preço')

    def test_040_e_041_tem_a_quantidade_de_linhas_da_producao(self):
        """93 e 106 — se a tabela encolher, alguém mexeu e o teste avisa."""
        self.assertEqual(len(core.PRECOS[40]), 93)
        self.assertEqual(len(core.PRECOS[41]), 106)

    def test_o_yuan_e_o_dolar_da_mestra_so_diferem_por_arredondamento(self):
        """A diferença conhecida: +0,06 no 040 e −0,32 no 041. Nada além disso.
        Se um dia passar de um dólar, é erro de plano, não arredondamento."""
        esperado = {39: D('0.00'), 40: D('0.06'), 41: D('-0.32')}
        for lote, p in core.PLANO.items():
            derivado = (p['total_rmb'] * p['fx']).quantize(D('0.01'))
            self.assertEqual(derivado - p['total_usd'], esperado[lote],
                             f'lote {lote}: {derivado} vs {p["total_usd"]}')

    def test_039_nao_tem_preco_por_linha(self):
        """Decisão do dono: o preço foi repactuado e ninguém guardou a quebra
        por categoria. Rateio inventado é pior que nenhum."""
        self.assertFalse(core.PLANO[39]['precos'])

    def test_o_039_paga_em_18_de_julho_e_fecha_em_04(self):
        """Fechamento e pagamento são datas diferentes (dono, 2026-09-01):
        o lote fechou em 04/07 e o Wu pagou duas semanas depois."""
        self.assertEqual(core.PLANO[39]['data'], date(2026, 7, 4))
        self.assertEqual(core.PLANO[39]['pago_em'], date(2026, 7, 18))

    def test_a_data_do_039_e_04_de_julho(self):
        """Do detalhe em mandarim (dd/mm, de 17/06 a 04/07) e do closed_at da
        produção. O 2026-04-07 da mestra é 04/07 lido como abril."""
        self.assertEqual(core.PLANO[39]['data'], date(2026, 7, 4))


# ═════════════════════ camada 2 — o comando ═══════════════════════════════

class DryRunTests(_Cenario):

    def test_dry_run_nao_grava_nada(self):
        p1, p2 = self._patch()
        with p1, p2:
            saida = _rodar()
        self.ov.refresh_from_db()
        self.assertEqual(self.ov.fx_usd_rate, D('0.1484'))
        self.assertEqual(self.ov.total_rmb, D('999.00'))
        self.assertEqual(Invoice.all_companies.count(), 0)
        self.assertEqual(Settlement.all_companies.count(), 0)
        self.assertEqual(Payment.all_companies.count(), 0)
        self.assertEqual(
            [l.unit_rmb for l in self.ov.lines.all()], [None, None])
        self.assertIn('DRY-RUN', saida)

    def test_herda_a_trava_de_banco_alvo(self):
        """A trava que teria evitado o susto: imprime o banco-alvo e, no
        --commit interativo, exige digitar o nome dele.

        Não dá para conferir pela saída capturada — o SafeWriteCommand escreve
        no stderr ANTES de o call_command redirecionar. Então se testa o que
        realmente importa: que a herança está lá e ligada."""
        from core.safe_command import SafeWriteCommand
        from vendas.management.commands.alinhar_vendas_eminer import Command
        self.assertTrue(issubclass(Command, SafeWriteCommand))
        self.assertTrue(Command.confirm_on_commit)


class CommitTests(_Cenario):

    def _commit(self):
        p1, p2 = self._patch()
        with p1, p2:
            return _rodar('--commit')

    def test_grava_a_cadeia_inteira_quitada(self):
        self._commit()
        self.ov.refresh_from_db()
        self.assertEqual(self.ov.fx_usd_rate, D('0.1500'))
        self.assertEqual(self.ov.total_rmb, D('160.00'))
        self.assertEqual(self.ov.total_usd, D('24.00'))
        self.assertIsNotNone(self.ov.received_at)
        self.assertEqual(self.ov.received_at.date(), date(2026, 7, 11))

        self.assertEqual(Settlement.all_companies.count(), 1)
        self.assertEqual(Settlement.all_companies.first().lines.count(), 0,
                         'acerto sem rejeição: o comprador ficou com tudo')

        inv = Invoice.all_companies.get()
        self.assertEqual(inv.status, INV_PAID)
        self.assertEqual(inv.total_usd, D('24.00'))
        self.assertEqual(inv.total_rmb, D('160.00'))
        self.assertEqual(inv.fee_pct, D('10.00'))
        self.assertEqual(inv.fee_usd, D('2.40'))
        self.assertEqual(inv.net_usd, D('21.60'))
        self.assertEqual(inv.balance_usd, D('0.00'))

        pg = Payment.all_companies.get()
        self.assertEqual(pg.amount_usd, D('24.00'))
        self.assertEqual(pg.paid_at, date(2026, 7, 18),
                         'o pagamento usa pago_em, não a data de fechamento')
        self.assertEqual(pg.reference, 'TRONLINK')

    def test_grava_preco_em_cada_linha(self):
        self._commit()
        precos = {(l.tier_value, l.unit_rmb, l.unit_usd)
                  for l in self.ov.lines.all()}
        self.assertEqual(precos, {(D('16.0'), D('12.00'), D('1.80')),
                                  (D('8.0'), D('8.00'), D('1.20'))})

    def test_a_soma_das_linhas_bate_com_o_total_da_ordem(self):
        self._commit()
        self.ov.refresh_from_db()
        soma = sum(l.unit_rmb * l.quantity for l in self.ov.lines.all())
        self.assertEqual(soma, self.ov.total_rmb)

    def test_limpa_o_preco_quando_o_plano_diz_sem_preco_por_linha(self):
        plano = {900: dict(PLANO_TESTE[900], precos=False)}
        SalesOrderLine.all_companies.filter(order=self.ov).update(
            unit_rmb=D('99'), unit_usd=D('9'))
        with patch(f'{CMD}.PLANO', plano), patch.object(core, 'PRECOS', {}):
            _rodar('--commit')
        for l in self.ov.lines.all():
            self.assertIsNone(l.unit_rmb)
            self.assertIsNone(l.unit_usd)
        self.assertEqual(Invoice.all_companies.get().total_usd, D('24.00'),
                         'o valor continua vindo do cabeçalho')

    def test_nao_pisa_num_recebimento_que_ja_existe(self):
        from datetime import datetime, timezone as tz
        antes = datetime(2026, 5, 1, 10, 0, tzinfo=tz.utc)
        SalesOrder.all_companies.filter(pk=self.ov.pk).update(received_at=antes)
        self._commit()
        self.ov.refresh_from_db()
        self.assertEqual(self.ov.received_at, antes)


class FaturaExistenteTests(_Cenario):

    def _fatura_velha(self, com_pagamento=False):
        with company_scope(self.empresa.id):
            st = Settlement(order=self.ov); st.save()
            inv = Invoice(order=self.ov, settlement=st,
                          number=DocSequence.next_number(self.empresa, 'inv'),
                          fx_usd_rate=D('0.1484'), total_rmb=D('100'),
                          total_usd=D('14.84'), fee_pct=D('10'),
                          fee_rmb=D('10'), fee_usd=D('1.48'), status=INV_OPEN)
            inv.save()
            if com_pagamento:
                Payment(invoice=inv, amount_usd=D('1.00'),
                        paid_at=date(2026, 7, 1)).save()
            return inv

    def test_cancela_a_fatura_errada_e_emite_outra(self):
        velha = self._fatura_velha()
        p1, p2 = self._patch()
        with p1, p2:
            _rodar('--commit')
        velha.refresh_from_db()
        self.assertEqual(velha.status, INV_CANCELLED,
                         'cancelada, não apagada — o número dela fica no histórico')
        self.assertIsNotNone(velha.cancelled_at)
        nova = Invoice.all_companies.exclude(pk=velha.pk).get()
        self.assertEqual(nova.total_usd, D('24.00'))
        self.assertEqual(nova.status, INV_PAID)

    def test_mantem_o_acerto_que_ja_existia(self):
        self._fatura_velha()
        p1, p2 = self._patch()
        with p1, p2:
            _rodar('--commit')
        self.assertEqual(Settlement.all_companies.count(), 1)

    def test_recusa_se_a_fatura_velha_ja_tem_pagamento(self):
        self._fatura_velha(com_pagamento=True)
        p1, p2 = self._patch()
        with p1, p2, self.assertRaisesMessage(CommandError, 'já tem pagamento'):
            _rodar('--commit')


class RecusaTests(_Cenario):

    def test_recusa_lote_fora_do_plano(self):
        p1, p2 = self._patch()
        with p1, p2, self.assertRaisesMessage(CommandError, 'fora do plano'):
            _rodar('--lote', '77')

    def test_recusa_lote_que_nao_existe_na_base(self):
        plano = {901: dict(PLANO_TESTE[900], precos=False)}
        with patch(f'{CMD}.PLANO', plano), \
             self.assertRaisesMessage(CommandError, 'não existe nesta base'):
            _rodar()

    def test_recusa_quando_a_ov_confirmada_nao_e_a_do_plano(self):
        plano = {900: dict(PLANO_TESTE[900], ov=99)}
        with patch(f'{CMD}.PLANO', plano), patch.object(core, 'PRECOS', PRECOS_TESTE), \
             self.assertRaisesMessage(CommandError, 'Recuso mexer'):
            _rodar()

    def test_recusa_quando_falta_preco_para_alguma_linha(self):
        precos = {900: {('Samsung', 'emmc', '', '16.0', 'GB'): '12'}}
        with patch(f'{CMD}.PLANO', PLANO_TESTE), patch.object(core, 'PRECOS', precos), \
             self.assertRaisesMessage(CommandError, 'sem preço na tabela'):
            _rodar()

    def test_recusa_quando_a_tabela_nao_soma_o_total_do_plano(self):
        precos = {900: {('Samsung', 'emmc', '', '16.0', 'GB'): '12',
                        ('Samsung', 'emmc', '', '8.0', 'GB'): '7'}}   # ¥155 ≠ ¥160
        with patch(f'{CMD}.PLANO', PLANO_TESTE), patch.object(core, 'PRECOS', precos), \
             self.assertRaisesMessage(CommandError, 'a tabela soma'):
            _rodar()

    def test_recusa_comprador_diferente(self):
        Buyer.all_companies.filter(pk=self.buyer.pk).update(name='Outro')
        p1, p2 = self._patch()
        with p1, p2, self.assertRaisesMessage(CommandError, 'esperava "Wu Quan"'):
            _rodar()


class RevertTests(_Cenario):

    def _foto(self):
        self.ov.refresh_from_db()
        return dict(
            fx=self.ov.fx_usd_rate, rmb=self.ov.total_rmb,
            usd=self.ov.total_usd, receb=self.ov.received_at,
            linhas=sorted((l.pk, l.unit_rmb, l.unit_usd) for l in self.ov.lines.all()),
            faturas=Invoice.all_companies.count(),
            acertos=Settlement.all_companies.count(),
            pagtos=Payment.all_companies.count())

    def test_revert_devolve_o_estado_exato(self):
        antes = self._foto()
        p1, p2 = self._patch()
        with p1, p2:
            _rodar('--commit')
        self.assertNotEqual(self._foto(), antes)
        with p1, p2:
            _rodar('--revert')
        self.assertEqual(self._foto(), antes)

    def test_revert_reabre_a_fatura_que_tinha_sido_cancelada(self):
        with company_scope(self.empresa.id):
            st = Settlement(order=self.ov); st.save()
            velha = Invoice(order=self.ov, settlement=st,
                            number=DocSequence.next_number(self.empresa, 'inv'),
                            fx_usd_rate=D('0.1484'), total_rmb=D('100'),
                            total_usd=D('14.84'), fee_pct=D('10'),
                            fee_rmb=D('10'), fee_usd=D('1.48'), status=INV_OPEN)
            velha.save()
        p1, p2 = self._patch()
        with p1, p2:
            _rodar('--commit')
            _rodar('--revert')
        velha.refresh_from_db()
        self.assertEqual(velha.status, INV_OPEN)
        self.assertIsNone(velha.cancelled_at)
        self.assertEqual(Invoice.all_companies.count(), 1)

    def test_nao_deixa_o_var_reverts_virar_lixeira(self):
        """O refresh_lote acumulou 231 backups. Este poda em 10."""
        from vendas.management.commands.alinhar_vendas_eminer import Command
        p1, p2 = self._patch()
        with p1, p2:
            for _ in range(14):
                _rodar('--commit')
                _rodar('--revert')
        pasta = os.path.dirname(_REVERT_TESTE)
        base = os.path.basename(_REVERT_TESTE)
        antigos = [f for f in os.listdir(pasta) if f.startswith(base + '.')]
        self.assertLessEqual(len(antigos), Command.MANTER_ANTIGOS)

    def test_revert_sem_nada_a_desfazer_reclama(self):
        with self.assertRaisesMessage(CommandError, 'nada a desfazer'):
            _rodar('--revert')


# ═════════════════════ camada 3 — a tela do comprador ═════════════════════

class TelaDoCompradorTests(_Cenario):
    """O que o Wu Quan vê depois da correção."""

    def setUp(self):
        super().setUp()
        self.parceiro = User.objects.create_user('wu_alinhar', password='x')
        self.buyer.users.add(self.parceiro)
        from django.utils import timezone
        SalesOrder.all_companies.filter(pk=self.ov.pk).update(
            shipped_at=timezone.localdate())

    def test_antes_a_compra_nao_tem_fatura_nem_pagamento(self):
        """O estado de hoje: a cadeia nunca foi lançada."""
        self.client.force_login(self.parceiro)
        tela = self.client.get(reverse('compras:detail', args=[self.ov.pk]))
        self.assertEqual(tela.status_code, 200)
        self.assertEqual(Invoice.all_companies.count(), 0)
        self.assertEqual(Payment.all_companies.count(), 0)

    def test_depois_a_tela_mostra_o_valor_pago_e_a_compra_quitada(self):
        p1, p2 = self._patch()
        with p1, p2:
            _rodar('--commit')
        self.client.force_login(self.parceiro)
        tela = self.client.get(reverse('compras:detail', args=[self.ov.pk]))
        self.assertEqual(tela.status_code, 200)
        corpo = tela.content.decode()
        # ponto ou vírgula conforme a localização — o que importa é o número
        self.assertTrue('US$ 24.00' in corpo or 'US$ 24,00' in corpo,
                        'a tela do comprador tem que mostrar o valor pago')
        self.assertTrue('160.00' in corpo or '160,00' in corpo,
                        'e o total em ¥ que as linhas produzem')
        inv = Invoice.all_companies.get()
        self.assertEqual(inv.status, INV_PAID)
        self.assertEqual(inv.balance_usd, D('0.00'))


class RegistroLegadoNaTelaTests(_Cenario):
    """A regra de tela para compra anterior ao sistema (dono, 2026-09-01).

    O lote 039 e os três legados têm o valor congelado no CABEÇALHO e nenhuma
    linha com ¥. Antes disto a tela imprimia "sem preço" em cada uma das 88
    linhas e ¥ 0,00 em cada marca, ao lado de um cabeçalho dizendo US$ 23.224
    PAGO — para o comprador, dado corrompido.
    """

    def setUp(self):
        super().setUp()
        self.parceiro = User.objects.create_user('wu_legado', password='x')
        self.buyer.users.add(self.parceiro)
        from django.utils import timezone as tz
        SalesOrder.all_companies.filter(pk=self.ov.pk).update(
            shipped_at=tz.localdate(), received_at=tz.now())
        self.client.force_login(self.parceiro)

    def _tela(self):
        r = self.client.get(reverse('compras:detail', args=[self.ov.pk]))
        self.assertEqual(r.status_code, 200)
        return r, r.content.decode()

    def _sem_preco_em_linha(self):
        """Sem preço na OV: é o estado do 039 depois do alinhamento."""
        SalesOrderLine.all_companies.filter(order=self.ov).update(
            unit_rmb=None, unit_usd=None)

    def test_sem_preco_em_nenhuma_linha_liga_a_regra(self):
        self._sem_preco_em_linha()
        r, h = self._tela()
        self.assertTrue(r.context[-1]['registro_legado'])
        self.assertIn('<b>Compra anterior ao sistema.</b>', h)

    def test_com_preco_nas_linhas_a_regra_fica_desligada(self):
        SalesOrderLine.all_companies.filter(order=self.ov).update(
            unit_rmb=D('12.00'), unit_usd=D('1.80'))
        r, h = self._tela()
        self.assertFalse(r.context[-1]['registro_legado'])
        self.assertNotIn('<b>Compra anterior ao sistema.</b>', h)

    def test_a_tabela_para_de_repetir_sem_preco(self):
        """Uma frase no lugar de N repetições — é o ponto da regra."""
        self._sem_preco_em_linha()
        _r, h = self._tela()
        corpo = h[:h.find('<script')]
        self.assertNotIn('sem preço', corpo)
        self.assertNotIn('¥ 0.00', corpo)

    def test_o_valor_do_cabecalho_continua_aparecendo(self):
        """Apagar a coluna não pode apagar o dinheiro: o total congelado é a
        única fonte que sobra."""
        self._sem_preco_em_linha()
        self.ov.refresh_from_db()
        alvo = str(self.ov.total_rmb)
        _r, h = self._tela()
        self.assertTrue(alvo in h or alvo.replace('.', ',') in h,
                        f'o ¥ {alvo} do cabeçalho sumiu junto com o das linhas')

    def test_rascunho_NAO_e_registro_legado(self):
        """Rascunho sem preço é outra coisa: falta cotar, e a tela tem que
        continuar dizendo 'sem preço' linha a linha."""
        self._sem_preco_em_linha()
        SalesOrder.all_companies.filter(pk=self.ov.pk).update(status='draft')
        r, _h = self._tela()
        self.assertFalse(r.context[-1]['registro_legado'])

    def test_ordem_confirmada_SEM_total_nao_existe_no_banco(self):
        """A guarda `total_rmb is not None` na regra é defensiva: a
        CheckConstraint `so_confirmed_is_frozen` já torna esse estado
        impossível. Este teste registra isso — se um dia a constraint cair, a
        guarda passa a ser a única proteção e alguém precisa saber."""
        from django.db.utils import IntegrityError
        self._sem_preco_em_linha()
        with self.assertRaises(IntegrityError):
            SalesOrder.all_companies.filter(pk=self.ov.pk).update(total_rmb=None)

    def test_preco_em_ALGUMAS_linhas_nao_liga_a_regra(self):
        """Meio preenchido é defeito de dado, não registro legado — ali o
        'sem preço' por linha é a informação certa."""
        self._sem_preco_em_linha()
        uma = SalesOrderLine.all_companies.filter(order=self.ov).first()
        SalesOrderLine.all_companies.filter(pk=uma.pk).update(
            unit_rmb=D('12.00'), unit_usd=D('1.80'))
        r, _h = self._tela()
        self.assertFalse(r.context[-1]['registro_legado'])

    def test_ordem_sem_nenhuma_linha_TAMBEM_e_registro_legado(self):
        """O CHIP-EXP022026: entradas sem chave de preço, então a OV não tem
        linha nenhuma e a tabela sai vazia ao lado de um cabeçalho com valor.
        É onde a frase mais falta."""
        SalesOrderLine.all_companies.filter(order=self.ov).delete()
        r, h = self._tela()
        self.assertTrue(r.context[-1]['registro_legado'])
        self.assertIn('<b>Compra anterior ao sistema.</b>', h)

    def test_o_javascript_sabe_da_regra(self):
        """O laço de recálculo escreveria '¥ 0.00' por cima do '—'. Só roda
        quando o comprador digita recusa, mas a guarda é para o dia em que
        passar a rodar."""
        self._sem_preco_em_linha()
        _r, h = self._tela()
        self.assertIn('var REGISTRO_LEGADO = true;', h)
        self.assertIn('if (eVal && !REGISTRO_LEGADO)', h)
