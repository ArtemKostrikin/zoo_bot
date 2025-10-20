from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from core.config import BOT_USERNAME_LINK
from data.quiz_data import QUIZ_DATA
from data.results_data import get_genitive_name


def get_start_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Начать викторину! ✨", callback_data="start_quiz")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_quiz_keyboard(question_index: int) -> InlineKeyboardMarkup:
    options = QUIZ_DATA[question_index]["options"]
    buttons = []

    for i, option in enumerate(options):
        answer_key = chr(65 + i)
        callback_data = f"q_{question_index}_a_{answer_key}"
        buttons.append([InlineKeyboardButton(text=option["text"], callback_data=callback_data)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_results_keyboard(result_animal_name: str) -> InlineKeyboardMarkup:
    genitive_name = get_genitive_name(result_animal_name)

    opeka_button = InlineKeyboardButton(
        text=f"🐾 Взять {genitive_name} под опеку!",
        callback_data="show_opeka_info"
    )

    share_text = f"Я прошел викторину 'ТотемZOO' от Московского зоопарка и оказался {result_animal_name}! Какое животное ты? Пройди тест: {BOT_USERNAME_LINK}"
    share_button = InlineKeyboardButton(
        text="📢 Поделиться результатом",
        switch_inline_query=share_text
    )

    contact_button = InlineKeyboardButton(text="✉️ Связаться с зоопарком", callback_data="contact_zoo")

    restart_button = InlineKeyboardButton(text="🔄 Попробовать ещё раз?", callback_data="start_quiz")

    feedback_button = InlineKeyboardButton(text="👍 Обратная связь", callback_data="start_feedback")

    buttons = [
        [opeka_button],
        [share_button],
        [contact_button, feedback_button],
        [restart_button]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_opeka_info_keyboard(animal_link: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="➡️ Перейти на страницу опеки животного", url=animal_link)],
        [InlineKeyboardButton(text="⬅️ Вернуться к результату", callback_data="back_to_result")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)