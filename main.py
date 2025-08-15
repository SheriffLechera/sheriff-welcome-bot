import time
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8494624954:AAEX94ATyNAUtp7My3oIKUM9vSXGePBBJ_s"
GROUP_ID = -1001829895172
TOPIC_ID = 13837
DELETE_AFTER = 90
ALLOW_REJOIN = True

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
pending = {}

WELCOME_TEXT = (
    "Welcome {name} ! Para continuar acepta las reglas debajo 👇🏼\n"
    "-To continue accept the rules below\n\n"
    "Solo subir chicas que TRAGAN LECHE y/o FACIALES. Utiliza los diferentes tópicos.\n"
    "-Facials & Cum Swallow ONLY. Use the topics.\n"
)

RULES_TEXT = (
    "<b>Reglas</b>\n\n"
    "Charlas sólo en el grupo de chat / Chatting only in \"Talk room\".\n\n"
    "Expulsamos aleatoriamente a los que no aportan ni reaccionan.\n"
    "We randomly kick users who doesn't react or share."
)

def accept_keyboard(user_id: int):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Acepto las reglas", callback_data=f"accept:{user_id}"))
    return kb

@bot.message_handler(content_types=['new_chat_members'])
def on_new_members(message):
    for m in message.new_chat_members:
        if m.is_bot:
            continue
        _send_welcome_flow(m)

@bot.chat_member_handler()
def on_chat_member(update: telebot.types.ChatMemberUpdated):
    try:
        if (update.new_chat_member.status == 'member' and
            update.old_chat_member.status in ('left', 'kicked') and
            not update.new_chat_member.user.is_bot):
            _send_welcome_flow(update.new_chat_member.user)
    except:
        pass

def _send_welcome_flow(user):
    try:
        name = user.first_name or "Usuario"
        wmsg = bot.send_message(
            GROUP_ID,
            WELCOME_TEXT.format(name=name),
            message_thread_id=TOPIC_ID
        )
        rmsg = bot.send_message(
            GROUP_ID,
            RULES_TEXT,
            reply_markup=accept_keyboard(user.id),
            message_thread_id=TOPIC_ID
        )
        pending[user.id] = {"welcome_id": wmsg.message_id, "rules_id": rmsg.message_id}
        threading.Thread(target=_timer_and_kick, args=(user.id,), daemon=True).start()
    except:
        pass

def _timer_and_kick(user_id: int):
    time.sleep(DELETE_AFTER)
    data = pending.get(user_id)
    if not data:
        return
    for mid in (data.get("welcome_id"), data.get("rules_id")):
        if mid:
            try:
                bot.delete_message(GROUP_ID, mid)
            except:
                pass
    try:
        bot.ban_chat_member(GROUP_ID, user_id)
        if ALLOW_REJOIN:
            bot.unban_chat_member(GROUP_ID, user_id)
    except:
        pass
    pending.pop(user_id, None)

@bot.callback_query_handler(func=lambda c: c.data.startswith("accept:"))
def on_accept(call):
    try:
        uid = int(call.data.split(":")[1])
    except:
        bot.answer_callback_query(call.id, "Error.", show_alert=True)
        return
    if call.from_user.id != uid:
        bot.answer_callback_query(call.id, "Este botón no es para ti.", show_alert=True)
        return
    data = pending.pop(uid, None)
    if data:
        for mid in (data.get("welcome_id"), data.get("rules_id"), call.message.message_id):
            if mid:
                try:
                    bot.delete_message(GROUP_ID, mid)
                except:
                    pass
    bot.answer_callback_query(call.id, "¡Gracias! Reglas aceptadas ✅")

print("Bot Sheriff Bienvenida activo...")
bot.infinity_polling(skip_pending=True)
