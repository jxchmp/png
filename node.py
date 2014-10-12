#!/usr/bin/env python3

import itertools
import copy
import structq

class ValidationException(Exception):
    """
    Base class for Validation exceptions, which are raised by validation
    methods. Validation exceptions are classed by 'level', from Info to
    Fatal.
    """
    levels = ["Info", "Warning", "Error", "Fatal"]
    def __init__(self, text, recovery_func=None, recovery_args=None,
                 recovery_kwargs=None):
        self.text = text
        self.recovery_func = recovery_func
        self.recovery_args = recovery_args if recovery_args else []
        self.recovery_kwargs = recovery_kwargs if recovery_kwargs else {}
        if self.level != 3 and self.recovery_func:
            raise ValueError("recovery_func provided for validation" +
                "exception with a level other than 'Error'")
            )

    def __str__(self):
        return "{}: {}".format(self.levels[self.level], self.text)

class ValidationInfo(ValidationException):
    """
    Exception representing Info level validation issues. An Info level
    validation exception should be raised for situations that are correct
    and require no special handling, but are in some way unusual.
    """
    level = 0

class ValidationWarning(ValidationException):
    """
    Exception representing Warning level validation issues. A Warning level
    validation exception should be raised for situations that are not
    correct and indicate a possible problem, but which require no special
    handling.
    """
    level = 1

class ValidationError(ValidationException):
    """
    Exception representing Error level validation issues. An Error level
    validation exception should be raised for situations that are incorrect
    and will require some special handling if parsing is to continue.
    """
    level = 2

class ValidationFatal(ValidationException):
    level = 3

def Attribute(f):
    """
    Decorator for attribute methods
    """
    f.is_attribute_method = True
    return f

class Validation(object):
    """
    Decorators for validation methods
    """
    @classmethod
    def _validation(cls, f, stage):
        f.is_validation_method = True
        f.stage = stage
        return f

    @classmethod
    def pre(f):
        return cls._validation(f, "pre")

    @classmethod
    def per_child_validation(cls, f):
        return cls._validation(f, "per_child")

    @classmethod
    def pre_derivation_validation(cls, f):
        return cls._validation(f, "pre_derivation")

    @classmethod
    def post_validation(cls, f):
        return cls._validation(f, "post")
    

class BaseNode(object):
    def __init__(self, name, parent):
        self._name = name
        self._children = []
        self._attributes = {}
        self._metadata = {}
        self._parent = parent
        if self._parent:
            self._parent._children.append(self)

    def add_data(self, d, meta=False):
        attrdict  = self._metadata if meta else self._attributes
        for k,v in d.items():
            if k in attrdict:
                if isinstance(attrdict[k], list):
                    attrdict.[k].append(v)
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

    def matches(self, criteria=None):
        """
        Return True if all criteria functions return True when called
        with this node as their argument. If no criteria are given
        return True. Otherwise, return False.
        """
        if criteira=None:
            return True
        return all(criterion(self) for criterion in criteria)

    def ancestors(self, criteria=None, or_self=False):
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
        return nodes

    def descendents(self, criteria=None, or_self=False):
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


class Definition(object):
    """
    Base class for definitions, which represent a definition of the structure
    of a filetype or a substructure of a filetype.
    """
    value_error_msg = ("Expected list and dict in value_func argument, but" +
                       "found {} and {}")
    def __init__(self, name, value_func=None, children=None, attributes=None,
                 validation=None, **kwargs):
        """
        Initialise the Definition. The only required argument is name, which
        is a label for the structure or substructure defined by the definition.
        Optional arguments are:
            value_func - Either a callable or a list containing a callable,
                and optionally a list of arguments and/or a dictionary of
                keyword arguments to be passed to the function when called.
                The function should take a source object and a node as
                arguments and whatever other arguments and keyword arguments
                that have been provided. If a value_func is provided then
                children should be None.
            children - A list of definitions that represent the substructures
                that the defined node contains. If children is provided then
                valuefunc should be None.
            attributes - A list of functions that will be used to set the
                attributes of the node defined by this object. These should
                be derived values rather than representing some portion of
                the underlying file.
            validation - A list of callables that will be used to validate
                the children and/or attributes of the node defined by this
                object.
        """
        self.name = name
        self._set_value_func_values(value_func)
        self.children = children if children else []
        self.attributes = self._get_attributes(attributes)
        self.validation = self._get_validation(validation)
        self._set_kwargs(kwargs)
        if self.children and self.value_func:
            raise ValueError("Cannot define both children and a " +
                             "value_func on the same Node.")
        elif not self.children and not self.value_func:
            raise ValueError("Either children or value_func must be defined" +
                " but both were None.")

    def _get_attributes(self, attributes):
        """
        Return a list of attribute methods composed of the given attributes
        and any method in the class or base classes that 
        """
        attributes = attributes if attributes else []
        method_names = set()
        for cls in type(self).mro():
            for k, v in cls.__dict__.items():
                if k not in method_names:
                    if hasattr(v, "is_attribute_method"):
                        attributes.append(v)
                        method_names.add(k)
        return attributes

    def _get_validation(self, validation):
        validation = validation if validation else {}
        method_names = set()
        for cls in type(self).mro():
            for k, v in cls.__items():
                if k not in method_names:
                    if hasattr(v, "is_validation_method"):
                        validation.append(v)
                        method_names.add(k)
        return validation

    def _set_value_func_values(self, value_func):
        """
        Set the instance attributes value_func, value_func_args and
        value_func_kwargs based on the provided value_func argument.
        value_func can be one of:
            a callable
            a list containing a single callable
            a list containing a callable and a list of arguments
            a list containing a callable and a dictionary of keyword args
            a list containing a callable, a list of args and a dictionary
                of keyword args.
        Raises ValueError if the value_func argument is not one of the above.
        """
        self.value_func = None
        self.value_func_args = None
        self.value_func_kwargs = None
        # make value_func a list and pad it with None so it's at least
        # three items long.
        value_func = list(value_func)
        while len(value_func) < 3:
            value_func.append(None)
        self.value_func, vf1, vf2 = value_func
        # the first element of the value_func list must be callable
        if self.value_func and not callable(self.value_func):
            raise ValueError("Expected value_func[0] to be callable")
        # check that the other parts of the value_func are the right type
        for arg, n in ((vf1, 1), (vf2, 2)):
            if arg and not isinstance(arg, (list, dict):
                raise ValueError(("Expected value_func[{}] to be list, " +
                    "dict or None, but found {}").format(
                       n,  vf1.__class__.__name__))
        # check that, if both args and kwargs are provided, we have a list
        # and a dict
        if vf1 and vf2 and type(vf1) == type(vf2):
            raise ValueError(value_error_msg.format(
                vf1.__class__.__name__, vf2.__class__.__name))
        # set args to the list and kwargs to the dict (or None if the
        # args/kwargs were not provided
        self.value_func_args = vf1 if isinstance(vf1, list) else vf2
        self.value_func_kwargs = vf1 if isinstance(vf1, dict) else vf2
    
    def _set_kwargs(self, kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)

    def resolve(self, attr, node):
        """
        Instance attributes may be either actual values, or may be 'future'
        values, which don't exist at the time the structure is defined. This
        takes an instance attribute and the Node object created at the point
        that the construct method is called and returns the resolved value
        of the attribute.
        """
        if hasattr(attr, "resolve_path"):
            return attr.resolve_path(node)
        else:
            return attr

    def resolve_all(self):
        """
        Return a dictionary of instance attributes in which all instance
        attributes are resolved to their value at the point of construction.
        """
        resolved = {}
        for k,v in self.__dict__.items():
            val = v if not hasattr(v, "resolve_path") else v.resolve_path(node)
            resolved[k] = val
        return resolved
            

    def __str__(self):
        return (
            "{cls}({name}, value_func={value_func}, " +
            "value_func_args={value_func_args}, " +
        resolved = self.resolve_all(node)
            "value_func_kwargs={value_func_kwargs}, children={children}, " +
            "attributes={attributes}, validation={validation})").format(
                cls = self.__class__.__name__,
                nodeclass = self.nodeclass,
                value_func = self.value_func,
                value_func_args = self.value_func_args,
                value_func_kwargs = self.value_func_kwargs,
                children = self.children,
                attributes = self.attributes,
                validation = self.validation
        )

    def validate_stage(self, node, stage, descendent=None):
        issues = []
        for validation in (v for v in self.validation if v.stage=stage):
            try:
                validation(node, descendent)
            except ValidationException as err:
                issues.append(err)
        node.add_data({"validation": issues}, meta=True)
        return issues

    def construct(self, source, parent=None, node=None):
        # If node is None then this has been called on the original
        # definition. This creates a copy of the definition instance and
        # replaces the __dict__ with a copy of this instance's dict where
        # all resolvable instance attributes are resolved to actual values.
        # i.e. validation, attribute and value functions can ignore the
        # distinction between real instance attributes and resolved attributes
        # and simply refer to the attribute in the usual way.
        if node is None:
            node = self.nodeclass(parent)
            facade = copy.copy(self)
            facade.__dict__ = self.resolve_all(node)
            return facade.construct(source, parent, node)
        # This must be a resolved copy of the definition, so do the actual
        # node construction work here.
        node.add_data({"definition": self}, meta=True)
        self.validate_stage(node, "pre")
        node.add_data(source.get_preread_metadata(node), meta=True)
        if self.value_func:
            node.add_data({"value":
                self.value_func(node, source, *self.value_func_args,
                                **self.value_func_kwargs)
            })
        for childdef in self.children:
            childnode = childdef.construct(source, node)
            self.validate_stage(node, "per_child", childnode)
        self.validate_stage(node, "pre_derivation")
        for k, v in (attr(node) for attr in self.attributes):
            node.add_data({k:v})
        self.validate_stage(node, "post")
        node.add_data(source.get_postread_metadata(node), meta=True)
        return node


class FileSource(object):
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")

    def get_preread_metadata(self, node):
        return {"source": self.path,
                "start_index": self.f.tell()}

    def get_postread_metadata(self, node):
        end = self.f.tell()
        return {"end_index": end,
                "length": end - node._metadata["start_index"]}

    def read(self, n=1):
        data = self.f.read(n)
        if len(data) < n:
            raise EOFError()


class StaticDef(Definition):
    def __init__(self, name, staticbytes, attributes=None, validation=None):
        super().__init__(name, self.get_value, attributes=attributes,
                         validation=validation, staticbytes=staticbytes)

    def get_value(self, node, source, *args, **kwargs)
        return source.read(self.staticbytes)

    @Validation.post_validation
    def validate(self, node, *args, **kwargs):
        if node._attributes["value"] != self.staticbytes:
            raise ValidationFatal("Expected {} but found {}".format(
            self.staticbytes, node._attributes["value"]))


class IntegerDef(Definition):
    def __init__(self, name, structformat, attributes=None, validation=None):
        super().__init__(name, self.get_value, attributes=attributes,
                         validation=validation, structformat=structformat)

    def get_value(self, node, source, *args, **kwargs):
        size = struct.calcsize(self.structformat)
        return struct.unpack(self.structformat, source.read(size))[0]
        

class IntegerSequenceDef(Definition, IntegerDef):
    def __init__(self, name, structformat, items, subseq_length=1,
                 attributes=None, validation=None):
        super().__init__(name, self.get_value, attributes=attributes,
                         validation=validation, structformat=structformat,
                         items = items, subseq_length = subseq_length)

    def get_value(self, node, source, *args, **kwargs):
        return tuple(
            [tuple(
                [IntegerDef.get_value(self, node, source)
                 for j in range(self.subseq_length)]
            ) for i in range(self.items)]
        )


class BytestringDef(Definition):
    def __init__(self, name, length, attributes=None, validation=None):
        super().__init__(name, self.get_value, attributes=attributes,
                         validation=validation, length=length)

    def get_value(self, node, source, *args, **kwargs):
        return source.read(self.length)


class StringDef(Definition):
    def __init__(self, name, length, encoding='utf8', attributes=None,
                 validation=None):
        super().__init__(name, self.get_value, attributes=attributes,
                         validation=validation, length=length,
                         encoding=encoding)

    def get_value(self, node, source, *args, **kwargs):
        return self.decode_value(node, source.read(self.length))

    def decode_value(self, node, val):
        try:
            return val.decode(self.encoding, errors="strict")
        except (ValueError, UnicodeDecodeError) as err:
            node.add_data({"validation": str(err)})
            return val.decode(self.encoding, errors="replace")
           

class NullTerminatedStringDef(Definition):
    def __init__(self, name, encoding='utf8', attributes=None,
                 validation=None):
        super().__init__(name, self.get_value, attributes=attributes,
                         validation=validation, encoding=encoding)

    def get_value(self, node, source, *args, **kwargs):
        return self.decode_value(
            node, bytearray(b for b in iter(source.read, b'\x00')))
