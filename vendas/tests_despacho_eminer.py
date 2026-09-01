"""
Testes do `datar_despacho_eminer`.

LOT/005 e LOT/006 seguiam em "despacho pendente" na lista de Vendas porque
não têm `shipped_at` nem `received_at`: são de julho, e o despacho (F4) só
começou a ser preenchido em agosto. O dono autorizou usar a data do
PAGAMENTO ("sim, pode usar as datas de pagamento").

O que estes testes travam, além do carimbo em si: que o comando **só preenche
campo vazio**, com UMA exceção nomeada — o `CORRECOES`, que conserta despacho
já registrado e é coberto pela `CorrecaoTests` no fim do arquivo. Fora dessa
lista, sobrescrever um despacho real seria trocar um fato por uma suposição.
"""

import os
import tempfile
from datetime import date, datetime
from datetime import timezone as _tz
from decimal import Decimal as D
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company
from tenancy.scope import company_scope
from vendas.models import (DocSequence, SEQ_INVOICE, SEQ_SO, Invoice, Payment,
                           SalesOrder)

User = get_user_model()
CMD = 'vendas.management.commands.datar_despacho_eminer'
_DIR = tempfile.mkdtemp(prefix='desp-')
_REVERT = os.path.join(_DIR, 'datar_despacho_eminer_revert.json')

PAGO_EM = date(2026, 7, 11)


class _Cenario(TestCase):
    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.op = User.objects.create_user('op_desp', password='x')
        self.n = 0

    def _ordem(self, *, pago_em=PAGO_EM, enviada=None, recebida=None,
               com_pagamento=True):
        self.n += 1
        with company_scope(self.empresa.id):
            lot = Lot.all_companies.create(
                company=self.empresa, number=self.n, description='x',
                status='closed', operator=self.op, origin='phone')
            so = SalesOrder(
                lot=lot, buyer=self.buyer, status='confirmed',
                fx_usd_rate=D('0.1400'), total_rmb=D('49550.40'),
                total_usd=D('6937.00'), shipped_at=enviada,
                received_at=recebida,
                number=DocSequence.next_number(self.empresa, SEQ_SO))
            so.save()
            inv = Invoice(
                order=so, status='paid', fx_usd_rate=D('0.1400'),
                total_rmb=D('49550.40'), total_usd=D('6937.00'),
                number=DocSequence.next_number(self.empresa, SEQ_INVOICE))
            inv.save()
            if com_pagamento:
                Payment(invoice=inv, amount_usd=D('6937.00'),
                        paid_at=pago_em, reference='TRONLINK').save()
        return so

    def _rodar(self, *args, ordens=None, legados=(), correcoes=None):
        out = StringIO()
        with patch(f'{CMD}.ORDENS', ordens or ()), \
             patch(f'{CMD}.LEGADOS', legados), \
             patch(f'{CMD}.CORRECOES', correcoes or {}), \
             patch(f'{CMD}.REVERT', _REVERT):
            call_command('datar_despacho_eminer', *args, stdout=out, stderr=out)
        return out.getvalue()

    def _recarregar(self, so):
        return SalesOrder.all_companies.get(pk=so.pk)


class CarimboTests(_Cenario):

    def test_dry_run_nao_grava(self):
        so = self._ordem()
        saida = self._rodar(ordens=(so.code,))
        self.assertIn('DRY-RUN', saida)
        self.assertIsNone(self._recarregar(so).shipped_at)

    def test_envio_recebe_a_data_do_pagamento(self):
        so = self._ordem()
        self._rodar('--commit', ordens=(so.code,))
        self.assertEqual(self._recarregar(so).shipped_at, PAGO_EM)

    def test_recebimento_fica_ao_meio_dia_do_mesmo_dia(self):
        so = self._ordem()
        self._rodar('--commit', ordens=(so.code,))
        self.assertEqual(self._recarregar(so).received_at,
                         datetime(2026, 7, 11, 12, 0, tzinfo=_tz.utc))

    def test_a_data_vem_do_pagamento_e_nao_de_constante_no_codigo(self):
        """Se o pagamento for outro, o carimbo acompanha."""
        so = self._ordem(pago_em=date(2026, 7, 17))
        self._rodar('--commit', ordens=(so.code,))
        self.assertEqual(self._recarregar(so).shipped_at, date(2026, 7, 17))

    def test_transportadora_e_rastreio_ficam_em_branco(self):
        so = self._ordem()
        self._rodar('--commit', ordens=(so.code,))
        novo = self._recarregar(so)
        self.assertEqual(novo.carrier, '')
        self.assertEqual(novo.tracking, '')
        self.assertIsNone(novo.shipped_by_id)


class NaoSobrescreveTests(_Cenario):
    """Despacho real, com transportadora e datas diferentes entre si, não é
    tocado — a menos que esteja no `CORRECOES` (ver `CorrecaoTests`)."""

    def test_nao_toca_ordem_que_ja_tem_os_dois(self):
        so = self._ordem(enviada=date(2026, 8, 18),
                         recebida=datetime(2026, 8, 30, 2, 15, tzinfo=_tz.utc))
        saida = self._rodar('--commit', ordens=(so.code,))
        self.assertIn('já tem os dois', saida)
        novo = self._recarregar(so)
        self.assertEqual(novo.shipped_at, date(2026, 8, 18))
        self.assertEqual(novo.received_at,
                         datetime(2026, 8, 30, 2, 15, tzinfo=_tz.utc))

    def test_preenche_so_o_que_falta(self):
        """Recebimento já existe (legado); só o envio entra."""
        recebido = datetime(2026, 6, 9, 12, 0, tzinfo=_tz.utc)
        so = self._ordem(pago_em=date(2026, 6, 9), recebida=recebido)
        self._rodar('--commit', ordens=(so.code,))
        novo = self._recarregar(so)
        self.assertEqual(novo.shipped_at, date(2026, 6, 9))
        self.assertEqual(novo.received_at, recebido, 'não pode ser remexido')

    def test_pula_ordem_sem_pagamento(self):
        so = self._ordem(com_pagamento=False)
        saida = self._rodar('--commit', ordens=(so.code,))
        self.assertIn('sem pagamento', saida)
        self.assertIsNone(self._recarregar(so).shipped_at)


class LegadosTests(_Cenario):

    def test_legado_fica_de_fora_por_padrao(self):
        so = self._ordem()
        self._rodar('--commit', ordens=(), legados=(so.code,))
        self.assertIsNone(self._recarregar(so).shipped_at)

    def test_incluir_legados_traz_ele(self):
        so = self._ordem()
        self._rodar('--commit', '--incluir-legados',
                    ordens=(), legados=(so.code,))
        self.assertEqual(self._recarregar(so).shipped_at, PAGO_EM)


class RecusaTests(_Cenario):

    def test_recusa_ordem_inexistente(self):
        with self.assertRaises(CommandError) as e:
            self._rodar('--commit', ordens=('SO/999/01/26',))
        self.assertIn('não encontrada', str(e.exception))


class RevertTests(_Cenario):

    def test_revert_apaga_o_que_foi_carimbado(self):
        so = self._ordem()
        self._rodar('--commit', ordens=(so.code,))
        self._rodar('--revert')
        novo = self._recarregar(so)
        self.assertIsNone(novo.shipped_at)
        self.assertIsNone(novo.received_at)

    def test_revert_devolve_so_os_campos_que_o_comando_preencheu(self):
        """Recebimento que já existia antes não pode sumir na reversão."""
        recebido = datetime(2026, 6, 9, 12, 0, tzinfo=_tz.utc)
        so = self._ordem(pago_em=date(2026, 6, 9), recebida=recebido)
        self._rodar('--commit', ordens=(so.code,))
        self._rodar('--revert')
        novo = self._recarregar(so)
        self.assertIsNone(novo.shipped_at)
        self.assertEqual(novo.received_at, recebido)

    def test_revert_sem_arquivo_reclama(self):
        with self.assertRaises(CommandError):
            self._rodar('--revert')


class PodaTests(_Cenario):
    def test_mantem_no_maximo_os_ultimos_backups(self):
        from vendas.management.commands import datar_despacho_eminer as m
        so = self._ordem()
        for _ in range(m.MANTER_ANTIGOS + 4):
            self._rodar('--commit', ordens=(so.code,))
            self._rodar('--revert')
        sobras = [f for f in os.listdir(_DIR)
                  if f.startswith(os.path.basename(_REVERT) + '.')]
        self.assertLessEqual(len(sobras), m.MANTER_ANTIGOS)


class CorrecaoTests(_Cenario):
    """`CORRECOES` — a exceção nomeada que SOBRESCREVE despacho já registrado.

    Produção dizia que o lote de US$ 23.224 saiu em 18/08, com o mesmo
    rastreio DHL do LOT/010. O dono corrigiu: *"Dia 11 de julho foi quando o
    lote de 23k foi despachado"* — alguém carimbou nele o embarque de outro
    lote."""

    CERTO = date(2026, 7, 11)

    def _com_despacho_errado(self):
        so = self._ordem(enviada=date(2026, 8, 18))
        with company_scope(self.empresa.id):
            SalesOrder.all_companies.filter(pk=so.pk).update(
                carrier='DHL', tracking='2486463965')
        return self._recarregar(so)

    def test_sobrescreve_o_despacho_errado(self):
        so = self._com_despacho_errado()
        self._rodar('--commit', correcoes={so.code: self.CERTO})
        self.assertEqual(self._recarregar(so).shipped_at, self.CERTO)

    def test_a_correcao_roda_sem_estar_em_ORDENS(self):
        """Conserto de fato errado não fica atrás de flag nem de lista."""
        so = self._com_despacho_errado()
        saida = self._rodar('--commit', ordens=(),
                            correcoes={so.code: self.CERTO})
        self.assertIn('CORRIGE', saida)

    def test_avisa_que_o_rastreio_ficou_orfao(self):
        so = self._com_despacho_errado()
        saida = self._rodar(correcoes={so.code: self.CERTO})
        self.assertIn('2486463965', saida)
        self.assertIn('NÃO é apagado', saida)

    def test_nao_apaga_o_rastreio(self):
        so = self._com_despacho_errado()
        self._rodar('--commit', correcoes={so.code: self.CERTO})
        novo = self._recarregar(so)
        self.assertEqual(novo.tracking, '2486463965')
        self.assertEqual(novo.carrier, 'DHL')

    def test_rodar_de_novo_nao_faz_nada(self):
        so = self._com_despacho_errado()
        self._rodar('--commit', correcoes={so.code: self.CERTO})
        saida = self._rodar('--commit', correcoes={so.code: self.CERTO})
        self.assertIn('já corrigido', saida)

    def test_revert_devolve_a_data_ANTIGA_e_nao_apaga(self):
        """A armadilha: reverter uma correção com `None` apagaria o despacho
        original. A reversão guarda o valor velho, não a lista de campos."""
        so = self._com_despacho_errado()
        self._rodar('--commit', correcoes={so.code: self.CERTO})
        self._rodar('--revert')
        self.assertEqual(self._recarregar(so).shipped_at, date(2026, 8, 18))
