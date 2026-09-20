"""
normalize_convention — migra chip_type/subtype para a forma CANONICA (convencao
opcao 1: geracao no chip_type). DRY-RUN por padrao. REVERSIVEL (grava JSON com os
valores antigos antes de aplicar).

    python manage.py normalize_convention                 # dry-run (mostra o diff)
    python manage.py normalize_convention --commit         # aplica + grava JSON reversivel
    python manage.py normalize_convention --revert <json>  # desfaz

O que faz (idempotente):
  - ChipFamily.chip_type/subtype  -> canonico (RAM/DDR generico -> geracao especifica)
  - KnownPart.chip_type/subtype   -> canonico
  - Desativa familias Kingston bogus (KF/KVR/ACR — Kingston nao fabrica DRAM avulsa)
  - Familias MULTI-GERACAO (ex.: K3 "LPDDR2/LPDDR3") -> token generico (flagged), NAO
    forca uma geracao (decisao do usuario).

NAO mexe em: confidence (preserva confirmed/manual), emcp_* e VALORES de spec.
Excecao unica (2026-07-11, bug lote 40): DENSIDADE NO LUGAR CERTO — KnownPart
DDR/GDDR/SDRAM/RDRAM com density_gbit vazio e capacity "pelada" em Gbit
('2G'/'2Gb', o que o bless_base gravava) ganha density_gbit='<n>Gb'. FILL-ONLY
(capacity fica; 'GB' nunca entra), mecanico e reversivel como o resto. E a
MESMA regra 4 do apply_kp_convention — este comando so a aplica ao legado.
Excecao 2 (2026-08-28): GERACAO NO LUGAR CERTO — KnownPart eMCP/uMCP cujo
`subtype` nao e token do vocabulario ganha a geracao vinda do proprio registro
(do subtype canonicalizavel, senao de dentro do `emcp_ram`). FILL-ONLY, deny by
default (`is_ram_generation`), so KnownPart (familia pode ser multi-geracao).
Sem isso, limpar o `emcp_ram` derruba 105 chips de RENTAVEL p/ INDETERMINADO.
Excecao 3 (2026-09-19): LARGURA NO LUGAR CERTO — KnownPart cuja `interface`
carrega LARGURA DE BARRAMENTO ('x16', 'x16 @ 800MHz') tem a largura movida para
o campo proprio `bus_width` e a velocidade para as `notes` ('Speed: ...'); a
`interface` volta a ser so PROTOCOLO (eMMC 5.1 / UFS 3.1). Sao 3.539 registros
medidos na Fase 0 do PLANO_BUS_WIDTH.md. FILL-ONLY em `bus_width`; a `interface`
SO e esvaziada quando tudo que havia nela teve destino (invariante I5 — mover
nunca apaga); `notes` so cresce. NAO toca em ChipFamily: a largura de familia
vem do yaml (Fase 4) e o proximo `load_brands` desfaria. Tres motivos de NAO
migrar, todos reportados com a lista COMPLETA de PNs: SOBRA SEM DESTINO
('x16 (2 dies)'), CONTRADICAO (ja tem outra largura em `bus_width`) e CLASSE NAO
PERMITE (eMMC/eMCP, onde largura de dados nao identifica o dispositivo).
Comportamento (label/rentabilidade) NAO muda — so o chip_type/subtype ARMAZENADO vira
canonico (o engine ja resolvia em tempo real via canonical_chip_type).
"""
import collections
import json
import re

from django.db import transaction

from chips.chip_types import canonical_chip_type, is_generic, label_kind
from chips.conventions import canonical_gen, is_ram_generation
from chips.knowledge.convention import (
    DENSITY_KINDS, RX_DENSITY_BARE, bus_width_problem, notes_com_speed,
    notes_tem_outra_speed, split_bus_width)
from chips.models import ChipFamily, KnownPart
from core.safe_command import SafeWriteCommand

#: Baldes de NAO MIGRADOS (excecao 3). Sao ROTULOS DE RELATORIO e tambem as
#: chaves que os testes leem — constantes para nao divergirem de um lado e de
#: outro na primeira alteracao.
NM_SOBRA = "SOBRA SEM DESTINO"
NM_CONTRA = "CONTRADICAO"
NM_CLASSE = "CLASSE NAO PERMITE"
NM_BALDES = (NM_SOBRA, NM_CONTRA, NM_CLASSE)

# Kingston nao fabrica silicio; familias DRAM "KF/KVR/ACR" sao bogus (ver memoria
# k-prefix-bga-is-samsung). KVR=ValueRAM=modulos; ACR=marking de modulo.
BOGUS_KINGSTON_PREFIXES = {"KF", "KVR", "ACR"}

# Numeros de geracao por familia, p/ detectar multi-geracao (2 numeros distintos).
_GEN_NUM_RE = re.compile(r"(?:LP|G)?DDR(\d+)", re.I)
#: Forma ABREVIADA da multi-geracao: "LPDDR4X/5X" — o "5X" NAO repete o prefixo,
#: entao o regex acima nao o enxerga e a string conta como UMA geracao so. Achado
#: em 2026-08-28: "LPDDR4X/5X" e justamente o exemplo citado no docstring do
#: `_plan` como a razao de nao migrar subtype... e nao era pego. Sem isto a
#: migracao escolheria a 4X e APAGARIA a 5X.
_GEN_NUM_ABREV_RE = re.compile(r"/\s*(\d+)X?", re.I)

#: Versao do protocolo de armazenamento dentro do subtype ("LPDDR4X + UFS 2.1").
#: NAO pode ser jogada fora ao canonizar o subtype: a versao do eMMC/UFS e
#: informacao COMERCIAL (o dono, 2026-08-27: "a versao emmc vale dinheiro"), e o
#: lugar dela e o campo `interface` (§6). O dry-run de 2026-08-28 pegou a 1a
#: versao desta migracao APAGANDO a versao de 43 registros em silencio.
_PROTOCOLO_RE = re.compile(r"\b(eMMC|UFS)\s*(\d+(?:\.\d+)?)", re.I)


def _protocolo(texto: str) -> str:
    """'LPDDR4X + UFS 2.1' -> 'UFS 2.1'.  Sem protocolo -> ''."""
    m = _PROTOCOLO_RE.search(texto or "")
    if not m:
        return ""
    nome = "eMMC" if m.group(1).lower() == "emmc" else "UFS"
    return f"{nome} {m.group(2)}"
_FAMILY_GENERIC = {"lpddr": "LPDDR", "ddr": "DDR", "gddr": "GDDR"}


def _multi_gen(subtype: str) -> bool:
    """True se o subtype menciona 2+ numeros de geracao DISTINTOS (ex.: LPDDR2/LPDDR3).
    DDR3/DDR3L conta como UM (mesmo numero 3, variante L)."""
    s = subtype or ""
    nums = set(_GEN_NUM_RE.findall(s)) | set(_GEN_NUM_ABREV_RE.findall(s))
    return len(nums) > 1


def _canon_subtype(canon_ct: str, subtype: str) -> str:
    """subtype canonico por tipo: DRAM=geracao; eMCP/uMCP=geracao LPDDR; eMMC/UFS=''; NAND=celula."""
    lk = label_kind(canon_ct)
    if lk in ("ddr", "lpddr", "gddr", "sdram", "rdram"):
        return canonical_gen(subtype or "") or (canon_ct if not is_generic(canon_ct) else (subtype or "").strip())
    if lk in ("emcp", "umcp"):
        return canonical_gen(subtype or "") or (subtype or "").strip()
    if lk in ("emmc", "ufs"):
        return ""
    if lk == "nand":
        return canonical_gen(subtype or "", "NAND Flash") or (subtype or "").strip()
    return (subtype or "").strip()


def _plan(obj):
    """Devolve ``(mudancas, motivo)``: ``{campo: [old, new]}`` e, quando a largura
    NAO migra, o balde do relatorio (`NM_*`) — string vazia quando nada impede.

    ⚠ A assinatura virou tupla na excecao 3: o `motivo` NAO pode entrar no dict de
    mudancas (viraria campo a gravar) nem descartar o resto do plano — um registro
    que nao migra a largura ainda pode ter chip_type/densidade/geracao a corrigir.

    Migra SO o chip_type (o campo critico e persistido no estoque). O subtype NAO e
    migrado: e canonicalizado em tempo de LEITURA por canonical_gen (gateway/engine),
    e migrar o subtype da FAMILIA quebra a extracao de geracao do engine (eMCP) e
    perde info de familias multi-geracao (ex.: "LPDDR4X/5X"). Limpeza de subtype no
    write-time fica para os populate_* (nascer limpo), nao para esta migracao."""
    ct = (obj.chip_type or "").strip()
    st = (obj.subtype or "").strip()
    canon = canonical_chip_type(ct, st)
    # multi-geracao -> mantem generico (decisao do usuario), nao forca uma geracao
    if _multi_gen(st) and not is_generic(canon):
        canon = _FAMILY_GENERIC.get(label_kind(canon), canon)
    # KnownPart cujos campos proprios sao genericos: a FAMILIA e a autoridade da
    # geracao (o engine ja resolve por ela no classify) — usa o tipo canonico dela.
    fam = getattr(obj, "family", None)
    if is_generic(canon) and fam is not None:
        fam_canon = canonical_chip_type(fam.chip_type or "", fam.subtype or "")
        if not is_generic(fam_canon):
            canon = fam_canon
    ch = {}
    if canon != (obj.chip_type or ""):
        ch["chip_type"] = [obj.chip_type, canon]
    # Densidade no lugar certo (regra 4 do apply_kp_convention; so KnownPart —
    # ChipFamily nao tem density_gbit). Usa o canon FINAL (pos-familia).
    if hasattr(obj, "density_gbit") and not (obj.density_gbit or "").strip() \
            and label_kind(canon) in DENSITY_KINDS:
        m = RX_DENSITY_BARE.match((obj.capacity or "").strip())
        if m:
            ch["density_gbit"] = [obj.density_gbit, f"{m.group(1)}Gb"]
    # Geracao no lugar certo (2026-08-28) — 2a excecao, gemea da densidade acima.
    # A geracao da RAM de um eMCP mora hoje DENTRO do `emcp_ram` ("LPDDR3 2GB"),
    # que e campo de MEDIDA e deve guardar UMA medida so (§6). Enquanto ela nao
    # estiver no `subtype`, limpar o `emcp_ram` derruba o veredito de 105 chips
    # de RENTAVEL para INDETERMINADO (medido no banco, 2026-08-28) — ver §7.
    # Nao inventa nada: MOVE dado ja confirmado de dentro do mesmo registro.
    #
    # FILL-ONLY, como a densidade: so escreve quando o subtype ATUAL nao e um
    # token do vocabulario. Nunca sobrescreve um subtype ja canonico.
    # DENY BY DEFAULT: o candidato tem que passar por `is_ram_generation`
    # (fullmatch, lista fechada). O `canonical_gen` PROPOE (e fail-open — devolve
    # frase intacta quando nao reconhece); o `is_ram_generation` DISPOE. Sem esse
    # par, "embedded Multi-Chip Package (LPDDR + eMMC)" viraria subtype.
    # SO KnownPart: ChipFamily pode ser MULTI-GERACAO de proposito ("LPDDR4X/5X")
    # e forcar uma geracao nela apagaria informacao (e a razao documentada no
    # `_plan` para o subtype nunca ter sido migrado).
    if hasattr(obj, "emcp_ram") and label_kind(canon) in ("emcp", "umcp") \
            and not is_ram_generation(st):
        ram = (obj.emcp_ram or "").strip()
        if not (_multi_gen(st) or _multi_gen(ram)):
            for cand in (canonical_gen(st), canonical_gen(ram)):
                if is_ram_generation(cand):
                    ch["subtype"] = [obj.subtype, cand]
                    # A versao do protocolo que estava no subtype MUDA DE CAMPO,
                    # nao evapora. Se a `interface` ja diz outra coisa, o comando
                    # NAO arbitra: desiste do registro inteiro (contradicao e
                    # decisao humana, e limpar o subtype sozinho perderia o dado).
                    proto = _protocolo(st)
                    if proto:
                        atual = (getattr(obj, "interface", "") or "").strip()
                        if not atual:
                            ch["interface"] = [obj.interface, proto]
                        elif atual.upper().replace(" ", "") != proto.upper().replace(" ", ""):
                            ch.pop("subtype")
                    break
    # ── Excecao 3 (2026-09-19): LARGURA NO LUGAR CERTO ────────────────────
    # `isinstance`, nao `hasattr("bus_width")`: desde a Fase 1 a ChipFamily
    # TAMBEM tem o campo, e o `hasattr` que o plano sugeriu deixaria a familia
    # entrar. Ela nao entra — a largura de familia vem do yaml (Fase 4) e o
    # proximo `load_brands` desfaria o que este comando escrevesse (dossie §5.1).
    motivo = ""
    if isinstance(obj, KnownPart):
        bw, sp, sobra = split_bus_width(obj.interface)
        if bw and sobra:
            # 'x16 (2 dies)': migrar so a largura APAGARIA o '(2 dies)'. I5.
            motivo = NM_SOBRA
        elif bw or sp:
            atual = (obj.bus_width or "").strip().lower()
            if bw and bus_width_problem(canon, bw):
                motivo = NM_CLASSE
            elif bw and atual and atual != bw:
                motivo = NM_CONTRA
            else:
                # FILL-ONLY: largura ja identica nao vira "mudanca" (a licao do
                # MIGRA4 — reescrita no-op suja o relatorio e o JSON de reversao).
                if bw and not atual:
                    ch["bus_width"] = [obj.bus_width, bw]
                # So aqui a `interface` e esvaziada: tudo que havia nela teve
                # destino (largura -> bus_width, velocidade -> notes).
                ch["interface"] = [obj.interface, ""]
                if sp:
                    novo = notes_com_speed(obj.notes, sp)
                    if novo != (obj.notes or ""):
                        ch["notes"] = [obj.notes, novo]
    return ch, motivo


#: Nome historico do JSON de reversao. `chips/tests.py` depende dele; o runbook
#: SEMPRE passa `--out normalize_convention_revert_<BANCO>_<AAAAMMDD>.json`, que e
#: o padrao do `backfill_doc_codes_revert_PROD_20260902.json` — dois bancos e duas
#: rodadas no mesmo dia nao podem compartilhar arquivo de reversao.
REVERT_DEFAULT = "normalize_convention_revert.json"


class Command(SafeWriteCommand):
    """⚠ `SafeWriteCommand`, nao `BaseCommand` (2026-09-19): este comando GRAVA em
    catalogo global e nao imprimia o banco-alvo. O dossie §10.3 registra uma rodada
    em producao feita achando que era local. O banner sai sempre; a confirmacao
    digitada so no `--commit` interativo."""

    help = "Migra chip_type/subtype/largura para a convencao canonica (reversivel, dry-run por padrao)."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true", help="Aplica (senao, dry-run).")
        parser.add_argument("--revert", type=str, default="", help="JSON de reversao a desfazer.")
        parser.add_argument("--out", type=str, default=REVERT_DEFAULT,
                            help=f"Caminho do JSON de reversao (default: {REVERT_DEFAULT}).")

    # ── revert ────────────────────────────────────────────────────────────────
    def _revert(self, path):
        log = json.load(open(path))
        # ⚠ `.update()`, NAO `save()` (2026-09-19). Reverter e RESTAURAR um estado
        # que estava no banco ha um minuto, nao escrever dado novo — e o `save()`
        # roda o normalizador de write-time POR CIMA da reversao e a desfaz em
        # silencio. Dois casos reais: `interface='x16'` restaurada e RECUSADA pelo
        # portao de largura (I2, e com razao: o valor mudou), e `interface='DDR3'`
        # restaurada seria APAGADA pela regra 3 do `apply_kp_convention`. O
        # `.update()` e o mesmo caminho por onde o legado entrou. Em Postgres os
        # gatilhos do pghistory capturam o `.update()` — a auditoria nao se perde.
        n_ok = 0
        with transaction.atomic():
            for e in log:
                Model = ChipFamily if e["model"] == "chipfamily" else KnownPart
                campos = {f: old for f, (old, _new) in e["changes"].items()}
                n_ok += Model.objects.filter(pk=e["pk"]).update(**campos)
        self.stdout.write(f"↩ revertido de {path} ({n_ok}/{len(log)} registros; "
                          "o que faltar ja nao existe no banco).")

    # ── handle ──────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        if opts["revert"]:
            return self._revert(opts["revert"])

        revert_log = []
        ct_moves = collections.Counter()
        st_moves = collections.Counter()
        if_moves = collections.Counter()
        bw_moves = collections.Counter()        # excecao 3: FORMA do movimento
        bw_marca = collections.Counter()        # excecao 3: por marca
        # ⚠ A excecao 1 (DENSIDADE, 2026-07-11) nunca teve contador: o relatorio
        # somava esses registros no total e nao os mostrava em lugar nenhum. Achado
        # em 2026-09-20, quando o dry-run do backfill de largura deu 3682 e os
        # baldes visiveis so explicavam 3539+161+2. Um `--commit` nao pode ter
        # linha invisivel — o dono assina o que ve.
        dg_moves = collections.Counter()        # excecao 1: densidade
        ct_kp = 0                               # chip_type SO de KnownPart
        nao_migrados = collections.defaultdict(list)
        notas_contraditorias = []
        samples = []

        # Familias
        n_fam = n_deact = 0
        for f in ChipFamily.objects.select_related("brand"):
            ch, _motivo = _plan(f)     # familia nunca migra largura (§4 F3)
            if ch:
                n_fam += 1
                revert_log.append({"model": "chipfamily", "pk": f.pk, "changes": ch})
                if "chip_type" in ch:
                    ct_moves[f"{ch['chip_type'][0]!r} -> {ch['chip_type'][1]!r}"] += 1
            if (f.brand and f.brand.name == "Kingston"
                    and f.prefix in BOGUS_KINGSTON_PREFIXES and f.active):
                n_deact += 1
                revert_log.append({"model": "chipfamily", "pk": f.pk,
                                   "changes": {"active": [True, False]}})

        # KnownParts
        n_kp = 0
        for kp in KnownPart.objects.select_related("family").iterator(chunk_size=1000):
            ch, motivo = _plan(kp)
            if motivo:
                nao_migrados[motivo].append(
                    f"{kp.part_number[:28]:28s} interface={kp.interface!r}"
                    + (f"  bus_width={kp.bus_width!r}" if (kp.bus_width or "") else "")
                    + f"  [{kp.chip_type or '?'}]")
            if ch:
                n_kp += 1
                revert_log.append({"model": "knownpart", "pk": kp.pk, "changes": ch})
                if "chip_type" in ch:
                    ct_moves[f"{ch['chip_type'][0]!r} -> {ch['chip_type'][1]!r}"] += 1
                    ct_kp += 1
                if "density_gbit" in ch:
                    dg_moves[f"(vazio) -> {ch['density_gbit'][1]!r}"] += 1
                if "subtype" in ch:
                    st_moves[f"{(ch['subtype'][0] or '(vazio)')!r} -> {ch['subtype'][1]!r}"] += 1
                # A `interface` muda por DOIS motivos diferentes: a excecao 2
                # ESCREVE o protocolo resgatado do subtype, a excecao 3 ESVAZIA
                # porque a largura foi para o campo proprio. Separar pelo valor
                # NOVO e o que mantem os dois numeros legiveis no relatorio — o
                # dono precisa ver quanto e largura antes de digitar --commit.
                if "interface" in ch and ch["interface"][1] != "":
                    if_moves[f"{(ch['interface'][0] or '(vazio)')!r} -> {ch['interface'][1]!r}"] += 1
                elif "interface" in ch:
                    velho = ch["interface"][0] or ""
                    bw_, sp_, _ = split_bus_width(velho)
                    if bw_ and sp_:
                        forma = f"{bw_} @ <velocidade>"
                        destino = "bus_width + notes 'Speed:'"
                    elif bw_:
                        forma, destino = bw_, "bus_width"
                    else:
                        forma, destino = "@ <velocidade>", "notes 'Speed:'"
                    bw_moves[f"{forma:<22} ->  {destino}"] += 1
                    bw_marca[kp.brand.name if kp.brand_id else "(sem marca)"] += 1
                    if sp_ and notes_tem_outra_speed(kp.notes, sp_):
                        notas_contraditorias.append(
                            f"{kp.part_number[:28]:28s} notes={(kp.notes or '')[:60]!r}"
                            f"  +Speed: {sp_}")
                if len(samples) < 12:
                    samples.append((kp.part_number, ch))

        self.stdout.write(f"\n=== normalize_convention ({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        self.stdout.write(f"  Familias a migrar:        {n_fam}")
        self.stdout.write(f"  Familias Kingston a desativar (bogus): {n_deact}")
        self.stdout.write(f"  KnownParts a migrar:      {n_kp}")
        self.stdout.write("\n  chip_type — top movimentos:")
        for k, c in ct_moves.most_common(20):
            self.stdout.write(f"    [{c:5d}x] {k}")
        if st_moves:
            self.stdout.write("\n  subtype — geracao no lugar certo "
                              f"({sum(st_moves.values())} KnownPart):")
            for k, c in st_moves.most_common(20):
                self.stdout.write(f"    [{c:5d}x] {k}")
        if if_moves:
            self.stdout.write("\n  interface — versao do protocolo RESGATADA do subtype "
                              f"({sum(if_moves.values())} KnownPart):")
            for k, c_ in if_moves.most_common(20):
                self.stdout.write(f"    [{c_:5d}x] {k}")
        if dg_moves:
            self.stdout.write("\n  density_gbit — DENSIDADE NO LUGAR CERTO "
                              f"({sum(dg_moves.values())} KnownPart):")
            for k, c_ in dg_moves.most_common(20):
                self.stdout.write(f"    [{c_:5d}x] {k}")
        if bw_moves:
            self.stdout.write("\n  bus_width — LARGURA NO LUGAR CERTO "
                              f"({sum(bw_moves.values())} KnownPart):")
            for k, c_ in bw_moves.most_common(20):
                self.stdout.write(f"    [{c_:5d}x] {k}")
            self.stdout.write("    por marca:")
            for k, c_ in bw_marca.most_common(40):
                self.stdout.write(f"      [{c_:5d}x] {k}")
        else:
            self.stdout.write("\n  bus_width — LARGURA NO LUGAR CERTO (0 KnownPart).")
        if notas_contraditorias:
            self.stdout.write("\n  ⚠ notes que JA declaram outra velocidade "
                              f"({len(notas_contraditorias)}) — a nova entra ao lado, "
                              "nada e apagado (I5); confira depois:")
            for ln in notas_contraditorias:
                self.stdout.write(f"       {ln}")
        total_nm = sum(len(v) for v in nao_migrados.values())
        if total_nm:
            self.stdout.write(f"\n  ⚠ NAO MIGRADOS ({total_nm} KnownPart) — decisao "
                              "humana; a largura destes fica onde esta:")
            for balde in NM_BALDES:
                linhas = nao_migrados.get(balde, [])
                if not linhas:
                    continue
                self.stdout.write(f"    -- {balde} ({len(linhas)}) --")
                for ln in linhas:      # LISTA COMPLETA, nunca amostra: sao os
                    self.stdout.write(f"       {ln}")   # casos que precisam de gente
        else:
            self.stdout.write("  NAO MIGRADOS: 0")
        # CONFERENCIA — o total nao e a soma dos baldes: um mesmo registro pode
        # estar em dois (ex.: eMCP que ganha geracao no `subtype` E tem velocidade
        # na `interface`). Mostrar os dois numeros e a diferenca e o que permite
        # conferir o dry-run sem abrir o banco.
        soma = (ct_kp + sum(dg_moves.values()) + sum(st_moves.values())
                + sum(if_moves.values()) + sum(bw_moves.values()))
        self.stdout.write("\n  conferencia dos baldes (KnownPart):")
        self.stdout.write(f"    chip_type canonico        {ct_kp:6d}")
        self.stdout.write(f"    densidade (excecao 1)     {sum(dg_moves.values()):6d}")
        self.stdout.write(f"    geracao/subtype (exc. 2)  {sum(st_moves.values()):6d}")
        self.stdout.write(f"    protocolo resgatado       {sum(if_moves.values()):6d}")
        self.stdout.write(f"    largura (excecao 3)       {sum(bw_moves.values()):6d}")
        self.stdout.write(f"    soma dos baldes           {soma:6d}")
        self.stdout.write(f"    REGISTROS distintos       {n_kp:6d}"
                          + (f"   ({soma - n_kp} em mais de um balde)"
                             if soma != n_kp else "   (nenhum em dois baldes)"))
        self.stdout.write("\n  amostra (KnownPart):")
        for pn, ch in samples:
            self.stdout.write(f"    {pn[:26]:26s} {ch}")

        if not opts["commit"]:
            self.stdout.write("\n[DRY-RUN] nada gravado. Rode com --commit para aplicar.")
            return

        with transaction.atomic():
            for e in revert_log:
                Model = ChipFamily if e["model"] == "chipfamily" else KnownPart
                obj = Model.objects.get(pk=e["pk"])
                for field, (_old, new) in e["changes"].items():
                    setattr(obj, field, new)
                obj.save(update_fields=list(e["changes"].keys()))

        path = opts["out"] or REVERT_DEFAULT
        json.dump(revert_log, open(path, "w"), ensure_ascii=False, indent=0)
        self.stdout.write(f"\n✅ aplicado ({len(revert_log)} mudancas). Reversivel: {path}")
        self.stdout.write("   ↻ O cache do engine recarrega sozinho (catalog_version, passo 1B).")
