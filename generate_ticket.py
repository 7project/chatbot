import os

import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

DIR_PATH = os.path.dirname(__file__)
TEMPLATE_PATH = '/files/bg.jpg'
TEMPLATE_PATH = os.path.normpath(DIR_PATH + TEMPLATE_PATH)
FONT_PATH = '/files/Roboto-Regular.ttf'
FONT_PATH = os.path.normpath(DIR_PATH + FONT_PATH)
FONT_SIZE = 20
COLOR_BLACK = (0, 0, 0)
NAME_OFFSET = (300, 180)
EMAIL_OFFSET = (300, 210)

AVATAR_SIZE = 90
AVATAR_OFFSET = (100, 170)


def generate_ticket(name, email):
    base = Image.open(TEMPLATE_PATH)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    draw = ImageDraw.Draw(base)
    draw.text(NAME_OFFSET, name, font=font, fill=COLOR_BLACK)
    draw.text(EMAIL_OFFSET, email, font=font, fill=COLOR_BLACK)

    response = requests.get(url=f'https://api.adorable.io/avatars/{AVATAR_SIZE}/{email}')
    avatar_file_like = BytesIO(response.content)
    avatar = Image.open(avatar_file_like)
    base.paste(avatar, AVATAR_OFFSET)

    temp_file = BytesIO()
    base.save(temp_file, 'png')
    temp_file.seek(0)

    return temp_file

