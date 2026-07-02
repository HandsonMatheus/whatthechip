"""
Comando Django para exportar o conteúdo do banco de volta para _content/*.html.

Versiona o conteúdo do CMS: exporta as páginas editadas no admin
(CKEditor → PostgreSQL) de volta para _content/*.html — o backup versionado
que o import_content relê para semear o banco.

Uso:
    python manage.py export_content
    python manage.py export_content --slug fab-samsung       # exporta só uma página
    python manage.py export_content --dry-run                # mostra o que seria exportado
    python manage.py export_content --force                  # sobrescreve sem confirmar diff

Após exportar, versione:
    git add _content/
    git commit -m "content: atualiza páginas"
    git push
"""
import os
import difflib
from django.core.management.base import BaseCommand, CommandError
from pages.models import Page


class Command(BaseCommand):
    help = 'Exporta páginas do banco PostgreSQL para _content/*.html'

    def add_arguments(self, parser):
        parser.add_argument(
            '--slug',
            type=str,
            default=None,
            help='Exporta somente a página com este slug (ex: fab-samsung)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria exportado sem gravar nada',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Sobrescreve arquivos existentes sem mostrar diff',
        )

    def handle(self, *args, **options):
        slug_filter = options['slug']
        dry_run     = options['dry_run']
        force       = options['force']

        # Resolve o caminho de _content/ relativo a este arquivo
        # commands/ → management/ → pages/ → chipdocs/
        base_dir = os.path.dirname(          # chipdocs/
            os.path.dirname(                 # pages/
                os.path.dirname(             # management/
                    os.path.dirname(         # commands/
                        os.path.abspath(__file__)
                    )
                )
            )
        )
        content_dir = os.path.join(base_dir, '_content')
        os.makedirs(content_dir, exist_ok=True)

        # Seleciona páginas
        qs = Page.objects.all().order_by('order', 'slug')
        if slug_filter:
            qs = qs.filter(slug=slug_filter)
            if not qs.exists():
                raise CommandError(
                    f"Nenhuma página encontrada com slug='{slug_filter}'. "
                    f"Slugs disponíveis: "
                    + ', '.join(Page.objects.values_list('slug', flat=True).order_by('slug'))
                )

        exported = skipped = unchanged = 0

        for page in qs:
            filename  = f"{page.slug}.html"
            out_path  = os.path.join(content_dir, filename)
            new_content = page.content or ''

            # Lê conteúdo atual do arquivo (se existir)
            old_content = ''
            if os.path.exists(out_path):
                with open(out_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()

            # Sem mudança
            if old_content == new_content:
                self.stdout.write(f'  = Sem mudança: {filename}')
                unchanged += 1
                continue

            # Dry-run: só reporta
            if dry_run:
                self.stdout.write(self.style.WARNING(f'  ~ Seria atualizado: {filename}'))
                if old_content:
                    diff = list(difflib.unified_diff(
                        old_content.splitlines(), new_content.splitlines(),
                        fromfile=f'_content/{filename} (atual)',
                        tofile=f'_content/{filename} (banco)',
                        lineterm='',
                    ))
                    for line in diff[:30]:   # mostra até 30 linhas do diff
                        self.stdout.write('    ' + line)
                    if len(diff) > 30:
                        self.stdout.write(f'    … (+{len(diff) - 30} linhas)')
                else:
                    self.stdout.write(f'    (arquivo novo — {len(new_content)} chars)')
                skipped += 1
                continue

            # Grava
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            size_kb = len(new_content.encode('utf-8')) // 1024 or 1
            if old_content:
                self.stdout.write(self.style.SUCCESS(f'  ↺ Atualizado: {filename} ({size_kb} KB)'))
            else:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Criado:     {filename} ({size_kb} KB)'))
            exported += 1

        # Resumo
        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY-RUN] {skipped} seriam atualizados, {unchanged} sem mudança. '
                f'Nenhum arquivo foi gravado.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Exportação concluída: {exported} arquivo(s) gravado(s), '
                f'{unchanged} sem mudança.'
            ))
            if exported:
                self.stdout.write('')
                self.stdout.write('  Próximos passos:')
                self.stdout.write('    git add _content/')
                self.stdout.write('    git commit -m "content: atualiza páginas"')
                self.stdout.write('    git push')
