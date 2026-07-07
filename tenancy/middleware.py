"""
tenancy/middleware.py — resolve a empresa da request (PLANO_MULTITENANT.md §6.1)
=================================================================================
Depois do AuthenticationMiddleware: pega o Membership ATIVO do usuário logado
(primeira empresa ativa — decisão §14.7 do plano, v1) e publica:

    request.membership   → Membership | None
    request.company      → Company | None
    request.company_role → 'operator' | 'manager' | 'admin' | None

…e seta o contextvar de escopo (tenancy/scope.py) pela duração da request,
resetando SEMPRE no finally (a thread/worker é reciclada entre requests — escopo
vazado seria mistura de empresas).

Usuário anônimo, sem vínculo ativo, ou de empresa desativada → tudo None; quem
decide o que fazer com isso são os gates de view (tenancy/access.py) — o
middleware não bloqueia nada (páginas públicas continuam públicas).

T4 (RLS): este middleware passa a abrir a transação da request e emitir
``SET LOCAL app.company_id = <id>`` logo após entrar nela (SET LOCAL por
TRANSAÇÃO, nunca SET por sessão — único modo seguro com PgBouncer em transaction
mode). Ver nota em tenancy/scope.py sobre por que o atomic é DESTE middleware.
"""

from .scope import reset_current_company, set_current_company


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
            return self.get_response(request)
        finally:
            # SEMPRE limpa — worker reaproveitado não pode herdar escopo.
            reset_current_company(token)

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
            .select_related('company')
            .order_by('pk')          # v1: primeira empresa ativa (§14.7)
            .first()
        )
