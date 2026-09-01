"""
tenancy/admin.py — administração de PLATAFORMA (só o dono do WTC)
==================================================================
Depois do bootstrap_tenancy, só superuser tem is_staff → o Django admin vira
ferramenta exclusiva de plataforma (§8 do plano). A gestão que a EMPRESA faz de
si mesma (usuários/filiais) ganha telas no app na T5/T6 — não aqui.
"""

from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Branch, Company, CompanyLogo, Membership, UserLanguage


class BranchSelect(forms.Select):
    """Select de filial com ``data-company`` em cada opção — combustível do
    membership_branch_filter.js (filtra as filiais pela empresa escolhida)."""

    def create_option(self, name, value, *args, **kwargs):
        option = super().create_option(name, value, *args, **kwargs)
        instance = getattr(value, 'instance', None)   # ModelChoiceIteratorValue
        if instance is not None:
            option['attrs']['data-company'] = str(instance.company_id)
        return option


# ── E4 (B4+B7): upload de logo → bytes no BANCO (CompanyLogo) ────────────────
_LOGO_MAX_BYTES = 1 * 1024 * 1024   # 1 MB — logo de header, não arte final
_LOGO_FORMATS   = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}


class CompanyAdminForm(forms.ModelForm):
    """O campo real não é editável (blob em CompanyLogo + metadados geridos
    pelo save_model); este form recebe o ARQUIVO e valida com Pillow o formato
    REAL (não a extensão) — SVG cai fora sozinho (Pillow não abre → sem risco
    de XSS por SVG servido inline)."""

    logo_upload = forms.ImageField(
        required=False, label='Logo (arquivo)',
        help_text='PNG, JPEG ou WebP, até 1 MB. Substitui o logo atual.')
    logo_clear = forms.BooleanField(
        required=False, label='Remover o logo atual')

    class Meta:
        model = Company
        fields = '__all__'

    def clean_logo_upload(self):
        f = self.cleaned_data.get('logo_upload')
        if not f:
            return f
        if f.size > _LOGO_MAX_BYTES:
            raise forms.ValidationError('Arquivo muito grande — máximo 1 MB.')
        fmt = f.image.format if getattr(f, 'image', None) else None
        if fmt not in _LOGO_FORMATS:
            raise forms.ValidationError(
                'Formato não suportado — use PNG, JPEG ou WebP.')
        return f


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    form = CompanyAdminForm
    list_display  = ('name', 'code', 'slug', 'service_fee_pct',
                     'payout_on_payment', 'active', 'ui_v2',
                     'last_lot_number', 'created_at')
    # `payout_on_payment` na lista E no filtro de propósito: é a chave que
    # decide se a tela do cliente promete dinheiro sozinha. Quem audita
    # precisa ver quais empresas estão ligadas sem abrir uma por uma.
    list_filter   = ('active', 'ui_v2', 'payout_on_payment')
    search_fields = ('name', 'slug', 'code')
    readonly_fields = ('created_at', 'logo_preview')
    prepopulated_fields = {'slug': ('name',)}

    def save_model(self, request, obj, form, change):
        """Grava a Company e sincroniza o logo (E4): blob em CompanyLogo,
        metadados (mime + updated_at, o cache-buster) na própria Company.
        Roda dentro do atomic do admin — blob e metadados nunca divergem."""
        super().save_model(request, obj, form, change)
        upload = form.cleaned_data.get('logo_upload')
        clear  = form.cleaned_data.get('logo_clear')
        if upload:
            upload.seek(0)
            CompanyLogo.objects.update_or_create(
                company=obj, defaults={'data': upload.read()})
            obj.logo_mime = _LOGO_FORMATS[upload.image.format]
            obj.logo_updated_at = timezone.now()
            obj.save(update_fields=['logo_mime', 'logo_updated_at'])
        elif clear:
            CompanyLogo.objects.filter(company=obj).delete()
            if obj.logo_mime:
                obj.logo_mime = ''
                obj.logo_updated_at = None
                obj.save(update_fields=['logo_mime', 'logo_updated_at'])

    @admin.display(description='Prévia da logo')
    def logo_preview(self, obj):
        if obj and obj.pk and obj.logo_mime:
            url = reverse('company_logo', kwargs={'slug': obj.slug})
            v = (int(obj.logo_updated_at.timestamp())
                 if obj.logo_updated_at else 0)
            return format_html(
                '<img src="{}?v={}" style="max-height:60px;border:1px solid #ddd;'
                'padding:2px;background:#fff">', url, v)
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


@admin.register(UserLanguage)
class UserLanguageAdmin(admin.ModelAdmin):
    """Preferência de idioma (i18n — I18N.md §3). Visão de LISTA (quem usa o
    quê); a edição do dia a dia é o inline na ficha do usuário (abaixo)."""
    list_display  = ('user', 'language', 'updated_at')
    list_filter   = ('language',)
    search_fields = ('user__username', 'user__email')
    autocomplete_fields = ('user',)
    readonly_fields = ('updated_at',)


# ── Idioma DENTRO da ficha do usuário ────────────────────────────────────────
# O fluxo real do dono é "criar/editar usuário" — a preferência de idioma tem
# que estar ALI, não numa tela separada. Re-registra o UserAdmin padrão do
# Django com o inline da preferência (I18N.md §3).
from django.contrib.auth import get_user_model                    # noqa: E402
from django.contrib.auth.admin import UserAdmin as _DjangoUserAdmin  # noqa: E402


class UserLanguageInline(admin.StackedInline):
    model = UserLanguage
    can_delete = True
    verbose_name = 'Idioma da plataforma'
    verbose_name_plural = 'Idioma da plataforma'
    extra = 0
    max_num = 1


_User = get_user_model()
admin.site.unregister(_User)


@admin.register(_User)
class UserAdmin(_DjangoUserAdmin):
    inlines = list(_DjangoUserAdmin.inlines) + [UserLanguageInline]
