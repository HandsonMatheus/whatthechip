"""Admin do vendas — ferramenta de PLATAFORMA (padrão PlatformScopedAdmin do
pricing): manager cru explícito; OV nasce no fechamento do lote e muda de
estado pelas telas /vendas/ — aqui é leitura/auditoria (e o único lugar onde
o NOME do comprador aparece, por decisão de sigilo)."""

from django.contrib import admin

from .models import DocSequence, SalesOrder, SalesOrderLine


class PlatformScopedAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = self.model.all_companies.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 0
    can_delete = False
    readonly_fields = ('brand', 'kind', 'gen', 'tier_value', 'tier_unit',
                       'quantity', 'unit_rmb', 'unit_usd', 'company')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SalesOrder)
class SalesOrderAdmin(PlatformScopedAdmin):
    list_display = ('code', 'company', 'lot', 'buyer', 'status',
                    'total_rmb', 'total_usd', 'fx_usd_rate',
                    'created_at', 'confirmed_at')
    list_filter = ('status', 'company', 'buyer')
    readonly_fields = ('company', 'number', 'lot', 'buyer', 'status',
                       'fx_usd_rate', 'total_rmb', 'total_usd',
                       'unkeyed_units', 'created_at', 'confirmed_at',
                       'confirmed_by', 'cancelled_at', 'cancelled_by')
    inlines = (SalesOrderLineInline,)

    def has_add_permission(self, request):
        return False        # nasce só no fechamento do lote


@admin.register(DocSequence)
class DocSequenceAdmin(PlatformScopedAdmin):
    list_display = ('company', 'kind', 'last_number')
    readonly_fields = ('company', 'kind', 'last_number')

    def has_add_permission(self, request):
        return False
