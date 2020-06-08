import os
import unittest
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch, Mock, ANY

from pony.orm import rollback, db_session
from vk_api.bot_longpoll import VkBotEventType, VkBotMessageEvent, VkBotEvent

import settings
from bot import Bot
from generate_ticket import generate_ticket


def isolate_db(test_func):
    def wrapper(*args, **kwargs):
        with db_session:
            test_func(*args, **kwargs)
            rollback()
    return wrapper


class TestOne(TestCase):
    RAW_EVENT = {'type': 'message_new',
                 'object': {'date': 1579524580, 'from_id': 15667246, 'id': 0, 'out': 0, 'peer_id': 2000000003,
                            'text': 'привет', 'conversation_message_id': 150, 'fwd_messages': [], 'important': False,
                            'random_id': 0, 'attachments': [], 'is_hidden': False}, 'group_id': 187171389,
                 'event_id': '0c4f340c990a2e901f59b25a4df5601f3ff0f694'}

    def test_run(self):
        count = 5
        obj1 = {'a': 1}
        events = [obj1] * count
        long_poll_mock = Mock(return_value=events)
        long_poll_listen_mock = Mock()
        long_poll_listen_mock.listen = long_poll_mock
        with patch('bot.vk_api.VkApi'):
            with patch('bot.VkBotLongPoll', return_value=long_poll_listen_mock):
                bot = Bot('', '')
                bot.on_event = Mock()
                bot.send_image = Mock()
                bot.run()
                bot.on_event.assert_called()
                bot.on_event.assert_any_call(obj1)

                assert bot.on_event.call_count == count

    INPUTS = [
        'Че как?',
        'Привет',
        'Когда?',
        'Где пройдет?',
        'Зарегистрируй меня',
        'Александр',
        'Мой адресс mail@mail',
        'mail@mail.ru',
    ]

    EXPECTED_OUTPUTS = [
        settings.DEFAULT_ANSWER,
        settings.INTENTS[0]['answer'],
        settings.INTENTS[1]['answer'],
        settings.INTENTS[2]['answer'],
        settings.SCENARIOS['registration']['steps']['step1']['text'],
        settings.SCENARIOS['registration']['steps']['step2']['text'],
        settings.SCENARIOS['registration']['steps']['step2']['failure_text'],
        settings.SCENARIOS['registration']['steps']['step3']['text'].format(name='Александр', email='mail@mail.ru')
    ]

    @isolate_db
    def test_run_ok(self):
        send_mock = Mock()
        api_mock = Mock()
        api_mock.messages.send = send_mock

        events = []
        for input_text in self.INPUTS:
            event = deepcopy(self.RAW_EVENT)
            event['object']['text'] = input_text
            events.append(VkBotMessageEvent(event))

        long_poll_mock = Mock()
        long_poll_mock.listen = Mock(return_value=events)

        with patch('bot.VkBotLongPoll', return_value=long_poll_mock):
            bot = Bot('', '')
            bot.api = api_mock
            bot.send_image = Mock()
            bot.run()

        assert send_mock.call_count == len(self.INPUTS)

        real_outputs = []
        for call in send_mock.call_args_list:
            args, kwargs = call
            real_outputs.append(kwargs['message'])
        print(f'{real_outputs}, \n{self.EXPECTED_OUTPUTS}')
        assert real_outputs == self.EXPECTED_OUTPUTS

    def test_image_generation(self):
        path_dir = os.path.dirname(__file__)
        path_file = '/files/ticket_example.png'
        path_file = os.path.normpath(path_dir + path_file)
        avatar_file = '/files/admin.png'
        avatar_file = os.path.normpath(path_dir + avatar_file)
        with open(avatar_file, 'rb') as avatar_f:
            avatar_mock = Mock()
            avatar_mock.content = avatar_f.read()
        with patch('requests.get', return_value=avatar_mock):
            ticket_file = generate_ticket('Admin', 'admin@admin.ru')

        with open(path_file, 'rb') \
                as expected_file:
            expected_bytes = expected_file.read()
        assert ticket_file.read() == expected_bytes


if __name__ == '__main__':
    unittest.main()
