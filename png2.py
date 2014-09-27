#!/usr/bin/env python3

from node import *
from operator import *


class ColorTypeNode(IntegerNode("color_type", "!B",
                    extra_attributes=["palette_used",
                                      "color_used",
                                      "alpha_used"])):
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
             StringNode("chunk_type", 4, "latin9",
                validations={
                    "reserved": simple_validation("reserved", eq, 0,
                                                  "Reserved bit is set.")
                },
                derivations={
                    "ancillary": bit_flag("value", 5, 0, ord),
                    "private": bit_flag("value", 5, 1, ord),
                    "reserved": bit_flag("value", 5, 2, ord),
                    "safe_to_copy": bit_flag("value", 5, 3, ord)
                }),
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
                             IntegerNode("color_type", "!B",
                                 validations={
                                    "value": simple_validation(
                                        "value", contains, (0,2,3,4,6),
                                        "Invalid value.")},
                                 derivations={
                                    "palette_used": bit_flag("value", 0),
                                    "color_used": bit_flag("value", 1),
                                    "alpha_used": bit_flag("value", 2)
                             }),
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
