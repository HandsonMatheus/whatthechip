"""
WhatTheChip — Estoque de Operadores
====================================
Modelo de inventário por lote.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _lazy

from tenancy.scope import CompanyScopedManager

import pghistory


@pghistory.track()  # PLANO_FX Fase C: cada trava/retrava de câmbio é evento
class Lot(models.Model):
    # Origem do lote (acordo com o comprador, 2026-08-01): TODO lote declara
    # de que classe de placa os chips saíram — celular × PCB (set-top, TV,
    # notebook, industrial…). Escolha OBRIGATÓRIA na abertura, sem default
    # (é a promessa comercial: eMMC de lote PCB vale a tabela por marca).
    # Chave canônica NUNCA traduz; o rótulo sim (i18n).
    ORIGIN_PHONE  = 'phone'
    ORIGIN_PCB    = 'pcb'
    #: Módulo de memória (pente DDR de PC/servidor, SODIMM) — 3ª origem, 2026-08-24.
    #: ⚠ NÃO é chave de preço: `pricing/engine.py::_row_origin` só usa a origem no
    #: eMMC (celular × PCB, acordo com o comprador). Qualquer origem fora dessas
    #: duas cai no fallback conservador 'phone' — então um eMMC que apareça num
    #: lote de RAM é cotado como celular, de propósito. Aqui a origem é
    #: PROCEDÊNCIA declarada, não tabela.
    ORIGIN_RAM    = 'ram'
    #: ── ORIGENS LEGADAS (dono, 2026-09-01) ────────────────────────────────
    #: MIXED e K9 são como o controle antigo em planilha classificava os
    #: envios, antes de o sistema existir. Entram no vocabulário porque a
    #: reconciliação traz esses lotes para dentro e o dono quer que a tela
    #: mostre o tipo REAL deles — traduzir MIXED para 'celular' seria o sistema
    #: inventando uma procedência que ninguém declarou.
    #: ⚠ Não são oferecidas para lote NOVO: ver ORIGIN_CHOICES_NOVAS.
    #: Rótulo é token canônico (como 'PCB'): nunca traduz.
    ORIGIN_MIXED  = 'mixed'
    ORIGIN_K9     = 'k9'
    ORIGIN_CHOICES = [
        (ORIGIN_PHONE, _lazy('Celular')),
        (ORIGIN_PCB,   'PCB'),
        (ORIGIN_RAM,   _lazy('Módulo de memória')),
        (ORIGIN_MIXED, 'MIXED'),
        (ORIGIN_K9,    'K9'),
    ]

    #: Origens que só existem no PASSADO — importadas do controle antigo.
    #: Ficam em ORIGIN_CHOICES (senão a tela não sabe rotular o lote legado),
    #: mas fora do formulário de abrir lote.
    ORIGIN_LEGACY = frozenset({ORIGIN_MIXED, ORIGIN_K9})


    #: Ícone da origem — mora AQUI, colado no ORIGIN_CHOICES, e não no template.
    #: Bug de prod 2026-08-28: o badge do lote era um `{% if lot.origin == 'pcb' %}`
    #: de DOIS caminhos em dois templates; a 3ª origem caía no `else` e o lote de
    #: MÓDULO DE MEMÓRIA aparecia como "📱 Origem: celular" — o sistema mentindo
    #: sobre a procedência declarada do material. É a 3ª vez que uma lista de
    #: origens escrita à mão fora do modelo quebra (antes: a tupla do `lot_create`
    #: e o `choices=` do `replicate_lot_xlsx`). Rótulo vem de
    #: `get_origin_display()` (já traduzido pelos `_lazy` acima); ícone, daqui.
    #: Origem nova = UMA linha aqui, e nenhum template muda.
    ORIGIN_ICONS = {
        ORIGIN_PHONE: '📱',
        ORIGIN_PCB:   '🔌',
        ORIGIN_RAM:   '💾',
        ORIGIN_MIXED: '🧩',
        ORIGIN_K9:    '🧱',
    }

    STATUS_OPEN   = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN,   'Aberto'),
        (STATUS_CLOSED, 'Fechado'),
    ]

    # T3: numeração POR EMPRESA — unique (company, number), não mais global.
    number      = models.PositiveIntegerField(verbose_name="Número")
    # T3 (PLANO_MULTITENANT.md §5.2): o lote é ativo da EMPRESA — a chave do
    # isolamento (e do futuro RLS). PROTECT: apagar empresa não leva lotes.
    company     = models.ForeignKey(
        'tenancy.Company', on_delete=models.PROTECT,
        related_name='lots', verbose_name='Empresa',
    )
    branch      = models.ForeignKey(
        'tenancy.Branch', on_delete=models.PROTECT,
        null=True, blank=True,               # filial é OPCIONAL no v1 (sempre)
        related_name='lots', verbose_name='Filial',
    )
    operator    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lots',
        verbose_name='Operador',
        help_text='Quem abriu o lote (o lote pertence à EMPRESA, não a ele).',
    )
    description = models.CharField(max_length=255, blank=True, default='', verbose_name='Descrição')
    origin      = models.CharField(max_length=5, choices=ORIGIN_CHOICES,
                                   verbose_name='Origem',
                                   help_text='Classe de placa de onde os chips '
                                             'saíram (celular × PCB) — define a '
                                             'tabela de preço do eMMC.')
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN, verbose_name='Status')

    @classmethod
    def origin_choices_novas(cls):
        """O que o gerente pode escolher ao abrir um lote HOJE: ORIGIN_CHOICES
        menos as legadas. É isto que a view de criação consome — nunca
        ORIGIN_CHOICES, que inclui MIXED e K9 só para rotular o passado.

        Método, e não constante de classe, porque comprehension no corpo da
        classe não enxerga ORIGIN_LEGACY (escopo de classe não entra no escopo
        da comprehension). Constante exigiria repetir os valores à mão, que é
        exatamente o tipo de lista duplicada que já quebrou aqui 3 vezes."""
        return [(v, r) for v, r in cls.ORIGIN_CHOICES
                if v not in cls.ORIGIN_LEGACY]

    @property
    def origin_icon(self) -> str:
        """Ícone da origem, da FONTE ÚNICA (`ORIGIN_ICONS`). Origem fora do
        vocabulário devolve um marcador NEUTRO — nunca o ícone de outra origem:
        badge que erra em silêncio é pior que badge sem ícone."""
        return self.ORIGIN_ICONS.get(self.origin, '📦')
    # ── Trava de câmbio (PLANO_FX Fase C, 2026-08-01): capturada ATOMICAMENTE
    #    no fechamento; imutável até reabertura (só superuser), quando volta
    #    ao vivo e o RE-fechamento captura taxa nova — o pghistory loga as
    #    duas travas. OV/fatura/pagamentos (2 pontas) usam a taxa DAQUI. ──
    fx_rate      = models.DecimalField(max_digits=8, decimal_places=4,
                                       null=True, blank=True,
                                       verbose_name='Câmbio travado (1¥→US$)')
    fx_source    = models.CharField(max_length=80, blank=True, default='',
                                    verbose_name='Fonte do câmbio')
    fx_locked_at = models.DateTimeField(null=True, blank=True,
                                        verbose_name='Câmbio travado em')
    fx_is_fallback = models.BooleanField(default=False,
                                         verbose_name='Câmbio de fallback')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Aberto em')

    @property
    def code(self) -> str:
        """``LOT-2026-0041`` — nomenclatura UNIVERSAL canônica: inglês, NUNCA
        traduz. É também o texto que o gerente digita para confirmar o
        fechamento e a exclusão (type-to-confirm).

        SEM código de empresa, de propósito (convenção §2.5): o número do lote
        é interno. Ele carregou o prefixo entre 18/08 e 02/09/2026 porque o lote
        era a primeira coluna do painel do COMPRADOR, que lê ordens de vários
        clientes e via dois `LOT/001/08/26`. O lote saiu daquela tabela — e é
        só por isso que tirar o prefixo daqui voltou a ser seguro.

        O fallback cobre o objeto ainda não salvo e fixture crua; depois do
        backfill não existe lote sem ``code_str``."""
        if self.code_str:
            return self.code_str
        from tenancy.doc_code import doc_code
        return doc_code('LOT', '', self.number, self.created_at,
                        ano=self.doc_year or None)
    # ── ANO DO DOCUMENTO — o da ABERTURA (dono, 2026-09-02) ───────────────
    # Não o do fechamento nem o do despacho: um lote aberto em dezembro de 2026
    # e fechado em fevereiro de 2027 é `LOT-2026-00NN`. Campo GRAVADO porque
    # entra na chave de unicidade (empresa, ano, número) e porque o ano tem de
    # ser IMUTÁVEL depois de emitido.
    # ⚠ Vem do horário LOCAL, não do UTC do banco: um lote aberto 31/dez 21:00
    # em Assunção já é 1º de janeiro em UTC, e o documento sairia com o ano
    # errado exatamente na fronteira que esta convenção existe para acertar.
    doc_year = models.PositiveSmallIntegerField(
        default=0, editable=False, verbose_name='Ano do documento')
    # ── JÁ FOI FECHADO ALGUMA VEZ (dono, 2026-09-02) ──────────────────────
    # Existe para uma pergunta só: apagar este lote pode DEVOLVER o número dele
    # ao contador? Pode, se ele nunca virou documento. Fechar emite o PDF de
    # conferência com o código dentro — a partir daí o número está no mundo e
    # não volta.
    # ⚠ Por que um campo, e não `closed_at`/`closed_by`: REABRIR zera os dois
    # (estoque/views.py::lot_reopen), e um lote reaberto já imprimiu. E por que
    # não o pghistory: os gatilhos de evento são do POSTGRES — na suíte (SQLite)
    # não existe evento nenhum, então a trava passaria no teste e não protegeria
    # nada em produção. Este projeto já teve trava assim.
    # Nunca volta para False. É memória, não estado.
    ever_closed = models.BooleanField(
        default=False, editable=False, verbose_name='Já foi fechado',
        help_text='Marca que o lote chegou a ser fechado alguma vez — o número '
                  'dele não volta mais para a sequência. Reabrir não desmarca.')
    # ── Código do documento, CONGELADO na criação (dono, 2026-08-18) ───────
    # Era propriedade calculada. Virou campo porque o identificador tem de ser
    # IMUTÁVEL depois de emitido — renomear o código da empresa não reescreve o
    # passado, que é como número de documento deve se comportar. O passado só
    # muda por `manage.py backfill_doc_codes`, no ato deliberado em que o dono
    # decide que tela e papel voltam a usar a mesma grafia.
    code_str = models.CharField(max_length=32, blank=True, default='',
                                editable=False, verbose_name='Código')
    closed_at   = models.DateTimeField(null=True, blank=True, verbose_name='Fechado em')
    # QUEM fechou (2026-08-18): o documento comercial do lote (PDF da OV do
    # gerente) precisa assinar o fechamento com um nome. Aditivo e NULLABLE de
    # propósito — lote fechado ANTES deste campo cai no fallback do
    # ``closed_by_user`` abaixo; migração sem RunPython (backfill em tabela com
    # RLS exigiria o GUC de plataforma no migrate do Render — armadilha
    # conhecida). SET_NULL: demitir usuário não apaga o lote.
    closed_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Fechado por',
        help_text='Quem fechou o lote (registro do documento comercial). '
                  'Vazio em lotes fechados antes de 2026-08-18.')

    # T3: o caminho PADRÃO já vem filtrado pela empresa corrente (fail-closed —
    # sem escopo EXPLODE); all_companies é o escape EXPLÍCITO de plataforma
    # (admin/comandos), auditável por grep. base_manager_name evita que as
    # travessias internas do Django passem pelo manager fail-closed.
    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        verbose_name = 'Lote'
        verbose_name_plural = 'Lotes'
        ordering = ['-number']
        base_manager_name = 'all_companies'
        # ⚠ default = CRU (padrão da doc do Django: default manager NÃO filtra).
        # Motivo concreto: Django 5 valida UniqueConstraint de formulário via
        # _default_manager — com o fail-closed ali, o admin de plataforma
        # EXPLODIA (CompanyScopeMissing em /admin/.../add/, bug 2026-07-09).
        # O caminho escopado continua sendo o EXPLÍCITO: Model.objects.
        default_manager_name = 'all_companies'
        constraints = [
            # Cada empresa tem a SUA sequência (Lote #001 da Brasil Reciclagem
            # coexiste com o #001 da eMiner). Substitui o unique global.
            # ⚠ E o ANO entra na chave (2026-09-02): a numeração reinicia em 1º
            # de janeiro, então o lote 1 de 2026 e o de 2027 coexistem.
            models.UniqueConstraint(fields=['company', 'doc_year', 'number'],
                                    name='unique_lot_company_year_number'),
            # Origem obrigatória e canônica (2026-08-01) — pega criação por
            # fora do open_for_company (shell/teste) ainda no INSERT.
            models.CheckConstraint(
                name='lot_origin_vocab',
                # Lista LITERAL de propósito: constraint de banco não pode
                # depender de constante Python (migração congela o SQL). Ao
                # somar origem nova, some aqui E gere migration.
                condition=models.Q(origin__in=['phone', 'pcb', 'ram',
                                               'mixed', 'k9'])),
        ]
        indexes = [
            # Toda consulta do app começa por company (§5.2).
            models.Index(fields=['company', '-number'],
                         name='lot_company_number_desc'),
        ]

    def __str__(self):
        # O código, e não `Lote #041`: com o reinício anual o número sozinho
        # deixou de identificar — o #1 de 2026 e o de 2027 são lotes diferentes.
        return self.code

    @property
    def closed_by_user(self):
        """Quem fechou o lote — ``None`` se não dá para saber.

        O campo ``closed_by`` só existe desde 2026-08-18. Para lote fechado
        ANTES disso o registro equivalente é o ``LotPricing.closed_by``: o
        snapshot de valoração é gravado no MESMO ato do fechamento
        (``_freeze_lot_pricing``). ⚠ Ele pode faltar (congelar valor nunca
        trava o fechamento — padrão F8) e por isso o retorno é opcional; quem
        exibe decide o texto do vazio.
        """
        if self.closed_by_id:
            return self.closed_by
        from pricing.models import LotPricing        # lazy: estoque ⊥ pricing
        lp = (LotPricing.all_companies
              .filter(lot_id=self.pk, closed_by__isnull=False)
              .select_related('closed_by').order_by('-created_at').first())
        return lp.closed_by if lp else None

    def save(self, *args, **kwargs):
        from django.utils import timezone
        # Portão no MODELO: filial tem que ser da mesma empresa do lote.
        if self.branch_id and self.company_id and \
                self.branch.company_id != self.company_id:
            raise ValidationError(
                {'branch': 'A filial deve pertencer à empresa do lote.'})
        # Ano de ABERTURA, em horário LOCAL (ver o campo). Só na criação: o ano
        # de um documento emitido não muda.
        if self._state.adding and not self.doc_year:
            self.doc_year = timezone.localdate().year
        # "Já foi fechado" no MODELO, não na view: o fechamento acontece pela
        # tela, por comando de legado e pelo admin, e a marca não pode depender
        # de quem chamou. Nunca volta para False.
        if self.status == self.STATUS_CLOSED and not self.ever_closed:
            self.ever_closed = True
            uf = kwargs.get('update_fields')
            if uf is not None and 'ever_closed' not in uf:
                # ⚠ sem isto o save(update_fields=[...]) do fechamento gravaria
                # tudo MENOS a marca — e ela é a trava da devolução de número.
                kwargs['update_fields'] = list(uf) + ['ever_closed']
        # Congela o código na CRIAÇÃO (ver tenancy/doc_code.py). Usa
        # timezone.now() em vez do created_at porque o auto_now_add só existe
        # DEPOIS do insert — e um segundo save() aqui dobraria o evento de
        # histórico do pghistory à toa.
        if self._state.adding and not self.code_str:
            # Sem código de empresa: o lote não leva prefixo (convenção §2.5).
            from tenancy.doc_code import doc_code
            self.code_str = doc_code('LOT', '', self.number, timezone.now(),
                                     ano=self.doc_year)
        return super().save(*args, **kwargs)

    # ── Exclusão: o número pode voltar? (dono, 2026-09-02) ────────────────
    @property
    def devolve_numero_ao_excluir(self) -> bool:
        """True se apagar este lote devolve o número dele para a sequência.

        Duas condições, e as duas têm de valer:

        1. **nunca foi fechado** — fechar emite o PDF de conferência com o
           código dentro; a partir daí o número está no mundo (§4 do contrato,
           "número emitido nunca se reusa");
        2. **é o último emitido** do ano da empresa — devolver um número do meio
           deixaria dois lotes diferentes com o mesmo código ao longo do tempo.

        É a MESMA regra que o ``delete()`` aplica; existe como propriedade para
        que o modal de confirmação possa avisar o gerente sem repeti-la."""
        if self.ever_closed or self.closed_at or self.status == self.STATUS_CLOSED:
            return False
        from vendas.models import DocSequence, SEQ_LOT
        seq = (DocSequence.all_companies
               .filter(company_id=self.company_id, kind=SEQ_LOT,
                       year=self.doc_year).first())
        return bool(seq and seq.last_number == self.number)

    def delete(self, *args, **kwargs):
        """Apaga o lote e, quando cabe, DEVOLVE o número à sequência.

        Portão no MODELO e não na view (dono, 2026-09-02): abrir um lote e
        apagá-lo em seguida tem de devolver o número venha o clique de onde
        vier — tela, admin ou shell.

        ⚠ ``queryset.delete()`` em massa NÃO passa por aqui, e é de propósito:
        comando de renumeração/limpeza não pode mexer em contador por efeito
        colateral. Quem apaga em massa acerta o contador explicitamente.
        """
        from vendas.models import DocSequence, SEQ_LOT
        with transaction.atomic():
            devolver = self.devolve_numero_ao_excluir
            company_id, ano, numero = self.company_id, self.doc_year, self.number
            resultado = super().delete(*args, **kwargs)
            if devolver:
                DocSequence.release_number(company_id, SEQ_LOT, ano, numero)
        return resultado

    @classmethod
    def open_for_company(cls, company, operator, description='', branch=None,
                         *, origin):
        """T2 (PLANO_MULTITENANT.md §7): abre um lote com numeração ATÔMICA por
        empresa. Substitui o antigo ``next_number()`` (``Max('number')+1``), que
        era uma CORRIDA real: dois gerentes clicando juntos liam o mesmo max e um
        levava ``IntegrityError`` na cara.

        Como funciona: ``DocSequence.next_number`` trava a linha da sequência
        (``select_for_update``) e incrementa — criações simultâneas serializam
        no lock e saem com números consecutivos, sem buraco e sem erro. O
        ``floor`` (maior ``number`` que existe de fato NAQUELE ano) é auto-cura
        de drift, aplicada dentro do mesmo lock.

        ── O contador mudou de casa (dono, 2026-09-02) ───────────────────────
        Era ``Company.last_lot_number``, um escalar que não sabia de ANO. Como o
        número passou a reiniciar em 1º de janeiro, o contador virou uma linha
        do ``DocSequence`` por (empresa, 'lot', ano) — a mesma mecânica que a
        ordem de venda e a fatura já usavam, e a mesma linha que a EXCLUSÃO de
        lote trava para devolver um número.
        ⚠ ``last_lot_number`` continua no cadastro (o ``bootstrap_tenancy`` e o
        admin o leem) e é mantido em dia aqui, mas não é mais a FONTE.

        ⚠ ``select_for_update`` é NO-OP no SQLite — o teste de corrida
        (``LotNumberRaceTests``) só prova algo rodando contra Postgres."""
        from django.db.models import Max
        from django.utils import timezone
        from tenancy.models import Company
        from vendas.models import DocSequence, SEQ_LOT

        # Ano de ABERTURA, em horário LOCAL (ver o campo `doc_year`).
        ano = timezone.localdate().year
        with transaction.atomic():
            if origin not in dict(cls.ORIGIN_CHOICES):
                raise ValidationError({'origin': (
                    'Origem do lote é OBRIGATÓRIA — acordo com o comprador, '
                    '2026-08-01. Sem default de propósito. Válidas: '
                    + ', '.join(dict(cls.ORIGIN_CHOICES)) + '.')})
            locked = Company.objects.select_for_update().get(pk=company.pk)
            # O floor olha só os lotes DESTA empresa NESTE ano (all_companies de
            # propósito: o método recebe a empresa explícita e não depende do
            # escopo ambiente — comandos/testes chamam direto).
            floor = (cls.all_companies.filter(company=locked, doc_year=ano)
                     .aggregate(Max('number'))['number__max']) or 0
            next_n = DocSequence.next_number(locked, SEQ_LOT, ano, floor=floor)
            # Espelho, não fonte: mantém o cadastro coerente com o maior número
            # emitido, para o admin não exibir um contador que mente.
            if next_n > locked.last_lot_number:
                locked.last_lot_number = next_n
                locked.save(update_fields=['last_lot_number'])
            return cls.all_companies.create(number=next_n, company=locked,
                                            origin=origin, doc_year=ano,
                                            branch=branch, operator=operator,
                                            description=description)

    @property
    def chip_count(self):
        return self.entries.count()

    @property
    def total_qty(self):
        from django.db.models import Sum
        result = self.entries.aggregate(Sum('quantity'))['quantity__sum']
        return result or 0

    @property
    def is_open(self):
        return self.status == self.STATUS_OPEN


class CompanyBoundByLot(models.Model):
    """Base das linhas do estoque (T3): DENORMALIZA a empresa do lote na própria
    tabela — o RLS (T4) exige a coluna local, e os índices compostos
    ``(company, …)`` também (PLANO_MULTITENANT.md §5.2). ``save()`` deriva a
    empresa do lote e REJEITA mismatch (consistência pai-filho no modelo, não na
    view). Managers: ``objects`` fail-closed; ``all_companies`` = plataforma."""

    company = models.ForeignKey('tenancy.Company', on_delete=models.PROTECT,
                                related_name='+', verbose_name='Empresa')

    objects       = CompanyScopedManager()
    all_companies = models.Manager()

    class Meta:
        abstract = True
        base_manager_name = 'all_companies'
        # ⚠ default = CRU (padrão da doc do Django: default manager NÃO filtra).
        # Motivo concreto: Django 5 valida UniqueConstraint de formulário via
        # _default_manager — com o fail-closed ali, o admin de plataforma
        # EXPLODIA (CompanyScopeMissing em /admin/.../add/, bug 2026-07-09).
        # O caminho escopado continua sendo o EXPLÍCITO: Model.objects.
        default_manager_name = 'all_companies'

    def save(self, *args, **kwargs):
        if self.lot_id:
            lot_company_id = self.lot.company_id
            if not self.company_id:
                self.company_id = lot_company_id      # herda do lote
            elif lot_company_id and self.company_id != lot_company_id:
                raise ValidationError(
                    {'company': 'A entrada pertence a uma empresa diferente do lote.'})
        return super().save(*args, **kwargs)


class InventoryEntry(CompanyBoundByLot):
    lot = models.ForeignKey(
        Lot,
        on_delete=models.CASCADE,
        related_name='entries',
        verbose_name='Lote',
    )
    part_number = models.CharField(max_length=100, db_index=True, verbose_name='Part Number')

    chip_type   = models.CharField(max_length=50,  blank=True, default='', verbose_name='Tipo')
    brand       = models.CharField(max_length=100, blank=True, default='', verbose_name='Fabricante')
    capacity    = models.CharField(max_length=100, blank=True, default='', verbose_name='Capacidade')
    emcp_ram    = models.CharField(max_length=100, blank=True, default='', verbose_name='RAM (eMCP)')
    emcp_nand   = models.CharField(max_length=100, blank=True, default='', verbose_name='NAND (eMCP)')
    is_emcp     = models.BooleanField(default=False, verbose_name='É eMCP/uMCP')
    interface   = models.CharField(max_length=100, blank=True, default='', verbose_name='Interface')
    classification_source = models.CharField(max_length=50, blank=True, default='', verbose_name='Fonte')
    # Passo 2: edição do catálogo sob a qual este snapshot foi calculado. Se for <
    # CatalogVersion.current(), a entrada está DEFASADA (resnapshot_lote/on-read revaluam).
    snapshot_catalog_version = models.IntegerField(default=0, verbose_name='Versão do snapshot')

    # ── F11.1 (2026-07-16): CHAVE DE PREÇO materializada no LANÇAMENTO ──────
    # O classify já roda na bancada; gravamos aqui a chave (kind/gen/tier —
    # vocabulário do pricing, estável: quem muda é o PREÇO, não a chave) e a
    # valoração/export resolvem contra a tabela Price VIVA por join — o
    # classify sai do caminho de LEITURA (incidente lote 41/42). Chave vazia
    # COM price_key_reason = chip sem chave (NO_KEY, motivo gravado); tudo
    # vazio = entrada LEGADA (valoração cai no fallback classify; cura
    # definitiva = resnapshot_lote, que faz o backfill). A defasagem segue a
    # régua do snapshot_catalog_version, como o resto do snapshot.
    price_kind = models.CharField(max_length=8, blank=True, default='',
                                  verbose_name='Chave de preço: tipo')
    price_gen = models.CharField(max_length=12, blank=True, default='',
                                 verbose_name='Chave de preço: geração')
    price_tier_value = models.DecimalField(max_digits=6, decimal_places=1,
                                           null=True, blank=True,
                                           verbose_name='Chave de preço: faixa')
    price_tier_unit = models.CharField(max_length=2, blank=True, default='',
                                       verbose_name='Chave de preço: unidade')
    price_key_reason = models.CharField(max_length=200, blank=True, default='',
                                        verbose_name='Sem chave (motivo)')

    quantity     = models.PositiveIntegerField(default=1, verbose_name='Quantidade')
    added_at     = models.DateTimeField(auto_now_add=True, verbose_name='Adicionado em')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta(CompanyBoundByLot.Meta):
        verbose_name = 'Entrada de Estoque'
        verbose_name_plural = 'Entradas de Estoque'
        ordering = ['-last_updated']
        constraints = [
            models.UniqueConstraint(
                fields=['lot', 'part_number'],
                name='unique_lot_pn',
            )
        ]
        indexes = [
            # §5.2: consultas lideradas por company (busca de PN e por lote).
            models.Index(fields=['company', 'part_number'],
                         name='inv_company_pn'),
            models.Index(fields=['company', 'lot'],
                         name='inv_company_lot'),
        ]

    def __str__(self):
        return f'{self.part_number} × {self.quantity} (Lote #{self.lot.number:03d})'

    @property
    def display_capacity(self):
        if self.is_emcp:
            parts = [p for p in [self.emcp_nand, self.emcp_ram] if p]
            return ' / '.join(parts) if parts else '—'
        return self.capacity or '—'

    @property
    def display_interface(self):
        if self.is_emcp and not self.interface:
            if self.emcp_ram:
                return self.emcp_ram.split()[0] if self.emcp_ram else '—'
        return self.interface or '—'


class PendingEntry(CompanyBoundByLot):
    """
    Fila de conferência: chip que o operador tentou adicionar mas que NÃO está
    confirmado no banco (classification_source != "banco de dados" e confidence
    fora de confirmed/manual). Em vez de contaminar o estoque, fica aqui para o
    gestor aprovar (vira InventoryEntry) ou reprovar (descarta). Ver add_chip e
    o bloqueio "só confirmados" (CLAUDE.md §2, regras de ouro).
    """
    lot         = models.ForeignKey(
        Lot, on_delete=models.CASCADE, related_name='pending', verbose_name='Lote',
    )
    part_number = models.CharField(max_length=100, db_index=True, verbose_name='Part Number')
    quantity    = models.PositiveIntegerField(default=1, verbose_name='Quantidade')

    # Snapshot da classificação no momento da tentativa (para o gestor revisar).
    chip_type   = models.CharField(max_length=50,  blank=True, default='', verbose_name='Tipo')
    brand       = models.CharField(max_length=100, blank=True, default='', verbose_name='Fabricante')
    capacity    = models.CharField(max_length=100, blank=True, default='', verbose_name='Capacidade')
    emcp_ram    = models.CharField(max_length=100, blank=True, default='', verbose_name='RAM (eMCP)')
    emcp_nand   = models.CharField(max_length=100, blank=True, default='', verbose_name='NAND (eMCP)')
    is_emcp     = models.BooleanField(default=False, verbose_name='É eMCP/uMCP')
    interface   = models.CharField(max_length=100, blank=True, default='', verbose_name='Interface')
    classification_source = models.CharField(max_length=50, blank=True, default='', verbose_name='Fonte')
    confidence  = models.CharField(max_length=20, blank=True, default='', verbose_name='Confiança')

    # Dica de revisão: PN confirmado mais parecido (provável erro de digitação).
    nearest_confirmed = models.CharField(max_length=100, blank=True, default='', verbose_name='Provável typo de')

    operator    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='pending_entries', verbose_name='Operador',
    )
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Tentado em')

    class Meta(CompanyBoundByLot.Meta):
        verbose_name = 'Pendente de Conferência'
        verbose_name_plural = 'Pendentes de Conferência'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['lot', 'part_number'],
                name='unique_pending_lot_pn',
            )
        ]

    def __str__(self):
        return f'{self.part_number} × {self.quantity} (pendente · Lote #{self.lot.number:03d})'


class SubmitToken(models.Model):
    """Idempotência do ``add_chip`` (bug Mundo Metal LOT/002/08/26, 2026-08-10):
    cada render do card de triagem embute um token UUID; o add_chip só APLICA a
    escrita se conseguir CRIAR a linha aqui (unique). POST duplicado — duplo
    clique, re-clique em rede lenta, retry após queda de conexão — encontra o
    token já usado e vira NO-OP que só re-renderiza o estado atual.

    De propósito a tabela NÃO guarda dado de tenant (só token aleatório +
    timestamp): fica FORA do RLS/T4 sem abrir exceção nova de policy, e um
    token não colide entre empresas (uuid4). Poda lazy: o próprio add_chip
    apaga tokens com mais de 48h (``created_at`` indexado). Ver
    ``estoque/views.py::_claim_submit_token``."""
    token      = models.CharField(max_length=32, unique=True,
                                  verbose_name='Token de envio')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True,
                                      verbose_name='Criado em')

    class Meta:
        verbose_name = 'Token de envio (idempotência)'
        verbose_name_plural = 'Tokens de envio (idempotência)'

    def __str__(self):
        return self.token


class RejectedEntry(CompanyBoundByLot):
    """
    Log de auditoria (append-only): chip CONFIRMADO no banco e com specs completas,
    mas que o operador tentou adicionar e foi barrado por NÃO RENTÁVEL na etapa 3 do
    gateway. Não entra no estoque nem na fila — segue para resíduo eletrônico. Serve
    só para auditoria e calibração das regras de rentabilidade (ver
    chips.engine.assess_profitability e estoque.views._compute_gateway).

    Por que sem unique(lot, part_number): cada tentativa de descarte é um evento
    distinto na linha do tempo. Acumular numa só linha esconderia a frequência — que
    é justamente o sinal de calibração. Logamos um registro por reprovação.
    """
    lot         = models.ForeignKey(
        Lot, on_delete=models.CASCADE, related_name='rejected', verbose_name='Lote',
    )
    part_number = models.CharField(max_length=100, db_index=True, verbose_name='Part Number')
    quantity    = models.PositiveIntegerField(default=1, verbose_name='Quantidade')

    # Snapshot da classificação no momento da reprovação (para auditoria posterior).
    chip_type   = models.CharField(max_length=50,  blank=True, default='', verbose_name='Tipo')
    brand       = models.CharField(max_length=100, blank=True, default='', verbose_name='Fabricante')
    capacity    = models.CharField(max_length=100, blank=True, default='', verbose_name='Capacidade')
    emcp_ram    = models.CharField(max_length=100, blank=True, default='', verbose_name='RAM (eMCP)')
    emcp_nand   = models.CharField(max_length=100, blank=True, default='', verbose_name='NAND (eMCP)')
    is_emcp     = models.BooleanField(default=False, verbose_name='É eMCP/uMCP')
    interface   = models.CharField(max_length=100, blank=True, default='', verbose_name='Interface')
    classification_source = models.CharField(max_length=50, blank=True, default='', verbose_name='Fonte')
    confidence  = models.CharField(max_length=20, blank=True, default='', verbose_name='Confiança')

    # Razão da reprovação. Hoje sempre "NÃO RENTÁVEL"; campo deixado extensível.
    rejection_reason = models.CharField(max_length=100, default='NÃO RENTÁVEL', verbose_name='Razão')

    operator    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='rejected_entries', verbose_name='Operador',
    )
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Reprovado em')

    class Meta(CompanyBoundByLot.Meta):
        verbose_name = 'Reprovado'
        verbose_name_plural = 'Reprovados'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.part_number} × {self.quantity} (reprovado · Lote #{self.lot.number:03d})'
