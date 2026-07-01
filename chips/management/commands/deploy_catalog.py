"""
deploy_catalog.py
=================
**PASSO 3** do `docs/PLANO_IMPLEMENTACAO_ESCALABILIDADE.md`: transforma a
"cerimônia de deploy de catálogo" (13+ comandos rodados na mão, em ordem, com o
risco de esquecer um ou reiniciar o servidor) em **UM** comando seguro.

Encadeia, na ordem canônica (CLAUDE.md §5), os comandos de catálogo que são
**rodáveis no Render** (código puro ou com dados versionados), cada um já
idempotente e com seu próprio `atomic()`:

    load_brands (todas as 11 marcas)  →  link_doc_pages  →
    sync_index_page  →  import_samsung_psg (--all)  →  fix_known_parts

e, no fim, **sobe o `catalog_version`** — o que **substitui o antigo "reinicie o
servidor após populate"** (regra de ouro #3): o engine recarrega o cache sozinho
em todos os workers (passo 1B).

⚠ **NÃO inclui `import_micron_catalog`**: ele depende dos `*_full-catalog.csv`,
que **não** estão versionados (só existem no working tree local) → quebraria no
Render. Rode-o à parte, localmente, quando atualizar o catálogo Micron.

Dry-run por padrão (cada sub-passo mostra o que faria). `--commit` grava e, num
terminal real, pede a confirmação do banco-alvo (SafeWriteCommand, passo 1C).

    python manage.py deploy_catalog              # dry-run (não grava)
    python manage.py deploy_catalog --commit     # grava tudo + sobe catalog_version

Quando o passo 4 migrar o conhecimento para YAML, troca-se a lista `_STEPS` pelos
`load_brands` correspondentes — o resto do comando (banner, ordem, bump) não muda.
"""

from django.core.management import call_command

from core.safe_command import SafeWriteCommand

# (nome_do_comando, kwargs_no_commit, suporta_--dry-run)
# (comando, kwargs no --commit, kwargs no dry-run [ou None se o passo não tem dry-run])
# A ordem é a canônica do CLAUDE.md §5. Só comandos rodáveis no Render.
_STEPS = [
    # Marcas migradas p/ YAML (passo 4): load_brands no lugar dos populate_* aposentados.
    # (populate_toshiba criava Toshiba E Kioxia → 2 load_brands.) Samsung 1ª: define os mapas
    # GLOBAIS DRAM_PC/DRAM_MOBILE (brand=None) que a densidade dela usa.
    ("load_brands", {"brand": "samsung", "commit": True}, {"brand": "samsung", "dry_run": True}),
    ("load_brands", {"brand": "piecemakers", "commit": True}, {"brand": "piecemakers", "dry_run": True}),
    ("load_brands", {"brand": "gigadevice", "commit": True}, {"brand": "gigadevice", "dry_run": True}),
    ("load_brands", {"brand": "rayson", "commit": True}, {"brand": "rayson", "dry_run": True}),
    ("load_brands", {"brand": "kingston", "commit": True}, {"brand": "kingston", "dry_run": True}),
    ("load_brands", {"brand": "sandisk", "commit": True}, {"brand": "sandisk", "dry_run": True}),
    ("load_brands", {"brand": "micron", "commit": True}, {"brand": "micron", "dry_run": True}),
    ("load_brands", {"brand": "toshiba", "commit": True}, {"brand": "toshiba", "dry_run": True}),
    ("load_brands", {"brand": "kioxia", "commit": True}, {"brand": "kioxia", "dry_run": True}),
    ("load_brands", {"brand": "hynix", "commit": True}, {"brand": "hynix", "dry_run": True}),
    ("load_brands", {"brand": "nanya", "commit": True}, {"brand": "nanya", "dry_run": True}),
    # add_chip_families APOSENTADO (2026-07-01): suas 39 famílias agora vivem nos yamls das marcas
    # (Nanya→nanya.yaml, Kingston KVR/KF/ACR/EMCP→kingston.yaml, o resto já estava). Eliminou o
    # brand duplicado 'KIOXIA' (maiúsculo) que ele criava.
    ("link_doc_pages",       {},                  {"dry_run": True}),
    ("sync_index_page",      {},                  {"dry_run": True}),
    ("import_samsung_psg",   {"all": True}, {"all": True, "dry_run": True}),  # data/psg/*.csv versionados
    ("fix_known_parts",      {},                  {"dry_run": True}),
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
