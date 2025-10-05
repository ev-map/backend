import os

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template import loader


@login_required
def playground(request):
    template = loader.get_template("playground.html")
    return HttpResponse(template.render({}, request))
