# ----------------------------------------------------------------------
# |
# |  RequestsSession.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-12 21:49:01
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the RequestsSession function"""

import os

from contextlib import contextmanager
from typing import Optional

import requests

import CommonEnvironment

from CommonEnvironmentEx.Package import InitRelativeImports

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

with InitRelativeImports():
    from .Config import Config


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
class SessionWrapper(object):
    # ----------------------------------------------------------------------
    def __init__(
        self,
        session: requests.Session,
        url_base: str,
    ):
        self.session                        = session
        self._url_base                      = url_base

    # ----------------------------------------------------------------------
    def __getattr__(self, name):
        return lambda *args, **kwargs: self(name, *args, **kwargs)

    # ----------------------------------------------------------------------
    def __call__(self, method, url, *args, **kwargs):
        response = getattr(self.session, method)(self._url_base + url, *args, **kwargs)

        response.raise_for_status()
        return response


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
@contextmanager
def RequestsSession(
    config: Config,
    etapi_token: Optional[str],
):
    with requests.Session() as session:
        session.headers.update(
            {
                "Authorization" : config.GetEtapiToken(etapi_token),
            },
        )

        yield SessionWrapper(session, "{}/ETAPI/".format(config.source_url))
