from django.contrib import admin
from .models import InventoryEntry


@admin.register(InventoryEntry)
class InventoryEntryAdmin(admin.ModelAdmin):
    list_display  = ("part_number", "operator", "chip_type", "display_capacity", "interface", "quantity", "last_updated")
    list_filter   = ("chip_type", "is_emcp", "operator")
    search_fields = ("part_number", "chip_type")
    readonly_fields = ("added_at", "last_updated")
    ordering      = ("-last_updated",)

    def display_capacity(self, obj):
        return obj.display_capacity
    display_capacity.short_description = "Capacidade"
