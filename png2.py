#!/usr/bin/env python3

from node import *
from operator import *

PNGStructure = DefinedChildrenNode("PNG", [
    StaticNode("signature", b'\x89PNG\r\n\x1a\n'),
    NodeSequenceNode("chunks",
        DefinedChildrenNode("chunk", [
            IntegerNode("length", "!I"),
            StringNode("chunk_type", 4, "latin1",
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
                "default": (
                    IntegerSequenceNode,
                    "unknown_chunk_payload",
                    ["!B", Path("./0/value")]),
                "IHDR": (
                    DefinedChildrenNode,
                    "IHDR_chunk_payload",
                    [[
                        IntegerNode("width", "!I",
                            validations={
                                "value": compound_validation([
                                    simple_validation(
                                        "value", gt, 0,
                                        "width must be greater than zero"
                                    ),
                                    simple_validation(
                                        "value", lt, 2**31,
                                        "width must be less than 2**31"
                                    )
                                ])
                            }),
                        IntegerNode("height", "!I",
                            validations={
                                "value": compound_validation([
                                    simple_validation(
                                        "value", gt, 0,
                                        "height must be greater than zero"
                                    ),
                                    simple_validation(
                                        "value", lt, 2**31,
                                        "height must be less than 2**31"
                                    )
                                ])
                            }),
                        IntegerNode("bit_depth", "!B",
                            validations={
                                "value": simple_validation(
                                    "value", contains, (1,2,4,8,16),
                                    "bit depth must be one of 1,2,4,8,16"
                                )
                            }),
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
                        IntegerNode("compression_method", "!B",
                            derivations={
                                "meaning": lookup(
                                    "value",
                                    {0: "deflate/inflate 32k sliding window"}
                                )
                            },
                            validations={
                                "value": simple_validation(
                                    "value", eq, 0,
                                    "Unknown compression method")
                            }
                        ),
                        IntegerNode("filter_method", "!B",
                             derivations={
                                "meaning": lookup(
                                    "value",
                                    {0: "adaptive filtering with 5 filter types"}
                                )
                            },
                            validations={
                                "value": simple_validation(
                                    "value", eq, 0,
                                    "Unknown filter method")
                            }
                        ),
                        IntegerNode("interlace_method", "!B",
                              derivations={
                                "meaning": lookup(
                                    "value",
                                    {0: "no interlacing",
                                     1: "Adam7 interlace"}
                                )
                            },
                            validations={
                                "value": simple_validation(
                                    "value", contains, (0,1),
                                    "Unknown interlace method")
                            }
                        )]
                    ])
                },
                Path("./1/value")
            ),
            IntegerNode("crc", "!I")]
        )
    )]
)


def test():
    with open("test3.png", "rb") as f:
        png = PNGStructure.from_buffer(f, None)
        print(png.tree_string())

if __name__ == "__main__":
    test()
