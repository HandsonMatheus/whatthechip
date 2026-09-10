# -*- coding: utf-8 -*-
"""A PROVA da conferência — modelo, foto e vocabulário (dono, 2026-09-10).

> "o comprador manda fotos dos chips danificados e observacoes sobre a
> qualidade do lote… ele possa anotar essas observacoes e anexar as fotos, e
> tanto as observacoes como as fotos sairem no PDF final"

Esta é a fatia 1: os dados. A tela e o PDF vêm depois, e vêm em cima disto.
"""
import io
from datetime import date
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from estoque.models import Lot
from pricing.models import Buyer
from tenancy.models import Company, Membership
from tenancy.scope import company_scope
from vendas import fotos
from vendas.models import (DefeitoTipo, DocSequence, Prova, ProvaFoto, SEQ_SO,
                           SalesOrder, SalesOrderLine, STATUS_CONFIRMED)

User = get_user_model()


def _png(w=40, h=30, cor=(200, 30, 40)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (w, h), cor).save(buf, format='PNG')
    return buf.getvalue()


def _jpg(w=3000, h=2000):
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (w, h), (90, 90, 90)).save(buf, format='JPEG', quality=95)
    return buf.getvalue()


class OVocabularioTests(TestCase):
    """O defeito é ETIQUETA, não texto — e é isso que o faz atravessar o
    balcão sem tradutor."""

    def setUp(self):
        # ⚠ O `canto_lascado` já existe: a migração 0028 o planta. Criar de
        #   novo estourava a unicidade do código — e a lição fica: teste de
        #   vocabulário semeado LÊ a semente, não a duplica. Se a semente
        #   mudar, é aqui que se descobre.
        self.d = DefeitoTipo.objects.get(codigo='canto_lascado')

    def test_o_MESMO_defeito_em_quatro_idiomas(self):
        """O comprador marca em chinês; o cliente lê em espanhol. Sem esta
        tabela, alguém traduz à mão toda vez — ou o cliente recebe 缺角."""
        self.assertEqual(self.d.rotulo('pt-br'), 'Canto lascado')
        self.assertEqual(self.d.rotulo('es'), 'Esquina astillada')
        self.assertEqual(self.d.rotulo('zh-hans'), '缺角')
        self.assertEqual(self.d.rotulo('en'), 'Chipped corner')

    def test_idioma_sem_traducao_cai_no_PORTUGUES_e_nao_no_codigo(self):
        """Código de banco na cara do cliente é pior que idioma errado."""
        d = DefeitoTipo.objects.create(codigo='novo', nome_pt='Defeito novo')
        self.assertEqual(d.rotulo('es'), 'Defeito novo')
        self.assertEqual(d.rotulo('zh'), 'Defeito novo')
        self.assertNotIn('novo_', d.rotulo('es'))

    def test_a_semente_da_migracao_esta_no_banco(self):
        """Os dez que a 0028 planta — a tela não pode nascer vazia."""
        self.assertGreaterEqual(DefeitoTipo.objects.count(), 10)
        for codigo in ('balls_faltando', 'empolamento', 'canto_lascado',
                       'risco'):
            self.assertTrue(
                DefeitoTipo.objects.filter(codigo=codigo).exists(), codigo)

    def test_balls_faltando_RECUSA_e_risco_DESCONTA(self):
        """A severidade é a ponte com a repactuação: cosmético justifica
        PREÇO menor, defeito funcional justifica unidade recusada.

        ⚠ Balls faltando é RECUSA, não identidade — o dono corrigiu isto em
          10/09: a foto do loupe não era remarcação, eram esferas faltando.
          Chip sem ball não solda; não é questão de valer menos.
        """
        balls = DefeitoTipo.objects.get(codigo='balls_faltando')
        risco = DefeitoTipo.objects.get(codigo='risco')
        self.assertEqual(balls.severidade, DefeitoTipo.SEV_RECUSA)
        self.assertEqual(risco.severidade, DefeitoTipo.SEV_DESCONTO)

    def test_o_vocabulario_e_GLOBAL(self):
        """Sem `company`: duas empresas conferindo o mesmo chip têm de ler o
        mesmo nome de defeito. É a regra da PoliticaOrigemTipo.

        ⚠ E, por consequência, SEM manager escopado: a primeira versão usava
          `PlatformSharedManager` e ler o vocabulário fora de um
          `company_scope` explodia com `CompanyScopeMissing` — numa tabela que
          não é de empresa nenhuma. Este teste prende as duas metades juntas.
        """
        self.assertFalse(
            any(f.name == 'company' for f in DefeitoTipo._meta.get_fields()))
        from tenancy.scope import CompanyScopedManager
        self.assertNotIsInstance(DefeitoTipo.objects, CompanyScopedManager)


class ATravessiaDaFotoTests(TestCase):
    """`vendas/fotos.py` — o que entra grande tem de sair pequeno e de pé."""

    def test_a_foto_de_celular_ENCOLHE(self):
        """3000×2000 é uma foto de celular. Se ela entrasse inteira, vinte
        delas num lote seriam dezenas de MB no Postgres."""
        raw = _jpg(3000, 2000)
        out = fotos.preparar(raw, 'chip.jpg')
        self.assertLessEqual(max(out['width'], out['height']),
                             fotos.LADO_GRANDE)
        self.assertLess(len(out['data']), len(raw) / 2,
                        'a foto não encolheu de verdade')

    def test_a_MINIATURA_e_muito_menor_que_a_grande(self):
        """Ela vem em toda listagem; se não for pequena, a tela paga por foto."""
        out = fotos.preparar(_jpg(3000, 2000))
        self.assertLess(len(out['thumb']), len(out['data']) / 4)

    def test_foto_PEQUENA_nao_e_ampliada(self):
        out = fotos.preparar(_png(40, 30))
        self.assertEqual((out['width'], out['height']), (40, 30))

    def test_PNG_com_transparencia_nao_vira_preto(self):
        """JPEG não tem alfa. Sem compor sobre branco, o fundo vira preto e a
        foto do chip fica ilegível."""
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGBA', (50, 50), (255, 0, 0, 0)).save(buf, format='PNG')
        out = fotos.preparar(buf.getvalue())
        img = Image.open(io.BytesIO(out['data']))
        self.assertEqual(img.mode, 'RGB')
        self.assertNotEqual(img.getpixel((25, 25)), (0, 0, 0))

    def test_o_EXIF_NAO_atravessa(self):
        """Encolhe o arquivo e, mais importante, tira a geolocalização: a foto
        vai parar na mão do cliente."""
        from PIL import Image
        out = fotos.preparar(_jpg(800, 600))
        img = Image.open(io.BytesIO(out['data']))
        self.assertFalse(img.getexif(), 'o EXIF veio junto')

    def test_a_foto_DEITADA_chega_de_pe(self):
        """O celular grava sempre na mesma orientação e diz no EXIF como
        girar. O navegador obedece; o reportlab não. Sem `exif_transpose`, a
        foto sai deitada SÓ no PDF — e ninguém percebe na tela."""
        from PIL import Image
        base = Image.new('RGB', (600, 300), (10, 10, 10))
        exif = base.getexif()
        exif[274] = 6                     # Orientation: girar 90°
        buf = io.BytesIO()
        base.save(buf, format='JPEG', exif=exif)
        out = fotos.preparar(buf.getvalue())
        self.assertGreater(out['height'], out['width'],
                           'a foto continuou deitada')

    def test_arquivo_grande_demais_e_recusado_ANTES_de_abrir(self):
        with self.assertRaises(ValidationError):
            fotos.preparar(b'x' * (fotos.MAX_BYTES + 1))

    def test_arquivo_que_nao_e_imagem_da_mensagem_legivel(self):
        """Ele está na bancada com o celular, não vai ler log."""
        with self.assertRaises(ValidationError) as cm:
            fotos.preparar(b'isto nao e uma imagem')
        self.assertIn('imagem', str(cm.exception).lower())

    def test_vazio_nao_estoura(self):
        with self.assertRaises(ValidationError):
            fotos.preparar(b'')


class _Base(TestCase):
    def setUp(self):
        self.emp = Company.objects.create(name='eMiner', slug='eminer', code='')
        self.buyer = Buyer.all_companies.create(company=None, name='Wu Quan',
                                                slug='wu-quan')
        self.parceiro = User.objects.create_user('u_wq', password='x')
        self.buyer.users.add(self.parceiro)
        self.gerente = User.objects.create_user('g', password='x')
        Membership.objects.create(user=self.gerente, company=self.emp,
                                  role=Membership.ROLE_MANAGER)
        with company_scope(self.emp.id):
            self.lot = Lot.all_companies.create(
                company=self.emp, number=9, description='x', status='closed',
                operator=self.gerente, origin='pcb')
            self.so = SalesOrder(
                lot=self.lot, buyer=self.buyer, status=STATUS_CONFIRMED,
                fx_usd_rate=D('0.1481'), total_rmb=D('100'),
                total_usd=D('14.81'), shipped_at=date(2026, 8, 18),
                received_at=timezone.now(),
                number=DocSequence.next_number(self.emp, SEQ_SO))
            self.so.save()
            self.linha = SalesOrderLine.all_companies.create(
                order=self.so, company=self.emp, brand='Micron', kind='emmc',
                gen='', tier_value=D('64'), tier_unit='GB', quantity=100,
                unit_rmb=D('1.00'), unit_usd=D('0.15'))


class AProvaTests(_Base):

    def _prova(self, **kw):
        with company_scope(self.emp.id):
            p = Prova(order=self.so, line=self.linha,
                      created_by=self.parceiro, **kw)
            p.save()
            return p

    def test_a_empresa_vem_da_ORDEM_sozinha(self):
        """Ninguém digita `company`: ela é derivada, como em toda tabela de
        vendas. É o que faz o RLS não ter buraco por esquecimento."""
        p = self._prova(nota='caixa molhada')
        self.assertEqual(p.company_id, self.emp.id)

    def test_a_prova_do_LOTE_nao_precisa_de_linha(self):
        """"A caixa chegou molhada" não é de uma linha — é do lote."""
        with company_scope(self.emp.id):
            p = Prova(order=self.so, line=None, nota='caixa molhada')
            p.save()
        self.assertIsNone(p.line_id)
        self.assertEqual(p.company_id, self.emp.id)

    def test_linha_de_OUTRA_ordem_e_recusada(self):
        """Prova pendurada na linha errada acusaria o chip errado."""
        with company_scope(self.emp.id):
            outro = Lot.all_companies.create(
                company=self.emp, number=10, description='y', status='closed',
                operator=self.gerente, origin='pcb')
            so2 = SalesOrder(lot=outro, buyer=self.buyer,
                             status=STATUS_CONFIRMED, fx_usd_rate=D('0.1481'),
                             total_rmb=D('1'), total_usd=D('1'),
                             shipped_at=date(2026, 8, 18),
                             number=DocSequence.next_number(self.emp, SEQ_SO))
            so2.save()
            p = Prova(order=so2, line=self.linha)
            with self.assertRaises(ValidationError):
                p.clean()

    def test_uma_prova_carrega_VARIOS_defeitos(self):
        """A foto da bancada dele mostra 磕角, 划痕 e 起泡 na mesma imagem."""
        p = self._prova()
        with company_scope(self.emp.id):
            p.defeitos.set(DefeitoTipo.objects.filter(
                codigo__in=['canto_lascado', 'risco', 'empolamento']))
            self.assertEqual(p.defeitos.count(), 3)

    def test_apagar_a_linha_leva_a_prova_junto(self):
        """CASCATA de propósito: prova órfã acusa um chip que não está mais na
        ordem — pior do que prova nenhuma."""
        p = self._prova()
        with company_scope(self.emp.id):
            self.linha.delete()
        self.assertFalse(Prova.all_companies.filter(pk=p.pk).exists())


class AFotoNoBancoTests(_Base):

    def _com_foto(self):
        with company_scope(self.emp.id):
            p = Prova(order=self.so, line=self.linha)
            p.save()
            f = ProvaFoto(prova=p, **fotos.preparar(_jpg(2000, 1500), 'a.jpg'))
            f.save()
            return p, f

    def test_a_foto_vai_para_o_POSTGRES_e_nao_para_o_disco(self):
        """O filesystem da Render é efêmero — um deploy apagaria a prova. É o
        mesmo motivo do comprovante de pagamento ter virado BinaryField."""
        _p, f = self._com_foto()
        self.assertTrue(ProvaFoto._meta.get_field('data').get_internal_type()
                        == 'BinaryField')
        with company_scope(self.emp.id):
            lido = ProvaFoto.com_dados.get(pk=f.pk)
        self.assertGreater(len(bytes(lido.data)), 1000)

    def test_a_LISTAGEM_nao_arrasta_o_blob_grande(self):
        """O teste que guarda a decisão do `_FotoManager`: `data` tem centenas
        de KB e é lido em toda visita se alguém escrever `.all()` distraído.
        Aqui o caminho seguro é o PADRÃO — e isto prova que continua sendo."""
        _p, f = self._com_foto()
        with company_scope(self.emp.id):
            obj = ProvaFoto.objects.get(pk=f.pk)
            self.assertIn('data', obj.get_deferred_fields(),
                          'o blob grande veio na listagem')
            self.assertNotIn('thumb', obj.get_deferred_fields(),
                             'a miniatura precisa vir — é a grade da tela')

    def test_a_empresa_da_foto_vem_da_PROVA(self):
        _p, f = self._com_foto()
        self.assertEqual(f.company_id, self.emp.id)

    def test_apagar_a_prova_leva_as_fotos(self):
        p, f = self._com_foto()
        with company_scope(self.emp.id):
            p.delete()
        self.assertFalse(ProvaFoto.all_companies.filter(pk=f.pk).exists())

    def test_o_tamanho_guardado_e_o_da_versao_REDUZIDA(self):
        """`size` existe para responder "quanto isto pesa no banco". Se
        guardasse o tamanho do original, mentiria por um fator de dez."""
        _p, f = self._com_foto()
        with company_scope(self.emp.id):
            lido = ProvaFoto.com_dados.get(pk=f.pk)
        self.assertEqual(f.size, len(bytes(lido.data)))
