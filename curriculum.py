"""Complete extractive course inventory, hybrid ranking, and persistent coverage.

The map indexes every chunk, not a sample. Its units are source sections (four
pages), not inferred learning objectives. Original passages remain authoritative;
the model must prove that its solution methods are supported by those passages.
"""
from __future__ import annotations
from study_catalog import QUESTION_SOURCE_TYPES, PRIMARY_SOURCE_REASON
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
import math
import random
import re
from typing import Any
import db
import retrieval
CONTENT_TYPES = ['syllabus', 'notes', 'exercise', 'past_paper', 'marking_scheme', 'exam_report']
STOP = set('the a an and or for of to in on is are be with this that by as at from it you your what which how copyright rights reserved university faculty department chapter lecture slide slides page pages example examples'.split())
STOP.update('we can both also then thus these those given using use let following hence such'.split())
NOT_ASSESSED = re.compile('\\(\\s*not\\s+required\\s*\\)|^\\s*not\\s+required\\s*$|(?:[-–—:]\\s*)not\\s+required\\s*$|\\bnot\\s+required\\s+for\\s+(?:the\\s+)?(?:exam|assessment|course)\\b|\\b(?:not\\s+examinable|not\\s+assessed|out\\s+of\\s+syllabus|for\\s+reference\\s+only|optional\\s+extension)\\b', re.I | re.M)

def canonical_term(term):
    irregular={'matrices':'matrix','vertices':'vertex','indices':'index','hypotheses':'hypothesis'}
    if term in {'series','species'}:return term
    if term in irregular:return irregular[term]
    if len(term)>4 and term.endswith('ies'):return term[:-3]+'y'
    if len(term)>=4 and term.endswith('s') and not term.endswith(('ss','us','is','ics','species')):return term[:-1]
    return term

@lru_cache(maxsize=2048)
def terms(text: str) -> frozenset[str]:
    text = re.sub('\\b(in|circum|ortho)[-\\s]+cent(?:er|re)s?\\b', lambda m: m[1] + 'centre', text, flags=re.I)
    text = re.sub('\\b(ortho|circum|in)?cent(?:er|re)s?\\b', lambda m: (m[1] or '') + 'centre', text, flags=re.I)
    return frozenset((canonical_term(term) for term in retrieval._tokens(text) if len(term) > 1 and term not in STOP))

def query_terms(topic):
    result = set(terms(topic))
    if re.search('\\b(?:four|4)\\s+cent(?:er|re)s?\\b|四心', topic, re.I):
        result.update({'centroid', 'orthocentre', 'incentre', 'circumcentre'})
    return frozenset(result)

def _legacy_scope_version(user_id: str, course_ids: list[str]) -> str:
    scopes = retrieval._course_scopes(user_id, course_ids)
    state = [(owner, sorted(courses or []), db.get_app_setting(f'index_collection:{owner}'), db.get_app_setting(f'corpus_revision:{owner}'), [(doc['id'], bool(doc.get('syllabus_enabled', 1))) for doc in db.list_documents(owner, courses)], [(cid, db.get_app_setting(f'concept_review:{owner}:{cid}')) for cid in courses or [c['id'] for c in db.list_courses(owner)]]) for owner, courses in scopes]
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()[:24]

def scope_version(user_id: str, course_ids: list[str]) -> str:
    import course_versions
    return course_versions.version(user_id,course_ids,_legacy_scope_version)

def scope_key(course_ids: list[str], version: str) -> str:
    return hashlib.sha256(json.dumps([sorted(course_ids), version]).encode()).hexdigest()[:24]

def section_id(source: dict[str, Any]) -> str:
    identity = [source.get('course_id'), source.get('source_file'), (int(source.get('page', 1)) - 1) // 4]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:20]

@lru_cache(maxsize=16)
def _load_map(user_id: str, courses: tuple[str, ...], version: str):
    rows = retrieval.inventory(user_id, list(courses))
    grouped = defaultdict(list)
    for source in rows:
        grouped[section_id(source)].append(source)
    sections = []
    for key, evidence in grouped.items():
        evidence.sort(key=lambda row: (row['page'], row.get('chunk_index', 0), row['chunk_id']))
        first = evidence[0]
        pages = sorted({row['page'] for row in evidence})
        vocabulary = Counter((term for row in evidence for term in terms(row['text'])))
        label = next((line.strip(' #•\t')[:100] for line in first['text'].splitlines() if 8 <= len(line.strip()) <= 140), first['source_title'])
        sections.append({'id': key, 'course_id': first['course_id'], 'source_file': first['source_file'], 'doc_type': first['doc_type'], 'title': label, 'pages': pages, 'keywords': [w for w, _ in vocabulary.most_common(12)], 'excluded': bool(NOT_ASSESSED.search(label) or any((NOT_ASSESSED.search(source['text'][:180]) for source in evidence if source.get('chunk_index', 0) == 0))), 'sources': evidence})
    stored = [{**{key: value for key, value in unit.items() if key != 'sources'}, 'chunk_ids': [source['chunk_id'] for source in unit['sources']]} for unit in sections]
    db.save_curriculum_map(user_id, list(courses), version, stored)
    return {'version': version, 'sections': sections, 'chunks': len(rows)}

def course_map(user_id: str, course_ids: list[str]):
    version = scope_version(user_id, course_ids)
    catalog = _load_map(user_id, tuple(sorted(course_ids)), version)
    flags = {(doc['course_id'], doc['filename']): bool(doc.get('syllabus_enabled', 1)) for owner, courses in retrieval._course_scopes(user_id, course_ids) for doc in db.list_documents(owner, courses)}
    catalog = {**catalog, 'sections': [{**unit, 'syllabus_enabled': flags.get((unit['course_id'], unit['source_file']), True)} for unit in catalog['sections']]}
    published = {(unit['course_id'], unit['source_file']) for unit in catalog['sections']}
    pending = []
    for owner, courses in retrieval._course_scopes(user_id, course_ids):
        pending.extend(({'filename': row['filename'], 'doc_type': row['doc_type'], 'course_id': row['course_id']} for row in db.list_documents(owner, courses) if (row['course_id'], row['filename']) not in published))
    return {**catalog, 'pending_documents': pending}

def scope_rules(user_id: str, course_ids: list[str]) -> str:
    rules = []
    for owner, courses in retrieval._course_scopes(user_id, course_ids):
        ids = courses or [course['id'] for course in db.list_courses(owner)]
        for course_id in ids:
            text = db.get_app_setting(f'course_scope:{owner}:{course_id}')
            if text:
                rules.append(text)
    return '\n'.join(rules)

def overview(catalog, rules='') -> str:
    """Describe every document. No summaries are treated as source evidence."""
    documents = defaultdict(list)
    for unit in catalog['sections']:
        documents[unit['course_id'], unit['source_file']].append(unit)
    lines = ['Owner-defined learning objectives/exclusions:\n' + rules] if rules else []
    syllabus = [source['text'] for unit in catalog['sections'] if unit['doc_type'] == 'syllabus' for source in unit['sources']]
    if syllabus:
        lines.append('Official syllabus text defines the allowed scope (content methods still require evidence):\n' + '\n'.join(syllabus))
    if catalog.get('pending_documents'):
        lines.append(str(len(catalog['pending_documents'])) + ' uploaded document(s) are not published yet. Coverage is incomplete; use only the supplied completed passages, never infer pending content or claim complete-course coverage.')
    lines.append('Complete indexed document inventory (navigation only, NOT proof of support):')
    for (_, name), units in sorted(documents.items()):
        keywords = Counter((word for unit in units for word in unit['keywords']))
        lines.append(f"- {name}: {len(units)} sections; terms: {', '.join((w for w, _ in keywords.most_common(10)))}")
    excluded = [unit['title'] for unit in catalog['sections'] if unit.get('excluded')]
    if excluded:
        lines.insert(0, 'Explicitly unassessed/excluded source sections (never test these): ' + '; '.join(excluded))
    return '\n'.join(lines)

def assessment_support(catalog, unit, query, allowed):
    """Bounded same-course companion evidence, without another embedding/LLM call."""
    target = set(query) | set(unit['keywords'][:10])
    best = {}
    for section in catalog['sections']:
        kind = section['doc_type']
        if section.get('excluded') or section['course_id'] != unit['course_id'] or section['source_file'] == unit['source_file'] or (kind not in allowed) or (kind not in {'notes', 'past_paper', 'marking_scheme', 'exam_report'}):
            continue
        for row in section['sources']:
            if row.get('quality_review_required'):
                continue
            overlap = len(target & terms(row['text']))
            if overlap >= 2 and (kind not in best or overlap > best[kind][0]):
                best[kind] = (overlap, row)
    return [row for _, row in sorted(best.values(), key=lambda item: item[0], reverse=True)[:3]]

def topical_evidence(catalog,unit,query,allowed,semantic):
    """Fuse topical lexical/vector ranks before spending context on neighbours.

    Adjacent exam questions often concern unrelated methods. Preserve the chosen
    coverage anchor, but retrieve substantive support across the whole course.
    """
    rows={}
    for section in catalog['sections']:
        if section.get('excluded') or section['course_id']!=unit['course_id'] or section['doc_type'] not in allowed:continue
        for row in section['sources']:
            if not row.get('quality_review_required'):rows[row['chunk_id']]=row
    target=set(query) or set(unit['keywords'][:8])
    tokens={key:terms(row['text']) for key,row in rows.items()}
    frequency=Counter(term for values in tokens.values() for term in values)
    lexical={key:sum(math.log(1+len(rows)/(1+frequency[t])) for t in target & values)/math.sqrt(20+len(values)) for key,values in tokens.items()}
    ranks={key:1/(10+i) for i,key in enumerate(sorted(lexical,key=lexical.get,reverse=True)) if lexical[key]>0}
    for i,row in enumerate(semantic):
        if row['chunk_id'] in rows:ranks[row['chunk_id']]=ranks.get(row['chunk_id'],0)+1.2/(10+i)
    return [rows[key] for key in sorted(ranks,key=ranks.get,reverse=True)[:7]]

def plan_context(user_id: str, course_ids: list[str], topic: str, *, whole=False, doc_types=None, count=1, exclude_skill_ids=None, figure_mode='none', target_skill_id=None):
    catalog = course_map(user_id, course_ids)
    if whole:
        catalog = {**catalog, 'sections': [unit for unit in catalog['sections'] if unit.get('syllabus_enabled', True)]}
        if not catalog['sections']:
            raise ValueError('No indexed documents are enabled for Any syllabus topic. Enable a document in Workspace or choose a specific topic.')
    if any((row['doc_type'] == 'syllabus' for row in catalog.get('pending_documents', []))):
        raise ValueError('The course syllabus is still being processed. Wait for its scope and exclusions before generating questions from this course.')
    import learning_store
    key = scope_key(course_ids, catalog['version'])
    allowed = set(doc_types or CONTENT_TYPES)
    import monitoring
    excluded = set(exclude_skill_ids or []) | monitoring.paused_skills(user_id, course_ids)
    sections = [unit for unit in catalog['sections'] if not unit.get('excluded') and unit['doc_type'] in allowed and (unit['id'] not in excluded)]
    sections = [{**unit, 'sources': [s for s in unit['sources'] if not s.get('quality_review_required')]} for unit in sections]
    sections = [unit for unit in sections if unit['sources']]
    sections=[unit for unit in sections if unit['doc_type'] in QUESTION_SOURCE_TYPES]
    if not sections:
        raise ValueError(PRIMARY_SOURCE_REASON)
    if target_skill_id:
        focused = [unit for unit in sections if unit['id'] == target_skill_id]
        if not focused:
            raise ValueError('The original learning objective is no longer available in the current course documents.')
        sections = focused
    if figure_mode == 'math':
        from math_figures import eligible
        sections = [unit for unit in sections if eligible(topic, unit['sources'])]
        if not sections:
            raise ValueError('No supported math figure sections match this selection. Choose supporting course documents or use Standard questions for topics without a checked figure renderer.')
    if not sections:
        if excluded:
            raise ValueError('The available source sections are temporarily cooling down after repeated validation failures. Try another covered section or return in 20 minutes; original files remain available.')
        raise ValueError('No indexed course sections match the selected source types. Upload/index material or adjust the selection.')
    from practice_novelty import history,coverage,relevant_questions
    recent=history(user_id)
    counts,chunk_counts=coverage(recent)
    recent_skills = {row['skill_id'] for row in [r for r in recent if r['skill_id']!='explained-example'][:8]}
    query = query_terms(topic)
    frequency = Counter((term for unit in sections for term in set().union(*(terms(s['text']) for s in unit['sources']))))
    semantic = [] if whole else retrieval.search(topic, user_id, 60, None, course_ids, list(allowed))
    semantic_scores = defaultdict(float)
    for rank, source in enumerate(semantic):
        for unit in sections:
            if any((s['chunk_id'] == source['chunk_id'] for s in unit['sources'])):
                # Overlapping chunks from one section are not independent votes.
                semantic_scores[unit['id']] = max(semantic_scores[unit['id']],1 / (60 + rank + 1))
    ranked = []
    for unit in sections:
        content = Counter((term for source in unit['sources'] for term in terms(source['text'])))
        score = sum((math.log(1 + len(sections) / (1 + frequency[t])) * content[t] / (content[t] + 1.2) for t in query if content[t]))
        ranked.append((score, unit))
    lexical_rank = {unit['id']: 1 / (61 + i) for i, (score, unit) in enumerate(sorted(ranked, key=lambda pair: pair[0], reverse=True)) if score > 0}
    if not whole:
        sections = [unit for unit in sections if unit['id'] in lexical_rank or unit['id'] in semantic_scores]
        if not sections:
            raise ValueError('This topic has no supporting course evidence. Choose a covered topic or add the missing notes.')
        relevance = {unit['id']: lexical_rank.get(unit['id'], 0) + semantic_scores.get(unit['id'], 0) for unit in sections}
        lexical_scores = {unit['id']: score for score, unit in ranked}
        best_lexical = max((lexical_scores[unit['id']] for unit in sections))
        if best_lexical > 0:
            focused = [unit for unit in sections if lexical_scores[unit['id']] >= best_lexical * 0.75]
            if focused:
                sections = focused
        else:
            best = max(relevance.values())
            sections = [unit for unit in sections if relevance[unit['id']] >= best * 0.75]
        # For a specified topic, relevance outranks novelty. Prefer an explicit
        # topic heading over an incidental mention in a neighbouring chapter,
        # then rotate within a close relevance band. Whole-syllabus selection
        # keeps its existing coverage/mastery rotation.
        relevance={unit['id']:relevance[unit['id']]*(1.35 if query and query<=terms(unit.get('title','')) else 1) for unit in sections}
        best=max(relevance.values())
        sections=[unit for unit in sections if relevance[unit['id']]>=best*.85]
    random.shuffle(sections)
    mastery_scores = learning_store.mastery(user_id)
    sections.sort(key=lambda unit: (unit['id'] in recent_skills,counts.get(unit['id'],0),0 if whole else -relevance[unit['id']],-learning_store.priority(unit['id'],mastery_scores)))
    selected, used_files = ([], set())
    while sections and len(selected) < count:
        unit = next((unit for unit in sections if (unit['course_id'], unit['source_file']) not in used_files), sections[0])
        selected.append(unit)
        used_files.add((unit['course_id'], unit['source_file']))
        sections.remove(unit)
    if len(selected) < count:
        originals = list(selected)
        while len(selected) < count:
            selected.append(originals[len(selected) % len(originals)])
    plans = []
    for unit in selected:
        sources = sorted(unit['sources'], key=lambda row: len(terms(row['text']) & query), reverse=True)
        overlap=max((len(terms(row['text']) & query) for row in sources),default=0)
        topical_sources=[row for row in sources if not overlap or len(terms(row['text']) & query)>=overlap*.75]
        anchor=min(topical_sources,key=lambda row:chunk_counts.get(row['chunk_id'],0))
        same_document = [source for section in catalog['sections'] if not section.get('excluded') and section['course_id'] == unit['course_id'] and (section['source_file'] == unit['source_file']) for source in section['sources'] if not source.get('quality_review_required')]
        neighbors = sorted(same_document, key=lambda row: (abs(row['page'] - anchor['page']) * 10000 + abs(row.get('chunk_index', 0) - anchor.get('chunk_index', 0)), row['page'], row.get('chunk_index', 0)))
        companions = assessment_support(catalog, unit, query, allowed)
        topical=topical_evidence(catalog,unit,query,allowed,semantic)
        continuation=[row for row in neighbors if row['page']==anchor['page'] and row['chunk_id']!=anchor['chunk_id']][:1]
        evidence = retrieval.pack_sources([anchor,*continuation,*topical,*companions,*neighbors[:2]], max_chars=10000)
        evidence = retrieval.relabel_sources(evidence)
        target = 'A covered concept from: ' + ', '.join(unit['keywords'][:6])
        plans.append({'skill_id': unit['id'], 'title': unit['title'], 'scope_key': key, 'sources': evidence, 'topic': topic if not whole else target})
    context = overview(catalog, scope_rules(user_id, course_ids))
    if len(context) > 20000:
        raise ValueError('The combined course scope is too large for one question request. Select fewer courses or provide a concise syllabus.')
    return {'version': catalog['version'], 'scope_key': key, 'overview': context, 'plans': plans, 'recent_questions': relevant_questions(recent,topic)}

def public_map(user_id, course_ids):
    catalog = course_map(user_id, course_ids)
    coverage = []
    for owner, courses in retrieval._course_scopes(user_id, course_ids):
        coverage.extend(db.extraction_coverage(owner, courses))
    return {'version': catalog['version'], 'chunks': catalog['chunks'], 'sections': [{key: value for key, value in unit.items() if key != 'sources'} for unit in catalog['sections']], 'coverage': coverage, 'coverage_known': {(row['course_id'], row['filename']) for row in coverage} == {(unit['course_id'], unit['source_file']) for unit in catalog['sections']}, 'scope_rules': scope_rules(user_id, course_ids), 'map_kind': 'extractive_source_sections'}
