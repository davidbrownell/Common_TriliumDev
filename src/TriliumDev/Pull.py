# ----------------------------------------------------------------------
# |
# |  Pull.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-12 21:33:47
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Implements 'Pull' functionality"""

import os
import textwrap
import yaml

from datetime import datetime
from io import StringIO
import multiprocessing
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from dataclasses import dataclass, field
import inflect as inflect_mod

import CommonEnvironment
from CommonEnvironment import FileSystem
from CommonEnvironment import TaskPool
from CommonEnvironment.Shell.All import CurrentShell
from CommonEnvironment.Shell.Commands.All import SymbolicLink
from CommonEnvironment.StreamDecorator import StreamDecorator, StreamDecoratorException

from CommonEnvironment.TypeInfo.FundamentalTypes.DateTimeTypeInfo import DateTimeTypeInfo
from CommonEnvironment.TypeInfo.FundamentalTypes.Serialization.StringSerialization import StringSerialization
from CommonEnvironment.TypeInfo.FundamentalTypes.UriTypeInfo import Uri

from CommonEnvironmentEx.Package import InitRelativeImports

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

with InitRelativeImports():
    from .Config import Config
    from . import Constants
    from .RequestsSession import RequestsSession
    from .TriliumAttribute import TriliumAttribute
    from .TriliumNoteShort import TriliumNoteShort


# ----------------------------------------------------------------------
inflect                                     = inflect_mod.engine()


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def Pull(
    config: Config,
    url: Optional[Uri],
    etapi_token: Optional[str],
    dm: StreamDecorator.DoneManagerInfo,
    *,
    overwrite_store: bool,
) -> None:
    directory_exists_error_template = textwrap.dedent(
        """\
        The directory '{}' already exists; specify '/overwrite' on the command line to overwrite it.

        Note that overwriting will LOSE ANY LOCAL CHANGES that have not yet been pushed or published.

        """,
    )

    store_directory = config.StoreDirectory
    if os.path.isdir(store_directory):
        if not overwrite_store:
            raise StreamDecoratorException(directory_exists_error_template.format(store_directory))

        FileSystem.RemoveTree(store_directory)

    hierarchy_directory = config.HierarchyDirectory
    if os.path.exists(hierarchy_directory):
        if not overwrite_store:
            raise StreamDecoratorException(directory_exists_error_template.format(hierarchy_directory))

        FileSystem.RemoveTree(hierarchy_directory)

    FileSystem.MakeDirs(store_directory)

    # ----------------------------------------------------------------------
    def SaveContent(
        core_id: int,  # pylint: disable=unused-argument
        note: "_WorkingNote",
        content: Optional[bytes],
    ) -> None:
        this_store_directory = os.path.join(store_directory, note.id)

        FileSystem.MakeDirs(this_store_directory)

        # Write the content
        if content is not None:
            assert note.content_extension is not None

            output_filename = os.path.join(
                this_store_directory,
                "{}{}".format(
                    Constants.CONTENT_FILENAME,
                    note.content_extension,
                ),
            )

            with open(output_filename, "wb") as f:
                f.write(content)

        # Write the attributes
        output_filename = os.path.join(this_store_directory, Constants.ATTRIBUTES_FILENAME)

        with open(output_filename, "w") as f:
            f.write(TriliumAttribute.SerializeItems(note.attributes))

    # ----------------------------------------------------------------------

    root = GetNotes(
        config,
        url,
        etapi_token,
        dm,
        SaveContent,
    )

    # Persist hierarchy
    dm.stream.write("Persisting hierarchy...")
    with dm.stream.DoneManager() as persist_dm:
        link_commands: List[SymbolicLink] = []

        persist_dm.stream.write("Calculating...")
        with persist_dm.stream.DoneManager():
            visited: Set[str] = set()

            # ----------------------------------------------------------------------
            def WalkHierarchy(
                note: TriliumNoteShort,
            ) -> None:
                if note.id in visited:
                    return

                visited.add(note.id)

                this_store_directory = os.path.join(store_directory, note.id)

                for link_name, child_note in note.children.items():
                    link_commands.append(
                        SymbolicLink(
                            os.path.join(
                                this_store_directory,
                                Constants.LINK_DIRECTORY_NAME_TEMPLATE.format(
                                    name=CurrentShell.ScrubFilename(link_name),
                                ),
                            ),
                            os.path.join(store_directory, child_note.id),
                            is_dir=True,
                            relative_path=True,
                        ),
                    )

                    WalkHierarchy(child_note)

            # ----------------------------------------------------------------------

            WalkHierarchy(root)

            link_commands.append(
                SymbolicLink(
                    hierarchy_directory,
                    os.path.join(store_directory, root.id),
                    is_dir=True,
                    relative_path=True,
                ),
            )

        assert link_commands

        persist_dm.stream.write("Executing...")
        with persist_dm.stream.DoneManager() as execute_dm:
            sink = StringIO()

            execute_dm.result = CurrentShell.ExecuteCommands(link_commands, sink)
            if execute_dm.result != 0:
                execute_dm.stream.write(sink.getvalue())
                return execute_dm.result


# ----------------------------------------------------------------------
def GetNotes(
    config: Config,
    url: Optional[Uri],
    etapi_token: Optional[str],
    dm: StreamDecorator.DoneManagerInfo,
    content_callback: Optional[
        Callable[
            [
                int,                        # core_id
                "_WorkingNote",             # note
                Optional[bytes],            # content
            ],
            None,
        ]
    ]=None,
    status_prefix="    ",
) -> TriliumNoteShort:
    content_callback = content_callback or (lambda *args, **kwargs: None)

    note_lookup: Dict[str, _WorkingNote] = {}

    with RequestsSession(config, url, etapi_token) as session:
        skipped_notifications: List[str] = []

        with dm.stream.SingleLineDoneManager(
            "Pulling notes...",
            done_suffix=lambda: "{} found".format(inflect.no("note", len(note_lookup))),
            suffix=lambda: "\n" if skipped_notifications else "",
        ) as pull_dm:
            # Get all the descendants of the root note
            search_items: List[
                Tuple[
                    Optional[_WorkingNote], # parent
                    Optional[str],          # branch id
                    str,                    # note id
                ],
            ] = [
                (None, None, config.root_note_id),
            ]

            # Don't output the skipped notifications right when they are encountered, as doing so
            # will screw up the output. Collect the notifications and display the information at
            # the end.
            prev_status_output_length = 0

            while search_items:
                # Update the status
                status = "{}{} found, {} remain".format(
                    status_prefix,
                    inflect.no("note", len(note_lookup)),
                    inflect.no("note", len(search_items)),
                )

                status_length = len(status)

                pull_dm.stream.write(
                    "\r{}{}".format(
                        status,
                        " " * max(0, prev_status_output_length - status_length),
                    ),
                )

                prev_status_output_length = status_length

                # Get the next item to search for
                parent, branch_id, note_id = search_items.pop()

                # Get the note
                response = session.get("notes/{}/".format(note_id)).json()

                include_note = True

                for attribute in response["attributes"]:
                    if attribute["type"] == "label" and attribute["name"] == Constants.NO_SYNC_ATTRIBUTE_NAME:
                        skipped_notifications.append(
                            "The note '{}' ({}) has been skipped because it is decorated with the '{}' label.".format(
                                response["title"],
                                response["noteId"],
                                Constants.NO_SYNC_ATTRIBUTE_NAME,
                            ),
                        )

                        include_note = False

                if not include_note:
                    continue

                note = _WorkingNote.FromResponse(response)
                note_lookup[note.id] = note

                if parent is None:
                    assert branch_id is None

                else:
                    assert branch_id is not None

                    # Get the branch that connects this note to its parent
                    branch = session.get("branches/{}/".format(branch_id)).json()

                    assert branch["parentNoteId"] == parent.id, (branch["branchId"], branch["parentNoteId"], parent.id)
                    assert branch["noteId"] == note.id, (branch["branchId"], branch["noteId"], note.id)

                    parent.children.setdefault(branch.get("prefix", None) or None, []).append(note)

                # Note that the following code assumes that 'childNoteIds' and 'childBranchIds'
                # are ordered consistently. The branch-related assertions above should fire if
                # this assumption turns out to be incorrect.
                for child_branch_id, child_id in zip(response["childBranchIds"], response["childNoteIds"]):
                    potential_note = note_lookup.get(child_id, None)

                    if potential_note is None:
                        search_items.append((note, child_branch_id, child_id))
                    else:
                        assert parent is not None

                        child_branch = session.get("branches/{}/".format(child_branch_id)).json()

                        assert child_branch["parentNoteId"] == note.id, (child_branch["branchId"], child_branch["parentNodeId"], note.id)
                        assert child_branch["noteId"] == potential_note.id, (child_branch["branchId"], child_branch["noteId"], potential_note.id)

                        note.children.setdefault(child_branch.get("prefix", None), []).append(potential_note)  # type: ignore  # pylint: disable=no-member

            if prev_status_output_length != 0:
                pull_dm.stream.write(
                    "\r{}\r  {}".format(" " * prev_status_output_length, "" if skipped_notifications else "  "),
                )


            # Display the skipped notifications
            for skipped_notification in skipped_notifications:
                pull_dm.stream.write_info(skipped_notification)

        # Extract the content
        with dm.stream.SingleLineDoneManager("Extracting content...") as extract_dm:
            # ----------------------------------------------------------------------
            def GetContent(
                core_index: int,
                note: _WorkingNote,
            ) -> None:
                if note.content_extension is None:
                    content = None
                else:
                    content = session.get("notes/{}/content/".format(note.id)).content

                    note.content_hash = TriliumNoteShort.CalculateHash(content)

                content_callback(core_index, note, content)

            # ----------------------------------------------------------------------

            TaskPool.Execute(
                [
                    TaskPool.Task(
                        note.title,
                        lambda core_index, note=note: GetContent(core_index, note),
                    )
                    for note in note_lookup.values()
                ],
                extract_dm.stream,
                progress_bar=True,
                num_concurrent_tasks=multiprocessing.cpu_count(),
            )

        dm.stream.write("Organizing content...")
        with dm.stream.DoneManager():
            # ----------------------------------------------------------------------
            def GetLinkName(
                child_id: str,
                parent_note: _WorkingNote,
            ) -> str:
                if parent_note.unique_link_names is None:
                    unique_names: Dict[str, int] = {}
                    unique_link_names: Dict[str, str] = {}

                    for prefix, child_notes in parent_note.children.items():
                        for child_note in child_notes:
                            if prefix is None:
                                unique_name = child_note.title
                            else:
                                unique_name = "{} - {}".format(prefix, child_note.title)

                            if unique_name in unique_names:
                                num_duplicates = unique_names[unique_name]
                                unique_names[unique_name] += 1

                                unique_name += " ({})".format(num_duplicates)
                            else:
                                unique_names[unique_name] = 1

                            unique_link_names[child_note.id] = unique_name

                    parent_note.unique_link_names = unique_link_names

                return parent_note.unique_link_names[child_id]

            # ----------------------------------------------------------------------
            def UpdateExportedChildren(
                note: _WorkingNote,
            ):
                for parent_id in note.parent_ids:
                    if parent_id == "root":
                        continue

                    parent_note = note_lookup.get(parent_id, None)
                    if parent_note is None:
                        continue

                    link_name = GetLinkName(note.id, parent_note)

                    if link_name not in parent_note.exported_children:
                        parent_note.exported_children[link_name] = note

                        UpdateExportedChildren(parent_note)

            # ----------------------------------------------------------------------

            for working_note in note_lookup.values():
                UpdateExportedChildren(working_note)

            trilium_note_lookup: Dict[str, TriliumNoteShort] = {}

            # ----------------------------------------------------------------------
            def CreateTriliumNote(
                note: _WorkingNote,
            ) -> TriliumNoteShort:
                potential_note = trilium_note_lookup.get(note.id, None)
                if potential_note is not None:
                    return potential_note

                parent_ids = [parent_id for parent_id in note.parent_ids if parent_id in note_lookup]

                result = TriliumNoteShort(
                    id=note.id,
                    note_type=note.note_type,
                    mime_type=note.mime_type,
                    parent_ids=parent_ids,
                    attributes=note.attributes,
                    content_hash=note.content_hash,
                    children={
                        link_name : CreateTriliumNote(child)
                        for link_name, child in note.exported_children.items()
                    },
                )

                trilium_note_lookup[result.id] = result

                return result

            # ----------------------------------------------------------------------

            return CreateTriliumNote(note_lookup[config.root_note_id])


# ----------------------------------------------------------------------
# |
# |  Private Types
# |
# ----------------------------------------------------------------------
@dataclass
class _WorkingNote(object):
    # ----------------------------------------------------------------------
    # Information created from response
    id: str
    title: str

    note_type: str
    mime_type: str

    utc_date_created: datetime
    utc_date_modified: datetime

    parent_ids: List[str]
    attributes: List[TriliumAttribute]

    content_extension: Optional[str]

    # Information populated later
    children: Dict[Optional[str], List["_WorkingNote"]] = field(init=False, default_factory=dict)
    unique_link_names: Optional[Dict[str, str]]         = field(init=False, default=None)

    content_hash: Optional[str]                         = field(init=False, default=None)

    exported_children: Dict[str, "_WorkingNote"]        = field(init=False, default_factory=dict)

    # ----------------------------------------------------------------------
    @classmethod
    def FromResponse(cls, response):
        attributes = [TriliumAttribute.FromResponse(attr) for attr in response["attributes"]]

        attributes.sort(
            key=lambda item: item.position,
        )

        note_type = response["type"]
        mime_type = response["mime"]

        content_extension: Optional[str] = None

        if note_type in ["code", "text"]:
            potential_extension = Constants.mimetype_extension_map.get(mime_type, None)
            if potential_extension is not None:
                content_extension = potential_extension

        return cls(
            id=response["noteId"],
            title=response["title"],
            note_type=response["type"],
            mime_type=response["mime"],
            utc_date_created=StringSerialization.DeserializeItem(cls._date_time_type_info, response["dateCreated"]),
            utc_date_modified=StringSerialization.DeserializeItem(cls._date_time_type_info, response["dateModified"]),
            parent_ids=response["parentNoteIds"],
            attributes=attributes,
            content_extension=content_extension,
        )

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    _date_time_type_info                    = DateTimeTypeInfo()
