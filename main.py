import os
import time
import threading
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# === CONFIG (tus datos ya puestos) ===
TOKEN = "8494624954:AAEX94ATyNAUtp7My3oIKUM9vSXGePBBJ_s"
GROUP_ID = -1001829895172
TOPIC_ID = 13837
DELETE_AFTER = 90  # segundos

# Si quieres que, al expulsar, pueda volver a entrar enseguida:
ALLOW_REJOIN = True  # expulsar y des-expulsar para permitir reingreso

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# Pendientes de aceptar reglas { user_id: {"welcome_id": int, "rules_id": int} }
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

# ============ MANEJO DE NUEVOS MIEMBROS ============

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
    except Exception as e:
        print("chat_member handler error:", e)

def _send_welcome_flow(user):
    try:
        name = user.first_name or "Usuario"
        # 1) Mensaje de bienvenida (en el tópico)
        wmsg = bot.send_message(
            GROUP_ID,
            WELCOME_TEXT.format(name=name),
            message_thread_id=TOPIC_ID
        )
        # 2) Mensaje de reglas + botón (en el tópico)
        rmsg = bot.send_message(
            GROUP_ID,
            RULES_TEXT,
            reply_markup=accept_keyboard(user.id),
            message_thread_id=TOPIC_ID
        )
        # Guardamos para borrado y control
        pending[user.id] = {"welcome_id": wmsg.message_id, "rules_id": rmsg.message_id}
        # Programar borrado/expulsión si no acepta en 90s
        threading.Thread(target=_timer_and_kick, args=(user.id,), daemon=True).start()
    except Exception as e:
        print("Error enviando bienvenida/reglas:", e)

def _timer_and_kick(user_id: int):
    time.sleep(DELETE_AFTER)
    data = pending.get(user_id)
    if not data:
        return
    # Borrar ambos mensajes
    for mid in (data.get("welcome_id"), data.get("rules_id")):
        if mid:
            try:
                bot.delete_message(GROUP_ID, mid)
            except Exception:
                pass
    # Expulsar (kick). Si ALLOW_REJOIN=True, desexpulsar para permitir reingreso
    try:
        bot.ban_chat_member(GROUP_ID, user_id)
        if ALLOW_REJOIN:
            bot.unban_chat_member(GROUP_ID, user_id)
    except Exception as e:
        print("Error expulsando/desexpulsando:", e)
    pending.pop(user_id, None)

# ============ MANEJO DEL BOTÓN "ACEPTO" ============

@bot.callback_query_handler(func=lambda c: c.data.startswith("accept:"))
def on_accept(call):
    try:
        _, uid_str = call.data.split(":", 1)
        uid = int(uid_str)
    except Exception:
        bot.answer_callback_query(call.id, "Error.", show_alert=True)
        return

    if call.from_user.id != uid:
        bot.answer_callback_query(call.id, "Este botón no es para ti.", show_alert=True)
        return

    data = pending.pop(uid, None)
    # Borrar mensajes inmediatamente
    if data:
        for mid in (data.get("welcome_id"), data.get("rules_id"), call.message.message_id):
            if mid:
                try:
                    bot.delete_message(GROUP_ID, mid)
                except Exception:
                    pass
    bot.answer_callback_query(call.id, "¡Gracias! Reglas aceptadas ✅")

# ============ WEBHOOK (Flask) ============

@app.get("/")
def root():
    return "ok", 200

@app.post(f"/{TOKEN}")
def receive_update():
    try:
        json_str = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        print("Webhook error:", e)
    return "", 200

def set_webhook_if_possible():
    # En Render, RENDER_EXTERNAL_URL apunta al dominio público del servicio
    url_base = os.environ.get("RENDER_EXTERNAL_URL")
    if url_base:
        webhook_url = f"{url_base}/{TOKEN}"
        try:
            bot.remove_webhook()
        except Exception:
            pass
        ok = bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "chat_member", "callback_query"]
        )
        print("Webhook set:", ok, webhook_url)
    else:
        print("RENDER_EXTERNAL_URL no encontrado; configura el webhook manualmente luego.")

# Ejecuta al importar (cuando el contenedor inicia)
set_webhook_if_possible()

# Para correr local (no se usa en Render, allí usamos gunicorn)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
