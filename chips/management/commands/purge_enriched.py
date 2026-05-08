"""
purge_enriched.py
==================
Apaga todos os registros KnownPart enriquecidos automaticamente
(por IA ou scraping de distribuidores), mantendo apenas os verificados
manualmente (confidence='manual') e os corrigidos (status='fixed').

O sistema vai re-enriquecer sob demanda quando usuários buscarem os PNs.
A gramática cobre a maioria dos chips Samsung diretamente.

Uso:
    python manage.py purge_enriched              # mostra contagem e apaga
    python manage.py purge_enriched --dry-run    # só mostra, não apaga
    python manage.py purge_enriched --keep confirmed  # mantém 'confirmed' também
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Apaga KnownParts enriquecidos automaticamente, mantendo apenas os manuais."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Exibe o que seria apagado sem apagar nada.",
        )
        parser.add_argument(
            "--keep",
            nargs="*",
            default=[],
            metavar="CONFIDENCE",
            help="Confidence levels extras para manter além de 'manual'. Ex: --keep confirmed",
        )

    def handle(self, *args, **options):
        from chips.models import KnownPart

        dry = options["dry_run"]
        extra_keep = options["keep"]

        # Sempre mantém: manual (humano validou) e status=fixed (corrigido manualmente)
        keep_confidence = {"manual"} | set(extra_keep)

        # Registros a apagar: enriquecidos automaticamente, não manuais, não fixed
        to_delete = KnownPart.objects.exclude(
            confidence__in=keep_confidence
        ).exclude(
            status="fixed"
        )

        # Breakdown por confidence para o usuário entender o que vai sumir
        from django.db.models import Count
        breakdown = (
            to_delete
            .values("confidence")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

        total = to_delete.count()
        kept  = KnownPart.objects.filter(
            confidence__in=keep_confidence
        ).count() + KnownPart.objects.filter(status="fixed").exclude(
            confidence__in=keep_confidence
        ).count()

        self.stdout.write("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.stdout.write(f"  Registros que SERÃO MANTIDOS : {kept}")
        self.stdout.write(f"  Registros que SERÃO APAGADOS : {total}")
        self.stdout.write("  Breakdown dos apagados:")
        for row in breakdown:
            self.stdout.write(f"    {row['confidence']:20s} → {row['total']}")
        self.stdout.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nada a apagar."))
            return

        if dry:
            self.stdout.write(self.style.WARNING("DRY RUN — nenhum registro foi apagado."))
            return

        # Confirmação rápida: sem prompt interativo, o usuário já decidiu ao rodar
        deleted_count, _ = to_delete.delete()

        self.stdout.write(self.style.SUCCESS(f"✅  {deleted_count} registros apagados."))
        self.stdout.write(
            "   O sistema vai re-enriquecer sob demanda quando os PNs forem buscados.\n"
        )
