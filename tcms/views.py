# -*- coding: utf-8 -*-
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, \
                        HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render_to_response
from django.utils import simplejson, html
from django.utils.encoding import force_unicode
from django.template.context import RequestContext
from django.template.defaultfilters import slugify
from django.contrib import messages
from django.contrib.admin.models import LogEntry, CHANGE, ADDITION, DELETION
from django.contrib.admin.views.main import IS_POPUP_VAR, SEARCH_VAR
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.decorators import user_passes_test

from tcms.models import Page, TYPES_MAP
from tcms.data_types import RawIdType
from tcms.forms import PageForm, CopyPageForm, ImportForm
from tcms.utils import update_cache
from tcms.exceptions import TemplateFormValidationError


class TextareaAjaxResponse(HttpResponse):
    """Response that wraps content in <textarea></textarea> for usage with
    jquery.forms.js plugin.
    """
    def __init__(self, data='', *args, **kwargs):
        super(TextareaAjaxResponse, self).__init__(*args, **kwargs)
        content = simplejson.dumps(data)
        self.content = '<textarea>%s</textarea>' % html.escape(content)


def permission_required(*perms):
    """Permissions checking decorator"""
    return user_passes_test(lambda u: u.has_perms(perms))


@permission_required('change_page')
def edit(request, page_id):
    """Page edition view"""
    page = get_object_or_404(Page, pk=page_id)
    page.load()

    if request.method == 'POST':
        form = PageForm(instance=page, data=request.POST, files=request.FILES)
        if form.is_valid():
            form.save()
            log(request, page, CHANGE, 'Page edited')
            messages.info(request, 'Page saved correctly')
            return HttpResponseRedirect(_edit_url(page_id))
    else:
        form = PageForm(instance=page)
    state = page.get_state_display()
    return _render('cms/edit.html', locals(), request)



@permission_required('add_value', 'change_value')
def edit_section(request, page_id, section):
    """Page section edition view"""
    page = get_object_or_404(Page, pk=page_id)

    if request.method == 'POST':
        basename = request.POST.get('basename')
        if not basename:
            raise AttributeError('Invalid basename')

        try:
            page.tpl.save(page, basename, data=request.POST,
                          files=request.FILES)
        except TemplateFormValidationError, e:
            if request.POST.get('is_ajax'):
                errors = [{'field': name, 'messages': list(errors)}
                                    for name, errors in e.errors.iteritems()]
                return TextareaAjaxResponse({'status': 'error',
                                             'errors': errors})
        else:
            log(request, page, CHANGE, 'Content for section %s updated (%s)' % \
                                                (section, basename))
            messages.info(request, 'Section data saved correctly')
            if request.POST.get('is_ajax'):
                return TextareaAjaxResponse({'status': 'ok'})
            else:
                url = _edit_section_url(page_id, section)
                url_hash = basename.replace('/', '-')
                return HttpResponseRedirect(url + '#' + url_hash)
    page.load(section)
    section_name = section  # used in template
    section = page.tpl[section_name]
    state = page.get_state_display()
    TCMS_CKEDITOR_BASE_URL = getattr(settings, 'TCMS_CKEDITOR_BASE_URL', '')
    if TCMS_CKEDITOR_BASE_URL and not TCMS_CKEDITOR_BASE_URL.endswith('/'):
        TCMS_CKEDITOR_BASE_URL += '/'
    return _render('cms/edit_section.html', locals(), request)


@permission_required('delete_value')
def clear(request, page_id, section):
    """Page section data clear. Clears some section values set."""
    if request.method == 'POST':
        page = get_object_or_404(Page, pk=page_id)
        basename = request.POST['basename']
        page.values.filter(name__startswith=basename).delete()
        log(request, page, CHANGE, 'Content for section %s cleared' % section)
        messages.info(request, 'Content for section %s cleared' % section)
    return HttpResponseRedirect(_edit_section_url(page_id, section))


def rawid(request):
    """Display a list to pick a raw id for an object of @type type, like
    django admin raw id feature"""
    Type = TYPES_MAP.get(request.GET.get('type'))
    if not issubclass(Type, RawIdType):
        return HttpResponseBadRequest('Wrong type "%s"' % Type)
    ctx = Type.rawid_context(request)
    ctx['type'] = Type.name()
    ctx['IS_POPUP_VAR'] = IS_POPUP_VAR
    ctx['is_popup'] = request.GET.get(IS_POPUP_VAR, False)
    ctx[SEARCH_VAR] = request.GET.get(SEARCH_VAR, '')
    return _render('cms/rawid.html', ctx, request)


@permission_required('add_page', 'add_path')
def copy(request, page_id):
    """Page copy view. Copies a page under a different URL/Locale"""
    page = get_object_or_404(Page, pk=page_id)

    if request.method == 'POST':
        form = CopyPageForm(request.POST)
        if form.is_valid(): # save page and duplicate values
            dup = form.save(page)
            log(request, page, ADDITION, 'Page copied to object %s (%s)' % \
                                                (dup.id, dup.path.path))
            log(request, dup, ADDITION, 'Page copied from %s (%s)' % \
                                                (page.id, page.path.path))
            messages.info(request, 'Page copied correctly')
            return HttpResponseRedirect(_edit_url(dup.id))
    else:
        form = CopyPageForm()
    return _render('cms/copy.html', locals(), request)


@permission_required('change_page', 'add_rendered', 'change_rendered')
def publish(request, page_id):
    """Page publishing view"""
    page = get_object_or_404(Page, pk=page_id)
    page.publish()
    update_cache()
    log(request, page, CHANGE, 'Page published')
    messages.info(request, 'Page %s published' % page)
    return HttpResponseRedirect(request.GET.get('next') or _edit_url(page_id))


@permission_required('change_page')
def unpublish(request, page_id):
    """Page unpublishing view"""
    page = get_object_or_404(Page, pk=page_id)
    page.unpublish()
    update_cache()
    log(request, page, CHANGE, 'Page unpublished')
    messages.info(request, 'Page %s unpublished' % page)
    return HttpResponseRedirect(request.GET.get('next') or _edit_url(page_id))


@permission_required('add_rendered', 'change_rendered')
def refresh(request, page_id):
    """Page rendered data refreshing view"""
    page = get_object_or_404(Page, pk=page_id)
    page.refresh()
    log(request, page, CHANGE, 'Content refreshed')
    messages.info(request, 'Content for page %s refreshed' % page)
    return HttpResponseRedirect(request.GET.get('next') or _edit_url(page_id))


@permission_required('delete_page', 'delete_value', 'delete_rendered')
def delete(request, page_id):
    """Page deletion view"""
    page = get_object_or_404(Page, pk=page_id)
    try:
        page.delete()
    except TypeError, e:
        messages.info(request, e.message)
        return HttpResponseRedirect(_edit_url(page_id))
    else:
        update_cache()
        log(request, page, DELETION, 'Page deleted')
        messages.info(request, 'Page %s deleted' % page)
        return HttpResponseRedirect(reverse('admin:tcms_page_changelist'))


def export(request, page_id):
    """Page exporting view"""
    page = get_object_or_404(Page.objects.select_related('path'), pk=page_id)
    response = HttpResponse(mimetype='application/x-download')
    page.to_xml(response)
    # homepage path is sluged as '', then we renamed it as 'homepage'
    name = slugify(page.path.path).replace('-', '_') or 'homepage'
    response['Content-Disposition'] = 'attachment; filename=%s.xml' % name
    log(request, page, CHANGE, 'Page exported')
    return response


@permission_required('add_path', 'add_page', 'add_value')
def import_page(request):
    """Page importing view"""
    if request.method == 'POST':
        form = ImportForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            try:
                page = form.save()
            except Exception, e:
                messages.info(request, 'Impossible to import: %s' % e)
            else:
                update_cache()
                log(request, page, ADDITION, 'Page imported')
                messages.info(request, 'Page %s imported' % page)
                return HttpResponseRedirect(_edit_url(page.id))
    else:
        form = ImportForm()
    return _render('cms/import.html', {'form': form}, request)


def log(request, obj, level, message=''):
    """Log events for user notification"""
    ct = ContentType.objects.get_for_model(obj.__class__).pk
    try:
        object_repr = force_unicode(obj)
    except:
        object_repr = ''
    LogEntry.objects.log_action(user_id=request.user.id, content_type_id=ct,
                                object_id=obj.pk, object_repr=object_repr,
                                action_flag=level, change_message=message)


def render_to_template(request, context=None):
    """Renders a page directly to it's default template defined, raises
    404 if current request is not a valid CMS page or if the related
    template doesn't define a template for it."""
    ctx = RequestContext(request)
    page = ctx.get('cms')
    if page is None or page.tpl.TEMPLATE is None:
        raise Http404('Not found')
    return render_to_response(page.tpl.TEMPLATE, context or {}, ctx)


def _edit_url(page_id):
    """Return edition url for @page_id"""
    return reverse('admin:cms_edit', args=(page_id,))

def _edit_section_url(page_id, section):
    """Return section edition url for @page_id/@section"""
    return _edit_url(page_id) + '%s/' % section

def _render(tpl, ctx, req):
    """Renders to response loading request context"""
    return render_to_response(tpl, ctx, RequestContext(req))
