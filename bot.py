import os
import json
import time
import requests
from datetime import datetime, timedelta
from flask import Flask

# =========================================================
#   BOT SETTINGS & WEB SERVER (FOR RENDER)
# =========================================================

TOKEN = "624856590:AAEpH8z4RdVxueSiGLXPscWtf1YypaPHDbE"
ADMIN_ID = "-1001443697465"

DEFAULT_DURATION = 30
DEFAULT_TARGETS = 5
DEFAULT_SOURCES = 3

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running and active!"


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
        "channels": [],
        "groups": [],
        "from": [],
        "ads": [],
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

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"SAVE ERROR: {e}")

def load_data():
    if not os.path.exists(DATA_FILE):
        initial_data = default_data()
        save_data(initial_data)
        return initial_data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = default_data()
    except Exception:
        data = default_data()

    default = default_data()
    for key, value in default.items():
        if key not in data:
            data[key] = value
    return data


# =========================================================
#   CHANNEL INFO & MARKDOWN LINK
# =========================================================

def get_channel_info(chat_id):
    res = tg("getChat", {"chat_id": chat_id})
    if res and res.get("ok"):
        chat = res.get("result", {})
        title = chat.get("title", "قناة بدون اسم")
        
        username = chat.get("username")
        if username:
            link = f"https://t.me/{username}"
        else:
            link = chat.get("invite_link")
            if not link:
                invite_res = tg("exportChatInviteLink", {"chat_id": chat_id})
                if invite_res and invite_res.get("ok"):
                    link = invite_res.get("result")
                else:
                    link = f"https://t.me/{chat_id}"
        return title, link
    return "قناة غير معروفة", f"https://t.me/{chat_id}"

def format_channel_markdown(chat_id):
    name, link = get_channel_info(chat_id)
    safe_name = name.replace("[", "").replace("]", "")
    return f"[{safe_name}]({link})"


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
            [button(f"🎯 الترويج لـ: {s['sources']} sources", "sources_menu")],
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
#   EXCHANGE LOGIC & LIVE COUNTDOWN
# =========================================================

def run_exchange_tick(data):
    current_time = time.time()
    duration_minutes = data["settings"]["duration"]
    duration_sec = duration_minutes * 60
    
    active_ads = []
    
    for ad in data.get("ads", []):
        post_time = ad["time"]
        elapsed_sec = current_time - post_time
        remaining_sec = duration_sec - elapsed_sec
        
        if remaining_sec <= 0:
            tg("deleteMessage", {"chat_id": ad["chat_id"], "message_id": ad["message_id"]})
        else:
            active_ads.append(ad)
            
            dt_post = datetime.fromtimestamp(post_time)
            dt_delete = dt_post + timedelta(minutes=duration_minutes)
            
            pub_time_str = dt_post.strftime("%I:%M %p").replace("AM", "صباحاً").replace("PM", "مساءً")
            del_time_str = dt_delete.strftime("%I:%M %p").replace("AM", "صباحاً").replace("PM", "مساءً")
            
            remaining_minutes = max(1, int(remaining_sec // 60) + (1 if remaining_sec % 60 > 0 else 0))
            
            ad_body = ad.get("base_text", "📢 **إعلان التبادل الإعلاني المشترك**")
            
            footer_text = (
                f"\n\n───────────────────\n"
                f"📌 تم النشر: `{pub_time_str}`\n"
                f"⏳ سيتم الحذف في: `{del_time_str}`\n"
                f"⏱️ حتى الحذف: *{remaining_minutes}* دقيقة"
            )
            
            full_text = ad_body + footer_text
            
            tg("editMessageText", {
                "chat_id": ad["chat_id"],
                "message_id": ad["message_id"],
                "text": full_text,
                "parse_mode": "Markdown"
            })
            
    data["ads"] = active_ads
    save_data(data)


# =========================================================
#   UPDATE PROCESSOR
# =========================================================

def process_update(data, update):
    if "my_chat_member" in update:
        mcm = update["my_chat_member"]
        chat = mcm["chat"]
        chat_id = chat["id"]
        chat_type = chat["type"]
        new_status = mcm["new_chat_member"]["status"]

        if new_status in ["member", "administrator"]:
            if chat_type == "channel":
                if chat_id not in data["channels"]:
                    data["channels"].append(chat_id)
                    save_data(data)
                    
                    ch_markdown = format_channel_markdown(chat_id)
                    tg("sendMessage", {
                        "chat_id": chat_id,
                        "text": f"✅ **تم تفعيل القناة بنجاح ضمن القنوات المشتركة للتبادل الإعلاني!**\n\nالقناة: {ch_markdown}",
                        "parse_mode": "Markdown"
                    })
                    send_admin(f"📢 **تم اضافة وتفعيل قناة جديدة!**\n\n• القناة: {ch_markdown}\n• الأيدي: `{chat_id}`")

            elif chat_type in ["group", "supergroup"]:
                if chat_id not in data["groups"]:
                    data["groups"].append(chat_id)
                    save_data(data)

        elif new_status in ["left", "kicked"]:
            if chat_id in data["channels"]:
                data["channels"].remove(chat_id)
                save_data(data)
                send_admin(f"⚠️ **تم طرد البوت أو إزالته من القناة وتم حذفها من التخزين!**\n• الأيدي: `{chat_id}`")
            if chat_id in data["groups"]:
                data["groups"].remove(chat_id)
                save_data(data)
        return

    if "callback_query" in update:
        cq = update["callback_query"]
        query_id = cq["id"]
        data_callback = cq["data"]
        chat_id = cq["message"]["chat"]["id"]
        message_id = cq["message"]["message_id"]

        if str(chat_id) == str(ADMIN_ID):
            s = data["settings"]
            
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
                current_dur = s["duration"]
                new_dur = 10 if current_dur >= 60 else current_dur + 10
                s["duration"] = new_dur
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
                    "text": f"⏱️ تم تحديث المدة إلى {new_dur} دقيقة",
                    "show_alert": True
                })
                return

            elif data_callback == "targets_menu":
                targets_kb = {
                    "inline_keyboard": [
                        [button(f"عدد القنوات المستهدفة الحالية: {s['targets']}", "noop")],
                        [button("➕ زيادة", "inc_targets"), button("➖ نقصان", "dec_targets")],
                        [button("🔙 رجوع للوحة التحكم", "back_home")]
                    ]
                }
                tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "📢 **إدارة القنوات المستهدفة للنشر:**",
                    "parse_mode": "Markdown",
                    "reply_markup": targets_kb
                })

            elif data_callback == "sources_menu":
                sources_kb = {
                    "inline_keyboard": [
                        [button(f"عدد قنوات المصدر الحالية: {s['sources']}", "noop")],
                        [button("➕ زيادة", "inc_sources"), button("➖ نقصان", "dec_sources")],
                        [button("🔙 رجوع للوحة التحكم", "back_home")]
                    ]
                }
                tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "🎯 **إدارة قنوات الترويج (المصادر):**",
                    "parse_mode": "Markdown",
                    "reply_markup": sources_kb
                })

            elif data_callback == "stats":
                channels_count = len(data.get("channels", []))
                groups_count = len(data.get("groups", []))
                users_count = len(data.get("from", []))
                ads_count = len(data.get("ads", []))
                
                stats_text = (
                    "📊 **إحصائيات البوت الحالية:**\n\n"
                    f"• القنوات المسجلة: `{channels_count}`\n"
                    f"• المجموعات المسجلة: `{groups_count}`\n"
                    f"• المستخدمين (from): `{users_count}`\n"
                    f"• الإعلانات النشطة: `{ads_count}`"
                )
                back_kb = {"inline_keyboard": [[button("🔙 رجوع للوحة التحكم", "back_home")]]}
                tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": stats_text,
                    "parse_mode": "Markdown",
                    "reply_markup": back_kb
                })

            elif data_callback == "back_home":
                tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "⚙️ **لوحة تحكم بوت التبادل الإعلاني**",
                    "parse_mode": "Markdown",
                    "reply_markup": admin_menu(data)
                })

            elif data_callback in ["inc_targets", "dec_targets"]:
                if data_callback == "inc_targets":
                    s["targets"] += 1
                else:
                    s["targets"] = max(1, s["targets"] - 1)
                save_data(data)
                targets_kb = {
                    "inline_keyboard": [
                        [button(f"عدد القنوات المستهدفة الحالية: {s['targets']}", "noop")],
                        [button("➕ زيادة", "inc_targets"), button("➖ نقصان", "dec_targets")],
                        [button("🔙 رجوع للوحة التحكم", "back_home")]
                    ]
                }
                tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "📢 **إدارة القنوات المستهدفة للنشر:**",
                    "parse_mode": "Markdown",
                    "reply_markup": targets_kb
                })

            elif data_callback in ["inc_sources", "dec_sources"]:
                if data_callback == "inc_sources":
                    s["sources"] += 1
                else:
                    s["sources"] = max(1, s["sources"] - 1)
                save_data(data)
                sources_kb = {
                    "inline_keyboard": [
                        [button(f"عدد قنوات المصدر الحالية: {s['sources']}", "noop")],
                        [button("➕ زيادة", "inc_sources"), button("➖ نقصان", "dec_sources")],
                        [button("🔙 رجوع للوحة التحكم", "back_home")]
                    ]
                }
                tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "🎯 **إدارة قنوات الترويج (المصادر):**",
                    "parse_mode": "Markdown",
                    "reply_markup": sources_kb
                })

            elif data_callback == "round_now":
                run_exchange_tick(data)
                tg("answerCallbackQuery", {"callback_query_id": query_id, "text": "✅ تم تنفيذ الجولة بنجاح"})

        tg("answerCallbackQuery", {"callback_query_id": query_id})
        return

    if "message" in update:
        message = update["message"]
        chat = message["chat"]
        chat_id = chat["id"]
        text = (message.get("text") or "").strip()

        # الاستجابة لأمر /start داخل مجموعة الأدمن المحددة
        if str(chat_id) == str(ADMIN_ID) and text == "/start":
            send_admin("⚙️ **لوحة تحكم بوت التبادل الإعلاني**", admin_menu(data))
            return


# =========================================================
#   BACKGROUND THREAD FOR BOT POLLING
# =========================================================

import threading

def bot_polling():
    print("Bot polling thread started...")
    offset = 0
    data = load_data()
    tg("deleteWebhook", {"drop_pending_updates": True})

    while True:
        try:
            updates = tg("getUpdates", {"offset": offset, "timeout": 30})
            if updates and updates.get("ok"):
                for result in updates.get("result", []):
                    offset = result["update_id"] + 1
                    process_update(data, result)
            
            if data.get("running", True):
                run_exchange_tick(data)
                
            time.sleep(60)
        except Exception as e:
            print(f"Polling Error: {e}")
            time.sleep(3)


# تشغيل البوت في مسار خلفي (Background Thread) ليعمل مع فلاسك على Render
if __name__ == "__main__":
    t = threading.Thread(target=bot_polling)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
