import logging
import os
import random
import re

import redis
import vk_api
from environs import Env
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id


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


def get_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('Новый вопрос', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('Сдаться', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button('Мой счёт', color=VkKeyboardColor.SECONDARY)
    return keyboard


def main():
    logging.basicConfig(level=logging.ERROR)
    logger.setLevel(logging.DEBUG)

    env = Env()
    env.read_env()

    redis_conn = redis.Redis(
        host=env.str('REDIS_HOST'),
        port=env.int('REDIS_PORT'),
        password=env.str('REDIS_PASSWORD'),
        decode_responses=True
    )

    vk_token = env.str('VK_GROUP_TOKEN')

    all_questions = []
    for filename in os.listdir('quiz_questions'):
        if filename.endswith('.txt'):
            path = os.path.join('quiz_questions', filename)
            all_questions.extend(parse_questions_from_file(path))

    vk_session = vk_api.VkApi(token=vk_token)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    keyboard = get_keyboard()

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            message = event.text.strip()

            try:
                if message == 'Новый вопрос':
                    question = random.choice(all_questions)
                    redis_conn.set(
                        f'vk_quiz:{user_id}:answer',
                        question['answer']
                    )
                    vk.messages.send(
                        user_id=user_id,
                        message=question['question'],
                        random_id=get_random_id(),
                        keyboard=keyboard.get_keyboard(),
                    )

                elif message == 'Сдаться':
                    answer = redis_conn.get(f'vk_quiz:{user_id}:answer')
                    if answer:
                        vk.messages.send(
                            user_id=user_id,
                            message=f'Правильный ответ: {answer}',
                            random_id=get_random_id(),
                            keyboard=keyboard.get_keyboard(),
                        )
                        question = random.choice(all_questions)
                        redis_conn.set(
                            f'vk_quiz:{user_id}:answer',
                            question['answer']
                        )
                        vk.messages.send(
                            user_id=user_id,
                            message=question['question'],
                            random_id=get_random_id(),
                            keyboard=keyboard.get_keyboard(),
                        )
                    else:
                        vk.messages.send(
                            user_id=user_id,
                            message='Сначала нажми «Новый вопрос» 🙂',
                            random_id=get_random_id(),
                            keyboard=keyboard.get_keyboard(),
                        )

                elif message == 'Мой счёт':
                    vk.messages.send(
                        user_id=user_id,
                        message='Скоро будет... 😉',
                        random_id=get_random_id(),
                        keyboard=keyboard.get_keyboard(),
                    )

                else:
                    correct_answer = redis_conn.get(f'vk_quiz:{user_id}:answer')
                    if correct_answer is None:
                        vk.messages.send(
                            user_id=user_id,
                            message='Сначала нажми «Новый вопрос» 🙂',
                            random_id=get_random_id(),
                            keyboard=keyboard.get_keyboard(),
                        )
                    else:
                        user_reply = message.lower()
                        clean_answer = re.split(r'[.(]', correct_answer)[0].lower()
                        if clean_answer in user_reply or user_reply in clean_answer:
                            vk.messages.send(
                                user_id=user_id,
                                message='Правильно! 🎉 Для следующего вопроса нажми «Новый вопрос»',
                                random_id=get_random_id(),
                                keyboard=keyboard.get_keyboard(),
                            )
                            redis_conn.delete(f'vk_quiz:{user_id}:answer')
                        else:
                            vk.messages.send(
                                user_id=user_id,
                                message='Неправильно… 😢 Попробуй ещё раз или нажми «Сдаться».',
                                random_id=get_random_id(),
                                keyboard=keyboard.get_keyboard(),
                            )

            except Exception:
                logger.error(
                    f'Ошибка при обработке сообщения от пользователя {user_id}',
                    exc_info=True
                )


if __name__ == '__main__':
    main()
