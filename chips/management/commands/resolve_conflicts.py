# -*- coding: utf-8 -*-
"""
resolve_conflicts.py — aplica a POLÍTICA POR CLASSE DE CAMPO aos conflitos.
===========================================================================
Par de ESCRITA do ``audit_submissions``. Existe porque a primeira varredura em
produção (2026-08-17) mostrou que a dívida das submissões não era campo vazio
(2 PNs) e sim **CONFLITO** (147): as pipelines de import (Micron API, Samsung
PSG) criaram/preencheram o registro, ele virou `approved`, e a submissão Tier-1
do chat que ia corrigir aquilo foi **pulada por ser "PN já aprovado"**. O valor
da máquina venceu o pesquisado, em silêncio.

⚠ Aplicar os conflitos em bloco seria ERRADO — em vários deles o BANCO é melhor:

    interface: 'x16 @ 800MHz (1600MTPS)'  →  'x16'           (banco mais rico)
    interface: 'eMMC 5.1'                 →  'eMMC 5.x'      (banco mais preciso)
    device:    'Samsung S6802 (Galaxy…'   →  'Samsung GT-S6802…'  (arquivo certo)
    chip_type: 'DDR3'                     →  'DDR3L'         (semântico, vale $)

Quem vence depende do **campo**, não do PN (decisão do dono, 2026-08-17):

| classe     | campos                                          | política |
|------------|-------------------------------------------------|----------|
| preço      | chip_type, subtype, capacity, density_gbit,     | a SUBMISSÃO vence (é o único
|            | density_gb, emcp_ram, emcp_nand                 | que mexe no valor do lote —
|            |                                                 | revise o diff do dry-run) |
| identidade | device, fbga_code                               | a SUBMISSÃO vence |
| interface  | interface                                       | fica o MAIS ESPECÍFICO |
| texto      | notes                                            | MERGE (nada se perde) |
|            | source_url                                       | mantém o do banco e registra
|            |                                                  | o do arquivo dentro do notes |

`source_url` não é concatenável (o campo é UMA url — juntar quebraria o link),
então o do arquivo entra como linha de fonte adicional no `notes`.

Travas: dry-run por padrão · `--commit` grava · backup JSON + `--revert` ·
`--exclude` pra tirar PN de fora · portão do modelo em cada save (PN que o
portão rejeitar é reportado, não derruba a varredura) · banner do banco-alvo.

Uso:
    python manage.py resolve_conflicts                          # dry-run, tudo
    python manage.py resolve_conflicts --brand Micron           # uma marca
    python manage.py resolve_conflicts --sem-precos             # só o seguro
    python manage.py resolve_conflicts --exclude "PN A,PN B"
    python manage.py resolve_conflicts --commit
    python manage.py resolve_conflicts --revert var/reverts/resolve_conflicts_*.json

Mapa da dívida (read-only): ``audit_submissions --por-campo``.
"""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import yaml

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from core.safe_command import SafeWriteCommand
from chips.models import KnownPart
from chips.normalize import normalize_pn
from chips.management.commands.audit_submissions import _CAMPOS, _CLASSE, _vazio

# Política por campo (derivada da classe — ver o cabeçalho).
_ARQUIVO_VENCE = {"chip_type", "subtype", "capacity", "density_gbit", "density_gb",
                  "emcp_ram", "emcp_nand", "device", "fbga_code"}
_MAIS_ESPECIFICO = {"interface"}
_MERGE = {"notes"}
_FONTE_NO_NOTES = {"source_url"}

_PRECO = {c for c, k in _CLASSE.items() if k == "preço"}


class Command(SafeWriteCommand):
    help = ("Aplica a política por classe de campo aos conflitos submissão × banco. "
            "Dry-run por padrão; --commit grava; --revert desfaz.")

    def add_arguments(self, parser):
        parser.add_argument("--dir", default="submissions")
        parser.add_argument("--brand", default="")
        parser.add_argument("--file", default="", help="Só este arquivo de submissão.")
        parser.add_argument("--fields", default="",
                            help="Limita aos campos listados (vírgula).")
        parser.add_argument("--sem-precos", action="store_true",
                            help="Pula os campos de PREÇO (aplica só o resto).")
        parser.add_argument("--exclude", default="", help="PNs a pular (vírgula).")
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--revert", default="")
        parser.add_argument("--backup", default="")

    def handle(self, *args, **o):
        if o["revert"]:
            return self._revert(o["revert"])

        w = self.stdout.write
        marca_filtro = (o["brand"] or "").strip().lower()
        campos_ok = {c.strip() for c in o["fields"].split(",") if c.strip()} or set(_CAMPOS)
        if o["sem_precos"]:
            campos_ok -= _PRECO
        excluir = {normalize_pn(p.strip()) for p in o["exclude"].split(",") if p.strip()}

        pasta = Path(o["dir"])
        if not pasta.is_absolute():
            pasta = Path(settings.BASE_DIR) / pasta
        arquivos = ([Path(o["file"])] if o["file"]
                    else sorted(pasta.glob("*.yaml")) + sorted(pasta.glob("*.yml")))

        plano, pulados = [], Counter()
        for caminho in arquivos:
            try:
                raw = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
            except Exception as e:
                w(self.style.WARNING(f"⚠ {caminho.name}: yaml ilegível ({e})"))
                continue
            marca = str(raw.get("brand") or "?")
            if marca_filtro and marca.lower() != marca_filtro:
                continue
            for d in (raw.get("known_parts") or []):
                pn = str(d.get("part_number") or "").strip()
                if not pn:
                    continue
                norm = normalize_pn(pn)
                if norm in excluir:
                    pulados["excluído pelo dono"] += 1
                    continue
                kp = KnownPart.objects.filter(part_number_norm=norm).first()
                if kp is None or kp.review_status != "approved":
                    continue
                acoes = self._decide(kp, d, campos_ok)
                if acoes:
                    plano.append((marca, kp, caminho.name, acoes))

        if not plano:
            w("✓ Nenhum conflito a resolver no escopo pedido.")
            if pulados:
                w(f"  ({', '.join(f'{v} {k}' for k, v in pulados.items())})")
            return

        self._mostra(plano, pulados)

        if not o["commit"]:
            w(self.style.WARNING(
                "\nDRY-RUN — nada gravado. Revise os campos de PREÇO acima "
                "(são os que mexem no valor do lote) e rode com --commit."))
            return

        aplicados, rejeitados, revert_log = 0, [], []
        for marca, kp, arq, acoes in plano:
            antes = {c: getattr(kp, c) or "" for c in _CAMPOS}
            try:
                with transaction.atomic():          # savepoint POR PN: um PN que o
                    for campo, _antes, novo, _pol in acoes:   # portão rejeitar não
                        setattr(kp, campo, novo)              # derruba a varredura
                    kp.save()
            except (ValidationError, Exception) as e:
                for campo, valor in antes.items():
                    setattr(kp, campo, valor)
                rejeitados.append((kp.part_number, str(e)[:120]))
                continue
            revert_log.append({"part_number": kp.part_number, "before": antes})
            aplicados += 1

        destino = self._grava_backup(o["backup"], revert_log) if revert_log else ""
        w(self.style.SUCCESS(f"\n✅ {aplicados} registro(s) atualizado(s)."))
        if destino:
            w(f"   Backup reversível: {destino}")
            w(f"   Desfazer: python manage.py resolve_conflicts --revert {destino}")
        if rejeitados:
            w(self.style.ERROR(f"\n⚠ {len(rejeitados)} REJEITADO(s) pelo portão do modelo "
                               f"(nada gravado neles):"))
            for pn, erro in rejeitados[:10]:
                w(f"    {pn}: {erro}")
        w(self.style.WARNING(
            "\n⚠ FECHE O LAÇO: o catálogo mudou, mas os LOTES guardam o snapshot do "
            "lançamento.\n   python manage.py resnapshot_lote --all           # dry-run\n"
            "   python manage.py resnapshot_lote --all --commit"))

    # ────────────────────────────────────────────────────────────────────
    def _decide(self, kp, d, campos_ok):
        """[(campo, antes, depois, política)] — só onde HÁ conflito real."""
        acoes = []
        for campo in _CAMPOS:
            if campo not in campos_ok:
                continue
            novo, atual = d.get(campo), getattr(kp, campo, "")
            if _vazio(novo) or _vazio(atual):
                continue                      # vazio é COMPLEMENTO (submit --fill-empty)
            atual_s, novo_s = str(atual).strip(), str(novo).strip()
            if atual_s == novo_s:
                continue
            if campo in _ARQUIVO_VENCE:
                acoes.append((campo, atual_s, novo_s, "submissão vence"))
            elif campo in _MAIS_ESPECIFICO:
                if len(novo_s) > len(atual_s):
                    acoes.append((campo, atual_s, novo_s, "mais específico"))
            elif campo in _MERGE:
                if novo_s not in atual_s:
                    acoes.append((campo, atual_s, f"{atual_s}\n— (submissão) {novo_s}",
                                  "merge"))
            elif campo in _FONTE_NO_NOTES:
                # o campo é UMA url: mantém a do banco e guarda a do arquivo na notes
                marca_fonte = f"— (submissão) fonte: {novo_s}"
                notas = str(getattr(kp, "notes", "") or "").strip()
                if marca_fonte not in notas:
                    ja = next((a for a in acoes if a[0] == "notes"), None)
                    base = ja[2] if ja else notas
                    if ja:
                        acoes.remove(ja)
                    acoes.append(("notes", notas,
                                  (base + "\n" + marca_fonte).strip(),
                                  "merge + fonte da submissão"))
        return acoes

    def _mostra(self, plano, pulados):
        w = self.stdout.write
        por_classe = defaultdict(list)
        for marca, kp, arq, acoes in plano:
            for campo, antes, depois, pol in acoes:
                por_classe[_CLASSE.get(campo, "?")].append((marca, kp, campo, antes, depois, pol))
        w(f"\n{len(plano)} registro(s) com conflito no escopo · "
          f"{sum(len(v) for v in por_classe.values())} campo(s) a resolver")
        if pulados:
            w(f"  ({', '.join(f'{v} {k}' for k, v in pulados.items())})")
        for classe in ("preço", "identidade", "texto"):
            itens = por_classe.get(classe)
            if not itens:
                continue
            titulo = f"\n── {classe.upper()} ({len(itens)} campo(s)) ──"
            w(self.style.ERROR(titulo) if classe == "preço" else titulo)
            limite = len(itens) if classe == "preço" else 12
            for marca, kp, campo, antes, depois, pol in itens[:limite]:
                w(f"  {marca}/{kp.part_number}  ·  {campo}  [{pol}]")
                w(f"      banco   : {antes[:100]!r}")
                w(f"      vira    : {depois[:100]!r}")
            if len(itens) > limite:
                w(f"  … +{len(itens) - limite}")

    def _grava_backup(self, caminho, revert_log):
        destino = caminho or os.path.join(
            settings.BASE_DIR, "var", "reverts",
            f"resolve_conflicts_revert_{datetime.now():%Y%m%d_%H%M%S}.json")
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        with open(destino, "w", encoding="utf-8") as fh:
            json.dump(revert_log, fh, ensure_ascii=False, indent=0)
        return destino

    def _revert(self, caminho):
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
        self.stdout.write(f"↩  Revertido: {n} de {len(log)} registro(s) de {caminho}.")
