import logging
import os
import random
import re

import redis
from environs import Env
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)

logger = logging.getLogger(__file__)


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


def start(update: Update, context: CallbackContext) -> None:
    """Ответ на /start с клавиатурой."""
    custom_keyboard = [['Новый вопрос', 'Сдаться'],
                       ['Мой счёт']]
    reply_markup = ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True)
    update.message.reply_text('Привет! Я бот для викторин', reply_markup=reply_markup)


def handle_message(update: Update, context: CallbackContext) -> None:
    user_message = update.message.text
    questions = context.bot_data.get('questions', [])
    redis_conn = context.bot_data.get('redis')
    user_id = update.effective_user.id

    if user_message == "Новый вопрос":
        question_content = random.choice(questions)
        question = question_content['question']
        answer = question_content ['answer']
        redis_conn.set(f'quiz:{user_id}:answer', answer)
        update.message.reply_text(question)

    elif user_message == "Сдаться":
        answer = redis_conn.get(f'quiz:{user_id}:answer')
        if answer:
            update.message.reply_text(f'Правильный ответ: {answer}')
            redis_conn.delete(f'quiz:{user_id}:answer')
        else:
            update.message.reply_text('Сначала задай мне вопрос 🙂')

    elif user_message == "Мой счёт":
        update.message.reply_text("Скоро будет... 😉")

    else:
        correct_answer = redis_conn.get(f'quiz:{user_id}:answer')
        if correct_answer is None:
            update.message.reply_text('Сначала запроси новый вопрос 😉')
        else:
            user_reply = user_message.strip().lower()
            clean_answer = re.split(r'[.(]', correct_answer)[0]
            if clean_answer in user_reply or user_reply in clean_answer:
                update.message.reply_text('Правильно! Поздравляю! 🎉 Для следующего вопроса нажми «Новый вопрос»')
                redis_conn.delete(f'quiz:{user_id}:answer')
            else:
                update.message.reply_text('Неправильно… 😢 Попробуй ещё раз или нажми «Сдаться».')


def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger.setLevel(logging.DEBUG)

    env = Env()
    env.read_env()

    redis_conn = redis.Redis(
        host=env.str('REDIS_HOST'),
        port=env.int('REDIS_PORT'),
        password=env.str('REDIS_PASSWORD'),
        decode_responses=True
    )

    tg_bot_token = env.str('TG_BOT_TOKEN')
    updater = Updater(tg_bot_token, use_context=True)
    dp = updater.dispatcher

    all_questions = []
    for filename in os.listdir('quiz_questions'):
        if filename.endswith('.txt'):
            path = os.path.join('quiz_questions', filename)
            all_questions.extend(parse_questions_from_file(path))

    dp.bot_data['questions'] = all_questions
    dp.bot_data['redis'] = redis_conn

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
