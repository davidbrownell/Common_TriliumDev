# ----------------------------------------------------------------------
# |
# |  Activities.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-18 15:26:44
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Activities invoked by changes in local content"""

import os

from typing import Callable

import CommonEnvironment

from CommonEnvironmentEx.Package import InitRelativeImports

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

with InitRelativeImports():
    from .Config import Config
    from . import Constants
    from .RequestsSession import SessionWrapper
    from .TriliumNoteShort import TriliumNoteShort


# ----------------------------------------------------------------------
def PushContent(
    config: Config,
    session: SessionWrapper,
    note: TriliumNoteShort,
    on_status_update: Callable[[str], None],
) -> None:
    # Get the content
    on_status_update("Reading content")

    filename = os.path.join(
        config.StoreDirectory,
        note.id,
        "{}{}".format(Constants.CONTENT_FILENAME, Constants.mimetype_extension_map[note.mime_type]),
    )

    if not os.path.isfile(filename):
        raise Exception("The file '{}' does not exist".format(filename))

    with open(filename, "rb") as f:
        content = f.read()

    # Upload the content
    on_status_update("Uploading content")

    session.put(
        "notes/{}/content/".format(note.id),
        data=content,
        headers={
            "Content-Type": "application/octet-stream",
        },
    )
