"""
scrape_preduo.py — Scraper do catálogo Preduo para KnownParts
==============================================================
Coleta Part Numbers de preduo.com e persiste no banco como
KnownPart(status="raw", confidence="distributor").

Preduo é um catálogo B2B do mercado de reciclagem de memórias para smartphones.
Na hierarquia de fontes:
    fabricante oficial > Octopart > distribuidor B2B > Preduo > IA > especulação

Cada tipo de chip em preduo.com tem uma lista paginada (WordPress server-rendered):
    https://www.preduo.com/list/emmc
    https://www.preduo.com/list/emmc/page/2
    https://www.preduo.com/list/lpddr/lpddr4
    https://www.preduo.com/list/lpddr/lpddr4/page/2
    ...

Resiliência HTTP (em ordem):
    1. curl_cffi — replica TLS fingerprint do Chrome, resolve a maioria dos casos
    2. Playwright — fallback para Cloudflare JS challenge que exige browser real

Uso:
    python manage.py scrape_preduo
    python manage.py scrape_preduo --dry-run
    python manage.py scrape_preduo --type eMCP --type eMMC
    python manage.py scrape_preduo --brand Micron
    python manage.py scrape_preduo --overwrite --limit 500
    python manage.py scrape_preduo --delay 3.0 --max-pages 50
"""

import re
import time
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)

# ── Tipos de chip cobertos pelo Preduo ───────────────────────────────────────
#
# Cada entrada: (key, url_path, chip_type_no_banco, subtype_no_banco)
#
# key      — identificador curto usado em --type
# url_path — caminho após https://www.preduo.com/
#            Paginação: {base_url}/page/{N}  (WordPress standard)
#
PREDUO_CHIP_TYPES: list[tuple[str, str, str, str]] = [
    # Mobile storage
    ("eMCP",     "list/emcp",            "eMCP",      ""),
    ("eMMC",     "list/emmc",            "eMMC",      ""),
    ("uMCP",     "list/umcp",            "uMCP",      ""),
    ("UFS",      "list/ufs",             "UFS",       ""),
    # Mobile DRAM
    ("LPDDR5T",  "list/lpddr/lpddr5t",          "RAM", "LPDDR5T"),
    ("LPDDR5X",  "list/lpddr/lpddr5x-lpddr",    "RAM", "LPDDR5X"),
    ("LPDDR5",   "list/lpddr/lpddr5-lpddr",     "RAM", "LPDDR5"),
    ("LPDDR4X",  "list/lpddr/lpddr4x",          "RAM", "LPDDR4X"),
    ("LPDDR4",   "list/lpddr/lpddr4",           "RAM", "LPDDR4"),
    ("LPDDR3",   "list/lpddr/lpddr3",           "RAM", "LPDDR3"),
    ("LPDDR2",   "list/lpddr/lpddr2",           "RAM", "LPDDR2"),
    # Client/Server DRAM
    ("DDR5",     "list/dram/ddr5",       "RAM", "DDR5"),
    ("DDR4",     "list/dram/ddr4",       "RAM", "DDR4"),
    ("DDR3",     "list/dram/ddr3-ddr",   "RAM", "DDR3"),
    ("DDR2",     "list/dram/ddr2",       "RAM", "DDR2"),
    # High-bandwidth / graphics DRAM
    ("GDDR6",    "list/gddr/gddr6",      "RAM", "GDDR6"),
    ("GDDR5",    "list/gddr/gddr5",      "RAM", "GDDR5"),
    ("HBM3E",    "list/hbm/hbm3e",      "RAM", "HBM3E"),
    ("HBM3",     "list/hbm/hbm3",       "RAM", "HBM3"),
    ("HBM2E",    "list/hbm/hbm2e",      "RAM", "HBM2E"),
    ("HBM2",     "list/hbm/hbm2",       "RAM", "HBM2"),
    # Flash
    ("NORFLASH", "list/norflash",        "NOR Flash", ""),
]

# ── Mapa prefixo → nome da marca ─────────────────────────────────────────────
#
# Ordem importa: prefixos mais longos primeiro para evitar matches parciais.
# Ex: "MT6" (MediaTek) antes de "MT" (Micron).
#
BRAND_PREFIX_MAP: list[tuple[str, str]] = [
    # Kingston (K* mais específicos ANTES de Samsung K*)
    ("KVR", "Kingston"), ("KHX", "Kingston"), ("KSM", "Kingston"), ("KCP", "Kingston"),
    # Samsung (todos os K* restantes)
    ("K",   "Samsung"),
    # SK Hynix
    ("H9",  "SK Hynix"), ("H8",  "SK Hynix"), ("HM",  "SK Hynix"), ("HY",  "SK Hynix"),
    # MediaTek antes de Micron (MT6/MT8 são MediaTek, restante é Micron)
    ("MT6", "MediaTek"), ("MT8", "MediaTek"),
    # Micron
    ("MT",  "Micron"), ("NW", "Micron"), ("D9", "Micron"),
    # KIOXIA / Toshiba Memory
    ("TH",  "KIOXIA"), ("TC", "KIOXIA"),
    # Elpida
    ("EB",  "Elpida"), ("ED", "Elpida"),
    # Nanya
    ("NT",  "Nanya"),
    # SanDisk (iNAND embutido — exclui consumer SD/USB)
    ("SDINB", "SanDisk"), ("SDTN", "SanDisk"), ("SDIN", "SanDisk"),
    ("SDCIT", "SanDisk"), ("SDFCG", "SanDisk"),
    # ISSI
    ("IS",  "ISSI"),
    # Rayson
    ("RS",  "Rayson"), ("EM", "Rayson"),
    # GigaDevice
    ("GD",  "GigaDevice"),
]

# Códigos curtos para Brand.code (get_or_create)
BRAND_CODE_MAP: dict[str, str] = {
    "Samsung":    "SAM",
    "SK Hynix":   "HYN",
    "Micron":     "MIC",
    "KIOXIA":     "KIO",
    "Elpida":     "ELP",
    "Nanya":      "NAN",
    "Kingston":   "KNG",
    "SanDisk":    "SND",
    "ISSI":       "ISS",
    "Rayson":     "RAY",
    "GigaDevice": "GGD",
    "MediaTek":   "MTK",
}

# ── Regex e constantes de validação de PN ────────────────────────────────────

_PN_RE = re.compile(r"\b([A-Z][A-Z0-9]{5,23})\b")
_NEXT_RE = re.compile(r"Next|›|»|next", re.I)

# Tokens que aparecem em páginas mas NUNCA são PNs
_FALSE_POSITIVES = frozenset({
    # Nomes de fabricantes
    "SAMSUNG", "SKHYNIX", "MICRON", "KIOXIA", "TOSHIBA", "ELPIDA", "NANYA",
    "KINGSTON", "SANDISK", "ISSI", "RAYSON", "GIGADEVICE", "MEDIATEK",
    "QUALCOMM", "PREDUO",
    # Tipos de chip — base e variantes com sufixo numérico curto
    # (LPDDR4, LPDDR5, etc. têm 6 chars + dígito e passariam o filtro sem esta lista)
    "EMMC", "LPDDR", "LPDDR2", "LPDDR3", "LPDDR4", "LPDDR5",
    "LPDDR4X", "LPDDR5X", "LPDDR5T",
    "DDR", "DDR2", "DDR3", "DDR4", "DDR5",
    "GDDR", "GDDR5", "GDDR6",
    "HBM2", "HBM3", "HBM2E", "HBM3E",
    "FLASH", "NAND", "NORFLASH",
    # Palavras genéricas de páginas web
    "MEMORY", "STORAGE", "SEARCH", "CONTACT", "PRODUCT", "CATEGORY",
    "DOWNLOAD", "AVAILABLE", "OVERVIEW", "FEATURES", "SUPPORT", "MODULE",
    "SERVER", "MOBILE", "LAPTOP", "DESKTOP",
})

_FORBIDDEN_SUBSTRINGS = ("PARTDETAILS",)


def _infer_brand(pn: str) -> str | None:
    """Infere a marca a partir do prefixo do PN. Retorna None se desconhecida."""
    for prefix, brand in BRAND_PREFIX_MAP:
        if pn.startswith(prefix):
            return brand
    return None


def _is_valid_pn(pn: str) -> bool:
    """Filtragem mínima: rejeita lixo óbvio, aceita tudo que parece ser um PN."""
    if len(pn) < 6 or len(pn) > 24:
        return False
    if pn in _FALSE_POSITIVES:
        return False
    if any(sub in pn for sub in _FORBIDDEN_SUBSTRINGS):
        return False
    if not re.search(r"\d", pn):
        return False  # palavra pura, sem dígitos
    if re.match(r"^\d+$", pn):
        return False  # número puro
    return True


def _extract_pns(text: str) -> list[str]:
    """Extrai candidatos a PN de um bloco de texto bruto."""
    seen: dict[str, None] = {}
    for m in _PN_RE.finditer(text.upper()):
        pn = m.group(1)
        if _is_valid_pn(pn) and pn not in seen:
            seen[pn] = None
    return list(seen.keys())


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _bs4_parse(html: str) -> "BeautifulSoup":
    """
    Parseia HTML com o melhor parser disponível.
    Tenta lxml primeiro (mais rápido), cai para html.parser (sempre disponível).
    """
    from bs4 import BeautifulSoup
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _make_session():
    """Cria sessão HTTP com TLS impersonation do Chrome (curl_cffi)."""
    try:
        from curl_cffi import requests as cffi_requests
        session = cffi_requests.Session(impersonate="chrome110")
        session._is_cffi = True
        return session
    except ImportError:
        import requests as std_requests
        session = std_requests.Session()
        session._is_cffi = False
        return session


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _fetch(url: str, session, retries: int = 3) -> "BeautifulSoup | None":
    """Busca URL com curl_cffi, retorna BeautifulSoup ou None."""
    try:
        from bs4 import BeautifulSoup  # noqa: F401
    except ImportError:
        raise CommandError("BeautifulSoup não instalado: pip install beautifulsoup4")

    for attempt in range(retries):
        try:
            r = session.get(url, headers=_HEADERS, timeout=25)
            if r.status_code == 200 and len(r.text) > 300:
                return _bs4_parse(r.text)
            if r.status_code in (403, 401, 429, 503):
                logger.warning("HTTP %s → %s", r.status_code, url)
                return None
            logger.debug("HTTP %s (tentativa %d) → %s", r.status_code, attempt + 1, url)
        except Exception as e:
            logger.warning("Erro (tentativa %d/%d) em %s: %s", attempt + 1, retries, url, e)
        time.sleep(1.5 * (attempt + 1))
    return None


# Instância global do browser Playwright — iniciada sob demanda, fechada no exit
_pw_instance = None
_pw_browser = None


def _pw_get_browser(headless: bool = True):
    """
    Inicia (ou reutiliza) o browser Playwright.

    headless=False (--show-browser):
        Abre uma janela Chrome visível. Bypassa detecção de headless do Cloudflare.
        Exige display (funciona em macOS/Linux com GUI, não funciona em servidor sem X11).
    """
    global _pw_instance, _pw_browser
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    if _pw_browser is None:
        _pw_instance = sync_playwright().start()
        _pw_browser = _pw_instance.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                # Sinais que Cloudflare verifica em headless:
                "--window-size=1280,800",
                "--start-maximized",
            ],
        )
        mode = "headful" if not headless else "headless"
        logger.info("[Playwright] Browser Chromium iniciado (%s)", mode)
    return _pw_browser


def _pw_close():
    global _pw_instance, _pw_browser
    for obj, method in [(_pw_browser, "close"), (_pw_instance, "stop")]:
        if obj:
            try:
                getattr(obj, method)()
            except Exception:
                pass
    _pw_browser = None
    _pw_instance = None


def _fetch_playwright(url: str, wait_ms: int = 3500, headless: bool = True) -> "BeautifulSoup | None":
    """
    Busca URL com Playwright (Chromium real), resolve JS challenges.

    headless=False: abre janela visível — melhor bypass de detecção Cloudflare.
    """
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout  # noqa: F401
        from bs4 import BeautifulSoup  # noqa: F401
    except ImportError:
        return None

    browser = _pw_get_browser(headless=headless)
    if not browser:
        return None

    ctx = None
    try:
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            },
        )
        page = ctx.new_page()
        # Anti-detecção: remove sinais óbvios de automação
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = { runtime: {} };
        """)
        page.goto(url, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(wait_ms)
        html = page.content()
        return _bs4_parse(html)
    except Exception as e:
        logger.warning("[Playwright] Erro em %s: %s", url, e)
        return None
    finally:
        if ctx:
            try:
                ctx.close()
            except Exception:
                pass


# ── Detecção de Cloudflare challenge ─────────────────────────────────────────

def _is_cf_challenge(soup) -> bool:
    """
    Retorna True se a página é um Cloudflare JS challenge (não o conteúdo real).

    curl_cffi pode retornar a página CF com status 200 e len > 300 — ela passa
    pelos filtros de _fetch() mas não tem PNs. Precisamos detectar isso para
    acionar o fallback Playwright antes de concluir que o tipo não tem dados.

    Indicadores típicos:
      - <title>Just a moment...</title>
      - <div id="cf-wrapper"> ou id="challenge-running"
      - Página muito curta contendo "cloudflare"
    """
    if soup is None:
        return False
    title = soup.find("title")
    if title and "just a moment" in title.get_text().lower():
        return True
    if soup.find(id="cf-wrapper") or soup.find(id="challenge-running"):
        return True
    page_text = soup.get_text().strip()
    # Página de challenge é sempre curta e menciona Cloudflare
    return len(page_text) < 800 and "cloudflare" in page_text.lower()


# ── Scraping de uma lista Preduo ─────────────────────────────────────────────

def _scrape_preduo_list(
    key: str,
    url_path: str,
    session,
    max_pages: int,
    delay: float,
    use_playwright: bool,
    headless: bool = True,
    log_fn=None,
) -> list[tuple[str, str]]:
    """
    Raspa todas as páginas de https://www.preduo.com/{url_path}.

    Paginação WordPress: {base_url}/page/{N}

    Retorna lista de (part_number, source_url).

    Estratégia de resiliência (em ordem):
      1. curl_cffi (TLS Chrome) — rápido, sem browser overhead
      2. Playwright — ativado automaticamente se curl_cffi retornar:
           a) None (timeout / conexão recusada)
           b) Cloudflare JS challenge (status 200 mas sem conteúdo real)
           c) Página com < 3 PNs na pág 1 (CF bypass parcial ou JS-rendered)
    """
    base_url = f"https://www.preduo.com/{url_path}"
    results: list[tuple[str, str]] = []

    # fetch_fn: começa com curl_cffi, pode ser trocada para Playwright
    def _curl_fetch(u: str):
        return _fetch(u, session)

    fetch_fn = _curl_fetch
    using_playwright = False

    def _activate_playwright(reason: str) -> bool:
        """Ativa Playwright e tenta buscar page_1_url novamente."""
        nonlocal fetch_fn, using_playwright
        if not use_playwright or using_playwright:
            return False
        msg = f"\n    ↳ {key}: {reason} — ativando Playwright (5s wait)..."
        if log_fn:
            log_fn(msg)
        else:
            logger.info(msg)
        fetch_fn = lambda u: _fetch_playwright(u, wait_ms=5000, headless=headless)
        using_playwright = True
        return True

    # Threshold mínimo de PNs para considerar uma página válida.
    # CF challenge pages geralmente retornam 0-2 tokens que passam o filtro
    # (Ray ID, session tokens) — uma listagem real tem dezenas ou centenas.
    _MIN_PNS_REAL_PAGE = 3

    for page_num in range(1, max_pages + 1):
        # WordPress pagination: /page/N suffix
        url = base_url if page_num == 1 else f"{base_url}/page/{page_num}"

        soup = fetch_fn(url)

        # ── Fallbacks na página 1 ─────────────────────────────────────────────
        if page_num == 1 and not using_playwright:
            page_pns = _extract_pns(soup.get_text(" ", strip=True)) if soup else []

            needs_pw = (
                soup is None                          # A: sem resposta
                or _is_cf_challenge(soup)             # B: CF challenge detectado pelo markup
                or len(page_pns) < _MIN_PNS_REAL_PAGE # C: poucos tokens — CF não detectado
                                                      #    ou JS-rendered table
            )
            if needs_pw:
                reason = (
                    "curl_cffi retornou None" if soup is None
                    else "Cloudflare challenge detectado" if _is_cf_challenge(soup)
                    else f"poucos PNs ({len(page_pns)}) — CF não detectado ou JS table"
                )
                if _activate_playwright(reason):
                    soup = fetch_fn(url)

        if soup is None:
            if page_num == 1:
                logger.warning(
                    "  %s: sem resposta em nenhuma tentativa — pulando tipo", key
                )
            break

        text = soup.get_text(" ", strip=True)
        pns = _extract_pns(text)

        if not pns:
            if page_num == 1:
                logger.warning("  %s: página 1 sem PNs após todas as tentativas", key)
            break  # pág > 1 sem PNs = fim da paginação

        for pn in pns:
            results.append((pn, url))

        # Verifica próxima página — WordPress usa /page/N nos links
        has_next = bool(
            soup.find("a", string=_NEXT_RE) or
            soup.find("a", href=re.compile(r"/page/\d+"))
        )
        if not has_next:
            break

        time.sleep(delay)

    logger.info("  %s: %d PNs encontrados", key, len(results))
    return results


# ── Command ──────────────────────────────────────────────────────────────────

class _DryRunAbort(Exception):
    pass


class Command(BaseCommand):
    help = (
        "Raspa preduo.com e salva Part Numbers como KnownPart(status='raw', "
        "confidence='distributor'). Todos os tipos de chip suportados pelo Preduo."
    )

    def add_arguments(self, parser):
        valid_keys = [k for k, _, _, _ in PREDUO_CHIP_TYPES]
        valid_brands = sorted({b for _, b in BRAND_PREFIX_MAP})

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Exibe o que seria feito sem salvar nada no banco.",
        )
        parser.add_argument(
            "--type",
            action="append",
            dest="types",
            metavar="TIPO",
            choices=valid_keys,
            help=(
                f"Tipo(s) de chip a raspar. Pode repetir: --type eMCP --type eMMC. "
                f"Tipos disponíveis: {', '.join(valid_keys)}"
            ),
        )
        parser.add_argument(
            "--brand",
            dest="brand",
            metavar="MARCA",
            help=(
                f"Filtra apenas PNs inferidos como desta marca. "
                f"Marcas: {', '.join(valid_brands)}"
            ),
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help=(
                "Atualiza KnownParts já existentes com os dados do Preduo "
                "(só se status=raw e confidence <= distributor)."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            metavar="N",
            help="Limita o total de registros novos salvos (0 = sem limite).",
        )
        parser.add_argument(
            "--max-pages",
            type=int,
            default=100,
            metavar="N",
            help="Número máximo de páginas por tipo de chip (padrão: 100).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=2.0,
            metavar="SEG",
            help="Pausa em segundos entre requests (padrão: 2.0).",
        )
        parser.add_argument(
            "--no-playwright",
            action="store_true",
            help="Desabilita o fallback Playwright mesmo se instalado.",
        )
        parser.add_argument(
            "--show-browser",
            action="store_true",
            help=(
                "Roda o Playwright em modo não-headless (janela visível). "
                "Melhor bypass do Cloudflare Bot Management. "
                "Exige display (macOS/Linux com GUI)."
            ),
        )

    def handle(self, *args, **options):
        import atexit
        atexit.register(_pw_close)

        dry        = options["dry_run"]
        overwrite  = options["overwrite"]
        limit      = options["limit"]
        max_pages  = options["max_pages"]
        delay      = options["delay"]
        brand_filter = options.get("brand")
        use_playwright = not options["no_playwright"]
        headless = not options.get("show_browser", False)

        # Determina quais tipos raspar
        selected_types = options.get("types") or None
        if selected_types:
            chip_types = [t for t in PREDUO_CHIP_TYPES if t[0] in selected_types]
        else:
            chip_types = list(PREDUO_CHIP_TYPES)

        if dry:
            self.stdout.write(self.style.WARNING(
                "⚠  DRY RUN — nenhuma alteração será salva.\n"
            ))

        self.stdout.write(
            f"Tipos a raspar: {', '.join(k for k, _, _, _ in chip_types)}\n"
            f"Brand filter: {brand_filter or '(todas)'}\n"
            f"Max páginas/tipo: {max_pages}  |  Delay: {delay}s  |  "
            f"Limit: {limit or '∞'}  |  Overwrite: {overwrite}\n"
        )

        # Verifica dependências
        try:
            from bs4 import BeautifulSoup  # noqa: F401
        except ImportError:
            raise CommandError(
                "beautifulsoup4 não instalado: pip install beautifulsoup4 lxml"
            )

        _playwright_ok = False
        if use_playwright:
            try:
                from playwright.sync_api import sync_playwright  # noqa: F401
                _playwright_ok = True
            except ImportError:
                self.stdout.write(self.style.WARNING(
                    "  ℹ  Playwright não instalado — sem fallback para JS challenges.\n"
                    "     Para instalar: pip install playwright && playwright install chromium\n"
                ))

        session = _make_session()
        cffi_available = getattr(session, "_is_cffi", False)
        if not cffi_available:
            self.stdout.write(self.style.WARNING(
                "  ℹ  curl_cffi não instalado — usando requests padrão.\n"
                "     Para instalar: pip install curl_cffi\n"
            ))

        # ── Coleta todos os PNs do Preduo ────────────────────────────────────
        # raw_entries: list de (pn, chip_type, subtype, source_url)
        raw_entries: list[tuple[str, str, str, str]] = []

        for key, url_path, chip_type, subtype in chip_types:
            self.stdout.write(f"\n▶  Raspando {key} ({url_path}) ...", ending="")
            self.stdout.flush()

            page_results = _scrape_preduo_list(
                key=key,
                url_path=url_path,
                session=session,
                max_pages=max_pages,
                delay=delay,
                use_playwright=_playwright_ok and use_playwright,
                headless=headless,
                log_fn=self.stdout.write,
            )

            count = 0
            brand_counts: dict[str, int] = {}
            for pn, src_url in page_results:
                inferred = _infer_brand(pn)
                brand_counts[inferred or "?"] = brand_counts.get(inferred or "?", 0) + 1
                if brand_filter and inferred != brand_filter:
                    continue
                raw_entries.append((pn, chip_type, subtype, src_url))
                count += 1

            total_for_type = len(page_results)
            if brand_filter and total_for_type > 0:
                # Mostra breakdown por marca para diagnóstico
                top = sorted(brand_counts.items(), key=lambda x: -x[1])[:5]
                brands_str = "  ".join(f"{b}:{n}" for b, n in top)
                self.stdout.write(
                    f" {count} PNs {brand_filter}  "
                    f"(total: {total_for_type} — marcas: {brands_str})"
                )
            else:
                self.stdout.write(f" {count} PNs")
            time.sleep(delay)

        # Remove duplicatas (mantém primeira ocorrência de cada PN)
        seen_pns: dict[str, tuple[str, str, str]] = {}
        for pn, chip_type, subtype, src_url in raw_entries:
            if pn not in seen_pns:
                seen_pns[pn] = (chip_type, subtype, src_url)

        total_unique = len(seen_pns)
        self.stdout.write(f"\n\nTotal PNs únicos coletados: {total_unique}")

        if total_unique == 0:
            self.stdout.write(self.style.WARNING(
                "\n⚠  Nenhum PN coletado. Causas prováveis:\n"
                "   1. Cloudflare JS challenge ativo → instale Playwright\n"
                "   2. Estrutura do site mudou → verifique manualmente\n"
                "   3. Filtro --brand muito restritivo\n"
            ))
            return

        # ── Salva no banco ────────────────────────────────────────────────────
        try:
            with transaction.atomic():
                counts = self._save_to_db(
                    seen_pns=seen_pns,
                    dry=dry,
                    overwrite=overwrite,
                    limit=limit,
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
            f"   PNs sem marca reconhecida:    {counts['no_brand']}\n"
        ))

        # Invalida cache do engine
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            self.stdout.write("   🗑  Cache do engine invalidado.")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))

    def _save_to_db(
        self,
        seen_pns: dict[str, tuple[str, str, str]],
        dry: bool,
        overwrite: bool,
        limit: int,
    ) -> dict[str, int]:
        """
        Salva os PNs coletados no banco.
        Retorna contagens: created, updated, skipped, no_brand.
        """
        from chips.models import Brand, KnownPart, Source

        counts = {"created": 0, "updated": 0, "skipped": 0, "no_brand": 0}

        # Cria (ou busca) o Source Preduo
        if not dry:
            preduo_source, _ = Source.objects.get_or_create(
                name="Preduo",
                src_type="scraper",
                defaults={"url": "https://www.preduo.com"},
            )
        else:
            preduo_source = None

        # Cache de Brand objects para evitar N queries
        _brand_cache: dict[str, Brand] = {}

        def _get_brand(brand_name: str) -> Brand | None:
            if brand_name in _brand_cache:
                return _brand_cache[brand_name]
            if dry:
                # Em dry-run não acessa o banco
                _brand_cache[brand_name] = None  # type: ignore[assignment]
                return None
            brand_code = BRAND_CODE_MAP.get(brand_name, brand_name[:3].upper())
            brand_obj, _ = Brand.objects.get_or_create(
                name=brand_name,
                defaults={"code": brand_code},
            )
            _brand_cache[brand_name] = brand_obj
            return brand_obj

        # Confidência alvo: qualquer KnownPart com confidência <= distributor
        # pode ser atualizado com --overwrite.
        # Ordem de precedência (menor = mais confiável):
        CONFIDENCE_ORDER = {
            "confirmed": 0, "manual": 1, "distributor": 2,
            "ai_high": 3, "ai_medium": 4, "ai_low": 5, "estimated": 6,
        }
        TARGET_CONFIDENCE = "distributor"
        TARGET_CONFIDENCE_RANK = CONFIDENCE_ORDER[TARGET_CONFIDENCE]

        saved = 0
        for pn, (chip_type, subtype, src_url) in seen_pns.items():
            if limit and saved >= limit:
                break

            brand_name = _infer_brand(pn)
            if brand_name is None:
                counts["no_brand"] += 1
                if dry:
                    self.stdout.write(
                        self.style.WARNING(f"  [no_brand] {pn}  {chip_type}")
                    )
                continue

            brand_obj = _get_brand(brand_name)

            if dry:
                # Verifica se já existe sem tocar no banco
                exists = KnownPart.objects.filter(part_number=pn).exists()
                action = "UPDATE" if (exists and overwrite) else ("SKIP" if exists else "CREATE")
                style = (
                    self.style.SUCCESS if action == "CREATE"
                    else self.style.WARNING if action == "UPDATE"
                    else lambda x: x
                )
                self.stdout.write(style(
                    f"  [{action}] {pn:30s}  {brand_name:12s}  {chip_type}"
                    + (f" {subtype}" if subtype else "")
                ))
                if action == "CREATE":
                    counts["created"] += 1
                    saved += 1
                elif action == "UPDATE":
                    counts["updated"] += 1
                    saved += 1
                else:
                    counts["skipped"] += 1
                continue

            # ── Salva no banco ────────────────────────────────────────────────
            try:
                existing = KnownPart.objects.filter(part_number=pn).first()

                if existing is None:
                    KnownPart.objects.create(
                        brand=brand_obj,
                        part_number=pn,
                        chip_type=chip_type,
                        subtype=subtype,
                        status="raw",
                        confidence=TARGET_CONFIDENCE,
                        source=preduo_source,
                        source_url=src_url,
                    )
                    counts["created"] += 1
                    saved += 1

                elif overwrite:
                    existing_rank = CONFIDENCE_ORDER.get(existing.confidence, 99)
                    if existing_rank >= TARGET_CONFIDENCE_RANK:
                        # Só sobrescreve se não tivermos dados mais confiáveis
                        update_fields: list[str] = []

                        if not existing.chip_type and chip_type:
                            existing.chip_type = chip_type
                            update_fields.append("chip_type")
                        if not existing.subtype and subtype:
                            existing.subtype = subtype
                            update_fields.append("subtype")
                        if existing.confidence != TARGET_CONFIDENCE:
                            existing.confidence = TARGET_CONFIDENCE
                            update_fields.append("confidence")
                        if existing.source is None:
                            existing.source = preduo_source
                            update_fields.append("source")
                        if not existing.source_url and src_url:
                            existing.source_url = src_url
                            update_fields.append("source_url")

                        if update_fields:
                            update_fields.append("last_updated")
                            existing.save(update_fields=update_fields)
                            counts["updated"] += 1
                            saved += 1
                        else:
                            counts["skipped"] += 1
                    else:
                        counts["skipped"] += 1

                else:
                    counts["skipped"] += 1

            except Exception as e:
                logger.warning("Erro ao salvar PN %s: %s", pn, e)

        return counts
