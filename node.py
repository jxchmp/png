#!/usr/bin/env python3

import itertools
import copy
import struct
import re
import operator
from validation import *
from path import Path


##############################################################################
# Node object                                                                #
##############################################################################

class Node(object):
    """
    A Node is an object which can contain other nodes or a value, which
    together make up a tree structure.

    A Node can either contain children or a value, but not both. Values that
    do not represent underlying data should be attributes of a node.
    """
    def __init__(self, name, parent):
        self._name = name
        self._children = []
        self._attributes = {}
        self._metadata = {}
        self._parent = parent
        if self._parent:
            self._parent._children.append(self)

    def __str__(self):
        #return "Node({}, {})".format(self._name, repr(self._parent))
        return self._qualname()

    def _qualname(self):
        s = []
        node = self
        while node:
            n = []
            n.append(node._name)
            if node._parent:
                siblings = [sib for sib in node._parent._children
                            if sib._name == node._name]
                if len(siblings) > 1:
                    n.append("[")
                    n.append(str(siblings.index(node)))
                    n.append("]")
            s.append("".join(n))
            node = node._parent
        return ".".join(reversed(s))


    def __getattr__(self, name):
        val = self._attributes.get(name)
        if val is not None:
            return val
        val = self._metadata.get(name)
        if val is not None:
            return val
        for child in self._children:
            if child._name == name:
                return child
        raise AttributeError("'{}' object has no attribute '{}'".format(
            self._name, name
        ))

    def tree_string(self):
        s = []
        stack = [(self,0)]
        while stack:
            node, depth = stack.pop()
            indent = "  " * depth
            s.append(indent + "Node("+ node._name + ")")
            for k,v in sorted(node.metadata.items()):
                if k != "definition":
                    s.append(("  " * (depth + 1)) + k + ": " + str(v))
            for k,v in sorted(node.attributes.items()):
                s.append(("  " * (depth + 1)) + k + ":" + str(v)[:32])
            for child in reversed(node.children):
                stack.append((child, depth + 1))
        return "\n".join(s)


    def add_data(self, d, meta=False):
        """
        Add the key: value pairs in d to the attributes or metadata of
        this node. This is non-destructive - if the key already exists
        then the value is changed to a list if necessary and the new
        value appended to it.
        """
        attrdict  = self._metadata if meta else self._attributes
        for k,v in d.items():
            if k in attrdict:
                if isinstance(attrdict[k], list):
                    attrdict[k].append(v)
                else:
                    attrdict[k] = [attrdict[k]]
                    attrdict[k].append(v)
            else:
                attrdict[k] = v

    @property
    def root(self):
        """
        Return the root node of the tree containing this node.
        """
        node = self
        for ancestor in self.ancestors():
            node = ancestor
        return node

    @property
    def siblings(self):
        """
        Return a list of sibling nodes including this node. i,e. the
        children of this node's parent.
        """
        return self._parent._children if self._parent else []

    @property
    def children(self):
        """
        Return a list of this node's children.
        """
        return self._children

    @property
    def parent(self):
        """
        Return this node's parent
        """
        return self._parent

    @property
    def attributes(self):
        """
        Return the attributes of this node.
        """
        return self._attributes

    @property
    def metadata(self):
        """
        Return the metadata of this node.
        """
        return self._metadata

    def matches(self, criteria=None):
        """
        Return True if all criteria functions return True when called
        with this node as their argument. If no criteria are given
        return True. Otherwise, return False.
        """
        if criteria is None:
            return True
        return all(criterion(self) for criterion in criteria)

    def gen_ancestors(self, criteria=None, or_self=False):
        """
        Return a generator iterating over the ancestor nodes of this
        node, for which all the criteria functions return True. If
        no criteria are given, all ancestor nodes are yielded. If
        or_self is True, then this node is included if it meets the
        criteria.
        """
        node = self if or_self else self._parent
        while node:
            if node.matches(criteria):
                yield node
            node = node._parent

    def ancestors(self, criteria=None, or_self=False):
        return [node for node in self.gen_ancestors(criteria, or_self)]

    def gen_descendents(self, criteria=None, or_self=False):
        """
        Return a generator, iterating over the descendent nodes of
        this node, for which all the criteria functions return True.
        If no criteria are given, all descendent nodes are yielded.
        If or_self is True, then this node is also included if it
        meets the criteria.
        """
        stack = [self] if or_self else list(reversed(self._children))
        while stack:
            node = stack.pop()
            if node.matches(criteria):
                yield node
            stack.extend(list(reversed(node._children)))

    def descendents(self, criteria=None, or_self=False):
        return [node for node in self.gen_descendents(criteria, or_self)]

    def count_descendents(self, criteria=None, or_self=False):
        return len(self.descendents(criteria, or_self))

    def __iter__(self):
        for node in self.descendents(or_self=True):
            yield node

    def all_nodes(self):
        return [node for node in self]

    def index(self, node=None):
        node =  node if node else self
        return self.root.all_nodes().index(node)
