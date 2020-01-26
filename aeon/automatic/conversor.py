from aeon.interpreter import run
from aeon.automatic.utils import generate_abstractions

from aeon.types import t_i, t_f
from aeon.ast import Var, Literal, Abstraction, Application, If, TAbstraction, TApplication

# Given a list of expressions, convert them into numeric discrete values
def convert(and_expressions):
    return [apply_conversion(condition) for condition in and_expressions]


# Apply the conversion to an expression
def apply_conversion(condition):
    variable = obtain_application_var(condition)
    if isinstance(variable, If):
        variable.then = apply_conversion(variable.then)
        variable.otherwise = apply_conversion(variable.otherwise)
        return condition
    elif isinstance(variable, Abstraction):
        variable.body = apply_conversion(variable.body)
        return condition
    # Else it is a Var
    elif variable.name.startswith('@'):
        return condition
    elif variable.name in ['==']:
        return abs_conversion(condition)
    elif variable.name in ['!=']:
        return neg_abs_conversion(condition)
    elif variable.name in ['!']:
        return not_conversion(condition)
    elif variable.name in ['&&']:
        return and_conversion(condition)
    elif variable.name in ['||']:
        return or_conversion(condition)
    elif variable.name in ['-->']:
        return implie_conversion(condition)
    elif variable.name in ['>', '<', '<=', '>=']:
        return if_conversion(condition)
    # It is a variable or f(variable)
    else:
        return boolean_conversion(condition)


# Obtains the most left var name of the application
def obtain_application_var(condition):
    if isinstance(condition, Var):
        return condition
    elif isinstance(condition, TAbstraction):
        return obtain_application_var(condition.body)
    elif isinstance(condition, TApplication):
        return obtain_application_var(condition.target)
    elif isinstance(condition, Application):
        return obtain_application_var(condition.target)
    # condition is Abstraction or If
    else:
        return condition


# =============================================================================
# ============================================================ Conversion rules
# a == b ~> norm(|a - b|) 
def abs_conversion(condition):
    result = Application(Var('-'), condition.argument)
    result = Application(result, condition.target.argument)
    return normalize(Application(Var('abs'), result))
# Auxiliary to normalize
def normalize(value):
    norm = Application(Application(Var('pow'), Literal(0.99, t_f)))
    return Application(Application(Var('-'), 1), norm)


# a != b ~> 1 - norm(|a - b|)
def abs_conversion(condition):
    converted = abs_conversion(condition)
    return Application(Application(Var('-'), Literal(1, t_i)), converted)


# condition ~> condition ? 0 : abs_conversion(condition)
def if_conversion(condition):
    then = Literal(0, t_i)
    otherwise = abs_conversion(condition)
    return If(condition, then, otherwise)


# a && b ~> (convert(a) + convert(b))/2
def and_conversion(condition):
    left = apply_conversion(condition.argument)
    right = apply_conversion(condition.target.argument)
    op = Application(Application(Var('+'), left), right)
    return Application(Application(Var('/'), op), Literal(2, t_i))


# a v b ~> min(f(a), f(b))
def or_conversion(condition):
    left = apply_conversion(condition.argument)
    right = apply_conversion(condition.target.argument)
    return Application(Application(Var('min'), left), right)


# a --> b ~> convert(!a || b)
def implie_conversion(condition):
    not_a = Application(Var('!'), condition.target.argument)
    return apply_conversion(Application(not_a, and_expr.argument))


# !condition ~> 1 - convert(condition)
def not_conversion(condition):
    converted = apply_conversion(condition.argument)
    return Application(Application(Var('-'), Literal(1, t_i)), converted)

# x or f(x) ~> f(x) ? 0 : 1
def boolean_conversion(condition):
    then = Literal(0, t_i)
    otherwise = Literal(1, t_i)
    return If(cond, then, otherwise)

# =============================================================================
# ================================================ Fitness functions conversion
def interpret_expressions(abstractions, expressions):

    abstraction, last_abstraction = abstractions

    optimizers = {
        '@maximize': maximize,
        '@minimize': minimize,
        '@evaluate': evaluate
    }

    result = list()

    for condition in expressions:
        if isinstance(condition, Application) and \
                isinstance(condition.target, Var) and \
                condition.target.name.startswith('@'):
            function = optimizers[condition.target.name]
            result.append(function(condition.argument))
        else:
            # Englobe the expressions with the parameters and return
            last_abstraction = condition
            function = run(abstraction)
            result.append(function)

    return result


# @maximize
def maximize(argument):
    pass


# @minimze
def minimize(argument):
    pass

# @evaluate('path')
def evaluate(argument):
    path = argument.name
    # Applies a function to a row and get its error
    def apply(function, row):
        return normalize(abs(row[-1] - reduce(lambda f, x: f(x), row[:-1], function)))

    with open(path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        return lambda f: sum([apply(f, row) for row in csv_reader[1:]])

    raise Exception('The csv file', path, 'is invalid.')
