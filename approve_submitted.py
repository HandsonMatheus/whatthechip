#!/usr/bin/env python
"""
approve_submitted.py — LOCAL, aponta DATABASE_URL pro PROD.

Aprova em MASSA todos os known_parts 'submitted' (review_status → approved), SEM
passar pelo admin/gunicorn — então SEM timeout de requisição (o que dá o 502 quando
você seleciona centenas no admin). Faz UM UPDATE + UM bump de catalog_version no fim
(o engine recarrega sozinho). O histórico (pghistory) é preservado: roda por trigger
no Postgres, pega o .update() também.

Four-eyes: pula registros que VOCÊ mesmo submeteu (submitted_by == você). Os
submetidos sem --user (submitted_by NULL, o caso do sync) são todos aprováveis.

Uso:
    export DATABASE_URL="postgresql://…render.com…"          # PROD (segredo)
    python approve_submitted.py --user <seu_username>          # DRY-RUN (só conta)
    python approve_submitted.py --user <seu_username> --commit  # aprova de verdade
"""
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.contrib.auth import get_user_model   # noqa: E402
from django.db.models import Q                    # noqa: E402
from django.utils import timezone                 # noqa: E402

from chips.models import CatalogVersion, KnownPart  # noqa: E402

U = get_user_model()
commit = "--commit" in sys.argv
uname = sys.argv[sys.argv.index("--user") + 1] if "--user" in sys.argv else None

if not uname:
    print("Falta --user <username> (quem aprova). Superusuários no banco:")
    for u in U.objects.filter(is_superuser=True).values_list("username", flat=True):
        print("   •", u)
    sys.exit(1)

user = U.objects.filter(username=uname).first()
if not user:
    print(f"❌ usuário '{uname}' não existe neste banco.")
    sys.exit(1)

# aprováveis = submitted E (submetido pelo sistema/NULL OU por outro usuário ≠ você)
approvable = (KnownPart.objects.filter(review_status="submitted")
              .filter(Q(submitted_by__isnull=True) | ~Q(submitted_by_id=user.id)))
blocked = KnownPart.objects.filter(review_status="submitted", submitted_by_id=user.id).count()

n = approvable.count()
print(f"submitted aprováveis por '{uname}': {n}"
      + (f"   ⚠ {blocked} bloqueados (four-eyes: submetidos por você — aprove com OUTRO usuário)"
         if blocked else ""))

if not commit:
    print("DRY-RUN — nada gravado. Rode de novo com --commit.")
    sys.exit(0)

if n:
    approvable.update(review_status="approved", approved_by=user,
                      reviewed_at=timezone.now())
    v = CatalogVersion.bump()
    print(f"✅ {n} aprovado(s). catalog_version → {v} (engine recarrega sozinho, sem restart).")
else:
    print("Nada a aprovar.")
