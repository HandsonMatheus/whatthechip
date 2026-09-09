"""
politica_origem.py — FONTE ÚNICA da regra "cada origem de lote aceita certos
tipos de chip" (dono, 2026-09-02).

⚠ ESTA REGRA NÃO É RENTABILIDADE. São duas perguntas diferentes e cada uma tem
o seu dono no código — misturá-las é reimplementar rentabilidade num segundo
lugar, o que a regra de ouro #11 proíbe:

    "este chip vale alguma coisa?"        → assess_profitability (chips/engine.py)
    "vale, MAS pertence a este lote?"     → aqui

Por isso GDDR/SDRAM/NAND **não aparecem** nesta tabela: já são sucata POR TIPO
no motor (`profit_family='dead'`), barradas no funil antes de chegar aqui.

VOCABULÁRIO FECHADO POR CONSTRUÇÃO. A tabela cobre exatamente os `kind` que têm
mercado — os `KINDS` do pricing (ddr, emcp, emmc, k9, lpddr, ssd, ufs, umcp).
Todo `label_kind` fora deles é (a) morto por tipo, ou (b) `none`/indeterminado.
Nenhum dos dois é assunto desta regra:
  · morto por tipo   → o funil já barra (rentabilidade);
  · indeterminado    → é falta de COBERTURA DE CATÁLOGO, não lote errado.
    Medido em 2026-09-02: 3 linhas de kind 'none' somavam 2.659 unidades de DDR
    Nanya/ISSI no lote CERTO, só sem tipificação. Barrá-las seria transformar
    todo buraco de gramática num chip recusado na bancada — e o operador
    aprenderia a ignorar o aviso, que é o custo real de um alarme que mente.

FAIL-CLOSED onde não há resposta. Origem fora do vocabulário, ou `kind` de
mercado sem linha na tabela, BARRA e diz por quê. O contrário ("não achei
regra, então libera") é o zero silencioso do `audit_category_codes` outra vez —
e existe precedente de origem fora do vocabulário no banco (o lote legado com
origin='k9').
"""
from django.utils.translation import gettext as _


def kinds_de_mercado() -> frozenset:
    """Os `kind` que esta regra governa. Import tardio: `estoque` não pode
    depender de `pricing` no topo do módulo (ciclo)."""
    from pricing.models import KINDS
    return KINDS


def motivo_neutro() -> str:
    """A recusa que o OPERADOR pode ler — sem dizer o que o chip É.

    Dono, 2026-09-09: *"não é para revelar o tipo do chip na frase, empregados
    não podem ter acesso a isso"*. A frase completa (`bloqueio_de_origem`) diz
    o TIPO e o LOTE de destino — e as duas coisas são exatamente o que a máscara
    do `tenancy.access.is_unmasked` existe para esconder: *"o conhecimento
    'PN → o que é → quanto vale' é o ativo da plataforma"*.

    ⚠ Vale para TODA superfície que o operador vê, não só o cartão: o `title`
    do botão e a RESPOSTA do `add_chip` também mostravam a frase completa — e a
    do `add_chip` aparece justamente quando alguém força o POST, que é o caminho
    de quem está fuçando. Fonte única aqui para que nenhuma delas fique para trás.

    Quem VÊ a frase completa é só o superusuário — o mesmo gate de sempre.
    """
    return _('Este chip não pode ser enviado com este lote. '
             'Comunique ao seu gestor.')


def origens_que_aceitam(kind: str) -> list:
    """Os RÓTULOS das origens para onde mandar o operador com este chip.

    É CONSELHO, não é a regra — a regra é o `permitido` da tabela. Por isso a
    lista é mais estreita que "toda origem com permitido=True", e as duas
    exclusões têm o mesmo motivo: **conselho que não dá pra seguir é pior que
    conselho nenhum.**

    Fica de fora:

    · **origem LEGADA** (MIXED, K9 — `Lot.ORIGIN_LEGACY`): não aparece na tela
      de abrir lote, então mandar o operador pra lá é mandá-lo procurar uma
      opção que não existe.

    · **origem que não FECHA nada**: origem cuja linha é toda `permitido=True`
      não teve régua decidida — é o estado em que a RAM nasceu (fase 2, tudo
      aberto de propósito) e em que qualquer origem nova vai nascer. Dono,
      2026-09-09: *"remova onde diz MÓDULO DE MEMÓRIA, ainda não temos chips
      pra isso agora"*. ⚠ E é auto-mantido de propósito: no dia em que a régua
      da RAM for decidida e ela fechar o primeiro tipo, ela volta a aparecer no
      conselho SOZINHA, sem ninguém lembrar de mexer aqui. Cravar `'ram'` numa
      lista neste arquivo seria a 4ª vez que este projeto escreve vocabulário
      fechado fora do modelo (ver CLAUDE.md §7, "3 quebras do MESMO campo").
      Ler também: origem que aceita TUDO não é conselho sobre onde ESTE chip
      vai — é só ausência de regra.
    """
    from estoque.models import Lot, PoliticaOrigemTipo

    decidem = set(PoliticaOrigemTipo.objects.filter(permitido=False)
                  .values_list('origin', flat=True))
    abertas = set(PoliticaOrigemTipo.objects
                  .filter(kind=kind, permitido=True)
                  .values_list('origin', flat=True))
    # ORDEM do formulário de abrir lote, não a do banco.
    return [rotulo for valor, rotulo in Lot.origin_choices_novas()
            if valor in abertas and valor in decidem]


def bloqueio_de_origem(origin: str, kind: str) -> str | None:
    """``None`` = pode entrar. String = motivo ACIONÁVEL, já traduzido.

    Acionável quer dizer: diz ao operador em que tipo de lote o chip ENTRA, não
    só que este não serve. Recusa sem destino faz o chip voltar pra bancada e
    virar problema de outra pessoa.
    """
    from estoque.models import Lot, PoliticaOrigemTipo

    kind = (kind or "").strip()
    origin = (origin or "").strip()

    # Fora do vocabulário de mercado → não é assunto desta regra (ver docstring).
    if kind not in kinds_de_mercado():
        return None

    if origin not in dict(Lot.ORIGIN_CHOICES):
        # Fail-closed: origem que ninguém declarou não tem política possível.
        return _('Este lote tem uma origem desconhecida (%(origem)s) — nenhum chip '
                 'pode ser lançado nele até a origem ser corrigida.') % {'origem': origin or '?'}

    linha = PoliticaOrigemTipo.objects.filter(origin=origin, kind=kind).first()
    if linha is None:
        # Fail-closed: a tabela é completa por construção (migração + teste de
        # declaração). Linha faltando = decisão que ninguém tomou, não permissão.
        return _('Tipo %(tipo)s ainda não tem regra definida para lotes de %(origem)s. '
                 'Fale com o gestor.') % {'tipo': kind.upper(), 'origem': origin}

    if linha.permitido:
        return None

    aceitam = origens_que_aceitam(kind)
    if aceitam:
        return _('%(tipo)s não entra em lote de %(origem)s. Este chip vai em: '
                 '%(aceitam)s.') % {'tipo': kind.upper(),
                                    'origem': dict(Lot.ORIGIN_CHOICES)[origin],
                                    'aceitam': ', '.join(str(a) for a in aceitam)}
    return _('%(tipo)s não entra em nenhum tipo de lote no momento.') % {
        'tipo': kind.upper()}
