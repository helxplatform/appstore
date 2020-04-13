from django.conf import settings
from django.apps import AppConfig


class PhenotypeConfig(AppConfig):
    name = 'phenotype'
    verbose_name = "Analyze Phenotype"
    url = settings.PHENOTYPE_REDIRECT_URL
    logo = 'img/carousel-monarch.png'
