# ----------------------------------------------------------------------
# |
# |  TriliumAttribute.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-12 21:39:49
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the TriliumAttribute object"""

import os
import sys

from contextlib import ExitStack
from typing import Any, List, Optional

from dataclasses import dataclass

import CommonEnvironment
from CommonEnvironment.YamlRepr import ObjectReprImplBase

from CommonEnvironment.TypeInfo.FundamentalTypes.DateTimeTypeInfo import DateTimeTypeInfo
from CommonEnvironment.TypeInfo.FundamentalTypes.Serialization.StringSerialization import StringSerialization

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

sys.path.insert(0, os.path.join(_script_dir, "Schemas", "GeneratedCode"))
with ExitStack() as exit_stack:
    exit_stack.callback(lambda: sys.path.pop(0))

    import TriliumAttribute_PythonYamlSerialization as Serialization  # type: ignore  # pylint: disable=import-error


# ----------------------------------------------------------------------
@dataclass(repr=False)
class TriliumAttribute(ObjectReprImplBase):
    id: str
    attr_type: str
    name: str
    value: Optional[Any]
    position: int
    is_inheritable: bool

    # ----------------------------------------------------------------------
    @classmethod
    def Create(cls, *args, **kwargs):
        """\
        This hack avoids pylint warnings associated with invoking dynamically
        generated constructors with too many methods.
        """
        return cls(*args, **kwargs)

    # ----------------------------------------------------------------------
    @classmethod
    def FromResponse(cls, response):
        return cls.Create(
            id=response["attributeId"],
            attr_type=response["type"],
            name=response["name"],
            value=response["value"],
            position=response["position"],
            is_inheritable=response["isInheritable"],
        )

    # ----------------------------------------------------------------------
    def __post_init__(self):
        super(TriliumAttribute, self).__init__(
            include_root_class_info=False,
            include_class_info=False,
            include_id=False,
            include_methods=False,
            include_private=False,
        )

    # ----------------------------------------------------------------------
    def Serialize(self) -> str:
        return Serialization.Serialize_Attribute(
            self,
            to_string=True,
            pretty_print=True,
            process_additional_data=True,
        )

    # ----------------------------------------------------------------------
    @staticmethod
    def SerializeItems(
        items: List["TriliumAttribute"],
    ) -> str:
        return Serialization.Serialize_Attributes(
            items,
            to_string=True,
            pretty_print=True,
            process_additional_data=True,
        )

    # ----------------------------------------------------------------------
    @classmethod
    def DeserializeItem(
        cls,
        content: str,
    ) -> "TriliumAttribute":
        return cls._DeserializedObjectToCls(Serialization.Deserialize_Attribute(content))

    # ----------------------------------------------------------------------
    @classmethod
    def DeserializeItems(
        cls,
        content: str,
    ) -> List["TriliumAttribute"]:
        return [
            cls._DeserializedObjectToCls(obj)
            for obj in Serialization.Deserialize_Attributes(content)
        ]

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    _date_time_type_info                    = DateTimeTypeInfo()

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def _DeserializedObjectToCls(cls, obj) -> "TriliumAttribute":
        data = obj.__dict__

        del data["_attribute_names"]

        return cls(**data)
