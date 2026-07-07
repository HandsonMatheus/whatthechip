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


@contextmanager
def company_scope(company):
    """Escopo explícito para comandos/jobs/testes.

    Aceita Company, id int, ou None (útil p/ simular "sem escopo" em teste)::

        with company_scope(eminer):
            export_lotes()   # managers escopados enxergam SÓ a eminer
    """
    cid = getattr(company, 'pk', company)
    token = _current_company_id.set(cid)
    try:
        yield cid
    finally:
        _current_company_id.reset(token)


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
