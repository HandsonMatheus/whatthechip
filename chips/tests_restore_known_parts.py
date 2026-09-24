"""
`restore_known_parts` × LARGURA (F5, 2026-09-24).

O comando de recuperação de desastre (regra de ouro 1b(d) do CLAUDE.md) grava
por `bulk_create`, que pula o portão do `clean()`. Backup anterior a 24/09 traz
a largura de barramento DENTRO do `interface` — 154 registros no seed, 3.539 no
Export de produção. Medido com o seed real, ANTES deste conserto:

* sem a trava da F5: restaurava os 596 e devolvia as 154 larguras ao
  `interface`, em silêncio (`bus_width` vazio em todos);
* com a trava: o `--commit` caía inteiro e restaurava ZERO — e o dry-run,
  antes, dizia "A criar: 596".

Agora o restore aplica a MESMA regra do backfill
(`normalize_convention.plano_largura`). As travas cobrem as duas camadas: o que
chega ao banco (script) e o que o dono lê antes de digitar `--commit` (saída).
"""
import json
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class RestoreKnownPartsLarguraTests(TestCase):

    def setUp(self):
        from chips.models import Brand
        Brand.objects.create(name="Samsung", code="SAM")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _roda(self, linhas, commit=False):
        caminho = os.path.join(self._tmp.name, "backup.json")
        with open(caminho, "w", encoding="utf-8") as fh:
            json.dump(linhas, fh)
        out = StringIO()
        call_command("restore_known_parts", caminho,
                     *(["--commit"] if commit else []), stdout=out)
        return out.getvalue()

    @staticmethod
    def _linha(pn, **campos):
        base = {"part_number": pn, "brand": "Samsung", "chip_type": "DDR3",
                "subtype": "DDR3", "capacity": "2Gb", "confidence": "confirmed"}
        base.update(campos)
        return base

    def _get(self, pn):
        from chips.models import KnownPart
        return KnownPart.objects.get(part_number=pn)

    # ── script: o que chega ao banco ─────────────────────────────────────
    def test_script_largura_pura_vai_para_o_bus_width(self):
        self._roda([self._linha("RST1", interface="x16")], commit=True)
        kp = self._get("RST1")
        self.assertEqual((kp.bus_width, kp.interface), ("x16", ""))

    def test_script_velocidade_vai_para_as_notes_e_nada_se_perde(self):
        """I5 — mover nunca apaga. A velocidade da Micron só existe ali."""
        self._roda([self._linha("RST2", interface="x16 @ 800MHz (1600MTPS)",
                                notes="Voltage: 1.5V"),
                    self._linha("RST3", interface="@ 1866MHz")], commit=True)
        a, b = self._get("RST2"), self._get("RST3")
        self.assertEqual((a.bus_width, a.interface), ("x16", ""))
        self.assertEqual(a.notes, "Voltage: 1.5V | Speed: 800MHz (1600MTPS)")
        self.assertEqual((b.bus_width, b.interface, b.notes), ("", "", "Speed: 1866MHz"))

    def test_script_protocolo_fica_onde_esta(self):
        """A versão do eMMC vale dinheiro (dono, 2026-08-27): não pode sumir."""
        self._roda([self._linha("RST4", chip_type="eMMC", subtype="", capacity="16GB",
                                interface="eMMC 5.1")], commit=True)
        kp = self._get("RST4")
        self.assertEqual((kp.interface, kp.bus_width), ("eMMC 5.1", ""))

    def test_script_sobra_restaura_como_estava_e_avisa(self):
        """'x16 (2 dies)': mover só a largura apagaria o '(2 dies)'. O banco aceita
        o valor (não é o token exato), então o registro volta como estava — e a
        saída diz qual, porque é decisão humana."""
        saida = self._roda([self._linha("RST5", interface="x16 (2 dies)")], commit=True)
        kp = self._get("RST5")
        self.assertEqual((kp.interface, kp.bus_width), ("x16 (2 dies)", ""))
        self.assertIn("SOBRA SEM DESTINO", saida)
        self.assertIn("RST5", saida)

    def test_script_token_exato_que_a_regra_nao_move_fica_FORA_e_o_resto_entra(self):
        """eMMC com 'x8' (CLASSE) e 'x16' com outra largura já gravada
        (CONTRADICAO): a regra não move, e o banco recusa o token exato. Esses
        dois ficam de fora — listados — e o resto do arquivo entra. Antes, um
        registro assim derrubava a restauração INTEIRA."""
        from chips.models import KnownPart
        saida = self._roda([
            self._linha("RST6", chip_type="eMMC", subtype="", capacity="16GB", interface="x8"),
            self._linha("RST7", interface="x16", bus_width="x8"),
            self._linha("RST8", interface="x16"),
        ], commit=True)
        self.assertFalse(KnownPart.objects.filter(part_number__in=["RST6", "RST7"]).exists())
        self.assertEqual(self._get("RST8").bus_width, "x16")
        self.assertIn("NÃO RESTAURADOS (2)", saida)
        for trecho in ("RST6", "RST7", "CLASSE NAO PERMITE", "CONTRADICAO"):
            self.assertIn(trecho, saida)

    # ── saída: o que o dono lê antes do --commit ──────────────────────────
    def test_interface_dry_run_diz_o_MESMO_que_o_commit_e_nao_grava(self):
        """O defeito que o seed mostrou: o dry-run prometia 596 e o commit
        entregava zero. Aqui o cabeçalho das duas rodadas tem de ser idêntico."""
        from chips.models import KnownPart
        linhas = [self._linha("RST9", interface="x16"),
                  self._linha("RST10", interface="x8 @ 800MHz"),
                  self._linha("RST11", chip_type="eMMC", subtype="", capacity="16GB",
                              interface="x8")]
        seco = self._roda(linhas)
        self.assertEqual(KnownPart.objects.count(), 0, "o dry-run GRAVOU")
        molhado = self._roda(linhas, commit=True)
        self.assertEqual(seco.splitlines()[0], molhado.splitlines()[0])
        self.assertIn("A criar: 2", seco.splitlines()[0])
        self.assertIn("NÃO restaurados: 1", seco.splitlines()[0])
        self.assertIn("largura no lugar certo — 2 dos 2 a criar", seco)
        self.assertEqual(KnownPart.objects.count(), 2)

    def test_interface_o_seed_REAL_restaura_inteiro_com_a_trava_no_ar(self):
        """O arquivo de verdade: 596 PNs, 154 com largura no `interface` (medido
        em 2026-09-24). Com a chips/0025 aplicada e sem o conserto, isto
        restaurava ZERO."""
        from django.conf import settings
        from chips.knowledge.convention import split_bus_width
        from chips.management.commands.restore_known_parts import _BRAND_ALIAS
        from chips.models import Brand, KnownPart
        caminho = os.path.join(settings.BASE_DIR, "seed_known_parts.json")
        with open(caminho, encoding="utf-8") as fh:
            linhas = json.load(fh)
        com_largura = sum(1 for r in linhas if split_bus_width(r.get("interface") or "")[0])
        self.assertEqual((len(linhas), com_largura), (596, 154),
                         "o seed mudou — reconfira os números deste teste")
        for i, nome in enumerate(sorted({_BRAND_ALIAS.get(r["brand"], r["brand"])
                                         for r in linhas})):
            Brand.objects.get_or_create(name=nome, defaults={"code": f"SEED{i:02d}"})
        out = StringIO()
        call_command("restore_known_parts", caminho, "--commit", stdout=out)
        self.assertIn("NÃO restaurados: 0", out.getvalue())
        self.assertEqual(KnownPart.objects.count(), 596)
        self.assertEqual(KnownPart.objects.exclude(bus_width="").count(), 154)
        sobrou = [kp.part_number for kp in KnownPart.objects.all()
                  if any(split_bus_width(kp.interface)[:2])]
        self.assertEqual(sobrou, [], "largura ficou no interface")
