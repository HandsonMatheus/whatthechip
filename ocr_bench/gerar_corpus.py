#!/usr/bin/env python3
"""
gerar_corpus.py — monta o ocr_bench/corpus.js (o "juiz" da bancada de OCR).

SOMENTE LEITURA. Não escreve no banco, não altera nada do catálogo.
(Regra de ouro #1 do CLAUDE.md vale para comandos que ALTERAM dados; este só lê.)

Dois modos:

    python3 gerar_corpus.py                 # do seed_known_parts.json (596 PNs) — funciona sem Django
    python3 gerar_corpus.py --from-db       # do banco (LOCAL por padrão) — 6 mil+ PNs, muito melhor

Para o banco de PROD (opcional, ainda só leitura):
    export DATABASE_URL="postgresql://…render.com:5432/…"
    python3 gerar_corpus.py --from-db

O corpus é o que decide a qualidade da bancada: quanto mais PNs reais, mais
honesta a medição. Comece pelo seed, troque pelo banco assim que puder.
"""
import argparse, json, os, sys, datetime, pathlib

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent


def _spec(cap, nand, ram, dgbit, dgb):
    """Uma linha curta de spec, só pra conferência visual no card do candidato."""
    if nand or ram:
        return " + ".join(x for x in (nand, ram) if x)
    return cap or dgbit or dgb or ""


def do_seed():
    p = RAIZ / "seed_known_parts.json"
    if not p.exists():
        sys.exit(f"não achei {p} — rode com --from-db ou ponha o seed na raiz do repo")
    regs = json.load(open(p, encoding="utf-8"))
    linhas = []
    for r in regs:
        pn = (r.get("part_number") or "").strip().upper()
        if not pn:
            continue
        linhas.append([
            pn,
            (r.get("brand") or "").strip(),
            (r.get("chip_type") or "").strip(),
            _spec(r.get("capacity"), r.get("emcp_nand"), r.get("emcp_ram"),
                  r.get("density_gbit"), r.get("density_gb")),
            (r.get("fbga_code") or "").strip().upper(),
        ])
    return linhas, f"seed_known_parts.json ({len(linhas)} PNs)"


def do_db():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    sys.path.insert(0, str(RAIZ))
    try:
        import django
        django.setup()
        from chips.models import KnownPart
    except Exception as e:
        sys.exit(f"não consegui subir o Django ({e}).\n"
                 f"Rode de dentro do venv, a partir da raiz do repo:\n"
                 f"  source venv/bin/activate && python3 ocr_bench/gerar_corpus.py --from-db")

    qs = (KnownPart.objects
          .filter(confidence__in=("confirmed", "manual", "distributor"),
                  review_status="approved")
          .select_related("brand")
          .values("part_number", "chip_type", "capacity", "emcp_nand", "emcp_ram",
                  "density_gbit", "density_gb", "fbga_code", "brand__name"))
    linhas = []
    for r in qs.iterator(chunk_size=2000):
        pn = (r["part_number"] or "").strip().upper()
        if not pn:
            continue
        linhas.append([
            pn,
            (r["brand__name"] or "").strip(),
            (r["chip_type"] or "").strip(),
            _spec(r["capacity"], r["emcp_nand"], r["emcp_ram"],
                  r["density_gbit"], r["density_gb"]),
            (r["fbga_code"] or "").strip().upper(),
        ])
    banco = os.environ.get("DATABASE_URL", "")
    onde = "PROD (DATABASE_URL)" if "render.com" in banco else "banco local"
    return linhas, f"{onde} — KnownPart approved ({len(linhas)} PNs)"


def prefixos():
    """Os prefixos de família da gramática — o discriminador 'esta linha é um PN'."""
    import re
    out = set()
    d = RAIZ / "chips" / "knowledge"
    if not d.exists():
        return []
    for f in sorted(d.glob("*.yaml")):
        if f.name.startswith("_"):          # fixture/rascunho não é marca (CLAUDE.md §7)
            continue
        for ln in open(f, encoding="utf-8"):
            m = re.match(r"""^\s*-?\s*prefix:\s*["']?([A-Za-z0-9\-]+)["']?\s*$""", ln)
            if m:
                out.add(m.group(1).upper())
    return sorted(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-db", action="store_true", help="lê do banco em vez do seed (só leitura)")
    a = ap.parse_args()

    linhas, fonte = do_db() if a.from_db else do_seed()
    linhas.sort(key=lambda r: r[0])
    pfx = prefixos()

    destino = AQUI / "corpus.js"
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write("/* corpus.js — GERADO por gerar_corpus.py. Não editar à mão. */\n")
        fh.write("window.WTC_CORPUS = {\n")
        fh.write(f'  gerado_em: {json.dumps(datetime.date.today().isoformat())},\n')
        fh.write(f'  fonte: {json.dumps(fonte)},\n')
        fh.write(f'  prefixos: {json.dumps(pfx, ensure_ascii=False)},\n')
        fh.write('  /* [part_number, marca, chip_type, spec, fbga] */\n')
        fh.write("  pns: [\n")
        for r in linhas:
            fh.write("    " + json.dumps(r, ensure_ascii=False) + ",\n")
        fh.write("  ]\n};\n")

    kb = destino.stat().st_size / 1024
    print(f"✓ {destino}")
    print(f"  fonte    : {fonte}")
    print(f"  PNs      : {len(linhas)}")
    print(f"  FBGA     : {sum(1 for r in linhas if r[4])}")
    print(f"  prefixos : {len(pfx)}")
    print(f"  tamanho  : {kb:.0f} KB")
