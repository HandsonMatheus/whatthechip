"""
WhatTheChip — Chips app models
==============================
Modelos para classificação e lookup de Part Numbers.

Hierarquia:
    Brand → ChipFamily → KnownPart
                ↓
           DecodeMap  (tabelas de decodificação reutilizáveis entre famílias)

Fluxo de confiança para KnownPart:
    confirmed > manual > distributor > ai_high > ai_medium > ai_low > estimated

Status de enriquecimento (KnownPart.status):
    raw       — PN coletado, ainda sem dados de capacidade/tipo
    enriched  — dados confirmados (por qualquer fonte)
    failed    — enriquecimento tentado e sem resultado útil
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
        ("ai",          "IA"),
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
    Part Number conhecido — pode ser raw (só o código) ou enriched (com dados completos).

    status:
        raw      — PN coletado pelo scraper, ainda sem dados de capacidade/tipo.
                   Será enriquecido pelo enrich_gemini.py na próxima rodada.
        enriched — tem pelo menos chip_type + (capacity ou emcp_ram/nand) preenchidos.
        failed   — enriquecimento tentado, Gemini não encontrou dados confiáveis.

    Double-check:
        Quando o engine decoda um PN pela gramática da família e também encontra
        um KnownPart enriquecido, os dois resultados são comparados.
        Divergência (ex: gramática diz DDR3 4Gb, banco diz DDR3 2Gb) é sinalizada
        como possível chip remarked — dado o contexto de reciclagem.
    """

    STATUS_CHOICES = [
        ("raw",      "⬜ Raw — sem enriquecimento"),
        ("enriched", "✅ Enriquecido"),
        ("failed",   "❌ Falha no enriquecimento"),
    ]
    CONFIDENCE_CHOICES = [
        ("confirmed",   "✅ Confirmado"),
        ("manual",      "✏️  Manual"),
        ("distributor", "🏪 Distribuidor"),
        ("ai_high",     "🤖 IA — Alta"),
        ("ai_medium",   "🤖 IA — Média"),
        ("ai_low",      "🤖 IA — Baixa"),
        ("estimated",   "~ Estimado"),
    ]

    brand        = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="parts")
    part_number  = models.TextField(unique=True, db_index=True)
    family       = models.ForeignKey(ChipFamily, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="parts")

    status       = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                    default="raw", db_index=True)

    chip_type    = models.TextField(blank=True, default="")
    subtype      = models.TextField(blank=True, default="")
    capacity     = models.TextField(blank=True, default="", help_text="Ex: 64GB, 512MB")
    density_gbit = models.TextField(blank=True, default="", help_text="Ex: 4Gb (por die)")
    density_gb   = models.TextField(blank=True, default="", help_text="Ex: 512MB (por die)")
    emcp_ram     = models.TextField(blank=True, default="", help_text="Ex: LPDDR4X 4GB")
    emcp_nand    = models.TextField(blank=True, default="", help_text="Ex: eMMC 5.1 64GB")
    interface    = models.TextField(blank=True, default="")
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

    @property
    def is_enriched(self):
        return self.status == "enriched"


class SearchLog(models.Model):
    part_number = models.TextField()
    found       = models.BooleanField(default=False)
    source_used = models.TextField(blank=True, default="",
                                   help_text="grammar | db_exact | gemini | not_found")
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
