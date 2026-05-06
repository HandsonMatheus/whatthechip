# Migração: troca RichTextField (CKEditor) por TextField simples.
# Sem mudança de schema no banco — ambos são colunas TEXT no PostgreSQL.
# Apenas remove a dependência do ckeditor do estado das migrations.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='page',
            name='content',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Conteúdo HTML da página',
            ),
        ),
    ]
