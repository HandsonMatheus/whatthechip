"""
tenancy/ui.py — canary de frontend POR EMPRESA (E5 — PLANO_MULTITENANT §17.7)
==============================================================================
Deploy de código é GLOBAL (1 serviço, 1 banco); o rollout por cliente vem
daqui: com ``Company.ui_v2`` ligado, ``ui()`` devolve ``[v2, atual]`` e o
``render()``/``select_template`` do Django usa o PRIMEIRO template que
existe — fallback automático tela a tela (o redesign migra por partes e os
templates atuais nunca são tocados; desligar o flag = rollback instantâneo).

De quem é o flag: do VÍNCULO (``request.company`` — mesma regra do escopo,
§10.2). Anônimo em host de tenant segue a empresa do host
(``request.tenant_host_company`` — ex.: tela de login do subdomínio).
Anônimo no canônico = sempre o atual.

Convenção de nome: 'estoque/painel.html' → 'estoque/v2/painel.html' (o
``v2/`` entra depois do 1º segmento; sem barra: 'base.html' →
'v2/base.html'). Partials idem: 'estoque/partials/confirm_card.html' →
'estoque/v2/partials/confirm_card.html'. Um template v2 que ``{% extends %}``
ou ``{% include %}`` deve apontar EXPLICITAMENTE pros caminhos v2 — quem
resolve por request são só as VIEWS (via este helper).
"""


def v2_name(template_name):
    """'estoque/painel.html' → 'estoque/v2/painel.html' (função pura)."""
    head, sep, rest = template_name.partition('/')
    return f'{head}/v2/{rest}' if sep else f'v2/{template_name}'


def ui(request, template_name):
    """Nome(s) de template pro ``render()``: a própria string (flag OFF) ou
    a lista ``[v2, atual]`` (flag ON — o select_template do Django usa o
    primeiro que existir)."""
    company = (getattr(request, 'company', None)
               or getattr(request, 'tenant_host_company', None))
    if company is None or not getattr(company, 'ui_v2', False):
        return template_name
    return [v2_name(template_name), template_name]
