"""
enrich_micron_fbga.py — Enriquece KnownParts Micron com FBGA codes oficiais
===========================================================================
Para cada KnownPart Micron com confidence='distributor':
  1. Consulta o FBGA Decoder oficial da Micron (API REST descoberta via DevTools)
  2. Para cada resultado (fbga_code + full_part_number):
       - Cria novo KnownPart com PN completo (com sufixo) e fbga_code preenchido
       - confidence='confirmed', source=Micron FBGA API
  3. Remove o registro base original (substituído pelos específicos com FBGA)

URL da API (busca por PN base, retorna todos os FBGAs):
  https://www.micron.com/content/micron/us/en/sales-support/design-tools/
  fbga-parts-decoder/_jcr_content.products.json/getpartbyfbgacode/-/-/-/en_US/-/{PN}/-

Motivação do modelo de dados:
  O FBGA gravado fisicamente no chip é o identificador definitivo.
  Um PN base (ex: MT29PZZZ8D5BKFTF) pode ter 3+ variantes de silício,
  cada uma com FBGA distinto. Para reciclagem, precisamos de 1 registro por FBGA.

Uso:
    python manage.py enrich_micron_fbga
    python manage.py enrich_micron_fbga --dry-run
    python manage.py enrich_micron_fbga --limit 10
    python manage.py enrich_micron_fbga --delay 1.5
    python manage.py enrich_micron_fbga --keep-base
"""

import re
import time
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)

# ── API endpoint descoberto via DevTools (Network tab) ────────────────────────
#
# Formato:  /getpartbyfbgacode/-/-/-/en_US/-/{PART_NUMBER}/{FBGA_CODE}
# Wildcard: usar "-" para campos não filtrados
# Busca por PN:   .../en_US/-/{PN}/-
# Busca por FBGA: .../en_US/-/-/{FBGA}
#
MICRON_FBGA_API = (
    "https://www.micron.com/content/micron/us/en/sales-support/design-tools/"
    "fbga-parts-decoder/_jcr_content.products.json/"
    "getpartbyfbgacode/-/-/-/en_US/-/{pn}/-"
)

MICRON_FBGA_SOURCE_URL = (
    "https://www.micron.com/sales-support/design-tools/fbga-parts-decoder"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.micron.com/sales-support/design-tools/fbga-parts-decoder",
}

# FBGA code: sempre 5 chars alfanuméricos (ex: JWB11, JY1O6)
_FBGA_RE = re.compile(r"^[A-Z0-9]{5}$")


# ── HTTP session ──────────────────────────────────────────────────────────────

def _make_session():
    """Prefere curl_cffi (TLS Chrome) para evitar bloqueios Cloudflare."""
    try:
        from curl_cffi import requests as cffi_requests
        s = cffi_requests.Session(impersonate="chrome110")
        s._is_cffi = True
        return s
    except ImportError:
        import requests as std_requests
        s = std_requests.Session()
        s._is_cffi = False
        return s


# ── Consulta API ──────────────────────────────────────────────────────────────

def _query_fbga_api(pn: str, session, retries: int = 3, verbose: bool = False) -> list[dict]:
    """
    Consulta a API FBGA da Micron para um PN base.

    Retorna lista de dicts: [{"fbga_code": "JWB11", "part_number": "MT29...18 W.95L"}, ...]
    Retorna [] se PN não encontrado ou erro.
    """
    url = MICRON_FBGA_API.format(pn=pn)

    if verbose:
        print(f"\n  [DEBUG] URL: {url}")

    for attempt in range(retries):
        try:
            r = session.get(url, headers=_HEADERS, timeout=25)

            if verbose:
                print(f"  [DEBUG] Status: {r.status_code}")
                print(f"  [DEBUG] Content-Type: {r.headers.get('content-type', 'N/A')}")
                print(f"  [DEBUG] Body (500 chars): {r.text[:500]!r}")

            if r.status_code == 200:
                try:
                    data = r.json()
                except Exception:
                    logger.warning(
                        "Resposta não-JSON para PN %s: %s", pn, r.text[:300]
                    )
                    return []
                return _parse_response(pn, data)

            elif r.status_code == 404:
                return []  # PN não existe no catálogo Micron

            elif r.status_code in (429, 503):
                wait = 5 * (attempt + 1)
                logger.warning(
                    "HTTP %s (rate limit?) para PN %s — aguardando %ds",
                    r.status_code, pn, wait,
                )
                time.sleep(wait)
                continue

            else:
                logger.warning(
                    "HTTP %s para PN %s (tentativa %d/%d)",
                    r.status_code, pn, attempt + 1, retries,
                )

        except Exception as e:
            logger.warning(
                "Erro na tentativa %d/%d para PN %s: %s",
                attempt + 1, retries, pn, e,
            )
            if verbose:
                print(f"  [DEBUG] Exceção: {e}")

        time.sleep(1.5 * (attempt + 1))

    return []


def _parse_response(base_pn: str, data) -> list[dict]:
    """
    Parseia a resposta JSON da API Micron FBGA.

    Formato real confirmado (2026-05):
    {
      "date": "...",
      "response-code": "200",
      "details": [
        {
          "part-number":  "MT29PZZZ8D5BKFTF-18 W.95L",
          "part-key":     "mt29pzzz8d5bkftf-18-w.95l",
          "part-name":    "MLC EMMC/LPDDR2 72G VFBGA",
          "sub-category": "obsolete-emmc-based-mcp",
          "fbga-code":    "JWB11",
          "pageurl":      "/products/obsolete/..."
        },
        ...
      ]
    }
    """
    # Normaliza para lista de itens
    if isinstance(data, dict):
        items = (
            data.get("details")       # formato real da API Micron
            or data.get("results")    # fallback
            or data.get("data")
            or data.get("products")
            or data.get("items")
            or []
        )
    elif isinstance(data, list):
        items = data
    else:
        logger.warning("Formato de resposta inesperado para PN %s: %r", base_pn, type(data))
        return []

    results = []
    seen_fbgas: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        # Extrai FBGA code — API usa "fbga-code" (com hífen)
        fbga = (
            item.get("fbga-code")     # formato real
            or item.get("fbgaCode")   # camelCase (fallback)
            or item.get("fbga_code")
            or item.get("fbga")
            or item.get("FBGA")
            or ""
        ).strip().upper()

        # Extrai PN completo — API usa "part-number" (com hífen)
        full_pn = (
            item.get("part-number")        # formato real
            or item.get("partNumber")      # camelCase (fallback)
            or item.get("part_number")
            or item.get("pn")
            or item.get("PN")
            or ""
        ).strip()

        # URL da página do produto no site da Micron (opcional)
        page_url = item.get("pageurl", "").strip()
        if page_url and not page_url.startswith("http"):
            page_url = f"https://www.micron.com{page_url}"

        # Valida
        if not fbga or not full_pn:
            continue
        if not _FBGA_RE.match(fbga):
            logger.debug("FBGA inválido ignorado: %r (PN: %s)", fbga, base_pn)
            continue
        if fbga in seen_fbgas:
            continue

        seen_fbgas.add(fbga)
        results.append({
            "fbga_code":  fbga,
            "part_number": full_pn,
            "source_url": page_url or MICRON_FBGA_API.format(pn=base_pn),
        })

    return results


# ── Command ───────────────────────────────────────────────────────────────────

class _DryRunAbort(Exception):
    pass


class Command(BaseCommand):
    help = (
        "Enriquece KnownParts Micron (confidence=distributor) "
        "consultando a API FBGA oficial da Micron. "
        "Cria um KnownPart por FBGA encontrado (confidence=confirmed) "
        "e remove o registro base original."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria feito sem alterar o banco.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            metavar="N",
            help="Processa no máximo N registros base (0 = sem limite).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            metavar="SEG",
            help="Pausa em segundos entre requests à API (padrão: 1.0).",
        )
        parser.add_argument(
            "--keep-base",
            action="store_true",
            help=(
                "Mantém o registro base original após enriquecer (não deleta). "
                "Útil para inspecionar antes de limpar."
            ),
        )
        parser.add_argument(
            "--pn",
            dest="pn_filter",
            metavar="PART_NUMBER",
            help="Processa apenas este PN específico (para teste).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Mostra status HTTP e corpo da resposta (para debug).",
        )

    def handle(self, *args, **options):
        from chips.models import KnownPart, Source

        dry       = options["dry_run"]
        limit     = options["limit"]
        delay     = options["delay"]
        keep_base = options["keep_base"]
        pn_filter = options.get("pn_filter")
        verbose   = options.get("verbose", False)

        if dry:
            self.stdout.write(self.style.WARNING(
                "⚠  DRY RUN — nenhuma alteração será salva.\n"
            ))

        # ── Seleciona registros a processar ──────────────────────────────────
        qs = KnownPart.objects.filter(
            brand__name="Micron",
            confidence="distributor",
        ).filter(
            Q(fbga_code="") | Q(fbga_code__isnull=True)
        ).select_related("brand").order_by("part_number")

        if pn_filter:
            qs = qs.filter(part_number=pn_filter)

        total = qs.count()

        if limit:
            qs = qs[:limit]

        self.stdout.write(
            f"KnownParts Micron raw sem FBGA: {total}"
            + (f"  (processando: {min(limit, total)})" if limit else "")
            + "\n"
        )

        if total == 0:
            self.stdout.write("Nada a fazer.")
            return

        # ── Dependências ──────────────────────────────────────────────────────
        session = _make_session()
        if not getattr(session, "_is_cffi", False):
            self.stdout.write(self.style.WARNING(
                "  ℹ  curl_cffi não instalado — usando requests padrão.\n"
                "     Para melhor bypass: pip install curl_cffi\n"
            ))

        if not dry:
            micron_source, created = Source.objects.get_or_create(
                name="Micron FBGA API",
                defaults={
                    "src_type": "api",
                    "url": MICRON_FBGA_SOURCE_URL,
                },
            )
            if created:
                self.stdout.write("  ℹ  Source 'Micron FBGA API' criado.\n")
        else:
            micron_source = None

        # ── Processa ──────────────────────────────────────────────────────────
        counts = {
            "created": 0,
            "skipped_dup": 0,
            "no_results": 0,
            "deleted_base": 0,
            "errors": 0,
        }

        list_qs = list(qs)  # materializa antes de deletar
        total_to_process = len(list_qs)

        for idx, base_kp in enumerate(list_qs, 1):
            pn = base_kp.part_number
            self.stdout.write(
                f"\n[{idx}/{total_to_process}] {pn} ... ",
                ending="",
            )
            self.stdout.flush()

            results = _query_fbga_api(pn, session, verbose=verbose)

            if not results:
                self.stdout.write(self.style.WARNING("sem resultados na API"))
                counts["no_results"] += 1
                time.sleep(delay)
                continue

            self.stdout.write(
                self.style.SUCCESS(f"{len(results)} FBGA(s):")
            )

            created_this_pn = 0
            for item in results:
                fbga     = item["fbga_code"]
                full_pn  = item["part_number"]
                self.stdout.write(f"   {fbga}  →  {full_pn}")

                if dry:
                    counts["created"] += 1
                    continue

                try:
                    with transaction.atomic():
                        # Checa duplicata por fbga_code (identificador físico único)
                        if KnownPart.objects.filter(fbga_code=fbga).exists():
                            self.stdout.write(f"        ↳ FBGA {fbga} já existe — pulando")
                            counts["skipped_dup"] += 1
                            continue

                        KnownPart.objects.create(
                            brand=base_kp.brand,
                            part_number=full_pn,
                            fbga_code=fbga,
                            chip_type=base_kp.chip_type,
                            subtype=base_kp.subtype,
                            confidence="confirmed",
                            source=micron_source,
                            source_url=item.get("source_url", MICRON_FBGA_API.format(pn=pn)),
                        )
                        counts["created"] += 1
                        created_this_pn += 1

                except Exception as e:
                    logger.warning(
                        "Erro ao criar KnownPart %s / FBGA %s: %s", full_pn, fbga, e
                    )
                    counts["errors"] += 1

            # Remove o base PN (foi substituído pelos registros específicos com FBGA)
            if not dry and not keep_base and created_this_pn > 0:
                try:
                    base_kp.delete()
                    counts["deleted_base"] += 1
                except Exception as e:
                    logger.warning("Erro ao deletar base PN %s: %s", pn, e)

            time.sleep(delay)

        # ── Relatório final ───────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f"\n\n✅  Concluído.\n"
            f"   KnownParts criados (FBGA + PN completo): {counts['created']}\n"
            f"   FBGAs ignorados (já existiam):           {counts['skipped_dup']}\n"
            f"   PNs base sem resultado na API:           {counts['no_results']}\n"
            f"   Registros base removidos:                {counts['deleted_base']}\n"
            f"   Erros:                                   {counts['errors']}\n"
        ))

        if dry:
            self.stdout.write(self.style.WARNING(
                "\nDry run — nenhuma alteração foi salva."
            ))
            return

        # Invalida cache do engine
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            self.stdout.write("   🗑  Cache do engine invalidado.")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))
