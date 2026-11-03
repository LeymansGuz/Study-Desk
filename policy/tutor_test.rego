package tutor

import rego.v1

test_hint_allowed if {
	result := decision with input as {"action": "generate_hint", "attempts": 0, "max_attempts": 3}
	result.allow == true
}

test_solution_locked_before_cap if {
	result := decision with input as {
		"action": "access_solution_key",
		"attempts": 2,
		"max_attempts": 3,
	}
	result.allow == false
}

test_solution_unlocked_at_cap if {
	result := decision with input as {
		"action": "access_solution_key",
		"attempts": 3,
		"max_attempts": 3,
	}
	result.allow == true
}

test_reveal_denied_before_cap if {
	result := decision with input as {
		"action": "reveal_answer",
		"attempts": 1,
		"max_attempts": 3,
	}
	result.allow == false
}

test_reveal_allowed_at_cap if {
	result := decision with input as {
		"action": "reveal_answer",
		"attempts": 3,
		"max_attempts": 3,
	}
	result.allow == true
}

test_unknown_action_fails_closed if {
	result := decision with input as {
		"action": "dump_solution_key",
		"attempts": 99,
		"max_attempts": 3,
	}
	result.allow == false
}

test_exam_key_locked_before_attempt if {
	result := decision with input as {
		"action": "reveal_exam_answer",
		"attempts": 0,
		"max_attempts": 3,
	}
	result.allow == false
}

test_exam_key_locked_after_first_attempt if {
	result := decision with input as {
		"action": "reveal_exam_answer",
		"attempts": 1,
		"max_attempts": 3,
	}
	result.allow == false
}

test_exam_key_unlocked_after_three_attempts if {
	result := decision with input as {
		"action": "reveal_exam_answer",
		"attempts": 3,
		"max_attempts": 3,
	}
	result.allow == true
}

test_exam_key_respects_five_attempt_setting if {
	locked := decision with input as {
		"action": "reveal_exam_answer",
		"attempts": 4,
		"max_attempts": 5,
	}
	unlocked := decision with input as {
		"action": "reveal_exam_answer",
		"attempts": 5,
		"max_attempts": 5,
	}
	locked.allow == false
	unlocked.allow == true
}
