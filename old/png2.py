#!/usr/bin/env python3

from node import *
from operator import *
import zlib

def decompress(node):
    try:
        return zlib.decompress(node.value, 15)
    except zlib.error:
        node.warnings.append("Decompression error.")
        return ""

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
                           "!B", Path("./*[classname=length]/value")),
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
                    "!B", Path("./*[classname=length]/value",
                               lambda val, n: val//3), 3),
                "IDAT": BytestringNode("IDAT_chunk_payload",
                    Path("./*[classname=length]/value")),
                "IEND": StaticNode("IEND_chunk_payload", b""),
                "bKGD": DelegatingNode({
                    1: IntegerNode("bKGD_chunk_payload", "!B"),
                    2: IntegerNode("bKGD_chunk_payload", "!H"),
                    6: IntegerSequenceNode("bKGD_chunk_payload", "!H", 3)},
                    Path("./*[classname=length]/value")),
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
                "iCCP": DefinedChildrenNode("iCCP_chunk_payload", [
                    NullTerminatedStringNode("profile_name", "latin1"),
                    IntegerNode("compression_method", "!B",
                        validations = {
                            "value": simple_validation("value", eq, 0)
                        },
                        derivations = {
                            "meaning": lookup(
                                "value", {0: "deflate/inflate compression"}
                            )
                        }
                    ),
                    BytestringNode("compressed_profile",
                        Path("../*[classname=length]/value",
                           lambda v,n: v - len(Path(
                                "./*/*[classname=profile_name]/value")(n)) + 2),
                        derivations = {
                            "decompressed_profile": 
                                lambda v, n: decompress(n)
                        }
                    )
                ]),
                "hIST": IntegerSequenceNode("hIST_chunk_payload", "!H",
                            Path("./*[classname=length]/value")),
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
                    "!B", Path("./*/.[classname=length]/value")),
                "sRGB": IntegerNode("sRGB_chunk_payload", "!B",
                    validations = {
                        "value": simple_validation("value", is_in, (0,1,2,3))
                    },
                    derivations = {
                        "rendering_intent": lookup("value",
                            {0: "perceptual",
                             1: "relative colorimetric",
                             2: "saturation",
                             3: "absolute colorimetric"}
                        )
                    }
                ),
                "tEXt": DefinedChildrenNode("tEXt_chunk_payload", [
                    NullTerminatedStringNode("keyword", "latin1"),
                    StringNode("text",
                        Path("../*[classname=length]/value",
                             lambda v,n: v - (
                                len(Path("./*[classname=tEXt_chunk_payload]" +
                                         "/*[classname=keyword]/value")(n))+1)
                            ),
                        "latin1")
                ]),
                "iTXt": DefinedChildrenNode("iTXt_chunk_payload", [
                    NullTerminatedStringNode("keyword"),
                    IntegerNode("compression_flag", "!B",
                        validations = {
                            "value": simple_validation("value", is_in, (0,1))
                        },
                        derivations = {
                            "meaning": lookup("value",
                                {0: "uncompressed text",
                                 1: "compressed text"}
                            )
                        }
                    ),
                    IntegerNode("compression_method", "!B",
                        validations = {
                            "value": simple_validation("value", eq, 0)
                        },
                        derivations = {
                            "meaning": lookup("value",
                                {0: "deflate/inflate compression"}
                            )
                        }
                    ),
                    NullTerminatedStringNode("language_tag"),
                    NullTerminatedStringNode("translated_keyword", "utf8"),
                    DelegatingNode({
                        0: StringNode("text", Path(
                            "../*[classname=length]/value",
                            lambda v, n: v - sum([
                                len(Path(
                                    "./*[classname=iTXt_chunk_payload]/" +
                                    "*[classname=keyword]/value")(n)),
                                len(Path(
                                    "./*[classname=iTXt_chunk_payload]/" +
                                    "*[classname=language_tag]/value")(n)),
                                len(Path(
                                    "./*[classname=iTXt_chunk_payload]/" +
                                    "*[classname=translated_keyword]/value")(n)),
                                5]))),
                        1: BytestringNode("compressed_text", Path(
                             "../*[classname=length]/value",
                            lambda v, n: v - sum([
                                len(Path(
                                    "./*[classname=iTXt_chunk_payload]/" +
                                    "*[classname=keyword]/value")(n)),
                                len(Path(
                                    "./*[classname=iTXt_chunk_payload]/" +
                                    "*[classname=language_tag]/value")(n)),
                                len(Path(
                                    "./*[classname=iTXt_chunk_payload]/" +
                                    "*[classname=translated_keyword]/value")(n)),
                                5])),
                            derivations = {
                                "decompressed_text": 
                                    lambda v, n: decompress(n)
                            }),
                        },
                        lambda n: n.children[1].value
                    )
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
                        lambda v, n: {2: "!H", 3: "!B", 0: "!H"}.get(
                            v, "!B")),
                     Path("../0/2/3/value",
                        lambda v, n: {2: 1,
                                      3: n.children[0].value,
                                      0: n.children[0].value//2}.get(
                                        v, n.children[0].value)),
                     Path("../0/2/3/value",
                        lambda v, n: {2: 3, 3: 1, 0: 1}.get(v, 1))),
                "zTXt": DefinedChildrenNode("zTXt_chunk_payload", [
                    NullTerminatedStringNode("keyword", "latin1"),
                    IntegerNode("compression_method", "!B",
                        validations = {
                            "value": simple_validation(
                                "value", eq, 0)},
                        derivations = {
                            "meaning": lookup("value",
                                {0: "deflate/inflate compression"})
                        }),
                    BytestringNode("compressed_text",
                        Path("../*[classname=length]/value",
                             lambda v,n: v - (
                                len(Path("./*[classname=zTXt_chunk_payload]" +
                                         "/*[classname=keyword]/value")(n))+2)
                            ),
                        derivations = {
                            "decompressed_text": 
                                lambda v, n: decompress(n)
                        }
                    )]),
                "oFFs": DefinedChildrenNode("oFFs_chunk_payload", [
                    IntegerNode("x_position", "!i"),
                    IntegerNode("y_position", "!i"),
                    IntegerNode("unit_specifier", "!B",
                        validations = {
                            "value": simple_validation("value", is_in, (0,1))
                        },
                        derivations = {
                            "meaning": lookup("value",
                                {0: "pixel", 1: "micrometer"})
                        }
                    )]),
                # not sure if this works as can't find any example images
                "pCAL": DefinedChildrenNode("pCAL_chunk_payload", [
                    NullTerminatedStringNode("calibration_name", "latin1"),
                    IntegerNode("original_zero", "!i"),
                    IntegerNode("original_max", "!i"),
                    IntegerNode("equation_type", "!B"),
                    IntegerNode("number_of_parameters", "!B"),
                    NullTerminatedStringNode("unit_name"),
                    NodeSequenceNode("parameters",
                        DelegatingNode({
                            True: NullTerminatedStringNode(
                                "parameter", "ascii"),
                            False: StringNode("parameter",
                                Path("../../*[classname=length]/value",
                                lambda v, n: v - sum([
                                    len(Path(
                                        "./*[classname=pCAL_chunk_payload]/" +
                                        "*[classname=calibration_name]/value")(n)),
                                    len(Path(
                                        "./*[classname=pCAL_chunk_payload]/" +
                                        "*[classname=unit_name]/value")(n)),
                                    sum([len(p) + 1 for p in 
                                        Path(
                                        "./*[classname=pCAL_chunk_payload]/" +
                                        "*[classname=parameters]/*/value",
                                        False)(n)]),
                                    11])
                                ),"utf8")
                            }, 
                            lambda n: Path(
                            "../*[classname=number_of_parameters]/value")(n) -
                            len(Path(
                                "../*[classname=parameters]/*")(n,False)) > 1
                        ),
                        Path("./*[classname=number_of_parameters]/value")
                        ),
                    ])},
                Path("./1/value")),
            IntegerNode("crc", "!I")],
            derivations={
                "payload_type": Path("./1/value")
            }
        )
    )]
)


def test():
    import sys
    with open(sys.argv[1], "rb") as f:
        png = PNGStructure.all_from_buffer(f, None)
        print(png.tree_string())

def test2():
    import os
    d = "/home/james/Documents/current_projects/png/test2" 
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".png"):
            with open(os.path.join(d, fn), "rb") as f:
                try:
                    print(fn)
                    png = PNGStructure.all_from_buffer(f, None)
                    print(png.tree_string())
                    print("_" * 80)
                    print("\n\n")
                except (BufferReadError, IndexError) as err:
                   print("Error reading " + fn, err)


if __name__ == "__main__":
    test2()
