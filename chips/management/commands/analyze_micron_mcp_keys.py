"""
analyze_micron_mcp_keys.py
==========================
Analisa os KnownParts de famílias MCP Micron (MT29TZZZ, MT29VZZZ, MT30AZZZ) para
descobrir e verificar as chaves de decodificação via dados OFICIAIS da API Micron.

OBJETIVO
--------
Construir os mapas MIC_MCP_CAP e MIC_TZZZ_GEN com dados verificados — não com
achismos ou inferências de outras famílias. Cada chave no mapa deve ter evidência
confirmada do campo "part-name" da API FBGA oficial da Micron.

FLUXO RECOMENDADO
-----------------
1. Coletar a família inteira:
     python manage.py collect_micron_catalog --strategy seed
     # usa JWA60/JY941 como sementes → expande para TODA a família MT29TZZZ

2. Preencher capacidades via API FBGA:
     python manage.py fill_capacity_from_micron_api

3. Analisar as chaves descobertas (este script):
     python manage.py analyze_micron_mcp_keys --prefix MT29TZZZ
     python manage.py analyze_micron_mcp_keys --prefix MT29VZZZ
     python manage.py analyze_micron_mcp_keys --prefix MT30AZZZ

4. Revisar o relatório — as entradas "CONFIRMADO" estão prontas para entrar
   no populate_micron_mcp.py. Entradas sem part-name na API precisam de
   verificação manual antes de serem adicionadas.

SAÍDA
-----
Para cada prefixo analisado, o script reporta:

  --- MIC_MCP_CAP (decode_cap, pn[8:11]) ---
  Chave  Chips  Exemplo PN              Part-name API Micron           Total Gb  NAND(GB)  RAM(GB)  Status
  8D5    3      MT29TZZZ8D5BKFAH...     MLC EMMC/LPDDR2 72G VFBGA    72        8         1        CONFIRMADO ✓
  AD8    12     MT29VZZZAD8GQFSL...     MCP 544Gb EMMC+LPDDR4 VFBGA  544       64        4        CONFIRMADO ✓
  ?X?    2      MT29TZZZ...             (sem API data)                 ?         ?         ?        REQUER PESQUISA

  ⚠ BUG-8 (2026-06-19): o part-name "MLC EMMC/LPDDR2 72G VFBGA" acima diz "LPDDR2"
  mas a família MT29TZZZ é LPDDR3 — o "LPDDR2" pertence à família MT29PZZZ (162-ball).
  A API Micron retorna part-names de famílias relacionadas que podem ter tipos de RAM
  DIFERENTES. Usar o part-name para determinar tipo de RAM = FONTE NÃO CONFIÁVEL.
  Fontes confiáveis: datasheet oficial / DigiKey (confirmado: MT29TZZZ = LPDDR3).

  --- MIC_TZZZ_GEN (decode_gen, pn[8]) ---
  Char  Chips  Tipo       Part-names API                              Status
  8     3      LPDDR3     MLC EMMC/LPDDR2 72G VFBGA (⚠ "LPDDR2"    CONFIRMADO ✓ (BUG-8:
                          no part-name é ERRO DA API — ver BUG-8)    datasheet=LPDDR3; pn[8] dígito → Gen A)
  A     7      (?)        (sem API data suficiente)                  REQUER PESQUISA

COMO FUNCIONA A EXTRAÇÃO DE CAPACIDADE
---------------------------------------
A API Micron retorna o campo "part-name" para cada chip.
Exemplos de formatos encontrados (todos confirmados da bancada):

  "MLC EMMC/LPDDR2 72G VFBGA"       → 72 Gbit total (Gen A MT29TZZZ)
  ⚠ ATENÇÃO BUG-8: "LPDDR2" neste part-name é ERRO da API Micron para MT29TZZZ.
    A família MT29TZZZ é LPDDR3. O "LPDDR2" pertence à MT29PZZZ (162-ball).
    NÃO use o part-name para inferir tipo de RAM — use datasheet/DigiKey.
  "MCP 544Gb EMMC+LPDDR4 VFBGA"     → 544 Gbit total
  "MCP eMMC+LPDDR4 1056Gb"          → 1056 Gbit total
  "e.MMC 5.1 + LPDDR4 544G"         → 544 Gbit total

O script parseia o total em Gbit e, quando possível, propõe o split NAND/RAM
usando as tabelas de decodificação já conhecidas como base de verificação.

Nota sobre unidades: "G" em part-names Micron de EMMC = Gbit (não GB!).
Chips SSD (MTFD) usam "GB" explícito — mas este script não cobre MTFD.

USO
----
    python manage.py analyze_micron_mcp_keys
    python manage.py analyze_micron_mcp_keys --prefix MT29TZZZ
    python manage.py analyze_micron_mcp_keys --prefix MT29VZZZ --verbose
    python manage.py analyze_micron_mcp_keys --fetch-missing   # chama a API para chips sem notes
    python manage.py analyze_micron_mcp_keys --export csv      # grava CSV para revisão offline
"""

import csv
import io
import re
import time
import logging
from collections import defaultdict

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# ── Famílias e suas posições de decodificação ────────────────────────────────
FAMILY_CONFIG = {
    "MT29VZZZ": {"cap_pos": 8, "cap_len": 3, "gen_pos": 8, "gen_len": 1,
                 "cap_map": "MIC_MCP_CAP", "gen_map": None,
                 "desc": "eMCP/uMCP LPDDR4 (eMMC 5.1 / UFS 2.2)"},
    "MT29TZZZ": {"cap_pos": 8, "cap_len": 3, "gen_pos": 8, "gen_len": 1,
                 "cap_map": "MIC_MCP_CAP", "gen_map": "MIC_TZZZ_GEN",
                 "desc": "eMCP LPDDR3 (eMMC 4.x/5.0, geração anterior) — BUG-8: TODA família é LPDDR3"},
    "MT30AZZZ": {"cap_pos": 8, "cap_len": 3, "gen_pos": 8, "gen_len": 1,
                 "cap_map": "MIC_MCP_CAP", "gen_map": None,
                 "desc": "uMCP LPDDR5 (UFS 3.1)"},
}

# Regex para extrair densidade total em Gbit do part-name
# Formatos encontrados na API Micron:
#   "MLC EMMC/LPDDR2 72G VFBGA"    → 72 (Gbit)
#   "MCP 544Gb EMMC+LPDDR4 VFBGA"  → 544 (Gbit, com 'b' minúsculo = Gbit)
#   "MCP eMMC+LPDDR4 1056Gb"       → 1056 (Gbit)
#   "e.MMC 5.1 + LPDDR4 544G"      → 544 (Gbit)
# Importante: "G" ou "Gb" em part-names Micron de eMMC/MCP = Gbit, nunca GB.
_GBIT_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*Gb?\b',  # "72G", "544Gb", "1056Gb" — case sensitive b
    re.IGNORECASE,
)

# Regex para detectar dados da API no campo notes
_API_TAG_RE = re.compile(r'\[Micron FBGA API\]', re.IGNORECASE)

# Chaves já verificadas no MIC_MCP_CAP (para marcar status)
KNOWN_CAP_KEYS = {
    "7D8", "AD8", "BD8",
    "AD9", "BD9", "CD9",
    "BDA", "CDA", "DDA", "EDA",
    "CDB", "DDB", "EDB",
    "8D5",  # Gen A confirmado JWA60/JY941
}

# Chaves já verificadas no MIC_TZZZ_GEN
KNOWN_GEN_KEYS = {"8"}


def _extract_gbit_from_partname(part_name: str) -> float | None:
    """
    Extrai total em Gbit do part-name Micron.

    Retorna o maior valor encontrado (o total da densidade sempre é o maior número
    no part-name — evita capturar números de versão como '5.1' ou '2.2').
    """
    if not part_name:
        return None
    candidates = []
    for m in _GBIT_RE.finditer(part_name):
        val = float(m.group(1))
        if val >= 8:  # Gbit mínimo razoável para MCP (8 Gbit = 1GB)
            candidates.append(val)
    return max(candidates) if candidates else None


def _extract_api_partname_from_notes(notes: str) -> str | None:
    """
    Extrai o part-name da API Micron do campo notes.

    O fill_capacity_from_micron_api.py grava no formato:
      "[Micron FBGA API] part-name: MLC EMMC/LPDDR2 72G VFBGA (source: ...)"
    ou simplesmente como parte do texto com a tag [Micron FBGA API].
    """
    if not notes or not _API_TAG_RE.search(notes):
        return None

    # Tenta extrair o part-name literal da linha
    # Formato: "[Micron FBGA API] part-name: <part_name>"
    m = re.search(r'part-name:\s*(.+?)(?:\s*\(source|\s*$)', notes, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Formato alternativo: "[Micron FBGA API] <part_name>"
    m = re.search(r'\[Micron FBGA API\]\s+(.+?)(?:\s*$|\n)', notes, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        # Filtra linhas que são apenas metadados (source: ..., date: ...)
        if not re.match(r'^(source|date|fbga|url):', candidate, re.IGNORECASE):
            return candidate

    return None


def _gbit_to_gb(gbit: float) -> str:
    """Converte Gbit para string GB (ex: 64.0 → '8GB', 8.0 → '1GB')."""
    gb = gbit / 8
    if gb == int(gb):
        return f"{int(gb)}GB"
    return f"{gb:.1f}GB"


def _propose_nand_ram_split(cap_key: str, total_gbit: float) -> tuple[str | None, str | None]:
    """
    Propõe o split NAND/RAM para uma chave de 3 chars com base no total Gbit.

    Tabela de RAM codes conhecidos (Gen B, confirmados via MT29VZZZ/MT30AZZZ):
      7 → 3GB (24Gb)
      A → 4GB (32Gb)
      B → 6GB (48Gb)
      C → 8GB (64Gb)
      D → 12GB (96Gb)
      E → 16GB (128Gb)

    Tabela de NAND codes conhecidos:
      D8 → 64GB (512Gb)
      D9 → 128GB (1024Gb)
      DA → 256GB (2048Gb)
      DB → 512GB (4096Gb)

    Para Gen A (pn[8] = dígito), a estrutura é diferente — não tenta inferir.
    Retorna (None, None) se não conseguir propor.

    ⚠ Estas são propostas baseadas em padrões EXISTENTES — devem ser confirmadas
    pelo part-name da API antes de entrar no mapa.
    """
    if len(cap_key) != 3:
        return None, None

    ram_char = cap_key[0]
    nand_code = cap_key[1:]

    # Gen A: pn[8] é dígito — não tenta inferir
    if ram_char.isdigit():
        return None, None

    # Tabela de RAM codes (confirmados via MT29VZZZ)
    ram_gb_map = {'7': 24, 'A': 32, 'B': 48, 'C': 64, 'D': 96, 'E': 128}
    # Tabela de NAND codes (confirmados via MT29VZZZ)
    nand_gb_map = {'D8': 512, 'D9': 1024, 'DA': 2048, 'DB': 4096}

    ram_gbit = ram_gb_map.get(ram_char)
    nand_gbit = nand_gb_map.get(nand_code)

    if ram_gbit is None or nand_gbit is None:
        return None, None

    # Verifica se o split bate com o total reportado pela API
    expected_total = ram_gbit + nand_gbit
    if abs(expected_total - total_gbit) < 1.0:
        return _gbit_to_gb(nand_gbit), _gbit_to_gb(ram_gbit)

    # Total não confere — proposta não confiável
    return None, None


class Command(BaseCommand):
    help = (
        "Analisa KnownParts MCP Micron para descobrir e verificar chaves de decode. "
        "Usa SOMENTE dados confirmados da API oficial Micron (campo notes). "
        "Pré-requisito: rodar collect_micron_catalog + fill_capacity_from_micron_api."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--prefix",
            type=str,
            default=None,
            choices=list(FAMILY_CONFIG.keys()),
            help="Prefixo da família a analisar. Padrão: todas as famílias.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Lista cada chip individualmente.",
        )
        parser.add_argument(
            "--fetch-missing",
            action="store_true",
            help="Chama a API Micron para chips sem API data nas notes (lento).",
        )
        parser.add_argument(
            "--export",
            type=str,
            default=None,
            choices=["csv"],
            help="Exporta resultado em CSV para revisão offline.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            help="Delay entre chamadas à API (segundos). Padrão: 1.0.",
        )

    def handle(self, *args, **options):
        prefixes = [options["prefix"]] if options["prefix"] else list(FAMILY_CONFIG.keys())
        verbose  = options["verbose"]
        fetch    = options["fetch_missing"]
        export   = options["export"]
        delay    = options["delay"]

        session = None
        if fetch:
            session = self._make_session()

        all_rows = []  # para exportação CSV

        for prefix in prefixes:
            cfg = FAMILY_CONFIG[prefix]
            self.stdout.write(self.style.SUCCESS(
                f"\n{'═'*70}\n  {prefix} — {cfg['desc']}\n{'═'*70}"
            ))
            rows = self._analyze_family(prefix, cfg, verbose, fetch, session, delay)
            all_rows.extend(rows)

        if export == "csv":
            self._export_csv(all_rows)

        if not export:
            self.stdout.write(self.style.SUCCESS(
                "\n✅  Análise concluída. "
                "Adicione ao populate_micron_mcp.py SOMENTE entradas 'CONFIRMADO ✓'.\n"
                "Para coletar mais chips da família:\n"
                "  python manage.py collect_micron_catalog --strategy seed\n"
                "  python manage.py fill_capacity_from_micron_api --limit 500\n"
            ))

    # ──────────────────────────────────────────────────────────────────────────

    def _analyze_family(self, prefix, cfg, verbose, fetch, session, delay):
        from chips.models import KnownPart, DecodeMap

        cap_pos = cfg["cap_pos"]
        cap_len = cfg["cap_len"]
        gen_pos = cfg["gen_pos"]
        gen_len = cfg["gen_len"]
        cap_map_name = cfg["cap_map"]
        gen_map_name = cfg.get("gen_map")

        # Carrega mapas existentes no banco
        existing_cap = {
            obj.char_key: (obj.val_primary, obj.val_secondary)
            for obj in DecodeMap.objects.filter(map_name=cap_map_name)
        }
        existing_gen = {}
        if gen_map_name:
            existing_gen = {
                obj.char_key: obj.val_primary
                for obj in DecodeMap.objects.filter(map_name=gen_map_name)
            }

        # Busca todos os KnownParts da família
        qs = KnownPart.objects.filter(
            part_number__startswith=prefix,
            status="enriched",
        ).values("part_number", "fbga_code", "notes", "emcp_nand", "emcp_ram", "confidence")

        total = qs.count()
        self.stdout.write(f"\n  KnownParts enriched: {total}")
        if total == 0:
            self.stdout.write(self.style.WARNING(
                f"  ⚠ Nenhum chip {prefix} no banco. "
                f"Rode: python manage.py collect_micron_catalog --strategy seed"
            ))
            return []

        # Agrupa por chave de capacidade (pn[cap_pos:cap_pos+cap_len])
        cap_groups  = defaultdict(list)  # key → list of (pn, fbga, part_name, total_gbit)
        gen_groups  = defaultdict(list)  # gen_char → list of (pn, fbga, part_name, total_gbit)
        no_api_data = []  # chips sem dados da API

        for row in qs:
            pn = row["part_number"]
            if len(pn) < cap_pos + cap_len:
                continue

            cap_key  = pn[cap_pos:cap_pos + cap_len]
            gen_char = pn[gen_pos:gen_pos + gen_len] if gen_map_name else None

            # Extrai part-name da API das notes
            notes     = row["notes"] or ""
            part_name = _extract_api_partname_from_notes(notes)
            total_gbit = None

            if part_name:
                total_gbit = _extract_gbit_from_partname(part_name)
            elif fetch and row["fbga_code"] and session:
                # Chama API para chips sem dados
                api_data = self._fetch_api(row["fbga_code"], session, verbose)
                if api_data:
                    part_name  = api_data.get("part_name", "")
                    total_gbit = _extract_gbit_from_partname(part_name)
                time.sleep(delay)

            chip_info = (pn, row["fbga_code"] or "", part_name or "", total_gbit)

            cap_groups[cap_key].append(chip_info)
            if gen_char and gen_map_name:
                gen_groups[gen_char].append(chip_info)

            if not part_name:
                no_api_data.append(pn)

        rows = []

        # ── Relatório: chaves de capacidade (MIC_MCP_CAP) ─────────────────────
        self.stdout.write(f"\n  {'─'*68}")
        self.stdout.write(f"  MIC_MCP_CAP — chaves de capacidade (pn[{cap_pos}:{cap_pos+cap_len}])")
        self.stdout.write(f"  {'─'*68}")
        header = f"  {'Chave':<5} {'Chips':>5}  {'Part-name API (exemplo)':<40}  {'Total Gb':>8}  {'NAND':>7}  {'RAM':>5}  Status"
        self.stdout.write(header)
        self.stdout.write(f"  {'─'*68}")

        for cap_key in sorted(cap_groups.keys()):
            chips = cap_groups[cap_key]
            n = len(chips)
            in_map = cap_key in existing_cap

            # Coleta todos os part-names e totais distintos
            part_names = list({c[2] for c in chips if c[2]})
            totals     = [c[3] for c in chips if c[3] is not None]
            total_gbit = min(totals) if totals else None  # usa min para evitar outliers

            example_pn    = chips[0][0][:28] if chips else ""
            example_pname = part_names[0][:40] if part_names else "(sem API data)"
            example_total = f"{total_gbit:.0f}" if total_gbit else "?"

            # Proposta de split
            nand_prop, ram_prop = None, None
            if total_gbit and not cap_key[0].isdigit():
                nand_prop, ram_prop = _propose_nand_ram_split(cap_key, total_gbit)

            if in_map:
                nand_str = existing_cap[cap_key][0]
                ram_str  = existing_cap[cap_key][1]
                if part_names and total_gbit:
                    status = "CONFIRMADO ✓"
                else:
                    status = "no mapa (sem API data)"
            else:
                nand_str = nand_prop or "?"
                ram_str  = ram_prop  or "?"
                if part_names and total_gbit and nand_prop:
                    status = "NOVO — verificado ✓ (adicionar ao mapa)"
                elif part_names and total_gbit:
                    status = "NOVO — verificado (split manual necessário)"
                else:
                    status = "REQUER PESQUISA (sem API data)"

            line = (
                f"  {cap_key:<5} {n:>5}  {example_pname:<40}  "
                f"{example_total:>8}  {nand_str:>7}  {ram_str:>5}  {status}"
            )
            if "REQUER" in status:
                self.stdout.write(self.style.WARNING(line))
            elif "NOVO" in status:
                self.stdout.write(self.style.SUCCESS(line))
            else:
                self.stdout.write(line)

            if verbose:
                for pn, fbga, pname, gbit in chips[:5]:
                    self.stdout.write(
                        f"      FBGA:{fbga or '?????'}  PN:{pn[:32]}  "
                        f"part-name:{pname[:40] or '(nenhum)'}  total:{gbit or '?'}Gb"
                    )
                if n > 5:
                    self.stdout.write(f"      ... e mais {n-5} chips")

            rows.append({
                "prefix":      prefix,
                "map":         cap_map_name,
                "key":         cap_key,
                "count":       n,
                "example_pn":  example_pn,
                "part_names":  " | ".join(part_names[:3]),
                "total_gbit":  example_total,
                "nand":        nand_str,
                "ram":         ram_str,
                "status":      status,
            })

        # ── Relatório: chaves de geração (MIC_TZZZ_GEN, se aplicável) ─────────
        if gen_map_name:
            self.stdout.write(f"\n  {'─'*68}")
            self.stdout.write(
                f"  {gen_map_name} — tipo de RAM por geração "
                f"(pn[{gen_pos}:{gen_pos+gen_len}])"
            )
            self.stdout.write(f"  {'─'*68}")
            header2 = f"  {'Char':<5} {'Chips':>5}  {'Tipo gen.':<12}  {'Part-name API (exemplo)':<42}  Status"
            self.stdout.write(header2)
            self.stdout.write(f"  {'─'*68}")

            for gen_char in sorted(gen_groups.keys()):
                chips = gen_groups[gen_char]
                n     = len(chips)
                in_map = gen_char in existing_gen
                mapped_type = existing_gen.get(gen_char, "")

                part_names = list({c[2] for c in chips if c[2]})
                example_pname = part_names[0][:42] if part_names else "(sem API data)"

                # Infere o tipo de geração pelo pn[8]
                if gen_char.isdigit():
                    inferred_type = "Gen A (pn[8]=dígito → LPDDR2?)"
                else:
                    inferred_type = "Gen B (pn[8]=letra → LPDDR3?)"

                type_str = mapped_type if in_map else inferred_type

                if in_map and part_names:
                    status = f"CONFIRMADO ✓ ({mapped_type})"
                elif in_map:
                    status = f"no mapa ({mapped_type}) — sem API data"
                elif part_names:
                    status = "NOVO — verificado (tipo inferido: revisar part-name)"
                else:
                    status = "REQUER PESQUISA"

                line = f"  {gen_char:<5} {n:>5}  {type_str:<12}  {example_pname:<42}  {status}"
                if "REQUER" in status:
                    self.stdout.write(self.style.WARNING(line))
                elif "NOVO" in status:
                    self.stdout.write(self.style.SUCCESS(line))
                else:
                    self.stdout.write(line)

                if verbose:
                    for pn, fbga, pname, gbit in chips[:3]:
                        lpddr = "LPDDR2" if "lpddr2" in pname.lower() else (
                            "LPDDR3" if "lpddr3" in pname.lower() else "?"
                        )
                        self.stdout.write(
                            f"      FBGA:{fbga or '?????'}  PN:{pn[:32]}  "
                            f"part-name:{pname[:42] or '(nenhum)'}  RAM:{lpddr}"
                        )

                rows.append({
                    "prefix":     prefix,
                    "map":        gen_map_name,
                    "key":        gen_char,
                    "count":      n,
                    "example_pn": chips[0][0][:28] if chips else "",
                    "part_names": " | ".join(part_names[:3]),
                    "total_gbit": "",
                    "nand":       "",
                    "ram":        type_str,
                    "status":     status,
                })

        # ── Chips sem API data ─────────────────────────────────────────────────
        if no_api_data:
            self.stdout.write(self.style.WARNING(
                f"\n  ⚠ {len(no_api_data)} chip(s) sem API data nas notes."
            ))
            self.stdout.write(
                "  Para obter os part-names oficiais da Micron:\n"
                "    python manage.py fill_capacity_from_micron_api\n"
                "    python manage.py analyze_micron_mcp_keys --fetch-missing\n"
            )
            if verbose:
                for pn in no_api_data[:10]:
                    self.stdout.write(f"    {pn}")
                if len(no_api_data) > 10:
                    self.stdout.write(f"    ... e mais {len(no_api_data)-10}")

        return rows

    # ──────────────────────────────────────────────────────────────────────────

    def _make_session(self):
        """curl_cffi preferido (TLS Chrome) para contornar bloqueios Cloudflare."""
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

    def _fetch_api(self, fbga: str, session, verbose: bool) -> dict | None:
        """Consulta a API Micron FBGA para obter part-name de um chip."""
        from chips.management.commands.fill_capacity_from_micron_api import (
            _query_by_fbga,
        )
        try:
            return _query_by_fbga(fbga, session, verbose=verbose)
        except Exception as e:
            logger.warning("Erro ao consultar API para FBGA %s: %s", fbga, e)
            return None

    def _export_csv(self, rows: list):
        """Exporta os resultados para CSV."""
        import os
        from django.conf import settings

        out_path = os.path.join(
            getattr(settings, "BASE_DIR", "."),
            "micron_mcp_keys_analysis.csv"
        )
        fieldnames = ["prefix", "map", "key", "count", "example_pn",
                      "part_names", "total_gbit", "nand", "ram", "status"]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(
            f"\n  CSV exportado: {out_path}"
        ))
        self.stdout.write(
            "  Abra no Excel/Sheets para revisar as entradas antes de adicionar ao mapa.\n"
        )
