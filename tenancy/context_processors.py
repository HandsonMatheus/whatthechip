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
    membership = getattr(request, 'membership', None)
    return {
        'wtc_membership': membership,
        'wtc_company':    getattr(request, 'company', None),
        'wtc_role':       getattr(request, 'company_role', None),
        # Hierarquia embutida: admin também é manager; manager também é operator.
        'wtc_is_operator': membership is not None,
        'wtc_is_manager':  bool(membership and membership.has_role('manager')),
        'wtc_is_admin':    bool(membership and membership.has_role('admin')),
    }
