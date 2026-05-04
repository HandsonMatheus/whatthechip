from django.db import models
from ckeditor.fields import RichTextField


class Page(models.Model):
    """Uma página de documentação do WhatTheChip."""

    slug        = models.SlugField(max_length=100, unique=True,
                                   help_text="Identificador na URL, ex: fab-samsung")
    title       = models.CharField(max_length=300,
                                   help_text="Título completo da página")
    nav_title   = models.CharField(max_length=100, blank=True,
                                   help_text="Título curto para a sidebar (opcional)")
    order       = models.PositiveIntegerField(default=0,
                                              help_text="Ordem de exibição na sidebar")
    section     = models.CharField(max_length=100, blank=True,
                                   help_text="Seção da sidebar, ex: '2. Fabricantes'")
    content     = RichTextField(config_name='default',
                                help_text="Conteúdo HTML da página (edite com CKEditor)")
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'slug']
        verbose_name = 'Página'
        verbose_name_plural = 'Páginas'

    def __str__(self):
        return f"{self.order:02d}. {self.title}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('page', kwargs={'slug': self.slug})
