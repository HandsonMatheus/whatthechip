# -*- coding: utf-8 -*-
"""
COLETAR_largura_bits.py — READ-ONLY. Levanta a LARGURA DE BARRAMENTO (x4/x8/x16)
dos PNs de uma marca, direto do SEU banco, e monta a planilha só com o que tem
prova.

    python COLETAR_largura_bits.py                    # Samsung (padrão)
    python COLETAR_largura_bits.py --marca micron     # a próxima marca
    python COLETAR_largura_bits.py --tudo             # mostra também o descartado

═══ A REGRA (verificada em fonte primária, não deduzida) ═══════════════════════
Nas famílias DISCRETAS de DRAM da Samsung o PN é posicional:

        K4B  2G  08  46  D
        │    │   │   │   └─ revisão de die
        │    │   │   └───── bancos + interface (DDR3: sempre '46')
        │    │   └───────── ORGANIZAÇÃO  ← pn[5:7], é isto que queremos
        │    └───────────── densidade (2 chars)  ← pn[3:5]
        └────────────────── família (K4B = DDR3)

Tabela de organização — campo 5 do PN ("Bit Organization"), do decodificador
OFICIAL da Samsung ("Component DRAM Ordering Information"). Reconferida em
2026-09-20 e COMPLETADA: a versão anterior deste arquivo tinha 6 dos 12 códigos.

        02 = x2                 04 = x4                 08 = x8
        16 = x16                32 = x32
        06 = x4 (stack Flexframe)      07 = x8 (stack Flexframe)
        26 = x4 (stack JEDEC)          27 = x8 (stack JEDEC)
        15 = x16 (2CS)                 30 = x32 (2CS,2CKE)     31 = x32 (2CS)

Os empilhados e os "2CS" descrevem o PACOTE, não a largura do die: vão para
REVISAR, nunca para o OURO. O 02 (x2) está fora do BUS_WIDTH_VOCAB do sistema
(x4…x64) — decodifica, mas não pode ser gravado; também vai para REVISAR.

A densidade ocupar SEMPRE 2 chars é o que mantém o deslocamento fixo — vale para
os códigos numéricos (28/51/56/64) e para os alfanuméricos (1G/2G/4G/8G/AG/AH/
BH/CH), todos já no DRAM_PC de chips/knowledge/samsung.yaml.

⚠ CORREÇÃO DO SAMSUNG.md (linha 109): lá está escrito "04/46 = x4". O '46' NÃO é
  largura — é bancos+interface do DDR3, e é IGUAL em x4, x8 e x16. Se algum
  caminho de código cair nesse ramo, ele carimba x4 em tudo. O '46' não entra
  aqui.

═══ POR QUE ESTE SCRIPT NÃO CONFIA NA REGRA SOZINHO ════════════════════════════
Uma regra posicional certa na família errada produz lixo com cara de dado. No
K4N ela erra: K4N51163QC dá 'x16' pela posição e o banco (fonte Tier-1) diz x32.

Então NENHUMA família entra por decreto. Uma família só é PROVADA se, no SEU
banco, ela tiver:
   · >= MIN_PROVAS PNs em que o campo `bus_width` — preenchido a partir da
     página oficial/datasheet, não do PN — CONCORDA com a regra;
   · ZERO divergências;
   · acordo em >= 2 larguras DISTINTAS (senão a regra nunca foi testada no
     ponto em que ela precisa discriminar).
Família nova que apareça amanhã se prova sozinha, sem eu editar lista nenhuma.

E o PN, individualmente, ainda precisa: review_status 'approved' e confidence
diferente de 'estimated' — um PN "estimado" pode nem existir no mundo real, e a
largura de um PN inventado é ficção decodificada com precisão.

⚠ CIRCULARIDADE (2026-09-20) — a razão do EXCLUIR_DECODIFICADOR abaixo.
Desde a submissão `samsung_largura_decodificador_*.yaml`, 168 KnownPart Samsung
têm `bus_width` vindo DESTA MESMA regra posicional. Contá-los como "acordo
independente" seria validar a regra contra ela mesma — o erro que o HANDOFF §3
chama de circularidade, e o mais difícil de enxergar porque o número fica
lindo. Este script LÊ os arquivos de submissão do decodificador e EXCLUI
aqueles PNs da contagem de prova. Sobram os que vieram do importador/datasheet,
que são prova de verdade.

Não escreve nada. Roda em transação revertida.
"""
import argparse
import csv
import os
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django                                                    # noqa: E402
django.setup()

from django.db import connection, transaction                    # noqa: E402

# ── a tabela oficial ────────────────────────────────────────────────────────
ORG = {'02': 'x2 (fora do vocabulário)',
       '04': 'x4', '08': 'x8', '16': 'x16', '32': 'x32',
       '06': 'x4 (stack Flexframe)', '07': 'x8 (stack Flexframe)',
       '26': 'x4 (stack JEDEC)', '27': 'x8 (stack JEDEC)',
       '15': 'x16 (2CS)', '30': 'x32 (2CS,2CKE)', '31': 'x32 (2CS)'}
#: Códigos que NÃO viram largura de die — pacote (stack/2CS) ou fora do
#: vocabulário. Vão para REVISAR com motivo próprio, nunca para o OURO.
NAO_E_LARGURA_SIMPLES = {'02', '06', '07', '15', '26', '27', '30', '31'}
#: Submissões cuja largura veio DO DECODIFICADOR (não de fonte independente).
#: Os PNs listados nelas não contam como prova — ver CIRCULARIDADE no topo.
EXCLUIR_DECODIFICADOR = 'submissions/*largura_decodificador*.yaml'
ALVO = {'x4', 'x8'}                   # o que ele quer na planilha
MIN_PROVAS = 5                        # acordos independentes para promover família
MIN_LARGURAS = 2                      # larguras distintas entre os acordos


def normalizar(pn: str) -> str:
    pn = unicodedata.normalize('NFKC', pn or '').upper()
    return ''.join(c for c in pn if c.isalnum())


def largura_pela_regra(pn_norm: str):
    """Devolve (prefixo, largura) ou (prefixo, None) se a posição não decodifica."""
    if len(pn_norm) < 7:
        return pn_norm[:3], None
    return pn_norm[:3], ORG.get(pn_norm[5:7])


def e_dram_discreta(chip_type: str) -> bool:
    """A regra posicional vale para DRAM DISCRETA (DDR/SDRAM/GDDR). NÃO vale para
    LPDDR, eMMC, eMCP, uMCP, UFS e NAND — lá o PN usa mapa de capacidade
    (K4E_CAP, LPDDR4_CAP…), e pn[5:7] cai no meio do código de capacidade,
    devolvendo um valor que PARECE largura e não é.

    ⚠ Achado em 2026-09-12, olhando a saída real: K4E4E164EB (LPDDR3) decodifica
      como 'x16' porque calha de ter '16' na posição. A trava de família impedia
      esse lixo de entrar no OURO — mas ele caía em REVISAR com o motivo ERRADO
      ("família sem prova"), o que mandaria alguém caçar datasheet de LPDDR3
      para promover uma família que nunca vai poder ser promovida por esta regra.
      Motivo errado custa trabalho humano, mesmo sem sujar o resultado.

    O teste sai do chip_type do banco, não de uma lista minha de prefixos: marca
    nova entra certa sozinha. chip_type vazio não reprova — aí só a família decide.
    """
    t = (chip_type or '').strip().upper()
    if not t:
        return True                      # não sei: deixo a trava de família decidir
    if t.startswith('LPDDR'):
        return False                     # antes do DDR — 'LPDDR3' começa com 'L'
    return t.startswith(('DDR', 'SDRAM', 'GDDR'))


def largura_do_banco(bus_width: str):
    """O que o banco já sabe — do campo `bus_width` (2026-09-20).

    ⚠ ANTES lia `interface`, e com razão: era lá que a largura morava. Depois do
    backfill da Fase 3 (PLANO_BUS_WIDTH.md) `interface` é só protocolo, e ler
    dali devolveria None para TODOS — o script continuaria rodando e diria que
    nenhuma família tem prova. Falha silenciosa, não erro. NÃO caia no
    "tenta bus_width, senão interface": seria reabrir a porta que a Fase 5 fecha.
    """
    t = (bus_width or '').strip().lower()
    return t if t in {'x4', 'x8', 'x16', 'x32', 'x64'} else None


def pns_do_decodificador():
    """PNs cuja largura veio do DECODIFICADOR — não contam como prova.

    Devolve ``(set de PNs normalizados, lista de arquivos lidos)``. Lê as
    submissões em vez de um campo do banco porque o `--fill-empty` só preenche
    campo VAZIO: `notes` e `source_url` dos 168 já estavam ocupados, então não
    há marca no registro. O arquivo de submissão É o registro de proveniência,
    e ele vai versionado no git.
    """
    import glob
    import re
    achados, arquivos = set(), sorted(glob.glob(EXCLUIR_DECODIFICADOR))
    rx = re.compile(r'^\s*-\s*part_number:\s*"?([^"\n]+?)"?\s*$')
    for caminho in arquivos:
        with open(caminho, encoding='utf-8') as f:
            for linha in f:
                m = rx.match(linha)
                if m:
                    achados.add(normalizar(m.group(1)))
    return achados, arquivos


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--marca', default='samsung', help='nome da marca (default: samsung)')
    ap.add_argument('--forcar-regra-samsung', action='store_true', dest='forcar',
                    help='aplica a gramática SAMSUNG a outra marca (quase sempre errado)')
    ap.add_argument('--tudo', action='store_true',
                    help='imprime também o que ficou de fora e por quê')
    ap.add_argument('--saida', default='', help='caminho do .xlsx (default: LARGURA_<marca>.xlsx)')
    args = ap.parse_args()

    from chips.models import KnownPart

    # ⚠ A REGRA POSICIONAL DESTE SCRIPT É A GRAMÁTICA DA SAMSUNG. Micron, Nanya,
    #   Hynix e Winbond numeram de outro jeito — pn[5:7] lá não é organização.
    #   A trava de promoção por família filtraria a maior parte do lixo, mas
    #   "quase sempre filtra" não é a barra: uma família que por acaso junte 5
    #   coincidências e 2 larguras entraria no OURO com cara de dado provado.
    #   Cada marca nova precisa da SUA gramática pesquisada antes. Por isso a
    #   recusa é explícita e não um aviso que se ignora rolando a tela.
    if args.marca.strip().lower() != 'samsung' and not args.forcar:
        print(f"✗ A regra deste script é a gramática da SAMSUNG (pn[5:7]).\n"
              f"  Para {args.marca!r} ela não vale — o resultado seria lixo com cara\n"
              f"  de dado. Pesquise a gramática da marca primeiro e me peça a versão\n"
              f"  dela. Se você sabe o que está fazendo: --forcar-regra-samsung")
        return 2

    d = connection.settings_dict
    print(f"\n⚠  BANCO-ALVO → name={d.get('NAME')}  host={d.get('HOST') or 'localhost'}")
    print(f"   MARCA → {args.marca}"
          + ("   ⚠ GRAMÁTICA SAMSUNG FORÇADA — confira cada linha do OURO"
             if args.forcar else "") + "\n")

    sid = transaction.savepoint()
    try:
        with transaction.atomic():
            qs = (KnownPart.objects
                  .filter(brand__name__iexact=args.marca)
                  .only('part_number', 'part_number_norm', 'chip_type', 'subtype',
                        'capacity', 'density_gbit', 'bus_width', 'confidence',
                        'review_status', 'source_url', 'notes'))
            partes = list(qs)
            if not partes:
                print(f"✗ ZERO PNs da marca {args.marca!r}. Isto não é 'não tem' —\n"
                      "  é leitura que não aconteceu, marca escrita diferente, ou banco\n"
                      "  vazio. Confira com: KnownPart.objects.values_list('brand__name',\n"
                      "  flat=True).distinct()")
                return 1
            print(f"{len(partes)} PN(s) da marca no banco.")
            excluidos, arqs = pns_do_decodificador()
            if arqs:
                print(f"  ⚠ {len(excluidos)} PN(s) com largura vinda do DECODIFICADOR "
                      f"({', '.join(a.split('/')[-1] for a in arqs)})")
                print(f"     não contam como prova — circularidade (HANDOFF §3).")

            # ── 1. decodifica e cruza, acumulando evidência POR FAMÍLIA ──────
            evid = defaultdict(lambda: {'ok': 0, 'div': 0, 'sem': 0,
                                        'larguras': set(), 'casos': []})
            linhas = []
            for kp in partes:
                pn_n = kp.part_number_norm or normalizar(kp.part_number)
                pref, regra = largura_pela_regra(pn_n)
                banco = largura_do_banco(kp.bus_width)
                # A largura que o decodificador escreveu NÃO é prova independente.
                if pn_n in excluidos:
                    banco = None
                if not e_dram_discreta(kp.chip_type):
                    regra = None         # a posição não significa largura aqui
                e = evid[pref]
                if regra is None:
                    situacao = 'regra não decodifica'
                elif banco is None:
                    e['sem'] += 1
                    situacao = 'só a regra'
                elif banco == regra.split()[0]:
                    e['ok'] += 1
                    e['larguras'].add(banco)
                    situacao = 'regra + banco (acordo)'
                else:
                    e['div'] += 1
                    e['casos'].append((kp.part_number, regra, banco))
                    situacao = 'DIVERGE'
                linhas.append({
                    'pn': kp.part_number, 'pn_norm': pn_n, 'familia': pref,
                    'regra': regra or '', 'banco': banco or '', 'situacao': situacao,
                    'tipo': kp.chip_type, 'subtype': kp.subtype,
                    'capacidade': kp.capacity, 'densidade': kp.density_gbit,
                    'confidence': kp.confidence, 'review': kp.review_status,
                    'fonte': kp.source_url,
                })

            # ── 2. promove família só com prova ─────────────────────────────
            provadas = {}
            for pref, e in evid.items():
                provadas[pref] = (e['ok'] >= MIN_PROVAS and e['div'] == 0
                                  and len(e['larguras']) >= MIN_LARGURAS)

            print("\n── EVIDÊNCIA POR FAMÍLIA " + "─" * 50)
            print(f"{'fam':<6}{'acordo':>7}{'diverg':>8}{'só regra':>10}"
                  f"  {'larguras provadas':<22}veredito")
            print("─" * 74)
            for pref in sorted(evid):
                e = evid[pref]
                if not (e['ok'] or e['div'] or e['sem']):
                    continue
                v = 'PROVADA' if provadas[pref] else (
                    'QUEBRA — excluída' if e['div'] else 'sem prova suficiente')
                print(f"{pref:<6}{e['ok']:>7}{e['div']:>8}{e['sem']:>10}"
                      f"  {','.join(sorted(e['larguras'])) or '—':<22}{v}")
                for c in e['casos'][:3]:
                    print(f"       ⚠ {c[0]}: regra={c[1]} · banco={c[2]}")

            # ── 3. classifica cada PN ───────────────────────────────────────
            ouro, revisar, fora = [], [], []
            for L in linhas:
                base = (L['regra'] or '').split()[0] if L['regra'] else ''
                cod = L['pn_norm'][5:7] if len(L['pn_norm']) >= 7 else ''
                stack = cod in NAO_E_LARGURA_SIMPLES
                if not L['regra']:
                    L['motivo'] = (f"{L['tipo'] or 'tipo não informado'} — outra gramática "
                                   "(LPDDR/eMMC/eMCP/UFS/NAND usam mapa de capacidade, "
                                   "não posição) ou PN curto demais"
                                   if not e_dram_discreta(L['tipo'])
                                   else 'posição não decodifica — PN curto ou fora do padrão')
                    fora.append(L)
                elif L['situacao'] == 'DIVERGE':
                    L['motivo'] = f"regra diz {L['regra']}, banco diz {L['banco']}"
                    revisar.append(L)
                elif not provadas[L['familia']]:
                    e = evid[L['familia']]
                    L['motivo'] = (f"família {L['familia']} sem prova no seu banco "
                                   f"({e['ok']} acordo(s), {len(e['larguras'])} largura(s))")
                    revisar.append(L)
                elif base not in ALVO:
                    L['motivo'] = f'{base} — fora do alvo (a planilha é de 4 e 8 bits)'
                    fora.append(L)
                elif stack:
                    L['motivo'] = (f'código {cod} = {L["regra"]} — descreve o PACOTE, '
                                   'não a largura do die. Decisão sua.')
                    revisar.append(L)
                elif L['review'] != 'approved':
                    L['motivo'] = f"review_status={L['review']} (não aprovado)"
                    revisar.append(L)
                elif L['confidence'] == 'estimated':
                    L['motivo'] = 'confidence=estimated — o PN pode nem existir'
                    revisar.append(L)
                else:
                    e = evid[L['familia']]
                    L['prova'] = ('direta — interface de fonte Tier-1 no banco concorda'
                                  if L['banco'] else
                                  f"regra — família {L['familia']} provada por "
                                  f"{e['ok']} acordo(s) independente(s), 0 divergência")
                    L['largura'] = base
                    ouro.append(L)

            print(f"\n── RESULTADO " + "─" * 62)
            print(f"  OURO (4/8 bits, com prova) : {len(ouro)}")
            print(f"  REVISAR                    : {len(revisar)}")
            print(f"  FORA DO ALVO               : {len(fora)}")
            por_w = defaultdict(int)
            for L in ouro:
                por_w[L['largura']] += 1
            print(f"  no ouro → " + ' · '.join(f'{k}: {v}' for k, v in sorted(por_w.items()))
                  if por_w else "  no ouro → (vazio)")

            if args.tudo:
                print("\n── REVISAR (por quê) " + "─" * 54)
                for L in revisar[:80]:
                    print(f"   {L['pn']:<26} {L['motivo']}")
                if len(revisar) > 80:
                    print(f"   … e mais {len(revisar) - 80}")

            _gravar(args, ouro, revisar, fora, evid, provadas)
    finally:
        transaction.savepoint_rollback(sid)

    if not ouro:
        print("\n✗ Planilha de OURO vazia — nada passou na barra. Rode com --tudo\n"
              "  para ver o motivo de cada exclusão antes de concluir qualquer coisa.")
        return 1
    return 0


def _gravar(args, ouro, revisar, fora, evid, provadas):
    marca = args.marca.lower()
    base = args.saida or f'LARGURA_{marca}.xlsx'
    csv_path = Path(base).with_suffix('.csv')

    # CSV sempre — não depende de nada e é o que sobrevive a qualquer ambiente.
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        w.writerow(['PART NUMBER', 'LARGURA', 'FAMILIA', 'TIPO', 'SUBTYPE',
                    'CAPACIDADE', 'DENSIDADE', 'PROVA', 'CONFIDENCE', 'FONTE'])
        for L in ouro:
            w.writerow([L['pn'], L['largura'], L['familia'], L['tipo'], L['subtype'],
                        L['capacidade'], L['densidade'], L['prova'],
                        L['confidence'], L['fonte']])
    print(f"\n📄 {csv_path}")

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("   (openpyxl ausente — só o CSV. pip install openpyxl)")
        return

    wb = Workbook()
    cab = Font(name='Arial', bold=True, color='FFFFFF')
    fill = PatternFill('solid', fgColor='1F4E78')
    corpo = Font(name='Arial')

    def folha(ws, cols, dados, chaves):
        ws.append(cols)
        for c in range(1, len(cols) + 1):
            cel = ws.cell(row=1, column=c)
            cel.font, cel.fill = cab, fill
            cel.alignment = Alignment(vertical='center')
        for L in dados:
            ws.append([L.get(k, '') for k in chaves])
        for row in ws.iter_rows(min_row=2):
            for cel in row:
                cel.font = corpo
        for i, col in enumerate(cols, start=1):
            larg = max([len(str(col))] + [len(str(L.get(chaves[i - 1], ''))) for L in dados[:400]])
            ws.column_dimensions[get_column_letter(i)].width = min(max(larg + 2, 10), 62)
        ws.freeze_panes = 'A2'

    ws = wb.active
    ws.title = f'OURO 4-8 bits'
    folha(ws, ['PART NUMBER', 'LARGURA', 'FAMÍLIA', 'TIPO', 'SUBTYPE', 'CAPACIDADE',
               'DENSIDADE', 'PROVA', 'CONFIDENCE', 'FONTE'],
          ouro, ['pn', 'largura', 'familia', 'tipo', 'subtype', 'capacidade',
                 'densidade', 'prova', 'confidence', 'fonte'])

    folha(wb.create_sheet('REVISAR'),
          ['PART NUMBER', 'REGRA DIZ', 'BANCO DIZ', 'FAMÍLIA', 'MOTIVO DA EXCLUSÃO',
           'CONFIDENCE', 'REVIEW', 'FONTE'],
          revisar, ['pn', 'regra', 'banco', 'familia', 'motivo', 'confidence',
                    'review', 'fonte'])

    folha(wb.create_sheet('FORA DO ALVO'),
          ['PART NUMBER', 'REGRA DIZ', 'BANCO DIZ', 'FAMÍLIA', 'MOTIVO'],
          fora, ['pn', 'regra', 'banco', 'familia', 'motivo'])

    dg = wb.create_sheet('DIAGNÓSTICO')
    diag = []
    for pref in sorted(evid):
        e = evid[pref]
        if not (e['ok'] or e['div'] or e['sem']):
            continue
        diag.append({
            'familia': pref, 'acordo': e['ok'], 'diverg': e['div'], 'so_regra': e['sem'],
            'larguras': ', '.join(sorted(e['larguras'])) or '—',
            'veredito': ('PROVADA' if provadas[pref] else
                         'QUEBRA — excluída' if e['div'] else 'sem prova suficiente'),
            'casos': '; '.join(f'{p}: regra={r} banco={b}' for p, r, b in e['casos'][:5]),
        })
    folha(dg, ['FAMÍLIA', 'ACORDOS', 'DIVERGÊNCIAS', 'SÓ REGRA', 'LARGURAS PROVADAS',
               'VEREDITO', 'CASOS DE DIVERGÊNCIA'],
          diag, ['familia', 'acordo', 'diverg', 'so_regra', 'larguras', 'veredito', 'casos'])

    dg.append([])
    dg.append(['Barra para PROVADA:', f'>= {MIN_PROVAS} acordos independentes, '
               f'0 divergências, >= {MIN_LARGURAS} larguras distintas'])
    dg.append(['Regra:', 'pn[5:7] = campo 5 do PN (Bit Organization) — '
               '02=x2 04=x4 06/26=x4 stack 07/27=x8 stack 08=x8 15=x16(2CS) '
               '16=x16 30/31=x32(2CS) 32=x32'])
    dg.append(['Fonte da regra:', 'Samsung, "Component DRAM Ordering Information" '
               '(decodificador oficial do fabricante), campo 5'])
    dg.append(['Âncoras do fabricante:', 'K4A4G045WD="1Gx4" · K4A8G085WC="1Gx8" · '
               'K4A8G165WC="512Mx16" (datasheets do domínio Samsung)'])
    dg.append(['Acordo é independente:', 'o campo bus_width veio do importador/'
               'datasheet, NÃO de decodificar o PN — os PNs da submissão do '
               'decodificador são excluídos da contagem (circularidade)'])
    for row in dg.iter_rows(min_row=len(diag) + 2):
        for cel in row:
            cel.font = Font(name='Arial', italic=True)

    wb.save(base)
    print(f"📊 {base}   (abas: OURO · REVISAR · FORA DO ALVO · DIAGNÓSTICO)")


if __name__ == '__main__':
    sys.exit(main())
