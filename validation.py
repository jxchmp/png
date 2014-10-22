#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import operator
import re
from collections import namedtuple

DEBUG = False 

##############################################################################
# Operator data                                                              #
##############################################################################

Op = namedtuple("Op", ["function", "symbol", "name", "reversed", "pass_node"])

class OpInfo(object):
    operators = [
        Op(operator.lt, "<", "be less than", False, False),
        Op(operator.le, "<=", "be less than or equal to", False, False),
        Op(operator.eq, "==", "be equal to", False, False),
        Op(operator.ne, "!=", "be unequal to", False, False),
        Op(operator.ge, ">=", "be greater than or equal to", False, False),
        Op(operator.gt, ">", "be greater than", False, False),
        Op(operator.contains, "in", "be in", True, False),
        Op(lambda a,b: a not in b, "not in", "not be in", False, False),
        Op(re.match, "matches", "match",  True, False)
    ]
    op_func_dict = {op.function: op for op in operators}
    op_symbol_dict = {op.symbol: op for op in operators}

##############################################################################
# Validation Class                                                           #
##############################################################################

class Validation(object):
    known_stages = ["pre", "per_child", "pre_derivation", "post"]
    def __init__(self, value, func, comparison, stage="post",
                 error=None, description=""):
        self.value = value
        if callable(func):
            self.func = func
        else:
            self.func = OpInfo.op_symbol_dict[func].function
        self.comparison = comparison
        if stage not in self.known_stages:
            raise ValueError("Unknown stage '{}'".format(stage))
        self.stage = stage
        self.error = error if error else ValidationWarning
        self.description = description if description else ""
        self.is_validation = True

    def __str__(self):
        return ("{cls}({value}, {func}, {comparison}, stage={stage}, " +
                "error={error})").format(
            cls = self.__class__.__name__,
            value=self.value,
            func = self.func,
            comparison=self.comparison,
            stage=self.stage,
            error=self.error
         )

    def resolve(self, path_or_val, node):
        if isinstance(path_or_val, (tuple, list)):
            if len(path_or_val) == 0:
                return path_or_val
            return tuple([self.resolve(el, node) for el in path_or_val])
        if hasattr(path_or_val, "resolve_path"):
            return path_or_val.resolve_path(node)
        elif isinstance(path_or_val, str):
            if hasattr(node, path_or_val):
                return getattr(node, path_or_val)
        return path_or_val

    def validate(self, node):
        value = self.resolve(self.value, node)
        comparison = self.resolve(self.comparison, node)
        if self.func in OpInfo.op_func_dict:
            if OpInfo.op_func_dict[self.func].reversed:
                arg1 = comparison
                arg2 = value
            else:
                arg1 = value
                arg2 = comparison
            try:
                if OpInfo.op_func_dict[self.func].pass_node:
                    res = self.func(arg1, arg2, node)
                else:
                    res = self.func(arg1, arg2)
            except TypeError as err:
                raise TypeError(
                    "Error applying '{}' to '{}' and '{}': {}".format(
                    OpInfo.op_func_dict[self.func].symbol,
                    arg1, arg2, err.args[0]))
        else:
            res = self.func(value, comparison)
        return (value, comparison, res) 

    def error_message(self, node, value, comparison):
        opinfo = OpInfo.op_func_dict.get(self.func)
        desc = (self.description + " ") if self.description else ""
        if opinfo:
            return ("{desc}(Validation failed while checking {val} on " +
                    "{node}; Expected value to {opdesc} {comparison} but " +
                    "found {value})").format(
                        desc = desc,
                        val = self.value,
                        node = node,
                        opdesc = opinfo.name,
                        comparison = comparison,
                        value = str(value)
                    )
        else:
            return "Validation failed while checking {val} on {node}".format(
                val = self.value,
                node = node
            )
        
    def __call__(self, definition, node, descendent=None):
        value, comparison, result = self.validate(node)
        if DEBUG:
            print("validation called", value, comparison, result)
        if not result:
            raise self.error(
                self.error_message(node, value, comparison)
            )

    def _validate_and_or(self, other):
        if not isinstance(other, Validation):
            raise TypeError(
                "unsupported operand type(s) for &: '{}' and '{}'".format(
                    type(self).__name__, type(other).__name__
                )
            )

    def __and__(self, other):
        self._validate_and_or(other)
        return AndValidation(self, other)

    def __or__(self, other):
        self._validate_and_or(other)
        return OrValidation(self, other)

    


class CompoundValidation(Validation):
    def __init__(self, v1, v2):
        # order v1 and v1 by error level, so that the highest error level
        # gets evaluated first
        if v1.error.level >= v2.error.level:
            self.v1 = v1
            self.v2 = v2
        else:
            self.v1 = v2
            self.v2 = v1
        # set our error to that of the validation with the highest error level
        self.error = v1.error
        # set our stage to the latest stage of the child validations
        self.stage = self.known_stages[max(
            self.known_stages.index(v1.stage),
            self.known_stages.index(v2.stage))]
        self.value = None
        self.comparison = None
        self.func = None


class AndValidation(CompoundValidation):
    def __call__(self, definition, node, descendent=None):
        if DEBUG:
            print("AndValidation called")
        self.v1(definition, node, descendent)
        self.v2(definition, node, descendent)

    def validate(self, node):
        return (None, None, v1.validate(node)[2] and v2.validate(node)[2])

class OrValidation(CompoundValidation):
    def __call__(self, definition, node, descendent):
        if DEBUG:
            print("OrValidation called")
        error = None
        for v in (self.v1, self.v2):
            try:
                v(definition, node, descendent)
            except ValidationException as err:
                if error:
                    raise error
                else:
                    error = err

    def validate(self, node):
        return (None, None, v1.validate(node)[2] or v2.validate(node)[2])
        
          

##############################################################################
# Validation Exceptions                                                      #
##############################################################################

class ValidationException(Exception):
    """
    Base class for Validation exceptions, which are raised by validation
    methods. Validation exceptions are classed by 'level', from Info to
    Fatal.
    """
    levels = ["Info", "Warning", "Error", "Fatal"]
    def __init__(self, text, recovery_func=None, recovery_args=None,
                 recovery_kwargs=None):
        self.text = text
        self.recovery_func = recovery_func
        self.recovery_args = recovery_args if recovery_args else []
        self.recovery_kwargs = recovery_kwargs if recovery_kwargs else {}
        if self.level != 3 and self.recovery_func:
            raise ValueError("recovery_func provided for validation" +
                "exception with a level other than 'Error'")


    def __str__(self):
        return "{}: {}".format(self.__class__.__name__, self.text)

class ValidationInfo(ValidationException):
    """
    Exception representing Info level validation issues. An Info level
    validation exception should be raised for situations that are correct
    and require no special handling, but are in some way unusual.
    """
    level = 0

class ValidationWarning(ValidationException):
    """
    Exception representing Warning level validation issues. A Warning level
    validation exception should be raised for situations that are not
    correct and indicate a possible problem, but which require no special
    handling.
    """
    level = 1

class ValidationError(ValidationException):
    """
    Exception representing Error level validation issues. An Error level
    validation exception should be raised for situations that are incorrect
    and will require some special handling if parsing is to continue.
    """
    level = 2

class ValidationFatal(ValidationException):
    level = 3


    
