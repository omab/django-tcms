===========
Django tCMS
===========

Django tCMS_ an easy to setup CMS that integrates easily with django-admin.

This project was brought to life by Matías Aguirre while hacking a CMS framework
for Mydeco_ while working on Insophia_.


-----------
Description
-----------

Sites with custom CMS systems usually relies on deployment to bring new pages
layouts, and these new pages are created by us, developers. tCMS_ brings a new
mechanism where new pages definitions can be defined using our favorite tool,
python_. With a set of building blocks pages are created easily once it's
structure is well defined.


--------
Features
--------

* Use python_ to define your pages.
* Django-admin integration.
* Rich editing using CKEditor_ (users need to install CKEditor_ and define
  setting for tCMS_ app).
* Pages i18n, check Localization section for more details.
* Easy template integration, an easy {{ cms.block_name }} includes named block.


------------
Dependencies
------------

This application only depends on django-admin.


------------
Installation
------------

From pypi_::

    $ pip install django-tcms

or::

    $ easy_install django-tcms

or clone from github_::

    $ git clone git://github.com/omab/django-tcms.git

and add tCMS_ to PYTHONPATH::

    $ export PYTHONPATH=$PYTHONPATH:$(pwd)/tcms/

or::

    $ cd tcms
    $ sudo python setup.py install


-------------
Configuration
-------------

- Add tCMS_ to installed applications::

    INSTALLED_APPS = (
        ...
        'tcms',
    )

- Define where your pages are defined::

    TCMS_PAGES = 'tcms_pages'

  The application will import the modules inside and inspect anything that
  has a ``PAGE`` variable defined.

- Define where images should be uploaded::

    TCMS_IMAGES_UPLOAD_TO = 'cms/image/%Y/%m/%d'

  This setting is used to populate a ``upload_to`` Django field parameter, so
  you can use any supported formats.

- Define this setting if you have CKEditor_ installed and want it to be used
  while editing content::

    TCMS_CKEDITOR_BASE_URL = '/media/js/ckeditor'

- The application uses Django cache to store content to speed up loading the
  content when serving the content to users, by default the cache name is
  ``tcms``, but you can override it by defining::

    TCMS_CACHE_NAME = '...'

- To enable page localizations, set this setting to ``True``::

    TCMS_LOCALIZED = True

  Localization is disabled by default.

- Define your settings with the extra name/values needed by your templates::

    RENDER_EXTRA_CONTEXT = {...}


------------
Localization
------------

If your site support multiple languages, you will want to create pages on every
language.

tCMS_ uses Django LANGUAGES when searching for supported languages, but allows
you to create global language pages, for example if you support ``en-gb`` and
``en-us`` locales, it's possible to define a page with locale ``en`` and it
will be used to server the same content for users requesting for one or other
locale.


---------------
Example proyect
---------------

Check the example_ to see how it works.


.. _tCMS: https://github.com/omab/django-tcms
.. _Mydeco: http://mydeco.com
.. _Insophia: http://insophia.com
.. _github: https://github.com/omab/django-tcms
.. _CKEditor: http://ckeditor.com/
.. _python: http://python.org
.. _example: https://github.com/omab/django-tcms/tree/master/example
.. _pypi: http://pypi.python.org/pypi/django-tcms
