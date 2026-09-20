# -*- coding: utf-8 -*-
"""
IDENTIFICAR_largura.py — READ-ONLY. Monta, por MARCA, o CSV de identificacao de
largura de barramento de cada chip: `LARGURA_IDENTIFICADA_<marca>.csv`.

    env -u DATABASE_URL python IDENTIFICAR_largura.py samsung
    env -u DATABASE_URL python IDENTIFICAR_largura.py micron

NAO ESCREVE NADA NO BANCO. Roda em transacao revertida. Aborta se ler zero.

Tres fontes, nesta ordem de autoridade:
  1. BANCO      — o campo `interface` do KnownPart, quando ja traz um token de
                  largura. E a testemunha independente que ja existe.
  2. EVIDENCIA  — `EVIDENCIA_largura.csv`, o que a pesquisa achou em datasheet do
                  fabricante. Casa por PREFIXO de PN (o sufixo "-BC##" das tabelas
                  da Samsung e curinga e cobre os sufixos do catalogo).
  3. REGRA      — a gramatica posicional da marca, e SO se a familia estiver
                  corroborada (>=5 concordancias entre regra e banco/evidencia,
                  0 divergencias, >=2 larguras distintas). Mesma barra do
                  COLETAR_largura_bits.py.

⚠ CIRCULARIDADE (HANDOFF §3): a regra nunca se prova sozinha. Ela so e aceita
depois de concordar com banco/evidencia, que sao independentes dela. Uma unica
divergencia derruba a familia inteira — e nao se "conserta" o PN.
"""
import collections, csv, os, re, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django; django.setup()                                    # noqa: E402
from django.db import connection, transaction                    # noqa: E402
from chips.models import KnownPart                               # noqa: E402
from chips.chip_types import spec_for                            # noqa: E402

MIN_PROVAS, MIN_LARGURAS = 5, 2
RX_LARGURA = re.compile(r"^\s*(x(?:4|8|16|32|64))\b", re.I)
# classes em que largura de barramento existe (PLANO_BUS_WIDTH §3.2)
CLASSES_OK = {"dram_pc", "dram_mobile", "dram_gpu", "dram_legacy", "dram_unknown", "nand_raw"}


# ── gramatica POSICIONAL por marca ────────────────────────────────────────────
# Cada funcao recebe o PN normalizado e devolve (largura, empilhado) ou (None, False).
# Marca sem gramatica publica (Micron = codigo FBGA a laser) devolve None sempre:
# ali a largura so pode vir do banco ou do datasheet, nunca do PN.
def _samsung(pn):
    """Campo 5 do PN Samsung ("Bit Organization"), em pn[5:7].

    Legenda OFICIAL COMPLETA — Samsung, "Component DRAM Ordering Information".
    ⚠ COMPLETADA em 2026-09-20: esta tabela tinha 6 dos 12 codigos. Os que
    faltavam (02, 15, 26, 27, 30, 31) nao afetaram nenhum PN do catalogo
    (medido: os 268 Samsung DDR usam so 04/08/16), mas um PN novo com codigo
    15 ou 31 voltava "nao identificado" sem ninguem saber por que.

        02 = x2   ⚠ FORA do BUS_WIDTH_VOCAB (x4..x64) — decodifica mas nao grava
        04 = x4                08 = x8                16 = x16       32 = x32
        06 = x4 stack (Flexframe)      07 = x8 stack (Flexframe)
        26 = x4 stack (JEDEC)          27 = x8 stack (JEDEC)
        15 = x16 (2CS)   30 = x32 (2CS,2CKE)   31 = x32 (2CS)

    O 2o valor da tupla e "nao e largura simples de die": empilhados e 2CS
    descrevem o PACOTE, e o x2 esta fora do vocabulario. Quem chama trata
    todos eles como decisao humana, nunca grava direto.

    ⚠ '46' NAO e x4 — e bancos+interface do DDR3, identico em x4/x8/x16
    (HANDOFF §4 Etapa 1). Nao entra na tabela de proposito."""
    tab = {"04": ("x4", False), "08": ("x8", False), "16": ("x16", False),
           "32": ("x32", False),
           "02": ("x2", True),                       # fora do vocabulario
           "06": ("x4", True), "07": ("x8", True),   # stack Flexframe
           "26": ("x4", True), "27": ("x8", True),   # stack JEDEC
           "15": ("x16", True),                      # 2CS
           "30": ("x32", True), "31": ("x32", True)} # 2CS
    return tab.get(pn[5:7], (None, False)) if len(pn) >= 7 else (None, False)

def _micron(pn):
    """Micron soletra a organizacao no PN: <profundidade><G|M><largura>.
    MT41K256M16 = 256M x16 · MT40A1G8 = 1G x8 · MT62F768M64 = 768M x64.

    ⚠ NAO confundir com o codigo FBGA de 5 caracteres gravado a laser (D9MNZ),
    que e o que o OPERADOR le no chip e esse sim nao decodifica — e por isso
    que o HANDOFF diz "Micron nao decodifica". O part number COMPLETO decodifica
    (PLANO_BUS_WIDTH §3.2), e e ele que esta no catalogo.

    Como toda regra posicional, so e usada depois de corroborada pelo banco: a
    Micron tem ~2.786 larguras la, entao se este regex estiver errado as
    divergencias aparecem em massa e a familia e excluida sozinha."""
    m = re.match(r"MT\d+[A-Z]+(\d+)([GM])(\d{1,2})", pn)
    if not m:
        return (None, False)
    larg = int(m.group(3))
    return (f"x{larg}", False) if larg in (4, 8, 16, 32, 64) else (None, False)


GRAMATICA = {"samsung": _samsung, "micron": _micron}


def largura_do_banco(kp):
    m = RX_LARGURA.match(kp.interface or "")
    return m.group(1).lower() if m else None


def carregar_evidencia():
    p = RAIZ / "EVIDENCIA_largura.csv"
    if not p.exists():
        print("⚠ EVIDENCIA_largura.csv nao existe — seguindo so com banco + regra")
        return []
    with p.open(encoding="utf-8-sig") as f:
        linhas = [r for r in csv.DictReader(f) if (r.get("PN_PREFIXO") or "").strip()]
    # prefixo mais LONGO primeiro: casa o mais especifico
    return sorted(linhas, key=lambda r: -len(r["PN_PREFIXO"]))


def main(marca):
    d = connection.settings_dict
    print(f"\n⚠  BANCO-ALVO → name={d.get('NAME')}  host={d.get('HOST') or 'localhost'}")
    print(f"   MARCA → {marca}   (LEITURA APENAS — nada sera gravado)\n")
    regra_de = GRAMATICA.get(marca)
    if regra_de is None:
        print(f"✗ sem gramatica declarada para '{marca}'. Marcas: {', '.join(GRAMATICA)}")
        return 2
    evid = carregar_evidencia()
    sid = transaction.savepoint()
    try:
        qs = (KnownPart.objects.select_related("brand", "family")
              .filter(brand__name__iexact=marca))
        total = qs.count()
        print(f"{total} PN(s) da marca no banco.")
        if total == 0:
            print("✗ ZERO — leitura que nao aconteceu (marca errada? banco vazio?). Abortando.")
            return 1

        regs = []
        for kp in qs.iterator(chunk_size=2000):
            spec = spec_for(kp.chip_type or "")
            classe = spec.category if spec else ""
            pn = (kp.part_number or "").upper()
            fam = kp.family.prefix if kp.family_id else (pn[:3] or "?")
            banco = largura_do_banco(kp)
            ev = next((e for e in evid if pn.startswith(e["PN_PREFIXO"].upper())), None)
            # regra SO em classe de DRAM/NAND discreta (LPDDR decodifica "por acaso")
            regra, empilhado = regra_de(pn) if classe in CLASSES_OK else (None, False)
            regs.append(dict(kp=kp, pn=pn, fam=fam, classe=classe, banco=banco,
                             ev=ev, regra=regra, empilhado=empilhado))

        # ── corroboracao por familia: regra × (banco ou evidencia) ────────────
        diag = collections.defaultdict(lambda: dict(ok=0, div=0, so_regra=0,
                                                    larg=set(), casos=[]))
        for r in regs:
            if not r["regra"]:
                continue
            indep = r["banco"] or (r["ev"]["LARGURA"].lower() if r["ev"] else None)
            dg = diag[r["fam"]]
            if indep is None:
                dg["so_regra"] += 1
            elif indep == r["regra"]:
                dg["ok"] += 1; dg["larg"].add(r["regra"])
            else:
                dg["div"] += 1
                dg["casos"].append(f"{r['pn']}: regra={r['regra']} · indep={indep}")
        provada = {f for f, c in diag.items()
                   if c["ok"] >= MIN_PROVAS and c["div"] == 0 and len(c["larg"]) >= MIN_LARGURAS}

        print("\n── CORROBORACAO POR FAMILIA ─────────────────────────────────────")
        print(f"{'fam':7}{'ok':>5}{'diverg':>8}{'so regra':>10}  larguras           veredito")
        for f in sorted(diag):
            c = diag[f]
            v = ("CORROBORADA" if f in provada else
                 "QUEBRA — excluida" if c["div"] else "sem prova suficiente")
            print(f"{f:7}{c['ok']:5}{c['div']:8}{c['so_regra']:10}  "
                  f"{','.join(sorted(c['larg'])) or '—':18} {v}")
            for caso in c["casos"]:
                print(f"       ⚠ {caso}")

        # ── monta o CSV ───────────────────────────────────────────────────────
        linhas, cnt = [], collections.Counter()
        for r in regs:
            if r["classe"] not in CLASSES_OK:
                larg, prova, fonte, org, obs = "", "fora do alvo", "", "", \
                    f"classe '{r['classe'] or '(sem tipo)'}' — largura nao se aplica"
            elif r["banco"]:
                larg, prova, fonte, org = r["banco"], "banco", r["kp"].source_url or "", ""
                obs = f"campo interface do KnownPart = {r['kp'].interface!r}"
            elif r["ev"]:
                larg, prova = r["ev"]["LARGURA"].lower(), r["ev"]["NIVEL"]
                fonte, org, obs = r["ev"]["FONTE"], r["ev"]["ORGANIZACAO"], r["ev"]["CITACAO"]
            elif r["regra"] and r["fam"] in provada:
                c = diag[r["fam"]]
                larg, prova, fonte, org = r["regra"], "regra", "", ""
                obs = (f"regra posicional — familia {r['fam']} corroborada por {c['ok']} "
                       f"concordancia(s), 0 divergencias, larguras {','.join(sorted(c['larg']))}")
            else:
                larg, prova, fonte, org = "", "NAO IDENTIFICADO", "", ""
                obs = (f"familia {r['fam']} sem corroboracao suficiente "
                       f"(precisa de {MIN_PROVAS} concordancias e {MIN_LARGURAS} larguras)"
                       + (f"; a regra sugere {r['regra']}" if r["regra"] else ""))
            cnt[prova] += 1
            linhas.append({"PART NUMBER": r["kp"].part_number, "FAMILIA": r["fam"],
                           "TIPO": r["kp"].chip_type or "", "CLASSE": r["classe"],
                           "LARGURA": larg, "ORGANIZACAO": org, "PROVA": prova,
                           "EMPILHADO": "sim" if r["empilhado"] else "",
                           "CAPACIDADE": r["kp"].capacity or "",
                           "CONFIDENCE": r["kp"].confidence,
                           "REVIEW": r["kp"].review_status, "FONTE": fonte, "OBS": obs})

        linhas.sort(key=lambda l: (l["CLASSE"] == "", l["FAMILIA"], l["PART NUMBER"]))
        saida = RAIZ / f"LARGURA_IDENTIFICADA_{marca}.csv"
        with saida.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
            w.writeheader(); w.writerows(linhas)

        print("\n── RESULTADO ────────────────────────────────────────────────────")
        for k in ("banco", "datasheet-fabricante", "octopart", "regra",
                  "NAO IDENTIFICADO", "fora do alvo"):
            if cnt[k]:
                print(f"  {k:22} {cnt[k]:5}")
        alvo = [l for l in linhas if l["PROVA"] != "fora do alvo"]
        ident = [l for l in alvo if l["LARGURA"]]
        print(f"\n  no alvo: {len(alvo)}   IDENTIFICADOS: {len(ident)}   "
              f"faltam: {len(alvo) - len(ident)}")
        print("  por largura:", dict(sorted(collections.Counter(
            l["LARGURA"] for l in ident).items())))
        print(f"\n📄 {saida.name}")
        return 0
    finally:
        transaction.savepoint_rollback(sid)


if __name__ == "__main__":
    sys.exit(main((sys.argv[1] if len(sys.argv) > 1 else "samsung").lower()))
