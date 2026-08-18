from django.contrib import admin
from django.db.models import F
from django.utils import timezone

from .models import InventoryEntry, Lot, PendingEntry, RejectedEntry


def _confirm_as_knownpart(pend):
    """Promove um PendingEntry aprovado a KnownPart manual/enriched (o gestor
    avalizou), para que o PN passe a ser confirmado no banco daqui pra frente.
    Defensivo: nunca rebaixa um confirmed/manual existente; falhas não quebram
    a ação de admin."""
    try:
        from chips.models import Brand, KnownPart
        existing = KnownPart.objects.filter(part_number=pend.part_number).first()
        if existing and existing.confidence in ("confirmed", "manual"):
            return
        name = (pend.brand or "").strip() or "Desconhecida"
        brand = Brand.objects.filter(name__iexact=name).first()
        if not brand:
            code = (name[:3] or "XXX").upper()
            while Brand.objects.filter(code=code).exists():
                code += "X"
            brand = Brand.objects.create(name=name, code=code, notes="Criada via aprovação de fila.")
        try:
            from chips.engine import _match_family
            family = _match_family(pend.part_number)
        except Exception:
            family = None
        KnownPart.objects.update_or_create(
            part_number=pend.part_number,
            defaults=dict(
                brand=brand, family=family, confidence="manual",
                chip_type=pend.chip_type or "", capacity=pend.capacity or "",
                emcp_ram=pend.emcp_ram or "", emcp_nand=pend.emcp_nand or "",
                interface=pend.interface or "",
                notes="Confirmado pelo gestor via fila de conferência (estoque).",
            ),
        )
    except Exception:
        pass


class PlatformScopedAdmin(admin.ModelAdmin):
    """Base dos ModelAdmins do estoque (T3): o Django admin é ferramenta de
    PLATAFORMA (§8 do plano) e enxerga TODAS as empresas — por isso usa o
    manager ``all_companies`` explicitamente (o manager padrão é fail-closed e
    explodiria fora de request escopada). Dropdowns de FK para Lot idem."""

    def get_queryset(self, request):
        qs = self.model.all_companies.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'lot':
            kwargs['queryset'] = Lot.all_companies.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Lot)
class LotAdmin(PlatformScopedAdmin):
    list_display  = ("number", "company", "branch", "operator", "description",
                     "status", "created_at", "closed_at", "closed_by")
    list_filter   = ("status", "company", "operator")
    search_fields = ("number", "description")
    readonly_fields = ("created_at",)
    ordering      = ("-number",)


@admin.register(InventoryEntry)
class InventoryEntryAdmin(PlatformScopedAdmin):
    list_display  = ("part_number", "company", "lot", "chip_type", "display_capacity", "interface", "quantity", "last_updated")
    list_filter   = ("chip_type", "is_emcp", "company", "lot__operator")
    search_fields = ("part_number", "chip_type")
    readonly_fields = ("added_at", "last_updated")
    ordering      = ("-last_updated",)

    def display_capacity(self, obj):
        return obj.display_capacity
    display_capacity.short_description = "Capacidade"


@admin.register(PendingEntry)
class PendingEntryAdmin(PlatformScopedAdmin):
    list_display  = ("part_number", "company", "lot", "chip_type", "capacity", "quantity",
                     "confidence", "nearest_confirmed", "operator", "created_at")
    # T3: o filtro por 'lot' (FK) usaria o manager fail-closed → filtra por company.
    list_filter   = ("classification_source", "confidence", "company", "operator")
    search_fields = ("part_number", "nearest_confirmed")
    readonly_fields = ("created_at",)
    ordering      = ("-created_at",)
    actions       = ("aprovar", "reprovar")

    @admin.action(description="✓ Aprovar: mover para o estoque e confirmar no banco")
    def aprovar(self, request, queryset):
        moved = 0
        for p in queryset:
            # all_companies: ação de PLATAFORMA (sem escopo de request). A
            # empresa da entrada nova herda do lote no save() (CompanyBoundByLot).
            entry, created = InventoryEntry.all_companies.get_or_create(
                lot=p.lot, part_number=p.part_number,
                defaults=dict(
                    chip_type=p.chip_type, brand=p.brand, capacity=p.capacity,
                    emcp_ram=p.emcp_ram, emcp_nand=p.emcp_nand, is_emcp=p.is_emcp,
                    interface=p.interface, classification_source="banco de dados",
                    quantity=p.quantity,
                ),
            )
            if not created:
                InventoryEntry.all_companies.filter(pk=entry.pk).update(
                    quantity=F("quantity") + p.quantity, last_updated=timezone.now())
            _confirm_as_knownpart(p)
            p.delete()
            moved += 1
        self.message_user(
            request,
            f"{moved} chip(s) movido(s) para o estoque e confirmado(s) no banco.")

    @admin.action(description="✗ Reprovar: descartar (typo / chip inexistente)")
    def reprovar(self, request, queryset):
        n = queryset.count()
        queryset.delete()
        self.message_user(request, f"{n} pendência(s) descartada(s).")


@admin.register(RejectedEntry)
class RejectedEntryAdmin(PlatformScopedAdmin):
    """Auditoria de chips reprovados por NÃO RENTÁVEL. Read-only: o registro é
    gravado só pelo fluxo de estoque (add_chip), nunca à mão. Use os filtros para
    calibrar as regras de rentabilidade (que tipos estão indo para o lixo)."""
    list_display  = ("part_number", "company", "lot", "chip_type", "display_capacity",
                     "rejection_reason", "quantity", "operator", "created_at")
    list_filter   = ("rejection_reason", "chip_type", "company", "operator")
    search_fields = ("part_number", "chip_type")
    ordering      = ("-created_at",)
    readonly_fields = (
        "lot", "part_number", "quantity", "chip_type", "brand", "capacity",
        "emcp_ram", "emcp_nand", "is_emcp", "interface", "classification_source",
        "confidence", "rejection_reason", "operator", "created_at",
    )

    def display_capacity(self, obj):
        if obj.is_emcp:
            parts = [p for p in [obj.emcp_nand, obj.emcp_ram] if p]
            return " / ".join(parts) if parts else "—"
        return obj.capacity or "—"
    display_capacity.short_description = "Capacidade"

    def has_add_permission(self, request):
        return False
