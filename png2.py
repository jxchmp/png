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
                    "reserved": simple_validation("reserved", eq, 0)
                },
                derivations={
                    "ancillary": bit_flag("value", 5, 0, ord),
                    "private": bit_flag("value", 5, 1, ord),
                    "reserved": bit_flag("value", 5, 2, ord),
                    "safe_to_copy": bit_flag("value", 5, 3, ord)
                }),
            DelegatingNode({
                "default": IntegerSequenceNode("unknown_chunk_payload",
                           "!B", Path("./0/value")),
                "IHDR": DefinedChildrenNode("IHDR_chunk_payload", [
                    IntegerNode("width", "!I",
                        validations={
                            "value": simple_validation(
                                "value", between, (0,(2**31)-1))
                        }),
                    IntegerNode("height", "!I",
                        validations={
                            "value": simple_validation(
                                "value", between, (0,(2**31)-1))
                        }),
                    IntegerNode("bit_depth", "!B",
                        validations={
                            "value": simple_validation(
                                "value", is_in, (1,2,4,8,16))
                        }),
                    IntegerNode("color_type", "!B",
                        validations={
                            "value": simple_validation(
                                "value", is_in, (0,2,3,4,6))
                        },
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
                                "value", eq, 0)
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
                                "value", eq, 0)
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
                                "value", is_in, (0,1))
                        }
                    )
                ]),
                "PLTE": IntegerSequenceNode("PLTE_chunk_payload",
                    "!B", Path("./0/value", lambda val, n: val//3), 3),
                "IDAT": BytestringNode("IDAT_chunk_payload",
                    Path("./0/value")),
                "IEND": StaticNode("IEND_chunk_payload", b""),
                "bKGD": DelegatingNode({
                    1: IntegerNode("bKGD_chunk_payload", "!B"),
                    2: IntegerNode("bKGD_chunk_payload", "!H"),
                    6: IntegerSequenceNode("bKGD_chunk_payload", "!H", 3)},
                    Path("./0/value")),
                "cHRM": DefinedChildrenNode("cHRM_chunk_payload", [
                    IntegerNode("white_point_x", "!I"),
                    IntegerNode("white_point_y", "!I"),
                    IntegerNode("red_x", "!I"),
                    IntegerNode("red_y", "!I"),
                    IntegerNode("green_x", "!I"),
                    IntegerNode("green_y", "!I"),
                    IntegerNode("blue_x", "!I"),
                    IntegerNode("blue_y", "!I")]),
                "gAMA": IntegerNode("gAMA_chunk_payload", "!I"),
                "hIST": IntegerSequenceNode("hIST_chunk_payload", "!H",
                                            Path("./0/value")),
                "pHYs": DefinedChildrenNode("pHYs_chunk_payload", [
                    IntegerNode("pixels_per_unit_x_axis", "!I"),
                    IntegerNode("pixels_per_unit_y_axis", "!I"),
                    IntegerNode("unit_specifier", "!B",
                        derivations = {
                            "meaning": lookup(
                                 "value", {0: "unknown", 1: "meter"})
                         })
                    ]),
                "sBIT": IntegerSequenceNode("sBIT_chunk_payload",
                    "!B", Path("./0/value")),
                "tEXt": DefinedChildrenNode("tEXt_chunk_payload", [
                    NullTerminatedStringNode("keyword", "latin1"),
                    StringNode("text",
                        Path("../0/value",
                             lambda v,n: v - (len(Path("./0/value")(n))+1)),
                        "latin1")
                ]),
                "tIME": DefinedChildrenNode("tIME_chunk_payload", [
                    IntegerNode("year", "!H"),
                    IntegerNode("month", "!B",
                        validations = {
                            "value": simple_validation(
                                "value", between, (1,12))
                        }),
                    IntegerNode("day", "!B",
                        validations = {
                            "value": simple_validation(
                                "value", between, (1,31))
                        }),
                    IntegerNode("hour", "!B",
                        validations = {
                            "value": simple_validation(
                                "value", between, (0,23))
                        }),
                    IntegerNode("minute", "!B",
                        validations = {
                            "value": simple_validation(
                                "value", between, (0,59))
                        }),
                    IntegerNode("second", "!B",
                        validations = {
                            "value": simple_validation(
                                "value", between, (0,60))
                        })
                ]),
                "tRNS": IntegerSequenceNode("tRNS_chunk_payload",
                     Path("../0/2/3/value",
                        lambda v, n: {2: "!H", 3: "!B", 0: "!H"}[v]),
                     Path("../0/2/3/value",
                        lambda v, n: {2: 1,
                                      3: n.children[0].value,
                                      0: n.children[0].value//2}[v]),
                     Path("../0/2/3/value",
                        lambda v, n: {2: 3, 3: 1, 0: 1}[v]))
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

def test2():
    import os
    d = "/home/james/Documents/current_projects/png/test" 
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".png"):
            with open(os.path.join(d, fn), "rb") as f:
                try:
                    png = PNGStructure.from_buffer(f, None)
                    #print(png.tree_string())
                except BufferReadError:
                   print("Error reading " + fn)


if __name__ == "__main__":
    test2()
