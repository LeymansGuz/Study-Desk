"""Bounded repair of calculator strings, never a redraft of a public question."""
import ast
import math
import re
from pydantic import BaseModel, Field
import tools
from calc import evaluate, solve_equation
INSTRUCTION = 'Fix ONLY the syntax to pure Python (e.g., change 2x to 2*x). Do not change the mathematical meaning.'

class SyntaxFix(BaseModel):
    expression: str = Field(min_length=1, max_length=2000)

class SyntaxSolverAnswer(tools.SolverAnswer):
    syntax_preserved: bool = False

def repairable(text):
    if not text or len(text) > 2000 or (not re.fullmatch('[0-9A-Za-z+\\-*/^().,{}\\[\\]\\\\\\s%=×÷−π√]+', text)) or ('__' in text):
        return False
    try:
        tree = ast.parse(text, mode='eval')
    except SyntaxError:
        return True
    return any((isinstance(node, ast.Call) and isinstance(node.func, (ast.Constant, ast.BinOp)) or (isinstance(node, ast.Name) and node.id == 'π') for node in ast.walk(tree)))

def calculate(item):
    return solve_equation(item.equation, item.variable, item.low, item.high) if item.equation.strip() else evaluate(item.expression)

async def repair_parts(parts):
    copied = [part.model_copy(deep=True) for part in parts]
    repairs = 0
    for part in copied:
        items = ([part] if part.expression.strip() or part.equation.strip() else []) + part.calculations
        for item in items:
            value = calculate(item)
            if value is not None and math.isfinite(value):
                continue
            field = 'equation' if item.equation.strip() else 'expression'
            original = getattr(item, field)
            if not repairable(original) and '__' not in original:
                try:
                    tree = ast.parse(original, mode='eval')
                    from calc import FUNCTIONS, CONSTANTS
                    names = set(FUNCTIONS) | set(CONSTANTS) | ({item.variable} if field == 'equation' else set())
                    unknown = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id not in names}
                    safe = all((not isinstance(n, (ast.Attribute, ast.Subscript, ast.Lambda, ast.ListComp)) for n in ast.walk(tree)))
                    if safe and unknown:
                        raise tools.CandidateError('The numeric plan uses unsupported operations or unresolved variables.', feedback='The expression ' + original[:350] + ' uses ' + ', '.join(sorted(unknown)) + '. This is not a Python syntax failure. Design a fully supported, feasible question with an evaluable result; do not invent special functions or advanced prerequisites absent from the source.')
                except SyntaxError:
                    pass
            if repairs >= 2 or not repairable(original):
                raise tools.ArithmeticRepairError('A calculator expression is invalid and cannot be safely syntax-repaired.')
            repairs += 1
            fixed = await tools._invoke_json(INSTRUCTION + '\nReturn only the repaired expression field. No question, answer key, new givens or substituted values.\n' + __import__('json').dumps({'broken_string': original}), temperature=0, schema=SyntaxFix)
            try:
                tree = ast.parse(fixed.expression, mode='eval')
                if any((isinstance(n, ast.BitXor) for n in ast.walk(tree))):
                    raise ValueError('Use **, not ^.')
            except (SyntaxError, ValueError) as exc:
                raise tools.ArithmeticRepairError('The isolated syntax repair did not produce pure Python.') from exc
            setattr(item, field, fixed.expression)
            value = calculate(item)
            if value is None or not math.isfinite(value):
                raise tools.ArithmeticRepairError('The repaired expression failed the Python evaluator.')
            prompt = 'Independently solve the repaired Python expression and compare its mathematical meaning with the original notation. Return syntax_preserved=true ONLY if no number, sign, grouping, unit, exponent or mathematical meaning changed. If ambiguous or altered, return false. Use one numeric part labelled answer; do not repair your inputs. For an equation, solve it over the supplied bracket.\n' + __import__('json').dumps({'original': original, 'repaired': fixed.expression, 'field': field, 'variable': item.variable, 'low': item.low, 'high': item.high})
            solved = await tools._invoke_json(prompt, temperature=0, schema=SyntaxSolverAnswer)
            try:
                checked = tools.evaluate_parts(solved.parts)
            except ValueError as exc:
                raise tools.ArithmeticRepairError('The repair Solver returned invalid calculation evidence.') from exc
            numeric = [p.value for p in checked if p.value is not None]
            if not solved.syntax_preserved or solved.missing_givens or len(numeric) != 1 or (not math.isclose(numeric[0], value, rel_tol=1e-09, abs_tol=1e-10)):
                raise tools.ArithmeticRepairError('The independent Solver did not confirm syntax repair preserved the mathematics.')
    return copied
