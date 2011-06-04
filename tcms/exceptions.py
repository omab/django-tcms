# -*- coding: utf-8 -*-
from django.forms import ValidationError


class TemplateFormValidationError(ValidationError):
    def __init__(self, form, *args, **kwargs):
        self.form = form
        self.errors = form.errors
        super(TemplateFormValidationError, self).__init__(*args, **kwargs)
