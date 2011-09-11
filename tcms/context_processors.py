# -*- coding: utf-8 -*-
from django.conf import settings

from tcms.models import Page, CMSID
from tcms.utils import id_from_cache


def cms(request):
    """
    Loads needed context data to render a CMS page.

    Raw values will be used if running in an instance with admin option
    enabled, if not, rendered content will be used instead.

    The processor looks for a cmsid GET parameter, if preset will load the
    page with that id.

    This function uses a cache to speed up page id retrieving and avoid
    unnecesary database hits. Will fallback to tipocms app if there's no
    id for url/locate pair.

    Request object might have a @cms_url attribute which will be used as an
    override for current request path when looking for pages. If it's a list,
    then each path is tested until the first match and finally current path
    is tested.

    If request.no_cms is True then everything is skipped and no CMS data is
    loaded.
    """
    if getattr(request, 'no_cms', False):
        return {}

    is_admin = 'django.contrib.admin' in settings.INSTALLED_APPS

    if is_admin and request.GET.get(CMSID):
        cmsid = request.GET.get(CMSID)
    else:
        paths = getattr(request, 'cms_url', None)
        # use path override if preset, it can be a list defining several
        # possible paths that can be used with current page
        if not paths:
            paths = [request.path]
        elif not isinstance(paths, list):
            paths = [paths]
        if request.path not in paths:
            paths.insert(0, request.path)

        cmsid = id_from_cache(paths, getattr(request, 'LANGUAGE_CODE', None))

    ctx = {'cms': None}
    if cmsid is not None:
        try:
            ctx['cms'] = Page.objects.select_related('path').get(pk=cmsid)
        except Page.DoesNotExist: # shouldn't happen
            pass
        else:
            ctx['cms'].load(rendered=not is_admin)
    return ctx
