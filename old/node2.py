#!/usr/bin/env python3

from collections import deque
from operator import *
import struct
import re


def is_in(a,b):
    """
    Another operator for more sensible semantics than __contains__ (i.e. in
    terms of validation, it makes more sense to say value is in
    a list of acceptable values).
    """
    return a in b

def between(a,b):
    """
    An additional operator to allow the common case of a value being valid
    when in a given range of values, rather than having to chain a less
    than and greater than check together. The range given is inclusive of
    the high and low values.
    """
    low, high = b
    return low <= a <= high

"""
Mapping of useful operator functions to string values for use in
automatic generation of warnings on validation errors.
"""
op_names = {
    lt: "<",
    le: "<=",
    eq: "==",
    ne: "!=",
    ge: ">=",
    gt: ">",
    not_: "not",
    truth: "true",
    contains: "be contained in",
    is_in: "in",
    between: "between"
}

class BufferReadError(Exception):
    pass

class Path(object):
    number = re.compile(r"^-?\d+$")
    name = re.compile(r"^[_a-zA-Z][_a-zA-Z0-9]*$")
    predicate = re.compile("(^.*)\[(.*)\]$")

    def __init__(self, path, transform=None):
        path =  path.replace("//", "#/").split("/")
        path = [el.replace("#", "//") for el in path]
        self.path = []
        for el in path:
            predicate_match = self.predicate.match(el)
            if predicate_match:
                self.path.append(predicate_match.groups())
            else:
                self.path.append((el, ""))
        self.transform = transform

    def __call__(self, node, first=True):
        nodes = [node]
        for nav, predicate in self.path:
            #print(nav, predicate)
            #for n in nodes:
            #    print("\t" + str(n))
            #    for nc in n.children:
            #        print("\t\t" + str(nc))
            if nav == "..":
                nodes = [n.parent for n in nodes]
            elif nav == ".":
                nodes = [n for n in nodes]
            elif nav == "*":
                _nodes = []
                for node in nodes:
                    _nodes.extend(node.children)
                nodes = _nodes
            elif nav == "//":
                nodes = [n.root for n in nodes]
            elif self.number.match(nav):
                nodes = [n.children[int(nav)] for n in nodes]
            elif self.name.match(nav):
                nodes = [getattr(n, nav) for n in nodes]
            if predicate:
                nodes = self.apply_predicate(nodes, predicate)
        if self.transform:
            nodes = [self.transform(n, node) for n in nodes]
        if first:
            return nodes[0]
        else:
            return nodes

    def apply_predicate(self, nodes, predicate):
        attrib, value = predicate.split("=")
        filtered_nodes = []
        for node in nodes:
            if hasattr(node, attrib):
                if getattr(node, attrib) == value:
                    filtered_nodes.append(node)
        return filtered_nodes

class _Node(object):
    _allowed_attributes = ("warnings")
    _attribute_defaults = {"warnings": list}

    def __init__(self, parent, noprocess=False, **kwargs):
        self.classname = self.__class__.__name__
        self.parent = parent
        #print(self.qualname, kwargs)
        self.children = []
        for name, val in kwargs.items():
            if name in self._allowed_attributes:
                setattr(self, name, val)
            else:
                raise AttributeError("Unknown attribute: {}".format(
                ))
        derivations = []
        for name in self._allowed_attributes:
            if not hasattr(self, name):
                if name in self._attribute_defaults:
                    default = self._attribute_defaults[name]
                    if callable(default):
                        default = default()
                    setattr(self, name, default)
                else:
                    derivations.append(name)
        self._derivations = derivations
        if not noprocess:
            self.derive_and_validate()

    def __str__(self):
        v = ""
        if hasattr(self, "value"):
            v = str(self.value)
            if len(v) > 32:
                v = v[:29] + "..."
        return "{}({})".format(self.qualname, v)

    @property
    def qualname(self):
        if self.parent:
            return self.parent.qualname + "." + self.classname
        else:
            return self.classname

    def derive_and_validate(self):
        self._derive(self._derivations)
        self._validate()

    def tree_string(self):
        s = []
        stack = [(self,0)]
        while stack:
            node, depth = stack.pop()
            indent = "  " * depth
            s.append(indent + "Node("+ node.__class__.__name__ + ")")
            for attr in node._allowed_attributes:
                if hasattr(node, attr):
                    val = getattr(node, attr)
                    if val != []:
                        if isinstance(val, list):
                            if len(val) > 8:
                                val = str(val[:8])[:-1] + ", ...]"
                        elif isinstance(val, bytes):
                            if len(val) > 64:
                                val = bytearray(val)[:64]
                                val.extend(b'...')
                                val = bytes(val)
                        s.append("{}{} = {}".format(
                        "  " * (depth+1), attr, str(val)))
            for child in reversed(node.children):
                stack.append((child, depth + 1))
        return "\n".join(s)
        
    @classmethod
    def from_buffer(cls, buffer, parent):
        raise NotImplementedError

    @classmethod
    def all_from_buffer(cls, buffer, parent):
        return [node for node in cls.from_buffer(buffer, parent)][0]

    @property
    def root(self):
        if self.parent is None:
            return self
        else:
            return self.parent.root

    @property
    def siblings(self):
        if self.parent is None:
            return []
        else:
            return self.parent.children

    def _validate(self):
        validation_methods = ["validate"]
        validation_methods.extend(["validate_" + attr
                                   for attr in self._allowed_attributes])
        for method in validation_methods:
            if hasattr(self, method):
                warning = getattr(self, method)()
                if warning:
                    if isinstance(warning, (list, tuple)):
                        self.warnings.extend(warning)
                    else:
                        self.warnings.append(warning)

    def _derive(self, attributes):
        methods = [("derive_" + attr, attr) for attr in attributes]
        for method, attribute in methods:
            if hasattr(self, method):
                try:
                    setattr(self, attribute, getattr(self, method)(self))
                except TypeError:
                    print("Error calling {} in {}".format(
                        method, self
                    ))
                    raise   
            elif method != "derive":
                raise ValueError

    def is_descendent_of(self, node):
        if self.parent is None:
            return False
        else:
            if self.parent is node:
                return True
            else:
                return self.parent.is_descendent_of(node)

    def is_ancestor_of(self, node):
        return node.is_descendent_of(self)

    def is_leaf(self):
        return self.children == []

    def iter_depth_first(self):
        stack = [self]
        while stack:
            node = stack.pop()
            for child in reversed(node.children):
                stack.append(child)
            yield node

    def iter_breadth_first(self):
        queue = deque([self])
        while queue:
            node = queue.popleft()
            queue.extend(node.children)
            yield node

    def match(self, classnames=None, attributes=None):
        if attributes is None:
            attributes = []
        if classnames is None or self.__class__.__name__ in classnames:
            for name, val in attributes:
                if hasattr(name):
                    if getattr(self, name) != val:
                        return False
                else:
                    return False
            return True
        return False 

    def find(self, classnames, attributes=None, limit=None):
        count = 0
        for node in self.iter_depth_first():
            if node.match(classnames, attributes):
                yield node
                count = count + 1
            if limit is not None and count == limit:
                break

    def find_all(self, classnames, attributes=None, limit=None):
        return [node for node in self.find(classnames, attributes, limit)]

    @classmethod
    def consume_byte(cls, buff):
        return cls.consume_bytes(buff, 1)[0]

    @classmethod
    def consume_bytes(cls, buff, n):
        if n < 1:
            raise BufferReadError(
                "Attempted to read negative bytes while reading {}".format(
                    cls.__name__))
        data = buff.read(n)
        if data is None or len(data) < n:
            raise BufferReadError(
                "End of file reached while reading {}".format(
                    cls.__name__))
        return data

def _default(arg):
    if callable(arg):
        return arg()
    else:
        return arg

def Node(name, allowed_attributes=list, defaults=dict, clsattrs=dict,
         validations=dict, derivations=dict):
    _allowed_attributes = [_Node._allowed_attributes]
    _allowed_attributes.extend(_default(allowed_attributes))
    defaults = _default(defaults)
    defaults.update(_Node._attribute_defaults)
    derivations = _default(derivations)
    _allowed_attributes.extend(list(derivations.keys()))
    clsattrs = _default(clsattrs)
    clsattrs["_allowed_attributes"] = tuple(_allowed_attributes)
    clsattrs["_attribute_defaults"] = defaults
    for validation_name, method in _default(validations).items():
        clsattrs["validate_" + validation_name] = method
    for derivation_name, method in derivations.items():
        clsattrs["derive_" + derivation_name] = method
    return type(name, (_Node,), clsattrs)

def simple_validation(name, op, value):
    def _(self):
        val = getattr(self, name)
        if op == contains:
            res = not op(value, val)
        else:
            res = not op(val, value)
        if res:
            return "Failed validation: {} '{}' {} {}".format(
                name, val, op_names[op], value)
    return _


def bit_flag(attr, bit, idx=None, transform=None):
    def _(self, *args):
        val = getattr(self, attr)
        if idx is not None:
            val = val[idx]
        if transform:
            val = transform(val)
        return val & (2**bit) > 0
    return _
    

def lookup(attr, d, default="unknown"):
    def _(self, *args):
        return d.get(getattr(self, attr), default)
    return _

def StaticNode(name, staticbytes, extra_attributes=list):
    @classmethod
    def from_buffer(cls, buff, parent):
        for val in cls._staticbytes:
            buffval = cls.consume_byte(buff)
            if val != buffval:
                raise BufferReadError(
                    "Expected value {} not found.".format(
                        cls._staticbytes
                    )
                )
        yield cls(parent)
    return Node(name,
        allowed_attributes = extra_attributes,
        clsattrs={
            "_staticbytes": staticbytes,
            "from_buffer": from_buffer
        })
   
def DefinedChildrenNode(name, substructures, **kwargs):
    @classmethod
    def from_buffer(cls, buff, parent):
        node = cls(parent, noprocess=True)
        yield node
        for substructure in cls._substructures:
            for child in substructure.from_buffer(buff, node):
                node.children.append(child)
        node.derive_and_validate()
    return Node(name,
        clsattrs={
            "_substructures": substructures,
            "from_buffer": from_buffer
        },
        **kwargs)


def _ValueNode(name, from_buffer, extra_attributes=list, extra_clsattrs=dict,
                **kwargs):
    allowed_attributes = ["value"]
    allowed_attributes.extend(_default(extra_attributes))
    clsattrs = {
        "from_buffer": classmethod(from_buffer)
    }
    clsattrs.update(_default(extra_clsattrs))
    return Node(name,
                allowed_attributes = allowed_attributes,
                clsattrs = clsattrs,
                **kwargs)
                

def IntegerNode(name, structformat, **kwargs):
    def from_buffer(cls, buff, parent):
        size = struct.calcsize(cls._structformat)
        value = struct.unpack(cls._structformat, cls.consume_bytes(buff, size))[0]
        yield cls(parent, value=value)
    return _ValueNode(name, from_buffer,
                     extra_clsattrs={"_structformat": structformat},
                     **kwargs)


def IntegerSequenceNode(name, structformat, items, subseq_length=1, **kwargs):
    outer = locals()
    def from_buffer(cls, buff, parent):
        if isinstance(cls._structformat, Path):
            _structformat = cls._structformat(parent)
        else:
            _structformat = cls._structformat
        if isinstance(outer["items"], Path):
            items = outer["items"](parent)
        else:
            items = outer["items"]
        if isinstance(outer["subseq_length"], Path):
            subseq_length = outer["subseq_length"](parent)
        else:
            subseq_length = outer["subseq_length"]
        size = struct.calcsize(_structformat)
        seq = []
        for i in range(items):
            thisseq = []
            for j in range(subseq_length):
                val = cls.consume_bytes(buff, size)
                thisseq.append(struct.unpack(_structformat, val)[0])
            if len(thisseq) == 1:
                seq.append(thisseq[0])
            else:
                seq.append(thisseq)
        yield cls(parent, value=seq)
    return _ValueNode(name, from_buffer,
                      extra_clsattrs={"_structformat": structformat},
                      **kwargs)

def BytestringNode(name, length, **kwargs):
    outer = locals()
    def from_buffer(cls, buff, parent):
        if isinstance(outer["length"], Path):
            length = outer["length"](parent)
        bytestring = cls.consume_bytes(buff, length)
        if len(bytestring) != length:
            raise BufferReadError(
                "End of buffer reached while reading {}".format(
                    outer["name"]))
        yield cls(parent, value=bytestring)
    return _ValueNode(name, from_buffer, **kwargs)


def StringNode(name, length, encoding='utf8', **kwargs):
    outer = locals()
    def from_buffer(cls, buff, parent):
        if isinstance(outer["length"], Path):
            length = outer["length"](parent)
        else:
            length = outer["length"]
        bytestring = cls.consume_bytes(buff, length)
        if len(bytestring) != length:
            raise BufferReadError(
                "End of buffer reached while reading {}".format(
                    outer["name"]))
        yield cls(parent, value=bytestring.decode(encoding))
    return _ValueNode(name, from_buffer, **kwargs)


def NullTerminatedStringNode(name, encoding='utf8', **kwargs):
    def from_buffer(cls, buff, parent):
        bytestring = bytearray()
        while True:
            byte = cls.consume_byte(buff)
            if byte == 0:
                break
            else:
                bytestring.append(byte)
        try:
            yield cls(parent, value=bytestring.decode(encoding))
        except UnicodeDecodeError:
            n = cls(parent, value=bytestring)
            n.warnings.append("Error decoding bytestring")
            yield n
    return _ValueNode(name, from_buffer, **kwargs)


def NodeSequenceNode(name, childclass, items=None, stop=None,
                     extra_attributes=None):
    outer = locals()
    @classmethod
    def from_buffer(cls, buff, parent):
        if isinstance(outer["items"], Path):
            items = outer["items"](parent)
        else:
            items = outer["items"]    
        node = cls(parent, noprocess=True)
        yield node
        if items is None:
            while True:
                try:
                    for child in cls._childclass.from_buffer(buff, node):
                       node.children.append(child)
                except BufferReadError:
                    break
                if stop is not None and stop(node):
                    break                        
        else:
            for i in range(items):
                for child in cls._childclass.from_buffer(buff, node):
                    node.children.append(child)
                if stop is not None and stop(node):
                    break
        node.derive_and_validate()
    allowed_attributes = []
    if extra_attributes:
        allowed_attributes.extend(extra_attributes)
    return Node(name, clsattrs={
        "_childclass": childclass,
        "_items": items,
        "from_buffer": from_buffer
        })


def DelegatingNode(classdict, keyfunc, **kwargs):
    @classmethod
    def from_buffer(cls, buff, parent):
        key = keyfunc(parent)
        vals = cls._classdict.get(key)
        if vals is None:
            vals = cls._classdict.get("default")
        if isinstance(vals, type):
            for child in vals.from_buffer(buff, parent):
                yield child
        else:
            vals = list(vals)
            if len(vals) == 2:
                vals.append([]),
            if len(vals) == 3:
                vals.append({})
            nodecls, name, args, kwargs = vals
            args2 = []
            kwargs2 = {}
            for arg in args:
                if callable(arg):
                    args2.append(arg(parent))
                else:
                    args2.append(arg)
            for kwarg in kwargs:
                if callable(kwargs):
                    kwargs2.append(arg(parent))
                else:
                    kwargs2.append(arg)
            ncl = nodecls(name, *args2, **kwargs2)
            for child in ncl.from_buffer(buff, parent):
                yield child
    return type("delegating_node", (object,),
        {
            "_classdict": classdict,
            "from_buffer": from_buffer
        })



