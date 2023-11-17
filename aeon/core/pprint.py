from __future__ import annotations

from aeon.core.liquid import LiquidLiteralBool
from aeon.core.terms import (
    Abstraction,
    Annotation,
    Application,
    Hole,
    If,
    Let,
    Literal,
    Rec,
    Term,
    TypeAbstraction,
    TypeApplication,
    Var,
)
from aeon.core.types import AbstractionType
from aeon.core.types import BaseType
from aeon.core.types import RefinedType
from aeon.core.types import Type
from aeon.core.types import TypeVar
from aeon.core.types import type_free_term_vars
from aeon.synthesis_grammar.grammar import aeon_prelude_ops_to_text


def pretty_print(t: Type) -> str:
    if isinstance(t, BaseType):
        return str(t)
    elif isinstance(t, TypeVar):
        return str(t)
    elif isinstance(t, AbstractionType):
        at = pretty_print(t.var_type)
        rt = pretty_print(t.type)
        if t.var_name in type_free_term_vars(t.var_type):
            return f"({t.var_name}:{at}) -> {rt}"
        else:
            return f"{at} -> {rt}"
    elif isinstance(t, RefinedType):
        it = pretty_print(t.type)
        if t.refinement == LiquidLiteralBool(True):
            return it
        else:
            return f"{{{t.name}:{it} | {t.refinement}}}"
    assert False


def pretty_print_term(term: Term):
    term_str: str = custom_preludes_ops_representation(term)[0]
    print(term_str)


def custom_preludes_ops_representation(term: Term, counter: int = 0) -> tuple[str, int]:
    prelude_operations: dict[str, str] = aeon_prelude_ops_to_text
    match term:
        case Application(fun=Var(name=var_name), arg=arg) if var_name in prelude_operations.keys():
            arg_str, counter = custom_preludes_ops_representation(arg, counter)
            counter += 1
            new_var_name = f"__{prelude_operations[var_name]}_{counter}__"
            personalized_op = f"(\\{new_var_name} -> {arg_str} {var_name} {new_var_name})"
            return personalized_op, counter

        case Application(fun=fun, arg=arg):
            fun_str, counter = custom_preludes_ops_representation(fun, counter)
            arg_str, counter = custom_preludes_ops_representation(arg, counter)
            return f"({fun_str} {arg_str})", counter

        case Annotation(expr=expr, type=type):
            expr_str, counter = custom_preludes_ops_representation(expr, counter)
            return f"({expr_str} : {type})", counter

        case Abstraction(var_name=var_name, body=body):
            body_str, counter = custom_preludes_ops_representation(body, counter)
            return f"(\\{var_name} -> {body_str})", counter

        case Let(var_name=var_name, var_value=var_value, body=body):
            var_value_str, counter = custom_preludes_ops_representation(var_value, counter)
            body_str, counter = custom_preludes_ops_representation(body, counter)
            return f"(let {var_name} = {var_value_str} in {body_str})", counter

        case Rec(var_name=var_name, var_type=var_type, var_value=var_value, body=body):
            var_value_str, counter = custom_preludes_ops_representation(var_value, counter)
            body_str, counter = custom_preludes_ops_representation(body, counter)
            return f"(rec {var_name} : {var_type} = {var_value_str} in {body_str})", counter

        case If(cond=cond, then=then, otherwise=otherwise):
            cond_str, counter = custom_preludes_ops_representation(cond, counter)
            then_str, counter = custom_preludes_ops_representation(then, counter)
            otherwise_str, counter = custom_preludes_ops_representation(otherwise, counter)
            return f"(if {cond_str} then {then_str} else {otherwise_str})", counter

        case TypeAbstraction(name=name, kind=kind, body=body):
            body_str, counter = custom_preludes_ops_representation(body, counter)
            return f"ƛ{name}:{kind}.({body_str})", counter

        case TypeApplication(body=body, type=type):
            body_str, counter = custom_preludes_ops_representation(body, counter)
            return f"({body_str})[{type}]", counter

        case Literal(_, _) | Var(_) | Hole(_):
            return str(term), counter

    return str(term), counter
