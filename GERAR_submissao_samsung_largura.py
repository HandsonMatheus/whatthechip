"""
GERAR_submissao_samsung_largura.py — a largura da Samsung DDR pelo DECODIFICADOR
OFICIAL do fabricante (campo 5 do part number: "Bit Organization").

READ-ONLY NO BANCO. So LE o catalogo e ESCREVE um arquivo .yaml de submissao.
Quem grava no banco e o `submit_known_parts --fill-empty --commit`, depois do
dry-run, rodado pelo dono.

    env -u DATABASE_URL python GERAR_submissao_samsung_largura.py
    env -u DATABASE_URL python GERAR_submissao_samsung_largura.py --out submissions/xxx.yaml

POR QUE ISTO NAO E "GRAMATICA"
------------------------------
O dono travou em 2026-09-20: *"a gramatica so e util na hora de saber rapido info
sobre um PN novo na bancada, nao deve ser usada como regua para nada... nossa
fonte de verdade sao fontes Tier-1 daquela marca"*. Este script NAO le a gramatica
do nosso yaml. Ele aplica o DECODIFICADOR PUBLICADO PELA SAMSUNG — "Component DRAM
Ordering Information", campo 5 = Bit Organization — e cada um dos tres codigos em
uso tem ancora em datasheet do dominio da Samsung (ver ANCORA abaixo). E a mesma
natureza de prova de um datasheet: documento do fabricante.

A DIFERENCA PRATICA: o decodificador cobre a familia inteira; o datasheet cobre um
PN. Por isso cada registro sai citando OS DOIS — a legenda que explica o codigo e o
datasheet Samsung que prova aquele codigo especifico.

⚠ CIRCULARIDADE (HANDOFF §3). Depois desta submissao, quase toda largura Samsung
DDR no catalogo tera vindo do decodificador. Entao o `COLETAR_largura_bits.py`
NAO PODE mais usar o catalogo Samsung DDR como prova independente da regra
posicional — validaria a regra contra ela mesma. Mas tambem NAO PRECISA: a regra
ja esta provada por documento do fabricante. Na F6, as familias Samsung DDR
entram na lista de "regra provada por documento" e o coletor as pula.
"""
import argparse
import collections
import datetime
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db import connection            # noqa: E402
from chips.models import KnownPart          # noqa: E402

#: Campo 5 do part number Samsung ("Bit Organization"), legenda OFICIAL completa.
#: 12 codigos — a nossa tabela em IDENTIFICAR_largura.py tinha 6 (ver F6).
LEGENDA_OFICIAL = {
    "02": "x2", "04": "x4", "06": "x4 Stack (Flexframe)",
    "07": "x8 Stack (Flexframe)", "08": "x8", "15": "x16 (2CS)", "16": "x16",
    "26": "x4 Stack (JEDEC Standard)", "27": "x8 Stack (JEDEC Standard)",
    "30": "x32 (2CS, 2CKE)", "31": "x32 (2CS)", "32": "x32",
}
#: So estes viram `bus_width`: largura simples, dentro do BUS_WIDTH_VOCAB. Os
#: empilhados e os "2CS" descrevem o PACOTE, nao a largura do die — vao para o
#: relatorio e ficam para decisao humana.
SIMPLES = {"04": "x4", "08": "x8", "16": "x16", "32": "x32"}

#: Datasheet do DOMINIO DA SAMSUNG que prova cada codigo (do EVIDENCIA_largura.csv,
#: reconferido em 2026-09-20).
ANCORA = {
    "x4":  ('K4A4G045WD → "1Gx4(K4A4G045WD-BC##)"',
            "https://download.semiconductor.samsung.com/resources/data-sheet/"
            "DDR4_4Gb_D_die_Registered_DIMM_Rev1_8_Aug_16-0.pdf"),
    "x8":  ('K4A8G085WC → "1Gx8(K4A8G085WC-BC##)"',
            "https://download.semiconductor.samsung.com/resources/data-sheet/"
            "DDR4_8Gb_C_die_Unbuffered_DIMM_Rev1.4_Apr.18.pdf"),
    "x16": ('K4A8G165WC → "512Mx16(K4A8G165WC-BC##)"',
            "https://download.semiconductor.samsung.com/resources/data-sheet/"
            "DDR4_8Gb_C_die_Unbuffered_DIMM_Rev1.4_Apr.18.pdf"),
    "x32": ('sem ancora Samsung propria — NAO EMITIDO, ver relatorio', ""),
}

#: Tipos do balde COMERCIAL (dono, 2026-09-20). LPDDR nao interessa; GDDR esta
#: fora do negocio desde 2026-07-23; RDRAM (K4Y) usa OUTRO esquema de PN e nao
#: pode passar por este decodificador.
def e_ddr_comercial(ct: str) -> bool:
    t = (ct or "").strip().upper()
    if not t or t.startswith("LPDDR") or t.startswith("GDDR") or t == "RDRAM":
        return False
    return t.startswith("DDR") or t == "SDRAM"


def main(caminho):
    d = connection.settings_dict
    print(f"\n⚠  BANCO-ALVO (somente leitura) → name={d.get('NAME')}  "
          f"host={d.get('HOST') or 'localhost'}\n")

    emitir, relatorio = [], collections.defaultdict(list)
    for kp in (KnownPart.objects.filter(brand__name__iexact="Samsung")
               .exclude(review_status="rejected")
               .select_related("brand").order_by("part_number").iterator(chunk_size=1000)):
        pn = (kp.part_number or "").strip()
        if not e_ddr_comercial(kp.chip_type):
            continue
        if (kp.bus_width or "").strip():
            relatorio["JA TEM LARGURA (nada a fazer)"].append(pn)
            continue
        if not pn.upper().startswith("K4") or len(pn) < 7:
            relatorio["PN fora do esquema K4 — decodificador nao se aplica"].append(pn)
            continue
        cod = pn[5:7]
        if cod not in LEGENDA_OFICIAL:
            relatorio[f"codigo {cod!r} FORA da legenda oficial Samsung"].append(pn)
            continue
        if cod not in SIMPLES:
            relatorio[f"codigo {cod!r} = {LEGENDA_OFICIAL[cod]} (empilhado/2CS — "
                      "decisao humana)"].append(pn)
            continue
        larg = SIMPLES[cod]
        if not ANCORA[larg][1]:
            relatorio[f"{larg}: sem ancora Samsung propria — nao emitido"].append(pn)
            continue
        emitir.append((kp, cod, larg))

    for motivo in sorted(relatorio):
        print(f"  [{len(relatorio[motivo]):4d}] {motivo}")
        if "JA TEM" not in motivo:
            for pn in relatorio[motivo][:15]:
                print(f"           {pn}")
    por_larg = collections.Counter(l for _k, _c, l in emitir)
    por_tipo = collections.Counter(k.chip_type for k, _c, _l in emitir)
    print(f"\n  A EMITIR: {len(emitir)} KnownPart")
    print(f"    por largura: {dict(por_larg.most_common())}")
    print(f"    por tipo:    {dict(por_tipo.most_common())}")
    if not emitir:
        print("\n  Nada a emitir — arquivo nao escrito.\n")
        return

    hoje = datetime.date.today().isoformat()
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(f"""# {caminho}
#
# Largura de barramento da DRAM Samsung, pelo DECODIFICADOR OFICIAL DO FABRICANTE.
# Gerado por GERAR_submissao_samsung_largura.py em {hoje}. Nada foi gravado no banco.
#
# FONTE DA REGRA — Samsung, "Component DRAM Ordering Information": o part number
# tem 11 campos e o CAMPO 5 e "Bit Organization". Legenda oficial completa:
#   02: x2 · 04: x4 · 06: x4 Stack (Flexframe) · 07: x8 Stack (Flexframe) ·
#   08: x8 · 15: x16 (2CS) · 16: x16 · 26: x4 Stack (JEDEC) · 27: x8 Stack (JEDEC) ·
#   30: x32 (2CS, 2CKE) · 31: x32 (2CS) · 32: x32
# Em K4B2G0846D: K(1) 4(2) B(3) 2G(4) 08(5) -> x8.
#
# FONTE DE CADA CODIGO — datasheet do dominio da Samsung, um por codigo em uso:
#   04 -> {ANCORA['x4'][0]}
#         {ANCORA['x4'][1]}
#   08 -> {ANCORA['x8'][0]}
#         {ANCORA['x8'][1]}
#   16 -> {ANCORA['x16'][0]}
#         {ANCORA['x16'][1]}
#
# ESCOPO: so DRAM comercial (DDR/DDR2/DDR3/DDR3L/DDR4/DDR5/SDRAM). LPDDR fora
# (o dono nao diferencia largura nela), GDDR fora (fora do negocio), RDRAM fora
# (K4Y usa outro esquema de PN). So os codigos de largura SIMPLES entram —
# empilhados e "2CS" descrevem o pacote e ficaram no relatorio.
#
# COMO APLICAR (o dono roda; os registros ja sao 'approved', entao isto e
# COMPLEMENTO — preenche campo vazio, nunca sobrescreve, nunca muda status):
#   python manage.py submit_known_parts {caminho}
#   python manage.py submit_known_parts {caminho} --fill-empty --commit
#
# ⚠ Depois disto, o COLETAR_largura_bits.py NAO pode usar o catalogo Samsung DDR
#   como prova independente da regra posicional (circularidade, HANDOFF §3) — e
#   nao precisa: a regra esta provada por documento do fabricante.

brand: Samsung

known_parts:
""")
        for kp, cod, larg in emitir:
            cit, url = ANCORA[larg]
            f.write(f'  - part_number: "{kp.part_number}"\n')
            f.write(f'    bus_width: "{larg}"\n')
            f.write(f'    confidence: "confirmed"\n')
            f.write(f'    notes: >\n')
            f.write(f'      Largura {larg} lida do campo 5 ("Bit Organization") do part number,\n')
            f.write(f'      codigo "{cod}", pelo decodificador oficial Samsung "Component DRAM\n')
            f.write(f'      Ordering Information". Codigo "{cod}" confirmado em datasheet Samsung:\n')
            f.write(f'      {cit}. Capacidade e demais campos intactos.\n')
            # ⚠ SEM `source_url` (2026-09-20). A tentacao era gravar aqui o
            # datasheet que ancora o CODIGO — mas os 168 PNs atravessam 13
            # familias e 5 geracoes (K4H DDR1 … K4RA DDR5), e as tres ancoras
            # sao todas DDR4. Pendurar um datasheet de DDR4 4Gb RDIMM como
            # "fonte" de um DDR5 e pior que nao ter fonte: parece verificacao e
            # nao e. A fonte real e o DECODIFICADOR, que vale para os 168 — e
            # ele mora no cabecalho DESTE arquivo, que vai versionado no git.
            # (Se o dono preferir uma URL no banco, e so descomentar com a do
            #  decodificador; nunca com a do datasheet de outro PN.)
            f.write("\n")

    print(f"\n  ✅ escrito: {caminho}")
    print(f"     dry-run:  python manage.py submit_known_parts {caminho}")
    print(f"     aplicar:  python manage.py submit_known_parts {caminho} --fill-empty --commit")
    print("\nNADA FOI ESCRITO NO BANCO.\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="submissions/samsung_largura_decodificador_"
                   + datetime.date.today().isoformat() + ".yaml")
    main(p.parse_args().out)
