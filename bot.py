from flask import Flask
import threading
import os
import time
import json
import random
import requests

# =========================================================
#   FLASK KEEP-ALIVE SERVER (للابقاء على الخدمة نشطة مجاناً)
# =========================================================

app = Flask('')

@app.route('/')
def home():
    return "Bot is active!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

# تشغيل السيرفر الوهمي في الخلفية أولاً
keep_alive()


# =========================================================
#   BOT SETTINGS
# =========================================================

TOKEN = "624856590:AAEpH8z4RdVxueSiGLXPscWtf1YypaPHDbE"
ADMIN_ID = "1443697465"

DEFAULT_DURATION = 30
DEFAULT_TARGETS = 5
DEFAULT_SOURCES = 3

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")


# =========================================================
#   TELEGRAM
# =========================================================

def tg(method, data=None):
    if data is None:
        data = {}
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    
    try:
        response = requests.post(url, data=data, timeout=45)
        result = response.json()
        return result
    except Exception as e:
        print(f"REQUEST ERROR: {e}")
        return None


# =========================================================
#   DEFAULT DATA
# =========================================================

def default_data():
    return {
        "private": {},
        "groups": {},
        "channels": {},
        "ads": [],
        "personal_ads": [],
        "admin_state": None,
        "round": 0,
        "next_source": 0,
        "running": True,
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


# =========================================================
#   LOAD DATA
# =========================================================

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

    for key, value in default["settings"].items():
        if key not in data["settings"]:
            data["settings"][key] = value

    for key, value in default["stats"].items():
        if key not in data["stats"]:
            data["stats"][key] = value

    return data


# =========================================================
#   SAVE
# =========================================================

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"SAVE ERROR: {e}")


# =========================================================
#   BUTTON
# =========================================================

def button(text, callback):
    return {
        "text": text,
        "callback_data": callback
    }


# =========================================================
#   ADMIN MENU
# =========================================================

def admin_menu(data):
    s = data["settings"]
    run_status = "🟢 التبادل يعمل" if data["running"] else "🔴 التبادل متوقف"

    return {
        "inline_keyboard": [
            [button(f"⏱️ مدة الإعلان: {s['duration']} دقيقة", "duration_menu")],
            [button(f"📢 النشر في: {s['targets']} قنوات", "targets_menu")],
            [button(f"🎯 الترويج لـ: {s['sources']} قنوات", "sources_menu")],
            [button(run_status, "toggle")],
            [button("📢 إعلان شخصي", "personal_ad"), button("📊 الإحصائيات", "stats")],
            [button("🔄 تشغيل جولة الآن", "round_now")]
        ]
    }


# =========================================================
#   SETTINGS MENUS
# =========================================================

def duration_menu():
    return {
        "inline_keyboard": [
            [button("10 دقيقة", "duration_10"), button("20 دقيقة", "duration_20")],
            [button("30 دقيقة", "duration_30"), button("40 دقيقة", "duration_40")],
            [button("50 دقيقة", "duration_50"), button("60 دقيقة", "duration_60")],
            [button("↩️ رجوع", "menu")]
        ]
    }


def targets_menu(data):
    n = data["settings"]["targets"]
    return {
        "inline_keyboard": [
            [button("➖", "targets_minus"), button(f"{n} قناة", "nothing"), button("➕", "targets_plus")],
            [button("↩️ رجوع", "menu")]
        ]
    }


def sources_menu(data):
    n = data["settings"]["sources"]
    return {
        "inline_keyboard": [
            [button("➖", "sources_minus"), button(f"{n} قناة", "nothing"), button("➕", "sources_plus")],
            [button("↩️ رجوع", "menu")]
        ]
    }


# =========================================================
#   ADMIN MESSAGE
# =========================================================

def send_admin(text, keyboard=None):
    payload = {
        "chat_id": ADMIN_ID,
        "text": text
    }
    if keyboard is not None:
        payload["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)

    return tg("sendMessage", payload)


# =========================================================
#   PERSONAL ADMIN AD
# =========================================================

def send_personal_ad(data, text):
    sent = 0
    failed = 0
    data["personal_ads"] = []

    for channel_id, channel in data["channels"].items():
        if not channel.get("active"):
            continue

        result = tg("sendMessage", {
            "chat_id": channel_id,
            "text": text,
            "reply_markup": json.dumps({
                "inline_keyboard": [
                    [{"text": "📢 أبو أسامة", "url": "https://t.me/NBots"}]
                ]
            }, ensure_ascii=False),
            "disable_web_page_preview": True
        })

        if result and result.get("ok") and "result" in result and "message_id" in result["result"]:
            data["personal_ads"].append({
                "chat_id": channel_id,
                "message_id": result["result"]["message_id"]
            })
            sent += 1
        else:
            failed += 1

        time.sleep(0.2)

    save_data(data)
    return {"sent": sent, "failed": failed}


# =========================================================
#   DELETE PERSONAL AD
# =========================================================

def delete_personal_ad(data):
    deleted = 0
    if data.get("personal_ads"):
        for ad in data["personal_ads"]:
            if "chat_id" not in ad or "message_id" not in ad:
                continue
            result = tg("deleteMessage", {
                "chat_id": ad["chat_id"],
                "message_id": ad["message_id"]
            })
            if result and result.get("ok"):
                deleted += 1

    data["personal_ads"] = []
    save_data(data)
    return deleted


# =========================================================
#   CLIENT START
# =========================================================

def send_client_start(chat_id):
    tg("sendMessage", {
        "chat_id": chat_id,
        "text": (
            "👋 أهلاً بك في بوت تبادل القنوات!\n\n"
            "📢 خدمة تبادل الإعلانات بين القنوات.\n\n"
            "🔄 يقوم البوت بتبادل الإعلانات تلقائياً بين القنوات المشتركة في النظام.\n\n"
            "➕ أضف البوت مشرفاً في قناتك ليتم تسجيلها في نظام التبادل.\n\n"
            "💬 للاستفسار أو التواصل مع المطور:"
        ),
        "reply_markup": json.dumps({
            "inline_keyboard": [
                [{"text": "👨‍💻 مراسلة المطور", "url": "https://t.me/uarbot?start=FCHNBot"}]
            ]
        }, ensure_ascii=False)
    })


# =========================================================
#   REGISTER CHANNEL
# =========================================================

def register_channel(data, chat):
    id_str = str(chat["id"])
    title = chat.get("title") or chat.get("username") or "قناة"
    username = chat.get("username")
    link = f"https://t.me/{username}" if username else None

    is_new = id_str not in data["channels"]

    if is_new:
        data["channels"][id_str] = {
            "id": id_str,
            "title": title,
            "username": username,
            "link": link,
            "active": True,
            "failures": 0,
            "delete_count": 0,
            "sent_count": 0,
            "received_count": 0,
            "added_at": int(time.time()),
            "last_sent": 0,
            "last_received": 0
        }
    else:
        data["channels"][id_str]["title"] = title
        data["channels"][id_str]["username"] = username
        data["channels"][id_str]["link"] = link
        data["channels"][id_str]["active"] = True

    save_data(data)

    if is_new:
        send_admin(f"🔔 **تنبيه: إضافة قناة جديدة!**\n\n📢 اسم القناة: {title}\n🆔 الأيدي: `{id_str}`\n🔗 المعرّف: @{username if username else 'بدون'}")
        
        tg("sendMessage", {
            "chat_id": id_str,
            "text": "✅ تم إضافة البوت بنجاح!\n\n📢 تم تسجيل القناة في نظام تبادل الإعلانات."
        })


# =========================================================
#   CREATE RANDOM AD
# =========================================================

def create_ad(channel):
    name = channel["title"]
    link = channel["link"]

    texts = [
        f"✨ قناة تستحق المتابعة!\n\n📢 {name}\nمحتوى جميل ومفيد بانتظارك 👇",
        f"🔥 لا تفوّت هذه القناة!\n\n🌟 {name}\nمحتوى متنوع ومميز يستحق المشاهدة.",
        f"💎 قناة مميزة لمحبي المحتوى الجميل!\n\n📌 {name}\nاكتشف محتوى جديد ومفيد.",
        f"🌹 قناة جميلة قد تعجبك!\n\n📢 {name}\nمحتوى متنوع بانتظارك.",
        f"🚀 اكتشف قناة جديدة اليوم!\n\n⭐ {name}\nمحتوى يستحق أن تراه بنفسك.",
        f"👀 شوف هذه القناة!\n\n📢 {name}\nفيها محتوى جميل ومفيد.",
        f"🎯 اقتراح اليوم:\n\n🌟 {name}\nإذا تحب المحتوى المميز، جرّبها.",
        f"💫 قناة تستحق التجربة!\n\n📢 {name}\nادخل وشوف المحتوى بنفسك.",
        f"⭐ للي يحب المحتوى المميز\n\n📢 {name}\nيمكن تلقى فيها أشياء تعجبك كثير.",
        f"🌟 اكتشاف جديد!\n\n📢 {name}\nقناة متنوعة تستحق الزيارة."
    ]

    return {
        "text": random.choice(texts),
        "link": link
    }


# =========================================================
#   SEND AD
# =========================================================

def send_ad(data, source_id, target_id):
    source = data["channels"][source_id]
    target = data["channels"][target_id]

    if not source.get("link"):
        return {"ok": False, "reason": "no_link"}

    ad = create_ad(source)

    result = tg("sendMessage", {
        "chat_id": target_id,
        "text": ad["text"],
        "reply_markup": json.dumps({
            "inline_keyboard": [
                [{"text": "🔗 دخول القناة", "url": ad["link"]}]
            ]
        }, ensure_ascii=False),
        "disable_web_page_preview": True
    })

    if not result or not result.get("ok"):
        data["channels"][target_id]["failures"] += 1
        data["stats"]["failed"] += 1
        save_data(data)
        reason = result.get("description") if result else "send_failed"
        return {"ok": False, "reason": reason}

    message_id = result["result"]["message_id"]

    data["ads"].append({
        "source": source_id,
        "target": target_id,
        "chat_id": target_id,
        "message_id": message_id,
        "created": int(time.time())
    })

    data["channels"][target_id]["failures"] = 0
    data["channels"][target_id]["received_count"] += 1
    data["channels"][target_id]["last_received"] = int(time.time())

    data["channels"][source_id]["sent_count"] += 1
    data["channels"][source_id]["last_sent"] = int(time.time())

    data["stats"]["sent"] += 1

    save_data(data)
    return {"ok": True, "message_id": message_id}


# =========================================================
#   DELETE ADS
# =========================================================

def delete_ads(data):
    if not data.get("ads"):
        return {"deleted": 0, "failed": 0}

    deleted = 0
    failed = 0

    for ad in data["ads"]:
        result = tg("deleteMessage", {
            "chat_id": ad["chat_id"],
            "message_id": ad["message_id"]
        })
        if result and result.get("ok"):
            deleted += 1
        else:
            failed += 1

    data["ads"] = []
    save_data(data)
    
    send_admin(f"🗑️ **عملية حذف تلقائية:**\nتم مسح الإعلانات القديمة بنجاح.\n- تم حذف: {deleted}\n- فشل حذف: {failed}")
    
    return {"deleted": deleted, "failed": failed}


# =========================================================
#   GET ACTIVE CHANNELS
# =========================================================

def active_channels(data):
    list_res = {}
    for cid, channel in data["channels"].items():
        if channel.get("active") and channel.get("link"):
            list_res[cid] = channel
    return list_res


# =========================================================
#   CHOOSE TARGETS FAIRLY
# =========================================================

def choose_targets(data, source_id, number):
    candidates = []

    for id_str, channel in data["channels"].items():
        if str(id_str) == str(source_id):
            continue
        if not channel.get("active") or not channel.get("link"):
            continue

        score = channel.get("received_count", 0)
        candidates.append({"id": id_str, "score": score})

    candidates.sort(key=lambda x: (x["score"], random.random()))

    result = []
    for candidate in candidates:
        result.append(candidate["id"])
        if len(result) >= number:
            break

    return result


# =========================================================
#   CHOOSE SOURCES FAIRLY
# =========================================================

def choose_sources(data, number):
    channels = active_channels(data)
    if not channels:
        return []

    ids = list(channels.keys())
    count = len(ids)
    start = data["next_source"] % count

    result = []
    for i in range(count):
        if len(result) >= number:
            break
        index = (start + i) % count
        result.append(ids[index])

    data["next_source"] = (start + len(result)) % count
    return result


# =========================================================
#   RUN ROUND
# =========================================================

def run_round(data):
    settings = data["settings"]
    sources = choose_sources(data, settings["sources"])

    if len(sources) == 0:
        send_admin("⚠️ **تنبيه:** تعذر تشغيل الجولة لعدم وجود قنوات نشطة كافية.")
        return

    send_admin(f"🔄 **بدء جولة جديدة...**\nجاري حذف الإعلانات القديمة ونشر الإعلانات الجديدة.")

    delete_info = delete_ads(data)

    data["round"] += 1
    round_num = data["round"]

    report = []
    total_success = 0
    total_failed = 0

    for source_id in sources:
        source = data["channels"][source_id]
        targets = choose_targets(data, source_id, settings["targets"])

        success = 0
        failed = 0

        for target_id in targets:
            result = send_ad(data, source_id, target_id)
            if result["ok"]:
                success += 1
                total_success += 1
            else:
                failed += 1
                total_failed += 1
            time.sleep(0.4)

        report.append({
            "name": source["title"],
            "success": success,
            "failed": failed
        })

    data["stats"]["rounds"] += 1
    save_data(data)

    text = f"📊 **تقرير تفصيلي للجولة #{round_num}**\n\n"
    for r in report:
        text += f"📢 قناة: {r['name']}\n✅ تم النشر بنجاح: {r['success']}\n❌ فشل النشر: {r['failed']}\n\n"

    text += (
        "━━━━━━━━━━━━\n"
        f"🎯 القنوات المروّج لها: {len(sources)}\n"
        f"📢 إجمالي المستهدفين الناجحين: {total_success}\n"
        f"❌ إجمالي الفشل: {total_failed}\n"
        f"🗑️ الحذف التلقائي السابق: {delete_info['deleted']} رسالة\n"
        f"⏱️ مدة الإعلان الحالية: {settings['duration']} دقيقة"
    )

    send_admin(text)
    print(f"✅ انتهت الجولة #{round_num}")


# =========================================================
#   STATS
# =========================================================

def stats_text(data):
    private_count = len(data["private"])
    groups_count = len(data["groups"])
    channels_count = len(data["channels"])
    active = sum(1 for c in data["channels"].values() if c.get("active"))
    ads_count = len(data["ads"])
    total = private_count + groups_count + channels_count

    return (
        "📊 **إحصائيات البوت الشاملة**\n\n"
        f"👤 الأشخاص بالخاص: {private_count}\n"
        f"👥 المجموعات: {groups_count}\n"
        f"📢 القنوات المسجلة: {channels_count}\n"
        f"🟢 القنوات النشطة حالياً: {active}\n\n"
        f"📌 جميع المحادثات المسجلة: {total}\n\n"
        f"🔄 رقم الجولة الحالية: {data['round']}\n"
        f"📨 الإعلانات النشطة الآن: {ads_count}\n\n"
        f"📤 إجمالي المنشورات الناجحة: {data['stats']['sent']}\n"
        f"❌ إجمالي الأخطاء/الفشل: {data['stats']['failed']}"
    )


# =========================================================
#   CALLBACK HANDLER
# =========================================================

def handle_callback(data, callback):
    chat = callback["message"]["chat"]
    chat_id = str(chat["id"])

    if chat_id != str(ADMIN_ID):
        return

    cb_id = callback["id"]
    action = callback["data"]
    message = callback["message"]
    message_id = message["message_id"]

    tg("answerCallbackQuery", {"callback_query_id": cb_id})

    if action == "menu":
        tg("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "⚙️ **لوحة إعدادات نظام التبادل الرئيسية**\n\nاختر الإعداد الذي تريد تغييره:",
            "reply_markup": json.dumps(admin_menu(data), ensure_ascii=False)
        })
        return

    if action == "personal_ad":
        data["admin_state"] = "waiting_personal_ad"
        save_data(data)
        send_admin(
            "📢 **إرسال إعلان شخصي لجميع القنوات**\n\n"
            "أرسل الآن في هذه المحادثة (القروب) **نص الإعلان** الذي تريد نشره.\n\n"
            "سيقوم البوت بنشره فوراً في كل القنوات النشطة مع زر باسم:\n📢 أبو أسامة"
        )
        return

    if action == "delete_personal_ad":
        deleted = delete_personal_ad(data)
        send_admin(f"🗑️ **حذف الإعلان الشخصي:**\nتم تنفيذ الحذف بنجاح. العدد المحذوف: {deleted} قناة.")
        return

    if action == "duration_menu":
        tg("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "⏱️ اختر مدة بقاء الإعلان قبل تدويره:",
            "reply_markup": json.dumps(duration_menu(), ensure_ascii=False)
        })
        return

    if action.startswith("duration_"):
        duration_val = int(action.split("_")[1])
        data["settings"]["duration"] = duration_val
        save_data(data)
        
        send_admin(f"⏱️ **تنبيه تحديث:** تم تغيير مدة بقاء الإعلان بنجاح إلى **{duration_val} دقيقة**.")
        
        tg("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": f"⚙️ تم تغيير مدة الإعلان إلى {duration_val} دقيقة.\n\nلوحة التحكم:",
            "reply_markup": json.dumps(admin_menu(data), ensure_ascii=False)
        })
        return

    if action == "targets_menu":
        tg("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "📢 كم عدد القنوات المستهدفة لنشر إعلان كل قناة فيها؟",
            "reply_markup": json.dumps(targets_menu(data), ensure_ascii=False)
        })
        return

    if action == "targets_plus":
        data["settings"]["targets"] += 1
        save_data(data)
    elif action == "targets_minus":
        if data["settings"]["targets"] > 1:
            data["settings"]["targets"] -= 1
        save_data(data)

    if action in ["targets_plus", "targets_minus"]:
        tg("editMessageReplyMarkup", {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": json.dumps(targets_menu(data), ensure_ascii=False)
        })
        return

    if action == "sources_menu":
        tg("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "🎯 كم قناة يتم اختيارها للترويج لها في الجولة الواحدة؟",
            "reply_markup": json.dumps(sources_menu(data), ensure_ascii=False)
        })
        return

    if action == "sources_plus":
        data["settings"]["sources"] += 1
        save_data(data)
    elif action == "sources_minus":
        if data["settings"]["sources"] > 1:
            data["settings"]["sources"] -= 1
        save_data(data)

    if action in ["sources_plus", "sources_minus"]:
        tg("editMessageReplyMarkup", {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": json.dumps(sources_menu(data), ensure_ascii=False)
        })
        return

    if action == "toggle":
        data["running"] = not data["running"]
        save_data(data)
        status_text_msg = "🟢 تم تفعيل نظام التبادل." if data["running"] else "🔴 تم إيقاف نظام التبادل مؤقتاً."
        send_admin(status_text_msg)
        
        tg("editMessageReplyMarkup", {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": json.dumps(admin_menu(data), ensure_ascii=False)
        })
        return

    if action == "stats":
        send_admin(stats_text(data))
        return

    if action == "round_now":
        send_admin("🔄 **طلب يدوي:** جاري تشغيل جولة فورية الآن...")
        run_round(data)
        return


# =========================================================
#   PROCESS UPDATE
# =========================================================

def process_update(data, update):
    if "callback_query" in update:
        handle_callback(data, update["callback_query"])
        return

    if "my_chat_member" in update:
        chat = update["my_chat_member"]["chat"]
        if chat.get("type") != "channel":
            return

        status = update["my_chat_member"].get("new_chat_member", {}).get("status", "")
        id_str = str(chat["id"])

        if status in ["administrator", "creator"]:
            register_channel(data, chat)
            return

        if status in ["left", "kicked"]:
            if id_str in data["channels"]:
                data["channels"][id_str]["active"] = False
                save_data(data)
                channel_name = data["channels"][id_str].get("title", id_str)
                send_admin(f"⚠️ **تنبيه مغادرة/حذف البوت:**\nتم طرد البوت أو فقدان الصلاحيات في قناة: `{channel_name}`")
            return

    if "message" in update:
        message = update["message"]
        chat = message["chat"]
        id_str = str(chat["id"])
        chat_type = chat["type"]
        text = (message.get("text") or "").strip()

        if chat_type == "private":
            data["private"][id_str] = True
        elif chat_type in ["group", "supergroup"]:
            data["groups"][id_str] = True

        save_data(data)

        if (
            id_str == str(ADMIN_ID) and
            data.get("admin_state") == "waiting_personal_ad" and
            text != ""
        ):
            data["admin_state"] = None
            save_data(data)

            send_admin("📢 جاري إرسال الإعلان الشخصي لكل القنوات النشطة...")
            result = send_personal_ad(data, text)

            send_admin(
                f"✅ **تم الانتهاء من الإعلان الشخصي:**\n\n"
                f"📤 تم الإرسال بنجاح إلى: {result['sent']} قناة\n"
                f"❌ فشل الإرسال في: {result['failed']} قناة",
                {
                    "inline_keyboard": [
                        [button("🗑️ حذف هذا الإعلان", "delete_personal_ad")],
                        [button("↩️ العودة للوحة التحكم", "menu")]
                    ]
                }
            )
            return

        if (
            id_str == str(ADMIN_ID) and
            text == "/start"
        ):
            send_admin("⚙️ **لوحة تحكم بوت التبادل الإعلاني**\n\nاختر من الأزرار بالأسفل للتحكم بكافة الإعدادات:", admin_menu(data))
            return

        if (
            chat_type == "private" and
            (text == "/start" or text.startswith("/start "))
        ):
            send_client_start(id_str)
            return


# =========================================================
#   MAIN START LOOP
# =========================================================

if __name__ == "__main__":
    print("\n====================================")
    print("   📢 EXCHANGE BOT (GROUP MANAGED)")
    print("====================================")

    tg("deleteWebhook", {"drop_pending_updates": False})

    data = load_data()

    initial = tg("getUpdates", {"offset": -1, "timeout": 1})
    offset = 0
    if initial and initial.get("result"):
        last = initial["result"][-1]
        offset = last["update_id"] + 1

    next_round = int(time.time()) + (data["settings"]["duration"] * 60)

    print("🟢 البوت يعمل الآن بكامل الميزات ويرسل التقارير للقروب...")

    while True:
        try:
            updates = tg("getUpdates", {
                "offset": offset,
                "timeout": 25,
                "allowed_updates": json.dumps(["message", "callback_query", "my_chat_member"])
            })

            if updates and updates.get("result"):
                for update in updates["result"]:
                    offset = update["update_id"] + 1
                    process_update(data, update)

            if data["running"] and int(time.time()) >= next_round:
                run_round(data)
                next_round = int(time.time()) + (data["settings"]["duration"] * 60)

        except Exception as e:
            print(f"LOOP ERROR: {e}")
            time.sleep(2)

        time.sleep(0.2)
