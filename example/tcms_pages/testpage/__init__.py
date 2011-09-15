from tcms.data_types import BigText, Text, Image
from tcms.tpl import Page, Several, Section, Single, Value


class SimpleText(Section):
    NAME = 'Simple text'
    DESCRIPTION = 'Single line text, useful for titles'
    template = 'tcms/simple.html'

    def set_fields(self, template=None):
        self['text'] = Single(text=Text())


class HTMLText(Section):
    NAME = 'HTML text'
    DESCRIPTION = 'Free HTML block'
    template = 'tcms/simple.html' # override if needed

    def set_fields(self):
        self['text'] = Single(text=BigText())


class Img(Section):
    NAME = 'Single image, outputs img tag'
    DESCRIPTION = 'Single image content, outputs img tag'
    template = 'tcms/image.html'

    def set_fields(self):
        self['image'] = Value(image=Image(), title=Text(),
                              alt=Text(), credits=Text(),
                              force_order=('image', 'title',
                                           'alt', 'credits'))


class Dots(Section):
    NAME = 'Dots list'
    DESCRIPTION = 'Dots list'
    template = 'tcms/dots.html'

    def set_fields(self):
        self['dots'] = Several(text=Single(text=Text()))


class Static(Page):
    NAME = 'Simple static page'
    DESCRIPTION = 'Use this template simple static page with big HTML block'

    def set_sections(self):
        self['heading'] = SimpleText()
        self['title'] = SimpleText()
        self['intro'] = HTMLText()
        self['content'] = HTMLText()
        self['image'] = Img()
        self['dots'] = Dots()


PAGE = Static
