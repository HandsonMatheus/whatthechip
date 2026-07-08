"""
Comando Django para importar o conteúdo de _content/*.html para o banco.

Uso:
    python manage.py import_content
    python manage.py import_content --update   # força atualização mesmo se já existir

i18n (I18N.md §9): o CONTEÚDO por idioma NÃO passa por aqui — as views leem
_content/<slug>.<código>.html direto do disco (fallback pt-br automático).
O que este comando também grava são os METADADOS traduzidos (title/nav/section
→ colunas *_es/*_en/*_zh_hans do modeltranslation), declarados na chave 'i18n'
de cada página — alimentam o <title> da aba e a navegação. Página sem 'i18n'
fica no fallback pt-br (nomes de marca como "2.1 Samsung" são iguais em
qualquer idioma — não precisam da chave).
"""
import os
from django.core.management.base import BaseCommand
from modeltranslation.utils import build_localized_fieldname
from pages.models import Page

PAGES = [
    {'file': 'index',         'title': 'Apresentação',                    'nav': 'Início',              'order':  1, 'section': 'Apresentação',
     'i18n': {
        'es':      {'title': 'Presentación', 'nav': 'Inicio', 'section': 'Presentación'},
        'en':      {'title': 'Overview',     'nav': 'Home',   'section': 'Overview'},
        'zh-hans': {'title': '简介',          'nav': '首页',    'section': '简介'},
     }},
    {'file': 'fabricantes',   'title': '2. Identificação por Fabricante', 'nav': '2. Fabricantes',       'order': 10, 'section': 'Conteúdo',
     'i18n': {
        'es':      {'title': '2. Identificación por Fabricante', 'nav': '2. Fabricantes',    'section': 'Contenido'},
        'en':      {'title': '2. Identification by Manufacturer', 'nav': '2. Manufacturers', 'section': 'Content'},
        'zh-hans': {'title': '2. 按制造商识别',                     'nav': '2. 制造商',          'section': '内容'},
     }},
    {'file': 'fab-samsung',   'title': '2.1 Samsung',                     'nav': '2.1 Samsung',          'order': 11, 'section': 'Conteúdo'},
    {'file': 'fab-hynix',     'title': '2.2 SK Hynix',                   'nav': '2.2 SK Hynix',         'order': 12, 'section': 'Conteúdo'},
    {'file': 'fab-micron',    'title': '2.3 Micron',                      'nav': '2.3 Micron',           'order': 13, 'section': 'Conteúdo'},
    {'file': 'fab-elpida',    'title': '2.4 Elpida Memory',               'nav': '2.4 Elpida',           'order': 14, 'section': 'Conteúdo'},
    {'file': 'fab-toshiba',   'title': '2.5 Toshiba / Kioxia',           'nav': '2.5 Toshiba',          'order': 15, 'section': 'Conteúdo'},
    {'file': 'fab-sandisk',   'title': '2.6 SanDisk / WD',               'nav': '2.6 SanDisk',          'order': 16, 'section': 'Conteúdo'},
    {'file': 'fab-nanya',     'title': '2.7 Nanya Technology',            'nav': '2.7 Nanya',            'order': 17, 'section': 'Conteúdo'},
    {'file': 'fab-kingston',  'title': '2.8 Kingston',                    'nav': '2.8 Kingston',         'order': 18, 'section': 'Conteúdo'},
    {'file': 'fab-rayson',    'title': '2.9 Rayson',                      'nav': '2.9 Rayson',           'order': 19, 'section': 'Conteúdo'},
    {'file': 'fab-issi',      'title': '2.10 ISSI',                       'nav': '2.10 ISSI',            'order': 20, 'section': 'Conteúdo'},
    {'file': 'fab-gigadevice','title': '2.11 GigaDevice',                 'nav': '2.11 GigaDevice',      'order': 21, 'section': 'Conteúdo'},
    {'file': 'contato',       'title': 'Contato',                         'nav': 'Contato',              'order': 80, 'section': 'Conteúdo',
     'i18n': {
        'es':      {'title': 'Contacto', 'nav': 'Contacto', 'section': 'Contenido'},
        'en':      {'title': 'Contact',  'nav': 'Contact',  'section': 'Content'},
        'zh-hans': {'title': '联系我们',   'nav': '联系我们',   'section': '内容'},
     }},
]


class Command(BaseCommand):
    help = 'Importa os arquivos _content/*.html para o banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update',
            action='store_true',
            help='Atualiza páginas que já existem no banco',
        )

    def handle(self, *args, **options):
        force_update = options['update']
        base_dir = os.path.dirname(      # chipdocs/
            os.path.dirname(             # pages/
                os.path.dirname(         # management/
                    os.path.dirname(     # commands/
                        os.path.abspath(__file__)
                    )
                )
            )
        )
        content_dir = os.path.join(base_dir, '_content')

        created = updated = skipped = missing = 0

        for p in PAGES:
            path = os.path.join(content_dir, f"{p['file']}.html")

            if not os.path.exists(path):
                self.stdout.write(self.style.WARNING(f"  AVISO: {p['file']}.html não encontrado"))
                missing += 1
                continue

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            exists = Page.objects.filter(slug=p['file']).exists()

            if exists and not force_update:
                self.stdout.write(f"  — Pulado (já existe): {p['file']}")
                skipped += 1
                continue

            defaults = {
                'title':     p['title'],
                'nav_title': p['nav'],
                'order':     p['order'],
                'section':   p['section'],
                'content':   content,
            }
            # i18n: metadados traduzidos → colunas do modeltranslation
            # (title_es, nav_title_zh_hans…). Conteúdo por idioma NÃO entra
            # aqui — a view resolve _content/<slug>.<código>.html do disco.
            for code, meta in (p.get('i18n') or {}).items():
                for src_key, field in (('title', 'title'),
                                       ('nav', 'nav_title'),
                                       ('section', 'section')):
                    if src_key in meta:
                        defaults[build_localized_fieldname(field, code)] = meta[src_key]

            obj, was_created = Page.objects.update_or_create(
                slug=p['file'],
                defaults=defaults,
            )

            if was_created:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Criado: {p['file']}"))
                created += 1
            else:
                self.stdout.write(self.style.SUCCESS(f"  ↺ Atualizado: {p['file']}"))
                updated += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Concluído: {created} criados, {updated} atualizados, '
            f'{skipped} pulados, {missing} não encontrados.'
        ))
        self.stdout.write(f'Total no banco: {Page.objects.count()} páginas.')
