# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.conf.urls.defaults import url, patterns
from django.contrib.admin.filterspecs import ChoicesFilterSpec, RelatedFilterSpec
from django.utils.encoding import smart_unicode
from django.views.generic.simple import redirect_to

from tcms import views
from tcms.models import Path, Page, Value
from tcms.utils import update_cache


class ValueOptions(admin.ModelAdmin):
    list_display = ('id', 'page', 'name', 'type')
    search_fields = ('name', 'value')
    list_filter = ('type',)
    raw_id_fields = ('page',)


class PathOptions(admin.ModelAdmin):
    list_display = ('id', 'path') + (('locale',) if settings.TCMS_LOCALIZED else ())
    search_fields = ('path',)
    list_filter = ('locale',) if settings.TCMS_LOCALIZED else ()
    exclude = ('locale',) if not settings.TCMS_LOCALIZED else ()


class LocaleFilterSpec(RelatedFilterSpec):
    """Path locale filter spec"""
    def __init__(self, req, admin):
        model = admin.model
        field = model._meta.get_field('path')
        super(LocaleFilterSpec, self).__init__(field, req, {}, model, admin)
        self.lookup_kwarg = '%s__locale' % field.name
        self.lookup_val = req.GET.get(self.lookup_kwarg, None)
        self.lookup_choices = settings.LANGUAGES
        self.title = lambda: 'locale'


class TemplateFilterSpec(ChoicesFilterSpec):
    """Template filter spec with full name"""
    def __init__(self, req, admin):
        model = admin.model
        field = model._meta.get_field('template')
        super(TemplateFilterSpec, self).__init__(field, req, {}, model, admin)

    def choices(self, cl):
        lv, lk = self.lookup_val, self.lookup_kwarg
        out = [('all', [{'selected': lv is None,
                         'query_string': cl.get_query_string({}, [lk]),
                         'display': 'All'}])]

        for group, choices in self.field.choices:
            out.append((group, [{'selected': smart_unicode(key) == lv,
                                 'query_string': cl.get_query_string({lk: key}),
                                 'display': value} for key, value in choices]))
        return out


class PageOptions(admin.ModelAdmin):
    list_display = ('id', 'path', 'state', 'short_updated', 'page_actions') + \
                        (('locale',) if settings.TCMS_LOCALIZED else ())
    list_filter = ('state', 'updated')
    search_fields = ('description', 'path__path')
    list_display_links = ()
    fieldsets = (
            ('Page information', {'fields': ('path', 'description', 'template')}),
            ('Metadata', {
                'fields': ('meta_title', 'meta_description', 'meta_keywords'),
                'classes': ('collapse',),
                'description': '<h4>This data will be used in page meta data</h4>'}),
            ('Search', {
                'fields': ('search_image', 'search_text'),
                'classes': ('collapse',),
                'description': '<h4>This data will be displayed on search results</h4>'})
    )
    raw_id_fields = ('path',)
    date_hierarchy = 'updated'
    list_select_related = True
    actions = None
    change_list_template = 'cms/page_change_list.html'
    object_history_template = 'cms/page_history.html'
    ordering = ('-id', 'path__path', 'state')

    def lookup_allowed(self, key, value):
        """Validate lookup rule, check if path is given and allow it"""
        return key.startswith('path') or \
               super(PageOptions, self).lookup_allowed(key, value)

    def changelist_view(self, request, extra_context=None):
        ctx = {'locale_filter': LocaleFilterSpec(request, self) if settings.TCMS_LOCALIZED else None,
               'template_filter': TemplateFilterSpec(request, self)}
        if extra_context:
            ctx.update(extra_context)
        return super(PageOptions, self).changelist_view(request, ctx)

    def response_add(self, request, obj, post_url_continue='../%s/'):
        response = super(PageOptions, self).\
                        response_add(request, obj, post_url_continue)
        keys = ('_continue', '_popup', '_addanother')
        update_cache()
        if any(k in request.POST for k in keys):
            return response
        else:
            return HttpResponseRedirect('../p/%s/' % obj.id)

    def locale(self, obj):
        return obj.path.get_locale_display()

    def short_updated(self, obj):
        return obj.updated.strftime('%d/%m/%Y %H:%M')
    short_updated.short_description = 'updated'

    def page_actions(self, obj):
        links = [
            '<a title="Edit" href="p/%(id)s/"><img src="%(media)s/edit.png" alt="Edit" /></a>',
            '<a title="Copy" href="p/%(id)s/copy/"><img src="%(media)s/copy.png" alt="Copy" /></a>',
            '<a title="Export" href="p/%(id)s/export/"><img src="%(media)s/package.png" alt="Export" /></a>',
            '<a title="Preview" target="_blank" href="%(preview)s"><img src="%(media)s/preview.png" alt="Preview" /></a>']
        if obj.is_live:
            links += [
                '<a title="Refresh" href="p/%(id)s/refresh/?next=%(next)s"><img src="%(media)s/refresh.png" alt="Refresh" /></a>',
                '<a title="Unpublish" href="p/%(id)s/unpublish/?next=%(next)s"><img src="%(media)s/unpublish.png" alt="Unpublish" /></a>',
                '<img src="%(media)s/delete_disabled.png" title="Delete" alt="Delete" />']
        else:
            links += [
                '<img title="Refresh" src="%(media)s/refresh_disabled.png" alt="Refresh" />',
                '<a title="Publish" href="p/%(id)s/publish/?next=%(next)s"><img src="%(media)s/publish.png" alt="Publish" /></a>',
                '<a title="Delete" href="p/%(id)s/delete/" class="warning"><img src="%(media)s/delete.png" alt="Delete" /></a>']
        links.append('<a title="History" href="%(id)s/history/"><img src="%(media)s/log.png" alt="History" /></a>')
        return ' '.join(links) % {'id': obj.id,
                                  'media': '/cms-media/img',
                                  'preview': obj.preview_url,
                                  'next': reverse('admin:tcms_page_changelist')}
    page_actions.allow_tags = True
    page_actions.short_description = 'Actions'

    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^rawid/$', views.rawid),
            url(r'^import/$', views.import_page),
            url(r'^(?P<page_id>\d+)/$', redirect_to, kwargs={'url': '../p/%(page_id)s/'}),
            url(r'^p/(?P<page_id>\d+)/$', views.edit, name='cms_edit'),
            url(r'^p/(?P<page_id>\d+)/copy/$', views.copy),
            url(r'^p/(?P<page_id>\d+)/publish/$', views.publish),
            url(r'^p/(?P<page_id>\d+)/unpublish/$', views.unpublish),
            url(r'^p/(?P<page_id>\d+)/refresh/$', views.refresh),
            url(r'^p/(?P<page_id>\d+)/delete/$', views.delete),
            url(r'^p/(?P<page_id>\d+)/export/$', views.export),
            url(r'^p/(?P<page_id>\d+)/(?P<section>[^/]+)/$', views.edit_section),
            url(r'^p/(?P<page_id>\d+)/(?P<section>[^/]+)/clear/$', views.clear),
        )
        return urlpatterns + super(PageOptions, self).get_urls()


admin.site.register(Path, PathOptions)
admin.site.register(Page, PageOptions)
admin.site.register(Value, ValueOptions)
