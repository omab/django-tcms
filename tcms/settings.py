# -*- coding: utf-8 -*-
# image upload media directory format
IMAGES_UPLOAD_TO = 'cms/image/%Y/%m/%d'

# pagination settings
PAGINATE_BY = 30

# value names separator
SEP = '/'

# GET parameter name to force a page loading by id
CMSID = 'cmsid'

# django admin base url
BASE_ADMIN = '/admin'

# django admin base url
CMS_ADMIN = '/admin/cms/page/'

# cache key to store page ids
CMS_CACHENAME = 'cms'

# extra values to be passed to rendering methods
RENDER_EXTRA_CONTEXT = {
    '_raw_enabled': True, # enable raw templatetag
}
