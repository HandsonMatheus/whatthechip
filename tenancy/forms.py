"""
tenancy/forms.py — formulário do onboarding de empresa (T6)
============================================================
PLANO_MULTITENANT §17.2 (E1): a PLATAFORMA cria "empresa + primeiro admin
(+ filial opcional) em < 5 min sem tocar código" (O5). O formulário valida; a
criação em si (3-4 objetos, atômica) vive na view ``company_new``.

O slug passa pelo ``validate_company_slug`` (B3) — formato DNS + reservados —
além do unique do banco. Unicidade de nome/slug/usuário é checada aqui com
``iexact`` de propósito: "ERecyclo" vs "erecyclo" seria confusão operacional
mesmo que o banco (case-sensitive) aceitasse os dois.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _lazy

from .models import Company, validate_company_slug


class CompanyOnboardingForm(forms.Form):
    company_name = forms.CharField(
        label=_lazy('Nome da empresa'), max_length=120,
        help_text=_lazy('Nome comercial exato (ex.: "eRecyclo").'))
    slug = forms.SlugField(
        label=_lazy('Slug — vira o subdomínio do cliente'), max_length=60,
        validators=[validate_company_slug],
        help_text=_lazy('Quase-permanente: minúsculas, dígitos e hífen '
                        '(ex.: "erecyclo" → erecyclo.whatthechip.app).'))
    branch_name = forms.CharField(
        label=_lazy('Filial (opcional)'), max_length=120, required=False,
        help_text=_lazy('Empresa de uma bancada só não precisa de filial.'))
    admin_username = forms.CharField(
        label=_lazy('Usuário do primeiro admin'), max_length=150)
    admin_email = forms.EmailField(
        label=_lazy('E-mail do primeiro admin (opcional)'), required=False)
    admin_password = forms.CharField(
        label=_lazy('Senha provisória'), min_length=8,
        widget=forms.PasswordInput(render_value=False),
        help_text=_lazy('Mínimo 8 caracteres. Entregue ao cliente por canal '
                        'seguro; a troca é feita pela plataforma (sem '
                        'autosserviço no v1).'))

    def clean_company_name(self):
        name = self.cleaned_data['company_name'].strip()
        if Company.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError(
                _lazy('Já existe empresa com este nome.'), code='name_taken')
        return name

    def clean_slug(self):
        slug = self.cleaned_data['slug'].strip()
        if Company.objects.filter(slug__iexact=slug).exists():
            raise forms.ValidationError(
                _lazy('Este slug já está em uso por outra empresa.'),
                code='slug_taken')
        return slug

    def clean_admin_username(self):
        username = self.cleaned_data['admin_username'].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                _lazy('Já existe um usuário com este nome — o primeiro admin '
                      'é sempre uma conta NOVA.'), code='user_taken')
        return username
