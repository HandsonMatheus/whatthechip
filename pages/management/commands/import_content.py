"""
Comando Django para importar o conteúdo de _content/*.html para o banco.

Uso:
    python manage.py import_content
    python manage.py import_content --update   # força atualização mesmo se já existir
"""
import os
from django.core.management.base import BaseCommand
from pages.models import Page

PAGES = [
    {'file': 'index',         'title': 'Apresentação',                    'nav': 'Início',              'order':  1, 'section': 'Apresentação'},
    {'file': 'aprender',      'title': '1.1 O que você vai aprender',     'nav': '1.1 O que vai aprender', 'order': 2, 'section': '1. Introdução'},
    {'file': 'o-que-e-chip',  'title': '1.2 O que é um Chip',            'nav': '1.2 O que é um Chip', 'order':  3, 'section': '1. Introdução'},
    {'file': 'evolucao',      'title': '1.3 Evolução: do pino à esfera', 'nav': '1.3 Evolução',         'order':  4, 'section': '1. Introdução'},
    {'file': 'metodologia',   'title': '1.4 Metodologia de Identificação','nav': '1.4 Metodologia',     'order':  5, 'section': '1. Introdução'},
    {'file': 'tipos',         'title': '1.5 Tipos de Chip',               'nav': '1.5 Tipos de Chip',   'order':  6, 'section': '1. Introdução'},
    {'file': 'fabricantes',   'title': '2. Identificação por Fabricante', 'nav': '2. Fabricantes',       'order': 10, 'section': 'Conteúdo'},
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
    {'file': 'prefixos',      'title': '3. Tabela Rápida de Prefixos',    'nav': '3. Prefixos',          'order': 30, 'section': 'Conteúdo'},
    {'file': 'remarked',      'title': '4. Chips Remarked / Counterfeit', 'nav': '4. Remarked',          'order': 40, 'section': 'Conteúdo'},
    {'file': 'viabilidade',   'title': '5. Hierarquia de Viabilidade',    'nav': '5. Viabilidade',       'order': 50, 'section': 'Conteúdo'},
    {'file': 'soc',           'title': '6. CPUs / SoCs',                  'nav': '6. CPUs / SoCs',       'order': 60, 'section': 'Conteúdo'},
    {'file': 'encerramento',  'title': 'Encerramento',                    'nav': 'Encerramento',         'order': 70, 'section': 'Conteúdo'},
    {'file': 'contato',       'title': 'Contato',                         'nav': 'Contato',              'order': 80, 'section': 'Conteúdo'},
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

            obj, was_created = Page.objects.update_or_create(
                slug=p['file'],
                defaults={
                    'title':     p['title'],
                    'nav_title': p['nav'],
                    'order':     p['order'],
                    'section':   p['section'],
                    'content':   content,
                }
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
