"""
core/safe_command.py
====================
Base para comandos que ESCREVEM no banco — passo 1C do
`docs/PLANO_IMPLEMENTACAO_ESCALABILIDADE.md` (a "trava de banco-alvo").

Imprime o BANCO-ALVO (host + nome) ANTES de qualquer coisa — a trava que teria
evitado o acidente "rodei no localhost achando que era produção". E, ao GRAVAR
(`--commit`) num terminal interativo, exige digitar o nome do banco para confirmar.

Adote num comando trocando `BaseCommand` por `SafeWriteCommand`:

    from core.safe_command import SafeWriteCommand
    class Command(SafeWriteCommand):
        ...

Sem `--commit` (dry-run), só mostra o banner — zero fricção. Com `--commit`,
mostra o banner E pede confirmação. Para desligar a confirmação num comando
específico, defina `confirm_on_commit = False`.
"""

import sys

from django.core.management.base import BaseCommand
from django.db import connection


class SafeWriteCommand(BaseCommand):
    #: Se True e o comando tiver --commit, exige digitar o nome do banco para gravar.
    confirm_on_commit = True

    def execute(self, *args, **options):
        db = connection.settings_dict
        name = db.get("NAME") or "?"
        host = db.get("HOST") or "localhost"
        port = db.get("PORT") or ""
        self.stderr.write(self.style.WARNING(
            f"⚠  BANCO-ALVO → name={name}  host={host}  port={port}"
        ))

        if (
            self.confirm_on_commit
            and options.get("commit")
            # Só no uso REAL via linha de comando — nunca em call_command/testes
            # (Django marca o caminho do CLI com _called_from_command_line).
            and getattr(self, "_called_from_command_line", False)
            and getattr(sys.stdin, "isatty", lambda: False)()
        ):
            typed = input(
                f"   Vai GRAVAR neste banco. Digite o nome '{name}' para confirmar: "
            )
            if typed.strip() != name:
                self.stderr.write(self.style.ERROR(
                    "   Abortado — nome do banco não confere."
                ))
                return
        return super().execute(*args, **options)
