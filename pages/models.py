import re
from django.db import models


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
    content     = models.TextField(blank=True, default="",
                                   help_text="Conteúdo HTML da página")
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'slug']
        verbose_name = 'Página'
        verbose_name_plural = 'Páginas'

    def __str__(self):
        return f"{self.order:02d}. {self.title}"

    @property
    def nav_class(self):
        """Classe CSS para a sidebar: 'sub', 'section-title', ou '' (vazio).

        Regras (baseadas no nav_title):
          - '1.1 …', '2.1 …' → sub           (subitens: dígito.dígito)
          - '2. …', '3. …'   → section-title  (seções principais numeradas)
          - slugs de seção conhecidos sem prefixo numérico → section-title
          - outros            → '' (item simples, ex: Início)
        """
        # Slugs que são sempre itens de seção, mesmo sem número no nav_title
        SECTION_SLUGS = {'encerramento'}

        label = (self.nav_title or self.title or '').strip()
        if re.match(r'^\d+\.\d+', label):
            return 'sub'
        if re.match(r'^\d+\.', label):
            return 'section-title'
        if self.slug in SECTION_SLUGS:
            return 'section-title'
        return ''

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('page', kwargs={'slug': self.slug})
