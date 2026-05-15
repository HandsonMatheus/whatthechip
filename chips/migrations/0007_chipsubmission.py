from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chips', '0006_alter_chipfamily_decode_cap_map_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChipSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('part_number',     models.TextField(db_index=True,
                    help_text='PN enviado pelo usuário')),
                ('photo',           models.ImageField(blank=True, null=True,
                    upload_to='submissions/%Y/%m/',
                    help_text='Foto do chip enviada pelo usuário (ajuda muito na identificação)')),
                ('context',         models.TextField(blank=True, default='',
                    help_text='Contexto livre: origem, marca do aparelho, observações')),
                ('submitter_email', models.EmailField(blank=True, default='', max_length=254,
                    help_text='E-mail para retorno ao usuário')),
                ('status',          models.CharField(
                    choices=[('pending', '⏳ Pendente'),
                             ('added', '✅ Adicionado ao banco'),
                             ('rejected', '✗ Rejeitado')],
                    default='pending', max_length=20, db_index=True)),
                ('notes',           models.TextField(blank=True, default='',
                    help_text='Anotações internas do operador')),
                ('created_at',      models.DateTimeField(auto_now_add=True)),
                ('resolved_at',     models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Envio de Chip',
                'verbose_name_plural': 'Envios de Chips (Adicionar chip)',
                'ordering': ['-created_at'],
            },
        ),
    ]
