from django.contrib import admin
from django.utils.html import format_html
from .models import Brand, Source, ChipFamily, DecodeMap, KnownPart, SearchLog, UnknownChip


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
        "decode_cap_map", "decode_density_type", "active", "priority", "doc_page"
    )
    list_filter   = ("brand", "chip_type", "is_emcp", "active")
    search_fields = ("prefix", "chip_type", "subtype")
    list_editable = ("priority", "active")
    autocomplete_fields = ("doc_page",)
    fieldsets = (
        ("Identificação", {
            "fields": ("brand", "prefix", "chip_type", "subtype", "interface", "is_emcp", "active", "priority")
        }),
        ("Decodificação", {
            "fields": (
                "decode_cap_pos", "decode_cap_map",
                "decode_gen_pos", "decode_gen_map",
                "decode_density_type",
                "suffix_rules",
            ),
            "classes": ("collapse",),
        }),
        ("Documentação e Contexto", {
            "fields": ("doc_page", "tip", "reasoning"),
            "classes": ("collapse",),
        }),
    )


@admin.register(DecodeMap)
class DecodeMapAdmin(admin.ModelAdmin):
    list_display  = ("map_name", "char_key", "val_primary", "val_secondary", "brand")
    list_filter   = ("map_name", "brand")
    search_fields = ("map_name", "char_key", "val_primary")
    ordering      = ("map_name", "char_key")


@admin.register(KnownPart)
class KnownPartAdmin(admin.ModelAdmin):
    list_display  = (
        "part_number", "brand", "status_badge", "chip_type",
        "capacity_display", "device", "confidence", "last_updated"
    )
    list_filter   = ("status", "brand", "chip_type", "confidence")
    search_fields = ("part_number", "device", "chip_type")
    readonly_fields = ("added_at", "last_updated")
    list_per_page = 50

    fieldsets = (
        ("Identificação", {
            "fields": ("brand", "family", "part_number", "status", "confidence", "source", "source_url")
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

    def status_badge(self, obj):
        colors = {"enriched": "green", "raw": "gray", "failed": "red"}
        labels = {"enriched": "✅ Enriquecido", "raw": "⬜ Raw", "failed": "❌ Falha"}
        color = colors.get(obj.status, "gray")
        label = labels.get(obj.status, obj.status)
        return format_html('<span style="color:{}">{}</span>', color, label)
    status_badge.short_description = "Status"

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
