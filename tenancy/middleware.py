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
        is_authenticated = bool(user is not None and user.is_authenticated)
        if not is_authenticated:
            return                                      # anônimo: nada a emitir
        is_platform = user.is_superuser
        with connection.cursor() as cur:
            # app.user_id: identidade p/ policies de AUTO-ACESSO — o caso real
            # é o COMPRADOR (sem Membership → sem app.company_id): a policy do
            # pricing_buyer deixa ele ver O PRÓPRIO buyer (pricing/0010), senão
            # o gate do /partner/ leria zero linhas e 403 (bug de prod
            # 2026-07-09 — o superuser do dev local mascarava, RLS não vale
            # p/ super).
            _set_guc(cur, 'app.user_id', str(user.pk), local=True)
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


class UserLanguageMiddleware:
    """i18n (I18N.md §3): aplica a preferência de idioma SALVA do usuário logado.

    O ``LocaleMiddleware`` já resolveu cookie → Accept-Language (região) → pt-br.
    Este middleware roda DEPOIS (na ordem de request) e, se o usuário tem
    ``UserLanguage.language`` preenchido e suportado, sobrepõe a ativação —
    fechando a cadeia: **preferência no banco > cookie > região > pt-br**.

    Anônimo ou sem preferência → no-op (fica o que o LocaleMiddleware decidiu).
    O idioma preferido segue a conta em qualquer dispositivo — o cookie, não.
    O cabeçalho ``Content-Language`` continua correto: o ``process_response`` do
    LocaleMiddleware (que roda depois, na volta) lê o idioma ATIVO via
    ``get_language()``, que é o que ativamos aqui.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.utils import translation

        # Django admin = superfície de PLATAFORMA, fixa em pt-br (decisão do
        # dono, 2026-07-08 — I18N.md §2.7). Motivo: o chrome do Django traduz
        # sozinho mas nossos verbose_names são PT (admin é só do dono/T1) —
        # híbrido parece quebrado. Fixar = 100% consistente, zero dívida.
        # O APP (bancada, /partner/, site) continua 100% multilíngue.
        if request.path.startswith('/admin/'):
            from django.conf import settings
            translation.activate(settings.LANGUAGE_CODE)
            request.LANGUAGE_CODE = translation.get_language()
            return self.get_response(request)

        lang = self._preferred_language(request)
        if lang:
            translation.activate(lang)
            request.LANGUAGE_CODE = translation.get_language()
        return self.get_response(request)

    @staticmethod
    def _preferred_language(request):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return None
        from django.conf import settings
        from .models import UserLanguage
        pref = (UserLanguage.objects
                .filter(user=user)
                .values_list('language', flat=True)
                .first())
        # Valida contra settings.LANGUAGES: idioma removido do settings deixa de
        # ser aplicado sem quebrar (fail-open para a detecção automática).
        if pref and pref in {code for code, _n in settings.LANGUAGES}:
            return pref
        return None
