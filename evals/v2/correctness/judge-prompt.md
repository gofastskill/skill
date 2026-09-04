You are grading one answer a coding agent gave to a question about the `fastskill`
command-line tool. Grade the answer below and nothing else. Do not grade its style, its
length or its tone, and do not reward or penalise an answer for explaining itself.

## The question the agent was asked

{{case.prompt}}

## A reference answer

{{case.expected}}

The reference answer is one correct response, not the only one. An answer that reaches the
same result by a different but valid route is correct. An answer that names the right flag
inside a command that would not do what was asked is not — that is the failure this judge
exists to catch, because a substring check cannot see it.

## The agent's answer

{{trial.final_answer}}

## What to score

{{rubric}}

## How to reply

{{output_contract}}

Reply with that JSON object and nothing else: no prose before it, no prose after it, no
code fence around it. Within each criterion write `reasoning` before `answer`, and let the
reasoning be the reason for the answer rather than a restatement of it.
