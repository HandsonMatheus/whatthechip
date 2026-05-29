"""
collect_octopart.py — Stage 3: coleta chips Micron via Octopart/Nexar API v4
=============================================================================
Usa a API GraphQL da Nexar (nexar.com) que é a plataforma atual da Octopart.

Papel duplo:
  1. Fonte direta de dados  → KnownPart com confidence='distributor'
  2. Descoberta de datasheets → adiciona URLs ao data/datasheet_urls.txt
     para o Stage 2 processar

Pré-requisito:
  Obtenha chave gratuita em https://nexar.com/api
  (Nexar = Octopart API v4 modernizado)

  Configure no .env:
    NEXAR_CLIENT_ID=seu_client_id
    NEXAR_CLIENT_SECRET=seu_client_secret

  OU variáveis de ambiente:
    export NEXAR_CLIENT_ID=seu_client_id
    export NEXAR_CLIENT_SECRET=seu_client_secret

  A API Nexar usa OAuth2 client_credentials — este script autentica
  automaticamente e renova o token.

Alternativa (Octopart v3 legacy, ainda funciona com chave gratuita):
  Configure OCTOPART_API_KEY no .env e o script usa automaticamente.

Uso:
    python manage.py collect_octopart
    python manage.py collect_octopart --dry-run
    python manage.py collect_octopart --chip-type eMCP
    python manage.py collect_octopart --chip-type eMMC --chip-type LPDDR4
    python manage.py collect_octopart --limit 500 --delay 1.0
    python manage.py collect_octopart --overwrite
"""

import os
import re
import time
import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

BASE_DIR     = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR     = BASE_DIR / "data"
URL_QUEUE    = DATA_DIR / "datasheet_urls.txt"
DATA_DIR.mkdir(exist_ok=True)

# Nexar OAuth2 (Octopart v4 GraphQL)
NEXAR_TOKEN_URL = "https://identity.nexar.com/connect/token"
NEXAR_API_URL   = "https://api.nexar.com/graphql"

# Octopart v3 REST (fallback)
OCTOPART_V3_URL = "https://octopart.com/api/v3/parts/search"

# FBGA RE
_FBGA_RE = re.compile(r"^[A-Z0-9]{5}$")

# Tipos de chip alvo para cada série Micron
CHIP_TYPE_PREFIXES = {
    "eMCP":   ["MT29VZZZ"],
    "uMCP":   ["MT30AZZZ"],
    "eMMC":   ["MT29F", "MT29S"],
    "UFS":    ["MT29P"],
    "LPDDR4": ["MT53B", "MT53E", "MT53D"],
    "LPDDR5": ["MT62F", "MT62J", "MT60B"],
    "LPDDR3": ["MT52L", "MT52F"],
    "NAND":   ["MT29F"],
}

# Para cada tipo, qual chip_type e subtype salvar
CHIP_TYPE_META = {
    "eMCP":   ("eMCP",  "LPDDR4"),
    "uMCP":   ("uMCP",  "LPDDR5"),
    "eMMC":   ("eMMC",  ""),
    "UFS":    ("UFS",   ""),
    "LPDDR4": ("DRAM",  "LPDDR4"),
    "LPDDR5": ("DRAM",  "LPDDR5"),
    "LPDDR3": ("DRAM",  "LPDDR3"),
    "NAND":   ("NAND",  ""),
}

ALL_CHIP_TYPES = list(CHIP_TYPE_META.keys())

# Query GraphQL Nexar para busca por fabricante + série
NEXAR_QUERY = """
query SearchParts($q: String!, $limit: Int!, $cursor: String) {
  supSearchMpns(
    q: $q,
    limit: $limit,
    cursor: $cursor
  ) {
    hits
    results {
      part {
        mpn
        manufacturer { name }
        shortDescription
        specs {
          attribute { name shortname }
          value
        }
        bestDatasheet { url }
        datasheets { url }
      }
    }
    nextCursor
  }
}
"""

# Query Octopart v3 (fallback)
OCTOPART_V3_QUERY_TEMPLATE = (
    "https://octopart.com/api/v3/parts/search"
    "?apikey={key}&q={q}&manufacturer=Micron+Technology&limit=100&start={start}"
    "&include[]=datasheets&include[]=specs"
)


# ── Autenticação Nexar ────────────────────────────────────────────────────────

class NexarAuth:
    """Gerencia token OAuth2 para a API Nexar."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id     = client_id
        self.client_secret = client_secret
        self._token: str   = ""
        self._expires_at   = 0.0

    def get_token(self, session) -> str:
        if time.time() < self._expires_at - 60:
            return self._token

        resp = session.post(
            NEXAR_TOKEN_URL,
            data={
                "grant_type":    "client_credentials",
                "client_id":     self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            raise CommandError(
                f"Falha na autenticação Nexar (HTTP {resp.status_code}): {resp.text[:200]}"
            )
        data = resp.json()
        self._token      = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 3600)
        return self._token

    def headers(self, session) -> dict:
        return {
            "Authorization": f"Bearer {self.get_token(session)}",
            "Content-Type":  "application/json",
        }


# ── Consultas à API ───────────────────────────────────────────────────────────

def _nexar_search(
    session,
    auth: NexarAuth,
    query: str,
    limit: int = 100,
    cursor: str | None = None,
) -> dict:
    """Executa uma query GraphQL na API Nexar."""
    payload = {
        "query": NEXAR_QUERY,
        "variables": {
            "q":      query,
            "limit":  limit,
            "cursor": cursor or "",
        },
    }
    resp = session.post(
        NEXAR_API_URL,
        json=payload,
        headers=auth.headers(session),
        timeout=30,
    )
    if resp.status_code != 200:
        logger.warning("Nexar HTTP %s para query %r", resp.status_code, query)
        return {}

    data = resp.json()
    errors = data.get("errors")
    if errors:
        logger.warning("Nexar GraphQL errors: %s", errors)

    return data.get("data", {}).get("supSearchMpns", {})


def _nexar_fetch_all(
    session,
    auth: NexarAuth,
    query: str,
    max_results: int = 2000,
    delay: float = 1.0,
    log_fn=print,
) -> list[dict]:
    """
    Pagina pela API Nexar para um determinado query.
    Retorna lista de part dicts: {mpn, manufacturer, specs, datasheets}
    """
    parts: list[dict] = []
    cursor: str | None = None
    page = 0

    while True:
        page += 1
        result = _nexar_search(session, auth, query, limit=100, cursor=cursor)
        if not result:
            break

        items = result.get("results", [])
        hits  = result.get("hits", 0)

        if page == 1:
            log_fn(f"  Hits totais: {hits}")

        for item in items:
            part = item.get("part")
            if part:
                parts.append(part)

        log_fn(f"  Página {page}: {len(items)} results (total até agora: {len(parts)})")

        cursor = result.get("nextCursor")
        if not cursor or not items or len(parts) >= max_results:
            break

        time.sleep(delay)

    return parts


def _octopart_v3_search(
    session,
    api_key: str,
    query: str,
    max_results: int = 1000,
    delay: float = 1.0,
    log_fn=print,
) -> list[dict]:
    """Fallback: busca via Octopart v3 REST API."""
    parts: list[dict] = []
    start = 0

    while True:
        url = OCTOPART_V3_QUERY_TEMPLATE.format(
            key=api_key, q=query, start=start
        )
        try:
            resp = session.get(url, timeout=20)
        except Exception as e:
            log_fn(f"  Erro HTTP: {e}")
            break

        if resp.status_code != 200:
            log_fn(f"  Octopart v3 HTTP {resp.status_code}")
            break

        data = resp.json()
        results = data.get("results", [])
        total   = data.get("hits", 0)

        if start == 0:
            log_fn(f"  Hits totais (v3): {total}")

        for item in results:
            part_data = item.get("item", {})
            parts.append({
                "mpn": part_data.get("mpn", ""),
                "manufacturer": {"name": part_data.get("manufacturer", {}).get("name", "")},
                "specs": [
                    {"attribute": {"name": s.get("attribute", {}).get("name", "")},
                     "value": s.get("value", "")}
                    for s in part_data.get("specs", {}).values()
                ],
                "bestDatasheet": {"url": part_data.get("datasheets", [{}])[0].get("url", "")}
                    if part_data.get("datasheets") else None,
                "datasheets": [{"url": d.get("url", "")} for d in part_data.get("datasheets", [])],
            })

        start += len(results)
        log_fn(f"  Start {start}: {len(results)} results")

        if start >= total or len(results) == 0 or start >= max_results:
            break

        time.sleep(delay)

    return parts


# ── Parsing de resultado ──────────────────────────────────────────────────────

def _parse_part(part: dict, chip_type_key: str) -> dict | None:
    """
    Converte um resultado Nexar/Octopart em dict padronizado.
    Retorna None se o part não for Micron ou não tiver PN válido.
    """
    mpn = (part.get("mpn") or "").strip().upper()
    if not mpn:
        return None

    manufacturer = (
        part.get("manufacturer", {}) or {}
    ).get("name", "").lower()

    if manufacturer and "micron" not in manufacturer:
        return None

    # Extrai FBGA dos specs (campo "marking" ou "fbga")
    fbga = ""
    for spec in (part.get("specs") or []):
        attr_name = (spec.get("attribute", {}) or {}).get("name", "").lower()
        if any(k in attr_name for k in ("fbga", "marking", "laser", "code")):
            val = (spec.get("value") or "").strip().upper()
            if val and _FBGA_RE.match(val):
                fbga = val
                break

    # Extrai URL de datasheet
    best_ds = (part.get("bestDatasheet") or {})
    ds_url  = (best_ds.get("url") or "").strip() if best_ds else ""
    all_ds  = [
        d.get("url", "").strip()
        for d in (part.get("datasheets") or [])
        if d.get("url")
    ]

    chip_type, subtype = CHIP_TYPE_META.get(chip_type_key, ("Flash", ""))

    return {
        "part_number": mpn,
        "fbga_code":   fbga,
        "chip_type":   chip_type,
        "subtype":     subtype,
        "datasheet_url": ds_url,
        "all_datasheet_urls": all_ds,
    }


# ── Persistência ──────────────────────────────────────────────────────────────

def _save_to_db(
    parts_data: list[dict],
    dry: bool,
    overwrite: bool,
    log_fn=print,
) -> dict[str, int]:
    from chips.models import Brand, KnownPart, Source

    CONFIDENCE_ORDER = {
        "confirmed": 0, "manual": 1, "distributor": 2,
        "ai_high": 3, "ai_medium": 4, "ai_low": 5, "estimated": 6,
    }
    MY_CONFIDENCE      = "distributor"
    MY_CONFIDENCE_RANK = CONFIDENCE_ORDER[MY_CONFIDENCE]

    counts = {"created": 0, "updated": 0, "skipped": 0, "ds_urls": 0}

    if dry:
        micron_brand  = None
        octopart_src  = None
    else:
        micron_brand, _ = Brand.objects.get_or_create(
            name="Micron",
            defaults={"code": "MIC"},
        )
        octopart_src, _ = Source.objects.get_or_create(
            name="Octopart",
            defaults={"src_type": "api", "url": "https://octopart.com"},
        )

    # Coleta URLs de datasheet para fila do Stage 2
    ds_urls_to_queue: list[str] = []

    for part in parts_data:
        pn      = part["part_number"]
        fbga    = part.get("fbga_code", "") or ""
        ct      = part["chip_type"]
        sub     = part["subtype"]
        ds_url  = part.get("datasheet_url", "") or ""
        all_ds  = part.get("all_datasheet_urls", []) or []

        for u in ([ds_url] + all_ds):
            if u and u.lower().endswith(".pdf") and u not in ds_urls_to_queue:
                ds_urls_to_queue.append(u)
                counts["ds_urls"] += 1

        if dry:
            exists = KnownPart.objects.filter(part_number=pn).exists()
            action = "UPDATE" if (exists and overwrite) else ("SKIP" if exists else "CREATE")
            log_fn(
                f"  [{action:6s}] {pn:40s}  fbga={fbga or '-':6s}  {ct}"
                + (f" {sub}" if sub else "")
            )
            if action == "CREATE":
                counts["created"] += 1
            elif action == "UPDATE":
                counts["updated"] += 1
            else:
                counts["skipped"] += 1
            continue

        try:
            existing = KnownPart.objects.filter(part_number=pn).first()

            if existing is None:
                KnownPart.objects.create(
                    brand=micron_brand,
                    part_number=pn,
                    fbga_code=fbga,
                    chip_type=ct,
                    subtype=sub,
                    status="raw",
                    confidence=MY_CONFIDENCE,
                    source=octopart_src,
                    source_url=ds_url or f"https://octopart.com/search?q={pn}",
                )
                counts["created"] += 1

            elif overwrite:
                existing_rank = CONFIDENCE_ORDER.get(existing.confidence, 99)
                if existing_rank >= MY_CONFIDENCE_RANK:
                    update_fields: list[str] = []
                    if fbga and not existing.fbga_code:
                        existing.fbga_code = fbga
                        update_fields.append("fbga_code")
                    if not existing.chip_type and ct:
                        existing.chip_type = ct
                        update_fields.append("chip_type")
                    if not existing.subtype and sub:
                        existing.subtype = sub
                        update_fields.append("subtype")
                    if existing.source is None:
                        existing.source = octopart_src
                        update_fields.append("source")
                    if not existing.source_url and ds_url:
                        existing.source_url = ds_url
                        update_fields.append("source_url")
                    if update_fields:
                        update_fields.append("last_updated")
                        existing.save(update_fields=update_fields)
                        counts["updated"] += 1
                    else:
                        counts["skipped"] += 1
                else:
                    counts["skipped"] += 1
            else:
                counts["skipped"] += 1

        except Exception as e:
            logger.warning("Erro ao salvar PN %s: %s", pn, e)

    # Adiciona URLs de datasheet à fila do Stage 2
    if not dry and ds_urls_to_queue:
        _queue_datasheet_urls(ds_urls_to_queue)

    return counts


def _queue_datasheet_urls(urls: list[str]):
    """Adiciona URLs de datasheet à fila do Stage 2."""
    URL_QUEUE.parent.mkdir(exist_ok=True)
    existing: set[str] = set()

    if URL_QUEUE.exists():
        for line in URL_QUEUE.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                existing.add(stripped)

    new_urls = [u for u in urls if u not in existing]
    if new_urls:
        with URL_QUEUE.open("a") as f:
            f.write(f"\n# Adicionado por collect_octopart ({len(new_urls)} URLs)\n")
            f.write("\n".join(new_urls) + "\n")
        logger.info("Adicionadas %d URLs de datasheet à fila.", len(new_urls))


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


# ── Command ───────────────────────────────────────────────────────────────────

class _DryRunAbort(Exception):
    pass


class Command(BaseCommand):
    help = (
        "Stage 3 — Coleta chips Micron via API Octopart/Nexar. "
        "Salva KnownPart com confidence='distributor' e alimenta "
        "data/datasheet_urls.txt para o Stage 2."
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
            "--chip-type",
            action="append",
            dest="chip_types",
            choices=ALL_CHIP_TYPES,
            metavar="TIPO",
            help=(
                f"Tipo(s) de chip a buscar. Pode repetir. "
                f"Tipos: {', '.join(ALL_CHIP_TYPES)}"
            ),
        )
        parser.add_argument(
            "--limit", type=int, default=0, metavar="N",
            help="Limite de resultados por tipo de chip (0 = sem limite).",
        )
        parser.add_argument(
            "--delay", type=float, default=1.0, metavar="SEG",
            help="Pausa em segundos entre requests (padrão: 1.0).",
        )

    def handle(self, *args, **options):
        raise CommandError(
            "collect_octopart está DESABILITADO.\n\n"
            "A API Nexar/Octopart tem custo elevado e não está em uso neste projeto.\n"
            "Para coletar chips Micron, use os outros stages:\n"
            "  Stage 2 — datasheets PDF:    python scripts/collect_datasheets.py\n"
            "  Stage 4 — Preduo bulk:       python manage.py collect_preduo_bulk\n"
            "  Stage 5 — Wayback Machine:   python scripts/collect_wayback.py\n"
        )

        dry      = options["dry_run"]
        overwrite = options["overwrite"]
        delay    = options["delay"]
        limit    = options["limit"] or 2000
        selected = options.get("chip_types") or ALL_CHIP_TYPES

        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        # ── Credenciais ───────────────────────────────────────────────────────
        # settings.py já faz load_dotenv(.env) na inicialização do Django.
        # Aqui só lemos os valores carregados em os.environ.
        nexar_id     = os.environ.get("NEXAR_CLIENT_ID", "").strip()
        nexar_secret = os.environ.get("NEXAR_CLIENT_SECRET", "").strip()
        octopart_key = os.environ.get("OCTOPART_API_KEY", "").strip()

        use_nexar    = bool(nexar_id and nexar_secret)
        use_octopart = bool(octopart_key)

        if not use_nexar and not use_octopart:
            raise CommandError(
                "Nenhuma credencial de API configurada.\n\n"
                "Adicione no arquivo .env (na raiz do projeto):\n\n"
                "  # Nexar (Octopart v4 — recomendado, gratuito)\n"
                "  NEXAR_CLIENT_ID=seu_client_id\n"
                "  NEXAR_CLIENT_SECRET=seu_client_secret\n\n"
                "  # OU Octopart v3 legacy\n"
                "  OCTOPART_API_KEY=sua_chave\n\n"
                "Obtenha credenciais em: https://nexar.com/api\n\n"
                f"  (chaves lidas: NEXAR_CLIENT_ID={'SET' if nexar_id else 'vazio'}, "
                f"NEXAR_CLIENT_SECRET={'SET' if nexar_secret else 'vazio'}, "
                f"OCTOPART_API_KEY={'SET' if octopart_key else 'vazio'})"
            )

        api_mode = "Nexar (Octopart v4)" if use_nexar else "Octopart v3"
        self.stdout.write(f"API: {api_mode}\n")
        self.stdout.write(f"Tipos a coletar: {', '.join(selected)}\n")

        session = _make_session()
        auth    = NexarAuth(nexar_id, nexar_secret) if use_nexar else None

        # ── Coleta por tipo de chip ───────────────────────────────────────────
        all_parts_data: list[dict] = []

        for chip_type_key in selected:
            prefixes = CHIP_TYPE_PREFIXES.get(chip_type_key, [])
            chip_type, subtype = CHIP_TYPE_META[chip_type_key]

            self.stdout.write(f"\n▶  {chip_type_key} (prefixos: {', '.join(prefixes)}) ...")

            parts_for_type: list[dict] = []

            for prefix in prefixes:
                query = f"Micron {prefix}"
                self.stdout.write(f"\n  Query: {query!r}")

                try:
                    if use_nexar:
                        raw_parts = _nexar_fetch_all(
                            session, auth, query,
                            max_results=limit,
                            delay=delay,
                            log_fn=self.stdout.write,
                        )
                    else:
                        raw_parts = _octopart_v3_search(
                            session, octopart_key, query,
                            max_results=limit,
                            delay=delay,
                            log_fn=self.stdout.write,
                        )
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  Erro na query {query!r}: {e}"))
                    continue

                for raw_part in raw_parts:
                    parsed = _parse_part(raw_part, chip_type_key)
                    if parsed:
                        parts_for_type.append(parsed)

                time.sleep(delay)

            # Remove duplicatas por PN dentro do tipo
            seen: set[str] = set()
            unique_for_type = []
            for p in parts_for_type:
                if p["part_number"] not in seen:
                    seen.add(p["part_number"])
                    unique_for_type.append(p)

            self.stdout.write(f"  {chip_type_key}: {len(unique_for_type)} PNs únicos")
            all_parts_data.extend(unique_for_type)

        # Remove duplicatas globais
        global_seen: set[str] = set()
        final_parts: list[dict] = []
        for p in all_parts_data:
            if p["part_number"] not in global_seen:
                global_seen.add(p["part_number"])
                final_parts.append(p)

        total = len(final_parts)
        self.stdout.write(f"\n\nTotal de PNs únicos coletados: {total}")

        if total == 0:
            self.stdout.write(self.style.WARNING("\n⚠  Nenhum PN coletado."))
            return

        # ── Salva no banco ────────────────────────────────────────────────────
        try:
            with transaction.atomic():
                counts = _save_to_db(
                    parts_data=final_parts,
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
            f"   Novos KnownParts criados:           {counts['created']}\n"
            f"   KnownParts atualizados:             {counts['updated']}\n"
            f"   Pulados (já existiam):              {counts['skipped']}\n"
            f"   URLs de datasheet adicionadas:      {counts['ds_urls']}\n"
        ))

        if counts["ds_urls"] > 0:
            self.stdout.write(
                f"   💡 Rode 'python scripts/collect_datasheets.py' "
                f"para processar os datasheets (Stage 2)."
            )

        # Invalida cache do engine
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            self.stdout.write("   🗑  Cache do engine invalidado.")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))
