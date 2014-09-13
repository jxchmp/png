#!/usr/bin/python3 

from structures import *
from itertools import chain

class ChunkTypeStructure(HomogenousSequenceStructure):
    fields = ("string_rep", "ancillary", "private", "reserved",
              "safe_to_copy")

    def __init__(self, name):
        super().__init__(name, 1, 4, "!", False)

    def consume_from_buffer(self, buffer, buffer_idx, **kwargs):
        raw_data, size, seq = self.consume_sequence(buffer, buffer_idx)
        string_rep = self.get_string_reps(seq, buffer_idx)
        properties = self.get_properties(seq, buffer_idx)
        ancillary, private, reserved, safe_to_copy = properties
        return self(raw_data, size, seq, string_rep, ancillary,
                    private, reserved, safe_to_copy)

    def get_string_rep(self, seq, buffer_idx):
        stringrep = []
        for i, val in enumerate(seq):
            try:
                if val not in range(65, 91) and val not in range(97, 123):
                    raise ValueError
                stringrep.append(chr(val))
            except ValueError:
                raise InvalidValueError(
                    self.name,
                    buffer_idx + (i),
                    val,
                    "Value must be in range 65-90 or 97-122")
       return "".join(stringrep)

    def get_properties(self, seq, buffer_idx):
        return [bool(val & 32) for val in seq]

    def validate_reserved(self, value, **kwargs):
        if value:
            return "Reserved bit is set."


class ChunkCRCStructure(IntegerStructure):
    crc_table = []
    for n in range(256):
        c = n
        for k in range(8):
            if c & 1:
                c = 0xEDB88320 ^ (c >> 1)
            else:
                c = c >> 1
        crc_table.append(c)

    @classmethod
    def generate_crc(cls, data):
        crc = 0xffffffff
        for i, val in enumerate(data):
            crc = cls.crc_table[(crc ^ val) & 0xff] ^ (crc >> 8)
        return crc


class BasePNGChunk(PayloadStructure):
    def __init__(self, name, payload)
        substructures = []
        substructures.append(IntegerStructure("length", 4, "!I"))
        substructures.append(ChunkTypeStructure("chunk_type"))
        substructures.append(ChunkPayloadStructure("payload", length, chunk_type))
        substructures.append(ChunkCRCStructure("crc", 4, "!I"))
        super().__init__(name, substructures)

    def validate_length(self, value, field_dict):
        if value >= 2**31:
            return "Length of {} exceeds maximum value {}".format(
                value, (2**31)-1
            )

    def validate_crc(self, value, field_dict):
        data_iterator = chain(field_dict["chunk_type"].raw_data,
                              field_dict["payload"].raw_data)
        crc = ChunkCRCStructure.generate_crc(data_iterator, value)
        if crc != value:
            return "CRC {} did not match calculated CRC {}".format(
                value, crc
            )
