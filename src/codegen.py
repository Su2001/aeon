from .typestructure import *

class Expr(object):
    def __init__(self, text="", is_stmt=False):
        self.text = text
        self.is_stmt = is_stmt

    def __str__(self):
        return self.text

class Block(object):
    def __init__(self, t):
        self.type = t
        self.stmts = []
        self.escape = None

    def add(self, stmt):
        self.stmts.append(stmt)

    def __str__(self):
        return self.get_stmts()

    def get_escape(self):
        if self.type == 'void':
            return ""
        if not self.escape and self.stmts:
            self.escape = self.stmts.pop()
        return self.escape

    def get_stmts(self):
        return "\n".join(map(lambda x: x+";", self.stmts))


class CodeGenerator(object):
    def __init__(self, table, typecontext):
        self.table = table
        self.typecontext = typecontext
        self.stack = [table, {}]
        self.blockstack = []
        self.counter = 0

    def push_frame(self):
        self.stack.append({})

    def pop_frame(self):
        self.stack = self.stack[:-1]

    def find(self, kw):
        for frame in self.stack[::-1]:
            if kw in frame:
                return frame[kw]
        return None

    def get_counter(self):
        self.counter += 1
        return self.counter


    def type_alias_resolver(self, ty):
        for ta in self.typecontext.type_aliases:
            if ta == ty:
                return self.typecontext.type_aliases[ta]
            mapping = ta.polymorphic_matches(ty, self.typecontext)
            if mapping:
                return self.typecontext.type_aliases[ta].polymorphic_fill(mapping)
        return None

    def type_convert(self, t):
        r = self.type_alias_resolver(t)
        if r:
            return self.type_convert(r)
        if t.arguments != None:
            #This is a lambda expression
            if len(t.arguments) == 0:
                return "java.util.function.Supplier<{}>".format(self.type_convert(t.type))
            elif len(t.arguments) == 1 and t.arguments[0] == t.type:
                return "java.util.function.UnaryOperator<{}>".format(self.type_convert(t.type))
            elif len(t.arguments) == 1 and str(t.type) == 'Boolean':
                return "java.util.function.Predicate<{}>".format(self.type_convert(t.arguments[0]))
            elif len(t.arguments) == 1 and str(t.type) == 'Void':
                return "java.util.function.Consumer<{}>".format(self.type_convert(t.arguments[0]))
            elif len(t.arguments) == 1:
                return "java.util.function.Function<{}, {}>".format(self.type_convert(t.arguments[0]), self.type_convert(t.type))
            elif len(t.arguments) == 2 and str(t.type) == 'Boolean':
                return "java.util.function.BiPredicate<{}>".format(self.type_convert(t.arguments[0]), self.type_convert(t.arguments[1]))
            elif len(t.arguments) == 2 and str(t.type) == 'Void':
                return "java.util.function.BiConsumer<{}>".format(self.type_convert(t.arguments[0]), self.type_convert(t.arguments[1]))
            elif len(t.arguments) == 2:
                return "java.util.function.BiFunction<{}, {}>".format(self.type_convert(t.arguments[0]), self.type_convert(t.arguments[1]), self.type_convert(t.type))
            else:
                print("Codegen unavaiable for lambdas with type: ", str(t))

        if t.type == 'Array':
            return str(t.parameters[0]) + "[]"
        if t.type == 'Void':
            return 'void'
        return str(t)


    def root(self, ast):
        return """
        public class E {{
            {}
        }}
        """.format(self.g_toplevel(ast))

    def genlist(self, ns, *args, **kwargs):
        return "\n".join([ self.generate(n, *args, **kwargs) for n in ns ])

    def g_toplevel(self, n):
        """ [decl] """
        return "\n\n".join(map(self.g_decl, n))

    def g_decl(self, n):
        """ decl -> string """

        if n.nodet == 'native':
            return ""

        if n.nodet == 'type':
            return "" # Codegeneration of type alias

        name = n.nodes[0]
        ftype = self.table[name]
        lrtype = self.type_convert(ftype.type)
        largtypes = ", ".join([ "{} {}".format(self.type_convert(a[1]), a[0]) for a in n.nodes[1]])

        body = self.g_block(n.nodes[6], type=lrtype)
        if name == 'main' and lrtype == 'void' and ftype.arguments and str(ftype.arguments[0]) == 'Array<String>':
            body = self.futurify_body(body, lrtype)

        if lrtype != "void":
            body_final = "return {};".format(body.get_escape())
        else:
            body_final = ""

        return """ public static {} {}({}) {{ {} \n {} }}""".format(
            lrtype,
            name,
            largtypes,
            body.get_stmts(),
            body_final
        )

    def futurify_body(self, body, lrtype):
        body.stmts.insert(0, "aeminium.runtime.futures.RuntimeManager.init()");
        if lrtype == 'void':
            body.stmts.append("aeminium.runtime.futures.RuntimeManager.shutdown()");
        else:
            body.stmts.append("{} ret_aeminium_manager = {}".format(lrtype, body.get_escape()));
            body.stmts.append("aeminium.runtime.futures.RuntimeManager.shutdown()");
            body.escape = "ret_aeminium_manager"
        return body


    def g_block(self, n, type='void'):
        b = Block(type)
        self.blockstack.append(b)
        for c in n.nodes:
            e = self.g_expr(c)
            if c != n.nodes[-1] and c.type != t_v and not e.is_stmt:
                b.add("J.noop(" + str(e) + ")")
            else:
                b.add(str(e))
        self.blockstack.pop()
        return b

    def g_expr(self, n):
        if n.nodet == 'invocation':
            return self.g_invocation(n)
        elif n.nodet == 'literal':
            return self.g_literal(n)
        elif n.nodet == 'let':
            return self.g_let(n)
        elif n.nodet in ["&&", "||", "<", "<=", ">", ">=", "==", "!=", "+", "-", "*", "/", "%"]:
            return self.g_op(n)
        elif n.nodet == 'atom':
            return self.g_atom(n)
        elif n.nodet == 'lambda':
            return self.g_lambda(n)
        elif n.nodet == 'block':
            return self.g_block(n, self.type_convert(n.type))
        else:
            print("new_type:", n)
            return Expr("X")

    def g_invocation(self, n):
        return Expr("""
            {}({})
        """.format(
            n.nodes[0],
            ", ".join([str(self.g_expr(x)) for x in n.nodes[1]])
        ), is_stmt=True)

    def g_atom(self, n):
        return Expr(n.nodes[0])

    def g_let(self, n):
        var_name = n.nodes[0]
        var_type = self.type_convert(n.type)
        var_value = self.g_expr(n.nodes[1])
        if self.find(var_name) != None:
            return Expr("{} = {}".format(var_name, str(var_value)), is_stmt=True)
        else:
            self.stack[-1][var_name] = var_type
            return Expr("{} {} = {}".format(var_type, var_name, str(var_value)), is_stmt=True)

    def g_lambda(self, n):
        args = ", ".join([ "{} {}".format(self.type_convert(i[1]), i[0]) for i in n.nodes[0] ])
        p2 = self.g_expr(n.nodes[1])
        if type(p2) == Block:
            esc = p2.get_escape()
            if esc:
                body = "{{ {}; return {}; }}".format(p2.get_stmts(), esc)
            else:
                body = "{{ {} }}".format(p2.get_stmts())
        else:
            body = str(p2)
        return Expr("({}) -> {}".format(args, body))


    def g_literal(self, n):
        return Expr(str(n.nodes[0]))


    def g_op(self, n):
        if len(n.nodes) == 2:
            return Expr("({1} {0} {2})".format(
                n.nodet,
                self.g_expr(n.nodes[0]),
                self.g_expr(n.nodes[1])
            ))
        else:
            return Expr("({0} {1})".format(
                n.nodet,
                self.g_expr(n.nodes[0])
            ))


def generate(ast, table, typecontext):
    return CodeGenerator(table, typecontext).root(ast)
