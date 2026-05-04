from django.contrib import admin
from .models import Page


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
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
        ('Conteúdo', {
            'fields': ('content',),
            'classes': ('wide',),
        }),
    )
