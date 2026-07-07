"""
bootstrap_tenancy — backfill da T1: cria a empresa #1 e os papéis nominais.
============================================================================
DRY-RUN POR PADRÃO (regra de ouro #1: o agente propõe, o DONO roda --commit).
Antes de rodar com --commit em banco vivo: backup fresco (Render Export) —
CLAUDE.md §2.1b.c.

O que faz (idempotente — pode rodar de novo para ajustar papéis):
  1. Cria (ou acha) a Company --company, slug derivado ou --slug.
  2. Dá Membership com papel aos usuários nomeados em --admin/--manager/--operator
     (usuário precisa EXISTIR; papel é atualizado se o vínculo já existe).
  3. Seed do contador de lote: last_lot_number = max(Lot.number) atual
     (ajuste da T2 antecipado — o contador já nasce certo).
  4. Tira is_staff de quem NÃO é superuser (Django admin vira só-plataforma, §8).
  5. Invalida TODAS as sessões (usuários relogam e o middleware nasce limpo, §13).
  6. Avisa sobre usuários ativos que ficaram SEM vínculo (terão 403 no estoque).

Exemplo (eMiner):
    python manage.py bootstrap_tenancy --company eMiner \
        --admin dono --manager chefe --operator op1 --operator op2 --commit
"""

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max
from django.utils.text import slugify

from estoque.models import Lot
from tenancy.models import Company, Membership


class Command(BaseCommand):
    help = ('Backfill T1 do multi-tenant: cria a empresa, atribui papéis, seeda o '
            'contador de lote, restringe o Django admin à plataforma e invalida '
            'sessões. Dry-run por padrão; --commit grava.')

    def add_arguments(self, parser):
        parser.add_argument('--company', required=True,
                            help='Nome da empresa (ex.: "eMiner").')
        parser.add_argument('--slug', default='',
                            help='Slug da empresa (default: derivado do nome).')
        parser.add_argument('--admin', action='append', default=[],
                            metavar='USERNAME', help='Usuário com papel admin (repetível).')
        parser.add_argument('--manager', action='append', default=[],
                            metavar='USERNAME', help='Usuário com papel gerente (repetível).')
        parser.add_argument('--operator', action='append', default=[],
                            metavar='USERNAME', help='Usuário com papel operador (repetível).')
        parser.add_argument('--commit', action='store_true',
                            help='Grava de verdade (sem isto: dry-run, nada muda).')

    @transaction.atomic
    def handle(self, *args, **opts):
        commit = opts['commit']
        User = get_user_model()

        roles = [(Membership.ROLE_ADMIN, opts['admin']),
                 (Membership.ROLE_MANAGER, opts['manager']),
                 (Membership.ROLE_OPERATOR, opts['operator'])]

        # ── Validação: usuários existem? papel duplicado? ────────────────────
        named = [u for _, users in roles for u in users]
        dupes = {u for u in named if named.count(u) > 1}
        if dupes:
            raise CommandError(f'Usuário em mais de um papel: {sorted(dupes)}')
        missing = [u for u in named if not User.objects.filter(username=u).exists()]
        if missing:
            raise CommandError(
                f'Usuários inexistentes: {missing}. Crie-os antes (ou corrija o nome).')

        # ── 1. Empresa ───────────────────────────────────────────────────────
        slug = opts['slug'] or slugify(opts['company'])
        company, created = Company.objects.get_or_create(
            name=opts['company'], defaults={'slug': slug})
        self._log(f'Empresa: {company.name!r} (slug={company.slug}) '
                  f'{"CRIADA" if created else "já existia"}')

        # ── 2. Papéis ────────────────────────────────────────────────────────
        for role, users in roles:
            for username in users:
                user = User.objects.get(username=username)
                m, m_created = Membership.objects.update_or_create(
                    user=user, company=company,
                    defaults={'role': role, 'active': True})
                self._log(f'  papel: {username} → {role} '
                          f'({"novo vínculo" if m_created else "vínculo atualizado"})')

        # ── 3. Seed do contador de lote (ajuste da T2, antecipado) ───────────
        # all_companies: comando de plataforma (T3) — olha só os lotes DESTA
        # empresa (pós-backfill 0012 todos têm company). company_scope (T4):
        # com RLS+FORCE, sem o GUC a query leria ZERO linhas e o seed falharia.
        from tenancy.scope import company_scope
        with company_scope(company):
            max_lot = (Lot.all_companies.filter(company=company)
                       .aggregate(Max('number'))['number__max'])
        if max_lot is not None and max_lot > company.last_lot_number:
            self._log(f'Contador de lote: last_lot_number {company.last_lot_number} '
                      f'→ {max_lot} (max atual)')
            company.last_lot_number = max_lot
            company.save(update_fields=['last_lot_number'])

        # ── 4. Django admin só-plataforma ────────────────────────────────────
        demoted = list(User.objects.filter(is_staff=True, is_superuser=False)
                       .values_list('username', flat=True))
        if demoted:
            self._log(f'is_staff removido (admin vira só-plataforma): {demoted}')
            User.objects.filter(is_staff=True, is_superuser=False).update(is_staff=False)
        else:
            self._log('is_staff: nada a remover (só superusers têm staff).')

        # ── 6. Quem ficou de fora (403 no estoque até ganhar vínculo) ────────
        linked = set(named)
        orphans = list(User.objects.filter(is_active=True, is_superuser=False)
                       .exclude(username__in=linked)
                       .exclude(memberships__active=True)
                       .values_list('username', flat=True).distinct())
        if orphans:
            self.stdout.write(self.style.WARNING(
                f'⚠ Usuários ativos SEM vínculo (terão 403 no estoque): {orphans}'))

        # ── 5. Sessões + commit/rollback ─────────────────────────────────────
        if commit:
            n_sessions = Session.objects.count()
            Session.objects.all().delete()
            self._log(f'Sessões invalidadas: {n_sessions} (todos relogam).')
            self.stdout.write(self.style.SUCCESS('✔ COMMIT aplicado.'))
        else:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado. Rode com --commit para aplicar '
                '(antes: backup fresco do banco).'))

    def _log(self, msg):
        self.stdout.write(msg)
