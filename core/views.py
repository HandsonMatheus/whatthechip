# -*- coding: utf-8 -*-
"""
core/views.py — páginas de ERRO da plataforma
==============================================
Hoje só o **403** (registrado como ``handler403`` nas DUAS URLconfs — canônica
``core/urls.py`` e de tenant ``core/urls_tenant.py``).

Por quê (dono, 2026-08-17)
--------------------------
O 403 padrão do Django é texto cru ("403 Forbidden"), sem cabeçalho nenhum:
quem cai nele **não descobre com qual conta está logado nem tem como sair**.
Como a sessão vale em TODOS os subdomínios (``SESSION_COOKIE_DOMAIN='.<domínio>'``
— settings §T7), testar o sistema com várias contas significa bater nessa
parede o tempo todo e ter que limpar cookie na mão pra escapar.

⚠ Isto é UX do ERRO — **não afrouxa gate nenhum**. O corpo só mostra o que o
PRÓPRIO requisitante já sabe: a conta dele, o papel dele, a empresa dele e o
endereço que ele digitou. NADA da empresa/página que barrou — em especial
``request.tenant_host_company`` NUNCA entra no contexto (§10.2: revelar de quem
é o subdomínio é enumeração de cliente). Quem tem que continuar barrando é o
gate da view (``tenancy/access.py``) e o middleware — esta página só explica.

Fora do alcance daqui (de propósito): ``/chips/search/`` e ``/chips/decode/``
devolvem ``JsonResponse(status=403)`` na própria view (F12 — negativa curta,
sem corpo), então NÃO passam por este handler e o cadeado
``_assert_403_sem_vazamento`` (chips/tests.py) continua valendo.
"""

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.template.loader import render_to_string

# Shell de cima: logado usa o MESMO cabeçalho do painel (menu, empresa, usuário,
# papel, idioma e o botão Sair — que é o ponto do exercício). Anônimo não tem
# menu pra mostrar: cai num casco mínimo com o link de entrar.
SHELL_LOGADO  = 'estoque/base_estoque.html'
SHELL_ANONIMO = '403_shell_anon.html'


def permission_denied(request, exception=None, template_name='403.html'):
    """``handler403`` — a página de "Acesso negado" com o menu do site.

    Recebe a ``PermissionDenied`` levantada pela view (``role_required`` /
    ``platform_required`` / gates locais) OU pelo ``HostTenantMiddleware``
    (host≠vínculo). ``str(exception)`` é a mensagem que o próprio código
    escreveu para o usuário — todas marcadas p/ tradução na origem.

    ⚠ Middleware x view: quando quem levanta é o middleware, o Django ainda não
    trocou a URLconf da thread (``set_urlconf`` só roda no ``resolve_request``),
    então o ``{% url %}`` do shell resolve pela canônica; quando é a view, pela
    de tenant. Os NOMES existem nas duas (levantamento em core/urls_tenant.py),
    logo o template renderiza igual nos dois casos — se algum dia um nome sumir
    de uma delas, a página de erro viraria 500 (``NoReverseMatch``). O teste
    ``Erro403Tests`` prende os dois caminhos.
    """
    motivo = str(exception).strip() if exception else ''

    # htmx (bancada/estoque): devolver o documento inteiro aqui só suja o
    # ``responseText`` — o htmx não faz swap de 4xx por padrão. Fragmento curto.
    if request.headers.get('HX-Request') == 'true':
        return HttpResponseForbidden(render_to_string(
            '403_htmx.html', {'wtc_403_motivo': motivo}, request=request))

    logado = bool(getattr(getattr(request, 'user', None), 'is_authenticated',
                          False))
    return render(request, template_name, {
        'wtc_403_motivo':   motivo,
        'wtc_403_base':     SHELL_LOGADO if logado else SHELL_ANONIMO,
        # Saída de emergência do host de tenant: o endereço CANÔNICO sempre
        # aceita a conta de qualquer empresa. Só o domínio (público, está na
        # barra do navegador) — nunca o slug da empresa dona do host.
        'wtc_403_canonico': _canonico(request),
    }, status=403)


def _canonico(request) -> str:
    """URL do host canônico quando a request veio de um subdomínio de tenant.

    Vazio no host canônico (o botão não aparece) e vazio sem
    ``WTC_TENANT_DOMAIN`` (feature multi-host desligada — settings §T7)."""
    dominio = (getattr(settings, 'WTC_TENANT_DOMAIN', '') or '').strip().lower()
    if not dominio:
        return ''
    host = request.get_host().split(':')[0].lower()
    if host == dominio or not host.endswith('.' + dominio):
        return ''
    return f'{request.scheme}://{dominio}/'
