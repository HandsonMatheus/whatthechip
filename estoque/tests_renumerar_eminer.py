"""
Testes do `renumerar_lotes_eminer` — a recontagem dos lotes a partir do 1.

É o comando mais perigoso do lote: reescreve identificador de documento e mexe
em todos os lotes de uma vez. Os testes cobrem o que pode dar errado de forma
silenciosa — colisão de número, buraco na sequência, mês do código trocado por
o de hoje, e reversão incompleta.

O mapa real (39→3, 40→5, …) é trocado por um de brinquedo para que o teste
monte o cenário inteiro.
"""

import os
import tempfile
from decimal import Decimal as D
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from datetime import datetime, timezone as tz

from estoque.models import Lot
from tenancy.models import Company
from tenancy.scope import company_scope

User = get_user_model()
CMD = 'estoque.management.commands.renumerar_lotes_eminer'
_REVERT_TESTE = os.path.join(tempfile.mkdtemp(prefix='renum-'),
                             'renumerar_lotes_eminer_revert.json')


def _rodar(*args, mapa=None, **kw):
    out = StringIO()
    with patch(f'{CMD}.MAPA', mapa if mapa is not None else MAPA_TESTE), \
         patch(f'{CMD}.REVERT', _REVERT_TESTE):
        call_command('renumerar_lotes_eminer', *args, stdout=out, stderr=out, **kw)
    return out.getvalue()


MAPA_TESTE = {39: 3, 40: 5, 41: 6}


class _Cenario(TestCase):
    """Legados já em 1, 2 e 4 (como o comando anterior deixa) + 39, 40, 41."""

    def setUp(self):
        self.empresa = Company.objects.create(name='eMiner', slug='eminer',
                                              code='')
        self.op = User.objects.create_user('op_renum', password='x')
        self.abertos = {}
        with company_scope(self.empresa.id):
            for n, mes, status in ((1, 4, 'closed'), (2, 6, 'closed'),
                                   (4, 7, 'closed'), (39, 5, 'closed'),
                                   (40, 7, 'closed'), (41, 7, 'open')):
                l = Lot.all_companies.create(
                    company=self.empresa, number=n, description=f'lote {n}',
                    status=status, operator=self.op, origin='phone')
                # created_at é auto_now_add — o mês do código sai dele
                # Em produção os lotes 39-45 têm code_str VAZIO (nasceram
                # antes do congelamento de 2026-08-18) e o código é calculado
                # do número. O create() daqui congela — desfaço para que o
                # cenário seja o real.
                Lot.all_companies.filter(pk=l.pk).update(
                    created_at=datetime(2026, mes, 15, 12, 0, tzinfo=tz.utc),
                    code_str='')
                self.abertos[n] = l.pk

    def _numeros(self):
        with company_scope(self.empresa.id):
            return sorted(Lot.objects.values_list('number', flat=True))

    def _codigos(self):
        with company_scope(self.empresa.id):
            return [l.code for l in Lot.objects.order_by('number')]


class DryRunTests(_Cenario):
    def test_nao_grava_nada(self):
        antes = self._numeros()
        saida = _rodar()
        self.assertEqual(self._numeros(), antes)
        self.assertIn('DRY-RUN', saida)

    def test_avisa_que_reescreve_documento(self):
        saida = _rodar()
        self.assertIn('reescreve o código do documento', saida)

    def test_avisa_sobre_lote_aberto(self):
        saida = _rodar()
        self.assertIn('ABERTOS agora', saida)


class RenumeracaoTests(_Cenario):

    def test_a_numeracao_final_e_1_ate_N_sem_buraco(self):
        _rodar('--commit')
        self.assertEqual(self._numeros(), [1, 2, 3, 4, 5, 6])

    def test_a_ordem_relativa_dos_renumerados_nao_muda(self):
        """Nenhum dos renumerados passa na frente de outro. Os legados SIM se
        intercalam — é o objetivo do mapa: o 39 (aberto em maio) tem que ficar
        antes do K9 (julho), e por isso vira 3 enquanto o K9 é 4."""
        alvos = set(MAPA_TESTE)
        with company_scope(self.empresa.id):
            antes = [l.pk for l in Lot.objects.order_by('number')
                     if l.number in alvos]
        _rodar('--commit')
        destinos = set(MAPA_TESTE.values())
        with company_scope(self.empresa.id):
            depois = [l.pk for l in Lot.objects.order_by('number')
                      if l.number in destinos]
        self.assertEqual(antes, depois)

    def test_o_codigo_novo_preserva_o_ANO_do_lote(self):
        """O lote 39 abriu em 2026: vira `LOT-2026-0003`, e o ano é o da
        ABERTURA, não o de hoje. ⚠ O MÊS saiu do identificador na convenção de
        2026-09-02 — era ele que carregava a ambiguidade `08/26`."""
        _rodar('--commit')
        with company_scope(self.empresa.id):
            l39 = Lot.objects.get(pk=self.abertos[39])
            self.assertEqual(l39.code, f'LOT-{l39.doc_year}-0003')
            l40 = Lot.objects.get(pk=self.abertos[40])
            self.assertEqual(l40.code, f'LOT-{l40.doc_year}-0005')

    def test_a_renumeracao_ACERTA_o_contador(self):
        """⚠ A 1ª execução não fazia isto: comprimir 39–50 em 1–13 deixou o
        contador em 50 e o próximo lote nasceria #51. A auto-cura só empurra
        para cima — contador adiantado ela não vê."""
        from vendas.models import DocSequence, SEQ_LOT
        _rodar('--commit')
        with company_scope(self.empresa.id):
            maior = max(l.number for l in Lot.objects.all())
            seq = DocSequence.all_companies.get(
                company=self.empresa, kind=SEQ_LOT,
                year=Lot.objects.first().doc_year)
            self.assertEqual(seq.last_number, maior)

    def test_o_codigo_fica_CONGELADO_e_nao_mais_calculado(self):
        """Antes o 39 tinha code_str vazio (código calculado do número).
        Depois tem que estar gravado, senão renumerar de novo mudaria o
        identificador sem ninguém pedir."""
        with company_scope(self.empresa.id):
            self.assertEqual(Lot.objects.get(pk=self.abertos[39]).code_str, '')
        _rodar('--commit')
        with company_scope(self.empresa.id):
            self.assertNotEqual(Lot.objects.get(pk=self.abertos[39]).code_str, '')

    def test_os_legados_nao_sao_tocados(self):
        with company_scope(self.empresa.id):
            antes = {n: Lot.objects.get(number=n).pk for n in (1, 2, 4)}
        _rodar('--commit')
        with company_scope(self.empresa.id):
            for n, pk in antes.items():
                self.assertEqual(Lot.objects.get(number=n).pk, pk)

    def test_so_fechados_deixa_o_aberto_quieto(self):
        _rodar('--commit', '--so-fechados')
        with company_scope(self.empresa.id):
            self.assertEqual(Lot.objects.get(pk=self.abertos[41]).number, 41,
                             'o lote aberto foi renumerado mesmo assim')
            self.assertEqual(Lot.objects.get(pk=self.abertos[39]).number, 3)


class RecusaTests(_Cenario):

    def test_recusa_mapa_com_destino_repetido(self):
        with self.assertRaisesMessage(CommandError, 'mesmo número'):
            _rodar('--commit', mapa={39: 3, 40: 3})

    def test_recusa_lote_que_nao_existe(self):
        with self.assertRaisesMessage(CommandError, 'mapa está velho'):
            _rodar('--commit', mapa={99: 3})

    def test_recusa_e_DESFAZ_se_a_numeracao_final_tiver_buraco(self):
        """A conferência roda dentro do atomic: se sobrar buraco, nada grava."""
        antes = self._numeros()
        with self.assertRaisesMessage(CommandError, 'não é 1..'):
            _rodar('--commit', mapa={39: 30, 40: 5, 41: 6})
        self.assertEqual(self._numeros(), antes, 'gravou apesar de recusar')

    def test_aguenta_destino_ocupado_por_lote_que_tambem_se_move(self):
        """39→4 com o 4 ainda ocupado, e o 4 saindo para o 3 na mesma leva.
        É a faixa de trânsito que faz isso passar sem depender da ORDEM em que
        os UPDATEs saem."""
        _rodar('--commit', mapa={4: 3, 39: 4, 40: 5, 41: 6})
        with company_scope(self.empresa.id):
            self.assertEqual(Lot.objects.get(pk=self.abertos[4]).number, 3)
            self.assertEqual(Lot.objects.get(pk=self.abertos[39]).number, 4)
            self.assertEqual(self._numeros(), [1, 2, 3, 4, 5, 6])

    def test_recusa_destino_de_lote_que_NAO_esta_no_mapa(self):
        with self.assertRaisesMessage(CommandError, 'não está no mapa'):
            _rodar('--commit', mapa={39: 2})


class RevertTests(_Cenario):

    def test_revert_devolve_numero_e_codigo(self):
        antes_num, antes_cod = self._numeros(), self._codigos()
        _rodar('--commit')
        self.assertNotEqual(self._numeros(), antes_num)
        _rodar('--revert')
        self.assertEqual(self._numeros(), antes_num)
        self.assertEqual(self._codigos(), antes_cod)

    def test_revert_devolve_o_code_str_VAZIO_de_quem_nao_tinha(self):
        """Não basta voltar o número: quem tinha código calculado tem que
        voltar a ter, senão sobra um code_str congelado que ninguém pediu."""
        _rodar('--commit')
        _rodar('--revert')
        with company_scope(self.empresa.id):
            self.assertEqual(Lot.objects.get(pk=self.abertos[39]).code_str, '')

    def test_revert_sem_nada_reclama(self):
        with self.assertRaisesMessage(CommandError, 'nada a desfazer'):
            _rodar('--revert')


class TravaTests(TestCase):
    def test_herda_o_safe_write_command(self):
        from core.safe_command import SafeWriteCommand
        from estoque.management.commands.renumerar_lotes_eminer import Command
        self.assertTrue(issubclass(Command, SafeWriteCommand))
        self.assertTrue(Command.confirm_on_commit)

    def test_o_mapa_real_nao_manda_dois_lotes_pro_mesmo_lugar(self):
        from estoque.management.commands.renumerar_lotes_eminer import MAPA
        self.assertEqual(len(set(MAPA.values())), len(MAPA))
        self.assertEqual(sorted(MAPA.values()) , sorted(set(MAPA.values())))

    def test_o_mapa_real_mais_os_legados_fecha_1_ate_13(self):
        from estoque.management.commands.renumerar_lotes_eminer import MAPA
        final = sorted(set(MAPA.values()) | {1, 2, 4})
        self.assertEqual(final, list(range(1, 14)),
                         'o mapa deixa buraco ou repetido na numeração final')


class OrdemDaListaDeLotesTests(TestCase):
    """A lista de lotes ordena por ABERTURA — e o número do lote É a sequência
    de abertura (o `Meta.ordering` do modelo diz `-number`).

    Bug de 2026-09-01: o template mandava `data-n="{{ lot.pk }}"` para o
    ordenador do navegador. Enquanto pk e número andaram juntos ninguém viu;
    os três lotes legados, criados no mesmo dia com número 1, 2 e 4 mas com a
    pk mais alta da tabela, foram parar no TOPO da lista — antes do lote 13.
    """

    def test_o_template_ordena_por_numero_e_nao_por_pk(self):
        import pathlib
        from django.conf import settings
        html = (pathlib.Path(settings.BASE_DIR) / 'estoque' / 'templates'
                / 'estoque' / 'lotes.html').read_text(encoding='utf-8')
        self.assertIn('data-n="{{ lot.number }}"', html)
        self.assertNotIn('data-n="{{ lot.pk }}"', html,
                         'a lista voltou a ordenar por chave primária — os '
                         'lotes importados vão pular para o topo de novo')

    def test_o_modelo_continua_ordenando_por_numero_decrescente(self):
        """O servidor e o navegador têm que concordar: se o Meta.ordering
        mudar sem o template mudar junto, a lista pisca ao carregar."""
        from estoque.models import Lot
        self.assertEqual(list(Lot._meta.ordering), ['-number'])
