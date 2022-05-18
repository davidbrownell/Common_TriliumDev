# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-17 07:38:58
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Builds code generated for the schema objects"""


# ----------------------------------------------------------------------
import os
import sys

from io import StringIO

import inflect as inflect_mod

import CommonEnvironment
from CommonEnvironment import BuildImpl
from CommonEnvironment import CommandLine
from CommonEnvironment import FileSystem
from CommonEnvironment import Process
from CommonEnvironment.Shell.All import CurrentShell
from CommonEnvironment.StreamDecorator import StreamDecorator

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
inflect                                     = inflect_mod.engine()


# ----------------------------------------------------------------------
@CommandLine.EntryPoint
@CommandLine.Constraints(                   # type: ignore
    output_stream=None,
)
def Build(
    force=False,
    output_stream=sys.stdout,
    verbose=False,
):
    with StreamDecorator(output_stream).DoneManager(
        line_prefix="",
        prefix="\nResults: ",
        suffix="\n",
    ) as dm:
        schema_filenames = []

        dm.stream.write("Finding schema files...")
        with dm.stream.DoneManager(
            done_suffix=lambda: "{} found".format(inflect.no("schema file", len(schema_filenames))),
        ):
            schema_filenames += FileSystem.WalkFiles(
                os.path.join(_script_dir, ".."),
                include_file_extensions=[".SimpleSchema"],
            )

        dm.stream.write("Processing files...")
        with dm.stream.DoneManager() as processing_dm:
            command_line_template = '"{script}" Generate PythonYaml {{name}} "{output_dir}" "/input={{input}}"{force}{verbose}'.format(
                script=CurrentShell.CreateScriptName("SimpleSchemaGenerator"),
                output_dir=os.path.join(_script_dir, "..", "GeneratedCode"),
                force=" /force" if force else "",
                verbose=" /verbose" if verbose else "",
            )

            for schema_filename_index, schema_filename in enumerate(schema_filenames):
                processing_dm.stream.write(
                    "'{}' ({} of {})...".format(
                        schema_filename,
                        schema_filename_index + 1,
                        len(schema_filenames),
                    ),
                )
                with processing_dm.stream.DoneManager() as this_dm:
                    command_line = command_line_template.format(
                        name=os.path.splitext(os.path.basename(schema_filename))[0],
                        input=schema_filename,
                    )

                    if verbose:
                        process_output_stream = this_dm.stream
                    else:
                        sink = StringIO()

                        process_output_stream = sink

                    this_dm.result = Process.Execute(command_line, process_output_stream)

                    if this_dm.result != 0 and not verbose:
                        this_dm.stream.write(sink.getvalue())  # type: ignore

        return dm.result


# ----------------------------------------------------------------------
@CommandLine.EntryPoint
@CommandLine.Constraints(                   # type: ignore
    output_stream=None,
)
def Clean(
    output_stream=sys.stdout,
):
    with StreamDecorator(output_stream).DoneManager(
        line_prefix="",
        prefix="\nResults: ",
        suffix="\n",
    ) as dm:
        output_dir = os.path.join(_script_dir, "..", "GeneratedCode")
        if not os.path.isdir(output_dir):
            dm.stream.write("The output dir '{}' does not exist.\n".format(output_dir))
            return dm.result

        dm.stream.write("Removing '{}'...".format(output_dir))
        with dm.stream.DoneManager():
            FileSystem.RemoveTree(output_dir)

        return dm.result


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        sys.exit(
            BuildImpl.Main(
                BuildImpl.Configuration(
                    name="Common_TriliumDev_Schemas",
                    requires_output_dir=False,
                ),
            ),
        )
    except KeyboardInterrupt:
        pass
