import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from collections import Counter
import os

from core.config import ADMIN_CHAT_ID, LINK_OPEKA_PROGRAM
from core.keyboards import (
    get_start_keyboard, get_quiz_keyboard, get_results_keyboard,
    get_opeka_info_keyboard, get_cancel_keyboard
)
from data.quiz_data import QUIZ_DATA, ANIMALS_ID
from data.results_data import RESULTS, OPEKA_INFO

router = Router()


class QuizStates(StatesGroup):
    START_QUIZ = State()
    IN_QUIZ = State()
    SHOW_RESULT = State()
    CONTACT_ZOO = State()
    FEEDBACK = State()


def get_final_animal(user_scores: dict) -> str:
    scores_counter = Counter(user_scores)

    if not scores_counter:
        return ANIMALS_ID["SLON"]

    most_common_animal, max_score = scores_counter.most_common(1)[0]

    logging.info(f"Final scores: {user_scores}")
    logging.info(f"Winner: {most_common_animal} with score {max_score}")

    return most_common_animal


async def send_final_result(chat_id: int, bot: Bot, state: FSMContext, result_animal_name: str):
    result_data = RESULTS.get(result_animal_name)
    if not result_data:
        await bot.send_message(chat_id, "Ошибка: не удалось найти данные для животного.")
        return

    caption = (
        f"🎉 **Поздравляем! Твое тотемное животное — {result_data['title']}!**\n\n"
        f"*{result_data['description']}*\n\n"
        f"— — — — — — — — — — — — — —\n"
        f"Твоя поддержка поможет обеспечить {result_animal_name.lower()} всем необходимым: "
        f"**{result_data['opeka_cost']}**. Узнай больше о программе опеки! 👇"
    )

    image_name = f"assets/{result_animal_name.lower()}.jpg"

    try:
        if os.path.exists(image_name):
            message = await bot.send_photo(
                chat_id=chat_id,
                photo=types.FSInputFile(image_name),
                caption=caption,
                reply_markup=get_results_keyboard(result_animal_name),
                parse_mode="Markdown"
            )
        else:
            message = await bot.send_message(
                chat_id,
                f"{caption}\n\n[Изображение животного не найдено в папке 'assets'].",
                reply_markup=get_results_keyboard(result_animal_name),
                parse_mode="Markdown"
            )

        await state.update_data(
            final_result_animal=result_animal_name,
            result_message_id=message.message_id
        )
        await state.set_state(QuizStates.SHOW_RESULT)

    except Exception as e:
        logging.error(f"Error sending result: {e}")
        await bot.send_message(
            chat_id,
            caption,
            reply_markup=get_results_keyboard(result_animal_name),
            parse_mode="Markdown"
        )
        await state.update_data(final_result_animal=result_animal_name)
        await state.set_state(QuizStates.SHOW_RESULT)


@router.message(Command("start"))
async def command_start_handler(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "👋 **Добро пожаловать в ТотемZOO!**\n\n"
        "Московский зоопарк предлагает узнать, какое животное из нашей коллекции является твоим тотемом. "
        "Пройди короткую, веселую викторину, и мы подберем тебе идеального подопечного! "
        "А заодно расскажем о нашей **программе опеки**, которая помогает спасать редкие виды.",
        reply_markup=get_start_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "start_quiz")
async def start_quiz_callback(call: types.CallbackQuery, state: FSMContext):
    await call.message.delete()

    initial_scores = {animal: 0 for animal in ANIMALS_ID.values()}

    await state.update_data(
        quiz_index=0,
        scores=initial_scores
    )
    await state.set_state(QuizStates.IN_QUIZ)

    await send_quiz_question(call.message, state)
    await call.answer()


async def send_quiz_question(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    quiz_index = user_data.get("quiz_index", 0)

    if quiz_index < len(QUIZ_DATA):
        question_data = QUIZ_DATA[quiz_index]
        await message.answer(
            text=f"**Вопрос {quiz_index + 1}/{len(QUIZ_DATA)}:**\n{question_data['question']}",
            reply_markup=get_quiz_keyboard(quiz_index),
            parse_mode="Markdown"
        )
        await state.update_data(quiz_index=quiz_index)
    else:
        await calculate_and_send_result(message.chat.id, message.bot, state)


@router.callback_query(QuizStates.IN_QUIZ, F.data.startswith("q_"))
async def process_quiz_answer(call: types.CallbackQuery, state: FSMContext):
    await call.message.delete()

    user_data = await state.get_data()
    current_scores = user_data.get("scores", {})
    quiz_index = user_data.get("quiz_index", 0)

    parts = call.data.split('_')
    if int(parts[1]) != quiz_index:
        logging.warning("Mismatched quiz index in callback data.")
        await call.answer("Произошла ошибка, попробуйте перезапустить.", show_alert=True)
        await call.bot.send_message(call.from_user.id, "Нажмите /start для перезапуска.")
        return

    answer_key = parts[3]
    answer_index = ord(answer_key) - 65

    try:
        score_update = QUIZ_DATA[quiz_index]["options"][answer_index]["score"]

        for animal, score in score_update.items():
            current_scores[animal] = current_scores.get(animal, 0) + score

        next_quiz_index = quiz_index + 1
        await state.update_data(scores=current_scores, quiz_index=next_quiz_index)

        if next_quiz_index < len(QUIZ_DATA):
            await send_quiz_question(call.message, state)
        else:
            await calculate_and_send_result(call.message.chat.id, call.bot, state)

    except IndexError:
        logging.error(f"Invalid answer index {answer_index} for question {quiz_index}")
        await call.answer("Произошла ошибка в данных викторины.", show_alert=True)
        await call.bot.send_message(call.from_user.id, "Нажмите /start для перезапуска.")

    await call.answer()


async def calculate_and_send_result(chat_id: int, bot: Bot, state: FSMContext):
    user_data = await state.get_data()
    final_scores = user_data.get("scores", {})

    result_animal = get_final_animal(final_scores)

    await send_final_result(chat_id, bot, state, result_animal)


@router.callback_query(QuizStates.SHOW_RESULT, F.data == "show_opeka_info")
async def show_opeka_info(call: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    animal_name = user_data.get("final_result_animal", ANIMALS_ID["SLON"])
    message_id = user_data.get("result_message_id")
    animal_data = RESULTS.get(animal_name, {})

    animal_link = animal_data.get("opeka_link", LINK_OPEKA_PROGRAM)

    await call.bot.edit_message_caption(
        chat_id=call.message.chat.id,
        message_id=message_id,
        caption=OPEKA_INFO,
        reply_markup=get_opeka_info_keyboard(animal_link),
        parse_mode="Markdown"
    )
    await call.answer()


@router.callback_query(QuizStates.SHOW_RESULT, F.data == "back_to_result")
async def back_to_result(call: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    animal_name = user_data.get("final_result_animal", ANIMALS_ID["SLON"])
    message_id = user_data.get("result_message_id")
    result_data = RESULTS.get(animal_name)

    caption = (
        f"🎉 **Твое тотемное животное — {result_data['title']}!**\n\n"
        f"*{result_data['description']}*\n\n"
        f"— — — — — — — — — — — — — —\n"
        f"Твоя поддержка поможет обеспечить {animal_name.lower()} всем необходимым: "
        f"**{result_data['opeka_cost']}**. Узнай больше о программе опеки! 👇"
    )

    await call.bot.edit_message_caption(
        chat_id=call.message.chat.id,
        message_id=message_id,
        caption=caption,
        reply_markup=get_results_keyboard(animal_name),
        parse_mode="Markdown"
    )

    await call.answer("Возвращаемся к результату.", show_alert=False)


@router.callback_query(QuizStates.SHOW_RESULT, F.data == "contact_zoo")
async def start_contact_zoo(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(QuizStates.CONTACT_ZOO)
    await call.message.answer(
        "✍️ Отправьте свой вопрос или пожелание сотрудникам зоопарка. "
        "Мы перешлем ваш результат викторины и ваш вопрос администратору. "
        "Для отмены нажмите '❌ Отмена'.",
        reply_markup=get_cancel_keyboard()
    )
    await call.answer()


@router.message(QuizStates.CONTACT_ZOO, F.text)
async def process_contact_zoo_message(message: types.Message, state: FSMContext, bot: Bot):
    user_data = await state.get_data()
    final_animal = user_data.get("final_result_animal", "неизвестно")

    if ADMIN_CHAT_ID == "YOUR_ADMIN_TELEGRAM_ID":
        await message.answer(
            "⚠️ **Внимание!** Администратор бота не настроен (ADMIN_CHAT_ID не установлен). "
            "Сообщение не отправлено. Пожалуйста, проверьте настройки.",
            parse_mode="Markdown"
        )
    else:
        contact_message = (
            f"**📩 НОВЫЙ КОНТАКТНЫЙ ЗАПРОС:**\n\n"
            f"**Пользователь:** @{message.from_user.username or 'нет юзернейма'} (ID: {message.from_user.id})\n"
            f"**Результат викторины:** {final_animal}\n"
            f"**Сообщение:** {message.text}"
        )

        try:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=contact_message,
                parse_mode="Markdown"
            )
            await message.answer("✅ Спасибо! Ваш вопрос переслан сотрудникам зоопарка. Мы свяжемся с вами!")
        except Exception as e:
            logging.error(f"Failed to send message to admin {ADMIN_CHAT_ID}: {e}")
            await message.answer("❌ Произошла ошибка при отправке сообщения. Пожалуйста, попробуйте позже.")

    await state.set_state(QuizStates.SHOW_RESULT)


@router.callback_query(QuizStates.SHOW_RESULT, F.data == "start_feedback")
async def start_feedback(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(QuizStates.FEEDBACK)
    await call.message.answer(
        "👍 Отлично! Напишите, пожалуйста, ваш отзыв о боте. Что понравилось, что можно улучшить? "
        "Для отмены нажмите '❌ Отмена'.",
        reply_markup=get_cancel_keyboard()
    )
    await call.answer()


@router.message(QuizStates.FEEDBACK, F.text)
async def process_feedback_message(message: types.Message, state: FSMContext, bot: Bot):
    user_data = await state.get_data()
    final_animal = user_data.get("final_result_animal", "неизвестно")

    if ADMIN_CHAT_ID == "YOUR_ADMIN_TELEGRAM_ID":
        await message.answer(
            "⚠️ **Внимание!** Администратор бота не настроен (ADMIN_CHAT_ID не установлен). "
            "Отзыв не отправлен. Пожалуйста, проверьте настройки.",
            parse_mode="Markdown"
        )
    else:
        feedback_message = (
            f"**🌟 НОВЫЙ ОТЗЫВ (FEEDBACK):**\n\n"
            f"**Пользователь:** @{message.from_user.username or 'нет юзернейма'} (ID: {message.from_user.id})\n"
            f"**Результат викторины:** {final_animal}\n"
            f"**Отзыв:** {message.text}"
        )

        try:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=feedback_message,
                parse_mode="Markdown"
            )
            await message.answer("✅ Спасибо за ваш отзыв! Это поможет нам сделать бота лучше.")
        except Exception as e:
            logging.error(f"Failed to send feedback to admin {ADMIN_CHAT_ID}: {e}")
            await message.answer("❌ Произошла ошибка при отправке отзыва.")

    await state.set_state(QuizStates.SHOW_RESULT)


@router.callback_query(F.data == "cancel_action", QuizStates.CONTACT_ZOO or QuizStates.FEEDBACK)
async def cancel_action(call: types.CallbackQuery, state: FSMContext):
    await call.message.delete()
    await state.set_state(QuizStates.SHOW_RESULT)
    await call.answer("Действие отменено.")


@router.message(Command("help"))
async def command_help_handler(message: types.Message):
    help_text = (
        "🤖 **ТотемZOO | Помощь**\n\n"
        "Это бот-викторина Московского зоопарка. Он поможет вам узнать ваше тотемное "
        "животное и расскажет о программе опеки.\n\n"
        "**Команды:**\n"
        "/start - Запустить викторину или вернуться в начало.\n"
        "/help - Показать эту справку.\n\n"
        "Если у вас есть вопросы к зоопарку, воспользуйтесь кнопкой **'✉️ Связаться с зоопарком'** после прохождения викторины."
    )
    await message.answer(help_text, parse_mode="Markdown")