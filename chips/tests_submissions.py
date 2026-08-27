# -*- coding: utf-8 -*-
"""
chips/tests_submissions.py — o canal de submissão × o banco
============================================================
Cadeado do bug de 2026-08-17 (dono): *"subi specs de PNs que já eram
confirmados e nada entrou"*. O ``submit_known_parts`` nunca rebaixa um PN
aprovado — isso está certo — mas a checagem vivia DENTRO do bloco do
``--commit``: o DRY-RUN não consultava o banco e dizia "13 válidos" para uma
submissão que ia gravar 12. A dívida ficava invisível e os LOTES herdavam
snapshot sem spec.

Os testes abaixo prendem as duas metades:
  · o dry-run TEM que enxergar o banco e nomear o que vai pular;
  · completar um aprovado é ADITIVO (só campo vazio), nunca sobrescreve,
    nunca rebaixa o status, exige fonte Tier-1 e é reversível.
"""
import json
import tempfile
from io import StringIO
from pathlib import Path

import yaml

from django.core.management import call_command
from django.test import TestCase

from chips.models import Brand, KnownPart


def _submissao(tmp: Path, nome: str, marca: str, partes: list) -> str:
    caminho = tmp / nome
    caminho.write_text(yaml.safe_dump(
        {"brand": marca, "known_parts": partes}, allow_unicode=True), encoding="utf-8")
    return str(caminho)


class SubmitKnownPartsTests(TestCase):
    """PN aprovado identity-only + submissão com spec = o caso do dono."""

    PN = "TESTKP0001-XY"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.brand = Brand.objects.create(name="MarcaTeste", code="MTS")

    def _aprovado(self, **campos):
        """Cria o registro LIVE (approved), identity-only por padrão."""
        return KnownPart.objects.create(
            part_number=self.PN, brand=self.brand, confidence="confirmed",
            review_status="approved", **campos)

    def _arquivo(self, **campos):
        base = {"part_number": self.PN, "chip_type": "eMMC", "capacity": "32GB",
                "confidence": "confirmed", "notes": "datasheet oficial (Tier-1)"}
        base.update(campos)
        return _submissao(self.tmp, "sub.yaml", "MarcaTeste", [base])

    # ── o furo original ────────────────────────────────────────────────────
    def test_dry_run_enxerga_o_banco(self):
        """ANTES: dry-run só validava schema e dizia "1 válido". Se ele não
        nomear o que vai PULAR, o erro volta na próxima submissão."""
        self._aprovado()
        out = StringIO()
        call_command("submit_known_parts", self._arquivo(), stdout=out)
        texto = out.getvalue()
        self.assertIn("COMPLEMENTO", texto)
        self.assertIn(self.PN, texto)
        self.assertIn("--fill-empty", texto)
        self.assertEqual(KnownPart.objects.get(part_number=self.PN).chip_type, "")

    def test_commit_sem_fill_empty_nao_toca_aprovado(self):
        """Comportamento de hoje PRESERVADO: sem a flag, aprovado não muda —
        mas agora o comando diz isso em voz alta."""
        self._aprovado()
        out = StringIO()
        call_command("submit_known_parts", self._arquivo(), commit=True, stdout=out)
        kp = KnownPart.objects.get(part_number=self.PN)
        self.assertEqual(kp.chip_type, "")
        self.assertEqual(kp.review_status, "approved")
        self.assertIn("--fill-empty", out.getvalue())

    def test_fill_empty_preenche_so_o_vazio(self):
        """Aditivo: preenche capacity (vazia) e NÃO sobrescreve chip_type."""
        self._aprovado(chip_type="eMMC")
        call_command("submit_known_parts", self._arquivo(chip_type="eMMC"),
                     commit=True, fill_empty=True, stdout=StringIO())
        kp = KnownPart.objects.get(part_number=self.PN)
        self.assertEqual(kp.capacity, "32GB")        # preencheu o vazio
        self.assertEqual(kp.chip_type, "eMMC")
        self.assertEqual(kp.review_status, "approved")   # NUNCA sai do ar

    def test_conflito_nunca_aplica_e_vira_relatorio(self):
        """Sobrescrever contradiz algo aprovado: não sai do CLI, vira arquivo."""
        self._aprovado(chip_type="eMMC", capacity="16GB")
        arquivo = self._arquivo(capacity="32GB")
        out = StringIO()
        call_command("submit_known_parts", arquivo, commit=True, fill_empty=True,
                     stdout=out)
        kp = KnownPart.objects.get(part_number=self.PN)
        self.assertEqual(kp.capacity, "16GB")            # banco intacto
        self.assertIn("CONFLITO", out.getvalue())
        relatorio = Path(f"{arquivo}.conflitos.yaml")
        self.assertTrue(relatorio.exists())
        dados = yaml.safe_load(relatorio.read_text(encoding="utf-8"))
        self.assertEqual(dados["conflitos"][0]["campos"][0]["banco"], "16GB")
        self.assertEqual(dados["conflitos"][0]["campos"][0]["arquivo"], "32GB")

    def test_sem_fonte_tier1_nao_completa(self):
        """Completar registro LIVE sem proveniência deixaria dado órfão."""
        self._aprovado()
        out = StringIO()
        call_command("submit_known_parts", self._arquivo(notes="", source_url=""),
                     commit=True, fill_empty=True, stdout=out)
        self.assertEqual(KnownPart.objects.get(part_number=self.PN).capacity, "")
        self.assertIn("SEM FONTE", out.getvalue())

    def test_lookup_usa_part_number_norm(self):
        """Antes o casamento era pelo part_number CRU: diferença de formatação
        fazia o comando achar que era PN novo (e bater na unique do _norm)."""
        KnownPart.objects.create(part_number="TESTKP 0002-XY", brand=self.brand,
                                 confidence="confirmed", review_status="approved")
        arquivo = _submissao(self.tmp, "norm.yaml", "MarcaTeste", [{
            "part_number": "TESTKP0002XY", "chip_type": "eMMC",
            "capacity": "64GB", "notes": "Tier-1"}])
        out = StringIO()
        call_command("submit_known_parts", arquivo, commit=True, fill_empty=True,
                     stdout=out)
        self.assertEqual(KnownPart.objects.filter(
            part_number__in=["TESTKP 0002-XY", "TESTKP0002XY"]).count(), 1)
        self.assertEqual(KnownPart.objects.get(
            part_number="TESTKP 0002-XY").capacity, "64GB")

    def test_revert_desfaz_o_complemento(self):
        self._aprovado()
        destino = str(self.tmp / "revert.json")
        call_command("submit_known_parts", self._arquivo(), commit=True,
                     fill_empty=True, backup=destino, stdout=StringIO())
        self.assertEqual(KnownPart.objects.get(part_number=self.PN).capacity, "32GB")
        call_command("submit_known_parts", revert=destino, stdout=StringIO())
        kp = KnownPart.objects.get(part_number=self.PN)
        self.assertEqual(kp.capacity, "")
        self.assertEqual(kp.chip_type, "")
        self.assertEqual(kp.review_status, "approved")
        self.assertTrue(json.load(open(destino)))       # log legível

    def test_pn_novo_continua_entrando_como_submitted(self):
        """Regressão do fluxo clássico: novo NUNCA entra aprovado."""
        call_command("submit_known_parts", self._arquivo(), commit=True,
                     fill_empty=True, stdout=StringIO())
        kp = KnownPart.objects.get(part_number=self.PN)
        self.assertEqual(kp.review_status, "submitted")
        self.assertEqual(kp.capacity, "32GB")


class AuditSubmissionsTests(TestCase):
    """O panorama read-only — a peça que torna a dívida visível de uma vez."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.brand = Brand.objects.create(name="MarcaAudit", code="MAU")

    def test_classifica_os_baldes(self):
        KnownPart.objects.create(part_number="AUD-VAZIO", brand=self.brand,
                                 confidence="confirmed", review_status="approved")
        KnownPart.objects.create(part_number="AUD-OK", brand=self.brand,
                                 confidence="confirmed", review_status="approved",
                                 chip_type="eMMC", capacity="8GB")
        KnownPart.objects.create(part_number="AUD-PEND", brand=self.brand,
                                 confidence="confirmed", review_status="submitted")
        _submissao(self.tmp, "a.yaml", "MarcaAudit", [
            {"part_number": "AUD-VAZIO", "chip_type": "eMMC", "capacity": "8GB",
             "notes": "Tier-1"},
            {"part_number": "AUD-OK", "chip_type": "eMMC", "capacity": "8GB"},
            {"part_number": "AUD-PEND", "chip_type": "eMMC"},
            {"part_number": "AUD-SUMIU", "chip_type": "eMMC"},
        ])
        out = StringIO()
        call_command("audit_submissions", dir=str(self.tmp), stdout=out)
        texto = out.getvalue()
        self.assertIn("MarcaAudit", texto)
        self.assertIn("AUD-VAZIO", texto)        # COMPLETA (a dívida)
        self.assertIn("AUD-SUMIU", texto)        # AUSENTE
        self.assertIn("COMPLETA", texto)
        # read-only de verdade
        self.assertEqual(KnownPart.objects.get(part_number="AUD-VAZIO").chip_type, "")

    def test_conflito_aparece_no_audit(self):
        KnownPart.objects.create(part_number="AUD-CONF", brand=self.brand,
                                 confidence="confirmed", review_status="approved",
                                 capacity="16GB")
        _submissao(self.tmp, "c.yaml", "MarcaAudit",
                   [{"part_number": "AUD-CONF", "capacity": "32GB"}])
        out = StringIO()
        call_command("audit_submissions", dir=str(self.tmp), stdout=out)
        self.assertIn("CONFLITO", out.getvalue())
        self.assertIn("AUD-CONF", out.getvalue())


class ResolveConflictsTests(TestCase):
    """A política POR CLASSE DE CAMPO (dono, 2026-08-17). O que prende aqui é o
    princípio: aplicar conflito em bloco degrada dado — em vários campos o BANCO
    (vindo das pipelines de import) é melhor que a submissão."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.brand = Brand.objects.create(name="MarcaConf", code="MCF")

    def _par(self, banco: dict, arquivo: dict, pn="CONF-0001"):
        kp = KnownPart.objects.create(part_number=pn, brand=self.brand,
                                      confidence="confirmed",
                                      review_status="approved", **banco)
        caminho = _submissao(self.tmp, "c.yaml", "MarcaConf",
                             [dict({"part_number": pn}, **arquivo)])
        return kp, caminho

    def _roda(self, **kw):
        out = StringIO()
        call_command("resolve_conflicts", dir=str(self.tmp), stdout=out, **kw)
        return out.getvalue()

    def test_preco_a_submissao_vence(self):
        kp, _ = self._par({"chip_type": "eMCP"}, {"chip_type": "MCP"})
        self._roda(commit=True)
        kp.refresh_from_db()
        self.assertEqual(kp.chip_type, "MCP")
        self.assertEqual(kp.review_status, "approved")   # não sai do ar

    def test_interface_fica_o_mais_especifico(self):
        """O caso real: o banco tinha 'x16 @ 800MHz (1600MTPS)' e o arquivo 'x16'
        — aplicar a submissão PERDERIA a velocidade."""
        kp, _ = self._par({"chip_type": "DDR3", "interface": "x16 @ 800MHz (1600MTPS)"},
                          {"chip_type": "DDR3", "interface": "x16"})
        self._roda(commit=True)
        kp.refresh_from_db()
        self.assertEqual(kp.interface, "x16 @ 800MHz (1600MTPS)")   # banco mantido

    def test_interface_aceita_quando_o_arquivo_e_mais_especifico(self):
        kp, _ = self._par({"chip_type": "eMMC", "interface": "eMMC 4.41"},
                          {"chip_type": "eMMC",
                           "interface": "e.MMC 4.41 (JESD84-A441)"})
        self._roda(commit=True)
        kp.refresh_from_db()
        self.assertEqual(kp.interface, "e.MMC 4.41 (JESD84-A441)")

    def test_notes_faz_merge_sem_perder_nenhum_lado(self):
        kp, _ = self._par({"notes": "Voltage: 1.8 VOLTS | Package: VFBGA"},
                          {"notes": "Identidade via API FBGA oficial (Tier-1)"})
        self._roda(commit=True)
        kp.refresh_from_db()
        self.assertIn("Voltage: 1.8 VOLTS", kp.notes)          # o do import
        self.assertIn("Identidade via API FBGA", kp.notes)     # o da submissão

    def test_source_url_do_arquivo_vai_pro_notes_e_a_url_do_banco_fica(self):
        """O campo é UMA url: concatenar quebraria o link."""
        kp, _ = self._par({"source_url": "psg_2h2014:K3KL9L90DM-MG", "notes": "do import"},
                          {"source_url": "https://semiconductor.samsung.com/x"})
        self._roda(commit=True)
        kp.refresh_from_db()
        self.assertEqual(kp.source_url, "psg_2h2014:K3KL9L90DM-MG")
        self.assertIn("https://semiconductor.samsung.com/x", kp.notes)

    def test_sem_precos_e_exclude(self):
        kp, _ = self._par({"chip_type": "eMCP", "notes": "do import"},
                          {"chip_type": "MCP", "notes": "da submissão"})
        self._roda(commit=True, sem_precos=True)
        kp.refresh_from_db()
        self.assertEqual(kp.chip_type, "eMCP")            # preço pulado
        self.assertIn("da submissão", kp.notes)           # texto aplicado
        texto = self._roda(commit=True, exclude="CONF-0001")
        self.assertIn("excluído pelo dono", texto)

    def test_dry_run_nao_grava_e_revert_desfaz(self):
        kp, _ = self._par({"chip_type": "eMCP"}, {"chip_type": "MCP"})
        self._roda()                                       # dry-run
        kp.refresh_from_db()
        self.assertEqual(kp.chip_type, "eMCP")
        destino = str(self.tmp / "rev.json")
        self._roda(commit=True, backup=destino)
        kp.refresh_from_db()
        self.assertEqual(kp.chip_type, "MCP")
        call_command("resolve_conflicts", revert=destino, stdout=StringIO())
        kp.refresh_from_db()
        self.assertEqual(kp.chip_type, "eMCP")

    def test_campo_vazio_nao_e_conflito(self):
        """Vazio é COMPLEMENTO (submit --fill-empty) — este comando não mexe."""
        kp, _ = self._par({"chip_type": ""}, {"chip_type": "MCP"})
        texto = self._roda(commit=True)
        kp.refresh_from_db()
        self.assertEqual(kp.chip_type, "")
        self.assertIn("Nenhum conflito", texto)


class AuditSemSpecsTests(TestCase):
    """Separar 'o registro está vazio' de 'aparece vazio na tela' é o ponto:
    quando a gramática decodifica, o engine completa na leitura e o conserto é
    resnapshot, não pesquisa."""

    def setUp(self):
        self.brand = Brand.objects.create(name="MarcaVazia", code="MVZ")

    def _roda(self, **kw):
        out = StringIO()
        call_command("audit_sem_specs", brand="MarcaVazia", stdout=out, **kw)
        return out.getvalue()

    def test_sem_familia_e_sem_spec_pede_pesquisa(self):
        KnownPart.objects.create(part_number="VAZIO-SEM-FAM", brand=self.brand,
                                 confidence="confirmed", review_status="approved")
        texto = self._roda()
        self.assertIn("VAZIO-SEM-FAM", texto)
        self.assertIn("PRECISA PESQUISA", texto)

    def test_com_tipo_mas_sem_capacidade_cai_em_so_tipo(self):
        KnownPart.objects.create(part_number="VAZIO-SO-TIPO", brand=self.brand,
                                 confidence="confirmed", review_status="approved",
                                 chip_type="eMMC")
        self.assertIn("SÓ TIPO", self._roda())

    def test_registro_com_capacidade_nao_aparece(self):
        KnownPart.objects.create(part_number="TEM-CAP", brand=self.brand,
                                 confidence="confirmed", review_status="approved",
                                 chip_type="eMMC", capacity="32GB")
        self.assertNotIn("TEM-CAP", self._roda())

    def test_e_read_only(self):
        kp = KnownPart.objects.create(part_number="RO-0001", brand=self.brand,
                                      confidence="confirmed", review_status="approved")
        self._roda()
        kp.refresh_from_db()
        self.assertEqual(kp.chip_type, "")
        self.assertEqual(kp.review_status, "approved")


class DeadlockSubmitResolveTests(TestCase):
    """O LAÇO entre `submit_known_parts --fill-empty` e `resolve_conflicts`.

    Relatado pelo dono em 2026-08-27 sobre 6 eMCP Micron MT29TZZZ7D7 (JZ050 e
    irmãos), com `emcp_nand`/`emcp_ram` vazios desde a importação FBGA. A
    sequência observada, e reproduzida aqui:

      1. submit --fill-empty  → CONFLITO só em `source_url`; nada preenchido
      2. resolve_conflicts    → não sobrescreve a url (é uma só); escreve um
                                marcador dentro de `notes`
      3. submit --fill-empty  → CONFLITO agora em `notes` E `source_url`

    Não era empate, era CATRACA: cada rodada do passo 2 ADICIONAVA um conflito.
    Causa raiz: os dois comandos não compartilhavam a definição de "conflito" —
    o `resolve_conflicts` tem política por classe (notes = merge, source_url =
    nunca sobrescreve), o `submit` comparava tudo por igualdade de string. Todo
    campo cuja política é "acumula" era, por construção, conflito PERMANENTE.
    """

    YAML = ("brand: Micron\n"
            "known_parts:\n"
            '  - part_number: "MT29TZZZ7D7DKLAH-107 W.9B7"\n'
            "    chip_type: eMCP\n"
            '    emcp_nand: "8GB"\n'
            '    emcp_ram: "LPDDR2 512MB"\n'
            "    confidence: confirmed\n"
            '    notes: "Pesquisa Tier-1: datasheet Micron MT29TZZZ7D7."\n'
            '    source_url: "https://www.micron.com/datasheet-jz050"\n')

    def _arquivo(self):
        import tempfile, os
        fd, p = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(self.YAML)
        self.addCleanup(lambda: os.path.exists(p) and os.unlink(p))
        return p

    def _kp(self, **extra):
        from chips.models import Brand, KnownPart
        b, _ = Brand.objects.get_or_create(name="Micron", defaults={"code": "MIC"})
        d = dict(brand=b, part_number="MT29TZZZ7D7DKLAH-107 W.9B7", chip_type="eMCP",
                 confidence="confirmed", review_status="approved",
                 source_url="https://api.micron.com/fbga/JZ050")
        d.update(extra)
        return KnownPart.objects.create(**d)

    def test_fill_empty_preenche_mesmo_com_source_url_divergente(self):
        """O caso do dono, passo 1: a url do banco (API FBGA) nunca vai bater com
        a do arquivo (datasheet). Isso NÃO pode impedir o complemento."""
        from django.core.management import call_command
        from chips.models import KnownPart
        kp = self._kp()
        call_command("submit_known_parts", self._arquivo(), "--commit", "--fill-empty")
        kp.refresh_from_db()
        self.assertEqual(kp.emcp_nand, "8GB")
        self.assertEqual(kp.emcp_ram, "LPDDR2 512MB")

    def test_fill_empty_preenche_DEPOIS_do_resolve_conflicts(self):
        """Passo 3 — o estado em que o registro ficava travado para sempre: o
        `notes` do banco é só o marcador que o `resolve_conflicts` escreveu, e o
        do arquivo é o texto de pesquisa inteiro. Nunca mais batem."""
        from django.core.management import call_command
        from chips.models import KnownPart
        kp = self._kp(notes="— (submissão) fonte: https://www.micron.com/datasheet-jz050")
        call_command("submit_known_parts", self._arquivo(), "--commit", "--fill-empty")
        kp.refresh_from_db()
        self.assertEqual(kp.emcp_nand, "8GB", "o laço voltou: campo vazio não foi preenchido")
        self.assertEqual(kp.emcp_ram, "LPDDR2 512MB")

    def test_conflito_de_DADO_continua_barrando_o_proprio_campo(self):
        """Afrouxar proveniência não pode afrouxar DADO. Capacidade divergente
        continua CONFLITO — e continua sem ser aplicada pelo comando."""
        from django.core.management import call_command
        from chips.models import KnownPart
        kp = self._kp(emcp_nand="4GB")          # banco diz 4GB, arquivo diz 8GB
        call_command("submit_known_parts", self._arquivo(), "--commit", "--fill-empty")
        kp.refresh_from_db()
        self.assertEqual(kp.emcp_nand, "4GB", "sobrescreveu valor aprovado divergente")
        self.assertEqual(kp.emcp_ram, "LPDDR2 512MB",
                         "o conflito em emcp_nand vetou o preenchimento do emcp_ram vazio")

    def test_divergir_SO_em_proveniencia_nao_e_conflito(self):
        """⚠ Este teste nasceu de uma MUTAÇÃO que não mordeu. As duas asserções
        de preenchimento acima passavam mesmo com a exclusão de proveniência
        REMOVIDA — porque o desacoplamento dos baldes, sozinho, já preenche.

        A exclusão de proveniência serve a outra coisa: o RELATO. Sem ela, um
        registro que só diverge em `notes`/`source_url` é reportado como
        CONFLITO para sempre e gera um `.conflitos.yaml` a cada rodada — um
        alarme que nunca apaga e que o dono aprende a ignorar. E ignorar
        CONFLITO é caro, porque é lá que mora o conflito de verdade."""
        from io import StringIO
        from django.core.management import call_command
        self._kp(emcp_nand="8GB", emcp_ram="LPDDR2 512MB",
                 notes="— (submissão) fonte: https://www.micron.com/datasheet-jz050")
        out = StringIO()
        call_command("submit_known_parts", self._arquivo(), stdout=out)
        import re as _re
        t = out.getvalue()
        def balde(nome):
            m = _re.search(rf"^\s*{nome}\s+(\d+)", t, _re.M)
            return int(m.group(1)) if m else 0
        self.assertEqual(balde("CONFLITO"), 0,
                         "reportou CONFLITO num registro que só diverge em "
                         "proveniência (notes/source_url)")
        self.assertEqual(balde("IGUAL"), 1,
                         "não classificou como IGUAL o registro que só diverge "
                         "em proveniência")
        self.assertEqual(balde("COMPLEMENTO"), 0)

    def test_painel_avisa_quando_o_PN_cai_nos_dois_baldes(self):
        from io import StringIO
        from django.core.management import call_command
        self._kp(emcp_nand="4GB")
        out = StringIO()
        call_command("submit_known_parts", self._arquivo(), stdout=out)
        t = out.getvalue()
        self.assertIn("DOIS baldes", t,
                      "o painel não avisou que o mesmo PN tem campo a completar E a decidir")
