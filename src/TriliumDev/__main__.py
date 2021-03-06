# ----------------------------------------------------------------------
# |
# |  __main__.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-12 07:00:26
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Tools that help when developing extensions within Trilium (https://github.com/zadam/trilium)."""

import multiprocessing
import os
import re
import sys
import textwrap

from typing import Callable, Dict, Optional, Tuple

import inflect as inflect_mod

import CommonEnvironment
from CommonEnvironment import CommandLine
from CommonEnvironment import FileSystem
from CommonEnvironment.Shell.All import CurrentShell
from CommonEnvironment.Shell import Commands
from CommonEnvironment.StreamDecorator import StreamDecorator, StreamDecoratorException
from CommonEnvironment import StringHelpers
from CommonEnvironment import TaskPool

from CommonEnvironmentEx.Package import InitRelativeImports

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

with InitRelativeImports():
    from . import Activities
    from .Config import Config, DockerConfig
    from . import Diff as DiffModule
    from . import LocalFilesystem
    from . import Pull as PullModule
    from . import RequestsSession


# ----------------------------------------------------------------------
inflect                                     = inflect_mod.engine()

DEFAULT_DEV_PORT                            = 8010


# ----------------------------------------------------------------------
_etapi_token_parameter                      = CommandLine.EntryPoint.Parameter("The ETAPI token to use.")


# ----------------------------------------------------------------------
def CommandLineSuffix() -> str:
    return Config.ETAPI_TOKEN_DESC


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
# TODO: Dev
# TODO: Publish

@CommandLine.EntryPoint(
    url=CommandLine.EntryPoint.Parameter("The url to a dev server used when syncing content."),
    etapi_token=_etapi_token_parameter,
    root_note_id=CommandLine.EntryPoint.Parameter("The Trilium note id of the note to use as the root when syncing content. The 'root' note will be used if none is specified."),
    no_pull=CommandLine.EntryPoint.Parameter("Do not pull content from the server."),
)                                           # type: ignore
@CommandLine.Constraints(                   # type: ignore
    url=CommandLine.UriTypeInfo(),
    etapi_token=CommandLine.StringTypeInfo(
        arity="?",
    ),
    root_note_id=CommandLine.StringTypeInfo(
        arity="?",
    ),
    working_directory=CommandLine.DirectoryTypeInfo(
        ensure_exists=False,
        arity="?",
    ),
    output_stream=None,
)
def Init(
    url,
    etapi_token=None,
    root_note_id="root",
    working_directory=os.getcwd(),
    no_pull=False,
    overwrite=False,
    output_stream=sys.stdout,
):
    """Initializes a local Trilium development environment using an existing development server. See 'InitDevServer' to create a development server and initialize a development environment against it."""

    with StreamDecorator(output_stream).DoneManager(
        line_prefix="",
        prefix="\nResults: ",
        suffix="\n",
    ) as dm:
        _InitImpl(
            url.ToString(),
            etapi_token,
            root_note_id,
            working_directory,
            dm.stream,
            no_pull=no_pull,
            overwrite=overwrite,
        )

        return dm.result


# ----------------------------------------------------------------------
@CommandLine.EntryPoint(
    trilium_docker_tag=CommandLine.EntryPoint.Parameter("The Trilium docker image tag used when creating the container; 'latest' is used if a tag is not specified."),
    docker_port=CommandLine.EntryPoint.Parameter("Port exposed by the docker container."),
    etapi_token=_etapi_token_parameter,
    root_note_id=CommandLine.EntryPoint.Parameter("The Trilium note id of the note to use as the root when syncing content. The 'root' note will be used if none is specified."),
    no_init=CommandLine.EntryPoint.Parameter("Do not initialize the local development environment."),
    no_pull=CommandLine.EntryPoint.Parameter("Do not pull content from the server."),
    refresh=CommandLine.EntryPoint.Parameter("Refreshes the local development environment by syncing with the Trilium data directory."),
    yes=CommandLine.EntryPoint.Parameter("Skip all prompts and continue."),
)                                           # type: ignore
@CommandLine.Constraints(                   # type: ignore
    trilium_data_directory=CommandLine.DirectoryTypeInfo(
        arity="?",
    ),
    trilium_docker_tag=CommandLine.StringTypeInfo(
        arity="?",
    ),
    docker_port=CommandLine.IntTypeInfo(
        min=1,
        arity="?",
    ),
    etapi_token=CommandLine.StringTypeInfo(
        arity="?",
    ),
    root_note_id=CommandLine.StringTypeInfo(
        arity="?",
    ),
    working_directory=CommandLine.DirectoryTypeInfo(
        ensure_exists=False,
        arity="?",
    ),
    output_stream=None,
)
def InitDevServer(
    trilium_data_directory=None,
    trilium_docker_tag=None,
    docker_port=None,
    etapi_token=None,
    root_note_id="root",
    working_directory=os.getcwd(),
    refresh=False,
    yes=False,
    no_init=False,
    no_pull=False,
    overwrite=False,
    output_stream=sys.stdout,
):
    """Copies Trilium's data directory, creates a docker instance to serve the copied content, and initializes a local Trilium development environment against that server."""

    with StreamDecorator(output_stream).DoneManager(
        line_prefix="",
        prefix="\nResults: ",
        suffix="\n",
    ) as dm:
        if trilium_data_directory is None:
            if CurrentShell.CategoryName == "Windows":
                # See if there is an Electron directory
                app_data = os.getenv("APPDATA")

                if app_data is not None:
                    potential_data_directory = os.path.realpath(os.path.join(app_data, "trilium-data"))
                    if os.path.isdir(potential_data_directory):
                        trilium_data_directory = potential_data_directory

        if trilium_data_directory is None:
            raise StreamDecoratorException("A default Trilium directory could not be found; please specify a directory on the command line.")

        if refresh:
            try:
                config = Config.Load(working_directory)
                docker_config = DockerConfig.Load(working_directory)

                trilium_docker_tag = docker_config.docker_tag
                docker_port = docker_config.docker_port

                root_note_id = config.root_note_id

                overwrite = True

            except Exception:
                raise StreamDecoratorException("Unable to refresh the information in '{}'; please initialize the local development environment again.".format(working_directory))

        dm.stream.write("\nProcessing the Trilium data directory at '{}'...".format(trilium_data_directory))
        with dm.stream.DoneManager(
            suffix="\n",
        ) as data_dm:
            for filename in [
                "config.ini",
                "document.db",
            ]:
                filename = os.path.join(trilium_data_directory, filename)
                if not os.path.isfile(filename):
                    raise StreamDecoratorException("'{}' does not appear to be a valid Trilium data directory.".format(trilium_data_directory))

            # Get the server port from config.ini
            config_filename = os.path.join(trilium_data_directory, "config.ini")

            config_port: Optional[int] = None
            port_regex = re.compile(r"^\s*port\s*=\s*(?P<port>\d+)\s*$")

            for line in open(config_filename, "r").readlines():
                potential_match = port_regex.match(line)
                if potential_match:
                    config_port = int(potential_match.group("port"))
                    break

            if config_port is None:
                raise StreamDecoratorException("Port information could not be found in '{}'.".format(config_filename))
            if docker_port is None:
                docker_port = config_port

            assert config_port is not None

            dev_output_directory = os.path.join(working_directory, Config.DEVELOPMENT_DIRECTORY)

            dest_directory = os.path.join(dev_output_directory, "dev_server_store")
            if os.path.isdir(dest_directory) and not overwrite:
                raise StreamDecoratorException("The destination directory '{}' already exists; specify '/overwrite' on the command line to overwrite it.".format(dest_directory))

            with data_dm.stream.SingleLineDoneManager("Copying content...") as copy_dm:
                FileSystem.RemoveTree(dest_directory)
                FileSystem.MakeDirs(os.path.dirname(dest_directory))

                FileSystem.CopyTree(
                    trilium_data_directory,
                    dest_directory,
                    optional_output_stream=copy_dm.stream,
                )

            # Note: No need to disable sync, as this version of Trilium running in the docker container
            # will not have access to the outside world, and therefore will not be able to sync.

            # Create a script to launch docker
            docker_script_filename = os.path.join(dev_output_directory, CurrentShell.CreateScriptName("docker"))

            if CurrentShell.CategoryName == "Windows":
                # Make the path relative
                script_dest_directory = r"%~dp0\dev_server_store"
            else:
                # It turns out that it is a bit challenging to get the dirname of a running script reliably in other operating
                # systems. Use the fullpath.
                script_dest_directory = dest_directory

            with open(docker_script_filename, "w") as f:
                f.write(
                    CurrentShell.GenerateCommands(
                        [
                            Commands.Execute(
                                'docker run -it --rm -p {docker_port}:{config_port} -v "{script_dest_directory}:/home/node/trilium-data" zadam/trilium{tag}'.format(
                                    docker_port=docker_port,
                                    config_port=config_port,
                                    script_dest_directory=script_dest_directory,
                                    tag=":{}".format(trilium_docker_tag) if trilium_docker_tag is not None else "",
                                ),
                            ),
                        ],
                    ),
                )

            CurrentShell.MakeFileExecutable(docker_script_filename)

            DockerConfig.Create(trilium_docker_tag, docker_port).Save(
                working_directory,
                overwrite=overwrite,
            )

        if not no_init:
            dm.stream.write("Initializing the local development environment...")
            with dm.stream.DoneManager() as init_dm:
                if not yes:
                    input(
                        StringHelpers.LeftJustify(
                            textwrap.dedent(
                                """\


                                Please start the docker container using '{}'

                                <Press Enter to continue>
                                """,
                            ).format(
                                docker_script_filename,
                            ).rstrip(),
                            4,
                            skip_first_line=False,
                        ),
                    )

                _InitImpl(
                    "http://localhost:{}".format(docker_port),
                    etapi_token,
                    root_note_id,
                    working_directory,
                    output_stream=init_dm.stream,
                    no_pull=no_pull,
                    overwrite=overwrite,
                )

        return dm.result


# ----------------------------------------------------------------------
@CommandLine.EntryPoint(
    etapi_token=_etapi_token_parameter,
)                                           # type: ignore
@CommandLine.Constraints(                   # type: ignore
    etapi_token=CommandLine.StringTypeInfo(),
    working_directory=CommandLine.DirectoryTypeInfo(
        arity="?",
    ),
    output_stream=None,
)
def SetEtapiToken(
    etapi_token,
    working_directory=os.getcwd(),
    output_stream=sys.stdout,
):
    """Sets an ETAPI token for use in the local development environment."""

    with StreamDecorator(output_stream).DoneManager(
        line_prefix="",
        prefix="\nResults: ",
        suffix="\n",
    ) as dm:
        config = Config.Load(working_directory)

        config.SaveEtapiToken(etapi_token)

        dm.stream.write("The ETAPI token has been saved.\n")

        return dm.result


# ----------------------------------------------------------------------
@CommandLine.EntryPoint(
    etapi_token=_etapi_token_parameter,
)                                           # type: ignore
@CommandLine.Constraints(                   # type: ignore
    working_directory=CommandLine.DirectoryTypeInfo(
        arity="?",
    ),
    etapi_token=CommandLine.StringTypeInfo(
        arity="?",
    ),
    output_stream=None,
)
def Pull(
    working_directory=os.getcwd(),
    etapi_token=None,
    overwrite=False,
    output_stream=sys.stdout,
):
    """Pulls content from a Trilium server"""

    with StreamDecorator(output_stream).DoneManager(
        line_prefix="",
        prefix="\nResults: ",
        suffix="\n",
    ) as dm:
        PullModule.Pull(
            Config.Load(working_directory),
            etapi_token,
            dm,
            overwrite_store=overwrite,
        )

        return dm.result


# ----------------------------------------------------------------------
@CommandLine.EntryPoint(
    etapi_token=_etapi_token_parameter,
)                                           # type: ignore
@CommandLine.Constraints(                   # type: ignore
    working_directory=CommandLine.DirectoryTypeInfo(
        arity="?",
    ),
    etapi_token=CommandLine.StringTypeInfo(
        arity="?",
    ),
    output_stream=None,
)
def Push(
    working_directory=os.getcwd(),
    etapi_token=None,
    output_stream=sys.stdout,
):
    """Pushes content to a Trilium server"""

    with StreamDecorator(output_stream).DoneManager(
        line_prefix="",
        prefix="\nResults: ",
        suffix="\n",
    ) as dm:
        config = Config.Load(working_directory)

        dm.stream.write("Loading reference notes...")
        with dm.stream.DoneManager(
            suffix="\n",
        ) as reference_dm:
            reference_notes = PullModule.GetNotes(
                config,
                etapi_token,
                reference_dm,
                lambda *args, **kwargs: None,
            )

            if reference_dm.result != 0:
                return reference_dm.result

        dm.stream.write("Loading local notes...")
        with dm.stream.DoneManager(
            suffix="\n",
        ) as local_dm:
            actual_notes = LocalFilesystem.GetNotes(config, local_dm)

            if local_dm.result != 0:
                return local_dm.result

            assert actual_notes is not None

        dm.stream.write("Comparing notes...")
        with dm.stream.DoneManager(
            suffix="\n",
        ) as compare_dm:
            activities: Dict[
                str,
                Callable[[RequestsSession.SessionWrapper, Callable[[str], None]], None]
            ] = {}

            for difference in DiffModule.EnumDifferences(config, reference_notes, actual_notes):
                if difference.diff_type == DiffModule.DiffType.content_type_changed:
                    raise Exception("TODO: 'content_type_changed' not supported yet")

                if difference.diff_type == DiffModule.DiffType.parent_id_added:
                    raise Exception("TODO: 'parent_id_added' not supported yet")

                if difference.diff_type == DiffModule.DiffType.parent_id_removed:
                    raise Exception("TODO: 'parent_id_removed' not supported yet")

                if difference.diff_type == DiffModule.DiffType.attribute_added:
                    raise Exception("TODO: 'attribute_added' not supported yet")

                if difference.diff_type == DiffModule.DiffType.attribute_removed:
                    raise Exception("TODO: 'attribute_removed' not supported yet")

                if difference.diff_type == DiffModule.DiffType.attribute_changed:
                    raise Exception("TODO: 'attribute_changed' not supported yet")

                if difference.diff_type == DiffModule.DiffType.content_changed:
                    activities[difference.ToString()] = (lambda session, on_status_update, note=difference.actual:
                        Activities.PushContent(config, session, note, on_status_update)
                    )

                if difference.diff_type == DiffModule.DiffType.child_added:
                    raise Exception("TODO: 'child_added' not supported yet")

                if difference.diff_type == DiffModule.DiffType.child_removed:
                    raise Exception("TODO: 'child_removed' not supported yet")

                if difference.diff_type == DiffModule.DiffType.child_changed:
                    raise Exception("TODO: 'child_changed' not supported yet")

                if difference.diff_type == DiffModule.DiffType.child_link_changed:
                    raise Exception("TODO: 'child_link_changed' not supported yet")

            if not activities:
                compare_dm.stream.write("No differences were detected.\n")
                return compare_dm.result

        with dm.stream.SingleLineDoneManager("Pushing {}...".format(inflect.no("change", len(activities)))) as activities_dm:
            with RequestsSession.RequestsSession(config, etapi_token) as session:
                # ----------------------------------------------------------------------
                def Execute(
                    data: Tuple[str, Callable[[RequestsSession.SessionWrapper, Callable[[str], None]], None]],
                    on_status_update: Callable[[str], None],
                ) -> None:
                    data[1](session, on_status_update)

                # ----------------------------------------------------------------------

                TaskPool.Transform(
                    list(activities.items()),
                    Execute,
                    activities_dm.stream,
                    num_concurrent_tasks=multiprocessing.cpu_count(),
                    name_functor=lambda index, item: item[0],
                )

        return dm.result


# ----------------------------------------------------------------------
@CommandLine.EntryPoint(
    etapi_token=_etapi_token_parameter,
)                                           # type: ignore
@CommandLine.Constraints(                   # type: ignore
    working_directory=CommandLine.DirectoryTypeInfo(
        arity="?",
    ),
    etapi_token=CommandLine.StringTypeInfo(
        arity="?",
    ),
    output_stream=None,
)
def Diff(
    working_directory=os.getcwd(),
    etapi_token=None,
    output_stream=sys.stdout,
):
    """Detects differences between local content and a Trilium server"""

    with StreamDecorator(output_stream).DoneManager(
        line_prefix="",
        prefix="\nResults: ",
        suffix="\n",
    ) as dm:
        config = Config.Load(working_directory)

        dm.stream.write("Loading reference notes...")
        with dm.stream.DoneManager(
            suffix="\n",
        ) as reference_dm:
            reference_notes = PullModule.GetNotes(
                config,
                etapi_token,
                reference_dm,
                lambda *args, **kwargs: None,
            )

            if reference_dm.result != 0:
                return reference_dm.result

        dm.stream.write("Loading local notes...")
        with dm.stream.DoneManager(
            suffix="\n",
        ) as local_dm:
            actual_notes = LocalFilesystem.GetNotes(config, local_dm)

            if local_dm.result != 0:
                return local_dm.result

            assert actual_notes is not None

        dm.stream.write("Comparing notes...")
        with dm.stream.DoneManager(
            suffix="\n",
        ) as compare_dm:
            for difference in DiffModule.EnumDifferences(config, reference_notes, actual_notes):
                compare_dm.stream.write("{}\n".format(difference.ToString()))
                compare_dm.result += 1

            if compare_dm.result == 0:
                compare_dm.stream.write("No differences were detected.\n")

        return dm.result


# ----------------------------------------------------------------------
@CommandLine.EntryPoint(
    etapi_token=_etapi_token_parameter,
)                                           # type: ignore
@CommandLine.Constraints(                   # type: ignore
    working_directory=CommandLine.DirectoryTypeInfo(
        arity="?",
    ),
    etapi_token=CommandLine.StringTypeInfo(
        arity="?",
    ),
    output_stream=None,
)
def Sync(
    working_directory=os.getcwd(),
    etapi_token=None,
    output_stream=sys.stdout,
):
    """Synchronizes local content and a Trilium server"""

    with StreamDecorator(output_stream).DoneManager(
        line_prefix="",
        prefix="\nResults: ",
        suffix="\n",
    ) as dm:
        config = Config.Load(working_directory)

        dm.stream.write("Syncing content...")
        with dm.stream.DoneManager() as sync_dm:
            raise NotImplementedError("TODO") # TODO

        return dm.result


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _InitImpl(
    url: str,
    etapi_token: Optional[str],
    root_note_id: str,
    working_directory: str,
    output_stream,
    *,
    no_pull: bool,
    overwrite: bool,
):
    output_stream.write("Saving configuration...")
    with output_stream.DoneManager() as dm:
        config = Config.Create(working_directory, url, root_note_id)

        config.Save(
            overwrite=overwrite,
        )

    if etapi_token is not None:
        output_stream.write("Saving ETAPI token...")
        with output_stream.DoneManager():
            config.SaveEtapiToken(etapi_token)

    if not no_pull:
        PullModule.Pull(
            config,
            etapi_token,
            dm,
            overwrite_store=overwrite,
        )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        sys.exit(
            CommandLine.Main()
        )
    except KeyboardInterrupt:
        pass
