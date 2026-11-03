"""Local model output bounds; usage/cost recording lives in observability."""
from fastapi import HTTPException

class BudgetExceeded(HTTPException):
    pass

def initialize():
    pass

def prune():
    pass

def reserve(user_id, prompt, max_output):
    return None

def finish(reservation, usage_known):
    pass
