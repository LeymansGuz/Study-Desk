"""Unlinked operational totals: no account identifiers or study content."""
import db

def initialize():
    with db.connect() as c:
        c.executescript('\n        CREATE TABLE IF NOT EXISTS anonymous_usage_totals(id INTEGER PRIMARY KEY CHECK(id=1),input_tokens INTEGER NOT NULL,output_tokens INTEGER NOT NULL,cost_usd REAL NOT NULL);\n        INSERT OR IGNORE INTO anonymous_usage_totals VALUES(1,0,0,0);\n        CREATE TABLE IF NOT EXISTS anonymous_usage_daily(day TEXT PRIMARY KEY,input_tokens INTEGER NOT NULL,output_tokens INTEGER NOT NULL,cost_usd REAL NOT NULL,calls INTEGER NOT NULL,errors INTEGER NOT NULL,missing_usage INTEGER NOT NULL);\n        CREATE TRIGGER IF NOT EXISTS retain_anonymous_usage AFTER INSERT ON anonymous_usage_daily BEGIN DELETE FROM anonymous_usage_daily WHERE day NOT IN (SELECT day FROM anonymous_usage_daily ORDER BY day DESC LIMIT 365); END;\n        CREATE VIEW IF NOT EXISTS operational_billing_totals AS SELECT input_tokens,output_tokens,cost_usd FROM billing_totals UNION ALL SELECT input_tokens,output_tokens,cost_usd FROM anonymous_usage_totals;\n        CREATE VIEW IF NOT EXISTS operational_billing_daily AS SELECT day,input_tokens,output_tokens,cost_usd FROM billing_daily UNION ALL SELECT day,input_tokens,output_tokens,cost_usd FROM anonymous_usage_daily;\n        CREATE VIEW IF NOT EXISTS operational_model_daily AS SELECT day,calls,errors,missing_usage FROM model_daily UNION ALL SELECT day,calls,errors,missing_usage FROM anonymous_usage_daily;\n        ')

def preserve(c, identifier):
    totals = c.execute('SELECT input_tokens,output_tokens,cost_usd FROM billing_totals WHERE user_id=?', (identifier,)).fetchone()
    if totals:
        c.execute('UPDATE anonymous_usage_totals SET input_tokens=input_tokens+?,output_tokens=output_tokens+?,cost_usd=cost_usd+? WHERE id=1', tuple(totals))
    days = c.execute('SELECT day FROM billing_daily WHERE user_id=? UNION SELECT day FROM model_daily WHERE user_id=?', (identifier, identifier)).fetchall()
    for day in days:
        billing = c.execute('SELECT input_tokens,output_tokens,cost_usd FROM billing_daily WHERE user_id=? AND day=?', (identifier, day[0])).fetchone()
        model = c.execute('SELECT calls,errors,missing_usage FROM model_daily WHERE user_id=? AND day=?', (identifier, day[0])).fetchone()
        values = (day[0], *(tuple(billing) if billing else (0, 0, 0)), *(tuple(model) if model else (0, 0, 0)))
        c.execute('INSERT INTO anonymous_usage_daily VALUES(?,?,?,?,?,?,?) ON CONFLICT(day) DO UPDATE SET input_tokens=input_tokens+excluded.input_tokens,output_tokens=output_tokens+excluded.output_tokens,cost_usd=cost_usd+excluded.cost_usd,calls=calls+excluded.calls,errors=errors+excluded.errors,missing_usage=missing_usage+excluded.missing_usage', values)
