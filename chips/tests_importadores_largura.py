# -*- coding: utf-8 -*-
"""Os importadores e a largura de barramento (PLANO_BUS_WIDTH §3.4).

Três importadores escreviam — ou podiam voltar a escrever — largura dentro do
`interface`. Cada um falhava de um jeito diferente, e é por isso que os testes
aqui são separados:

- **`import_micron_catalog`** montava ``"x32 @ 1866MHz"`` e entregava no
  `interface`. O `KnownPart.save()` chama `full_clean()`, então o portão da F2
  RECUSA — barulhento, mas o importador inteiro parava.
- **`import_chipid`** relê o banco legado do chipid_project, que é a ORIGEM dos
  ``x16`` das 25 famílias. Aqui o perigo é pior: `ChipFamily` **não** tem
  `save()` que chame `full_clean()`, então reimportar desfaria a Fase 4 **em
  silêncio**.
- **`import_samsung_psg`** *parecia* ter o mesmo defeito (copia a coluna
  `interface` do CSV), mas não tem: a coluna traz protocolo (``eMMC 5.1``,
  ``UFS 2.1``) ou geração (``DDR3``, ``LPDDR4X``), nunca um token de largura.
  O teste existe para que continue assim — se alguém puser ``x16`` num CSV
  novo, ele acende.
"""
from django.test import SimpleTestCase

from chips.knowledge.convention import interface_problem
from chips.management.commands.import_micron_catalog import (
    _build_bus_width, _build_speed,
)
from chips.management.commands.import_chipid import _reparte_interface
from chips.management.commands.import_samsung_psg import _bus_width_do_org


class MicronVelocidadeVaiParaNotesTests(SimpleTestCase):
    """A velocidade sai do `interface` e vira a string que o backfill produz."""

    def test_speed_e_mts_viram_uma_string_so(self):
        self.assertEqual(_build_speed("1866MHz", "3733MTPS"), "1866MHz (3733MTPS)")

    def test_mts_igual_a_speed_nao_duplica(self):
        self.assertEqual(_build_speed("800MHz", "800MHz"), "800MHz")

    def test_sem_velocidade_e_string_vazia(self):
        self.assertEqual(_build_speed("", ""), "")


class MicronLarguraNoVocabularioTests(SimpleTestCase):
    """O CSV da Micron passa pelo vocabulário fechado antes de virar `bus_width`."""

    def test_token_normal(self):
        self.assertEqual(_build_bus_width("x32", "RAM"), ("x32", ""))

    def test_maiuscula_e_normalizada(self):
        self.assertEqual(_build_bus_width("X16", "RAM")[0], "x16")

    def test_so_o_numero_ganha_o_x(self):
        self.assertEqual(_build_bus_width("16", "RAM")[0], "x16")

    def test_fora_do_vocabulario_nao_migra_e_da_motivo(self):
        largura, motivo = _build_bus_width("x12", "RAM")
        self.assertEqual(largura, "")
        self.assertIn("vocabul", motivo)

    def test_emmc_nao_recebe_largura(self):
        """Em eMMC a largura é modo do host (JESD84 EXT_CSD[183]), não o chip."""
        largura, motivo = _build_bus_width("x8", "eMMC")
        self.assertEqual(largura, "")
        self.assertIn("classe", motivo)

    def test_umcp_nao_recebe_largura(self):
        """uMCP tem DOIS barramentos — um campo só seria ambíguo."""
        self.assertEqual(_build_bus_width("x32", "uMCP")[0], "")

    def test_vazio_nao_e_problema(self):
        self.assertEqual(_build_bus_width("", "RAM"), ("", ""))


class ChipidRepartseOLegadoTests(SimpleTestCase):
    """O `interface` do banco legado é repartido, nunca copiado cru."""

    def test_largura_pura_sai_do_interface(self):
        interface, largura, _ = _reparte_interface("x16", "RAM", "")
        self.assertEqual((interface, largura), ("", "x16"))

    def test_largura_com_velocidade(self):
        interface, largura, notes = _reparte_interface("x8 @ 800MHz", "RAM", "")
        self.assertEqual((interface, largura), ("", "x8"))
        self.assertEqual(notes, "Speed: 800MHz")

    def test_protocolo_fica_intacto(self):
        self.assertEqual(
            _reparte_interface("eMMC 5.1", "eMMC", "")[:2], ("eMMC 5.1", ""),
        )

    def test_sobra_sem_destino_nao_migra(self):
        """`x16 (2 dies)`: migrar e descartar a sobra é apagar dado em silêncio."""
        self.assertEqual(
            _reparte_interface("x16 (2 dies)", "RAM", "")[:2], ("x16 (2 dies)", ""),
        )

    def test_classe_que_nao_admite_largura_nao_migra(self):
        self.assertEqual(_reparte_interface("x8", "eMMC", "")[:2], ("x8", ""))

    def test_notes_existentes_sao_preservadas(self):
        self.assertEqual(
            _reparte_interface("x16", "RAM", "Voltage: 1.5V")[2], "Voltage: 1.5V",
        )

    def test_notes_ganham_a_velocidade_sem_perder_o_que_havia(self):
        notes = _reparte_interface("x16 @ 800MHz", "RAM", "Voltage: 1.5V")[2]
        self.assertEqual(notes, "Voltage: 1.5V | Speed: 800MHz")


class SamsungPsgCsvNaoTemLarguraNoInterfaceTests(SimpleTestCase):
    """Trava de regressão: nenhum CSV do PSG pode trazer largura no `interface`.

    Este importador NÃO foi alterado — foi absolvido por medição. O teste lê os
    CSVs de verdade, então um arquivo novo com `x16` na coluna errada acende
    aqui em vez de ser recusado pelo portão na hora de importar.
    """

    def test_todo_valor_de_interface_dos_csvs_passa_pelo_portao(self):
        import csv
        import glob
        import os

        from django.conf import settings

        raiz = os.path.join(str(settings.BASE_DIR), "data", "psg")
        arquivos = sorted(glob.glob(os.path.join(raiz, "*.csv")))
        self.assertTrue(arquivos, f"nenhum CSV do PSG em {raiz}")

        ruins = []
        for caminho in arquivos:
            with open(caminho, newline="", encoding="utf-8") as f:
                for linha in csv.DictReader(f):
                    valor = (linha.get("interface") or "").strip()
                    if valor and interface_problem(valor) is not None:
                        ruins.append(f"{os.path.basename(caminho)}: {valor!r}")

        self.assertEqual(
            ruins, [],
            "CSV do PSG com largura na coluna `interface` — a largura vai para "
            "`bus_width`:\n  " + "\n  ".join(sorted(set(ruins))),
        )


class SamsungPsgOrganizationViraLarguraTests(SimpleTestCase):
    """A coluna `organization` do PSG é largura Tier-1 Samsung — nas DDR, só.

    Medido nos 18 CSVs em 2026-09-23: a coluna tem dois formatos e a divisão é
    exata. ``512Mx8`` (linhas × largura de um die) aparece SEMPRE e SÓ em
    DDR3/DDR3L/DDR4 — 86 linhas. ``2CH x16`` (canais × largura POR CANAL)
    aparece SEMPRE e SÓ em LPDDR — 136 linhas, e não se mapeia: um LPDDR de
    ``2CH x16`` não é comparável a um DDR3 ``x16``.
    """

    def test_organizacao_de_die_vira_largura(self):
        self.assertEqual(_bus_width_do_org("512Mx8", "DDR"), ("x8", ""))
        self.assertEqual(_bus_width_do_org("1Gx4", "DDR4"), ("x4", ""))
        self.assertEqual(_bus_width_do_org("128Mx16", "DDR"), ("x16", ""))

    def test_multicanal_do_lpddr_nao_vira_largura(self):
        """A armadilha: um `search` acharia 'x16' dentro de '4CH x16'."""
        for org in ("2CH x16", "1CH x32", "4CH x16"):
            largura, motivo = _bus_width_do_org(org, "LPDDR4")
            self.assertEqual(largura, "", f"{org} não podia virar largura de die")
            self.assertIn("multi-canal", motivo)

    def test_vazio_nao_e_problema(self):
        self.assertEqual(_bus_width_do_org("", "DDR"), ("", ""))

    def test_largura_fora_do_vocabulario_nao_migra(self):
        largura, motivo = _bus_width_do_org("512Mx12", "DDR")
        self.assertEqual(largura, "")
        self.assertIn("vocabul", motivo)

    def test_formato_estranho_nao_migra(self):
        largura, motivo = _bus_width_do_org("banana", "DDR")
        self.assertEqual(largura, "")
        self.assertIn("não reconhecido", motivo)

    def test_classe_que_nao_admite_largura_recusa(self):
        largura, motivo = _bus_width_do_org("512Mx8", "eMMC")
        self.assertEqual(largura, "")
        self.assertIn("classe", motivo)

    def test_os_csvs_reais_dao_86_larguras_e_nenhuma_de_lpddr(self):
        """Trava sobre os dados: 86 larguras, todas DDR; 136 LPDDR recusadas.

        Se um CSV novo entrar, este número muda — e é para mudar conscientemente,
        não por acidente. O que NÃO pode mudar é a segunda asserção: nenhuma
        largura pode nascer de uma linha LPDDR.
        """
        import csv
        import glob
        import os

        from django.conf import settings

        CT = {"DDR": "DDR", "LPDDR2": "LPDDR2", "LPDDR3": "LPDDR3",
              "LPDDR4": "LPDDR4", "LPDDR4X": "LPDDR4X", "LPDDR5": "LPDDR5",
              "LPDDR5X": "LPDDR5X", "eMMC": "eMMC", "UFS": "UFS",
              "eMCP": "eMCP", "uMCP": "uMCP"}

        raiz = os.path.join(str(settings.BASE_DIR), "data", "psg")
        mapeadas, recusadas, lpddr_mapeada = 0, 0, []
        for caminho in sorted(glob.glob(os.path.join(raiz, "*.csv"))):
            with open(caminho, newline="", encoding="utf-8") as f:
                for linha in csv.DictReader(f):
                    org = (linha.get("organization") or "").strip()
                    if not org:
                        continue
                    bruto = linha.get("chip_type", "")
                    largura, _ = _bus_width_do_org(org, CT.get(bruto, bruto))
                    if largura:
                        mapeadas += 1
                        if "LP" in bruto.upper():
                            lpddr_mapeada.append(f"{bruto}/{org}→{largura}")
                    else:
                        recusadas += 1

        self.assertEqual(
            lpddr_mapeada, [],
            "largura de die criada a partir de linha LPDDR (multi-canal): "
            + ", ".join(lpddr_mapeada),
        )
        self.assertEqual((mapeadas, recusadas), (86, 136))
