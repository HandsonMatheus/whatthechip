"""
collect_preduo_bulk.py — Stage 4: coleta Micron em volume via Preduo
====================================================================
Wrapper sobre scrape_preduo.py focado exclusivamente em chips Micron.

Reutiliza toda a infraestrutura do scrape_preduo.py (URLs corretas,
parsing, Playwright fallback, HTTP session) — scrape_preduo.py é a
fonte da verdade para os URLs do Preduo.

Diferenças vs. `scrape_preduo --brand Micron`:
  • Rastreia progresso por categoria em data/preduo_progress.json
    para retomar de onde parou sem re-raspar categorias concluídas.
  • Foca apenas nas categorias relevantes para Micron (filtra HBM, DDR,
    GDDR etc. que Micron não faz).
  • Alimenta data/datasheet_urls.txt para o Stage 2 (pdfplumber).
  • Relatório de cobertura por tipo no final.

Uso:
    python manage.py collect_preduo_bulk
    python manage.py collect_preduo_bulk --dry-run
    python manage.py collect_preduo_bulk --resume
    python manage.py collect_preduo_bulk --reset-progress
    python manage.py collect_preduo_bulk --max-pages 50 --delay 2.5
    python manage.py collect_preduo_bulk --overwrite
    python manage.py collect_preduo_bulk --type eMCP --type LPDDR4
    python manage.py collect_preduo_bulk --no-playwright
    python manage.py collect_preduo_bulk --show-browser
"""

import json
import logging
import re
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# ── Importa infraestrutura do scrape_preduo (fonte da verdade) ───────────────
from chips.management.commands.scrape_preduo import (
    PREDUO_CHIP_TYPES,
    BRAND_CODE_MAP,
    _infer_brand,
    _make_session,
    _scrape_preduo_list,
    _pw_close,
)

import atexit
atexit.register(_pw_close)

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

BASE_DIR      = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR      = BASE_DIR / "data"
PROGRESS_FILE = DATA_DIR / "preduo_progress.json"
URL_QUEUE     = DATA_DIR / "datasheet_urls.txt"
DATA_DIR.mkdir(exist_ok=True)

# Subconjunto de PREDUO_CHIP_TYPES relevante para Micron.
# Micron fabrica: eMCP, uMCP, eMMC, UFS, LPDDR2-5(X/T), NAND.
# Micron NÃO fabrica: DDR3/4/5, GDDR, HBM, NOR (comercialmente relevante).
MICRON_RELEVANT_KEYS = {
    "eMCP", "uMCP", "eMMC", "UFS",
    "LPDDR5T", "LPDDR5X", "LPDDR5", "LPDDR4X", "LPDDR4", "LPDDR3", "LPDDR2",
    "NORFLASH",  # Micron tem NOR flash (ex: MT25Q*)
}

# Filtrado de PREDUO_CHIP_TYPES — mantém a ordem original
MICRON_CHIP_TYPES = [
    t for t in PREDUO_CHIP_TYPES if t[0] in MICRON_RELEVANT_KEYS
]

ALL_KEYS = [k for k, _, _, _ in MICRON_CHIP_TYPES]


# ── Gestão de progresso ───────────────────────────────────────────────────────

def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_progress(progress: dict):
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


# ── Fila de datasheets para Stage 2 ──────────────────────────────────────────

def _queue_datasheet_urls(urls: list[str]):
    """Adiciona URLs de datasheet PDF à fila do Stage 2."""
    existing: set[str] = set()
    if URL_QUEUE.exists():
        for line in URL_QUEUE.read_text().splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                existing.add(s)

    new_urls = [u for u in urls if u not in existing and u.lower().endswith(".pdf")]
    if new_urls:
        with URL_QUEUE.open("a") as f:
            f.write(f"\n# Adicionado por collect_preduo_bulk ({len(new_urls)} URLs)\n")
            f.write("\n".join(new_urls) + "\n")
        logger.info("Adicionadas %d URLs de datasheet à fila.", len(new_urls))
    return len(new_urls)


# ── Persistência ──────────────────────────────────────────────────────────────

def _save_to_db(
    seen_pns: dict[str, tuple[str, str, str]],
    dry: bool,
    overwrite: bool,
    log_fn=print,
) -> dict[str, int]:
    from chips.models import Brand, KnownPart, Source

    CONFIDENCE_ORDER = {
        "confirmed": 0, "manual": 1, "distributor": 2,
        "estimated": 3,
    }
    MY_CONFIDENCE      = "distributor"
    MY_CONFIDENCE_RANK = CONFIDENCE_ORDER[MY_CONFIDENCE]

    counts = {"created": 0, "updated": 0, "skipped": 0}

    if dry:
        micron_brand = None
        preduo_src   = None
    else:
        micron_brand, _ = Brand.objects.get_or_create(
            name="Micron", defaults={"code": "MIC"}
        )
        preduo_src, _ = Source.objects.get_or_create(
            name="Preduo",
            defaults={"src_type": "scraper", "url": "https://www.preduo.com"},
        )

    for pn, (chip_type, subtype, src_url) in seen_pns.items():
        if dry:
            exists = KnownPart.objects.filter(part_number=pn).exists()
            action = "UPDATE" if (exists and overwrite) else ("SKIP" if exists else "CREATE")
            if action != "SKIP":
                log_fn(
                    f"  [{action:6s}] {pn:40s}  {chip_type}"
                    + (f" {subtype}" if subtype else "")
                )
            counts["created" if action == "CREATE" else
                   "updated" if action == "UPDATE" else "skipped"] += 1
            continue

        try:
            existing = KnownPart.objects.filter(part_number=pn).first()

            if existing is None:
                KnownPart.objects.create(
                    brand=micron_brand,
                    part_number=pn,
                    chip_type=chip_type,
                    subtype=subtype,
                    confidence=MY_CONFIDENCE,
                    source=preduo_src,
                    source_url=src_url,
                )
                counts["created"] += 1

            elif overwrite:
                existing_rank = CONFIDENCE_ORDER.get(existing.confidence, 99)
                if existing_rank >= MY_CONFIDENCE_RANK:
                    upd: list[str] = []
                    if not existing.chip_type and chip_type:
                        existing.chip_type = chip_type; upd.append("chip_type")
                    if not existing.subtype and subtype:
                        existing.subtype = subtype; upd.append("subtype")
                    if existing.source is None:
                        existing.source = preduo_src; upd.append("source")
                    if not existing.source_url and src_url:
                        existing.source_url = src_url; upd.append("source_url")
                    if upd:
                        upd.append("last_updated")
                        existing.save(update_fields=upd)
                        counts["updated"] += 1
                    else:
                        counts["skipped"] += 1
                else:
                    counts["skipped"] += 1
            else:
                counts["skipped"] += 1

        except Exception as e:
            logger.warning("Erro ao salvar PN %s: %s", pn, e)

    return counts


# ── Command ───────────────────────────────────────────────────────────────────

class _DryRunAbort(Exception):
    pass


class Command(BaseCommand):
    help = (
        "Stage 4 — Coleta chips Micron em volume via Preduo, "
        "varrendo todas as categorias relevantes com filtragem por prefixo de marca."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Mostra o que seria feito sem alterar o banco.",
        )
        parser.add_argument(
            "--overwrite", action="store_true",
            help="Atualiza KnownParts existentes com confidence >= distributor.",
        )
        parser.add_argument(
            "--max-pages", type=int, default=50, metavar="N",
            help="Máximo de páginas por categoria (padrão: 50).",
        )
        parser.add_argument(
            "--delay", type=float, default=2.5, metavar="SEG",
            help="Pausa em segundos entre requests (padrão: 2.5).",
        )
        parser.add_argument(
            "--resume", action="store_true",
            help="Retoma progresso anterior (data/preduo_progress.json).",
        )
        parser.add_argument(
            "--reset-progress", action="store_true",
            help="Ignora progresso anterior e recomeça do zero.",
        )
        parser.add_argument(
            "--no-playwright", action="store_true",
            help="Desabilita fallback Playwright para Cloudflare JS challenge.",
        )
        parser.add_argument(
            "--show-browser", action="store_true",
            help="Playwright não-headless (janela visível). Melhor bypass CF.",
        )
        parser.add_argument(
            "--type",
            action="append",
            dest="types",
            choices=ALL_KEYS,
            metavar="TIPO",
            help=(
                f"Restringe a tipos específicos. Pode repetir. "
                f"Disponíveis: {', '.join(ALL_KEYS)}"
            ),
        )

    def handle(self, *args, **options):
        dry            = options["dry_run"]
        overwrite      = options["overwrite"]
        max_pages      = options["max_pages"]
        delay          = options["delay"]
        resume         = options["resume"]
        reset          = options["reset_progress"]
        use_playwright = not options["no_playwright"]
        headless       = not options.get("show_browser", False)
        selected_types = options.get("types")

        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        # Verifica dependências
        try:
            from bs4 import BeautifulSoup  # noqa: F401
        except ImportError:
            raise CommandError("beautifulsoup4 não instalado: pip install beautifulsoup4 lxml")

        playwright_ok = False
        if use_playwright:
            try:
                from playwright.sync_api import sync_playwright  # noqa: F401
                playwright_ok = True
            except ImportError:
                self.stdout.write(self.style.WARNING(
                    "  ℹ  Playwright não instalado — sem fallback CF.\n"
                    "     pip install playwright && playwright install chromium\n"
                ))

        session = _make_session()
        if not getattr(session, "_is_cffi", False):
            self.stdout.write(self.style.WARNING(
                "  ℹ  curl_cffi não instalado — usando requests padrão.\n"
                "     pip install curl_cffi\n"
            ))

        # Carrega / reseta progresso
        if reset:
            progress: dict = {}
            if PROGRESS_FILE.exists():
                PROGRESS_FILE.unlink()
                self.stdout.write("  ♻  Progresso anterior removido.\n")
        elif resume:
            progress = _load_progress()
            if progress:
                done = sum(1 for v in progress.values() if v.get("done"))
                self.stdout.write(
                    f"  ♻  Retomando progresso ({done} categorias já concluídas).\n"
                )
        else:
            progress = {}

        # Filtra tipos de chip
        chip_types = MICRON_CHIP_TYPES
        if selected_types:
            chip_types = [t for t in MICRON_CHIP_TYPES if t[0] in selected_types]

        self.stdout.write(
            f"Categorias: {', '.join(k for k, _, _, _ in chip_types)}\n"
            f"Max páginas/categoria: {max_pages}  |  Delay: {delay}s  |  "
            f"Playwright: {'sim' if playwright_ok else 'não'}\n"
        )

        # ── Coleta ────────────────────────────────────────────────────────────
        # seen_pns: pn → (chip_type, subtype, source_url)
        # Primeira ocorrência de cada PN ganha.
        seen_pns: dict[str, tuple[str, str, str]] = {}
        category_stats: dict[str, int] = {}

        for key, url_path, chip_type, subtype in chip_types:
            # Pula categorias já concluídas (modo --resume)
            if progress.get(key, {}).get("done"):
                prev_count = progress[key].get("pn_count", 0)
                self.stdout.write(f"\n▶  {key}: (concluído anteriormente — {prev_count} PNs)")
                continue

            self.stdout.write(f"\n▶  Raspando {key} ({url_path}) ...")
            self.stdout.flush()

            raw_results = _scrape_preduo_list(
                key=key,
                url_path=url_path,
                session=session,
                max_pages=max_pages,
                delay=delay,
                use_playwright=playwright_ok and use_playwright,
                headless=headless,
                log_fn=self.stdout.write,
            )

            # Filtra apenas Micron
            micron_count = 0
            for pn, src_url in raw_results:
                if _infer_brand(pn) != "Micron":
                    continue
                if pn not in seen_pns:
                    seen_pns[pn] = (chip_type, subtype, src_url)
                    micron_count += 1

            category_stats[key] = micron_count
            self.stdout.write(
                f"  {key}: {micron_count} PNs Micron únicos "
                f"(total na página: {len(raw_results)})"
            )

            # Salva progresso
            progress[key] = {"done": True, "pn_count": micron_count}
            if not dry:
                _save_progress(progress)

            time.sleep(delay)

        total_unique = len(seen_pns)
        self.stdout.write(f"\n\nTotal PNs Micron únicos coletados: {total_unique}")

        # Relatório por categoria
        if category_stats:
            self.stdout.write("\nCobertura por categoria:")
            for key, count in category_stats.items():
                self.stdout.write(f"  {key:<12} {count:>5} PNs Micron")

        if total_unique == 0:
            self.stdout.write(self.style.WARNING(
                "\n⚠  Nenhum PN coletado. Causas prováveis:\n"
                "   1. Cloudflare JS challenge → instale Playwright ou use --show-browser\n"
                "   2. Estrutura do site mudou → verifique manualmente\n"
                "   3. curl_cffi não instalado → pip install curl_cffi\n"
            ))
            return

        # ── Salva no banco ────────────────────────────────────────────────────
        try:
            with transaction.atomic():
                counts = _save_to_db(
                    seen_pns=seen_pns,
                    dry=dry,
                    overwrite=overwrite,
                    log_fn=self.stdout.write,
                )
                if dry:
                    raise _DryRunAbort()
        except _DryRunAbort:
            self.stdout.write(self.style.WARNING(
                "\nDry run concluído — nenhuma alteração salva."
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f"\n✅  Concluído.\n"
            f"   Novos KnownParts criados:     {counts['created']}\n"
            f"   KnownParts atualizados:       {counts['updated']}\n"
            f"   Pulados (já existiam):        {counts['skipped']}\n"
        ))

        # Invalida cache
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            self.stdout.write("   🗑  Cache do engine invalidado.")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))
