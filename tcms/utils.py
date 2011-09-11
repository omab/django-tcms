# -*- coding: utf-8 -*-
import re
import base64
from os.path import split
from cStringIO import StringIO

from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models.fields.files import ImageFieldFile
from django.utils.datastructures import DotExpandedDict


CACHE_NAME = getattr(settings, 'TCMS_CACHE_NAME', 'tcms')

# Capital letters regex
CAPLETTERS = re.compile('([A-Z])')

def human_title(value):
    """Converts camel-case word to human readeable format."""
    return ' '.join(word.title()
                        for word in CAPLETTERS.sub(r' \1', value)\
                                              .replace('_', ' ')\
                                              .split())


def update_cache():
    """Updates CMS pages cache, cache structure is a dictioray which key
    is a tuple of page path, locale and state, and valud is page id."""
    from tcms.models import Page, WIP, LIVE

    pages = Page.objects.filter(state__in=[WIP, LIVE]).select_related('path')

    if getattr(settings, 'TCMS_LOCALIZED', False):
        values = dict(((page.path.path, page.path.locale, page.state), page.id)
                            for page in pages)
    else:
        values = dict(((page.path.path, page.state), page.id)
                            for page in pages)
    cache.set(CACHE_NAME, values)
    return values


def locale_tags(locale):
    """ Splits a locale/language tag into a subtags sequence
    >>> locale_tags('en')
    ('en', '')
    >>> locale_tags('en-gb')
    ('en-gb', 'en', '')
    >>> locale_tags('')
    ('',)
    """
    if not locale:
        return ('',)
    return (locale,) + locale_tags(locale.rpartition('-')[0])


def id_from_cache(paths, locale=None):
    """Load page id from cache if present. Will try locale and sub locales
    withing LIVE and WIP states."""
    from tcms.models import WIP, LIVE

    values = cache.get(CACHE_NAME)
    if values is None: # load cache if not entry
        values = update_cache()

    if not isinstance(paths, (list, tuple)):
        paths = [paths]

    locales = locale_tags(locale)
    for path in paths: # test each path for possible locales
        path = normalize_path(path)
        if getattr(settings, 'TCMS_LOCALIZED', False):
            for loc in locales:
                if (path, loc, LIVE) in values:
                    return values[(path, loc, LIVE)]
                elif (path, loc, WIP) in values:
                    return values[(path, loc, WIP)]
        else:
            if (path, LIVE) in values:
                return values[(path, LIVE)]
            elif (path, WIP) in values:
                return values[(path, WIP)]


def save_b64_image(value, name, model_field, save=False):
    """
    Saves an base64 encoded string as a file using @model_field
    (which must be an django.db.models.fields.files.ImageFieldFile
    instance) save method. @name is file name to save to, but might
    gain suffixes on coincidence. Model instance will be saved by
    django if @save flag is True. Returns saved file name or none
    if @value and @name are not valid.
    """
    if value and name and isinstance(model_field, ImageFieldFile):
        value = base64.decodestring(value)
        sio = StringIO()
        sio.write(value)
        sio.seek(0)
        data = InMemoryUploadedFile(file=sio, name=name, field_name=None,
                                    content_type=None, size=len(value),
                                    charset=None)
        model_field.save(name, data, save=save)
        return model_field.name


def image_to_b64(model_field):
    """Encodes image value in base64 encoding. Returns tuple with
    file name and encoded content, None in case of error.
    @model_field must be an django.db.models.fields.files.ImageFieldFile
    instance.
    """
    if isinstance(model_field, ImageFieldFile):
        try:
            return (split(model_field.name)[-1],
                    base64.encodestring(model_field.read(model_field.size)))
        except: # ignore exceptions
            pass


def normalize_path(path):
    """Normalize a path to be used on CMS. Basically, appends a trailing slahs"""
    path = path.strip('/')
    path = ('/' + path + '/') if path else '/'
    return path


def dotted_dict_to_choices(dict_, sort=True):
    """Coverts a dotted dictionary (see DotExpandedDict class for details)
    to a recursive choices format which will be used to form <optgroup> tags
    when used with django fields using choices attribute."""
    def _flat(name, values, first=False):
        """Flatten structure, recursive."""
        if isinstance(values, dict):
            choices = [_flat(name + '.' + k, v) for k, v in values.iteritems()]
        elif not first:
            return (name, values.NAME)
        else:
            choices = [(name, values.NAME)]
        if sort:
            choices.sort(key=lambda x: x[0])
        return (name.title(), choices)

    choices = [_flat(k, v, True)
                    for k, v in DotExpandedDict(dict_).iteritems()]
    if sort:
        choices.sort(key=lambda (x, y): x if isinstance(y, list) else y)
    return choices
