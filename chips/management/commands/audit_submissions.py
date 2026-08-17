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


def _vazio(v) -> bool:
    return not str(v or "").strip()


class Command(BaseCommand):
    help = "READ-ONLY: confronta submissions/*.yaml com o banco e mostra a dívida por marca."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default="submissions",
                            help="Pasta das submissões (default: submissions/).")
        parser.add_argument("--brand", default="", help="Filtra por marca (nome do arquivo).")
        parser.add_argument("--detail", action="store_true",
                            help="Lista PN a PN em vez de amostra.")

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
        if any(conf_dif.values()):
            w(self.style.WARNING("\n⚠ confidence divergente (banco → arquivo):"))
            for marca in sorted(conf_dif):
                for item in (conf_dif[marca] if o["detail"] else conf_dif[marca][:10]):
                    w(f"    {marca}: {item[0]:<32} {item[1]} → {item[2]}")

    # ────────────────────────────────────────────────────────────────────
    def _classifica(self, pn, d, conf_dif, marca):
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
        conf_arq = str(d.get("confidence") or "confirmed").strip()
        if conf_arq != kp.confidence:
            conf_dif[marca].append((pn, kp.confidence, conf_arq))
        if muda:
            return "CONFLITO", "; ".join(muda)
        if preencher:
            return "COMPLETA", ", ".join(preencher)
        return "OK", ""

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
