from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("part_number", models.CharField(db_index=True, max_length=100, verbose_name="Part Number")),
                ("chip_type", models.CharField(blank=True, default="", max_length=50, verbose_name="Tipo")),
                ("capacity", models.CharField(blank=True, default="", max_length=100, verbose_name="Capacidade")),
                ("emcp_ram", models.CharField(blank=True, default="", max_length=100, verbose_name="RAM (eMCP)")),
                ("emcp_nand", models.CharField(blank=True, default="", max_length=100, verbose_name="NAND (eMCP)")),
                ("is_emcp", models.BooleanField(default=False, verbose_name="É eMCP/uMCP")),
                ("interface", models.CharField(blank=True, default="", max_length=100, verbose_name="Interface")),
                ("classification_source", models.CharField(blank=True, default="", max_length=50, verbose_name="Fonte da classificação")),
                ("quantity", models.PositiveIntegerField(default=1, verbose_name="Quantidade")),
                ("added_at", models.DateTimeField(auto_now_add=True, verbose_name="Adicionado em")),
                ("last_updated", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                (
                    "operator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Operador",
                    ),
                ),
            ],
            options={
                "verbose_name": "Entrada de Estoque",
                "verbose_name_plural": "Entradas de Estoque",
                "ordering": ["-last_updated"],
            },
        ),
        migrations.AddConstraint(
            model_name="inventoryentry",
            constraint=models.UniqueConstraint(
                fields=["operator", "part_number"],
                name="unique_operator_pn",
            ),
        ),
    ]
