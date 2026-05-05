"""
Management command: link_doc_pages
===================================
Vincula automaticamente cada ChipFamily à sua página de documentação
no WhatTheChip, baseado no nome da marca.

Uso:
    python manage.py link_doc_pages
    python manage.py link_doc_pages --dry-run   # mostra o que faria, sem salvar
"""

from django.core.management.base import BaseCommand
from chips.models import ChipFamily
from pages.models import Page


# Mapeamento: nome da marca (case-insensitive) → slug da página de documentação
BRAND_TO_SLUG = {
    "samsung":          "fab-samsung",
    "sk hynix":         "fab-hynix",
    "hynix":            "fab-hynix",
    "micron":           "fab-micron",
    "elpida":           "fab-elpida",
    "toshiba":          "fab-toshiba",
    "kioxia":           "fab-toshiba",
    "toshiba / kioxia": "fab-toshiba",
    "sandisk":          "fab-sandisk",
    "sandisk / wd":     "fab-sandisk",
    "wd":               "fab-sandisk",
    "nanya":            "fab-nanya",
    "kingston":         "fab-kingston",
    "rayson":           "fab-rayson",
    "issi":             "fab-issi",
    "gigadevice":       "fab-gigadevice",
}


class Command(BaseCommand):
    help = "Vincula ChipFamilies às páginas de documentação pelo nome da marca"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", default=False,
            help="Mostra o que seria feito sem salvar nada"
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠ DRY RUN — nenhum dado será salvo\n"))

        # Pré-carrega as páginas existentes no banco
        pages_by_slug = {p.slug: p for p in Page.objects.all()}

        families = ChipFamily.objects.select_related("brand").order_by("brand__name", "prefix")

        linked = skipped_no_page = skipped_already = not_mapped = 0

        for fam in families:
            brand_key = fam.brand.name.strip().lower()
            slug = BRAND_TO_SLUG.get(brand_key)

            if not slug:
                self.stdout.write(
                    self.style.WARNING(f"  ⚠ Sem mapeamento para marca '{fam.brand.name}' (família {fam.prefix})")
                )
                not_mapped += 1
                continue

            page = pages_by_slug.get(slug)
            if not page:
                self.stdout.write(
                    self.style.WARNING(f"  ⚠ Página '{slug}' não existe no banco (família {fam.prefix})")
                )
                skipped_no_page += 1
                continue

            if fam.doc_page_id == page.id:
                skipped_already += 1
                continue

            self.stdout.write(
                f"  {fam.prefix:12s} ({fam.brand.name}) → {slug}"
            )

            if not dry_run:
                fam.doc_page = page
                fam.save(update_fields=["doc_page"])

            linked += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{'Seriam vinculados' if dry_run else 'Vinculados'}: {linked}"
        ))
        if skipped_already:
            self.stdout.write(f"Já estavam corretos: {skipped_already}")
        if skipped_no_page:
            self.stdout.write(self.style.WARNING(f"Página não encontrada: {skipped_no_page}"))
        if not_mapped:
            self.stdout.write(self.style.WARNING(f"Marca sem mapeamento: {not_mapped}"))

        if not dry_run and linked > 0:
            self.stdout.write(self.style.SUCCESS(
                "\n✅ Pronto! Agora os resultados de busca incluem link para a documentação."
            ))
