from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('pages', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Brand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(unique=True)),
                ('code', models.TextField(help_text='Código curto, ex: SAM, HYN, MIC', unique=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Marca',
                'verbose_name_plural': 'Marcas',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Source',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.TextField(blank=True, default='')),
                ('name', models.TextField()),
                ('src_type', models.CharField(choices=[('manual', 'Manual'), ('scraper', 'Scraper'), ('distributor', 'Distribuidor'), ('ai', 'IA'), ('datasheet', 'Datasheet')], max_length=32)),
                ('fetched_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Fonte',
                'verbose_name_plural': 'Fontes',
            },
        ),
        migrations.CreateModel(
            name='ChipFamily',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefix', models.TextField(db_index=True, help_text='Prefixo do PN, ex: KLM, K4B, H5AN')),
                ('chip_type', models.TextField(help_text='Ex: eMMC, RAM, eMCP, UFS')),
                ('subtype', models.TextField(blank=True, default='', help_text='Ex: DDR3 SDRAM, LPDDR4X')),
                ('interface', models.TextField(blank=True, default='')),
                ('decode_cap_pos', models.IntegerField(blank=True, help_text='Posição no PN que indica a capacidade', null=True)),
                ('decode_cap_map', models.TextField(blank=True, default='', help_text='Nome do DecodeMap para capacidade')),
                ('decode_gen_pos', models.IntegerField(blank=True, null=True)),
                ('decode_gen_map', models.TextField(blank=True, default='', help_text='Nome do DecodeMap para geração')),
                ('decode_density_type', models.TextField(blank=True, default='', help_text="'pc' ou 'mobile' para chips DRAM")),
                ('is_emcp', models.BooleanField(default=False)),
                ('suffix_rules', models.TextField(blank=True, default='', help_text='JSON com regras de sufixo')),
                ('tip', models.TextField(blank=True, default='', help_text='Dica exibida para o operador')),
                ('reasoning', models.TextField(blank=True, default='', help_text='JSON list com passos de raciocínio')),
                ('priority', models.IntegerField(default=100, help_text='Menor = maior prioridade no match de prefixo')),
                ('active', models.BooleanField(default=True)),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('brand', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='families', to='chips.brand')),
                ('doc_page', models.ForeignKey(blank=True, help_text='Página de documentação correspondente (fab-samsung, fab-hynix...)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='chip_families', to='pages.page')),
            ],
            options={
                'verbose_name': 'Família de Chip',
                'verbose_name_plural': 'Famílias de Chips',
                'ordering': ['priority', 'prefix'],
            },
        ),
        migrations.CreateModel(
            name='DecodeMap',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('map_name', models.TextField(help_text='Ex: CAP_MAP, DRAM_PC, DRAM_MOBILE, EMMC_GEN')),
                ('char_key', models.TextField(help_text='Chave — caractere ou código do PN')),
                ('val_primary', models.TextField(blank=True, default='', help_text='Valor principal, ex: 16GB')),
                ('val_secondary', models.TextField(blank=True, default='', help_text='Valor secundário, ex: 128MB por die')),
                ('notes', models.TextField(blank=True, default='')),
                ('brand', models.ForeignKey(blank=True, help_text='Deixar em branco se o mapa for universal', null=True, on_delete=django.db.models.deletion.SET_NULL, to='chips.brand')),
            ],
            options={
                'verbose_name': 'Mapa de Decodificação',
                'verbose_name_plural': 'Mapas de Decodificação',
                'ordering': ['map_name', 'char_key'],
                'unique_together': {('map_name', 'char_key', 'brand')},
            },
        ),
        migrations.CreateModel(
            name='KnownPart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('part_number', models.TextField(db_index=True, unique=True)),
                ('status', models.CharField(choices=[('raw', '⬜ Raw — sem enriquecimento'), ('enriched', '✅ Enriquecido'), ('failed', '❌ Falha no enriquecimento')], db_index=True, default='raw', max_length=20)),
                ('chip_type', models.TextField(blank=True, default='')),
                ('subtype', models.TextField(blank=True, default='')),
                ('capacity', models.TextField(blank=True, default='', help_text='Ex: 64GB, 512MB')),
                ('density_gbit', models.TextField(blank=True, default='', help_text='Ex: 4Gb (por die)')),
                ('density_gb', models.TextField(blank=True, default='', help_text='Ex: 512MB (por die)')),
                ('emcp_ram', models.TextField(blank=True, default='', help_text='Ex: LPDDR4X 4GB')),
                ('emcp_nand', models.TextField(blank=True, default='', help_text='Ex: eMMC 5.1 64GB')),
                ('interface', models.TextField(blank=True, default='')),
                ('device', models.TextField(blank=True, default='', help_text='Ex: Galaxy J3/J5 2016')),
                ('notes', models.TextField(blank=True, default='')),
                ('confidence', models.CharField(choices=[('confirmed', '✅ Confirmado'), ('manual', '✏️  Manual'), ('distributor', '🏪 Distribuidor'), ('ai_high', '🤖 IA — Alta'), ('ai_medium', '🤖 IA — Média'), ('ai_low', '🤖 IA — Baixa'), ('estimated', '~ Estimado')], default='estimated', max_length=20)),
                ('source_url', models.TextField(blank=True, default='')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('brand', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parts', to='chips.brand')),
                ('family', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='parts', to='chips.chipfamily')),
                ('source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='chips.source')),
            ],
            options={
                'verbose_name': 'Part Number Conhecido',
                'verbose_name_plural': 'Part Numbers Conhecidos',
                'ordering': ['part_number'],
            },
        ),
        migrations.CreateModel(
            name='SearchLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('part_number', models.TextField()),
                ('found', models.BooleanField(default=False)),
                ('source_used', models.TextField(blank=True, default='', help_text='grammar | db_exact | gemini | not_found')),
                ('searched_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Log de Busca',
                'verbose_name_plural': 'Logs de Busca',
                'ordering': ['-searched_at'],
            },
        ),
        migrations.CreateModel(
            name='UnknownChip',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('part_number', models.TextField(unique=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('logged_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Chip Desconhecido',
                'verbose_name_plural': 'Chips Desconhecidos',
                'ordering': ['-logged_at'],
            },
        ),
    ]
