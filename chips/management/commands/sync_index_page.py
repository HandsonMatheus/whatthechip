"""
Management command: sync_index_page
=====================================
Lê o arquivo _content/index.html e atualiza o conteúdo da Page
com slug='index' no banco de dados.

Necessário porque o Django serve o conteúdo das Pages a partir do banco,
não diretamente dos arquivos _content/.

Uso:
    python manage.py sync_index_page
    python manage.py sync_index_page --dry-run
"""

from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from pages.models import Page


class Command(BaseCommand):
    help = "Sincroniza _content/index.html para a Page slug='index' no banco"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", default=False,
            help="Mostra o conteúdo que seria salvo sem gravar"
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        content_path = Path(__file__).resolve().parents[3] / "_content" / "index.html"

        if not content_path.exists():
            raise CommandError(f"Arquivo não encontrado: {content_path}")

        new_content = content_path.read_text(encoding="utf-8")

        try:
            page = Page.objects.get(slug="index")
        except Page.DoesNotExist:
            raise CommandError(
                "Page com slug='index' não existe no banco. "
                "Crie-a primeiro pelo admin em /admin/pages/page/."
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — conteúdo NÃO será salvo"))
            self.stdout.write(f"  Arquivo: {content_path}")
            self.stdout.write(f"  Tamanho atual no banco: {len(page.content)} chars")
            self.stdout.write(f"  Tamanho novo:           {len(new_content)} chars")
            return

        page.content = new_content
        page.save(update_fields=["content"])

        self.stdout.write(self.style.SUCCESS(
            f"✅ Page 'index' atualizada — {len(new_content)} chars gravados."
        ))
        # (§10.7.5 do PLANO_MULTITENANT, corrigido 2026-08-15: a copy antiga
        # afirmava que a home usa a API /chips/search/ — ela é plataforma-only
        # desde o fim da busca pública.)
        self.stdout.write(
            "Lembrete: a consulta de PN é PLATAFORMA-ONLY — a home não usa "
            "mais a API /chips/search/ (fim da busca pública, 2026-08-05)."
        )
