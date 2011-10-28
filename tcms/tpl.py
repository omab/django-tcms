# -*- coding: utf-8 -*-
"""Template definition base classes and build structures."""
import re
from os import walk, sep
from os.path import dirname
from collections import defaultdict

from django.conf import settings
from django.template import loader, Context
from django.utils.datastructures import SortedDict
from django.utils.safestring import mark_safe
from django.utils.importlib import import_module

from tcms.data_types import BaseType
from tcms.utils import human_title
from tcms.exceptions import TemplateFormValidationError


RENDER_EXTRA_CONTEXT = getattr(settings, 'TCMS_RENDER_EXTRA_CONTEXT', {})
SEP = '/'

class Page(SortedDict):
    """
    Page base class.

    A page is built with sections, each section will defined it's needed
    values. Sections are accessible using dict mechanims.
    """
    NAME = ''           # template name
    DESCRIPTION = ''    # template description
    TEMPLATE = None     # possible template to use to render this page type

    # Migration data
    #   migration_template: must be a template path to match TipoCMS
    #                       live pages
    #
    #   migration_names: must be a list of triplets in the form
    #                    [(regex, new_name, type), ...] where
    #                    regex: is a regular expression that matches TipoCMS
    #                           fragment/content names (SEP is used to join
    #                           values)
    #                    new_name: is string new name, might contain
    #                              placeholders if regex captures values
    #                    type: is CMS value type
    migration_template = None
    migration_names = None

    def __init__(self):
        """Init method.
        Subclasses must defined Section using self[section_name] = SectionSubclass(...).
        Page

        Ordering is determined by key insertions as this is a SortedDict subclass.
        """
        self.set_sections()
        for name, section in self.iteritems():
            section.basename = name # set section basename
            section.page = self

    def set_sections(self):
        """Setup fields in subclasses, by default page has not sections."""
        pass

    def load(self, values):
        """Load values. @values must be a list of (name, value) pairs.
        Values will be loaded into each section.
        """
        # group values per section
        grouped = defaultdict(list)
        for name, value in values:
            section, name = split_basename(name, 1)
            grouped[section].append((name, value))

        # load values on each section
        for section, values in grouped.iteritems():
            self[section].load(values)

    @classmethod
    def fix_path_hacks(cls, path):
        """Override with needed code to remove TipoCMS path hacks
        like '/new/' on homepage or '/new-magazine/' in /the-magazine/.
        @path will come with trailing slash always."""
        return path

    @classmethod
    def migrate(cls, template, tipocms_page):
        """Migrates TipoCMS pages to CMS. This method can be removed
        once all TipoCMS pages are migrated."""
        from tcms.models import Path, Page, Value, LIVE
        from tipocms.models import CmsTextContent, CmsImageContent

        http_path = tipocms_page.http_path.strip()
        if not http_path.startswith('/'): # avoid invalid pages
            return

        if not http_path.endswith('/'):
            http_path += '/'
        http_path = cls.fix_path_hacks(http_path)

        path, created = Path.objects.get_or_create(path=http_path,
                                                   locale=tipocms_page.locale)
        if not created: # path already, check page entry
            if Page.objects.filter(path=path, state=LIVE).count() > 0:
                return

            http_path = cls.fix_path_hacks(http_path)

        path, created = Path.objects.get_or_create(path=http_path,
                                                   locale=tipocms_page.locale)
        if not created: # path already, check page entry
            if Page.objects.filter(path=path, state=LIVE).count() > 0:
                return

        page = Page(path=path, template=template,
                    description=tipocms_page.description)

        # add meta data
        for meta in tipocms_page.cmspagemetacontent_set.all():
            if meta.name == 'title':
                page.meta_title = meta.text
            elif meta.name == 'description':
                page.meta_description = meta.text
            elif meta.name == 'keywords':
                page.meta_keywords = meta.text
        page.save() # save new page

        def try_save(name, value):
            for matcher, new_name, Type in cls.migration_names:
                match = re.match(r'^%s$' % matcher, name)
                if match:
                    groups = match.groups()
                    if groups:
                        new_name = new_name % groups
                    # try to get method to post-process migration value
                    # from template instance
                    migrate = getattr(cls, '%s_migrate' % Type.name(),
                                      lambda p, v: v)
                    page.values.add(Value(name=new_name, type=Type.name(),
                                          value=migrate(page, value)))
                    break


        # save values
        for f in tipocms_page.cmsfragment_set.select_related('template').all():
            # avoid empty fragments
            if f.template.template_path == 'cms/fragment/empty.html':
                continue
            names = []
            for c in f.cmscontentmapping_set.all():
                obj = c.object
                if isinstance(obj, (CmsTextContent, CmsImageContent)):
                    name = mkbasename(f.name, c.name)
                    if name in names: # do not process repeated values
                        continue
                    names.append(name)
                    try_save(name, obj.value())
                    # try to save images alt/credits values by matching
                    # value name adding /alt and /credits endings
                    if isinstance(obj, CmsImageContent):
                        alt, credits = obj.alt, obj.credits
                        if alt:
                            try_save(mkbasename(name, 'alt'), alt.strip())
                        if credits:
                            try_save(mkbasename(name, 'credits'), credits.strip())
        page.publish()
        return page

    def save(self, page, basename, *args, **kwargs):
        """Save method. Will delegate save functionality to it's
        corresponding section."""
        name, subname = split_basename(basename, 1)
        return self[name].save(page, subname, *args, **kwargs)

    def render_sections(self, *args, **kwargs):
        """Return a list of section names and rendered content.
        Rendering is delegated to each section and arguments are passed
        directly."""
        return [(name, section.render(*args, **kwargs))
                    for name, section in self.iteritems()]


class Section(SortedDict):
    """Section base class.

    A section is build from group names, each group name is build from names
    sets (see FieldSet below).

    Sections values are grouped by basenames, a basename is a unique string
    in a page that will group the section values under that name, this value
    will be prepended to stored values names and striped out on loading.
    Section name on page is a good candidate to use as basename.
    """
    NAME = ''           # section name
    DESCRIPTION = ''    # section description
    basename = None     # section basename (used to store values in database)
    page = None

    def __init__(self):
        """Init method. Defines basename as class name if not defined."""
        self.basename = self.basename or self.__class__.__name__.lower()
        self.set_fields()

    def set_fields(self):
        """Setup fields in subclasses"""
        raise NotImplementedError('Implement in subclass')

    def inc_form(self):
        """Returns form data concerning to each section part"""
        return [item.inc_form(self.basename, name)
                            for name, item in self.iteritems()]

    def load(self, values):
        """Load values into section parts. @values must be a list of tuples
        of (name, value) pair."""
        # group values by part name
        grouped = defaultdict(list)
        for name, value in values:
            part, name = split_basename(name, 1)
            grouped[part].append((name, value))

        # delegate values loading to each section part
        for name, values in grouped.iteritems():
            self[name].load(values)

    def save(self, page, basename, *args, **kwargs):
        """Save method. Will delegate saving to corresponding part"""
        # get name, subname from basename, parts that are Value instance
        # directly will lack of a subname.
        try:
            name, subname = split_basename(basename, 1)
        except ValueError:
            name, subname = basename, None
        return self[name].save(page, subname, *args, **kwargs)

    def done_percent(self):
        """Returns a done percent of this section."""
        values = [item.done_percent() for item in self.values()]
        total, done = reduce(_reduce_pairs, values) if values else (0, 0)
        return int(done * 100 / total)

    def __nonzero__(self):
        """Boolean check, a section is True if any value is True"""
        return any(map(bool, self.values()))

    def __unicode__(self):
        """Return rendered result as unicode representation. Useful for
        templates"""
        return self.render()

    def render(self, extra_context=None):
        """Render defined section template. Section instance will be
        accessible throw an 'obj' context value"""
        context = extra_context or {}
        if RENDER_EXTRA_CONTEXT:
            context.update(RENDER_EXTRA_CONTEXT)
        context['obj'] = self
        out = loader.get_template(self.template).render(Context(context))
        return mark_safe(out or '')


class FieldSet(object):
    """
    Data types fields definition.
    This class allows to define set of fields to build complex pages.
    """
    def __init__(self, force_order=None, **fields):
        """Init method.

        @fields defines name/values for fields on this set, values
        can be another FieldSet instance, alloweing to build complex
        tree like structures, or a BaseType which will be the leaves
        of the tree and final fields.

        @force_order is a list of names to define the order that
        fields should be presented on forms and other areas.
        """
        # check that each field value is a BaseType of FieldSet instance
        for value in fields.values():
            if not isinstance(value, (BaseType, FieldSet)):
                raise ValueError('%s is not a valid type' % value)
        self.data = None # loaded data should be stored here
        self.cache = {} # store converted values from data types
        self.loaded = False # flag to mark that data was loaded
        self.fields = SortedDict() # fields
        for name in _ordering(force_order, fields): # store fields ordered
            self.fields[name] = fields[name]

    def inc_form(self, *names):
        """Include form method, must return a dict with context
        values and cannot miss tpl key with template path that will
        render the form."""
        data = self._inc_form(*names)
        if data and 'tpl' not in data:
            raise ValueError('Missing form template')
        return data

    def _inc_form(self, *names):
        """Return form data needed to render form. Implement in subclass"""
        raise NotImplementedError('Implement in subclass')

    def load(self, values):
        """Load data into fields.
        Relies on subclasses _load method to do the propper task. Won't load if
        data was already loaded."""
        if not self.loaded:
            self._load(values)
            self.loaded = True

    def _load(self, values):
        """Load data into fields, implement in subclass"""
        raise NotImplementedError('Implement in subclass')

    def clone(self):
        """Clone FieldSet, sub FieldSets will be cloned too if any."""
        fields = dict((k, v.clone() if isinstance(v, FieldSet) else v)
                            for k, v in self.fields.iteritems())
        return self.__class__(force_order=self.fields.keys(), **fields)

    def done_percent(self):
        """Return fields done percent."""
        vals = [item.done_percent() for item in self.fields.values()]
        return reduce(_reduce_pairs, vals) if vals else (len(self), 0)

    def __len__(self):
        """Return loaded data lenght"""
        return self.loaded and len(self.data) or 0

    def __nonzero__(self):
        """Must returns FieldSet filled status, no fields or data means
        not filled. Implement in subclass."""
        if self.loaded:
            data = any(bool(v) for v in self.data.itervalues()) \
                        if self.data else False
            fields = any(bool(v) for v in self.fields.itervalues()
                            if isinstance(v, FieldSet)) \
                        if self.fields else False
            return data or fields
        else:
            return False

    def __hasitem__(self, name):
        return name in self.fields

    def __getitem__(self, name):
        """Dict like accessor to section fields. Sub FieldSets are
        returned directly while BaseType values are proccesed by
        it's type value method first."""
        if name in self.fields:
            if self.loaded:
                item = self.fields[name]
                if isinstance(item, BaseType):
                    if name not in self.cache:
                        self.cache[name] = item.value(self.data.get(name))
                    return self.cache[name]
                elif isinstance(item, FieldSet):
                    return item
            else:
                return None
        else:
            raise KeyError('Missing value "%s"' % name)

    def __getattr__(self, name):
        try:
            return self.__getitem__(name)
        except KeyError, e:
            raise AttributeError(str(e))


class Value(FieldSet):
    """
    Value section type.

    This is the simpler node type that a section can be built with, it
    represents a set of name/BaseType that makes sense together. The
    form representation will show all fields and save them together too.
    """
    def __init__(self, force_order=None, **fields):
        # check that all fields are BaseType instances
        for type in fields.itervalues():
            if not isinstance(type, BaseType):
                raise ValueError('%s is not a valid BaseType' % type)
        super(Value, self).__init__(force_order, **fields)

    def _form(self, *args, **kwargs):
        """Return form for current fields.
        Form is cached so we can keep bounded form with errors to report
        to user."""
        from tcms.forms import DynamicForm
        if not hasattr(self, '__form'):
            setattr(self, '__form', DynamicForm(self.fields.items(),
                                                *args, **kwargs))
        return getattr(self, '__form')

    def _load(self, values):
        """Load data handler, will store data for names defined in
        instance fields."""
        self.data = dict((name, value) for name, value in values
                                if name in self.fields)

    def _inc_form(self, *names):
        """Include form handler. Returns needed data to render form
        for current values set, will use loaded data as initial but
        will use form creatd in save() method if was called first,
        this will render a form with error messages if any.
        """
        if self.data: # prepare value to form inclusion
            data = dict((name, self.fields[name].form_value(value))
                            for name, value in self.data.iteritems())
        else:
            data = {}

        bn = data['basename'] = mkbasename(*names)
        form = self._form(initial=data)
        return {'form': form, 'basename': bn,
                'form_id': bn.replace(SEP, '-'),
                'form_title': human_title(names[-1]),
                'tpl': 'cms/edit/value.html'}

    def save(self, page, basename, *args, **kwargs):
        """Save handler. Will save and return Values instances for data
        passed or raise TemplateFormValidationError if form is invalid
        """
        form = self._form(*args, **kwargs)
        if form.is_valid():
            return form.save(page)
        else:
            raise TemplateFormValidationError(form, 'Form error')

    def done_percent(self):
        """Returns done percent caclulated from count of fields and
        loaded data."""
        return (len(self.fields), len(self.data) if self.data else 0)


class Single(Value):
    """Single value field, offers direct access to value attributes."""
    def __init__(self, *args, **kwargs):
        """Only a name/value pair is allowed and is enforced"""
        super(Single, self).__init__(*args, **kwargs)
        # raise AttributeError if several names were passed
        if len(self.fields) > 1:
            raise AttributeError('Multiple names passed')
        self._value = None
        self.name, self.type = self.fields.items()[0]

    def __getattr__(self, name):
        """Direct access to value attributes, raises AttributeError if
        instance data is no loaded."""
        if self.loaded:
            return getattr(self.value, name)
        else:
            raise AttributeError('"Single" object has no attribute "%s"' \
                                            % name)

    @property
    def value(self):
        """Return proccessed value for type"""
        if not self._value:
            self._value = self.type.value(self.data.get(self.name))
        return self._value

    def __unicode__(self):
        """Unicode representation of loaded value"""
        return mark_safe(unicode(self.value)) if self.loaded else ''


class Group(FieldSet):
    """Grouped content field type.

    Allows to create nested FieldSet structure for complex page sections values.
    """
    def __init__(self, force_order=None, **fields):
        # check that all fields are FieldSets instances
        for type in fields.itervalues():
            if not isinstance(type, FieldSet):
                raise ValueError('%s is not a valid FieldSet' % type)
        super(Group, self).__init__(force_order, **fields)

    def _load(self, values):
        """Load data handler, will delegate loading to each sub FieldSets"""
        # group by name
        grouped = defaultdict(list)
        for name, value in values:
            name, subname = split_basename(name, 1)
            grouped[name].append((subname, value))

        # load values into each sub fieldset
        for name, values in grouped.iteritems():
            self.fields[name].load(values)

    def _inc_form(self, *names):
        """Include form handler, will return context data for rendering
        form for this group of values"""
        bn = mkbasename(*names)
        forms = [i.inc_form(bn, n) for n, i in self.fields.items()]
        return {'basename': bn, 'form_title': human_title(names[-1]),
                'form_id': bn.replace(SEP, '-'), 'tpl': 'cms/edit/group.html',
                'subforms': forms}

    def save(self, page, basename, *args, **kwargs):
        """Save handler"""
        try:
            name, subname = split_basename(basename, 1)
        except ValueError:
            name, subname = basename, None
        return self.fields[name].save(page, subname, *args, **kwargs)


class Several(FieldSet):
    """Several field set type.

    This FieldSet subclass allows the definition of list like values,
    allowing to manage them as a list, keeping it's definition position,
    and grouped values. Each field must be a FieldSet instance.
    """
    def __init__(self, up_to=None, force_order=None, **fields):
        """Init method.

        @up_to allows to define an upper limit of values to this set
        """
        # check that all fields are FieldSets instances
        for type in fields.itervalues():
            if not isinstance(type, FieldSet):
                raise ValueError('%s is not a valid FieldSet' % type)
        self.up_to = up_to
        super(Several, self).__init__(force_order, **fields)

    def _load(self, values):
        """Load data handler. Will load and group data in a list way sorted
        by position"""
        self.data = []
        # group values by position and name
        grouped = defaultdict(list)
        for name, value in values:
            pos, base_name, subname = split_basename(name, 2)
            grouped[(pos, base_name)].append((subname, value))

        # Clone sub fields and load data into them for each position
        by_pos = defaultdict(dict)
        for (pos, base_name), values in grouped.iteritems():
            by_pos[pos][base_name] = self.fields[base_name].clone()
            by_pos[pos][base_name].load(values)

        # store values and sort by pos
        self.data = by_pos.items()
        self.data.sort(key=lambda x: int(x[0]))

    def _inc_form(self, *names):
        """Returns data needed to render form for this FieldSet type"""
        forms, offset = [], 0
        bn = mkbasename(*names)
        order = self.fields.keys()

        for pos, items in (self.data or []):
            forms += [items[name].inc_form(bn, pos, name) for name in order]
            offset = max(offset, int(pos))

        # one extra empty form for adding new rows
        with_extra_form = not self.up_to or len(forms) < self.up_to
        if with_extra_form:
            for name, item in self.fields.items():
                forms.append(item.inc_form(bn, str(offset + 1), name))

        return {'subforms': forms, 'basename': bn,
                'tpl': 'cms/edit/several.html',
                'form_id': bn.replace(SEP, '-'),
                'with_extra_form': with_extra_form,
                'form_title': human_title(names[-1])}

    def save(self, page, basename, *args, **kwargs):
        """Save handler, will delegate saving into sub fieldset"""
        try:
            pos, name, subname = split_basename(basename, 2)
        except ValueError:
            (pos, name), subname = split_basename(basename, 1), None
        return self.fields[name].save(page, subname, *args, **kwargs)

    def done_percent(self):
        """Returns done percent for current fieldsets, deletages calculation
        to subfields and reduces the result."""
        if self.data:
            return reduce(_reduce_pairs, (value.done_percent()
                                for pos, values in self.data
                                    for value in values.itervalues()))
        else:
            return (len(self.fields), 0)

    def __iter__(self):
        """Iteration behavior, will iterate over loaded data yielding values"""
        for pos, value in (self.data or []):
            yield value

    def __nonzero__(self):
        """Returns True if any sub-value contains data."""
        return self.loaded and \
               any(map(lambda item: any(map(bool, item[1].values())),
                       self.data))


def mkbasename(*values):
    """Creates basenames for forms"""
    return SEP.join(values)


def split_basename(value, maxsplit):
    """Splits form basenames"""
    return value.split(SEP, maxsplit)


def _reduce_pairs(left, right):
    """Reduce left and right pairs as a sum of it's items"""
    return (left[0] + right[0], left[1] + right[1])


def _ordering(names, dict_):
    """Return ordering names giving preference to @names values
    if their entries are present in @dict_.

    Return sorted @dict_ keys if not names are passed. Missing names
    present on @dict_ but not in @names will be added (sorted) at the
    end.
    """
    if not names:
        return sorted(dict_)
    else:
        out, d = [], dict_.copy()
        for name in names:
            if name in dict_: # add names only if present in dict_
                out.append(name)
                d.pop(name)
        return out + sorted(d) # append the rest of dict_ keys


def _load_templates():
    """Return tuple with templates entries loaded in dict and choices list.

    Load templates modules defined under settings.TCMS_PAGES, that will be
    loaded in a dict which key will be name and value will be template
    class. Also it will be loaded in a sorted by name list of tuples where
    first value will be template name and second will be template verbose
    name.
    """
    mod = import_module(settings.TCMS_PAGES)

    entries, dir_name = {}, dirname(mod.__file__)
    for path, subdirs, files in walk(dir_name):
        name = path.replace(dir_name, '').strip(sep).replace(sep, '.')

        for file in filter(lambda f: f.endswith('.py'), files):
            fname = file.replace('.py', '')
            import_name = filter(None, (settings.TCMS_PAGES, name, fname))

            try:
                mod = import_module('.'.join(import_name))
                if hasattr(mod, 'PAGE'):
                    entries[name or fname] = mod.PAGE
            except (ImportError, AttributeError):
                pass
    return entries

# templates mapping and choices
PAGES = _load_templates()
