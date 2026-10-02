# =====================================================
#   HULU PAY — Referral & Task Bot (Amharic)
#   ሙሉ በአማርኛ | 4 Mandatory Channels | Task System
# =====================================================

import re
import time
import sqlite3
import telebot
from telebot import types

# ============ CONFIG ============
BOT_TOKEN = "8787473431:AAEFDykTUNiEAiPGd5Q_7lR1nQOZtC3WwmE"
BOT_USERNAME = "HuluPayET_bot"

ADMIN_IDS = [7783622296]

MANDATORY_CHANNELS = [
    {"id": "@Sheger_tech1",       "name": "📢 Sheger Tech"},
    {"id": "@ethiocashflow",      "name": "📢 Ethio Cash Flow"},
    {"id": "@AmanIncomeLab",      "name": "📢 Aman Income Lab"},
    {"id": "@OnlineIncomeHub07",  "name": "📢 Online Income Hub"},
]

WITHDRAW_CHANNEL = "@OnlineIncomeHub07"

REFERRAL_BONUS  = 3.0          # ብር / ሪፈራል
BONUS_AMOUNT    = 1.0          # የቀን ቦነስ
BONUS_INTERVAL  = 24 * 3600    # 24 ሰዓት
MIN_WITHDRAW    = 50.0         # ዝቅተኛ ዊዝድሮ
MIN_WITHDRAW_TASK = 20.0       # ዝቅተኛ ለታስክ (አማራጭ)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# ============ DATABASE ============
conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()

def init_db():
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id       INTEGER PRIMARY KEY,
        username      TEXT,
        first_name    TEXT,
        referrer_id   INTEGER,
        balance       REAL DEFAULT 0,
        wallet_type   TEXT,
        wallet_number TEXT,
        last_bonus    REAL DEFAULT 0,
        joined_at     REAL,
        verified      INTEGER DEFAULT 0,
        is_banned     INTEGER DEFAULT 0
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS withdrawals (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id       INTEGER,
        amount        REAL,
        wallet_type   TEXT,
        wallet_number TEXT,
        status        TEXT DEFAULT 'pending',
        created_at    REAL
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT,
        description TEXT,
        reward      REAL,
        url         TEXT,
        is_active   INTEGER DEFAULT 1,
        created_at  REAL
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS task_completions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        task_id     INTEGER,
        status      TEXT DEFAULT 'pending',
        created_at  REAL
    )""")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_ref  ON users(referrer_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_wd   ON withdrawals(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tc   ON task_completions(user_id)")
    conn.commit()

init_db()

# ---------- DB HELPERS ----------
def get_user(uid):
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()

def create_user(uid, username, first_name, ref=None):
    if get_user(uid):
        return False
    cur.execute("""INSERT INTO users
        (user_id,username,first_name,referrer_id,joined_at,verified)
        VALUES (?,?,?,?,?,0)""",
        (uid, username, first_name, ref, time.time()))
    conn.commit()
    return True

def mark_verified(uid):
    cur.execute("UPDATE users SET verified=1 WHERE user_id=?", (uid,))
    conn.commit()

def add_balance(uid, amount):
    cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
    conn.commit()

def set_wallet(uid, wtype, wnumber):
    cur.execute("UPDATE users SET wallet_type=?, wallet_number=? WHERE user_id=?",
                (wtype, wnumber, uid))
    conn.commit()

def set_last_bonus(uid):
    cur.execute("UPDATE users SET last_bonus=? WHERE user_id=?", (time.time(), uid))
    conn.commit()

def count_referrals(uid):
    cur.execute("SELECT COUNT(*) FROM users WHERE referrer_id=? AND verified=1", (uid,))
    return cur.fetchone()[0]

def get_referrals(uid):
    cur.execute("""SELECT user_id, username, first_name
                   FROM users WHERE referrer_id=? AND verified=1""", (uid,))
    return cur.fetchall()

def top_referrers(limit=10):
    cur.execute("""SELECT first_name, username, user_id,
                   (SELECT COUNT(*) FROM users u2
                    WHERE u2.referrer_id=u1.user_id AND u2.verified=1) AS c
                   FROM users u1
                   ORDER BY c DESC, u1.joined_at ASC LIMIT ?""", (limit,))
    return cur.fetchall()

def create_withdrawal(uid, amount, wtype, wnumber):
    cur.execute("""INSERT INTO withdrawals
        (user_id,amount,wallet_type,wallet_number,created_at)
        VALUES (?,?,?,?,?)""",
        (uid, amount, wtype, wnumber, time.time()))
    conn.commit()
    return cur.lastrowid

def update_withdrawal(wid, status):
    cur.execute("UPDATE withdrawals SET status=? WHERE id=?", (status, wid))
    conn.commit()

def get_withdrawal(wid):
    cur.execute("SELECT * FROM withdrawals WHERE id=?", (wid,))
    return cur.fetchone()

def total_users():
    cur.execute("SELECT COUNT(*) FROM users"); return cur.fetchone()[0]

def total_paid():
    cur.execute("SELECT COALESCE(SUM(amount),0) FROM withdrawals WHERE status='paid'")
    return cur.fetchone()[0]

def all_users(limit=50, offset=0):
    cur.execute("""SELECT user_id, username, first_name, balance
                   FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?""",
                (limit, offset))
    return cur.fetchall()

# ---------- TASKS ----------
def add_task(title, description, reward, url):
    cur.execute("""INSERT INTO tasks (title,description,reward,url,created_at)
                   VALUES (?,?,?,?,?)""",
                (title, description, reward, url, time.time()))
    conn.commit()
    return cur.lastrowid

def list_tasks(active_only=True):
    q = "SELECT * FROM tasks"
    if active_only: q += " WHERE is_active=1"
    q += " ORDER BY id DESC"
    cur.execute(q)
    return cur.fetchall()

def get_task(tid):
    cur.execute("SELECT * FROM tasks WHERE id=?", (tid,))
    return cur.fetchone()

def delete_task(tid):
    cur.execute("DELETE FROM tasks WHERE id=?", (tid,))
    conn.commit()

def already_done(uid, tid):
    cur.execute("""SELECT id FROM task_completions
                   WHERE user_id=? AND task_id=? AND status IN ('pending','approved')""",
                (uid, tid))
    return cur.fetchone() is not None

def create_completion(uid, tid):
    cur.execute("""INSERT INTO task_completions (user_id,task_id,created_at)
                   VALUES (?,?,?)""", (uid, tid, time.time()))
    conn.commit()
    return cur.lastrowid

def get_completion(cid):
    cur.execute("SELECT * FROM task_completions WHERE id=?", (cid,))
    return cur.fetchone()

def update_completion(cid, status):
    cur.execute("UPDATE task_completions SET status=? WHERE id=?", (status, cid))
    conn.commit()

# ============ HELPERS ============
def is_admin(uid): return uid in ADMIN_IDS

def is_banned(uid):
    u = get_user(uid)
    return bool(u and u[10])

def check_channels(uid):
    """ያልተቀላቀላቸውን ቻናሎች ይመልሳል"""
    missing = []
    for ch in MANDATORY_CHANNELS:
        try:
            m = bot.get_chat_member(ch["id"], uid)
            if m.status not in ("member", "administrator", "creator"):
                missing.append(ch)
        except Exception as e:
            # ቦቱ አድሚን ካልሆነ ወይም ቻናል ከሌለ
            print(f"[CH CHECK ERROR] {ch['id']}: {e}")
            missing.append(ch)
    return missing

def join_keyboard(missing):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for ch in missing:
        kb.add(types.InlineKeyboardButton(
            ch["name"], url=f"https://t.me/{ch['id'].lstrip('@')}"))
    kb.add(types.InlineKeyboardButton("✅ አረጋግጠ", callback_data="verify"))
    return kb

def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💰 ባላንስ",   callback_data="balance"),
        types.InlineKeyboardButton("👛 ዋሌት",    callback_data="wallet"),
        types.InlineKeyboardButton("👥 ሪፈራል",   callback_data="referral"),
        types.InlineKeyboardButton("💸 ዊዝድሮ",  callback_data="withdraw"),
        types.InlineKeyboardButton("📋 ታስክ",    callback_data="task"),
        types.InlineKeyboardButton("🎁 ቦነስ",    callback_data="bonus"),
    )
    return kb

def wallet_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🏦 ሲቢኢ (CBE)",   callback_data="wal_cbe"),
        types.InlineKeyboardButton("📱 ቴሌብር",       callback_data="wal_tele"),
        types.InlineKeyboardButton("🔙 ተመለስ",       callback_data="back_main"),
    )
    return kb

def back_main_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="back_main"))
    return kb

def show_welcome(uid, name):
    text = (
        f"🎊 እንኳን ደህና መጡ *{name}*!\n\n"
        f"🤖 ይህ *Hulu Pay* የሪፈራል ቦት ነው።\n"
        f"👥 ሰዎችን ጋብዘህ ገቢ አግኝ።\n\n"
        f"💰 በአንድ ሪፈራል: *{REFERRAL_BONUS} ብር*\n"
        f"🎁 የቀን ቦነስ: *{BONUS_AMOUNT} ብር*\n"
        f"📋 ታስኮች: በአድሚን የሚታደሱ\n"
        f"💸 ዝቅተኛ ዊዝድሮ: *{MIN_WITHDRAW:.0f} ብር*\n\n"
        f"📌 ከታች ያለውን ምረጥ፦"
    )
    bot.send_message(uid, text, reply_markup=main_menu())

# ============ /start ============
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    uid = msg.from_user.id
    if is_banned(uid):
        bot.send_message(uid, "🚫 ከቦቱ ታግደዋል።")
        return

    username = msg.from_user.username or ""
    first    = msg.from_user.first_name or "ተጠቃሚ"

    # ሪፈራል አውጣ
    args = msg.text.split()
    ref = None
    if len(args) > 1 and args[1].startswith("ref"):
        try:
            r = int(args[1][3:])
            if r != uid and get_user(r):
                ref = r
        except: pass

    existing = get_user(uid)
    if not existing:
        create_user(uid, username, first, ref)

    # ቻናሎች ተረጋግጥ
    missing = check_channels(uid)
    if missing:
        bot.send_message(uid,
            "👋 እንኳን ደህና መጡ!\n\n"
            "📌 ቦቱን ለመጠቀም መጀመሪያ ከታች ያሉትን ቻናሎች ይቀላቀሉ።\n"
            "ከዛ *አረጋግጠ* ይጫኑ።",
            reply_markup=join_keyboard(missing))
        return

    # ሁሉንም ተቀላቅሏል → verified + ሪፈራል ቦነስ
    if existing and existing[9] == 0:
        mark_verified(uid)
        if existing[3]:  # referrer_id
            add_balance(existing[3], REFERRAL_BONUS)
            try:
                bot.send_message(existing[3],
                    f"🎉 *አዲስ ሪፈራል!*\n"
                    f"💰 +{REFERRAL_BONUS} ብር ተጨምሯል።")
            except: pass
    elif existing is None:
        mark_verified(uid)
        if ref:
            add_balance(ref, REFERRAL_BONUS)
            try:
                bot.send_message(ref,
                    f"🎉 *አዲስ ሪፈራል!*\n"
                    f"💰 +{REFERRAL_BONUS} ብር ተጨምሯል።")
            except: pass

    show_welcome(uid, first)

# ============ VERIFY ============
@bot.callback_query_handler(func=lambda c: c.data == "verify")
def cb_verify(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "🚫 ታግደዋል", show_alert=True); return

    missing = check_channels(uid)
    if missing:
        bot.answer_callback_query(call.id, "❌ ገና አልተቀላቀልክም!", show_alert=True)
        names = "\n".join(f"• {c['name']}" for c in missing)
        bot.send_message(uid,
            f"⚠️ *ያልተቀላቀልካቸው ቻናሎች:*\n\n{names}\n\n"
            f"ተቀላቅለህ *አረጋግጠ* ይጫኑ።",
            reply_markup=join_keyboard(missing))
        return

    bot.answer_callback_query(call.id, "✅ ተረጋግጧል!")

    # verified አድርግ + ሪፈራል ቦነስ
    u = get_user(uid)
    if u and u[9] == 0:
        mark_verified(uid)
        if u[3]:
            add_balance(u[3], REFERRAL_BONUS)
            try:
                bot.send_message(u[3],
                    f"🎉 *አዲስ ሪፈራል!*\n"
                    f"💰 +{REFERRAL_BONUS} ብር ተጨምሯል።")
            except: pass

    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    show_welcome(uid, call.from_user.first_name or "ተጠቃሚ")

# ============ MAIN MENU ============
@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back(call):
    if is_banned(call.from_user.id):
        bot.answer_callback_query(call.id); return
    bot.answer_callback_query(call.id)
    try: bot.delete_message(call.from_user.id, call.message.message_id)
    except: pass
    show_welcome(call.from_user.id, call.from_user.first_name or "ተጠቃሚ")

@bot.callback_query_handler(func=lambda c: c.data == "balance")
def cb_balance(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id); return
    u = get_user(uid)
    if not u: return
    text = (
        f"💰 *የእርስዎ ባላንስ*\n\n"
        f"┌ 💵 ባላንስ: *{u[4]:.2f} ብር*\n"
        f"├ 👥 ሪፈራሎች: *{count_referrals(uid)}*\n"
        f"└ 💸 ዝቅተኛ ዊዝድሮ: *{MIN_WITHDRAW:.0f} ብር*"
    )
    bot.answer_callback_query(call.id)
    bot.send_message(uid, text, reply_markup=back_main_kb())

@bot.callback_query_handler(func=lambda c: c.data == "referral")
def cb_referral(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id); return
    link = f"https://t.me/{BOT_USERNAME}?start=ref{uid}"
    text = (
        f"👥 *የእርስዎ ሪፈራል ሊንክ*\n\n"
        f"`{link}`\n\n"
        f"💵 በአንድ ሪፈራል: *{REFERRAL_BONUS} ብር*\n"
        f"📊 የጋበዙት: *{count_referrals(uid)}*\n\n"
        f"🔗 ሊንኩን ለጓደኞችዎ ይላኩ።\n"
        f"ጓደኛዎ ሁሉንም ቻናሎች ሲቀላቀል ብቻ ቦነሱ ይጨመራል።"
    )
    bot.answer_callback_query(call.id)
    bot.send_message(uid, text, reply_markup=back_main_kb())

# ============ BONUS ============
@bot.callback_query_handler(func=lambda c: c.data == "bonus")
def cb_bonus(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id); return
    u = get_user(uid)
    if not u:
        bot.answer_callback_query(call.id); return

    last = u[7] or 0
    now = time.time()
    elapsed = now - last

    if last > 0 and elapsed < BONUS_INTERVAL:
        remain = int(BONUS_INTERVAL - elapsed)
        h, m = remain // 3600, (remain % 3600) // 60
        bot.answer_callback_query(call.id,
            f"⏳ ገና {h} ሰዓት {m} ደቂቃ ቀርቷል", show_alert=True)
        return

    add_balance(uid, BONUS_AMOUNT)
    set_last_bonus(uid)
    new_bal = u[4] + BONUS_AMOUNT
    bot.answer_callback_query(call.id, f"🎁 +{BONUS_AMOUNT} ብር!", show_alert=True)
    bot.send_message(uid,
        f"🎁 *የቀን ቦነስ ተቀብለዋል!*\n\n"
        f"💰 +{BONUS_AMOUNT:.2f} ብር\n"
        f"📊 አዲስ ባላንስ: *{new_bal:.2f} ብር*\n\n"
        f"⏰ በ24 ሰዓት ውስጥ እንደገና ይሞክሩ።",
        reply_markup=back_main_kb())

# ============ WALLET ============
@bot.callback_query_handler(func=lambda c: c.data == "wallet")
def cb_wallet(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id); return
    u = get_user(uid)
    cur_w = "❌ አልተገናኘም"
    if u and u[5]:
        cur_w = f"✅ {u[5]} — `{u[6]}`"
    bot.answer_callback_query(call.id)
    bot.send_message(uid,
        f"👛 *ዋሌት ማስተዳደር*\n\n"
        f"የአሁኑ ዋሌት: {cur_w}\n\n"
        f"አዲስ ዋሌት ለማስገባት ይምረጡ፦",
        reply_markup=wallet_menu())

@bot.callback_query_handler(func=lambda c: c.data in ("wal_cbe", "wal_tele"))
def cb_wallet_type(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id); return
    bot.answer_callback_query(call.id)

    if call.data == "wal_cbe":
        bot.send_message(uid,
            "🏦 *ሲቢኢ (CBE)*\n\n"
            "የሂሳብ ቁጥርዎን ይላኩ።\n"
            "📌 *13 አሃዝ* መሆን አለበት\n"
            "📌 በ *1000* መጀመር አለበት\n\n"
            "ለምሳሌ: `1000123456789`\n\n"
            "❌ ለመሰረዝ /start ይጫኑ")
        bot.register_next_step_handler_by_chat_id(uid, save_wallet_cbe)
    else:
        bot.send_message(uid,
            "📱 *ቴሌብር*\n\n"
            "የስልክ ቁጥርዎን ይላኩ።\n"
            "📌 *10 አሃዝ* መሆን አለበት\n"
            "📌 በ *09* መጀመር አለበት\n\n"
            "ለምሳሌ: `0912345678`\n\n"
            "❌ ለመሰረዝ /start ይጫኑ")
        bot.register_next_step_handler_by_chat_id(uid, save_wallet_tele)

def save_wallet_cbe(msg):
    uid = msg.from_user.id
    num = (msg.text or "").strip()
    if not re.fullmatch(r"1000\d{9}", num):
        bot.send_message(uid,
            "❌ *ትክክል ያልሆነ ቁጥር!*\n\n"
            "13 አሃዝ እና በ1000 መጀመር አለበት።\n"
            "እንደገና ይሞክሩ /start")
        return
    set_wallet(uid, "ሲቢኢ", num)
    bot.send_message(uid,
        f"✅ *ዋሌት ተገናኝቷል!*\n\n🏦 ሲቢኢ\n`{num}`",
        reply_markup=back_main_kb())

def save_wallet_tele(msg):
    uid = msg.from_user.id
    num = (msg.text or "").strip()
    if not re.fullmatch(r"09\d{8}", num):
        bot.send_message(uid,
            "❌ *ትክክል ያልሆነ ቁጥር!*\n\n"
            "10 አሃዝ እና በ09 መጀመር አለበት።\n"
            "እንደገና ይሞክሩ /start")
        return
    set_wallet(uid, "ቴሌብር", num)
    bot.send_message(uid,
        f"✅ *ዋሌት ተገናኝቷል!*\n\n📱 ቴሌብር\n`{num}`",
        reply_markup=back_main_kb())

# ============ WITHDRAW ============
@bot.callback_query_handler(func=lambda c: c.data == "withdraw")
def cb_withdraw(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id); return
    u = get_user(uid)
    if not u:
        bot.answer_callback_query(call.id); return

    if not u[5]:
        bot.answer_callback_query(call.id, "❌ መጀመሪያ ዋሌት አገናኝ!", show_alert=True)
        bot.send_message(uid,
            "⚠️ *ዋሌት አልተገናኘም!*\n\n"
            "ዊዝድሮ ለማድረግ መጀመሪያ ዋሌት ማገናኘት ያስፈልጋል።",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("👛 ዋሌት አገናኝ", callback_data="wallet")))
        return

    if u[4] < MIN_WITHDRAW:
        bot.answer_callback_query(call.id, "❌ ባላንስ አይበቃም!", show_alert=True)
        bot.send_message(uid,
            f"⚠️ *ባላንስ አይበቃም*\n\n"
            f"💰 ያለዎት: *{u[4]:.2f} ብር*\n"
            f"📌 ዝቅተኛ: *{MIN_WITHDRAW:.0f} ብር*\n"
            f"❌ የቀረ: *{MIN_WITHDRAW - u[4]:.2f} ብር*",
            reply_markup=back_main_kb())
        return

    bot.answer_callback_query(call.id)
    bot.send_message(uid,
        f"💸 *ዊዝድሮ ጥያቄ*\n\n"
        f"💰 ባላንስ: *{u[4]:.2f} ብር*\n"
        f"📌 ዝቅተኛ: *{MIN_WITHDRAW:.0f} ብር*\n"
        f"👛 ዋሌት: *{u[5]}* — `{u[6]}`\n\n"
        f"ስንት ብር ማውጣት ይፈልጋሉ? ቁጥር ብቻ ይላኩ፦")
    bot.register_next_step_handler_by_chat_id(uid, process_withdraw_amount)

def process_withdraw_amount(msg):
    uid = msg.from_user.id
    try:
        amount = float((msg.text or "").strip())
    except:
        bot.send_message(uid, "❌ ቁጥር ብቻ ይላኩ። /start")
        return
    u = get_user(uid)
    if not u: return

    if amount < MIN_WITHDRAW:
        bot.send_message(uid, f"❌ ዝቅተኛ ዊዝድሮ *{MIN_WITHDRAW:.0f} ብር* ነው።")
        return
    if amount > u[4]:
        bot.send_message(uid, f"❌ ባላንስ አይበቃም። ያለዎት: *{u[4]:.2f} ብር*")
        return

    add_balance(uid, -amount)
    wid = create_withdrawal(uid, amount, u[5], u[6])

    text = (
        f"💸 *አዲስ የዊዝድሮ ጥያቄ* #{wid}\n\n"
        f"👤 ስም: {u[2]}\n"
        f"🆔 አይዲ: `{uid}`\n"
        f"💰 መጠን: *{amount:.2f} ብር*\n"
        f"👛 ዋሌት: {u[5]}\n"
        f"🔢 ቁጥር: `{u[6]}`\n"
        f"📊 ቀሪ ባላንስ: {u[4]-amount:.2f} ብር"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ ተከፍሏል", callback_data=f"wd_paid_{wid}"),
        types.InlineKeyboardButton("❌ ውድቅ",   callback_data=f"wd_rej_{wid}"),
    )
    try:
        bot.send_message(WITHDRAW_CHANNEL, text, reply_markup=kb)
    except Exception as e:
        add_balance(uid, amount)
        bot.send_message(uid, "❌ ስህተት ተፈጠረ። እንደገና ይሞክሩ።")
        print("Withdraw post error:", e)
        return

    bot.send_message(uid,
        f"✅ *የዊዝድሮ ጥያቄዎ ተልኳል!*\n\n"
        f"🆔 ቁጥር: #{wid}\n"
        f"💰 መጠን: *{amount:.2f} ብር*\n"
        f"👛 ዋሌት: {u[5]}\n\n"
        f"⏳ በ24 ሰዓት ውስጥ ይከፈላል።",
        reply_markup=back_main_kb())

# ============ ADMIN: WITHDRAW ACTION ============
@bot.callback_query_handler(func=lambda c: c.data.startswith("wd_"))
def cb_wd_action(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ አድሚን ብቻ!", show_alert=True); return

    parts = call.data.split("_")
    action, wid = parts[1], int(parts[2])
    w = get_withdrawal(wid)
    if not w:
        bot.answer_callback_query(call.id, "❌ አልተገኘም", show_alert=True); return
    if w[5] != "pending":
        bot.answer_callback_query(call.id, "⚠️ አስቀድሞ ተሰርቷል", show_alert=True); return

    if action == "paid":
        update_withdrawal(wid, "paid")
        bot.answer_callback_query(call.id, "✅ ተከፍሏል", show_alert=True)
        try:
            bot.edit_message_text(call.message.text + "\n\n✅ *ተከፍሏል*",
                chat_id=call.message.chat.id, message_id=call.message.message_id)
        except: pass
        try:
            bot.send_message(w[1],
                f"✅ *ዊዝድሮ ተከፍሏል!*\n\n"
                f"🆔 #{wid}\n💰 {w[2]:.2f} ብር\n"
                f"👛 {w[3]} — `{w[4]}`\n\n"
                f"አመሰግናለሁ! 🙏")
        except: pass

    elif action == "rej":
        update_withdrawal(wid, "rejected")
        add_balance(w[1], w[2])
        bot.answer_callback_query(call.id, "❌ ውድቅ", show_alert=True)
        try:
            bot.edit_message_text(call.message.text + "\n\n❌ *ውድቅ ተደርጓል*",
                chat_id=call.message.chat.id, message_id=call.message.message_id)
        except: pass
        try:
            bot.send_message(w[1],
                f"❌ *ዊዝድሮ ውድቅ ተደርጓል*\n\n"
                f"🆔 #{wid}\n💰 {w[2]:.2f} ብር ወደ ባላንስዎ ተመልሷል።\n"
                f"ለተፈጠረው ችግር ይቅርታ።")
        except: pass

# ============ TASKS (USER) ============
@bot.callback_query_handler(func=lambda c: c.data == "task")
def cb_task(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id); return
    tasks = list_tasks()
    bot.answer_callback_query(call.id)

    if not tasks:
        bot.send_message(uid,
            "📋 *ታስኮች*\n\n"
            "🔜 በቅርቡ ታስኮች ይመጣሉ...\n"
            "በዚህ ጊዜ በሪፈራል እና በቦነስ ገቢ ያግኙ።",
            reply_markup=back_main_kb())
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    for t in tasks:
        tid, title, desc, reward, url, active, _ = t
        kb.add(types.InlineKeyboardButton(
            f"📌 {title} — {reward:.2f} ብር", callback_data=f"task_view_{tid}"))
    kb.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="back_main"))
    bot.send_message(uid,
        f"📋 *ያሉ ታስኮች* ({len(tasks)})\n\n"
        f"አንዱን ምርጠው ይስሩ፣ ከዛ አድሚን ያረጋግጣል።",
        reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("task_view_"))
def cb_task_view(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id); return
    tid = int(call.data.replace("task_view_", ""))
    t = get_task(tid)
    if not t:
        bot.answer_callback_query(call.id, "❌ አልተገኘም", show_alert=True); return

    _, title, desc, reward, url, active, _ = t
    if not active:
        bot.answer_callback_query(call.id, "❌ ታስኩ ተዘግቷል", show_alert=True); return

    if already_done(uid, tid):
        bot.answer_callback_query(call.id, "⚠️ አስቀድመው ሰርተዋል", show_alert=True)
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    if url:
        kb.add(types.InlineKeyboardButton("🔗 ታስኩን ክፈት", url=url))
    kb.add(types.InlineKeyboardButton("✅ አደረግሁ", callback_data=f"task_done_{tid}"))
    kb.add(types.InlineKeyboardButton("🔙 ተመለስ", callback_data="task"))

    text = (
        f"📋 *{title}*\n\n"
        f"{desc or '—'}\n\n"
        f"💰 ሽልማት: *{reward:.2f} ብር*\n\n"
        f"ታስኩን ሰርተው ጨርሰው *✅ አደረግሁ* ይጫኑ።\n"
        f"አድሚን ያረጋግጣል።"
    )
    bot.answer_callback_query(call.id)
    bot.send_message(uid, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("task_done_"))
def cb_task_done(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id); return
    tid = int(call.data.replace("task_done_", ""))
    t = get_task(tid)
    if not t:
        bot.answer_callback_query(call.id, "❌"); return
    if already_done(uid, tid):
        bot.answer_callback_query(call.id, "⚠️ አስቀድመው ሰርተዋል", show_alert=True); return

    cid = create_completion(uid, tid)
    bot.answer_callback_query(call.id, "✅ ለአድሚን ተልኳል!", show_alert=True)

    u = get_user(uid)
    _, title, desc, reward, url, active, _ = t

    # ለአድሚን ላክ
    for admin in ADMIN_IDS:
        try:
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"ta_ok_{cid}"),
                types.InlineKeyboardButton("❌ ውድቅ",  callback_data=f"ta_no_{cid}"),
            )
            bot.send_message(admin,
                f"📋 *አዲስ የታስክ ጥያቄ* #{cid}\n\n"
                f"👤 ስም: {u[2]}\n"
                f"🆔 አይዲ: `{uid}`\n"
                f"📛 ዩዘርኔም: @{u[1] or '—'}\n\n"
                f"📌 ታስክ: *{title}*\n"
                f"💰 ሽልማት: *{reward:.2f} ብር*",
                reply_markup=kb)
        except: pass

    bot.send_message(uid,
        f"✅ *ጥያቄዎ ለአድሚን ተልኳል!*\n\n"
        f"📌 {title}\n"
        f"💰 ሽልማት: {reward:.2f} ብር\n\n"
        f"⏳ አድሚን ሲያረጋግጥ ባላንስዎ ይጨመራል።",
        reply_markup=back_main_kb())

# ---------- TASK: ADMIN ACTION ----------
@bot.callback_query_handler(func=lambda c: c.data.startswith("ta_"))
def cb_task_action(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ አድሚን ብቻ!", show_alert=True); return
    parts = call.data.split("_")
    action, cid = parts[1], int(parts[2])
    tc = get_completion(cid)
    if not tc:
        bot.answer_callback_query(call.id, "❌"); return
    if tc[3] != "pending":
        bot.answer_callback_query(call.id, "⚠️ ተሰርቷል", show_alert=True); return

    uid, tid = tc[1], tc[2]
    t = get_task(tid)
    reward = t[3] if t else 0

    if action == "ok":
        update_completion(cid, "approved")
        add_balance(uid, reward)
        bot.answer_callback_query(call.id, "✅ ጸድቋል", show_alert=True)
        try:
            bot.edit_message_text(call.message.text + "\n\n✅ *ጸድቋል*",
                chat_id=call.message.chat.id, message_id=call.message.message_id)
        except: pass
        try:
            bot.send_message(uid,
                f"🎉 *የታስክ ሽልማት ተቀብለዋል!*\n\n"
                f"📌 {t[1] if t else ''}\n"
                f"💰 +{reward:.2f} ብር")
        except: pass

    else:
        update_completion(cid, "rejected")
        bot.answer_callback_query(call.id, "❌ ውድቅ", show_alert=True)
        try:
            bot.edit_message_text(call.message.text + "\n\n❌ *ውድቅ ተደርጓል*",
                chat_id=call.message.chat.id, message_id=call.message.message_id)
        except: pass
        try:
            bot.send_message(uid,
                f"❌ *የታስክ ጥያቄዎ ውድቅ ተደርጓል*")
        except: pass

# ============ ADMIN PANEL ============
@bot.message_handler(commands=["admin"])
def cmd_admin(msg):
    uid = msg.from_user.id
    if not is_admin(uid): return
    total = total_users()
    paid  = total_paid()
    tasks = len(list_tasks(active_only=False))
    text = (
        f"👑 *የአድሚን ፓነል — Hulu Pay*\n\n"
        f"👥 ጠቅላላ ተጠቃሚዎች: *{total}*\n"
        f"💸 ጠቅላላ የተከፈለ: *{paid:.2f} ብር*\n"
        f"📋 ጠቅላላ ታስኮች: *{tasks}*\n\n"
        f"📋 *ትዕዛዞች:*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"*ታስክ:*\n"
        f"/addtask — ታስክ ጨምር\n"
        f"/tasks — ታስኮችን ይመልከቱ\n"
        f"/deltask <id> — ታስክ አጥፋ\n"
        f"━━━━━━━━━━━━━━━\n"
        f"*ተጠቃሚ:*\n"
        f"/users — የተጠቃሚዎች ዝርዝር\n"
        f"/top — ከፍተኛ ሪፈረሮች\n"
        f"/user <id> — የአንድ ተጠቃሚ ዝርዝር\n"
        f"/add <id> <amount> — ባላንስ ጨምር\n"
        f"/sub <id> <amount> — ባላንስ ቀንስ\n"
        f"/ban <id> — አግድ\n"
        f"/unban <id> — ክፈት\n"
        f"/broadcast <text> — ለሁሉም ላክ\n"
        f"/stats — ስታቲስቲክስ"
    )
    bot.send_message(uid, text)

# ---------- ADMIN: TASKS ----------
@bot.message_handler(commands=["addtask"])
def cmd_addtask(msg):
    if not is_admin(msg.from_user.id): return
    bot.send_message(msg.chat.id,
        "📋 *አዲስ ታስክ*\n\n"
        "በዚህ ቅርጸት ይላኩ፦\n\n"
        "`/addtask ርዕስ | መግለጫ | ሽልማት | ሊንክ`\n\n"
        "ለምሳሌ፦\n"
        "`/addtask ቻናል ጆይን | ቻናሉን ተቀላቀሉ | 5 | https://t.me/example`\n\n"
        "📌 ሊንክ ካልፈለጉ `-` ይጻፉ።")
    bot.register_next_step_handler_by_chat_id(msg.chat.id, process_addtask)

def process_addtask(msg):
    if not is_admin(msg.from_user.id): return
    text = (msg.text or "").strip()
    if not text.startswith("/addtask"):
        bot.send_message(msg.chat.id, "❌ እንደገና /addtask ይጫኑ።"); return
    body = text.replace("/addtask", "", 1).strip()
    parts = [p.strip() for p in body.split("|")]
    if len(parts) < 3:
        bot.send_message(msg.chat.id, "❌ ቅርጸቱ ተሳስቷል። እንደገና ይሞክሩ።"); return

    title = parts[0]
    desc  = parts[1]
    try:
        reward = float(parts[2])
    except:
        bot.send_message(msg.chat.id, "❌ ሽልማቱ ቁጥር መሆን አለበት።"); return
    url = parts[3] if len(parts) > 3 and parts[3] != "-" else None

    tid = add_task(title, desc, reward, url)
    bot.send_message(msg.chat.id,
        f"✅ *ታስክ ተጨምሯል!*\n\n"
        f"🆔 #{tid}\n📌 {title}\n💰 {reward:.2f} ብር")

@bot.message_handler(commands=["tasks"])
def cmd_tasks(msg):
    if not is_admin(msg.from_user.id): return
    tasks = list_tasks(active_only=False)
    if not tasks:
        bot.send_message(msg.chat.id, "📋 ታስክ የለም።"); return
    text = "📋 *ሁሉም ታስኮች*\n\n"
    for t in tasks:
        tid, title, desc, reward, url, active, _ = t
        st = "🟢" if active else "🔴"
        text += f"{st} #{tid} — {title}\n   💰 {reward:.2f} ብር | 🔗 {url or '—'}\n\n"
    text += "🗑 ለማጥፋት: /deltask <id>"
    bot.send_message(msg.chat.id, text)

@bot.message_handler(commands=["deltask"])
def cmd_deltask(msg):
    if not is_admin(msg.from_user.id): return
    try:
        tid = int(msg.text.split()[1])
    except:
        bot.send_message(msg.chat.id, "አጠቃቀም: /deltask <id>"); return
    if not get_task(tid):
        bot.send_message(msg.chat.id, "❌ አልተገኘም"); return
    delete_task(tid)
    bot.send_message(msg.chat.id, f"✅ #{tid} ተጠፍቷል")

# ---------- ADMIN: USERS ----------
@bot.message_handler(commands=["users"])
def cmd_users(msg):
    if not is_admin(msg.from_user.id): return
    rows = all_users(50)
    if not rows:
        bot.send_message(msg.chat.id, "ተጠቃሚ የለም።"); return
    text = "👥 *የተጠቃሚዎች ዝርዝር (50 ቀዳሚ)*\n\n"
    for uid, uname, fname, bal in rows:
        text += f"• {fname} | @{uname or '—'} | `{uid}` | {bal:.2f} ብር\n"
    bot.send_message(msg.chat.id, text)

@bot.message_handler(commands=["top"])
def cmd_top(msg):
    if not is_admin(msg.from_user.id): return
    rows = top_referrers(10)
    if not rows:
        bot.send_message(msg.chat.id, "የለም።"); return
    text = "🏆 *ከፍተኛ ሪፈረሮች*\n\n"
    for i, (fname, uname, uid, c) in enumerate(rows, 1):
        text += f"{i}. {fname} | @{uname or '—'} | `{uid}` | {c} ሪፈራል\n"
    bot.send_message(msg.chat.id, text)

@bot.message_handler(commands=["user"])
def cmd_user(msg):
    if not is_admin(msg.from_user.id): return
    try:
        uid = int(msg.text.split()[1])
    except:
        bot.send_message(msg.chat.id, "አጠቃቀም: /user <id>"); return
    u = get_user(uid)
    if not u:
        bot.send_message(msg.chat.id, "❌ አልተገኘም"); return
    refs = get_referrals(uid)
    text = (
        f"👤 *የተጠቃሚ ዝርዝር*\n\n"
        f"🆔 `{u[0]}`\n"
        f"👤 ስም: {u[2]}\n"
        f"📛 ዩዘርኔም: @{u[1] or '—'}\n"
        f"💰 ባላንስ: {u[4]:.2f} ብር\n"
        f"👥 ሪፈራሎች: {len(refs)}\n"
        f"👛 ዋሌት: {u[5] or '—'} ({u[6] or '—'})\n"
        f"✅ የተረጋገጠ: {'አዎ' if u[9] else 'አይ'}\n"
        f"🚫 የታገደ: {'አዎ' if u[10] else 'አይ'}\n"
    )
    if refs:
        text += "\n*የጋበዛቸው:*\n"
        for r in refs[:20]:
            text += f"• {r[2]} | @{r[1] or '—'} | `{r[0]}`\n"
    bot.send_message(msg.chat.id, text)

@bot.message_handler(commands=["add", "sub"])
def cmd_addsub(msg):
    if not is_admin(msg.from_user.id): return
    try:
        _, uid, amt = msg.text.split()
        uid, amt = int(uid), float(amt)
    except:
        bot.send_message(msg.chat.id, "አጠቃቀም: /add <id> <amount>"); return
    if not get_user(uid):
        bot.send_message(msg.chat.id, "❌ አልተገኘም"); return
    if msg.text.startswith("/add"):
        add_balance(uid, amt)
        bot.send_message(msg.chat.id, f"✅ +{amt:.2f} ተጨምሯል")
        try: bot.send_message(uid, f"💰 +{amt:.2f} ብር ተጨምሯል!")
        except: pass
    else:
        add_balance(uid, -amt)
        bot.send_message(msg.chat.id, f"✅ -{amt:.2f} ቀንሷል")
        try: bot.send_message(uid, f"⚠️ -{amt:.2f} ብር ተቀንሷል")
        except: pass

@bot.message_handler(commands=["ban", "unban"])
def cmd_ban(msg):
    if not is_admin(msg.from_user.id): return
    try:
        uid = int(msg.text.split()[1])
    except:
        bot.send_message(msg.chat.id, "አጠቃቀም: /ban <id>"); return
    val = 1 if msg.text.startswith("/ban") else 0
    cur.execute("UPDATE users SET is_banned=? WHERE user_id=?", (val, uid))
    conn.commit()
    bot.send_message(msg.chat.id, "✅ ተሰርቷል")
    if val == 1:
        try: bot.send_message(uid, "🚫 ከቦቱ ታግደዋል።")
        except: pass

@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(msg):
    if not is_admin(msg.from_user.id): return
    text = msg.text.replace("/broadcast", "", 1).strip()
    if not text:
        bot.send_message(msg.chat.id, "ጽሁፍ ያስፈልጋል"); return
    cur.execute("SELECT user_id FROM users WHERE is_banned=0")
    ok, fail = 0, 0
    for (uid,) in cur.fetchall():
        try:
            bot.send_message(uid, text); ok += 1
            time.sleep(0.05)
        except: fail += 1
    bot.send_message(msg.chat.id, f"✅ {ok} ተልኳል | ❌ {fail} አልተላከም")

@bot.message_handler(commands=["stats"])
def cmd_stats(msg):
    if not is_admin(msg.from_user.id): return
    total   = total_users()
    cur.execute("SELECT COUNT(*) FROM users WHERE verified=1")
    verified = cur.fetchone()[0]
    paid     = total_paid()
    cur.execute("SELECT COALESCE(SUM(balance),0) FROM users")
    total_bal = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
    pending_wd = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM task_completions WHERE status='pending'")
    pending_tasks = cur.fetchone()[0]

    text = (
        f"📊 *ስታቲስቲክስ — Hulu Pay*\n\n"
        f"👥 ጠቅላላ ተጠቃሚ: *{total}*\n"
        f"✅ የተረጋገጡ: *{verified}*\n"
        f"💰 ጠቅላላ ባላንስ: *{total_bal:.2f} ብር*\n"
        f"💸 የተከፈለ: *{paid:.2f} ብር*\n"
        f"⏳ በመጠበቅ ያሉ ዊዝድሮ: *{pending_wd}*\n"
        f"⏳ በመጠበቅ ያሉ ታስክ: *{pending_tasks}*"
    )
    bot.send_message(msg.chat.id, text)

# ============ STARTUP ============
def startup_check():
    print("=" * 45)
    print("🤖 Hulu Pay Bot — ተጀምሯል")
    print("=" * 45)
    # ቻናሎች ላይ ቦቱ አድሚን መሆኑን አረጋግጥ
    for ch in MANDATORY_CHANNELS:
        try:
            me = bot.get_me()
            m = bot.get_chat_member(ch["id"], me.id)
            if m.status in ("administrator", "creator"):
                print(f"✅ {ch['name']} — አድሚን ነው")
            else:
                print(f"⚠️  {ch['name']} — አድሚን አይደለም! (status: {m.status})")
        except Exception as e:
            print(f"❌ {ch['name']} — ስህተት: {e}")
    try:
        me = bot.get_me()
        m = bot.get_chat_member(WITHDRAW_CHANNEL, me.id)
        if m.status in ("administrator", "creator"):
            print(f"✅ የዊዝድሮ ቻናል — አድሚን ነው")
        else:
            print(f"⚠️  የዊዝድሮ ቻናል — አድሚን አይደለም!")
    except Exception as e:
        print(f"❌ የዊዝድሮ ቻናል — ስህተት: {e}")
    print("=" * 45)

if __name__ == "__main__":
    startup_check()
    bot.infinity_polling(timeout=30, long_polling_timeout=30)
