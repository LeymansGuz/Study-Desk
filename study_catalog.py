"""Shared public choices for study forms, request schemas and course imports."""
from typing import Literal, get_args

DocumentType = Literal['syllabus','notes','past_paper','exercise','marking_scheme','exam_report']
DOCUMENT_TYPES = {
    'syllabus':'Syllabus / learning outcomes',
    'notes':'Notes',
    'past_paper':'Past paper',
    'exercise':'Exercise / assignment',
    'marking_scheme':'Marking scheme',
    'exam_report':'Exam report',
}
DOC_TYPES = frozenset(get_args(DocumentType))
Difficulty = Literal['easy','medium','hard','insane']
QuestionType = Literal['mcq','short_answer','long_answer','essay','calculation','proof','true_false']
QUESTION_LABELS = {'mcq':'Multiple choice','short_answer':'Short answer','long_answer':'Long answer',
                   'essay':'Essay','calculation':'Calculation','proof':'Proof / derivation','true_false':'True / false'}


def public():
    return {'document_types':DOCUMENT_TYPES,'question_types':QUESTION_LABELS,
            'difficulties':{level:level.title() for level in get_args(Difficulty)}}


QUESTION_SOURCE_TYPES = frozenset({'notes','past_paper','exercise'})
PRIMARY_SOURCE_REASON = ('Choose notes, exercises or past papers as primary question sources. '
                        'Syllabuses define scope; marking schemes and exam reports provide assessment support.')
