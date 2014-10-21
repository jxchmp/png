#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class AttributeProcessingError(Exception):
    pass

class Attribute(object):
    def __init__(self, name, func, funcargs=None, funckwargs=None):
        self.funcargs = funcargs if funcargs is not None else []
        self.funckwargs = funckwargs if funckwargs is not None else {}
        self.name = name
        self.func = func
        self.is_attribute_method = True

    def __call__(self, node):
        funcargs = []
        for arg in self.funcargs:
            if hasattr(arg, "resolve_path"):
                funcargs.append(arg.resolve_path(node))
            else:
                funcargs.append(arg)
        funckwargs = {}
        for k,v in self.funckwargs.items():
            if hasattr(v, "resolve_path"):
                funckwargs[k] = v.resolve_path(node)
            else:
                funckwargs[k] = v
        if hasattr(self.func, "resolve_path"):
            return (self.name, self.func.resolve_path(node))
        else:
            return (self.name, self.func(node, *funcargs, **funckwargs))
            



