from django.contrib import admin
from django import forms
from .models import Page


class PageAdminForm(forms.ModelForm):
    """
    Textarea monospace com barra de templates — substitui o CKEditor.
    Os templates são inseridos no cursor via page_admin_templates.js.
    """
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 40,
            'id': 'id_content',   # usado pelo JS para localizar o textarea
        }),
        required=False,
        help_text='HTML puro da página. Use os botões acima para inserir templates.',
    )

    class Meta:
        model  = Page
        fields = '__all__'

    class Media:
        js = ('js/page_admin_templates.js',)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    form                = PageAdminForm
    list_display        = ('order', 'slug', 'title', 'section', 'updated_at')
    list_display_links  = ('slug', 'title')
    list_editable       = ('order',)
    prepopulated_fields = {'slug': ('nav_title',)}
    search_fields       = ('title', 'slug', 'content')
    list_filter         = ('section',)
    ordering            = ('order',)

    fieldsets = (
        ('Identificação', {
            'fields': ('slug', 'title', 'nav_title', 'order', 'section')
        }),
        ('Conteúdo HTML', {
            'fields': ('content',),
            'classes': ('wide',),
        }),
    )
