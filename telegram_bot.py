import logging
import os
import random
import re
from enum import Enum

import redis
from environs import Env
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
)


logger = logging.getLogger(__file__)


class States(Enum):
    QUESTION = 1


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


def start(update: Update, context: CallbackContext):
    redis_conn = context.bot_data['redis']
    user_id = update.effective_user.id

    redis_conn.delete(f'quiz:{user_id}:answer')

    custom_keyboard = [['Новый вопрос', 'Сдаться'],
                       ['Мой счёт']]
    reply_markup = ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True)

    update.message.reply_text(
        'Привет! Я бот для викторин 🧠\n\n'
        'Нажми «Новый вопрос», чтобы начать.',
        reply_markup=reply_markup
    )
    return States.QUESTION


def handle_new_question_request(update: Update, context: CallbackContext):
    questions = context.bot_data['questions']
    redis_conn = context.bot_data['redis']
    user_id = update.effective_user.id

    question_data = random.choice(questions)
    redis_conn.set(f'quiz:{user_id}:answer', question_data['answer'])

    update.message.reply_text(question_data['question'])
    return States.QUESTION


def handle_solution_attempt(update: Update, context: CallbackContext):
    redis_conn = context.bot_data['redis']
    user_id = update.effective_user.id
    correct_answer = redis_conn.get(f'quiz:{user_id}:answer')

    if correct_answer is None:
        update.message.reply_text(
            'Сначала запроси новый вопрос 😉'
        )
        return States.QUESTION

    user_reply = update.message.text.strip().lower()
    clean_answer = re.split(r'[.(]', correct_answer)[0].strip().lower()

    if clean_answer in user_reply or user_reply in clean_answer:
        update.message.reply_text(
            'Правильно! 🎉 Для следующего вопроса нажми «Новый вопрос»'
        )
        redis_conn.delete(f'quiz:{user_id}:answer')
        return States.QUESTION
    else:
        update.message.reply_text(
            'Неправильно… 😢 Попробуй ещё раз или нажми «Сдаться».'
        )
        return States.QUESTION


def handle_surrender(update: Update, context: CallbackContext):
    redis_conn = context.bot_data['redis']
    user_id = update.effective_user.id
    correct_answer = redis_conn.get(f'quiz:{user_id}:answer')

    if correct_answer:
        update.message.reply_text(f'Правильный ответ: {correct_answer}')
        redis_conn.delete(f'quiz:{user_id}:answer')
    else:
        update.message.reply_text(
            'Ты пока не задал вопрос.'
        )

    return handle_new_question_request(update, context)


def handle_score(update: Update, context: CallbackContext):
    update.message.reply_text(
        'Скоро будет... 😉'
    )
    return States.QUESTION


def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.ERROR
    )
    logger.setLevel(logging.DEBUG)

    try:
        env = Env()
        env.read_env()

        redis_conn = redis.Redis(
            host=env.str('REDIS_HOST'),
            port=env.int('REDIS_PORT'),
            password=env.str('REDIS_PASSWORD'),
            decode_responses=True
        )
        redis_conn.ping()

        tg_bot_token = env.str('TG_BOT_TOKEN')
    except Exception:
        logger.exception("Ошибка при инициализации окружения или Redis:")
        return

    try:
        all_questions = []
        for filename in os.listdir('quiz_questions'):
            if filename.endswith('.txt'):
                path = os.path.join('quiz_questions', filename)
                all_questions.extend(parse_questions_from_file(path))

        if not all_questions:
            logger.warning("Не загружено ни одного вопроса.")
    except Exception:
        logger.exception("Ошибка при чтении вопросов:")
        return

    try:
        updater = Updater(tg_bot_token, use_context=True)
        dp = updater.dispatcher

        dp.bot_data['questions'] = all_questions
        dp.bot_data['redis'] = redis_conn

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                States.QUESTION: [
                    MessageHandler(
                        Filters.regex('^(Новый вопрос)$'),
                        handle_new_question_request
                    ),
                    MessageHandler(
                        Filters.regex('^(Сдаться)$'),
                        handle_surrender
                    ),
                    MessageHandler(
                        Filters.regex('^(Мой счёт)$'),
                        handle_score
                    ),
                    MessageHandler(
                        Filters.text & ~Filters.command,
                        handle_solution_attempt
                    ),
                ],
            },
            fallbacks=[CommandHandler('start', start)],
        )

        dp.add_handler(conv_handler)

        updater.start_polling()
        updater.idle()

    except Exception:
        logger.exception("Ошибка при запуске бота:")


if __name__ == '__main__':
    main()
