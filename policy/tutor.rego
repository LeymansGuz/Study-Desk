package tutor

import rego.v1

# Fail closed: any request that does not match an allow rule is denied.
default decision := {
	"allow": false,
	"action": "unknown",
	"reason": "fail_closed: no policy rule allows this action",
}

# Hints never expose the answer key, so they are always safe.
decision := {
	"allow": true,
	"action": input.action,
	"reason": "hints are permitted while the answer key stays private",
} if input.action == "generate_hint"

# The grader may compare against the private grading key, but policy forbids
# returning it to the student before the attempt cap.
decision := {
	"allow": true,
	"action": input.action,
	"reason": "grading may use the private key without exposing it",
} if input.action == "judge_answer"

# The full worked solution may be loaded into the model context only after the
# student has exhausted the attempt budget.
decision := {
	"allow": true,
	"action": input.action,
	"reason": sprintf("solution key unlocked after %d attempts", [input.max_attempts]),
} if {
	input.action == "access_solution_key"
	input.attempts >= input.max_attempts
}

decision := {
	"allow": false,
	"action": input.action,
	"reason": sprintf(
		"solution key locked: %d of %d attempts used",
		[input.attempts, input.max_attempts],
	),
} if {
	input.action == "access_solution_key"
	input.attempts < input.max_attempts
}

# Releasing the answer to the student follows the same cap.
decision := {
	"allow": true,
	"action": input.action,
	"reason": sprintf("answer reveal allowed after %d attempts", [input.max_attempts]),
} if {
	input.action == "reveal_answer"
	input.attempts >= input.max_attempts
}

decision := {
	"allow": false,
	"action": input.action,
	"reason": sprintf(
		"answer reveal denied: %d of %d attempts used",
		[input.attempts, input.max_attempts],
	),
} if {
	input.action == "reveal_answer"
	input.attempts < input.max_attempts
}

# Confirming a correct answer is not the same as revealing the solution key.
decision := {
	"allow": true,
	"action": input.action,
	"reason": "correct-answer confirmation does not expose the solution key",
} if input.action == "confirm_correct"

# Mock-exam rule: the key for a question unlocks only after the configured
# number of submitted attempts on that question.
decision := {
	"allow": true,
	"action": input.action,
	"reason": sprintf(
		"mock-exam answer key unlocked after %d submitted attempts",
		[input.max_attempts],
	),
} if {
	input.action == "reveal_exam_answer"
	input.attempts >= input.max_attempts
}

decision := {
	"allow": false,
	"action": input.action,
	"reason": sprintf(
		"mock-exam answer key locked: %d of %d attempts used",
		[input.attempts, input.max_attempts],
	),
} if {
	input.action == "reveal_exam_answer"
	input.attempts < input.max_attempts
}
