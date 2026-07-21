"""
WhatTheChip — Tenancy (multi-empresa)
======================================
Os três modelos da fundação (PLANO_MULTITENANT.md §5.1):

    Company    → a EMPRESA-cliente. É a fronteira do isolamento (a chave do
                 futuro RLS). Empresa #1 = eMiner (criada pelo bootstrap_tenancy).
    Branch     → filial/planta ("Matriz", "Bancada CDE"). Sub-unidade
                 organizacional — NÃO é tenant; segurança é sempre por empresa.
    Membership → o vínculo usuário×empresa com PAPEL (admin/manager/operator).
                 Uma conta pode ter papel em mais de uma empresa (consultor);
                 no v1 o middleware usa a primeira ativa.

Regras estruturais (invioláveis):
  - PROTECT, não CASCADE, em company/branch: apagar empresa por acidente não
    pode levar lotes/históricos junto. Desativação é ``active=False``.
  - pghistory nos três modelos: mudança de papel é EVENTO DE SEGURANÇA.
  - "Plataforma" (o dono do WTC) = ``is_superuser`` — acima das empresas, não é
    role de Membership. Para navegar o app, o dono tem um Membership normal na
    eMiner (decisão 2026-07-06, §14.4).
"""

import pghistory

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
# i18n (I18N.md §5/CLAUDE.md §6): rótulo de choices EXIBIDO a usuário final
# (ex.: crachá de papel no header do painel) passa por gettext_lazy. O VALOR
# ('operator'…) é chave de lógica — nunca traduz.
from django.utils.translation import gettext_lazy as _lazy


@pghistory.track()  # auditoria: criação/desativação de empresa é evento de plataforma
class Company(models.Model):
    """Empresa-cliente (tenant). A fronteira do isolamento comercial."""

    name   = models.CharField(max_length=120, unique=True, verbose_name='Nome')
    slug   = models.SlugField(max_length=60, unique=True, verbose_name='Slug',
                              help_text='Identificador para rotas/domínio futuros (ex.: "eminer").')
    active = models.BooleanField(default=True, verbose_name='Ativa',
                                 help_text='Desativar ≠ deletar — o histórico fica.')
    # F12 (máscara de categoria, dono 2026-07-17): o conhecimento de chips é o
    # ativo do NEGÓCIO — empresa-CLIENTE vê só o código opaco C-### (bancada,
    # export, OV, fatura); a empresa DA PLATAFORMA (eMiner) vê os rótulos
    # reais. Marcar só a(s) empresa(s) dona(s) do WhatTheChip.
    is_platform = models.BooleanField(
        default=False, verbose_name='Empresa da plataforma',
        help_text='Dona do WhatTheChip: usuários dela veem os rótulos REAIS '
                  'de categoria. Empresas-cliente veem só o código C-### '
                  '(F12 — proteção do conhecimento).')
    # Branding por empresa (logo nas telas do app / subdomínio futuro — §10).
    # ⚠ Em produção (Render) o filesystem é EFÊMERO: upload some no próximo
    # deploy. Antes de usar logo em prod: disco persistente do Render ou S3.
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True,
                             verbose_name='Logo',
                             help_text='PNG/JPG. Em produção exige disco '
                                       'persistente (Render) ou S3 — ver nota.')
    # Contador atômico da numeração de lote POR-EMPRESA (T2, §7): o lot_create
    # trava esta linha com select_for_update e incrementa — elimina a corrida do
    # antigo Max('number')+1. Seed da eMiner = max atual, feito no bootstrap_tenancy.
    last_lot_number = models.PositiveIntegerField(
        default=0, verbose_name='Último nº de lote',
        help_text='Contador atômico da numeração de lote (T2). Não editar à mão.')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criada em')
    notes      = models.TextField(blank=True, default='', verbose_name='Notas')

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['name']

    def __str__(self):
        return self.name


@pghistory.track()  # auditoria: filiais fazem parte da estrutura da empresa
class Branch(models.Model):
    """Filial/planta de uma empresa. NULLABLE em tudo no v1 — empresa pequena
    (1 bancada) não é obrigada a criar filial."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT,
                                related_name='branches', verbose_name='Empresa')
    name    = models.CharField(max_length=120, verbose_name='Nome')
    active  = models.BooleanField(default=True, verbose_name='Ativa')

    class Meta:
        verbose_name = 'Filial'
        verbose_name_plural = 'Filiais'
        ordering = ['company__name', 'name']
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'],
                                    name='unique_branch_company_name'),
        ]

    def __str__(self):
        return f'{self.company.name} · {self.name}'


@pghistory.track()  # auditoria: mudança de papel é evento de SEGURANÇA
class Membership(models.Model):
    """Vínculo usuário×empresa com papel. É o que o middleware resolve a cada
    request para definir a empresa (contextvar) e o papel (gates de view)."""

    ROLE_OPERATOR = 'operator'
    ROLE_MANAGER  = 'manager'
    ROLE_ADMIN    = 'admin'
    ROLE_CHOICES = [
        (ROLE_OPERATOR, _lazy('Operador')),
        (ROLE_MANAGER,  _lazy('Gerente')),
        (ROLE_ADMIN,    _lazy('Admin da empresa')),
    ]
    #: Hierarquia: papel maior herda as permissões do menor (§8 do plano).
    ROLE_LEVEL = {ROLE_OPERATOR: 1, ROLE_MANAGER: 2, ROLE_ADMIN: 3}

    user    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='memberships', verbose_name='Usuário')
    company = models.ForeignKey(Company, on_delete=models.PROTECT,
                                related_name='memberships', verbose_name='Empresa')
    branch  = models.ForeignKey(Branch, on_delete=models.PROTECT,
                                null=True, blank=True,
                                related_name='memberships', verbose_name='Filial')
    role    = models.CharField(max_length=10, choices=ROLE_CHOICES,
                               default=ROLE_OPERATOR, verbose_name='Papel')
    active  = models.BooleanField(default=True, verbose_name='Ativo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    class Meta:
        verbose_name = 'Vínculo (papel)'
        verbose_name_plural = 'Vínculos (papéis)'
        ordering = ['company__name', 'user__username']
        constraints = [
            models.UniqueConstraint(fields=['user', 'company'],
                                    name='unique_membership_user_company'),
            # Vocabulário travado no BANCO (mesmo padrão do confidence_vocab do
            # KnownPart): escrita ad-hoc com papel inválido falha no insert.
            models.CheckConstraint(
                check=Q(role__in=['operator', 'manager', 'admin']),
                name='membership_role_vocab'),
        ]
        indexes = [
            models.Index(fields=['company', 'role'], name='membership_company_role'),
        ]

    def __str__(self):
        return f'{self.user.username} @ {self.company.name} ({self.get_role_display()})'

    # ── Papel ────────────────────────────────────────────────────────────────
    @property
    def role_level(self) -> int:
        return self.ROLE_LEVEL.get(self.role, 0)

    def has_role(self, min_role: str) -> bool:
        """True se o papel deste vínculo é >= ``min_role`` na hierarquia.
        Ex.: um admin ``has_role('manager')`` → True."""
        need = self.ROLE_LEVEL.get(min_role)
        if need is None:
            raise ValueError(f'Papel desconhecido: {min_role!r}')
        return self.role_level >= need

    # ── Consistência filial×empresa (portão no MODELO, não só na view) ──────
    def clean(self):
        super().clean()
        if self.branch_id and self.branch.company_id != self.company_id:
            raise ValidationError(
                {'branch': 'A filial deve pertencer à mesma empresa do vínculo.'})

    def save(self, *args, **kwargs):
        # Guard barato e direcionado (não full_clean: uniques já são constraint).
        self.clean()
        return super().save(*args, **kwargs)


def _language_choices():
    """Choices dinâmicos = settings.LANGUAGES (fonte única dos idiomas ativos).

    Callable (Django 5+): idioma novo em settings aparece no admin sem migração —
    é o que mantém "idioma novo ≈ 1 arquivo .po" (I18N.md §4)."""
    from django.conf import settings as _s
    return list(_s.LANGUAGES)


class UserLanguage(models.Model):
    """Preferência de idioma da PESSOA (i18n — I18N.md §3).

    GLOBAL (sem ``company``): a língua é do usuário, não da empresa — um técnico
    chinês numa empresa paraguaia lê a UI em 中文. Camada 1 da cadeia de
    resolução (vence cookie e Accept-Language via ``UserLanguageMiddleware``).

    Vazio = sem preferência → cai na detecção automática (cookie → região).
    Escrita: o próprio usuário pelo seletor do topo (``tenancy.views.set_language``)
    ou o dono no admin ao criar a conta (não há cadastro público).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='language_pref', verbose_name='Usuário')
    language = models.CharField(
        max_length=10, blank=True, default='', choices=_language_choices,
        verbose_name='Idioma',
        help_text='Vazio = automático (cookie do navegador → idioma do navegador/região).')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        verbose_name = 'Preferência de idioma'
        verbose_name_plural = 'Preferências de idioma'

    def __str__(self):
        return f'{self.user.username} → {self.language or "automático"}'
