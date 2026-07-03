"""
guard_catalog.py — TRIPWIRE contra perda silenciosa do catálogo vivo.

O banco de produção é a FONTE DA VERDADE do catálogo de known_parts, que só cresce
(regra de ouro §2). Este comando guarda um **high-water mark** (o maior nº de
known_parts já visto, em `CatalogVersion.max_known_parts`) e:

  • se a contagem atual CRESCEU  → atualiza o high-water (silencioso, é o esperado);
  • se a contagem atual DESPENCOU → **falha com exit code 1** e um alarme berrante.

"Despencou" = caiu abaixo de `high_water × (1 - tolerância)` (default 10%). Assim,
se prod cair de 6.571 pra 886 de novo (como no incidente de jul/2026), o alarme
dispara SOZINHO — não depende de ninguém perceber. Rode DEPOIS de todo deploy e/ou
agende diário. É read-only exceto pelo bump do high-water (nunca apaga nada).

Uso:
    python manage.py guard_catalog                 # checa; atualiza o high-water se cresceu
    python manage.py guard_catalog --tolerance 5   # mais sensível (falha se cair >5%)
    python manage.py guard_catalog --reset         # re-baseia o high-water na contagem atual
                                                    #   (use SÓ após uma queda legítima e revisada)
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Tripwire: falha se o nº de known_parts despencar vs. o high-water mark."

    def add_arguments(self, parser):
        parser.add_argument("--tolerance", type=float, default=10.0,
                            help="Queda máxima tolerada em %% do high-water (default: 10).")
        parser.add_argument("--reset", action="store_true",
                            help="Re-baseia o high-water na contagem atual (após queda legítima).")

    def handle(self, *args, **opts):
        from chips.models import KnownPart, CatalogVersion

        atual = KnownPart.objects.count()
        cv = CatalogVersion.current_row()
        hw = cv.max_known_parts

        if opts["reset"]:
            cv.max_known_parts = atual
            cv.save(update_fields=["max_known_parts"])
            self.stdout.write(self.style.WARNING(
                f"↺ high-water re-baseado: {hw} → {atual} known_parts."))
            return

        # 1ª vez (high-water zerado) ou crescimento → só registra e segue.
        if atual >= hw:
            if atual > hw:
                cv.max_known_parts = atual
                cv.save(update_fields=["max_known_parts"])
                self.stdout.write(self.style.SUCCESS(
                    f"✓ catálogo OK e cresceu: {hw} → {atual} known_parts (high-water atualizado)."))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"✓ catálogo OK: {atual} known_parts (high-water {hw})."))
            return

        # Caiu. Passou da tolerância?
        piso = hw * (1 - opts["tolerance"] / 100.0)
        queda_pct = (hw - atual) / hw * 100.0 if hw else 0.0
        if atual < piso:
            self.stderr.write(self.style.ERROR(
                "\n🚨🚨🚨 ALARME DE CATÁLOGO 🚨🚨🚨\n"
                f"  known_parts DESPENCOU: {hw} (high-water) → {atual}  "
                f"(−{queda_pct:.1f}%, tolerância {opts['tolerance']:.0f}%).\n"
                "  Isto é a assinatura de uma PERDA SILENCIOSA (deploy que não levou o\n"
                "  banco vivo adiante, purga, ou swap de banco). NÃO ignore.\n"
                "  → Investigue AGORA. Recupere via backup (Export/PITR) + restore_known_parts.\n"
                "  → Só depois de recuperar/entender, use --reset pra re-baixar o high-water.\n"))
            raise SystemExit(1)

        self.stdout.write(self.style.WARNING(
            f"⚠ catálogo caiu de leve: {hw} → {atual} (−{queda_pct:.1f}%, dentro dos "
            f"{opts['tolerance']:.0f}%). High-water mantido em {hw}."))
