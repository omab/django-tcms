from os.path import join, dirname

from django.contrib import admin
from django.conf.urls.defaults import patterns, include, url
from django.views.generic.simple import direct_to_template


admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', direct_to_template, {'template': 'testpage.html'}),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^media/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root':  join(dirname(__file__), 'media')},
        name='media'),
    url(r'^cms-media/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root':  join(dirname(__file__), 'tcms/media')},
        name='cms_media'),
)
