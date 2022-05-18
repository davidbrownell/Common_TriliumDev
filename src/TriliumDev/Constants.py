# ----------------------------------------------------------------------
# |
# |  Constants.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-13 14:29:22
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains constant values used by multiple modules"""

import os

import CommonEnvironment

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
CONTENT_FILENAME                            = "content"
ATTRIBUTES_FILENAME                         = "attributes.yaml"
LINK_DIRECTORY_NAME_TEMPLATE                = "[link] {name}"

NO_SYNC_ATTRIBUTE_NAME                      = "triliumDevNoSync"


# ----------------------------------------------------------------------
mimetype_extension_map                      = {
    "text/css": ".css",
    "text/html": ".html",
    "application/json": ".json",
    "application/javascript;env=backend": ".backend.js",
    "application/javascript;env=frontend": ".frontend.js",
}


# ----------------------------------------------------------------------
mimetype_note_type_map                      = {
    "text/html": "text",
    "text/css": "code",
    "application/json": "code",
    "application/javascript;env=backend": "code",
    "application/javascript;env=frontend": "code",
}
