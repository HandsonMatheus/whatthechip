"""O piso por peça do SSD, e a porta pela qual o comprador pede as taxas.

Duas coisas, uma migração, porque a segunda existe para mover a primeira.

**`Buyer.ssd_floor_rmb`** — spec v2 §3.2: `preço(cap) = max(round(¥/GB × GB),
piso)`. Nasce NULL, e NULL é "sem piso": nenhum preço muda até alguém pôr um
número. O linear puro cobra ¥13 por um SSD de 128GB e ¥102 por um de 1TB,
mas manusear, testar e embalar custa o mesmo nos dois.

**`RateChangeRequest`** — o four-eyes do `PriceChangeRequest` para SSD e K9,
que não têm linha de grade: o preço deles mora no `Buyer`, e a FK `price` de
lá é obrigatória. Tabela nova em vez de afrouxar aquela FK (a tabela que a
bancada lê, com constraint e RLS em cima) ou cunhar `Price` falso (duas
fontes de verdade — e o ¥/GB tem 3 casas, que `price_min` não guarda).

⚠ A churn de trigger do `buyer` é do pghistory: acrescentar coluna a modelo
rastreado regenera `insert_insert`/`update_update`. Gerada pelo Django, não
escrita à mão.

⚠ As policies de RLS vêm na 0028 — tabela nova nasce sem nenhuma, e sem
FORCE o `postgres` dono do schema atravessaria empresa.
"""

import django.db.models.deletion
import django.db.models.manager
import pgtrigger.compiler
import pgtrigger.migrations
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pghistory', '0007_auto_20250421_0444'),
        ('pricing', '0026_buyer_read_self_access'),
        ('tenancy', '0011_company_service_fee'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RateChangeRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('ssd', 'SSD'), ('k9', 'K9')], max_length=8, verbose_name='Tipo')),
                ('new_rate', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Nova taxa ¥')),
                ('new_floor', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='Novo piso ¥/peça (SSD)')),
                ('old_rate', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Taxa anterior')),
                ('old_floor', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='Piso anterior')),
                ('review_status', models.CharField(choices=[('pending', 'Pendente'), ('approved', 'Aprovado'), ('rejected', 'Rejeitado')], default='pending', max_length=10, verbose_name='Revisão')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Pedido em')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Revisado em')),
                ('seen_by_partner', models.BooleanField(default=False, verbose_name='Visto pelo parceiro')),
            ],
            options={
                'verbose_name': 'Mudança de taxa de contrato (revisão)',
                'verbose_name_plural': 'Mudanças de taxa de contrato (revisão)',
                'ordering': ['-created_at'],
                'base_manager_name': 'all_companies',
                'default_manager_name': 'all_companies',
            },
            managers=[
                ('all_companies', django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name='RateChangeRequestEvent',
            fields=[
                ('pgh_id', models.AutoField(primary_key=True, serialize=False)),
                ('pgh_created_at', models.DateTimeField(auto_now_add=True)),
                ('pgh_label', models.TextField(help_text='The event label.')),
                ('id', models.BigIntegerField()),
                ('kind', models.CharField(choices=[('ssd', 'SSD'), ('k9', 'K9')], max_length=8, verbose_name='Tipo')),
                ('new_rate', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Nova taxa ¥')),
                ('new_floor', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='Novo piso ¥/peça (SSD)')),
                ('old_rate', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Taxa anterior')),
                ('old_floor', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='Piso anterior')),
                ('review_status', models.CharField(choices=[('pending', 'Pendente'), ('approved', 'Aprovado'), ('rejected', 'Rejeitado')], default='pending', max_length=10, verbose_name='Revisão')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Pedido em')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Revisado em')),
                ('seen_by_partner', models.BooleanField(default=False, verbose_name='Visto pelo parceiro')),
            ],
            options={
                'abstract': False,
            },
        ),
        pgtrigger.migrations.RemoveTrigger(
            model_name='buyer',
            name='insert_insert',
        ),
        pgtrigger.migrations.RemoveTrigger(
            model_name='buyer',
            name='update_update',
        ),
        migrations.AddField(
            model_name='buyer',
            name='ssd_floor_rmb',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Piso por PEÇA do SSD: nenhuma peça sai por menos que isto, por menor que seja a capacidade (ex.: 18 → 128GB a ¥0,10/GB daria ¥13, mas sai ¥18). Vazio = sem piso.', max_digits=8, null=True, verbose_name='SSD — ¥ mínimo por peça'),
        ),
        migrations.AddField(
            model_name='buyerevent',
            name='ssd_floor_rmb',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Piso por PEÇA do SSD: nenhuma peça sai por menos que isto, por menor que seja a capacidade (ex.: 18 → 128GB a ¥0,10/GB daria ¥13, mas sai ¥18). Vazio = sem piso.', max_digits=8, null=True, verbose_name='SSD — ¥ mínimo por peça'),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='buyer',
            trigger=pgtrigger.compiler.Trigger(name='insert_insert', sql=pgtrigger.compiler.UpsertTriggerSql(func='INSERT INTO "pricing_buyerevent" ("active", "company_id", "created_at", "fx_usd_rate", "id", "k9_rmb_each", "name", "notes", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "prices_in_rmb", "ship_to_address", "ship_to_email", "ship_to_name", "ship_to_phone", "slug", "ssd_floor_rmb", "ssd_rmb_per_gb") VALUES (NEW."active", NEW."company_id", NEW."created_at", NEW."fx_usd_rate", NEW."id", NEW."k9_rmb_each", NEW."name", NEW."notes", _pgh_attach_context(), NOW(), \'insert\', NEW."id", NEW."prices_in_rmb", NEW."ship_to_address", NEW."ship_to_email", NEW."ship_to_name", NEW."ship_to_phone", NEW."slug", NEW."ssd_floor_rmb", NEW."ssd_rmb_per_gb"); RETURN NULL;', hash='64953ad472ebf0b10b32a0a6aeb7f21186ea6115', operation='INSERT', pgid='pgtrigger_insert_insert_35de3', table='pricing_buyer', when='AFTER')),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='buyer',
            trigger=pgtrigger.compiler.Trigger(name='update_update', sql=pgtrigger.compiler.UpsertTriggerSql(condition='WHEN (OLD.* IS DISTINCT FROM NEW.*)', func='INSERT INTO "pricing_buyerevent" ("active", "company_id", "created_at", "fx_usd_rate", "id", "k9_rmb_each", "name", "notes", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "prices_in_rmb", "ship_to_address", "ship_to_email", "ship_to_name", "ship_to_phone", "slug", "ssd_floor_rmb", "ssd_rmb_per_gb") VALUES (NEW."active", NEW."company_id", NEW."created_at", NEW."fx_usd_rate", NEW."id", NEW."k9_rmb_each", NEW."name", NEW."notes", _pgh_attach_context(), NOW(), \'update\', NEW."id", NEW."prices_in_rmb", NEW."ship_to_address", NEW."ship_to_email", NEW."ship_to_name", NEW."ship_to_phone", NEW."slug", NEW."ssd_floor_rmb", NEW."ssd_rmb_per_gb"); RETURN NULL;', hash='b7610ac7b58964380d842200db126deac1e5c150', operation='UPDATE', pgid='pgtrigger_update_update_2c806', table='pricing_buyer', when='AFTER')),
        ),
        migrations.AddField(
            model_name='ratechangerequest',
            name='buyer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rate_requests', to='pricing.buyer', verbose_name='Comprador'),
        ),
        migrations.AddField(
            model_name='ratechangerequest',
            name='company',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='tenancy.company', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='ratechangerequest',
            name='requested_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Pedido por'),
        ),
        migrations.AddField(
            model_name='ratechangerequest',
            name='reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Revisado por'),
        ),
        migrations.AddField(
            model_name='ratechangerequestevent',
            name='buyer',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to='pricing.buyer', verbose_name='Comprador'),
        ),
        migrations.AddField(
            model_name='ratechangerequestevent',
            name='company',
            field=models.ForeignKey(blank=True, db_constraint=False, editable=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to='tenancy.company', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='ratechangerequestevent',
            name='pgh_context',
            field=models.ForeignKey(db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='pghistory.context'),
        ),
        migrations.AddField(
            model_name='ratechangerequestevent',
            name='pgh_obj',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='events', to='pricing.ratechangerequest'),
        ),
        migrations.AddField(
            model_name='ratechangerequestevent',
            name='requested_by',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Pedido por'),
        ),
        migrations.AddField(
            model_name='ratechangerequestevent',
            name='reviewed_by',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Revisado por'),
        ),
        migrations.AddConstraint(
            model_name='ratechangerequest',
            constraint=models.UniqueConstraint(condition=models.Q(('review_status', 'pending')), fields=('buyer', 'kind'), name='one_pending_rate_per_kind'),
        ),
        migrations.AddConstraint(
            model_name='ratechangerequest',
            constraint=models.CheckConstraint(condition=models.Q(('review_status__in', ['pending', 'approved', 'rejected'])), name='rcr_review_vocab'),
        ),
        migrations.AddConstraint(
            model_name='ratechangerequest',
            constraint=models.CheckConstraint(condition=models.Q(('kind', 'ssd'), ('new_floor__isnull', True), _connector='OR'), name='rcr_floor_only_ssd'),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='ratechangerequest',
            trigger=pgtrigger.compiler.Trigger(name='insert_insert', sql=pgtrigger.compiler.UpsertTriggerSql(func='INSERT INTO "pricing_ratechangerequestevent" ("buyer_id", "company_id", "created_at", "id", "kind", "new_floor", "new_rate", "old_floor", "old_rate", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "requested_by_id", "review_status", "reviewed_at", "reviewed_by_id", "seen_by_partner") VALUES (NEW."buyer_id", NEW."company_id", NEW."created_at", NEW."id", NEW."kind", NEW."new_floor", NEW."new_rate", NEW."old_floor", NEW."old_rate", _pgh_attach_context(), NOW(), \'insert\', NEW."id", NEW."requested_by_id", NEW."review_status", NEW."reviewed_at", NEW."reviewed_by_id", NEW."seen_by_partner"); RETURN NULL;', hash='9f8b2fcf7ce69cd592df3bccc2119c38b71bf744', operation='INSERT', pgid='pgtrigger_insert_insert_4fb24', table='pricing_ratechangerequest', when='AFTER')),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='ratechangerequest',
            trigger=pgtrigger.compiler.Trigger(name='update_update', sql=pgtrigger.compiler.UpsertTriggerSql(condition='WHEN (OLD.* IS DISTINCT FROM NEW.*)', func='INSERT INTO "pricing_ratechangerequestevent" ("buyer_id", "company_id", "created_at", "id", "kind", "new_floor", "new_rate", "old_floor", "old_rate", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "requested_by_id", "review_status", "reviewed_at", "reviewed_by_id", "seen_by_partner") VALUES (NEW."buyer_id", NEW."company_id", NEW."created_at", NEW."id", NEW."kind", NEW."new_floor", NEW."new_rate", NEW."old_floor", NEW."old_rate", _pgh_attach_context(), NOW(), \'update\', NEW."id", NEW."requested_by_id", NEW."review_status", NEW."reviewed_at", NEW."reviewed_by_id", NEW."seen_by_partner"); RETURN NULL;', hash='671ad586b1a679e0bef4b93007d54f126ebf809e', operation='UPDATE', pgid='pgtrigger_update_update_5a6c5', table='pricing_ratechangerequest', when='AFTER')),
        ),
    ]
