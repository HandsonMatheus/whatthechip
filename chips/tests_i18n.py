# -*- coding: utf-8 -*-
"""
Testes do sistema de i18n (I18N.md) — rodam na suíte padrão (`test chips`).
============================================================================
Cobrem as três garantias da arquitetura:

  1. RÓTULOS — a camada chips/labels.py resolve nos 4 idiomas e o valor
     CANÔNICO nunca muda (o engine continua falando pt-br).
  2. CADEIA DE RESOLUÇÃO — preferência no banco (UserLanguage) > cookie >
     Accept-Language (região) > pt-br; o seletor persiste a preferência.
  3. PORTÃO — os catálogos versionados passam no check_translations (a mesma
     engine que barra a rotina de tradução por IA — I18N.md §7).

Vive em chips/ (e não em tenancy/) de propósito: é o app que a suíte
documentada (`test chips estoque`) sempre roda.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from chips.labels import profitability_label, source_label
from pages.models import Page
from tenancy.models import UserLanguage


class LabelsI18NTests(TestCase):
    """Superfície 2 (I18N.md §5): canônico ≠ rótulo, nos 4 idiomas."""

    EXPECTED_PROFIT = {
        'pt-br':   'NÃO RENTÁVEL',
        'es':      'NO RENTABLE',
        'en':      'NOT PROFITABLE',
        'zh-hans': '无利润',
    }
    EXPECTED_SOURCE = {
        'pt-br':   'banco de dados',
        'es':      'base de datos',
        'en':      'database',
        'zh-hans': '数据库',
    }

    def tearDown(self):
        translation.deactivate_all()

    def test_rotulo_de_rentabilidade_por_idioma(self):
        for lng, esperado in self.EXPECTED_PROFIT.items():
            with translation.override(lng):
                self.assertEqual(str(profitability_label('NÃO RENTÁVEL')), esperado)

    def test_rotulo_de_fonte_por_idioma(self):
        for lng, esperado in self.EXPECTED_SOURCE.items():
            with translation.override(lng):
                self.assertEqual(str(source_label('banco de dados')), esperado)

    def test_valor_canonico_nunca_muda(self):
        """O ENGINE fala pt-br canônico em qualquer idioma ativo — se este teste
        quebrar, alguém traduziu valor de lógica (regra de ouro do i18n)."""
        from chips.engine import assess_profitability
        with translation.override('zh-hans'):
            veredito = assess_profitability({'chip_type': 'ePoP', 'subtype': ''})
        self.assertEqual(veredito, 'NÃO RENTÁVEL')

    def test_fail_open_para_valor_desconhecido(self):
        with translation.override('es'):
            self.assertEqual(profitability_label('QUALQUER COISA'), 'QUALQUER COISA')
            self.assertEqual(source_label('outra fonte'), 'outra fonte')


class CadeiaDeResolucaoTests(TestCase):
    """Camadas da detecção (I18N.md §3): banco > cookie > região > pt-br."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('op1', password='x')

    def test_fallback_e_pt_br(self):
        resp = self.client.get('/login/')
        self.assertEqual(resp.headers.get('Content-Language'), 'pt-br')

    def test_regiao_accept_language(self):
        """Navegador da China → zh-hans; do Paraguai → es. Sem cookie, sem login."""
        c = Client(headers={'accept-language': 'zh-CN,zh;q=0.9'})
        self.assertEqual(c.get('/login/').headers.get('Content-Language'), 'zh-hans')
        c = Client(headers={'accept-language': 'es-PY,es;q=0.9'})
        self.assertEqual(c.get('/login/').headers.get('Content-Language'), 'es')

    def test_cookie_vence_accept_language(self):
        c = Client(headers={'accept-language': 'en-US,en;q=0.9'})
        c.cookies[settings.LANGUAGE_COOKIE_NAME] = 'es'
        self.assertEqual(c.get('/login/').headers.get('Content-Language'), 'es')

    def test_preferencia_no_banco_vence_tudo(self):
        UserLanguage.objects.create(user=self.user, language='zh-hans')
        c = Client(headers={'accept-language': 'en-US,en;q=0.9'})
        c.force_login(self.user)
        c.cookies[settings.LANGUAGE_COOKIE_NAME] = 'es'   # cookie diz es…
        resp = c.get('/login/')
        self.assertEqual(resp.headers.get('Content-Language'), 'zh-hans')

    def test_preferencia_invalida_cai_na_deteccao(self):
        """Idioma removido do settings não pode travar o usuário (fail-open)."""
        UserLanguage.objects.create(user=self.user, language='xx-removido')
        c = Client(headers={'accept-language': 'es-PY,es;q=0.9'})
        c.force_login(self.user)
        self.assertEqual(c.get('/login/').headers.get('Content-Language'), 'es')

    def test_set_language_persiste_para_logado(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('set_language'),
                                {'language': 'en', 'next': '/login/'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            UserLanguage.objects.get(user=self.user).language, 'en')
        # e a próxima página já vem em inglês
        self.assertEqual(
            self.client.get('/login/').headers.get('Content-Language'), 'en')

    def test_set_language_anonimo_soh_cookie(self):
        resp = self.client.post(reverse('set_language'),
                                {'language': 'es', 'next': '/login/'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(UserLanguage.objects.count(), 0)   # nada persistido
        self.assertEqual(
            self.client.get('/login/').headers.get('Content-Language'), 'es')

    def test_set_language_rejeita_idioma_desconhecido(self):
        self.client.force_login(self.user)
        self.client.post(reverse('set_language'),
                         {'language': 'kl-ingon', 'next': '/login/'})
        self.assertEqual(UserLanguage.objects.count(), 0)


class TemplateSmokeTests(TestCase):
    """As páginas-chave renderizam nos 4 idiomas (marcação sem erro de sintaxe)."""

    def test_login_renderiza_em_todos_os_idiomas(self):
        for lng, _nome in settings.LANGUAGES:
            c = Client()
            c.cookies[settings.LANGUAGE_COOKIE_NAME] = lng
            resp = c.get('/login/')
            self.assertEqual(resp.status_code, 200, lng)

    def test_decode_card_renderiza_em_zh(self):
        """O parcial HTMX do decode (o card da bancada) renderiza em 中文."""
        c = Client()
        c.cookies[settings.LANGUAGE_COOKIE_NAME] = 'zh-hans'
        resp = c.get('/chips/decode/', {'pn': 'KMQX10006M'})
        self.assertEqual(resp.status_code, 200)

    def test_catalogo_js_por_idioma(self):
        """O JavaScriptCatalog serve o gettext() do mic.js no idioma ativo."""
        c = Client()
        c.cookies[settings.LANGUAGE_COOKIE_NAME] = 'es'
        resp = c.get(reverse('javascript-catalog'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Escuchando', resp.content.decode())


class I18nSourceVenvGuardTests(TestCase):
    """BUG real (2026-07-10): o venv do dono vive DENTRO do projeto
    (chipdocs/venv/), então a descoberta dinâmica classificava django/
    modeltranslation/pghistory como "apps locais" e o portão varria os
    templates e _() do PRÓPRIO Django (msgids falsos + PT-cru de terceiros).
    Não reproduzia no sandbox (pacotes fora do BASE_DIR) — por isso estes
    testes prendem o comportamento nos DOIS ambientes."""

    def test_caminho_de_venv_e_excluido(self):
        from pathlib import Path
        from chips.i18n_source import _excluded
        self.assertTrue(_excluded(Path(
            'venv/lib/python3.14/site-packages/django/contrib/admin/templates/a.html')))
        self.assertTrue(_excluded(Path('.venv/lib/python3.12/site-packages/x.py')))
        self.assertTrue(_excluded(Path('staticfiles/admin/js/core.js')))
        self.assertFalse(_excluded(Path('estoque/templates/estoque/estoque.html')))
        self.assertFalse(_excluded(Path('chips/views.py')))

    def test_apps_de_site_packages_nunca_sao_locais(self):
        """Na máquina do dono (venv dentro do projeto) isto FALHAVA pré-fix:
        django/modeltranslation entravam como apps locais."""
        from chips.i18n_source import _local_app_paths
        nomes = {p.name for p in _local_app_paths()}
        self.assertTrue({'chips', 'estoque', 'pricing', 'tenancy', 'pages'} <= nomes,
                        f'apps do projeto sumiram da descoberta: {nomes}')
        intrusos = {'django', 'admin', 'modeltranslation', 'pghistory',
                    'pgtrigger', 'contrib'} & nomes
        self.assertFalse(intrusos, f'app de site-packages tratado como local: {intrusos}')

    def test_varredura_nunca_entra_no_venv(self):
        from chips.i18n_source import (template_files, python_files, js_files,
                                       _EXCLUDED_PARTS)
        for f in (list(template_files()) + list(python_files())
                  + list(js_files())):
            self.assertFalse(
                _EXCLUDED_PARTS.intersection(f.parts),
                f'arquivo de venv/estático varrido pelo portão: {f}')


class PortaoDeCatalogoTests(TestCase):
    """O check_translations (I18N.md §7) passa nos catálogos versionados.
    Se este teste quebrar: alguém ativou idioma sem catálogo, deixou entrada
    vazia/fuzzy, quebrou placeholder/HTML ou traduziu termo protegido."""

    def test_catalogos_publicaveis(self):
        from django.core.management import call_command
        call_command('check_translations', verbosity=0)   # CommandError = falha


class I18nChoicesDeclarationTests(TestCase):
    """CONVENÇÃO i18n de choices (CLAUDE.md §6 / I18N.md §5.2): rótulo de
    choices que CHEGA a usuário final (get_FOO_display em template, badge,
    dashboard) nasce com gettext_lazy. Todo campo com choices dos apps do
    projeto ou tem rótulos traduzíveis (lazy/Promise), ou está DECLARADO
    abaixo com justificativa. Campo novo sem decisão = suíte vermelha —
    mesmo padrão do TenancyDeclarationTests.

    Classe de erro real que motivou o portão (2026-07-08): o crachá de papel
    do header (`wtc_membership.get_role_display`) ficava em PT nos 4 idiomas
    porque ROLE_CHOICES nasceu sem _lazy."""

    DECLARADOS = {
        # ── Admin-only: o Django admin é superfície de PLATAFORMA, fixa em
        #    pt-br (decisão do dono 2026-07-08 — I18N.md §2.7). Estes rótulos
        #    nunca chegam a operador/comprador; se um dia chegarem, saem daqui
        #    e ganham _lazy.
        'chips.Source.src_type',
        'chips.KnownPart.confidence',
        'chips.KnownPart.review_status',
        'chips.CorrectionRequest.status',
        'chips.ChipSubmission.status',
        'estoque.Lot.status',            # UI usa chave (lot.status) + trans no template
        'pricing.PricingConfig.default_scenario',
        # ── Rótulo = DADO técnico, idêntico em qualquer idioma (glossário):
        'pricing.Price.kind',            # eMMC / UFS / eMCP…
        'pricing.Price.tier_unit',       # GB (pacote) / Gb (die) — admin-only
    }
    APPS_DO_PROJETO = {'chips', 'estoque', 'pages', 'tenancy', 'pricing'}

    def test_todo_choices_declara_traducao(self):
        from django.apps import apps as django_apps
        from django.utils.functional import Promise
        faltando = []
        for model in django_apps.get_models():
            if model._meta.app_label not in self.APPS_DO_PROJETO:
                continue
            if hasattr(model, 'pgh_tracked_model'):
                continue    # espelhos de evento pghistory herdam os campos
            for field in model._meta.fields:
                choices = field.choices
                if not choices:
                    continue
                if callable(choices):
                    choices = choices()
                label = f'{model._meta.app_label}.{model.__name__}.{field.name}'
                if label in self.DECLARADOS:
                    continue
                if all(isinstance(nome, Promise) for _v, nome in choices):
                    continue          # traduzível (gettext_lazy) — ok
                faltando.append(label)
        self.assertEqual(
            faltando, [],
            'Campo(s) com choices SEM decisão de i18n: ou envolva os rótulos '
            'em gettext_lazy (se chegam a usuário final), ou adicione à lista '
            'DECLARADOS com justificativa (admin-only/rótulo-dado): '
            f'{faltando}')


class CmsConteudoPorIdiomaTests(TestCase):
    """Superfície 3 (I18N.md §9): o conteúdo editorial vem de ARQUIVO
    (_content/<slug>.<código>.html, escolhido pelo idioma ativo, fallback
    pt-br) e os METADADOS (title…) vêm do modeltranslation no banco."""

    HOME_PROBES = {
        'pt-br':   'Experimente',
        'es':      'Prueba',
        'en':      'Try it',
        'zh-hans': '试试看',
    }

    def _client_em(self, lng):
        c = Client()
        c.cookies[settings.LANGUAGE_COOKIE_NAME] = lng
        return c

    def test_home_serve_o_arquivo_do_idioma_ativo(self):
        for lng, probe in self.HOME_PROBES.items():
            resp = self._client_em(lng).get('/')
            self.assertEqual(resp.status_code, 200, lng)
            self.assertIn(probe, resp.content.decode(), lng)

    def test_home_placeholders_resolvem_em_todo_idioma(self):
        """{{STAT_*}}/{{PREFIX_DATA}} têm que sumir também nos arquivos traduzidos
        (a view roda os replaces DEPOIS de escolher o arquivo)."""
        for lng in self.HOME_PROBES:
            html = self._client_em(lng).get('/').content.decode()
            # os 4 placeholders REAIS têm que ter sido substituídos (o comentário
            # do topo do arquivo cita "{{STAT_*}}" literal — não conta).
            for ph in ('{{STAT_PARTS}}', '{{STAT_BRANDS}}',
                       '{{STAT_FAMILIES}}', '{{STAT_SEARCHES}}',
                       '{{PREFIX_DATA}}'):
                self.assertNotIn(ph, html, f'{lng}: {ph}')

    def test_pagina_sem_traducao_cai_no_pt(self):
        """Página cujo _content só existe em PT (ex.: fabricantes) renderiza o
        conteúdo PT em qualquer idioma — fallback, nunca em branco."""
        Page.objects.create(slug='fabricantes', title='2. Identificação por Fabricante',
                            order=10, content='')
        resp = self._client_em('zh-hans').get('/fabricantes/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.content), 500)   # veio conteúdo (PT do disco)

    def test_metadado_traduzido_pelo_modeltranslation(self):
        """title_es alimenta o <title> quando o idioma ativo é es."""
        Page.objects.create(slug='contato', title='Contato', title_es='Contacto',
                            order=80, content='<p>x</p>')
        html = self._client_em('es').get('/contato/').content.decode()
        self.assertIn('Contacto — WhatTheChip?', html)

    def test_titulo_da_home_traduz(self):
        html = self._client_em('zh-hans').get('/').content.decode()
        self.assertIn('<title>首页 — WhatTheChip?</title>', html)


class SeletorDeIdiomaPresenteTests(TestCase):
    """MULTILANGUAGE.md: TODA superfície do produto tem um seletor de idioma
    visível — home (dropdown do topnav), login, painel/estoque (shell escuro)
    e dashboard do parceiro. Shell novo sem seletor = este teste quebra."""

    SETLANG = 'action="/i18n/setlang/"'

    def test_home_tem_dropdown(self):
        html = self.client.get('/').content.decode()
        self.assertIn(self.SETLANG, html)
        self.assertIn('data-lang="zh-hans"', html)   # itens do dropdown

    def test_login_tem_seletor(self):
        self.assertIn(self.SETLANG, self.client.get('/login/').content.decode())

    def test_painel_e_estoque_tem_seletor(self):
        from tenancy.models import Company, Membership
        u = get_user_model().objects.create_user('op_sel', password='x')
        co = Company.objects.create(name='Sel', slug='sel')
        Membership.objects.create(user=u, company=co, role='operator')
        self.client.force_login(u)
        html = self.client.get('/painel/').content.decode()
        self.assertIn(self.SETLANG, html)
        # variante 'shell' (visível no header escuro — não o select transparente)
        self.assertIn('border:1px solid #525252', html)

    def test_partner_tem_seletor(self):
        from pricing.models import Buyer
        from tenancy.models import Company
        u = get_user_model().objects.create_user('buyer_sel', password='x')
        co = Company.objects.create(name='SelP', slug='selp')
        b = Buyer.all_companies.create(company=co, name='Wu', slug='wu')
        b.users.add(u)
        self.client.force_login(u)
        html = self.client.get('/partner/').content.decode()
        self.assertIn(self.SETLANG, html)
        self.assertIn('border:1px solid #525252', html)


class AdminPlataformaPtBrTests(TestCase):
    """O Django admin é fixo em pt-br (decisão 2026-07-08 — I18N.md §2.7):
    ferramenta de plataforma, 100% consistente, zero dívida de tradução de
    verbose_names. O APP continua multilíngue."""

    def test_admin_ignora_idioma_do_usuario(self):
        from tenancy.models import UserLanguage
        u = get_user_model().objects.create_user(
            'dono', password='x', is_staff=True, is_superuser=True)
        UserLanguage.objects.create(user=u, language='zh-hans')
        c = Client(headers={'accept-language': 'zh-CN'})
        c.force_login(u)
        resp = c.get('/admin/')
        self.assertEqual(resp.headers.get('Content-Language'), 'pt-br')

    def test_app_continua_no_idioma_do_usuario(self):
        from tenancy.models import UserLanguage
        u = get_user_model().objects.create_user('op9', password='x')
        UserLanguage.objects.create(user=u, language='zh-hans')
        c = Client()
        c.force_login(u)
        self.assertEqual(
            c.get('/login/').headers.get('Content-Language'), 'zh-hans')
