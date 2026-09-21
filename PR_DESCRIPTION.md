Title: Calibrate Pulse Python syntax for readable interview practice

Pulse should test reasoning about the request-to-response flow and basic Python
data structures. This change expands dense routing calls, event construction,
summary calculations, pagination responses, and validation into readable steps.
Validation limits and required fields use named arguments where helpful.

Simple list and set comprehensions, dictionary access and updates, tuple returns,
list slicing, nested JSON, and iteration over dictionaries remain part of the
application. The README records the roughly 70–80% straightforward / 20–30%
moderately compact Python guideline, patterns to preserve, syntax to avoid, and
a small sorting-with-key exercise. API behavior and registration order stay the
same.

Validation: all 28 existing tests pass, including HTTP integration tests, atomic
batch writes, failed updates, filtering, pagination, response copies, and errors.
`git diff --check` passes.
