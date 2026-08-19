"""
fill_capacity_from_micron_api.py
================================
Preenche capacidade de KnownParts Micron que estão sem dados de capacidade,
consultando a API FBGA oficial da Micron e o mapa de decodificação MIC_MCP_CAP.

FONTES (em ordem de prioridade)
-------------------------------
1. PN MTFC (modelo numérico — convenção oficial Micron):
   - MTFC{N}G...   → capacidade = N GB    (N=4,8,16,32,64,128,256,512)
   - MTFC{N}T...   → capacidade = N × 1000 GB (ex: MTFC1T = 1TB = 1000GB)
   - Fonte: ordering guide oficial Micron (Product Family Naming Convention)
   - Não requer consulta à API; é derivado do próprio PN que já está no banco

2. API FBGA Micron (reverse lookup FBGA → produto):
   - URL: ...getpartbyfbgacode/-/-/-/en_US/-/-/{FBGA}
   - Retorna: part-name (ex: "2100AT 128GB BGA1620S1 SSD") — dado oficial Micron
   - Salvo em notes com carimbo [Micron FBGA API]
   - Para SSD/MTFD: extrai capacity do part-name (formatos explícitos "128GB", "1.8TB")
   - Para MTFC: part-name salvo em notes para auditoria, mas NÃO usado para capacity
     (motivo: part-names de eMMC/UFS usam "G" = Gbit, não GB, o que seria ambíguo)

3. Mapa MIC_MCP_CAP (para família MT29VZZZ / MT29TZZZ / MT30AZZZ):
   - Chave pn[8:11] → (NAND_GB, RAM_GB) — verificado contra COMPONENT DENSITY
     dos CSVs oficiais da Micron (vide populate_micron_mcp.py)
   - Preenche emcp_nand e emcp_ram diretamente

NOTA SOBRE UNIDADES NAS PART-NAMES MICRON
------------------------------------------
Atenção: a notação "G" em part-names MTFC (eMMC/UFS) é GBIT, não GB:
  "EMMC 64G VFBGA"     → MTFC8G...  → 64 Gbit = 8 GB  ← nunca usar como GB!
  "MLC EMMC 512G LFBGA"→ MTFC64G...  → 512 Gbit = 64 GB
  "512Gb Universal..."  → 512 Gbit = 64 GB (Gb explícito)
Apenas part-names de SSD (MTFD) usam "GB" explícito em bytes.

COBERTURA
---------
Todos os KnownParts Micron com fbga_code preenchido e sem capacity/emcp_nand/emcp_ram.
Chips sem fbga_code são ignorados (impossível fazer reverse lookup sem FBGA).

Uso:
    python manage.py fill_capacity_from_micron_api
    python manage.py fill_capacity_from_micron_api --dry-run
    python manage.py fill_capacity_from_micron_api --limit 50
    python manage.py fill_capacity_from_micron_api --delay 1.5
    python manage.py fill_capacity_from_micron_api --verbose
    python manage.py fill_capacity_from_micron_api --fbga JZ177   (teste)
    python manage.py fill_capacity_from_micron_api --fix-wrong-mtfc  (corrige valores errados já salvos)
"""

import re
import time
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)

# ── API endpoint (reverse lookup: FBGA → PN + part-name) ─────────────────────
MICRON_FBGA_REVERSE_API = (
    "https://www.micron.com/content/micron/us/en/sales-support/design-tools/"
    "fbga-parts-decoder/_jcr_content.products.json/"
    "getpartbyfbgacode/-/-/-/en_US/-/-/{fbga}"
)

MICRON_FBGA_SOURCE_URL = (
    "https://www.micron.com/sales-support/design-tools/fbga-parts-decoder"
)

# ⚠ SEM User-Agent aqui de propósito (2026-08-19). O curl_cffi já emite o UA
# que combina com o TLS/HTTP2 do perfil que ele imita; cravar um UA à mão
# criava a incoerência clássica que WAF adora — o handshake dizia Chrome 110 e
# o cabeçalho dizia Chrome 124. Só o fallback (requests puro) precisa de um UA
# escrito, e aí ele vai em _UA_FALLBACK.
_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.micron.com/sales-support/design-tools/fbga-parts-decoder",
}

_UA_FALLBACK = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

#: Perfis do curl_cffi, do mais novo pro mais velho — o primeiro que a versão
#: instalada aceitar. Perfil ANTIGO é pior que nenhum: um fingerprint de
#: Chrome 110 em 2026 não existe mais no mundo real e denuncia o robô.
_PERFIS_TLS = ("chrome131", "chrome124", "chrome120", "chrome116", "chrome110")

#: Assinaturas da página de bloqueio (F5 BIG-IP ASM). Chega com HTTP 200 e
#: corpo HTML — sem isto, o `r.json()` estoura, a função devolve None e o
#: chamador lê como "FBGA sem resultado". Bloqueio virando "vazio" é a pior
#: leitura possível: foi assim que a investigação da Micron quase concluiu
#: "a fonte está vazia" quando o que havia era porta fechada.
_MARCAS_DE_BLOQUEIO = ("request rejected", "requested url was rejected",
                       "support id is", "access denied")


class MicronBloqueado(Exception):
    """O WAF da Micron recusou a requisição (≠ FBGA sem resultado)."""

# Famílias MCP com decode map para NAND+RAM individuais
MCP_FAMILIES = ("MT29VZZZ", "MT29TZZZ", "MT30AZZZ")

# Prefixos de chips Micron standalone (eMMC, UFS, LPDDR — não MCP)
STANDALONE_PREFIXES = (
    "MTFC",   # eMMC Micron
    "MT53",   # LPDDR4
    "MT62",   # NAND
    "MT63",   # NAND
    "MT64",   # NAND
    "MTFD",   # SSD / storage
)

# ── Regex para extrair densidade do part-name ────────────────────────────────
#
# ATENÇÃO SOBRE UNIDADES NAS PART-NAMES MICRON:
#   MTFC eMMC/UFS: "G" = Gbit → dividir por 8 para obter GB
#     "EMMC 64G VFBGA"    = 64 Gbit = 8 GB  (chip MTFC8G)
#     "MLC EMMC 512G LFBGA" = 512 Gbit = 64 GB  (chip MTFC64G)
#   MTFD SSD: "GB" explícito e correto
#     "128GB BGA1620S1 SSD" = 128 GB
#     "1.8TB 4150 AT SSD"   = 1.8 TB
#   Explícito "Gb" (lowercase b): sempre Gbit
#     "512Gb Universal Flash Storage" = 512 Gbit = 64 GB
#
# Para chips MTFC: NÃO usar part-name para capacity — usar PN (ex: MTFC8G=8GB).
# Para chips MTFD SSD: usar part-name com "GB" / "TB" / "Gb" explícitos.

# GB case-sensitive (NÃO re.I — para não capturar "Gb" como GB)
_DENSITY_RE_GB  = re.compile(r'(\d+(?:\.\d+)?)\s*GB\b')         # explícito GB (uppercase obrigatório)
_DENSITY_RE_Gb  = re.compile(r'(\d+(?:\.\d+)?)\s*Gb\b')         # case-sensitive: Gbit
_DENSITY_RE_TB  = re.compile(r'(\d+(?:\.\d+)?)\s*TB\b',  re.I)  # Terabytes

# Regex para extrair capacidade do PN MTFC (convenção oficial Micron)
# MTFC{N}G... → N GB    MTFC{N}T... → N × 1000 GB
_MTFC_CAP_RE = re.compile(r'^MTFC(\d+)([GT])', re.I)


# ── HTTP session ──────────────────────────────────────────────────────────────

def _make_session():
    """Prefere curl_cffi (TLS de Chrome real) para não ser barrado no WAF.

    Usa o perfil MAIS NOVO que a versão instalada aceitar (_PERFIS_TLS). Um
    perfil velho é pior que nenhum: em 2026 um fingerprint de Chrome 110 não
    corresponde a navegador nenhum vivo, e é justamente isso que o WAF procura.
    """
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        import requests as std_requests
        s = std_requests.Session()
        s.headers["User-Agent"] = _UA_FALLBACK
        s._is_cffi = False
        s._perfil = ""
        return s
    for perfil in _PERFIS_TLS:
        try:
            s = cffi_requests.Session(impersonate=perfil)
        except Exception:
            continue            # versão instalada não conhece este perfil
        s._is_cffi = True
        s._perfil = perfil
        return s
    s = cffi_requests.Session()
    s._is_cffi = True
    s._perfil = "(padrão)"
    return s


# ── Reverse FBGA lookup ───────────────────────────────────────────────────────

def _e_bloqueio(status: int, corpo: str) -> bool:
    """O corpo é a página de bloqueio do WAF? (F5 BIG-IP ASM e parentes.)

    Ela chega com HTTP 200 e HTML — indistinguível de "sem resultado" para
    quem só tenta `r.json()`. Também trata 403 com corpo HTML.
    """
    baixo = (corpo or "").lower()
    if any(m in baixo for m in _MARCAS_DE_BLOQUEIO):
        return True
    return status == 403 and "<html" in baixo


def _query_by_fbga(fbga: str, session, retries: int = 3, verbose: bool = False) -> dict | None:
    """
    Consulta a API Micron pelo FBGA code (reverse lookup).

    Retorna dict: {"part_name": "...", "part_number": "...", "sub_category": "..."} ou None.
    """
    url = MICRON_FBGA_REVERSE_API.format(fbga=fbga)

    if verbose:
        print(f"\n  [DEBUG] URL: {url}")

    for attempt in range(retries):
        try:
            r = session.get(url, headers=_HEADERS, timeout=25)

            if verbose:
                print(f"  [DEBUG] Status: {r.status_code}")
                print(f"  [DEBUG] Body (300 chars): {r.text[:300]!r}")

            corpo = r.text or ""
            if _e_bloqueio(r.status_code, corpo):
                raise MicronBloqueado(
                    f"HTTP {r.status_code} — o WAF da Micron recusou a "
                    f"requisição (FBGA {fbga}).")

            if r.status_code == 200:
                try:
                    data = r.json()
                except Exception:
                    # Não é bloqueio conhecido nem JSON: some com o motivo se
                    # devolver None aqui. Melhor levantar do que virar "vazio".
                    raise MicronBloqueado(
                        f"resposta HTTP 200 NÃO-JSON para FBGA {fbga} — "
                        f"provável página de bloqueio/interstitial. "
                        f"Início do corpo: {corpo[:120]!r}")

                # Normaliza lista
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

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    part_name = (
                        item.get("part-name")
                        or item.get("partName")
                        or item.get("part_name")
                        or ""
                    ).strip()
                    part_number = (
                        item.get("part-number")
                        or item.get("partNumber")
                        or item.get("part_number")
                        or ""
                    ).strip()
                    sub_cat = (
                        item.get("sub-category")
                        or item.get("subCategory")
                        or item.get("sub_category")
                        or ""
                    ).strip()
                    if part_name or part_number:
                        return {
                            "part_name":    part_name,
                            "part_number":  part_number,
                            "sub_category": sub_cat,
                        }
                return None

            elif r.status_code == 404:
                return None

            elif r.status_code in (429, 503):
                wait = 5 * (attempt + 1)
                logger.warning("HTTP %s (rate limit?) para FBGA %s — aguardando %ds",
                               r.status_code, fbga, wait)
                time.sleep(wait)
                continue
            else:
                logger.warning("HTTP %s para FBGA %s (tentativa %d/%d)",
                               r.status_code, fbga, attempt + 1, retries)

        except MicronBloqueado:
            raise                      # bloqueio NUNCA vira "sem resultado"
        except Exception as e:
            logger.warning("Erro na tentativa %d/%d para FBGA %s: %s",
                           attempt + 1, retries, fbga, e)
            if verbose:
                print(f"  [DEBUG] Exceção: {e}")

        time.sleep(1.5 * (attempt + 1))

    return None


# ── Parsers de part-name ──────────────────────────────────────────────────────

def _capacity_from_mtfc_pn(pn: str) -> str | None:
    """
    Extrai capacidade diretamente do PN de chips MTFC (convenção oficial Micron).

    Micron Ordering Guide — Product Family Naming Convention:
      MTFC{N}G... → N GB   (N = 4, 8, 16, 32, 64, 128, 256, 512)
      MTFC{N}T... → N TB   (N = 1, 2)

    Esta função é a fonte primária para chips MTFC — mais confiável que
    parsear o part-name, que usa "G" = Gbit nas linhas de eMMC/UFS.

    Exemplos:
      "MTFC8GACAAAM-1M WT"  → "8GB"
      "MTFC64GAZAOTD-AAT"   → "64GB"
      "MTFC128GAZAUT-AAT"   → "128GB"
      "MTFC1T..."           → "1000GB"  (1 TB)
    """
    pn_clean = re.sub(r'[^A-Z0-9]', '', pn.upper())
    m = _MTFC_CAP_RE.match(pn_clean)
    if not m:
        return None
    n    = int(m.group(1))
    unit = m.group(2).upper()
    if unit == 'G':
        return f"{n}GB"
    elif unit == 'T':
        return f"{n * 1000}GB"  # TB → GB
    return None


def _parse_part_name_ssd(part_name: str) -> str | None:
    """
    Extrai capacidade de chips SSD/MTFD do part-name.
    Suporta: "128GB", "1.8TB", "512Gb" (Gbit → GB).
    NÃO deve ser chamado para chips MTFC eMMC/UFS
    (onde "G" significa Gbit, não GB).

    Exemplos (SSD MTFD):
      "2100AT 128GB BGA1620S1 SSD"         → "128GB"
      "MTFDKER1T8TGK-1BM45A2YY 1.8TB SSD" → "1800GB"
      "MTFDKEL128THE-1BM15ATYY 128GB SSD"  → "128GB"
    """
    # TB primeiro (para evitar match parcial do número em "1.8TB" → "1GB")
    m = _DENSITY_RE_TB.search(part_name)
    if m:
        tb = float(m.group(1))
        gb = int(tb * 1000)
        return f"{gb}GB"

    # Explícito GB (case-sensitive: não captura "Gb")
    m = _DENSITY_RE_GB.search(part_name)
    if m:
        return f"{int(float(m.group(1)))}GB"

    # Explícito Gbit: converte Gbit → GB
    m = _DENSITY_RE_Gb.search(part_name)
    if m:
        gb = float(m.group(1)) / 8
        return f"{int(gb)}GB" if gb == int(gb) else f"{gb:.1f}GB"

    return None


def _parse_part_name_total_gbit(part_name: str) -> str | None:
    """
    Extrai densidade TOTAL de chips MCP do part-name.
    Salvo apenas em notes como referência oficial (auditoria).

    Exemplos:
      "uMCP/LPDDR4 544Gb VFBGA"    → "544Gb"
      "MLC EMMC/LPDDR2 72Gb VFBGA" → "72Gb"
    """
    # Explícito Gbit (case-sensitive: "Gb" ≠ "GB")
    m = _DENSITY_RE_Gb.search(part_name)
    if m:
        return f"{m.group(1)}Gb"

    # Explícito GB (raro em MCP, mas coberto)
    m = _DENSITY_RE_GB.search(part_name)
    if m:
        return f"{m.group(1)}GB"

    # TB
    m = _DENSITY_RE_TB.search(part_name)
    if m:
        return f"{m.group(1)}TB"

    return None


# ── Decode map lookup ─────────────────────────────────────────────────────────

def _decode_mcp_capacity(pn: str) -> tuple[str, str] | None:
    """
    Usa o mapa MIC_MCP_CAP para obter NAND+RAM de chips MT29VZZZ/MT30AZZZ.

    Retorna (nand_gb, ram_gb) se a chave pn[8:11] estiver no mapa, ou None.

    Fonte primária: DecodeMap do banco, populado por populate_micron_mcp.py
    e verificado contra COMPONENT DENSITY dos CSVs oficiais da Micron.
    """
    if len(pn) < 11:
        return None

    # Remove caracteres não-alfanuméricos antes de extrair (PN pode ter sufixos)
    pn_clean = re.sub(r'[^A-Z0-9]', '', pn.upper())
    key = pn_clean[8:11]

    if not key:
        return None

    from chips.models import DecodeMap
    entry = DecodeMap.objects.filter(
        map_name="MIC_MCP_CAP",
        char_key=key,
    ).values("val_primary", "val_secondary").first()

    if entry:
        return entry["val_primary"], entry["val_secondary"]
    return None


def _is_mcp_pn(pn: str) -> bool:
    """Retorna True se o PN pertence a uma família MCP Micron."""
    pn_upper = pn.upper()
    return any(pn_upper.startswith(f) for f in MCP_FAMILIES)


def _is_standalone_pn(pn: str) -> bool:
    """Retorna True se o PN pertence a um chip Micron standalone."""
    pn_upper = pn.upper()
    return any(pn_upper.startswith(f) for f in STANDALONE_PREFIXES)


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Preenche capacidade de KnownParts Micron sem dados de capacidade, "
        "consultando a API FBGA oficial da Micron (reverse lookup por FBGA code) "
        "e o mapa MIC_MCP_CAP verificado. Fonte oficial: micron.com/fbga-parts-decoder."
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
            help="Processa no máximo N chips (0 = sem limite).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            metavar="SEG",
            help="Pausa em segundos entre requests à API (padrão: 1.0).",
        )
        parser.add_argument(
            "--fbga",
            dest="fbga_filter",
            metavar="FBGA_CODE",
            help="Processa apenas este FBGA específico (para teste).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Mostra detalhes de cada request e parse.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Reprocessa chips que já têm emcp_nand/emcp_ram preenchidos "
                "(útil para corrigir dados antigos)."
            ),
        )
        parser.add_argument(
            "--fix-wrong-mtfc",
            action="store_true",
            dest="fix_wrong_mtfc",
            help=(
                "Modo de correção: corrige capacidades MTFC salvas erradas pela execução "
                "anterior com o bug Gb→GB. Não consulta a API — recalcula direto do PN. "
                "Ex: MTFC8G com capacity='64GB' → corrige para '8GB'."
            ),
        )

    def handle(self, *args, **options):
        from chips.models import KnownPart

        dry            = options["dry_run"]
        limit          = options["limit"]
        delay          = options["delay"]
        verbose        = options["verbose"]
        force          = options["force"]
        fix_wrong_mtfc = options.get("fix_wrong_mtfc", False)
        fbga_filter    = options.get("fbga_filter")

        # ── Modo correção: recalcula MTFC a partir do PN sem consultar a API ──
        if fix_wrong_mtfc:
            self._fix_wrong_mtfc_capacities(dry, verbose)
            return

        if dry:
            self.stdout.write(self.style.WARNING(
                "⚠  DRY RUN — nenhuma alteração será salva.\n"
            ))

        # ── Seleciona candidatos ──────────────────────────────────────────────
        qs = KnownPart.objects.filter(
            brand__name="Micron",
        ).exclude(
            fbga_code=""
        ).exclude(
            fbga_code__isnull=True
        )

        if not force:
            # Filtra apenas chips sem dados de capacidade
            qs = qs.filter(
                Q(emcp_nand="") | Q(emcp_nand__isnull=True)
            ).filter(
                Q(emcp_ram="") | Q(emcp_ram__isnull=True)
            ).filter(
                Q(capacity="") | Q(capacity__isnull=True)
            )

        # ⚠ `--fbga ""` (variável de shell não expandida) já disparou uma
        # varredura de 1.462 requisições sem querer (2026-08-18) — que é a
        # explicação mais provável do bloqueio de IP que veio depois. Passar a
        # flag e ela chegar VAZIA nunca significa "faz tudo": significa que o
        # comando de quem chamou está errado.
        if fbga_filter is not None:
            alvo = (fbga_filter or "").strip().upper()
            if not alvo:
                raise CommandError(
                    "--fbga veio VAZIO. Isso quase sempre é variável de shell "
                    "não expandida\n(ex.: `--fbga $C` com $C vazio) — e sem esta "
                    "trava viraria uma\nVARREDURA de todos os FBGA da Micron, "
                    "que é como se queima o IP no WAF.\n"
                    "Informe o código (ex.: --fbga D8KFG) ou omita a flag para "
                    "processar todos.")
            qs = qs.filter(fbga_code=alvo)

        total = qs.count()

        if limit:
            qs = qs[:limit]

        self.stdout.write(
            f"KnownParts Micron com FBGA sem capacidade: {total}"
            + (f"  (processando: {min(limit, total) if limit else total})" if limit else "")
            + "\n"
        )

        if total == 0:
            self.stdout.write("Nada a fazer.")
            return

        # ── Inicializa sessão HTTP ────────────────────────────────────────────
        session = _make_session()
        if not getattr(session, "_is_cffi", False):
            self.stdout.write(self.style.WARNING(
                "  ℹ  curl_cffi não instalado — usando requests padrão.\n"
                "     Para melhor bypass: pip install curl_cffi\n"
            ))

        # ── Processa ──────────────────────────────────────────────────────────
        counts = {
            "api_ok":          0,   # part-name obtido da API
            "api_no_result":   0,   # API não retornou resultado
            "decode_map":      0,   # capacidade via MIC_MCP_CAP
            "standalone_cap":  0,   # capacidade de chip standalone via part-name
            "notes_only":      0,   # apenas part-name salvo em notes (MCP sem decode)
            "skipped":         0,   # chip sem FBGA ou sem prefix reconhecido
            "errors":          0,
        }

        list_qs = list(qs)
        total_to_process = len(list_qs)

        for idx, kp in enumerate(list_qs, 1):
            fbga = kp.fbga_code
            pn   = kp.part_number

            self.stdout.write(
                f"\n[{idx}/{total_to_process}] FBGA={fbga}  PN={pn[:50]}",
                ending="",
            )
            self.stdout.flush()

            # ── Consulta API (reverse lookup) ─────────────────────────────────
            try:
                api_result = _query_by_fbga(fbga, session, verbose=verbose)
            except MicronBloqueado as e:
                # Para TUDO. Continuar a fila só empilha requisição recusada no
                # mesmo IP — em WAF de bloqueio por reputação, insistir RENOVA
                # a punição em vez de esperá-la vencer.
                raise CommandError(
                    f"BLOQUEADO pelo WAF da Micron — {e}\n\n"
                    f"  Isto NÃO é 'FBGA sem resultado': a resposta nem chegou "
                    f"a ser JSON.\n"
                    f"  Perfil TLS usado: {getattr(session, '_perfil', '?') or 'requests puro'}\n\n"
                    f"  O que costuma resolver, nesta ordem:\n"
                    f"    1. PARAR de tentar por algumas horas — cada tentativa "
                    f"recusada renova o bloqueio;\n"
                    f"    2. rodar de OUTRA REDE/IP (o bloqueio é por origem);\n"
                    f"    3. conferir se curl_cffi está instalado (sem ele o TLS "
                    f"denuncia o robô).\n"
                    f"  E NUNCA rodar a varredura completa: foi o que queimou o "
                    f"IP em 2026-08-18.")

            if api_result:
                part_name = api_result.get("part_name", "")
                sub_cat   = api_result.get("sub_category", "")
                counts["api_ok"] += 1
                self.stdout.write(
                    self.style.SUCCESS(f"\n  part-name: {part_name!r}  sub-cat: {sub_cat!r}")
                )
            else:
                part_name = ""
                sub_cat   = ""
                counts["api_no_result"] += 1
                self.stdout.write(self.style.WARNING("\n  API: sem resultado"))

            # ── Determina capacidade ──────────────────────────────────────────
            new_emcp_nand = ""
            new_emcp_ram  = ""
            new_capacity  = ""
            notes_append  = ""

            is_mcp        = _is_mcp_pn(pn)
            is_standalone = _is_standalone_pn(pn)

            if is_mcp:
                # ── MCP: decodifica via MIC_MCP_CAP primeiro ─────────────────
                decoded = _decode_mcp_capacity(pn)
                if decoded:
                    nand_gb, ram_gb = decoded

                    # Interface: UFS ou eMMC baseado em source_url
                    src = kp.source_url or ""
                    if "ufs-based-mcp" in src:
                        iface = "UFS 2.2"
                    elif "emmc-based-mcp" in src:
                        iface = "eMMC 5.1"
                    else:
                        # Fallback: usa subtype para inferir interface da família
                        iface = _infer_interface(pn)

                    new_emcp_nand = f"{iface} {nand_gb}"
                    new_emcp_ram  = f"LPDDR{_infer_lpddr_gen(pn)} {ram_gb}"
                    counts["decode_map"] += 1
                    self.stdout.write(
                        f"  decode_map: {new_emcp_nand} + {new_emcp_ram}"
                    )

                if part_name:
                    # Salva total Gbit em notes (carimbo oficial)
                    total_dens = _parse_part_name_total_gbit(part_name)
                    stamp = f"[Micron FBGA API] part-name: {part_name!r}"
                    if total_dens:
                        stamp += f" — densidade total: {total_dens}"
                    notes_append = stamp
                    if decoded:
                        counts["notes_only"]  # já contado via decode_map
                    else:
                        counts["notes_only"] += 1
                        self.stdout.write(f"  notes: {stamp}")

            elif is_standalone:
                # ── Standalone: capacidade por família ───────────────────────
                is_mtfc = pn.upper().startswith("MTFC")
                is_mtfd = pn.upper().startswith("MTFD")

                if is_mtfc:
                    # FONTE PRIMÁRIA para MTFC: convenção do próprio PN (oficial Micron)
                    # Part-name usa "G" = Gbit (não GB) para eMMC/UFS → não parsear!
                    cap = _capacity_from_mtfc_pn(pn)
                    if cap:
                        new_capacity = cap
                        counts["standalone_cap"] += 1
                        self.stdout.write(f"  MTFC PN → cap: {cap}")
                    # Part-name salvo em notes apenas como referência
                    if part_name:
                        notes_append = f"[Micron FBGA API] part-name: {part_name!r}"

                elif is_mtfd:
                    # SSD: part-name usa GB/TB explícitos — parse correto
                    if part_name:
                        cap = _parse_part_name_ssd(part_name)
                        if cap:
                            new_capacity = cap
                            counts["standalone_cap"] += 1
                            self.stdout.write(f"  MTFD SSD → cap: {cap}")
                        notes_append = f"[Micron FBGA API] part-name: {part_name!r}"

                else:
                    # MT53 (LPDDR4), MT62/63/64 (NAND) — parse SSD (usa GB explícito)
                    if part_name:
                        cap = _parse_part_name_ssd(part_name)
                        if cap:
                            new_capacity = cap
                            counts["standalone_cap"] += 1
                            self.stdout.write(f"  standalone cap: {cap}")
                        notes_append = f"[Micron FBGA API] part-name: {part_name!r}"

            else:
                # PN não reconhecido — salva apenas part-name em notes
                if part_name:
                    notes_append = f"[Micron FBGA API] part-name: {part_name!r}"
                    counts["notes_only"] += 1
                    self.stdout.write(f"  notes: {notes_append}")
                else:
                    counts["skipped"] += 1
                    self.stdout.write("  PN não reconhecido e sem part-name — pulando")

            # ── Salva no banco ────────────────────────────────────────────────
            if not (new_emcp_nand or new_emcp_ram or new_capacity or notes_append):
                self.stdout.write("  → nada a salvar")
                time.sleep(delay)
                continue

            if dry:
                self.stdout.write(self.style.WARNING("  [DRY] não salvo"))
                time.sleep(delay)
                continue

            try:
                with transaction.atomic():
                    changed = False
                    update_fields = []

                    if new_emcp_nand and (force or not kp.emcp_nand):
                        kp.emcp_nand = new_emcp_nand
                        update_fields.append("emcp_nand")
                        changed = True

                    if new_emcp_ram and (force or not kp.emcp_ram):
                        kp.emcp_ram = new_emcp_ram
                        update_fields.append("emcp_ram")
                        changed = True

                    if new_capacity and (force or not kp.capacity):
                        kp.capacity = new_capacity
                        update_fields.append("capacity")
                        changed = True

                    if notes_append:
                        existing_notes = kp.notes or ""
                        if notes_append not in existing_notes:
                            kp.notes = f"{existing_notes}\n{notes_append}".strip()
                            update_fields.append("notes")
                            changed = True

                    if changed:
                        kp.save(update_fields=update_fields)
                        self.stdout.write(
                            self.style.SUCCESS(f"  ✓ salvo: {', '.join(update_fields)}")
                        )

            except Exception as e:
                logger.warning("Erro ao salvar FBGA %s / PN %s: %s", fbga, pn, e)
                counts["errors"] += 1

            time.sleep(delay)

        # ── Relatório final ───────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f"\n\n✅  Concluído.\n"
            f"   part-name obtido da API Micron:         {counts['api_ok']}\n"
            f"   API sem resultado:                      {counts['api_no_result']}\n"
            f"   capacidade via MIC_MCP_CAP (decode map): {counts['decode_map']}\n"
            f"   capacidade standalone via part-name:     {counts['standalone_cap']}\n"
            f"   part-name em notes (MCP sem decode):     {counts['notes_only']}\n"
            f"   PNs ignorados (não reconhecido):         {counts['skipped']}\n"
            f"   Erros:                                   {counts['errors']}\n"
        ))

        if dry:
            self.stdout.write(self.style.WARNING("\nDry run — nenhuma alteração foi salva."))
            return

        # Invalida cache do engine
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            self.stdout.write("   🗑  Cache do engine invalidado.")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))

    def _fix_wrong_mtfc_capacities(self, dry: bool, verbose: bool):
        """
        Corrige capacidades MTFC salvas erradas pela execução anterior com bug Gb→GB.

        O bug: _DENSITY_RE_GB tinha re.I (case-insensitive), então "64G" do
        part-name "EMMC 64G VFBGA" era capturado como "64GB" quando na verdade
        64G = 64 Gbit = 8 GB. Chips como MTFC8G... ficaram com capacity="64GB"
        em vez de "8GB".

        Esta função recalcula direto do PN (MTFC{N}G = N GB) sem consultar a API.
        """
        from chips.models import KnownPart

        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        qs = KnownPart.objects.filter(
            brand__name="Micron",
            part_number__iregex=r'^MTFC',
        ).exclude(
            Q(capacity="") | Q(capacity__isnull=True)
        )

        total = qs.count()
        self.stdout.write(f"MTFC chips com capacity preenchido: {total}\n")

        if total == 0:
            self.stdout.write("Nada a corrigir.")
            return

        counts = {"fixed": 0, "already_ok": 0, "no_decode": 0, "errors": 0}

        for kp in qs.iterator():
            correct = _capacity_from_mtfc_pn(kp.part_number)
            if not correct:
                counts["no_decode"] += 1
                if verbose:
                    self.stdout.write(
                        f"  {kp.fbga_code or '-----'}  {kp.part_number[:48]:<48}  "
                        f"→ sem decode de PN"
                    )
                continue

            if kp.capacity == correct:
                counts["already_ok"] += 1
                continue

            if verbose:
                self.stdout.write(
                    f"  {kp.fbga_code or '-----'}  {kp.part_number[:48]:<48}  "
                    f"{kp.capacity!r} → {correct!r}"
                )

            if not dry:
                try:
                    with transaction.atomic():
                        kp.capacity = correct
                        kp.save(update_fields=["capacity"])
                    counts["fixed"] += 1
                except Exception as e:
                    logger.warning("Erro ao corrigir %s: %s", kp.part_number, e)
                    counts["errors"] += 1
            else:
                counts["fixed"] += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n✅  Correção MTFC concluída.\n"
            f"   Capacidades corrigidas: {counts['fixed']}\n"
            f"   Já corretas:            {counts['already_ok']}\n"
            f"   Sem decode de PN:       {counts['no_decode']}\n"
            f"   Erros:                  {counts['errors']}\n"
        ))

        if dry:
            self.stdout.write(self.style.WARNING("Dry run — nenhuma alteração foi salva."))
            return

        # Invalida cache do engine (capacity mudou)
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            self.stdout.write("   🗑  Cache do engine invalidado.")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))


# ── Helpers de família ────────────────────────────────────────────────────────

def _infer_interface(pn: str) -> str:
    """Infere interface NAND pela família do PN."""
    pn_upper = pn.upper()
    if pn_upper.startswith("MT30AZZZ"):
        return "UFS 3.1"
    if pn_upper.startswith("MT29VZZZ"):
        # Tenta pelo 12º char (pn[11]): F=UFS, G=eMMC
        pn_clean = re.sub(r'[^A-Z0-9]', '', pn_upper)
        if len(pn_clean) > 11:
            c = pn_clean[11]
            if c == 'F':
                return "UFS 2.2"
            elif c == 'G':
                return "eMMC 5.1"
        return "eMMC 5.1"  # padrão MT29VZZZ
    if pn_upper.startswith("MT29TZZZ"):
        return "eMMC 5.0"
    return "eMMC"


def _infer_lpddr_gen(pn: str) -> str:
    """Infere geração LPDDR pela família do PN."""
    pn_upper = pn.upper()
    if pn_upper.startswith("MT30AZZZ"):
        return "5"
    if pn_upper.startswith("MT29VZZZ"):
        return "4"
    if pn_upper.startswith("MT29TZZZ"):
        return "3"
    return "4"  # padrão conservador
