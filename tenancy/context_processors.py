"""
tenancy/context_processors.py — papel/empresa nos templates
============================================================
Navegação renderizada por papel (§9 do plano): os templates escondem o que o
papel não pode fazer. Lembrete: isto é UX — a barreira real é o gate da view
(tenancy/access.py).

Uso nos templates:
    {% if wtc_is_manager %} …botão Fechar/Exportar… {% endif %}
    {% if wtc_is_admin %}   …gestão da empresa…     {% endif %}
"""


def tenancy(request):
    from .access import is_unmasked as _is_unmasked

    membership = getattr(request, 'membership', None)
    is_admin = bool(membership and membership.has_role('admin'))
    user = getattr(request, 'user', None)
    superuser = bool(user and getattr(user, 'is_authenticated', False)
                     and user.is_superuser)
    unmasked = _is_unmasked(request)

    return {
        'wtc_membership': membership,
        'wtc_company':    getattr(request, 'company', None),
        'wtc_role':       getattr(request, 'company_role', None),
        # Hierarquia embutida: admin também é manager; manager também é operator.
        'wtc_is_operator': membership is not None,
        'wtc_is_manager':  bool(membership and membership.has_role('manager')),
        'wtc_is_admin':    is_admin,
        # ── F12+ / handoff de design: objeto ÚNICO de acesso para o mascaramento
        #    na UI (espelha o access.js do protótipo). ⚠ Isto é UX — a barreira
        #    REAL é o gate da view + o SERVIDOR omitir os campos sigilosos do
        #    JSON/HTML. NUNCA confie só nestes flags no template.
        #    Matriz (handoff §Regra central): operador/gerente = mascarado;
        #    admin da empresa = +preço +vendas; plataforma/superuser =
        #    unmasked +preço +debug.
        'access': {
            'is_unmasked':   unmasked,
            'can_see_price': unmasked or is_admin,
            # ⚠ A matriz do handoff diz plataforma=❌ em vendas; hoje admin inclui
            #   o dono (eMiner é a plataforma E vende) → mantido admin p/ não tirar
            #   o Vendas de quem usa. Confirmar a regra com o dono.
            'can_sales':     is_admin,
            'can_debug':     superuser,
            'role_tag': ('Plataforma' if superuser
                         else 'Admin' if is_admin
                         else membership.get_role_display() if membership
                         else ''),
        },
    }
