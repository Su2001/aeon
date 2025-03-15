from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass

from aeon.core.types import (
    AbstractionType,
    BaseKind,
    BaseType,
    RefinedType,
    Top,
    TypeConstructor,
    TypePolymorphism,
    TypeVar,
)
from aeon.core.types import Kind
from aeon.core.types import StarKind
from aeon.core.types import Type


class TypingContext(ABC):
    def type_of(self, name: str) -> Type | None:
        assert False

    def with_var(self, name: str, type: Type) -> TypingContext:
        return VariableBinder(self, name, type)

    def with_typevar(self, name: str, kind: Kind) -> TypingContext:
        return TypeBinder(self, name, kind)

    def fresh_var(self):
        if not hasattr(self, "global_counter"):
            self.global_counter = 0
        self.global_counter += 1
        return f"fresh_{self.global_counter}"

    def kind_of(self, ty: Type) -> Kind:
        match ty:
            case BaseType(_) | Top() | RefinedType(_, BaseType(_), _) | RefinedType(_, TypeConstructor(_, _), _):
                return BaseKind()
            case TypeVar(name):
                assert (name, BaseKind()) in self.typevars()
                # TODO Polytypes: What it * is in context?
                return BaseKind()
            case RefinedType(_, TypeVar(name), _):
                assert (name, BaseKind()) in self.typevars(), f"{name} not in {self.typevars()}"
                return BaseKind()
            case AbstractionType(_, _, _):
                return StarKind()
            case TypePolymorphism(_, _, _):
                return StarKind()
            case TypeConstructor(_, _):
                return StarKind()
            case _:
                assert False, f"Unknown type in context: {ty}"

    @abstractmethod
    def typevars(self) -> list[tuple[str, Kind]]: ...

    @abstractmethod
    def vars(self) -> list[tuple[str, Type]]: ...

    @abstractmethod
    def get_type_constructor(self, name: str) -> list[str] | None: ...


class EmptyContext(TypingContext):
    def __init__(self):
        self.counter = 0

    def type_of(self, name: str) -> Type | None:
        return None

    def __repr__(self) -> str:
        return "ø"

    def typevars(self) -> list[tuple[str, Kind]]:
        return []

    def vars(self) -> list[tuple[str, Type]]:
        return []

    def __hash__(self) -> int:
        return 0

    def get_type_constructor(self, name: str) -> list[str] | None:
        if name in ["Unit", "Int", "Bool", "Float", "String"]:
            return []
        return None


@dataclass
class NonEmptyContext(TypingContext):
    prev: TypingContext

    def type_of(self, name: str) -> Type | None:
        return self.prev.type_of(name)

    def vars(self) -> list[tuple[str, Type]]:
        return self.prev.vars()

    def typevars(self) -> list[tuple[str, Kind]]:
        return self.prev.typevars()

    def get_type_constructor(self, name: str) -> list[str] | None:
        return self.prev.get_type_constructor(name)


@dataclass
class UninterpretedBinder(NonEmptyContext):
    name: str
    type: AbstractionType

    def type_of(self, name: str) -> Type | None:
        if name == self.name:
            return self.type
        return self.prev.type_of(name)

    def fresh_var(self):
        name = self.name
        while name == self.name:
            name = self.prev.fresh_var()
        return name

    def __repr__(self) -> str:
        return f"{self.prev},{self.name}:{self.type}"

    def vars(self) -> list[tuple[str, Type]]:
        return [(self.name, self.type)] + self.prev.vars()

    def __hash__(self) -> int:
        return hash(self.prev) + hash(self.name) + hash(self.type)


@dataclass(init=False)
class VariableBinder(NonEmptyContext):
    name: str
    type: Type

    def __init__(self, prev: TypingContext, name: str, type: Type):
        self.prev = prev
        self.name = name
        self.type = type
        assert isinstance(prev, TypingContext)
        assert isinstance(type, Type)
        assert name not in prev.vars()

    def type_of(self, name: str) -> Type | None:
        if name == self.name:
            return self.type
        return self.prev.type_of(name)

    def fresh_var(self):
        name = self.name
        while name == self.name:
            name = self.prev.fresh_var()
        return name

    def __repr__(self) -> str:
        return f"{self.prev},{self.name}:{self.type}"

    def vars(self) -> list[tuple[str, Type]]:
        return [(self.name, self.type)] + self.prev.vars()

    def __hash__(self) -> int:
        return hash(self.prev) + hash(self.name) + hash(self.type)


@dataclass(init=False)
class TypeBinder(NonEmptyContext):
    type_name: str
    type_kind: Kind

    def __init__(
        self,
        prev: TypingContext,
        type_name: str,
        type_kind: Kind = StarKind(),
    ):
        self.prev = prev
        self.type_name = type_name
        self.type_kind = type_kind

    def fresh_var(self):
        name = self.type_name
        while name == self.type_name:
            name = self.prev.fresh_var()
        return name

    def typevars(self) -> list[tuple[str, Kind]]:
        return [(self.type_name, self.type_kind)] + self.prev.typevars()

    def __repr__(self) -> str:
        return f"{self.prev},<{self.type_name}:{self.type_kind}>"

    def __hash__(self) -> int:
        return hash(self.prev) + hash(self.type_name) + hash(self.type_kind)


@dataclass
class TypeConstructorBinder(NonEmptyContext):
    name: str
    args: list[str]

    def get_type_constructor(self, name: str) -> list[str] | None:
        if name == self.name:
            return self.args
        return self.prev.get_type_constructor(name)

    def __repr__(self) -> str:
        argss = " ".join(self.args)
        return f"{self.prev},[{self.name} {argss}]"

    def __hash__(self) -> int:
        return hash(self.prev) + hash(self.name)
