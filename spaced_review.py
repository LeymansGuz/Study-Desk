"""FSRS scheduling, using UTC timestamps and persisted memory state."""
import json
from datetime import datetime, timezone
from fsrs import Card, Rating, Scheduler
RATINGS = {'again': Rating.Again, 'hard': Rating.Hard, 'good': Rating.Good, 'easy': Rating.Easy}
SCHEDULER = Scheduler(enable_fuzzing=False)

def initialize(connection):
    columns = {row['name'] for row in connection.execute('PRAGMA table_info(flashcards)')}
    for name, kind in [('stability', 'REAL'), ('difficulty', 'REAL'), ('due_date', 'TEXT'), ('fsrs_json', "TEXT NOT NULL DEFAULT ''")]:
        if name not in columns:
            connection.execute(f'ALTER TABLE flashcards ADD COLUMN {name} {kind}')
    connection.execute('UPDATE flashcards SET due_date=next_review_at WHERE due_date IS NULL')

def schedule(row, rating, now=None):
    if rating not in RATINGS:
        raise ValueError('Choose Again, Hard, Good or Easy.')
    now = now or datetime.now(timezone.utc)
    card = Card.from_dict(json.loads(row['fsrs_json'])) if row['fsrs_json'] else Card(due=now)
    card, _ = SCHEDULER.review_card(card, RATINGS[rating], review_datetime=now)
    return (card, (card.due - now).total_seconds() / 86400)
