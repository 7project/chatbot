import random

import requests
import vk_api
import logging

from pony.orm import db_session
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

import handlers
from models import UserState, Registration

try:
    import settings
except ImportError:
    exit('Do copy settings.py.default to rename settings.py and set token.')

log = logging.getLogger('Bot')


def configure_logging():
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
    stream_handler.setLevel(logging.INFO)
    log.addHandler(stream_handler)

    file_handler = logging.FileHandler('logging.log', 'w', encoding='utf8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%d-%m-%Y %H:%M'))
    file_handler.setLevel(logging.DEBUG)
    log.addHandler(file_handler)
    log.setLevel(logging.DEBUG)


class Bot:
    """
    Echo Bot for vk.com
    Use Python 3.7
    """
    def __init__(self, group_id, token):
        """
        :param group_id: group_id in group vk.com
        :param token: secret token
        """
        self.group_id = group_id
        self.token = token
        self.vk = vk_api.VkApi(token=token)
        self.long_poll = VkBotLongPoll(self.vk, self.group_id)
        self.api = self.vk.get_api()

    def run(self):
        """
        Запускает логику бота на обработку событий.
        :return: None
        """
        for event in self.long_poll.listen():
            log.info('Получено событие на обработку %s', event)
            try:
                self.on_event(event)
            except Exception:
                log.exception('Ошибка обработки события')

    @db_session
    def on_event(self, event):
        """
        Отправляет сообщение назад если это текст.
        :param event: VkBotMessageEvent object
        :return: None
        """
        if event.type != VkBotEventType.MESSAGE_NEW:
            log.info('Пришло событие, которое не обрабатано, типа - %s', event.type)
            return

        text = event.object.text
        user_id = event.object.peer_id

        state = UserState.get(user_id=str(user_id))

        if state is not None:
            self.continue_scenario(text, state, user_id)
        else:
            for intent in settings.INTENTS:
                log.debug(f'User gets {intent}')
                if any(token in text.lower() for token in intent['tokens']):
                    # run intent
                    if intent['answer']:
                        self.send_text(intent['answer'], user_id)
                        break
                    else:
                        self.start_scenario(user_id, intent['scenario'], text)
                        break
            else:
                self.send_text(settings.DEFAULT_ANSWER, user_id)

    def send_text(self, text_to_send, user_id):
        self.api.messages.send(
            peer_id=user_id,
            message=text_to_send,
            random_id=random.randint(1, 2 ** 20),
        )

    def send_image(self, image, user_id):
        upload_url = self.api.photos.getMessagesUploadServer()['upload_url']
        upload_data = requests.post(url=upload_url, files={'photo': ('image.png', image, 'image/png')}).json()
        image_data = self.api.photos.saveMessagesPhoto(**upload_data)

        owner_id = image_data[0]['owner_id']
        media_id = image_data[0]['id']
        attachment = f'photo{owner_id}_{media_id}'

        self.api.messages.send(
            attachment=attachment,
            random_id=random.randint(1, 2 ** 20),
            peer_id=user_id,
        )

    def send_step(self, step, user_id, text, context):
        if 'text' in step:
            self.send_text(step['text'].format(**context), user_id)
        if 'image' in step:
            handler = getattr(handlers, step['image'])
            image = handler(text, context)
            self.send_image(image, user_id)

    def start_scenario(self, user_id, scenario_name, text):
        scenario = settings.SCENARIOS[scenario_name]
        first_step = scenario['first_step']
        step = scenario['steps'][first_step]
        self.send_step(step, user_id, text, context={})
        UserState(user_id=str(user_id), scenario_name=scenario_name, step_name=first_step, context={})

    def continue_scenario(self, text, state, user_id):
        # продолжаем сценарий
        steps = settings.SCENARIOS[state.scenario_name]['steps']
        step = steps[state.step_name]

        handler = getattr(handlers, step['handler'])
        if handler(text=text, context=state.context):
            # next step
            next_step = steps[step['next_step']]
            self.send_step(next_step, user_id, text, state.context)

            if next_step['next_step']:
                # switch to next step
                state.step_name = step['next_step']
            else:
                # finish scenario
                log.info('Пользователь {name} {email} прошел сценарий.'.format(**state.context))
                Registration(name=state.context['name'], email=state.context['email'])
                state.delete()
        else:
            text_to_send = step['failure_text'].format(**state.context)
            self.send_text(text_to_send, user_id)


if __name__ == '__main__':
    configure_logging()
    bot = Bot(settings.GROUP_ID, settings.TOKEN)
    bot.run()
