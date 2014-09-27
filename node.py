#!/usr/bin/env python3

from collections import deque
from operator import *
import struct
import inspect
import re

class BufferReadError(Exception):
    pass


class _Node(object):
    _allowed_attributes = ("warnings")
    _attribute_defaults = {"warnings": list}

    def __init__(self, parent, **kwargs):
        self.parent = parent
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
        self._derive(derivations)
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
                        s.append("{}{} = {}".format(
                        "  " * (depth+1), attr, str(val)))
            for child in reversed(node.children):
                stack.append((child, depth + 1))
        return "\n".join(s)
        
    @classmethod
    def from_buffer(cls, buffer, parent):
        raise NotImplementedError

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
                    self.warnings.append(warning)

    def _derive(self, attributes):
        methods = [("derive_" + attr, attr) for attr in attributes]
        for method, attribute in methods:
            if hasattr(self, method):
                setattr(self, attribute, getattr(self, method)())
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

    def find(self, classnames, attributes=None, limit=None):
        count = 0
        for node in self.iter_depth_first():
            if node.match(classnames, attributes):
                yield node
                count = count + 1
            if limit is not None and count == limit:
                break

    @classmethod
    def consume_byte(cls, buff):
        return cls.consume_bytes(buff, 1)[0]

    @classmethod
    def consume_bytes(cls, buff, n):
        data = buff.read(n)
        if data is None or len(data) < n:
            raise BufferReadError
        return data

        


def Node(name, allowed_attributes=None, defaults=None, clsattrs=None):
    if allowed_attributes is None:
        allowed_attributes = []
    _allowed_attributes = [_Node._allowed_attributes]
    _allowed_attributes.extend(allowed_attributes)
    if defaults is None:
        defaults = {}
    defaults.update(_Node._attribute_defaults)
    if clsattrs is None:
        clsattrs = {}
    clsattrs["_allowed_attributes"] = tuple(_allowed_attributes)
    clsattrs["_attribute_defaults"] = defaults
    return type(name, (_Node,), clsattrs)


def StaticNode(name, staticbytes, extra_attributes=None):
    def from_buffer(cls, buff, parent):
        for val in cls._staticbytes:
            buffval = cls.consume_byte(buff)
            if val != buffval:
                raise BufferReadError(
                    "Expected value {} not found.".format(
                        cls._staticbytes
                    )
                )
        return cls(parent)
    return Node(name,
        allowed_attributes = extra_attributes,
        clsattrs={
            "_staticbytes": staticbytes,
            "from_buffer": classmethod(from_buffer)
        })
   
def DefinedChildrenNode(name, substructures, extra_attributes=None):
    def from_buffer(cls, buff, parent):
        node = cls(parent)
        for substructure in cls._substructures:
            node.children.append(substructure.from_buffer(buff, node))
        return node
    return Node(name,
        allowed_attributes = extra_attributes,
        clsattrs={
            "_substructures": substructures,
            "from_buffer": classmethod(from_buffer)
        })

def IntegerNode(name, structformat, extra_attributes=None):
    def from_buffer(cls, buff, parent):
        size = struct.calcsize(cls._structformat)
        value = struct.unpack(cls._structformat, cls.consume_bytes(buff, size))[0]
        return cls(parent, value=value)
    allowed_attributes = ["value"]
    if extra_attributes:
        allowed_attributes.extend(extra_attributes)
    return Node(name,
        allowed_attributes = allowed_attributes,
        clsattrs={
            "_structformat": structformat,
            "from_buffer": classmethod(from_buffer)
        })

def IntegerSequenceNode(name, structformat, items, subseq_length=1,
                        extra_attributes=None):
    def from_buffer(cls, buff, parent):
        size = struct.calcsize(cls._structformat)
        seq = []
        for i in range(items):
            thisseq = []
            for j in range(subseq_length):
                val = cls.consume_bytes(buff, size)
                thisseq.append(struct.unpack(cls._structformat, val)[0])
            if len(thisseq) == 1:
                seq.append(thisseq[0])
            else:
                seq.append(thisseq)
        return cls(parent, value=seq)
    allowed_attributes = ["value"]
    if extra_attributes:
        allowed_attributes.extend(extra_attributes)
    return Node(name,
        allowed_attributes = allowed_attributes,
        clsattrs={
            "_structformat": structformat,
            "from_buffer": classmethod(from_buffer)
        })

def StringNode(name, length, encoding='utf8', extra_attributes=None):
    def from_buffer(cls, buff, parent):
        bytestring = cls.consume_bytes(buff, length)
        if len(bytestring) != length:
            raise BufferReadError
        return cls(parent, value=bytestring.decode(encoding))
    allowed_attributes = ["value"]
    if extra_attributes:
        allowed_attributes.extend(extra_attributes)
    return Node(name,
        allowed_attributes = allowed_attributes,
        clsattrs={
            "from_buffer": classmethod(from_buffer)
        })

def NullTerminatedStringNode(name, encoding='utf8', extra_attributes=None):
    def from_buffer(cls, buff, parent):
        bytestring = bytearray()
        while True:
            byte = self.consume_byte(1)
            if byte == 0:
                break
            else:
                bytestring.append(byte)
        return cls(parent, value=bytestring.decode(encoding))
    allowed_attributes = ["value"]
    if extra_attributes:
        allowed_attributes.extend(extra_attributes)
    return Node(name,
        allowed_attributes = allowed_attributes,
        clsattrs={
            "from_buffer": classmethod(from_buffer)
        })


def NodeSequenceNode(name, childclass, items=None, stop=None,
                     extra_attributes=None):
    def from_buffer(cls, buff, parent):
        node = cls(parent)
        if cls._items is None:
            while True:
                try:
                    childnode = cls._childclass.from_buffer(buff, node)
                    node.children.append(childnode)
                except BufferReadError:
                    break
                if stop is not None and stop(node):
                    break                        
        else:
            for i in range(cls._items):
                childnode = cls._childclass.from_buffer(buff, node)
                node.children.append(childnode)
                if stop is not None and stop(node):
                    break
        return node
    allowed_attributes = []
    if extra_attributes:
        allowed_attributes.extend(extra_attributes)
    return Node(name, clsattrs={
        "_childclass": childclass,
        "_items": items,
        "from_buffer": classmethod(from_buffer)
        })


def DelegatingNode(classdict, keyfunc):
    def from_buffer(cls, buff, parent):
        key = keyfunc(parent)
        vals = cls._classdict.get(key)
        if vals is None:
            vals = cls._classdict.get("default")
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
        return nodecls(name, *args2, **kwargs2).from_buffer(buff, parent)
    return type("delegating_node", (object,),
        {
            "_classdict": classdict,
            "from_buffer": classmethod(from_buffer)
        })



