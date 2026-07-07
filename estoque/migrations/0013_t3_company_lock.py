# T3 — passo 3 de 3 (PLANO_MULTITENANT.md §5.2): TRAVAR.
# NOT NULL nas colunas company (backfill garantido pela 0012), numeração por
# empresa (cai o unique global do number; entra unique (company, number)) e
# índices compostos liderados por company. Escrita à mão: o makemigrations
# pergunta interativamente no null=True→False; aqui as linhas já estão povoadas.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0012_t3_backfill_company'),
        ('tenancy', '0001_initial'),
    ]

    operations = [
        # ── NOT NULL (as 4 colunas já estão povoadas pela 0012) ─────────────
        migrations.AlterField(
            model_name='lot',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='lots', to='tenancy.company',
                verbose_name='Empresa'),
        ),
        migrations.AlterField(
            model_name='inventoryentry',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+', to='tenancy.company',
                verbose_name='Empresa'),
        ),
        migrations.AlterField(
            model_name='pendingentry',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+', to='tenancy.company',
                verbose_name='Empresa'),
        ),
        migrations.AlterField(
            model_name='rejectedentry',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+', to='tenancy.company',
                verbose_name='Empresa'),
        ),
        # ── Numeração por empresa ────────────────────────────────────────────
        migrations.AlterField(
            model_name='lot',
            name='number',
            field=models.PositiveIntegerField(verbose_name='Número'),
        ),
        migrations.AddConstraint(
            model_name='lot',
            constraint=models.UniqueConstraint(
                fields=('company', 'number'),
                name='unique_lot_company_number'),
        ),
        # ── Índices compostos (toda consulta começa por company) ────────────
        migrations.AddIndex(
            model_name='lot',
            index=models.Index(fields=['company', '-number'],
                               name='lot_company_number_desc'),
        ),
        migrations.AddIndex(
            model_name='inventoryentry',
            index=models.Index(fields=['company', 'part_number'],
                               name='inv_company_pn'),
        ),
        migrations.AddIndex(
            model_name='inventoryentry',
            index=models.Index(fields=['company', 'lot'],
                               name='inv_company_lot'),
        ),
    ]
