"""Public assessment criteria and safe per-criterion feedback for extended answers."""
import re
from pydantic import BaseModel, Field
from typing import Literal

class CriterionResult(BaseModel):
    id: str = Field(max_length=30)
    verdict: Literal['correct', 'partial', 'incorrect', 'not_answered']
    feedback: str = Field(default='', max_length=500)

def criteria(question, kind):
    if kind not in {'long_answer', 'essay', 'proof'}:
        return []
    if kind == 'proof':
        return [{'id': 'logic', 'title': 'Logical argument', 'expectation': 'Establish the requested conclusion with valid steps; numerical examples alone are insufficient.'}, {'id': 'justification', 'title': 'Justification', 'expectation': 'Justify the methods and deductions required by the question; an equivalent valid proof is accepted.'}, {'id': 'coverage', 'title': 'Required coverage', 'expectation': 'Address all requested parts, assumptions and any stated domains, boundary or equality cases.'}]
    result = [{'id': 'knowledge', 'title': 'Accuracy', 'expectation': 'Use correct, relevant course knowledge and terminology.'}, {'id': 'reasoning', 'title': 'Reasoning', 'expectation': 'Show the requested methods and deductions for each part; equivalent valid methods are accepted.' if kind == 'long_answer' else 'Develop a coherent explanation or argument in connected paragraphs; supported alternative arguments are accepted.'}, {'id': 'coverage', 'title': 'Required coverage', 'expectation': 'Address every requested aspect clearly; writing style is not graded unless explicitly requested.'}]
    if re.search('evidence|data|results|experiment|source|scenario|measure', question, re.I):
        result.append({'id': 'evidence', 'title': 'Use of evidence', 'expectation': 'Use the information supplied in the question accurately to support your argument.'})
    if re.search('limitation|evaluat|critique|alternative|compare|case|assumption', question, re.I):
        result.append({'id': 'evaluation', 'title': 'Evaluation', 'expectation': 'Address the requested comparison, assumptions, alternatives or limitations without overclaiming.'})
    return result

def summary(results):
    names = {'correct': 'Correct', 'partial': 'Partly correct', 'incorrect': 'Needs correction', 'not_answered': 'Not addressed'}
    return '\n'.join((f"- **{row.id.replace('_', ' ').capitalize()}: {names[row.verdict]}.**" + (' ' + row.feedback if row.feedback else '') for row in results))
