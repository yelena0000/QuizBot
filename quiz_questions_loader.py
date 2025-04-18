import os


def parse_questions_from_file(filepath):
    with open(filepath, encoding='koi8-r') as file:
        content = file.read()

    raw_questions = content.strip().split('\n\n')
    qa_pairs = []
    current_question = {}

    for block in raw_questions:
        if block.startswith('Вопрос'):
            current_question['question'] = block.partition(':')[2].strip()
        elif block.startswith('Ответ'):
            current_question['answer'] = block.partition(':')[2].strip()
            if 'question' in current_question and 'answer' in current_question:
                qa_pairs.append(current_question)
            current_question = {}

    return qa_pairs


def load_all_questions(folder='quiz_questions'):
    all_questions = []
    for filename in os.listdir(folder):
        if filename.endswith('.txt'):
            path = os.path.join(folder, filename)
            all_questions.extend(parse_questions_from_file(path))
    return all_questions
