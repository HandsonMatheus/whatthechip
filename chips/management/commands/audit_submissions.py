# -*- coding: utf-8 -*-
"""
audit_submissions.py — READ-ONLY: o ARQUIVO de submissões × o BANCO.
=====================================================================
Responde, para TODAS as marcas de uma vez: *"o que das minhas submissões não
está no banco?"*. É o par de leitura do ``submit_known_parts``, e existe porque
a dívida que ele criava era INVISÍVEL — um PN já aprovado era pulado, e o aviso
só aparecia depois do ``--commit``, no fim da saída (o dry-run nem consultava o
banco). Meses de submissões depois, ninguém sabia o tamanho do rombo.

Como a pasta ``submissions/`` guarda TODO formulário já entregue, replicá-la
contra o banco reconstrói a dívida inteira sem precisar de histórico nenhum.

NÃO ESCREVE NADA. Rode com o DATABASE_URL do banco que quer inspecionar
(inclusive o de produção, pelo Render Shell):

    python manage.py audit_submissions
    python manage.py audit_submissions --brand Micron --detail
    python manage.py audit_submissions --dir submissions --confidence confirmed,manual

Baldes (os MESMOS do submit_known_parts, pela mesma chave ``part_number_norm``):
    AUSENTE    não existe no banco (nunca entrou, ou foi apagado/rejeitado)
    PENDENTE   existe em draft/submitted/rejected — esperando aprovação no admin
    COMPLETA   aprovado com campo VAZIO que a submissão preencheria  ← a dívida
    CONFLITO   aprovado com valor DIFERENTE do arquivo (decisão humana)
    OK         aprovado e já com o que o arquivo diz

Conserto do balde COMPLETA:
    python manage.py submit_known_parts <arquivo> --commit --fill-empty
"""
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from django.conf import settings
from django.core.management.base import BaseCommand

from chips.models import KnownPart
from chips.normalize import normalize_pn

# 'confidence' fora do confronto de campos: nunca é vazio (default 'confirmed'),
# então divergência ali é decisão de AUTORIDADE — reportada à parte.
_CAMPOS = ["chip_type", "subtype", "capacity", "density_gbit", "density_gb",
           "emcp_ram", "emcp_nand", "interface", "fbga_code", "device",
           "notes", "source_url"]

_BALDES = ["AUSENTE", "PENDENTE", "COMPLETA", "CONFLITO", "OK"]

# Classe do campo — é o eixo da DECISÃO num conflito, não o campo em si:
#   preço      muda a classificação e portanto o valor do lote (o que urge)
#   identidade diz QUAL peça é (não mexe em preço, mas é o casamento do PN)
#   texto      proveniência/descrição — quase sempre o mais VERBOSO é o melhor
_CLASSE = {
    "chip_type": "preço", "subtype": "preço", "capacity": "preço",
    "density_gbit": "preço", "density_gb": "preço",
    "emcp_ram": "preço", "emcp_nand": "preço",
    "fbga_code": "identidade", "device": "identidade",
    "interface": "texto", "notes": "texto", "source_url": "texto",
}


def _vazio(v) -> bool:
    return not str(v or "").strip()


class Command(BaseCommand):
    help = "READ-ONLY: confronta submissions/*.yaml com o banco e mostra a dívida por marca."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default="submissions",
                            help="Pasta das submissões (default: submissions/).")
        parser.add_argument("--brand", default="", help="Filtra por marca (nome do arquivo).")
        parser.add_argument("--detail", action="store_true",
                            help="Lista PN a PN em vez de amostra, com valores INTEIROS.")
        parser.add_argument("--por-campo", action="store_true",
                            help="Resume os CONFLITOS por CAMPO (é assim que se decide a "
                                 "política: quem vence, banco ou submissão, campo a campo).")

    def handle(self, *args, **o):
        w = self.stdout.write
        marca_filtro = (o["brand"] or "").strip().lower()
        pasta = Path(o["dir"])
        if not pasta.is_absolute():
            pasta = Path(settings.BASE_DIR) / pasta
        if not pasta.exists():
            w(self.style.ERROR(f"pasta não encontrada: {pasta}"))
            return

        resumo = defaultdict(Counter)
        detalhe = {b: defaultdict(list) for b in _BALDES}
        conf_dif = defaultdict(list)
        self._por_campo = defaultdict(list)   # campo → [(marca, pn, banco, arquivo)]
        arquivos = sorted(pasta.glob("*.yaml")) + sorted(pasta.glob("*.yml"))

        for caminho in arquivos:
            try:
                raw = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
            except Exception as e:            # arquivo torto não derruba a auditoria
                w(self.style.WARNING(f"⚠ {caminho.name}: yaml ilegível ({e})"))
                continue
            marca = str(raw.get("brand") or "?")
            if marca_filtro and marca.lower() != marca_filtro:
                continue
            for d in (raw.get("known_parts") or []):
                pn = str(d.get("part_number") or "").strip()
                if not pn:
                    continue
                balde, extra = self._classifica(pn, d, conf_dif, marca)
                resumo[marca][balde] += 1
                detalhe[balde][marca].append((pn, caminho.name, extra))

        if not resumo:
            w("Nenhuma submissão casou com o filtro.")
            return

        w(f"\n{len(arquivos)} arquivo(s) em {pasta} · banco: "
          f"{settings.DATABASES['default'].get('NAME')}\n")
        w(f"{'MARCA':<18}" + "".join(f"{b:>10}" for b in _BALDES) + f"{'TOTAL':>9}")
        w("-" * 80)
        total = Counter()
        for marca in sorted(resumo):
            linha = resumo[marca]
            total.update(linha)
            w(f"{marca:<18}" + "".join(f"{linha[b]:>10}" for b in _BALDES)
              + f"{sum(linha.values()):>9}")
        w("-" * 80)
        w(f"{'TOTAL':<18}" + "".join(f"{total[b]:>10}" for b in _BALDES)
          + f"{sum(total.values()):>9}")

        self._secao("COMPLETA — aprovado com campo vazio que a submissão preencheria "
                    "(conserto: submit_known_parts <arquivo> --commit --fill-empty)",
                    detalhe["COMPLETA"], o["detail"], self.style.WARNING)
        self._secao("CONFLITO — banco ≠ arquivo (decisão humana, no admin)",
                    detalhe["CONFLITO"], o["detail"], self.style.ERROR)
        self._secao("PENDENTE — esperando aprovação no admin",
                    detalhe["PENDENTE"], o["detail"], None)
        self._secao("AUSENTE — submetido um dia, não está no banco",
                    detalhe["AUSENTE"], o["detail"], None)
        if o["por_campo"]:
            self._resumo_por_campo(o["detail"])
        if any(conf_dif.values()):
            w(self.style.WARNING("\n⚠ confidence divergente (banco → arquivo):"))
            for marca in sorted(conf_dif):
                for item in (conf_dif[marca] if o["detail"] else conf_dif[marca][:10]):
                    w(f"    {marca}: {item[0]:<32} {item[1]} → {item[2]}")

    # ────────────────────────────────────────────────────────────────────
    def _classifica(self, pn, d, conf_dif, marca):   # noqa: C901
        kp = KnownPart.objects.filter(part_number_norm=normalize_pn(pn)).first()
        if kp is None:
            return "AUSENTE", ""
        if kp.review_status != "approved":
            return "PENDENTE", kp.review_status
        preencher, muda = [], []
        for c in _CAMPOS:
            novo, atual = d.get(c), getattr(kp, c, "")
            if _vazio(novo):
                continue
            if _vazio(atual):
                preencher.append(c)
            elif str(atual).strip() != str(novo).strip():
                muda.append(f"{c}: {str(atual)[:24]!r}→{str(novo)[:24]!r}")
                self._por_campo[c].append(
                    (marca, pn, str(atual).strip(), str(novo).strip()))
        conf_arq = str(d.get("confidence") or "confirmed").strip()
        if conf_arq != kp.confidence:
            conf_dif[marca].append((pn, kp.confidence, conf_arq))
        if muda:
            return "CONFLITO", "; ".join(muda)
        if preencher:
            return "COMPLETA", ", ".join(preencher)
        return "OK", ""

    def _resumo_por_campo(self, detalhe):
        """CONFLITO agrupado por CAMPO — a visão que permite decidir por CLASSE
        em vez de PN a PN. `banco+longo` conta os casos em que o valor do BANCO
        é mais rico que o do arquivo (ex.: interface 'x16 @ 800MHz (1600MTPS)'
        contra 'x16'): aplicar a submissão nesses PERDERIA informação."""
        w = self.stdout.write
        if not self._por_campo:
            return
        w(self.style.WARNING("\n\nCONFLITOS POR CAMPO — decida a política por classe:"))
        w("  classe 'preço' muda a classificação (e o valor do lote); 'texto' é "
          "proveniência.\n  banco+longo/arquivo+longo só ajudam nos campos de TEXTO "
          "(mais verboso ≈ mais rico);\n  em campo de preço o que vale é qual fonte "
          "tem Tier-1, não o tamanho.")
        w(f"\n{'CAMPO':<14}{'CLASSE':<11}{'CONFLITOS':>10}{'banco+longo':>13}"
          f"{'arq+longo':>11}   MARCAS")
        w("-" * 92)
        for campo in sorted(self._por_campo,
                            key=lambda c: (_CLASSE.get(c, "z") != "preço",
                                           -len(self._por_campo[c]))):
            itens = self._por_campo[campo]
            banco_maior = sum(1 for _m, _p, a, n in itens if len(a) > len(n))
            arq_maior = sum(1 for _m, _p, a, n in itens if len(n) > len(a))
            marcas = ", ".join(sorted({m for m, _p, _a, _n in itens}))
            w(f"{campo:<14}{_CLASSE.get(campo, '?'):<11}{len(itens):>10}"
              f"{banco_maior:>13}{arq_maior:>11}   {marcas[:34]}")
        w("-" * 92)
        for campo in sorted(self._por_campo, key=lambda c: -len(self._por_campo[c])):
            itens = self._por_campo[campo]
            w(f"\n  {campo} ({len(itens)}):")
            for marca, pn, atual, novo in (itens if detalhe else itens[:4]):
                corte = 4000 if detalhe else 70
                w(f"    {marca}/{pn}")
                w(f"      banco   : {atual[:corte]!r}")
                w(f"      arquivo : {novo[:corte]!r}")
            if not detalhe and len(itens) > 4:
                w(f"    … +{len(itens) - 4} (use --por-campo --detail)")

    def _secao(self, titulo, por_marca, detalhe, estilo):
        if not any(por_marca.values()):
            return
        w = self.stdout.write
        n = sum(len(v) for v in por_marca.values())
        cab = f"\n{titulo}  —  {n} PN(s)"
        w(estilo(cab) if estilo else cab)
        for marca in sorted(por_marca):
            itens = por_marca[marca]
            w(f"  {marca} ({len(itens)}):")
            for pn, arq, extra in (itens if detalhe else itens[:8]):
                w(f"    {pn:<34} ← {arq}" + (f"  [{extra}]" if extra else ""))
            if not detalhe and len(itens) > 8:
                w(f"    … +{len(itens) - 8} (use --detail)")
