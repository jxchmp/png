#!/usr/bin/env python3

import re
from operator import *
from types import SimpleNamespace

class PathParseError(Exception):
    def __init__(self, message, path, subpaths):
        super().__init__(
            "{}\npath: {}\nsubpaths: {}".format(
                message, path, subpaths
            )
        )


class Path(object):
    node_classes = []
    contexts = set("start") 

    def __init__(self, path):
        self.path = path
        self.path_root = self.parse(path)

    def __str__(self):
        return str(self.path_root)

    @classmethod
    def register(cls, nodecls):
        nodecls.re = re.compile(nodecls.pattern)
        cls.node_classes.append(nodecls)
        cls.node_classes.sort(key=PathNode.sortkey)

    def iter_nodecls(self):
        for nodecls in self.node_classes:
            yield nodecls

    def parse(self, path, parentnode=None):
        parentnode = parentnode if parentnode else PathNode()
        for nodecls in self.iter_nodecls() :
            match = nodecls.re.search(path)
            if match:
                print(match.groups())
                groups = match.groups()
                if nodecls.terminal:
                    node = nodecls(parentnode, groups[0])
                else:
                    node = nodecls(parentnode, groups[1])
                    for s in filter(bool, (groups[0], groups[2])):
                        self.parse(s, node)
                break
        else:
            raise PathParseError("No match found", path, ())
        return parentnode
               

class PathNode(object):
    terminal = False
    def __init__(self, parent=None, value=None):
        if parent:
            parent.add_child(self)
        self.children = []

    def __str__(self):
        return "{}(\n{}\n)".format(
            self.__class__.__name__,
            "\n".join("    " + line for line in 
                "\n".join(
                    str(child) for child in self.children
                 ).split("\n")
            )
        )        

    @staticmethod
    def sortkey(cls):
        return cls.precedence

    def add_child(self, child):
        self.children.append(child)

    def __iter__(self):
        return iter(self.children)

    def evaluate(self, nodes):
        return [child.evaluate(nodes) for child in self]


class TerminalNode(PathNode):
    terminal = True
    def __init__(self, parent=None, value=None):
        parent.add_child(self)
        self.value = value

    def __str__(self):
        return "{}".format(self.value)
        
    def evaluate(self, node):
        return node.value
    
@Path.register
class SelfNode(TerminalNode):
    precedence = 0 
    pattern = r"^(\.)$"

@Path.register
class NameNode(TerminalNode):
    precedence = 0
    pattern = r"^([_a-zA-Z][_a-zA-Z0-9]+)$"

@Path.register
class NumberNode(TerminalNode):
    precedence = 0
    pattern = r"^(\d+)$"

@Path.register
class AllNode(TerminalNode):
    precedence = 0
    pattern = r"^(\*)$"

@Path.register
class DescendentOrSelfNode(PathNode):
    precedence = 45 
    pattern = r"^([^/]*?)(//)(.*)$"

@Path.register
class StepNode(PathNode):
    precedence = 50 
    pattern = r"^(.*?)(/)([^/].*?)$"

@Path.register
class PredicateNode(PathNode):
    precedence = 40
    pattern = r"^([_a-zA-Z][_a-zA-Z0-9]+|\*?)()(\[(.*?|\d+)\].*)$"

@Path.register
class AttributeNode(PathNode):
    precedence = 50
    pattern = r"^()(\@)([_a-zA-Z][_a-zA-Z0-9]+|\*)$"


@Path.register
class EqualsNode(PathNode):
    precedence = 45 
    pattern = r"^(.+)(=)(.+)"



def test():
    paths = [
        "./author",
        "author",
        "first_name",
        "/bookstore",
        "//author",
        "book[/bookstore/@speciality=@style]",
        "author/first_name",
        "bookstore//title",
        "bookstore//book/excerpt//emph",
        ".//title",
        "author/*",
        "book/*/last_name",
        "*/*",
        "*[@specialty]",
        "@style",
        "price/@exchange",
        "price/@exchange/total",
        "book[@style]",
        "@*",
        "./first_name",
        "first_name",
        "author[1]",
        "author[first_name][3]",
    ]
    for p in paths:
        print(p)
        print(Path(p))

test()

"""
@Path.register
class Number(TerminalNode):
    # 20
    pattern = r"^()(\d+)()$"
    precedence = 10

@Path.register
class P1(PathNode):
    # (nn) -> '' 'nn' ''
    pattern = r"^()(?:\()(.*)()(?:\))$"
    precedence = 11

@Path.register
class P2(PathNode):
    # nn(nn) -> '' 'nn' '(nn)'
    pattern = r"^()(\d+)(\(.+\))"
    precedence = 12

@Path.register
class P3(PathNode):
    # (nn)nn -> '' '(nn)' 'nn'
    pattern = r"^()(\(.*\))(\d+$)"
    precedence = 13


def test():
    tests = ["20",
             "(20)",
             "(20(30))",
             "((20(30)))",
             "((20(30(40))))",
             "(20((30)30)30)"]
    for t in tests:
        print(t)
        print(Path(t))

if __name__ == "__main__":
    test()
"""
    
