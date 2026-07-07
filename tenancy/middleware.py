"""
tenancy/middleware.py — resolve a empresa da request (PLANO_MULTITENANT.md §6)
===============================================================================
Depois do AuthenticationMiddleware: pega o Membership ATIVO do usuário logado
(primeira empresa ativa — decisão §14.7 do plano, v1) e publica:

    request.membership   → Membership | None
    request.company      → Company | None
    request.company_role → 'operator' | 'manager' | 'admin' | None

…e seta o contextvar de escopo (tenancy/scope.py) pela duração da request,
resetando SEMPRE no finally (a thread/worker é reciclada entre requests — escopo
vazado seria mistura de empresas).

T4 (Camada B — RLS): no Postgres, ESTE middleware abre a transação externa da
request e emite os GUCs que as policies leem, TRANSACTION-LOCAL
(``set_config(..., local=True)`` ≡ SET LOCAL):

    app.company_id → empresa do vínculo (linhas da empresa)
    app.platform   → '1' para superuser (plataforma enxerga tudo — Django admin)

⚠ Por que o atomic é DESTE middleware (correção §6.2 da revisão 2026-07-06):
``ATOMIC_REQUESTS`` abre a transação só em volta da VIEW — um SET LOCAL emitido
por middleware fora dela seria no-op. Transaction-local é o único modo seguro
com PgBouncer em transaction mode (a conexão é reciclada entre transações —
variável de SESSÃO vazaria entre empresas).

Usuário anônimo/sem vínculo → nada de GUC → com FORCE RLS o banco devolve ZERO
linhas das tabelas de estoque (fail-closed também na Camada B). Quem decide o
que fazer é o gate de view (403) — o middleware não bloqueia páginas públicas.
"""

from django.db import connection, transaction

from .scope import _set_guc, reset_current_company, set_current_company


class TenancyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        membership = self._resolve_membership(request)

        request.membership   = membership
        request.company      = membership.company if membership else None
        request.company_role = membership.role if membership else None

        token = set_current_company(membership.company_id if membership else None)
        try:
            if connection.vendor == 'postgresql':
                # T4: transação da request é NOSSA (ver docstring) — o GUC
                # transaction-local morre junto com ela, PgBouncer-safe.
                with transaction.atomic():
                    self._emit_rls_gucs(request, membership)
                    return self.get_response(request)
            return self.get_response(request)          # SQLite (testes): sem RLS
        finally:
            # SEMPRE limpa — worker reaproveitado não pode herdar escopo.
            reset_current_company(token)

    @staticmethod
    def _emit_rls_gucs(request, membership):
        user = getattr(request, 'user', None)
        is_platform = bool(user is not None and user.is_authenticated
                           and user.is_superuser)
        if membership is None and not is_platform:
            return                                      # anônimo: nada a emitir
        with connection.cursor() as cur:
            if membership is not None:
                _set_guc(cur, 'app.company_id',
                         str(membership.company_id), local=True)
            if is_platform:
                # Plataforma (superuser): policies liberam TODAS as linhas —
                # é o Django admin operando acima das empresas (§8).
                _set_guc(cur, 'app.platform', '1', local=True)

    @staticmethod
    def _resolve_membership(request):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return None
        # Import tardio: evita tocar o app registry na importação do módulo.
        from .models import Membership
        return (
            Membership.objects
            .filter(user=user, active=True, company__active=True)
            .select_related('company', 'branch')
            .order_by('pk')          # v1: primeira empresa ativa (§14.7)
            .first()
        )
