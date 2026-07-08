# -*- coding: utf-8 -*-
"""
Backfill do modeltranslation (i18n — I18N.md §9): copia o conteúdo PT existente
(colunas-base title/nav_title/section/content) para as colunas *_pt_br criadas
na 0003. Sem isto, a resolução por idioma acharia NULL no pt_br e o fallback
falharia para os registros antigos — é o equivalente ADITIVO do
``manage.py update_translation_fields`` do pacote, rodando sozinho no deploy
(migrations aditivas, padrão do projeto). Idempotente: F() copia o valor atual;
re-rodar não perde nada (as *_pt_br são espelho da base neste ponto da história).
"""
from django.db import migrations
from django.db.models import F


def copia_base_para_pt_br(apps, schema_editor):
    Page = apps.get_model('pages', 'Page')
    Page.objects.update(
        title_pt_br=F('title'),
        nav_title_pt_br=F('nav_title'),
        section_pt_br=F('section'),
        content_pt_br=F('content'),
    )


def noop(apps, schema_editor):
    """Reversão: as colunas *_pt_br continuam existindo (a 0003 é quem as
    remove no reverse); nada a desfazer aqui."""


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0003_page_content_en_page_content_es_page_content_pt_br_and_more'),
    ]

    operations = [
        migrations.RunPython(copia_base_para_pt_br, noop),
    ]
