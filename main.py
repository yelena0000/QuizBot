import os

def parse_questions_from_file(filepath):
    with open(filepath, encoding='koi8-r') as file:
        content = file.read()

    # Разделим на блоки — каждый блок это один вопрос
    raw_questions = content.strip().split('\n\n')

    qa_pairs = []
    current_question = {}

    for block in raw_questions:
        if block.startswith('Вопрос'):
            current_question['question'] = block.partition(':')[2].strip()
        elif block.startswith('Ответ'):
            current_question['answer'] = block.partition(':')[2].strip()
            # сохраняем, только если и вопрос и ответ присутствуют
            if 'question' in current_question and 'answer' in current_question:
                qa_pairs.append(current_question)
            current_question = {}

    return qa_pairs



def main():
    all_questions = []

    for filename in os.listdir('quiz_questions'):
        if filename.endswith('.txt'):
            path = os.path.join('quiz_questions', filename)
            all_questions.extend(parse_questions_from_file(path))

    print(all_questions[0]['question'])


if __name__ == '__main__':
    main()