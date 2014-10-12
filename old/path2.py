#!/usr/bin/env python3

from io import StringIO, SEEK_END
import re

class LexError(Exception):
    pass

class PathLexer(object):
    tokendict = dict()
    start_token = None

    def __init__(self, s):
        if self.start_token is None:
            raise LexError("No start token defined.")
        self.inputbuffer = StringIO(s)
        self.tokenbuffer = StringIO()
        self.last_token = None
        self.last_token_type = None

    def buffer_char(self):
        char = self.inputbuffer.read(1)
        c = char if char else "\x00"
        self.tokenbuffer.seek(0, SEEK_END)
        self.tokenbuffer.write(c)
        self.tokenbuffer.seek(0)
        return bool(char)
            

    @classmethod
    def register(cls, tokenclass):
        if tokenclass == "Start":
            if cls.start_token is None:
                cls.start_token = tokenclass
            else:
                raise LexError("Multiple start tokens defined")
        for name in tokenclass.follows:
            cls.tokendict.setdefault(name, []).append(tokenclass)

    def emit(self, token):
        self.last_token = token.__class__.__name__
        return token

    def _lex(self):
        finished = False
        yield self.emit(self.start_token(""))
        while True:
            if not finished:
                if not self.buffer_char():
                    finished = True
            token = self.recognize()
            if token:
                yield self.emit(token)
            elif finished:
                break
        remainder = self.tokenbuffer.getvalue()
        if remainder:
            raise LexError(
                "Unprocessed input after lexing finished: {}".format(
                    remainder
                ))
   
    @classmethod
    def lex(cls, s):
        lexer = cls(s)
        for token in lexer._lex():
            yield token

    def recognize(self):
        value = self.tokenbuffer.getvalue()
        if value:
            candidates = (self.tokendict[self.last_token] + 
                          self.tokendict.get(self.last_token_type, []))
            if not candidates:
                raise LexError(
                    "No candidates following {}".format(self.last_token))
            for tokenclass in candidates:
                match = tokenclass.pattern.match(value)
                if match:
                    tokenvalue = self.tokenbuffer.read(match.end(1))
                    self.tokenbuffer = StringIO(self.tokenbuffer.read())
                    return tokenclass(tokenvalue)
        return None
                

class _Token(object):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return "{}: {!r}".format(self.__class__.__name__, self.value)
    

def Token(name, pattern, follows, token_type=None):
    cls = type(name, (_Token,), {
        "pattern": re.compile(pattern),
        "follows": follows,
        "token_type": token_type
    })
    PathLexer.register(cls)

class RewriteRule(object):
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def match(self, token_list):
        pass


functions = ["last", "position", "count", "id", "local-name", "name",
             "string", "concat", "starts-with", "contains", "substring-before",
             "substring-after", "substring", "string-length",
             "normalize-space", "translate", "boolean", "not", "true",
             "false", "number", "sum", "floor", "ceiling", "round"]

axes = ["ancestor", "ancestor-or-self", "attribute", "child", "descendent",
        "descendent-or-self", "following", "following-sibling",
        "parent", "preceding", "preceding-sibling", "self"]

nodetypes = ["comment", "text", "processing-instruction", "node"]

Token("Root",
      r"(/)(?=[a-zA-Z@\*\.])",
      ["Start"],
      "AbsoluteIdentifier")
Token("DescendentsOfRoot",
      r"(//)",
      ["Start"]
      "AbsoluteIdentifier")

for axis in axes:
    Token("{}Axis".format(axis.capitalize()),
          "({})(?=::)".format(axis),
          ["Start", "AbsoluteIdentifier"],
          "AxisSpecifier")

Token("AbbreviatedAttributeSpecifier",
      r"(@)",
      ["Start", "AbsoluteIdentifier"],
      "AxisSpecifier")

Token("AllTest",
      r"(\*)",
      ["Start", "AxisSpecifier", "AbsoluteIdentifier"],
      "NameTest")

Token("Name",
      r"([_a-zA-Z][_a-zA-Z0-9]+)(?:[/\[\]\x00\s=])",
      ["Start", "AxisSpecifier", "AbsoluteIdentifier"],
      "Name")

for nodetype in nodetypes:
    Token("{}NodeTest".format(nodetype.capitalize()),
          r"({})(?=\()".format(nodetype),
          ["Start", "AxisSpecifier", "AbsoluteIdentifier"],
          "NodeTypeTest")

Token("OpenParen", r"\(", ["NodeTypeTest"], "OpenParenToken")

Token("CloseParen", r"\)", ["OpenParen", "Literal"], "CloseParenToken")

Token("Literal",
      r"('[^']*')|(\"[^\"]*\")",
      ["ProcessingInstructionNodeTestStartToken"],
      "Literal")


Token("PredicateStart",
      r"(\[)",
      ["NameTest", "Name"]


Token("Start", r"", [])


Token("SelfStep", r"(\.)[^.]", ["Start"], "AbbreviatedStep")
Token("ParentStep", r"\.\.", ["Start"], "AbbrviatedStep")

Token("Step", r"(/)(?:[^/])",
      ["Start", "Self", "StartPredicate", "Identifier", "All"],
      "Operator")
Token("DescendentOrSelf",
      r"(//)",
      ["Start", "Identifier", "Self"],
      "Operator")
Token("UnionOperator", r"(\|)", [], "Operator")
Token("AdditionOperator", r"(\+)", [], "Operator")
Token("SubtractionOperator", r"(\-)", [], "Operator")
Token("EqualityOperator", r"(=)", [], "Operator")
Token("InequalityOperator", r"(!=)", [], "Operator")
Token("LessThanOperator", r"(<)(?=[^=])", [], "Operator")
Token("LessThanOrEqualOperator", r"(<=)", [], "Operator")
Token("GreaterThanOperator", r"(>)(?=[^=])", [], "Operator")
Token("GreaterThanOrEqualOperator", r"(>=)", [], "Operator")

Token("AndOperator", r"(and)", [], "OperatorName")
Token("OrOperator", r"(or)", [], "OperatorName")
Token("ModOperator", r"(mod)", [], "OperatorName")
Token("DivOperator", r"(div)", [], "OperatorName")

Token("MultiplyOperator", r"(\*)", [], "MultiplyOperator")

for function in functions:
    Token("{}Function".format(function.capitalize()),
          "({})".format(function) + r"(\s*?:\()",
          [],
          "FunctionName")




Token("NumberToken",
      r"(\d+(?:\.\d+)?|\.d+)(?:[\]])",
      ["StartPredicate"],
      "Number")

Token("StartPredicate",
      r"(\[)",
      ["Identifier", "All", "EndPredicate"],
      "ExprToken")
Token("EndPredicate",
      r"(\])",
      ["Identifier", "Number"],
      "ExprToken")
Token("End", r"(\x00)", ["Identifier", "EndPredicate", "All"])


def test():
    strings = [
        "./author",
        "author",
        "first_name",
        "/bookstore",
        "//author",
        "book[/bookstore/@specialty=@style]",
        "author/first_name",
        "bookstore//title",
        "bookstore/*/title",
        "bookstore//book/excerpt//emph",
        ".//title",
        "author/*",
        "book/*/last_name",
        "*/*",
        "*[@specialty]",
        "@style",
        "price/@exchange",
        "price/@exchange/total",
        "book[@style]",
        "book/@style",
        "@*",
        "./first_name",
        "first_name",
        "author[1]",
        "author[first_name][3]"

    ]
    for string in strings:
        print(string)
        for token in PathLexer.lex(string):
            print(token)
        print("-" * 80)


if __name__ == "__main__":
    test()
