"""Conservative checks of explicit numeric equalities in displayed working.

Unknown symbolic/LaTeX syntax is left to the mathematical verifier. Only fully
numeric expressions understood by the bounded calculator can produce a failure.
"""
import math
import re
from calc import evaluate

def has_draft_working(question,solution):
    """Reject abandoned computation transcripts, not legitimate error-analysis tasks."""
    if re.search(r'\b(?:find|identify|explain|correct|diagnose)\b.{0,55}\b(?:error|mistake|flaw|incorrect)\b|\bcritique\b',question,re.I):
        return False
    # A failed derivation followed by recalculation is a draft transcript, even
    # when it eventually lands on the right key. Independent verification that
    # agrees, and ordinary scientific model rejection, do not meet both tests.
    recalculation=re.search(r'\b(?:rechecking|recomputing|recalculating|correcting)\b',solution,re.I)
    abandoned=re.search(r'\b(?:does not match|discrepancy|the error is|is wrong|cannot both be|contradicts)\b',solution,re.I)
    if recalculation and abandoned:
        return True
    return bool(re.search(r'\b(?:a cleaner (?:route|approach)|this is not yet (?:the|a) clean|so this (?:expansion|calculation|solution) is wrong|recompute:|correct candidate is|let me (?:recalculate|recompute|correct)|oops\b|wait[,:;!])|\bactually\b[^.\n]{0,100}\?|\bthis does not (?:break|show|establish|prove)\b',solution,re.I))


def numeric_expression(text):
    text=text.strip().replace('−','-').replace('\\left','').replace('\\right','')
    text=text.replace('\\dfrac','\\frac').replace('\\tfrac','\\frac')
    text=text.replace('\\times','*').replace('\\cdot','*').replace('\\,','').replace('\\!','')
    for _ in range(4):
        text=re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}',r'((\1)/(\2))',text)
    text=re.sub(r'\\sqrt\{([^{}]+)\}',r'sqrt(\1)',text)
    text=re.sub(r'\^\{([^{}]+)\}',r'**(\1)',text).replace('^','**')
    text=text.replace('\\ln','log').replace('\\log','log').replace('\\pi','pi')
    text=text.replace('{','(').replace('}',')')
    text=re.sub(r'(?<=[0-9)])\s*(?=\()', '*',text)
    return text


def working_issues(working):
    issues=[]
    pattern=r'\$\$(.*?)\$\$|(?<![\\$])\$(?!\$)(.*?)(?<!\\)\$|\\\[(.*?)\\\]|\\\((.*?)\\\)'
    for match in re.finditer(pattern,working,re.S):
        context=working[max(0,match.start()-80):min(len(working),match.end()+80)]
        if re.search(r'\b(?:incorrect|wrong|false|claims?|mistake|contradiction)\b',context,re.I):
            continue
        expression=next(x for x in match.groups() if x is not None)
        pieces=re.split(r'\\approx|\\simeq|(?<![<>!])=(?!=)',expression)
        for left,right in zip(pieces,pieces[1:]):
            # In graph theory e is an edge count, not necessarily Euler's number.
            # Never guess a binding for it in prose working.
            if re.search(r'\be\b',left):continue
            right=right.strip().rstrip('.,;')
            if not re.fullmatch(r'-?\d+(?:\.\d+)?',right):continue
            value=evaluate(numeric_expression(left))
            if value is None:continue
            stated=float(right);digits=len(right.split('.')[1]) if '.' in right else 0
            tolerance=.50001*10**(-digits)+abs(value)*1e-9
            if not math.isclose(value,stated,rel_tol=0,abs_tol=tolerance):
                issues.append({'expression':left[:160],'stated':stated,'computed':value})
    return issues[:8]
