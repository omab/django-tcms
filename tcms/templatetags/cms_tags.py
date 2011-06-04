# -*- coding: utf-8 -*-
from operator import add

from django.template import Library

from tcms.models import Path, WIP, LIVE


register = Library()


@register.inclusion_tag('cms/template_filter.html')
def admin_template_filter(cl, spec):
    return {'title': spec.title(),
            'choices' : list(spec.choices(cl))}


@register.filter
def similar_pages(page):
    if page:
        return reduce(add, (list(path.pages.filter(state__in=(WIP, LIVE)))
                             for path in Path.objects.filter(path=page.path.path)))
    else:
        return []
