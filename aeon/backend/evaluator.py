from typing import Any, Dict, List, Tuple
from aeon.core.terms import Abstraction, Application, If, Let, Literal, Rec, Term, Var


class EvaluationContext(object):
    variables: Dict[str, Any]

    def __init__(self, prev: Dict[str, Any] = None):
        if prev:
            self.variables = {k: v for (k, v) in prev.items()}
        else:
            self.variables = {}

    def with_var(self, name: str, value: Any):
        v = self.variables.copy()
        v.update({name: value})
        return EvaluationContext(v)

    def get(self, name: str):
        return self.variables[name]


# pattern match term
def eval(t: Term, ctx: EvaluationContext = EvaluationContext()):
    if isinstance(t, Literal):
        return t.value
    elif isinstance(t, Var):
        return ctx.get(t.name)
    elif isinstance(t, Abstraction):
        return lambda k: eval(t.body, ctx.with_var(t.var_name, k))
    elif isinstance(t, Application):
        return eval(t.fun, ctx)(eval(t.arg, ctx))
    elif isinstance(t, Let):
        return eval(t.body, ctx.with_var(t.var_name, eval(t.var_value, ctx)))
    elif isinstance(t, Rec):

        if isinstance(t.var_value, Abstraction):
            fun = t.var_value

            def v(x):
                return eval(
                    fun.body,
                    ctx.with_var(t.var_name, v).with_var(fun.var_name, x),
                )

        else:
            v = eval(t.var_value, ctx)
        return eval(t.body, ctx.with_var(t.var_name, v))
    elif isinstance(t, If):
        c = eval(t.cond, ctx)
        return bool(c) and eval(t.cond, ctx) or eval(t.otherwise, ctx)
    assert False
