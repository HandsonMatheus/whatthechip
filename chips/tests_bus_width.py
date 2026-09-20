"""
LARGURA DE BARRAMENTO separada do PROTOCOLO (2026-09, PLANO_BUS_WIDTH.md).

Até aqui o campo `interface` guardava DUAS coisas — 'eMMC 5.1' (versão do
protocolo) e 'x16' (largura do barramento de dados) — de forma consistente e
por decisão de projeto. O que mudou foi o negócio: o comprador revelou em
13-14/09 que a largura muda PREÇO, CAIXA e RENTABILIDADE (chip de 78 bolas de
DDR3 1Gb ele simplesmente recusa), e um campo que guarda duas coisas não pode
virar eixo de preço.

Estas travas cobrem a FUNDAÇÃO: o parser, os dois portões e a precedência no
engine. O que elas protegem, em uma frase cada:

* `SplitBusWidthTests` — a sobra nunca evapora. 'x16 (2 dies)' não migra.
* `InterfaceNaoELarguraTests` — o portão rejeita largura em `interface`, MAS
  perdoa o legado inalterado (3.539 registros esperam o backfill; sem o
  grandfather, todo re-save quebraria antes da migração acontecer).
* `BusWidthClassePermitidaTests` — deny by default. eMMC não tem largura de
  dispositivo: em eMMC ela é MODO do host (JESD84, EXT_CSD[183]).
* `EngineBusWidthTests` — a precedência, que é onde mora a circularidade:
  banco confirmado > gramática > família > banco não-confirmado.
"""

from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from unittest.mock import patch

from chips.conventions import BUS_WIDTH_VOCAB, is_bus_width, width_class_of
from chips.knowledge.convention import (bus_width_problem, interface_problem,
                                        interface_sem_largura, split_bus_width)


class SplitBusWidthTests(SimpleTestCase):
    """A tabela do PLANO_BUS_WIDTH §3.4, linha a linha.

    ⚠ A linha que mais importa é a da SOBRA: 'x16 (2 dies)' devolve resto
    não-vazio, e quem chama NÃO migra. Migrar e descartar o '(2 dies)' é o erro
    que o CLAUDE.md §7 chama de "dado apagado em silêncio" — e foi exatamente
    o que quase aconteceu com a velocidade da Micron, que só existe no
    `interface` e em lugar nenhum mais.
    """

    def test_tabela_do_plano(self):
        casos = [
            ("x16",                       ("x16", "", "")),
            ("X16",                       ("x16", "", "")),          # caixa
            ("  x16  ",                   ("x16", "", "")),          # espaço
            ("x16 @ 800MHz (1600MTPS)",   ("x16", "800MHz (1600MTPS)", "")),
            ("x32 @ 1866MHz",             ("x32", "1866MHz", "")),
            ("@ 1866MHz (3733MTPS)",      ("", "1866MHz (3733MTPS)", "")),
            ("x16 (2 dies)",              ("x16", "", "(2 dies)")),  # SOBRA
            ("eMMC 5.1",                  ("", "", "eMMC 5.1")),
            ("UFS 3.1",                   ("", "", "UFS 3.1")),
            ("Async/ONFI",                ("", "", "Async/ONFI")),
            ("NAND (x8/x16)",             ("", "", "NAND (x8/x16)")),
            ("x8x16",                     ("", "", "x8x16")),
            ("x 16",                      ("", "", "x 16")),
            ("16x",                       ("", "", "16x")),
            ("DDR4",                      ("", "", "DDR4")),
            ("",                          ("", "", "")),
            (None,                        ("", "", "")),
        ]
        for entrada, esperado in casos:
            with self.subTest(entrada=entrada):
                self.assertEqual(split_bus_width(entrada), esperado)

    def test_sobra_desconhecida_NAO_e_migravel(self):
        """Quem chama decide pelo `resto`: não-vazio = não migra, reporta."""
        largura, velocidade, resto = split_bus_width("x16 (2 dies)")
        self.assertEqual(largura, "x16")
        self.assertTrue(resto, "a sobra sumiu — quem chamar vai migrar e apagar")

    def test_is_bus_width_e_fullmatch_nunca_search(self):
        """É a regra que este projeto pagou TRÊS vezes (CLAUDE.md §7): para
        DECIDIR se uma string é token de vocabulário, `fullmatch`; `search` só
        serve para EXTRAIR de string já validada."""
        for bom in BUS_WIDTH_VOCAB:
            self.assertTrue(is_bus_width(bom))
        self.assertTrue(is_bus_width(" X8 "))                   # tolerante na leitura
        for ruim in ("x8 @ 800MHz", "x2", "x128", "DDR4", "x8x16", "", None):
            self.assertFalse(is_bus_width(ruim), f"{ruim!r} passou")

    def test_interface_sem_largura_descarta_a_largura_e_preserva_protocolo(self):
        self.assertEqual(interface_sem_largura("x16"), "")
        self.assertEqual(interface_sem_largura("x16 @ 800MHz"), "")
        self.assertEqual(interface_sem_largura("eMMC 5.1"), "eMMC 5.1")
        self.assertEqual(interface_sem_largura(""), "")

    def test_width_class_of(self):
        self.assertEqual(width_class_of("x4"), "narrow")
        self.assertEqual(width_class_of("x8"), "narrow")
        self.assertEqual(width_class_of("X16"), "wide")
        # x32/x64 não existem em DDR discreta neste mercado — dar classe a eles
        # seria inventar mercado.
        for vazio in ("x32", "x64", "", None, "lixo"):
            self.assertEqual(width_class_of(vazio), "")


class BusWidthClassePermitidaTests(SimpleTestCase):
    """DENY BY DEFAULT — a classe do chip decide se largura faz sentido."""

    def test_dram_e_nand_cru_aceitam(self):
        for ct in ("DDR3", "DDR4", "LPDDR4X", "GDDR5", "SDRAM", "NAND Flash"):
            self.assertIsNone(bus_width_problem(ct, "x16"), f"{ct} recusou")

    def test_gerenciado_recusa(self):
        """eMMC: a largura é MODO do host (JESD84, EXT_CSD[183]) — todo eMMC
        suporta 1/4/8 bits, então ela não identifica o dispositivo.
        eMCP/uMCP: o pacote tem DOIS barramentos; um campo só seria ambíguo."""
        for ct in ("eMMC", "UFS", "eMCP", "uMCP"):
            msg = bus_width_problem(ct, "x8")
            self.assertIsNotNone(msg, f"{ct} aceitou largura")
            self.assertIn("vazio", msg.lower())

    def test_chip_type_vazio_e_FAIL_OPEN(self):
        """Identity-only defere à gramática — mesma doutrina do
        `family_type_conflict`. Barrar aqui quebraria submissão legítima."""
        self.assertIsNone(bus_width_problem("", "x8"))

    def test_fora_do_vocabulario_recusa_mesmo_em_classe_boa(self):
        msg = bus_width_problem("DDR3", "x2")
        self.assertIsNotNone(msg)
        self.assertIn("vocabulário", msg)

    def test_vazio_sempre_passa(self):
        for ct in ("DDR3", "eMMC", ""):
            self.assertIsNone(bus_width_problem(ct, ""))


class InterfaceProblemTests(SimpleTestCase):
    """A mensagem que o chat de marca lê no dry-run (decisão D3)."""

    def test_largura_em_interface_e_rejeitada_com_mensagem_acionavel(self):
        msg = interface_problem("x16")
        self.assertIsNotNone(msg)
        self.assertIn("bus_width", msg, "a mensagem não ensina o conserto")

    def test_largura_mais_velocidade_cita_as_DUAS_mudancas(self):
        msg = interface_problem("x16 @ 800MHz (1600MTPS)")
        self.assertIn("bus_width", msg)
        self.assertIn("notes", msg, "não disse para onde vai a velocidade")

    def test_protocolo_com_numero_passa(self):
        """'eMMC 5.1' tem número e não pode ser confundido com largura — o
        casamento é ancorado no início E no vocabulário fechado."""
        for ok in ("eMMC 5.1", "UFS 3.1", "Async/ONFI", "NAND (x8/x16)", ""):
            self.assertIsNone(interface_problem(ok), f"{ok!r} foi rejeitado")


class InterfaceNaoELarguraTests(TestCase):
    """O portão no MODELO — e o grandfather, que é o que o torna aplicável.

    Sem o perdão do legado inalterado, o re-save de qualquer um dos 3.539
    registros que ainda têm largura em `interface` quebraria: `resnapshot_lote`,
    `bless_base` e o PRÓPRIO backfill travariam antes de a migração acontecer.
    """

    def setUp(self):
        from chips.models import Brand
        self.marca = Brand.objects.create(name="TesteBW", code="TBW")

    def _kp(self, **kw):
        from chips.models import KnownPart
        base = dict(brand=self.marca, part_number="TBW0001", chip_type="DDR3",
                    confidence="confirmed", review_status="approved")
        base.update(kw)
        return KnownPart(**base)

    def test_registro_NOVO_com_largura_em_interface_e_rejeitado(self):
        with self.assertRaises(ValidationError) as ctx:
            self._kp(interface="x16").save()
        self.assertIn("bus_width", str(ctx.exception.message_dict))

    def test_legado_INALTERADO_continua_re_salvavel(self):
        """GRANDFATHER. Grava por baixo do portão (como o legado entrou), depois
        re-salva mexendo em OUTRO campo: tem de passar."""
        from chips.models import KnownPart
        kp = self._kp(interface="x16")
        KnownPart.objects.bulk_create([kp])          # pula clean(), como o legado
        kp = KnownPart.objects.get(part_number="TBW0001")
        kp.device = "Galaxy J5"
        kp.save()                                     # NÃO pode levantar
        kp.refresh_from_db()
        self.assertEqual(kp.interface, "x16", "o portão apagou legado que não devia")

    def test_MUDAR_o_interface_legado_PARA_outra_largura_e_rejeitado(self):
        """O perdão é do valor inalterado, não do campo."""
        from chips.models import KnownPart
        KnownPart.objects.bulk_create([self._kp(interface="x16")])
        kp = KnownPart.objects.get(part_number="TBW0001")
        kp.interface = "x8"
        with self.assertRaises(ValidationError):
            kp.save()

    def test_esvaziar_o_interface_legado_e_PERMITIDO(self):
        """É exatamente o que o backfill da F3 faz — se isto travar, a migração
        não roda."""
        from chips.models import KnownPart
        KnownPart.objects.bulk_create([self._kp(interface="x16")])
        kp = KnownPart.objects.get(part_number="TBW0001")
        kp.interface, kp.bus_width = "", "x16"
        kp.save()
        kp.refresh_from_db()
        self.assertEqual((kp.interface, kp.bus_width), ("", "x16"))

    def test_bus_width_NAO_tem_grandfather(self):
        """Campo novo, sem legado a perdoar: a regra de CLASSE valida SEMPRE.

        ⚠ A 1ª versão deste teste tentava plantar `bus_width='x2'` por
        `bulk_create` — e não conseguiu: a CheckConstraint barra fora do
        vocabulário até por essa porta. Ou seja, largura INVÁLIDA é impossível
        de existir no banco, e testar o perdão dela seria testar o nada. O que
        de fato pode existir é largura VÁLIDA na classe ERRADA — a regra de
        classe (I3) mora só no `clean()`, não no banco. É esse o caso real."""
        from chips.models import KnownPart
        KnownPart.objects.bulk_create([self._kp(chip_type="eMMC", bus_width="x8")])
        kp = KnownPart.objects.get(part_number="TBW0001")
        kp.device = "qualquer"                     # mexe em OUTRO campo
        with self.assertRaises(ValidationError) as ctx:
            kp.save()                              # sem perdão: rejeita mesmo assim
        self.assertIn("bus_width", str(ctx.exception.message_dict))

    def test_largura_fora_do_vocabulario_e_impossivel_ate_por_bulk_create(self):
        """O corolário do teste acima, explícito: nem `bulk_create` fura."""
        from django.db import IntegrityError
        from chips.models import KnownPart
        with self.assertRaises(IntegrityError):
            KnownPart.objects.bulk_create([self._kp(bus_width="x2")])

    def test_normaliza_a_caixa_antes_de_gravar(self):
        kp = self._kp(bus_width="X16")
        kp.save()
        kp.refresh_from_db()
        self.assertEqual(kp.bus_width, "x16")

    def test_o_BANCO_barra_mesmo_sem_passar_pelo_clean(self):
        """`.update()` de queryset não chama save() nem clean() — é por onde
        entrou metade do legado deste projeto. A CheckConstraint pega."""
        from django.db import IntegrityError
        from chips.models import KnownPart
        kp = self._kp(bus_width="x8")
        kp.save()
        with self.assertRaises(IntegrityError):
            KnownPart.objects.filter(pk=kp.pk).update(bus_width="x2")

    def test_vocabulario_da_constraint_ESPELHA_a_fonte_unica(self):
        """Se alguém acrescentar uma largura em BUS_WIDTH_VOCAB e esquecer a
        constraint (ou o contrário), este teste morde. É a lição das quatro
        quebras da origem do lote: vocabulário fechado tem UM dono."""
        from chips.models import ChipFamily, KnownPart
        for modelo in (KnownPart, ChipFamily):
            cons = [c for c in modelo._meta.constraints
                    if c.name.endswith("_bus_width_vocab")]
            self.assertEqual(len(cons), 1, f"{modelo.__name__} sem a constraint")
            self.assertIn(("",) + BUS_WIDTH_VOCAB, list(cons[0].condition.children[0]),
                          f"{modelo.__name__}: a constraint divergiu do vocabulário")


class ChipFamilyPortaoTests(TestCase):
    """A família não tinha `clean()` — o admin escrevia nela sem portão nenhum."""

    def setUp(self):
        from chips.models import Brand
        self.marca = Brand.objects.create(name="TesteFam", code="TFM")

    def _fam(self, **kw):
        from chips.models import ChipFamily
        base = dict(brand=self.marca, prefix="TFM", chip_type="DDR3")
        base.update(kw)
        return ChipFamily(**base)

    def test_largura_em_interface_e_rejeitada(self):
        with self.assertRaises(ValidationError):
            self._fam(interface="x16").full_clean()

    def test_bus_width_em_familia_gerenciada_e_rejeitada(self):
        with self.assertRaises(ValidationError):
            self._fam(chip_type="eMMC", bus_width="x8").full_clean()

    def test_decode_width_pos_SEM_map_e_rejeitado(self):
        """Posição sozinha não decodifica nada — e a metade declarada daria a
        impressão de que a família tem gramática de largura quando não tem."""
        with self.assertRaises(ValidationError) as ctx:
            self._fam(decode_width_pos=5).full_clean()
        self.assertIn("decode_width_map", str(ctx.exception.message_dict))

    def test_os_dois_vazios_passam(self):
        self._fam().full_clean()


class EngineBusWidthTests(TestCase):
    """A PRECEDÊNCIA: banco confirmado > gramática > família > banco não-confirmado.

    Esta ordem não é estética — é o que impede a circularidade do coletor
    (HANDOFF §3). A regra posicional só é confiável porque foi cruzada contra
    uma fonte INDEPENDENTE (o datasheet, via banco). Se a gramática pudesse
    vencer um registro confirmado, a prova viraria a regra concordando consigo
    mesma, e ninguém perceberia: errado com aparência de verificado.

    ⚠ As fixturas usam prefixo e mapa que NÃO existem no mundo real (ZZW…), pela
    lição do CLAUDE.md §7: teste preso a um dado real cai quando o dado é
    consertado.
    """

    def setUp(self):
        from chips.models import Brand, ChipFamily, DecodeMap
        self.marca = Brand.objects.create(name="TesteEng", code="TEN")
        # Mapa de largura inventado: chave de 2 chars na posição 3.
        for chave, largura in (("AA", "x8"), ("BB", "x16"), ("CC", "x4")):
            DecodeMap.objects.create(map_name="ZZW_WIDTH", char_key=chave,
                                     val_primary=largura, val_secondary="",
                                     brand=self.marca)
        self.fam_gram = ChipFamily.objects.create(
            brand=self.marca, prefix="ZZWG", chip_type="DDR3", subtype="DDR3",
            decode_width_pos=4, decode_width_len=2, decode_width_map="ZZW_WIDTH")
        self.fam_fixa = ChipFamily.objects.create(
            brand=self.marca, prefix="ZZWF", chip_type="DDR3", subtype="DDR3",
            bus_width="x16")
        self.fam_muda = ChipFamily.objects.create(
            brand=self.marca, prefix="ZZWM", chip_type="DDR3", subtype="DDR3")

    def _kp(self, pn, **kw):
        from chips.models import KnownPart
        base = dict(brand=self.marca, part_number=pn, chip_type="DDR3",
                    subtype="DDR3", confidence="confirmed",
                    review_status="approved", capacity="256MB")
        base.update(kw)
        return KnownPart.objects.create(**base)

    def _c(self, pn):
        from chips.engine import classify
        return classify(pn)

    # ── família ──────────────────────────────────────────────────────────
    def test_familia_com_largura_fixa_aparece_no_resultado(self):
        r = self._c("ZZWF000000")
        self.assertEqual(r["bus_width"], "x16")
        self.assertEqual(r["bus_width_source"], "familia")

    def test_familia_sem_largura_devolve_vazio_e_sem_procedencia(self):
        r = self._c("ZZWM000000")
        self.assertEqual(r["bus_width"], "")
        self.assertEqual(r["bus_width_source"], "")

    # ── gramática ────────────────────────────────────────────────────────
    def test_gramatica_decodifica_a_largura_do_PN(self):
        r = self._c("ZZWGAA0000")           # pos 4-5 = 'AA' → x8
        self.assertEqual(r["bus_width"], "x8")
        self.assertEqual(r["bus_width_source"], "gramatica")

    def test_chave_fora_do_mapa_nao_inventa_largura(self):
        r = self._c("ZZWGZZ0000")           # 'ZZ' não está no mapa
        self.assertEqual(r["bus_width"], "")

    def test_valor_do_mapa_fora_do_vocabulario_e_IGNORADO(self):
        """Mapa é dado editável no admin. Se alguém puser 'x2' ou 'DDR4' ali, o
        engine não pode repassar lixo para o campo que vai virar eixo de preço."""
        from chips.models import DecodeMap
        DecodeMap.objects.create(map_name="ZZW_WIDTH", char_key="DD",
                                 val_primary="x2", val_secondary="", brand=self.marca)
        r = self._c("ZZWGDD0000")
        self.assertEqual(r["bus_width"], "", "largura fora do vocabulário passou")

    # ── o cruzamento: quem vence quem ────────────────────────────────────
    def test_banco_CONFIRMADO_vence_a_familia(self):
        self._kp("ZZWF111111", bus_width="x8")
        r = self._c("ZZWF111111")
        self.assertEqual(r["bus_width"], "x8")
        self.assertEqual(r["bus_width_source"], "banco")

    def test_banco_CONFIRMADO_vence_a_GRAMATICA(self):
        """O caso que protege contra o K4N: a regra diz uma coisa, o datasheet
        diz outra, e é o datasheet que manda."""
        self._kp("ZZWGAA1111", bus_width="x16")     # gramática diria x8
        r = self._c("ZZWGAA1111")
        self.assertEqual(r["bus_width"], "x16")
        self.assertEqual(r["bus_width_source"], "banco")

    def test_distribuidor_NAO_vence_a_familia_so_COMPLEMENTA(self):
        """Visibilidade não é autoridade (regra de ouro #2/#6): dado de
        distribuidor erra capacidade e tipo com frequência."""
        self._kp("ZZWF222222", bus_width="x8", confidence="distributor")
        r = self._c("ZZWF222222")
        self.assertEqual(r["bus_width"], "x16", "distributor sobrepôs a família")
        self.assertEqual(r["bus_width_source"], "familia")

    def test_distribuidor_PREENCHE_quando_ninguem_mais_sabe(self):
        self._kp("ZZWM333333", bus_width="x8", confidence="distributor")
        r = self._c("ZZWM333333")
        self.assertEqual(r["bus_width"], "x8")
        self.assertEqual(r["bus_width_source"], "banco")

    # ── gerenciado ───────────────────────────────────────────────────────
    def test_emcp_nao_carrega_largura(self):
        from chips.models import ChipFamily
        ChipFamily.objects.create(brand=self.marca, prefix="ZZWE",
                                  chip_type="eMCP", subtype="LPDDR4",
                                  is_emcp=True)
        r = self._c("ZZWE000000")
        self.assertEqual(r["bus_width"], "")

    # ── a chave inteira ──────────────────────────────────────────────────
    def test_todo_caminho_CLASSIFICADO_traz_as_duas_chaves(self):
        """Família, gramática e banco: os três devolvem as chaves."""
        for pn in ("ZZWF000000", "ZZWM000000", "ZZWGAA0000"):
            r = self._c(pn)
            with self.subTest(pn=pn):
                self.assertIn("bus_width", r)
                self.assertIn("bus_width_source", r)

    def test_PN_desconhecido_devolve_resultado_REDUZIDO_sem_as_chaves(self):
        """⚠ ACHADO ao escrever esta trava (2026-09-20), e vale documentar.

        PN que não casa família nenhuma NÃO passa por `_result_from_family`: sai
        um dicionário REDUZIDO, sem `bus_width` — e sem `interface`, `capacity`
        ou `chip_type` também. Não é regressão da largura, é como o caminho
        sempre foi.

        Quem cobre isso é o `setdefault` do `estoque/views.py`, porque o
        template acessa esses campos como ARGUMENTO de filtro
        (`default:result.capacity`), onde a resolução é ESTRITA e chave faltando
        derruba o preview com 500 — foi o bug de 2026-08-05. O teste do outro
        lado (`SnapshotBusWidthTests`) prova que a largura entrou naquela tupla.

        Este teste existe para FIXAR o comportamento: se um dia o reduzido
        passar a trazer as chaves, ótimo — mas que seja por decisão, não por
        acidente."""
        r = self._c("PNQUENAOEXISTE123")
        self.assertFalse(r.get("known"))
        self.assertNotIn("bus_width", r)
        self.assertNotIn("interface", r)      # o vizinho, pelo mesmo motivo


class ProcedenciaDaLarguraNaTelaTests(TestCase):
    """A tela TEM de dizer de onde veio a largura (regra do dono, 2026-09-20).

        "a gramática só é útil na hora de saber rápido info sobre um PN novo na
         bancada, não deve ser usada como régua para nada... nossa fonte de
         verdade são fontes Tier-1 daquela marca."

    O buraco que essa regra expôs: até 2026-09-20 os cartões imprimiam
    `result.bus_width` puro. Uma largura ADIVINHADA pelo part number aparecia
    IDÊNTICA a uma confirmada em datasheet, e o operador não tinha como
    distinguir — o `bus_width_source` já existia no resultado do engine e
    simplesmente não chegava ao pixel.

    Regra: só `banco` sai limpo. `gramatica` e `familia` saem etiquetados.
    """

    CARTOES = ("chips/partials/decode_card.html",
               "estoque/partials/confirm_card.html")

    def _render(self, template, **extra):
        """Renderiza o partial direto. `lot` é só para o `{% url %}` do
        confirm_card não estourar — nenhum caso aqui depende do lote."""
        from django.template.loader import render_to_string
        # dict que devolve '' para chave ausente: o cartão lê dezenas de campos
        # do resultado e um `{{ x|filtro }}` com chave faltando ESTOURA. Listar
        # todos aqui seria uma segunda cópia do contrato do engine, que
        # envelheceria calada — este teste é sobre a etiqueta de procedência.
        class _Res(dict):
            def __missing__(self, k):
                return ""
        result = _Res(known=True, pn="ZZTESTE1", chip_type="DDR3",
                      capacity="2Gb", bus_width="x8", is_emcp=False)
        result.update(extra)
        return render_to_string(template, {"result": result,
                                           "lot": SimpleNamespace(pk=1)})

    def test_largura_do_BANCO_sai_sem_etiqueta(self):
        """O valor do registro é o único que vale preço — ele sai limpo."""
        for t in self.CARTOES:
            with self.subTest(template=t):
                html = self._render(t, bus_width_source="banco")
                self.assertIn("x8", html)
                self.assertNotIn("bw-src", html,
                                 "etiquetou a largura que veio do REGISTRO")

    def test_largura_da_GRAMATICA_sai_etiquetada(self):
        """⚠ A mutação que morde: apagar o `{% if %}` faz o palpite virar
        datasheet aos olhos de quem está na bancada."""
        for t in self.CARTOES:
            with self.subTest(template=t):
                html = self._render(t, bus_width_source="gramatica")
                self.assertIn("x8", html)
                self.assertIn("bw-src", html)
                self.assertIn("lido do PN", html)

    def test_largura_da_FAMILIA_sai_etiquetada(self):
        for t in self.CARTOES:
            with self.subTest(template=t):
                html = self._render(t, bus_width_source="familia")
                self.assertIn("bw-src", html)
                self.assertIn("da família", html)

    def test_sem_fonte_declarada_nao_inventa_etiqueta(self):
        """Fonte vazia (resultado antigo, caminho não coberto) não vira palpite
        nem vira datasheet: fica sem etiqueta, como o valor do registro. É
        fail-open de propósito — etiquetar por ignorância seria mentir também."""
        for t in self.CARTOES:
            with self.subTest(template=t):
                self.assertNotIn("bw-src", self._render(t, bus_width_source=""))

    def test_a_ETIQUETA_traduz_mas_o_TOKEN_nao(self):
        """Mesma lei do rótulo 'Largura': a lógica compara CHAVE, o usuário vê
        RÓTULO, o banco guarda CANÔNICO. 'x8' é valor canônico e não traduz;
        'lido do PN' é texto de tela e traduz."""
        from django.utils import translation
        for t in self.CARTOES:
            for idioma, esperado in (("es", "leído del PN"),
                                     ("en", "read from the PN"),
                                     ("zh-hans", "从料号读出")):
                with self.subTest(template=t, idioma=idioma):
                    with translation.override(idioma):
                        html = self._render(t, bus_width_source="gramatica")
                    self.assertIn(esperado, html,
                                  f"etiqueta não traduzida em {idioma}")
                    self.assertIn("x8", html, "o TOKEN foi traduzido")
