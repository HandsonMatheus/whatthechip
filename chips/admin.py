from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from .models import (
    Brand, Source, ChipFamily, DecodeMap, KnownPart, SearchLog,
    UnknownChip, CorrectionRequest, ChipSubmission, ProfitabilityConfig,
)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display  = ("name", "code", "families_count", "parts_count", "added_at")
    search_fields = ("name", "code")

    def families_count(self, obj):
        return obj.families.count()
    families_count.short_description = "Famílias"

    def parts_count(self, obj):
        return obj.parts.count()
    parts_count.short_description = "Part Numbers"


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display  = ("name", "src_type", "url", "fetched_at")
    list_filter   = ("src_type",)
    search_fields = ("name", "url")


@admin.register(ChipFamily)
class ChipFamilyAdmin(admin.ModelAdmin):
    list_display  = (
        "prefix", "brand", "chip_type", "subtype", "is_emcp",
        "decode_summary", "active", "priority", "doc_link",
    )
    list_filter   = ("brand", "chip_type", "is_emcp", "active")
    search_fields = ("prefix", "chip_type", "subtype")
    list_editable = ("priority", "active")
    autocomplete_fields = ("doc_page",)
    fieldsets = (
        ("Identificação", {
            "fields": ("brand", "prefix", "chip_type", "subtype", "interface", "is_emcp", "active", "priority"),
            "description": (
                "<strong>interface</strong>: versão do padrão de armazenamento da família — "
                "ex: 'eMMC 5.1', 'UFS 3.1'. "
                "Para eMCP, é a versão do NAND interno (ex: 'eMMC 5.1'). "
                "Deixe em branco se desconhecido."
            ),
        }),
        ("Decodificação do Part Number", {
            "fields": (
                "decode_cap_pos", "decode_cap_len", "decode_cap_map",
                "decode_gen_pos", "decode_gen_map",
                "decode_density_type",
                "suffix_rules",
            ),
            "classes": ("collapse",),
            "description": (
                "Campos de anatomia do PN. "
                "<b>cap_pos + cap_len + cap_map</b>: decodifica capacidade (eMMC/NAND) ou par NAND+RAM (eMCP). "
                "<b>gen_pos + gen_map</b>: decodifica geração ou tipo RAM. "
                "Todos os índices são 0-based (K=0, M=1, R=2, …)."
            ),
        }),
        ("Documentação e Contexto", {
            "fields": ("doc_page", "tip", "reasoning"),
            "classes": ("collapse",),
            "description": (
                "Vincule a <b>doc_page</b> à página de anatomia correspondente no WhatTheChip. "
                "O resultado de busca exibirá um link '📄 Ver anatomia'."
            ),
        }),
    )

    def decode_summary(self, obj):
        parts = []
        if obj.decode_cap_map:
            cap_len = obj.decode_cap_len or 1
            parts.append(f"cap@{obj.decode_cap_pos}[{cap_len}]={obj.decode_cap_map}")
        if obj.decode_gen_map:
            parts.append(f"gen@{obj.decode_gen_pos}={obj.decode_gen_map}")
        if obj.decode_density_type:
            parts.append(f"dens={obj.decode_density_type}")
        return " | ".join(parts) if parts else "—"
    decode_summary.short_description = "Decode rules"

    def doc_link(self, obj):
        if obj.doc_page_id:
            try:
                url = obj.doc_page.get_absolute_url()
                return format_html('<a href="{}" target="_blank">📄 {}</a>', url, obj.doc_page.slug)
            except Exception:
                return "📄 (erro)"
        return "—"
    doc_link.short_description = "Doc"


@admin.register(DecodeMap)
class DecodeMapAdmin(admin.ModelAdmin):
    list_display  = ("map_name", "char_key", "val_primary", "val_secondary", "brand")
    list_filter   = ("map_name", "brand")
    search_fields = ("map_name", "char_key", "val_primary")
    ordering      = ("map_name", "char_key")


@admin.register(KnownPart)
class KnownPartAdmin(admin.ModelAdmin):
    list_display  = (
        "part_number", "fbga_code", "brand", "chip_type",
        "capacity_display", "device", "confidence", "last_updated"
    )
    list_filter   = ("brand", "chip_type", "confidence")
    search_fields = ("part_number", "fbga_code", "device", "chip_type")
    readonly_fields = ("added_at", "last_updated")
    list_per_page = 50

    fieldsets = (
        ("Identificação", {
            "fields": ("brand", "family", "part_number", "fbga_code", "confidence", "source", "source_url")
        }),
        ("Dados do Chip", {
            "fields": ("chip_type", "subtype", "interface", "capacity", "density_gbit", "density_gb")
        }),
        ("eMCP / uMCP", {
            "fields": ("emcp_ram", "emcp_nand"),
            "classes": ("collapse",),
        }),
        ("Contexto", {
            "fields": ("device", "notes", "added_at", "last_updated"),
            "classes": ("collapse",),
        }),
    )

    def capacity_display(self, obj):
        if obj.emcp_ram:
            return f"RAM: {obj.emcp_ram} / NAND: {obj.emcp_nand}"
        return obj.capacity or obj.density_gbit or "—"
    capacity_display.short_description = "Capacidade"


@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display  = ("part_number", "found", "source_used", "searched_at")
    list_filter   = ("found", "source_used")
    search_fields = ("part_number",)
    readonly_fields = ("searched_at",)

    def has_add_permission(self, request):
        return False


@admin.register(UnknownChip)
class UnknownChipAdmin(admin.ModelAdmin):
    list_display  = ("part_number", "logged_at")
    search_fields = ("part_number",)
    readonly_fields = ("logged_at",)

    def has_add_permission(self, request):
        return False


@admin.register(CorrectionRequest)
class CorrectionRequestAdmin(admin.ModelAdmin):
    list_display   = ("part_number", "reported_chip_type", "reported_capacity",
                      "status_badge", "reported_at", "knownpart_link")
    list_filter    = ("status",)
    search_fields  = ("part_number",)
    readonly_fields = ("part_number", "reported_chip_type", "reported_capacity", "reported_at")
    fields         = ("part_number", "reported_chip_type", "reported_capacity",
                      "reported_at", "status", "notes")
    actions        = ["mark_fixed", "mark_rejected"]

    def has_add_permission(self, request):
        return False

    def status_badge(self, obj):
        colors = {"pending": "#B45309", "fixed": "#166534", "rejected": "#6B7280"}
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            colors.get(obj.status, "#000"),
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def knownpart_link(self, obj):
        from .models import KnownPart
        try:
            kp = KnownPart.objects.get(part_number=obj.part_number)
            url = f"/admin/chips/knownpart/{kp.pk}/change/"
            return format_html('<a href="{}">📦 Ver no banco</a>', url)
        except KnownPart.DoesNotExist:
            return "—"
    knownpart_link.short_description = "KnownPart"

    @admin.action(description="✅ Marcar como corrigido")
    def mark_fixed(self, request, queryset):
        queryset.update(status="fixed", resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} solicitação(ões) marcada(s) como corrigida(s).")

    @admin.action(description="✗ Marcar como rejeitado")
    def mark_rejected(self, request, queryset):
        queryset.update(status="rejected", resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} solicitação(ões) rejeitada(s).")


@admin.register(ChipSubmission)
class ChipSubmissionAdmin(admin.ModelAdmin):
    """Triagem dos envios colaborativos da feature 'Adicionar chip'."""
    list_display    = ("part_number", "status_badge", "has_photo",
                       "submitter_email", "created_at")
    list_filter     = ("status",)
    search_fields   = ("part_number", "submitter_email", "context")
    readonly_fields = ("part_number", "photo", "photo_preview", "context",
                       "submitter_email", "created_at", "resolved_at")
    fields          = ("part_number", "photo_preview", "photo", "context",
                       "submitter_email", "created_at", "status", "notes", "resolved_at")
    actions         = ["mark_added", "mark_rejected"]

    def has_add_permission(self, request):
        return False

    def status_badge(self, obj):
        colors = {"pending": "#B45309", "added": "#166534", "rejected": "#6B7280"}
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            colors.get(obj.status, "#000"), obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def has_photo(self, obj):
        return "📷 sim" if obj.photo else "—"
    has_photo.short_description = "Foto"

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-height:280px;max-width:100%;'
                'border:1px solid #ccc;border-radius:2px" />',
                obj.photo.url,
            )
        return "— sem foto enviada —"
    photo_preview.short_description = "Pré-visualização"

    @admin.action(description="✅ Marcar como adicionado ao banco")
    def mark_added(self, request, queryset):
        queryset.update(status="added", resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} envio(s) marcado(s) como adicionado(s).")

    @admin.action(description="✗ Marcar como rejeitado")
    def mark_rejected(self, request, queryset):
        queryset.update(status="rejected", resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} envio(s) rejeitado(s).")


# ── Configuração de Rentabilidade (singleton) ─────────────────────────────────

@admin.register(ProfitabilityConfig)
class ProfitabilityConfigAdmin(admin.ModelAdmin):
    """
    Admin singleton para as regras de rentabilidade.
    Não permite adicionar nem deletar — sempre existe exatamente um registro (pk=1).
    Alterações têm efeito imediato sem restart do servidor.
    """

    fieldsets = (
        ("eMCP / uMCP", {
            "description": (
                "Pacotes eMCP (eMMC + LPDDR) e uMCP (UFS + LPDDR). "
                "Todos os critérios abaixo devem ser atendidos simultaneamente."
            ),
            "fields": ("emcp_min_lpddr_gen", "emcp_min_ram_gb", "emcp_min_nand_gb"),
        }),
        ("eMMC standalone", {
            "fields": ("emmc_min_cap_gb",),
        }),
        ("UFS standalone", {
            "fields": ("ufs_min_cap_gb",),
        }),
        ("LPDDR standalone", {
            "description": "RAM móvel. LPDDR3 e LPDDR4+ têm limiares de capacidade separados.",
            "fields": ("lpddr_min_gen", "lpddr3_min_cap_gb", "lpddr4plus_min_cap_gb"),
        }),
        ("DDR standalone", {
            "description": (
                "RAM de PC/servidor. Threshold em Gigabits por die — "
                "atenção: Gb ≠ GB.  (2 Gb = 256 MB | 8 Gb = 1 GB)"
            ),
            "fields": ("ddr_min_gen", "ddr3_min_gbit", "ddr4plus_min_gbit"),
        }),
        ("Histórico", {
            "classes": ("collapse",),
            "fields": ("updated_at", "notes"),
        }),
    )

    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Singleton: bloqueia criação de registros extras
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Redireciona a listagem diretamente para o único objeto (cria se não existir)
        obj = ProfitabilityConfig.get_config()
        return redirect(reverse("admin:chips_profitabilityconfig_change", args=[obj.pk]))
