"""
tenancy/scope.py — o escopo de empresa da request (Camada A do isolamento)
===========================================================================
PLANO_MULTITENANT.md §6.1. Um ``ContextVar`` guarda a empresa "corrente":

  - Em request web, o ``TenancyMiddleware`` seta a partir do Membership ativo.
  - Fora de request (comando, job, shell), o escopo é SEMPRE explícito:
        with company_scope(company):
            ...
    Comando tenant-scoped sem escopo declarado não passa em review.

FAIL-CLOSED é a decisão-chave: código tenant-scoped rodando sem escopo EXPLODE
(``CompanyScopeMissing``) em vez de vazar "todos". O escape explícito e gritante
é o manager ``all_companies`` (só em código de plataforma, auditável por grep).

Na T1 apenas os utilitários existem; os modelos do estoque adotam o
``CompanyScopedManager`` na T3 (retrofit), junto com:
  - ``objects = CompanyScopedManager()`` (caminho padrão JÁ filtrado);
  - ``all_companies = models.Manager()`` (escape de plataforma);
  - ``Meta.base_manager_name = 'all_companies'`` — ⚠ OBRIGATÓRIO: travessias
    internas do Django (related managers, validação, admin) usam o base manager;
    sem isso elas passariam pelo manager fail-closed e explodiriam fora de request.

Na T4 entra a Camada B (RLS no Postgres): o middleware passa a emitir
``SET LOCAL app.company_id`` DENTRO da transação — atenção: o middleware precisa
abrir ele mesmo o ``transaction.atomic()`` externo em volta do ``get_response``
(``ATOMIC_REQUESTS`` abre a transação só em volta da VIEW; um SET LOCAL emitido
por middleware fora dela seria no-op).
"""

from contextlib import contextmanager
from contextvars import ContextVar

from django.db import models

#: Empresa corrente (id) — None = sem escopo (fail-closed em quem exigir).
_current_company_id: ContextVar[int | None] = ContextVar(
    'wtc_current_company_id', default=None)


class CompanyScopeMissing(RuntimeError):
    """Código tenant-scoped executado SEM escopo de empresa (bug de plumbing).
    Nunca capture para "seguir sem filtro" — o fail-closed é o produto."""


def current_company_id() -> int | None:
    """Id da empresa corrente, ou None (sem explodir — para código GLOBAL que
    apenas ANOTA a empresa quando ela existe, ex.: SearchLog.company)."""
    return _current_company_id.get()


def require_company_id() -> int:
    """Id da empresa corrente, ou ``CompanyScopeMissing`` (para código
    tenant-scoped: nunca 'todos' por omissão)."""
    cid = _current_company_id.get()
    if cid is None:
        raise CompanyScopeMissing(
            'Operação tenant-scoped sem escopo de empresa. Em request web o '
            'TenancyMiddleware seta o escopo; em comando/job use '
            '"with company_scope(company):" (ou o manager all_companies, se for '
            'código de PLATAFORMA de propósito).')
    return cid


def set_current_company(company_id: int | None):
    """Seta o escopo cru e devolve o token p/ reset (uso do middleware)."""
    return _current_company_id.set(company_id)


def reset_current_company(token) -> None:
    _current_company_id.reset(token)


def _set_guc(cursor, name: str, value: str, local: bool = False) -> None:
    """Seta um GUC do Postgres (a variável que as policies de RLS leem — T4).
    ``set_config(..., local=True)`` == SET LOCAL (morre no fim da transação —
    o único modo seguro com PgBouncer em transaction mode)."""
    cursor.execute('SELECT set_config(%s, %s, %s)', [name, value, local])


def _read_guc(cursor, name: str) -> str | None:
    cursor.execute("SELECT current_setting(%s, true)", [name])
    return cursor.fetchone()[0]


@contextmanager
def company_scope(company):
    """Escopo explícito para comandos/jobs/testes.

    Aceita Company, id int, ou None (útil p/ simular "sem escopo" em teste)::

        with company_scope(eminer):
            export_lotes()   # managers escopados enxergam SÓ a eminer

    T4: além do contextvar (Camada A), seta o GUC ``app.company_id`` da conexão
    (Camada B — sem ele, com RLS+FORCE ativos, até o dono da tabela lê ZERO
    linhas). Sessão-level com restauração no exit; no SQLite é no-op.
    """
    from django.db import connection

    cid = getattr(company, 'pk', company)
    token = _current_company_id.set(cid)
    use_guc = connection.vendor == 'postgresql'
    guc_prev = None
    if use_guc:
        with connection.cursor() as cur:
            guc_prev = _read_guc(cur, 'app.company_id')
            _set_guc(cur, 'app.company_id', '' if cid is None else str(cid))
    try:
        yield cid
    finally:
        _current_company_id.reset(token)
        if use_guc:
            with connection.cursor() as cur:
                _set_guc(cur, 'app.company_id', guc_prev or '')


@contextmanager
def platform_scope():
    """Escopo de PLATAFORMA para ESCRITA em linha de plataforma — Camada B.

    ⚠ Ele ABRE a transação (``transaction.atomic()``) e emite, DENTRO dela,
    ``SET LOCAL app.platform = '1'`` — o mesmo escape do middleware para
    superuser e de todo RunPython de dados em tabela com RLS (CLAUDE.md §7,
    modelo em ``pricing/migrations/0021``). Use no lugar do ``atomic()`` cru::

        with platform_scope():
            row.save()          # linha de PLATAFORMA (company IS NULL)

    POR QUE existe (bug de prod, comando ``enable_price_row``, 2026-08-17):
    desde ``pricing/0021`` comprador/lista/preço são de PLATAFORMA
    (``company_id IS NULL`` — a tabela do comprador precifica TODAS as
    empresas). As policies viraram um par leitura/escrita:

      · LEITURA  ``tenant_read``: empresa OU plataforma OU ``company IS NULL``
        → o comando LÊ a linha normalmente (por isso o dry-run passa);
      · ESCRITA  ``tenant_upd``/``tenant_ins``: empresa dona OU plataforma OU
        usuário-parceiro → com SÓ o ``app.company_id`` do
        ``scope_command_to_company``, ``NULL = <id>`` é NULL: o UPDATE casa
        **ZERO linhas, em silêncio**.

    E aí vem a pegadinha: o Django não vê erro no UPDATE vazio — o
    ``Model._save_table`` conclui "não existia" e cai no INSERT de fallback,
    que bate no ``WITH CHECK`` e estoura o enganoso *"new row violates
    row-level security policy"* (traceback apontando INSERT de linha NOVA
    numa linha que existe desde o seed).

    ``SET LOCAL`` morre no commit/rollback — PgBouncer-safe, sem restauração
    manual. Dentro de um ``atomic()`` externo o ``atomic()`` daqui vira
    savepoint e o GUC vale até o fim da transação EXTERNA (aceitável: o
    chamador é comando/job de plataforma, dono do próprio ciclo).

    É ESCAPE EXPLÍCITO, auditável por grep — como o manager ``all_companies``:
    só em código de PLATAFORMA. No SQLite (testes) é no-op, só a transação.
    """
    from django.db import connection, transaction

    with transaction.atomic():
        if connection.vendor == 'postgresql':
            with connection.cursor() as cur:
                _set_guc(cur, 'app.platform', '1', local=True)
            yield True
        else:
            yield False


def scope_command_to_company(slug=None, stdout=None):
    """Escopo de empresa para MANAGEMENT COMMANDS (§6.1: fora de request o
    escopo é sempre explícito — comando tenant-scoped sem escopo não passa).

    - ``--company <slug>`` informado → usa essa empresa;
    - omitido e existe UMA empresa ativa → usa-a (instalação single-tenant
      continua ergonômica; continua fail-closed: com 2+ empresas, EXPLODE
      pedindo o slug em vez de escolher sozinho).

    Seta o contextvar do PROCESSO (o comando morre com ele — sem reset) e
    devolve a Company. Chame na PRIMEIRA linha do handle().
    """
    from .models import Company
    if slug:
        try:
            company = Company.objects.get(slug=slug)
        except Company.DoesNotExist:
            raise CompanyScopeMissing(f'Empresa com slug {slug!r} não existe.')
    else:
        active = list(Company.objects.filter(active=True).order_by('pk')[:2])
        if len(active) != 1:
            raise CompanyScopeMissing(
                'Há 0 ou 2+ empresas ativas — identifique com --company <slug>.')
        company = active[0]
    set_current_company(company.pk)
    # T4: comando roda FORA do middleware → seta o GUC do RLS na sessão da
    # conexão do processo (sem ele, com FORCE RLS, as queries leem 0 linhas).
    from django.db import connection
    if connection.vendor == 'postgresql':
        with connection.cursor() as cur:
            _set_guc(cur, 'app.company_id', str(company.pk))
    if stdout is not None:
        stdout.write(f'Escopo de empresa: {company.name} (slug={company.slug})')
    return company


class CompanyScopedManager(models.Manager):
    """Manager padrão dos modelos POR-EMPRESA (adoção na T3 — ver docstring do
    módulo). Filtra TODA queryset pela empresa corrente; sem escopo → explode."""

    def get_queryset(self):
        cid = _current_company_id.get()
        if cid is None:
            # FAIL-CLOSED: sem escopo → ERRO, nunca "todas as empresas".
            raise CompanyScopeMissing(
                f'{self.model.__name__} consultado sem escopo de empresa. '
                'Use company_scope(...) ou, em código de plataforma, o manager '
                'all_companies (explícito e auditável).')
        return super().get_queryset().filter(company_id=cid)


class PlatformSharedManager(CompanyScopedManager):
    """Escopado + PLATAFORMA (dono, 2026-08-03 — revisa a F2 do pricing): a
    empresa vê os registros DELA **e** os de plataforma (``company IS NULL``).

    Nasceu para o ``Buyer``: o comprador é um ATIVO DA PLATAFORMA — a tabela
    de preços dele vale para TODAS as empresas (o modelo de negócio é comissão
    sobre o total), mas a ENTIDADE continua invisível ao cliente (rótulo fixo
    'WhatTheChip' nas telas de empresa, F11.3) e a gestão é só-plataforma.
    Continua FAIL-CLOSED: sem escopo explode igual ao pai. A Camada B espelha
    (pricing/0021: leitura de ``company IS NULL`` liberada; ESCRITA continua
    empresa dona / plataforma / usuário-parceiro)."""

    def get_queryset(self):
        cid = _current_company_id.get()
        if cid is None:
            raise CompanyScopeMissing(
                f'{self.model.__name__} consultado sem escopo de empresa. '
                'Use company_scope(...) ou, em código de plataforma, o manager '
                'all_companies (explícito e auditável).')
        return models.Manager.get_queryset(self).filter(
            models.Q(company_id=cid) | models.Q(company__isnull=True))
