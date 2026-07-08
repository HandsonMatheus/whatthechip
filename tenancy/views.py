"""
tenancy/views.py — set_language com persistência da preferência (i18n)
=======================================================================
Envolve a view nativa ``django.views.i18n.set_language`` (que grava o cookie
``django_language`` e redireciona de volta) e, se o usuário está LOGADO,
persiste a escolha em ``UserLanguage`` — assim a preferência segue a conta em
qualquer dispositivo (camada 1 da cadeia de resolução; ver I18N.md §3).

Anônimo: comportamento idêntico ao Django puro (só cookie). O template não
muda nada: continua postando para ``{% url 'set_language' %}``.
"""

from django.conf import settings
from django.views.i18n import set_language as _django_set_language


def set_language(request):
    """POST language=<código> → cookie (Django) + preferência no banco (logado)."""
    response = _django_set_language(request)

    lang = request.POST.get('language')
    user = getattr(request, 'user', None)
    if (
        request.method == 'POST'
        and lang
        and lang in {code for code, _name in settings.LANGUAGES}
        and user is not None
        and user.is_authenticated
    ):
        # Import tardio (padrão do app): não toca o registry na importação.
        from .models import UserLanguage
        UserLanguage.objects.update_or_create(
            user=user, defaults={'language': lang})

    return response
