#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Python runtime component of shape.bzl. This file is not meant to be used
# directly, instead it contains supporting implementations for bzl/shape.bzl.
# See that file for motivations and usage documentation.

import importlib.resources
from typing import Type, TypeVar

import pydantic

# types that may be used by generated code (which imports * from this file for
# convenience)
from antlir.fs_utils import Path  # noqa: F401


S = TypeVar("S")


class ShapeMeta(pydantic.main.ModelMetaclass):
    def __new__(metacls, name, bases, dct):  # noqa: B902
        cls = super().__new__(metacls, name, bases, dct)
        # Only apply shape meta hacks to generated classes, not user-written
        # subclasses
        cls.__GENERATED_SHAPE__ = dct.get("__GENERATED_SHAPE__", False)
        if cls.__GENERATED_SHAPE__:
            cls.__name__ = repr(cls)
            cls.__qualname__ = repr(cls)

            # create an inner class `types` to make all the fields types usable
            # from a user of shape without having to know the cryptic generated
            # class names
            if "types" in dct or "types" in dct.get("__annotations__", {}):
                raise KeyError("'types' cannot be used as a shape field name")
            types_cls = {}
            for key, f in cls.__fields__.items():
                types_cls[key] = f.type_
                # pydantic already does some magic to extract list element
                # types and dict value types, but export tuples as a tuple of
                # types instead of typing.Tuple
                # NOTE: pydantic extracts the dict value type as the type,
                # which is a little bit of a strange interface, so that is
                # liable to change if we ever care about making a dict key
                # accessible (for example, if the key is a shape)
                if getattr(f.type_, "__origin__", None) == tuple:
                    types_cls[key] = f.type_.__args__
            cls.types = type("types", (object,), types_cls)

        return cls

    def __repr__(cls):  # noqa: B902
        """
        Human-readable class __repr__, that hides the ugly autogenerated
        shape class names.
        """
        fields = ", ".join(
            f"{key}={f._type_display()}" for key, f in cls.__fields__.items()
        )
        clsname = "shape"
        if not cls.__GENERATED_SHAPE__:
            clsname = cls.__name__
        return f"{clsname}({fields})"


class Shape(pydantic.BaseModel, metaclass=ShapeMeta):
    class Config:
        allow_mutation = False

    @classmethod
    def read_resource(cls: Type[S], package: str, name: str) -> S:
        with importlib.resources.open_text(package, name) as r:
            return cls.parse_raw(r.read())

    def __hash__(self):
        return hash((type(self), *self.__dict__.values()))

    def __repr__(self):
        """
        Human-readable instance __repr__, that hides the ugly autogenerated
        shape class names.
        """
        if not type(self).__GENERATED_SHAPE__:
            return super().__repr__()
        # print only the set fields in the defined order
        fields = ", ".join(
            f"{key}={repr(getattr(self, key))}" for key in self.__fields__
        )
        return f"shape({fields})"
