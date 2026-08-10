# ============================================================================
# DIAGNÓSTICO — Lote LOT/002/08/26 (Mundo Metal / eRecyclo) — 100% READ-ONLY
# ============================================================================
# Bug investigado: quantidade do lote INFLADA vs contagem física (5631 no
# sistema vs ~4900 contados). Hipótese: POSTs duplicados no add_chip
# (duplo clique / re-clique em internet lenta — sem idempotência no servidor).
#
# Como rodar (Render Shell, na raiz do projeto):
#   python manage.py shell
#   >>> exec(open('diagnostico_lote002_mundometal.py').read())
#
# NÃO grava nada: só SELECTs. Usa company_scope() (seta o GUC do RLS — sem
# isso as tabelas do estoque leriam 0 linhas em silêncio; armadilha §6.2.2).
# ============================================================================
from datetime import timedelta
from collections import defaultdict

from django.db.models import Sum
from django.utils import timezone

from tenancy.models import Company
from tenancy.scope import company_scope
from estoque.models import Lot, InventoryEntry, PendingEntry, RejectedEntry

SEP = '─' * 74

# ── 1. Localizar a empresa ──────────────────────────────────────────────────
TERMS = ('mundo', 'metal', 'recyclo')
cands = [c for c in Company.objects.all()
         if any(t in (c.name or '').lower() or t in (c.slug or '').lower()
                for t in TERMS)]
print(SEP)
print('EMPRESAS CANDIDATAS:')
for c in cands:
    print(f'  pk={c.pk}  name={c.name!r}  slug={c.slug!r}')
if not cands:
    print('  ⚠ nenhuma empresa com mundo/metal/recyclo no nome — ver lista:')
    for c in Company.objects.all():
        print(f'    pk={c.pk}  name={c.name!r}  slug={c.slug!r}')

# ── 2. Para cada candidata: achar o lote 002 de 08/2026 e diagnosticar ──────
DUP_WINDOW_S = 120          # janela p/ considerar 2 tentativas como "duplicata"

for comp in cands:
    with company_scope(comp):
        lot = (Lot.objects
               .filter(number=2, created_at__year=2026, created_at__month=8)
               .first())
        print(SEP)
        print(f'EMPRESA {comp.name!r} (pk={comp.pk})')
        if lot is None:
            print('  — sem lote number=2 aberto em 08/2026 (códigos existentes:')
            for l in Lot.objects.all()[:15]:
                print(f'      {l.code}  status={l.status}  '
                      f'total={l.total_qty}')
            print('    )')
            continue

        total = lot.total_qty
        n_pns = lot.chip_count
        print(f'  LOTE {lot.code}  status={lot.status}  aberto em '
              f'{lot.created_at:%d/%m/%Y %H:%M}')
        print(f'  TOTAL NO SISTEMA: {total} un. em {n_pns} PNs '
              f'(contagem física relatada: ~4900 → excesso ≈ {total - 4900})')

        # ── 2a. Top PNs por quantidade (os mais prováveis de estarem inflados)
        print(f'\n  TOP 25 PNs POR QUANTIDADE:')
        print(f'  {"PN":<22}{"qtd":>6}   {"1º lançamento":<17}'
              f'{"último lançamento":<17}')
        for e in (InventoryEntry.objects.filter(lot=lot)
                  .order_by('-quantity')[:25]):
            print(f'  {e.part_number:<22}{e.quantity:>6}   '
                  f'{timezone.localtime(e.added_at):%d/%m %H:%M:%S}   '
                  f'{timezone.localtime(e.last_updated):%d/%m %H:%M:%S}')

        # ── 2b. Caso relatado: D9SHD (e vizinhos D9*)
        print(f'\n  CASO RELATADO — PNs D9* no lote '
              f'(operador diz ter lançado ~100 de D9SHD):')
        d9 = InventoryEntry.objects.filter(lot=lot,
                                           part_number__istartswith='D9')
        if not d9.exists():
            print('    (nenhum PN D9* neste lote)')
        for e in d9.order_by('-quantity'):
            print(f'    {e.part_number:<20} qtd={e.quantity:<6} '
                  f'1º={timezone.localtime(e.added_at):%d/%m %H:%M:%S}  '
                  f'último={timezone.localtime(e.last_updated):%d/%m %H:%M:%S}')

        # ── 2c. IMPRESSÃO DIGITAL de duplo-envio na RejectedEntry ──────────
        # InventoryEntry agrega por PN (não guarda lançamento a lançamento),
        # mas a RejectedEntry é APPEND-ONLY: cada clique em "Registrar
        # descarte" vira UMA linha. Se a conexão lenta está gerando POSTs
        # duplicados, aqui aparecem pares idênticos (mesmo PN, mesma qtd,
        # mesmo operador) separados por segundos — prova mecânica do bug.
        print(f'\n  DUPLICATAS NA RejectedEntry (janela ≤{DUP_WINDOW_S}s, '
              f'últimos 30 dias, TODOS os lotes da empresa):')
        since = timezone.now() - timedelta(days=30)
        rej = list(RejectedEntry.objects
                   .filter(created_at__gte=since)
                   .order_by('part_number', 'created_at')
                   .values('lot_id', 'part_number', 'quantity',
                           'operator_id', 'created_at'))
        groups = defaultdict(list)
        for r in rej:
            groups[(r['lot_id'], r['part_number'], r['quantity'],
                    r['operator_id'])].append(r['created_at'])
        dup_pairs = 0
        for (lot_id, pn, qty, op), times in sorted(groups.items()):
            times.sort()
            for a, b in zip(times, times[1:]):
                gap = (b - a).total_seconds()
                if gap <= DUP_WINDOW_S:
                    dup_pairs += 1
                    print(f'    lote_id={lot_id}  {pn:<20} qtd={qty:<5} '
                          f'op={op}  Δ={gap:5.1f}s  '
                          f'({timezone.localtime(a):%d/%m %H:%M:%S} → '
                          f'{timezone.localtime(b):%H:%M:%S})')
        if dup_pairs == 0:
            print('    (nenhum par ≤ janela — descartes não duplicaram '
                  'no período)')
        else:
            print(f'    ⇒ {dup_pairs} par(es) de cliques duplicados '
                  f'registrados — o mesmo padrão infla o estoque '
                  f'(lá as duplicatas se SOMAM na quantidade, invisíveis).')

        # ── 2d. Fila de conferência do lote (contexto)
        pend = PendingEntry.objects.filter(lot=lot)
        print(f'\n  FILA DE CONFERÊNCIA DO LOTE: {pend.count()} PN(s), '
              f'{pend.aggregate(s=Sum("quantity"))["s"] or 0} un.')

print(SEP)
print('FIM — nada foi gravado. Cole a saída no chat para a análise.')
