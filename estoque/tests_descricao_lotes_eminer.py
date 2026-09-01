"""
Testes do `descrever_lotes_renomeados_eminer`.

A renumeração pôs os lotes em ordem cronológica, mas o packing list que viajou
com a caixa diz `LOT/042/07/26` e o WhatsApp diz 39. O dono pediu (2026-09-01)
que o código antigo vivesse na descrição do próprio lote, para quem procurar
pelo número velho ainda achar.

O que estes testes travam: que o texto do operador NÃO é apagado, que o código
antigo é reconstruído do `MAPA` (fonte única) e não digitado, e que rodar duas
vezes não empilha.
"""

import os
import tempfile
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from estoque.models import Lot
from tenancy.models import Company
from tenancy.scope import company_scope

User = get_user_model()
CMD = 'estoque.management.commands.descrever_lotes_renomeados_eminer'
_DIR = tempfile.mkdtemp(prefix='descr-')
_REVERT = os.path.join(_DIR, 'descrever_lotes_renomeados_eminer_revert.json')


class _Cenario(TestCase):
    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='')
        # ⚠ `Company.save()` dá código automático ('EMI') a empresa NOVA
        # (regra de 2026-08-18). A eMiner de produção é anterior a isso e tem
        # `code=''` — é dela que saem os códigos antigos `LOT/039/05/26`, sem
        # o EMI. O fixture tem de imitar a produção, não a regra de hoje.
        Company.objects.filter(pk=self.empresa.pk).update(code='')
        self.empresa.refresh_from_db()
        self.op = User.objects.create_user('op_descr', password='x')

    def _lote(self, numero, descricao='', mes=7):
        with company_scope(self.empresa.id):
            lot = Lot.all_companies.create(
                company=self.empresa, number=numero, description=descricao,
                status='closed', operator=self.op, origin='phone')
            Lot.all_companies.filter(pk=lot.pk).update(
                created_at=timezone.now().replace(year=2026, month=mes, day=6))
        return Lot.all_companies.get(pk=lot.pk)

    def _rodar(self, *args, antigo=None):
        out = StringIO()
        with patch(f'{CMD}.ANTIGO', antigo or {}), \
             patch(f'{CMD}.REVERT', _REVERT):
            call_command('descrever_lotes_renomeados_eminer', *args,
                         stdout=out, stderr=out)
        return out.getvalue()

    def _descricao(self, lot):
        return Lot.all_companies.get(pk=lot.pk).description


class EscritaTests(_Cenario):

    def test_dry_run_nao_grava(self):
        lot = self._lote(5)
        saida = self._rodar(antigo={5: 40})
        self.assertIn('DRY-RUN', saida)
        self.assertEqual(self._descricao(lot), '')

    def test_lote_sem_descricao_ganha_o_codigo_antigo(self):
        lot = self._lote(5)
        self._rodar('--commit', antigo={5: 40})
        self.assertEqual(self._descricao(lot), 'Antes: LOT/040/07/26')

    def test_o_texto_do_operador_continua_na_frente(self):
        lot = self._lote(3, descricao='EMINER MOBILE', mes=5)
        self._rodar('--commit', antigo={3: 39})
        self.assertEqual(self._descricao(lot),
                         'EMINER MOBILE · antes LOT/039/05/26')

    def test_o_mes_vem_da_abertura_do_lote_e_nao_de_hoje(self):
        """O código antigo é o que está no papel que já circulou."""
        lot = self._lote(8, mes=8)
        self._rodar('--commit', antigo={8: 43})
        self.assertIn('LOT/043/08/26', self._descricao(lot))

    def test_rodar_duas_vezes_nao_empilha(self):
        lot = self._lote(5)
        self._rodar('--commit', antigo={5: 40})
        saida = self._rodar('--commit', antigo={5: 40})
        self.assertIn('já tem', saida)
        self.assertEqual(self._descricao(lot).count('LOT/040'), 1)

    def test_lote_inexistente_e_pulado_sem_estourar(self):
        saida = self._rodar('--commit', antigo={77: 99})
        self.assertIn('não existe', saida)


class FormatoDoCodigoTests(_Cenario):
    """O código é montado pelo `doc_code()`, não por f-string local."""

    def test_empresa_com_codigo_entra_no_documento(self):
        Company.objects.filter(pk=self.empresa.pk).update(code='EMI')
        self.empresa.refresh_from_db()
        lot = self._lote(5)
        self._rodar('--commit', antigo={5: 40})
        self.assertEqual(self._descricao(lot), 'Antes: LOT/EMI/040/07/26')


class FonteUnicaTests(_Cenario):
    """O número antigo sai do MAPA da renumeração, nunca redigitado aqui."""

    def test_o_mapa_invertido_e_o_do_renumerar(self):
        from estoque.management.commands.renumerar_lotes_eminer import MAPA
        from estoque.management.commands import (
            descrever_lotes_renomeados_eminer as m)
        self.assertEqual(m.ANTIGO, {n: a for a, n in MAPA.items()})

    def test_cobre_todos_os_lotes_renumerados(self):
        from estoque.management.commands.renumerar_lotes_eminer import MAPA
        from estoque.management.commands import (
            descrever_lotes_renomeados_eminer as m)
        self.assertEqual(len(m.ANTIGO), len(MAPA))


class RevertTests(_Cenario):

    def test_revert_devolve_a_descricao_original(self):
        lot = self._lote(3, descricao='EMINER MOBILE', mes=5)
        self._rodar('--commit', antigo={3: 39})
        self._rodar('--revert')
        self.assertEqual(self._descricao(lot), 'EMINER MOBILE')

    def test_revert_devolve_o_vazio_quando_era_vazio(self):
        lot = self._lote(5)
        self._rodar('--commit', antigo={5: 40})
        self._rodar('--revert')
        self.assertEqual(self._descricao(lot), '')

    def test_revert_sem_arquivo_reclama(self):
        with self.assertRaises(CommandError):
            self._rodar('--revert')


class PodaTests(_Cenario):
    def test_mantem_no_maximo_os_ultimos_backups(self):
        from estoque.management.commands import (
            descrever_lotes_renomeados_eminer as m)
        self._lote(5)
        for _ in range(m.MANTER_ANTIGOS + 4):
            self._rodar('--commit', antigo={5: 40})
            self._rodar('--revert')
        sobras = [f for f in os.listdir(_DIR)
                  if f.startswith(os.path.basename(_REVERT) + '.')]
        self.assertLessEqual(len(sobras), m.MANTER_ANTIGOS)
