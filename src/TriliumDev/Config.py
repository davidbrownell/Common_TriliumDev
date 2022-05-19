# ----------------------------------------------------------------------
# |
# |  Config.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-12 21:29:12
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the Config object"""

import os
import textwrap

from typing import Optional

from dataclasses import dataclass
import rtyaml

import CommonEnvironment
from CommonEnvironment import FileSystem
from CommonEnvironment.Shell.All import CurrentShell
from CommonEnvironment.StreamDecorator import StreamDecoratorException
from CommonEnvironment.YamlRepr import ObjectReprImplBase

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
@dataclass(frozen=True, repr=False)
class Config(ObjectReprImplBase):
    CONFIG_FILENAME                         = "config.yaml"

    ETAPI_TOKEN_FILENAME                    = "etapi_token.bin"

    DEVELOPMENT_DIRECTORY                   = ".trilium_dev"
    HIERARCHY_DIRECTORY                     = "hierarchy"
    STORE_DIRECTORY                         = "store"

    ETAPI_ENVIRONMENT_VARIABLE_NAME         = "TRILIUM_DEV_ETAPI_TOKEN"

    ETAPI_TOKEN_DESC                        = textwrap.dedent(
        """\
        The token used to connect to a Trilium instance ETAPI server. This value can be provided
        using any of these conventions:

            - As a command-line parameter
            - In the environment variable '{env_var_name}'
            - As previously saved via '{script_name} SaveEtapiToken <profile_name> <token>'

        To generate a new ETAPI token:

            1) Open Trilium
            2) Click the Trilium logo
            3) Select 'Options'
            4) Select the 'ETAPI' tab
            5) Click the 'Create new ETAPI Token' button
            6) Enter a name for the token (e.g. "Trilium Dev Services")
            7) Click the 'OK' button
            8) Copy the token and save it according to one of the usage conventions outlined above.

        """,
    ).format(
        env_var_name=ETAPI_ENVIRONMENT_VARIABLE_NAME,
        script_name=_script_name,
    )

    # ----------------------------------------------------------------------
    working_directory: str
    source_url: str
    root_note_id: str

    # ----------------------------------------------------------------------
    @classmethod
    def Create(cls, *args, **kwargs):
        """\
        This hack avoids pylint warnings associated with invoking dynamically
        generated constructors with too many methods.
        """
        return cls(*args, **kwargs)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        super(Config, self).__init__(
            CONFIG_FILENAME=None,
            ETAPI_TOKEN_FILENAME=None,
            DEVELOPMENT_DIRECTORY=None,
            HIERARCHY_DIRECTORY=None,
            STORE_DIRECTORY=None,
            ETAPI_ENVIRONMENT_VARIABLE_NAME=None,
            ETAPI_TOKEN_DESC=None,

            working_directory=None,

            DevelopmentDirectory=None,
            HierarchyDirectory=None,
            StoreDirectory=None,
        )

    # ----------------------------------------------------------------------
    @property
    def DevelopmentDirectory(self) -> str:
        return os.path.join(self.working_directory, self.__class__.DEVELOPMENT_DIRECTORY)

    @property
    def HierarchyDirectory(self) -> str:
        return os.path.join(self.working_directory, self.__class__.HIERARCHY_DIRECTORY)

    @property
    def StoreDirectory(self) -> str:
        return os.path.join(self.working_directory, self.__class__.STORE_DIRECTORY)

    # ----------------------------------------------------------------------
    def Save(
        self,
        *,
        overwrite: bool,
    ) -> None:
        config_filename = self._CreateConfigFilename(self.working_directory)

        if os.path.isfile(config_filename):
            if not overwrite:
                raise StreamDecoratorException("The configuration filename '{}' already exists; specify '/overwrite' on the command line to overwrite it.".format(config_filename))
        else:
            FileSystem.MakeDirs(os.path.dirname(config_filename))

        with open(config_filename, "w") as f:
            f.write(
                self.ToYamlString(
                    include_root_class_info=False,
                    include_class_info=False,
                    include_id=False,
                    include_methods=False,
                    include_private=False,
                ),
            )

        with open(
            os.path.join(
                self.working_directory,
                self.__class__.DEVELOPMENT_DIRECTORY,
                "readme.txt",
            ),
            "w",
        ) as f:
            f.write(
                textwrap.dedent(
                    """\
                    The files in this directory contain information that is specific to your
                    local development environment; it may also CONTAIN SECRETS in the form
                    of persisted ETAPI tokens.

                    While attempts have been made to secure this information, the contents
                    of this directory should...

                        ...NEVER BE MADE AVAILABLE TO ANYONE ELSE!
                        ...NEVER BE USED ON ANOTHER MACHINE!
                        ...NEVER BE ADDED TO A VERSION CONTROL SYSTEM!
                    """,
                ),
            )

    # ----------------------------------------------------------------------
    @classmethod
    def Load(
        cls,
        working_directory: str,
    ) -> "Config":
        config_filename = cls._CreateConfigFilename(working_directory)

        if not os.path.isfile(config_filename):
            raise StreamDecoratorException(
                "The filename '{}' does not exist. Run 'TriliumDev Init' to initialize a local development environment.".format(
                    config_filename,
                ),
            )

        with open(config_filename, "r") as f:
            content = rtyaml.load(f)

        content["working_directory"] = working_directory

        return cls(**content)

    # ----------------------------------------------------------------------
    def GetEtapiToken(
        self,
        etapi_token: Optional[str]
    ) -> str:
        if etapi_token:
            return etapi_token

        etapi_token = os.getenv(self.__class__.ETAPI_ENVIRONMENT_VARIABLE_NAME)
        if etapi_token is not None:
            return etapi_token

        # Load from file
        token_filename = self._CreateEtapiTokenFilename()

        if os.path.isfile(token_filename):
            with open(token_filename, "rb") as f:
                etapi_bytes = f.read()

            if CurrentShell.CategoryName == "Windows":
                import win32crypt
                etapi_bytes = win32crypt.CryptUnprotectData(etapi_bytes, None, None, None, 0)
                assert etapi_bytes is not None

                etapi_bytes = etapi_bytes[1]

            return etapi_bytes.decode()

        raise StreamDecoratorException(
            textwrap.dedent(
                """\
                An ETAPI token is required.

                {}
                """,
            ).format(
                self.__class__.ETAPI_TOKEN_DESC,
            ),
        )

    # ----------------------------------------------------------------------
    def SaveEtapiToken(
        self,
        etapi_token: str,
    ) -> None:
        etapi_bytes = etapi_token.encode()

        if CurrentShell.CategoryName == "Windows":
            import win32crypt
            etapi_bytes = win32crypt.CryptProtectData(etapi_token.encode(), "", None, None, None, 0)

        token_filename = self._CreateEtapiTokenFilename()

        with open(token_filename, "wb") as f:
            f.write(etapi_bytes)

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def _CreateConfigFilename(
        cls,
        working_directory: str,
    ) -> str:
        return os.path.join(
            working_directory,
            cls.DEVELOPMENT_DIRECTORY,
            cls.CONFIG_FILENAME,
        )

    # ----------------------------------------------------------------------
    def _CreateEtapiTokenFilename(self) -> str:
        return os.path.join(
            self.working_directory,
            self.__class__.DEVELOPMENT_DIRECTORY,
            self.__class__.ETAPI_TOKEN_FILENAME,
        )


# ----------------------------------------------------------------------
@dataclass(frozen=True, repr=False)
class DockerConfig(ObjectReprImplBase):
    CONFIG_FILENAME                         = "docker_config.yaml"

    # ----------------------------------------------------------------------
    docker_tag: Optional[str]
    docker_port: int

    # ----------------------------------------------------------------------
    @classmethod
    def Create(cls, *args, **kwargs):
        """\
        This hack avoids pylint warnings associated with invoking dynamically
        generated constructors with too many methods.
        """
        return cls(*args, **kwargs)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        super(DockerConfig, self).__init__(
            CONFIG_FILENAME=None,
        )

    # ----------------------------------------------------------------------
    def Save(
        self,
        working_directory: str,
        *,
        overwrite: bool,
    ) -> None:
        config_filename = self._CreateConfigFilename(working_directory)

        if os.path.isfile(config_filename):
            if not overwrite:
                raise StreamDecoratorException("The configuration filename '{}' already exists; specify '/overwrite' on the command line to overwrite it.".format(config_filename))
        else:
            FileSystem.MakeDirs(os.path.dirname(config_filename))

        with open(config_filename, "w") as f:
            f.write(
                self.ToYamlString(
                    include_root_class_info=False,
                    include_class_info=False,
                    include_id=False,
                    include_methods=False,
                    include_private=False,
                ),
            )

    # ----------------------------------------------------------------------
    @classmethod
    def Load(
        cls,
        working_directory: str,
    ) -> "DockerConfig":
        config_filename = cls._CreateConfigFilename(working_directory)

        if not os.path.isfile(config_filename):
            raise StreamDecoratorException(
                "The filename '{}' does not exist. Run 'TriliumDev.py Init' to initialize a local development environment.".format(
                    config_filename,
                ),
            )

        with open(config_filename, "r") as f:
            content = rtyaml.load(f)

        return cls(**content)

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def _CreateConfigFilename(
        cls,
        working_directory: str,
    ) -> str:
        return os.path.join(
            working_directory,
            Config.DEVELOPMENT_DIRECTORY,
            cls.CONFIG_FILENAME,
        )
