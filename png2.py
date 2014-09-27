#!/usr/bin/env python3

from node import *

class ChunkTypeNode(StringNode("chunk_type", 4, "latin9",
                    ["ancillary", "private", "reserved", "safe_to_copy"])):
    def derive_flag_bit(self, idx):
        return (ord(self.value[idx]) & 32) > 0

    def derive_ancillary(self):
        return self.derive_flag_bit(0)

    def derive_private(self):
        return self.derive_flag_bit(1)
    
    def derive_reserved(self):
        return self.derive_flag_bit(2)
    
    def derive_safe_to_copy(self):
        return self.derive_flag_bit(3)

    def validate_reserved(self):
        if self.reserved:
            return "Reserved bit is set."


class ColorTypeNode(IntegerNode("color_type", "!B",
                    ["palette_used", "color_used", "alpha_used"])):
    def derive_palette_used(self):
        return (self.value & 1) > 0

    def derive_color_used(self):
        return (self.value & 2) > 0

    def derive_alpha_used(self):
        return (self.value & 4) > 0

    def validate_value(self):
        if self.value not in (0, 2, 3, 4, 6):
            return "Invalid value"


PNGStructure = DefinedChildrenNode("PNG", [
    StaticNode("signature", b'\x89PNG\r\n\x1a\n'),
    NodeSequenceNode("chunks",
        DefinedChildrenNode("chunk",
            [IntegerNode("length", "!I"),
             ChunkTypeNode,
             DelegatingNode({
                "default": (IntegerSequenceNode,
                            "unknown_chunk_payload",
                            ["!B",lambda x: x.children[0].value],
                            {}),
                "IHDR": (DefinedChildrenNode,
                        "IHDR_chunk_payload",
                        [
                            [IntegerNode("width", "!I"),
                             IntegerNode("height", "!I"),
                             IntegerNode("bit_depth", "!B"),
                             ColorTypeNode,
                             IntegerNode("compression_method", "!B"),
                             IntegerNode("filter_method", "!B"),
                             IntegerNode("interlace_method", "!B")]
                        ],
                        {})
                },
                lambda x: x.children[1].value),
                IntegerNode("crc", "!I")
            ]

        )
    )]
)

def test():
    with open("test3.png", "rb") as f:
        png = PNGStructure.from_buffer(f, None)
        print(png.tree_string())

if __name__ == "__main__":
    test()
