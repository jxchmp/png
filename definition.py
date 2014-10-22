#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from node import Node
from validation import *
from attribute import *
from path import Path

import itertools
import struct

DEBUG = False 

#############################################################################
# Definition base class                                                     #
#############################################################################

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
        and any method in the class or base classes that has the 
        is_attribute_method attribute set to a True value.
        """
        attributes = attributes if attributes else []
        method_names = set()
        # type(self).mro() returns a list of the base classes of this instance
        # in method resolution order. i.e. In the order that Python would
        # find them if called normally.
        for cls in type(self).mro():
            for k, v in cls.__dict__.items():
                if k not in method_names:
                    if hasattr(v, "is_attribute_method"):
                        if v.is_attribute_method:
                            attributes.append(v)
                            method_names.add(k)
        return attributes

    def _get_validation(self, validation):
        """
        Return a list of validation methods composed of the given validation
        methods and any method in the class or base classes that has the
        is_validation_method attribute set to a True value.
        """
        validation = validation if validation else [] 
        method_names = set()
        for cls in type(self).mro():
            for k, v in cls.__dict__.items():
                if k not in method_names:
                    if hasattr(v, "is_validation_method"):
                        if v.is_validation_method:
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
        value_func = list([value_func])
        while len(value_func) < 3:
            value_func.append(None)
        self.value_func, vf1, vf2 = value_func
        # the first element of the value_func list must be callable
        if self.value_func and not callable(self.value_func):
            raise ValueError("Expected value_func[0] to be callable")
        # check that the other parts of the value_func are the right type
        for arg, n in ((vf1, 1), (vf2, 2)):
            if arg and not isinstance(arg, (list, dict)):
                raise ValueError(("Expected value_func[{}] to be list, " +
                    "dict or None, but found {}").format(
                       n,  vf1.__class__.__name__))
        # check that, if both args and kwargs are provided, we have a list
        # and a dict
        if vf1 and vf2 and type(vf1) == type(vf2):
            raise ValueError(value_error_msg.format(
                vf1.__class__.__name__, vf2.__class__.__name))
        vf2 = vf2 if vf2 else {}
        # set args to the list and kwargs to the dict (or None if the
        # args/kwargs were not provided
        vfargs = vf1 if isinstance(vf1, list) else vf2
        vfkwargs = vf1 if isinstance(vf1, dict) else vf2
        self.value_func_args = vfargs if vfargs else []
        self.value_func_kwargs = vfkwargs if vfkwargs else {}
    
    def _set_kwargs(self, kwargs):
        """
        Helper function which binds the key: value pairs in kwargs to the
        instance as instance attributes. This lets subclasses call
        super().__init__(...) with keyword arguments that become instance
        attributes.
        """
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

    def resolve_all(self, node):
        """
        Return a dictionary of instance attributes in which all instance
        attributes are resolved to their value at the point of construction.
        """
        resolved = {}
        for k,v in self.__dict__.items():
            if DEBUG:
                print("resolve", k, v)
            val = v if not hasattr(v, "resolve_path") else v.resolve_path(node)
            resolved[k] = val
        return resolved
            

    def __str__(self):
        vals = []
        for k,v in sorted(self.__dict__.items()):
            if k != "_name" and k not in self.__class__.__dict__:
                vals.append("{k}={v}".format(k=k,v=v))
        vals = ", ".join(vals)
        return "{cls}({name}, {vals})".format(
            cls = self.__class__.__name__,
            name = self.name,
            vals = vals
        )

    def validate_stage(self, node, stage, descendent=None):
        """
        Call the validation methods in self.validaton with the given
        node and descendent where the validation method's stage
        attribute matches the given stage.
        """
        issues = []
        if DEBUG:
            print("validate_stage", node, stage, descendent)
            print("validation is", [str(v) for v in self.validation])
        for validation in (v for v in self.validation if v.stage == stage):
            if DEBUG:
                print("validating against", validation)
            try:
                validation(self, node, descendent)
            except (ValidationInfo, ValidationWarning, ValidationError) as err:
                issues.append(err)
            except (ValidationFatal):
                raise
        if issues:
            node.add_data({"validation": issues}, meta=True)
        return issues

    def construct(self, source, parent=None, _node=None):
        """
        Construct and return a node using the data from the given source.
        If parent is given, the node will be added as a child of the parent
        node. The _node argument is used internally and should generally be
        omitted when calling construct externally.

        The node object (and its attributes) are added to the tree as soon
        as possible during the method, which allows nodes in the partially
        built tree to be referenced.

        (When the _node argument is None, construct creates a copy of self
        and calls the resolve_all method on the copy to resolve any Path
        objects that have been passed in as instance attributes. These are
        essentially delayed function calls which allow the definer to refer
        to parts of the tree that don't exist at compile time. Creating the
        copied object avoids overwriting these attributes while allowing
        validation/attribute/value methods to ignore the whole thing and just
        use normal self.foo attribute access.)
        """
        # If _node is None then this has been called on the original
        # definition. This creates a copy of the definition instance and
        # replaces the __dict__ with a copy of this instance's dict where
        # all resolvable instance attributes are resolved to actual values.
        # i.e. validation, attribute and value functions can ignore the
        # distinction between real instance attributes and resolved attributes
        # and simply refer to the attribute in the usual way.
        if DEBUG:
            print("constructing {}{}".format(self.name, 
                "" if not _node else "(facade)"
            ))
        if _node is None:
            node = Node(self.name, parent)
            facade = object.__new__(self.__class__)
            facade.__dict__ = self.resolve_all(node)
            return facade.construct(source, parent, node)
        # This must be a resolved copy of the definition, so do the actual
        # node construction work here.
        node = _node
        node.add_data({"definition": self}, meta=True)
        self.validate_stage(node, "pre")
        node.add_data(source.get_preread_metadata(node), meta=True)
        if self.value_func:
            node.add_data({"value":
                self.value_func.__call__(self, node, source,
                    *self.value_func_args, **self.value_func_kwargs)
            })
        if callable(self.children):
            children = self.children()
        else:
            children = self.children
        if hasattr(children, "send"):
            children.send(None)
            childnode = children.send(node)
            while True:
                try:
                    childdef = children.send(childnode)
                    childnode = childdef.construct(source, node)
                    self.validate_stage(node, "per_child", childnode)
                except StopIteration:
                    break
        else:
            for childdef in children:
                childnode = childdef.construct(source, node)
                self.validate_stage(node, "per_child", childnode)
        self.validate_stage(node, "pre_derivation")
        for attr in self.attributes:
            if DEBUG:
                print("attribute:", attr)
            try:
                name, val = attr(node)
                node.add_data({name: val})
            except AttributeProcessingError as err:
                node.add_data({"validation": [err]}, meta=True)
        node.add_data(source.get_postread_metadata(node), meta=True)
        self.validate_stage(node, "post")
        return node


    @staticmethod
    def bit_flag(attr_name, attr, bit, idx=None, transform=None):
        def _bit_flag(node):
            val = getattr(node, attr)
            val = val[idx] if idx is not None else val
            val = transform(val) if transform is not None else val
            return (attr_name, val & (2**bit) > 0)
        return _bit_flag

    @staticmethod
    def attribute(attr_name, f):
        def _attribute(node):
            if hasattr(f, "resolve_path"):
                return (attr_name, f.resolve_path(node))
            else:
                return (attr_name, f(node))
        return _attribute

##############################################################################
# Definition leaf classes                                                    #
##############################################################################

class StaticDef(Definition):
    """
    Definition class for nodes representing a known, static bytestring
    within the file. e.g. File signatures. The staticbytes argument
    provides the expected bytestring. If the expected bytestring is not
    found when constructing the node, then a ValidationFatal exeption is
    raised.
    """
    def __init__(self, name, staticbytes, attributes=None, validation=None):
        v = Validation(Path().value, "==", staticbytes, error=ValidationFatal)
        validation = validation if validation else []
        validation.append(v)
        super().__init__(name, self.__class__.get_value, attributes=attributes,
                         validation=validation, staticbytes=staticbytes)

    def get_value(self, node, source, *args, **kwargs):
        """
        Read the number of bytes contained in self.staticbytes from the
        source and return it.
        """
        return source.read(len(self.staticbytes))

class IntegerDef(Definition):
    """
    Definition class for nodes representing a single integer. The
    structformat argument is a string defining the features of the integer
    (endianness, size, signedness) as per the documentation for the
    struct module.
    """
    def __init__(self, name, structformat, attributes=None, validation=None):
        super().__init__(name, self.__class__.get_value, attributes=attributes,
                         validation=validation, structformat=structformat)

    def get_value(self, node, source, *args, **kwargs):
        """
        Read bytes from source and return an integer as parsed using the
        self.structformat string and the struct module.
        """
        size = struct.calcsize(self.structformat)
        return struct.unpack(self.structformat, source.read(size))[0]


class IntegerSequenceDef(IntegerDef):
    """
    Definition class for nodes representing a sequence of integers or a
    sequence of integer sequences. The structformat argument is a string
    defining the features of the integer (see the documentation for
    IntegerDef). The items argument defines the number of integers or
    subsequences in the sequence. The subseq_length argument provides the
    length of the subsequences (default 1). If subseq_length is 1, then
    a tuple of integers is returns. If subseq_length is greater than 1,
    then a tuple of tuples is returned.
    """
    def __init__(self, name, structformat, items, subseq_length=1,
                 attributes=None, validation=None):
        self.items = items
        self.subseq_length = subseq_length
        super().__init__(name, structformat, attributes=attributes,
                         validation=validation)

    def get_value(self, node, source, *args, **kwargs):
        """
        Read bytes from the source and return a tuple of integers or a
        tuple containing tuples which contain subseq_length integers.
        """
        if self.items < 0:
            raise ValidationFatal(
                "items is less than 0"
            )
        if self.subseq_length < 0:
            raise ValidationFatal(
                "subseq_length is less than 0"
            )
        seq = []
        for i in range(self.items):
            subseq = []
            for j in range(self.subseq_length):
                subseq.append(IntegerDef.get_value(self, node, source))
            if len(subseq) == 1:
                seq.append(subseq[0])
            else:
                seq.append(tuple(subseq))
        return tuple(seq)
                


class BytestringDef(Definition):
    """
    Definition class for nodes representing a bytestring. The length
    argument gives the number of bytes in the bytestring.
    """
    def __init__(self, name, length, attributes=None, validation=None):
        super().__init__(name, self.__class__.get_value, attributes=attributes,
                         validation=validation, length=length)

    def get_value(self, node, source, *args, **kwargs):
        """
        Read from source and return a bytes object containing self.length
        bytes.
        """
        if self.length < 0:
            raise ValidationFatal(
                "length is less than zero"
            )
        return source.read(self.length)


class StringDef(Definition):
    """
    Definition class for nodes representing an encoded string. The length
    argument gives the number of bytes to be read. The encoding argument
    gives the expected encoding of these bytes (default utf8).
    """
    def __init__(self, name, length, encoding='utf8', attributes=None,
                 validation=None):
        super().__init__(name, self.__class__.get_value, attributes=attributes,
                         validation=validation, length=length,
                         encoding=encoding)

    def get_value(self, node, source, *args, **kwargs):
        """
        Read self.length bytes from source and return a string decoded
        from self.encoding. If errors are encountered when decoding,
        record these in the node's metadata and decode again
        less strictly.
        """
        if self.length < 0:
            raise ValidationFatal("length is less than 0")
        return self.decode_value(node, source.read(self.length))

    def decode_value(self, node, val):
        """
        Return a string produced from decoding val using self.encoding.
        """
        try:
            return val.decode(self.encoding, errors="strict")
        except (ValueError, UnicodeDecodeError) as err:
            node.add_data({"validation": ValidationError(str(err))},
                          meta=True)
            return val.decode(self.encoding, errors="replace")

class NullTerminatedStringDef(StringDef):
    """
    Definition class for nodes representing a null terminated string.
    The encoding argument gives the expected encoding of the string (default
    utf8).
    """
    def __init__(self, name, encoding='utf8', attributes=None,
                 validation=None):
        super().__init__(name, self.__class__.get_value, attributes=attributes,
                         validation=validation, encoding=encoding)

    def get_value(self, node, source, *args, **kwargs):
        """
        Read bytes from source until a null byte (0x00) is encountered,
        then return a string produced from decoding using self.encoding.
        If errors are encountered when decoding, record these in the
        node's metadata and decode again less strictly.
        """
        #val = bytearray()
        #for byte in iter(source.read, 0):
        #    print(type(byte), byte)
        #    val.append(byte)
        #return self.decode_value(node, val)
        return self.decode_value(
            node, bytearray(b''.join(b for b in iter(source.read, b'\x00'))))

##############################################################################
# Definition container classes                                               #
##############################################################################


class DefinedChildrenDef(Definition):
    """
    Definition class for nodes representing a node containing child nodes.
    The children argument should be a list of child definitions.
    """
    def __init__(self, name, children, attributes=None, validation=None):
        super().__init__(name, None, children=children, attributes=attributes,
                         validation=validation)


class NodeSequenceDef(Definition):
    """
    Definition class for nodes containing a homogenous sequence of child
    nodes. The childdef argument is a Definition instance which is used
    for constructing the sequence. The optional items argument should be the
    number of child nodes in the sequence (if known). If the number of nodes
    is variable, then the optional stop argument should provide a function
    that returns True to indicate the sequence is complete when called with
    the most recently created node.
    """
    def __init__(self, name, childdef, items=None, stop=None,
                 attributes=None, validation=None):
        stop = stop if stop else lambda node: False
        super().__init__(name, None, attributes=attributes,
                         validation=validation,
                         children=self.child_generator(childdef), items=items,
                         stop=stop)

    def construct(self, source, parent, _node=None):
        # if neither self.stop nor self.items is defined then the only
        # way that construction can end is by running out of file, in which
        # case an EOFError will be generated. This is OK as long as the most
        # recent child added is complete
        if DEBUG:
            print("Constructing {}".format(self.name))
        try:
            return super().construct(source, parent, _node)
        except EOFError:
            reraise = True
            if self.items is None:
                children = parent.children[-1].children
                if len(children) >= 2:
                    if children[-2].metadata["end_index"] == source.tell():
                        # get rid of the last node - it was created but
                        # when trying to read from source to get its data
                        # we hit end of file
                        del children[-1]
                        reraise = False
            if reraise:
                raise

    def child_generator(self, childdef):
        node = (yield None)
        if isinstance(self.items, Path):
            items = self.items.resolve_path(node)
        else:
            items = self.items
        if items is not None and items < 0:
            raise ValidationFatal("items is less than 0")
        for i in itertools.count() if not items else range(items+1):
            if node is not None and self.stop(node):
                break
            if DEBUG:
                print("yielded", i)
            node = (yield childdef)





class DelegatingDef(Definition):
    """
    Definition class representing a Node whose type is determined at
    construction time. The defdict argument is a dictionary mapping keys to
    definition instances while keyfunc is a function that should return a
    key mapping to the desired definition when called with the parent node.
    """
    def __init__(self, defdict, keyfunc, validation=None):
        self.name = "DelegatingDef"
        self.keyfunc = keyfunc
        self.defdict = defdict
        self.validation = self._get_validation(validation)


    def construct(self, source, parent):
        if DEBUG:
            print("Constructing {}".format(self.name))
            print("validating stage - pre")
        # create a fake node so that Path semantics work properly
        fakenode = Node(self.name, parent)
        self.validate_stage(fakenode, "pre")
        if hasattr(self.keyfunc, "resolve_path"):
            key = self.keyfunc.resolve_path(fakenode)
        else:
            key = self.keyfunc(fakenode)
        delegated = self.defdict.get(key, self.defdict.get("default"))
        while not isinstance(delegated, Definition):
            delegated = self.defdict.get(
                delegated, self.defdict.get("default"))
            if delegated is None:
                break
        # delete the fake node before constructing the real one
        del fakenode.parent.children[-1]
        if delegated:
            return delegated.construct(source, parent)
        else:
            parent.add_data({"validation":[
                ValidationWarning(
                     "Failed to find a definition to delegate to."
                )
            ]}, meta=True)

    def register(self, definition, name=None):
        self.defdict[name if name else definition.name] = definition
        return definition

