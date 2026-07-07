# T3 — passo 2 de 3 (PLANO_MULTITENANT.md §5.2): BACKFILL das colunas company.
#
# Regras (determinísticas, sem input manual — auditadas em teste):
#   1. Lote SEM empresa herda a empresa do Membership ATIVO de quem o abriu
#      (`operator`); sem vínculo, cai na primeira Company (pk) — a empresa #1
#      é a eMiner por construção (bootstrap_tenancy).
#   2. PRODUÇÃO no primeiro deploy: existe lote mas NENHUMA Company (o
#      bootstrap ainda não rodou lá) → esta migração CRIA a eMiner
#      (slug='eminer') para o backfill não quebrar o build. O
#      bootstrap_tenancy posterior faz get_or_create com o MESMO nome e só
#      completa papéis/contador — rode-o com --company eMiner (exato).
#   3. Filhos (InventoryEntry/PendingEntry/RejectedEntry) herdam do lote
#      (denormalização §5.2 — o RLS da T4 precisa da coluna local).
#
# Reversível: o reverse é no-op (as colunas somem revertendo a 0011).
# ⚠ Antes de rodar em banco vivo: backup fresco (CLAUDE.md §2.1b.c).

from django.db import migrations
from django.db.models import OuterRef, Subquery


def backfill(apps, schema_editor):
    Lot = apps.get_model('estoque', 'Lot')
    Company = apps.get_model('tenancy', 'Company')
    Membership = apps.get_model('tenancy', 'Membership')

    orphan_lots = Lot.objects.filter(company__isnull=True)

    if orphan_lots.exists() and not Company.objects.exists():
        # Produção, primeiro deploy do multi-tenant: o catálogo vivo é da
        # eMiner. Nome/slug EXATOS aos do bootstrap_tenancy (§16 do plano).
        Company.objects.create(name='eMiner', slug='eminer')

    default_company = Company.objects.order_by('pk').first()

    for lot in orphan_lots.iterator():
        membership = (Membership.objects
                      .filter(user_id=lot.operator_id, active=True)
                      .order_by('pk').first())
        lot.company_id = (membership.company_id if membership
                          else default_company.pk)
        lot.save(update_fields=['company'])

    # Filhos herdam do lote — set-based (Subquery), sem loop por linha.
    for name in ('InventoryEntry', 'PendingEntry', 'RejectedEntry'):
        Model = apps.get_model('estoque', name)
        Model.objects.filter(company__isnull=True).update(
            company_id=Subquery(
                Lot.objects.filter(pk=OuterRef('lot_id')).values('company_id')[:1]))


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0011_t3_company_nullable'),
        ('tenancy', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
