import os
import json
import random
import time
import requests
from flask import Flask, request

# =========================================================
#   BOT SETTINGS
# =========================================================

TOKEN = "624856590:AAEpH8z4RdVxueSiGLXPscWtf1YypaPHDbE"
ADMIN_ID = "-1001443697465"

DEFAULT_DURATION = 30
DEFAULT_TARGETS = 5
DEFAULT_SOURCES = 3

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

# =========================================================
#   FLASK APP & WEBHOOK ROUTE
# =========================================================

app = Flask('')

@app.route('/')
def home():
    return "Bot is active via Webhook & Cron!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = request.get_json()
        if update:
            data = load_data()
            process_update(data, update)
        return "OK", 200
    else:
        return "Invalid content type", 403

# مسار خاص يتم استدعاؤه تلقائياً عبر Cron Job لتنفيذ دورات النشر والحذف
@app.route('/cron')
def cron_job():
    data = load_data()
    if data.get("running", True):
        run_exchange_tick(data)
    return "Cron executed", 200


# =========================================================
#   TELEGRAM API
# =========================================================

def tg(method, data=None):
    if data is None:
        data = {}
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    try:
        response = requests.post(url, json=data, timeout=45)
        return response.json()
    except Exception as e:
        print(f"REQUEST ERROR: {e}")
        return None


# =========================================================
#   DEFAULT DATA & STORAGE
# =========================================================

def default_data():
    return {
        "channels": [],       # القنوات المشتركة للتبادل
        "ads": [],            # الإعلانات النشطة حالياً المراد حذفها لاحقاً
        "running": True,
        "next_source": 0,
        "settings": {
            "duration": DEFAULT_DURATION,
            "targets": DEFAULT_TARGETS,
            "sources": DEFAULT_SOURCES
        },
        "stats": {
            "sent": 0,
            "failed": 0,
            "rounds": 0
        }
    }

def load_data():
    if not os.path.exists(DATA_FILE):
        return default_data()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default_data()
    except Exception:
        return default_data()

    default = default_data()
    for key, value in default.items():
        if key not in data:
            data[key] = value
    return data

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"SAVE ERROR: {e}")


# =========================================================
#   UI & MENUS
# =========================================================

def button(text, callback):
    return {"text": text, "callback_data": callback}

def admin_menu(data):
    s = data["settings"]
    run_status = "🟢 التبادل يعمل" if data["running"] else "🔴 التبادل متوقف"
    return {
        "inline_keyboard": [
            [button(f"⏱️ مدة الإعلان: {s['duration']} دقيقة", "change_duration")],
            [button(f"📢 النشر في: {s['targets']} قنوات", "targets_menu")],
            [button(f"🎯 الترويج لـ: {s['sources']} قنوات", "sources_menu")],
            [button(run_status, "toggle")],
            [button("📊 الإحصائيات", "stats"), button("🔄 تنفيذ جولة الآن", "round_now")]
        ]
    }

def send_admin(text, keyboard=None):
    payload = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown"}
    if keyboard is not None:
        payload["reply_markup"] = keyboard
    return tg("sendMessage", payload)


# =========================================================
#   EXCHANGE & TIMING LOGIC (النشر والحذف التلقائي)
# =========================================================

def run_exchange_tick(data):
    current_time = time.time()
    
    # 1. فحص الإعلانات القديمة وحذفها إذا انتهت المدة المحددة
    active_ads = []
    for ad in data.get("ads", []):
        duration_sec = data["settings"]["duration"] * 60
        if current_time - ad["time"] >= duration_sec:
            tg("deleteMessage", {"chat_id": ad["chat_id"], "message_id": ad["message_id"]})
        else:
            active_ads.append(ad)
    data["ads"] = active_ads

    # 2. عملية نشر جديدة
    channels = data.get("channels", [])
    if len(channels) >= 2:
        pass

    save_data(data)


# =========================================================
#   UPDATE PROCESSOR
# =========================================================

def process_update(data, update):
    if "callback_query" in update:
        cq = update["callback_query"]
        query_id = cq["id"]
        data_callback = cq["data"]
        chat_id = cq["message"]["chat"]["id"]
        message_id = cq["message"]["message_id"]

        if str(chat_id) == str(ADMIN_ID):
            if data_callback == "toggle":
                data["running"] = not data["running"]
                save_data(data)
                tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "⚙️ **لوحة تحكم بوت التبادل الإعلاني**",
                    "parse_mode": "Markdown",
                    "reply_markup": admin_menu(data)
                })
            elif data_callback == "change_duration":
                # زيادة المدة بـ 10 دقائق (مثلاً كخيار سريع للتجربة) أو التبديل بين القيم
                current_dur = data["settings"]["duration"]
                new_dur = 10 if current_dur >= 30 else current_dur + 10
                if new_dur > 60:
                    new_dur = 10
                data["settings"]["duration"] = new_dur
                save_data(data)
                
                tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "⚙️ **لوحة تحكم بوت التبادل الإعلاني**",
                    "parse_mode": "Markdown",
                    "reply_markup": admin_menu(data)
                })
                tg("answerCallbackQuery", {
                    "callback_query_id": query_id,
                    "text": f"⏱️ تم تغيير مدة الإعلان إلى {new_dur} دقيقة",
                    "show_alert": True
                })
                return
            elif data_callback == "round_now":
                run_exchange_tick(data)
                tg("answerCallbackQuery", {"callback_query_id": query_id, "text": "✅ تم تنفيذ الجولة بنجاح"})
        
        tg("answerCallbackQuery", {"callback_query_id": query_id})
        return

    if "message" in update:
        message = update["message"]
        chat = message["chat"]
        id_str = str(chat["id"])
        text = (message.get("text") or "").strip()

        if id_str == str(ADMIN_ID) and text == "/start":
            send_admin("⚙️ **لوحة تحكم بوت التبادل الإعلاني**", admin_menu(data))
            return


# =========================================================
#   SET WEBHOOK & RUN FLASK
# =========================================================

def set_webhook():
    render_url = "https://channel-bot-dn6k.onrender.com"
    webhook_url = f"{render_url}/{TOKEN}"
    res = tg("setWebhook", {"url": webhook_url})
    print(f"Webhook setup response: {res}")

if __name__ == "__main__":
    set_webhook()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
