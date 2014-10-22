#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from definition import *
from validation import *
from attribute import *
from path import Path
from source import FileSource
import zlib

##############################################################################
# Utility functions                                                          #
##############################################################################

def decompress(node, value):
    """
    Return the decompressed value of the given zlib DEFLATE
    compressed bytestring.
    """
    try:
        return zlib.decompress(value, 15)
    except zlib.error:
        raise AttributeProcessingError(
            "Decompression error on node '{}'".format(node))
        return ""


##############################################################################
# Payloads                                                                   #
##############################################################################

PNGPayloads = DelegatingDef({}, Path().chunk_type.value + "_payload")

# An unknown chunk payload is treated as a bytestring, using the length given
# in the chunk length field
PNGPayloads.register(
    BytestringDef(
        "unknown_payload",
        Path().parent.children[0].attributes["value"],
    ), "default"
)

##############################################################################
# Critical chunks                                                            #
##############################################################################

# IHDR - Image Header
# http://www.w3.org/TR/PNG/#11IHDR
PNGPayloads.register(
    DefinedChildrenDef("IHDR_payload", [
        IntegerDef("width", "!I",
            validation=[Validation("value", "in", range(0,2**31),
                        description="Invalid width")]),
        IntegerDef("height", "!I",
            validation=[Validation("value", "in", range(0, 2**31),
                        description="Invalid height")]),
        IntegerDef("bit_depth", "!B",
            validation=[Validation("value", "in", [1,2,4,8,16],
                        description="Invalid bit_depth")]),
        IntegerDef("color_type", "!B",
            validation=[
                Validation("value", "in", [0,2,3,4,6],
                        description="Invalid color_type"),
                Validation(("value", Path().parent.bit_depth.value),
                           "in",
                           [(0,1), (0,2), (0,4), (0,8), (0,16),
                            (2,8), (2,16), (3,1), (3,2), (3,4), (3,8),
                            (4,8), (4,16), (6,8), (6,16)],
                        description="Invalid combination of color_type and " +
                                    "bit_depth")
            ]),
        IntegerDef("compression_method", "!B",
            validation=[Validation("value", "==", 0,
                        description="Invalid compression_method")]),
        IntegerDef("filter_method", "!B",
            validation=[Validation("value", "==", 0,
                        description="Invalid filter_method")]),
        IntegerDef("interlace_method", "!B",
            validation=[Validation("value", "in", [0,1],
                        description="Invalid interlace_method")])
        ],
        validation = [
            Validation(
                Path().root.count_descendents(
                    [lambda n: n._name == 'IHDR_payload']),
                "==", 1, stage="pre",
                error=ValidationError,
                description="IHDR chunk can only appear once"),
            Validation(
                Path().root.descendents([
                    lambda node: node._name == "chunks"
                ])[0].children.index(Path().parent), "==", 0,
                description="IHDR chunk must be the first chunk")
        ]
    )
)

# PLTE - Palette
# http://www.w3.org/TR/PNG/#11PLTE
PNGPayloads.register(
    IntegerSequenceDef("PLTE_payload", "!B",
        Path().siblings[0].attributes["value"] // 3, 3,
        validation=[
            Validation(Path().parent.children[0].value % 3, "==", 0,
                    description="PLTE length must be divisible by 3"),
            Validation(
                Path().root.count_descendents(
                    [lambda n: n._name == "PLTE_payload"]),
                    "==", 1, stage="pre", error=ValidationError,
                    description="PLTE chunk can only appear once"),
            Validation(
                Path().root.descendents([
                    lambda n: n._name == "IDAT_payload"]), "==", [],
                    description="PLTE chunk must appear before first IDAT " +
                                "chunk"),
            Validation(
                Path().root.count_descendents(
                    [lambda node: node._name in
                    ("bKGD_payload", "hIST_payload", "tRNS_payload")]
                ), "==", 0,
                description="PLTE chunk must appear before bKGD, hIST and " +
                            "tRNS chunks")
        ]
    )
)

# IDAT - Image Data
# http://www.w3.org/TR/PNG/#11IDAT
PNGPayloads.register(
    BytestringDef("IDAT_payload", Path().siblings[0].value,
        validation = [
            Validation(
                Path().root.count_descendents([
                    lambda node: node._name == "IDAT_payload"
                ]), "==", 1) |
            Validation(
                Path().parent.parent.children[-2].attributes["type"],
                "==", "IDAT", description="IDAT payloads must be sequential"
            )
        ]
    )
)

# IEND - Image Trailer
# http://www.w3.org/TR/PNG/#11IEND
PNGPayloads.register(
    StaticDef("IEND_payload", b'')
)

##############################################################################
# Ancillary chunks                                                           #
##############################################################################

# tRNS - Transparency
# http://www.w3.org/TR/PNG/#11tRNS
PNGPayloads.register(
    DelegatingDef({
            0:  IntegerDef("tRNS_payload", "!H"),
            2:  IntegerSequenceDef("tRNS_payload", "!H", 1, 3),
            "default":  IntegerSequenceDef("tRNS_payload", "!B",
                             Path().siblings[0].value)
        },
        Path().root.descendents(
            [lambda node: node._name=="IHDR_payload"])[0].color_type.value,
        validation=[
            Validation(
                Path().root.descendents(
                    [lambda node: node._name=="IHDR_payload"]), 
                "!=", [], stage="pre", error=ValidationFatal,
                description="tRNS chunk requires IHDR chunk"
            ),
            Validation(
                Path().root.count_descendents(
                    [lambda n: n._name == "tRNS_payload"]),
                    "==", 0, stage="pre", error=ValidationError,
                    description="tRNS chunk can only appear once"),

        ]
    ), "tRNS_payload"
)

# cHRM - Primary chromaticities and white point
# http://www.w3.org/TR/PNG/#11cHRM
PNGPayloads.register(
    DefinedChildrenDef("cHRM_payload", [
        IntegerDef("white_point_x", "!I"),
        IntegerDef("white_point_y", "!I"),
        IntegerDef("red_x", "!I"),
        IntegerDef("red_y", "!I"),
        IntegerDef("green_x", "!I"),
        IntegerDef("green_y", "!I"),
        IntegerDef("blue_x", "!I"),
        IntegerDef("blue_y", "!I")
        ],
        validation=[
            Validation(Path().root.count_descendents(
                    [lambda n: n._name == 'cHRM_payload']),
                "==", 1, stage="pre", error=ValidationError,
                description="cHRM chunk can only appear once"),
            Validation(
                Path().root.count_descendents(
                    [lambda node: node._name in
                    ("IDAT_payload", "PLTE_payload")]
                ), "==", 0,
                description="cHRM chunk must appear before PLTE and IDAT " +
                            "chunks")
        ]
    )
)

# gAMA - Image gamma
# http://www.w3.org/TR/PNG/#11gAMA
PNGPayloads.register(
    IntegerDef("gAMA_payload", "!I",
        validation=[
            Validation(Path().root.count_descendents(
                    [lambda n: n._name == 'gAMA_payload']),
                "==", 1, stage="pre", error=ValidationError,
                description="gAMA chunk can only appear once"),
            Validation(
                Path().root.count_descendents(
                    [lambda node: node._name in
                    ("IDAT_payload", "PLTE_payload")]
                ), "==", 0,
                description="gAMA chunk must appear before PLTE and IDAT " +
                            "chunks"
            )
        ]   
    )
)

# iCCP - Embedded ICC profile
# http://www.w3.org/TR/PNG/#11iCCP
PNGPayloads.register(
    DefinedChildrenDef("iCCP_payload", [
        NullTerminatedStringDef("profile_name", "latin1"),
        IntegerDef("compression_method", "!B",
            validation=[Validation("value", "==", 0,
                        description="Invalid compression_method")]),
        BytestringDef("compressed_profile",
            (Path().parent.parent.children[0].value -
            (Path().parent.profile_name.length + 1)),
            attributes = [
                Attribute("decompressed_profile", decompress, [Path().value])
            ])
        ],
        validation=[
             Validation(Path().root.count_descendents(
                    [lambda n: n._name == 'iCCP_payload']),
                "==", 1, stage="pre", error=ValidationError,
                description="iCCP chunk can only appear once"),
            Validation(
                Path().root.count_descendents(
                    [lambda node: node._name in
                    ("IDAT_payload", "PLTE_payload")]
                ), "==", 0,
                description="iCCP chunk must appear before PLTE and IDAT " +
                            "chunks"),
            Validation(
                Path().root.count_descendents(
                    [lambda node: node._name == "sRGB_payload"]
                ), "==", 0, error=ValidationWarning,
                description="iCCP chunk should not appear when sRGB chunk " +
                            "present"
            )
        ]   
    )
)

# sBIT - Significant bits
# http://www.w3.org/TR/PNG/#11sBIT
PNGPayloads.register(
    DelegatingDef({
        0: DefinedChildrenDef("sBIT_payload", [
                IntegerDef("significant_greyscale_bits", "!B")
           ]),
        2: DefinedChildrenDef("sBIT_payload", [
                IntegerDef("significant_red_bits", "!B"),
                IntegerDef("significant_green_bits", "!B"),
                IntegerDef("significant_blue_bits", "!B")
           ]),
        3: 2,
        4: DefinedChildrenDef("sBIT_payload", [
                IntegerDef("significant_greyscale_bits", "!B"),
                IntegerDef("significant_alpha_bits", "!B")
           ]),
        6: DefinedChildrenDef("sBIT_payload", [
                IntegerDef("significant_red_bits", "!B"),
                IntegerDef("significant_green_bits", "!B"),
                IntegerDef("significant_blue_bits", "!B"),
                IntegerDef("significant_alpha_bits", "!B")
           ]),
        "default": BytestringDef("sBIT_payload", 
                       Path().siblings[0].attributes["value"]
                   )
        },
        Path().root.descendents(
            [lambda node: node._name=="IHDR_payload"])[0].color_type.value,
        validation = [
            Validation(Path().root.count_descendents(
                    [lambda n: n._name == 'sBIT_payload']),
                "==", 0, stage="pre", error=ValidationError,
                description="sBIT chunk can only appear once"),
            Validation(
                Path().root.count_descendents(
                    [lambda node: node._name in
                     ("IDAT_payload", "PLTE_payload")]
                ), "==", 0,
                description="sBIT chunk must appear before PLTE and " +
                            "IDAT chunks")
        ]
    ),
    "sBIT_payload"
)

# sRGB - Standard RGB colour space
# http://www.w3.org/TR/PNG/#11sRGB
PNGPayloads.register(
    IntegerDef("sRGB_payload", "!B",
        validation=[
            Validation("value", "in", (0,1,2,3),
                        description="Invalid sRGB value"),
            Validation(Path().root.count_descendents(
                [lambda n: n._name == 'sRGB_payload']),
                "==", 1, stage="pre", error=ValidationError,
                description="sRGB chunk can only appear once"),
            Validation(
                Path().root.count_descendents(
                [lambda node: node._name in ("IDAT_payload", "PLTE_payload")]
                ), "==", 0,
                description="sRGB chunk must appear before PLTE and IDAT " +
                            "chunks"),
            Validation(
                Path().root.count_descendents(
                    [lambda node: node._name == "iCCP_payload"]
                ), "==", 0, error=ValidationWarning,
                description="sRGB chunk should not appear when iCCP chunk " +
                            "present"
            )
        ]
    )
)

# tEXt - Textual data
# http://www.w3.org/TR/PNG/#11tEXt
PNGPayloads.register(
    DefinedChildrenDef("tEXt_payload", [
        NullTerminatedStringDef("keyword", "latin1"),
        StringDef("text",
            Path().parent.parent.children[0].value -
            (Path().parent.keyword.length), "latin1")
    ])
)

# zTXt - Compressed text data
# http://www.w3.org/TR/PNG/#11zTXt
PNGPayloads.register(
    DefinedChildrenDef("zTXt_payload", [
        NullTerminatedStringDef("keyword", "latin1"),
        IntegerDef("compression_method", "!B",
            validation=[Validation("value", "==", 0,
                            description="Invalid zTXt compression_method")]
        ),
        BytestringDef("compressed_text",
            Path().parent.parent.children[0].value - 
            (Path().parent.keyword.length + 1),
            attributes = [
                Attribute("decompressed_text", decompress, [Path().value])
            ]
        )
    ])
)

# iTXt - International textual data
# http://www.w3.org/TR/PNG/#11iTXt
PNGPayloads.register(
    DefinedChildrenDef("iTXt_payload", [
        NullTerminatedStringDef("keyword", "latin1"),
        IntegerDef("compression_flag", "!B",
            validation=[Validation("value", "in", (0,1),
                            description="Invalid iTXt compression_flag")]),
        IntegerDef("compression_method", "!B",
            validation=[Validation("value", "==", 0,
                            description="Invalid iTXt compression_method")]),
        NullTerminatedStringDef("language_tag", "latin1"),
        NullTerminatedStringDef("translated_keyword", "utf-8"),
        DelegatingDef({
            0: StringDef("text",
                Path().parent.parent.children[0].value -
                (Path().parent.keyword.length +
                 Path().parent.language_tag.length +
                 Path().parent.translated_keyword.length + 2),
                "utf-8"),
            1: StringDef("text",
                Path().parent.parent.children[0].value -
                (Path().parent.keyword.length +
                 Path().parent.language_tag.length +
                 Path().parent.translated_keyword.length + 2),
                "utf-8",
                attributes = [Attribute("decompressed_text", decompress,
                                        Path().value)
                ]),
            "default": 0
            },
            Path().compression_flag.value
        )
    ])
)

##############################################################################
# Miscellaneous Information                                                  #
##############################################################################

# bKGD - Background colour
# http://www.w3.org/TR/PNG/#11bKGD
PNGPayloads.register(
    DelegatingDef({
            0: IntegerDef("bKGD_payload", "!H"),
            4: 0,
            2: IntegerSequenceDef("bKGD_payload", "!H", 1, 3),
            6: 2,
            3: IntegerDef("bKDG_payload", "!B"),
            "default": BytestringDef("bKGD_payload", 
                         Path().siblings[0].attributes["value"]
                   )
        },
        Path().root.descendents(
            [lambda node: node._name=="IHDR_payload"])[0].color_type.value,
        validation = [
            Validation(Path().root.descendents(
                [lambda node: node._name=="IHDR_payload"]),
                "not in", [[],()], stage="pre", error=ValidationFatal,
                description="bKDG chunk requires IHDR chunk"),
            Validation(Path().root.count_descendents(
                [lambda n: n._name == 'bKGD_payload']),
                "==", 0, stage="pre", error=ValidationError,
                description="bKGD chunk can only appear once"),
            Validation(
                Path().root.count_descendents(
                    [lambda node: node._name == ("IDAT_payload")]
                ), "==", 0,
                description="bKGD chunk must appear before IDAT chunks")
        ]
    ),
    "bKGD_payload"
)

# hIST - Image histogram
# http://www.w3.org/TR/PNG/#11hIST
PNGPayloads.register(
    IntegerSequenceDef("hIST_payload", "!H", Path().siblings[0].value // 2,
    validation = [
        Validation(Path().root.count_descendents(
            [lambda n: n._name == 'hIST_payload']),
            "==", 1, stage="pre", error=ValidationError,
            description="hIST chunk can only appear once"),
        Validation(
            Path().root.count_descendents(
                [lambda node: node._name == ("IDAT_payload")]
            ), "==", 0,
            description="hIST chunk must appear before IDAT chunks")
        ]
    )
)

# pHYs - Physical pixel dimensions
# http://www.w3.org/TR/PNG/#11pHYs
PNGPayloads.register(
    DefinedChildrenDef("pHYs_payload", [
        IntegerDef("pixels_per_unit_x_axis", "!I"),
        IntegerDef("pixels_per_unit_y_axis", "!I"),
        IntegerDef("unit_specifier", "!B",
            validation=[Validation("value", "in", (0,1),
                description="Invalid pHYs unit_specifier")])
        ],
        validation = [
            Validation(Path().root.count_descendents(
                [lambda n: n._name == 'pHYs_payload']),
                "==", 1, stage="pre", error=ValidationError,
                description="pHYs chunk can only appear once"),
            Validation(
                Path().root.count_descendents(
                    [lambda node: node._name == ("IDAT_payload")]
                ), "==", 0,
                description="pHYs chunk must appear before IDAT chunks")
        ]
    )
)

# sPLT - Suggested palette
# http://www.w3.org/TR/PNG/#11sPLT
PNGPayloads.register(
    DefinedChildrenDef("sPLT_payload", [
        NullTerminatedStringDef("palette_name", "latin1"),
        IntegerDef("sample_depth", "!B"),
        NodeSequenceDef("sPLT_entry",
            DelegatingDef({
                1: 8,
                2: 8,
                4: 8,
                8: DefinedChildrenDef("palette", [
                        IntegerDef("red", "!B"),
                        IntegerDef("green", "!B"),
                        IntegerDef("blue", "!B"),
                        IntegerDef("alpha", "!B"),
                        IntegerDef("frequency", "!H")
                   ]),
                16:DefinedChildrenDef("palette", [
                        IntegerDef("red", "!H"),
                        IntegerDef("green", "!H"),
                        IntegerDef("blue", "!H"),
                        IntegerDef("alpha", "!H"),
                        IntegerDef("frequency", "!H")
                   ])
                }, Path().parent.sample_depth.value
            ), ((Path().parent.parent.children[0].value -
                (Path().parent.palette_name.length + 1)) //
                (((Path().parent.sample_depth.value // 8) * 4) + 2))
        )],
        validation = [
            Validation(
                Path().root.count_descendents(
                    [lambda node: node._name == ("IDAT_payload")]
                ), "==", 0,
                description="sPLT chunk must appear before IDAT chunks")
        ]
    )
)

# tIME - Image last modification time
# http://www.w3.org/TR/PNG/#11tIME
PNGPayloads.register(
    DefinedChildrenDef("tIME_payload", [
        IntegerDef("year", "!H"),
        IntegerDef("month", "!B",
            validation=[Validation("value", "in", range(1, 13),
                description="Invalid tIME month value")]
        ),
        IntegerDef("day", "!B",
            validation=[Validation("value", "in", range(1, 32),
                description="Invalid tIME day value")]
        ),
        IntegerDef("hour", "!B",
            validation=[Validation("value", "in", range(24),
                description="Invalid tIME hour value")]
        ),
        IntegerDef("minute", "!B",
            validation=[Validation("value", "in", range(60),
                description="Invalid tIME minute value")]
        ),
        IntegerDef("second", "!B",
            validation=[Validation("value", "in", range(61),
                description="Invalid tIME second value")]
        )],
        validation = [
            Validation(Path().root.count_descendents(
                    [lambda n: n._name == 'tIME_payload']),
                    "==", 1, stage="pre", error=ValidationError,
                    description="tIME chunk can only appear once"
            )
        ]  
    )
)


##############################################################################
# Chunk and PNG structures                                                   #
##############################################################################


# Chunk structure
PNGChunk = DefinedChildrenDef("chunk", [
        IntegerDef("length", "!I",
            validation=[Validation("value", "in", range(0, 2**31))]),
        StringDef("chunk_type", 4, "ascii",
            validation = [
                Validation("value", "matches", r'[a-zA-Z]{4}',
                    description="Invalid chunk name"),
                Validation("reserved", "==", False,
                    description="Reserved bit of chunk is set",
                    error=ValidationInfo)
            ],
            attributes = [
                Definition.bit_flag("ancillary", "value", 5, 0, ord),
                Definition.bit_flag("private", "value", 5, 1, ord),
                Definition.bit_flag("reserved", "value", 5, 2, ord),
                Definition.bit_flag("safe_to_copy", "value", 5, 2, ord)
            ]
        ),
        PNGPayloads,
        IntegerDef("crc", "!I")
    ],
    validation = [
        Validation(Path().children[2].length, "==", Path().children[0].value,
            error=ValidationFatal,
            description="Length declared in chunk header does not match " +
                        "the size of the chunk found on reading"
            )
    ],
    attributes = [
        Attribute("type", Path().children[1].value)
    ]
)

# PNG structure
PNG = DefinedChildrenDef("PNG", [
        StaticDef("signature", b'\x89PNG\r\n\x1a\n'),
        NodeSequenceDef("chunks", PNGChunk)
    ]
)

def main():
    import sys, node
    for fn in sys.argv[1:]:
        print(fn)
        root = node.Node("root", None)
        try:
            png = PNG.construct(FileSource(fn), root)
        except ValidationFatal as err:
            print("    " + str(err))
        except EOFError as err:
            print("    " + str(err))
        except:
            print(root.tree_string())
            raise
        for n in root:
            for issue in n.metadata.get("validation", []):
                print("    " + str(issue))
        #input("...")

if __name__ == "__main__":
    main()
