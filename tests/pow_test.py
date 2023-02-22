from __future__ import annotations

from aeon.sugar.desugar import desugar
from aeon.backend.evaluator import eval
from aeon.backend.evaluator import EvaluationContext
from aeon.core.types import t_int
from aeon.core.types import top
from aeon.frontend.parser import parse_term
from aeon.frontend.parser import parse_type
from aeon.sugar.parser import parse_program
from aeon.prelude.prelude import evaluation_vars
from aeon.prelude.prelude import typing_vars
from aeon.typing.typeinfer import check_type
from aeon.utils.ctx_helpers import build_context

def check_compile(source, ty, res):
    p, ctx, ectx = desugar(parse_program(source))
    assert check_type(ctx, p, ty)
    #assert eval(p, ectx) == res


def test_anf():
    source = r"""
        type Unit;
        def math : Unit = native_import "math";
        def test (b:{x:Float | 1 <= x <= 100}) -> (e:{y:Float | 1 <= y <= 100}) ->  Int { native "math.pow(b , e)"} 
        """
    check_compile(source, top, 1)
