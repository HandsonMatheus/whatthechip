"""
Remove páginas do CMS (linhas `Page`) por slug.

Use quando uma página editorial foi aposentada: além de apagar o
`_content/<slug>.html`, rode este comando (contra o banco certo) para tirar a
linha `Page` — senão a página continua no MENU e, sem o arquivo, cai no
conteúdo ANTIGO do banco (fallback de `page_detail`).

Dry-run por padrão; use `--commit` para aplicar.

Uso:
    python manage.py delete_pages --slugs aprender tipos soc           # dry-run
    python manage.py delete_pages --slugs aprender tipos soc --commit  # aplica

Em produção, rode localmente apontando DATABASE_URL ao Render.
"""
from django.core.management.base import BaseCommand
from pages.models import Page


class Command(BaseCommand):
    help = 'Remove páginas (linhas Page) do CMS por slug. Dry-run por padrão; use --commit.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--slugs', nargs='+', required=True,
            help='Slugs a remover (separados por espaço).',
        )
        parser.add_argument(
            '--commit', action='store_true',
            help='Aplica a remoção. Sem esta flag, é dry-run (nada é apagado).',
        )

    def handle(self, *args, **options):
        slugs  = options['slugs']
        commit = options['commit']

        qs      = Page.objects.filter(slug__in=slugs)
        found   = sorted(qs.values_list('slug', flat=True))
        missing = sorted(s for s in slugs if s not in found)

        if missing:
            self.stdout.write(self.style.WARNING(
                f'  Sem linha Page (ignorados): {", ".join(missing)}'
            ))

        if not found:
            self.stdout.write(self.style.WARNING('Nenhuma página a remover.'))
            return

        for s in found:
            self.stdout.write(f'  {"− apagaria" if not commit else "✗ apagada"}: {s}')

        if not commit:
            self.stdout.write(self.style.WARNING(
                f'\n[DRY-RUN] {len(found)} página(s) seriam removidas. '
                f'Rode com --commit para aplicar.'
            ))
        else:
            count, _ = qs.delete()
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ {len(found)} página(s) removida(s) do banco.'
            ))
