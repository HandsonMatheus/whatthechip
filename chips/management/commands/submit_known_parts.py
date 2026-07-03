"""
submit_known_parts.py — canal de CONTRIBUIÇÃO de known_parts (Opção 2).

Substitui a autoria via YAML+PR para os known_parts: um chat de marca (ou o dono) escreve
um arquivo de SUBMISSÃO e roda este comando, que valida pelo PORTÃO (o MESMO `KnownPartSpec`
do `load_brands`) e grava cada PN como **review_status='submitted'** — OCULTO do engine até
o dono APROVAR no admin (fila Aprovar/Reprovar, com four-eyes). O arquivo é FORMULÁRIO de
submissão, NÃO a fonte da verdade: é consumido uma vez, não vai pro git, não re-sincroniza
(logo, sem drift). A GRAMÁTICA continua no yaml/PR (`load_brands`); só a AUTORIDADE passa aqui.

Formato (yaml):
    brand: "SK Hynix"
    submitted_by: "meu_usuario"        # opcional; senão use --user
    known_parts:
      - part_number: "H9HCNNNCPMMLXR-NEE"
        chip_type: "eMCP"
        subtype: "LPDDR4"
        emcp_nand: "32GB"
        emcp_ram: "LPDDR4 3GB"
        confidence: confirmed
        notes: "datasheet SK Hynix rev.1.2 / Octopart"   # fonte Tier-1 (proveniência)

Uso:
    python manage.py submit_known_parts arquivo.yaml            # dry-run = portão
    python manage.py submit_known_parts arquivo.yaml --commit --user meu_usuario
"""
import yaml

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

_FIELDS = ["chip_type", "subtype", "capacity", "density_gbit", "density_gb", "emcp_ram",
           "emcp_nand", "interface", "fbga_code", "device", "notes", "source_url", "confidence"]


class Command(BaseCommand):
    help = "Submete known_parts (review_status='submitted') pelo portão. Dry-run por padrão."

    def add_arguments(self, parser):
        parser.add_argument("arquivo")
        parser.add_argument("--commit", action="store_true",
                            help="Grava de verdade (sem isto é dry-run = só o portão).")
        parser.add_argument("--user", default="",
                            help="username do submitter (four-eyes: não poderá auto-aprovar).")

    def handle(self, *args, **opts):
        from django.contrib.auth import get_user_model
        from chips.knowledge.schema import KnownPartSpec
        from chips.models import Brand, KnownPart

        raw = yaml.safe_load(open(opts["arquivo"], encoding="utf-8")) or {}
        brand_name = raw.get("brand")
        if not brand_name:
            raise CommandError("arquivo precisa de 'brand: <nome>'.")
        kps_raw = raw.get("known_parts") or []
        if not kps_raw:
            raise CommandError("nenhum known_part no arquivo.")

        # PORTÃO: valida + normaliza cada known_part (mesmo KnownPartSpec do load_brands).
        specs, erros = [], []
        for i, d in enumerate(kps_raw, 1):
            try:
                specs.append(KnownPartSpec(**d))
            except Exception as e:
                erros.append(f"  #{i} ({d.get('part_number', '?')}): {e}")
        if erros:
            raise CommandError("PORTÃO rejeitou:\n" + "\n".join(erros))

        brand = Brand.objects.filter(name=brand_name).first()
        if brand is None:
            raise CommandError(f"marca '{brand_name}' não existe no banco (crie a gramática antes).")

        uname = opts["user"] or raw.get("submitted_by") or ""
        submitter = None
        if uname:
            submitter = get_user_model().objects.filter(username=uname).first()
            if submitter is None:
                raise CommandError(f"usuário '{uname}' não existe.")

        # Proveniência: confirmed/manual sem fonte Tier-1 é AVISO acionável (não bloqueia
        # a submissão — a revisão humana é o filtro; mas o revisor tem que ver o furo).
        sem_fonte = [s.part_number for s in specs
                     if s.confidence in ("confirmed", "manual") and not (s.notes or s.source_url)]

        self.stdout.write(f"Marca: {brand_name} · {len(specs)} known_part(s) válido(s) no portão · "
                          f"submitter: {uname or '(nenhum)'}")
        if sem_fonte:
            self.stdout.write(self.style.WARNING(
                f"⚠ {len(sem_fonte)} confirmed/manual SEM fonte Tier-1 na notes/source_url "
                f"(o revisor deve exigir): {', '.join(sem_fonte[:10])}"))

        if not opts["commit"]:
            self.stdout.write(self.style.WARNING("DRY-RUN — nada gravado. Use --commit para submeter."))
            return

        criados = 0
        with transaction.atomic():
            for s in specs:
                obj = (KnownPart.objects.filter(part_number=s.part_number).first()
                       or KnownPart(part_number=s.part_number))
                obj.brand = brand
                for k in _FIELDS:
                    setattr(obj, k, getattr(s, k))
                obj.review_status = "submitted"   # OCULTO até aprovação
                obj.submitted_by = submitter
                obj.save()                         # clean() re-valida/normaliza
                criados += 1
        self.stdout.write(self.style.SUCCESS(
            f"✓ {criados} submetido(s) como 'submitted'. Aprove em /admin/chips/knownpart/ "
            f"(filtro review_status → Submetido)."))
