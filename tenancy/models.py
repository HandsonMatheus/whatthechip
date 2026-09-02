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

import re
from decimal import Decimal

import pghistory

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
# i18n (I18N.md §5/CLAUDE.md §6): rótulo de choices EXIBIDO a usuário final
# (ex.: crachá de papel no header do painel) passa por gettext_lazy. O VALOR
# ('operator'…) é chave de lógica — nunca traduz.
from django.utils.translation import gettext_lazy as _lazy


# ── B3 (T6/T7 — PLANO_MULTITENANT §10.4/§17.2): o slug vira HOSTNAME ─────────
# Na T7 o slug é o subdomínio público do cliente (erecyclo.whatthechip.app) e é
# quase-permanente. Duas travas, congeladas em CÓDIGO (não em dado):
#
# 1) FORMATO = rótulo DNS (RFC 1123): minúsculas/dígitos/hífen, não começa nem
#    termina com hífen, máx. 63 chars. ⚠ O SlugField do Django ACEITA "_" e
#    maiúsculas — hostname NÃO; por isso o validador próprio.
# 2) RESERVADOS: nomes de infra/DNS e superfícies do produto que jamais podem
#    virar subdomínio de cliente (o middleware da T7 trata `www` etc. à parte).
RESERVED_COMPANY_SLUGS = frozenset({
    # infra / DNS clássicos
    'www', 'mail', 'email', 'ftp', 'sftp', 'smtp', 'imap', 'pop',
    'ns1', 'ns2', 'dns', 'mx', 'cdn', 'assets', 'static', 'media',
    # superfícies e rotas do produto (evita colisão/confusão futura)
    'admin', 'api', 'app', 'partner', 'platform', 'status', 'docs',
    'help', 'support', 'blog', 'dev', 'staging', 'test', 'demo',
    'login', 'logout', 'painel', 'estoque', 'chips', 'vendas',
    'pricing', 'company', 'whatthechip', 'branding',
})

_DNS_LABEL_RE = re.compile(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$')


def validate_company_code(code):
    """2 a 4 letras MAIÚSCULAS (ou vazio = legado, sem prefixo no documento).

    Restrito de propósito: o código entra em `EMIN-SO-2026-0004`, que é
    CANÔNICO — nunca traduz, e é digitado pelo gerente no type-to-confirm do
    fechamento. Dígito, hífen e acento fora; ambiguidade de leitura em papel
    impresso é o que estamos evitando.

    ⚠ Continua aceitando de 2 a 4 letras mesmo depois de a SEMENTE virar 4
    (2026-09-02): a semente é o padrão de quem não escolhe, não uma regra de
    formato. Fechar em exatamente 4 quebraria empresa que já tenha código curto
    escolhido à mão, e vazio (o legado) tem de continuar passando.
    """
    if not code:
        return
    if not re.fullmatch(r'[A-Z]{2,4}', code):
        raise ValidationError(_lazy(
            'Código da empresa inválido: use de 2 a 4 letras MAIÚSCULAS '
            '(ex.: "EMIN"). Vazio também vale — o documento sai sem prefixo.'))


def suggest_company_code(name, taken=None) -> str:
    """Código SUGERIDO a partir do nome — as **4** primeiras LETRAS (dono,
    2026-09-02): "eMiner" → ``EMIN``, "eRecyclo" → ``EREC``.

    Serve ao cadastro: o dono não quer digitar código a cada empresa nova, e
    empresa sem código emite documento sem prefixo (``SO-2026-0004``) — que é
    justamente a colisão que o código veio desfazer. Então o padrão é gerado.

    Por que 4 e não 3 (era 3 até 2026-09-01): o prefixo passou a ser a ÚNICA
    coisa que separa a ordem de venda de dois clientes (o lote perdeu o dele,
    §2.5 da convenção), e 4 letras erram menos — "Recicladora Sul" e
    "Recicladora Norte" colidiriam de qualquer jeito, mas com 4 a colisão fica
    rara o bastante para ser resolvida à mão por quem cadastra.

    Regras, nesta ordem:
      · acento cai (``Açaí`` → ``ACAI``) e só A-Z sobrevive — dígito e espaço
        fora, porque o código é lido em papel impresso e digitado no
        type-to-confirm do fechamento;
      · 4 letras; ocupado → 3 letras + B, C, D… (segue com 4 caracteres, que é
        o ``max_length``, e mantém o código distinguível);
      · nome com menos de 2 letras → ``''`` (documento sem prefixo): é melhor
        sair sem código do que sair com um código ambíguo.

    ``taken`` são os códigos JÁ EM USO. O chamador passa; assim a função é pura
    e testável sem banco.
    """
    import unicodedata
    sem_acento = ''.join(c for c in unicodedata.normalize('NFKD', name or '')
                         if not unicodedata.combining(c)).upper()
    letras = ''.join(c for c in sem_acento if 'A' <= c <= 'Z')
    if len(letras) < 2:
        return ''
    ocupados = {(t or '').upper() for t in (taken or ())}
    if letras[:4] not in ocupados:
        return letras[:4]
    # Desempate: mantém as iniciais e troca a última letra. `letras[:3]` pode
    # ter 2 caracteres num nome curto — o resultado segue dentro de 2..4.
    base = letras[:3]
    for sufixo in 'BCDEFGHIJKLMNOPQRSTUVWXYZ':
        if base + sufixo not in ocupados:
            return base + sufixo
    return ''


def validate_company_slug(value):
    """Valida o slug da empresa como FUTURO HOSTNAME (B3).

    Usado em 3 camadas: o campo (admin/forms via full_clean), o formulário de
    onboarding (T6) e o portão no ``Company.save()`` — este último cobre também
    escrita ad-hoc por shell/ORM (padrão "portão no MODELO" do projeto).
    """
    v = value or ''
    if not _DNS_LABEL_RE.match(v):
        raise ValidationError(
            _lazy('Slug inválido para virar subdomínio: use só minúsculas, '
                  'dígitos e hífen (sem "_", ponto, espaço ou acento; não '
                  'pode começar/terminar com hífen; máx. 63 caracteres).'),
            code='slug_not_dns')
    if v in RESERVED_COMPANY_SLUGS:
        raise ValidationError(
            _lazy('O slug "%(slug)s" é reservado da plataforma — escolha outro.'),
            code='slug_reserved', params={'slug': v})


@pghistory.track()  # auditoria: criação/desativação de empresa é evento de plataforma
class Company(models.Model):
    """Empresa-cliente (tenant). A fronteira do isolamento comercial."""

    name   = models.CharField(max_length=120, unique=True, verbose_name='Nome')
    slug   = models.SlugField(max_length=60, unique=True, verbose_name='Slug',
                              validators=[validate_company_slug],
                              help_text='Identificador de rotas e o SUBDOMÍNIO '
                                        'futuro do cliente (ex.: "eminer" → '
                                        'eminer.whatthechip.app). Quase-permanente: '
                                        'minúsculas, dígitos e hífen (B3).')
    # ── Código curto da empresa (dono, 2026-08-18) ────────────────────────
    # A numeração de lote/OV/fatura é POR EMPRESA (decisão de julho: "o lote
    # 41 continua sendo o 41"), então o CÓDIGO colide entre clientes — o
    # comprador via dois `LOT/001/08/26` na lista dele, de empresas
    # diferentes. Este código entra no documento e desfaz a colisão:
    # `EMIN-SO-2026-0004`.
    # ⚠ Desde 2026-09-02 o prefixo vive só na ORDEM DE VENDA: o lote saiu da
    # tabela do comprador e voltou a ser número interno (`LOT-2026-0041`).
    # Tirar o prefixo do lote só é seguro POR CAUSA dessa mudança de tela —
    # com a coluna lá, o lote 1 de dois clientes vira a mesma string de novo.
    # ⚠ Recusado de propósito o código de PAÍS (PY/VE): duas recicladoras do
    # mesmo país voltariam a colidir, e país é metadado de EMBARQUE — já
    # viaja no endereço do SHIP FROM, não pertence ao identificador.
    # Quase-permanente como o slug: ele fica gravado nos documentos emitidos
    # (`code_str`), então mudá-lo NÃO reescreve o passado — mas o futuro
    # passa a divergir do que a empresa usou até aqui.
    code = models.CharField(
        max_length=4, blank=True, default='', verbose_name='Código',
        help_text='2 a 4 letras MAIÚSCULAS que identificam a empresa nas '
                  'ordens de venda (ex.: "EMIN" → EMIN-SO-2026-0004). Em '
                  'branco numa empresa NOVA, sai automático: as 4 primeiras '
                  'letras do nome. O código do LOTE não leva prefixo.')
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
    # E5 (§17.7 — canary por cliente, 2026-08-16): rollout do redesign de
    # frontend POR EMPRESA. Ligado → as views servem o template v2 quando o
    # arquivo existe (tenancy/ui.py; fallback automático pro atual, tela a
    # tela). Rollout e rollback viram checkbox — nunca deploy.
    ui_v2 = models.BooleanField(
        default=False, verbose_name='Frontend v2 (canary)',
        help_text='Liga o redesign novo pra ESTA empresa (eMiner primeiro, '
                  'depois as demais). Tela sem arquivo v2 cai na atual — '
                  'seguro ligar a qualquer momento; desligar = rollback '
                  'instantâneo, sem deploy.')
    # Branding por empresa (E4 — B4+B7, decisão do dono 2026-08-16): o logo
    # mora no BANCO (CompanyLogo, 1-pra-1), não em arquivo — o filesystem da
    # Render é efêmero e /media/ nem é servido com DEBUG=False (B7). Aqui na
    # Company ficam só METADADOS baratos: o header checa logo_mime em TODA
    # página sem arrastar o blob (que só sai na view ``company_logo``).
    logo_mime = models.CharField(
        max_length=32, blank=True, default='', editable=False,
        verbose_name='MIME do logo',
        help_text='Vazio = sem logo. Gerido pelo upload no admin — não editar.')
    # ── SHIP FROM — endereço de quem embarca (dono, 2026-08-18) ──────────
    # O documento do lote viaja com o pacote, e o comprador precisa saber de
    # QUAL cliente veio (eMiner × eRecyclo × …). O nome já é o da empresa;
    # aqui entra só o endereço. TEXTO LIVRE pelo mesmo motivo do SHIP TO do
    # comprador: cada país tem uma estrutura e a transportadora quer o bloco
    # exatamente como o remetente o escreve. Vazio = o PDF mostra só o nome.
    address = models.TextField(
        blank=True, default='', verbose_name='Endereço (SHIP FROM)',
        help_text='Endereço de embarque desta empresa, uma linha por linha. '
                  'Aparece no documento que acompanha o lote. Vazio = só o '
                  'nome da empresa aparece.')
    # ── TAXA DE SERVIÇO DA PLATAFORMA (dono, 2026-08-19) ─────────────────
    # O comprador paga o WhatTheChip pelo lote INTEIRO; o WhatTheChip repassa
    # ao cliente já deduzindo esta porcentagem. É o modelo de receita da
    # plataforma, e o cliente vê a dedução na tela dele (bruto → taxa →
    # líquido).
    #
    # Por que campo, e não constante: contrato é por cliente. Quando um deles
    # negociar 7%, muda-se o cadastro — sem deploy, sem migração no meio de um
    # acerto em andamento.
    #
    # ⚠ O valor efetivamente cobrado fica CONGELADO na fatura (`Invoice.
    # fee_pct`), como o câmbio: mudar aqui NUNCA reescreve venda já acertada.
    service_fee_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0')),
                    MaxValueValidator(Decimal('100'))],
        verbose_name='Taxa de serviço (%)',
        help_text='Percentual que o WhatTheChip retém do resultado de cada '
                  'venda desta empresa. Vale para venda NOVA — o que já foi '
                  'faturado guarda a taxa da época.')
    # ── QUEM RECEBE O DINHEIRO DO COMPRADOR (dono, 2026-09-01) ───────────
    # O modelo padrão da plataforma tem TRÊS passos: o comprador paga o WTC, o
    # WTC confere, o WTC transfere o líquido ao cliente. Cada passo é um
    # registro, e o `Payout` existe porque a tela do cliente não pode prometer
    # dinheiro que ainda não saiu da conta do WhatTheChip.
    #
    # Só que há arranjo comercial em que esses três passos são UM. Na eMiner o
    # comprador deposita direto nas carteiras DELA (BINANCE HANDSON, TRONLINK):
    # o WTC nunca toca no dinheiro, só cobra a taxa por fora. Ali "o comprador
    # pagou" e "o cliente recebeu" não são dois eventos — é o mesmo evento
    # visto de dois lados, e exigir um segundo registro manual só cria a janela
    # em que a tela do cliente diz "a receber" sobre dinheiro que já está na
    # conta dele. Foi exatamente o que aconteceu com as seis vendas
    # reconciliadas em 01/09, corrigidas depois por comando.
    #
    # ⚠ Por que é campo da EMPRESA e não constante: é cláusula de contrato,
    # não regra do produto. Cliente novo em que o WTC realmente segura o
    # dinheiro nasce com isto DESLIGADO — e tem que nascer assim, porque o
    # padrão errado aqui declara pago o que ninguém pagou. Ligar é decisão
    # explícita de quem conhece o arranjo.
    payout_on_payment = models.BooleanField(
        default=False, verbose_name='Comprador paga direto ao cliente',
        help_text='Ligue APENAS quando o comprador deposita nas contas desta '
                  'empresa, sem passar pelo WhatTheChip. Aí a quitação da '
                  'fatura registra sozinha o repasse do líquido. Desligado '
                  '(padrão), o repasse é lançado à mão quando o WTC '
                  'transferir.')
    logo_updated_at = models.DateTimeField(
        null=True, blank=True, editable=False,
        verbose_name='Logo atualizado em',
        help_text='Cache-buster (?v=) das tags <img>. Gerido pelo upload.')
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
        constraints = [
            # Único só entre os PREENCHIDOS: vazio é o legado e se repete.
            models.UniqueConstraint(fields=['code'], condition=~models.Q(code=''),
                                    name='unique_company_code'),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Portão no MODELO (B3 — mesmo padrão do Membership.clean): validador
        # de campo só roda em full_clean/forms; aqui cobre TODO caminho de
        # escrita (shell/ORM/comando). Migrações de dados usam modelo
        # HISTÓRICO (sem métodos custom) — backfills antigos não quebram.
        validate_company_slug(self.slug)
        self.code = (self.code or '').strip().upper()
        # Empresa NOVA sem código ganha um padrão (dono, 2026-09-02): as 4
        # primeiras letras do nome. Só na CRIAÇÃO — apagar o código de uma
        # empresa existente é uma decisão, não um descuido a ser desfeito.
        if self._state.adding and not self.code:
            self.code = suggest_company_code(
                self.name,
                taken=Company.objects.exclude(code='').values_list('code', flat=True))
        validate_company_code(self.code)
        return super().save(*args, **kwargs)


class CompanyLogo(models.Model):
    """Bytes do logo da empresa (E4 — B4+B7). Tabela PRÓPRIA de propósito:
    a Company é lida em toda request (middleware/header) e não pode arrastar
    um blob de até 1 MB — aqui o blob só é lido pela view ``company_logo``.
    Sem RLS, como as demais tabelas de tenancy (§6): branding é público (a
    tela de login do subdomínio serve anônimo). Sem pghistory: histórico de
    blob só incharia o event store."""

    company = models.OneToOneField(
        Company, on_delete=models.CASCADE, primary_key=True,
        related_name='logo_asset', verbose_name='Empresa')
    data = models.BinaryField(verbose_name='Bytes do logo')

    class Meta:
        verbose_name = 'Logo de empresa'
        verbose_name_plural = 'Logos de empresa'

    def __str__(self):
        return f'Logo de {self.company}'


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
