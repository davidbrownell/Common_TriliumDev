# ----------------------------------------------------------------------
# |
# |  Dev.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-19 16:29:09
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Implements Dev functionality"""

import os
import time

from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import CommonEnvironment
from CommonEnvironment.StreamDecorator import StreamDecorator

from CommonEnvironment.TypeInfo.FundamentalTypes.DateTimeTypeInfo import DateTimeTypeInfo
from CommonEnvironment.TypeInfo.FundamentalTypes.Serialization.StringSerialization import StringSerialization

from CommonEnvironmentEx.Package import InitRelativeImports

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

with InitRelativeImports():
    from .Config import Config
    from . import Constants
    from .Diff import DiffInfo, DiffType
    from . import LocalFilesystem
    from .RequestsSession import RequestsSession
    from .TriliumNoteShort import TriliumNoteShort


# ----------------------------------------------------------------------
def Monitor(
    config: Config,
    etapi_token: Optional[str],
    dm: StreamDecorator.DoneManagerInfo,
    *,
    refresh_url: Optional[str]=None,
    refresh_port: Optional[int]=None,
) -> None:
    # Get the local notes and create a lookup map
    dm.stream.write("Configuring...")
    with dm.stream.DoneManager(
        suffix="\n",
    ) as config_dm:
        local_root = LocalFilesystem.GetNotes(config, config_dm)
        if local_root is None:
            return

        config_dm.stream.write("Organizing notes...")
        with config_dm.stream.DoneManager():
            notes_lookup: Dict[str, TriliumNoteShort] = {}

            # ----------------------------------------------------------------------
            def AddNote(
                note: TriliumNoteShort,
            ) -> None:
                if note.id in notes_lookup:
                    return

                notes_lookup[note.id] = note

                for child_note in note.children.values():
                    AddNote(child_note)

            # ----------------------------------------------------------------------

            AddNote(local_root)

    dm.stream.write("Monitoring '{}'...".format(config.StoreDirectory))
    with dm.stream.DoneManager() as monitor_dm:
        if refresh_port is not None or refresh_url is not None:
            if refresh_url is None:
                refresh_url = "http://localhost:{}/dev/refresh/".format(refresh_port)
            else:
                refresh_url = "{}/dev/refresh/".format(refresh_url.rstrip("/"))

            # ----------------------------------------------------------------------
            def PingRefreshServer(session, output_stream) -> None:
                output_stream.write("Pinging '{}'...".format(refresh_url))
                with output_stream.DoneManager():
                    response = session.session.put(refresh_url)
                    response.raise_for_status()

            # ----------------------------------------------------------------------

            ping_func = PingRefreshServer

        else:
            ping_func = lambda *args, **kwargs: None

        # ----------------------------------------------------------------------
        class LocalEvents(FileSystemEventHandler):
            # ----------------------------------------------------------------------
            @classmethod
            def on_created(cls, event):
                with cls._GetEventStream(event.src_path) as output_stream:
                    output_stream.write("TODO: Creation not implemented yet {}\n".format(event))

            # ----------------------------------------------------------------------
            @classmethod
            def on_deleted(cls, event):
                with cls._GetEventStream(event.src_path) as output_stream:
                    output_stream.write("TODO: Deletion not implemented yet {}\n".format(event))

            # ----------------------------------------------------------------------
            @classmethod
            def on_modified(cls, event):
                with cls._GetEventStream(event.src_path) as output_stream:
                    dirname, basename = os.path.split(event.src_path)

                    if not basename.startswith(Constants.CONTENT_FILENAME):
                        output_stream.write("TODO: Modifications of non-content types is not supported at this time.\n")
                        return

                    note_id = os.path.basename(dirname)

                    note = notes_lookup.get(note_id, None)
                    if note is None:
                        output_stream.write("'{}' is not a recognized note.\n".format(note_id))
                        return

                    diff_info = DiffInfo.Create(DiffType.content_changed, note, note, None)

                    output_stream.write("{}..".format(diff_info.ToString()))
                    with output_stream.DoneManager() as this_dm:
                        with RequestsSession(config, None, etapi_token) as session:
                            diff_info.ToActivity()(
                                config,
                                session,
                                lambda value: this_dm.stream.write("{}\n".format(value)),
                            )

                            ping_func(session, output_stream)

            # ----------------------------------------------------------------------
            @classmethod
            def on_moved(cls, event):
                with cls._GetEventStream(event.src_path) as output_stream:
                    output_stream.write("TODO: Moved not implemented yet {}\n".format(event))

            # ----------------------------------------------------------------------
            # ----------------------------------------------------------------------
            # ----------------------------------------------------------------------
            @classmethod
            @contextmanager
            def _GetEventStream(
                cls,
                filename: str,
            ):
                monitor_dm.stream.write(
                    "[{}] {}".format(
                        StringSerialization.SerializeItem(cls._date_time_type_info, datetime.now()),
                        filename,
                    ),
                )

                with monitor_dm.stream.DoneManager(
                    suffix="\n",
                ) as this_dm:
                    yield this_dm.stream

            # ----------------------------------------------------------------------
            _date_time_type_info        = DateTimeTypeInfo()

        # ----------------------------------------------------------------------

        observer = Observer()

        observer.schedule(
            LocalEvents(),
            config.StoreDirectory,
            recursive=True,
        )

        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()

        observer.join()
