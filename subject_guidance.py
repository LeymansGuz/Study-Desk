"""Discipline-neutral requirements: evidence decides the subject and valid methods."""
GUIDANCE = "\nInfer the discipline and course level from the supplied evidence; never assume finance.\nUse the discipline's notation and assessment style. Do not force numerical work into\nconceptual subjects or invent clinical advice from incomplete notes.\nFor calculus check domains, boundary conditions, constants of integration and units.\nFor matrices check dimensions, multiplication order, rank/invertibility and requested\nentries; never treat a matrix as a scalar. Use LaTeX bmatrix/pmatrix notation.\nFor physics state idealizations, directions, signs, dimensions and required constants.\nFor biology separate mechanisms, observations and causal claims; respect organism/context.\nFor psychology distinguish theories from established findings, correlation from causation,\nand competing interpretations; avoid an ambiguous MCQ where several options fit.\nFor nursing use the source's population, clinical context and jurisdiction; include\ncontraindications, units and safety constraints when relevant. If the source does not\nsupport a safe unambiguous key, reject the candidate rather than invent a protocol.\nFor ICT state language/version, indexing conventions, inputs and execution assumptions\nwhere relevant; check algorithm edge cases and distinguish pseudocode from executable code.\nFor finance retain timing, compounding, cash-flow direction, payoff/profit distinction,\nno-arbitrage assumptions and independently computed arithmetic checks.\nFor every other subject apply the same evidence, scope, independent-solution and verifier\nrequirements. Difficulty comes from covered reasoning, not unseen prerequisites.\nUse Markdown for structured text and fenced code. Use $...$ or $$...$$ for LaTeX math;\nescape backslashes correctly in JSON. Put MC option content only in options, never in the\nquestion body or in a revealed explanation. An option's description is its public text,\nnot an explanation of why it is correct. Never reveal the key in descriptions.\n"

GROUNDING_BOUNDARY = (
    'Ground required domain methods and factual claims, not the invented public problem data. '
    'Evaluating numeric arithmetic, counting explicitly given event indices and interpreting '
    'supplied units are deductions from the public givens; do not invent a lecture citation '
    'or cite a heading to establish them. This does not authorize an unsupported theorem, '
    'pricing formula, mechanism or prerequisite. Course exclusions still take precedence.'
)
GUIDANCE += '\n'+GROUNDING_BOUNDARY+'\n'



def interpretation_issues(question,working):
    """Narrow, source-independent identities for established named frameworks."""
    import re
    if not re.search(r'\bCAPM\b|\bSML\b|security market line',question+' '+working,re.I):return []
    issues=[]
    for sentence in re.split(r'(?<=[.!?])\s+|\n',working):
        if re.search(r'\b(?:not|incorrect|wrong|false|mistaken)\b',sentence,re.I):continue
        below=re.search(r'\bbelow\b.{0,90}\b(?:SML|security market line|line)\b',sentence,re.I)
        above=re.search(r'\babove\b.{0,90}\b(?:SML|security market line|line)\b',sentence,re.I)
        if below and re.search(r'\bunderpriced\b',sentence,re.I):
            issues.append('In CAPM/SML, an expected return below the required return indicates overpriced, holding expected cash flows and risk fixed; it does not indicate underpriced.')
        if above and re.search(r'\boverpriced\b',sentence,re.I):
            issues.append('In CAPM/SML, an expected return above the required return indicates underpriced, holding expected cash flows and risk fixed; it does not indicate overpriced.')
    return issues
