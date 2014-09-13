#!/usr/bin/python3

from collections import namedtuple
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
                    name = self.name
                    index = self.index
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


class BaseStructure(object):
    fields = ("raw_data", "size")
    defaults = {"warnings": list}

    def __new__(cls, *args, **kwargs):
        if hasattr(super(cls), "fields"):
            fields = list(cls.fields)
            fields.extend(super().fields)
            cls.fields = tuple(fields)
        if hasattr(super(cls), "defaults"):
            for key, value in super(cls).defaults.items():
                if key not in cls.defaults:
                    cls.defaults[key] = value
        return cls(*args, **kwargs)

    def __init__(self, name, **kwargs):
        self.name = name
        field_class_args = list(self.fields)
        field_class_args.extend("warnings")
        self._field_class = namedtuple(name, self.fields)

    def __call__(self, *args, **kwargs):
        fieldargs = {}
        for field in self.fields:
            if args:
                value = args.pop(0)
            elif field in kwargs:
                value = kwargs.pop(field)
            elif field in self.defaults:
                value = defaults[field]
                if callable(val):
                    value = val()
            else:
                raise TypeError("Expected argument '{}' missing".format(
                   field))
            fieldargs[field] = value
        if args:
            raise TypeError("Too many arguments")
        if kwargs:
            duplicates = [key for key in kwargs if key in self.fields])
            if duplicates:
                raise TypeError(
                    ("Keyword argument duplicates positional argument: " +
                    "{}").format(duplicates))
            else:
                raise TypeError("Unknown keyword arguments: {}".format(
                    kwargs.keys()
                )
        for field in self.fields:
            validation_func = "validate_" + field)
            if hasattr(self, validation_func):
                warning = getattr(self, validation_func)(value, fieldargs)
                if warning:
                    fieldargs["warnings"].append(warning)
        return self._field_class(**fieldargs)

    def consume_byte(self, buffer, buffer_idx, offset):
        val = buffer.read(1)
        if len(val) == 0 or val is None: 
            raise EndOfBufferError(self.name, buffer_idx+offset)
        else:
            return val


class StaticStructure(BaseStructure):
    def __init__(self, name, staticdata, **kwargs):
        super().__init__(name, **kwargs)
        self.staticdata = staticdata

    def consume_from_buffer(self, buffer, buffer_idx, **kwargs):
        raw_data = bytearray()
        for i, value in enumerate(self.data):
            buffer_val = self.consume_byte()
            raw_data.append(buffer_val) 
            if buffer_val != self.staticdata[i]:
                raise UnexpectedValueError(self.name, buffer_idx + offset,
                    self.staticdata[i], buffer_val)
        return self(raw_data, len(raw_data))


class PayloadStructure(BaseStructure):
    """
    A structure in which one or more substructures provide metadata
    for a payload of some kind.
    """

    def __new__(cls, name, substructures):
        cls.fields = tuple([sub.name for sub in substructures])
        return super(cls).__new__(cls, name)

    def __init__(self, name, substructures):
        self.substructures = substructures
        super().__init__(self.name)       

    def consume_from_buffer(self, buffer, buffer_idx, **kwargs):
        d = {}
        offset = 0
        for substructure in self.substructures:
            field = substructure.consume_from_buffer()
            offset = offset + field.size
            d[substructure.name] = substructure.consume_from_buffer(fields=d)
        d["size"] = offset
        return self(**d)


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

    fields = ("value")

    def __init__(self, name, octets, byteorder="!", signed=True): 
        super().__init__(name)
        self.size = octets
        self.structformat = "{}{}".format(byteorder,
                            self.format_dict[(octets, signed)])

    def consume_integer(self, buffer, buffer_idx):
        raw_data = bytearray()
        for i in range(self.size):
            raw_data.append(self.consume_byte(buffer_idx, i))
        value = struct.unpack(self.structformat, raw_data)[0]
        return (raw_data, len(raw_data), value)

    def consume_from_buffer(self, buffer, buffer_idx, **kwargs):
        raw_data, size, value = self.consume_integer(buffer, buffer_idx)
        return self(raw_data, size, value)


class HomogenousSequenceStructure(IntegerStructure):
    def __init__(self, name, octets_per_item, number_of_items,
                 byteorder="!", signed=True): 
        super().__init__(name, octets_per_item, byteorder, signed)
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
       return (raw_data, len(raw_data, tuple(seq)) 

    def consume_from_buffer(self, buffer, buffer_idx, **kwargs):
       return self(*self.consume_sequence(buffer, buffer_idx))
