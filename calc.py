"""Small deterministic calculator used to audit generated quantitative answers.

Only pure functions from this module are exposed. The evaluator deliberately
accepts a tiny expression language: numbers, parentheses, arithmetic operators,
and the functions below. It never imports, evaluates names, or runs user code.
"""
from __future__ import annotations
import ast
import math
import re
from typing import Callable

def add(x: float, y: float) -> float:
    return x + y

def subtract(x: float, y: float) -> float:
    return x - y

def multiply(x: float, y: float) -> float:
    return x * y

def divide(x: float, y: float) -> float:
    if y == 0:
        raise ZeroDivisionError('division by zero')
    return x / y

def power(x: float, y: float) -> float:
    return x ** y

def sqrt(x: float) -> float:
    return math.sqrt(x)

def exp(x: float) -> float:
    return math.exp(x)

def log(x: float) -> float:
    return math.log(x)

def absolute(x: float) -> float:
    return abs(x)

def sin(x: float) -> float:
    return math.sin(x)

def cos(x: float) -> float:
    return math.cos(x)

def tan(x: float) -> float:
    return math.tan(x)

def asin(x: float) -> float:
    return math.asin(x)

def acos(x: float) -> float:
    return math.acos(x)

def atan(x: float) -> float:
    return math.atan(x)

def floor(x: float) -> float:
    return math.floor(x)

def ceil(x: float) -> float:
    return math.ceil(x)
def _counting_integer(value, maximum):
    if not math.isfinite(value) or value != int(value) or not 0 <= value <= maximum:
        raise ValueError('Counting operands must be bounded nonnegative integers.')
    return int(value)


def factorial(n):
    return math.factorial(_counting_integer(n,170))


def comb(n,k):
    return math.comb(_counting_integer(n,1000),_counting_integer(k,1000))


def perm(n,k):
    return math.perm(_counting_integer(n,170),_counting_integer(k,170))

FUNCTIONS: dict[str, Callable[..., float]] = {'factorial':factorial,'comb':comb,'perm':perm,'add': add, 'subtract': subtract, 'multiply': multiply, 'divide': divide, 'power': power, 'sqrt': sqrt, 'exp': exp, 'log': log, 'abs': absolute, 'atan': math.atan, 'sin': math.sin, 'cos': math.cos, 'tan': math.tan, 'asin': math.asin, 'acos': math.acos, 'floor': math.floor, 'ceil': math.ceil}
CONSTANTS = {'pi': math.pi, 'e': math.e}
_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.USub, ast.UAdd, ast.Name, ast.Load, ast.Call)

def evaluate(expression: str) -> float | None:
    """Evaluate a calculator expression, returning None if it is unsafe/invalid."""
    cleaned = expression.strip().replace('^', '**').replace('$', '').replace('−', '-')
    cleaned = re.sub('(?<=\\d),(?=\\d{3}(?:\\D|$))', '', cleaned)
    if not cleaned or len(cleaned) > 2000:
        return None
    try:
        tree = ast.parse(cleaned, mode='eval')
    except SyntaxError:
        return None
    if sum((1 for _ in ast.walk(tree))) > 256:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return None
        if isinstance(node, ast.Name) and node.id not in FUNCTIONS and (node.id not in CONSTANTS):
            return None
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
                return None
            if node.keywords:
                return None
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                return None
            try:
                node.value = float(node.value)
            except (OverflowError, ValueError):
                return None
    try:
        value = eval(compile(tree, '<calculator>', 'eval'), {'__builtins__': {}}, {**FUNCTIONS, **CONSTANTS})
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None

def _evaluate_with_variable(expression: str, variable: str, value: float) -> float | None:
    """Evaluate an equation expression for one named variable."""
    cleaned = expression.strip().replace('^', '**').replace('−', '-').replace('$', '')
    if len(cleaned) > 2000:
        return None
    try:
        tree = ast.parse(cleaned, mode='eval')
    except SyntaxError:
        return None
    if sum((1 for _ in ast.walk(tree))) > 256:
        return None

    class Substitute(ast.NodeTransformer):

        def visit_Name(self, node):
            return ast.copy_location(ast.Constant(float(value)), node) if node.id == variable else node
    try:
        return evaluate(ast.unparse(Substitute().visit(tree)))
    except (ValueError, TypeError, OverflowError):
        return None

def solve_equation(expression: str, variable: str='x', low: float=0.0001, high: float=1.0) -> float | None:
    """Find a root by bisection when the caller supplies a bracketing interval."""
    if low >= high:
        return None
    f_low = _evaluate_with_variable(expression, variable, low)
    f_high = _evaluate_with_variable(expression, variable, high)
    if f_low is None or f_high is None:
        return None
    if abs(f_low) < 1e-09:
        return low
    if abs(f_high) < 1e-09:
        return high
    if f_low * f_high > 0:
        return None
    for _ in range(120):
        mid = (low + high) / 2
        f_mid = _evaluate_with_variable(expression, variable, mid)
        if f_mid is None:
            return None
        if abs(f_mid) < 1e-10:
            return mid
        if f_low * f_mid <= 0:
            high = mid
        else:
            low = mid
            f_low = f_mid
    result = (low + high) / 2
    residual = _evaluate_with_variable(expression, variable, result)
    return result if residual is not None and abs(residual) <= 1e-07 else None
