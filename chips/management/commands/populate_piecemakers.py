"""
populate_piecemakers.py
========================
Popula o banco com as famílias de chips PieceMakers Technology e seus mapas
de decodificação posicional.

PieceMakers Technology, Inc. — Hsinchu, Taiwan. Fundada 2006.
Fabless DRAM design company: DDR/DDR2/DDR3/DDR3L/DDR4, PSRAM, KGD.
ISO 9001 e 14001 certificada.

Para o mercado de reciclagem, os chips relevantes são:
  - DDR3 / DDR3L standalone (PMF5xx / PMF4xx) — alta frequência na esteira
  - DDR4 standalone (PMAxx) — emergente
  - DDR2 / DDR1 / SDRAM — NÃO RENTÁVEL, routing apenas

Idempotente: usa get_or_create em tudo. Pode ser rodado múltiplas vezes.

Regra de ouro (hierarquia de fontes — nunca quebrar):
    fabricante (piecemakers.com.tw / datasheet oficial)
      > Digilent / boards documentados
        > Octopart
          > distribuidor rastreável
            > IA externa / especulação

Fontes desta implementação (Tier 1 / verificável):
  - piecemakers.com.tw/products/standard-dram/ — catálogo oficial da marca
  - glochip.com/ddr3/piecemakers.html — tabela completa DDR3/DDR2/DDR1 PieceMakers
  - element14.com (2022-06-01, hrishi98): Arty S7-50 usa PMF511816EBR como
    drop-in para Micron MT41K128M16XX-15E (2Gb, x16, DDR3, 1.35V/1.5V)
  - datasheet link em element14: piecemakers.com.tw/api/v1/file/e0a55febeeb036f135c7698e33aed1e8.pdf

Uso:
    python manage.py populate_piecemakers
    python manage.py populate_piecemakers --dry-run
    python manage.py populate_piecemakers --overwrite
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Popula famílias e mapas de decodificação PieceMakers Technology no banco."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Exibe as operações sem salvar no banco.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Atualiza entradas existentes no banco (DecodeMap + ChipFamily).",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        overwrite = options["overwrite"]
        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))
        if overwrite:
            self.stdout.write(self.style.WARNING("⚠  OVERWRITE — entradas existentes serão atualizadas.\n"))

        try:
            with transaction.atomic():
                self._run(dry, overwrite)
                if dry:
                    raise DryRunAbort()
        except DryRunAbort:
            self.stdout.write(self.style.WARNING("\nDry run concluído. Nenhuma alteração salva."))

        if not dry:
            self.stdout.write(self.style.SUCCESS("\n✅  PieceMakers populada com sucesso."))
            try:
                from chips.engine import clear_engine_cache
                clear_engine_cache()
                self.stdout.write("   🗑  Cache do engine invalidado.")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))

    # ──────────────────────────────────────────────────────────────────────────

    def _run(self, dry, overwrite=False):
        from chips.models import Brand, ChipFamily, DecodeMap

        # ── Marca ─────────────────────────────────────────────────────────────
        pm, created = Brand.objects.get_or_create(
            name="PieceMakers",
            defaults={
                "code": "PMK",
                "notes": (
                    "Taiwan (Hsinchu) · Fundada 2006 · Fabless DRAM design. "
                    "Fundador: Tah-Kang Joseph Ting (>40 anos IC, >60 patentes). "
                    "Produtos: SDR/DDR/DDR2/DDR3/DDR3L/DDR4, PSRAM, KGD. "
                    "ISO 9001 e 14001. Representantes: China, Japão, França, Israel, Turquia. "
                    "Site: piecemakers.com.tw"
                ),
            },
        )
        self._log(created, "Marca", "PieceMakers", dry)

        # ══════════════════════════════════════════════════════════════════════
        # DecodeMap: PMF_DDR3_CAP — Densidade DDR3/DDR3L PieceMakers (PMF4xx / PMF5xx)
        # ══════════════════════════════════════════════════════════════════════
        #
        # Posição: pn[4:6] (5ª e 6ª posições, índice 0), comprimento 2 chars.
        #
        # Anatomia do PN PMF DDR3:
        #   P  M  F  [volt]  [dens]  [8]  [bus]  [rev]  B  R  -  [suffix]
        #   0  1  2     3     4-5     6    7-8     9    10 11
        #
        #   volt: 5=1.5V (DDR3) · 4=1.35V (DDR3L)
        #   dens (pn[4:6]): código log2 de Mbit da densidade
        #   bus  (pn[7:9]): 08=x8 · 16=x16
        #   rev  (pn[9]):   B/C/D/E/F/G = revisão de silício
        #   BR:             package FBGA (96FBGA para x16, 78FBGA para x8)
        #   suffix: velocidade/temperatura/grade (ex: KADN, KAIN, MBIN)
        #
        # Conversão Gb → MB (capacidade por die, campo usado pelo gateway):
        #   1Gb = 128MB · 2Gb = 256MB · 4Gb = 512MB
        #
        # Fontes:
        #   - piecemakers.com.tw/products/standard-dram/ ✓ (oficial, DDR3 2Gb listado)
        #   - glochip.com/ddr3/piecemakers.html ✓ (tabela completa com densidades explícitas):
        #       PMF510816DBR=1Gb/x16 · PMF511816EBR=2Gb/x16 · PMF512816CBR=4Gb/x16
        #   - Padrão confirmado: "1X" = log2(densidade em Gbit) × 10
        #       "10"=1Gb(2^10Mb) · "11"=2Gb(2^11Mb) · "12"=4Gb(2^12Mb)
        #
        ddr3_cap = [
            # char_key  val_primary  val_secondary
            ("10", "128MB", ""),  # 1Gb = 128MB por die
                                  # PMF510808DBR, PMF510816CBR/DBR/EBR — 1Gb
                                  # Fonte: glochip DDR3 table (PieceMakers Tier-2) ✓
                                  # Rentabilidade: 1Gb < ddr3_min_gbit(2Gb) → NÃO RENTÁVEL
            ("11", "256MB", ""),  # 2Gb = 256MB por die
                                  # PMF511808EBR (x8) · PMF511816EBR (x16) · PMF511816FBR (x16)
                                  # Fonte: glochip ✓ · Digilent Arty S7-50 (MT41K128M16 drop-in) ✓
                                  # Rentabilidade: 2Gb = ddr3_min_gbit → limiar mínimo RENTÁVEL
            ("12", "512MB", ""),  # 4Gb = 512MB por die
                                  # PMF512808CBR/DBR/EBR/FBR · PMF512816CBR/DBR/EBR/FBR
                                  # Fonte: glochip ✓
                                  # Rentabilidade: 4Gb > ddr3_min_gbit(2Gb) → RENTÁVEL
        ]
        self._bulk_map("PMF_DDR3_CAP", ddr3_cap, pm, dry, overwrite)

        # ── Famílias ──────────────────────────────────────────────────────────
        families = self._families(pm)
        created_count = updated_count = 0
        for fdata in families:
            prefix = fdata.pop("prefix")
            fam = ChipFamily.objects.filter(prefix=prefix).first()
            created = fam is None
            if created:
                fam = ChipFamily(prefix=prefix)

            brand_changed = (not created) and (fam.brand_id != pm.pk)
            changed = created or brand_changed
            if brand_changed:
                fam.doc_page = None
            if changed:
                fam.brand = pm
            for k, v in fdata.items():
                if getattr(fam, k, None) != v:
                    setattr(fam, k, v)
                    changed = True

            if changed:
                if not dry:
                    fam.save()
                if created:
                    created_count += 1
                    self._log(True, "Família", f"{prefix} — {fam.chip_type}/{fam.subtype}", dry)
                else:
                    updated_count += 1
                    self._log(False, "Família (atualizada)", f"{prefix} — {fam.chip_type}/{fam.subtype}", dry)

        self.stdout.write(
            f"\n  Famílias: {created_count} criadas, {updated_count} atualizadas."
        )

    # ──────────────────────────────────────────────────────────────────────────

    def _families(self, pm):
        """Retorna lista de dicts de famílias PieceMakers para upsert."""
        return [

            # ═══ DDR3 SDRAM 1.5V (PMF5xx) ═════════════════════════════════════
            #
            # Prefixo: PMF5 — 4 chars; maior prioridade que PMF (fallback 4 chars).
            # Chips: PMF510xxx (1Gb) · PMF511xxx (2Gb) · PMF512xxx (4Gb).
            # Decode de densidade: pn[4:6] via PMF_DDR3_CAP.
            # Interface (bus width) pn[7:9]: 08=x8 · 16=x16 — sem decode por mapa,
            #   registrado no tip. Preencher interface via fix_known_parts p/ PNs confirmados.
            # Package: 96FBGA (x16) · 78FBGA (x8).
            # Fontes: piecemakers.com.tw ✓ · glochip ✓ · Arty S7-50 (2Gb x16) ✓
            #
            dict(
                prefix="PMF5", chip_type="RAM", subtype="DDR3",
                interface="",
                is_emcp=False, active=True, priority=40,
                pn_length=None,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="PMF_DDR3_CAP",
                tip=(
                    "DDR3 SDRAM PieceMakers Technology, 1.5V (PMF5xx). "
                    "pn[4:6] = densidade: 10=1Gb(128MB) · 11=2Gb(256MB) · 12=4Gb(512MB). "
                    "pn[7:9] = barramento: 08=x8 · 16=x16. "
                    "pn[9] = revisão de silício: B/C/D/E/F/G. "
                    "Package: 96FBGA (x16) · 78FBGA (x8). "
                    "PMF511816EBR é drop-in compatível com Micron MT41K128M16XX-15E "
                    "(Digilent Arty S7-50 ✓). Suporta 1.35V apesar de ser nominalmente 1.5V. "
                    "Rentabilidade: 1Gb → NÃO RENTÁVEL; 2Gb/4Gb → RENTÁVEL (DDR3)."
                ),
            ),

            # ═══ DDR3L SDRAM 1.35V (PMF4xx) ═══════════════════════════════════
            #
            # Prefixo: PMF4 — 4 chars; maior prioridade que PMF (fallback).
            # Mesma estrutura posicional que PMF5, apenas tensão diferente.
            # Chips: PMF410xxx (1Gb) · PMF411xxx (2Gb) · PMF412xxx (4Gb).
            # PMF411816EBR-KAIN (2Gb, x16, 1.35V) — confirmado absunshine.com ✓.
            #
            dict(
                prefix="PMF4", chip_type="RAM", subtype="DDR3L",
                interface="",
                is_emcp=False, active=True, priority=40,
                pn_length=None,
                decode_cap_pos=4, decode_cap_len=2, decode_cap_map="PMF_DDR3_CAP",
                tip=(
                    "DDR3L SDRAM PieceMakers Technology, 1.35V low-voltage (PMF4xx). "
                    "Mesma estrutura posicional do PMF5 (DDR3 1.5V); só a tensão difere. "
                    "pn[4:6] = densidade: 10=1Gb(128MB) · 11=2Gb(256MB) · 12=4Gb(512MB). "
                    "pn[7:9] = barramento: 08=x8 · 16=x16. "
                    "pn[9] = revisão: B/C/D/E/F/G. "
                    "Package: 96FBGA (x16) · 78FBGA (x8). "
                    "Típico em notebooks e tablets que exigem baixa tensão. "
                    "Rentabilidade: 1Gb → NÃO RENTÁVEL; 2Gb/4Gb → RENTÁVEL (DDR3L=DDR3)."
                ),
            ),

            # ═══ PMF fallback (DDR3 genérico) ══════════════════════════════════
            #
            # Captura qualquer PMF não coberto por PMF4/PMF5 (ex: revisões futuras).
            # Routing apenas — sem decode posicional.
            # priority=70 (menor prioridade que PMF4/PMF5 que têm priority=40).
            #
            dict(
                prefix="PMF", chip_type="RAM", subtype="DDR3",
                interface="",
                is_emcp=False, active=True, priority=70,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                tip=(
                    "DDR3/DDR3L PieceMakers Technology — família genérica de fallback. "
                    "Cobre PNs PMF não reconhecidos por PMF4 (DDR3L) ou PMF5 (DDR3). "
                    "Sem decode posicional — verificar PN individualmente. "
                    "Estrutura: PMF[volt][dens][8][bus][rev]BR-[suffix]. "
                    "volt: 4=1.35V(DDR3L) · 5=1.5V(DDR3). dens: 10=1Gb · 11=2Gb · 12=4Gb. "
                    "bus: 08=x8 · 16=x16."
                ),
            ),

            # ═══ DDR4 SDRAM (PMA) ══════════════════════════════════════════════
            #
            # Família PMA = DDR4 PieceMakers.
            # Catálogo atual (2026): 4Gb apenas (PMA212508ABR=x8 · PMA212816ABR=x16).
            # Decode posicional não implementado — estrutura do PN DDR4 ainda não
            # totalmente confirmada em fontes Tier 1 para múltiplas densidades.
            # Routing apenas por ora: identifica o chip como DDR4 para triagem.
            # Fontes: piecemakers.com.tw ✓ · glochip ✓
            #
            dict(
                prefix="PMA", chip_type="RAM", subtype="DDR4",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                tip=(
                    "DDR4 SDRAM PieceMakers Technology (PMA). 1.2V. "
                    "Catálogo atual: 4Gb x8 (PMA212508ABR) · 4Gb x16 (PMA212816ABR). "
                    "Velocidades: 2133/2400/2666 Mbps. Package: 78FBGA (x8) · 96FBGA (x16). "
                    "Decode posicional pendente — estrutura PN DDR4 não totalmente confirmada. "
                    "Routing: classifica como DDR4 para bancada de triagem. "
                    "Adicionar KnownPart via fix_known_parts para PNs confirmados. "
                    "Rentabilidade: DDR4 qualquer densidade → RENTÁVEL (verifique ProfitabilityConfig)."
                ),
            ),

            # ═══ DDR2 SDRAM (PME) ══════════════════════════════════════════════
            #
            # Família PME = DDR2 PieceMakers. 1.8V. Geração morta (gen < 3 → NÃO RENTÁVEL).
            # Densidades: 128Mb · 256Mb · 512Mb · 1Gb.
            # Package: FBGA (60FBGA=x8, 84FBGA=x16) — "BR" no sufixo.
            # Estrutura: PME[8][07-10][4][08/16][rev]BR
            #   pn[3]="8" = 1.8V; pn[4:6]="07"-"10" = log2(density em Mb)
            # Routing apenas: NÃO RENTÁVEL independente da densidade.
            # Fonte: glochip (tabela completa) ✓
            #
            dict(
                prefix="PME", chip_type="RAM", subtype="DDR2",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                tip=(
                    "DDR2 SDRAM PieceMakers Technology (PME). 1.8V. Geração MORTA → NÃO RENTÁVEL. "
                    "Densidades: 128Mb/256Mb/512Mb/1Gb. Package: 60FBGA(x8) · 84FBGA(x16). "
                    "Estrutura: PME[8][07=128Mb·08=256Mb·09=512Mb·10=1Gb][4][08/16][rev]BR. "
                    "DDR2 gen < 3 → assess_profitability = NÃO RENTÁVEL. Destino: resíduo/moagem."
                ),
            ),

            # ═══ DDR SDRAM (PMD) ═══════════════════════════════════════════════
            #
            # Família PMD = DDR1 PieceMakers.
            # Tensões: PMD6xx = 1.8V · PMD7xx = 2.5V.
            # Densidades: 64Mb · 128Mb · 256Mb · 512Mb.
            # Package: TSOPII (sufixo TR em vez de BR).
            # Routing apenas: NÃO RENTÁVEL.
            # Fonte: glochip ✓ · piecemakers.com.tw ✓
            #
            dict(
                prefix="PMD", chip_type="RAM", subtype="DDR1",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                tip=(
                    "DDR SDRAM (DDR1) PieceMakers Technology (PMD). Geração MORTA → NÃO RENTÁVEL. "
                    "PMD6xx = 1.8V · PMD7xx = 2.5V. "
                    "Densidades: 64Mb/128Mb/256Mb/512Mb. Package: TSOPII (sufixo TR). "
                    "DDR1 gen < 3 → NÃO RENTÁVEL. Destino: resíduo/moagem."
                ),
            ),

            # ═══ SDRAM (PMS) ═══════════════════════════════════════════════════
            #
            # Família PMS = SDR SDRAM PieceMakers. 3.3V. Geração mais antiga — NÃO RENTÁVEL.
            # Densidades: 16Mb · 64Mb · 128Mb. Package: TSOPII (sufixo TR).
            # Fonte: piecemakers.com.tw ✓ · glochip ✓
            #
            dict(
                prefix="PMS", chip_type="RAM", subtype="SDRAM",
                interface="",
                is_emcp=False, active=True, priority=50,
                pn_length=None,
                decode_cap_pos=None, decode_cap_len=1, decode_cap_map="",
                tip=(
                    "SDR SDRAM PieceMakers Technology (PMS). 3.3V. Geração MAIS ANTIGA → NÃO RENTÁVEL. "
                    "Densidades: 16Mb/64Mb/128Mb. Package: TSOPII (sufixo TR). "
                    "Destino: resíduo/moagem."
                ),
            ),

        ]

    # ──────────────────────────────────────────────────────────────────────────

    def _bulk_map(self, map_name, entries, brand, dry, overwrite=False):
        from chips.models import DecodeMap
        created = updated = 0
        for char_key, val_primary, val_secondary in entries:
            obj, created_flag = DecodeMap.objects.get_or_create(
                map_name=map_name,
                char_key=char_key,
                brand=brand,
                defaults={"val_primary": val_primary, "val_secondary": val_secondary},
            )
            if created_flag:
                created += 1
                self._log(True, f"DecodeMap {map_name}", f"{char_key} → {val_primary}", dry)
            elif overwrite:
                changed = False
                if obj.val_primary != val_primary:
                    obj.val_primary = val_primary
                    changed = True
                if obj.val_secondary != val_secondary:
                    obj.val_secondary = val_secondary
                    changed = True
                if changed:
                    if not dry:
                        obj.save()
                    updated += 1
                    self._log(False, f"DecodeMap {map_name}", f"{char_key} → {val_primary} (atualizado)", dry)
        msg = f"  Mapa {map_name}: {created} criadas"
        if overwrite:
            msg += f", {updated} atualizadas"
        msg += "."
        self.stdout.write(msg)

    def _log(self, created, kind, name, dry):
        prefix = "[DRY] " if dry else ""
        action = "CRIADO" if created else "atualizado"
        icon = "✚" if created else "↻"
        self.stdout.write(f"  {prefix}{icon} {kind}: {name} ({action})")


class DryRunAbort(Exception):
    """Sinaliza o rollback controlado do dry run."""
    pass
