"""
fix_known_parts.py
===================
Corrige registros KnownPart com dados sujos vindos de distribuidores externos.

Cada entrada em CORRECTIONS define o part_number a corrigir e os campos a
atualizar. Campos com valor None são limpos (string vazia no banco).

Idempotente: pode ser rodado múltiplas vezes sem efeitos colaterais.

Uso:
    python manage.py fix_known_parts
    python manage.py fix_known_parts --dry-run    # mostra mudanças sem salvar
    python manage.py fix_known_parts --pn KMDP6001DA  # corrige só um PN
"""

from django.core.management.base import BaseCommand
from django.db import transaction


# ── Tabela de correções ───────────────────────────────────────────────────────
#
# Formato de cada entrada:
#   {
#     "pn":      "<part number exato>",
#     "fields":  { "<campo>": "<novo valor>" },   # None = limpar o campo
#     "reason":  "<explicação da correção>",
#   }
#
# Campos suportados: emcp_ram, emcp_nand, device, confidence, status
# ─────────────────────────────────────────────────────────────────────────────

CORRECTIONS = [

    # ── KMDP6001DA ────────────────────────────────────────────────────────────
    # Problema: banco continha dados do distribuidor Censtry (lixo).
    #   emcp_ram = "LPDDR4X 6GB"  → ERRADO. Datasheet: 32Gb ÷ 8 = 4GB.
    #   device   = "Galaxy MX6432" → ERRADO. Não existe esse celular.
    #              MX6432 é código interno Samsung do encapsulamento
    #              (64 = 64GB eMMC, 32 = 32Gb RAM). Fontes reais de uso:
    #              tablets e mid-range de terceiros (Oppo, Vivo, etc).
    # Correção: P6 agora mapeado no SAM_EMCP_CAP (populate_samsung.py).
    #           Este fix limpa o registro sujo para que a gramática vença
    #           na próxima classificação sem herdar a capacidade errada do DB.
    {
        "pn": "KMDP6001DA",
        "fields": {
            "emcp_ram": "LPDDR4X 4GB",
            "device":   "",             # limpar — "Galaxy MX6432" não existe
        },
        "reason": (
            "RAM corrigida: 32Gb ÷ 8 = 4GB (era 6GB do distribuidor Censtry). "
            "Device apagado: 'Galaxy MX6432' é código interno Samsung, não celular."
        ),
    },

    # ── KMQD60013M ───────────────────────────────────────────────────────────
    # Problema: banco continha dados do distribuidor Wolfchip (lixo).
    #   emcp_ram = "LPDDR3 2GB"  → ERRADO. Gramática: D6 = 32GB + 3GB.
    # Erro típico de catálogo asiático: confunde variantes de 2GB (cap "14")
    # com os de 3GB (cap "D6"). A gramática resolve D6 corretamente.
    # Após o fix do engine (distributor não vence gramática), a gramática já
    # vence sozinha. Esta entrada limpa o registro histórico no banco.
    {
        "pn": "KMQD60013M",
        "fields": {
            "emcp_ram": "LPDDR3 3GB",
        },
        "reason": (
            "RAM corrigida: D6 = 32GB eMMC + 3GB LPDDR3 (era 2GB do distribuidor Wolfchip). "
            "Erro típico de catálogo: confundiu variante de 2GB com D6=3GB."
        ),
    },

    # ── KMRNW0001M ───────────────────────────────────────────────────────────
    # Problema: banco continha resultado alucinado pelo Gemini (confidence=ai_high).
    #   emcp_nand = "eMMC 5.1 64GB" → ERRADO. NW = 8GB NAND (chip entry-level).
    #   emcp_ram  = "LPDDR4/4X 4GB" → ERRADO. NW = 1GB RAM.
    # NW é cap_key de chip entry-level (Galaxy A budget 2018-2019), destino resíduo.
    # Após adicionar NW ao SAM_EMCP_CAP, a gramática vence sozinha (grammar_wins=True).
    # Este fix limpa o registro alucinado para consistência histórica no banco.
    {
        "pn": "KMRNW0001M",
        "fields": {
            "emcp_nand": "eMMC 5.1 8GB",
            "emcp_ram":  "LPDDR4/4X 1GB",
            "device":    "",
        },
        "reason": (
            "Gemini alucinado: dizia eMMC 5.1 64GB + LPDDR4/4X 4GB. "
            "Correto: NW = 8GB NAND + 1GB RAM (chip entry-level, resíduo). "
            "NW adicionado ao SAM_EMCP_CAP — gramática resolve diretamente."
        ),
    },

    # ── KLUDG4U1EA ───────────────────────────────────────────────────────────
    # Problema: banco continha resultado alucinado pelo Gemini (confidence=ai_high)
    # com brand classificado como Kioxia (família KLUDG estava cadastrada errado
    # em add_chip_families.py como Kioxia). KLUDG é Samsung UFS 2.1.
    # Decodificação correta pela gramática:
    #   K=Samsung, L=NAND standalone, U=UFS, D=128GB (SAM_FLASH_CAP), G=TLC NAND,
    #   pn[6]='U' → UFS 2.1/3.0 → capacity = 128GB, interface = UFS 2.1.
    # Após populate_samsung --overwrite, a família KLUDG é migrada para brand=Samsung.
    # Este fix limpa campos que o Gemini pode ter preenchido incorretamente.
    {
        "pn": "KLUDG4U1EA",
        "fields": {
            "capacity": "128GB",
            "interface": "UFS 2.1",
            "device":    "",   # limpar device alucinado, se houver
        },
        "reason": (
            "Família KLUDG estava cadastrada como Kioxia (erro em add_chip_families.py). "
            "KLUDG é Samsung UFS 2.1: K=Samsung, L=NAND, U=UFS, D=128GB, pn[6]=U→UFS 2.1. "
            "fix: capacity=128GB, interface=UFS 2.1, device apagado. "
            "Família corrigida via populate_samsung --overwrite."
        ),
    },

    # ── K3KL9L90DMMGCU ───────────────────────────────────────────────────────
    # Problema: Gemini gravou capacity="16Gbit" (em Gbit, não GB — causaria
    # confusão de inventário: operador leria "16" e catalogaria como 16GB).
    # Octopart confirma: 512M × 32bits = 16Gb = 2GB.
    # Após adicionar 9L ao LPDDR5_CAP, a gramática resolve diretamente.
    {
        "pn": "K3KL9L90DMMGCU",
        "fields": {
            "capacity": "2GB",
        },
        "reason": (
            "capacity corrigido: Gemini gravou '16Gbit' (Gbit em vez de GB). "
            "Octopart: 512MX32 = 16Gb = 2GB. "
            "9L adicionado ao LPDDR5_CAP — gramática resolve diretamente."
        ),
    },

    # ── KM8V8001JM ───────────────────────────────────────────────────────────
    # Problema: cap_key V8 estava mapeado como 128GB+8GB no SAM_EMCP_CAP
    # (fonte: AI externa, sem confirmação de fabricante).
    # Fabricante confirma via KM5V8001DM-B622: V8 = 128GB UFS + 32Gb LPDDR4X.
    # 32Gb ÷ 8 = 4GB. Cap_key compartilhado → KM8V8001JM também é 4GB.
    # SAM_EMCP_CAP corrigido: V8 = "128GB" + "4GB".
    {
        "pn": "KM8V8001JM",
        "fields": {
            "emcp_nand": "UFS 128GB",
            "emcp_ram":  "LPDDR4X 4GB",
        },
        "reason": (
            "V8 corrigido: era 128GB+8GB (AI sem confirmação). "
            "Fabricante (KM5V8001DM-B622): 32Gb LPDDR4X ÷ 8 = 4GB. "
            "Cap_key V8 compartilhado no SAM_EMCP_CAP — ambos os chips são 4GB."
        ),
    },

    # ── KMGD6001BM ───────────────────────────────────────────────────────────
    # ⚠ REVERSAL 2026-05-09: a correção anterior estava ERRADA.
    #
    # Histórico:
    #   Distribuidor Jotrin tinha: emcp_nand="eMMC 32GB", emcp_ram="LPDDR3 3GB"
    #   Fix anterior "corrigiu" para: emcp_nand="UFS 3.1 32GB", emcp_ram="LPDDR4X 3GB"
    #   Razão do fix anterior: acreditava-se que KMG = uMCP UFS 3.1 + LPDDR4X.
    #
    # O que a evidência mostra agora:
    #   Datasheet KMGP6001BM confirma: KMG = eMCP eMMC 5.1 + LPDDR3.
    #   O distribuidor Jotrin estava CERTO no tipo (eMMC + LPDDR3).
    #   Família KMG corrigida em populate_samsung.py: chip_type=eMCP, decode_gen_pos=None.
    #   G em EMCP_RAM_TYPES = "LPDDR3" — confirma a família corretamente.
    #
    # D6 no SAM_EMCP_CAP = 32GB + 3GB (confirmado). Valores corretos abaixo.
    {
        "pn": "KMGD6001BM",
        "fields": {
            "emcp_nand": "eMMC 5.1 32GB",
            "emcp_ram":  "LPDDR3 3GB",
            "device":    "",
        },
        "reason": (
            "REVERSAL: fix anterior estava errado — KMG é eMCP eMMC 5.1 + LPDDR3, não uMCP UFS 3.1. "
            "Datasheet KMGP6001BM (2026-05-09) confirma a família. "
            "D6 = 32GB eMMC + 3GB LPDDR3 (SAM_EMCP_CAP, sem controvérsia). "
            "Device apagado: 'Galaxy A (MV3224)' é código interno Samsung — mantido."
        ),
    },

    # ── KMR8X0001M ───────────────────────────────────────────────────────────
    # Problema: SAM_EMCP_CAP tinha 8X = "8GB NAND + 1GB RAM" (ERRADO).
    # Confirmado 2026-05-09: KMR8X0001M-B608 = 16GB eMMC + 16Gb (2GB) LPDDR3.
    # Correção do mapa: 8X NAND corrigida de 8GB → 16GB.
    # RAM do mapa: 1GB (base KMQ8X). KMR8X tem 2GB — conflito de shared map.
    # Este fix corrige o registro histórico no banco para o valor real do KMR8X.
    {
        "pn": "KMR8X0001M",
        "fields": {
            "emcp_nand": "eMMC 5.1 16GB",
            "emcp_ram":  "LPDDR4/4X 2GB",
        },
        "reason": (
            "NAND corrigida: 8X era 8GB no mapa (ERRADO). KMR8X0001M-B608 = 16GB eMMC. "
            "RAM corrigida: 16Gb ÷ 8 = 2GB (mapa usa 1GB como base KMQ8X — divergência de família). "
            "8X no SAM_EMCP_CAP corrigido para 16GB NAND. "
            "KMQ8X000SA-B414 (1GB) e KMR8X0001M (2GB) confirmados em B2B (SBiT)."
        ),
    },

    # ── KMGP6001BM ───────────────────────────────────────────────────────────
    # Problema: SAM_EMCP_CAP["P6"] = 4GB (base KMDP6001DA-B425, família KMD/LPDDR4X).
    # KMG é família LPDDR3 — para KMG, P6 = 64GB eMMC + 24Gb LPDDR3 → 24Gb÷8 = 3GB.
    # Mesma divergência de shared cap_key que KMRX60014M (X6 base KM4=2GB vs KMR=4GB).
    # Datasheet KMGP6001BM confirma KMG = eMCP eMMC 5.1 + LPDDR3 ✓
    {
        "pn": "KMGP6001BM",
        "fields": {
            "emcp_nand": "eMMC 5.1 64GB",
            "emcp_ram":  "LPDDR3 3GB",
        },
        "reason": (
            "P6 no SAM_EMCP_CAP = 4GB (base KMDP6001DA-B425, família KMD/LPDDR4X). "
            "KMG é LPDDR3: P6 para KMG = 64GB eMMC + 24Gb LPDDR3 → 24Gb÷8=3GB. "
            "Divergência de cap_key compartilhado — override necessário para família KMG."
        ),
    },

    # ── KMRX60014M ───────────────────────────────────────────────────────────
    # Problema: SAM_EMCP_CAP mapeia X6 = "32GB NAND + 2GB RAM" (base KM4X6001KM).
    # KMRX60014M-B614 = 32GB eMMC 5.1 + 32Gb LPDDR4/4X → 32Gb ÷ 8 = 4GB.
    # Conflito de shared map: X6 base é 2GB (KM4X série), KMRX6 é 4GB (KMR série).
    # Este fix corrige o registro KMRX60014M para o valor real da família KMR.
    {
        "pn": "KMRX60014M",
        "fields": {
            "emcp_nand": "eMMC 5.1 32GB",
            "emcp_ram":  "LPDDR4/4X 4GB",
        },
        "reason": (
            "X6 base mapeado como 2GB (KM4X6001KM, Octopart). "
            "KMRX60014M-B614 = 32GB eMMC 5.1 + 32Gb LPDDR4/4X → 32Gb÷8=4GB. "
            "Divergência de família no shared cap_key X6: KM4X6→2GB, KMRX6→4GB. "
            "Override necessário para corrigir registro no banco."
        ),
    },

]


# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Corrige registros KnownPart com dados sujos de distribuidores."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Exibe as correções sem salvar no banco.",
        )
        parser.add_argument(
            "--pn",
            type=str,
            default=None,
            help="Corrige apenas o part number informado.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        target_pn = options["pn"]

        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        corrections = CORRECTIONS
        if target_pn:
            corrections = [c for c in CORRECTIONS if c["pn"] == target_pn]
            if not corrections:
                self.stdout.write(self.style.ERROR(f"PN '{target_pn}' não encontrado na tabela de correções."))
                return

        fixed = skipped = not_found = 0

        for entry in corrections:
            pn     = entry["pn"]
            fields = entry["fields"]
            reason = entry.get("reason", "")

            from chips.models import KnownPart
            try:
                obj = KnownPart.objects.get(part_number=pn)
            except KnownPart.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  ⚠ Não encontrado no banco: {pn}"))
                not_found += 1
                continue

            changed_fields = []
            for field, new_val in fields.items():
                old_val = getattr(obj, field, None)
                resolved = new_val if new_val is not None else ""
                if old_val != resolved:
                    changed_fields.append((field, old_val, resolved))
                    if not dry:
                        setattr(obj, field, resolved)

            if not changed_fields:
                self.stdout.write(f"  — {pn}: já correto, sem alterações.")
                skipped += 1
                continue

            if not dry:
                try:
                    with transaction.atomic():
                        obj.save()
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ✗ Erro ao salvar {pn}: {e}"))
                    continue

            prefix = "[DRY] " if dry else ""
            self.stdout.write(self.style.SUCCESS(f"  {prefix}✚ {pn} — {len(changed_fields)} campo(s) corrigido(s):"))
            for field, old, new in changed_fields:
                self.stdout.write(f"      {field}: {repr(old)} → {repr(new)}")
            if reason:
                self.stdout.write(f"      Motivo: {reason}")
            fixed += 1

        self.stdout.write(
            f"\n{'[DRY] ' if dry else ''}Resultado: {fixed} corrigido(s), "
            f"{skipped} já correto(s), {not_found} não encontrado(s) no banco."
        )
        if not dry and fixed:
            self.stdout.write(self.style.SUCCESS("\n✅  Correções aplicadas com sucesso."))
