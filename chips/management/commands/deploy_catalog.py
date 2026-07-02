"""
deploy_catalog.py
=================
Transforma a "cerimônia de deploy de catálogo" (vários comandos na mão, em ordem,
com risco de esquecer um) em **UM** comando seguro.

Encadeia, na ordem canônica (CLAUDE.md §5), os passos **rodáveis no Render** (código
puro ou dados versionados), cada um idempotente e com seu `atomic()`:

    load_brands (TODAS as marcas — autodescobertas de chips/knowledge/*.yaml,
    Samsung 1ª pelos mapas globais)  →  link_doc_pages  →  sync_index_page  →
    import_samsung_psg (--all)

e, no fim, **sobe o `catalog_version`**: o engine recarrega o cache sozinho em todos
os workers, **sem reiniciar o servidor** (regra de ouro #3).

⚠ **NÃO inclui `import_micron_catalog`**: depende dos `*_full-catalog.csv`, não
versionados (só no working tree local) → rode-o à parte, localmente.

Dry-run por padrão. `--commit` grava e, num terminal real, pede confirmação do
banco-alvo (SafeWriteCommand).

    python manage.py deploy_catalog              # dry-run (não grava)
    python manage.py deploy_catalog --commit     # grava tudo + sobe catalog_version
"""

import glob
import os

from django.conf import settings
from django.core.management import call_command

from core.safe_command import SafeWriteCommand

_KNOWLEDGE_DIR = os.path.join(settings.BASE_DIR, "chips", "knowledge")


def _discover_brands():
    """AUTODESCOBERTA: as marcas do deploy são TODOS os `chips/knowledge/*.yaml` —
    soltar um yaml novo já entra no deploy, sem editar este arquivo. **Samsung 1ª**:
    ela define os mapas GLOBAIS `DRAM_PC`/`DRAM_MOBILE` (brand=None) que as densidades
    das outras marcas referenciam."""
    nomes = sorted(
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(_KNOWLEDGE_DIR, "*.yaml"))
    )
    if "samsung" in nomes:
        nomes = ["samsung"] + [n for n in nomes if n != "samsung"]
    return nomes


# (comando, kwargs no --commit, kwargs no dry-run [ou None se o passo não tem dry-run]).
# Ordem canônica (CLAUDE.md §5). Só comandos rodáveis no Render. As marcas são
# autodescobertas dos yamls (load_brands substituiu os populate_* aposentados).
_STEPS = [
    ("load_brands", {"brand": b, "commit": True}, {"brand": b, "dry_run": True})
    for b in _discover_brands()
] + [
    ("link_doc_pages",     {},            {"dry_run": True}),
    ("sync_index_page",    {},            {"dry_run": True}),
    ("import_samsung_psg", {"all": True}, {"all": True, "dry_run": True}),  # data/psg/*.csv versionados
]


class Command(SafeWriteCommand):
    help = ("Encadeia a montagem do catálogo (populate_*/import/fix) num comando, "
            "sobe o catalog_version no fim. Dry-run por padrão.")

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true",
                            help="Grava de verdade (sem isto é dry-run).")

    def handle(self, *args, **opts):
        commit = bool(opts.get("commit"))
        modo = "COMMIT (gravando)" if commit else "DRY-RUN (nada é gravado)"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== deploy_catalog — {modo} === {len(_STEPS)} passos\n"))

        executados, pulados = 0, 0
        for i, (name, commit_kwargs, dry_kwargs) in enumerate(_STEPS, 1):
            if commit:
                self.stdout.write(self.style.HTTP_INFO(f"[{i}/{len(_STEPS)}] {name} {commit_kwargs or ''}"))
                call_command(name, **commit_kwargs)
                executados += 1
            elif dry_kwargs is not None:
                self.stdout.write(self.style.HTTP_INFO(f"[{i}/{len(_STEPS)}] {name} (dry-run)"))
                call_command(name, **dry_kwargs)
                executados += 1
            else:
                self.stdout.write(self.style.WARNING(
                    f"[{i}/{len(_STEPS)}] {name}: não tem --dry-run → pulado (roda no --commit)"))
                pulados += 1

        if commit:
            from chips.models import CatalogVersion
            nova = CatalogVersion.bump()
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ catálogo montado ({executados} passos). catalog_version → {nova}. "
                f"O engine recarrega o cache sozinho — NÃO precisa reiniciar o servidor."))
        else:
            self.stdout.write(self.style.WARNING(
                f"\nDRY-RUN: {executados} passo(s) simulado(s), {pulados} pulado(s) "
                f"(sem --dry-run). Use --commit para gravar."))
