# -*- coding: utf-8 -*-
from django import forms
from django.contrib.admin.widgets import AdminFileWidget

from tcms.models import Page, Path, Value, WIP
from tcms.tpl import mkbasename
from tcms.fields import PathWidget, AdminTexareaField, AdminCharField


class PageForm(forms.ModelForm):
    """Edit page form"""
    path = forms.CharField(label='URL', widget=PathWidget())
    description = AdminTexareaField(required=False)
    search_image = forms.ImageField(label='Image', widget=AdminFileWidget, required=False)
    search_text = AdminTexareaField(label='Text', required=False)
    meta_title = AdminCharField(label='Title', required=False)
    meta_keywords = AdminCharField(label='Keywords', required=False)
    meta_description = AdminTexareaField(label='Description', required=False)

    def clean_path(self):
        """Path cleaning"""
        return _clean_path(self)

    def page_fields(self):
        """Returns page concerning fields, handly for template"""
        for field in self:
            name = field.html_name
            if not (name.startswith('meta_') or name.startswith('search_')):
                yield field

    def metadata_fields(self):
        """Returns page metadata fields, handly for template"""
        for field in self:
            if field.html_name.startswith('meta_'):
                yield field

    def search_fields(self):
        """Returns page search fields, handly for template"""
        for field in self:
            if field.html_name.startswith('search_'):
                yield field

    class Meta:
        model = Page
        exclude = ('template', 'state', 'updated')


class CopyPageForm(forms.ModelForm):
    """Copy page form"""
    path = forms.CharField(label='URL', widget=PathWidget())

    def clean_path(self):
        """Path cleaning"""
        path = _clean_path(self)
        # validate that there's no another WIP page with same path
        if path.pages.filter(state=WIP).count() > 0:
            raise forms.ValidationError(
                    'Another "Work in progress" page exist for given URL')
        return path

    def save(self, orig):
        """Copy and return new page"""
        return orig.copy(self.cleaned_data['path'])

    class Meta:
        model = Page
        fields = ('path',)


class ImportForm(forms.Form):
    """Page importing form"""
    file = forms.FileField(label='Exported file', required=True)

    def clean_file(self):
        """File cleaning, validates it using Page.valid_xml()"""
        file = self.cleaned_data['file']
        try:
            Page.valid_xml(file.read())
        except forms.ValidationError, e:
            raise e
        else:
            file.seek(0) # seek file because will be used again
            return file

    def save(self):
        return Page.from_xml(self.cleaned_data['file'].read())


class DynamicForm(forms.Form):
    """Dynamic form. Will create a form from a set of (name, type) pairs."""
    basename = forms.CharField(widget=forms.HiddenInput(), required=True)

    def __init__(self, names, *args, **kwargs):
        """Init method, will add fields according to name and type."""
        super(DynamicForm, self).__init__(*args, **kwargs)
        self.names = names
        for name, type in names:
            self.fields[name] = type.as_field(label=name.replace('_', ' '),
                                              required=False)

    def save(self, page):
        """Save method. Will save each section value.
        Will return saved values"""
        result = []
        basename = self.cleaned_data['basename']

        for name, type in self.names:
            try: # use type save handler
                value = type.to_database(self, name)
            except ValueError: # ignore error
                pass
            else:
                vname = mkbasename(basename, name)
                try: # try to update a Value instance
                    obj = page.values.get(name=vname)
                    # if types are different, like it was changed in page
                    # definition, needs to be overriden to avoid duplications
                    # because of uniqueness definition on Value model
                    if obj.type != type.name():
                        obj.type = type.name()
                    obj.value = value
                    obj.save()
                except Value.DoesNotExist: # save new value
                    obj = page.values.create(name=vname, type=type.name(),
                                             value=value)
                result.append(obj)
        return result


def _clean_path(form, field='path'):
    """Retrieve Path object or raise ValidationError if not exists"""
    try:
        path = Path.objects.get(pk=form.cleaned_data[field])
    except Path.DoesNotExist:
        raise forms.ValidationError('Invalid %s' % field)
    return path
