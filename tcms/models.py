# -*- coding: utf-8 -*-
from urlparse import urljoin
from xml.etree import ElementTree
from operator import or_

from django.db import models, transaction
from django.db.models.query import Q
from django.conf import settings
from django.utils.xmlutils import SimplerXMLGenerator
from django.utils.safestring import mark_safe
from django.utils.importlib import import_module
from django.core.exceptions import ValidationError

from tcms.data_types import BASE_TYPES
from tcms.tpl import PAGES, RENDER_EXTRA_CONTEXT
from tcms.utils import save_b64_image, image_to_b64, update_cache, \
                       normalize_path, dotted_dict_to_choices


# page states
WIP, LIVE, OLD = ('wip', 'live', 'old')
STATES = ((WIP, 'Work in Progress'), (LIVE, 'Live'), (OLD, 'Old page'))

# Load extra data types
EXTRA_TYPES_SETTINGS = getattr(settings, 'EXTRA_TYPES_SETTINGS', None)
if EXTRA_TYPES_SETTINGS:
    try:
        module, name = EXTRA_TYPES_SETTINGS.rsplit('.', 1)
        LOCAL_TYPES = getattr(import_module(module), name, [])
    except (AttributeError, ImportError):
        LOCAL_TYPES = []
else:
    LOCAL_TYPES = []

TYPES_MAP = dict((Type.__name__.lower(), Type)
                    for Type in BASE_TYPES + LOCAL_TYPES)

CMSID = 'cmsid'
IMAGES_UPLOAD_TO = getattr(settings, 'TCMS_IMAGES_UPLOAD_TO',
                           'cms/image/%Y/%m/%d')


class Path(models.Model):
    """A CMS Page path."""
    path = models.CharField(max_length=200)
    locale = models.CharField(max_length=255, blank=True, default='',
                              choices=settings.LANGUAGES)

    def save(self, *args, **kwargs):
        """Save method. Enforces absolute paths."""
        self.path = normalize_path(self.path)
        super(Path, self).save(*args, **kwargs)

    def full_url(self):
        """Returns path full url"""
        return urljoin(settings.SITE_URL, self.path)

    def live(self):
        """Returns current live Page for current instance path and
        locale values."""
        try:
            return self.pages.get(state=LIVE)
        except Page.DoesNotExist:
            pass

    def __unicode__(self):
        return self.path

    def __str__(self):
        return self.path

    class Meta:
        unique_together = ('path', 'locale')
        verbose_name = 'URL'


class Page(models.Model):
    """A CMS Page"""
    path = models.ForeignKey(Path, related_name='pages', verbose_name='URL')
    template = models.CharField(max_length=512,
                                choices=dotted_dict_to_choices(PAGES))
    state = models.CharField(max_length=20, default=WIP, choices=STATES)
    description = models.TextField(blank=True)
    updated = models.DateTimeField(editable=False, auto_now_add=True)

    # metadata
    meta_title = models.CharField(max_length=1024, blank=True, default='',
                                  help_text='Metadata title content')
    meta_description = models.CharField(max_length=1024, blank=True, default='',
                                    help_text='Metadata description content')
    meta_keywords = models.CharField(max_length=1024, blank=True, default='',
                                     help_text='Metadata keywords content')

    # values for search indexers
    search_image = models.ImageField(upload_to=IMAGES_UPLOAD_TO, blank=True,
                                     help_text='Image shown on search results')
    search_text = models.TextField(blank=True, default='',
                           help_text='Description displayed on search results')

    def __init__(self, *args, **kwargs):
        super(Page, self).__init__(*args, **kwargs)
        self._loaded = False
        self._rendered = False
        self._template = None

    @property
    def thumbnail(self):
        """Return @search_image as page thumbnail if it's needed to be included
        it's usually used on sharing sites like facebook"""
        return self.search_image

    def save(self, *args, **kwargs):
        """Save handler, will ensure that only one WIP exists per path"""
        if not self.id:
            Page.validate_unique_wip(self.path)
        super(Page, self).save(*args, **kwargs)

    @classmethod
    def validate_unique_wip(cls, path):
        """Validates WIP state uniqueness for path @path"""
        if Page.objects.filter(path=path, state=WIP).count() > 0:
            raise ValidationError(
                    'Another "Work in progress" page exist for given URL')

    @property
    def preview_url(self):
        return '%s?%s=%s&cms_locale=%s' % (self.path.path, CMSID, self.pk,
                                           self.path.locale)

    @property
    def tpl(self):
        """Returns Template Page instance for current defined template"""
        if self._template is None:
            self._template = PAGES.get(self.template)()
        return self._template

    def load(self, sections=None, rendered=False):
        """
        Load page data.
            If @section is passed, only data for that section is loaded.
            If @rendered flag is passed, only rendered data is loaded
        """
        if not self._loaded:
            if sections:
                if not isinstance(sections, (list, tuple)):
                    sections = (sections,)
                sections = reduce(or_, (Q(name__startswith=section)
                                            for section in sections))

            self._rendered = rendered
            if rendered: # load rendered content
                qs = self.rendered_data.values_list('name', 'value')
                if sections:
                    qs = qs.filter(sections)
                for name, value in qs:
                    setattr(self, name, mark_safe(value))
            else: # load values
                qs = self.values.values_list('name', 'value')
                if sections:
                    qs = qs.filter(sections)
                self.tpl.load(qs)
            self._loaded = True

    @property
    def is_live(self):
        """Return True if page is in Live state or False in other case"""
        return self.state == LIVE

    def refresh(self, *args, **kwargs):
        """Refresh rendered data, subsections are rendered by page template
        sections and stored. Extra arguments will be passed to section
        rendering method.
        """
        extra_context = kwargs.pop('extra_context', {})

        if RENDER_EXTRA_CONTEXT:
            extra_context.update(RENDER_EXTRA_CONTEXT)

        extra_context['cms'] = self
        kwargs['extra_context'] = extra_context

        self.load()
        for name, value in self.tpl.render_sections(*args, **kwargs):
            obj, created = Rendered.objects.get_or_create(page=self, name=name)
            obj.value = value
            obj.save()

    @transaction.commit_on_success
    def publish(self, *args, **kwargs):
        """Publish page, will generate rendered content and unpublish current
        live page with same path and state.

        Arguments will be passed to refresh method which will be passed to
        rendering method.
        """
        similar = {'path': self.path, 'state': LIVE}
        for page in Page.objects.filter(**similar):
            page.unpublish()

        self.refresh(*args, **kwargs)
        self.state = LIVE
        self.save()
        update_cache()

    def unpublish(self):
        """Unpublish page, rendered content is not droped"""
        self.state = OLD
        self.save()
        update_cache()

    @transaction.commit_on_success
    def delete(self):
        """Delete a Page, only no Live pages can be deleted. Rendered content
        and values are deleted too"""
        if self.state == LIVE:
            raise TypeError('live pages cannot be deleted')
        self.rendered_data.all().delete()
        self.values.all().delete()
        super(Page, self).delete()
        update_cache()

    @transaction.commit_on_success
    def copy(self, path):
        """Return copy of this page.

        Copies current page under a new @path. This method behaves like
        cloning if path is the same as current one.
        """
        args = {'path': path,
                'template': self.template,
                'description': self.description,
                'meta_title': self.meta_title,
                'meta_description': self.meta_description,
                'meta_keywords': self.meta_keywords,
                'search_image': self.search_image,
                'search_text': self.search_text}
        copy = Page(**args)
        copy.save()

        # duplicate values
        for value in self.values.all():
            value.id = None
            copy.values.add(value)

        return copy

    def to_xml(self, out, encoding=settings.DEFAULT_CHARSET):
        """Exports page data in a XML formated file. It stores
        page info as first item and value data following it.
        Files are base64 encoded and exported too.

        Example:
        <cms-page>
          <page path="/path/" template="homepage" description="Homepage"
                locale="en-gb" meta_title="Title" meta_description="Description"
                meta_keywords="Keywords" search_image="base64 encoded image"
                search_image_name="file name of search image"
                search_text="Search text"></page>
          <value name="heading" type="text" value="Page title"></value>
          <value name="an_image" type="image" value="bas64 enconded"></value>
          ...
        </cms-page>
        """
        xml = SimplerXMLGenerator(out=out, encoding=encoding)
        xml.startDocument()
        xml.startElement('cms-page', {})

        # store page info in first child
        data = {'path': self.path.path, 'template': self.template,
                'description': self.description, 'locale': self.path.locale,
                'meta_title': self.meta_title,
                'meta_description': self.meta_description,
                'meta_keywords': self.meta_keywords,
                'search_text': self.search_text}
        if self.search_image: # add image content if any
            img = image_to_b64(self.search_image)
            if img is not None:
                name, content = img
                data['search_image_name'] = name
                data['search_image'] = content

        xml.startElement('page', data)
        xml.endElement('page')

        # store values
        values = self.values.values_list('name', 'type', 'value')
        for name, value_type, value in values:
            attrs = {'name': name, 'type': value_type, 'value': value}

            if value_type in TYPES_MAP:
                attrs.update(TYPES_MAP[value_type]().to_xml(value))
            xml.startElement('value', attrs)
            xml.endElement('value')

        xml.endElement('cms-page')
        xml.endDocument()
        return out

    @classmethod
    def valid_xml(cls, source):
        """Validatos source as a valid XML exported page"""
        # check XML structure
        try:
            etree = ElementTree.fromstring(source)
        except Exception, e:
            raise ValidationError('Malformed XML or not an XML document "%s"' \
                                        % str(e))

        # check page information (it's stored in first subnode)
        page_info = etree[0].attrib

        # check template
        tpl = page_info.get('template')
        if not tpl or tpl not in PAGES:
            raise ValidationError('Malformed XML: wrong template %s' % tpl)

        # check path
        path = page_info.get('path')
        if not path:
            raise ValidationError('Malformed XML: missing path')

        # check path/locale pair, if it does't exists importing
        # is safe because will be created, if it exists, the page
        # state needs to be checked because only one WIP page per
        # path is allowed
        locale = page_info.get('locale', '')
        try:
            path = Path.objects.get(path=path, locale=locale)
        except Path.DoesNotExist:
            pass
        else:
            Page.validate_unique_wip(path)

    @classmethod
    def from_xml(cls, source):
        """Import a page information. @source must be an XML exported
        valid page.
        """
        # page *must* be validated first
        etree = ElementTree.fromstring(source) # parse XML

        page_info = etree[0].attrib # page info in first child

        path = page_info.get('path')
        locale = page_info.get('locale', '')
        path, created = Path.objects.get_or_create(path=path, locale=locale)

        # save page data, image is saved later if any
        data = {'meta_title': page_info.get('meta_title', ''),
                'meta_description': page_info.get('meta_description', ''),
                'meta_keywords': page_info.get('meta_keywords', ''),
                'search_text': page_info.get('search_text', ''),
                'description': page_info.get('description', ''),
                'template': page_info.get('template'), 'path': path}
        page = Page(**data)
        page.save()

        # save search image if any
        save_b64_image(page_info.get('search_image'),
                       page_info.get('search_image_name'),
                       page.search_image, save=True)

        # values are from second child to end
        for node in etree[1:]:
            attr = node.attrib
            name, value_type, value = attr['name'], attr['type'], attr['value']
            if value_type in TYPES_MAP:
                value = TYPES_MAP[value_type]().from_xml(attr)
            page.values.add(Value(name=name, value=value, type=value_type))
        return page

    def __getitem__(self, name):
        """Get item handler, once page data is loaded is possible to
        access page section using [] notation.
        """
        if self._loaded and self._rendered and hasattr(self, name):
            # return rendered content if available
            return mark_safe(getattr(self, name, '').strip())
        return self.tpl[name] # return page section

    def __unicode__(self):
        return unicode(self.path)

    def __str__(self):
        return str(self.path)


class Value(models.Model):
    """CMS Page value
    @page  is page the value belongs too
    @name  is used to generate values namspaces. First token denotes section
           that value belongs too, second name denotes section fragment and
           follow up names describe grouping and list position. Last token is
           value name
    @value is store database value
    @type  is data type name
    """
    page = models.ForeignKey(Page, related_name='values')
    name = models.CharField(max_length=255)
    value = models.TextField(blank=True)
    type = models.CharField(max_length=32, choices=((name, Type.description)
                                    for name, Type in TYPES_MAP.iteritems()))

    def __unicode__(self):
        return u'%s (%s)' % (self.name, self.value[:20])

    class Meta:
        unique_together = ('page', 'name')


class Rendered(models.Model):
    """CMS Page rendered content for rapid page loading"""
    page = models.ForeignKey(Page, related_name='rendered_data')
    name = models.CharField(max_length=64, blank=False)
    value = models.TextField()

    class Meta:
        unique_together = ('page', 'name')
