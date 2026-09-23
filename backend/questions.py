"""Server-owned question bank for the IntelliProctor technical MCQ MVP."""

TECHNICAL_QUESTIONS = [
    {"id": "python-list-comprehension", "topic": "Python", "difficulty": "easy", "prompt": "What does `[x * 2 for x in range(3)]` evaluate to?", "options": ["[0, 2, 4]", "[1, 2, 3]", "[0, 1, 2]", "[2, 4, 6]"], "answer": 0},
    {"id": "big-o-hash-map", "topic": "Algorithms", "difficulty": "easy", "prompt": "What is the typical average-case lookup time for a hash map?", "options": ["O(1)", "O(log n)", "O(n)", "O(n²)"], "answer": 0},
    {"id": "sql-left-join", "topic": "SQL", "difficulty": "medium", "prompt": "Which JOIN keeps every row from the left table, even when there is no match on the right?", "options": ["INNER JOIN", "LEFT JOIN", "CROSS JOIN", "SELF JOIN"], "answer": 1},
    {"id": "http-idempotency", "topic": "Web", "difficulty": "medium", "prompt": "Which HTTP method is intended to be idempotent when replacing a resource?", "options": ["POST", "PATCH", "PUT", "CONNECT"], "answer": 2},
    {"id": "git-rebase", "topic": "Git", "difficulty": "medium", "prompt": "What is the main effect of `git rebase main` on a feature branch?", "options": ["Deletes main", "Replays feature commits onto main", "Creates a merge commit only", "Pushes to remote"], "answer": 1},
    {"id": "javascript-closure", "topic": "JavaScript", "difficulty": "medium", "prompt": "A closure lets a function do what?", "options": ["Access variables from its lexical outer scope", "Run only once", "Avoid asynchronous code", "Convert strings to numbers"], "answer": 0},
    {"id": "database-index", "topic": "Databases", "difficulty": "medium", "prompt": "What is a common trade-off of adding a database index?", "options": ["Faster reads but slower writes and extra storage", "Faster writes with no trade-off", "It encrypts data", "It removes duplicates automatically"], "answer": 0},
    {"id": "unit-test-purpose", "topic": "Testing", "difficulty": "easy", "prompt": "What should a focused unit test generally verify?", "options": ["One small behavior in isolation", "The complete production network", "Every browser at once", "Only the user interface colors"], "answer": 0},
    {"id": "docker-image", "topic": "DevOps", "difficulty": "medium", "prompt": "Which statement best describes a Docker image?", "options": ["A running process", "A read-only template used to create containers", "A cloud provider", "A source-control branch"], "answer": 1},
    {"id": "race-condition", "topic": "Concurrency", "difficulty": "hard", "prompt": "What most directly causes a race condition?", "options": ["Two operations access shared state without safe coordination", "A slow network request", "A syntax error", "An empty database table"], "answer": 0},
]


def public_questions():
    """Never send answer keys to the browser."""
    return [{key: value for key, value in question.items() if key != "answer"} for question in TECHNICAL_QUESTIONS]


def grade_answers(answers: dict) -> tuple[int, int, list[dict]]:
    results = []
    correct = 0
    for question in TECHNICAL_QUESTIONS:
        selected = answers.get(question["id"])
        is_correct = selected == question["answer"]
        correct += int(is_correct)
        results.append({"question_id": question["id"], "selected_option": selected, "is_correct": is_correct})
    return correct, len(TECHNICAL_QUESTIONS), results
