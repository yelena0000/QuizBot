import logging
import random
import re

import redis
import vk_api
from environs import Env
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

from quiz_questions_loader import load_all_questions


logger = logging.getLogger(__file__)


def get_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('Новый вопрос', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('Сдаться', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button('Мой счёт', color=VkKeyboardColor.SECONDARY)
    return keyboard


def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.ERROR
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

    vk_token = env.str('VK_GROUP_TOKEN')

    all_questions = load_all_questions()

    vk_session = vk_api.VkApi(token=vk_token)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    keyboard = get_keyboard()

    for event in longpoll.listen():
        if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
            continue

        user_id = event.user_id
        message = event.text.strip()

        try:
            if message.lower() in ('начать', '/start'):
                vk.messages.send(
                    user_id=user_id,
                    message='Привет! Я бот для викторин 🧠\nНажми кнопку, чтобы начать.',
                    random_id=get_random_id(),
                    keyboard=keyboard.get_keyboard(),
                )
                continue

            if message == 'Новый вопрос':
                question = random.choice(all_questions)
                redis_conn.set(f'vk-quiz:{user_id}:answer', question['answer'])
                vk.messages.send(
                    user_id=user_id,
                    message=question['question'],
                    random_id=get_random_id(),
                    keyboard=keyboard.get_keyboard(),
                )
                continue

            if message == 'Сдаться':
                answer = redis_conn.get(f'vk-quiz:{user_id}:answer')
                if not answer:
                    vk.messages.send(
                        user_id=user_id,
                        message='Сначала нажми «Новый вопрос» 🙂',
                        random_id=get_random_id(),
                        keyboard=keyboard.get_keyboard(),
                    )
                    continue

                vk.messages.send(
                    user_id=user_id,
                    message=f'Правильный ответ: {answer}',
                    random_id=get_random_id(),
                    keyboard=keyboard.get_keyboard(),
                )
                question = random.choice(all_questions)
                redis_conn.set(f'vk-quiz:{user_id}:answer', question['answer'])
                vk.messages.send(
                    user_id=user_id,
                    message=question['question'],
                    random_id=get_random_id(),
                    keyboard=keyboard.get_keyboard(),
                )
                continue

            if message == 'Мой счёт':
                vk.messages.send(
                    user_id=user_id,
                    message='Скоро будет... 😉',
                    random_id=get_random_id(),
                    keyboard=keyboard.get_keyboard(),
                )
                continue

            correct_answer = redis_conn.get(f'vk-quiz:{user_id}:answer')
            if not correct_answer:
                vk.messages.send(
                    user_id=user_id,
                    message='Сначала нажми «Новый вопрос» 🙂',
                    random_id=get_random_id(),
                    keyboard=keyboard.get_keyboard(),
                )
                continue

            user_reply = message.lower()
            clean_answer = re.split(r'[.(]', correct_answer)[0].lower()
            if clean_answer in user_reply or user_reply in clean_answer:
                vk.messages.send(
                    user_id=user_id,
                    message='Правильно! 🎉 Для следующего вопроса нажми «Новый вопрос»',
                    random_id=get_random_id(),
                    keyboard=keyboard.get_keyboard(),
                )
                redis_conn.delete(f'vk-quiz:{user_id}:answer')
                continue

            vk.messages.send(
                user_id=user_id,
                message='Неправильно… 😢 Попробуй ещё раз или нажми «Сдаться».',
                random_id=get_random_id(),
                keyboard=keyboard.get_keyboard(),
            )

        except Exception:
            logger.exception(f'Ошибка при обработке сообщения от пользователя {user_id}')


if __name__ == '__main__':
    main()
