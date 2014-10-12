#!/usr/bin/python3

from collections import namedtuple, OrderedDict
import struct


class StructureReadError(Exception):
    """
    Base exception for errors found while reading a structure.
    """
    def __init__(self, name, index, message):
        self.name = name
        self.index = index
        self.message = message

    def __str__(self):
        return ("Problem occured while reading field '{name}' " +
                "at index {index}: {message}").format(
                    name = self.name,
                    index = self.index,
                    message = self.message
                )

class EndOfBufferError(StructureReadError):
    """
    Exception for an error occurring where reading from a buffer failed.
    """
    def __init__(self, name, index):
        super().__init__(name, index,
            "Reached end of buffer")


class UnexpectedValueError(StructureReadError):
    """
    Exception for errors in which an expected value was not found.
    """
    def __init__(self, name, index, expected, actual):
        super().__init__(name, index,
            "Expected byte 0x{expected:02X} but found {actual:02X}".format(
                expected = expected,
                actual = actual
            )
        )


class UnknownValueError(StructureReadError):
    """
    Exception for errors in which a value was expected to be one of a
    number of possible values, but was not.
    """
    def __init__(self, name, index, value):
        super().__init__(name, index,
            "Value '{}' not known.".format(value))

class InvalidValueError(StructureReadError):
    def __init__(self, name, index, value, reason):
        super().__init__(name, index,
            "Value '{}' not valid. {}".format(value, reason)
         )



class StructureNode(object):
    def __init__(self, parent, name, clsname, fields, defaults, data):
        self.parent = parent
        self.name = name
        self.clsname = clsname
        self.children = OrderedDict()
        self.fields = fields
        self.defaults = defaults
        self.set_children(fields, defaults, data)

    @property
    def raw_data(self):
        if ("raw_data" in self.children
            and self.children["raw_data"] is not None):
            return self.children["raw_data"]
        else:
            raw_data = bytearray()
            for name, child in self:
                if isinstance(child, self.__class__):
                    raw_data.extend(child.raw_data)
            return raw_data

    @raw_data.setter
    def raw_data(self, value):
        self.children["raw_data"] = value

    def iter_depth_first(self):
        stack = [self]
        while stack:
            node = stack.pop()
            childnodes = []
            for name, node in node.iterchildren():
                childnodes.append(node)
            childnodes.reverse()
            stack.extend(childnodes)
            yield node

    def find(self, clsname, attributes=(), limit=None):
        matches = 0
        for node in self.iter_depth_first():
            if node.clsname == clsname:
                matched = all([node.children.get(attrib) == val
                               for attrib, val in attributes])
                if matched:
                    yield node
                    if limit is not None:
                        matches = matches + 1
                        if matches == limit:
                            break

    def find_one(self, clsname, attributes=()):
        matched = [node for node in self.find(clsname, attributes, 1)]
        if matched:
            return matches[0]
        else:
            return None

    def find_all(self, clsname, attributes=()):
        return [node for node in self.find(clsname, attributes)]

    def __str__(self):
        return "StructureNode({})".format(self.name)

    def __getattr__(self, name):
        children = super().__getattribute__("children")
        if name in children:
            return children[name]
        else:
            raise AttributeError(
                "'{}' object has no attribute '{}'".format(
                    str(self), name
                )
            )

    def __getitem__(self, key):
        if isinstance(key, int):
            return [item for item in self.children.items()][key]
        else:
            return self.children[key]

    def __setitem__(self, key, value):
        self.children[key] = value

    def setdefault(self, key, default):
        return self.children.setdefault(key, default)

    def __iter__(self):
        return iter(self.children.items())
        
    def __reversed__(self):
        return reversed([el for el in self.children.items()])

    def iterattributes(self):
        for name, child in self:
            if not isinstance(child, self.__class__):
                yield (name, child)

    def iterchildren(self):
        for name, child in self:
            if isinstance(child, self.__class__):
                yield (name, child)
            

    def set_children(self, fields,  defaults, data):
        if not data:
            return
        for i, field in enumerate(fields):
            value_found = False
            value = None
            if field in data:
                value = data[field]
                value_found = True
            if value_found:
                self.children[field] = value
            else:
                if field in defaults:
                    default_value = defaults[field]
                    if callable(default_value):
                        default_value = default_value()
                    self.children[field] = default_value
                else:
                    raise TypeError(
                        "Expected argument '{}' missing".format(
                                                          field))


class MetaStructure(type):
    def __new__(meta, name, bases, attrs):
        fields = list(attrs.get("_fields", []))
        fields.reverse()
        defaults = attrs.get("_defaults", {}).copy()
        for base in bases:
            if hasattr(base, "fields"):
                basefields = list(base.fields)
                basefields.reverse()
                fields.extend(basefields)
            elif hasattr(base, "_fields"):
                basefields = list(base._fields)
                basefields.reverse()
                fields.extend(basefields)
            if hasattr(base, "defaults"):
                for key, item in base.defaults.items():
                    if key not in defaults:
                        defaults[key] = item
            elif hasattr(base, "_defaults"):
                for key, item in base._defaults.items():
                    if key not in defaults:
                        defaults[key] = item
        fields.reverse() 
        attrs = attrs.copy()
        attrs["fields"] = tuple(fields)
        attrs["defaults"] = defaults
        return type.__new__(meta, name, bases, attrs)
       
class BaseStructure(object, metaclass=MetaStructure):
    _fields = ("raw_data", "size")
    _defaults = {"warnings": list}

    def __init__(self, root, parent_node, keep_raw_data=True, **kwargs):
        self.root = root
        if hasattr(self, "name"):
            defaultname = self.name
        else:
            defaultname = self.__class__.__name__
        self.name = kwargs.get("name", defaultname)
        self.node = StructureNode(parent_node, self.name,
                                  self.__class__.__name__,
                                  self.fields, self.defaults,  {})
        field_class_args = list(self.fields)
        if "warnings" not in field_class_args:
            field_class_args.append("warnings")
        self._field_class = namedtuple(self.name, field_class_args)
        fields = list(self.fields)
        if "warnings" not in fields:
            fields.append("warnings")
        self.fields = tuple(fields)
        self.keep_raw_data = keep_raw_data

    def __call__(self):
        for field in self.fields:
            validation_func = "validate_" + field
            if hasattr(self, validation_func):
                value = self.node[field]
                warning = getattr(self, validation_func)(value)
                if warning:
                    self.warn(warning)
        return self.node

    def consume_byte(self, buffer, buffer_idx, offset):
        val = buffer.read(1)
        if len(val) == 0 or val is None: 
            raise EndOfBufferError(self.name, buffer_idx+offset)
        else:
            return val[0]

    def warn(self, message):
        self.node.setdefault("warnings", []).append(message)

class RootStructure(object):
    def __init__(self):
        self.node = StructureNode(None, "root", self.__class__.__name__,
                                  [], {}, {})

class DerivedStructure(BaseStructure):
    _fields = ("value",)

    def __init__(self, root, parent_node, derivation_function, **kwargs):
        super().__init__(root, parent_node, **kwargs)
        self.derivation_function = derivation_function

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        value = self.derivation_function(**kwargs)
        self.node["size"] = 0
        self.node["value"] = value
        return self()


class StaticStructure(BaseStructure):
    def __init__(self, root, parent_node,  staticdata, **kwargs):
        super().__init__(root, parent_node, **kwargs)
        self.staticdata = staticdata

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        raw_data = bytearray()
        offset = 0
        for i, value in enumerate(self.staticdata):
            buffer_val = self.consume_byte(buffer, buffer_idx, offset)
            offset = offset + 1
            raw_data.append(buffer_val) 
            if buffer_val != value:
                raise UnexpectedValueError(self.name, buffer_idx + offset,
                    value, buffer_val)
        self.node["raw_data"] = raw_data
        self.node["size"] = len(raw_data)
        return self()

class PayloadStructure(BaseStructure):
    """
    A structure in which one or more substructures provide metadata
    for a payload of some kind.
    """
    name = "payload"
    
    def __init__(self, root, parent_node, substructures, **kwargs):
        self.substructures = substructures
        self.fields = list(self.fields)
        self.fields.extend(sub.name for sub in substructures)
        self.fields = tuple(self.fields)
        super().__init__(root, parent_node, **kwargs)       
        for substructure in substructures:
            substructure.parent = self.node


    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        offset = 0
        raw_data = bytearray()
        for substructure in self.substructures:
            ok_to_read = True
            if isinstance(substructure, type):
                try:
                    inst = substructure(self.root, self.node)
                except ValueError as err:
                    self.warn("Error initialising {}: {}".format(
                        substructure, err.message))
                    ok_to_read = False
                else:
                    substructure = inst
            if ok_to_read:
                field = substructure.consume_from_buffer(buffer,
                                                         buffer_idx + offset,
                                                         **self.node.children)
                offset = offset + field.size
                self.node[substructure.name] = field
            else:
                size = substructure.get_size(self.node)
                for i in range(size):
                    self.consume_byte()
                offset = offset + size
        self.node["raw_data"] = None
        self.node["size"] = offset
        return self()


class IntegerStructure(BaseStructure):
    format_dict = {
       (1, True): "b",
       (1, False): "B",
       (2, True): "h",
       (2, False): "H",
       (4, True): "i",
       (4, False): "I",
       (8, True): "q",
       (8, False): "Q"
    }

    _fields = ("value",)

    def __init__(self, root, parent_node, octets, seq_length=1, byteorder="!",
                 signed=True, **kwargs): 
        super().__init__(root, parent_node, **kwargs)
        self.size = octets * seq_length
        self.structformat = "{}{}".format(byteorder,
                            (self.format_dict[(octets, signed)] * seq_length))

    def consume_integer(self, buffer, buffer_idx=0):
        raw_data = bytearray()
        for i in range(self.size):
            raw_data.append(self.consume_byte(buffer, buffer_idx, i))
        value = struct.unpack(self.structformat, raw_data)
        if len(value) == 1:
            value = value[0]
        return (raw_data, len(raw_data), value)

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        raw_data, size, value = self.consume_integer(buffer, buffer_idx)
        self.node["raw_data"] = raw_data
        self.node["size"] = size
        self.node["value"] = value
        return self() 

class CodedIntegerStructure(IntegerStructure):
    _fields = ("meaning",)

    def __init__(self, root, parent_node, mapping, octets, seq_length=1,
                 byteorder="!", signed=True, **kwargs):
        self.mapping = mapping
        super().__init__(root, parent_node, octets, seq_length, byteorder,
                         signed, **kwargs)
   
    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        raw_data, size, value = self.consume_integer(buffer, buffer_idx)
        meaning = self.mapping.get(value, "unknown")
        self.node["raw_data"] = raw_data
        self.node["size"] = size
        self.node["value"] = value
        self.node["meaning"] = meaning
        return self()


class HomogenousSequenceStructure(IntegerStructure):
    def __init__(self, root, parent_node, octets_per_item, number_of_items,
                 seq_length=1, byteorder="!", signed=True, **kwargs): 
        super().__init__(root, parent_node, octets_per_item, seq_length,
                         byteorder, signed, **kwargs)
        self.number_of_items = number_of_items

    def consume_sequence(self, buffer, buffer_idx):
        seq = []
        raw_data = []
        offset = 0
        for i in range(self.number_of_items):
            data, size, value = self.consume_integer(buffer,
                                                      buffer_idx + offset)
            offset = offset + size
            raw_data.extend(data)
            seq.append(value)
            size = len(raw_data)
        return (raw_data, size, tuple(seq)) 

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        raw_data, size, seq = self.consume_sequence(buffer, buffer_idx)
        self.node["raw_data"] = bytearray(raw_data)
        self.node["size"] = size
        self.node["value"] = seq
        return self()

class ContainerStructure(BaseStructure):
    _fields = ("contents",)

    def __init__(self, root, parent_node, content_class,
                 allow_buffer_end=True, **kwargs):
        super().__init__(root, parent_node, **kwargs)
        self.content_class = content_class
        self._stop = False
        self.allow_buffer_end = allow_buffer_end

    def should_stop(self):
        return self._stop

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        self.node.raw_data = None
        self.node.size = 0
        self.node["contents"] = StructureNode(self.node, "contents",
                                              self.__class__.__name__,
                                              [], [], {})
        offset = 0
        i = 0
        while not self.should_stop():
            item = self.content_class(self.root, self.node,
                                       **self.node.contents.children)
            try:
                field = item.consume_from_buffer(buffer, buffer_idx + offset,
                                                 **kwargs)
            except EndOfBufferError:
                if self.allow_buffer_end:
                    field = None
                    self._stop = True
                else:
                    raise
            if field:
                offset = offset + field.size
                self.node.size = self.node.size + field.size
                self.node["contents"][field.name + "_" + str(i).zfill(5)] = field
            i = i + 1
        return self()
