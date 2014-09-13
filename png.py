#!/usr/bin/python3 

from structures import *
from itertools import chain

class ChunkTypeStructure(HomogenousSequenceStructure):
    name = "chunk_type"
    _fields = ("string_rep", "ancillary", "private", "reserved",
              "safe_to_copy")

    def __init__(self, **kwargs):
        super().__init__(1, 4, "!", False, **kwargs)

    def consume_from_buffer(self, buffer, buffer_idx, **kwargs):
        raw_data, size, seq = self.consume_sequence(buffer, buffer_idx)
        string_rep = self.get_string_rep(seq, buffer_idx)
        properties = self.get_properties(seq, buffer_idx)
        ancillary, private, reserved, safe_to_copy = properties
        if not self.keep_raw_data:
            raw_data = None
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

    def validate_reserved(self, validation_value, **kwargs):
        if validation_value:
            return "Reserved bit is set."


class ChunkCRCStructure(IntegerStructure):
    name = "chunk_crc"
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


class ChunkPayloadStructure(object):
    name = "payload"
    payload_registry = {}
    def __new__(cls, d):
        chunk_type = d["chunk_type"].string_rep
        chunk_length = d["length"].value
        payload_cls = cls.payload_registry.get(
                        chunk_type,
                        UnknownChunkPayloadStructure)
        return payload_cls(chunk_length)

def registered_payload(cls):
    k = cls.registration_id
    d = ChunkPayloadStructure.payload_registry
    d[k] = cls
    return cls

class UnknownChunkPayloadStructure(HomogenousSequenceStructure):
    name = "unknown_payload"
    def __init__(self, size):
        super().__init__(1, size, "!", False, name=self.name)
 
@registered_payload
class IHDRPayloadStructure(PayloadStructure):
    registration_id = "IHDR"
    name = "ihdr_payload"

    def __init__(self, size, **kwargs):
        self.substructures = [
            IntegerStructure(4, signed=False, name="width"),
            IntegerStructure(4, signed=False, name="height"),
            IntegerStructure(1, signed=False, name="bit_depth"),
            IntegerStructure(1, signed=False, name="color_type"),
            IntegerStructure(1, signed=False, name="compression_method"),
            IntegerStructure(1, signed=False, name="filter_method"),
            IntegerStructure(1, signed=False, name="interlace_method")
        ]
        super().__init__(**kwargs)
        



class PNGChunkStructure(PayloadStructure):
    name = "chunk"
    def __init__(self, **kwargs):
        substructures = []
        substructures.append(IntegerStructure(4, "!", False, name="length"))
        substructures.append(ChunkTypeStructure(name="chunk_type"))
        substructures.append(ChunkPayloadStructure)
        substructures.append(ChunkCRCStructure(4, "!", False, name="crc"))
        super().__init__(substructures)

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

class PNGFileSignatureStructure(StaticStructure):
    name = "png_file_signature"
    signature = b'\x89PNG\r\n\x1a\n'
    def __init__(self):
        super().__init__(self.signature)

class PNGStructure(PayloadStructure):
    def __init__(self):
        substructures = []
        substructures.append(PNGFileSignatureStructure())
        substructures.append(ContainerStructure(PNGChunkStructure,
                            name="png_chunks"))
        super().__init__(substructures)

if __name__ == "__main__":
    import sys
    with open(sys.argv[1], "rb") as f:
        png = PNGStructure()
        pngfield = png.consume_from_buffer(f, 0)
        print(pngfield)
