# ----------------------------------------------------------------------
# |
# |  TriliumNoteShort.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-12 21:37:23
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the TriliumNoteShort object"""

import hashlib
import os
import uuid

from typing import Any, Dict, List, Optional

from dataclasses import dataclass

import CommonEnvironment
from CommonEnvironment.YamlRepr import ObjectReprImplBase

from CommonEnvironmentEx.Package import InitRelativeImports

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

with InitRelativeImports():
    from .TriliumAttribute import TriliumAttribute


# ----------------------------------------------------------------------
@dataclass(frozen=True, repr=False)
class TriliumNoteShort(ObjectReprImplBase):
    id: str

    note_type: str
    mime_type: str

    parent_ids: List[str]
    attributes: List[TriliumAttribute]

    content_hash: Optional[str]

    children: Dict[str, "TriliumNoteShort"]

    # ----------------------------------------------------------------------
    def __post_init__(self):
        super(TriliumNoteShort, self).__init__(
            include_root_class_info=False,
            include_class_info=False,
            include_id=False,
            include_methods=False,
            include_private=False,
        )

    # ----------------------------------------------------------------------
    def ToMetadata(self) -> Dict[str, Any]:
        return {
            "note_type": self.note_type,
            "mime_type": self.mime_type,
            "links": {link_name: child.id for link_name, child in self.children.items()},
        }

    # ----------------------------------------------------------------------
    @staticmethod
    def CreateTemporaryId() -> str:
        return "__{}__".format(str(uuid.uuid4()).replace("-", ""))

    # ----------------------------------------------------------------------
    @staticmethod
    def IsTemporaryId(
        note_id: str,
    ) -> bool:
        return note_id.startswith("__") and note_id.endswith("__") and len(note_id) >= 5

    # ----------------------------------------------------------------------
    @staticmethod
    def CalculateHash(
        content: bytes,
    ) -> str:
        return hashlib.sha256(content).hexdigest()
