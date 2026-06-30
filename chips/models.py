"""
WhatTheChip — Chips app models
==============================
Modelos para classificação e lookup de Part Numbers.

Hierarquia:
    Brand → ChipFamily → KnownPart
                ↓
           DecodeMap  (tabelas de decodificação reutilizáveis entre famílias)

Fluxo de confiança para KnownPart:
    confirmed > manual > distributor > estimated

    Só confirmed/manual são autoritativos no engine (vencem a gramática). Não há
    enriquecimento automático por IA — as specs vêm de confirmação manual.
"""

from django.db import models


class Brand(models.Model):
    name = models.TextField(unique=True)
    code = models.TextField(unique=True, help_text="Código curto, ex: SAM, HYN, MIC")
    notes = models.TextField(blank=True, default="")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Source(models.Model):
    SOURCE_TYPES = [
        ("manual",      "Manual"),
        ("scraper",     "Scraper"),
        ("distributor", "Distribuidor"),
        ("datasheet",   "Datasheet"),
    ]
    url      = models.TextField(blank=True, default="")
    name     = models.TextField()
    src_type = models.CharField(max_length=32, choices=SOURCE_TYPES)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fonte"
        verbose_name_plural = "Fontes"

    def __str__(self):
        return f"{self.name} ({self.src_type})"


class ChipFamily(models.Model):
    """
    Família de chips identificada por um prefixo de PN.

    Campos de decodificação:
        decode_cap_pos / decode_cap_map   — posição e mapa para capacidade (ex: eMMC/UFS)
        decode_gen_pos / decode_gen_map   — posição e mapa para geração (ex: eMMC 4.5 vs 5.1)
        decode_density_type               — 'pc' ou 'mobile' para chips DRAM

    doc_page: link opcional para a página de documentação correspondente no WhatTheChip.
    Permite que o resultado de busca inclua um link direto para a documentação.
    """
    brand               = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="families")
    prefix              = models.TextField(db_index=True, help_text="Prefixo do PN, ex: KLM, K4B, H5AN")
    chip_type           = models.TextField(help_text="Ex: eMMC, RAM, eMCP, UFS")
    subtype             = models.TextField(blank=True, default="", help_text="Ex: DDR3 SDRAM, LPDDR4X")
    interface           = models.TextField(blank=True, default="")
    decode_cap_pos      = models.IntegerField(null=True, blank=True,
                              help_text="Índice (0-based) do 1º char que codifica a capacidade. "
                                        "Ex: KLM[C]G0016A → pos=3")
    decode_cap_len      = models.IntegerField(default=1,
                              help_text="Nº de chars da chave de capacidade (padrão=1). "
                                        "Use 2 para eMCP com pares como 'X1', 'BT', 'GD'")
    decode_cap_map      = models.TextField(blank=True, default="",
                              help_text="Nome do DecodeMap para capacidade. "
                                        "Para eMCP: val_primary=cap NAND, val_secondary=cap RAM")
    decode_gen_pos      = models.IntegerField(null=True, blank=True,
                              help_text="Índice (0-based) do char que codifica a geração/tipo RAM. "
                                        "Ex: KMR[R]x1000B → pos=2 → 'R'=LPDDR4/4X")
    decode_gen_map      = models.TextField(blank=True, default="",
                              help_text="Nome do DecodeMap para geração/tipo RAM. "
                                        "val_primary=geração (ex: 'LPDDR4/4X', 'eMMC 5.1')")
    decode_gen_len      = models.IntegerField(default=1,
                              help_text="Nº de chars da chave no mapa de geração/RAM (padrão=1). "
                                        "Use 2 para eMCP com chaves de 2 chars como 'AC', 'AD', 'A8'.")
    decode_density_type = models.TextField(blank=True, default="",
                              help_text="'pc' ou 'mobile' — ativa decode de densidade DRAM")
    pn_length           = models.IntegerField(null=True, blank=True,
                              help_text="Comprimento canônico do PN (sem sufixo opcional após hífen). "
                                        "Ex: KLM8G1GETF = 10. Usado pela UI de PIN para detectar "
                                        "conclusão da entrada e disparar o decode automaticamente. "
                                        "Deixar em branco se o comprimento for variável.")
    is_emcp             = models.BooleanField(default=False)
    suffix_rules        = models.TextField(blank=True, default="", help_text="JSON com regras de sufixo")
    tip                 = models.TextField(blank=True, default="", help_text="Dica exibida para o operador")
    reasoning           = models.TextField(blank=True, default="", help_text="JSON list com passos de raciocínio")
    priority            = models.IntegerField(default=100, help_text="Menor = maior prioridade no match de prefixo")
    active              = models.BooleanField(default=True)
    is_documented       = models.BooleanField(
        default=True,
        help_text="False para famílias identificadas mas sem documentação pública verificável. "
                  "Exibe banner de contribuição na UI e desativa persistência automática na fila."
    )

    # Ligação com a documentação do WhatTheChip
    doc_page = models.ForeignKey(
        "pages.Page",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="chip_families",
        help_text="Página de documentação correspondente (fab-samsung, fab-hynix...)",
    )

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Família de Chip"
        verbose_name_plural = "Famílias de Chips"
        ordering = ["priority", "prefix"]

    def __str__(self):
        return f"{self.prefix} — {self.chip_type} ({self.brand.name})"


class DecodeMap(models.Model):
    """
    Tabela de decodificação: mapeia um caractere/código do PN para seu significado.

    Exemplos:
        CAP_MAP   A → 16GB
        DRAM_PC   4G → 4Gb = 512MB
        EMMC_GEN  7 → eMMC 5.1
    """
    map_name    = models.TextField(help_text="Ex: CAP_MAP, DRAM_PC, DRAM_MOBILE, EMMC_GEN")
    char_key    = models.TextField(help_text="Chave — caractere ou código do PN")
    val_primary = models.TextField(blank=True, default="", help_text="Valor principal, ex: 16GB")
    val_secondary = models.TextField(blank=True, default="", help_text="Valor secundário, ex: 128MB por die")
    brand       = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True,
                                    help_text="Deixar em branco se o mapa for universal")
    notes       = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Mapa de Decodificação"
        verbose_name_plural = "Mapas de Decodificação"
        unique_together = [("map_name", "char_key", "brand")]
        ordering = ["map_name", "char_key"]

    def __str__(self):
        return f"{self.map_name}[{self.char_key}] = {self.val_primary}"


class KnownPart(models.Model):
    """
    Part Number conhecido, com specs confirmadas por fonte humana/oficial.

    Autoridade:
        Só registros com confidence em (confirmed, manual) vencem a gramática no
        engine. distributor/estimated apenas complementam quando a gramática é
        incompleta. Não há enriquecimento automático por IA.

    Double-check:
        Quando o engine decoda um PN pela gramática da família e também encontra
        um KnownPart para o mesmo PN, os dois resultados são comparados.
        Divergência (ex: gramática diz DDR3 4Gb, banco diz DDR3 2Gb) é sinalizada
        como possível chip remarked — dado o contexto de reciclagem.
    """

    CONFIDENCE_CHOICES = [
        ("confirmed",   "✅ Confirmado"),
        ("manual",      "✏️  Manual"),
        ("distributor", "🏪 Distribuidor"),
        ("estimated",   "~ Estimado"),
    ]

    brand        = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="parts")
    part_number  = models.TextField(unique=True, db_index=True)
    family       = models.ForeignKey(ChipFamily, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="parts")

    chip_type    = models.TextField(blank=True, default="")
    subtype      = models.TextField(blank=True, default="")
    capacity     = models.TextField(blank=True, default="", help_text="Ex: 64GB, 512MB")
    density_gbit = models.TextField(blank=True, default="", help_text="Ex: 4Gb (por die)")
    density_gb   = models.TextField(blank=True, default="", help_text="Ex: 512MB (por die)")
    emcp_ram     = models.TextField(blank=True, default="", help_text="Ex: LPDDR4X 4GB")
    emcp_nand    = models.TextField(blank=True, default="", help_text="Ex: eMMC 5.1 64GB")
    interface    = models.TextField(blank=True, default="")
    fbga_code    = models.CharField(
        max_length=10,
        blank=True,
        default="",
        db_index=True,
        help_text=(
            "Código FBGA gravado a laser no chip (ex: D9VFC). "
            "Micron DRAM mobile: padrão D9XXX. NAND: D8XXX. "
            "Permite lookup direto pelo código que o operador lê na esteira, "
            "sem precisar digitar o PN completo."
        ),
    )
    device       = models.TextField(blank=True, default="", help_text="Ex: Galaxy J3/J5 2016")
    notes        = models.TextField(blank=True, default="")

    confidence   = models.CharField(max_length=20, choices=CONFIDENCE_CHOICES, default="estimated")
    source       = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True, blank=True)
    source_url   = models.TextField(blank=True, default="")

    added_at     = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Part Number Conhecido"
        verbose_name_plural = "Part Numbers Conhecidos"
        ordering = ["part_number"]

    def __str__(self):
        return self.part_number


class SearchLog(models.Model):
    part_number = models.TextField()
    found       = models.BooleanField(default=False)
    source_used = models.TextField(blank=True, default="",
                                   help_text="grammar | db_exact | db_fbga | not_found")
    searched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log de Busca"
        verbose_name_plural = "Logs de Busca"
        ordering = ["-searched_at"]

    def __str__(self):
        return f"{self.part_number} ({'✓' if self.found else '✗'})"


class UnknownChip(models.Model):
    """PNs que o sistema não conseguiu classificar por nenhuma via."""
    part_number = models.TextField(unique=True)
    notes       = models.TextField(blank=True, default="")
    logged_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Chip Desconhecido"
        verbose_name_plural = "Chips Desconhecidos"
        ordering = ["-logged_at"]

    def __str__(self):
        return self.part_number


class CorrectionRequest(models.Model):
    """
    Solicitação de correção enviada por usuário ao clicar em 'Reportar erro'.

    Fluxo de triagem:
        pending  → operador analisa no admin
        fixed    → gabarito ou KnownPart corrigido
        rejected → falso positivo (classificação estava certa)
    """
    STATUS_CHOICES = [
        ("pending",  "⏳ Pendente"),
        ("fixed",    "✅ Corrigido"),
        ("rejected", "✗ Rejeitado"),
    ]

    part_number    = models.TextField(db_index=True)
    reported_chip_type  = models.TextField(blank=True, default="",
                              help_text="Tipo exibido no momento do reporte (pode estar errado)")
    reported_capacity   = models.TextField(blank=True, default="",
                              help_text="Capacidade exibida no momento do reporte")
    notes          = models.TextField(blank=True, default="",
                              help_text="Observação livre (preenchida pelo operador no admin)")
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default="pending", db_index=True)
    reported_at    = models.DateTimeField(auto_now_add=True)
    resolved_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Solicitação de Correção"
        verbose_name_plural = "Solicitações de Correção"
        ordering = ["-reported_at"]

    def __str__(self):
        return f"{self.part_number} ({self.get_status_display()})"


class ChipSubmission(models.Model):
    """
    Envio colaborativo de PN não catalogado — feature "Adicionar chip".

    É a alma colaborativa do produto: quando o usuário busca um PN que NÃO
    está no banco, mostramos um card amigável e pedimos que ele envie o PN
    (idealmente com foto do chip) para análise manual. A equipe adiciona ao
    banco em até 48 h. O mesmo fluxo é acessível pelo link "Adicionar chip"
    no menu principal.

    Alimenta o crescimento do banco pela comunidade — o "Google dos chips"
    cresce com cada envio.

    Fluxo de triagem:
        pending  → operador analisa no admin
        added    → chip adicionado ao banco (vira KnownPart / ChipFamily)
        rejected → não foi possível identificar / envio inválido
    """
    STATUS_CHOICES = [
        ("pending",  "⏳ Pendente"),
        ("added",    "✅ Adicionado ao banco"),
        ("rejected", "✗ Rejeitado"),
    ]

    part_number     = models.TextField(db_index=True, help_text="PN enviado pelo usuário")
    photo           = models.ImageField(
        upload_to="submissions/%Y/%m/", blank=True, null=True,
        help_text="Foto do chip enviada pelo usuário (ajuda muito na identificação)")
    context         = models.TextField(
        blank=True, default="",
        help_text="Contexto livre: origem, marca do aparelho, observações")
    submitter_email = models.EmailField(
        blank=True, default="", help_text="E-mail para retorno ao usuário")
    status          = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    notes           = models.TextField(
        blank=True, default="", help_text="Anotações internas do operador")
    created_at      = models.DateTimeField(auto_now_add=True)
    resolved_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Envio de Chip"
        verbose_name_plural = "Envios de Chips (Adicionar chip)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.part_number} ({self.get_status_display()})"


class ProfitabilityConfig(models.Model):
    """
    Regras de rentabilidade configuráveis pelo admin Django.

    Singleton — sempre pk=1. Edite pelo admin; as alterações têm efeito imediato
    sem necessidade de restart ou redeploy. Crie com get_config() se não existir.

    Unidades:
        - Capacidade de armazenamento (eMMC, UFS, eMCP/uMCP): GB
        - Capacidade de RAM (LPDDR standalone, eMCP/uMCP): GB
        - Densidade DDR: Gigabits por die (Gb)  →  8 Gb = 1 GB
    """

    # ── eMCP / uMCP ──────────────────────────────────────────────────────────
    emcp_min_lpddr_gen = models.IntegerField(
        default=3,
        verbose_name="eMCP/uMCP — Geração LPDDR mínima",
        help_text="Gerações abaixo deste valor → NÃO RENTÁVEL.  (3 = LPDDR3 é o mínimo aceito)"
    )
    emcp_min_ram_gb = models.FloatField(
        default=1.0,
        verbose_name="eMCP/uMCP — RAM mínima (GB)",
        help_text="Chips com menos de X GB de RAM → NÃO RENTÁVEL."
    )
    emcp_min_nand_gb = models.FloatField(
        default=8.0,
        verbose_name="eMCP/uMCP — NAND mínima (GB)",
        help_text="Chips com menos de X GB de NAND → NÃO RENTÁVEL."
    )

    # ── eMMC standalone ───────────────────────────────────────────────────────
    emmc_min_cap_gb = models.FloatField(
        default=4.0,
        verbose_name="eMMC — Capacidade mínima (GB)",
        help_text="eMMC com menos de X GB → NÃO RENTÁVEL.  (ex: 4 = a partir de 4 GB)"
    )

    # ── UFS standalone ────────────────────────────────────────────────────────
    ufs_min_cap_gb = models.FloatField(
        default=4.0,
        verbose_name="UFS — Capacidade mínima (GB)",
        help_text="UFS com menos de X GB → NÃO RENTÁVEL."
    )

    # ── LPDDR standalone ─────────────────────────────────────────────────────
    lpddr_min_gen = models.IntegerField(
        default=3,
        verbose_name="LPDDR — Geração mínima",
        help_text="Gerações abaixo deste valor → NÃO RENTÁVEL.  (3 = LPDDR3 é o mínimo)"
    )
    lpddr3_min_cap_gb = models.FloatField(
        default=2.0,
        verbose_name="LPDDR3 — Capacidade mínima (GB)",
        help_text="Para LPDDR3: abaixo de X GB → NÃO RENTÁVEL."
    )
    lpddr4plus_min_cap_gb = models.FloatField(
        default=1.0,
        verbose_name="LPDDR4+ — Capacidade mínima (GB)",
        help_text="Para LPDDR4 ou superior: abaixo de X GB → NÃO RENTÁVEL."
    )

    # ── DDR standalone ────────────────────────────────────────────────────────
    ddr_min_gen = models.IntegerField(
        default=3,
        verbose_name="DDR — Geração mínima",
        help_text="Gerações abaixo deste valor → NÃO RENTÁVEL.  (3 = DDR3 é o mínimo)"
    )
    ddr3_min_gbit = models.FloatField(
        default=2.0,
        verbose_name="DDR3 — Densidade mínima (Gb por die)",
        help_text="Para DDR3: abaixo de X Gb por die → NÃO RENTÁVEL.  (2 Gb = 256 MB | 4 Gb = 512 MB | 8 Gb = 1 GB)"
    )
    ddr4plus_min_gbit = models.FloatField(
        default=1.0,
        verbose_name="DDR4+ — Densidade mínima (Gb por die)",
        help_text="Para DDR4 ou superior: abaixo de X Gb por die → NÃO RENTÁVEL.  (1 Gb = 128 MB | 2 Gb = 256 MB | 8 Gb = 1 GB)"
    )

    # ── GDDR standalone (memória de GPU) ──────────────────────────────────────
    gddr_min_gen = models.IntegerField(
        default=3,
        verbose_name="GDDR — Geração mínima",
        help_text="Gerações abaixo deste valor → NÃO RENTÁVEL.  (3 = GDDR3 é o mínimo; GDDR2 e sem número → NÃO RENTÁVEL)"
    )

    # ── Metadados ─────────────────────────────────────────────────────────────
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última atualização")
    notes = models.TextField(
        blank=True, default="",
        verbose_name="Notas / Histórico de alterações",
        help_text="Registre o motivo das alterações para auditoria futura."
    )

    class Meta:
        verbose_name        = "Configuração de Rentabilidade"
        verbose_name_plural = "Configuração de Rentabilidade"

    def __str__(self):
        return f"Regras de Rentabilidade (atualizado: {self.updated_at.strftime('%d/%m/%Y %H:%M')})"

    @classmethod
    def get_config(cls):
        """Retorna a configuração ativa (singleton pk=1). Cria com defaults se não existir."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CatalogVersion(models.Model):
    """
    Carimbo de edição do catálogo (singleton, sempre pk=1).

    Sobe (`bump()`) sempre que a GRAMÁTICA muda (`ChipFamily`/`DecodeMap`) ou os
    limiares de rentabilidade (`ProfitabilityConfig`) — via sinais em
    `chips/apps.py`. O engine usa esse número como CHAVE do cache em memória
    (`chips/engine.py`): quando ele muda, cada worker do gunicorn recarrega o
    catálogo SOZINHO na leitura seguinte → **acaba a regra "reinicie após
    populate"** (regra de ouro #3).

    É consultado na leitura (1 SELECT barato por classify). Ver
    docs/PLANO_IMPLEMENTACAO_ESCALABILIDADE.md §Passo 1B (Insight B da proposta).
    """
    id         = models.PositiveSmallIntegerField(primary_key=True, default=1)
    version    = models.BigIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Versão do Catálogo"
        verbose_name_plural = "Versão do Catálogo"

    def __str__(self):
        return f"catalog_version = {self.version}"

    @classmethod
    def current(cls) -> int:
        """Edição atual (int). NÃO cria a linha; devolve 1 se ainda não existe."""
        v = cls.objects.filter(pk=1).values_list("version", flat=True).first()
        return v if v is not None else 1

    @classmethod
    def bump(cls) -> int:
        """Incrementa a edição (atômico via F()). Cria a linha na 1ª vez."""
        from django.db.models import F
        n = cls.objects.filter(pk=1).update(version=F("version") + 1)
        if not n:  # linha ainda não existe
            cls.objects.get_or_create(pk=1, defaults={"version": 2})
        return cls.current()
