"""
collect_datasheets.py — Stage 2: coleta chips Micron de datasheets PDF
======================================================================
Fluxo:
  1. Lê uma lista de URLs de datasheet (data/datasheet_urls.txt) gerada pelos
     stages 3/4, OU descobre PDFs via a API de produtos da Micron.
  2. Baixa cada PDF para cache local em data/datasheets/
  3. Usa pdfplumber para localizar a seção "Ordering Information"
  4. Extrai linhas de tabela com Part Number e/ou FBGA code
  5. Salva no banco como KnownPart com status='confirmed', confidence='confirmed'

Fontes de URLs:
  a) data/datasheet_urls.txt — uma URL por linha (gerado por collect_octopart,
     collect_preduo_bulk ou adicionado manualmente)
  b) API de categorias da Micron (mobile storage) — descoberta automática
  c) Argumento --url / --url-file na linha de comando

Dependência:
    pip install pdfplumber

Uso:
    python scripts/collect_datasheets.py
    python scripts/collect_datasheets.py --dry-run
    python scripts/collect_datasheets.py --url https://download.micron.com/.../ds.pdf
    python scripts/collect_datasheets.py --url-file data/datasheet_urls.txt
    python scripts/collect_datasheets.py --discover          # só descobre URLs, não baixa
    python scripts/collect_datasheets.py --limit 20 --delay 2
"""

import os
import re
import sys
import time
import json
import hashlib
import argparse
import logging
from pathlib import Path
from urllib.parse import urlparse, urljoin

# ── Setup Django ──────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)

# ── Constantes ────────────────────────────────────────────────────────────────

BASE_DIR     = Path(__file__).resolve().parent.parent
DATA_DIR     = BASE_DIR / "data"
DS_CACHE_DIR = DATA_DIR / "datasheets"
URL_QUEUE    = DATA_DIR / "datasheet_urls.txt"

DS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Headers para requests HTTP
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
}

# FBGA code: 5 chars alfanuméricos maiúsculos
_FBGA_RE = re.compile(r"\b([A-Z][A-Z0-9]{4}|[A-Z0-9]{5})\b")

# Padrões de PN Micron: MT[29|30|4A|52|53|...] ou D9xxx
_PN_RE = re.compile(
    r"\b(MT[0-9]{2}[A-Z0-9]{8,}|D9[A-Z0-9]{3,})\b",
    re.IGNORECASE,
)

# Palavras-chave para localizar a seção de ordering info no PDF
_ORDERING_HEADERS = re.compile(
    r"ordering\s+information|part\s+number\s+description|"
    r"valid\s+combinations|ordering\s+part\s+number",
    re.IGNORECASE,
)

# Palavras-chave de coluna que indicam FBGA
_FBGA_COL_RE = re.compile(r"fbga|marking|laser|code", re.IGNORECASE)

# URLs de categorias Micron para descoberta de datasheets.
#
# NOTA: micron.com é uma SPA React — as páginas de produto NÃO contêm
# links de PDF no HTML estático. A descoberta automática é limitada.
# Para adicionar PDFs manualmente, edite data/datasheet_seed_urls.txt
# (criado automaticamente na primeira execução com --discover).
#
# URLs que retornam HTML real com links de PDF (documentação técnica):
MICRON_PRODUCT_PAGES = [
    # eMMC — única categoria que ainda retorna HTML com algum conteúdo
    "https://www.micron.com/products/managed-nand/emmc",
    # Biblioteca de documentos técnicos (HTML estático com links)
    "https://www.micron.com/support/tools-and-utilities/fbga",
    "https://media-www.micron.com/media/document/",
    # Wayback Machine — arquivos de datasheet Micron pre-SPA (2015-2018)
    "https://web.archive.org/web/2017*/http://www.micron.com/~/media/documents/products/data-sheet/lpdram/",
    "https://web.archive.org/web/2017*/http://www.micron.com/~/media/documents/products/data-sheet/flash/",
]

# Padrão para extrair links de datasheet das páginas Micron.
# Cobre CDNs históricos e atuais da Micron:
#   download.micron.com   — CDN legado (pre-2018)
#   media-www.micron.com  — CDN atual para documentos
#   assets.micron.com     — CDN para assets de marketing
#   micron.com/content    — Dam/AEM interno
_PDF_LINK_RE = re.compile(
    r'https?://[^\s"\'<>]*'
    r'(?:download\.micron\.com|media-www\.micron\.com|assets\.micron\.com'
    r'|micron\.com/content|micron\.com/~/media)'
    r'[^\s"\'<>]*\.pdf',
    re.IGNORECASE,
)

# Arquivo de sementes — URLs de PDF curadas manualmente.
# Edite este arquivo para adicionar datasheets específicos.
SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "datasheet_seed_urls.txt"

_SEED_FILE_TEMPLATE = """\
# datasheet_seed_urls.txt — URLs de datasheets Micron para processar
# Uma URL por linha. Linhas com # são comentários.
#
# Como encontrar datasheets Micron eMCP/eMMC/LPDDR4:
#   1. Acesse https://www.micron.com/support/tools-and-utilities/fbga
#   2. Digite um PN base (ex: MT29VZZZAD8GQFSL) e clique em "Data Sheet"
#   3. Copie o URL do PDF e cole aqui
#
# Exemplos de URLs válidas (verifique disponibilidade):
# https://media-www.micron.com/media/document/data-sheet/...
#
# ── eMCP série MT29VZZZ ───────────────────────────────────────────────────────
# (adicione URLs encontradas via micron.com ou buscas web)
#
# ── eMMC série MTFC ──────────────────────────────────────────────────────────
# (adicione URLs encontradas via micron.com ou buscas web)
#
# ── LPDDR4 série MT53E ───────────────────────────────────────────────────────
# (adicione URLs encontradas via micron.com ou buscas web)
"""


# ── HTTP session ──────────────────────────────────────────────────────────────

def _make_session():
    """Prefere curl_cffi para bypass de bot detection."""
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


def _get(session, url: str, timeout: int = 30, stream: bool = False):
    """GET com retry simples."""
    for attempt in range(3):
        try:
            r = session.get(url, headers=_HEADERS, timeout=timeout, stream=stream)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 503):
                time.sleep(5 * (attempt + 1))
                continue
            logger.warning("HTTP %s: %s", r.status_code, url)
            return None
        except Exception as e:
            logger.warning("Erro (tentativa %d/3): %s — %s", attempt + 1, e, url)
            time.sleep(2 * (attempt + 1))
    return None


# ── Descoberta de datasheets ──────────────────────────────────────────────────

def _ensure_seed_file():
    """Cria o arquivo de sementes se ainda não existir."""
    if not SEED_FILE.exists():
        SEED_FILE.parent.mkdir(parents=True, exist_ok=True)
        SEED_FILE.write_text(_SEED_FILE_TEMPLATE)
        logger.info("Arquivo de sementes criado: %s", SEED_FILE)
        logger.info("Edite este arquivo para adicionar PDFs de datasheet.")


def _load_seed_urls() -> list[str]:
    """Lê URLs do arquivo de sementes (data/datasheet_seed_urls.txt)."""
    _ensure_seed_file()
    urls = []
    for line in SEED_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line.lower().endswith(".pdf"):
            urls.append(line)
    return urls


def discover_datasheet_urls(session, delay: float = 2.0) -> list[str]:
    """
    Vasculha as páginas de produto da Micron e extrai links de datasheet PDF.
    Também carrega URLs do arquivo de sementes (data/datasheet_seed_urls.txt).
    Retorna lista de URLs únicas.

    NOTA: micron.com é SPA React — a descoberta automática tem rendimento baixo.
    Para melhores resultados, adicione URLs diretamente em data/datasheet_seed_urls.txt.
    """
    found: set[str] = set()

    # 1. Carrega URLs do arquivo de sementes (curadas manualmente)
    seed_urls = _load_seed_urls()
    if seed_urls:
        logger.info("Seed file: %d URLs carregadas de %s", len(seed_urls), SEED_FILE)
        found.update(seed_urls)
    else:
        logger.info(
            "Seed file vazio. Adicione PDFs em: %s", SEED_FILE
        )

    # 2. Tenta descobrir PDFs nas páginas de produto Micron
    #    (rendimento baixo — Micron usa SPA, mas algumas páginas ainda têm links)
    scraped = 0
    for page_url in MICRON_PRODUCT_PAGES:
        # Pula URLs do Wayback Machine (são CDX queries, não páginas com PDF links)
        if "web.archive.org" in page_url:
            continue
        logger.info("Descobrindo datasheets em: %s", page_url)
        r = _get(session, page_url, timeout=20)
        if r is None:
            continue

        text = r.text
        pdfs = _PDF_LINK_RE.findall(text)
        for pdf_url in pdfs:
            found.add(pdf_url)
        if pdfs:
            scraped += len(pdfs)
            logger.info("  %d PDFs encontrados nesta página", len(pdfs))
        time.sleep(delay)

    if scraped == 0 and not seed_urls:
        logger.warning(
            "Nenhum PDF encontrado via scraping nem no seed file.\n"
            "  → Adicione URLs de datasheet em: %s\n"
            "  → Exemplo: python scripts/collect_datasheets.py "
            "--url https://media-www.micron.com/.../ds.pdf",
            SEED_FILE,
        )

    return sorted(found)


def load_url_queue(url_file: Path) -> list[str]:
    """Lê URLs do arquivo de fila (uma por linha, comentários com #)."""
    if not url_file.exists():
        return []
    urls = []
    for line in url_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def save_url_queue(url_file: Path, urls: list[str]):
    """Salva/atualiza a fila de URLs (preserva linhas de comentário existentes)."""
    existing: set[str] = set()
    lines: list[str] = []

    if url_file.exists():
        for line in url_file.read_text().splitlines():
            lines.append(line)
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                existing.add(stripped)

    new_urls = [u for u in urls if u not in existing]
    if new_urls:
        lines.append("")
        lines.append(f"# Adicionado automaticamente ({len(new_urls)} URLs)")
        lines.extend(new_urls)
        url_file.write_text("\n".join(lines) + "\n")
        logger.info("Adicionadas %d URLs novas à fila: %s", len(new_urls), url_file)
    else:
        logger.info("Nenhuma URL nova para adicionar à fila.")


# ── Download e cache de PDFs ──────────────────────────────────────────────────

def _pdf_cache_path(url: str) -> Path:
    """Gera caminho de cache baseado no hash da URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    filename  = Path(urlparse(url).path).name or f"{url_hash}.pdf"
    # Preserva nome original + hash para evitar colisões
    stem = Path(filename).stem[:40]
    return DS_CACHE_DIR / f"{stem}_{url_hash}.pdf"


def download_pdf(session, url: str, delay: float = 1.0) -> Path | None:
    """
    Baixa um PDF para cache local.
    Retorna o Path do arquivo baixado (ou do cache existente).
    """
    cache_path = _pdf_cache_path(url)

    if cache_path.exists() and cache_path.stat().st_size > 1024:
        logger.debug("Cache hit: %s", cache_path.name)
        return cache_path

    logger.info("Baixando: %s", url)
    r = _get(session, url, timeout=60, stream=True)
    if r is None:
        return None

    # Verifica se é realmente um PDF
    content_type = r.headers.get("content-type", "")
    if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
        logger.warning("Não é PDF (content-type: %s): %s", content_type, url)
        return None

    try:
        data = r.content
        if len(data) < 1024:
            logger.warning("PDF muito pequeno (%d bytes), pulando: %s", len(data), url)
            return None
        cache_path.write_bytes(data)
        logger.info("  Salvo: %s (%d KB)", cache_path.name, len(data) // 1024)
        time.sleep(delay)
        return cache_path
    except Exception as e:
        logger.warning("Erro ao salvar PDF %s: %s", url, e)
        return None


# ── Extração de dados do PDF ──────────────────────────────────────────────────

def extract_chips_from_pdf(pdf_path: Path, source_url: str) -> list[dict]:
    """
    Extrai Part Numbers e FBGA codes de um datasheet Micron.

    Estratégia:
    1. Varre todas as páginas procurando tabelas com cabeçalho "Ordering Information"
    2. Para cada tabela candidata, identifica colunas de PN e FBGA
    3. Extrai pares (part_number, fbga_code) de cada linha

    Retorna lista de dicts:
      {"part_number": "MT29...", "fbga_code": "JWB11" ou "", "source_url": url}
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber não instalado: pip install pdfplumber")
        return []

    results: list[dict] = []
    seen_pns: set[str] = set()

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            in_ordering_section = False

            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""

                # Detecta início da seção Ordering Information
                if _ORDERING_HEADERS.search(text):
                    in_ordering_section = True

                # Fim da seção (próxima seção principal)
                if in_ordering_section and re.search(
                    r"^(?:Notes?|Electrical|Mechanical|Absolute|Timing|Signal|Pin|Ball|"
                    r"Package|Revision|References?)\b",
                    text, re.MULTILINE | re.IGNORECASE
                ) and page_num > 1:
                    # Continua — pode ser só um cabeçalho de página
                    pass

                if not in_ordering_section:
                    # Mesmo fora da seção, procura padrões de PN + FBGA em texto livre
                    _extract_from_text(text, source_url, results, seen_pns)
                    continue

                # ── Extração via tabelas ──────────────────────────────────────
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    _extract_from_table(table, source_url, results, seen_pns)

                # ── Extração via texto livre (fallback) ───────────────────────
                _extract_from_text(text, source_url, results, seen_pns)

    except Exception as e:
        logger.warning("Erro ao processar PDF %s: %s", pdf_path.name, e)

    return results


def _extract_from_table(
    table: list[list],
    source_url: str,
    results: list[dict],
    seen_pns: set[str],
):
    """
    Extrai pares (PN, FBGA) de uma tabela pdfplumber.

    Formato esperado de tabela Micron:
      | Part Number          | FBGA Code | Density | ...
      | MT29VZZZAD8GQFSL-046 | JY941     | 544Gb   | ...
    """
    if not table:
        return

    headers = [str(c or "").strip() for c in table[0]]

    # Identifica índices das colunas relevantes
    pn_col   = _find_col(headers, [r"part\s*number", r"ordering\s*pn", r"^pn$", r"^mpn$"])
    fbga_col = _find_col(headers, [r"fbga", r"code\s*marking", r"laser\s*mark"])

    # Se não achou cabeçalho de PN, tenta na segunda linha (alguns PDFs mesclam)
    if pn_col is None and len(table) > 1:
        alt_headers = [str(c or "").strip() for c in table[1]]
        pn_col   = _find_col(alt_headers, [r"part\s*number", r"^pn$"])
        fbga_col = _find_col(alt_headers, [r"fbga", r"code"])
        data_start = 2
    else:
        data_start = 1

    for row in table[data_start:]:
        if not row:
            continue
        cells = [str(c or "").strip() for c in row]

        pn   = cells[pn_col].upper()   if pn_col   is not None and pn_col   < len(cells) else ""
        fbga = cells[fbga_col].upper() if fbga_col is not None and fbga_col < len(cells) else ""

        # Fallback: varre todas as células procurando padrões
        if not pn:
            for cell in cells:
                m = _PN_RE.match(cell.strip())
                if m:
                    pn = m.group(0).upper()
                    break

        if not fbga:
            for cell in cells:
                m = _FBGA_RE.match(cell.strip())
                if m and len(cell.strip()) == 5:
                    fbga = cell.strip().upper()
                    break

        # Limpa PN (remove sufixos de temperatura/package após espaço ou tab)
        pn = re.split(r"\s{2,}|\t", pn)[0].strip()

        if not _PN_RE.match(pn):
            continue
        if pn in seen_pns:
            continue

        seen_pns.add(pn)
        results.append({
            "part_number": pn,
            "fbga_code": fbga if (fbga and _FBGA_RE.match(fbga) and len(fbga) == 5) else "",
            "source_url": source_url,
        })


def _extract_from_text(
    text: str,
    source_url: str,
    results: list[dict],
    seen_pns: set[str],
):
    """
    Extração de texto livre: encontra PNs e FBGAs próximos um do outro.
    Menos confiável que extração por tabela — usado como fallback.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        pn_match = _PN_RE.search(line)
        if not pn_match:
            continue
        pn = pn_match.group(0).upper()
        if pn in seen_pns:
            continue

        # Procura FBGA na mesma linha ou nas 2 próximas
        fbga = ""
        context = " ".join(lines[max(0, i-1):min(len(lines), i+3)])
        fbga_candidates = _FBGA_RE.findall(context)
        for candidate in fbga_candidates:
            # FBGA começa com J (eMMC/eMCP) ou D9 (DRAM) ou similar
            if len(candidate) == 5 and candidate[0] in "JDN":
                fbga = candidate
                break

        seen_pns.add(pn)
        results.append({
            "part_number": pn,
            "fbga_code": fbga,
            "source_url": source_url,
        })


def _find_col(headers: list[str], patterns: list[str]) -> int | None:
    """Retorna o índice da primeira coluna que corresponde a algum padrão."""
    for pattern in patterns:
        rx = re.compile(pattern, re.IGNORECASE)
        for i, h in enumerate(headers):
            if rx.search(h):
                return i
    return None


# ── Inferência de chip_type a partir do PN Micron ────────────────────────────

def _infer_chip_type(pn: str) -> tuple[str, str]:
    """
    Retorna (chip_type, subtype) inferido do PN Micron.
    Fallback: ("Flash", "")

    Convenção de prefixos Micron:
      MT29VZZZ* → eMCP LPDDR4 (eMMC 5.1 + RAM)
      MT30AZZZ* → uMCP LPDDR5 (UFS 3.1 + RAM)
      MTFC* / MTFD* → eMMC (iNAND managed NAND — ex: MTFC8GACAJCN)
      MT29P*  → UFS storage
      MT53B/D/E* → LPDDR4
      MT62*/MT63*/MT64* → LPDDR5
      MT52L/F* → LPDDR3
      MT29F* / MT29S* → NAND Flash (raw NAND, NÃO eMMC)
      D9xxx   → DRAM mobile (código FBGA density)
    """
    pn = pn.upper()

    # eMCP / uMCP (ordem importa — antes de qualquer MT29/MT30 genérico)
    if pn.startswith("MT29VZZZ"):
        return ("eMCP", "LPDDR4")
    if pn.startswith("MT30AZZZ"):
        return ("uMCP", "LPDDR5")

    # eMMC iNAND Micron — prefixo MTFC ou MTFD (ex: MTFC8GACAJCN)
    if re.match(r"MT[FC][A-Z]", pn):
        return ("eMMC", "")

    # UFS — MT29P...
    if pn.startswith("MT29P"):
        return ("UFS", "")

    # LPDDR4 — MT53B..., MT53E..., MT53D...
    if re.match(r"MT53[BDED]", pn):
        return ("DRAM", "LPDDR4")

    # LPDDR5 — MT62F..., MT62J..., MT63*, MT64*
    if re.match(r"MT6[2-4]", pn):
        return ("DRAM", "LPDDR5")

    # LPDDR3 — MT52L..., MT52F...
    if re.match(r"MT52[LF]", pn):
        return ("DRAM", "LPDDR3")

    # NAND Flash — MT29F* / MT29S* (raw NAND, não managed)
    if re.match(r"MT29[FS]", pn):
        return ("NAND", "")

    # DRAM mobile D9xxx (código de densidade FBGA)
    if re.match(r"D9[A-Z0-9]{3}", pn):
        return ("DRAM", "")

    return ("Flash", "")


# ── Persistência no banco ─────────────────────────────────────────────────────

def save_chips_to_db(
    chips: list[dict],
    source_name: str,
    dry: bool,
    overwrite: bool,
) -> dict[str, int]:
    """
    Salva chips extraídos de datasheets no banco.
    confidence=confirmed pois a fonte é o datasheet oficial.
    """
    from chips.models import Brand, KnownPart, Source

    CONFIDENCE_ORDER = {
        "confirmed": 0, "manual": 1, "distributor": 2,
        "ai_high": 3, "ai_medium": 4, "ai_low": 5, "estimated": 6,
    }
    MY_CONFIDENCE      = "confirmed"
    MY_CONFIDENCE_RANK = CONFIDENCE_ORDER[MY_CONFIDENCE]

    counts = {"created": 0, "updated": 0, "skipped": 0, "no_brand": 0}

    if dry:
        micron_source = None
        micron_brand  = None
    else:
        micron_brand, _ = Brand.objects.get_or_create(
            name="Micron",
            defaults={"code": "MIC", "notes": "Micron Technology"},
        )
        micron_source, _ = Source.objects.get_or_create(
            name=source_name,
            defaults={"src_type": "datasheet", "url": "https://www.micron.com"},
        )

    for chip in chips:
        pn       = chip["part_number"]
        fbga     = chip.get("fbga_code", "") or ""
        src_url  = chip.get("source_url", "")

        # Só importa PNs Micron
        if not re.match(r"MT[0-9]{2}|D9[A-Z0-9]{3}", pn.upper()):
            counts["no_brand"] += 1
            continue

        chip_type, subtype = _infer_chip_type(pn)

        if dry:
            exists = KnownPart.objects.filter(part_number=pn).exists()
            action = "UPDATE" if (exists and overwrite) else ("SKIP" if exists else "CREATE")
            print(
                f"  [{action:6s}] {pn:40s}  fbga={fbga or '-':6s}  {chip_type}"
                + (f" {subtype}" if subtype else "")
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
                    chip_type=chip_type,
                    subtype=subtype,
                    status="confirmed",
                    confidence=MY_CONFIDENCE,
                    source=micron_source,
                    source_url=src_url,
                )
                counts["created"] += 1

            elif overwrite:
                existing_rank = CONFIDENCE_ORDER.get(existing.confidence, 99)
                if existing_rank >= MY_CONFIDENCE_RANK:
                    update_fields: list[str] = []
                    if fbga and not existing.fbga_code:
                        existing.fbga_code = fbga
                        update_fields.append("fbga_code")
                    if not existing.chip_type and chip_type:
                        existing.chip_type = chip_type
                        update_fields.append("chip_type")
                    if not existing.subtype and subtype:
                        existing.subtype = subtype
                        update_fields.append("subtype")
                    if existing.confidence != MY_CONFIDENCE:
                        existing.confidence = MY_CONFIDENCE
                        update_fields.append("confidence")
                    if not existing.source_url and src_url:
                        existing.source_url = src_url
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

    return counts


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Stage 2: coleta chips Micron de datasheets PDF."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Exibe o que seria feito sem salvar.")
    parser.add_argument("--discover", action="store_true",
                        help="Apenas descobre URLs de datasheet e salva na fila, sem baixar.")
    parser.add_argument("--url", metavar="URL", action="append", default=[],
                        help="URL de datasheet específico (pode repetir).")
    parser.add_argument("--url-file", metavar="ARQUIVO", default=None,
                        help="Arquivo com URLs de datasheet (padrão: data/datasheet_urls.txt).")
    parser.add_argument("--overwrite", action="store_true",
                        help="Atualiza KnownParts existentes se confidence <= confirmed.")
    parser.add_argument("--limit", type=int, default=0, metavar="N",
                        help="Processa no máximo N PDFs (0 = sem limite).")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Pausa em segundos entre downloads (padrão: 2.0).")
    parser.add_argument("--no-discover", action="store_true",
                        help="Não faz descoberta automática de URLs — usa apenas lista explícita.")
    args = parser.parse_args()

    dry = args.dry_run
    if dry:
        print("⚠  DRY RUN — nenhuma alteração será salva.\n")

    # Verifica pdfplumber
    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        print("❌  pdfplumber não instalado: pip install pdfplumber")
        sys.exit(1)

    session = _make_session()
    if not getattr(session, "_is_cffi", False):
        print("ℹ  curl_cffi não disponível — usando requests padrão.")

    # ── Coleta URLs ────────────────────────────────────────────────────────────

    all_urls: list[str] = list(args.url)

    # Arquivo de fila explícito ou padrão
    url_file = Path(args.url_file) if args.url_file else URL_QUEUE
    queue_urls = load_url_queue(url_file)
    all_urls.extend(queue_urls)
    print(f"URLs da fila ({url_file.name}): {len(queue_urls)}")

    # Descoberta automática (via páginas de produto Micron)
    if not args.no_discover:
        print("\nDescoberta automática de datasheets em micron.com ...")
        discovered = discover_datasheet_urls(session, delay=args.delay)
        print(f"  {len(discovered)} URLs descobertas")
        all_urls.extend(discovered)

        if not dry:
            save_url_queue(url_file, discovered)

    # Remove duplicatas mantendo ordem
    seen_urls: set[str] = set()
    unique_urls: list[str] = []
    for u in all_urls:
        if u not in seen_urls and u.lower().endswith(".pdf"):
            seen_urls.add(u)
            unique_urls.append(u)

    print(f"\nTotal de URLs únicas a processar: {len(unique_urls)}")

    if args.discover:
        print("--discover ativo — URLs salvas, saindo sem baixar PDFs.")
        return

    if args.limit:
        unique_urls = unique_urls[:args.limit]
        print(f"  (limitado a {args.limit})")

    if not unique_urls:
        print("\n⚠  Nenhuma URL de datasheet encontrada.")
        print("   Opções:")
        print("   1. Rode --discover para popular a fila automaticamente")
        print("   2. Passe --url <URL> explicitamente")
        print(f"   3. Adicione URLs em {url_file}")
        return

    # ── Processa PDFs ─────────────────────────────────────────────────────────

    total_chips: list[dict] = []
    processed = 0

    for i, url in enumerate(unique_urls, 1):
        print(f"\n[{i}/{len(unique_urls)}] {url}")

        pdf_path = download_pdf(session, url, delay=args.delay)
        if pdf_path is None:
            print("  ⚠  Falha no download, pulando.")
            continue

        chips = extract_chips_from_pdf(pdf_path, source_url=url)
        print(f"  {len(chips)} chips extraídos do PDF")

        total_chips.extend(chips)
        processed += 1
        time.sleep(args.delay)

    print(f"\n\nTotal de chips extraídos: {len(total_chips)}  (de {processed} PDFs)")

    if not total_chips:
        print("Nada para salvar.")
        return

    # ── Salva no banco ─────────────────────────────────────────────────────────

    counts = save_chips_to_db(
        chips=total_chips,
        source_name="Micron Datasheet",
        dry=dry,
        overwrite=args.overwrite,
    )

    print(
        f"\n{'[DRY RUN] ' if dry else ''}Resultado:\n"
        f"  Criados:      {counts['created']}\n"
        f"  Atualizados:  {counts['updated']}\n"
        f"  Pulados:      {counts['skipped']}\n"
        f"  Sem marca:    {counts['no_brand']}\n"
    )

    if dry:
        print("⚠  DRY RUN — nenhuma alteração foi salva.")
        return

    # Invalida cache do engine
    try:
        from chips.engine import clear_engine_cache
        clear_engine_cache()
        print("🗑  Cache do engine invalidado.")
    except Exception as e:
        print(f"⚠  Cache não invalidado: {e}")


if __name__ == "__main__":
    main()
