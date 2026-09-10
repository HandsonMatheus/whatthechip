# -*- coding: utf-8 -*-
"""
audit_campo_forma.py — varre os known_parts atrás de PROSA em campo de MEDIDA.
===============================================================================
READ-ONLY. Não grava nada, não precisa de confirmação.

POR QUE EXISTE (incidente 2026-08-24)
--------------------------------------
O dono viu no admin um `KMYFE0B0CA` (Samsung eMCP) cuja coluna Capacidade dizia,
literalmente::

    RAM: SDRAM 1GB (pré-LPDDR, não é LPDDR — ver notes) /
    NAND: moviNAND ~1GB (NAND MLC 8Gb + controlador, 2 dies) + OneNAND 1GB

Uma frase inteira dentro de `emcp_ram`/`emcp_nand`. O portão não pegou — e não
pegou porque **não existe checagem de forma nesses campos**: o `KnownPartSpec`
declara `capacity/emcp_ram/emcp_nand/density_*` como `str = ""` livre, e o
`model_validator` diz, no próprio docstring, *"NÃO rejeita (known_part é ponto de
dado)"*. A convenção `emcp_ram = 'LPDDR{n} {cap}GB'` está escrita no `CLAUDE.md §6`
como **regra absoluta** e não é aplicada em lugar nenhum do código.

POR QUE ISSO É CARO (medido, não suposto)
------------------------------------------
`assess_profitability` e o label da caixa leem esses campos com `_extract_gib`,
que é um `re.search` — ele pega o **primeiro** número que casar e segue. Com prosa,
o "primeiro" depende da ordem das palavras. O MESMO chip, com a MESMA informação
escrita de três jeitos::

    'moviNAND ~1GB (NAND MLC 8Gb + …) + OneNAND 1GB'      → 1GB  → caixa EMCP1+1
    'NAND MLC 8Gb + … = moviNAND 1GB + OneNAND 1GB'       → 8GB  → caixa EMCP8+1
    'moviNAND + OneNAND, 2GB no total (MLC 8Gb por die)'  → 2GB  → caixa EMCP2+1

Três prateleiras diferentes para o mesmo chip físico. E note o segundo caso: ele
leu **8Gb (gigaBIT) como 8GB** — o bug clássico de unidade da casa, entrando por
um canal que ninguém estava vigiando. No `KMYFE0B0CA` o veredito não mudou, mas
por **coincidência dupla**: o primeiro número da frase era o certo, e SDRAM
pré-LPDDR já é NÃO RENTÁVEL por geração de qualquer forma. Sorte não é controle.

O QUE ELE CLASSIFICA
--------------------
Por campo, três baldes — e a diferença entre eles é o ponto:

* ``CANÔNICO``  — bate a forma da convenção.
* ``ALTERNATIVO`` — forma diferente da convenção mas **estabelecida e legível pelo
  engine** (ex.: ``emcp_nand='eMMC 5.1 16GB'``, 55 ocorrências no seed curado).
  Não é erro; é a convenção real sendo mais larga que o `CLAUDE.md`. Reportado
  como informação, não como dívida.
* ``PROSA``    — texto livre onde deveria haver medida. É a dívida.

Para todo ``PROSA`` ele imprime **o que o engine extrai** e **em que caixa o chip
cai** — que é a pergunta que interessa, não a estética do campo.

USO
---
    python manage.py audit_campo_forma                # tudo
    python manage.py audit_campo_forma --brand samsung
    python manage.py audit_campo_forma --so-prosa     # só a dívida
    python manage.py audit_campo_forma --csv divida.csv
"""
import csv
import re

from chips.conventions import _RAM_GEN_RE

from django.core.management.base import BaseCommand

# ── formas aceitas ───────────────────────────────────────────────────────────
# Convenção (CLAUDE.md §6). `_UNI` é case-SENSITIVE de propósito: 'Gb' (gigabit)
# e 'GB' (gigabyte) são grandezas diferentes e confundi-las é o bug histórico da
# casa (MICRON.md §4). O `?` no espaço aceita '4GB' e '4 GB'.
_NUM = r"\d+(?:\.\d+)?"
#: Vocabulário de geração de RAM — vem da FONTE ÚNICA do projeto
#: (`chips/conventions.py::_RAM_GEN_RE`), não de uma lista repetida aqui.
#: ⚠ Motivo (2026-08-26): a 1ª versão deste auditor exigia `^LPDDR\d+X?` e por
#: isso marcava `emcp_ram='SDRAM 1GB'` como AMBÍGUO — o KMYFE0B0CA da Samsung,
#: um eMCP de 2008 cuja RAM é SDRAM móvel PRÉ-LPDDR. O dado estava CERTO e a
#: regra é que era estreita. Auditor que grita com dado bom treina o leitor a
#: ignorar o auditor. Ler do vocabulário oficial também impede o auditor de
#: divergir do resto do sistema quando uma geração nova entrar.
#: (`mDDR` — nome antigo do LPDDR1 — NÃO está no vocabulário; se aparecer, é
#: decisão de domínio do chat da marca, não conserto silencioso daqui.)
_RAM_GEN_SRC = _RAM_GEN_RE.pattern

_CANONICO = {
    "emcp_ram":     re.compile(rf"^{_RAM_GEN_SRC}\s+{_NUM}\s?(GB|MB)$"),
    "emcp_nand":    re.compile(rf"^{_NUM}\s?(GB|MB|TB)$"),
    "capacity":     re.compile(rf"^{_NUM}\s?(GB|MB|TB|G|M)$"),
    "density_gbit": re.compile(rf"^{_NUM}\s?Gb$"),
    "density_gb":   re.compile(rf"^{_NUM}\s?(GB|MB)$"),
}
# Formas que NÃO são a convenção mas são estabelecidas e o engine lê bem.
_ALTERNATIVO = {
    # 'eMMC 5.1 16GB' · 'UFS 2.2 128GB' · 'eMMC 4.5 / 5.0 16GB' · 'eMMC 5.x 8GB'
    # — interface (com faixa de versão, opcionalmente) + UMA capacidade.
    # ⚠ A faixa com barra ('4.5 / 5.0') entrou em 2026-08-24: a 1ª versão deste
    # auditor a marcava como PROSA por causa do '/', e eram 6 registros SK Hynix
    # perfeitamente legíveis (o engine extrai 16.0 e a caixa sai certa). Auditor
    # que grita com dado bom treina o leitor a ignorar o auditor.
    "emcp_nand": re.compile(
        rf"^(eMMC|UFS)(\s[\d.]+x?(\s?/\s?[\d.]+x?)?)?\s+{_NUM}\s?(GB|MB|TB)$", re.I),
}

#: Valor NULO gravado como TEXTO. Classe própria porque a origem e a correção são
#: outras: não é "faltou unidade", é `None`/`null` do Python que virou string no
#: caminho de escrita. O `apply_kp_convention` já limpa (`_NONE_STRINGS`), então o
#: que sobrar no banco é ANTERIOR a essa regra ou entrou por caminho que não passa
#: por ela. O engine tolera (o `_size_for_entry` ignora a string 'None' — CLAUDE.md
#: §6), então não quebra nada hoje; é sujeira, não incêndio.
_NULO = {"none", "null", "nan", "-", "--", "n/a", "na", ""}

#: Duas COISAS diferentes no mesmo campo (ex.: `emcp_nand='eMMC 5.x + LPDDR3 16GB'`
#: — a interface do NAND E a geração da RAM, com uma capacidade só que não se sabe
#: de quem é). Diferente de faixa de versão: aqui há dois SUBSTANTIVOS de produto.
_RX_DOIS_PRODUTOS = re.compile(
    r"\b(eMMC|UFS|NAND|moviNAND|OneNAND)\b.*\+.*\b(LPDDR|mDDR|SDRAM|DDR)", re.I)

#: Marcas de PROSA. Não é heurística de comprimento: é a presença de estrutura de
#: FRASE (parênteses, travessão, vírgula, barra, "ver notes", "~", "no total") num
#: campo cujo contrato é UM número + UMA unidade.
_MARCAS_DE_PROSA = re.compile(
    r"[(),/]|—|–|~|\bver\b|\bnotes?\b|\bno total\b|\bpor die\b|\baprox|\bcerca\b",
    re.I,
)

#: O sinal mais forte, e o que não depende de pontuação: **duas ou mais MEDIDAS**
#: no mesmo campo. O contrato é UMA medida; `'NAND 512MB + mDDR1 256MB'` não tem
#: parêntese nem travessão e mesmo assim é prosa — são dois números com unidade
#: disputando o mesmo campo, e o `_extract_gib` fica com o primeiro que encontrar.
#: Case-SENSITIVE: 'Gb' e 'GB' contam separado porque são grandezas diferentes.
_RX_MEDIDA = re.compile(r"\d+(?:\.\d+)?\s?(?:GB|MB|TB|Gb|Mb|Tb)\b")

#: Qualquer unidade de tamanho, para separar os dois sub-casos do AMBÍGUO:
#: número PELADO ('64' — não se sabe a grandeza) × unidade FORA da convenção do
#: campo ('512Mb' num `density_gbit`, que é em Gb — a grandeza se sabe, falta
#: converter). São dívidas diferentes e a correção é diferente.
_RX_QUALQUER_UNIDADE = re.compile(r"\d\s?(?:GB|MB|TB|Gb|Mb|Tb|kb|KB)\b")

#: Medida em MB (mega) sem nenhuma em GB — o caso que o `_extract_gb` do label
#: não enxerga. Case-insensitive no 'B' porque aqui a distinção Gb/GB não importa:
#: o que importa é a ORDEM DE GRANDEZA que o regex do label ignora.
_RX_SO_MB = re.compile(r"\d+(?:\.\d+)?\s?MB\b(?!.*\d\s?GB)", re.I)

_CAMPOS = ("capacity", "emcp_ram", "emcp_nand", "density_gbit", "density_gb")


def classifica(campo: str, valor: str) -> str:
    """CANÔNICO | ALTERNATIVO | PROSA | AMBÍGUO — para um valor não vazio."""
    v = (valor or "").strip()
    if not v:
        return ""
    if v.lower() in _NULO:
        return "NULO"
    if _CANONICO[campo].match(v):
        return "CANÔNICO"
    alt = _ALTERNATIVO.get(campo)
    if alt and alt.match(v):
        return "ALTERNATIVO"
    if (_MARCAS_DE_PROSA.search(v) or len(_RX_MEDIDA.findall(v)) >= 2
            or _RX_DOIS_PRODUTOS.search(v)):
        return "PROSA"
    # Nem canônico nem prosa: tipicamente unidade faltando ('64' em vez de '64Gb').
    return "AMBÍGUO"


class Command(BaseCommand):
    help = ("READ-ONLY: acha PROSA em campo de medida do known_part (capacity, "
            "emcp_ram, emcp_nand, density_*) e mostra o que o engine extrai dela.")

    def add_arguments(self, parser):
        parser.add_argument("--brand", default="", help="slug/nome da marca (substring).")
        parser.add_argument("--so-prosa", action="store_true",
                            help="Só PROSA e AMBÍGUO — esconde o que está OK.")
        parser.add_argument("--csv", default="", help="Grava a dívida num CSV.")
        parser.add_argument("--limite", type=int, default=40,
                            help="Máx. de linhas detalhadas por campo (default 40).")

    def handle(self, *args, **o):
        from chips.models import KnownPart

        w = self.stdout.write
        qs = KnownPart.objects.select_related("brand", "family").all()
        if o["brand"]:
            qs = qs.filter(brand__name__icontains=o["brand"])

        total = qs.count()
        w(self.style.MIGRATE_HEADING(
            f"\n=== audit_campo_forma · READ-ONLY · {total} known_part(s) varrido(s) ==="))

        # TRIPWIRE (lição do audit_category_codes, CLAUDE.md §7): zero silencioso
        # numa auditoria é indistinguível de "está tudo limpo". Grite.
        if total == 0:
            w(self.style.ERROR(
                "\n⚠ ZERO known_parts varridos. Isso NÃO quer dizer 'catálogo limpo' — "
                "quer dizer que a varredura não enxergou nada.\n"
                "  Confira o banco-alvo e o --brand antes de concluir qualquer coisa."))
            return

        achados, contagem = [], {c: {} for c in _CAMPOS}
        for kp in qs.iterator():
            for campo in _CAMPOS:
                valor = (getattr(kp, campo, "") or "").strip()
                if not valor:
                    continue
                cls = classifica(campo, valor)
                contagem[campo][cls] = contagem[campo].get(cls, 0) + 1
                if cls in ("PROSA", "AMBÍGUO", "NULO"):
                    achados.append((kp, campo, valor, cls))

        # ── painel ───────────────────────────────────────────────────────────
        w("")
        w(f"  {'campo':<14} {'CANÔNICO':>9} {'ALTERNAT.':>10} {'NULO':>6} "
          f"{'AMBÍGUO':>9} {'PROSA':>7}")
        w("  " + "-" * 61)
        for campo in _CAMPOS:
            c = contagem[campo]
            prosa = c.get("PROSA", 0)
            linha = (f"  {campo:<14} {c.get('CANÔNICO',0):>9} {c.get('ALTERNATIVO',0):>10} "
                     f"{c.get('NULO',0):>6} {c.get('AMBÍGUO',0):>9} {prosa:>7}")
            w(self.style.ERROR(linha) if prosa else linha)

        divida = [a for a in achados if a[3] == "PROSA"]
        ambiguo = [a for a in achados if a[3] == "AMBÍGUO"]
        nulos = [a for a in achados if a[3] == "NULO"]

        # ── LABEL TRUNCADO: achado 2026-08-24, INDEPENDENTE da prosa ─────────
        # O branch eMCP/uMCP do gateway monta a etiqueta com `_extract_gb`, que só
        # casa 'GB' — NUNCA 'MB'. Então um eMCP com RAM de 512MB (comuníssimo em
        # legado) sai como 'EMCP4+', sem a parte da RAM. É o MESMO bug que o branch
        # NAND teve e que foi corrigido em 2026-06-19 trocando para `_format_cap`
        # (que lê MB); o eMCP/uMCP ficou para trás. Aqui só REPORTA — mudar o
        # label muda a CHAVE do código de caixa (F12), e código de caixa é eterno:
        # gaveta já etiquetada no cliente não pode mudar de nome sozinha.
        # ⚠ Sub-classificar é o ponto: "70 truncados" parece UM problema e são
        # TRÊS, com donos diferentes. Misturar os três num número só faz o dono
        # decidir errado — ou não decidir.
        truncados = []
        for kp in qs.iterator():
            if not (kp.emcp_ram or kp.emcp_nand):
                continue
            _, caixa = self._extrai_caixa(kp)
            if not (caixa.endswith("+") or caixa in ("eMCP", "uMCP")):
                continue
            ram = (kp.emcp_ram or "").strip()
            nand = (kp.emcp_nand or "").strip()
            tem_ram = bool(ram) and ram.lower() not in _NULO
            tem_nand = bool(nand) and nand.lower() not in _NULO
            if not tem_ram and not tem_nand:
                # Não há o que rotular: o registro é IDENTITY-ONLY (PN↔FBGA sem
                # spec). Trabalho de DADO, não de código — e já tem frente
                # própria: DOSSIE_MICRON_identity_only / PLANO_MICRON_IDENTITY_ONLY_FASE2.
                causa = "sem-dado"
            elif tem_ram and not tem_nand:
                # Tem RAM, falta NAND — e o label é `f"EMCP{n}+{r}" if nand else 'eMCP'`:
                # o guard exige NAND e DESCARTA a RAM conhecida junto. Bug de CÓDIGO,
                # e diferente do de MB.
                causa = "guard-nand"
            elif _RX_SO_MB.search(ram) or _RX_SO_MB.search(nand):
                # O `_extract_gb` só casa 'GB'. Bug de CÓDIGO — o mesmo que o branch
                # NAND teve e que foi corrigido em 2026-06-19.
                causa = "ram-em-MB"
            else:
                causa = "outro"
            truncados.append((kp, caixa, causa))

        if not achados:
            w(self.style.SUCCESS("\n✅ Nenhum campo de medida com prosa ou unidade faltando."))
            return

        # ── o que o engine faz com cada um (a parte acionável) ───────────────
        if divida:
            w(self.style.ERROR(f"\n\n■ PROSA em campo de medida — {len(divida)} ocorrência(s)"))
            w("  Para cada uma: o que está escrito, o que o engine EXTRAI, e em que "
              "caixa\n  o chip cai. É a extração que decide prateleira e preço — não o texto.\n")
            for kp, campo, valor, _ in divida[:o["limite"]]:
                w(f"  {kp.part_number}  ({kp.brand.name if kp.brand else '—'} · "
                  f"{kp.chip_type or '—'} · {kp.review_status})")
                w(f"     {campo} = {valor[:100]!r}")
                w(f"     {self._impacto(kp)}")
                w("")
            if len(divida) > o["limite"]:
                w(f"  … +{len(divida) - o['limite']} (use --limite ou --csv)")

        if ambiguo:
            w(self.style.WARNING(
                f"\n■ AMBÍGUO — {len(ambiguo)} ocorrência(s), em DOIS sub-casos"))
            w("  [sem-un]  número pelado: '64' não diz se é 64Gb ou 64GB — 8× de diferença,")
            w("            e o pricing lê o número.")
            w("  [un-fora] TEM unidade, mas não a que o campo espera (ex.: '512Mb' num")
            w("            `density_gbit`, que é em Gb). Não é descuido de digitação: é")
            w("            conversão pendente, e a conta é outra. Corrigir é diferente.\n")
            for kp, campo, valor, _ in ambiguo[:o["limite"]]:
                sub = "un-fora" if _RX_QUALQUER_UNIDADE.search(valor) else "sem-un"
                w(f"    [{sub}] {kp.part_number:<24} {campo:<13} {valor[:40]!r}")
            if len(ambiguo) > o["limite"]:
                w(f"    … +{len(ambiguo) - o['limite']}")

        # ── por marca: de onde vem a dívida ──────────────────────────────────
        # ⚠ `setdefault` com as chaves ENUMERADAS à mão explodiu (KeyError: 'NULO')
        # quando o balde NULO foi criado em 2026-08-24: um dicionário de contagem
        # que precisa conhecer o vocabulário de antemão quebra a cada classe nova.
        # Agora conta pelo que APARECE.
        por_marca = {}
        for kp, _, _, cls in achados:
            nome = kp.brand.name if kp.brand else "(sem marca)"
            d = por_marca.setdefault(nome, {})
            d[cls] = d.get(cls, 0) + 1
        w("\n■ Por marca (quem precisa ser avisado)")
        for nome, d in sorted(por_marca.items(), key=lambda x: -sum(x[1].values())):
            w(f"    {nome:<20} prosa={d.get('PROSA', 0):<4} "
              f"ambíguo={d.get('AMBÍGUO', 0):<4} nulo={d.get('NULO', 0)}")

        if nulos:
            w(self.style.WARNING(
                f"\n■ NULO gravado como TEXTO — {len(nulos)} ocorrência(s)"))
            w("  A string 'None' (o None do Python virado texto). O engine tolera — o")
            w("  `_size_for_entry` ignora 'None' (CLAUDE.md §6) — então é sujeira, não")
            w("  incêndio. Mas o `apply_kp_convention` já limpa isso no save, então o que")
            w("  está aí é ANTERIOR à regra ou entrou por caminho que não passa por ela.\n")
            porc = {}
            for kp, campo, _, _ in nulos:
                porc[campo] = porc.get(campo, 0) + 1
            for campo, n in sorted(porc.items(), key=lambda x: -x[1]):
                w(f"    {campo:<14} {n}")

        if truncados:
            w(self.style.ERROR(
                f"\n■ LABEL DE CAIXA TRUNCADO — {len(truncados)} chip(s)"))
            w("  ⚠ Achado SEPARADO da prosa, e provavelmente mais caro. O branch eMCP/uMCP")
            w("  do gateway usa `_extract_gb`, que só casa 'GB' — nunca 'MB'. eMCP com RAM")
            w("  de 512MB (comuníssimo em legado) vira 'EMCP4+', SEM a RAM. É o mesmo bug")
            w("  que o branch NAND teve e que foi corrigido em 2026-06-19 com `_format_cap`;")
            w("  o eMCP/uMCP ficou para trás.")
            w("  ⚠ NÃO corrija sem decidir o custo: mudar o label muda a CHAVE do código de")
            w("  caixa (F12), e código de caixa é ETERNO — gaveta já etiquetada não muda de")
            w("  nome sozinha. Ver CLAUDE.md §7.\n")
            porc = {}
            for _, _, causa in truncados:
                porc[causa] = porc.get(causa, 0) + 1
            w("  São TRÊS problemas, com DONOS diferentes — não misture:")
            w(f"    [ram-em-MB]  {porc.get('ram-em-MB', 0):>4}  bug de CÓDIGO — `_extract_gb` "
              f"cego pra MB. Decisão do dono (F12).")
            w(f"    [guard-nand] {porc.get('guard-nand', 0):>4}  bug de CÓDIGO, OUTRO — o label é "
              f"`if nand else 'eMCP'`, então")
            w( "                       falta de NAND joga fora a RAM que se CONHECE.")
            w(f"    [sem-dado]   {porc.get('sem-dado', 0):>4}  NÃO é bug de label: o registro é "
              f"identity-only (PN↔FBGA")
            w( "                       sem spec). Trabalho de DADO, e já tem frente própria —")
            w( "                       DOSSIE_MICRON_identity_only / PLANO_MICRON_IDENTITY_ONLY_FASE2.")
            if porc.get("outro"):
                w(f"    [outro]      {porc['outro']:>4}  investigar caso a caso.")
            w("")
            for kp, caixa, causa in sorted(truncados, key=lambda t: t[2])[:o["limite"]]:
                w(f"    [{causa:<10}] {kp.part_number:<24} "
                  f"nand={(kp.emcp_nand or '—')[:20]:<22} "
                  f"ram={(kp.emcp_ram or '—')[:18]:<20} → {caixa!r}")
            if len(truncados) > o["limite"]:
                w(f"    … +{len(truncados) - o['limite']}")

        if o["csv"]:
            with open(o["csv"], "w", newline="", encoding="utf-8") as fh:
                wr = csv.writer(fh)
                wr.writerow(["part_number", "brand", "chip_type", "review_status",
                             "campo", "valor", "classe", "engine_extrai", "caixa"])
                for kp, campo, valor, cls in achados:
                    extrai, caixa = self._extrai_caixa(kp)
                    wr.writerow([kp.part_number, kp.brand.name if kp.brand else "",
                                 kp.chip_type, kp.review_status, campo, valor, cls,
                                 extrai, caixa])
            w(self.style.SUCCESS(f"\n✅ CSV: {o['csv']}"))

        w(self.style.WARNING(
            "\n⚠ NADA foi alterado (read-only). Corrigir known_part é pelo canal normal: "
            "o chat da marca\n  entrega submissão nova e o dono roda "
            "`submit_known_parts` — CONFLITO é decisão humana."))

    # ── helpers ─────────────────────────────────────────────────────────────
    def _extrai_caixa(self, kp):
        """(o que o engine extrai, label da caixa) — tolerante a qualquer erro:
        um auditor que estoura no meio da varredura é pior que um campo feio."""
        try:
            from chips.engine import _extract_gib
            from estoque.views import _compute_destination
            r = {"chip_type": kp.chip_type, "subtype": kp.subtype,
                 "capacity": kp.capacity, "emcp_ram": kp.emcp_ram,
                 "emcp_nand": kp.emcp_nand, "dram_density": kp.density_gbit,
                 "interface": kp.interface, "brand": kp.brand.name if kp.brand else "",
                 "pn": kp.part_number, "is_emcp": bool(kp.emcp_ram or kp.emcp_nand)}
            partes = []
            for campo in ("emcp_nand", "emcp_ram", "capacity"):
                v = getattr(kp, campo, "") or ""
                if v:
                    partes.append(f"{campo}→{_extract_gib(v)}")
            caixa = _compute_destination(r)
            caixa = caixa[0] if isinstance(caixa, tuple) else str(caixa)
            return " ".join(partes), caixa
        except Exception as e:                                   # noqa: BLE001
            return f"(falhou: {type(e).__name__})", "?"

    def _impacto(self, kp):
        extrai, caixa = self._extrai_caixa(kp)
        return f"engine lê: {extrai or '—'}   →   CAIXA: {caixa}"
