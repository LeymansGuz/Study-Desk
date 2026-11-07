"""Public verification receipts never contain a key, index or private review."""
import math

FLAGS = frozenset({'solver_passed','source_passed','verifier_passed',
                   'math_format_passed','originality_passed','opa_passed'})


def public_fields(value):
    if not isinstance(value,dict):
        return {}
    result={key:value[key] for key in FLAGS if type(value.get(key)) is bool}
    latency=value.get('latency')
    if type(latency) in {int,float} and math.isfinite(latency) and latency>=0:
        result['latency']=latency
    attempts=value.get('candidate_attempts')
    if type(attempts) is int and 1<=attempts<=10:
        result['candidate_attempts']=attempts
    kind=value.get('solver_kind')
    if isinstance(kind,str) and kind in {'checked_construction','independent_solver'}:
        result['solver_kind']=kind
    return result
