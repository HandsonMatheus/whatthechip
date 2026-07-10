"""
Admin do pricing — ferramenta de PLATAFORMA (PRECIFICACAO §7).

O Django admin enxerga TODAS as empresas (padrão PlatformScopedAdmin do
estoque): usa o manager ``all_companies`` explicitamente, porque o manager
padrão é fail-closed e explodiria fora de request escopada. É aqui (e SÓ aqui)
que ``updated_by``/``last_updated`` aparecem — o dashboard do comprador não
mostra auditoria.
"""

from django.contrib import admin

from .models import (Buyer, LotPricing, Price, PriceChangeRequest, PriceList,
                     PricingConfig)


class PlatformScopedAdmin(admin.ModelAdmin):
    """Base: admin é plataforma → vê todas as empresas (manager explícito)."""

    def get_queryset(self, request):
        qs = self.model.all_companies.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Dropdowns de FK escopadas também precisam do manager de plataforma.
        if db_field.name == 'buyer':
            kwargs['queryset'] = Buyer.all_companies.all()
        elif db_field.name in ('price_list', 'inherits_from'):
            kwargs['queryset'] = PriceList.all_companies.select_related('buyer', 'brand')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Buyer)
class BuyerAdmin(PlatformScopedAdmin):
    list_display  = ('name', 'company', 'active', 'created_at')
    list_filter   = ('active', 'company')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('users',)


@admin.register(PriceList)
class PriceListAdmin(PlatformScopedAdmin):
    list_display  = ('__str__', 'buyer', 'brand', 'inherits_from', 'active')
    list_filter   = ('active', 'buyer')
    search_fields = ('buyer__name', 'brand__name')
    readonly_fields = ('company', 'created_at')
    fieldsets = ((None, {
        'fields': ('buyer', 'brand', 'inherits_from', 'active',
                   'company', 'created_at'),
        # Anti-footgun (caso Rayson, 2026-07-10): lista criada "só pra herdar"
        # polui a sidebar do parceiro e o catálogo PDF — a herança da genérica
        # já é automática pela AUSÊNCIA de lista.
        'description': '⚠ Marca SEM lista já usa os preços de "Outras marcas" '
                       'automaticamente — NÃO crie lista só para herdar. Crie '
                       'lista apenas quando a marca terá preços PRÓPRIOS '
                       '(ela passa a aparecer na sidebar do parceiro e no '
                       'catálogo PDF).',
    }),)


@admin.register(Price)
class PriceAdmin(PlatformScopedAdmin):
    list_display  = ('price_list', 'kind', 'gen', 'tier_value', 'tier_unit',
                     'status', 'price_min', 'price_max', 'quote_date',
                     'last_updated', 'updated_by')
    list_filter   = ('kind', 'status', 'price_list__buyer')
    search_fields = ('gen', 'price_list__buyer__name', 'price_list__brand__name')
    # Auditoria interna: visível AQUI, nunca no dashboard do comprador (§7).
    readonly_fields = ('company', 'last_updated', 'updated_by')

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user      # Feature 3: registra QUEM mudou
        super().save_model(request, obj, form, change)


@admin.register(LotPricing)
class LotPricingAdmin(PlatformScopedAdmin):
    """Valoração congelada (F8): registro de auditoria — só leitura no admin."""

    list_display = ('lot', 'buyer', 'company', 'total_mid', 'coverage_units',
                    'priced_units', 'total_units', 'created_at', 'closed_by')
    list_filter  = ('buyer', 'company')
    readonly_fields = ('lot', 'buyer', 'company', 'total_low', 'total_mid',
                       'total_high', 'priced_units', 'total_units',
                       'priced_lines', 'total_lines', 'lines', 'created_at',
                       'closed_by')

    def has_add_permission(self, request):
        return False        # nasce só no fechamento do lote


@admin.register(PriceChangeRequest)
class PriceChangeRequestAdmin(PlatformScopedAdmin):
    """F6.1 — a FILA DE REVISÃO das mudanças do comprador. Nada vale até o
    admin aprovar aqui (actions em massa). O pedido em si é read-only."""

    list_display  = ('price', 'delta', 'requested_by', 'created_at',
                     'review_status', 'reviewed_by', 'reviewed_at')
    list_filter   = ('review_status', 'price__price_list__buyer')
    ordering      = ('review_status', '-created_at')   # pendentes primeiro
    actions       = ('aprovar', 'rejeitar')
    readonly_fields = ('price', 'company', 'new_status', 'new_price',
                       'old_status', 'old_price', 'review_status',
                       'requested_by', 'created_at', 'reviewed_by', 'reviewed_at')

    @admin.display(description='Mudança pedida')
    def delta(self, obj):
        de = (f'US$ {obj.old_price}' if obj.old_status == 'quoted'
              else obj.get_old_status_display() if hasattr(obj, 'get_old_status_display')
              else obj.old_status)
        para = (f'US$ {obj.new_price}' if obj.new_status == 'quoted'
                else obj.get_new_status_display())
        return f'{de} → {para}'

    def has_add_permission(self, request):
        return False        # pedido nasce só no /partner/

    @admin.action(description='✔ Aprovar selecionadas (aplica no preço)')
    def aprovar(self, request, queryset):
        n = 0
        for req in queryset.filter(review_status=PriceChangeRequest.REVIEW_PENDING):
            req.approve(request.user)
            n += 1
        self.message_user(request, f'{n} mudança(s) aprovada(s) e aplicada(s).')

    @admin.action(description='✘ Rejeitar selecionadas (preço fica como está)')
    def rejeitar(self, request, queryset):
        n = 0
        for req in queryset.filter(review_status=PriceChangeRequest.REVIEW_PENDING):
            req.reject(request.user)
            n += 1
        self.message_user(request, f'{n} mudança(s) rejeitada(s).')


@admin.register(PricingConfig)
class PricingConfigAdmin(admin.ModelAdmin):
    """Singleton (padrão ProfitabilityConfig): sem add depois do 1º, sem delete."""

    list_display = ('__str__', 'staleness_days', 'default_scenario')

    def has_add_permission(self, request):
        return not PricingConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
