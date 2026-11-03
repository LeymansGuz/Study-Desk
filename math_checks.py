"""Bounded symbolic verification, isolated from the web worker.

Checks verify mathematical claims, not whether an unstated premise was intended.
The evidence reviewer still checks how each claim relates to the public question.
"""
from __future__ import annotations
import ast
import json
import subprocess
import sys
from pathlib import Path

def safe_expression(text, names):
    import sympy as s
    tree = ast.parse(text.replace('^', '**'), mode='eval')
    if len(text) > 600 or len(list(ast.walk(tree))) > 100:
        raise ValueError('Expression is too complex.')
    functions = {'sin': s.sin, 'cos': s.cos, 'tan': s.tan, 'exp': s.exp, 'log': s.log, 'sqrt': s.sqrt, 'abs': s.Abs}

    def visit(node):
        if isinstance(node, ast.List):
            if not 1 <= len(node.elts) <= 6 or any((not isinstance(row, ast.List) or not 1 <= len(row.elts) <= 6 for row in node.elts)):
                raise ValueError('Matrices must be at most 6 by 6.')
            rows = [[visit(cell) for cell in row.elts] for row in node.elts]
            if len({len(row) for row in rows}) != 1:
                raise ValueError('Matrix rows have different lengths.')
            return s.Matrix(rows)
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            if abs(node.value) > 100000000.0:
                raise ValueError('Constant too large.')
            return s.Rational(str(node.value))
        if isinstance(node, ast.Name) and node.id in names:
            return names[node.id]
        if isinstance(node, ast.Name) and node.id in {'pi', 'E'}:
            return {'pi': s.pi, 'E': s.E}[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            a, b = (visit(node.left), visit(node.right))
            if isinstance(node.op, ast.Pow):
                if b.is_number and abs(float(b)) > 20:
                    raise ValueError('Exponent too large.')
                return a ** b
            if isinstance(node.op, ast.Div):
                return a / b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Sub):
                return a - b
            return a + b
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and (node.func.id in functions) and (len(node.args) == 1) and (not node.keywords):
            return functions[node.func.id](visit(node.args[0]))
        raise ValueError('Unsupported mathematical syntax.')
    return visit(tree.body)

def check_claim(claim):
    import sympy as s
    import math
    variables = claim.get('variables', ['x'])
    if len(variables) > 3 or any((not name.isalpha() or len(name) > 8 for name in variables)):
        raise ValueError('Invalid variables.')
    names = {name: s.Symbol(name, real=True) for name in variables}
    assumptions=claim.get('assumptions',[])
    if len(assumptions)>6:
        raise ValueError('Too many assumptions.')
    constraints=[]
    for condition in assumptions:
        if not isinstance(condition,str) or len(condition)>600:
            raise ValueError('Invalid assumption.')
        node=ast.parse(condition,mode='eval').body
        if not isinstance(node,ast.Compare) or len(node.ops)!=1:
            raise ValueError('Assumptions must be simple comparisons.')
        lhs=safe_expression(ast.unparse(node.left),names)
        rhs=safe_expression(ast.unparse(node.comparators[0]),names)
        relation={ast.Eq:s.Eq,ast.NotEq:s.Ne,ast.Lt:s.Lt,ast.LtE:s.Le,ast.Gt:s.Gt,ast.GtE:s.Ge}.get(type(node.ops[0]))
        if relation is None:raise ValueError('Unsupported assumption.')
        constraints.append(relation(lhs,rhs))

    def domain_signature(text):
        constraints = []
        for node in ast.walk(ast.parse(text.replace('^', '**'), mode='eval')):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                constraints.append(('nonzero', str(s.factor(safe_expression(ast.unparse(node.right), names)))))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and (node.func.id in {'sqrt', 'log', 'tan'}):
                constraints.append((node.func.id, str(safe_expression(ast.unparse(node.args[0]), names))))
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                exponent = safe_expression(ast.unparse(node.right), names)
                if exponent.is_number and (exponent < 0 or not exponent.is_integer):
                    constraints.append(('power-domain', str(safe_expression(ast.unparse(node.left), names))))
        return sorted(set(constraints))
    left = safe_expression(claim['left'], names)
    right = safe_expression(claim['right'], names)
    kind = claim.get('kind', 'equivalence')
    if constraints and kind!='equivalence':
        # Do not certify roots/integrals/matrices under an unproved restriction.
        return {'status':'unresolved','kind':kind,'domain_review_required':True,'reason':'Conditional check requires independent premise/domain review.'}
    if kind == 'definite_integral':
        bounds = claim.get('bounds', [])
        if not 1 <= len(bounds) <= 3:
            raise ValueError('A definite integral needs one to three ordered bounds.')
        seen = set()
        for bound in bounds:
            if len(bound) != 3 or bound[0] not in names or bound[0] in seen:
                raise ValueError('Invalid integration bound.')
            variable, lower, upper = bound
            seen.add(variable)
            low, high = (safe_expression(lower, names), safe_expression(upper, names))
            if names[variable] in low.free_symbols | high.free_symbols:
                raise ValueError('Integration bounds cannot depend on their own variable.')
            left = s.integrate(left, (names[variable], low, high))
        if left.has(s.Integral) or left.free_symbols or right.free_symbols:
            return {'status': 'unresolved', 'kind': kind, 'reason': 'Integral requires explicit independent review.'}
        difference = s.simplify(left - right)
        if difference == 0:
            return {'status': 'passed', 'kind': kind}
        if difference.is_number and difference.is_finite and (abs(float(difference)) > 1e-08):
            return {'status': 'failed', 'kind': kind, 'reason': 'The integral of the supplied integrand and bounds disagrees with the proposed answer.'}
        return {'status': 'unresolved', 'kind': kind}
    if kind == 'matrix':
        if not isinstance(left, s.MatrixBase) or not isinstance(right, s.MatrixBase) or left.shape != right.shape:
            return {'status': 'failed', 'kind': kind, 'reason': 'Matrix dimensions do not match.'}
        difference = (left - right).applyfunc(s.simplify)
        if all((entry == 0 for entry in difference)):
            return {'status': 'passed', 'kind': kind, 'domain_review_required': domain_signature(claim['left']) != domain_signature(claim['right'])}
        for sample in claim.get('samples', [-2, -1, 0, 0.5, 1, 2])[:16]:
            substitutions = {symbol: sample for symbol in names.values()}
            evaluated = difference.subs(substitutions)
            if any((entry.is_number and entry.is_finite and (abs(float(entry)) > 1e-08) for entry in evaluated)):
                return {'status': 'failed', 'kind': kind, 'counterexample': sample}
        return {'status': 'unresolved', 'kind': kind}
    if kind == 'derivative':
        left = s.diff(left, names[variables[0]])
    elif kind == 'integral':
        right = s.diff(right, names[variables[0]])
    elif kind == 'root':
        if len(variables) != 1:
            raise ValueError('Root checks need one variable.')
        left = left.subs(names[variables[0]], right)
        right = s.Integer(0)
    elif kind != 'equivalence':
        raise ValueError('Unknown mathematical check.')
    difference = s.simplify(left - right)
    samples = claim.get('samples', [-2, -1, 0, 0.5, 1, 2])[:16]
    tested = 0
    for value in samples:
        bindings = {symbol: float(value) + index * 0.137 for index, symbol in enumerate(names.values())}
        if constraints and not all(condition.subs(bindings)==s.true for condition in constraints):
            continue
        a, b = (left.subs(bindings), right.subs(bindings))
        if a.has(s.zoo, s.nan, s.oo, -s.oo) or b.has(s.zoo, s.nan, s.oo, -s.oo):
            continue
        try:
            av, bv = (float(a), float(b))
        except (TypeError, ValueError):
            continue
        tested += 1
        if not math.isclose(av, bv, rel_tol=1e-07, abs_tol=1e-08):
            return {'status': 'failed', 'counterexample': float(value), 'kind': kind}
    if difference == 0:
        if constraints:
            return {'status':'passed','kind':kind,'substitutions':tested,'domain_review_required':True}
        domain_warning = domain_signature(claim['left']) != domain_signature(claim['right'])
        return {'status': 'passed', 'kind': kind, 'substitutions': tested, 'domain_review_required': domain_warning}
    return {'status': 'unresolved', 'kind': kind, 'substitutions': tested}
from collections import OrderedDict
import threading
_PASSED_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()

def verify_claims(parts):
    from pipeline_runtime import LOCAL_CHECKS
    local = LOCAL_CHECKS.get()
    if local is None:
        return _verify_claims(parts)
    key = json.dumps([c.model_dump() for p in parts for c in getattr(p, 'checks', [])][:12], sort_keys=True, separators=(',', ':'))
    with _CACHE_LOCK:
        if key in local:
            return json.loads(local[key])
    result = _verify_claims(parts)
    with _CACHE_LOCK:
        if len(local) < 32:
            local[key] = json.dumps(result)
    return result

def _verify_claims(parts):
    claims = [claim.model_dump() for part in parts for claim in getattr(part, 'checks', [])]
    if not claims:
        return []
    key = json.dumps(claims[:12], sort_keys=True, separators=(',', ':'))
    with _CACHE_LOCK:
        if key in _PASSED_CACHE:
            _PASSED_CACHE.move_to_end(key)
            return json.loads(_PASSED_CACHE[key])
    try:
        command=[sys.executable,'--math-worker'] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve()),'--worker']
        completed = subprocess.run(command, input=json.dumps(claims[:12]), text=True, capture_output=True, timeout=6, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if completed.returncode:
            return [{'status': 'unresolved', 'reason': 'Symbolic check could not finish.'}]
        result = json.loads(completed.stdout)
        if result and all((row.get('status') == 'passed' for row in result)):
            with _CACHE_LOCK:
                _PASSED_CACHE[key] = json.dumps(result)
                while len(_PASSED_CACHE) > 128:
                    _PASSED_CACHE.popitem(last=False)
        return result
    except (subprocess.TimeoutExpired, ValueError):
        return [{'status': 'unresolved', 'reason': 'Symbolic check reached its time limit.'}]
if __name__ == '__main__':
    results = []
    for claim in json.load(sys.stdin):
        try:
            results.append(check_claim(claim))
        except Exception:
            results.append({'status': 'unresolved', 'reason': 'Unsupported or invalid expression.'})
    print(json.dumps(results))
