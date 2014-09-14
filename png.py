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
    name = "payload"
    def __init__(self, size):
        super().__init__(1, size, "!", False, name=self.name)

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        field = super().consume_from_buffer(buffer, buffer_idx, **kwargs)
        return field._replace(value = "...")
 
@registered_payload
class IHDRPayloadStructure(PayloadStructure):
    registration_id = "IHDR"

    def __init__(self, size, **kwargs):
        substructures = [
            IntegerStructure(4, signed=False, name="width"),
            IntegerStructure(4, signed=False, name="height"),
            IntegerStructure(1, signed=False, name="bit_depth"),
            ColorTypeStructure(1, signed=False),
            CodedIntegerStructure({0: "deflate/inflate"}, 1,
                                  signed=False, name="compression_method"),
            CodedIntegerStructure({0: "adaptive"}, 1,
                                  signed=False, name="filter_method"),
            CodedIntegerStructure({0: "no interlacing",
                                   1: "Adam7"}, 1,
                                  signed=False, name="interlace_method"),
            DerivedStructure(self.derive_sample_depth, name="sample_depth")
        ]
        super().__init__(substructures, **kwargs)

    def derive_sample_depth(self, **kwargs):
        if kwargs["bit_depth"].value != 3:
            return 8
        else:
            return kwargs["bit_depth"]

    def validate_dimension(self, value, dimension):
        if value == 0:
            return "Zero {} is not allowed".format(dimension)
        elif value >= 2**31:
            return "Maximum {} is {}".format(dimension, (2**31) -1)
        
    def validate_width(self, validation_value, **kwargs):
        return self.validate_dimension(validation_value.value, "width")

    def validate_height(self, validation_value, **kwargs):
        return self.validate_dimension(validation_value.value, "height")

    def validate_bit_depth(self, validation_value, **kwargs):
        if validation_value.value not in [1,2,4,8,16]:
            return "Allowed values are 1,2,4,8 and 16"

    allowed_color_type_bit_depths = {
        0: (1,2,4,8,16),
        2: (8,16),
        3: (1,2,4,8),
        4: (8,16),
        6: (8,16)
    }

    def validate_color_type(self, validation_value, **kwargs):
        color_type = validation_value.value
        bit_depth = kwargs["bit_depth"].value
        allowed = self.allowed_color_type_bit_depths.get(color_type)
        if allowed:
            if bit_depth not in allowed:
                return "Allowed bit depths for color_type are {}".format(
                    allowed
                )
        else:
           return "Unknown color type so no known allowed bit depths" 

    def validate_compression_method(self, validation_value, **kwargs):
        if validation_value.value != 0:
            return "Unknown compression method. Only method 0 is known."

    def validate_filter_method(self, validation_value, **kwargs):
        if validation_value.value != 0:
            return "Unknown filter method. Only method 0 is known."

    def validate_interlace__method(self, validation_value, **kwargs):
        if validation_value.value not in (0,1):
            return "Unknown filter method. Only methods 0 and 1 are known."



class ColorTypeStructure(IntegerStructure):
    name = "color_type"
    _fields = ("palette_used", "color_used", "alpha_channel_used")

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        raw_data, size, value = super().consume_integer(
                                        buffer, buffer_idx)
        palette_used = bool(value & 1)
        color_used = bool(value & 2)
        alpha_channel_used = bool(value & 4)
        return self(raw_data, size, value, palette_used, color_used,
                    alpha_channel_used)

    def validate_value(self, validation_value, **kwargs):
        if validation_value not in [0,2,3,4,6]:
            return "Permitted values are 0,2,4,4 and 6"


class PNGChunkStructure(PayloadStructure):
    name = "chunk"
    def __init__(self, **kwargs):
        substructures = []
        substructures.append(IntegerStructure(4, "!", False, name="length"))
        substructures.append(ChunkTypeStructure(name="chunk_type"))
        substructures.append(ChunkPayloadStructure)
        substructures.append(ChunkCRCStructure(4, "!", False, name="crc"))
        super().__init__(substructures)

    def validate_length(self, validation_value, **kwargs):
        if validation_value.value >= 2**31:
            return "Length of {} exceeds maximum value {}".format(
                validation_value.value, (2**31)-1
            )

    def validate_crc(self, validation_value, **kwargs):
        if (kwargs["chunk_type"].raw_data is not None and
            kwargs["payload"].raw_data is not None):
            data_iterator = chain(kwargs["chunk_type"].raw_data,
                                  kwargs["payload"].raw_data)
            crc = ChunkCRCStructure.generate_crc(data_iterator,
                                            validation_value.value)
            if crc != validation_value.value:
                return "CRC {} did not match calculated CRC {}".format(
                    validation_value,value, crc
                )
        else:
            return "Unable to validate CRC"

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
