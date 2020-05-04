from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect


@login_required()
def phenotype_analyze(request):
    return HttpResponseRedirect(settings.PHENOTYPE_REDIRECT_URL)
