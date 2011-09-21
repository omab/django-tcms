from django.contrib import sitemaps
from django.core import urlresolvers
from models import Page, LIVE

class TCMSSitemap(sitemaps.Sitemap):
    """Return the sitemap items from CMS"""
    def __init__(self, patterns=None, priority=None, changefreq=None):
        """
        patterns is list of url patterns to find CMS pages for. Should have "name" param defined
        when patterns are ommited all live cms pages are used
        
        priority and changefreq allows to define eponymous params in resulting sitemap
        """
        
        if hasattr(patterns, "__iter__"):
            self.patterns = [pattern.name for pattern in patterns 
                if hasattr(pattern, 'name') and pattern.name]
        else:
            self.patterns = None

        self.priority = priority
        self.changefreq = changefreq

    def items(self):
        pages = Page.objects.select_related('path').filter(state = LIVE)

        if self.patterns != None:
            urls = map(urlresolvers.reverse, self.patterns)
            urls = [url + '/' if not url.endswith('/') else url for url in urls]
            
            pages = list(pages.filter(path__path__in = urls))
            
        return pages
        

    def changefreq(self, obj):
        return self.changefreq

    def priority(self, obj):
        return self.priority

    def lastmod(self, obj):
        return obj.updated

    def location(self, obj):
        return str(obj.path)