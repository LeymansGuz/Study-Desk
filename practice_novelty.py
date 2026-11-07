"""Bounded practice history independent of corpus revisions and source filters."""
import re
from collections import Counter

HISTORY_LIMIT=2000


def question_key(text):
    """Number-only changes are the same practice task, not a new reasoning exercise."""
    return ' '.join(re.sub(r'[-+]?\d+(?:[.,]\d+)*','#',str(text).casefold()).split())


def task_text(question,options=None):
    """Choice order is presentation; option bodies are part of the public task."""
    if not options:return question
    bodies=sorted(re.sub(r'^[A-Ha-h][.)]\s*','',str(option)).strip() for option in options)
    return question+'\nChoices:\n'+'\n'.join(bodies)


def history(user_id):
    import db
    return db.recent_exposures(user_id,None,HISTORY_LIMIT) if user_id else []


def relevant_questions(rows,topic='',limit=24):
    words=set(re.findall(r'[a-z]{3,}',topic.casefold()))
    ranked=sorted(enumerate(rows),key=lambda pair:(-len(words & set(re.findall(r'[a-z]{3,}',pair[1]['question'].casefold()))),pair[0]))
    return [row['question'] for _,row in ranked[:limit]]


def coverage(rows):
    return Counter(row['skill_id'] for row in rows),Counter(row['chunk_ids'][0] for row in rows if row.get('chunk_ids'))


def closest_tasks(question,previous,limit=3):
    words=set(re.findall(r'[a-z]{3,}',question_key(question)))
    def overlap(text):
        other=set(re.findall(r'[a-z]{3,}',question_key(text)))
        return len(words & other)/max(1,len(words | other))
    unique=list(dict.fromkeys(previous))
    return [text[:1000] for text in sorted(unique,key=overlap,reverse=True)[:limit] if overlap(text)>.08]
