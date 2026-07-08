from django.contrib import admin
from django import forms
from modeltranslation.admin import TranslationAdmin
from .models import Page


class PageAdminForm(forms.ModelForm):
    """
    Textarea monospace com barra de templates — substitui o CKEditor.
    Os templates são inseridos no cursor via page_admin_templates.js.
    Com o modeltranslation (I18N.md §9), 'content' vira content (pt-br base) +
    content_es/content_en/content_zh_hans — o textarea grande é aplicado a
    todos em formfield_for_dbfield (abaixo), não mais campo a campo aqui.
    """

    class Meta:
        model  = Page
        fields = '__all__'

    class Media:
        js = ('js/page_admin_templates.js',)


@admin.register(Page)
class PageAdmin(TranslationAdmin):
    """i18n do CMS: TranslationAdmin agrupa os campos traduzíveis por idioma.
    Coluna-base = pt-br; tradução vazia cai no fallback PT na exibição.
    A FONTE das traduções continua sendo _content/<slug>.<lang>.html no git
    (import_content/sync_index_page) — o admin é edição pontual."""
    form                = PageAdminForm
    list_display        = ('order', 'slug', 'title', 'section', 'updated_at')
    list_display_links  = ('slug', 'title')
    list_editable       = ('order',)
    prepopulated_fields = {'slug': ('nav_title',)}
    search_fields       = ('title', 'slug', 'content')
    list_filter         = ('section',)
    ordering            = ('order',)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        # Todos os content_<lang> ganham o textarea grande do fluxo antigo
        # (o id_content original é preservado no campo base p/ o JS).
        if db_field.name.startswith('content'):
            kwargs['widget'] = forms.Textarea(
                attrs={'rows': 40, 'id': f'id_{db_field.name}'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)
