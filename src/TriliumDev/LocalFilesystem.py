# ----------------------------------------------------------------------
# |
# |  LocalFilesystem.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-16 06:53:08
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains functionality that helps when working with the local filesystem"""

import os
import textwrap

from typing import cast, Dict, List, Optional, Pattern

from dataclasses import dataclass
import inflect as inflect_module

import CommonEnvironment
from CommonEnvironment import RegularExpression
from CommonEnvironment.Shell.All import CurrentShell
from CommonEnvironment.StreamDecorator import StreamDecorator
from CommonEnvironment import TaskPool

from CommonEnvironmentEx.Package import InitRelativeImports

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

with InitRelativeImports():
    from .Config import Config
    from . import Constants
    from .TriliumAttribute import TriliumAttribute
    from .TriliumNoteShort import TriliumNoteShort


# ----------------------------------------------------------------------
inflect                                     = inflect_module.engine()


# ----------------------------------------------------------------------
def GetNotes(
    config: Config,
    dm: StreamDecorator.DoneManagerInfo,
) -> Optional[TriliumNoteShort]:
    # Load the notes
    store_directory = config.StoreDirectory
    working_note_data: Dict[str, _WorkingData] = {}

    with dm.stream.SingleLineDoneManager(
        "Processing notes in '{}'...".format(store_directory),
        done_suffix=lambda: "{} found".format(inflect.no("note", len(working_note_data))),
    ) as processing_dm:
        # ----------------------------------------------------------------------
        def Execute(
            note_id: str,
        ) -> Optional[List[str]]:
            note_fullpath = os.path.join(store_directory, note_id)

            if os.path.isfile(note_fullpath):
                return [
                    "ERROR: '{}' is a file, which isn't expected at this level.\n".format(note_fullpath),
                ]

            errors = _AddWorkingData(
                working_note_data,
                note_id,
                note_fullpath,
            )

            return errors or None

        # ----------------------------------------------------------------------

        for errors in TaskPool.Transform(
            os.listdir(store_directory),
            Execute,
            processing_dm.stream,
            num_concurrent_tasks=1,
            name_functor=lambda index, note_id: note_id,
        ):
            if errors:
                processing_dm.stream.write("".join(errors))
                processing_dm.result = -1

        if processing_dm.result != 0:
            return None

    dm.stream.write("Organizing content...")
    with dm.stream.DoneManager() as organizing_dm:
        # Update the parents
        parent_map: Dict[str, List[str]] = {}

        for working_data in working_note_data.values():
            if working_data.id not in parent_map:
                parent_map[working_data.id] = []

            for child_id in working_data.children.values():
                parent_map.setdefault(child_id, []).append(working_data.id)

        # Create the Trilium notes
        note_lookup: Dict[str, TriliumNoteShort] = {}

        # ----------------------------------------------------------------------
        def CreateNote(
            working_data: _WorkingData,
        ) -> TriliumNoteShort:
            potential_node = note_lookup.get(working_data.id, None)
            if potential_node is not None:
                return potential_node

            if not working_data.mime_type:
                note_type = ""
            else:
                assert working_data.mime_type in Constants.mimetype_note_type_map, working_data.mime_type
                note_type = Constants.mimetype_note_type_map[working_data.mime_type]

            note = TriliumNoteShort(
                id=working_data.id,
                note_type=note_type,
                mime_type=working_data.mime_type or "",
                parent_ids=parent_map[working_data.id],
                attributes=working_data.attributes,
                content_hash=working_data.content_hash,
                children={
                    child_link: CreateNote(working_note_data[child_id])
                    for child_link, child_id in working_data.children.items()
                },
            )

            note_lookup[note.id] = note

            return note

        # ----------------------------------------------------------------------

        roots: List[TriliumNoteShort] = []

        for working_data in working_note_data.values():
            note = CreateNote(working_data)

            if not note.parent_ids:
                roots.append(note)

        assert len(roots) == 1
        return roots[0]


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class _WorkingData(object):
    # ----------------------------------------------------------------------
    id: str
    mime_type: Optional[str]
    content_hash: Optional[str]
    attributes: List[TriliumAttribute]
    children: Dict[str, str]


# ----------------------------------------------------------------------
_link_regex: Pattern                        = cast(Pattern, RegularExpression.TemplateStringToRegex(Constants.LINK_DIRECTORY_NAME_TEMPLATE))


# ----------------------------------------------------------------------
def _AddWorkingData(
    working_data_lookup: Dict[str, _WorkingData],
    note_id: str,
    note_fullpath: str,
) -> List[str]:
    errors: List[str] = []

    mime_type: Optional[str] = None
    content_hash: Optional[str] = None
    attributes: List[TriliumAttribute] = []
    children: Dict[str, str] = {}

    for note_item in os.listdir(note_fullpath):
        note_item_fullpath = os.path.join(note_fullpath, note_item)

        if note_item == Constants.ATTRIBUTES_FILENAME:
            assert not attributes

            with open(note_item_fullpath) as f:
                attributes += TriliumAttribute.DeserializeItems(f.read())

        elif note_item.startswith(Constants.CONTENT_FILENAME):
            # Get the hash
            assert content_hash is None

            with open(note_item_fullpath, "rb") as f:
                content_hash = TriliumNoteShort.CalculateHash(f.read())

            # Get the mime type
            assert mime_type is None

            for potential_mime_type, extension in Constants.mimetype_extension_map.items():
                if note_item.endswith(extension):
                    mime_type = potential_mime_type
                    break

            if mime_type is None:
                errors.append("ERROR: Unable to determine the mime type for '{}'.\n".format(note_item_fullpath))
                continue

        elif os.path.isfile(note_item_fullpath):
            errors.append("ERROR: '{}' is a file, which isn't expected at this level.\n".format(note_item_fullpath))
            continue

        else:
            match = _link_regex.match(note_item)
            if not match:
                errors.append(
                    "ERROR: '{}' is not recognized; links should be written as '{}'.\n".format(
                        note_item,
                        Constants.LINK_DIRECTORY_NAME_TEMPLATE.format(
                            name="<link_name>",
                        ),
                    ),
                )
                continue

            if CurrentShell.IsSymLink(note_item_fullpath):
                resolved_link = CurrentShell.ResolveSymLink(note_item_fullpath)

                child_id = os.path.basename(resolved_link)
                assert not TriliumNoteShort.IsTemporaryId(child_id)

            else:
                child_id = TriliumNoteShort.CreateTemporaryId()
                errors += _AddWorkingData(working_data_lookup, child_id, note_item_fullpath)

            children[note_item] = child_id

    if not errors:
        assert note_id not in working_data_lookup

        working_data_lookup[note_id] = _WorkingData(
            note_id,
            mime_type,
            content_hash,
            attributes,
            children,
        )

    return errors
