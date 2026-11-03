"""Visible expectations derived exclusively from the public question."""
import re
from answer_parts import part_labels

def rubric(question, question_type='short_answer'):
    labels = part_labels(question) or ['answer']
    segments = re.split('(?<!\\w)\\((?:[a-h]|[ivx]{1,4})\\)|\\n\\s*[a-h][.)]', question, flags=re.I)
    shared_working = bool(re.search('(?:show.*(?:work|steps)|justify.*conclusions).*(?:each part|all parts)', segments[0], re.I))
    segments = segments[1:] if len(segments) > 1 else segments
    result = []
    for index, label in enumerate(labels):
        text = segments[index] if index < len(segments) else question
        if question_type in {'mcq', 'true_false'}:
            mode, expectation = ('choice', 'Choose one answer.')
        elif re.search('\\b(prove|proof|show that|justify)\\b', text, re.I):
            mode, expectation = ('justification', 'Give a justified argument addressing the statement.')
        elif re.search('\\b(show (?:your |all )?work|working|derive|derivation|steps)\\b', text, re.I):
            mode, expectation = ('working', 'Show the method and working, with the final result.')
        elif shared_working:
            mode, expectation = ('working', 'Show working and justify your conclusion for this part.')
        elif re.search('\\b(explain|interpret|discuss|describe|why|compare)\\b', text, re.I):
            mode, expectation = ('explanation', 'Explain the requested idea or interpretation.')
        else:
            mode, expectation = ('answer', 'Give the requested answer; include units where relevant. Working is optional.')
        result.append({'label': label, 'mode': mode, 'expectation': expectation})
    return result
