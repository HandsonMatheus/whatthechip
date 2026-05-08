"""
nexar_validate.py — Construção e validação de gabaritos via Nexar (Octopart) API
==================================================================================
WhatTheChip · Samsung IC Classification Project

Ferramenta principal para construir gabaritos de classificação consultando a
base de dados real da Nexar (Octopart) via API GraphQL.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PLANOS NEXAR E BUDGET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 PLANO AVALIAÇÃO (gratuito):
   Limite: 10 "matched parts" TOTAL (não por mês).
   Uso: apenas testes manuais no Playground da Nexar. NÃO usar este script.

 PLANO PAGO (Starter ~$99/mês):
   Limite: 2.000 "matched parts" / mês.
   "Matched parts" = partes retornadas pela API (não chamadas).
   Cada busca retorna até --limit partes de uma vez.

 Budget estimado com plano pago (--limit 20):
   eMCP  (6 famílias × 20):  120 partes = 6 chamadas
   uMCP  (4 famílias × 20):   80 partes = 4 chamadas
   eMMC  (1 família  × 20):   20 partes = 1 chamada
   UFS   (1 família  × 20):   20 partes = 1 chamada
   DRAM  (6 famílias × 20):  120 partes = 6 chamadas
   ─────────────────────────────────────────────────
   TOTAL Samsung completo:   360 partes = 18 chamadas  ✅ 1,8% do budget mensal

 NOTA SOBRE BUSCA POR PREFIXO:
   A query usa "Samsung KMQ" (não apenas "KMQ") para evitar que componentes de
   outros fabricantes com prefixo similar (ex: capacitores EKMQ da United
   Chemi-Con) consumam budget e contaminem os resultados.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 MODOS DE OPERAÇÃO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 MODO 1 — DISCOVER (padrão, mais eficiente para gabaritos)
   Busca por prefixo → descobre todos os códigos de capacidade existentes
   → gera tabela de gabarito diretamente importável no WTC.

   Exemplo:
     python nexar_validate.py --discover KMQ
     python nexar_validate.py --discover KMR KMQ KMS   (múltiplas)
     python nexar_validate.py --discover ALL_EMCP       (grupo predefinido)
     python nexar_validate.py --discover ALL_SAMSUNG    (gabarito completo)

 MODO 2 — VALIDATE (econômico para dúvidas pontuais)
   Busca um PN específico → compara com o que o motor WTC decodificaria.
   Use para resolver dúvidas sobre regras específicas, não para gabarito.

   Exemplo:
     python nexar_validate.py --validate KMRH60014A KMRY60014A

 FLAGS COMUNS:
   --output gabarito.csv   Salva resultado em CSV (importar no Excel/Sheets)
   --limit 20              Partes por busca (padrão: 20, máx recomendado)
   --dry-run               Simula sem chamar a API (mostra budget que usaria)
   --verbose               Exibe descrições brutas da Nexar

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 CONFIGURAÇÃO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Adicione ao .env na raiz do projeto:
   NEXAR_CLIENT_ID=seu_id_aqui
   NEXAR_CLIENT_SECRET=seu_secret_aqui

 Obter credenciais: https://portal.nexar.com → Applications → sua app
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# ── Configuração ──────────────────────────────────────────────────────────────

NEXAR_TOKEN_URL = "https://identity.nexar.com/connect/token"
NEXAR_GRAPH_URL = "https://api.nexar.com/graphql"

_ENV_PATH = Path(__file__).parent.parent / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

CLIENT_ID     = os.environ.get("NEXAR_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("NEXAR_CLIENT_SECRET", "")

MONTHLY_BUDGET = 2_000   # matched parts/mês (plano gratuito)


# ── Grupos de famílias predefinidos ──────────────────────────────────────────
# Cada grupo mapeia nome → lista de prefixos Samsung.
# Use --discover ALL_EMCP para rodar todas as famílias eMCP de uma vez.

FAMILY_GROUPS: dict[str, list[str]] = {
    # eMCP (eMMC + LPDDR, no mesmo package)
    "ALL_EMCP":   ["KMK", "KMF", "KMN", "KMQ", "KMR", "KMS"],
    # uMCP (UFS + LPDDR, no mesmo package)
    "ALL_UMCP":   ["KMD", "KMG", "KML", "KMV2", "KMV3"],
    # eMMC standalone
    "ALL_EMMC":   ["KLM"],
    # UFS standalone
    "ALL_UFS":    ["KLU"],
    # DRAM mobile
    "ALL_LPDDR":  ["K4P", "K3Q", "K4F", "K4U", "K3KL", "K3LK"],
    # DRAM desktop/server
    "ALL_DDR":    ["K4H", "K4T", "K4B", "K4A", "K4R"],
    # GDDR (gráficos)
    "ALL_GDDR":   ["K4J", "K4G", "K4Z"],
    # NAND Flash raw
    "ALL_NAND":   ["K9F", "K9G", "K9H", "K9K", "K9L", "K9W", "K9X", "K9Z"],
    # NOR Flash / Mask ROM
    "ALL_NOR":    ["K5", "K8"],
    # Samsung completo (use com cuidado — 20+ chamadas)
    "ALL_SAMSUNG": [
        "KMK", "KMF", "KMN", "KMQ", "KMR", "KMS",
        "KMD", "KMG", "KML", "KMV2", "KMV3",
        "KLM", "KLU",
        "K4P", "K3Q", "K4F", "K4U", "K3KL", "K3LK",
        "K4H", "K4T", "K4B", "K4A", "K4R",
        "K4J", "K4G", "K4Z",
        "K9F", "K9G",
        "K5",
    ],
}

# Metadados das famílias: tipo de chip, posições de decode, interface
FAMILY_META: dict[str, dict] = {
    # eMCP
    "KMK":  {"chip_type": "eMCP", "is_emcp": True, "ram_gen": "LPDDR2",    "nand_iface": "eMMC",     "cap_pos": (3,5), "gen_pos": 2},
    "KMF":  {"chip_type": "eMCP", "is_emcp": True, "ram_gen": "LPDDR3",    "nand_iface": "eMMC 5.1", "cap_pos": (3,5), "gen_pos": 2},
    "KMN":  {"chip_type": "eMCP", "is_emcp": True, "ram_gen": "LPDDR3",    "nand_iface": "eMMC 5.1", "cap_pos": (3,5), "gen_pos": 2},
    "KMQ":  {"chip_type": "eMCP", "is_emcp": True, "ram_gen": "LPDDR3",    "nand_iface": "eMMC 5.1", "cap_pos": (3,5), "gen_pos": 2},
    "KMR":  {"chip_type": "eMCP", "is_emcp": True, "ram_gen": "LPDDR4/4X", "nand_iface": "eMMC 5.1", "cap_pos": (3,5), "gen_pos": 2},
    "KMS":  {"chip_type": "eMCP", "is_emcp": True, "ram_gen": "LPDDR4X",   "nand_iface": "eMMC 5.1", "cap_pos": (3,5), "gen_pos": 2},
    # uMCP
    "KMD":  {"chip_type": "uMCP", "is_emcp": True, "ram_gen": "LPDDR4X",   "nand_iface": "UFS 2.1",  "cap_pos": (3,5), "gen_pos": 2},
    "KMG":  {"chip_type": "uMCP", "is_emcp": True, "ram_gen": "LPDDR4X",   "nand_iface": "UFS 3.1",  "cap_pos": (3,5), "gen_pos": 2},
    "KML":  {"chip_type": "uMCP", "is_emcp": True, "ram_gen": "LPDDR5",    "nand_iface": "UFS 3.1",  "cap_pos": (3,5), "gen_pos": 2},
    "KMV2": {"chip_type": "uMCP", "is_emcp": True, "ram_gen": "LPDDR5X",   "nand_iface": "UFS 4.0",  "cap_pos": (4,6), "gen_pos": None},
    "KMV3": {"chip_type": "uMCP", "is_emcp": True, "ram_gen": "LPDDR5X",   "nand_iface": "UFS 4.0",  "cap_pos": (4,6), "gen_pos": None},
    # eMMC
    "KLM":  {"chip_type": "eMMC", "is_emcp": False, "ram_gen": None,       "nand_iface": "eMMC 5.1", "cap_pos": (3,4), "gen_pos": None},
    # UFS
    "KLU":  {"chip_type": "UFS",  "is_emcp": False, "ram_gen": None,       "nand_iface": "UFS 3.1",  "cap_pos": (3,4), "gen_pos": None},
    # LPDDR mobile
    "K4P":  {"chip_type": "LPDDR2", "is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K3Q":  {"chip_type": "LPDDR3", "is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K4F":  {"chip_type": "LPDDR4", "is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K4U":  {"chip_type": "LPDDR4X","is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K3KL": {"chip_type": "LPDDR5", "is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K3LK": {"chip_type": "LPDDR5X","is_emcp": False, "nand_iface": None, "cap_pos": None},
    # DDR desktop
    "K4H":  {"chip_type": "DDR",  "is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K4T":  {"chip_type": "DDR2", "is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K4B":  {"chip_type": "DDR3", "is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K4A":  {"chip_type": "DDR4", "is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K4R":  {"chip_type": "DDR5", "is_emcp": False, "nand_iface": None, "cap_pos": None},
    # GDDR
    "K4J":  {"chip_type": "GDDR3","is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K4G":  {"chip_type": "GDDR5","is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K4Z":  {"chip_type": "GDDR6","is_emcp": False, "nand_iface": None, "cap_pos": None},
    # NAND
    "K9F":  {"chip_type": "NAND Flash SLC","is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K9G":  {"chip_type": "NAND Flash MLC","is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K9H":  {"chip_type": "NAND Flash MLC","is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K9K":  {"chip_type": "NAND Flash",    "is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K9L":  {"chip_type": "NAND Flash MLC","is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K9W":  {"chip_type": "NAND Flash SLC","is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K9X":  {"chip_type": "NAND Flash",    "is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K9Z":  {"chip_type": "NAND Flash",    "is_emcp": False, "nand_iface": None, "cap_pos": None},
    # NOR
    "K5":   {"chip_type": "NOR Flash", "is_emcp": False, "nand_iface": None, "cap_pos": None},
    "K8":   {"chip_type": "NOR Flash", "is_emcp": False, "nand_iface": None, "cap_pos": None},
}


# ── Gabarito atual do WTC (para comparação no modo discover) ─────────────────
# Capacidades mapeadas atualmente no SAM_EMCP_CAP.
# Usado para identificar entradas novas descobertas pela Nexar.

WTC_EMCP_CAP = {
    # ── Matriz direta (legado, 2012-2017) ──────────────────────────────────
    "11": ("4GB",   "512MB"),
    "72": ("8GB",   "1GB"),
    "82": ("16GB",  "1GB"),
    "31": ("16GB",  "2GB"),
    "21": ("32GB",  "2GB"),
    "41": ("32GB",  "4GB"),
    # ── Alfanumérico geração 1 (2017-2019) ─────────────────────────────────
    "5X": ("8GB",   "1GB"),
    "BT": ("16GB",  "2GB"),
    "V7": ("16GB",  "2GB"),    # alias BT
    "GD": ("32GB",  "3GB"),
    "W7": ("32GB",  "3GB"),    # alias GD
    "W8": ("32GB",  "4GB"),
    "X1": ("64GB",  "4GB"),
    "H9": ("64GB",  "4GB"),    # alias X1
    "M4": ("128GB", "4GB"),
    "J2": ("128GB", "6GB"),
    "P5": ("256GB", "8GB"),
    # ── Alfanumérico geração 2 (2020-2022, padrão [X]6) ────────────────────
    "D6": ("32GB",  "3GB"),    # Galaxy A21s (KMQD6·, KMRD6·)
    "E6": ("32GB",  "3GB"),    # alias D6 (lote alternativo)
    "V6": ("32GB",  "3GB"),    # alias D6 (revisão)
    "U6": ("64GB",  "3GB"),    # Galaxy A41 (KMQU6·)
    "X6": ("64GB",  "3GB"),    # alias U6
    "T6": ("64GB",  "4GB"),    # Galaxy A41 4GB (KMQT6·)
    "Y6": ("128GB", "4GB"),    # Galaxy A51 (KMQY6·)
    "H6": ("64GB",  "4GB"),    # KMRH60014A (A7 2017): H=64GB consistente com H9
    # Z6: evidência insuficiente — omitido (vai para Gemini)
    "L6": ("256GB", "8GB"),    # 256GB NAND + 8GB RAM  (KMFL6·, uMCP S21 FE)
    # uMCP high-cap (2021+) — derivados por padrão, verificar com PN real
    "K6": ("128GB", "8GB"),    # 128GB NAND + 8GB RAM  (KML·, S21 Exynos / A73 5G)
    # 256GB+12GB e 512GB+12GB: pendentes de confirmação por PN real
}

WTC_FLASH_CAP = {
    "4": "4GB", "8": "8GB", "A": "16GB", "B": "32GB",
    "C": "64GB", "D": "128GB", "E": "256GB", "F": "512GB", "G": "1TB",
}


# ── Autenticação ──────────────────────────────────────────────────────────────

_token_cache: dict = {}

def _get_token(client_id: str, client_secret: str) -> str:
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("expires_at", 0) > now + 60:
        return _token_cache["token"]

    data = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
    }).encode()
    req = urllib.request.Request(
        NEXAR_TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
        _token_cache["token"]      = body["access_token"]
        _token_cache["expires_at"] = now + body.get("expires_in", 3600)
        return _token_cache["token"]
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")
        raise RuntimeError(
            f"Falha na autenticação Nexar (HTTP {e.code}):\n{err}\n\n"
            "Verifique NEXAR_CLIENT_ID e NEXAR_CLIENT_SECRET no .env"
        ) from e


# ── Queries GraphQL ───────────────────────────────────────────────────────────

# Query principal: busca por MPN/prefixo, retorna múltiplos resultados
NEXAR_QUERY = """
query SearchMpn($q: String!, $limit: Int!) {
  supSearchMpn(q: $q, limit: $limit) {
    results {
      part {
        mpn
        manufacturer { name }
        shortDescription
        descriptions { text }
        specs { attribute { name shortname } displayValue }
        bestDatasheet { url }
      }
    }
  }
}
"""

def _graphql(query: str, variables: dict, token: str) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        NEXAR_GRAPH_URL, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read())


def _search(query_str: str, limit: int, token: str) -> list[dict]:
    """Busca na Nexar e retorna lista de objetos 'part'."""
    try:
        data = _graphql(NEXAR_QUERY, {"q": query_str, "limit": limit}, token)
        results = (data.get("data") or {}).get("supSearchMpn", {}).get("results") or []
        return [r["part"] for r in results if r.get("part")]
    except urllib.error.HTTPError as e:
        print(f"    ⚠️  HTTP {e.code} ao buscar '{query_str}'")
        return []
    except Exception as e:
        print(f"    ⚠️  Erro ao buscar '{query_str}': {e}")
        return []


# ── Parsing de specs e descrições ─────────────────────────────────────────────

_CAP_RE   = re.compile(r"(\d+(?:\.\d+)?)\s*(GB|MB|TB|Gb|Mb)", re.I)
_LPDDR_RE = re.compile(r"LP\s*DDR\s*(\d+\s*X?)", re.I)
_DDR_RE   = re.compile(r"\bDDR\s*(\d+)\b", re.I)
_EMMC_RE  = re.compile(r"eMMC\s*(\d+(?:\.\d+)?)", re.I)
_UFS_RE   = re.compile(r"UFS\s*(\d+(?:\.\d+)?)", re.I)
_GDDR_RE  = re.compile(r"GDDR\s*(\d+\s*X?)", re.I)


def _all_text(part: dict) -> str:
    """Concatena toda a informação textual do part."""
    chunks = [part.get("shortDescription", "")]
    for d in (part.get("descriptions") or []):
        chunks.append(d.get("text", ""))
    for s in (part.get("specs") or []):
        chunks.append(s.get("displayValue", ""))
    return " | ".join(t for t in chunks if t)


@dataclass
class ParsedPart:
    mpn:          str
    manufacturer: str
    description:  str
    datasheet:    str
    # eMCP/uMCP
    ram_type:     str | None = None
    ram_cap:      str | None = None
    nand_iface:   str | None = None
    nand_cap:     str | None = None
    # standalone (eMMC, UFS, DRAM, NAND, NOR)
    capacity:     str | None = None
    density_mbit: str | None = None
    # chave extraída do PN (para gabarito)
    cap_key:      str | None = None
    # fonte de confiança
    confidence:   str = "?"
    raw_text:     str = field(default="", repr=False)


def _parse_part(part: dict, prefix: str) -> ParsedPart:
    """Extrai specs relevantes de um part retornado pela Nexar."""
    mpn   = (part.get("mpn") or "").strip().upper()
    mfr   = (part.get("manufacturer") or {}).get("name", "")
    desc  = (part.get("shortDescription") or "").strip()
    ds    = (part.get("bestDatasheet") or {}).get("url", "")
    text  = _all_text(part)

    p = ParsedPart(mpn=mpn, manufacturer=mfr, description=desc,
                   datasheet=ds, raw_text=text)

    meta = FAMILY_META.get(prefix, {})
    is_emcp = meta.get("is_emcp", False)

    # ── Extrai chave de capacidade do PN ─────────────────────────────────────
    cap_pos = meta.get("cap_pos")
    pn_clean = mpn.split("-")[0]
    if cap_pos and len(pn_clean) >= cap_pos[1]:
        p.cap_key = pn_clean[cap_pos[0]:cap_pos[1]]

    # ── Specs estruturadas ────────────────────────────────────────────────────
    for spec in (part.get("specs") or []):
        attr = spec.get("attribute") or {}
        name = (attr.get("name") or attr.get("shortname") or "").lower()
        val  = (spec.get("displayValue") or "").strip()

        if not val:
            continue

        # RAM type
        if any(k in name for k in ("memory type", "ram type", "dram type", "technology")):
            lp = _LPDDR_RE.search(val)
            if lp and not p.ram_type:
                p.ram_type = f"LPDDR{lp.group(1).upper().strip()}"

        # RAM / NAND capacity via spec name
        if any(k in name for k in ("ram", "dram capacity", "dram size", "volatile memory")):
            m = _CAP_RE.search(val)
            if m and not p.ram_cap:
                p.ram_cap = _normalize_cap(m.group(1), m.group(2))

        if any(k in name for k in ("flash", "storage", "nand", "emmc", "ufs", "non-volatile")):
            m = _CAP_RE.search(val)
            if m and not p.nand_cap:
                p.nand_cap = _normalize_cap(m.group(1), m.group(2))
            em = _EMMC_RE.search(val)
            if em and not p.nand_iface:
                p.nand_iface = f"eMMC {em.group(1)}"
            ufs = _UFS_RE.search(val)
            if ufs and not p.nand_iface:
                p.nand_iface = f"UFS {ufs.group(1)}"

        # Standalone capacity
        if any(k in name for k in ("capacity", "memory size", "data retention")):
            m = _CAP_RE.search(val)
            if m and not p.capacity and not is_emcp:
                p.capacity = _normalize_cap(m.group(1), m.group(2))

    # ── Fallback: parsing de texto livre ─────────────────────────────────────
    if is_emcp:
        # Padrão comum: "LPDDR3 2GB + eMMC 5.1 16GB" ou "16GB eMMC + 2GB LPDDR3"
        _parse_emcp_from_text(text, p)
    else:
        _parse_standalone_from_text(text, p, meta.get("chip_type", ""))

    # ── Confiança ─────────────────────────────────────────────────────────────
    if is_emcp:
        if p.ram_cap and p.nand_cap and p.ram_type:
            p.confidence = "HIGH"
        elif p.ram_cap and p.nand_cap:
            p.confidence = "MED"
        elif p.ram_cap or p.nand_cap:
            p.confidence = "LOW"
        else:
            p.confidence = "NONE"
    else:
        if p.capacity:
            p.confidence = "HIGH" if len(p.capacity) >= 3 else "MED"
        elif p.density_mbit:
            p.confidence = "MED"
        else:
            p.confidence = "NONE"

    return p


def _normalize_cap(val: str, unit: str) -> str:
    """Normaliza capacidade para string limpa. Ex: '1.5' + 'GB' → '1.5GB'"""
    v = float(val)
    u = unit.upper()
    if u in ("GB", "TB"):
        # Arredonda se inteiro
        return f"{int(v)}{u}" if v == int(v) else f"{v}{u}"
    if u in ("MB",):
        return f"{int(v)}MB" if v == int(v) else f"{v}MB"
    if u in ("GB".lower(), "GB"):
        return f"{int(v)}Gb"  # densidade
    return f"{val}{u}"


def _parse_emcp_from_text(text: str, p: ParsedPart):
    """Extrai RAM type, RAM cap e NAND cap de texto livre para eMCP/uMCP."""
    text_upper = text.upper()

    # RAM type
    if not p.ram_type:
        lp = _LPDDR_RE.search(text)
        if lp:
            p.ram_type = f"LPDDR{lp.group(1).upper().strip()}"

    # Padrões comuns de descrição eMCP:
    # "LPDDR3 2GB NAND 16GB eMMC 5.1"
    # "2GB LPDDR4X + 64GB UFS 3.1"
    # "16GB+2GB eMCP"

    # Extrai todas as capacidades encontradas no texto
    caps = []
    for m in _CAP_RE.finditer(text):
        caps.append((_normalize_cap(m.group(1), m.group(2)), m.start()))

    if not caps:
        return

    # Tenta identificar RAM vs NAND pela posição no texto e contexto
    ram_caps  = []
    nand_caps = []

    for cap, pos in caps:
        before = text_upper[max(0, pos-30):pos].upper()
        after  = text_upper[pos:pos+30].upper()
        context = before + after

        is_ram  = any(k in context for k in ("LPDDR", "RAM", "DRAM", "VOLATILE"))
        is_nand = any(k in context for k in ("EMMC", "UFS", "NAND", "FLASH", "STORAGE", "NON-VOLATILE"))

        if is_ram and not p.ram_cap:
            ram_caps.append(cap)
        elif is_nand and not p.nand_cap:
            nand_caps.append(cap)

    # Aplica o que encontrou com contexto
    if ram_caps and not p.ram_cap:
        p.ram_cap = ram_caps[0]
    if nand_caps and not p.nand_cap:
        p.nand_cap = nand_caps[0]

    # Fallback: se dois valores sem contexto claro, maior = NAND, menor = RAM
    if not p.ram_cap and not p.nand_cap and len(caps) >= 2:
        def cap_to_bytes(c):
            m = re.match(r"([\d.]+)(GB|MB|TB)", c, re.I)
            if not m: return 0
            v, u = float(m.group(1)), m.group(2).upper()
            return v * (1024**3 if u == "GB" else 1024**2 if u == "MB" else 1024**4)
        sorted_caps = sorted(caps, key=lambda x: cap_to_bytes(x[0]))
        p.ram_cap  = sorted_caps[0][0]   # menor = RAM
        p.nand_cap = sorted_caps[-1][0]  # maior = NAND

    # Interface NAND
    if not p.nand_iface:
        em = _EMMC_RE.search(text)
        if em:
            p.nand_iface = f"eMMC {em.group(1)}"
        else:
            ufs = _UFS_RE.search(text)
            if ufs:
                p.nand_iface = f"UFS {ufs.group(1)}"


def _parse_standalone_from_text(text: str, p: ParsedPart, chip_type: str):
    """Extrai capacidade de chips standalone (eMMC, UFS, DRAM, NAND, NOR)."""
    if not p.capacity:
        m = _CAP_RE.search(text)
        if m:
            p.capacity = _normalize_cap(m.group(1), m.group(2))

    # Densidade em Gbit (para DRAM)
    if not p.density_mbit and "DDR" in chip_type.upper():
        gbit = re.search(r"(\d+)\s*Gb(?:it)?", text, re.I)
        if gbit:
            p.density_mbit = f"{gbit.group(1)}Gb"


# ── MODO DISCOVER: construção de gabarito ─────────────────────────────────────

@dataclass
class GabaritoEntry:
    prefix:    str
    chip_type: str
    ram_gen:   str | None
    nand_iface: str | None
    cap_key:   str   # código de 1 ou 2 chars do PN
    nand_cap:  str | None
    ram_cap:   str | None
    capacity:  str | None   # para chips não-eMCP
    example_pns: list[str] = field(default_factory=list)
    confidence:  str = "?"
    nexar_desc:  str = ""
    in_wtc:      bool = False
    wtc_nand:    str | None = None
    wtc_ram:     str | None = None
    conflict:    bool = False


def _discover_family(prefix: str, limit: int, token: str, verbose: bool) -> list[GabaritoEntry]:
    """
    Busca pelo prefixo na Nexar e constrói entradas do gabarito.
    Retorna uma entrada por código de capacidade único encontrado.
    """
    meta     = FAMILY_META.get(prefix, {})
    is_emcp  = meta.get("is_emcp", False)
    cap_pos  = meta.get("cap_pos")
    chip_type = meta.get("chip_type", prefix)

    # Query inclui "Samsung" para evitar que o Nexar retorne componentes de outros
    # fabricantes cujo MPN contenha o mesmo prefixo curto (ex: capacitores EKMQ
    # da United Chemi-Con aparecem ao buscar "KMQ" sem fabricante).
    query_str = f"Samsung {prefix}"
    print(f"  🔍  Buscando '{query_str}' ({chip_type}) → limit={limit}...")
    parts = _search(query_str, limit, token)

    if not parts:
        print(f"      ⚠️  Nenhum resultado para '{query_str}'")
        return []

    # Filtra: só partes cujo MPN começa com o prefixo E fabricante é Samsung.
    # Dupla garantia: a query "Samsung X" já prioriza, mas o filtro elimina
    # qualquer residual de outro fabricante que passe.
    parts = [
        p for p in parts
        if (p.get("mpn") or "").upper().startswith(prefix)
        and "samsung" in (p.get("manufacturer") or {}).get("name", "").lower()
    ]
    print(f"      → {len(parts)} partes Samsung com prefixo {prefix}")

    # Parseia cada parte
    parsed_list = [_parse_part(p, prefix) for p in parts]

    if verbose:
        for pp in parsed_list:
            print(f"         [{pp.mpn}] ram={pp.ram_type} {pp.ram_cap} | "
                  f"nand={pp.nand_iface} {pp.nand_cap} | "
                  f"cap={pp.capacity} | key={pp.cap_key} | conf={pp.confidence}")
            if pp.description:
                print(f"           desc: {pp.description[:100]}")

    # Agrupa por cap_key para montar gabarito
    grouped: dict[str, list[ParsedPart]] = {}
    no_key: list[ParsedPart] = []

    for pp in parsed_list:
        if pp.cap_key:
            grouped.setdefault(pp.cap_key, []).append(pp)
        else:
            no_key.append(pp)

    entries: list[GabaritoEntry] = []

    # Entradas com cap_key (mapeáveis no gabarito)
    for key, pps in sorted(grouped.items()):
        # Escolhe o parsed com maior confiança
        best = max(pps, key=lambda x: {"HIGH": 3, "MED": 2, "LOW": 1, "NONE": 0}.get(x.confidence, 0))

        # Capacidade NAND e RAM: consenso entre os parses do mesmo key
        nand_caps = [p.nand_cap for p in pps if p.nand_cap]
        ram_caps  = [p.ram_cap  for p in pps if p.ram_cap]
        caps      = [p.capacity for p in pps if p.capacity]

        nand_cap = _majority(nand_caps)
        ram_cap  = _majority(ram_caps)
        capacity = _majority(caps)

        nand_iface = best.nand_iface or meta.get("nand_iface")
        ram_gen    = best.ram_type   or meta.get("ram_gen")

        # Verifica conflito com gabarito WTC atual
        wtc_entry = WTC_EMCP_CAP.get(key) if is_emcp else None
        wtc_flash  = WTC_FLASH_CAP.get(key) if not is_emcp and key in WTC_FLASH_CAP else None
        wtc_nand = wtc_ram = None
        conflict = False
        in_wtc   = False

        if wtc_entry:
            in_wtc   = True
            wtc_nand = wtc_entry[0]
            wtc_ram  = wtc_entry[1]
            conflict = (
                (nand_cap and wtc_nand and nand_cap != wtc_nand) or
                (ram_cap  and wtc_ram  and ram_cap  != wtc_ram)
            )
        elif wtc_flash:
            in_wtc    = True
            wtc_nand  = wtc_flash
            conflict  = (capacity and wtc_flash and capacity != wtc_flash)

        entry = GabaritoEntry(
            prefix=prefix, chip_type=chip_type,
            ram_gen=ram_gen, nand_iface=nand_iface,
            cap_key=key,
            nand_cap=nand_cap, ram_cap=ram_cap, capacity=capacity,
            example_pns=[p.mpn for p in pps[:3]],
            confidence=best.confidence,
            nexar_desc=best.description[:80],
            in_wtc=in_wtc, wtc_nand=wtc_nand, wtc_ram=wtc_ram,
            conflict=conflict,
        )
        entries.append(entry)

    # Entradas sem cap_key (sem posição de decode conhecida)
    if no_key:
        for pp in no_key:
            if pp.confidence in ("HIGH", "MED") and (pp.nand_cap or pp.capacity):
                entries.append(GabaritoEntry(
                    prefix=prefix, chip_type=chip_type,
                    ram_gen=pp.ram_type or meta.get("ram_gen"),
                    nand_iface=pp.nand_iface or meta.get("nand_iface"),
                    cap_key="—",
                    nand_cap=pp.nand_cap, ram_cap=pp.ram_cap, capacity=pp.capacity,
                    example_pns=[pp.mpn],
                    confidence=pp.confidence,
                    nexar_desc=pp.description[:80],
                ))

    return entries


def _majority(lst: list[str]) -> str | None:
    """Retorna o valor mais frequente na lista. None se vazia."""
    if not lst:
        return None
    counts: dict[str, int] = {}
    for v in lst:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=counts.__getitem__)


# ── MODO VALIDATE: validação de PNs específicos ───────────────────────────────

@dataclass
class ValidationRow:
    pn:         str
    prefix:     str
    chip_type:  str
    wtc_decode: str
    nex_result: str
    status:     str
    datasheet:  str = ""


def _wtc_local_decode(pn: str) -> tuple[str, str, str]:
    """
    Decodificação local simplificada (sem banco Django).
    Retorna (prefix, chip_type, decode_str).
    """
    pn_up = pn.upper().split("-")[0].strip()

    EMCP_GEN = {
        "K": "LPDDR2", "F": "LPDDR3", "N": "LPDDR3", "Q": "LPDDR3",
        "R": "LPDDR4/4X", "S": "LPDDR4X",
        "D": "LPDDR4X", "E": "LPDDR4/4X", "G": "LPDDR4X", "L": "LPDDR5", "V": "LPDDR5/5X",
    }
    for prefix in sorted(FAMILY_META.keys(), key=len, reverse=True):
        if pn_up.startswith(prefix):
            meta      = FAMILY_META[prefix]
            chip_type = meta["chip_type"]
            cap_pos   = meta.get("cap_pos")
            gen_pos   = meta.get("gen_pos")
            is_emcp   = meta.get("is_emcp", False)

            ram_type = None
            cap_key  = None
            nand_cap = ram_cap = cap_str = None

            if gen_pos is not None and len(pn_up) > gen_pos:
                ram_type = EMCP_GEN.get(pn_up[gen_pos], meta.get("ram_gen"))
            else:
                ram_type = meta.get("ram_gen")

            if cap_pos and len(pn_up) >= cap_pos[1]:
                cap_key = pn_up[cap_pos[0]:cap_pos[1]]

            if is_emcp and cap_key:
                entry = WTC_EMCP_CAP.get(cap_key)
                if entry:
                    nand_cap, ram_cap = entry
                    decode_str = (f"{chip_type} | {ram_type} {ram_cap} + "
                                  f"{meta.get('nand_iface','eMMC')} {nand_cap}")
                else:
                    decode_str = f"{chip_type} | {ram_type} + {meta.get('nand_iface','eMMC')} | chave '{cap_key}' não mapeada"
            elif not is_emcp and cap_key:
                cap_val = WTC_FLASH_CAP.get(cap_key, f"'{cap_key}'?")
                decode_str = f"{chip_type} {cap_val}"
            else:
                decode_str = f"{chip_type} | decode não disponível localmente"

            return prefix, chip_type, decode_str

    return "?", "Desconhecido", "Prefixo não reconhecido"


def _validate_pns(pns: list[str], limit: int, token: str, verbose: bool) -> list[ValidationRow]:
    """Valida PNs específicos contra a Nexar."""
    rows = []
    for pn in pns:
        pn_clean = pn.upper().split("-")[0]
        prefix, chip_type, wtc_decode = _wtc_local_decode(pn_clean)

        parts  = _search(pn_clean, min(limit, 3), token)   # max 3 por PN específico
        if not parts:
            rows.append(ValidationRow(
                pn=pn, prefix=prefix, chip_type=chip_type,
                wtc_decode=wtc_decode, nex_result="—", status="🔍 SEM_DADOS",
            ))
            continue

        # Pega o resultado mais próximo
        best_part = parts[0]
        for p in parts:
            if (p.get("mpn") or "").upper().startswith(pn_clean[:5]):
                best_part = p
                break

        parsed  = _parse_part(best_part, prefix)
        meta    = FAMILY_META.get(prefix, {})
        is_emcp = meta.get("is_emcp", False)

        if is_emcp:
            nex_str = (f"{parsed.ram_type or '?'} {parsed.ram_cap or '?'} + "
                       f"{parsed.nand_iface or '?'} {parsed.nand_cap or '?'}")
        else:
            nex_str = parsed.capacity or parsed.description[:60] or "—"

        # Status
        if parsed.confidence == "NONE":
            status = "❓ PARCIAL"
        else:
            status = _compare_decode(wtc_decode, nex_str, is_emcp)

        if verbose and parsed.description:
            print(f"    [{pn}] Nexar desc: {parsed.description}")
            print(f"    [{pn}] Nexar raw:  {parsed.raw_text[:120]}")

        rows.append(ValidationRow(
            pn=pn, prefix=prefix, chip_type=chip_type,
            wtc_decode=wtc_decode, nex_result=nex_str, status=status,
            datasheet=parsed.datasheet,
        ))

    return rows


def _compare_decode(wtc: str, nex: str, is_emcp: bool) -> str:
    """Compara decode WTC vs Nexar e retorna status."""
    if not nex or nex == "—" or "?" in nex:
        return "❓ PARCIAL"
    # Extrai capacidades de ambos e compara
    wtc_caps = set(re.findall(r"\d+(?:\.\d+)?(?:GB|MB)", wtc, re.I))
    nex_caps = set(re.findall(r"\d+(?:\.\d+)?(?:GB|MB)", nex, re.I))
    if not wtc_caps or not nex_caps:
        return "❓ PARCIAL"
    conflicts = wtc_caps.symmetric_difference(nex_caps)
    return "✅ MATCH" if not conflicts else f"⚠️  DIVERGE (WTC: {wtc_caps} ≠ NEX: {nex_caps})"


# ── Saída — terminal ──────────────────────────────────────────────────────────

def _print_gabarito(entries: list[GabaritoEntry], prefix: str):
    meta      = FAMILY_META.get(prefix, {})
    chip_type = meta.get("chip_type", prefix)
    ram_gen   = meta.get("ram_gen", "—")
    nand_if   = meta.get("nand_iface", "—")
    cap_pos   = meta.get("cap_pos")

    pos_str   = f"pos {cap_pos[0]}-{cap_pos[1]-1}" if cap_pos else "variável"

    print(f"\n  ┌─── GABARITO {prefix} ({chip_type}) ───────────────────────────────────")
    print(f"  │  Geração RAM: {ram_gen}  │  Interface NAND: {nand_if}  │  Chave: {pos_str} do PN")
    print(f"  ├─────────────┬─────────────┬─────────────┬──────────┬──────────────")
    print(f"  │  CHAVE (PN) │  NAND Cap   │  RAM Cap    │  Conf.   │  Status WTC")
    print(f"  ├─────────────┼─────────────┼─────────────┼──────────┼──────────────")

    for e in sorted(entries, key=lambda x: x.cap_key):
        key_str  = e.cap_key.ljust(11)
        nand_str = (e.nand_cap or e.capacity or "—").ljust(11)
        ram_str  = (e.ram_cap or "—").ljust(11)
        conf_str = e.confidence.ljust(8)

        if e.conflict:
            wtc_str = f"⚠️  CONFLITO (WTC: nand={e.wtc_nand} ram={e.wtc_ram})"
        elif e.in_wtc:
            wtc_str = "✅ já no gabarito"
        else:
            wtc_str = "🆕 NOVO — adicionar ao SAM_EMCP_CAP"

        print(f"  │  {key_str}│  {nand_str}│  {ram_str}│  {conf_str}│  {wtc_str}")
        if e.example_pns:
            print(f"  │             │  Exemplos: {', '.join(e.example_pns[:2])}")

    print(f"  └─────────────┴─────────────┴─────────────┴──────────┴──────────────")


def _print_validation(rows: list[ValidationRow]):
    print(f"\n  {'PN':<22} {'WTC DECODE':<40} {'NEXAR':<35} STATUS")
    print("  " + "─" * 115)
    for r in rows:
        print(f"  {r.pn:<22} {r.wtc_decode:<40} {r.nex_result:<35} {r.status}")


# ── Exportação CSV ─────────────────────────────────────────────────────────────

def _export_discover_csv(all_entries: list[GabaritoEntry], path: str):
    fields = ["prefix", "chip_type", "ram_gen", "nand_iface", "cap_key",
              "nand_cap", "ram_cap", "capacity", "confidence",
              "in_wtc", "wtc_nand", "wtc_ram", "conflict",
              "example_pns", "nexar_desc"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for e in all_entries:
            w.writerow({
                "prefix":      e.prefix,
                "chip_type":   e.chip_type,
                "ram_gen":     e.ram_gen or "",
                "nand_iface":  e.nand_iface or "",
                "cap_key":     e.cap_key,
                "nand_cap":    e.nand_cap or "",
                "ram_cap":     e.ram_cap or "",
                "capacity":    e.capacity or "",
                "confidence":  e.confidence,
                "in_wtc":      "sim" if e.in_wtc else "nao",
                "wtc_nand":    e.wtc_nand or "",
                "wtc_ram":     e.wtc_ram or "",
                "conflict":    "SIM" if e.conflict else "",
                "example_pns": "|".join(e.example_pns),
                "nexar_desc":  e.nexar_desc,
            })
    print(f"\n  📄 CSV salvo: {path}")


def _export_validate_csv(rows: list[ValidationRow], path: str):
    fields = ["pn", "prefix", "chip_type", "wtc_decode", "nex_result", "status", "datasheet"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(vars(r))
    print(f"\n  📄 CSV salvo: {path}")


# ── Budget tracker ─────────────────────────────────────────────────────────────

class BudgetTracker:
    def __init__(self, limit_per_call: int):
        self.limit = limit_per_call
        self.calls = 0
        self.parts = 0

    def record(self, n_parts: int):
        self.calls += 1
        self.parts += n_parts

    def print_summary(self):
        pct = self.parts / MONTHLY_BUDGET * 100
        remaining = MONTHLY_BUDGET - self.parts
        print(f"\n  💳  Budget usado: {self.parts} partes matched de {MONTHLY_BUDGET}/mês "
              f"({pct:.1f}%) em {self.calls} chamadas")
        print(f"      Restante estimado: {remaining} partes "
              f"({remaining // self.limit} chamadas a {self.limit}/chamada)")


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Nexar API — construção de gabaritos e validação de regras WhatTheChip.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--discover", "-d", nargs="+", metavar="PREFIXO_OU_GRUPO",
        help=(
            "MODO GABARITO (recomendado). Busca pelo prefixo ou grupo predefinido. "
            f"Grupos: {', '.join(FAMILY_GROUPS.keys())}. "
            "Ex: --discover KMQ  --discover ALL_EMCP  --discover KMQ KMR KMS"
        ),
    )
    mode.add_argument(
        "--validate", "-v", nargs="+", metavar="PN",
        help=(
            "MODO VALIDAÇÃO. Valida PNs específicos contra Nexar. "
            "Usa 1-3 partes por PN. "
            "Ex: --validate KMRH60014A KMRY60014A"
        ),
    )
    mode.add_argument(
        "--budget", action="store_true",
        help="Simula o budget que seria usado (sem chamadas reais).",
    )

    parser.add_argument("--client-id",     default=CLIENT_ID)
    parser.add_argument("--client-secret", default=CLIENT_SECRET)
    parser.add_argument(
        "--limit", "-l", type=int, default=20,
        help="Partes retornadas por chamada (padrão: 20, máx recomendado para economy).",
    )
    parser.add_argument("--output", "-o", help="Arquivo CSV de saída.")
    parser.add_argument("--verbose", action="store_true", help="Exibe texto bruto da Nexar.")
    parser.add_argument("--delay",  type=float, default=0.3, help="Delay entre chamadas (s).")

    args = parser.parse_args()

    # ── Budget simulation ─────────────────────────────────────────────────────
    if args.budget:
        print("\n📊  SIMULAÇÃO DE BUDGET (sem chamadas reais)\n")
        for group_name, prefixes in FAMILY_GROUPS.items():
            calls = len(prefixes)
            parts = calls * args.limit
            pct   = parts / MONTHLY_BUDGET * 100
            print(f"  {group_name:<20} {calls:>2} chamadas × {args.limit} = "
                  f"{parts:>4} partes ({pct:.1f}% do budget)")
        total_samsung = len(FAMILY_GROUPS["ALL_SAMSUNG"])
        total_parts   = total_samsung * args.limit
        print(f"\n  ALL_SAMSUNG completo: {total_samsung} chamadas × {args.limit} = "
              f"{total_parts} partes ({total_parts/MONTHLY_BUDGET*100:.1f}% do budget)")
        print(f"\n  Budget mensal total: {MONTHLY_BUDGET} partes")
        print(f"  Restante após Samsung: {MONTHLY_BUDGET - total_parts} partes\n")
        return

    # ── Autenticação ──────────────────────────────────────────────────────────
    cid = args.client_id
    cs  = args.client_secret

    if not cid or not cs:
        print("\n❌  Credenciais Nexar não encontradas.")
        print("   Adicione ao .env (na raiz do projeto):")
        print("     NEXAR_CLIENT_ID=seu_client_id")
        print("     NEXAR_CLIENT_SECRET=seu_client_secret")
        print("   Obtenha em: https://portal.nexar.com → Applications\n")
        sys.exit(1)

    print(f"\n🔐  Autenticando na Nexar...")
    try:
        token = _get_token(cid, cs)
        print("✅  Autenticado.")
    except RuntimeError as e:
        print(f"\n❌  {e}")
        sys.exit(1)

    budget = BudgetTracker(args.limit)
    ts     = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── MODO DISCOVER ─────────────────────────────────────────────────────────
    if args.discover:
        # Expande grupos predefinidos
        prefixes: list[str] = []
        for token_arg in args.discover:
            tok = token_arg.upper()
            if tok in FAMILY_GROUPS:
                prefixes.extend(FAMILY_GROUPS[tok])
                print(f"\n  Grupo '{tok}': {', '.join(FAMILY_GROUPS[tok])}")
            elif tok in FAMILY_META:
                prefixes.append(tok)
            else:
                print(f"  ⚠️  '{token_arg}' não reconhecido. "
                      f"Prefixos: {', '.join(FAMILY_META.keys())} | "
                      f"Grupos: {', '.join(FAMILY_GROUPS.keys())}")

        if not prefixes:
            print("\n❌  Nenhum prefixo válido informado.")
            sys.exit(1)

        # Estimativa de budget
        est_parts = len(prefixes) * args.limit
        est_pct   = est_parts / MONTHLY_BUDGET * 100
        print(f"\n  📋  {len(prefixes)} prefixo(s) → estimativa: "
              f"{est_parts} partes matched ({est_pct:.1f}% do budget)\n")

        all_entries: list[GabaritoEntry] = []

        for prefix in prefixes:
            entries = _discover_family(prefix, args.limit, token, args.verbose)
            budget.record(len(entries))
            all_entries.extend(entries)
            _print_gabarito(entries, prefix)
            if args.delay > 0:
                time.sleep(args.delay)

        # Resumo
        new_entries = [e for e in all_entries if not e.in_wtc and e.cap_key != "—"]
        conflicts   = [e for e in all_entries if e.conflict]
        high_conf   = [e for e in all_entries if e.confidence == "HIGH"]

        print(f"\n  ━━━  RESUMO GABARITO ({ts}) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"  Total de entradas encontradas: {len(all_entries)}")
        print(f"  Alta confiança (HIGH):          {len(high_conf)}")
        print(f"  🆕 Novas (não estão no WTC):    {len(new_entries)}")
        print(f"  ⚠️  Conflitos com WTC atual:     {len(conflicts)}")

        if new_entries:
            print(f"\n  ── Novas entradas para adicionar ao SAM_EMCP_CAP ──────────")
            for e in new_entries:
                ram_str  = f', "{e.cap_key}", "{e.nand_cap}", "{e.ram_cap}"' if e.ram_cap else ""
                cap_str  = f', "{e.cap_key}", "{e.capacity}", ""' if e.capacity and not e.ram_cap else ""
                code_str = ram_str or cap_str
                print(f"    ({code_str.strip()})  # {e.chip_type} | ex: {e.example_pns[0] if e.example_pns else '—'}")

        if conflicts:
            print(f"\n  ── Conflitos para revisar ─────────────────────────────────")
            for e in conflicts:
                print(f"    [{e.prefix}] chave={e.cap_key}: "
                      f"WTC diz nand={e.wtc_nand}/ram={e.wtc_ram} | "
                      f"Nexar diz nand={e.nand_cap}/ram={e.ram_cap} | "
                      f"ex: {e.example_pns[0] if e.example_pns else '—'}")

        if args.output:
            _export_discover_csv(all_entries, args.output)

    # ── MODO VALIDATE ─────────────────────────────────────────────────────────
    elif args.validate:
        pns = [p.upper() for p in args.validate]
        print(f"\n  🔍  Validando {len(pns)} PN(s)...\n")
        rows = _validate_pns(pns, args.limit, token, args.verbose)
        budget.record(len(pns) * 3)
        _print_validation(rows)
        if args.output:
            _export_validate_csv(rows, args.output)

    budget.print_summary()
    print()


if __name__ == "__main__":
    main()
