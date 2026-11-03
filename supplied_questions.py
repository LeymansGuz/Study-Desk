"""Conservative local classification; the independent solver handles other cases."""
import re

def classify(text):
    matches = list(re.finditer('(?m)(?:^|[ \\t]+)([A-D])[.)]\\s+', text))
    if len(matches) == 4 and [m[1] for m in matches] == list('ABCD'):
        options = [text[m.end():matches[i + 1].start() if i < 3 else len(text)].strip() for i, m in enumerate(matches)]
        if all(options):
            return ('mcq', text[:matches[0].start()].strip(), options)
    from answer_parts import part_labels
    if re.search('(?:^|[.!?:;]\\s*)(?:write\\s+(?:an?\\s+)?(?:essay|extended response)|critically (?:evaluate|discuss))\\b', text, re.I):
        return ('essay', text, [])
    if len(part_labels(text)) > 1:
        return ('long_answer', text, [])
    if re.search('(?:^|[.!?:;]\\s*|\\([a-hivx]+\\)\\s*)(?:prove|show that|derive)\\b', text, re.I):
        return ('proof', text, [])
    if re.search('\\b(true or false|true/false)\\b', text, re.I):
        return ('true_false', text, ['True', 'False'])
    return (None, text, [])
