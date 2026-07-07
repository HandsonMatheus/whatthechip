"""
tenancy/access.py — gates de PAPEL para views (PLANO_MULTITENANT.md §8)
========================================================================
Duas camadas independentes: o gate decide o PAPEL (403); o escopo de empresa é
do middleware/manager. Esconder botão no template NUNCA é a única barreira — a
barreira real é aqui, na view.

Matriz (§8, decisão do dono 2026-07-06):
    operator → buscar/classificar, adicionar a lote ABERTO
    manager  → + abrir/fechar lote, fila de conferência, export
    admin    → + gestão da empresa (usuários/filiais; preço no projeto irmão)

Sem bypass de is_superuser DE PROPÓSITO: plataforma navegando o app usa um
Membership real (o dono tem papel admin na eMiner — decisão §14.4). Superuser
sem vínculo fica no Django admin, que é a ferramenta de plataforma.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def role_required(min_role: str):
    """Decorator de view: exige login + Membership ativo + papel >= ``min_role``.

    - Anônimo            → redirect para o login (comportamento do login_required);
    - Logado sem vínculo → 403 (conta existe mas não pertence a empresa ativa);
    - Papel insuficiente → 403.

    Uso (substitui o @login_required — ele já cuida do redirect)::

        @role_required('manager')
        def lot_close(request, lot_pk): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            membership = getattr(request, 'membership', None)
            if membership is None:
                # F6 (PRECIFICACAO §7.1): conta de COMPRADOR é externa — o
                # vínculo é Buyer.users, não Membership. Em vez de 403, a
                # lançadeira (/painel/) e qualquer rota de estoque mandam o
                # parceiro pro dashboard DELE. Import lazy: tenancy não
                # depende do pricing no load do app.
                try:
                    from pricing.models import Buyer
                    _e_comprador = Buyer.all_companies.filter(
                        users=request.user, active=True).exists()
                except Exception:
                    _e_comprador = False
                if _e_comprador:
                    from django.shortcuts import redirect
                    return redirect('/partner/')
                raise PermissionDenied(
                    'Sua conta não está vinculada a nenhuma empresa ativa. '
                    'Fale com o administrador.')
            if not membership.has_role(min_role):
                raise PermissionDenied(
                    'Seu papel não permite esta ação.')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


class RoleRequiredMixin:
    """Versão para class-based views (nenhuma no app hoje; fica pronta)::

        class LotCloseView(RoleRequiredMixin, View):
            required_role = 'manager'
    """
    required_role = 'operator'

    def dispatch(self, request, *args, **kwargs):
        gate = role_required(self.required_role)(super().dispatch)
        return gate(request, *args, **kwargs)
