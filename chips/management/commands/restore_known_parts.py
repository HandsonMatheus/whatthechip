"""
restore_known_parts.py — recuperação EMERGENCIAL dos known_parts a partir de um
JSON extraído do backup (Export) do prod.

Preenche as LACUNAS de known_parts no banco: cria os que ainda NÃO existem (chave =
part_number normalizado), mapeando a marca (Toshiba/Kioxia/KIOXIA → Toshiba-Kioxia) e
religando a família por prefixo. NÃO sobrescreve o que já existe — o dado curado do
yaml/PSG VENCE. Dedupa pela chave normalizada, mantendo a MAIOR confiança.

LARGURA (F5, 2026-09-24). Backup anterior a 24/09 traz a largura de barramento
DENTRO do `interface` ('x16', 'x16 @ 800MHz (1600MTPS)'): 3.539 registros no
Export de produção, 154 no seed. O restore aplica a MESMA regra do backfill
(`normalize_convention.plano_largura`): largura → `bus_width`, velocidade →
`notes`, e o `interface` fica só com protocolo. Sem isso havia dois defeitos, um
de cada lado da trava da F5: antes dela, as larguras voltavam ao campo errado EM
SILÊNCIO (o `bulk_create` pula o portão do `clean()`); depois dela, o banco recusa
o token exato e o `--commit` inteiro caía, com o dry-run dizendo que ia dar certo.
O que a regra deixa para decisão humana (SOBRA SEM DESTINO, CONTRADICAO, CLASSE
NAO PERMITE) é LISTADO, nunca resolvido em silêncio: restaura como estava quando
o banco aceita o valor; quando o `interface` é o token exato, que o banco recusa,
aquele registro NÃO é restaurado — e a lista diz qual.

Uso (rodar LOCALMENTE apontando DATABASE_URL ao prod):
    python manage.py restore_known_parts _restore_kp.json            # dry-run
    python manage.py restore_known_parts _restore_kp.json --commit   # grava + sobe catalog_version
"""
import collections
import json

from django.core.management.base import BaseCommand
from django.db import transaction

_CONF_RANK = {"confirmed": 3, "manual": 2, "distributor": 1, "estimated": 0}
_BRAND_ALIAS = {"Toshiba": "Toshiba-Kioxia", "Kioxia": "Toshiba-Kioxia", "KIOXIA": "Toshiba-Kioxia"}
_FIELDS = ("chip_type", "subtype", "capacity", "density_gbit", "density_gb", "emcp_ram",
           "emcp_nand", "interface", "bus_width", "device", "notes", "source_url",
           "fbga_code")


class Command(BaseCommand):
    help = "Recupera known_parts de um JSON de backup, preenchendo as lacunas do banco."

    def add_arguments(self, parser):
        parser.add_argument("json_file")
        parser.add_argument("--commit", action="store_true",
                            help="Grava de verdade (sem isto é dry-run).")

    def handle(self, *args, **opts):
        from chips.models import KnownPart, ChipFamily, Brand, CatalogVersion
        from chips.normalize import normalize_pn
        from chips.conventions import INTERFACE_VETADA
        from chips.knowledge.convention import apply_kp_convention, split_bus_width
        from chips.management.commands.normalize_convention import (
            NM_BALDES, canon_do_registro, plano_largura)

        commit = opts["commit"]
        rows = json.load(open(opts["json_file"], encoding="utf-8"))
        # maior confiança primeiro → o dedup mantém a melhor
        rows.sort(key=lambda r: _CONF_RANK.get(r.get("confidence"), 0), reverse=True)

        brands = {b.name: b for b in Brand.objects.all()}
        fams = sorted(ChipFamily.objects.all(), key=lambda f: -len(f.prefix))

        def match_family(pnn):
            for f in fams:
                if f.prefix and pnn.startswith(f.prefix.upper()):
                    return f
            return None

        ja_no_banco = set(KnownPart.objects.values_list("part_number_norm", flat=True))
        seen, novos = set(), []
        mantidos = dup_backup = sem_marca = 0
        marcas_faltando = set()
        largura = collections.Counter()                  # forma do movimento → quantos
        nao_migrados = collections.defaultdict(list)     # restaurados como estavam
        nao_restaurados = collections.defaultdict(list)  # o banco recusaria o valor

        for r in rows:
            pn = (r.get("part_number") or "").strip()
            if not pn:
                continue
            pnn = normalize_pn(pn)
            if pnn in ja_no_banco:
                mantidos += 1
                continue
            if pnn in seen:
                dup_backup += 1
                continue
            nome = _BRAND_ALIAS.get(r.get("brand"), r.get("brand"))
            brand = brands.get(nome)
            if brand is None:
                sem_marca += 1
                marcas_faltando.add(r.get("brand"))
                continue
            seen.add(pnn)
            kp = KnownPart(part_number=pn, part_number_norm=pnn, brand=brand,
                           family=match_family(pnn),
                           confidence=r.get("confidence") or "confirmed",
                           **{f: (r.get(f) or "") for f in _FIELDS})
            apply_kp_convention(kp)   # bulk_create pula o clean() → normaliza aqui (subtype/interface/'None')
            # LARGURA — a mesma régua do backfill (F5). O `canon` também é o do
            # backfill: a classe decide se largura cabe (eMMC/eMCP não têm).
            mud, motivo = plano_largura(canon_do_registro(kp), kp.interface,
                                        kp.bus_width, kp.notes)
            if motivo:
                linha = (f"{pn[:28]:28s} interface={kp.interface!r}"
                         + (f"  bus_width={kp.bus_width!r}" if kp.bus_width else "")
                         + f"  [{kp.chip_type or '?'}]")
                if kp.interface in INTERFACE_VETADA:
                    nao_restaurados[motivo].append(linha)   # o banco recusaria
                    continue
                nao_migrados[motivo].append(linha)
            for campo, (_antigo, novo) in mud.items():
                setattr(kp, campo, novo)
            if "interface" in mud:
                # O rótulo é o MESMO do relatório do normalize_convention — assim
                # as duas saídas se comparam linha a linha.
                bw_, sp_, _ = split_bus_width(mud["interface"][0] or "")
                if bw_ and sp_:
                    forma, destino = f"{bw_} @ <velocidade>", "bus_width + notes 'Speed:'"
                elif bw_:
                    forma, destino = bw_, "bus_width"
                else:
                    forma, destino = "@ <velocidade>", "notes 'Speed:'"
                largura[f"{forma:<22} ->  {destino}"] += 1
            novos.append(kp)

        criados = len(novos)
        n_nao_rest = sum(len(v) for v in nao_restaurados.values())
        n_nao_mig = sum(len(v) for v in nao_migrados.values())
        self.stdout.write(
            f"A criar: {criados}  ·  já existiam (mantidos): {mantidos}  ·  "
            f"dups no backup: {dup_backup}  ·  sem marca: {sem_marca}  ·  "
            f"NÃO restaurados: {n_nao_rest}")
        if marcas_faltando:
            self.stdout.write(self.style.WARNING(f"  marcas não encontradas no banco: {sorted(marcas_faltando)}"))
        self.stdout.write(f"  largura no lugar certo — {sum(largura.values())} dos {criados} a criar "
                          "(a mesma regra do normalize_convention):")
        for k, c in largura.most_common():
            self.stdout.write(f"    [{c:5d}x] {k}")
        # As duas listas são COMPLETAS, nunca amostra: são os casos que precisam
        # de gente, e o 6º escondido é o que fica errado para sempre.
        if n_nao_mig:
            self.stdout.write(self.style.WARNING(
                f"  ⚠ NÃO MIGRADOS ({n_nao_mig}) — restaurados com a largura onde "
                "estava; decisão humana:"))
            for balde in NM_BALDES:
                for i, ln in enumerate(nao_migrados.get(balde, [])):
                    if i == 0:
                        self.stdout.write(f"    -- {balde} ({len(nao_migrados[balde])}) --")
                    self.stdout.write(f"       {ln}")
        if n_nao_rest:
            self.stdout.write(self.style.WARNING(
                f"  ⚠ NÃO RESTAURADOS ({n_nao_rest}) — o banco recusa largura no "
                "`interface` (trava da F5); estes ficam FORA, estão no JSON — decisão humana:"))
            for balde in NM_BALDES:
                for i, ln in enumerate(nao_restaurados.get(balde, [])):
                    if i == 0:
                        self.stdout.write(f"    -- {balde} ({len(nao_restaurados[balde])}) --")
                    self.stdout.write(f"       {ln}")

        if not commit:
            self.stdout.write(self.style.WARNING("DRY-RUN — nada gravado. Use --commit para aplicar."))
            return

        with transaction.atomic():
            KnownPart.objects.bulk_create(novos, batch_size=500)
        v = CatalogVersion.bump()
        self.stdout.write(self.style.SUCCESS(
            f"✓ {criados} known_parts restaurados. catalog_version → {v}. O engine recarrega sozinho."))
