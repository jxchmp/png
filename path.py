#!/usr/bin/env python3

DEBUG = False 

class Path(object):
    def __init__(self, parent=None, name=None, call=False,
                 args=None, kwargs=None):
        self.__parent = parent
        self.__name = name
        self.__call = call
        self.__args = args if args else []
        self.__kwargs = kwargs if kwargs else {}

    def resolve_path(self, obj, node=None):
        if DEBUG:
            print("resolve path", str(self))
        if node is None:
            node = obj
        if self.__parent is not None:
            obj = self.__parent.resolve_path(obj, node)
            if self.__call:
                args = []
                for arg in self.__args:
                    if isinstance(arg, Path):
                        args.append(arg.resolve_path(node))
                    else:
                        args.append(arg)
                kwargs = {}
                for k, v in self.__kwargs.items():
                    if isinstance(v, Path):
                        kwargs[k] = v.resolve_path(node)
                    else:
                        kwargs[k] = v
                if self.__name:
                    if DEBUG:
                        print("returning {}({},{}) {}".format(
                            str(self.__name),
                            str([str(a) for a in args]),
                            str(["(" + str(k) + "," + str(v) + ") "
                                for k,v in kwargs]),
                            str(getattr(obj, self.__name)(*args, **kwargs))
                        ))
                    return getattr(obj, self.__name)(*args, **kwargs)
                if DEBUG:
                    print("returning call args {} and kwargs{}: {}".format(
                        str(args), str(kwargs), str(obj(*args, **kwargs))
                    ))
                return obj(*args, **kwargs)
            else:
                if DEBUG:
                    print("returning attribute {} ({})".format(
                        self.__name, getattr(obj, self.__name)
                    ))
                return getattr(obj, self.__name)
        else:
            if DEBUG:
                print("returning {}".format(obj))
            return obj

    def __getattribute__(self, name):
        if name.startswith("_Path") or name == "resolve_path":
            return object.__getattribute__(self, name)
        else:
            return Path(self, name)
        return name

    def __call__(self, *args, **kwargs):
        return Path(self, None, True, args, kwargs)

    def __repr__(self):
        return str(self)

    def __str__(self):
        s = []
        obj = self
        while obj is not None:
            name = obj.__name if obj.__name else "Path"
            call_signature = []
            if obj.__call:
                call_signature.append("(")
                call_signature.append(", ".join(
                    [str(arg) if not isinstance(arg, Path) else "..."
                     for arg in obj.__args]))
                call_signature.append(", ".join(
                    k + "=" + (str(v) if not isinstance(v, Path) else "...")
                    for k,v in obj.__kwargs.items()))
                call_signature.append(")")
            s.append(str(name) + "".join(call_signature))
            obj = obj.__parent
        return ".".join(reversed(s))
            
    def __bytes__(self):
        return Path(self, "__str__", True)

    def __lt__(self, other):
        return Path(self, "__lt__", True, [other])

    def __le__(self, other):
        return Path(self, "__le__", True, [other])

    def __eq__(self, other):
        return Path(self, "__eq__", True, [other])

    def __ne__(self, other):
        return Path(self, "__ne__", True, [other])

    def __gt__(self, other):
        return Path(self, "__gt__", True, [other])

    def __ge__(self, other):
        return Path(self, "__ge__", True, [other])

    def __bool__(self):
        return Path(self, "__bool__", True)

    def __len__(self):
        return Path(self, "__len__", True)

    def __getitem__(self, key):
        return Path(self, "__getitem__", True, [key])

    def __setitem__(self, key, value):
        return Path(self, "__setitem__", True, [key, value])

    def __iter__(self):
        return Path(self, "__iter__", True)

    def __contains__(self, item):
        return Path(self, "__contains__", True, [item])

    def __add__(self, other):
        return Path(self, "__add__", True, [other])

    def __sub__(self, other):
        return Path(self, "__sub__", True, [other])

    def __mul__(self, other):
        return Path(self, "__mul__", True, [other])

    def __truediv__(self, other):
        return Path(self, "__truediv__", True, [other])

    def __floordiv__(self, other):
        return Path(self, "__floordiv__", True, [other])

    def __mod__(self, other):
        return Path(self, "__mod__", True, [other])
    
    def __divmod__(self, other):
        return Path(self, "__divmod__", True, [other])

    def __pow__(self, other, modulo=None):
        return Path(self, "__pow__", True, [other, modulo])

    def __lshift__(self, other):
        return Path(self, "__lshift__", True, [other])

    def __rshift__(self, other):
        return Path(self, "__rshift__", True, [other])

    def __and__(self, other):
        return Path(self, "__and__", True, [other])

    def __or__(self, other):
        return Path(self, "__or__", True, [other])

    def __xor__(self, other):
        return Path(self, "__xor__", True, [other])

    def __radd__(self, other):
        return Path(self, "__add__", True, [other])

    def __rsub__(self, other):
        return Path(self, "__sub__", True, [other])

    def __rmul__(self, other):
        return Path(self, "__mul__", True, [other])

    def __rtruediv__(self, other):
        return Path(self, "__truediv__", True, [other])

    def __rfloordiv__(self, other):
        return Path(self, "__floordiv__", True, [other])

    def __rmod__(self, other):
        return Path(self, "__mod__", True, [other])
    
    def __rdivmod__(self, other):
        return Path(self, "__divmod__", True, [other])

    def __rpow__(self, other):
        return Path(self, "__pow__", True, [other, modulo])

    def __rlshift__(self, other):
        return Path(self, "__lshift__", True, [other])

    def __rrshift__(self, other):
        return Path(self, "__rshift__", True, [other])

    def __rand__(self, other):
        return Path(self, "__and__", True, [other])

    def __ror__(self, other):
        return Path(self, "__or__", True, [other])

    def __rxor__(self, other):
        return Path(self, "__xor__", True, [other])

    def __neg__(self):
        return Path(self, "__neg__", True)

    def __pos__(self):
        return Path(self, "__pos__", True)

    def __abs__(self):
        return Path(self, "__abs__", True)

    def __invert__(self):
        return Path(self, "__invert__", True)

    def __complex__(self):
        return Path(self, "__complex__", True)

    def __int__(self):
        return Path(self, "__int__", True)

    def __float__(self):
        return Path(self, "__float__", True)

    def __round__(self):
        return Path(self, "__round__", True)


        

class A(object):
    pass



def test():
    obj = A()
    g = (obj.b.c.d(5) for obj in [obj])
    obj.b = A()
    obj.b.c = A()
    obj.b.c.d = lambda x: x
    p = Path().b.c.d(5)
    q = 5 + Path().b.c.d(5)
    print(p.resolve_path(obj))
    print(next(g))
    print(q.resolve_path(obj))


if __name__ == "__main__":
    test()
