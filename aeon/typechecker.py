from .automatic import synthesise 

from .typestructure import *
from .zed import zed


class TypeContext(object):
    def __init__(self, typedecl=None, refined=True):
        self.types = typedecl and typedecl or []
        self.type_aliases = {}
        self.subclasses = []
        self.refined = refined

        self.types.append(Type('Integer'))
        self.types.append(Type('Double'))
        self.types.append(Type('Boolean'))
        self.types.append(Type('String'))

    def add_type(self, t):
        self.types.append(t)

    def add_type_alias(self, t1, t2):
        self.type_aliases[t1] = t2.copy()
        
    def handle_aliases(self, t, recursive=False):

        if recursive and type(t) == Type:
            t.type = self.handle_aliases(t.type)
            if t.arguments:
                t.arguments = list(map(self.handle_aliases, t.arguments))
            if t.parameters:
                t.parameters = list(map(self.handle_aliases, t.parameters))
            return self.handle_aliases(t.copy())
        
        for ta in self.type_aliases:
            replacements = {}
            if t.freevars and ta.freevars:
                if len(t.freevars) == len(ta.freevars):
                    right_copy = t.copy()
                    for rv, fv in zip(t.freevars, ta.freevars):
                        right_copy = right_copy.copy_replacing_freevar(rv, fv)
                        replacements[fv] = rv
                    v = ta == right_copy
                else:
                    v = False
            else:
                v = t == ta
            if v:
                b = self.type_aliases[ta].copy()
                for k in replacements:
                    b = b.copy_replacing_freevar(k, replacements[k])
                return b
            
        # T<Integer> under type T<P> aliasing java.util.T<P> should be java.util.T<Integer>
        for possible_generic_type in self.type_aliases:
            if possible_generic_type.freevars:
                for v in possible_generic_type.freevars:
                    for ct in self.types:
                        ft_concrete = possible_generic_type.copy_replacing_freevar(v, ct)
                        if self.is_subtype(t, ft_concrete, do_aliases=False):
                            return self.type_aliases[possible_generic_type].copy_replacing_freevar(v, ct)

        return t

    def is_subtype(self, t1, t2, under=None, do_aliases=True, check_refined=True, new_context=False):
        if str(t2) in ['Void', 'Object']:
            return True
        if do_aliases:
            t1 = self.handle_aliases(t1)
            t2 = self.handle_aliases(t2)    

        r = t1 == t2
        if r and self.refined and check_refined:
            return zed.try_subtype(t1, t2, new_context, under)
        return r
        
        
    def resolve_type(self, t):
        return self.handle_aliases(t)

    def check_function_arguments(self, args, ft):
        if ft.freevars:
            for v in ft.freevars:
                for ct in self.types:
                    ft_concrete = ft.copy_replacing_freevar(v, ct)
                    a, ft_concrete_r = self.check_function_arguments(args, ft_concrete)
                    if a:
                        return (a, ft_concrete_r)
            return (False, None)
        else:            
            valid = all([ self.is_subtype(a, b, new_context=True) for a,b in zip(args, ft.arguments) ])
            return (valid, ft)


class Context(object):
    def __init__(self, tcontext):
        self.stack = []
        self.typecontext = tcontext
        self.push_frame()
        self.funs = {}

    def push_frame(self):
        self.stack.append({})

    def push_frame(self):
        self.stack.append({})

    def pop_frame(self):
        self.stack = self.stack[:-1]

    def find(self, kw):
        for frame in self.stack[::-1]:
            if kw in frame:
                return frame[kw]
        return None

    def set(self, k, v):
        self.stack[-1][k] = v

    def define_fun(self, name, type_, n):
        r = self.set(name, type_)
        if name not in self.funs:
            self.funs[name] = [ (name, type_, n) ]
            new_name = name
        else:
            new_name = name + "__multiple__" + str(len(self.funs[name]))
            self.funs[name].append( (new_name, type_, n) )
            if len(self.funs[name]) == 2:
                original_new_name = name + "__multiple__0"
                self.funs[name][0] = (original_new_name, self.funs[name][0][1], self.funs[name][0][2])
                self.funs[name][0][2].md_name = original_new_name
        return new_name


class TypeChecker(object):
    def __init__(self, refined=True):
        self.typecontext = TypeContext(refined=refined)
        self.context = Context(self.typecontext)
        self.refined = refined

    def type_error(self, string):
        raise Exception("Type Error", string)

    def is_subtype(self, a, b, *args, **kwargs):
        return self.typecontext.is_subtype(a, b, *args, **kwargs)

    def check_function_arguments(self, args, ft):
        return self.typecontext.check_function_arguments(args, ft)

    def typelist(self, ns, last_expects=None ,*args, **kwargs):
        if not ns:
            return []
        for n in ns[:-1]:
            self.typecheck(n, *args, **kwargs)
        self.typecheck(ns[-1], expects=last_expects, *args, **kwargs)
        return ns

    def t_type(self, n):
        if len(n.nodes) > 2 and n.nodes[2]:
            n.nodes[0].set_conditions(n.nodes[2], names=['self'])

        self.typecontext.add_type(n.nodes[0])
        if len(n.nodes) > 1 and n.nodes[1]:
            self.typecontext.add_type_alias(n.nodes[1], n.nodes[0])

    def t_native(self, n):
        name = n.nodes[0]
        n.type = n.nodes[2].nodes[1]
        ft = Type(arguments = [self.typecontext.resolve_type(x.nodes[1]) for x in  n.nodes[1]],
                  type=self.typecontext.resolve_type(n.type),
                  freevars = n.nodes[3],
                  conditions=n.nodes[4],
                  effects=n.nodes[5])
        ft.set_conditions(n.nodes[4], [n.nodes[2].nodes[0]], [x.nodes[0] for x in n.nodes[1]])
        ft.set_effects(n.nodes[5], [n.nodes[2].nodes[0]], [x.nodes[0] for x in n.nodes[1]])
        self.function_type = ft
        n.md_name = self.context.define_fun(name, ft, n)

    def t_decl(self, n):
        n.type = n.nodes[2].nodes[1]
        name = n.nodes[0]
        argtypes = [self.typecontext.resolve_type(x.nodes[1]) for x in  n.nodes[1]]
        ft = Type(arguments = argtypes,
                  type=self.typecontext.resolve_type(n.type),
                  freevars = n.nodes[3],
                  conditions=n.nodes[4],
                  effects=n.nodes[5])
        ft.set_conditions(n.nodes[4], [n.nodes[2].nodes[0]], [x.nodes[0] for x in n.nodes[1]])
        ft.set_effects(n.nodes[5], [n.nodes[2].nodes[0]], [x.nodes[0] for x in n.nodes[1]])
        n.md_name = self.context.define_fun(name, ft, n)
        self.function_name = n.md_name
        self.function_type = ft

        # Body
        self.context.push_frame()

        for arg, argt in zip(n.nodes[1], argtypes):
            self.context.set(arg.nodes[0], argt)
    
        # body
        self.typecheck(n.nodes[6], expects = ft.type)
        if n.nodes[6]: 
            real_type = n.nodes[6].type
        else:
            real_type = t_v

        if not self.is_subtype(real_type, n.type):
            self.type_error("Function {} expected {} and body returns {}".format(name, n.type, real_type))
        if self.refined:
            if not self.is_subtype(real_type, n.type, under=(ft, argtypes)):
                self.type_error("Function {} failed post-condition {} when returning {}".format(name, ft, real_type))
            

        self.context.pop_frame()


    def t_invocation(self, n):
        self.typelist(n.nodes[1])
        name = n.nodes[0]
        t = self.context.find(name)
        if not t:
            self.type_error("Unknown function {}".format(name))
        t.propagate_freevars()

        t_name = self.typecontext.handle_aliases(t, recursive=True)
        if not t_name:
            self.type_error("Unknown function {}".format(name))
        if t_name.arguments == None:
            self.type_error("Function {} is not callable".format(name))

        actual_argument_types = [ c.type for c in n.nodes[1] ]
    
        valid, concrete_type = self.check_function_arguments(actual_argument_types, t_name)
        if valid:
            n.type = concrete_type.type # Return type
        else:
            self.type_error("Wrong argument types for {} | Expected {} -- Got {}".format(
                            name,
                            str(t_name),
                            str(list(map(str, actual_argument_types))),
                ))

        if self.refined:
            ok, ref_name = zed.refine_function_invocation(concrete_type, actual_argument_types)
            if not ok:
                self.type_error("Refinement checking failed for {}: Got {}, expected {}".format(
                            name,
                            str(list(map(str, actual_argument_types))),
                            str(concrete_type)
                ))
            if ref_name:
                n.type.refined = ref_name
                n.type.context = zed.copy_assertions()
            
            if name == 'J.iif':
                zed.assert_if(n.type, actual_argument_types[1], actual_argument_types[2] )

    def t_lambda(self, n):
        args = [ c[1] for c in n.nodes[0] ]
        # Body
        self.context.push_frame()
        for arg in n.nodes[0]:
            if self.context.find(arg[0]) != None:
                self.type_error("Argument {} of lambda {} is already defined as variable".format(arg[0], str(n)))
            self.context.set(arg[0], arg[1])
        self.typecheck(n.nodes[1])
        self.context.pop_frame()

        n.type = Type(
            arguments = args,
            type = n.nodes[1].type
        )

    def t_atom(self, n):
        k = self.context.find(n.nodes[0])
        if k == None:
            self.type_error("Unknown variable {}".format(n.nodes[0]))
        n.type = k
        if self.refined and not hasattr(n.type, "refined"):
            n.type.refined = zed.refine_atom(n.type)
            n.type.context = zed.copy_assertions()
            n.type.zed_conditions == []

    def t_let(self, n):
        self.typecheck(n.nodes[1])
        if n.nodes[2]:
            n.type = n.nodes[2]
            if not self.is_subtype(n.nodes[1].type, n.type):
                self.type_error("Variable {} is not of type {}, but rather {}".format(n.nodes[0], n.type, n.nodes[1].type))
        else:
            n.type = n.nodes[1].type
        n.type = self.typecontext.resolve_type(n.type)
        self.context.set(n.nodes[0], n.type)

    def t_op(self, n):
        if n.nodet in ['&&', '||']:
            n.type = t_b
            self.typelist(n.nodes)
            for c in n.nodes:
                if c.type != t_b:
                    raise Exception("{} expected boolean arguments in {}. Got {}.".format(n.nodet, c, c.type))
        elif n.nodet in ["<", "<=", ">", ">=", "==", "!="]:
            n.type = t_b
            self.typelist(n.nodes)
        elif n.nodet in ["+", "-", "*", "/", "%"]:
            self.typelist(n.nodes)
            n.type = t_i if all([ k.type == t_i for k in n.nodes]) else t_f
            if self.refined:
                n.type.refined = zed.combine(n.type, n.nodet, n.nodes)
                n.type.context = zed.copy_assertions()
        else:
            self.type_error("Unknown operator {}".format(n.nodet))

    def t_literal(self, n):
        # Base type created on the frontend
        if self.refined:
            n.type.refined = zed.make_literal(n.type, n.nodes[0])
            n.type.context = zed.copy_assertions()
            n.type.conditions = [ Node('==', Node('atom', 'self'), Node('literal', n.nodes[0])) ]
            

    def typecheck(self, n, expects=None):
        if type(n) == list:
            return self.typelist(n)
        if type(n) == str:
            print(n, "string invalid")
            return n
        if n.nodet == 'type':
            return self.t_type(n)
        elif n.nodet == 'native':
            return self.t_native(n)
        elif n.nodet == 'decl':
            return self.t_decl(n)
        elif n.nodet == 'invocation':
            return self.t_invocation(n)
        elif n.nodet == 'lambda':
            return self.t_lambda(n)
        elif n.nodet == 'atom':
            return self.t_atom(n)
        elif n.nodet == 'let':
            return self.t_let(n)
        elif not n.nodet.isalnum():
            return self.t_op(n)
        elif n.nodet == 'literal':
            return self.t_literal(n)
        elif n.nodet == 'block':
            self.typelist(n.nodes, last_expects = expects)
            if n.nodes:
                n.type = n.nodes[-1].type
            else:
                n.type = t_v
        elif n.nodet == 'hole':
            n.type = 'block'
            n.nodes = [synthesise(n, expects, function_name=self.function_name, function_type=self.function_type)]
            n.type = n.nodes[0].type
        else:
            print("No TypeCheck rule for", n.nodet)
        return n


def typecheck(ast, refined=True):
    tc = TypeChecker(refined=refined)
    return tc.typecheck(ast), tc.context, tc.typecontext
    
    