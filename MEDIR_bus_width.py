# -*- coding: utf-8 -*-
"""
MEDIR_bus_width.py — READ-ONLY. Quanto de LARGURA (x4/x8/x16/x32/x64) mora hoje no
campo `interface`, em KnownPart e ChipFamily, por classe e por marca — e o que NÃO é
largura nem protocolo (OUTRO, listado valor a valor).

    env -u DATABASE_URL python MEDIR_bus_width.py      # local
    python MEDIR_bus_width.py                           # prod (DATABASE_URL exportado)

Roda em transação revertida. Aborta em zero (leitura que não aconteceu ≠ "não tem").
"""
import collections, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django; django.setup()                                     # noqa: E402
from django.db import connection, transaction                     # noqa: E402
from chips.models import KnownPart, ChipFamily                    # noqa: E402
from chips.chip_types import spec_for                             # noqa: E402
# Depois da Fase 2 importe de chips.knowledge.convention: split_bus_width, e de
# chips.conventions: BUS_WIDTH_VOCAB. Na Fase 0 (antes do código existir) use as cópias abaixo.
VOCAB = ("x4", "x8", "x16", "x32", "x64")
RX_LEAD  = re.compile(r"^\s*(x(?:4|8|16|32|64))\b\s*(.*)$", re.I)
RX_SPEED = re.compile(r"^@\s*(\S.*)$")
RX_PROTO = re.compile(r"(eMMC|UFS|ONFI|Async|NAND|NOR|SPI|PPN|mDOC|Rambus|PCIe)", re.I)
RX_ANY   = re.compile(r"\bx(4|8|16|32|64)\b", re.I)          # largura em QUALQUER posição (só para listar)

def balde(v: str) -> str:
    v = (v or "").strip()
    if not v: return "VAZIO"
    m = RX_LEAD.match(v)
    if m:
        resto = m.group(2).strip()
        if not resto: return "LARGURA_PURA"
        if RX_SPEED.match(resto): return "LARGURA+VELOCIDADE"
        return "LARGURA+SOBRA"          # 'x16 (2 dies)' — sobra sem destino
    if RX_SPEED.match(v): return "VELOCIDADE_SÓ"
    if RX_PROTO.search(v): return "PROTOCOLO"
    return "OUTRO"

def classe(chip_type: str) -> str:
    s = spec_for(chip_type or "")
    return s.category if s else ("(vazio)" if not chip_type else "(fora do vocabulário)")

def main():
    d = connection.settings_dict
    print(f"\n⚠  BANCO-ALVO → name={d.get('NAME')}  host={d.get('HOST') or 'localhost'}  port={d.get('PORT') or ''}\n")
    sid = transaction.savepoint()
    try:
        total = KnownPart.objects.count(); nfam = ChipFamily.objects.count()
        print(f"KnownPart: {total}   ChipFamily: {nfam}")
        if total == 0 or nfam == 0:
            print("✗ ZERO linhas — leitura que não aconteceu (banco errado? vazio?). Abortando."); return 1

        # 1. KnownPart: balde × classe, por marca, e OUTRO valor a valor
        bc = collections.Counter(); por_marca = collections.Counter(); outros = collections.Counter()
        classe_nao_permite = []; diverg = []; sobras = []
        qs = KnownPart.objects.select_related("brand", "family").only(
            "part_number", "interface", "chip_type", "brand__name", "family__interface", "family__prefix")
        for kp in qs.iterator(chunk_size=2000):
            b = balde(kp.interface); c = classe(kp.chip_type)
            bc[(b, c)] += 1
            if b != "VAZIO": por_marca[(kp.brand.name, b)] += 1
            if b == "OUTRO": outros[kp.interface.strip()] += 1
            if b == "LARGURA+SOBRA": sobras.append((kp.part_number, kp.interface))
            if b.startswith("LARGURA") and c in ("managed_nand", "managed_mcp", "catalog"):
                classe_nao_permite.append((kp.part_number, kp.chip_type, kp.interface))
            if b.startswith("LARGURA") and kp.family and RX_LEAD.match(kp.family.interface or ""):
                fw = RX_LEAD.match(kp.family.interface).group(1).lower()
                kw = RX_LEAD.match(kp.interface).group(1).lower()
                if fw != kw: diverg.append((kp.part_number, kp.family.prefix, fw, kw))
        print("\n── KnownPart.interface: balde × classe ──")
        for (b, c), n in sorted(bc.items(), key=lambda kv: -kv[1]): print(f"{n:6d}  {b:20s} {c}")
        print("\n── por marca (só não-vazios) ──")
        for (m, b), n in sorted(por_marca.items()): print(f"{n:6d}  {m:16s} {b}")
        print(f"\n── OUTRO ({sum(outros.values())} registros, {len(outros)} valores distintos) — TODOS: ──")
        for v, n in outros.most_common(): print(f"{n:6d}  {v!r}")
        print(f"\n── LARGURA+SOBRA (não migram): {len(sobras)} ──"); [print("   ", *s) for s in sobras]
        print(f"\n── largura em classe NÃO permitida (eMMC/UFS/eMCP/uMCP/catalog): {len(classe_nao_permite)} ──"); [print("   ", *s) for s in classe_nao_permite]
        print(f"\n── DIVERGÊNCIA known × família (tela vai mudar para o valor do registro): {len(diverg)} ──"); [print("   ", *s) for s in diverg]

        # 2. ChipFamily
        fb = collections.Counter(); fout = []; fdentro = []
        for f in ChipFamily.objects.select_related("brand").only("prefix", "interface", "chip_type", "brand__name"):
            b = balde(f.interface); fb[b] += 1
            if b not in ("VAZIO", "PROTOCOLO"): fout.append((f.brand.name, f.prefix, f.chip_type, f.interface))
            elif RX_ANY.search(f.interface or ""): fdentro.append((f.brand.name, f.prefix, f.chip_type, f.interface))
        print("\n── ChipFamily.interface ──")
        for b, n in fb.most_common(): print(f"{n:6d}  {b}")
        print("   famílias fora de VAZIO/PROTOCOLO (as 25 + os OUTRO):"); [print("   ", *x) for x in sorted(fout)]
        print("   largura DENTRO de texto de protocolo (não migram — decisão do dono):"); [print("   ", *x) for x in sorted(fdentro)]

        # 3. Lote (informativo, D6 — nada será tocado). RLS: precisa do escopo de plataforma.
        try:
            from tenancy.scope import platform_scope
            from estoque.models import InventoryEntry, PendingEntry, RejectedEntry
            with platform_scope():
                for M in (InventoryEntry, PendingEntry, RejectedEntry):
                    tot = M.all_companies.count()
                    n = sum(1 for e in M.all_companies.only("interface").iterator() if balde(e.interface).startswith(("LARGURA", "VELOCIDADE")))
                    print(f"   {M.__name__:15s} total={tot:6d}  com largura/velocidade em interface={n}")
                    if tot == 0: print("   ⚠ zero linhas — se o banco tem lotes, o RLS engoliu a leitura")
        except Exception as exc:            # noqa: BLE001
            print(f"   (lote não lido: {type(exc).__name__}: {exc})")
        return 0
    finally:
        transaction.savepoint_rollback(sid)

if __name__ == "__main__":
    sys.exit(main())
