#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
micron_catalog_snapshot.py  —  Fase 0 / sonda 2 (PLANO_MICRON_IDENTITY_ONLY_FASE2.md)
=====================================================================================
Baixa os catálogos oficiais da Micron pelo endpoint AEM `getpartcatalog` (o XHR que
alimenta a tabela do part-catalog) e salva um SNAPSHOT local datado, JSON puro.

Por que existe: o endpoint responde **headless, sem login**, com `Technology` (tipo +
célula NAND + geração RAM), `Protocol` (interface) e `Component Density` (TOTAL) — a
fonte oficial machine-readable de TIPO e TOTAL. Ver `micron_fase2/catalog_index.md`.

READ-ONLY total: só faz GET numa API pública e grava arquivos. **Não toca no banco.**
Local-only (usa curl_cffi, que não está no requirements-render). Rode você (o dono):

    python scripts/micron_catalog_snapshot.py                 # todos os catálogos
    python scripts/micron_catalog_snapshot.py --only lpddr5x  # 1 catálogo (substring do slug)
    python scripts/micron_catalog_snapshot.py --out micron_fase2/snapshots --delay 1.5
    python scripts/micron_catalog_snapshot.py --url <PATH>    # adiciona um PATH avulso

Saída: `<out>/<YYYY-MM-DD>/<slug>.json` + um `_index.json` com o resumo (contagem por
catálogo, valores distintos de Technology, status). A contagem por catálogo é o teste
de PAGINAÇÃO: compare `count` com o "Show all" da UI num catálogo grande (DDR) — se
bater, o JSON traz tudo; se truncar, achamos o limite.
"""
import argparse
import datetime as _dt
import json
import os
import sys
import time

# Template CONFIRMADO (2026-07-15). <PATH> = caminho do produto; as 2 últimas pastas repetem.
URL_TMPL = (
    "https://www.micron.com/content/micron/us/en/products/{path}/part-catalog/"
    "_jcr_content.products.json/getpartcatalog/{tail}/-/en_US.json"
)

# Catálogos por PATH (RAIZ AEM confirmada 2026-07-16 via busca + endpoint). O snapshotter
# usa as 2 ÚLTIMAS pastas do PATH como <tail>. ✓ = validado (endpoint ou página oficial);
# ~ = derivado por analogia (404 é inócuo — só ajustar o slug). Raízes:
#   MCP → multichip-packages/ · discreta → memory/{lpddr,dram}-components/ ·
#   eMMC/UFS → storage/managed-nand/ · obsoletos → obsolete/obsolete-<slug>.
CATALOGS = [
    # ── Gerenciados MCP (Segmento A) — CORRENTES ──────────────────────────
    "multichip-packages/ufs-based-mcp",            # ✓ uMCP (14)
    "multichip-packages/emmc-based-mcp",           # ✓ eMCP + NAND-MCP (15)
    "multichip-packages/nand-based-mcp",           # ✓ NAND-MCP (8)
    # ── eMMC/UFS standalone (Segmento A) — raiz storage/ ──────────────────
    "storage/managed-nand/emmc",                   # ✓ eMMC (40)
    "storage/managed-nand/universal-flash-storage",# ~ UFS standalone (slug corrigido 07-16)
    # ── Discreta (Segmento B) — raiz memory/…-components/ ─────────────────
    # LPDDR3 corrente NÃO existe (404) → está no obsolete-lpddr. Não incluir.
    "memory/lpddr-components/lpddr4",              # ✓ 133 (MIX: MT53B/D=LPDDR4, MT53E=LPDDR4X, MT40A=DDR4)
    "memory/lpddr-components/lpddr5",              # ~
    "memory/lpddr-components/lpddr5x",             # ~ (base do fix LPDDR4X→LPDDR5X)
    "memory/dram-components/ddr4-sdram",           # ✓ página oficial
    "memory/dram-components/ddr5-sdram",           # ~
    # ── OBSOLETOS — raiz obsolete/obsolete-<slug> ─────────────────────────
    "obsolete/obsolete-lpddr",
    "obsolete/obsolete-lpddr4",
    "obsolete/obsolete-lpddr5",
    "obsolete/obsolete-lpddr5x",
    "obsolete/obsolete-ddr4-sdram",                # ✓ página oficial
    "obsolete/obsolete-ddr3-sdram",
    "obsolete/obsolete-ddr2-sdram",
    "obsolete/obsolete-sdram",
    "obsolete/obsolete-emmc",                      # ✓ página oficial (MTFC+N2M)
    "obsolete/obsolete-universal-flash-storage",   # ✓ uMCP obsoleto (era 'obsolete-umcp-catalog', HTTP400)
    "obsolete/obsolete-nand-mcp-catalog",          # ✓ 88 (MT29C legado + NAND/NOR MCP)
    "obsolete/obsolete-gddr6",
]

# Ainda fora da lista (raiz obsolete/ provável; adicione via --url se precisar — quase tudo
# é dead-by-gen, só tipo): obsolete-{mlc,tlc,slc,3d}-nand, obsolete-{parallel,serial}-nor,
# obsolete-xccela-flash, obsolete-rldram-memory, obsolete-universal-flash-storage.

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.micron.com/products",
}


def _make_session():
    """curl_cffi (TLS Chrome) p/ evitar bloqueio; fallback requests. Igual ao pipeline FBGA."""
    try:
        from curl_cffi import requests as cffi
        return cffi.Session(impersonate="chrome110")
    except ImportError:
        import requests
        return requests.Session()


def _url_for(path: str) -> str:
    tail = "/".join(path.strip("/").split("/")[-2:])
    return URL_TMPL.format(path=path.strip("/"), tail=tail)


def _slug(path: str) -> str:
    return path.strip("/").split("/")[-1]


def _distinct_technology(details: list) -> list:
    seen = []
    for d in details:
        for a in d.get("attr", []):
            if a.get("name") == "Technology" and a.get("value") not in seen:
                seen.append(a.get("value"))
    return seen


def main() -> int:
    ap = argparse.ArgumentParser(description="Snapshot dos catálogos Micron (getpartcatalog).")
    ap.add_argument("--out", default="micron_fase2/snapshots", help="Diretório-base de saída.")
    ap.add_argument("--only", default="", help="Só catálogos cujo slug contém esta substring.")
    ap.add_argument("--url", action="append", default=[], metavar="PATH",
                    help="PATH avulso extra (repetível), ex.: managed-nand/emmc.")
    ap.add_argument("--delay", type=float, default=1.2, help="Pausa entre requests (s).")
    args = ap.parse_args()

    date = _dt.date.today().isoformat()
    outdir = os.path.join(args.out, date)
    os.makedirs(outdir, exist_ok=True)

    catalogs = [c for c in (CATALOGS + args.url) if args.only.lower() in _slug(c).lower()]
    session = _make_session()
    index, ok, total_parts = [], 0, 0

    for path in catalogs:
        url, slug = _url_for(path), _slug(path)
        try:
            r = session.get(url, headers=_HEADERS, timeout=40)
            status = r.status_code
            if status == 200 and "application/json" in r.headers.get("Content-Type", ""):
                data = r.json()
                details = data.get("details", [])
                with open(os.path.join(outdir, f"{slug}.json"), "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=1)
                techs = _distinct_technology(details)
                ok += 1
                total_parts += len(details)
                print(f"  ✓ {slug:32s} {len(details):5d} partes  · Technology: {techs}")
                index.append({"path": path, "slug": slug, "status": 200,
                              "count": len(details), "technology": techs})
            else:
                print(f"  ✗ {slug:32s} HTTP {status} (grupo/slug a confirmar na UI)")
                index.append({"path": path, "slug": slug, "status": status, "count": 0})
        except Exception as e:
            print(f"  ! {slug:32s} erro: {e}")
            index.append({"path": path, "slug": slug, "status": "error", "error": str(e)})
        time.sleep(args.delay)

    with open(os.path.join(outdir, "_index.json"), "w", encoding="utf-8") as fh:
        json.dump({"date": date, "catalogs": index}, fh, ensure_ascii=False, indent=1)

    print(f"\nSnapshot {date}: {ok}/{len(catalogs)} catálogos OK · {total_parts} partes · dir: {outdir}")
    print("Paginação: compare 'count' de um catálogo DDR grande com o 'Show all' da UI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
