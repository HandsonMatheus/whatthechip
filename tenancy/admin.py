"""
tenancy/admin.py — administração de PLATAFORMA (só o dono do WTC)
==================================================================
Depois do bootstrap_tenancy, só superuser tem is_staff → o Django admin vira
ferramenta exclusiva de plataforma (§8 do plano). A gestão que a EMPRESA faz de
si mesma (usuários/filiais) ganha telas no app na T5/T6 — não aqui.
"""

from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import Branch, Company, Membership


class BranchSelect(forms.Select):
    """Select de filial com ``data-company`` em cada opção — combustível do
    membership_branch_filter.js (filtra as filiais pela empresa escolhida)."""

    def create_option(self, name, value, *args, **kwargs):
        option = super().create_option(name, value, *args, **kwargs)
        instance = getattr(value, 'instance', None)   # ModelChoiceIteratorValue
        if instance is not None:
            option['attrs']['data-company'] = str(instance.company_id)
        return option


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display  = ('name', 'slug', 'active', 'last_lot_number', 'created_at')
    list_filter   = ('active',)
    search_fields = ('name', 'slug')
    readonly_fields = ('created_at', 'logo_preview')
    prepopulated_fields = {'slug': ('name',)}

    @admin.display(description='Prévia da logo')
    def logo_preview(self, obj):
        if obj and obj.logo:
            return format_html(
                '<img src="{}" style="max-height:60px;border:1px solid #ddd;'
                'padding:2px;background:#fff">', obj.logo.url)
        return '—'


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display  = ('name', 'company', 'active')
    list_filter   = ('active', 'company')
    search_fields = ('name', 'company__name')


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display  = ('user', 'company', 'role', 'branch', 'active', 'created_at')
    list_filter   = ('role', 'active', 'company')
    search_fields = ('user__username', 'user__email', 'company__name')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('user',)

    class Media:
        # Filtra o select de filial pela empresa escolhida (UX; a barreira real
        # é o clean() do modelo, que rejeita filial de outra empresa).
        js = ('tenancy/membership_branch_filter.js',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'branch':
            kwargs['widget'] = BranchSelect()
            kwargs['queryset'] = (Branch.objects.select_related('company')
                                  .order_by('company__name', 'name'))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
