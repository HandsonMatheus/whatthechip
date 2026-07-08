"""
scripts/i18n_compile.py — compila locale/**/*.po → .mo SEM gettext
===================================================================
Fallback do ``python manage.py compilemessages`` (que exige o msgfmt do GNU
gettext — I18N.md §6.2/§6.3) para ambientes sem ele (sandbox de agente, máquina
sem brew). Usa ``polib`` (``pip install polib``). O runtime do Django lê o .mo,
não o .po — sem este passo a tradução NÃO aparece (armadilha §8.6).

Uso (na raiz do projeto):
    python scripts/i18n_compile.py            # compila todos os idiomas
    python scripts/i18n_compile.py es en      # só estes
"""
import sys
from pathlib import Path

try:
    import polib
except ImportError:
    sys.exit('polib ausente: pip install polib (ou use manage.py compilemessages)')

BASE = Path(__file__).resolve().parent.parent
only = set(sys.argv[1:])

n = 0
for po_path in sorted((BASE / 'locale').rglob('*.po')):
    lang = po_path.parent.parent.name          # locale/<lang>/LC_MESSAGES/x.po
    if only and lang not in only and lang.replace('_', '-').lower() not in only:
        continue
    po = polib.pofile(str(po_path))
    mo_path = po_path.with_suffix('.mo')
    po.save_as_mofile(str(mo_path))
    print(f'✓ {mo_path.relative_to(BASE)} ({len(po)} entradas)')
    n += 1
print(f'{n} catálogo(s) compilado(s).' if n else 'Nada a compilar.')
