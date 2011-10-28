# -*- coding: utf-8 -*-
"""
Page template data types definitions. Here are defined custom data types
with it's corresponding behavior to interact with the CMS. Project models
can be added and will work in a raw_id way.
"""
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models
from django.forms import ChoiceField, BooleanField
from django.utils.safestring import mark_safe
from django.db.models.loading import get_model

from tcms.utils import save_b64_image, image_to_b64
from tcms.fields import RelatedWidget, AdminCharField, PreviewImageField, \
                        RichTexareaField, AdminDateField, AdminDateTimeField


__all__ = ['BaseType', 'PlainType', 'RawIdType', 'Text', 'BigText', 'Option',
           'Flag', 'Image', 'Date', 'DateTime', 'BASE_TYPES']

IMAGES_UPLOAD_TO = getattr(settings, 'TCMS_IMAGES_UPLOAD_TO', 'cms/image/%Y/%m/%d')


class BaseType(object):
    """Base type, types should extend this class"""
    description = '' # type description
    field = AdminCharField # form field, an AdminCharField by default

    def as_field(self, *args, **kwargs):
        """Return field for current type, an AdminCharField by default."""
        return self.field(*args, **kwargs)

    def to_database(self, form, name):
        """Prepare data in form to be saved into database. Override in
        subclass
        """
        raise NotImplementedError, 'implement in subclass'

    def form_value(self, value):
        """Return treated value for usage in form"""
        return self.value(value)

    def value(self, value):
        """Return value to be shown.
            * return value marked safe if it's an string.
            * return passed value in other cases
        """
        if isinstance(value, (str, unicode)):
            value = mark_safe(value)
        return value

    def to_xml(self, value):
        """Return value to be included in a XML file. Must return a dict
        with data to be include. Return value by default.
        """
        return {'value': value}

    def from_xml(self, data):
        """Return value that was stored in a XML file. @data should be
        a dictionary with same format as returned by to_xml method.
        """
        if isinstance(data, dict):
            return data.get('value')

    @classmethod
    def name(cls):
        """Return type name, works as an instance or class method"""
        try:
            if issubclass(cls, BaseType):
                return cls.__name__.lower()
        except TypeError:
            return cls.__class__.__name__.lower()

    @classmethod
    def __str__(cls):
        return cls.description


class PlainType(BaseType):
    """Plain text data type."""
    def to_database(self, form, name):
        """Prepares value to database storage, raises ValueError if value is
        missing"""
        if name not in form.cleaned_data:
            raise ValueError, 'missing value'
        return form.cleaned_data[name]


class RawIdType(PlainType):
    """Raw Id type, allows related definition to proyect models entries"""
    # model or url must be defined or AttributeError will raised in that case
    model = None  # model related too
    url = None    # url override in case url cannot be built from model like
                  # wsmodels/Product
    model_key = 'pk'  # Custom model primary key field
    select_related = None  # Select related option, it *must* be a list

    def __init__(self, *args, **kwargs):
        self.model = kwargs.pop('model', self.model)
        self.url = kwargs.pop('url', self.url)
        self.model_key = kwargs.pop('model_key', self.model_key)
        self.select_related = kwargs.pop('select_related', self.select_related)
        super(RawIdType, self).__init__(*args, **kwargs)

    def get_model(self):
        """Return model, imports it the first time if attribute is a string."""
        if isinstance(self.model, basestring):
            app_label, name = self.model.split('.', 1)
            self.model = get_model(app_label, name)
        return self.model

    def as_field(self, *args, **kwargs):
        """Prepares form field, uses custom url if preset or tries to build from
        model class. Raises AttributeError if none of this fields are defined"""
        if self.url:  # try url
            url = self.url
        elif self.model:  # try building using model options
            model = self.get_model()
            opt = model._meta
            url = reverse('admin:%s_%s_changelist' % (opt.app_label,
                                                      opt.module_name))
        else:
            raise AttributeError, 'model or url must be defined'
        return self.field(widget=RelatedWidget(url), *args, **kwargs)

    def form_value(self, value):
        """Return raw value to be used in form"""
        return value

    def value(self, value):
        """Returns model instance from value, value will be iterpreted as
        a model id. Returns none if object does not exist."""
        model = self.get_model()
        qs = model.objects.get_query_set()
        if self.select_related:
            qs = qs.select_related(*self.select_related)
        try:
            return qs.get({self.model_key: value})
        except model.DoesNotExist:
            return None

    def rawid_context(self, request):
        """Custom rawid index. If a custom rawid list is needed
        (like wsmodels/Product case), this method will be invoked requesting
        context values to be displayed by cms/rawid.html template.
        """
        raise NotImplementedError, 'implement in subclass'


class Text(PlainType):
    """Simple text type"""
    description = 'Text (one line)'


class BigText(PlainType):
    """Rich text type"""
    description = 'Large text (multiple lines)'
    field = RichTexareaField


class Option(PlainType):
    """Defined options data type"""
    description = 'Options (combo select)'
    field = ChoiceField

    def __init__(self, choices):
        """Init method.
        @choices is a list of pairs that will be used when creating
        form field and validate on saving.
        """
        self.choices = choices

    def as_field(self, *args, **kwargs):
        """Prepares form field, uses choices"""
        kwargs.pop('choices', None) # remove any possible choices
        return self.field(choices=self.choices, *args, **kwargs)

    def to_database(self, form, name):
        """Prepares value to database storage, raises ValueError if value is
        missing"""
        value = super(Option, self).to_database(form, name)
        if value not in dict(self.choices):
            raise ValueError, '"%s" is not a valid choice' % value
        return value


class Flag(PlainType):
    """True/False data type"""
    description = 'On/Off flag'
    field = BooleanField

    def value(self, value):
        """Interprets value using django BooleanField way, this will
        parse t, True or 1 as True values and f, False, 0 as False ones."""
        return models.BooleanField().to_python(value)


class Image(PlainType):
    """Image data type"""
    description = 'Image'
    field = PreviewImageField # use custom field

    def to_database(self, form, name):
        """"Saves image data to filesystem and returns file generated name
        to be stored in database"""
        if name not in form.files: # no file uploaded
            raise ValueError, 'missing value'
        data = form.files[name]
        obj = self._model() # hackish way to save file
        obj.value.save(data.name, data, save=False) # use field value to save
        return obj.value.name

    def _model(self, value=None):
        """Returns a django model instance with a value field of ImageField type,
        handy to save or read image file. @value will be loaded as image value."""
        class _Model(models.Model):
            value = models.ImageField(upload_to=IMAGES_UPLOAD_TO, blank=True)
        return _Model(value=value)

    def to_xml(self, value):
        """Convert image data to be stored in a XML file, the image is enconded
        in base64. Image name and enconded value are returned."""
        img = image_to_b64(self._model(value).value)
        if img is not None:
            name, value = img
            return {'file_name': name, 'value': value}
        else:
            return {'value': value}

    def from_xml(self, data):
        """Reads image stored in a XML file, value must be an base64 enconded
        image and name must be present."""
        if 'value' in data and 'file_name' in data:
            return save_b64_image(data['value'], data['file_name'],
                                  self._model().value)

    def value(self, value):
        """Return image value as a model would return it"""
        img = self._model(value or None).value
        if img.name:
            return img


class Date(PlainType):
    """Date data type"""
    description = 'Date'
    field = AdminDateField

    def value(self, value):
        """Return date instance"""
        return models.DateField().to_python(value)


class DateTime(PlainType):
    """Datetime data type"""
    description = 'DateTime'
    field = AdminDateTimeField

    def value(self, value):
        """Return date instance"""
        return models.DateTimeField().to_python(value)


# Base types definition
BASE_TYPES = [Text, BigText, Image, Option, Flag, Date, DateTime]

## Define your project related types here, example:
#
# from django.contrib.auth.models import User
# 
# from tcms.data_types import RawIdType
# 
# __all__ = ['User', 'LOCAL_TYPES']
# 
# 
# class User(RawIdType):
#     """Django auth user data type"""
#     description = 'Django Auth User'
#     model = User
# 
# # Types definition
# LOCAL_TYPES = [User]
