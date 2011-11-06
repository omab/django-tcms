# -*- coding: utf-8 -*-
"""Setup file for easy installation"""
from os.path import join, dirname
from setuptools import setup


version = __import__('tcms').__version__

LONG_DESCRIPTION = """
Django tCMS an easy to setup CMS that integrates easily with django-admin.

django-tcms was brought to life by Matías Aguirre while hacking a CMS framework
for Mydeco while working on Insophia.
"""

def long_description():
    """Return long description from README.rst if it's present
    because it doesn't get installed."""
    try:
        return open(join(dirname(__file__), 'README.rst')).read()
    except IOError:
        return LONG_DESCRIPTION


setup(name='django-tcms',
      version=version,
      author=u'Matías Aguirre',
      author_email='matiasaguirre@gmail.com',
      description='Django tCMS.',
      license='BSD',
      keywords='django, cms, django-admin',
      url='https://github.com/omab/django-tcms',
      packages=['tcms',
                'tcms.templatetags'],
      package_data={
          'tcms': [
              'templates/cms/*.html',
              'templates/cms/edit/*.html',
              'static/css/*.css',
              'static/js/*.js',
              'static/img/*.png',
              'static/img/*.gif',
              'static/img/*.gif',
              'static/img/fancybox/*.gif',
              'static/img/fancybox/*.png',
          ]
      },
      long_description=long_description(),
      install_requires=['django>=1.2.5'],
      classifiers=['Framework :: Django',
                   'Development Status :: 4 - Beta',
                   'Topic :: Internet',
                   'License :: OSI Approved :: BSD License',
                   'Intended Audience :: Developers',
                   'Environment :: Web Environment',
                   'Programming Language :: Python :: 2.5',
                   'Programming Language :: Python :: 2.6',
                   'Programming Language :: Python :: 2.7'])
