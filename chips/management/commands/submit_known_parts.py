"""
submit_known_parts.py — canal de CONTRIBUIÇÃO de known_parts (Opção 2).

Substitui a autoria via YAML+PR para os known_parts: um chat de marca (ou o dono) escreve
um arquivo de SUBMISSÃO e roda este comando, que valida pelo PORTÃO (o MESMO `KnownPartSpec`
do `load_brands`) e grava cada PN como **review_status='submitted'** — OCULTO do engine até
o dono APROVAR no admin (fila Aprovar/Reprovar, com four-eyes). O arquivo é FORMULÁRIO de
submissão, NÃO a fonte da verdade: é consumido uma vez, não vai pro git, não re-sincroniza
(logo, sem drift). A GRAMÁTICA continua no yaml/PR (`load_brands`); só a AUTORIDADE passa aqui.

O QUE MUDOU EM 2026-08-17 (dono: "subi specs de PNs que já eram confirmados e nada entrou")
==========================================================================================
Um PN já APROVADO nunca é rebaixado pra 'submitted' — isso tiraria do ar um registro live.
Certo. Errado era o RESTO: a checagem morava DENTRO do bloco do ``--commit``, então o
DRY-RUN — o portão em que todo mundo confia — **não consultava o banco** e dizia "13
válidos" para uma submissão que ia gravar 10. O aviso só nascia depois de gravar, no fim de
uma saída longa. Resultado: dezenas de PNs "confirmados" ficaram identity-only e os LOTES
herdaram o snapshot sem spec.

Agora, em QUALQUER modo (dry-run inclusive), cada PN é confrontado com o banco pela chave
canônica (``part_number_norm`` — antes o lookup era pelo ``part_number`` cru, e uma
diferença de formatação já fazia o comando errar o registro existente) e cai num balde:

    NOVO        não existe → entra como 'submitted' (fluxo de sempre)
    RESUBMETE   existe em draft/submitted/rejected → reescrito como 'submitted'
    COMPLEMENTO aprovado com campo VAZIO que a submissão preenche  ← a dívida invisível
    CONFLITO    aprovado com valor DIFERENTE do arquivo (não é preencher, é MUDAR)
    IGUAL       aprovado e já com o que o arquivo diz — nada a fazer

A assimetria é o desenho todo: **preencher vazio ≠ sobrescrever**. Preencher não contradiz
nenhuma afirmação anterior (é aditivo e reversível) e por isso ganha caminho de massa,
``--fill-empty``. Sobrescrever contradiz algo já aprovado: NUNCA sai daqui — vira o arquivo
``<submissão>.conflitos.yaml`` (banco × arquivo lado a lado) e é decisão humana no admin.

Travas do ``--fill-empty`` (mesmo ritual do ``correct_known_parts``):
  • só campo VAZIO no banco e preenchido no arquivo — jamais sobrescreve;
  • ``review_status`` continua 'approved': o registro não sai do ar um segundo;
  • exige proveniência Tier-1 no PN (``notes`` ou ``source_url``) — sem fonte, pula e avisa;
  • escreve pelo PORTÃO (``KnownPart.save()`` → full_clean + convenção + bump da
    catalog_version, que é o que faz o estoque enxergar as entradas como DEFASADAS);
  • backup JSON reversível → ``--revert <json>``;
  • banner do BANCO-ALVO + confirmação digitada (SafeWriteCommand) — só neste caminho.

⚠ Preencher o catálogo NÃO conserta os lotes sozinho: ``InventoryEntry`` guarda o snapshot
do lançamento. O comando imprime o ``resnapshot_lote`` no fim — esse é o fechamento do laço.

Formato (yaml):
    brand: "SK Hynix"
    submitted_by: "meu_usuario"        # opcional; senão use --user
    known_parts:
      - part_number: "H9HCNNNCPMMLXR-NEE"
        chip_type: "eMCP"
        subtype: "LPDDR4"
        emcp_nand: "32GB"
        emcp_ram: "LPDDR4 3GB"
        confidence: confirmed
        notes: "datasheet SK Hynix rev.1.2 / Octopart"   # fonte Tier-1 (proveniência)

Uso:
    python manage.py submit_known_parts arquivo.yaml                    # dry-run = portão + baldes
    python manage.py submit_known_parts arquivo.yaml --commit --user meu_usuario
    python manage.py submit_known_parts arquivo.yaml --commit --fill-empty   # + completa aprovados
    python manage.py submit_known_parts --revert var/reverts/fill_kp_*.json  # desfaz o complemento

Panorama de TODAS as submissões contra o banco (read-only): ``audit_submissions``.
"""
import json
import os
from datetime import datetime

import yaml

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction

from core.safe_command import SafeWriteCommand

_FIELDS = ["chip_type", "subtype", "capacity", "density_gbit", "density_gb", "emcp_ram",
           "emcp_nand", "interface", "fbga_code", "device", "notes", "source_url",
           "confidence"]

# Campos que o --fill-empty pode PREENCHER. `confidence` fica de fora de propósito: ele
# nunca é vazio (default 'confirmed'), então mudá-lo é decisão de AUTORIDADE, não
# complemento — divergência é só reportada.
_CAMPOS_SPEC = [f for f in _FIELDS if f != "confidence"]

#: Campos de PROVENIÊNCIA, que ACUMULAM em vez de conflitar. Vêm da fonte
#: única — a política do `resolve_conflicts` —, para os dois comandos não
#: divergirem outra vez sobre o que é "conflito".
from chips.management.commands.resolve_conflicts import (  # noqa: E402
    _MERGE as _POL_MERGE, _FONTE_NO_NOTES as _POL_FONTE)
_ACUMULAM = _POL_MERGE | _POL_FONTE


def _vazio(v) -> bool:
    return not str(v or "").strip()


class Command(SafeWriteCommand):
    help = ("Submete known_parts (review_status='submitted') pelo portão e mostra o que já "
            "existe no banco. Dry-run por padrão; --fill-empty completa aprovados sem spec.")

    # Submissão normal (só grava 'submitted', oculto do engine) não pede confirmação —
    # é o comando do dia a dia. Escrever em registro APROVADO (--fill-empty) pede.
    confirm_on_commit = False

    def add_arguments(self, parser):
        parser.add_argument("arquivo", nargs="?", default="")
        parser.add_argument("--commit", action="store_true",
                            help="Grava de verdade (sem isto é dry-run = só o portão).")
        parser.add_argument("--user", default="",
                            help="username do submitter (four-eyes: não poderá auto-aprovar).")
        parser.add_argument("--fill-empty", action="store_true",
                            help="Preenche os campos VAZIOS de PNs já aprovados (nunca "
                                 "sobrescreve valor existente, nunca rebaixa o status).")
        parser.add_argument("--revert", default="",
                            help="JSON de reversão de um --fill-empty a desfazer.")
        parser.add_argument("--backup", default="",
                            help="Caminho do JSON de backup (default: var/reverts/).")

    def execute(self, *args, **options):
        # A confirmação digitada do SafeWriteCommand vale para o caminho que toca
        # registro APROVADO — não para a submissão comum.
        self.confirm_on_commit = bool(options.get("fill_empty") and options.get("commit"))
        return super().execute(*args, **options)

    # ────────────────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        from django.contrib.auth import get_user_model
        from chips.knowledge.schema import KnownPartSpec
        from chips.models import Brand, KnownPart
        from chips.normalize import normalize_pn

        if opts["revert"]:
            return self._revert(opts["revert"])
        if not opts["arquivo"]:
            raise CommandError("informe o arquivo de submissão (ou --revert <json>).")

        raw = yaml.safe_load(open(opts["arquivo"], encoding="utf-8")) or {}
        brand_name = raw.get("brand")
        if not brand_name:
            raise CommandError("arquivo precisa de 'brand: <nome>'.")
        # ⚠ O erro que já mordeu DUAS vezes (Kingston, 2026-08-17 e 2026-08-19):
        # o chat de marca escreve `brand:` como BLOCO (name/code/notes), que é o
        # formato do yaml de GRAMÁTICA. Aí `brand_name` vira dict, o filter não
        # casa nada e a mensagem genérica lá embaixo manda "crie a gramática
        # antes" — conselho errado, que joga o dono na trilha errada por horas.
        # A submissão só NOMEIA a marca; nome/code/notes vivem na gramática.
        if isinstance(brand_name, dict):
            nome = brand_name.get("name") or "<nome da marca>"
            raise CommandError(
                "'brand' veio como BLOCO, não como texto — esse é o formato do "
                "yaml de GRAMÁTICA\n(chips/knowledge/<marca>.yaml), não o da "
                "submissão. A gramática NÃO está faltando.\n\n"
                f"  troque o bloco inteiro por uma linha só:\n\n"
                f"      brand: {nome}\n\n"
                "  (a submissão apenas nomeia a marca; name/code/notes são da "
                "gramática)")
        kps_raw = raw.get("known_parts") or []
        if not kps_raw:
            raise CommandError("nenhum known_part no arquivo.")

        # PORTÃO: valida + normaliza cada known_part (mesmo KnownPartSpec do load_brands).
        specs, erros = [], []
        for i, d in enumerate(kps_raw, 1):
            try:
                specs.append(KnownPartSpec(**d))
            except Exception as e:
                erros.append(f"  #{i} ({d.get('part_number', '?')}): {e}")
        if erros:
            raise CommandError("PORTÃO rejeitou:\n" + "\n".join(erros))

        # PORTÃO 2 (tipo × FAMÍLIA): o KnownPartSpec valida o known_part ISOLADO — não conhece
        # a família que o prefixo vai casar. Cruza aqui (mesma trava do clean() do modelo) pra o
        # chat ver o conflito eMCP↔não-eMCP no DRY-RUN, não só quando o --commit explode no save.
        from chips.knowledge.convention import family_type_conflict
        conflitos_tipo = [f"  {s.part_number}: {msg}"
                          for s in specs
                          if (msg := family_type_conflict(s.part_number, s.chip_type))]
        if conflitos_tipo:
            raise CommandError("PORTÃO (tipo × família) rejeitou:\n" + "\n".join(conflitos_tipo))

        brand = Brand.objects.filter(name=brand_name).first()
        if brand is None:
            # Marca de verdade ausente: aí sim a gramática é o caminho. Mas
            # mostra as parecidas — erro de grafia é bem mais comum do que
            # marca nova (o portão só chega aqui depois de validar os PNs).
            from difflib import get_close_matches
            todas = sorted(Brand.objects.values_list("name", flat=True))
            perto = get_close_matches(str(brand_name), todas, n=3, cutoff=0.6)
            dica = (f"\n  parecida(s) no banco: {', '.join(perto)}" if perto
                    else f"\n  no banco hoje: {', '.join(todas[:12])}"
                         + ("…" if len(todas) > 12 else ""))
            raise CommandError(
                f"marca '{brand_name}' não existe no banco — crie a gramática "
                f"antes (chips/knowledge/, load_brands).{dica}")

        uname = opts["user"] or raw.get("submitted_by") or ""
        submitter = None
        if uname:
            submitter = get_user_model().objects.filter(username=uname).first()
            if submitter is None:
                raise CommandError(f"usuário '{uname}' não existe.")

        # ── CONFRONTO COM O BANCO (agora TAMBÉM no dry-run — era o furo) ────────────
        novos, resubmete, complemento, conflito, iguais, sem_fonte = [], [], [], [], [], []
        conf_dif = []
        for s in specs:
            kp = KnownPart.objects.filter(
                part_number_norm=normalize_pn(s.part_number)).first()
            if kp is None:
                novos.append((s, None))
                continue
            if kp.review_status != "approved":
                resubmete.append((s, kp))
                continue
            preencher, muda = [], []
            for campo in _CAMPOS_SPEC:
                novo, atual = getattr(s, campo), getattr(kp, campo, "")
                if _vazio(novo):
                    continue
                if _vazio(atual):
                    preencher.append(campo)
                elif str(atual).strip() != str(novo).strip():
                    # PROVENIÊNCIA NÃO É CONFLITO (2026-08-27). `notes` e
                    # `source_url` ACUMULAM — é o que o `resolve_conflicts` faz
                    # com eles (_MERGE e _FONTE_NO_NOTES). Compará-los por
                    # igualdade de string aqui tornava os dois comandos
                    # INSATISFAZÍVEIS juntos: o `resolve_conflicts`, ao resolver
                    # um conflito de `source_url`, NUNCA sobrescreve a url (é uma
                    # só, juntar quebraria o link) — ele escreve um marcador
                    # dentro de `notes`. Resultado medido: `source_url` diverge
                    # para sempre, e `notes` passa a divergir TAMBÉM. O registro
                    # ficava travado em CONFLITO permanente e o `--fill-empty`
                    # não preenchia mais nada nele — nem os campos genuinamente
                    # vazios. Pior: cada rodada do `resolve_conflicts` ADICIONAVA
                    # um conflito (1 → 2), então o par se afastava da solução.
                    # Caso real: 6 eMCP Micron MT29TZZZ7D7 (JZ050 e irmãos) com
                    # `emcp_nand`/`emcp_ram` vazios desde a importação FBGA.
                    if campo in _ACUMULAM:
                        continue
                    muda.append((campo, str(atual), str(novo)))
            if s.confidence != kp.confidence:
                conf_dif.append((s.part_number, kp.confidence, s.confidence))
            # ⚠ OS BALDES NÃO SÃO MAIS EXCLUDENTES. `preencher` e `muda` são
            # conjuntos DISJUNTOS por construção (o `if _vazio(atual)` separa),
            # então um conflito em `capacity` não tem por que vetar o
            # preenchimento de um `emcp_ram` VAZIO no mesmo PN — e era isso que
            # o antigo `if muda: … elif preencher:` fazia. Um PN pode legitimamente
            # ter campo a completar E campo a decidir; o painel mostra os dois.
            if preencher:
                # Proveniência: completar um registro LIVE sem fonte Tier-1 no arquivo
                # seria dado órfão — o revisor não teria o que conferir depois.
                if _vazio(s.notes) and _vazio(s.source_url):
                    sem_fonte.append((s, kp, preencher))
                else:
                    complemento.append((s, kp, preencher))
            if muda:
                conflito.append((s, kp, muda))
            if not preencher and not muda:
                iguais.append((s, kp))

        # FORMA dos campos de medida (2026-08-24). O portão Pydantic NÃO rejeita
        # known_part de propósito ("é ponto de dado") — então prosa em
        # capacity/emcp_* passava INVISÍVEL. Aqui ela pelo menos APARECE, usando a
        # MESMA classificação do `audit_campo_forma` (fonte única, sem regra
        # duplicada). Continua não bloqueando: quem decide é o revisor.
        from chips.management.commands.audit_campo_forma import classifica, _CAMPOS
        forma_ruim = []
        for sp in specs:
            for campo in _CAMPOS:
                valor = (getattr(sp, campo, "") or "").strip()
                if valor and classifica(campo, valor) in ("PROSA", "AMBÍGUO"):
                    forma_ruim.append((sp.part_number, campo, valor,
                                       classifica(campo, valor)))

        self._painel(brand_name, uname, specs, novos, resubmete, complemento,
                     conflito, iguais, sem_fonte, conf_dif, opts, forma_ruim)

        caminho_conflitos = ""
        if conflito:
            caminho_conflitos = self._grava_conflitos(opts["arquivo"], brand_name, conflito)

        if not opts["commit"]:
            self.stdout.write(self.style.WARNING(
                "\nDRY-RUN — nada gravado. Use --commit para submeter"
                + (" (e --fill-empty para completar os aprovados acima)." if complemento
                   else ".")))
            return

        # ── GRAVAÇÃO ───────────────────────────────────────────────────────────────
        criados, preenchidos, revert_log = 0, [], []
        with transaction.atomic():
            for s, kp in novos + resubmete:
                obj = kp or KnownPart(part_number=s.part_number)
                obj.brand = brand
                for k in _FIELDS:
                    setattr(obj, k, getattr(s, k))
                obj.review_status = "submitted"   # OCULTO até aprovação
                obj.submitted_by = submitter
                obj.save()                         # clean() re-valida/normaliza
                criados += 1

            if opts["fill_empty"]:
                for s, kp, campos in complemento:
                    # Backup do ESTADO INTEIRO da spec (não só dos campos tocados): o
                    # save() passa pela convenção e pode normalizar vizinhos.
                    revert_log.append({
                        "part_number": kp.part_number,
                        "before": {c: getattr(kp, c) or "" for c in _CAMPOS_SPEC},
                    })
                    for c in campos:
                        setattr(kp, c, getattr(s, c))
                    # review_status/submitted_by/approved_by INTOCADOS de propósito:
                    # o registro continua live e a autoria original é preservada.
                    kp.save()
                    preenchidos.append((kp.part_number, campos))

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ {criados} submetido(s) como 'submitted'. Aprove em /admin/chips/knownpart/ "
            f"(filtro review_status → Submetido)."))

        if preenchidos:
            destino = self._grava_backup(opts["backup"], revert_log)
            self.stdout.write(self.style.SUCCESS(
                f"✓ {len(preenchidos)} aprovado(s) COMPLETADO(s) (só campos vazios; "
                f"seguem approved/no ar)."))
            for pn, campos in preenchidos[:15]:
                self.stdout.write(f"    {pn:<34} ← {', '.join(campos)}")
            if len(preenchidos) > 15:
                self.stdout.write(f"    … +{len(preenchidos) - 15}")
            self.stdout.write(f"   Backup reversível: {destino}")
            self.stdout.write(f"   Desfazer: python manage.py submit_known_parts --revert {destino}")
            self.stdout.write(self.style.WARNING(
                "\n⚠ FECHE O LAÇO: o catálogo mudou, mas os LOTES guardam o snapshot do "
                "lançamento.\n   python manage.py resnapshot_lote --all           # dry-run\n"
                "   python manage.py resnapshot_lote --all --commit"))
        elif complemento:
            self.stdout.write(self.style.WARNING(
                f"⚠ {len(complemento)} PN(s) aprovado(s) com campo VAZIO NÃO foram tocados — "
                f"rode de novo com --fill-empty para completá-los."))
        if caminho_conflitos:
            self.stdout.write(self.style.WARNING(
                f"⚠ conflitos NÃO aplicados (decisão humana): {caminho_conflitos}"))

    # ────────────────────────────────────────────────────────────────────────
    def _painel(self, brand_name, uname, specs, novos, resubmete, complemento,
                conflito, iguais, sem_fonte, conf_dif, opts, forma_ruim=()):
        """O que o dry-run NÃO mostrava: a foto do arquivo contra o banco, no TOPO."""
        w = self.stdout.write
        w(f"Marca: {brand_name} · {len(specs)} known_part(s) válido(s) no portão · "
          f"submitter: {uname or '(nenhum)'}")
        w("")
        w(f"  NOVO         {len(novos):>4}  → entram como 'submitted' (aprovar no admin)")
        if resubmete:
            w(f"  RESUBMETE    {len(resubmete):>4}  → já existiam em rascunho/submetido, reescritos")
        estilo = self.style.WARNING if complemento else (lambda s: s)
        w(estilo(f"  COMPLEMENTO  {len(complemento):>4}  → APROVADOS com campo vazio que este "
                 f"arquivo preenche{'  [--fill-empty]' if complemento and not opts['fill_empty'] else ''}"))
        if sem_fonte:
            w(self.style.WARNING(
                f"  SEM FONTE    {len(sem_fonte):>4}  → completariam um aprovado, mas o arquivo "
                f"não tem notes/source_url"))
        if conflito:
            w(self.style.ERROR(
                f"  CONFLITO     {len(conflito):>4}  → APROVADOS com valor DIFERENTE — nunca "
                f"aplicado aqui"))
        w(f"  IGUAL        {len(iguais):>4}  → aprovados e já com o que o arquivo diz")

        # ⚠ Os baldes deixaram de ser excludentes em 2026-08-27, então a soma pode
        # passar do total de PNs. Dizer isso explicitamente evita o leitor achar
        # que a conta está errada — e mostra QUAIS PNs estão nos dois lados, que
        # é a informação nova: parte do registro completa agora, parte espera
        # decisão sua.
        nos_dois = ({s.part_number for s, _, _ in complemento}
                    & {s.part_number for s, _, _ in conflito})
        if nos_dois:
            w(self.style.WARNING(
                f"  ↑ {len(nos_dois)} PN(s) contam nos DOIS baldes: campo vazio que o "
                f"--fill-empty completa E campo divergente que só você decide — "
                f"{', '.join(sorted(nos_dois)[:6])}"))

        # Proveniência dos NOVOS (aviso de sempre — a revisão humana é o filtro).
        faltando = [s.part_number for s, _ in novos + resubmete
                    if s.confidence in ("confirmed", "manual")
                    and _vazio(s.notes) and _vazio(s.source_url)]
        if faltando:
            w(self.style.WARNING(
                f"\n⚠ {len(faltando)} confirmed/manual SEM fonte Tier-1 na notes/source_url "
                f"(o revisor deve exigir): {', '.join(faltando[:10])}"))
        if complemento:
            w("\n  Campos a completar:")
            for s, kp, campos in complemento[:15]:
                w(f"    {kp.part_number:<34} ← {', '.join(campos)}")
            if len(complemento) > 15:
                w(f"    … +{len(complemento) - 15}")
        for s, kp, campos in sem_fonte[:10]:
            w(self.style.WARNING(f"    (sem fonte) {kp.part_number:<28} ← {', '.join(campos)}"))
        if conflito:
            w("\n  Conflitos (banco → arquivo):")
            for s, kp, muda in conflito[:10]:
                for campo, atual, novo in muda:
                    w(f"    {kp.part_number:<30} {campo:<12} {atual[:28]!r} → {novo[:28]!r}")
        if conf_dif:
            w(self.style.WARNING(
                "\n  ⚠ confidence divergente (NÃO é alterado por este comando; mude no admin):"))
            for pn, atual, novo in conf_dif[:10]:
                w(f"    {pn:<34} {atual} → {novo}")
        if forma_ruim:
            w(self.style.ERROR(
                f"\n  ⚠ FORMA suspeita em {len(forma_ruim)} campo(s) de MEDIDA "
                f"(capacity/emcp_*/density_*):"))
            for pn, campo, valor, cls in forma_ruim[:10]:
                w(f"    [{cls}] {pn:<24} {campo:<13} {valor[:52]!r}")
            if len(forma_ruim) > 10:
                w(f"    … +{len(forma_ruim) - 10}")
            w("    Esses campos são lidos por regex (`_extract_gib` pega o PRIMEIRO número).")
            w("    Prosa aí dentro faz o MESMO chip cair em caixas diferentes conforme a")
            w("    ordem das palavras — e 'Gb' no meio da frase vira 'GB' (8x). Diagnóstico")
            w("    completo: `python manage.py audit_campo_forma`.")

    def _grava_conflitos(self, arquivo, brand_name, conflito):
        """Relatório de conflito (não toca o banco) — sai em dry-run TAMBÉM, que é
        quando ainda dá pra corrigir o arquivo."""
        destino = f"{arquivo}.conflitos.yaml"
        payload = {
            "brand": brand_name,
            "gerado_por": "submit_known_parts (relatório — nada foi gravado no banco)",
            "conflitos": [
                {"part_number": kp.part_number,
                 "campos": [{"campo": c, "banco": a, "arquivo": n} for c, a, n in muda]}
                for _s, kp, muda in conflito
            ],
        }
        try:
            with open(destino, "w", encoding="utf-8") as fh:
                yaml.safe_dump(payload, fh, allow_unicode=True, sort_keys=False)
        except OSError as e:
            self.stdout.write(self.style.WARNING(f"⚠ não consegui escrever {destino}: {e}"))
            return ""
        return destino

    def _grava_backup(self, caminho, revert_log):
        destino = caminho or os.path.join(
            settings.BASE_DIR, "var", "reverts",
            f"fill_kp_revert_{datetime.now():%Y%m%d_%H%M%S}.json")
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        with open(destino, "w", encoding="utf-8") as fh:
            json.dump(revert_log, fh, ensure_ascii=False, indent=0)
        return destino

    def _revert(self, caminho):
        from chips.models import KnownPart
        log = json.load(open(caminho, encoding="utf-8"))
        n = 0
        for row in log:
            kp = KnownPart.objects.filter(part_number=row["part_number"]).first()
            if kp is None:
                continue
            for campo, antes in row["before"].items():
                setattr(kp, campo, antes)
            kp.save()
            n += 1
        self.stdout.write(f"↩  Revertido: {n} de {len(log)} registro(s) restaurado(s) de {caminho}.")
