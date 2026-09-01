"""
vendas/alinhar_eminer_core.py
=============================
Os NÚMEROS da reconciliação das vendas da eMiner — separados do comando para
que o teste possa conferir a aritmética sem tocar no banco.

De onde vem cada coisa (decisão do dono, 2026-08-31):

  VALOR        A planilha mestra `VENDAS EMINER.xlsx`, coluna RECEBIDO. É o que
               a fatura cobra e o pagamento quita. Nem produção nem os detalhes
               por lote têm voto aqui.
  QUANTIDADE   Os detalhes por lote (os `.xlsx` em mandarim). Part number sem
               preço sai do vendido.
  DATA         Idem — o detalhe manda. O `最后添加` do 039 está em dd/mm e vai
               de 17/06/2026 a 04/07/2026; o arquivo foi criado em 04/07 04:39;
               produção tem closed_at 2026-07-04. O "2026-04-07" da mestra é
               04/07 lido como abril.
  TAXA ¥→US$   A do lote. 0,15 no 039 (o detalhe declara "固定，不可修改", a
               tabela do Wu Quan usa 0,15 e a ordem em produção concorda).
               0,14 no 040 e no 041 — os detalhes declaram, e a conta fecha no
               centavo contra o que foi pago. O 0,15 gravado nessas duas ordens
               é o bug (é de onde sai o 8443.15 que o dono anotou).
  COMISSÃO     `Company.service_fee_pct`, que já é 10% — a coluna COM. WTC.

PREÇO POR LINHA
  O 040 e o 041 TÊM preço por linha, e ele não é chute: cruzando os part
  numbers do detalhe com `lot.entries` e agregando pela mesma chave que o
  `create_draft_for_lot` usa (marca, price_kind, fold_gen, tier), 326/326 PNs
  do lote 40 casaram, nenhum grupo ficou com dois preços diferentes, e a soma
  bate no centavo com o total do detalhe. A tabela abaixo é esse resultado,
  congelado — `self_check()` reconfere a soma antes de qualquer gravação.

  O 039 NÃO tem. O preço foi repactuado depois da cotação (ver
  CARTA_WUQUAN_REPACTUACAO.md: ¥183.571 → ¥160.292, 97% da queda em 7
  categorias de eMCP e LPDDR) e ninguém guardou a quebra por categoria. Decisão
  do dono: linhas só com quantidade, valor no cabeçalho e na fatura. Não
  inventar rateio proporcional — um preço por linha que ninguém acordou é
  pior que nenhum.

⚠ Só os três lotes que JÁ existem em produção. Os três legados da mestra
  (CHIP-EXP012026, CHIP-EXP022026 e o K9) ainda dependem de decisão do dono
  sobre que código recebem, e ficam para uma segunda leva.
"""

from datetime import date
from decimal import Decimal as D

#: Empresa. Um comprador só, sempre o mesmo.
EMPRESA_SLUG = 'eminer'
COMPRADOR = 'Wu Quan'


#: lote -> o que a mestra manda gravar.
#:   ov            número da ordem de venda (confere antes de escrever)
#:   fx            taxa ¥→US$ correta do lote
#:   total_rmb     None = soma das linhas (040/041); valor = cabeçalho (039)
#:   total_usd     SEMPRE a coluna RECEBIDO da mestra
#:   precos        True = grava preço por linha (tabela PRECOS); False = limpa
#:   data          fechamento real, do detalhe do lote (vira o `received_at`)
#:   pago_em       quando o dinheiro entrou. Nem sempre é a data de fechamento:
#:                 no 039 o lote fechou em 04/07 e o Wu pagou em 18/07 (dono,
#:                 2026-09-01). A mestra só tem a coluna FECHAMENTO, então para
#:                 o 040 e o 041 é a mesma data até haver informação melhor.
#:   carteira      coluna PAGADO EM da mestra, vai na referência do pagamento
PLANO = {
    39: dict(ov=5,  fx=D('0.15'), total_rmb=D('154826.67'), total_usd=D('23224.00'),
             precos=False, data=date(2026, 7, 4), pago_em=date(2026, 7, 18),
             carteira='BINANCE HANDSON',
             nota='Preço repactuado após a cotação; valor no cabeçalho, sem quebra por linha.'),
    40: dict(ov=1,  fx=D('0.14'), total_rmb=D('49550.40'),  total_usd=D('6937.00'),
             precos=True,  data=date(2026, 7, 11), pago_em=date(2026, 7, 11),
             carteira='TRONLINK',
             nota='Preço por linha vindo do detalhe; 6 unidades sem chave de preço ficam fora.'),
    41: dict(ov=2,  fx=D('0.14'), total_rmb=D('44647.70'),  total_usd=D('6251.00'),
             precos=True,  data=date(2026, 7, 17), pago_em=date(2026, 7, 17),
             carteira='TRONLINK',
             nota='Preço por linha vindo do detalhe; 68 unidades sem chave de preço ficam fora.'),
}


#: (marca, price_kind, gen_dobrado, tier_value, tier_unit) -> ¥ unitário.
#: Gerado do cruzamento detalhe × lot.entries; conferido por self_check().
PRECOS = {40: {('Kingston', 'emcp', '', '16.0', 'GB'): '16',
    ('Kingston', 'emcp', '', '8.0', 'GB'): '10',
    ('Micron', 'ddr', 'DDR3', '2.0', 'Gb'): '2.8',
    ('Micron', 'ddr', 'DDR3', '4.0', 'Gb'): '3.8',
    ('Micron', 'ddr', 'DDR4', '8.0', 'Gb'): '10.4',
    ('Micron', 'emcp', '', '128.0', 'GB'): '105',
    ('Micron', 'emcp', '', '16.0', 'GB'): '16',
    ('Micron', 'emcp', '', '32.0', 'GB'): '37.5',
    ('Micron', 'emcp', '', '64.0', 'GB'): '95',
    ('Micron', 'emcp', '', '8.0', 'GB'): '10',
    ('Micron', 'emmc', '', '128.0', 'GB'): '35',
    ('Micron', 'emmc', '', '16.0', 'GB'): '12',
    ('Micron', 'emmc', '', '256.0', 'GB'): '40',
    ('Micron', 'emmc', '', '4.0', 'GB'): '5',
    ('Micron', 'emmc', '', '64.0', 'GB'): '30',
    ('Micron', 'lpddr', 'LPDDR3', '2.0', 'GB'): '3',
    ('Micron', 'lpddr', 'LPDDR3', '3.0', 'GB'): '3',
    ('Micron', 'lpddr', 'LPDDR3', '4.0', 'GB'): '5',
    ('Micron', 'lpddr', 'LPDDR4', '2.0', 'GB'): '8',
    ('Micron', 'lpddr', 'LPDDR4', '3.0', 'GB'): '8',
    ('Micron', 'lpddr', 'LPDDR4', '4.0', 'GB'): '15',
    ('Micron', 'lpddr', 'LPDDR4', '6.0', 'GB'): '30',
    ('Micron', 'lpddr', 'LPDDR5', '8.0', 'GB'): '60',
    ('Micron', 'umcp', '', '64.0', 'GB'): '95',
    ('Nanya', 'ddr', 'DDR3', '2.0', 'Gb'): '2.8',
    ('Nanya', 'ddr', 'DDR3', '4.0', 'Gb'): '3.8',
    ('Rayson', 'emmc', '', '8.0', 'GB'): '10',
    ('Rayson', 'lpddr', 'LPDDR4', '2.0', 'GB'): '8',
    ('SK Hynix', 'ddr', 'DDR3', '2.0', 'Gb'): '2.8',
    ('SK Hynix', 'ddr', 'DDR3', '4.0', 'Gb'): '3.8',
    ('SK Hynix', 'ddr', 'DDR4', '4.0', 'Gb'): '6.2',
    ('SK Hynix', 'emcp', '', '128.0', 'GB'): '105',
    ('SK Hynix', 'emcp', '', '16.0', 'GB'): '16',
    ('SK Hynix', 'emcp', '', '32.0', 'GB'): '37.5',
    ('SK Hynix', 'emcp', '', '64.0', 'GB'): '95',
    ('SK Hynix', 'emcp', '', '8.0', 'GB'): '10',
    ('SK Hynix', 'emmc', '', '128.0', 'GB'): '35',
    ('SK Hynix', 'emmc', '', '16.0', 'GB'): '12',
    ('SK Hynix', 'emmc', '', '32.0', 'GB'): '20',
    ('SK Hynix', 'emmc', '', '4.0', 'GB'): '5',
    ('SK Hynix', 'emmc', '', '64.0', 'GB'): '30',
    ('SK Hynix', 'emmc', '', '8.0', 'GB'): '10',
    ('SK Hynix', 'lpddr', 'LPDDR3', '2.0', 'GB'): '3',
    ('SK Hynix', 'lpddr', 'LPDDR3', '3.0', 'GB'): '3',
    ('SK Hynix', 'lpddr', 'LPDDR3', '4.0', 'GB'): '5',
    ('SK Hynix', 'lpddr', 'LPDDR4', '4.0', 'GB'): '15',
    ('SK Hynix', 'lpddr', 'LPDDR4', '6.0', 'GB'): '30',
    ('SK Hynix', 'ufs', '', '32.0', 'GB'): '20',
    ('SK Hynix', 'umcp', '', '128.0', 'GB'): '105',
    ('Samsung', 'ddr', 'DDR3', '2.0', 'Gb'): '2.8',
    ('Samsung', 'ddr', 'DDR3', '4.0', 'Gb'): '3.8',
    ('Samsung', 'ddr', 'DDR3', '8.0', 'Gb'): '3.8',
    ('Samsung', 'emcp', '', '128.0', 'GB'): '105',
    ('Samsung', 'emcp', '', '16.0', 'GB'): '16',
    ('Samsung', 'emcp', '', '32.0', 'GB'): '37.5',
    ('Samsung', 'emcp', '', '64.0', 'GB'): '95',
    ('Samsung', 'emcp', '', '8.0', 'GB'): '10',
    ('Samsung', 'emmc', '', '128.0', 'GB'): '35',
    ('Samsung', 'emmc', '', '16.0', 'GB'): '12',
    ('Samsung', 'emmc', '', '32.0', 'GB'): '20',
    ('Samsung', 'emmc', '', '4.0', 'GB'): '5',
    ('Samsung', 'emmc', '', '64.0', 'GB'): '30',
    ('Samsung', 'emmc', '', '8.0', 'GB'): '10',
    ('Samsung', 'lpddr', 'LPDDR3', '2.0', 'GB'): '3',
    ('Samsung', 'lpddr', 'LPDDR3', '3.0', 'GB'): '3',
    ('Samsung', 'lpddr', 'LPDDR3', '4.0', 'GB'): '5',
    ('Samsung', 'lpddr', 'LPDDR4', '2.0', 'GB'): '8',
    ('Samsung', 'lpddr', 'LPDDR4', '3.0', 'GB'): '8',
    ('Samsung', 'lpddr', 'LPDDR4', '4.0', 'GB'): '15',
    ('Samsung', 'lpddr', 'LPDDR4', '6.0', 'GB'): '30',
    ('Samsung', 'lpddr', 'LPDDR4', '8.0', 'GB'): '40',
    ('Samsung', 'lpddr', 'LPDDR5', '6.0', 'GB'): '40',
    ('Samsung', 'lpddr', 'LPDDR5', '8.0', 'GB'): '60',
    ('Samsung', 'ufs', '', '128.0', 'GB'): '35',
    ('Samsung', 'ufs', '', '256.0', 'GB'): '40',
    ('Samsung', 'ufs', '', '32.0', 'GB'): '20',
    ('Samsung', 'ufs', '', '512.0', 'GB'): '50',
    ('Samsung', 'ufs', '', '64.0', 'GB'): '30',
    ('Samsung', 'umcp', '', '128.0', 'GB'): '105',
    ('Samsung', 'umcp', '', '256.0', 'GB'): '115',
    ('SanDisk', 'emcp', '', '16.0', 'GB'): '16',
    ('SanDisk', 'emmc', '', '128.0', 'GB'): '35',
    ('SanDisk', 'emmc', '', '16.0', 'GB'): '12',
    ('SanDisk', 'emmc', '', '32.0', 'GB'): '20',
    ('SanDisk', 'emmc', '', '4.0', 'GB'): '5',
    ('SanDisk', 'emmc', '', '64.0', 'GB'): '30',
    ('SanDisk', 'emmc', '', '8.0', 'GB'): '10',
    ('Toshiba-Kioxia', 'emmc', '', '16.0', 'GB'): '12',
    ('Toshiba-Kioxia', 'emmc', '', '32.0', 'GB'): '20',
    ('Toshiba-Kioxia', 'emmc', '', '4.0', 'GB'): '5',
    ('Toshiba-Kioxia', 'emmc', '', '8.0', 'GB'): '10',
    ('Toshiba-Kioxia', 'ufs', '', '128.0', 'GB'): '35',
    ('Toshiba-Kioxia', 'ufs', '', '64.0', 'GB'): '30'},
41: {('GigaDevice', 'ddr', 'DDR4', '4.0', 'Gb'): '6.2',
    ('Kingston', 'emcp', '', '16.0', 'GB'): '16',
    ('Kingston', 'emcp', '', '8.0', 'GB'): '10',
    ('Micron', 'ddr', 'DDR3', '1.0', 'Gb'): '2',
    ('Micron', 'ddr', 'DDR3', '2.0', 'Gb'): '2.8',
    ('Micron', 'ddr', 'DDR3', '4.0', 'Gb'): '3.8',
    ('Micron', 'ddr', 'DDR3', '8.0', 'Gb'): '3.8',
    ('Micron', 'ddr', 'DDR4', '8.0', 'Gb'): '10.4',
    ('Micron', 'emcp', '', '128.0', 'GB'): '105',
    ('Micron', 'emcp', '', '16.0', 'GB'): '16',
    ('Micron', 'emcp', '', '32.0', 'GB'): '37.5',
    ('Micron', 'emcp', '', '64.0', 'GB'): '95',
    ('Micron', 'emcp', '', '8.0', 'GB'): '10',
    ('Micron', 'emmc', '', '128.0', 'GB'): '35',
    ('Micron', 'emmc', '', '16.0', 'GB'): '12',
    ('Micron', 'emmc', '', '4.0', 'GB'): '5',
    ('Micron', 'emmc', '', '8.0', 'GB'): '10',
    ('Micron', 'lpddr', 'LPDDR3', '2.0', 'GB'): '3',
    ('Micron', 'lpddr', 'LPDDR3', '3.0', 'GB'): '3',
    ('Micron', 'lpddr', 'LPDDR3', '4.0', 'GB'): '5',
    ('Micron', 'lpddr', 'LPDDR4', '1.0', 'GB'): '3',
    ('Micron', 'lpddr', 'LPDDR4', '2.0', 'GB'): '8',
    ('Micron', 'lpddr', 'LPDDR4', '3.0', 'GB'): '8',
    ('Micron', 'lpddr', 'LPDDR4', '4.0', 'GB'): '15',
    ('Micron', 'lpddr', 'LPDDR4', '6.0', 'GB'): '30',
    ('Micron', 'lpddr', 'LPDDR4', '8.0', 'GB'): '40',
    ('Micron', 'umcp', '', '64.0', 'GB'): '95',
    ('Nanya', 'ddr', 'DDR3', '1.0', 'Gb'): '2',
    ('Nanya', 'ddr', 'DDR3', '2.0', 'Gb'): '2.8',
    ('Nanya', 'ddr', 'DDR3', '4.0', 'Gb'): '3.8',
    ('Rayson', 'emmc', '', '8.0', 'GB'): '10',
    ('Rayson', 'lpddr', 'LPDDR4', '2.0', 'GB'): '8',
    ('SK Hynix', 'ddr', 'DDR3', '1.0', 'Gb'): '2',
    ('SK Hynix', 'ddr', 'DDR3', '2.0', 'Gb'): '2.8',
    ('SK Hynix', 'ddr', 'DDR3', '4.0', 'Gb'): '3.8',
    ('SK Hynix', 'emcp', '', '128.0', 'GB'): '105',
    ('SK Hynix', 'emcp', '', '16.0', 'GB'): '16',
    ('SK Hynix', 'emcp', '', '32.0', 'GB'): '37.5',
    ('SK Hynix', 'emcp', '', '64.0', 'GB'): '95',
    ('SK Hynix', 'emcp', '', '8.0', 'GB'): '10',
    ('SK Hynix', 'emmc', '', '128.0', 'GB'): '35',
    ('SK Hynix', 'emmc', '', '16.0', 'GB'): '12',
    ('SK Hynix', 'emmc', '', '32.0', 'GB'): '20',
    ('SK Hynix', 'emmc', '', '4.0', 'GB'): '5',
    ('SK Hynix', 'emmc', '', '64.0', 'GB'): '30',
    ('SK Hynix', 'emmc', '', '8.0', 'GB'): '10',
    ('SK Hynix', 'lpddr', 'LPDDR3', '1.0', 'GB'): '3',
    ('SK Hynix', 'lpddr', 'LPDDR3', '2.0', 'GB'): '3',
    ('SK Hynix', 'lpddr', 'LPDDR3', '3.0', 'GB'): '3',
    ('SK Hynix', 'lpddr', 'LPDDR3', '4.0', 'GB'): '5',
    ('SK Hynix', 'lpddr', 'LPDDR4', '1.0', 'GB'): '3',
    ('SK Hynix', 'lpddr', 'LPDDR4', '2.0', 'GB'): '8',
    ('SK Hynix', 'lpddr', 'LPDDR4', '4.0', 'GB'): '15',
    ('SK Hynix', 'lpddr', 'LPDDR4', '6.0', 'GB'): '30',
    ('SK Hynix', 'lpddr', 'LPDDR4', '8.0', 'GB'): '40',
    ('SK Hynix', 'ufs', '', '32.0', 'GB'): '20',
    ('SK Hynix', 'umcp', '', '128.0', 'GB'): '105',
    ('SK Hynix', 'umcp', '', '64.0', 'GB'): '95',
    ('Samsung', 'ddr', 'DDR3', '1.0', 'Gb'): '2',
    ('Samsung', 'ddr', 'DDR3', '2.0', 'Gb'): '2.8',
    ('Samsung', 'ddr', 'DDR3', '4.0', 'Gb'): '3.8',
    ('Samsung', 'ddr', 'DDR3', '8.0', 'Gb'): '3.8',
    ('Samsung', 'ddr', 'DDR4', '4.0', 'Gb'): '6.2',
    ('Samsung', 'ddr', 'DDR4', '8.0', 'Gb'): '10.4',
    ('Samsung', 'emcp', '', '128.0', 'GB'): '105',
    ('Samsung', 'emcp', '', '16.0', 'GB'): '16',
    ('Samsung', 'emcp', '', '32.0', 'GB'): '37.5',
    ('Samsung', 'emcp', '', '64.0', 'GB'): '95',
    ('Samsung', 'emcp', '', '8.0', 'GB'): '10',
    ('Samsung', 'emmc', '', '16.0', 'GB'): '12',
    ('Samsung', 'emmc', '', '32.0', 'GB'): '20',
    ('Samsung', 'emmc', '', '4.0', 'GB'): '5',
    ('Samsung', 'emmc', '', '64.0', 'GB'): '30',
    ('Samsung', 'emmc', '', '8.0', 'GB'): '10',
    ('Samsung', 'lpddr', 'LPDDR3', '1.0', 'GB'): '3',
    ('Samsung', 'lpddr', 'LPDDR3', '1.5', 'GB'): '3',
    ('Samsung', 'lpddr', 'LPDDR3', '2.0', 'GB'): '3',
    ('Samsung', 'lpddr', 'LPDDR3', '3.0', 'GB'): '3',
    ('Samsung', 'lpddr', 'LPDDR3', '4.0', 'GB'): '5',
    ('Samsung', 'lpddr', 'LPDDR4', '1.0', 'GB'): '3',
    ('Samsung', 'lpddr', 'LPDDR4', '2.0', 'GB'): '8',
    ('Samsung', 'lpddr', 'LPDDR4', '3.0', 'GB'): '8',
    ('Samsung', 'lpddr', 'LPDDR4', '4.0', 'GB'): '15',
    ('Samsung', 'lpddr', 'LPDDR4', '6.0', 'GB'): '30',
    ('Samsung', 'lpddr', 'LPDDR4', '8.0', 'GB'): '40',
    ('Samsung', 'lpddr', 'LPDDR5', '12.0', 'GB'): '80',
    ('Samsung', 'lpddr', 'LPDDR5', '6.0', 'GB'): '40',
    ('Samsung', 'ufs', '', '128.0', 'GB'): '35',
    ('Samsung', 'ufs', '', '256.0', 'GB'): '40',
    ('Samsung', 'ufs', '', '32.0', 'GB'): '20',
    ('Samsung', 'ufs', '', '64.0', 'GB'): '30',
    ('Samsung', 'umcp', '', '128.0', 'GB'): '105',
    ('Samsung', 'umcp', '', '64.0', 'GB'): '95',
    ('SanDisk', 'emcp', '', '16.0', 'GB'): '16',
    ('SanDisk', 'emmc', '', '128.0', 'GB'): '35',
    ('SanDisk', 'emmc', '', '16.0', 'GB'): '12',
    ('SanDisk', 'emmc', '', '32.0', 'GB'): '20',
    ('SanDisk', 'emmc', '', '4.0', 'GB'): '5',
    ('SanDisk', 'emmc', '', '64.0', 'GB'): '30',
    ('SanDisk', 'emmc', '', '8.0', 'GB'): '10',
    ('Toshiba-Kioxia', 'emmc', '', '16.0', 'GB'): '12',
    ('Toshiba-Kioxia', 'emmc', '', '32.0', 'GB'): '20',
    ('Toshiba-Kioxia', 'emmc', '', '4.0', 'GB'): '5',
    ('Toshiba-Kioxia', 'emmc', '', '8.0', 'GB'): '10',
    ('Toshiba-Kioxia', 'ufs', '', '128.0', 'GB'): '35',
    ('Toshiba-Kioxia', 'ufs', '', '64.0', 'GB'): '30'}}


def soma_linhas(lote, linhas):
    """Σ (¥ unitário da tabela × quantidade) para as linhas de uma OV.

    `linhas` = iterável de objetos com brand/kind/gen/tier_value/tier_unit/
    quantity. Levanta KeyError se alguma linha não estiver na tabela — silêncio
    aqui viraria fatura a menos.
    """
    tab = PRECOS[lote]
    total = D('0.00')
    for l in linhas:
        total += D(tab[chave(l)]) * l.quantity
    return total


def chave(linha):
    """A mesma chave que o create_draft_for_lot usa para agregar."""
    return (linha.brand or '', linha.kind, linha.gen,
            str(linha.tier_value), linha.tier_unit)


def self_check(plano=None, precos=None):
    """Confere a aritmética da tabela ANTES de qualquer gravação.

    Recebe as tabelas por parâmetro (e não as do módulo) para que o teste possa
    conferir um plano de brinquedo com as mesmas regras do de verdade — checar
    sempre o plano real tornaria o próprio self_check impossível de testar.

    Não olha o banco: só verifica que a tabela congelada soma o mesmo total
    que o PLANO declara, e que taxa × ¥ chega perto do US$ da mestra. Se um dia
    alguém editar um preço à mão, isto estoura em vez de gravar torto.
    """
    plano = PLANO if plano is None else plano
    precos = PRECOS if precos is None else precos
    erros = []
    for lote, p in plano.items():
        if p['precos'] and lote not in precos:
            erros.append(f'lote {lote}: precos=True mas não há tabela de preços')
        # ¥ × taxa tem que chegar perto do US$ da mestra (o resto é
        # arredondamento de quem somou a planilha — até 1 dólar).
        derivado = p['total_rmb'] * p['fx']
        if abs(derivado - p['total_usd']) > D('1'):
            erros.append(
                f'lote {lote}: ¥{p["total_rmb"]} × {p["fx"]} = {derivado:.2f}, '
                f'mas a mestra diz US$ {p["total_usd"]} — diferença grande demais '
                f'para ser arredondamento')
    # A tabela de preços tem que somar exatamente o total_rmb declarado?
    # Não dá para checar aqui (depende das quantidades, que estão no banco) —
    # o comando faz essa conferência com as linhas na mão, antes de gravar.
    if erros:
        raise AssertionError('self_check falhou:\n  ' + '\n  '.join(erros))
    return True


# ══════════════════════════════════════════════════════════════════════════
# OS TRÊS LOTES LEGADOS — envios que só existem na planilha mestra
# ══════════════════════════════════════════════════════════════════════════
# Nunca entraram no sistema porque são anteriores a ele. Entram agora com a
# cadeia inteira já quitada, e com o número que o mapa de renumeração aprovado
# pelo dono (2026-09-01) reserva para eles: 1, 2 e 4 — livres hoje, porque a
# eMiner começa no 39.
#
# TAXA: 0,15 nos três. Não é chute — é o que a aritmética da fatura do EXP02
# mostra (os 20 preços em US$ dão ¥ INTEIRO a 0,15 e nenhum a 0,14) e o que o
# K9 confirma (US$ 0,15/unidade ÷ 0,15 = ¥ 1,00 exato). O 0,14 só aparece nos
# lotes 040 e 041, de meados de julho em diante.
#
# LINHAS: só o K9 tem. O EXP02 tem os 20 part numbers da fatura, mas na forma
# CURTA que a fatura usa (`K4B2G16`, não `K4B2G1646Q`) — o classify resolve
# tipo e capacidade em 10 dos 20. Deduzir a capacidade que falta a partir do
# preço seria inventar chave de catálogo, que é justamente o que a casa não
# faz. Então as entradas nascem com part number, quantidade, marca e tipo, SEM
# chave de preço, e o valor mora no cabeçalho. Quando alguém resolver esses
# PNs no catálogo, o `fix_pns` preenche a chave e as linhas aparecem.
# O EXP01 não tem nem isso: não apareceu fatura dele, então nasce só com o
# cabeçalho e a contagem fica registrada na descrição.

#: (part_number, quantidade, marca, tipo, ¥ unitário da fatura)
#: O ¥ vem de US$ ÷ 0,15 e é guardado como MEMÓRIA da fatura — não vira preço
#: de linha enquanto a chave de catálogo não existir.
ENTRADAS_EXP02 = [('IS43TR16128BL', 222, '', '', '2'),
 ('H5ANBG6NDJ', 4, 'SK Hynix', 'DDR4', '13'),
 ('RS70B08G3', 1, 'Rayson', 'eMMC', '5'),
 ('KMQEG0013B', 217, 'Samsung', 'eMCP', '15'),
 ('H5TQ2G63', 2009, 'SK Hynix', 'DDR3', '3'),
 ('H5TQ4G63', 294, 'SK Hynix', 'DDR3', '4'),
 ('D9VCT', 115, 'Micron', 'DDR3L', '3'),
 ('D9PQL', 13, 'Micron', 'DDR3L', '3'),
 ('NT5C256M16', 93, '', '', '4'),
 ('NT5C128M16', 2344, '', '', '3'),
 ('K4A8G16', 16, 'Samsung', 'DDR4', '13'),
 ('D9PTH', 35, 'Micron', 'DDR3L', '3'),
 ('K4A4G16', 276, 'Samsung', 'DDR4', '6'),
 ('D9PXV', 16, 'Micron', 'DDR3L', '4'),
 ('D9SHD', 1102, 'Micron', 'DDR3L', '3'),
 ('K4B2G16', 3514, 'Samsung', 'DDR3', '3'),
 ('K4B4G16', 585, 'Samsung', 'DDR3', '4'),
 ('D9PSZ', 77, 'Micron', 'DDR3L', '3'),
 ('D9PTK', 850, 'Micron', 'DDR3L', '3'),
 ('D9SDD', 1109, 'Micron', 'DDR3L', '3')]


LEGADOS = {
    1: dict(
        nome='CHIP-EXP012026', origin='mixed',
        descricao=('CHIP-EXP012026 — importado do controle antigo. 10.049 chips '
                   'pela contagem da planilha; sem detalhe por part number, '
                   'então o lote nasce sem entradas e o valor fica no cabeçalho.'),
        unidades=10049, fx=D('0.15'),
        total_rmb=D('9749.87'), total_usd=D('1462.48'),
        data=date(2026, 4, 8), pago_em=date(2026, 4, 8),
        carteira='BINANCE HANDSON', entradas=(), linha_k9=None,
        aviso='¥ derivado de US$ ÷ 0,15; sem fatura, não dá para reconstruir linha a linha.'),
    2: dict(
        nome='CHIP-EXP022026', origin='pcb',
        descricao=('CHIP-EXP022026 — importado do controle antigo. Fatura de '
                   '26/05/2026 para Tang Dongmei (Macau), 20 part numbers, '
                   '12.892 chips, US$ 6.461,40 a 0,15 = ¥ 43.076,00.'),
        unidades=12892, fx=D('0.15'),
        total_rmb=D('43076.00'), total_usd=D('6461.40'),
        data=date(2026, 6, 9), pago_em=date(2026, 6, 9),
        carteira='BINANCE HANDSON', entradas=ENTRADAS_EXP02, linha_k9=None,
        aviso='Entradas sem chave de preço: a fatura traz o PN na forma curta.'),
    4: dict(
        nome='K9', origin='k9',
        descricao=('K9 — importado do controle antigo. 5.507 chips de NAND cru '
                   'a ¥ 1,00 cada (US$ 0,15 a 0,15). Preço plano, uma linha só.'),
        unidades=5507, fx=D('0.15'),
        total_rmb=D('5507.00'), total_usd=D('826.05'),
        data=date(2026, 7, 4), pago_em=date(2026, 7, 4),
        carteira='BINANCE HANDSON',
        entradas=(('K9', 5507, '', 'K9', '1'),),
        linha_k9=dict(kind='k9', tier_value=D('1'), tier_unit='', unit_rmb=D('1.00')),
        aviso='Data 04/07 confirmada pelo dono (a mestra dizia 2026-04-07, mm/dd trocado).'),
}


def self_check_legados(legados=None):
    """A aritmética dos legados: ¥ × taxa tem que dar o US$ da mestra, e a soma
    das entradas tem que dar a contagem declarada."""
    legados = LEGADOS if legados is None else legados
    erros = []
    for num, p in legados.items():
        derivado = (p['total_rmb'] * p['fx']).quantize(D('0.01'))
        if abs(derivado - p['total_usd']) > D('0.01'):
            erros.append(f'lote {num}: ¥{p["total_rmb"]} x {p["fx"]} = {derivado}, '
                         f'mas a mestra diz US$ {p["total_usd"]}')
        if p['entradas']:
            soma = sum(q for _pn, q, _m, _t, _y in p['entradas'])
            if soma != p['unidades']:
                erros.append(f'lote {num}: entradas somam {soma}, '
                             f'declarado {p["unidades"]}')
    if erros:
        raise AssertionError('self_check_legados falhou:\n  ' + '\n  '.join(erros))
    return True
