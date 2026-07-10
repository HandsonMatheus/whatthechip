"""
scripts/i18n_extract.py — extração de msgids SEM gettext (fallback de sandbox)
===============================================================================
CLI fino sobre a biblioteca **`chips/i18n_source.py`** (a mesma que o portão
``check_translations`` usa na verificação de COMPLETUDE — regra 8). O fluxo
canônico continua sendo ``manage.py makemessages`` (exige GNU gettext — ver
I18N.md §6.2); este script cobre ambientes sem ele (sandbox de agente).

Uso (na raiz do projeto, venv ativo):
    python scripts/i18n_extract.py                # msgids por domínio (JSON)
    python scripts/i18n_extract.py --locations    # inclui arquivo:linha

Saída: {"django": [...], "djangojs": [...]} — idênticos aos do makemessages
(mesmo templatize), então os .po continuam msgmerge-compatíveis.
"""

import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_test')

import django  # noqa: E402

django.setup()

from chips.i18n_source import extract_django, extract_djangojs  # noqa: E402

if __name__ == '__main__':
    with_loc = '--locations' in sys.argv
    print(json.dumps({
        'django':   extract_django(with_locations=with_loc),
        'djangojs': extract_djangojs(with_locations=with_loc),
    }, ensure_ascii=False, indent=1))
