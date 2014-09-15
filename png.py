#!/usr/bin/python3 

from structures import *
from itertools import chain
import zlib

class ChunkTypeStructure(HomogenousSequenceStructure):
    name = "chunk_type"
    _fields = ("string_rep", "ancillary", "private", "reserved",
              "safe_to_copy")

    def __init__(self, root, parent_node, **kwargs):
        super().__init__(root, parent_node, 1, 4, seq_length=1, byteorder="!",
                         signed= False, **kwargs)

    def consume_from_buffer(self, buffer, buffer_idx, **kwargs):
        raw_data, size, seq = self.consume_sequence(buffer, buffer_idx)
        self.node["raw_data"] = bytearray(raw_data)
        self.node["size"] = size
        self.node["value"] = seq
        self.node["string_rep"] = self.get_string_rep(seq, buffer_idx)
        properties = self.get_properties(seq, buffer_idx)
        ancillary, private, reserved, safe_to_copy = properties
        self.node["ancillary"] = ancillary
        self.node["private"] = private
        self.node["reserved"] = reserved
        self.node["safe_to_copy"] = safe_to_copy
        return self()

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

    def validate_reserved(self, validation_value):
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
    def __new__(cls, root, d):
        chunk_type = d["chunk_type"].string_rep
        chunk_length = cls.get_size(d)
        payload_cls = cls.payload_registry.get(
                        chunk_type,
                        UnknownChunkPayloadStructure)
        inst = payload_cls(root, d, chunk_length)
        inst.name = "payload"
        return inst

    @classmethod
    def get_size(cls, parent_node):
        return parent_node["length"].value

def registered_payload(cls):
    k = cls.registration_id
    d = ChunkPayloadStructure.payload_registry
    d[k] = cls
    return cls

class UnknownChunkPayloadStructure(HomogenousSequenceStructure):
    name = "payload"
    def __init__(self, root, parent_node, size, **kwargs):
        super().__init__(root, parent_node, 1, size, seq_length=1,
                         byteorder="!", signed=False, name=self.name)

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        super().consume_from_buffer(buffer, buffer_idx, **kwargs)
        self.node["value"] = "..."
        return self()
 
@registered_payload
class IHDRPayloadStructure(PayloadStructure):
    registration_id = "IHDR"

    def __init__(self, root, parent_node, size, **kwargs):
        substructures = [
            IntegerStructure(root, None, 4, signed=False, name="width"),
            IntegerStructure(root, None, 4, signed=False, name="height"),
            IntegerStructure(root, None, 1, signed=False, name="bit_depth"),
            ColorTypeStructure(root, None, 1, signed=False),
            CodedIntegerStructure(root, None, {0: "deflate/inflate"}, 1,
                                  signed=False, name="compression_method"),
            CodedIntegerStructure(root, None, {0: "adaptive"}, 1,
                                  signed=False, name="filter_method"),
            CodedIntegerStructure(root, None, {0: "no interlacing",
                                   1: "Adam7"}, 1,
                                  signed=False, name="interlace_method"),
            DerivedStructure(root, None, self.derive_sample_depth,
                             name="sample_depth")
        ]
        super().__init__(root, parent_node, substructures, **kwargs)

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
        
    def validate_width(self, validation_value):
        return self.validate_dimension(validation_value.value, "width")

    def validate_height(self, validation_value):
        return self.validate_dimension(validation_value.value, "height")

    def validate_bit_depth(self, validation_value):
        if validation_value.value not in [1,2,4,8,16]:
            return "Allowed values are 1,2,4,8 and 16"

    allowed_color_type_bit_depths = {
        0: (1,2,4,8,16),
        2: (8,16),
        3: (1,2,4,8),
        4: (8,16),
        6: (8,16)
    }

    def validate_color_type(self, validation_value):
        color_type = validation_value.value
        bit_depth = self.node.bit_depth.value
        allowed = self.allowed_color_type_bit_depths.get(color_type)
        if allowed:
            if bit_depth not in allowed:
                return "Allowed bit depths for color_type are {}".format(
                    allowed
                )
        else:
           return "Unknown color type so no known allowed bit depths" 

    def validate_compression_method(self, validation_value):
        if validation_value.value != 0:
            return "Unknown compression method. Only method 0 is known."

    def validate_filter_method(self, validation_value):
        if validation_value.value != 0:
            return "Unknown filter method. Only method 0 is known."

    def validate_interlace__method(self, validation_value):
        if validation_value.value not in (0,1):
            return "Unknown filter method. Only methods 0 and 1 are known."


@registered_payload
class PLTEPayloadStructure(HomogenousSequenceStructure):
    registration_id = "PLTE"

    def __init__(self, root, parent_node,  size, **kwargs):
        super().__init__(root, parent_node, 1, size, seq_length=3,
                         byteorder="!", signed=False, **kwargs)
   

@registered_payload
class IDATPayloadStructure(HomogenousSequenceStructure):
    registration_id = "IDAT"

    def __init__(self, root, parent_node, size, **kwargs):
        super().__init__(root, parent_node, 1, size, byteorder="!",
                         signed=False, **kwargs)


@registered_payload
class IENDPayloadStructure(StaticStructure):
    registration_id = "IEND"

    def __init__(self, root, parent_node, size, **kwargs):
        super().__init__(root, parent_node, "", **kwargs)



@registered_payload
class bKGDPayloadStructure(HomogenousSequenceStructure):
    registration_id = "bKGD"

    def __init__(self, root, parent_node, size, **kwargs):
        self.color_type_node = root.find_one("ColorTypeStructure")
        if size == 1:
            octets_per_item = 1
            number_of_items = 1
            seq_length = 1
        elif size == 2:
            octets_per_item = 2
            number_of_items = 1
            seq_length = 1
        elif size == 6:
            octets_per_item = 2
            number_of_items = 1
            seq_length = 3
        else:
            raise ValueError("Size must be 1,2 or 6")
        super().__init__(root, parent_node, octets_per_item, number_of_items,
                         byteorder="!", signed=False)


@registered_payload
class cHRMPayloadStructure(HomogenousSequenceStructure):
    registration_id = "cHRM"
    _fields = ('white_point_x', 'white_point_y', 'red_x', 'red_y', 'green_x',
               'green_y', 'blue_x', 'blue_y')

    def __init__(self, root, parent_node, size, **kwargs):
        super().__init__(root, parent_node, 4, 8, byteorder="!",
                          signed=False)

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        super().consume_from_buffer(buffer, buffer_idx, **kwargs)
        for val, name in zip(self.node.value, self._fields):
            self.node[name] = val/100000    
        return self()


@registered_payload
class gAMAPayloadStructure(IntegerStructure):
    registration_id = "gAMA"
    _fields = ('gamma')

    def __init__(self, root, parent_node, size, **kwargs):
        super().__init__(root, parent_node, 4, byteorder="!",
                          signed=False)


    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        super().consume_from_buffer(buffer, buffer_idx, **kwargs)
        self.node["gamma"] = self.node.value / 100000
        return self()

@registered_payload
class hISTPayloadStructure(HomogenousSequenceStructure):
    registration_id = "hIST"

    def __init__(self, root, parent_node, size, **kwargs):
        super().__init__(root, parent_node, 2, byteorder="!",
                          signed=False)

@registered_payload
class pHYsPayloadStructure(PayloadStructure):
    registration_id = "pHYs"

    def __init__(self, root, parent_node, size, **kwargs):
        substructures = [
            IntegerStructure(root, None, 4, byteorder="!", signed=False,
                            name="pixels_per_unit_x"),
            IntegerStructure(root, None, 4, byteorder="!", signed=False,
                            name="pixels_per_unit_y"),
            CodedIntegerStructure(root, None, {0: "unknown", 1: "meter"},
                                  1, byteorder="!", signed=False,
                                  name="unit_specifier")
        ]
        super().__init__(root, parent_node, substructures, **kwargs)


@registered_payload
class sBITPayloadStructure(HomogenousSequenceStructure):
    registration_id = "sBIT"

    def __init__(self, root, parent_node, size, **kwargs):
        super().__init__(root, parent_node, 1, size, byteorder="!",
                         signed=False)




@registered_payload
class tEXtPayloadStructure(HomogenousSequenceStructure):
    registration_id = "tEXt"
    _fields = ('keyword', 'text')

    def __init__(self, root, parent_node, size, **kwargs):
        super().__init__(root, parent_node, 1, size, byteorder="!",
                         signed=False)

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        super().consume_from_buffer(buffer, buffer_idx, **kwargs)
        keyword = []
        text = []
        in_keyword = True
        for val in self.node.value:
            if in_keyword and val == 0:
                in_keyword = False
            else:
                char = bytes([val]).decode('latin1')
                if in_keyword:
                    keyword.append(char)
                else:
                    text.append(char)
        self.node["keyword"] = "".join(keyword)
        self.node["text"] = "".join(text)
        return self()


@registered_payload
class tIMEPayloadStructure(PayloadStructure):
    registration_id = "tIME"

    def __init__(self, root, parent_node, size, **kwargs):
        substructures = [
            IntegerStructure(root, None, 2, byteorder="!", signed=False,
                            name="year"),
            IntegerStructure(root, None, 1, byteorder="!", signed=False,
                            name="month"),
            IntegerStructure(root, None, 1, byteorder="!", signed=False,
                            name="day"),
            IntegerStructure(root, None, 1, byteorder="!", signed=False,
                            name="hour"),
            IntegerStructure(root, None, 1, byteorder="!", signed=False,
                            name="minute"),
            IntegerStructure(root, None, 1, byteorder="!", signed=False,
                            name="second")
        ]
        super().__init__(root, parent_node, substructures, **kwargs)

@registered_payload
class tRNSPayloadStructure(HomogenousSequenceStructure):
    registration_id = "tRNS"

    def __init__(self, root, parent_node, size, **kwargs):
        color_type = root.find_one("ColorTypeStructure").value
        if color_type == 3:
            octets_per_item = 1
            number_of_items = size
            seq_length = 1
        elif color_type == 0:
            octets_per_item = 2
            number_of_items = 1
            seq_length = 1
        elif color_type == 2:
            octets_per_item = 2
            number_of_items = 1 
            seq_length = 3
        super().__init__(root, parent_node, octets_per_item, number_of_items,
                         seq_length, size, byteorder="!", signed=False)


@registered_payload
class zTXtPayloadStructure(HomogenousSequenceStructure):
    registration_id = "zTXt"
    _fields = ('keyword', 'compression_method', 'compressed_text', 'text')

    def __init__(self, root, parent_node, size, **kwargs):
        super().__init__(root, parent_node, 1, size, byteorder="!",
                         signed=False)

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        super().consume_from_buffer(buffer, buffer_idx, **kwargs)
        keyword = []
        compression_method = None
        compressed_text = bytearray()
        in_keyword = True
        for val in self.node.value:
            if in_keyword and val == 0:
                in_keyword = False
            elif not in_keyword and compression_method is None:
                compression_method = val
            elif in_keyword :
                char = bytes([val]).decode('latin1')
                keyword.append(char)
            else:
                compressed_text.append(val)
        if compression_method != 0:
            self.warn("Unknown compression method.")
            text = ""
        else:
            text = zlib.decompress(compressed_text, 15)
        self.node["keyword"] = "".join(keyword)
        self.node["compression_method"] = compression_method
        self.node["compressed_text"] = compressed_text
        self.node["text"] = text
        return self()




class ColorTypeStructure(IntegerStructure):
    name = "color_type"
    _fields = ("palette_used", "color_used", "alpha_channel_used")

    def consume_from_buffer(self, buffer, buffer_idx=0, **kwargs):
        raw_data, size, value = super().consume_integer(
                                        buffer, buffer_idx)
        self.node["raw_data"] = raw_data
        self.node["size"] = size
        self.node["value"] = value
        self.node["palette_used"] =  bool(value & 1)
        self.node["color_used"] = bool(value & 2)
        self.node["alpha_channel_used"] = bool(value & 4)
        return self()

    def validate_value(self, validation_value):
        if validation_value not in [0,2,3,4,6]:
            return "Permitted values are 0,2,4,4 and 6"


class PNGChunkStructure(PayloadStructure):
    name = "chunk"
    def __init__(self, root, parent_node, **kwargs):
        substructures = []
        substructures.append(IntegerStructure(root, None, 4, byteorder= "!",
                                              signed=False, name="length"))
        substructures.append(ChunkTypeStructure(root, None, name="chunk_type"))
        substructures.append(ChunkPayloadStructure)
        substructures.append(ChunkCRCStructure(root, None, 4, byteorder="!",
                                               signed=False, name="crc"))
        super().__init__(root, parent_node, substructures)

    def validate_length(self, validation_value):
        if validation_value.value >= 2**31:
            return "Length of {} exceeds maximum value {}".format(
                validation_value.value, (2**31)-1
            )

    def validate_crc(self, validation_value):
        if (self.node.chunk_type.raw_data is not None and
            self.node.payload.raw_data is not None):
            data_iterator = chain(self.node.chunk_type.raw_data,
                                  self.node.payload.raw_data)
            crc = ChunkCRCStructure.generate_crc(data_iterator)
            if crc != validation_value.value:
                return "CRC {} did not match calculated CRC {}".format(
                    validation_value.value, crc
                )
        else:
            return "Unable to validate CRC"

class PNGFileSignatureStructure(StaticStructure):
    name = "png_file_signature"
    signature = b'\x89PNG\r\n\x1a\n'
    def __init__(self, root, parent_node):
        super().__init__(root, parent_node, self.signature)


class PNGStructure(PayloadStructure):
    def __init__(self):
        self.root_node = PNGRoot().node
        substructures = []
        substructures.append(PNGFileSignatureStructure(self.root_node, None))
        substructures.append(ContainerStructure(self.root_node,
                                                None,
                                                PNGChunkStructure,
                                                name="png_chunks"))
        super().__init__(self.root_node, self.root_node, substructures)

    singular_chunks = ["IHDR", "PLTE", "IEND", "cHRM", "gAMA", "sBIT",
                       "bKGD", "hIST", "tRNS", "pHYs", "tIME"]
    mandatory_chunks = ["IHDR", "IDAT", "IEND"]
    chunk_orderings = [
        ("cHRM", ("PLTE", "IDAT"), ()),
        ("gAMA", ("PLTE", "IDAT"), ()),
        ("sBIT", ("PLTE", "IDAT"), ()),
        ("bKGD", ("IDAT",), ("PLTE",)),
        ("hIST", ("IDAT",), ("PLTE",)),
        ("tRNS", ("IDAT",), ("PLTE",)),
        ("pHYs", ("IDAT",), ())
    ]

    def validate_png_chunks(self, png_chunks):
        chunks = [item.chunk_type.string_rep
                  for item in png_chunks.contents.children.values()]
        chunk_indices = {}
        for i, chunk in enumerate(chunks):
            chunk_indices.setdefault(chunk, []).append(i)
        if chunks[0] != "IHDR":
            self.warn("IHDR chunk must be first")
        for chunk in self.singular_chunks:
            if chunks.count(chunk) > 1:
                self.warn("Multiple {} chunks are not allowed".format(
                    chunk ))
        for chunk in self.mandatory_chunks:
            if chunks.count(chunk) == 0:
                self.warn("At least one {} chunk must be present".format(
                    chunk))
        consecutive = True
        started = False
        ended = False
        for chunk in chunks:
            if not started:
                if chunk == "IDAT":
                    started = True
            elif not ended:
                if chunk != "IDAT":
                    ended = True
            else:
                if chunk == "IDAT":
                    consecutive = False
                    break
        if not consecutive:
            self.warn("IDAT chunks must be consecutive")
        if chunks[-1] != "IEND":
            self.warn("IEND chunk must be last")
        for chunk, before, after in self.chunk_orderings:
            if chunk in chunks:
                for before_chunk in before:
                    if before_chunk in chunks:
                        mx = max(chunk_indices[before_chunk])
                        mn = min(chunk_indices[chunk])
                        if mn > mx:
                            self.warn(
                                "{} chunk must be before {} chunk".format(
                                    before_chunk, chunk))
                for after_chunk in after:
                    if after_chunk in chunks:
                        mn = min(chunk_indices[after_chunk])
                        mx = max(chunk_indices[chunk])
                        if mn > mx:
                            self.warn(
                                "{} chunk must be after {} chunk".format(
                                    after_chunk, chunk))

class PNGRoot(RootStructure):
    pass


if __name__ == "__main__":
    import sys
    with open(sys.argv[1], "rb") as f:
        png = PNGStructure()
        pngfield = png.consume_from_buffer(f, 0)
        stack = [(pngfield, 0, None)]
        while stack:
            item, depth, name = stack.pop()
            if hasattr(item, "name"):
                name = item.name + "(" + item.clsname + ")"
            indent = "   " * depth
#            print(item, type(item), isinstance(item, StructureNode))
            if isinstance(item, StructureNode):
#                print(item.children)
                print(indent + name)
                for childname, child in reversed(item):
                    stack.append((child, depth+1, childname))
            else:
                s = str(item)
                if len(s) > 64:
                    s = s[:61] + "..."
                print(indent + name + ": " + s)


