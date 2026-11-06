"""Bounded publication-text repair; cannot mutate the public problem or key."""
from typing import ClassVar
import json
from pydantic import BaseModel,Field
from security import wrap_untrusted

class WorkingRepair(BaseModel):
    SYSTEM_PROMPT:ClassVar[str]='Return a clean final worked solution, not a deliberation transcript. Fix the stated display defects without changing any public given, requested outcome, answer, proof hypothesis or calculator plan. Preserve every necessary proof case and domain. Use exact expressions until the final rounding; write \\approx for rounded decimals, never an exact equality to a differently rounded product. Do not recompute a final value from a rounded intermediate: retain its exact expression instead. Remove abandoned exploratory calculations, not necessary reasoning. If the unchanged key/plans cannot support a correct complete solution, set repair_possible=false; never conceal a substantive contradiction.'
    worked_solution:str=Field(default='',max_length=10000)
    repair_possible:bool

async def repair(draft,issues):
    import tools
    from answer_parts import calculator_evidence
    prompt=wrap_untrusted('public_question',draft.question,max_chars=16000)+'\nOptions: '+json.dumps(draft.options)+'\n'+wrap_untrusted('unchanged_answer_key',draft.canonical_answer,max_chars=5000)+'\n'+wrap_untrusted('evaluated_calculator_evidence',calculator_evidence(draft.answer_parts),max_chars=5000)+'\n'+wrap_untrusted('working_to_clean',draft.solution,max_chars=10000)+'\nDisplay defects: '+json.dumps(issues)
    result=await tools._invoke_json(prompt,0,WorkingRepair)
    return result.worked_solution.strip() if result.repair_possible and len(result.worked_solution.strip())>=20 else None
