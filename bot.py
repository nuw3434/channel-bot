import os
import json
import time
import requests

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
#   EXCHANGE & TIMING LOGIC
# =========================================================

def run_exchange_tick(data):
    current_time = time.time()
    
    # فحص الإعلانات القديمة وحذفها إذا انتهت المدة المحددة
    active_ads = []
    for ad in data.get("ads", []):
        duration_sec = data["settings"]["duration"] * 60
        if current_time - ad["time"] >= duration_sec:
            tg("deleteMessage", {"chat_id": ad["chat_id"], "message_id": ad["message_id"]})
        else:
            active_ads.append(ad)
    data["ads"] = active_ads
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
            s = data["settings"]
            
            # 1. زر تشغيل وإيقاف التبادل
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

            # 2. زر تغيير مدة الإعلان
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

            # 3. زر النشر في (Targets Menu)
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
                    "text": "📢 **إدارة القنوات المستهدفة للنشر:**\nاختر التعديل المناسب:",
                    "parse_mode": "Markdown",
                    "reply_markup": targets_kb
                })

            # 4. زر الترويج لـ (Sources Menu)
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
                    "text": "🎯 **إدارة قنوات الترويج (المصادر):**\nاختر التعديل المناسب:",
                    "parse_mode": "Markdown",
                    "reply_markup": sources_kb
                })

            # 5. زر الإحصائيات (Stats)
            elif data_callback == "stats":
                stats = data["stats"]
                channels_count = len(data.get("channels", []))
                ads_count = len(data.get("ads", []))
                
                stats_text = (
                    "📊 **إحصائيات البوت الحالية:**\n\n"
                    f"• عدد القنوات المسجلة: `{channels_count}`\n"
                    f"• الإعلانات النشطة حالياً: `{ads_count}`\n"
                    f"• الرسائل المرسلة بنجاح: `{stats.get('sent', 0)}`\n"
                    f"• الفشلات المسجلة: `{stats.get('failed', 0)}`\n"
                    f"• إجمالي الجولات: `{stats.get('rounds', 0)}`"
                )
                back_kb = {"inline_keyboard": [[button("🔙 رجوع للوحة التحكم", "back_home")]]}
                tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": stats_text,
                    "parse_mode": "Markdown",
                    "reply_markup": back_kb
                })

            # 6. زر الرجوع للقائمة الرئيسية
            elif data_callback == "back_home":
                tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "⚙️ **لوحة تحكم بوت التبادل الإعلاني**",
                    "parse_mode": "Markdown",
                    "reply_markup": admin_menu(data)
                })

            # 7. أزرار تعديل الأرقام
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
                    "text": "📢 **إدارة القنوات المستهدفة للنشر:**\nاختر التعديل المناسب:",
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
                    "text": "🎯 **إدارة قنوات الترويج (المصادر):**\nاختر التعديل المناسب:",
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
        id_str = str(chat["id"])
        text = (message.get("text") or "").strip()

        if id_str == str(ADMIN_ID) and text == "/start":
            send_admin("⚙️ **لوحة تحكم بوت التبادل الإعلاني**", admin_menu(data))
            return


# =========================================================
#   MAIN LOOP (getUpdates)
# =========================================================

def main():
    print("Bot is running with getUpdates...")
    offset = 0
    data = load_data()

    # حذف الـ Webhook القديم لضمان عمل getUpdates بنجاح
    tg("deleteWebhook", {"drop_pending_updates": True})

    while True:
        try:
            updates = tg("getUpdates", {"offset": offset, "timeout": 30})
            if updates and updates.get("ok"):
                for result in updates.get("result", []):
                    offset = result["update_id"] + 1
                    process_update(data, result)
            time.sleep(1)
        except Exception as e:
            print(f"Polling Error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
