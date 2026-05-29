"""
lookup_fbga.py — Busca reversa: FBGA code → Part Number via API oficial Micron
==============================================================================
O pipeline padrão (enrich_micron_fbga) faz PN→FBGA.
Este comando faz o inverso: dado um FBGA code gravado no chip, consulta a
API da Micron para descobrir o Part Number correspondente e salva no banco.

Uso principal: chip da bancada não reconhecido → rodar este comando → chip
passa a ser identificado instantaneamente pelo motor.

API usada:
  https://www.micron.com/.../getpartbyfbgacode/-/-/-/en_US/-/-/{FBGA_CODE}
  (wildcard "-" no campo PN = busca por FBGA)

Uso:
    python manage.py lookup_fbga JW464 JZ185 JWB13 JZ109 JY934 D9RRD
    python manage.py lookup_fbga JW464 --dry-run
    python manage.py lookup_fbga --file data/fbga_pendentes.txt
    python manage.py lookup_fbga JW464 --verbose
"""

import re
import time
import logging

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

# ── API Micron FBGA (busca reversa por FBGA code) ─────────────────────────────
#
# Mesma API que enrich_micron_fbga, mas com os campos invertidos:
#   forward (PN→FBGAs):  .../en_US/-/{PN}/-
#   reverse (FBGA→PN):   .../en_US/-/-/{FBGA}
#
MICRON_FBGA_API_REVERSE = (
    "https://www.micron.com/content/micron/us/en/sales-support/design-tools/"
    "fbga-parts-decoder/_jcr_content.products.json/"
    "getpartbyfbgacode/-/-/-/en_US/-/-/{fbga}"
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

_FBGA_RE     = re.compile(r"^[A-Z0-9]{5}$")
_PN_PREFIX   = re.compile(r"^(MT|MTFC|MTFD|NW|D9)", re.IGNORECASE)


# ── Inferência de chip_type a partir do PN retornado pela API ─────────────────

def _infer_from_pn(full_pn: str) -> tuple[str, str]:
    """
    Infere (chip_type, subtype) do PN completo retornado pela API.
    Usado quando a API não retorna sub-category explicitamente.
    """
    pn = full_pn.upper().split()[0]   # ignora sufixo após espaço (ex: "18 W.95L")

    if pn.startswith("MT29VZZZ"):  return ("eMCP", "LPDDR4")
    if pn.startswith("MT29TZZZ"):  return ("eMCP", "LPDDR3")
    if pn.startswith("MT30AZZZ"):  return ("uMCP", "LPDDR5")
    if re.match(r"MTFC|MTFD",pn):  return ("eMMC", "")
    if pn.startswith("MT29P"):     return ("UFS",  "")
    if re.match(r"MT53[BDE]",pn):  return ("DRAM", "LPDDR4")
    if re.match(r"MT53[EF]",pn):   return ("DRAM", "LPDDR5")
    if re.match(r"MT52[LF]",pn):   return ("DRAM", "LPDDR3")
    if re.match(r"MT6[234]",pn):   return ("DRAM", "LPDDR5")
    if re.match(r"MT29[FS]",pn):   return ("NAND", "")
    if pn.startswith("D9"):        return ("DRAM", "")
    return ("", "")


def _chip_type_from_subcategory(sub: str) -> tuple[str, str]:
    """
    Mapeia 'sub-category' da API para (chip_type, subtype).
    Exemplos de sub-category: 'emmc-based-mcp', 'emmc', 'lpddr4', 'ufs', ...
    """
    sub = sub.lower().replace("-", " ")
    if "emmc" in sub and "mcp" in sub:  return ("eMCP", "")
    if "ufs"  in sub and "mcp" in sub:  return ("uMCP", "")
    if "emmc" in sub:                   return ("eMMC", "")
    if "ufs"  in sub:                   return ("UFS",  "")
    if "lpddr5x" in sub:                return ("DRAM", "LPDDR5X")
    if "lpddr5"  in sub:                return ("DRAM", "LPDDR5")
    if "lpddr4x" in sub:                return ("DRAM", "LPDDR4X")
    if "lpddr4"  in sub:                return ("DRAM", "LPDDR4")
    if "lpddr3"  in sub:                return ("DRAM", "LPDDR3")
    if "lpddr2"  in sub:                return ("DRAM", "LPDDR2")
    if "nand"    in sub:                return ("NAND", "")
    return ("", "")


# ── HTTP session ──────────────────────────────────────────────────────────────

def _make_session():
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

def query_by_fbga(fbga_code: str, session, verbose: bool = False) -> dict | None:
    """
    Consulta a API Micron pelo código FBGA (busca reversa).

    Retorna dict com:
      {
        "fbga_code":   "JW464",
        "part_number": "MTFC...",
        "chip_type":   "eMMC",
        "subtype":     "",
        "source_url":  "https://...",
        "part_name":   "...",    (descrição do produto)
        "page_url":    "https://www.micron.com/products/...",
      }
    Retorna None se não encontrado.
    """
    url = MICRON_FBGA_API_REVERSE.format(fbga=fbga_code)

    if verbose:
        print(f"  [DEBUG] URL: {url}")

    for attempt in range(3):
        try:
            r = session.get(url, headers=_HEADERS, timeout=25)

            if verbose:
                print(f"  [DEBUG] HTTP {r.status_code}")
                print(f"  [DEBUG] Body: {r.text[:600]!r}")

            if r.status_code == 404:
                return None

            if r.status_code in (429, 503):
                time.sleep(8 * (attempt + 1))
                continue

            if r.status_code != 200:
                logger.warning("HTTP %s para FBGA %s", r.status_code, fbga_code)
                time.sleep(2)
                continue

            data = r.json()
            break

        except Exception as e:
            if verbose:
                print(f"  [DEBUG] Exceção: {e}")
            logger.warning("Erro (tentativa %d/3) FBGA %s: %s", attempt + 1, fbga_code, e)
            time.sleep(2 * (attempt + 1))
    else:
        return None

    # Normaliza resposta
    if isinstance(data, dict):
        items = (
            data.get("details")
            or data.get("results")
            or data.get("data")
            or data.get("products")
            or []
        )
    elif isinstance(data, list):
        items = data
    else:
        return None

    if not items:
        return None

    # Pega o primeiro resultado (busca por FBGA deve retornar exatamente 1)
    item = items[0] if isinstance(items[0], dict) else {}

    full_pn   = (item.get("part-number") or item.get("partNumber") or "").strip()
    fbga_ret  = (item.get("fbga-code")   or item.get("fbgaCode")   or fbga_code).strip().upper()
    sub_cat   = (item.get("sub-category") or item.get("subCategory") or "").strip()
    part_name = (item.get("part-name")   or item.get("partName")   or "").strip()
    page_url  = (item.get("pageurl")     or item.get("pageUrl")    or "").strip()

    if not full_pn:
        return None

    if page_url and not page_url.startswith("http"):
        page_url = f"https://www.micron.com{page_url}"

    # Infere chip_type
    chip_type, subtype = _chip_type_from_subcategory(sub_cat)
    if not chip_type:
        chip_type, subtype = _infer_from_pn(full_pn)

    return {
        "fbga_code":   fbga_ret,
        "part_number": full_pn,
        "chip_type":   chip_type,
        "subtype":     subtype,
        "source_url":  page_url or MICRON_FBGA_API_REVERSE.format(fbga=fbga_code),
        "part_name":   part_name,
        "page_url":    page_url,
    }


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Busca reversa: dado um código FBGA gravado no chip, consulta a API oficial "
        "da Micron para descobrir o Part Number e salva no banco com "
        "confidence='confirmed', status='enriched'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "fbga_codes",
            nargs="*",
            metavar="FBGA",
            help="Um ou mais códigos FBGA (ex: JW464 JZ185 D9RRD).",
        )
        parser.add_argument(
            "--file", "-f",
            dest="fbga_file",
            metavar="ARQUIVO",
            help="Arquivo de texto com um FBGA por linha.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria feito sem alterar o banco.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            metavar="SEG",
            help="Pausa em segundos entre requests (padrão: 1.0).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Mostra detalhes da request/resposta HTTP.",
        )

    def handle(self, *args, **options):
        from chips.models import Brand, KnownPart, Source
        from pathlib import Path

        dry     = options["dry_run"]
        delay   = options["delay"]
        verbose = options["verbose"]

        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        # ── Coleta os códigos FBGA ────────────────────────────────────────────
        fbga_codes: list[str] = [c.strip().upper() for c in options["fbga_codes"] if c.strip()]

        if options.get("fbga_file"):
            p = Path(options["fbga_file"])
            if not p.exists():
                raise CommandError(f"Arquivo não encontrado: {p}")
            for line in p.read_text().splitlines():
                line = line.strip().upper()
                if line and not line.startswith("#"):
                    fbga_codes.append(line)

        # Deduplica preservando ordem
        seen_input: set[str] = set()
        unique_codes: list[str] = []
        for code in fbga_codes:
            if code not in seen_input:
                seen_input.add(code)
                unique_codes.append(code)
        fbga_codes = unique_codes

        if not fbga_codes:
            raise CommandError(
                "Nenhum código FBGA fornecido.\n"
                "Uso: python manage.py lookup_fbga JW464 JZ185 JWB13\n"
                "  ou: python manage.py lookup_fbga --file data/fbga_pendentes.txt"
            )

        # Valida formato
        invalidos = [c for c in fbga_codes if not _FBGA_RE.match(c)]
        if invalidos:
            self.stdout.write(self.style.WARNING(
                f"  ⚠  Códigos com formato incomum (5 chars alfanum.): "
                f"{', '.join(invalidos)}\n"
                f"     Continuando mesmo assim — a API pode reconhecê-los.\n"
            ))

        self.stdout.write(f"Consultando API Micron para {len(fbga_codes)} código(s):\n"
                          f"  {', '.join(fbga_codes)}\n")

        # ── HTTP session ──────────────────────────────────────────────────────
        session = _make_session()
        if not getattr(session, "_is_cffi", False):
            self.stdout.write(self.style.WARNING(
                "  ℹ  curl_cffi não instalado — usando requests padrão.\n"
            ))

        # ── Busca ─────────────────────────────────────────────────────────────
        results: list[dict] = []
        not_found: list[str] = []

        for i, fbga in enumerate(fbga_codes, 1):
            self.stdout.write(f"\n[{i}/{len(fbga_codes)}] {fbga} ...")
            self.stdout.flush()

            result = query_by_fbga(fbga, session, verbose=verbose)

            if result is None:
                self.stdout.write(f"  ✗  Não encontrado na API Micron")
                not_found.append(fbga)
            else:
                ct = result["chip_type"]
                st = result["subtype"]
                pn = result["part_number"]
                nm = result["part_name"]
                self.stdout.write(
                    f"  ✓  {pn}"
                    + (f"  [{ct}{' ' + st if st else ''}]" if ct else "")
                    + (f"\n     {nm}" if nm else "")
                )
                results.append(result)

            if i < len(fbga_codes):
                time.sleep(delay)

        # ── Resumo da busca ───────────────────────────────────────────────────
        self.stdout.write(f"\n\nEncontrados: {len(results)} / {len(fbga_codes)}")
        if not_found:
            self.stdout.write(
                f"Não encontrados: {', '.join(not_found)}\n"
                f"  → Verifique se o código está correto (5 chars, maiúsculas).\n"
                f"  → Chips Samsung/SK Hynix usam nomenclaturas diferentes e\n"
                f"    não aparecem na API da Micron.\n"
            )

        if not results:
            return

        if dry:
            self.stdout.write(self.style.WARNING("\nDRY RUN — nada salvo."))
            return

        # ── Salva no banco ────────────────────────────────────────────────────
        micron_brand, _ = Brand.objects.get_or_create(
            name="Micron", defaults={"code": "MIC"}
        )
        micron_source, _ = Source.objects.get_or_create(
            name="Micron FBGA API",
            defaults={"src_type": "api", "url": MICRON_FBGA_SOURCE_URL},
        )

        counts = {"created": 0, "skipped": 0, "updated": 0}

        for r in results:
            fbga = r["fbga_code"]
            pn   = r["part_number"]

            # Verifica se FBGA já existe
            existing_fbga = KnownPart.objects.filter(fbga_code=fbga).first()
            if existing_fbga:
                self.stdout.write(
                    f"  FBGA {fbga} já existe ({existing_fbga.part_number}) — pulando"
                )
                counts["skipped"] += 1
                continue

            # Verifica se PN já existe (sem FBGA)
            existing_pn = KnownPart.objects.filter(part_number=pn).first()
            if existing_pn and not existing_pn.fbga_code:
                existing_pn.fbga_code   = fbga
                existing_pn.status      = "enriched"
                existing_pn.confidence  = "confirmed"
                existing_pn.source      = micron_source
                existing_pn.source_url  = r["source_url"]
                if r["chip_type"] and not existing_pn.chip_type:
                    existing_pn.chip_type = r["chip_type"]
                if r["subtype"] and not existing_pn.subtype:
                    existing_pn.subtype = r["subtype"]
                existing_pn.save()
                self.stdout.write(f"  ✓  {fbga} → atualizado PN existente {pn}")
                counts["updated"] += 1
                continue

            # Cria novo KnownPart
            try:
                KnownPart.objects.create(
                    brand      = micron_brand,
                    part_number= pn,
                    fbga_code  = fbga,
                    chip_type  = r["chip_type"],
                    subtype    = r["subtype"],
                    status     = "enriched",
                    confidence = "confirmed",
                    source     = micron_source,
                    source_url = r["source_url"],
                    notes      = r["part_name"] if r["part_name"] else "",
                )
                self.stdout.write(
                    f"  ✓  {fbga} → criado: {pn}"
                    + (f"  [{r['chip_type']}]" if r["chip_type"] else "")
                )
                counts["created"] += 1
            except Exception as e:
                logger.error("Erro ao criar KnownPart para FBGA %s: %s", fbga, e)

        # Invalida cache
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS(
            f"\n✅  Concluído.\n"
            f"   Criados:    {counts['created']}\n"
            f"   Atualizados:{counts['updated']}\n"
            f"   Pulados:    {counts['skipped']}\n"
        ))

        if counts["created"] or counts["updated"]:
            self.stdout.write(
                "💡 Teste agora na bancada — os chips devem ser reconhecidos pelo motor."
            )
