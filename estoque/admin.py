from django.contrib import admin
from .models import InventoryEntry, Lot


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display  = ("number", "operator", "description", "status", "created_at", "closed_at")
    list_filter   = ("status", "operator")
    search_fields = ("number", "description")
    readonly_fields = ("created_at",)
    ordering      = ("-number",)


@admin.register(InventoryEntry)
class InventoryEntryAdmin(admin.ModelAdmin):
    list_display  = ("part_number", "lot", "chip_type", "display_capacity", "interface", "quantity", "last_updated")
    list_filter   = ("chip_type", "is_emcp", "lot__operator")
    search_fields = ("part_number", "chip_type")
    readonly_fields = ("added_at", "last_updated")
    ordering      = ("-last_updated",)

    def display_capacity(self, obj):
        return obj.display_capacity
    display_capacity.short_description = "Capacidade"
