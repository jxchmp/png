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

    def __init__(self, keep_raw_data=False, **kwargs):
        if hasattr(self, "name"):
            defaultname = self.name
        else:
            defaultname = self.__class__.__name__
        self.name = kwargs.get("name", defaultname)
        field_class_args = list(self.fields)
        field_class_args.append("warnings")
        self._field_class = namedtuple(self.name, field_class_args)
        fields = list(self.fields)
        fields.append("warnings")
        self.fields = tuple(fields)
        self.keep_raw_data = keep_raw_data

    def __call__(self, *args, **kwargs):
        fieldargs = {}
        args = list(args)
        for field in self.fields:
            if args:
                value = args.pop(0)
            elif field in kwargs:
                value = kwargs.pop(field)
            elif field in self.defaults:
                value = self.defaults[field]
                if callable(value):
                    value = value()
            else:
                raise TypeError("Expected argument '{}' missing".format(
                   field))
            fieldargs[field] = value
        if args:
            raise TypeError("Too many arguments")
        if kwargs:
            duplicates = [key for key in kwargs if key in self.fields]
            if duplicates:
                raise TypeError(
                    ("Keyword argument duplicates positional argument: " +
                    "{}").format(duplicates))
            else:
                raise TypeError("Unknown keyword arguments: {}".format(
                    kwargs.keys()))
        for field in self.fields:
            validation_func = "validate_" + field
            if hasattr(self, validation_func):
                value = fieldargs[field]
                warning = getattr(self, validation_func)(value, **fieldargs)
                if warning:
                    fieldargs["warnings"].append(warning)
        return self._field_class(**fieldargs)

    def consume_byte(self, buffer, buffer_idx, offset):
        val = buffer.read(1)
        if len(val) == 0 or val is None: 
            raise EndOfBufferError(self.name, buffer_idx+offset)
        else:
            return val[0]

class DerivedStructure(BaseStructure):
    _fields = ("value",)

    def __init__(self, derivation_function, **kwargs):
        super().__init__(**kwargs)
        self.derivation_function = derivation_function

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        value = self.derivation_function(**kwargs)
        return self(None, 0, value)        


class StaticStructure(BaseStructure):
    def __init__(self,  staticdata, **kwargs):
        super().__init__(**kwargs)
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
        if not self.keep_raw_data:
            size = len(raw_data)
            raw_data = None
        else:
            size = len(raw_data)
        return self(raw_data, size)


class PayloadStructure(BaseStructure):
    """
    A structure in which one or more substructures provide metadata
    for a payload of some kind.
    """
    name = "payload"
    
    def __init__(self, substructures, **kwargs):
        self.substructures = substructures
        self.fields = list(self.fields)
        self.fields.extend(sub.name for sub in substructures)
        self.fields = tuple(self.fields)
        super().__init__(**kwargs)       

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        payload = {}
        offset = 0
        for substructure in self.substructures:
            if isinstance(substructure, type):
                substructure = substructure(payload)
            field = substructure.consume_from_buffer(buffer,
                                                     buffer_idx + offset,
                                                     **payload)
            offset = offset + field.size
            payload[substructure.name] = field
        return self(None, offset, **payload)


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

    def __init__(self, octets, byteorder="!", signed=True, **kwargs): 
        super().__init__(**kwargs)
        self.size = octets
        self.structformat = "{}{}".format(byteorder,
                            self.format_dict[(octets, signed)])

    def consume_integer(self, buffer, buffer_idx=0):
        raw_data = bytearray()
        for i in range(self.size):
            raw_data.append(self.consume_byte(buffer, buffer_idx, i))
        value = struct.unpack(self.structformat, raw_data)[0]
        return (raw_data, len(raw_data), value)

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        raw_data, size, value = self.consume_integer(buffer, buffer_idx)
        if not self.keep_raw_data:
            raw_data = None
        return self(raw_data, size, value)


class CodedIntegerStructure(IntegerStructure):
    _fields = ("meaning",)

    def __init__(self, mapping, octets, byteorder="!", signed=True,
                  **kwargs):
        self.mapping = mapping
        super().__init__(octets, byteorder, signed, **kwargs)
   
    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        raw_data, size, value = self.consume_integer(buffer, buffer_idx)
        if not self.keep_raw_data:
            raw_data = None
        meaning = self.mapping.get(value, "unknown")
        return self(raw_data, size, value, meaning)



class HomogenousSequenceStructure(IntegerStructure):
    def __init__(self, octets_per_item, number_of_items,
                 byteorder="!", signed=True, **kwargs): 
        super().__init__(octets_per_item, byteorder, signed, **kwargs)
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
        if not self.keep_raw_data:
            size = len(raw_data)
            raw_data = None
        return (raw_data, size, tuple(seq)) 

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
       return self(*self.consume_sequence(buffer, buffer_idx))


class ContainerStructure(BaseStructure):
    _fields = ("contents",)

    def __init__(self, content_class, allow_buffer_end=True, **kwargs):
        super().__init__(**kwargs)
        self.content_class = content_class
        self._stop = False
        self.allow_buffer_end = allow_buffer_end

    def should_stop(self):
        return self._stop

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        contents = OrderedDict()
        offset = 0
        while not self.should_stop():
            item = self.content_class(**contents)
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
                contents.setdefault(field.__class__.__name__, []).append(field)
        return self(None, offset, contents)
