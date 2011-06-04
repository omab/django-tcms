# -*- coding: utf-8 -*-
from urlparse import urljoin

from django.conf import settings
from django.db.models.fields.files import ImageFieldFile
from django.forms import FileInput, TextInput, CharField, ImageField, \
                         DateField, DateTimeField
from django.utils.safestring import mark_safe
from django.contrib.admin.templatetags.adminmedia import admin_media_prefix
from django.contrib.admin.widgets import ForeignKeyRawIdWidget, \
                                         AdminTextareaWidget, \
                                         AdminTextInputWidget, \
                                         AdminDateWidget, \
                                         AdminSplitDateTime


class PathWidget(ForeignKeyRawIdWidget):
    """Path widget like raw_id on django-admin."""
    def __init__(self, attrs=None):
        from tcms.models import Page
        rel = Page._meta.get_field('path').rel
        super(PathWidget, self).__init__(rel, attrs)

    def render(self, *args, **kwargs):
        return mark_safe(super(PathWidget, self).render(*args, **kwargs)\
                                                .replace('href="../../../',
                                                         'href="/admin/'))


class ImageFileInput(FileInput):
    """File input with direct link to view/download file"""
    def render(self, name, value, attrs=None):
        """Render file input and add preview image and link to file on
        MEDIA_URL path if value is given"""
        out = super(ImageFileInput, self).render(name, value, attrs=attrs)
        if value and isinstance(value, (str, unicode, ImageFieldFile)):
            if isinstance(value, ImageFieldFile):
                file_url = value.url
            else:
                file_url = urljoin(settings.MEDIA_URL, value)
            out += """<a class="file-preview" target="_blank" href="%s">
                   <img height="100" src="%s" /></a>""" % (file_url, file_url)
        return mark_safe(out)


class RelatedWidget(TextInput):
    """Related values widget"""
    def __init__(self, related_link, *args, **kwargs):
        """Related Widget with raw_id behavior. @related_link is url to open"""
        self.related_link = related_link
        super(RelatedWidget, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None):
        """Renders input field and adds a custom related link."""
        attrs = attrs or {}
        if not attrs.has_key('class'):
            attrs['class'] = 'vForeignKeyRawIdAdminField vLargeTextField'
        out = super(RelatedWidget, self).render(name, value, attrs=attrs) + \
        """<a href="%s" class="related-lookup" id="lookup_id_%s"
              onclick="return showRelatedObjectLookupPopup(this);">
           <img src="%simg/admin/selector-search.gif" width="16" height="16"
                alt="Lookup" /></a>""" % \
               (self.related_link, name, admin_media_prefix())
        return mark_safe(out)


class RichEditorWidget(AdminTextareaWidget):
    """Textarea widget with link to enable rich editing"""
    def render(self, name, value, attrs=None):
        """Renders input field and adds a custom related link."""
        attrs = attrs or {}
        attrs['class'] = 'vLargeTextField'
        out = super(RichEditorWidget, self).render(name, value, attrs=attrs) + \
        '<a href="#" class="richedit" id="text_id_%s">Rich editor</a>' % name
        return mark_safe(out)


# Fields
class AdminCharField(CharField):
    """Charfield using Admin text input widget"""
    widget = AdminTextInputWidget


class AdminTexareaField(CharField):
    """Charfield using Admin textarea widget"""
    widget = AdminTextareaWidget


class RichTexareaField(CharField):
    """Charfield with rich-editor support"""
    widget = RichEditorWidget(attrs={'class': 'vLargeTextField richtext'})


class PreviewImageField(ImageField):
    """Imagefile with small preview linked image"""
    widget = ImageFileInput


class AdminDateField(DateField):
    """Date field with admin widget"""
    widget = AdminDateWidget


class AdminDateTimeField(DateTimeField):
    """Date field with admin widget"""
    widget = AdminSplitDateTime
