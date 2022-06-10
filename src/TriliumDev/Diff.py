# ----------------------------------------------------------------------
# |
# |  Diff.py
# |
# |  David Brownell <db@DavidBrownell.db@DavidBrownell.com>
# |      2022-05-18 10:40:37
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Calculates the differences between 2 TriliumNote objects"""

import os

from enum import auto, Enum
from typing import cast, Callable, Dict, Generator, List, Optional, Set, Tuple, Union

from dataclasses import dataclass

import CommonEnvironment
from CommonEnvironment.YamlRepr import ObjectReprImplBase

from CommonEnvironmentEx.Package import InitRelativeImports

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

with InitRelativeImports():
    from . import Activities
    from .Config import Config
    from .RequestsSession import SessionWrapper
    from .TriliumAttribute import TriliumAttribute
    from .TriliumNoteShort import TriliumNoteShort


# ----------------------------------------------------------------------
class DiffType(Enum):
    content_type_changed                    = auto()

    parent_id_added                         = auto()
    parent_id_removed                       = auto()

    attribute_added                         = auto()
    attribute_removed                       = auto()
    attribute_changed                       = auto()

    content_changed                         = auto()

    child_added                             = auto()
    child_removed                           = auto()
    child_changed                           = auto()
    child_link_changed                      = auto()


# ----------------------------------------------------------------------
@dataclass(frozen=True, repr=False)
class DiffInfo(ObjectReprImplBase):
    # ----------------------------------------------------------------------
    # |
    # |  Public Types
    # |
    # ----------------------------------------------------------------------
    ToActivityResultType                    = Callable[
        [
            Config,
            SessionWrapper,
            Callable[[str], None],          # status_functor
        ],
        None,
    ]

    # ----------------------------------------------------------------------
    # |
    # |  Public Data
    # |
    # ----------------------------------------------------------------------
    diff_type: DiffType

    reference: TriliumNoteShort
    actual: TriliumNoteShort

    context: Union[
        None,                               # content_type_changed
                                            # content_changed

        str,                                # parent_id_added
                                            # parent_id_removed

        TriliumAttribute,                   # attribute_added
                                            # attribute_removed
                                            # attribute_changed

        Tuple[str, TriliumNoteShort],       # child_added
                                            # child_removed
                                            # child_changed
                                            # child_link_changed
    ]

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
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
        display_note_func = lambda note: note.id

        ObjectReprImplBase.__init__(
            self,
            reference=display_note_func,    # type: ignore
            actual=display_note_func,       # type: ignore
            context=None,
        )

    # ----------------------------------------------------------------------
    def ToString(self) -> str:
        if self.diff_type == DiffType.content_type_changed:
            return "[{}] Content type changed".format(self.actual.id)

        if self.diff_type == DiffType.parent_id_added:
            return "[{}] Parent '{}' was added".format(self.actual.id, self.context)

        if self.diff_type == DiffType.parent_id_removed:
            return "[{}] Parent '{}' was removed".format(self.actual.id, self.context)

        if self.diff_type == DiffType.attribute_added:
            return "[{}] Attribute '{}' was added".format(self.actual.id, cast(TriliumAttribute, self.context).id)

        if self.diff_type == DiffType.attribute_removed:
            return "[{}] Attribute '{}' was removed".format(self.actual.id, cast(TriliumAttribute, self.context).id)

        if self.diff_type == DiffType.attribute_changed:
            return "[{}] Attribute '{}' changed".format(self.actual.id, cast(TriliumAttribute, self.context).id)

        if self.diff_type == DiffType.content_changed:
            return "[{}] Content changed".format(self.actual.id)

        if self.diff_type == DiffType.child_added:
            context = cast(Tuple[str, TriliumNoteShort], self.context)
            return "[{}] Child linked as '{}' was added to '{}'".format(self.actual.id, context[0], context[1].id)

        if self.diff_type == DiffType.child_removed:
            context = cast(Tuple[str, TriliumNoteShort], self.context)
            return "[{}] Child linked as '{}' was removed to '{}'".format(self.actual.id, context[0], context[1].id)

        if self.diff_type == DiffType.child_changed:
            context = cast(Tuple[str, TriliumNoteShort], self.context)
            return "[{}] Child linked as '{}' was changed to '{}'".format(self.actual.id, context[0], context[1].id)

        if self.diff_type == DiffType.child_link_changed:
            context = cast(Tuple[str, TriliumNoteShort], self.context)
            return "[{}] Child '{}'s link was changed to '{}'".format(self.actual.id, context[1].id, context[0])

        assert False, self.diff_type

    # ----------------------------------------------------------------------
    def ToActivity(self) -> "DiffInfo.ToActivityResultType":
        if self.diff_type == DiffType.content_type_changed:
            raise Exception("TODO: 'content_type_changed' not supported yet")

        if self.diff_type == DiffType.parent_id_added:
            raise Exception("TODO: 'parent_id_added' not supported yet")

        if self.diff_type == DiffType.parent_id_removed:
            raise Exception("TODO: 'parent_id_removed' not supported yet")

        if self.diff_type == DiffType.attribute_added:
            raise Exception("TODO: 'attribute_added' not supported yet")

        if self.diff_type == DiffType.attribute_removed:
            raise Exception("TODO: 'attribute_removed' not supported yet")

        if self.diff_type == DiffType.attribute_changed:
            raise Exception("TODO: 'attribute_changed' not supported yet")

        if self.diff_type == DiffType.content_changed:
            return lambda config, session, on_status_update: Activities.PushContent(config, session, on_status_update, self.actual)

        if self.diff_type == DiffType.child_added:
            raise Exception("TODO: 'child_added' not supported yet")

        if self.diff_type == DiffType.child_removed:
            raise Exception("TODO: 'child_removed' not supported yet")

        if self.diff_type == DiffType.child_changed:
            raise Exception("TODO: 'child_changed' not supported yet")

        if self.diff_type == DiffType.child_link_changed:
            raise Exception("TODO: 'child_link_changed' not supported yet")

        assert False, self.diff_type


# ----------------------------------------------------------------------
def EnumDifferences(
    config: Config,
    reference: TriliumNoteShort,
    actual: TriliumNoteShort,
) -> Generator[DiffInfo, None, None]:
    yield from _EnumDifferencesImpl(config, reference, actual, set(), set())


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _EnumDifferencesImpl(
    config: Config,
    reference: TriliumNoteShort,
    actual: TriliumNoteShort,
    reference_processed: Set[str],
    actual_processed: Set[str],
) -> Generator[DiffInfo, None, None]:
    if reference.id in reference_processed:
        assert actual.id in actual_processed
        return

    reference_processed.add(reference.id)
    actual_processed.add(actual.id)

    # Content
    if actual.note_type:
        if actual.mime_type != reference.mime_type:
            yield DiffInfo.Create(DiffType.content_type_changed, reference, actual, None)
        elif actual.content_hash != reference.content_hash:
            yield DiffInfo.Create(DiffType.content_changed, reference, actual, None)

    # Parent Ids
    actual_parent_ids = set(actual.parent_ids)
    reference_parent_ids = set(reference.parent_ids)

    for parent_id in actual_parent_ids.difference(reference_parent_ids):
        yield DiffInfo.Create(DiffType.parent_id_added, reference, actual, parent_id)

    for parent_id in reference_parent_ids.difference(actual_parent_ids):
        yield DiffInfo.Create(DiffType.parent_id_removed, reference, actual, parent_id)

    # Attributes
    actual_attributes: Dict[str, TriliumAttribute] = {attribute.id: attribute for attribute in actual.attributes}
    reference_attributes: Dict[str, TriliumAttribute] = {attribute.id: attribute for attribute in reference.attributes}

    for actual_attribute_id, actual_attribute in actual_attributes.items():
        reference_attribute = reference_attributes.get(actual_attribute_id, None)

        if reference_attribute is None:
            yield DiffInfo.Create(DiffType.attribute_added, reference, actual, actual_attribute)
            continue

        if actual_attribute != reference_attribute:
            yield DiffInfo.Create(DiffType.attribute_changed, reference, actual, actual_attribute)

    for reference_attribute_id, reference_attribute in reference_attributes.items():
        if reference_attribute_id not in actual_attributes:
            yield DiffInfo.Create(DiffType.attribute_removed, reference, actual, reference_attribute)

    # Children
    children_to_enumerate: List[Tuple[TriliumNoteShort, TriliumNoteShort]] = []

    unmatched_reference_child_links: Set[str] = set(reference.children.keys())

    for actual_child_link, actual_child in actual.children.items():
        reference_child: Optional[TriliumNoteShort] = None
        reference_child_link: Optional[str] = None

        reference_child = reference.children.get(actual_child_link, None)
        if reference_child is not None:
            reference_child_link = actual_child_link
        else:
            # Attempt to find the child under a different link name
            for potential_reference_child_link, reference_child_item in reference.children.items():
                if reference_child_item.id == actual_child.id:
                    reference_child_link = potential_reference_child_link
                    reference_child = reference_child_item

                    break

        if reference_child is None:
            assert reference_child_link is None

            yield DiffInfo.Create(DiffType.child_added, reference, actual, (actual_child_link, actual_child))
            continue

        assert reference_child_link is not None
        unmatched_reference_child_links.remove(reference_child_link)

        # Defer the enumeration of the children so that we can generate all the differences with this
        # note before generating differences with its children.
        children_to_enumerate.append((reference_child, actual_child))

    for reference_child_link in unmatched_reference_child_links:
        reference_child = reference.children[reference_child_link]

        yield DiffInfo.Create(DiffType.child_removed, reference, actual, (reference_child_link, reference_child))

    # Enumerate any children
    for reference_child, actual_child in children_to_enumerate:
        yield from _EnumDifferencesImpl(
            config,
            reference_child,
            actual_child,
            reference_processed,
            actual_processed,
        )
