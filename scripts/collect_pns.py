#!/usr/bin/env python3
"""
collect_pns.py — Coletor Robusto de Part Numbers
==================================================
Coleta PNs de múltiplas fontes web e salva em state/{brand}_pns.json.
Suporta todas as gerações: SDRAM, DDR, DDR2, DDR3, DDR4, DDR5, eMMC, UFS,
LPDDR (todas as versões), eMCP, NOR Flash, SRAM, SoC/CPU.

Marcas suportadas:
  Memória:    Samsung, SK Hynix, Micron, KIOXIA, Elpida, Nanya, Kingston, SanDisk
  Discretos:  ISSI, Rayson, GigaDevice
  SoC/CPU:    Qualcomm, MediaTek, Spreadtrum

Uso (de dentro do chipdocs/):
  python scripts/collect_pns.py --brand Samsung
  python scripts/collect_pns.py --brand Samsung --force
  python scripts/collect_pns.py --brand Samsung --sources preduo,glochip
  python scripts/collect_pns.py --list-sources
  python scripts/collect_pns.py --list-brands

Saída: scripts/state/{Brand}_pns.json
Log:   scripts/logs/{Brand}_collect.log
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote as _url_quote

# ── HTTP client: curl_cffi com TLS impersonation ──────────────────────────────
#
# curl_cffi replica o TLS fingerprint do Chrome — primeira linha de defesa
# contra bot-detection baseado em TLS (wolfchip, alldatasheet, parte do glochip).
# Fallback para requests padrão se não estiver instalado.
#
# Instalação: pip install curl_cffi
#
try:
    from curl_cffi import requests
    from curl_cffi.requests import Session as CurlSession
    _CURL_AVAILABLE = True
except ImportError:
    import requests
    CurlSession = None
    _CURL_AVAILABLE = False

# ── Playwright: browser real para JS challenges (Cloudflare Bot Management) ───
#
# Sites como glochip.com e preduo.com usam Cloudflare JS challenge — retornam
# uma página que requer execução de JavaScript para liberar o conteúdo real.
# curl_cffi não resolve isso; só um browser completo resolve.
#
# Playwright mantém uma instância do Chromium reutilizável durante toda a execução
# do script (não abre/fecha um browser por request — isso seria muito lento).
#
# Instalação (uma vez por máquina):
#   pip install playwright
#   playwright install chromium
#
# Sem Playwright: fontes afetadas tentam curl_cffi e, se falharem, retornam 0.
# O wayback machine é o backup principal nesses casos.
#
# ╔═══════════════════════════════════════════════════════════════╗
# ║  Para adicionar suporte Playwright a uma nova fonte:          ║
# ║  1. Implemente _source_NOME_playwright(brand) usando          ║
# ║     get_browser(url) em vez de get(url, session)              ║
# ║  2. Adicione fallback no final de source_NOME() existente     ║
# ║     if not result and _PLAYWRIGHT_AVAILABLE: ...              ║
# ╚═══════════════════════════════════════════════════════════════╝
#
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

import atexit

# Instância global reutilizável — iniciada na primeira chamada, fechada no exit
_pw_instance  = None
_pw_browser   = None


def _pw_browser_get() -> object:
    """Retorna o browser Playwright, iniciando-o se necessário."""
    global _pw_instance, _pw_browser
    if not _PLAYWRIGHT_AVAILABLE:
        return None
    if _pw_browser is None:
        _pw_instance = sync_playwright().start()
        _pw_browser  = _pw_instance.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        logging.info("  [Playwright] Browser Chromium iniciado")
    return _pw_browser


def _pw_close():
    """Fecha o browser Playwright ao sair do script."""
    global _pw_instance, _pw_browser
    if _pw_browser:
        try:
            _pw_browser.close()
        except Exception:
            pass
        _pw_browser = None
    if _pw_instance:
        try:
            _pw_instance.stop()
        except Exception:
            pass
        _pw_instance = None


atexit.register(_pw_close)


def get_browser(url: str, wait_ms: int = 2500) -> "BeautifulSoup | None":
    """
    Busca uma URL usando Playwright (Chromium real).

    Resolve JS challenges do Cloudflare e páginas com renderização client-side —
    casos onde curl_cffi falha com timeout ou connection reset.

    wait_ms: tempo de espera após o carregamento inicial para o JS renderizar.
             Aumente para 4000-5000 em sites mais lentos.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        return None
    browser = _pw_browser_get()
    if not browser:
        return None
    ctx = None
    try:
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        page = ctx.new_page()
        # Esconde que é Playwright (remove navigator.webdriver)
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page.goto(url, wait_until="domcontentloaded", timeout=35000)
        page.wait_for_timeout(wait_ms)
        html = page.content()
        return BeautifulSoup(html, "lxml")
    except Exception as e:
        logging.warning(f"    [Playwright] Erro em {url}: {e}")
        return None
    finally:
        if ctx:
            try:
                ctx.close()
            except Exception:
                pass


from bs4 import BeautifulSoup

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent   # chipdocs/
SCRIPTS_DIR = Path(__file__).resolve().parent
STATE_DIR   = SCRIPTS_DIR / "state"
LOGS_DIR    = SCRIPTS_DIR / "logs"
STATE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

DELAY = 2.0   # segundos entre requests

# ── PN validation ─────────────────────────────────────────────────────────────
#
# FILOSOFIA DO COLETOR:
# A coleta deve ser AMPLA — o objetivo é não perder nenhum PN válido.
# Identificar a família exata (KLMxxx = eMMC, KMRxxx = eMCP) é trabalho
# do CLASSIFICADOR (engine.py).
#
# Aqui só perguntamos: "esse token parece ser um PN desta marca?"
# Critérios: começa com o prefixo certo + tem pelo menos um dígito +
# comprimento razoável + não é uma palavra conhecida.
#
# ADICIONANDO UMA NOVA MARCA:
# 1. Adicione a marca em BRAND_LETTERS com seus prefixos conhecidos
# 2. Se houver conflito com outra marca (ex: MT é Samsung E MediaTek),
#    adicione os prefixos conflitantes em BRAND_EXCLUSIONS da marca mais genérica
# 3. Isso é tudo que o coletor precisa — o engine.py cuida do resto
#

BRAND_LETTERS: dict[str, tuple[str, ...]] = {
    # ── Memória ───────────────────────────────────────────────────────────────
    # Samsung: todos os chips de memória começam com K
    # (KM* = eMCP, KL* = eMMC/UFS, K4* = LPDDR4/DDR4, K3* = LPDDR5, etc.)
    "Samsung":    ("K",),

    # SK Hynix: H8*, H9*, HM*, HY* (LPDDR/eMMC/UFS)
    "SK Hynix":   ("H8", "H9", "HM", "HY"),

    # Micron: MT* (nota: MT6/MT8 são MediaTek — ver BRAND_EXCLUSIONS)
    # NW* = Numonyx legado, D9* = código interno DDR
    "Micron":     ("MT", "NW", "D9"),

    # KIOXIA / Toshiba Memory: TH* e TC*
    "KIOXIA":     ("TH", "TC"),

    # Elpida: EB* (LPDDR mobile) e ED* (DDR3)
    "Elpida":     ("EB", "ED"),

    # Nanya: NT* (DDR3/DDR4/LPDDR)
    "Nanya":      ("NT",),

    # Kingston: prefixos específicos K* que NÃO são Samsung
    "Kingston":   ("KVR", "KHX", "KSM", "KCP"),

    # SanDisk / Western Digital: SD* (iNAND eMMC, microSD, etc.)
    "SanDisk":    ("SD",),

    # ── Discretos ─────────────────────────────────────────────────────────────
    "ISSI":       ("IS",),
    "Rayson":     ("RS", "EM"),
    "GigaDevice": ("GD",),

    # ── SoC / CPU ─────────────────────────────────────────────────────────────
    # Qualcomm: SM* (Snapdragon), MSM* (legacy), APQ*, SDM*, QM*
    "Qualcomm":   ("SM", "MSM", "APQ", "SDM", "QM"),

    # MediaTek: MT6* e MT8* (específico para não conflitar com Micron MT*)
    "MediaTek":   ("MT6", "MT8"),

    # Spreadtrum / Unisoc: SC*, UMS*, T3*/T6*/T7* (SoCs)
    "Spreadtrum": ("SC", "UMS"),
}

# Prefixos a EXCLUIR para marcas específicas — resolve conflitos de namespace.
# Ex: "MT" é Micron, mas "MT6" e "MT8" são MediaTek.
#     "K" é Samsung, mas "KVR", "KHX", "KSM", "KCP" são Kingston.
BRAND_EXCLUSIONS: dict[str, tuple[str, ...]] = {
    # Samsung: prefixos K* que NÃO são chips de memória Samsung
    "Samsung": (
        # ── Kingston (usa K*) ─────────────────────────────────────────────
        "KVR", "KHX", "KSM", "KCP", "KIN",
        # ── Conectores / passivos (aparecem no findchips junto com Samsung) ─
        "KF2",          # Molex/EDAC connectors (KF2EDGRKM…)
        "KBU",          # bridge rectifiers (KBU6KM3P…)
        "KFR", "KFK",   # relés/outros (KFRKM50, KFKM50…)
        # ── LEDs Kingbright (prefixo KP*) ────────────────────────────────
        "KPB", "KPK", "KPT", "KPH", "KP2",
        # ── Outros componentes passivos / discretos ───────────────────────
        "KSK", "KSJ",   # não são Samsung memory
        "KAG",          # não é Samsung memory
        "KM1",          # KM1x não é prefixo eMCP Samsung (KM2-KM9 são)
    ),
    "Micron":  ("MT6", "MT8"),   # MediaTek usa MT6*/MT8*

    # SanDisk: filtra produtos de consumo removíveis — só queremos eMMC embutido
    # SDSQ* = microSD consumer (SDSQUA, SDSQXAZ, SDSQAB...)
    # SDSD* = SD cards consumer (SDSDQAD, SDSDQ...)
    # SDSS* = SSD consumer para PC (SDSSDHII, SDSSDP...)
    # SDCF* = CompactFlash — storage removível profissional
    # SDIX* = iXpand Lightning/USB drives
    # SDDD* = Dual Drive OTG USB
    # SDCZ* = USB thumb drives (Cruzer, Ultra...)
    # SDBS* = SSD portátil (Extreme Portable)
    # SDRX* = receptores / não é chip de memória
    # SDP* (curto) = peças/acessórios não-memória
    "SanDisk": ("SDSQ", "SDSD", "SDSS", "SDCF", "SDIX", "SDDD", "SDCZ", "SDBS", "SDRX"),
}

# Tokens que NUNCA são PNs — palavras comuns que aparecem em páginas de chips
FALSE_POSITIVES = {
    # Nomes de marcas como texto corrido
    "KINGSTON", "SAMSUNG", "SKHYNIX", "TOSHIBA", "KIOXIA", "MICRON",
    "WESTERN", "SANDISK", "UNISOC", "QUALCOMM", "MEDIATEK", "ELPIDA",
    "GIGADEVICE", "RAYSON", "NANYA", "ISSI",
    # Nomes de produtos / tecnologias
    "SNAPDRAGON", "HELIO", "EXYNOS", "DIMENSITY", "GALAXY", "IPHONE",
    "KUMPULAN",
    # Termos técnicos que parecem PNs mas não são
    "MEMORY", "STORAGE", "EMMC", "FLASH", "NAND", "LPDDR", "DATASHEET",
    "SDRAM", "DRAM", "NVME", "EEPROM",
    # Palavras de UI / navegação
    "AVAILABLE", "CONTACT", "PRODUCT", "CATEGORY", "HOMEPAGE", "SEARCH",
    "LAPTOP", "DESKTOP", "MOBILE", "TABLET", "SERVER", "MODULE",
    "DOWNLOAD", "OVERVIEW", "FEATURES", "SUPPORT", "REGISTER",
}

# Substrings que, se presentes em qualquer PN candidato, o invalidam.
# Usadas para filtrar artefatos de scraping (ex: findchips concatena o texto
# "PARTDETAILS" ao final do PN em alguns links de produto).
FORBIDDEN_PN_SUBSTRINGS: tuple[str, ...] = (
    "PARTDETAILS",   # findchips: slug da URL de detalhe concatenado ao PN
    "SURKMG",        # Kingbright LED suffix (KPBA3010SURKMGKC…)
    "SURKM",         # variante do anterior
)

REVISION_RE = re.compile(r"[-_][A-Z]{0,2}\d{2,4}[A-Z]?$")


def normalize_pn(raw: str) -> str:
    """Normaliza um candidato a PN: maiúsculas, só alfanumérico, sem sufixo de revisão."""
    pn = raw.strip().upper()
    pn = re.sub(r"[^A-Z0-9]", "", pn)
    pn = REVISION_RE.sub("", pn)
    return pn


def is_valid_pn(pn: str, brand: str) -> bool:
    """
    Valida se um candidato pode ser um PN da marca indicada.

    Propositalmente PERMISSIVO para coleta — só filtra lixo óbvio.
    A classificação exata (tipo, família, geração) é feita pelo enriquecedor.

    Critérios:
    1. Comprimento: 7-24 chars (PNs reais são pelo menos 7)
    2. Não é palavra pura: deve ter pelo menos um dígito
    3. Não é número puro: deve ter pelo menos uma letra
    4. Não está na lista de falsos positivos conhecidos
    5. Começa com o prefixo da marca
    6. Não começa com prefixo de OUTRA marca que colide
    """
    # Comprimento mínimo 6: SoCs como SM8450, MT6765, SC9863A têm 6 chars
    if len(pn) < 6 or len(pn) > 24:
        return False

    # Falso positivo explícito (match exato)
    if pn in FALSE_POSITIVES:
        return False

    # Substring proibida — artefatos de scraping (ex: "PARTDETAILS" do findchips)
    if any(sub in pn for sub in FORBIDDEN_PN_SUBSTRINGS):
        return False

    # Palavra pura (sem dígitos) — nunca é PN de chip
    if not re.search(r"\d", pn):
        return False

    # Número puro — nunca é PN de chip
    if re.match(r"^\d+$", pn):
        return False

    # Verifica prefixo da marca
    brand_prefixes = BRAND_LETTERS.get(brand)
    if brand_prefixes is None:
        # Marca desconhecida — aceita qualquer coisa minimamente válida
        return True
    if not any(pn.startswith(p) for p in brand_prefixes):
        return False

    # Exclui prefixos de outras marcas que colidem com esta
    exclusions = BRAND_EXCLUSIONS.get(brand, ())
    if any(pn.startswith(exc) for exc in exclusions):
        return False

    return True


def extract_pns(text: str, brand: str) -> list[str]:
    """
    Extrai e valida candidatos a PN de um bloco de texto.
    Usa regex amplo para captura, depois filtra com is_valid_pn.
    """
    found = []
    # Captura tokens alfanuméricos de 6-24 chars começando com letra maiúscula
    # Mínimo de 6 para cobrir SoCs curtos como SM8450, MT6765
    for m in re.finditer(r"\b([A-Z][A-Z0-9]{5,23})\b", text):
        pn = normalize_pn(m.group(1))
        if is_valid_pn(pn, brand):
            found.append(pn)
    return list(dict.fromkeys(found))


# ── Django DB dedup ────────────────────────────────────────────────────────────

_django_loaded = False
_db_pns: set[str] = set()
GOOD_CONFIDENCE = {"confirmed", "manual", "distributor"}


def load_db_pns():
    global _django_loaded, _db_pns
    if _django_loaded:
        return
    try:
        sys.path.insert(0, str(BASE_DIR))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
        try:
            from dotenv import load_dotenv
            load_dotenv(BASE_DIR / ".env")
        except ImportError:
            pass
        import django
        django.setup()
        from chips.models import KnownPart
        _db_pns = set(
            KnownPart.objects
            .filter(confidence__in=GOOD_CONFIDENCE)
            .values_list("part_number", flat=True)
        )
        logging.info(f"  DB: {len(_db_pns)} PNs já existem com boa confiança — serão pulados")
        _django_loaded = True
    except Exception as e:
        logging.warning(f"  Não foi possível carregar Django DB para dedup: {e}")
        _django_loaded = True


def already_in_db(pn: str) -> bool:
    return pn in _db_pns


# ── HTTP helper ───────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def get(url: str, session, retries: int = 3) -> BeautifulSoup | None:
    for attempt in range(retries):
        try:
            r = session.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 200 and len(r.text) > 300:
                return BeautifulSoup(r.text, "lxml")
            if r.status_code in (403, 401, 429, 503):
                logging.warning(f"    HTTP {r.status_code} → {url}")
                return None
            logging.debug(f"    HTTP {r.status_code} (attempt {attempt+1}) → {url}")
        except requests.exceptions.Timeout:
            logging.warning(f"    Timeout (attempt {attempt+1}) → {url}")
        except Exception as e:
            logging.warning(f"    Erro ({attempt+1}/{retries}) em {url}: {e}")
        time.sleep(DELAY * (attempt + 1))
    return None


# ── Sources — Samsung / SK Hynix / Micron / KIOXIA ────────────────────────────

def _source_preduo_playwright(brand: str) -> list[str]:
    """
    Variante Playwright de preduo.com — usada quando curl_cffi retorna 0.
    Cloudflare JS challenge exige browser real para liberar o conteúdo.
    """
    list_pages = [
        "https://www.preduo.com/eMCP-List",
        "https://www.preduo.com/eMMC-List",
        "https://www.preduo.com/UFS-List",
        "https://www.preduo.com/LPDDR4-List",
        "https://www.preduo.com/LPDDR5-List",
        "https://www.preduo.com/DDR4-List",
        "https://www.preduo.com/DDR5-List",
    ]
    pns: list[str] = []
    for base_url in list_pages:
        for page in range(1, 30):
            url = f"{base_url}?page={page}" if page > 1 else base_url
            soup = get_browser(url, wait_ms=3000)
            if not soup:
                break
            found = extract_pns(soup.get_text(" ", strip=True), brand)
            if not found and page > 1:
                break
            pns.extend(found)
            if not soup.find("a", string=re.compile(r"Next|›|»|next", re.I)):
                break
            time.sleep(DELAY)
        time.sleep(DELAY)
    return pns


def source_preduo(session, brand: str) -> list[str]:
    """
    preduo.com — catálogos eMCP/eMMC/UFS/LPDDR por categoria.

    Fluxo de resiliência:
      1. curl_cffi (TLS Chrome) — rápido, funciona quando preduo não está com
         Cloudflare JS challenge ativo
      2. Playwright (Chromium real) — fallback se curl_cffi retornar 0 PNs;
         resolve qualquer JS challenge que o curl_cffi não consegue
    """
    pns = []
    list_pages = [
        "https://www.preduo.com/eMCP-List",
        "https://www.preduo.com/eMMC-List",
        "https://www.preduo.com/UFS-List",
        "https://www.preduo.com/LPDDR4-List",
        "https://www.preduo.com/LPDDR5-List",
        "https://www.preduo.com/DDR4-List",
        "https://www.preduo.com/DDR5-List",
    ]
    for base_url in list_pages:
        for page in range(1, 30):
            url = f"{base_url}?page={page}" if page > 1 else base_url
            soup = get(url, session)
            if not soup:
                break
            found = extract_pns(soup.get_text(" ", strip=True), brand)
            if not found and page > 1:
                break
            pns.extend(found)
            if not soup.find("a", string=re.compile(r"Next|›|»|next", re.I)):
                break
            time.sleep(DELAY)
        time.sleep(DELAY)

    result = list(dict.fromkeys(pns))

    # Fallback Playwright: se curl_cffi não trouxe nada e Playwright está disponível
    if not result and _PLAYWRIGHT_AVAILABLE:
        logging.info("  preduo: curl_cffi retornou 0 — tentando Playwright (JS challenge)...")
        pw_pns = _source_preduo_playwright(brand)
        if pw_pns:
            result = list(dict.fromkeys(pw_pns))
            logging.info(f"  preduo [Playwright]: {len(result)} PNs únicos")
        else:
            logging.warning("  preduo [Playwright]: também retornou 0 — site bloqueado ou sem PNs")
    elif not result:
        logging.warning("  preduo: 0 PNs — Playwright não disponível (pip install playwright && playwright install chromium)")

    logging.info(f"  preduo: {len(result)} PNs únicos")
    return result


def source_glochip(session, brand: str) -> list[str]:
    """
    glochip.com — agregador paginado por prefixo e categoria.

    Samsung tem muitas séries eMCP além das KMR/KLM/KLU — todas as variantes
    KMQ, KMD, KMF, KMK, KMG, KM8, KM3, KM5, KM2, KM4, KMV, KMN, KMS etc.
    Cada família representa uma geração/tecnologia diferente (LPDDR3→LPDDR5).
    Listamos todas para maximizar cobertura.

    Fluxo de resiliência:
      1. curl_cffi (TLS Chrome) — primeira tentativa
      2. Playwright (Chromium real) — fallback se curl_cffi retornar 0;
         glochip usa Cloudflare JS challenge que exige browser real
    """
    pns = []
    brand_prefixes = {
        "Samsung": [
            # eMCP — todas as séries KM* (geração por sufixo do 3º char)
            ("KMR",  "eMCP"),   # LPDDR3 (mais antigos)
            ("KMQ",  "eMCP"),   # LPDDR4
            ("KMD",  "eMCP"),   # LPDDR4X
            ("KMF",  "eMCP"),   # LPDDR4X (variante)
            ("KMK",  "eMCP"),   # LPDDR3/LPDDR4
            ("KMG",  "eMCP"),   # LPDDR3
            ("KM8",  "eMCP"),   # LPDDR2 legado
            ("KM3",  "eMCP"),   # LPDDR4X / LPDDR5
            ("KM5",  "eMCP"),   # LPDDR5
            ("KM2",  "eMCP"),   # LPDDR4
            ("KM4",  "eMCP"),   # LPDDR4X
            ("KMV",  "eMCP"),   # variante
            ("KMN",  "eMCP"),   # variante
            ("KMS",  "eMCP"),   # variante
            ("KMT",  "eMCP"),   # variante
            ("KMJ",  "eMCP"),   # variante
            ("KML",  "eMCP"),   # variante
            ("KMI",  "eMCP"),   # variante
            # eMMC standalone (KLM*)
            ("KLMA", "eMMC"),
            ("KLMB", "eMMC"),
            ("KLMC", "eMMC"),
            ("KLMD", "eMMC"),
            ("KLME", "eMMC"),
            ("KLMF", "eMMC"),
            ("KLMG", "eMMC"),
            # UFS (KLU*)
            ("KLUA", "UFS"),
            ("KLUB", "UFS"),
            ("KLUC", "UFS"),
            ("KLUD", "UFS"),
            ("KLUE", "UFS"),
            ("KLUF", "UFS"),
            # DRAM standalone
            ("K4F",  "LPDDR4"),
            ("K3RG", "LPDDR4X"),
            ("K3L",  "LPDDR5"),
            ("K4Z",  "DDR4"),
            ("K4A",  "DDR4"),
        ],
        "SK Hynix": [
            ("H9HP", "LPDDR"),
            ("H9HQ", "LPDDR"),
            ("H9TQ", "LPDDR"),
            ("H8L",  "LPDDR"),
            ("HMCG", "LPDDR"),
            ("HM",   "LPDDR"),
        ],
        "Micron": [
            ("MTFC", "eMMC"),
            ("MT29F","NAND"),
            ("MT57", "eMMC"),
        ],
        "KIOXIA": [
            ("THGB", "eMMC"),
            ("THGL", "eMMC"),
            ("THGM", "eMMC"),
            ("TC",   "eMMC"),
        ],
        "Elpida": [
            ("EBJ",  "LPDDR"),
            ("EDF",  "DDR3"),
        ],
        "Nanya": [
            ("NT5CC","DDR3"),
            ("NT5CB","DDR3"),
            ("NT6",  "LPDDR"),
        ],
        "GigaDevice": [
            ("GD25Q","NOR Flash"),
            ("GD25B","NOR Flash"),
            ("GD5F", "NAND"),
        ],
        "ISSI": [
            ("IS42", "SDRAM"),
            ("IS61", "SRAM"),
            ("IS62", "SRAM"),
        ],
    }

    searches = brand_prefixes.get(brand, [])
    if not searches:
        logging.info(f"  glochip: sem prefixos configurados para {brand}")
        return []

    def _scrape_glochip(get_fn, searches: list) -> list[str]:
        """Lógica de scraping compartilhada entre curl_cffi e Playwright."""
        collected: list[str] = []
        seen_keywords: set[str] = set()
        for keyword, cat in searches:
            if any(keyword.startswith(seen) for seen in seen_keywords):
                continue
            seen_keywords.add(keyword)
            for page in range(1, 25):
                url = (
                    f"https://www.glochip.com/search"
                    f"?keyword={keyword}&category={cat}&page={page}"
                )
                soup = get_fn(url)
                if not soup:
                    break
                found = extract_pns(soup.get_text(" ", strip=True), brand)
                if not found and page > 1:
                    break
                collected.extend(found)
                has_next = bool(
                    soup.find("a", href=re.compile(r"page=\d+")) or
                    soup.find("a", string=re.compile(r"Next|›|»|next", re.I))
                )
                if not has_next:
                    break
                time.sleep(DELAY)
            time.sleep(DELAY)
        return collected

    # ── Tentativa 1: curl_cffi ──────────────────────────────────────────────
    pns = _scrape_glochip(lambda url: get(url, session), searches)
    result = list(dict.fromkeys(pns))

    # ── Tentativa 2: Playwright (JS challenge fallback) ─────────────────────
    if not result and _PLAYWRIGHT_AVAILABLE:
        logging.info("  glochip: curl_cffi retornou 0 — tentando Playwright (JS challenge)...")
        pw_pns = _scrape_glochip(lambda url: get_browser(url, wait_ms=4000), searches)
        result = list(dict.fromkeys(pw_pns))
        if result:
            logging.info(f"  glochip [Playwright]: {len(result)} PNs únicos")
        else:
            logging.warning("  glochip [Playwright]: também retornou 0 — JS challenge ativo ou site fora do ar")
    elif not result:
        logging.warning("  glochip: 0 PNs — instale Playwright para bypass de JS challenge: pip install playwright && playwright install chromium")

    logging.info(f"  glochip: {len(result)} PNs únicos")
    return result


def source_serviceemmc(session: requests.Session, brand: str) -> list[str]:
    """
    serviceemmc.com — blog técnico denso com listas PN×dispositivo.
    Acessa URLs fixas conhecidas + tenta descobrir mais posts via sitemap e tags.
    """
    if brand not in ("Samsung", "SK Hynix", "Micron", "KIOXIA"):
        return []

    pns = []

    # URLs confirmadas com listas de PNs Samsung
    samsung_urls = [
        # Listas de referência principais (páginas estáticas densas)
        "https://www.serviceemmc.com/p/emmc-list.html",
        "https://www.serviceemmc.com/p/emcp-list.html",
        # Posts históricos com listas completas
        "https://www.serviceemmc.com/2017/09/cid-emmcp-bga-221.html",
        "https://www.serviceemmc.com/2023/06/universall-flash-storage-ufs-list-update.html",
        "https://www.serviceemmc.com/2020/01/emmc-list-samsung.html",
        "https://www.serviceemmc.com/2018/04/samsung-emcp-lpddr4.html",
        "https://www.serviceemmc.com/2016/12/chip-emmc-emcp-samsung.html",
        "https://www.serviceemmc.com/2019/03/samsung-ufs-list.html",
        "https://www.serviceemmc.com/2021/08/samsung-emcp-list-lpddr4x.html",
        "https://www.serviceemmc.com/2022/01/samsung-ufs-30-list.html",
        "https://www.serviceemmc.com/2022/11/samsung-ufs-31-list.html",
        "https://www.serviceemmc.com/2023/02/samsung-emcp-list-lpddr4x-update.html",
        "https://www.serviceemmc.com/2023/10/samsung-ufs-32-list.html",
        "https://www.serviceemmc.com/2024/01/samsung-ufs-40-list.html",
        "https://www.serviceemmc.com/2021/01/samsung-emmc-53-list.html",
        "https://www.serviceemmc.com/2020/06/samsung-emcp-lpddr5.html",
    ]

    hynix_urls = [
        "https://www.serviceemmc.com/2020/03/hynix-emmc-list.html",
        "https://www.serviceemmc.com/2018/11/hynix-emcp-list.html",
        "https://www.serviceemmc.com/2022/04/sk-hynix-ufs-list.html",
    ]

    micron_urls = [
        "https://www.serviceemmc.com/2020/05/micron-emmc-list.html",
        "https://www.serviceemmc.com/2021/03/micron-ufs-list.html",
    ]

    urls_by_brand = {
        "Samsung":  samsung_urls,
        "SK Hynix": hynix_urls,
        "Micron":   micron_urls,
        "KIOXIA":   [],
    }

    target_urls = urls_by_brand.get(brand, [])

    # Tenta descobrir mais posts via tag de busca
    search_urls = {
        "Samsung":  [
            "https://www.serviceemmc.com/search/label/Samsung",
            "https://www.serviceemmc.com/search/label/eMMC",
            "https://www.serviceemmc.com/search/label/eMCP",
            "https://www.serviceemmc.com/search/label/UFS",
        ],
        "SK Hynix": ["https://www.serviceemmc.com/search/label/Hynix"],
        "Micron":   ["https://www.serviceemmc.com/search/label/Micron"],
        "KIOXIA":   [],
    }

    # Descobre links de posts adicionais via páginas de tag
    discovered_urls: set[str] = set(target_urls)
    for search_url in search_urls.get(brand, []):
        soup = get(search_url, session)
        if not soup:
            time.sleep(DELAY)
            continue
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            # Links de posts do blog (formato /YYYY/MM/titulo.html)
            if (href.startswith("https://www.serviceemmc.com/20") and
                    href.endswith(".html") and href not in discovered_urls):
                discovered_urls.add(href)
        time.sleep(DELAY)

    # Processa todos os URLs conhecidos + descobertos
    all_urls = list(discovered_urls)
    logging.info(f"  serviceemmc: {len(all_urls)} URLs a processar para {brand}")

    for url in all_urls:
        soup = get(url, session)
        if not soup:
            continue
        found = extract_pns(soup.get_text(" ", strip=True), brand)
        if found:
            pns.extend(found)
            logging.info(f"    serviceemmc: {len(found)} PNs de {url.split('/')[-1]}")
        time.sleep(DELAY)

    result = list(dict.fromkeys(pns))
    logging.info(f"  serviceemmc: {len(result)} PNs únicos")
    return result


def source_wolfchip(session, brand: str) -> list[str]:
    """
    wolfchip.com — distribuidor com catálogo Samsung/Hynix/Micron/KIOXIA.

    Fluxo de resiliência:
      1. curl_cffi (TLS Chrome) — wolfchip às vezes bloqueia por TLS fingerprint;
         curl_cffi resolve a maioria dos casos
      2. Playwright (Chromium real) — fallback se curl_cffi retornar 0
    """
    if brand not in ("Samsung", "SK Hynix", "Micron", "KIOXIA"):
        return []

    brand_slug = {
        "Samsung": ["samsung", "samsung-emcp", "samsung-emmc", "samsung-ufs"],
        "SK Hynix": ["hynix", "sk-hynix"],
        "Micron": ["micron"],
        "KIOXIA": ["kioxia", "toshiba"],
    }.get(brand, [brand.lower()])

    base_urls = (
        [f"https://www.wolfchip.com/category/{s}/" for s in brand_slug]
        + ["https://www.wolfchip.com/category/emmc/",
           "https://www.wolfchip.com/category/ufs/"]
    )

    def _scrape_wolfchip(get_fn) -> list[str]:
        collected: list[str] = []
        for base_url in base_urls:
            for page in range(1, 8):
                url = f"{base_url}page/{page}/" if page > 1 else base_url
                soup = get_fn(url)
                if not soup:
                    break
                found = extract_pns(soup.get_text(" ", strip=True), brand)
                if not found and page > 1:
                    break
                collected.extend(found)
                time.sleep(DELAY)
            time.sleep(DELAY)
        return collected

    # ── Tentativa 1: curl_cffi ──────────────────────────────────────────────
    pns = _scrape_wolfchip(lambda url: get(url, session))
    result = list(dict.fromkeys(pns))

    # ── Tentativa 2: Playwright ─────────────────────────────────────────────
    if not result and _PLAYWRIGHT_AVAILABLE:
        logging.info("  wolfchip: curl_cffi retornou 0 — tentando Playwright...")
        pw_pns = _scrape_wolfchip(lambda url: get_browser(url, wait_ms=3000))
        result = list(dict.fromkeys(pw_pns))
        if result:
            logging.info(f"  wolfchip [Playwright]: {len(result)} PNs únicos")
        else:
            logging.warning("  wolfchip [Playwright]: também retornou 0")
    elif not result:
        logging.warning("  wolfchip: 0 PNs — instale Playwright para fallback: pip install playwright && playwright install chromium")

    logging.info(f"  wolfchip: {len(result)} PNs únicos")
    return result


def source_jotrin(session: requests.Session, brand: str) -> list[str]:
    """
    jotrin.com — distribuidor internacional multi-marca.

    O Jotrin mudou sua estrutura de URLs. A estratégia agora é:
    1. Busca por keyword na página de pesquisa (/product/list.html?search_term=...)
    2. Extrai PNs dos links de produtos (href contendo /product/detail/)
    3. Fallback: extração de texto genérica da página de resultados
    """
    pns = []

    brand_terms = {
        "Samsung":   [
            "KMQ", "KMR", "KMD", "KMF", "KMK", "KMG", "KM3", "KM5",
            "KLMB", "KLMC", "KLMD", "KLME", "KLUB", "KLUC", "K4F",
        ],
        "SK Hynix":  ["H9HP", "H9HQ", "H9TQ", "H9TP", "HMCG", "HMBG", "HMAH",
                      "H26M", "H26T", "H28U", "H54G", "H8L"],
        "Micron":    ["MT29F", "MT29E", "MT57", "MTFC", "MTFD", "MT52", "MT53"],
        "KIOXIA":    ["THGB", "THGA", "THGJ", "THGN", "THGV", "TC58"],
        "Elpida":    ["EBJ", "EBK", "EBU", "EDF", "EDJ"],
        "Nanya":     ["NT5CC", "NT5CB", "NT5CA", "NT5CD", "NT6CL", "NT6CP", "NT8GA"],
        # Kingston: DDR3 legado (KVR16/13) são os mais comuns em notebooks 2012-2015
        # DDR4 (KVR21/26/32) dominam laptops 2016-2022; DDR5 (KVR48/64) são os novos
        "Kingston":  [
            "KVR13",  # DDR3-1333 legado
            "KVR16",  # DDR3-1600 — muito comum notebooks antigos
            "KVR21",  # DDR4-2133
            "KVR26",  # DDR4-2666 — mais popular DDR4
            "KVR32",  # DDR4-3200
            "KVR48",  # DDR5-4800
            "KVR64",  # DDR5-6400
            "KHX",    # HyperX (gaming, todas gerações)
            "KSM26",  # Server ECC DDR4-2666
            "KSM32",  # Server ECC DDR4-3200
            "KCP4",   # Compatibility DDR4
        ],
        # SanDisk iNAND: SDINB = família 7xxx (7132/7250/7332/7550) — mais comum em celulares
        # SDIN5/7/8 = gerações antigas eMMC 4.x/5.0; SDTN = iNAND 8EU (eMMC 5.1 moderno)
        # SDCIT = industrial iNAND; SDFCG = industrial flash
        "SanDisk":   ["SDINB", "SDTN", "SDIN5", "SDIN7", "SDIN8", "SDCIT", "SDFCG"],
        "ISSI":      ["IS42S", "IS43R", "IS61C", "IS62C", "IS45R"],
        "Rayson":    ["RS512", "RS1G", "EM6"],
        "GigaDevice":["GD25Q", "GD25B", "GD5F1", "GD5F2"],
        "Qualcomm":  ["SM8", "SM7", "SM6", "MSM"],
        "MediaTek":  ["MT6765", "MT6768", "MT8183", "MT6833"],
        "Spreadtrum":["SC9863", "SC9832", "T618", "T760"],
    }

    terms = brand_terms.get(brand, [brand[:4]])

    # Múltiplos padrões de URL do Jotrin (a estrutura muda às vezes)
    def _get_jotrin_urls(term: str) -> list[str]:
        return [
            f"https://www.jotrin.com/product/list.html?search_term={term}",
            f"https://www.jotrin.com/search/?keyword={term}",
            f"https://www.jotrin.com/product/parts/{term}",
        ]

    for term in terms:
        found_any = False
        for url in _get_jotrin_urls(term):
            soup = get(url, session)
            if not soup:
                continue

            # Estratégia 1: extrai PNs dos hrefs de produtos
            product_pns = []
            for a in soup.select("a[href*='product'], a[href*='detail'], a[href*='parts']"):
                href = a.get("href", "")
                # O PN geralmente é o último segmento da URL do produto
                segments = [s for s in href.rstrip("/").split("/") if s]
                if segments:
                    candidate = normalize_pn(segments[-1])
                    if is_valid_pn(candidate, brand):
                        product_pns.append(candidate)
                # Também tenta o texto do link
                text = a.get_text(strip=True).upper()
                if text:
                    candidate = normalize_pn(text)
                    if is_valid_pn(candidate, brand):
                        product_pns.append(candidate)

            # Estratégia 2: extração de texto genérica
            text_pns = extract_pns(soup.get_text(" ", strip=True), brand)

            found = list(dict.fromkeys(product_pns + text_pns))
            if found:
                pns.extend(found)
                logging.debug(f"    jotrin [{term}]: {len(found)} PNs de {url}")
                found_any = True
                break

        if not found_any:
            logging.debug(f"    jotrin [{term}]: sem resultados em nenhuma URL")
        time.sleep(DELAY)

    result = list(dict.fromkeys(pns))
    logging.info(f"  jotrin: {len(result)} PNs únicos")
    return result


def source_censtry(session: requests.Session, brand: str) -> list[str]:
    """censtry.com — comunidade técnica com listas de chips."""
    pns = []
    brand_urls = {
        "Samsung":  [
            "https://www.censtry.com/samsung-emmc-list/",
            "https://www.censtry.com/samsung-emcp-list/",
            "https://www.censtry.com/samsung-ufs-list/",
            "https://www.censtry.com/samsung-memory/",
        ],
        "SK Hynix": ["https://www.censtry.com/sk-hynix-emmc-list/"],
        "Micron":   ["https://www.censtry.com/micron-emmc-list/"],
    }
    urls = brand_urls.get(brand, [])
    for url in urls:
        soup = get(url, session)
        if not soup:
            continue
        found = extract_pns(soup.get_text(" ", strip=True), brand)
        pns.extend(found)
        time.sleep(DELAY)
    result = list(dict.fromkeys(pns))
    logging.info(f"  censtry: {len(result)} PNs únicos")
    return result


def source_alldatasheet(session, brand: str) -> list[str]:
    """
    alldatasheet.com — base de datasheets; muito confiável.

    Fluxo de resiliência:
      1. curl_cffi (TLS Chrome) — alldatasheet bloqueia scrapers via TLS;
         curl_cffi resolve a maioria dos casos
      2. Playwright (Chromium real) — fallback se curl_cffi retornar 0
    """
    brand_prefixes_ads = {
        "Samsung":   ["KMQ", "KMR", "KMS", "KLMB", "KLMC", "KLMD", "KLUB", "KLUC",
                      "KMFE", "KMFN", "KMFP", "KMFX", "K4F8", "K4ZAF"],
        "SK Hynix":  ["H9HP", "H9HQ", "H9TQ", "H9TP", "HMCG", "HMBG",
                      "H26M", "H26T", "H28U", "H8L"],
        "Micron":    ["MT29F", "MT29E", "MTFC", "MT52", "MT53"],
        "KIOXIA":    ["THGB", "THGA", "THGJ", "THGN", "TC58"],
        "Elpida":    ["EBJ", "EBK", "EDF", "EDJ"],
        "Nanya":     ["NT5CC", "NT5CB", "NT5CA", "NT6CL", "NT8GA"],
        "ISSI":      ["IS42S", "IS61C", "IS62WV"],
        "GigaDevice":["GD25Q", "GD25B"],
    }
    prefixes = brand_prefixes_ads.get(brand, [])

    def _scrape_ads(get_fn) -> list[str]:
        collected: list[str] = []
        for prefix in prefixes:
            url = f"https://www.alldatasheet.com/search.jsp?Searchword={prefix}&sType=1"
            soup = get_fn(url)
            if not soup:
                time.sleep(DELAY)
                continue
            for link in soup.select("a[href*='/datasheet/']"):
                text = link.get_text(strip=True).upper()
                pn = normalize_pn(text)
                if is_valid_pn(pn, brand):
                    collected.append(pn)
            found = extract_pns(soup.get_text(" ", strip=True), brand)
            collected.extend(found)
            time.sleep(DELAY)
        return collected

    # ── Tentativa 1: curl_cffi ──────────────────────────────────────────────
    pns = _scrape_ads(lambda url: get(url, session))
    result = list(dict.fromkeys(pns))

    # ── Tentativa 2: Playwright ─────────────────────────────────────────────
    if not result and _PLAYWRIGHT_AVAILABLE:
        logging.info("  alldatasheet: curl_cffi retornou 0 — tentando Playwright...")
        pw_pns = _scrape_ads(lambda url: get_browser(url, wait_ms=3000))
        result = list(dict.fromkeys(pw_pns))
        if result:
            logging.info(f"  alldatasheet [Playwright]: {len(result)} PNs únicos")
        else:
            logging.warning("  alldatasheet [Playwright]: também retornou 0")
    elif not result:
        logging.warning("  alldatasheet: 0 PNs — instale Playwright: pip install playwright && playwright install chromium")

    logging.info(f"  alldatasheet: {len(result)} PNs únicos")
    return result


def source_lcsc(session: requests.Session, brand: str) -> list[str]:
    """lcsc.com — maior distribuidor chinês; catálogo extenso."""
    pns = []
    brand_terms_lcsc = {
        # Samsung — todas as categorias com prefixo curto para cobertura ampla
        "Samsung":   [
            "KMQ", "KMR", "KMD", "KMF", "KMK",  # eMCP (mais comuns)
            "KLMB", "KLMC", "KLMD", "KLME",       # eMMC
            "KLUB", "KLUC", "KLUD",                # UFS
            "K4F", "K3RG", "K4Z",                  # DRAM standalone
        ],
        "SK Hynix":  ["H9HP", "H9HQ", "H9TQ", "H9TP", "HMCG", "H26M", "H28U"],
        "Micron":    ["MT29", "MTFC", "MT57", "MT52", "MT53"],
        "GigaDevice":["GD25Q", "GD25B", "GD5F"],
        "ISSI":      ["IS25", "IS42", "IS61", "IS62"],
        "Nanya":     ["NT5CC", "NT5CB", "NT5CA", "NT6CL", "NT8GA"],
        "KIOXIA":    ["THGB", "THGA", "THGJ", "TC58"],
        "Elpida":    ["EBJ", "EBK", "EDF"],
    }
    terms = brand_terms_lcsc.get(brand, [])
    for term in terms:
        url = f"https://www.lcsc.com/search?q={term}"
        soup = get(url, session)
        if soup:
            found = extract_pns(soup.get_text(" ", strip=True), brand)
            pns.extend(found)
        time.sleep(DELAY)
    result = list(dict.fromkeys(pns))
    logging.info(f"  lcsc: {len(result)} PNs únicos")
    return result


def source_martview(session: requests.Session, brand: str) -> list[str]:
    """martview-forum.com — fórum de técnicos de reparo de celular."""
    pns = []
    brand_lower = brand.lower().replace(" ", "+")
    search_urls = [
        f"https://www.martview-forum.com/search/?q={brand_lower}+emmc",
        f"https://www.martview-forum.com/search/?q={brand_lower}+emcp",
        f"https://www.martview-forum.com/search/?q={brand_lower}+ufs",
    ]
    for url in search_urls:
        soup = get(url, session)
        if not soup:
            continue
        thread_links = [
            a.get("href", "") for a in soup.select("a[href*='/threads/']")
        ][:10]
        for href in thread_links:
            thread_url = href if href.startswith("http") else "https://www.martview-forum.com" + href
            thread_soup = get(thread_url, session)
            if thread_soup:
                found = extract_pns(thread_soup.get_text(" ", strip=True), brand)
                pns.extend(found)
            time.sleep(DELAY)
        time.sleep(DELAY)
    result = list(dict.fromkeys(pns))
    logging.info(f"  martview: {len(result)} PNs únicos")
    return result


def source_gsm_forum(session: requests.Session, brand: str) -> list[str]:
    """gsm-forum.com — maior fórum de técnicos GSM do mundo."""
    pns = []
    urls = [
        "https://forum.gsmhosting.com/vbb/f700/",
        "https://forum.gsmhosting.com/vbb/f700/page2/",
        "https://forum.gsmhosting.com/vbb/f700/page3/",
    ]
    for url in urls:
        soup = get(url, session)
        if not soup:
            continue
        found = extract_pns(soup.get_text(" ", strip=True), brand)
        pns.extend(found)
        time.sleep(DELAY)
    result = list(dict.fromkeys(pns))
    logging.info(f"  gsm_forum: {len(result)} PNs únicos")
    return result


def source_chip1stop(session, brand: str) -> list[str]:
    """
    chip1stop.com — distribuidor japonês (Fujitsu Group) com catálogo extenso.

    Sem Cloudflare agressivo — acessível via curl_cffi. Boa cobertura de
    memórias Samsung, SK Hynix, Micron e KIOXIA vendidas no mercado asiático.
    Isso inclui PNs que não aparecem nos distribuidores ocidentais.

    ╔═════════════════════════════════════════════════════════════════╗
    ║  Para adicionar uma nova marca: adicione os termos de busca    ║
    ║  em brand_terms_c1s abaixo.                                    ║
    ╚═════════════════════════════════════════════════════════════════╝
    """
    brand_terms_c1s: dict[str, list[str]] = {
        # Samsung — todas as categorias:
        #   eMCP:  KMQ/KMR/KMD/KMF/KMK/KMG/KM3/KM5 (LPDDR2→LPDDR5 + NAND integrado)
        #   eMMC:  KLMB/KLMC/KLMD/KLME/KLMF/KLMG
        #   UFS:   KLUB/KLUC/KLUD/KLUE
        #   DRAM:  K4F (LPDDR4), K3RG/K3L (LPDDR5), K4Z/K4A (DDR4)
        "Samsung":   [
            "KMQ", "KMR", "KMD", "KMF", "KMK", "KMG", "KM3", "KM5",  # eMCP
            "KLMB", "KLMC", "KLMD", "KLME", "KLMF", "KLMG",            # eMMC
            "KLUB", "KLUC", "KLUD", "KLUE",                             # UFS
            "K4F", "K3RG", "K3L", "K4Z", "K4A",                        # DRAM
        ],
        "SK Hynix":  ["H9HP", "H9HQ", "H9TQ", "H9TP", "HMCG", "HMBG",
                      "H26M", "H26T", "H28U", "H8L"],
        "Micron":    ["MT29F", "MTFC", "MT57", "MT29E", "MT52", "MT53"],
        "KIOXIA":    ["THGB", "THGA", "THGJ", "THGN", "TC58"],
        "Elpida":    ["EBJ", "EBK", "EDF", "EDJ"],
        "Nanya":     ["NT5CC", "NT5CB", "NT5CA", "NT6CL", "NT8GA"],
        "GigaDevice":["GD25Q", "GD25B", "GD5F"],
        "ISSI":      ["IS42", "IS61", "IS62", "IS45"],
    }
    terms = brand_terms_c1s.get(brand, [])
    if not terms:
        return []

    pns: list[str] = []
    for term in terms:
        url = f"https://www.chip1stop.com/en/search?dispLang=EN&searchWord={term}"
        soup = get(url, session)
        if soup:
            # Chip1stop lista PNs em células de tabela e links
            for el in soup.select("td, .product-name, a[href*='partno']"):
                text = el.get_text(strip=True).upper()
                pn = normalize_pn(text)
                if is_valid_pn(pn, brand):
                    pns.append(pn)
            found = extract_pns(soup.get_text(" ", strip=True), brand)
            pns.extend(found)
        time.sleep(DELAY)

    result = list(dict.fromkeys(pns))
    logging.info(f"  chip1stop: {len(result)} PNs únicos")
    return result


# ── Samsung Semiconductor Official ────────────────────────────────────────────
#
# semiconductor.samsung.com é o site público oficial da Samsung para
# desenvolvedores e compradores. NÃO é o portal B2B MemoryLink (login corporativo).
#
# Vantagem estratégica sobre distribuidores:
#   - Dado primário do fabricante → sem intermediário
#   - Zero Cloudflare agressivo (site institucional/marketing)
#   - Cobre produtos descontinuados que saíram dos distribuidores
#   - PNs com variantes de revisão completas (ex: KLM8G1GETF-B041)
#
# Estratégia de extração (3 camadas):
#   1. Sitemap XML     → PNs diretamente nas URLs dos produtos (mais eficiente)
#   2. curl_cffi       → páginas de categoria com lista de produtos
#   3. Playwright      → fallback para conteúdo JS-rendered (Next.js SPA)
#
# PARA ESCALAR PARA NOVAS MARCAS:
# Adicione entradas em OFFICIAL_SEMI_SITES abaixo com as URLs do site oficial
# do fabricante. A lógica de extração é genérica — funciona para qualquer
# site que coloque o PN no slug da URL ou no texto da página.
#
# Referências para outros fabricantes:
#   Micron:    https://www.micron.com/products/
#   SK Hynix:  https://product.skhynix.com/products/
#   KIOXIA:    https://business.kioxia.com/en-apac/
# ─────────────────────────────────────────────────────────────────────────────

# URLs de categoria por marca e tipo de chip.
# Ordem: URLs mais prováveis de ter dados primeiro.
OFFICIAL_SEMI_SITES: dict[str, dict[str, list[str]]] = {
    # ──────────────────────────────────────────────────────────────────────────
    # Samsung Semiconductor — semiconductor.samsung.com
    #
    # NOTA: o sitemap.xml cobre a maioria dos produtos DRAM (LPDDR4/5, HBM,
    # GDDR, DDR4/5). As URLs abaixo são usadas como FALLBACK pelas camadas
    # curl_cffi e Playwright quando o sitemap não encontrar PNs suficientes.
    #
    # eMMC (KLM*) e eMCP (KMR*/KMQ*) são melhor coletados via preduo,
    # serviceemmc e glochip — o sitemap Samsung não os lista individualmente.
    # ──────────────────────────────────────────────────────────────────────────
    "Samsung": {
        # ── Storage ──────────────────────────────────────────────────────────
        "emmc": [
            "https://semiconductor.samsung.com/us/consumer-storage/emmc/",
            "https://semiconductor.samsung.com/global/consumer-storage/emmc/",
        ],
        "ufs": [
            "https://semiconductor.samsung.com/us/consumer-storage/ufs/",
            "https://semiconductor.samsung.com/global/consumer-storage/ufs/",
        ],
        "emcp": [
            "https://semiconductor.samsung.com/us/mobile-storage/emcp/",
            "https://semiconductor.samsung.com/global/mobile-storage/emcp/",
        ],
        # ── Mobile DRAM ───────────────────────────────────────────────────────
        "lpddr5": [
            "https://semiconductor.samsung.com/us/mobile-dram/lpddr5/",
            "https://semiconductor.samsung.com/us/dram/lpddr/lpddr5/",
        ],
        "lpddr4x": [
            "https://semiconductor.samsung.com/us/mobile-dram/lpddr4x/",
            "https://semiconductor.samsung.com/us/dram/lpddr/lpddr4x/",
        ],
        "lpddr4": [
            "https://semiconductor.samsung.com/us/mobile-dram/lpddr4/",
            "https://semiconductor.samsung.com/us/dram/lpddr/lpddr4/",
        ],
        "lpddr3": [
            "https://semiconductor.samsung.com/us/mobile-dram/lpddr3/",
            "https://semiconductor.samsung.com/us/dram/lpddr/lpddr3/",
        ],
        # ── Server / Client DRAM ─────────────────────────────────────────────
        "ddr5": [
            "https://semiconductor.samsung.com/us/dram/ddr5/",
        ],
        "ddr4": [
            "https://semiconductor.samsung.com/us/dram/ddr4/",
        ],
        "ddr3": [
            "https://semiconductor.samsung.com/us/dram/ddr3/",
        ],
        # ── High Bandwidth / Specialty DRAM ──────────────────────────────────
        "hbm": [
            "https://semiconductor.samsung.com/us/dram/hbm/",
        ],
        "gddr6": [
            "https://semiconductor.samsung.com/us/dram/gddr/gddr6/",
            "https://semiconductor.samsung.com/us/dram/gddr/",
        ],
        "wide_io": [
            "https://semiconductor.samsung.com/us/dram/wide-io-dram/",
        ],
    },
}

# Sitemaps a tentar (em ordem de prioridade).
# O Samsung Semiconductor usa Next.js — o sitemap é server-generated e
# geralmente acessível sem JavaScript.
OFFICIAL_SEMI_SITEMAPS: dict[str, list[str]] = {
    "Samsung": [
        "https://semiconductor.samsung.com/sitemap.xml",
        "https://semiconductor.samsung.com/sitemap-en-US.xml",
        "https://semiconductor.samsung.com/sitemap_products.xml",
        "https://semiconductor.samsung.com/us/sitemap.xml",
    ],
}

# Regex para extrair o slug do produto de URLs do semiconductor.samsung.com.
# Ex: /consumer-storage/emmc/klm8g1getf-b041/          → captura "klm8g1getf-b041"
# Ex: /us/mobile-dram/lpddr5/k3rg3g3me-dgch/           → captura "k3rg3g3me-dgch"
# Ex: /dram/lpddr/lpddr4x/k4u2e3s4aa-tucl/             → captura "k4u2e3s4aa-tucl"
#
# O padrão usa {1,3} segmentos intermediários com backtracking greedy:
# tenta consumir o máximo possível e recua até o grupo de captura final bater.
# Isso garante que sempre capturamos o ÚLTIMO segmento da URL (o PN real),
# não a família ou subfamília do produto.
_SEMI_PROD_SLUG_RE = re.compile(
    r"/(?:consumer-storage|mobile-storage|mobile-dram|dram|nor-flash|sram|nand)"
    r"(?:/[^/]+){1,3}"         # 1–3 segmentos intermediários (família/subfamília)
    r"/([a-zA-Z][a-zA-Z0-9\-]{5,30})"  # PN: último segmento do produto
    r"(?:/|\?|$)",
    re.IGNORECASE,
)


def _semi_extract_pns_from_urls(urls: list[str], brand: str) -> list[str]:
    """
    Extrai PNs de uma lista de URLs do site oficial do fabricante.
    O PN está no slug da URL do produto: /emmc/KLM8G1GETF-B041/ → KLM8G1GETFB041.
    """
    pns: list[str] = []
    for url in urls:
        m = _SEMI_PROD_SLUG_RE.search(url)
        if not m:
            continue
        pn = normalize_pn(m.group(1))
        if is_valid_pn(pn, brand):
            pns.append(pn)
    return pns


def _semi_fetch_xml(url: str, session) -> "BeautifulSoup | None":
    """
    Busca uma URL de sitemap e parseia como XML correto.

    Usa BeautifulSoup com features="xml" em vez do parser HTML padrão da função
    get() — evita XMLParsedAsHTMLWarning e garante que as tags <loc> sejam
    encontradas corretamente no namespace do sitemap.
    """
    try:
        from bs4 import XMLParsedAsHTMLWarning
        import warnings

        r = session.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200 or len(r.text) < 100:
            logging.info(f"    [sitemap] HTTP {r.status_code} para {url}")
            return None

        # Suprime o warning de HTML→XML e usa parser XML nativo
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
            try:
                return BeautifulSoup(r.text, features="xml")
            except Exception:
                # lxml xml não disponível — cai para html com supressão de warning
                return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        logging.info(f"    [sitemap] Erro ao buscar {url}: {e}")
        return None


def _semi_scrape_sitemap(session, brand: str) -> list[str]:
    """
    Extrai PNs via sitemap XML do site oficial do fabricante.

    O sitemap lista URLs de todos os produtos — o PN está no slug da URL.
    Segue sitemap indexes (sitemap de sitemaps) automaticamente, sem
    filtro de keyword (antes restringia demais e pulava sub-sitemaps válidos).

    Logging detalhado ajuda a diagnosticar se o sitemap foi encontrado,
    quantas URLs contém, e quantas matcharam o padrão de PN.
    """
    sitemaps = OFFICIAL_SEMI_SITEMAPS.get(brand, [])
    if not sitemaps:
        return []

    for sitemap_url in sitemaps:
        try:
            soup = _semi_fetch_xml(sitemap_url, session)
            if not soup:
                time.sleep(DELAY)
                continue

            # Coleta todas as <loc> tags do sitemap
            locs = [tag.get_text(strip=True) for tag in soup.find_all("loc")]
            logging.info(
                f"    [sitemap] {sitemap_url.split('/')[-1]}: "
                f"{len(locs)} <loc> encontradas"
            )
            if locs:
                logging.info(
                    f"    [sitemap] Amostra de URLs: "
                    f"{[u.replace('https://semiconductor.samsung.com','') for u in locs[:3]]}"
                )

            # Verifica se é um sitemap index (tem tags <sitemap>)
            sitemap_tags = soup.find_all("sitemap")
            if sitemap_tags:
                # É um sitemap index — segue TODOS os sub-sitemaps (sem filtro)
                sub_urls = [t.find("loc").get_text(strip=True)
                            for t in sitemap_tags if t.find("loc")]
                logging.info(
                    f"    [sitemap] É um índice com {len(sub_urls)} sub-sitemaps: "
                    f"{[u.split('/')[-1] for u in sub_urls[:5]]}"
                )
                all_sub_locs: list[str] = []
                for sub_url in sub_urls[:20]:   # segue todos (max 20)
                    sub_soup = _semi_fetch_xml(sub_url, session)
                    if sub_soup:
                        sub_locs = [t.get_text(strip=True)
                                    for t in sub_soup.find_all("loc")]
                        logging.info(
                            f"      [sitemap] {sub_url.split('/')[-1]}: "
                            f"{len(sub_locs)} URLs"
                        )
                        all_sub_locs.extend(sub_locs)
                    time.sleep(0.5)
                locs.extend(all_sub_locs)

            logging.info(f"    [sitemap] Total de URLs para checar: {len(locs)}")
            pns = _semi_extract_pns_from_urls(locs, brand)
            logging.info(
                f"    [sitemap] {len(pns)} PNs extraídos de {len(locs)} URLs"
            )
            if pns:
                logging.info(
                    f"  samsung_semi [sitemap]: {len(pns)} PNs de {sitemap_url}"
                )
                return list(dict.fromkeys(pns))
            else:
                # Não encontrou PNs — mostra amostra das URLs para diagnóstico
                product_like = [u for u in locs if any(
                    k in u for k in ("emmc", "ufs", "emcp", "dram", "lpddr", "storage")
                )][:5]
                if product_like:
                    logging.info(
                        f"    [sitemap] URLs de produto encontradas mas sem match "
                        f"de PN Samsung: {product_like}"
                    )

        except Exception as e:
            logging.info(f"  samsung_semi sitemap erro ({sitemap_url}): {e}")

        time.sleep(DELAY)

    return []


def _semi_scrape_category(url: str, session, brand: str,
                           use_playwright: bool = False) -> list[str]:
    """
    Extrai PNs de uma página de categoria do site oficial do fabricante.

    Estratégias (em ordem de confiabilidade):
    1. Links de produto: PN está no href (mais preciso)
    2. __NEXT_DATA__: JSON server-side do Next.js (contém dados dos produtos
       mesmo que não renderizados na DOM ainda — chave para SPAs)
    3. Extração de texto genérica como fallback

    Playwright: tempo de espera de 8s + scroll para trigger lazy loading.
    """
    if use_playwright:
        if not _PLAYWRIGHT_AVAILABLE:
            return []
        browser = _pw_browser_get()
        if not browser:
            return []
        ctx = None
        try:
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                viewport={"width": 1280, "height": 900},
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            page = ctx.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(3000)

            # Scroll para trigger lazy loading de produtos
            for _ in range(4):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(800)

            # ── Estratégia A: __NEXT_DATA__ (JSON do SSR do Next.js) ──────
            next_data_raw = page.evaluate("""
                () => {
                    const el = document.getElementById('__NEXT_DATA__');
                    return el ? el.textContent : null;
                }
            """)
            pns: list[str] = []
            if next_data_raw:
                logging.info(
                    f"    [samsung_semi] __NEXT_DATA__ encontrado "
                    f"({len(next_data_raw)} chars) — extraindo PNs..."
                )
                # Trata o JSON como texto e extrai PNs diretamente
                pns.extend(extract_pns(next_data_raw, brand))

            # ── Estratégia B: links e texto da DOM ───────────────────────
            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            href_urls = []
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if not href.startswith("http"):
                    href = "https://semiconductor.samsung.com" + href
                href_urls.append(href)
            pns.extend(_semi_extract_pns_from_urls(href_urls, brand))
            pns.extend(extract_pns(soup.get_text(" ", strip=True), brand))

            return list(dict.fromkeys(pns))

        except Exception as e:
            logging.warning(f"    [samsung_semi Playwright] Erro em {url}: {e}")
            return []
        finally:
            if ctx:
                try:
                    ctx.close()
                except Exception:
                    pass
    else:
        soup = get(url, session)
        if not soup:
            return []

        pns: list[str] = []
        href_urls: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not href.startswith("http"):
                href = "https://semiconductor.samsung.com" + href
            href_urls.append(href)
        pns.extend(_semi_extract_pns_from_urls(href_urls, brand))
        pns.extend(extract_pns(soup.get_text(" ", strip=True), brand))
        return list(dict.fromkeys(pns))


# Prefixos Samsung para busca na página de pesquisa do site oficial.
# Usados em _semi_search_playwright() — cada prefixo gera uma query de busca.
#
# O Samsung Semiconductor sitemap cobre bem os chips DRAM (K4U*, K3K*, KHB*
# etc.), mas NÃO lista individualmente os chips eMCP, eMMC e UFS. A única
# forma de descobri-los via site oficial é pela barra de busca — que retorna
# páginas de produto com PNs individuais.
#
# Para adicionar novos prefixos: inclua-os na lista correspondente ao tipo.
SAMSUNG_SEMI_SEARCH_TERMS = [
    # ── eMCP (todas as séries KM*) ────────────────────────────────────────
    # Chips eMMC+LPDDR combinados — linha principal de interesse do projeto.
    "KMQ",   # eMCP 8+4, 16+4 (KMQ310013M, KMQE60013M…)
    "KMR",   # eMCP com LPDDR4 (KMR210013M, KMR631NGULCLFS…)
    "KMD",   # eMCP high-capacity (KMDH6001DA, KMDP6001DB…)
    "KMF",   # eMCP mid-range (KMF310012M, KMFN60012M…)
    "KMK",   # eMCP multi-die (KMK5X000VM, KMK8X000VM…)
    "KMG",   # eMCP LPDDR4X (KMGX6001BA, KMGE6001BM…)
    "KM3",   # eMCP 3D (KM3V6001CA, KM3H6001CA…)
    "KM5",   # eMCP série 5 (KM5H7001DM, KM5V8001DM…)
    "KM8",   # eMCP série 8 (KM8F8001JM, KM8V8001JM…)
    "KM2",   # eMCP série 2 (KM2V8001CM, KM2L9001CM…)
    "KM4",   # eMCP série 4 (KM4X60002M, KM4X6001KM…)
    "KMV",   # eMCP LPDDR (KMVUS000LA, KMVTU000LM…)
    "KMS",   # eMCP série S (KMS5X000KM, KMS5U000KM…)
    "KMN",   # eMCP série N (KMN9X000RM, KMN5X000ZM…)
    "KML",   # eMCP série L (KML5U000HM…)
    "KMI",   # eMCP série I (KMI9W0004M…)
    "KMJ",   # eMCP série J (KMJ5U000WM, KMJ5X000WM…)
    "KME",   # eMCP série E
    # ── eMMC standalone (KLM*) ───────────────────────────────────────────
    "KLMB",  # eMMC 5.1 série B
    "KLMC",  # eMMC 5.1 série C
    "KLMD",  # eMMC 5.1 série D
    "KLME",  # eMMC 5.1 série E
    "KLMF",  # eMMC 5.1 série F
    "KLMG",  # eMMC 5.1 série G
    "KLUB",  # UFS 2.x série B
    # ── UFS standalone (KLU*) ────────────────────────────────────────────
    "KLUC",  # UFS 3.x série C
    "KLUD",  # UFS 3.x série D
    "KLUE",  # UFS 4.x série E
    # ── DRAM complementar (não coberto totalmente pelo sitemap) ───────────
    "K4F",   # LPDDR4X specialty (K4FHE3S4HAKFCL…)
    "K4R",   # Wide IO / LPDDR legado
    "K4V",   # LPDDR4 legado
    "K3U",   # LPDDR5 (K3UH6H60AMTFCL…)
    "KHB",   # HBM2E/HBM3 (KHBAC4A03DMC1H…)
    # ── UFS card / eUFS ──────────────────────────────────────────────────
    "KMW",   # possível série UFS card
    "KMDG",  # eMCP alto desempenho (KMDGX4SBS…)
]


def _semi_search_playwright(brand: str) -> list[str]:
    """
    Busca PNs individuais via página de pesquisa do semiconductor.samsung.com.

    O Samsung Semiconductor usa Next.js com carregamento de produtos via
    XHR/fetch APÓS o DOM estar pronto — os resultados NÃO estão no
    __NEXT_DATA__ inicial. Por isso usamos duas estratégias simultâneas:

    1. Network interception: captura as respostas JSON das chamadas de API
       (XHR/fetch) que o browser faz para carregar os resultados.
    2. wait_until="networkidle": garante que todas as chamadas de API
       completaram antes de lermos o DOM — sem isso, o DOM está vazio.

    Endpoint de busca: /us/search/?query={prefix}

    Na primeira execução, loga os URLs das APIs capturadas (diagnóstico).
    """
    if brand != "Samsung" or not _PLAYWRIGHT_AVAILABLE:
        return []

    browser = _pw_browser_get()
    if not browser:
        return []

    pns: list[str] = []
    base_url = "https://semiconductor.samsung.com/us/search/?query={}"
    _first_term = True   # log de diagnóstico só no 1º termo

    for term in SAMSUNG_SEMI_SEARCH_TERMS:
        url = base_url.format(term)
        ctx = None
        try:
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )

            # ── Intercepção de respostas JSON (XHR / fetch) ───────────────
            # Captura os corpos de TODAS as respostas JSON da página.
            # Os resultados de busca do Samsung chegam por aqui, não pelo DOM.
            api_bodies: list[str] = []
            api_urls:   list[str] = []   # para log de diagnóstico

            def _on_response(resp) -> None:
                try:
                    ct = resp.headers.get("content-type", "")
                    if resp.status == 200 and "json" in ct:
                        body = resp.body()   # bytes — sync Playwright
                        api_bodies.append(body.decode("utf-8", errors="ignore"))
                        api_urls.append(resp.url)
                except Exception:
                    pass

            page.on("response", _on_response)

            # networkidle = espera até ZERO requests pendentes por 500ms
            # Garante que todas as chamadas XHR/fetch de busca completaram.
            try:
                page.goto(url, wait_until="networkidle", timeout=25000)
            except Exception:
                # Timeout de networkidle (página muito pesada) — espera mínimo
                page.wait_for_timeout(6000)

            # Scroll extra para disparar lazy-load se houver
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(500)

            # Log de diagnóstico só na primeira busca
            if _first_term and api_urls:
                _first_term = False
                logging.debug(
                    f"    [samsung_semi search] APIs capturadas para '{term}': "
                    + ", ".join(u.split("?")[0].replace(
                        "https://semiconductor.samsung.com", ""
                    ) for u in api_urls[:6])
                )

            term_pns: list[str] = []

            # ── 1. PNs das respostas JSON interceptadas ───────────────────
            for body in api_bodies:
                # Texto livre (model names, descriptions)
                term_pns.extend(extract_pns(body, brand))
                # URLs de produto embutidas no JSON (/mobile-storage/emcp/kmq…)
                embedded_urls = re.findall(
                    r'"(/(?:mobile-storage|consumer-storage|mobile-dram|dram)'
                    r'/[^"]{5,80})"',
                    body,
                )
                term_pns.extend(_semi_extract_pns_from_urls(embedded_urls, brand))

            # ── 2. __NEXT_DATA__ (estrutura estática da página) ───────────
            next_data = page.evaluate("""
                () => {
                    const el = document.getElementById('__NEXT_DATA__');
                    return el ? el.textContent : null;
                }
            """)
            if next_data:
                term_pns.extend(extract_pns(next_data, brand))
                embedded_urls = re.findall(
                    r'"(/(?:mobile-storage|consumer-storage|mobile-dram|dram)'
                    r'/[^"]{5,80})"',
                    next_data,
                )
                term_pns.extend(_semi_extract_pns_from_urls(embedded_urls, brand))

            # ── 3. Links e texto do DOM (fallback) ───────────────────────
            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            href_urls = []
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if not href.startswith("http"):
                    href = "https://semiconductor.samsung.com" + href
                href_urls.append(href)
            term_pns.extend(_semi_extract_pns_from_urls(href_urls, brand))
            term_pns.extend(extract_pns(soup.get_text(" ", strip=True), brand))

            term_pns = list(dict.fromkeys(term_pns))
            if term_pns:
                logging.info(
                    f"    [samsung_semi search] '{term}': {len(term_pns)} PNs"
                )
            pns.extend(term_pns)

        except Exception as e:
            logging.warning(f"    [samsung_semi search] Erro '{term}': {e}")
        finally:
            if ctx:
                try:
                    ctx.close()
                except Exception:
                    pass

        time.sleep(0.8)

    return list(dict.fromkeys(pns))


def source_samsung_semi(session, brand: str) -> list[str]:
    """
    semiconductor.samsung.com — site oficial da Samsung Semiconductor.

    Fonte primária: dados direto do fabricante — eMMC, UFS, eMCP, LPDDR, DDR.
    Zero Cloudflare agressivo (site institucional de marketing).

    Fluxo de extração (4 camadas paralelas):

      Camada 1 — Sitemap XML (SEMPRE)
        O sitemap lista URLs de produto DRAM individualmente. Extrai PNs
        dos slugs em ~5s. Cobre: K4U*, K3K*, K3L*, K3U*, KHB*, K4Z*, K4F*.
        eMCP e eMMC NÃO aparecem no sitemap.

      Camada 2 — Playwright Search (SEMPRE, se Playwright disponível)
        Busca cada prefixo da lista SAMSUNG_SEMI_SEARCH_TERMS na barra de
        pesquisa do site. É a única forma de capturar eMCP (KMQ*, KMR*,
        KMD*, KMF*…) e eMMC/UFS (KLM*, KLU*) via site oficial.
        Estimativa: ~5 min para ~40 termos.

      Camada 3 — curl_cffi em páginas de categoria (fallback)
        Ativada somente se Camadas 1+2 juntas trouxerem < 20 PNs.
        As páginas de categoria mostram famílias ("eMMC 5.1"), não PNs —
        em testes extensivos retornou 0 PNs. Mantida como redundância.

      Camada 4 — Playwright em páginas de categoria (fallback profundo)
        Ativada somente se Camadas 1+2+3 trouxerem < 20 PNs.

    Escalonável via OFFICIAL_SEMI_SITES e OFFICIAL_SEMI_SITEMAPS:
    adicione entradas para Micron, SK Hynix etc. para reusar esta função.

    ╔═════════════════════════════════════════════════════════════════╗
    ║  Para escalar para outras marcas:                               ║
    ║  1. Adicione URLs em OFFICIAL_SEMI_SITES[nova_marca]            ║
    ║  2. Adicione sitemaps em OFFICIAL_SEMI_SITEMAPS[nova_marca]     ║
    ║  3. Remova o guard if brand != "Samsung" abaixo                 ║
    ║  4. Adicione "samsung_semi" → "nova_marca_semi" em ALL_SOURCES  ║
    ╚═════════════════════════════════════════════════════════════════╝
    """
    if brand not in OFFICIAL_SEMI_SITES:
        return []

    pns: list[str] = []

    # ── Camada 1: Sitemap XML (sempre) ────────────────────────────────────
    # Cobre chips DRAM em ~5s. eMCP/eMMC/UFS não estão no sitemap.
    logging.info("  samsung_semi: [1/4] sitemap XML...")
    sitemap_pns = _semi_scrape_sitemap(session, brand)
    if sitemap_pns:
        pns.extend(sitemap_pns)
        logging.info(
            f"  samsung_semi [sitemap]: {len(sitemap_pns)} PNs "
            f"(DRAM: K4*, K3*, KHB*…)"
        )
    else:
        logging.info("  samsung_semi [sitemap]: 0 PNs")

    # ── Camada 2: Playwright Search por prefixo (sempre) ─────────────────
    # Única forma de capturar eMCP (KMQ*, KMR*, KMD*…), eMMC (KLM*) e
    # UFS (KLU*) do site oficial. Roda SEMPRE — independente do sitemap.
    if _PLAYWRIGHT_AVAILABLE:
        logging.info(
            f"  samsung_semi: [2/4] Playwright Search "
            f"({len(SAMSUNG_SEMI_SEARCH_TERMS)} termos: eMCP, eMMC, UFS, DRAM)..."
        )
        search_pns = _semi_search_playwright(brand)
        if search_pns:
            pns.extend(search_pns)
            logging.info(
                f"  samsung_semi [search]: {len(search_pns)} PNs adicionais "
                f"(eMCP/eMMC/UFS)"
            )
        else:
            logging.info(
                "  samsung_semi [search]: 0 PNs — "
                "página de busca pode não retornar PNs individuais em texto"
            )
    else:
        logging.warning(
            "  samsung_semi: Playwright não disponível — eMCP/eMMC/UFS não serão "
            "coletados do site oficial. Instale: "
            "pip install playwright && playwright install chromium"
        )

    result_so_far = list(dict.fromkeys(pns))

    # ── Camadas 3+4: fallback de categoria (só se 1+2 zerados) ───────────
    # As páginas de categoria do Samsung Semiconductor mostram famílias de
    # produto ("eMMC 5.1 Solution"), nunca PNs individuais. Mantidas aqui
    # como rede de segurança para o caso de mudança de arquitetura do site.
    if len(result_so_far) < 20:
        logging.info(
            "  samsung_semi: [3/4] camadas 1+2 insuficientes — "
            "tentando páginas de categoria..."
        )
        categories = OFFICIAL_SEMI_SITES.get(brand, {})

        # Camada 3: curl_cffi
        for cat_name, cat_urls in categories.items():
            for url in cat_urls:
                found = _semi_scrape_category(
                    url, session, brand, use_playwright=False
                )
                if found:
                    pns.extend(found)
                    logging.info(
                        f"    samsung_semi [{cat_name}]: {len(found)} PNs via curl_cffi"
                    )
                    break
                time.sleep(DELAY)
            time.sleep(DELAY)

        after_layer3 = list(dict.fromkeys(pns))

        # Camada 4: Playwright nas categorias
        if len(after_layer3) < 20 and _PLAYWRIGHT_AVAILABLE:
            logging.info("  samsung_semi: [4/4] Playwright em páginas de categoria...")
            for cat_name, cat_urls in categories.items():
                for url in cat_urls[:1]:
                    found = _semi_scrape_category(
                        url, session, brand, use_playwright=True
                    )
                    if found:
                        pns.extend(found)
                        logging.info(
                            f"    samsung_semi [Playwright/{cat_name}]: {len(found)} PNs"
                        )
                        break
                    time.sleep(DELAY)
                time.sleep(DELAY)

    result = list(dict.fromkeys(pns))
    logging.info(f"  samsung_semi: {len(result)} PNs únicos no total")
    return result


# ── DigiKey API ────────────────────────────────────────────────────────────────
#
# DigiKey é o maior distribuidor eletrônico do mundo e tem catálogo completo de
# chips Samsung, SK Hynix, Micron, KIOXIA etc. A API v4 é gratuita e retorna
# dados estruturados — sem HTML, sem Cloudflare, sem bot detection.
#
# Autenticação: OAuth2 client_credentials (Client ID + Client Secret)
# Token expira em 1800s — renovado automaticamente a cada execução do script.
#
# Cadastro (gratuito, ~2 minutos):
#   1. Acesse: https://developer.digikey.com/
#   2. "Get Started" → "Create Organization" → escolha "Free" plan
#   3. Crie um "Production App" (mesmo para testes — sandbox tem dados limitados)
#   4. Copie o Client ID e Client Secret para o .env
#
# ╔═══════════════════════════════════════════════════════════════╗
# ║  Para adicionar uma nova marca: edite DIGIKEY_SEARCH_TERMS   ║
# ║  abaixo com os prefixos relevantes.                          ║
# ╚═══════════════════════════════════════════════════════════════╝

# Termos de busca por marca — prefixos curtos retornam mais resultados.
# DigiKey busca por substring no PN do fabricante, então "KMQ" encontra
# KMQ28U64A-AGCB, KMQ310013M-B419, etc.
DIGIKEY_SEARCH_TERMS: dict[str, list[str]] = {
    "Samsung": [
        # eMCP (LPDDR + NAND integrado) — séries KM*
        "KMQ", "KMR", "KMD", "KMF", "KMK", "KMG", "KM3", "KM5",
        # eMMC standalone — séries KLM*
        "KLMB", "KLMC", "KLMD", "KLME", "KLMF", "KLMG",
        # UFS — séries KLU*
        "KLUB", "KLUC", "KLUD", "KLUE",
        # DRAM standalone — LPDDR4/5, DDR4
        "K4F", "K3RG", "K3L", "K4Z", "K4A",
    ],
    "SK Hynix": [
        # eMCP / LPDDR mobile
        "H9HP", "H9HQ", "H9TQ", "H9TP",
        # LPDDR5 standalone
        "HMCG", "HMBG", "HMAH",
        # eMMC / UFS standalone
        "H26M", "H26T", "H28U", "H54G", "HCNN",
        # LPDDR3 legado
        "H8L",
    ],
    "Micron": [
        "MT29F", "MT29E", "MTFC", "MT57", "MTFD",
        "MT52", "MT53", "MT40A", "MT41K",
    ],
    "KIOXIA": [
        # eMMC — THGB* cobre 7xxx, THGA* cobre versões antigas
        "THGB", "THGA",
        # UFS 3.x — THGJ*, THGV*
        "THGJ", "THGV",
        # eMMC 5.1 — THGN*
        "THGN",
        # NAND raw
        "TC58",
    ],
    "Elpida": [
        "EBJ", "EBK", "EBL", "EBU",
        "EDF", "EDJ", "EDK",
    ],
    "Nanya": [
        "NT5CC", "NT5CB", "NT5CA", "NT5CD",
        "NT6CL", "NT6CM", "NT6CP",
        "NT8GA", "NT8GB",
    ],
    "GigaDevice": [
        "GD25Q", "GD25B", "GD5F",
    ],
    "ISSI": [
        "IS42S", "IS61C", "IS62WV", "IS45R",
    ],
    "Kingston": [
        # DDR3 (notebooks 2010-2015)
        "KVR13", "KVR16",
        # DDR4 (notebooks 2016-2022) — KVR26 é o mais popular
        "KVR21", "KVR26", "KVR29", "KVR32",
        # DDR5 (notebooks 2022+)
        "KVR48", "KVR52", "KVR56", "KVR64",
        # HyperX gaming e Server ECC
        "KHX", "KSM26", "KSM32", "KSM48",
    ],
    # SanDisk iNAND — eMMC/UFS embutido para mobile/industrial
    # NÃO incluir SDSQ (microSD), SDSS (SSD PC), SDCZ (USB)
    "SanDisk": [
        "SDINB",   # iNAND 7xxx (7132/7250/7332/7550) — mais comum em Android
        "SDTN",    # iNAND 8EU eMMC 5.1 / UFS 2.1 — geração moderna
        "SDIN8",   # iNAND Extreme eMMC 5.0 HS400 (2015-2017)
        "SDIN5",   # iNAND eMMC 4.3/4.5 legado
        "SDCIT",   # iNAND Industrial
    ],
}

_digikey_token: dict = {}   # cache do token OAuth2 {access_token, expires_at}


def _digikey_get_token(client_id: str, client_secret: str) -> str | None:
    """
    Obtém (ou reutiliza o cache de) um access token OAuth2 do DigiKey.
    Usa client_credentials — sem interação humana necessária.
    """
    import time as _time
    global _digikey_token
    now = _time.time()
    if _digikey_token.get("access_token") and _digikey_token.get("expires_at", 0) > now + 60:
        return _digikey_token["access_token"]

    try:
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({
            "grant_type":    "client_credentials",
            "client_id":     client_id,
            "client_secret": client_secret,
        }).encode()
        req = urllib.request.Request(
            "https://api.digikey.com/v1/oauth2/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read())
        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 1800))
        _digikey_token = {"access_token": token, "expires_at": now + expires_in}
        logging.info("  [DigiKey] Token OAuth2 obtido com sucesso")
        return token
    except Exception as e:
        logging.error(f"  [DigiKey] Falha ao obter token OAuth2: {e}")
        return None


def source_digikey(session, brand: str) -> list[str]:
    """
    DigiKey API v4 — maior distribuidor eletrônico do mundo.

    Retorna PNs reais do fabricante (ManufacturerProductNumber) buscando
    por prefixo de keyword. Dados estruturados — sem HTML, sem Cloudflare.
    Cobertura: Samsung, SK Hynix, Micron, KIOXIA, Elpida, Nanya, etc.

    Requer DIGIKEY_CLIENT_ID e DIGIKEY_CLIENT_SECRET no .env.
    Cadastro gratuito em: https://developer.digikey.com/

    ╔═════════════════════════════════════════════════════════════════╗
    ║  Para adicionar uma nova marca: edite DIGIKEY_SEARCH_TERMS.   ║
    ╚═════════════════════════════════════════════════════════════════╝
    """
    client_id     = os.getenv("DIGIKEY_CLIENT_ID", "").strip()
    client_secret = os.getenv("DIGIKEY_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        logging.info("  digikey: DIGIKEY_CLIENT_ID/SECRET não configurados — pulando")
        logging.info("           Cadastre-se em https://developer.digikey.com/ (gratuito)")
        return []

    terms = DIGIKEY_SEARCH_TERMS.get(brand, [])
    if not terms:
        logging.info(f"  digikey: sem termos configurados para {brand}")
        return []

    token = _digikey_get_token(client_id, client_secret)
    if not token:
        return []

    pns: list[str] = []
    base_url = "https://api.digikey.com/products/v4/search/keyword"
    headers  = {
        "Authorization":             f"Bearer {token}",
        "X-DIGIKEY-Client-Id":       client_id,
        "X-DIGIKEY-Locale-Site":     "US",
        "X-DIGIKEY-Locale-Language": "en",
        "X-DIGIKEY-Locale-Currency": "USD",
        "Content-Type":              "application/json",
    }

    _DIGIKEY_MAX_429_RETRIES = 5   # máx tentativas por termo antes de pular
    _DIGIKEY_BASE_429_WAIT   = 60  # backoff inicial em segundos
    _DIGIKEY_MAX_429_WAIT    = 300 # teto do backoff (5 min)

    for term in terms:
        offset = 0
        page_size = 50
        _retry_401  = False  # evita loop infinito em caso de 401 persistente
        _429_count  = 0      # tentativas 429 acumuladas neste termo
        _429_wait   = _DIGIKEY_BASE_429_WAIT  # backoff atual

        while True:
            body = json.dumps({
                "Keywords":            term,
                "RecordCount":         page_size,
                "RecordStartPosition": offset,
                "Filters":             {},
                "Sort":                {"SortOption": "SortByDigiKeyPartNumber", "Direction": "Ascending", "SortParameterId": 0},
                "RequestedQuantity":   0,
                "SearchOptions":       ["ManufacturerPartSearch"],
            }).encode()
            try:
                import urllib.request as _urlreq
                import urllib.error   as _urlerr
                req = _urlreq.Request(base_url, data=body, headers=headers, method="POST")
                with _urlreq.urlopen(req, timeout=20) as resp:
                    data_resp = json.loads(resp.read())
            except _urlerr.HTTPError as e:
                if e.code == 401 and not _retry_401:
                    # Token expirou durante a sessão — força renovação e retenta
                    logging.warning(
                        f"    [DigiKey] 401 para '{term}' — renovando token OAuth2..."
                    )
                    _digikey_token.clear()
                    new_token = _digikey_get_token(client_id, client_secret)
                    if new_token:
                        token = new_token
                        headers["Authorization"] = f"Bearer {token}"
                        _retry_401 = True
                        time.sleep(5)   # pequena pausa após renovação
                        continue  # retenta com token novo
                    logging.error("    [DigiKey] Falha ao renovar token — abortando")
                    break
                elif e.code == 401:
                    logging.warning(
                        f"    [DigiKey] 401 persistente para '{term}' — "
                        "verifique se o app está em modo 'Production' (não Sandbox) "
                        "em developer.digikey.com → My Apps"
                    )
                    break
                elif e.code == 403:
                    logging.warning(
                        f"    [DigiKey] 403 para '{term}' — endpoint sem permissão. "
                        "O plano Free pode não incluir o endpoint v4/search/keyword."
                    )
                    break
                elif e.code == 429:
                    _429_count += 1
                    if _429_count > _DIGIKEY_MAX_429_RETRIES:
                        logging.warning(
                            f"    [DigiKey] 429 persistente — pulando '{term}' "
                            f"após {_DIGIKEY_MAX_429_RETRIES} tentativas"
                        )
                        break
                    logging.warning(
                        f"    [DigiKey] 429 rate limit (tentativa {_429_count}/"
                        f"{_DIGIKEY_MAX_429_RETRIES}) — aguardando {_429_wait}s"
                    )
                    time.sleep(_429_wait)
                    _429_wait = min(_429_wait * 2, _DIGIKEY_MAX_429_WAIT)  # backoff exponencial
                    continue
                else:
                    logging.warning(
                        f"    [DigiKey] HTTP {e.code} para '{term}'"
                    )
                    break
            except Exception as e:
                logging.warning(f"    [DigiKey] Erro ao buscar '{term}': {e}")
                break

            # Sucesso — reseta contadores de backoff
            _429_count = 0
            _429_wait  = _DIGIKEY_BASE_429_WAIT

            products = data_resp.get("Products", [])
            if not products:
                break

            for prod in products:
                raw = prod.get("ManufacturerProductNumber", "") or ""
                pn  = normalize_pn(raw)
                if is_valid_pn(pn, brand):
                    pns.append(pn)

            total = data_resp.get("ProductsCount", 0)
            offset += len(products)
            if offset >= total or not products:
                break
            time.sleep(1.5)   # DigiKey free tier: 1000 req/day — pace generoso entre páginas

        logging.debug(f"    [DigiKey] '{term}': {len([p for p in pns])} acum.")
        time.sleep(3)   # pausa entre termos — evita rajada que dispara 429

    result = list(dict.fromkeys(pns))
    logging.info(f"  digikey: {len(result)} PNs únicos")
    return result


# ── Mouser API ─────────────────────────────────────────────────────────────────
#
# Mouser é o segundo maior distribuidor eletrônico do mundo.
# API simples: apenas uma API Key (sem OAuth2). Cadastro gratuito.
#
# Cadastro (gratuito, ~1 minuto):
#   1. Acesse: https://www.mouser.com/api-hub/
#   2. "Sign Up" → preencha com e-mail e nome
#   3. Receba a API key por e-mail imediatamente
#   4. Copie para o .env como MOUSER_API_KEY
#
# Limite: 1000 requisições/dia no plano gratuito.
#
# ╔═══════════════════════════════════════════════════════════════╗
# ║  Para adicionar uma nova marca: edite MOUSER_SEARCH_TERMS   ║
# ║  abaixo com os prefixos relevantes.                         ║
# ╚═══════════════════════════════════════════════════════════════╝

MOUSER_SEARCH_TERMS: dict[str, list[str]] = {
    "Samsung": [
        "KMQ", "KMR", "KMD", "KMF", "KMK", "KMG", "KM3", "KM5",
        "KLMB", "KLMC", "KLMD", "KLME", "KLMF", "KLMG",
        "KLUB", "KLUC", "KLUD", "KLUE",
        "K4F", "K3RG", "K3L", "K4Z",
    ],
    "SK Hynix": [
        # eMCP / LPDDR mobile
        "H9HP", "H9HQ", "H9TQ", "H9TP",
        # LPDDR5
        "HMCG", "HMBG", "HMAH",
        # eMMC / UFS
        "H26M", "H26T", "H28U", "H54G",
        # LPDDR3 legado
        "H8L",
    ],
    "Micron": [
        "MT29F", "MT29E", "MTFC", "MT57",
        "MT52", "MT53", "MT40A", "MT41K",
    ],
    "KIOXIA": [
        "THGB", "THGA",   # eMMC
        "THGJ", "THGV",   # UFS 3.x
        "THGN",            # eMMC 5.1 novo
        "TC58",            # NAND raw
    ],
    "Elpida": [
        "EBJ", "EBK", "EBU",
        "EDF", "EDJ",
    ],
    "Nanya": [
        "NT5CC", "NT5CB", "NT5CA", "NT5CD",
        "NT6CL", "NT6CP",
        "NT8GA",
    ],
    "GigaDevice": [
        "GD25Q", "GD25B", "GD5F",
    ],
    "ISSI": [
        "IS42S", "IS61C", "IS62WV",
    ],
    "Kingston": [
        "KVR13", "KVR16",             # DDR3 legado
        "KVR21", "KVR26", "KVR32",    # DDR4 — KVR26 é o mais comum
        "KVR48", "KVR64",             # DDR5
        "KHX", "KSM26", "KSM32",      # HyperX + Server ECC
    ],
    # SanDisk iNAND — eMMC/UFS embutido para mobile/industrial
    "SanDisk": [
        "SDINB",   # iNAND 7xxx — mais comum em Android
        "SDTN",    # iNAND 8EU eMMC 5.1 / UFS 2.1
        "SDIN8",   # iNAND Extreme eMMC 5.0
        "SDIN5",   # legado eMMC 4.x
        "SDCIT",   # industrial
    ],
}


def source_mouser(session, brand: str) -> list[str]:
    """
    Mouser Electronics API v1 — 2º maior distribuidor eletrônico do mundo.

    Busca por keyword (prefixo do PN) e retorna ManufacturerPartNumber.
    API key simples — sem OAuth2. Dados estruturados, sem Cloudflare.

    Requer MOUSER_API_KEY no .env.
    Cadastro gratuito em: https://www.mouser.com/api-hub/

    ╔═════════════════════════════════════════════════════════════════╗
    ║  Para adicionar uma nova marca: edite MOUSER_SEARCH_TERMS.    ║
    ╚═════════════════════════════════════════════════════════════════╝
    """
    api_key = os.getenv("MOUSER_API_KEY", "").strip()
    if not api_key:
        logging.info("  mouser: MOUSER_API_KEY não configurada — pulando")
        logging.info("          Cadastre-se em https://www.mouser.com/api-hub/ (gratuito)")
        return []

    # Mouser API Keys são GUIDs no formato xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    import re as _re
    _guid_re = _re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        _re.IGNORECASE,
    )
    if not _guid_re.match(api_key):
        logging.warning(
            "  mouser: MOUSER_API_KEY parece inválida (formato esperado: GUID "
            "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx).\n"
            "          Gere ou renove a chave em https://www.mouser.com/api-hub/ → My Keys"
        )
        return []

    terms = MOUSER_SEARCH_TERMS.get(brand, [])
    if not terms:
        logging.info(f"  mouser: sem termos configurados para {brand}")
        return []

    pns: list[str] = []
    base_url = f"https://api.mouser.com/api/v1/search/keyword?apiKey={api_key}"
    page_size = 50

    for term in terms:
        starting = 0
        while True:
            body = json.dumps({
                "SearchByKeywordRequest": {
                    "keyword":        term,
                    "records":        page_size,
                    "startingRecord": starting,
                    "searchOptions":  "InStock",   # filtra só em estoque — dados mais confiáveis
                    "searchWithSYMB": "",
                }
            }).encode()
            try:
                import urllib.request as _urlreq
                req = _urlreq.Request(
                    base_url,
                    data=body,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    method="POST",
                )
                with _urlreq.urlopen(req, timeout=20) as resp:
                    data_resp = json.loads(resp.read())
            except Exception as e:
                logging.warning(f"    [Mouser] Erro ao buscar '{term}': {e}")
                break

            errors = data_resp.get("Errors", [])
            if errors:
                # Diagnóstico específico para API Key inválida/expirada
                _key_err = any(
                    "API Key" in str(err.get("PropertyName", ""))
                    or "identifier" in str(err.get("Message", "")).lower()
                    for err in errors
                )
                if _key_err:
                    logging.warning(
                        f"    [Mouser] API Key rejeitada — gere ou renove em "
                        "https://www.mouser.com/api-hub/ → My Keys e atualize MOUSER_API_KEY no .env"
                    )
                    return []   # inútil continuar com chave inválida
                logging.warning(f"    [Mouser] API error para '{term}': {errors}")
                break

            parts = (
                data_resp.get("SearchResults", {}).get("Parts", [])
                or []
            )
            if not parts:
                break

            for part in parts:
                raw = part.get("ManufacturerPartNumber", "") or ""
                pn  = normalize_pn(raw)
                if is_valid_pn(pn, brand):
                    pns.append(pn)
                # Também tenta o Mouser Part Number que às vezes tem o PN completo
                raw2 = part.get("MouserPartNumber", "") or ""
                pn2  = normalize_pn(raw2)
                if is_valid_pn(pn2, brand):
                    pns.append(pn2)

            total = int(data_resp.get("SearchResults", {}).get("NumberOfResult", 0) or 0)
            starting += len(parts)
            if starting >= total or not parts:
                break
            time.sleep(0.3)

        logging.debug(f"    [Mouser] '{term}': busca concluída")
        time.sleep(0.5)

    result = list(dict.fromkeys(pns))
    logging.info(f"  mouser: {len(result)} PNs únicos")
    return result


# ── Nexar API (GraphQL) ────────────────────────────────────────────────────────
#
# Nexar é uma plataforma de inteligência de componentes que AGREGA dados de
# DigiKey, Mouser, Arrow, Digi-Components e 20+ distribuidores numa única API.
#
# Por que Nexar em vez de DigiKey/Mouser diretamente:
#   - Uma query cobre todos os distribuidores simultaneamente
#   - Retorna MPNs reais do fabricante (não SKUs do distribuidor)
#   - Cobre SK Hynix, Micron, KIOXIA com boa profundidade
#   - Free tier: 1.000 queries/mês — suficiente para coleta periódica
#   - Não depende de aprovação de endpoint como DigiKey v4
#
# Cadastro (~2 minutos): https://nexar.com/
#   1. Cadastre-se com e-mail
#   2. Vá em "Applications" → "New Application"
#   3. Copie Client ID e Client Secret para o .env
#   Scope obrigatório para o token: supply.domain
#
# ╔═══════════════════════════════════════════════════════════════╗
# ║  Para adicionar uma nova marca: edite NEXAR_SEARCH_TERMS.   ║
# ║  Use termos amplos (ex: "KMQ Samsung") para maximizar o     ║
# ║  retorno por query dentro do limite mensal.                  ║
# ╚═══════════════════════════════════════════════════════════════╝

NEXAR_SEARCH_TERMS: dict[str, list[str]] = {
    # Samsung — prefixos separados por família para cobertura total
    "Samsung": [
        # eMCP (LPDDR + NAND integrado) — todas as séries KM*
        "KMQ Samsung", "KMR Samsung", "KMD Samsung", "KMF Samsung",
        "KMK Samsung", "KMG Samsung", "KM3 Samsung", "KM5 Samsung",
        # eMMC standalone — séries KLM*
        "KLMB Samsung", "KLMC Samsung", "KLMD Samsung",
        "KLME Samsung", "KLMF Samsung", "KLMG Samsung",
        # UFS standalone — séries KLU*
        "KLUB Samsung", "KLUC Samsung", "KLUD Samsung", "KLUE Samsung",
        # DRAM standalone — LPDDR4/5, DDR4
        "K4F Samsung", "K3RG Samsung", "K3L Samsung", "K4Z Samsung",
    ],
    "SK Hynix": [
        "H9HP Hynix", "H9HQ Hynix", "H9TQ Hynix",
        "HMCG Hynix", "H8L Hynix", "H54G Hynix",
    ],
    "Micron": [
        "MT29F Micron", "MT29E Micron", "MTFC Micron",
        "MT57 Micron",  "MTFD Micron",
    ],
    "KIOXIA": [
        "THGB KIOXIA", "THGL KIOXIA", "THGM KIOXIA", "THGR KIOXIA",
    ],
    "Elpida": [
        "EBJ Elpida", "EDF Elpida", "EDJ Elpida",
    ],
    "Nanya": [
        "NT5CC Nanya", "NT5CB Nanya", "NT8GA Nanya",
    ],
    "GigaDevice": [
        "GD25Q GigaDevice", "GD25B GigaDevice", "GD5F GigaDevice",
    ],
    "ISSI": [
        "IS42S ISSI", "IS61C ISSI", "IS62WV ISSI", "IS45R ISSI",
    ],
    "Kingston": [
        "KVR13 Kingston", "KVR16 Kingston",
        "KVR21 Kingston", "KVR26 Kingston", "KVR32 Kingston",
        "KVR48 Kingston", "KVR64 Kingston",
        "KHX Kingston", "KSM Kingston",
    ],
    # ── SanDisk (Western Digital) iNAND ──────────────────────────────────────
    # Linha iNAND = eMMC/UFS embutido para smartphones e tablets.
    # NÃO incluir SDSQ (microSD), SDSS (SSD PC), SDCZ (USB): são produtos de consumo.
    #
    # SDINB*  = iNAND 7xxx (7132/7250/7332/7550) — eMMC 5.1 — MAIS COMUM em celulares
    #   SDINBDA = iNAND 7550 (16-256 GB)    SDINBDD = iNAND 7250 (8-64 GB)
    #   SDINBDG = iNAND 7332 (8-64 GB)      SDINBDE = iNAND 7132 (4-16 GB)
    # SDTN*   = iNAND 8EU / 8350 — eMMC 5.1 HS400 + UFS 2.1 (geração mais nova)
    #   SDTNQG / SDTNRG = iNAND 8EU eMMC     SDTNPM = iNAND 8EU UFS
    # SDIN8*  = iNAND Extreme eMMC 5.0 HS400 (2015-2017)
    # SDIN7*  = iNAND Ultra eMMC 4.41 (2012-2015)
    # SDIN5*  = iNAND eMMC 4.3/4.5 legacy (2010-2013)
    # SDCIT*  = iNAND Industrial eMMC/UFS (todos os grades)
    # SDFCG*  = industrial flash (grade comercial extendido)
    "SanDisk": [
        # ── Série 7xxx — MAIS IMPORTANTE (maior presença em celulares Android) ─
        "SDINBDA",   # iNAND 7550 eMMC 5.1 (16/32/64/128/256 GB)
        "SDINBDD",   # iNAND 7250 eMMC 5.1 (8/16/32/64 GB)
        "SDINBDG",   # iNAND 7332 eMMC 5.1 (8/16/32/64 GB)
        "SDINBDE",   # iNAND 7132 eMMC 5.1 (4/8/16 GB)
        "SDINBDH",   # variante iNAND 7xxx (grades automotivo/industrial)
        # ── iNAND 8EU / 8350 — geração moderna ──────────────────────────────
        "SDTNQG",    # iNAND 8EU eMMC 5.1 (8/16/32/64 GB) — padrão
        "SDTNRG",    # iNAND 8EU eMMC (variante)
        "SDTNPM",    # iNAND 8EU UFS 2.1
        # ── Legado iNAND (eMMC 4.x / 5.0) — comum em reparos antigos ────────
        "SDIN8",     # iNAND Extreme eMMC 5.0 HS400 (2015-2017): SDIN8DE4, SDIN8DE1
        "SDIN7",     # iNAND Ultra eMMC 4.41 (2012-2015): SDIN7DU2, SDIN7DP2
        "SDIN5",     # iNAND eMMC 4.3/4.5 (2010-2013): SDIN5C2, SDIN5D1
        # ── Industrial / automotive ──────────────────────────────────────────
        "SDCIT",     # iNAND Industrial eMMC/UFS (todos os grades)
        "SDFCG",     # industrial flash grade estendido
    ],
}

_nexar_token: dict = {}  # cache do token OAuth2 {access_token, expires_at}

_NEXAR_TOKEN_URL = "https://identity.nexar.com/connect/token"
_NEXAR_API_URL   = "https://api.nexar.com/graphql"

# GraphQL query — retorna mpn + fabricante + descrição curta.
# limit=50 por query: balanceia cobertura vs. consumo do free tier.
_NEXAR_QUERY = """
query NexarSearch($q: String!, $limit: Int) {
  supSearch(q: $q, limit: $limit) {
    results {
      part {
        mpn
        manufacturer {
          name
        }
        shortDescription
      }
    }
  }
}
"""


def _nexar_get_token(client_id: str, client_secret: str) -> str | None:
    """
    Obtém (ou reutiliza do cache) um access token OAuth2 do Nexar.
    Scope: supply.domain — obrigatório para o supSearch.
    """
    import time as _time
    global _nexar_token
    now = _time.time()
    if _nexar_token.get("access_token") and _nexar_token.get("expires_at", 0) > now + 60:
        return _nexar_token["access_token"]

    try:
        import urllib.request as _urlreq, urllib.parse as _urlparse
        data = _urlparse.urlencode({
            "grant_type":    "client_credentials",
            "client_id":     client_id,
            "client_secret": client_secret,
        }).encode()
        req = _urlreq.Request(
            _NEXAR_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with _urlreq.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read())
        token      = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        _nexar_token = {"access_token": token, "expires_at": now + expires_in}
        logging.info("  [Nexar] Token OAuth2 obtido com sucesso")
        return token
    except Exception as e:
        logging.error(f"  [Nexar] Falha ao obter token: {e}")
        return None


def source_nexar(session, brand: str) -> list[str]:
    """
    Nexar GraphQL API — agrega DigiKey, Mouser, Arrow e 20+ distribuidores.

    Uma query retorna MPNs de múltiplas fontes simultaneamente.
    Especialmente valioso para SK Hynix, Micron e KIOXIA onde DigiKey e
    Mouser têm problemas de credencial.

    Free tier: 1.000 queries/mês — use termos amplos para maximizar.
    Requer NEXAR_CLIENT_ID e NEXAR_CLIENT_SECRET no .env.
    Cadastro gratuito em: https://nexar.com/

    ╔═════════════════════════════════════════════════════════════════╗
    ║  Para adicionar uma nova marca: edite NEXAR_SEARCH_TERMS.     ║
    ╚═════════════════════════════════════════════════════════════════╝
    """
    client_id     = os.getenv("NEXAR_CLIENT_ID", "").strip()
    client_secret = os.getenv("NEXAR_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        logging.info("  nexar: NEXAR_CLIENT_ID/SECRET não configurados — pulando")
        logging.info(
            "         Cadastre-se em https://nexar.com/ (gratuito, 1.000 queries/mês)"
        )
        return []

    terms = NEXAR_SEARCH_TERMS.get(brand, [])
    if not terms:
        logging.info(f"  nexar: sem termos configurados para {brand}")
        return []

    token = _nexar_get_token(client_id, client_secret)
    if not token:
        return []

    pns: list[str] = []

    for term in terms:
        try:
            import urllib.request as _urlreq, urllib.error as _urlerr
            body = json.dumps({
                "query":     _NEXAR_QUERY,
                "variables": {"q": term, "limit": 50},
            }).encode()
            req = _urlreq.Request(
                _NEXAR_API_URL,
                data=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type":  "application/json",
                },
                method="POST",
            )
            with _urlreq.urlopen(req, timeout=30) as resp:
                data_resp = json.loads(resp.read())

            # GraphQL retorna erros dentro do payload (não como HTTP 4xx)
            gql_errors = data_resp.get("errors")
            if gql_errors:
                err_msg = gql_errors[0].get("message", "?")
                # "part limit of 0" = restrição do free tier → sair imediatamente
                # para não desperdiçar o orçamento mensal de 1.000 queries.
                if "part limit" in err_msg.lower() or "exceeded your" in err_msg.lower():
                    logging.warning(
                        "  [Nexar] ⚠  Free tier sem acesso a supSearch: "
                        f'"{err_msg}"\n'
                        "         → Contate api@nexar.com para upgrade ou acesso à supply.domain.\n"
                        "         → Abortando todas as queries Nexar para preservar o orçamento mensal."
                    )
                    return []   # sai imediatamente — não queima mais queries
                logging.warning(
                    f"    [Nexar] GraphQL error para '{term}': {err_msg}"
                )
                continue

            results = (
                data_resp.get("data", {})
                         .get("supSearch", {})
                         .get("results", [])
                or []
            )

            found_this: list[str] = []
            for r in results:
                raw = (r.get("part") or {}).get("mpn", "") or ""
                pn  = normalize_pn(raw)
                if is_valid_pn(pn, brand):
                    found_this.append(pn)
            pns.extend(found_this)
            if found_this:
                logging.debug(f"    [Nexar] '{term}': {len(found_this)} PNs")

        except _urlerr.HTTPError as e:
            if e.code == 401:
                # Token expirou mid-sessão — renova e retenta
                logging.warning("  [Nexar] 401 — renovando token...")
                _nexar_token.clear()
                token = _nexar_get_token(client_id, client_secret)
                if not token:
                    break
            elif e.code == 429:
                logging.warning("  [Nexar] 429 rate limit — aguardando 30s")
                time.sleep(30)
                # Retenta o mesmo term na próxima iteração (loop continua)
            else:
                logging.warning(f"  [Nexar] HTTP {e.code} para '{term}'")
        except Exception as e:
            logging.warning(f"    [Nexar] Erro para '{term}': {e}")

        time.sleep(0.5)  # Gentil com o free tier (1000 queries/mês)

    result = list(dict.fromkeys(pns))
    logging.info(f"  nexar: {len(result)} PNs únicos")
    return result


# ── findchips.com ──────────────────────────────────────────────────────────────
#
# findchips.com (Supplyframe/Molex) agrega estoque de 40+ distribuidores e mostra
# os model numbers exatos. Boa cobertura de Samsung eMCP/eMMC que outros agregadores
# não têm. Usa Cloudflare — curl_cffi com impersonação Chrome geralmente bypassa.
#
# Sem cadastro nem API key — scraping direto.
#
# URL: https://www.findchips.com/search/{pn_prefix}
# Cada linha de resultado tem o MPN na tag com classe "part-number-links-primary".
#
# ╔═══════════════════════════════════════════════════════════════╗
# ║  Para adicionar uma nova marca: inclua seus prefixos em       ║
# ║  FINDCHIPS_SEARCH_TERMS.                                      ║
# ╚═══════════════════════════════════════════════════════════════╝

FINDCHIPS_SEARCH_TERMS: dict[str, list[str]] = {
    # ── Samsung ───────────────────────────────────────────────────────────────
    "Samsung": [
        # eMCP — todas as séries KM* conhecidas
        "KMQ", "KMR", "KMD", "KMF", "KMK", "KMG", "KM3", "KM5",
        "KM8", "KM2", "KM4", "KMV", "KMS", "KMN", "KML",
        "KMI", "KMJ", "KME", "KMW", "KMDG",
        # eMMC standalone — todas as séries KLM*
        "KLMB", "KLMC", "KLMD", "KLME", "KLMF", "KLMG",
        # UFS standalone — todas as séries KLU*
        "KLUB", "KLUC", "KLUD", "KLUE",
    ],
    # ── SK Hynix ──────────────────────────────────────────────────────────────
    # Prefixos H9* = LPDDR4/5 eMCP, H26*/H28* = eMMC/UFS, HM* = LPDDR5,
    # HY* = legado DDR2/LPDDR, H8L* = LPDDR3, H54G* = UFS, HCNN* = UFS 3.x
    "SK Hynix": [
        # eMCP / LPDDR mobile
        "H9HP", "H9HQ", "H9TQ", "H9TP",
        # LPDDR5 (novos)
        "HMCG", "HMBG", "HMAH",
        # eMMC
        "H26M", "H26T",
        # UFS
        "H28U", "H54G", "HCNN",
        # LPDDR3 / LPDDR2 legado
        "H8L", "H9JS", "H9PS",
        # DDR3/4 mobile
        "HY5DU", "HY5SF",
    ],
    # ── Micron ────────────────────────────────────────────────────────────────
    # MT29* = NAND/eMMC, MTFC* = eMMC, MTFD* = NVMe, MT52/53* = LPDDR4,
    # MT40A* = DDR4, MT41K* = DDR3, MT47H* = DDR2, NW* = Numonyx NAND
    "Micron": [
        # eMMC
        "MTFC", "MT29F", "MT29E",
        # NVMe / storage
        "MTFD",
        # LPDDR4/5
        "MT52", "MT53",
        # DDR4 / DDR3 / DDR2
        "MT40A", "MT41K", "MT47H",
        # HBM
        "MT57", "MT61",
        # NOR / legado
        "MT28EW", "NW",
    ],
    # ── KIOXIA (ex-Toshiba Memory) ────────────────────────────────────────────
    # THGB* = eMMC, THGN* = UFS, THGJ* = UFS, TC58* = NAND, TCBDB* = UFS card
    "KIOXIA": [
        # eMMC (várias gerações)
        "THGBM", "THGBF", "THGAM", "THGBH", "THGBI", "THGBJ",
        "THGBL", "THGBR",
        # UFS
        "THGNM", "THGJF", "THGJB", "THGJD",
        # NAND flash standalone
        "TC58", "TCBDB",
        # Toshiba legacy (ainda usados)
        "THGVR", "THGVS",
    ],
    # ── Elpida (adquirida pela Micron em 2013, chips legado muito usados) ──────
    # EB* = LPDDR2/3 mobile, ED* = DDR3/LPDDR desktop/server
    "Elpida": [
        # LPDDR2 / LPDDR3 mobile
        "EBJ", "EBK", "EBL", "EBU",
        # DDR3 / LPDDR server/desktop
        "EDF", "EDJ", "EDK",
        # LPDDR4 (final da linha antes da aquisição)
        "EDB",
    ],
    # ── Nanya ─────────────────────────────────────────────────────────────────
    # NT5* = DDR3/DDR4, NT6* = LPDDR2/3/4, NT8* = LPDDR4X
    "Nanya": [
        # DDR3 / DDR4
        "NT5CC", "NT5CB", "NT5CA", "NT5CD",
        # LPDDR2 / LPDDR3
        "NT6CL", "NT6CM", "NT6CN",
        # LPDDR4 / LPDDR4X
        "NT6CP", "NT8GA", "NT8GB",
    ],
    # ── Kingston ──────────────────────────────────────────────────────────────
    # Kingston faz módulos DDR (DIMMs/SODIMMs) para notebooks e desktops.
    # NÃO fabricam os dies — compram de Samsung/Micron/SK Hynix e encapsulam.
    # PNs com "/" (ex: KVR26S19S8/8) são normalizados para KVR26S19S88.
    #
    # Formato geral: KVR{speed}{tipo}{dados_extra}/{capacidade_GB}
    #   speed: 13=1333, 16=1600 (DDR3); 21=2133, 26=2666, 32=3200 (DDR4)
    #          48=4800, 52=5200, 56=5600, 64=6400 (DDR5)
    #   tipo: S=SODIMM (laptop), N=UDIMM (desktop), E=ECC, R=RDIMM (server)
    "Kingston": [
        # DDR3 — muito comum em notebooks 2010-2015
        "KVR13",     # DDR3-1333 (KVR13S9S8/4, KVR13N9S8/4...)
        "KVR16",     # DDR3-1600 — o mais encontrado em campo
        # DDR4 — notebooks 2016-2022
        "KVR21",     # DDR4-2133
        "KVR26",     # DDR4-2666 — mais popular DDR4
        "KVR29",     # DDR4-2933
        "KVR32",     # DDR4-3200
        # DDR5 — notebooks 2022+
        "KVR48",     # DDR5-4800
        "KVR52",     # DDR5-5200
        "KVR56",     # DDR5-5600
        "KVR64",     # DDR5-6400
        # HyperX gaming
        "KHX16",     # HyperX DDR3
        "KHX24",     # HyperX DDR4-2400
        "KHX26",     # HyperX DDR4-2666
        "KHX32",     # HyperX DDR4-3200
        "KHX36",     # HyperX DDR4-3600
        # Server ECC
        "KSM26",     # DDR4-2666 ECC
        "KSM32",     # DDR4-3200 ECC
        "KSM48",     # DDR5 ECC
    ],
}


def source_findchips(session, brand: str) -> list[str]:
    """
    findchips.com — agregador de 40+ distribuidores (Supplyframe/Molex).

    Busca PNs por prefixo e extrai MPNs dos resultados HTML.
    Especialmente útil para Samsung eMCP e SK Hynix — boa cobertura
    de chips descontinuados/legado que sites oficiais não listam.

    Sem API key — curl_cffi bypass Cloudflare via impersonação Chrome.

    ╔═══════════════════════════════════════════════════════════════╗
    ║  Para adicionar marca: edite FINDCHIPS_SEARCH_TERMS.         ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    terms = FINDCHIPS_SEARCH_TERMS.get(brand, [])
    if not terms:
        logging.info(f"  findchips: sem termos configurados para {brand}")
        return []

    pns: list[str] = []

    for term in terms:
        url = f"https://www.findchips.com/search/{term}"
        try:
            soup = get(url, session)
            if not soup:
                time.sleep(DELAY)
                continue

            found_this: list[str] = []

            # Seletores primários para MPNs no findchips
            # O site lista PNs em <span class="part-number-links-primary"> ou
            # em <td class="td-mfr-pn"> dependendo da versão da UI.
            for sel in (
                "span.part-number-links-primary",
                "td.td-mfr-pn",
                "a.part-detail-link",
                "h2.part-title",
            ):
                for el in soup.select(sel):
                    raw = el.get_text(strip=True)
                    pn  = normalize_pn(raw)
                    if is_valid_pn(pn, brand):
                        found_this.append(pn)

            # Fallback: extrai de todos os links cujas URLs contêm o prefixo
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                # links de produto têm o MPN no texto do link
                pn = normalize_pn(text)
                if is_valid_pn(pn, brand):
                    found_this.append(pn)

            # Fallback genérico de texto
            found_this.extend(extract_pns(soup.get_text(" ", strip=True), brand))

            found_this = list(dict.fromkeys(found_this))
            if found_this:
                logging.info(f"    [findchips] '{term}': {len(found_this)} PNs")
            pns.extend(found_this)

        except Exception as e:
            logging.warning(f"    [findchips] Erro para '{term}': {e}")

        time.sleep(DELAY)

    result = list(dict.fromkeys(pns))
    logging.info(f"  findchips: {len(result)} PNs únicos")
    return result


# ── Arrow Electronics API ──────────────────────────────────────────────────────
#
# Arrow Electronics é o 3º maior distribuidor eletrônico do mundo.
# Diferença em relação a DigiKey/Mouser: tem linha direta com fabricantes Samsung,
# SK Hynix e Micron — catálogo complementar especialmente para chips de memória.
#
# Autenticação: API Key (cadastro gratuito em developer.arrow.com)
# Endpoint: https://api.arrow.com/itemservice/v4/en/search
#
# Cadastro (~2 min): https://developer.arrow.com/
#   1. "Sign Up" → preencha nome e e-mail
#   2. "Applications" → "New Application" → escolha "Item Service"
#   3. Copie a API Key para ARROW_API_KEY no .env
#
# ╔═══════════════════════════════════════════════════════════════╗
# ║  Para adicionar marca: edite ARROW_SEARCH_TERMS.             ║
# ╚═══════════════════════════════════════════════════════════════╝

ARROW_SEARCH_TERMS: dict[str, list[str]] = {
    "Samsung": [
        "KMQ", "KMR", "KMD", "KMF", "KMK", "KMG",
        "KLMB", "KLMC", "KLMD", "KLME",
        "KLUB", "KLUC",
        "K4U", "K3K", "K3L",
    ],
    "SK Hynix": [
        "H9HP", "H9HQ", "H9TQ", "HMCG", "HMBG",
        "H26M", "H26T", "H28U",
        "H8L", "H54G",
    ],
    "Micron": [
        "MTFC", "MT29F", "MT29E",
        "MTFD", "MT52", "MT53",
        "MT40A", "MT41K",
    ],
    "KIOXIA": [
        "THGBM", "THGBF", "THGAM", "THGBH",
        "THGNM", "THGJF", "TC58",
    ],
    "Elpida": [
        "EBJ", "EBK", "EBU",
        "EDF", "EDJ",
    ],
    "Nanya": [
        "NT5CC", "NT5CB", "NT6CL", "NT6CP", "NT8GA",
    ],
    # SanDisk iNAND — Arrow tem boa cobertura de eMMC industrial/mobile
    "SanDisk": [
        # Série 7xxx — mais presente em celulares Android
        "SDINBDA", "SDINBDD", "SDINBDG", "SDINBDE",
        # iNAND 8EU — geração moderna
        "SDTNQG", "SDTNRG", "SDTNPM",
        # Legado eMMC 5.0 / 4.x
        "SDIN8", "SDIN7", "SDIN5",
        # Industrial
        "SDCIT",
    ],
    # Kingston — módulos DDR para notebooks/desktops
    # Arrow tem boa cobertura de módulos de memória Kingston para o mercado profissional
    "Kingston": [
        # DDR3 (legacy notebooks 2010-2015)
        "KVR13", "KVR16",
        # DDR4 (notebooks 2016-2022) — KVR26 é o prefixo mais encontrado
        "KVR21", "KVR26", "KVR29", "KVR32",
        # DDR5 (notebooks 2022+)
        "KVR48", "KVR64",
        # HyperX gaming + Server ECC
        "KHX", "KSM26", "KSM32",
    ],
}


def source_arrow(session, brand: str) -> list[str]:
    """
    Arrow Electronics API v4 — 3º maior distribuidor eletrônico do mundo.

    Complementa DigiKey e Mouser com cobertura diferente para Samsung eMCP,
    SK Hynix LPDDR e Micron. API gratuita, sem Cloudflare.

    Requer ARROW_API_KEY no .env.
    Cadastro gratuito em: https://developer.arrow.com/

    ╔═══════════════════════════════════════════════════════════════╗
    ║  Para adicionar marca: edite ARROW_SEARCH_TERMS.             ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    api_key = os.getenv("ARROW_API_KEY", "").strip()
    if not api_key:
        logging.info("  arrow: ARROW_API_KEY não configurada — pulando")
        logging.info(
            "         Cadastro gratuito em: https://developer.arrow.com/"
        )
        return []

    terms = ARROW_SEARCH_TERMS.get(brand, [])
    if not terms:
        logging.info(f"  arrow: sem termos configurados para {brand}")
        return []

    pns: list[str] = []

    for term in terms:
        try:
            import urllib.request as _urlreq, urllib.parse as _urlparse

            params = _urlparse.urlencode({
                "q":      term,
                "apikey": api_key,
                "rows":   100,
                "start":  0,
            })
            req = _urlreq.Request(
                f"https://api.arrow.com/itemservice/v4/en/search?{params}",
                headers={"Accept": "application/json"},
            )
            with _urlreq.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())

            # Resposta: {"itemServiceResult": {"data": [{"partNumber": "KMQ..."}, ...]}}
            items = (
                data.get("itemServiceResult", {})
                    .get("data", [])
                or []
            )
            found_this: list[str] = []
            for item in items:
                raw = item.get("partNumber") or item.get("mpn") or ""
                pn  = normalize_pn(raw)
                if is_valid_pn(pn, brand):
                    found_this.append(pn)
            if found_this:
                logging.debug(f"    [arrow] '{term}': {len(found_this)} PNs")
            pns.extend(found_this)

        except Exception as e:
            logging.warning(f"    [arrow] Erro para '{term}': {e}")

        time.sleep(0.5)

    result = list(dict.fromkeys(pns))
    logging.info(f"  arrow: {len(result)} PNs únicos")
    return result


# ── Wayback Machine (Internet Archive) ────────────────────────────────────────
#
# Estratégia de backup para sites que bloqueiam scrapers (Cloudflare, GeoIP etc.).
# O Wayback Machine arquiva páginas públicas periodicamente e NÃO bloqueia scrapers.
# Usamos a CDX API para encontrar snapshots de 2023-2024 (período mais rico) e
# depois buscamos o HTML estático do arquivo — sem JS challenge, sem bot detection.
#
# ╔═══════════════════════════════════════════════════════════════╗
# ║  Para adicionar uma nova marca:                               ║
# ║  1. Adicione a entrada em WAYBACK_URLS com a lista de         ║
# ║     (url_original, label) — use páginas que listam PNs        ║
# ║  2. A função source_wayback() busca automaticamente o         ║
# ║     snapshot mais recente de cada URL via CDX API             ║
# ╚═══════════════════════════════════════════════════════════════╝

# URLs originais para buscar snapshots no Wayback Machine.
# Cada entrada é uma lista de (url_original, label_fonte) a serem buscadas.
# Priorize URLs que listam muitos PNs por página (listagens, categorias).
WAYBACK_URLS: dict[str, list[tuple[str, str]]] = {
    # ── Samsung ──────────────────────────────────────────────────────────────
    # REGRA: use apenas URLs sem query string — query strings com & quebram
    # o parâmetro da CDX API. Para glochip, use as páginas de categoria
    # (ex: /brand/samsung/) em vez de /search?keyword=...
    "Samsung": [
        # preduo — listagens estáticas por tipo (sem query string → CDX ok)
        ("https://www.preduo.com/eMCP-List",                "preduo/eMCP"),
        ("https://www.preduo.com/eMMC-List",                "preduo/eMMC"),
        ("https://www.preduo.com/UFS-List",                 "preduo/UFS"),
        ("https://www.preduo.com/LPDDR4-List",              "preduo/LPDDR4"),
        # serviceemmc — blog técnico; posts estáticos, bem arquivados
        ("https://www.serviceemmc.com/p/emmc-list.html",    "serviceemmc/emmc-list"),
        ("https://www.serviceemmc.com/p/emcp-list.html",    "serviceemmc/emcp-list"),
        # censtry — listas de PNs por tipo; páginas simples
        ("https://www.censtry.com/samsung-emmc-list/",      "censtry/eMMC"),
        ("https://www.censtry.com/samsung-emcp-list/",      "censtry/eMCP"),
        ("https://www.censtry.com/samsung-ufs-list/",       "censtry/UFS"),
        # wolfchip — categorias (sem query string)
        ("https://www.wolfchip.com/category/samsung/",      "wolfchip/samsung"),
        ("https://www.wolfchip.com/category/emmc/",         "wolfchip/emmc"),
        ("https://www.wolfchip.com/category/ufs/",          "wolfchip/ufs"),
    ],
    # ── SK Hynix ─────────────────────────────────────────────────────────────
    "SK Hynix": [
        ("https://www.preduo.com/eMCP-List",                "preduo/eMCP"),
        ("https://www.censtry.com/sk-hynix-emmc-list/",    "censtry/eMMC"),
        ("https://www.wolfchip.com/category/hynix/",        "wolfchip/hynix"),
    ],
    # ── Micron ───────────────────────────────────────────────────────────────
    "Micron": [
        ("https://www.preduo.com/eMMC-List",                "preduo/eMMC"),
        ("https://www.censtry.com/micron-emmc-list/",       "censtry/eMMC"),
        ("https://www.wolfchip.com/category/micron/",       "wolfchip/micron"),
    ],
    # ── KIOXIA / Toshiba ─────────────────────────────────────────────────────
    "KIOXIA": [
        ("https://www.preduo.com/eMMC-List",                "preduo/eMMC"),
        ("https://www.wolfchip.com/category/kioxia/",       "wolfchip/kioxia"),
        ("https://www.wolfchip.com/category/toshiba/",      "wolfchip/toshiba"),
    ],
    # ── Elpida ───────────────────────────────────────────────────────────────
    "Elpida": [
        ("https://www.preduo.com/eMCP-List",                "preduo/eMCP"),
    ],
    # ── Nanya ────────────────────────────────────────────────────────────────
    "Nanya": [
        ("https://www.preduo.com/eMCP-List",                "preduo/eMCP"),
    ],
    # ── GigaDevice ───────────────────────────────────────────────────────────
    "GigaDevice": [
        ("https://www.preduo.com/eMCP-List",                "preduo/eMCP"),
    ],
}


def _cdx_get_snapshot(original_url: str, session) -> str | None:
    """
    Consulta a CDX API do Wayback Machine para encontrar o snapshot mais
    recente disponível de uma URL.

    IMPORTANTE: a URL original é URL-encoded antes de ser passada como parâmetro
    da CDX API — sem isso, URLs com query strings (ex: glochip.com/search?keyword=X)
    quebram a requisição porque o '&' é interpretado como separador de parâmetro.

    Retorna a URL do snapshot (ex: https://web.archive.org/web/20240315.../url)
    ou None se não houver snapshot disponível.
    """
    # URL-encode the target URL to avoid breaking CDX query params
    encoded_url = _url_quote(original_url, safe="")

    cdx_url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url={encoded_url}"
        "&output=json"
        "&fl=timestamp,statuscode,original"
        "&from=20200101"        # janela ampla: 2020-2025
        "&to=20251231"
        "&limit=5"              # pega até 5 candidatos
        "&sort=reverse"         # mais recente primeiro
    )
    try:
        r = session.get(cdx_url, timeout=20)
        if r.status_code != 200:
            logging.debug(f"    [CDX] HTTP {r.status_code} para {original_url}")
            return None
        data = r.json()
        if not data:
            logging.debug(f"    [CDX] Nenhum snapshot para {original_url}")
            return None

        # CDX retorna [[header_row], [ts, sc, orig], ...]
        # Filtra o header e prefere snapshots com statuscode 200 ou 301/302
        rows = [row for row in data if row and row[0] != "timestamp"]
        if not rows:
            logging.debug(f"    [CDX] Nenhuma linha de resultado para {original_url}")
            return None

        # Prefere status 200; cai para qualquer outro se não tiver
        good = [r for r in rows if len(r) >= 2 and r[1] in ("200", "301", "302")]
        chosen = good[0] if good else rows[0]

        timestamp = chosen[0]
        orig      = chosen[2] if len(chosen) >= 3 else original_url
        snapshot  = f"https://web.archive.org/web/{timestamp}/{orig}"
        logging.debug(f"    [CDX] Snapshot escolhido: {timestamp} (status {chosen[1] if len(chosen)>=2 else '?'})")
        return snapshot

    except Exception as e:
        logging.debug(f"    [CDX] Erro para {original_url}: {e}")
        return None


def source_wayback(session, brand: str) -> list[str]:
    """
    Internet Archive Wayback Machine — backup para sites com bot-detection.

    Busca snapshots arquivados de 2023-2024 das URLs mais ricas de PNs para
    cada marca. archive.org não bloqueia scrapers, então isto funciona mesmo
    quando preduo/glochip/censtry retornam 0 via curl_cffi e Playwright.

    Esta fonte é especialmente valiosa como:
    - Safety net quando outras fontes falham
    - Verificação histórica de PNs descontinuados
    - Desbloqueio de sites com proteção geográfica ou Cloudflare agressivo

    ╔═════════════════════════════════════════════════════════════════╗
    ║  Para adicionar uma nova marca: edite WAYBACK_URLS acima.      ║
    ║  Não é necessário modificar esta função.                        ║
    ╚═════════════════════════════════════════════════════════════════╝
    """
    targets = WAYBACK_URLS.get(brand, [])
    if not targets:
        logging.info(f"  wayback: sem URLs configuradas para {brand}")
        return []

    pns: list[str] = []
    snapshot_hits = 0

    for original_url, label in targets:
        snapshot_url = _cdx_get_snapshot(original_url, session)
        if not snapshot_url:
            logging.debug(f"    [Wayback] sem snapshot para {label} ({original_url})")
            time.sleep(0.5)
            continue

        logging.info(f"    [Wayback] {label}: snapshot encontrado → {snapshot_url[:80]}...")
        soup = get(snapshot_url, session)
        if not soup:
            logging.debug(f"    [Wayback] falha ao buscar snapshot de {label}")
            time.sleep(DELAY)
            continue

        found = extract_pns(soup.get_text(" ", strip=True), brand)
        if found:
            pns.extend(found)
            snapshot_hits += 1
            logging.info(f"    [Wayback] {label}: {len(found)} PNs extraídos")
        else:
            logging.debug(f"    [Wayback] {label}: snapshot obtido mas sem PNs reconhecidos")

        time.sleep(DELAY)

    result = list(dict.fromkeys(pns))
    logging.info(
        f"  wayback: {len(result)} PNs únicos de {snapshot_hits}/{len(targets)} snapshots"
    )
    return result


# ── Source registry ────────────────────────────────────────────────────────────

ALL_SOURCES = {
    # ── Site oficial do fabricante (MELHOR FONTE — dado primário, sem bot detection) ─
    "samsung_semi": (source_samsung_semi, "semiconductor.samsung.com — site oficial Samsung; eMMC/UFS/eMCP/LPDDR"),

    # ── APIs de distribuidores (RECOMENDADAS — sem bot detection, dados estruturados) ──
    # Requerem cadastro gratuito — veja instruções nos comentários de cada função.
    # Configure as keys no .env antes de usar.
    "digikey":      (source_digikey,      "DigiKey API v4 — maior distribuidor mundial (OAuth2, gratuito)"),
    "mouser":       (source_mouser,       "Mouser API v1 — 2º maior distribuidor (API key, gratuito)"),
    "nexar":        (source_nexar,        "Nexar GraphQL API — agrega DigiKey+Mouser+Arrow+20 distribuidores (gratuito, 1k/mês)"),
    "arrow":        (source_arrow,        "Arrow Electronics API v4 — 3º maior distribuidor; catálogo complementar Samsung/Hynix (gratuito)"),

    # ── Fontes HTML (curl_cffi + Playwright fallback quando bloqueado) ──────
    "findchips":    (source_findchips,    "findchips.com — agrega 40+ distribuidores; boa cobertura eMCP legado (curl_cffi)"),
    "preduo":       (source_preduo,       "preduo.com — catálogos eMCP/eMMC/UFS/DDR (curl_cffi + Playwright)"),
    "glochip":      (source_glochip,      "glochip.com — agregador por prefixo (curl_cffi + Playwright)"),
    "serviceemmc":  (source_serviceemmc,  "serviceemmc.com — blog técnico PN×dispositivo (Samsung)"),
    "alldatasheet": (source_alldatasheet, "alldatasheet.com — base de datasheets (curl_cffi + Playwright)"),
    "lcsc":         (source_lcsc,         "lcsc.com — distribuidor chinês catálogo extenso"),
    "wolfchip":     (source_wolfchip,     "wolfchip.com — distribuidor Samsung/Hynix (curl_cffi + Playwright)"),
    "jotrin":       (source_jotrin,       "jotrin.com — distribuidor internacional (multi-marca)"),
    "censtry":      (source_censtry,      "censtry.com — comunidade técnica"),
    "chip1stop":    (source_chip1stop,    "chip1stop.com — distribuidor japonês Fujitsu; catálogo asiático"),
    "martview":     (source_martview,     "martview-forum.com — fórum de técnicos"),
    "gsm_forum":    (source_gsm_forum,    "gsm-forum.com — maior fórum GSM do mundo"),

    # ── Backup via Internet Archive ─────────────────────────────────────────
    # Nunca bloqueia scrapers — recupera snapshots históricos de sites
    # que agora têm Cloudflare ou bloqueio geográfico.
    # ATENÇÃO: URLs em WAYBACK_URLS não devem ter query strings com '&'.
    "wayback":      (source_wayback,      "archive.org Wayback Machine — backup histórico (nunca bloqueia)"),
}

DEFAULT_SOURCES = [
    "preduo", "glochip", "serviceemmc", "wolfchip", "jotrin", "alldatasheet", "censtry"
]

# Fontes por marca (padrão recomendado).
# ─────────────────────────────────────────────────────────────────────────────
# Estratégia de resiliência em camadas:
#   1. Fontes primárias (preduo, glochip, serviceemmc…) via curl_cffi
#   2. Fallback automático para Playwright quando curl_cffi retorna 0
#   3. wayback como última linha — snapshots históricos do Internet Archive
#
# Para adicionar uma nova marca:
#   1. Adicione a lista de fontes aqui (use wayback para marcas com cobertura
#      em preduo/glochip/censtry — ver WAYBACK_URLS)
#   2. Adicione prefixos nos dicts internos de cada fonte relevante
#   3. Adicione entradas em WAYBACK_URLS se a marca tiver dados em preduo/glochip
#   (Consulte docs/BRANDS.md para o guia completo passo-a-passo)
# ─────────────────────────────────────────────────────────────────────────────
BRAND_DEFAULT_SOURCES = {
    # Ordem de execução importa: site oficial do fabricante primeiro
    # (dado primário, zero Cloudflare), depois APIs de distribuidor,
    # depois fontes HTML, wayback como último safety net.
    #
    # Novas fontes:
    #   samsung_semi  → semiconductor.samsung.com (oficial Samsung, 3 camadas)
    #   nexar         → GraphQL que agrega DigiKey+Mouser+Arrow+20 distribuidores
    "Samsung":    [
        "samsung_semi",   # site oficial — DRAM via sitemap + eMCP via Playwright search
        "digikey",        # API: cadastro em developer.digikey.com
        "arrow",          # API: cadastro em developer.arrow.com (complementa DigiKey)
        "nexar",          # API: agregador GraphQL (free tier restrito)
        "mouser",         # API: cadastro em mouser.com/api-hub
        "findchips",      # scraping: agrega 40+ distribuidores (eMCP legado)
        "preduo", "glochip", "serviceemmc", "wolfchip",
        "alldatasheet", "jotrin", "censtry", "lcsc",
        "chip1stop",
        "wayback",
    ],
    "SK Hynix":   [
        "digikey", "arrow", "nexar", "mouser", "findchips",
        "preduo", "glochip", "wolfchip", "alldatasheet", "jotrin",
        "chip1stop", "wayback",
    ],
    "Micron":     [
        "digikey", "arrow", "nexar", "mouser", "findchips",
        "preduo", "glochip", "wolfchip", "alldatasheet", "jotrin",
        "chip1stop", "wayback",
    ],
    "KIOXIA":     [
        "digikey", "arrow", "nexar", "mouser", "findchips",
        "preduo", "glochip", "alldatasheet", "jotrin",
        "chip1stop", "wayback",
    ],
    "Elpida":     ["digikey", "nexar", "mouser", "jotrin", "alldatasheet", "chip1stop", "wayback"],
    "Nanya":      ["digikey", "nexar", "mouser", "jotrin", "alldatasheet", "lcsc", "chip1stop", "wayback"],
    "Kingston":   ["digikey", "arrow", "nexar", "mouser", "findchips", "jotrin", "alldatasheet"],
    "SanDisk":    ["digikey", "arrow", "nexar", "mouser", "findchips", "jotrin", "alldatasheet"],
    "ISSI":       ["digikey", "nexar", "mouser", "jotrin", "alldatasheet", "lcsc", "chip1stop"],
    "Rayson":     ["nexar", "jotrin"],
    "GigaDevice": ["digikey", "nexar", "mouser", "jotrin", "alldatasheet", "lcsc", "chip1stop", "wayback"],
    "Qualcomm":   ["digikey", "nexar", "mouser", "jotrin"],
    "MediaTek":   ["digikey", "nexar", "mouser", "jotrin"],
    "Spreadtrum": ["nexar", "jotrin"],
}


# ── State management ───────────────────────────────────────────────────────────

def load_state(brand: str) -> dict:
    path = STATE_DIR / f"{brand}_pns.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {
        "brand": brand,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources_done": [],
        "pns": [],
        "total": 0,
    }


def save_state(brand: str, state: dict):
    path = STATE_DIR / f"{brand}_pns.json"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state["total"] = len(state["pns"])
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    all_brand_names = sorted(BRAND_LETTERS.keys())

    parser = argparse.ArgumentParser(
        description="Coleta Part Numbers de múltiplas fontes (todas as gerações)")
    parser.add_argument("--brand",        default="Samsung",
                        help=f"Marca alvo. Disponíveis: {', '.join(all_brand_names)}")
    parser.add_argument("--sources",      default="",
                        help="Fontes separadas por vírgula (padrão: automático por marca)")
    parser.add_argument("--force",        action="store_true",
                        help="Força re-scraping de fontes já concluídas")
    parser.add_argument("--no-db-dedup",  action="store_true",
                        help="Não verifica banco Django para deduplicação")
    parser.add_argument("--list-sources", action="store_true",
                        help="Lista fontes disponíveis e sai")
    parser.add_argument("--list-brands",  action="store_true",
                        help="Lista marcas suportadas e sai")
    args = parser.parse_args()

    if args.list_sources:
        print("\nFontes disponíveis:\n")
        for name, (_, desc) in ALL_SOURCES.items():
            marker = "●" if name in DEFAULT_SOURCES else "○"
            print(f"  {marker} {name:<14} {desc}")
        print(f"\n● = default   ○ = opcional\n")
        return

    if args.list_brands:
        print("\nMarcas suportadas:\n")
        for b in all_brand_names:
            srcs = BRAND_DEFAULT_SOURCES.get(b, DEFAULT_SOURCES)
            print(f"  {b:<16} fontes: {', '.join(srcs)}")
        print()
        return

    brand = args.brand

    # Valida marca
    if brand not in BRAND_LETTERS:
        # Tenta match case-insensitive
        match = next((b for b in BRAND_LETTERS if b.lower() == brand.lower()), None)
        if match:
            brand = match
        else:
            print(f"Marca '{brand}' desconhecida. Use --list-brands para ver as disponíveis.")
            sys.exit(1)

    # Seleciona fontes
    if args.sources:
        sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    else:
        sources = BRAND_DEFAULT_SOURCES.get(brand, DEFAULT_SOURCES)

    # Logging — sem double-logging quando stdout é redirecionado para arquivo
    log_file = LOGS_DIR / f"{brand}_collect.log"
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    root_logger.addHandler(fh)
    if sys.stdout.isatty():
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root_logger.addHandler(sh)

    logging.info("=" * 60)
    logging.info(f"collect_pns.py — {brand}")
    logging.info(f"Fontes: {sources}")
    logging.info("=" * 60)

    if not args.no_db_dedup:
        load_db_pns()

    state = load_state(brand)
    logging.info(f"Estado atual: {state['total']} PNs de {state['sources_done']}")

    if _CURL_AVAILABLE:
        session = CurlSession(impersonate="chrome124")
        session.headers.update(HEADERS)
        logging.info("  Cliente HTTP: curl_cffi (Chrome TLS) — bypass bot-detection ativo")
    else:
        session = requests.Session()
        session.headers.update(HEADERS)
        logging.warning("  curl_cffi não instalado — usando requests padrão (pode ser bloqueado)"
                        " | instale com: pip install curl_cffi")

    new_total = 0

    for source_name in sources:
        if source_name not in ALL_SOURCES:
            logging.warning(f"Fonte desconhecida: '{source_name}' — ignorando")
            continue

        if source_name in state["sources_done"] and not args.force:
            logging.info(f"✓ {source_name}: já coletado — pulando (use --force para re-scrape)")
            continue

        logging.info(f"\n▶ Coletando de: {source_name}")
        fn = ALL_SOURCES[source_name][0]

        try:
            raw_pns = fn(session, brand)
        except KeyboardInterrupt:
            logging.warning("\nInterrompido — salvando checkpoint...")
            save_state(brand, state)
            sys.exit(0)
        except Exception as e:
            logging.error(f"  ✗ {source_name}: erro inesperado: {e}")
            continue

        existing_in_state = set(state["pns"])
        new_pns = []
        skipped_db = 0
        for pn in raw_pns:
            if pn in existing_in_state:
                continue
            if already_in_db(pn):
                skipped_db += 1
                continue
            new_pns.append(pn)
            existing_in_state.add(pn)

        state["pns"].extend(new_pns)
        if source_name not in state["sources_done"]:
            state["sources_done"].append(source_name)

        new_total += len(new_pns)
        skip_msg = f" ({skipped_db} já no banco)" if skipped_db else ""
        logging.info(f"  ✓ {source_name}: {len(raw_pns)} encontrados → {len(new_pns)} novos{skip_msg}")

        save_state(brand, state)
        logging.info(f"  💾 Checkpoint salvo — total: {state['total']} PNs")
        time.sleep(DELAY)

    logging.info(f"\n{'='*60}")
    logging.info(f"✅ Coleta finalizada — {brand}")
    logging.info(f"   PNs novos nesta rodada : {new_total}")
    logging.info(f"   Total acumulado        : {state['total']}")
    logging.info(f"   Fontes concluídas      : {state['sources_done']}")
    logging.info(f"   Estado salvo em        : scripts/state/{brand}_pns.json")
    logging.info(f"   Log em                 : scripts/logs/{brand}_collect.log")
    logging.info(f"\n   Próximo passo:")
    logging.info(f"   (specs preenchidas por confirmação manual no admin)")


if __name__ == "__main__":
    main()
