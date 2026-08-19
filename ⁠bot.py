import sqlite3
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = "8955259098:AAFiFggDcJaIsnIxr8Mh0fOUyxFBURLqjts"
MAIN_ADMIN_ID = 8241567709  # Your primary immutable master admin ID
GROUP_LINK = "https://t.me/playversegroup"
UPI_HANDLE = "6284635033@fam"
SUPPORT_HANDLE = "@OGxSUKHMANxYT"

CRYPTO_WALLETS = {
    "BEP20": "0xd1A8F830AF83D7CBC2105223c10063EF991D98c5",
    "SOL": "8n5utQ22d8nsrs9RvAzc5Adjsd1m97Jtbxw3HstbReKs",
    "TRON": "TGS8Yq1CLJPptBjFRLAiGAadxeMWxzZkkB",
    "ETH": "0xd1A8F830AF83D7CBC2105223c10063EF991D98c5"
}

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.00,
            upi TEXT DEFAULT 'Not Set',
            usd_address TEXT DEFAULT 'Not Set',
            total_wagered REAL DEFAULT 0.00,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            details TEXT,
            status TEXT DEFAULT 'PENDING'
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gift_codes (
            code TEXT PRIMARY KEY,
            amount REAL DEFAULT 10.00,
            max_uses INTEGER DEFAULT 10,
            current_uses INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gift_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            code TEXT,
            claim_date DATE DEFAULT (DATE('now'))
        )
    """)
    
    # Ensure master admin is always authorized
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (MAIN_ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()

def is_admin(user_id: int) -> bool:
    if user_id == MAIN_ADMIN_ID:
        return True
    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return bool(res)

def calculate_payout(amount, multiplier=1.90):
    raw_win = amount * multiplier
    profit = raw_win - amount
    tax_rate = 0.01 if amount <= 100 else 0.025
    return round(raw_win - (profit * tax_rate), 2)

async def check_dm_context(update: Update) -> bool:
    chat = update.effective_chat
    if chat.type != "private":
        keyboard = [
            [InlineKeyboardButton("📥 **DEPOSIT**", url=f"https://t.me/{update.get_bot().username}?start=deposit"),
             InlineKeyboardButton("📤 **WITHDRAW**", url=f"https://t.me/{update.get_bot().username}?start=withdraw")]
        ]
        await update.message.reply_text(
            "🔒 **RESTRICTED COMMAND ACTION**\n\n"
            "⚡ **FOR MAXIMUM SECURITY & FINANCIAL PRIVACY, DEPOSITS AND WITHDRAWALS CAN ONLY BE EXECUTED DIRECTLY INSIDE BOT DM (INBOX).**\n\n"
            "👇 **TAP BELOW TO PROCEED SECURELY:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return False
    return True

# --- START & HELPERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username or user.first_name))
    conn.commit()
    conn.close()

    if args and args[0] == "deposit":
        if await check_dm_context(update):
            await deposit(update, context)
        return
    elif args and args[0] == "withdraw":
        if await check_dm_context(update):
            await withdraw(update, context)
        return

    welcome_msg = (
        "👑 **WELCOME TO PLAYVERSE ENTERPRISE** 👑\n\n"
        "⚡ **THE ULTIMATE DESTINATION FOR DECENTRALIZED GAMING & INSTANT PAYOUTS.**\n\n"
        "💎 **CHOOSE AN OPTION BELOW OR JOIN OUR COMMUNITY GROUP:**"
    )
    keyboard = [
        [InlineKeyboardButton("📥 **DEPOSIT**", callback_data="menu_deposit"),
         InlineKeyboardButton("📤 **WITHDRAW**", callback_data="menu_withdraw")],
        [InlineKeyboardButton("🌟 **OFFICIAL COMMUNITY GROUP**", url=GROUP_LINK)]
    ]
    await update.message.reply_text(welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "menu_deposit":
        if query.message.chat.type != "private":
            await query.message.reply_text("🔒 **PLEASE OPEN BOT DM TO DEPOSIT SAFELY.**")
            return
        await deposit(update, context)
    elif query.data == "menu_withdraw":
        if query.message.chat.type != "private":
            await query.message.reply_text("🔒 **PLEASE OPEN BOT DM TO WITHDRAW SAFELY.**")
            return
        await withdraw(update, context)

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📞 **PLAYVERSE CUSTOMER SUPPORT**\n\n"
        f"✨ **FOR ASSISTANCE, DISPUTES, OR MANUAL VERIFICATION, CONTACT OUR OFFICIAL SUPPORT DESK:**\n"
        f"👉 **{SUPPORT_HANDLE}**",
        parse_mode="Markdown"
    )

# --- WALLET & BALANCE ---
async def wallet_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, upi, usd_address, wins, losses FROM users WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()
    conn.close()

    balance, upi, usd_address, wins, losses = row if row else (0.00, "Not Set", "Not Set", 0, 0)
    msg = (
        f"💼 **PLAYVERSE ELITE SECURE WALLET**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **HOLDER:** `{user.first_name}`\n"
        f"💵 **BALANCE:** `₹{balance:.2f}`\n"
        f"📱 **UPI ID:** `{upi}`\n"
        f"💎 **USDT ADDRESS:** `{usd_address}`\n"
        f"📊 **RECORD:** `{wins} WINS | {losses} LOSSES`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 **MINIMUM WITHDRAWAL:** `₹50.00 / $5`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def saveupi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("📋 **SYNTAX FORMAT ERROR**\n\n⚡ **USAGE:** `/saveupi yourname@paytm`", parse_mode="Markdown")
        return
    upi_id = args[0]
    if "@" not in upi_id and "." not in upi_id:
        await update.message.reply_text("❌ **INVALID UPI ADDRESS FORMAT PROVIDED.**", parse_mode="Markdown")
        return
    user = update.effective_user
    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET upi = ? WHERE user_id = ?", (upi_id, user.id))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ **UPI REGISTRATION SUCCESSFUL & SECURED!**", parse_mode="Markdown")

# --- DEPOSIT & WITHDRAWAL GATEWAYS ---
async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_dm_context(update): return
    keyboard = [
        [InlineKeyboardButton("📱 **UPI / QR INSTANT DEPOSIT**", callback_data="dep_upi")],
        [InlineKeyboardButton("💎 **USDT (BEP20)**", callback_data="dep_crypto_BEP20")],
        [InlineKeyboardButton("☀️ **SOLANA**", callback_data="dep_crypto_SOL")],
        [InlineKeyboardButton("⚡ **TRON (TRC20)**", callback_data="dep_crypto_TRON")],
        [InlineKeyboardButton("🔷 **ETHEREUM (ERC20)**", callback_data="dep_crypto_ETH")]
    ]
    msg = update.callback_query.message if update.callback_query else update.message
    text = "🚀 **SECURE HIGH-SPEED DEPOSIT GATEWAY**\n\n💎 **CHOOSE YOUR PREFERRED PAYMENT NETWORK BELOW:**"
    if update.callback_query:
        await update.callback_query.answer()
        await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "dep_upi":
        keyboard = [[InlineKeyboardButton("✅ I HAVE PAID", callback_data="dep_paid_confirm")]]
        msg = (
            "📥 **ENTER AMOUNT TO DEPOSIT (MIN ₹50 — MAX ₹5000)**\n\n"
            f"👉 **SEND PAYMENT TO OFFICIAL UPI ID:**\n`{UPI_HANDLE}`\n\n"
            "✨ **AFTER TRANSFERRING, TAP THE BUTTON BELOW TO SUBMIT YOUR 12-DIGIT UTR.**"
        )
        await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data.startswith("dep_crypto_"):
        chain = data.split("_")[-1]
        address = CRYPTO_WALLETS.get(chain, "")
        context.user_data["pending_crypto_chain"] = chain
        keyboard = [[InlineKeyboardButton("✅ I HAVE PAID", callback_data="dep_crypto_paid_confirm")]]
        msg = (
            f"💎 **CRYPTO DEPOSIT GATEWAY — {chain}**\n"
            f"🎯 **MINIMUM DEPOSIT:** `$5.00`\n\n"
            f"📍 **OFFICIAL {chain} ADDRESS:**\n`{address}`\n\n"
            f"💡 **SEND EXACT AMOUNT FIRST, THEN TAP BELOW.**"
        )
        await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def deposit_paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting_utr"] = True
    await query.message.reply_text(
        "✨🎯 **PLEASE SEND YOUR 12-DIGIT UTR NUMBER NOW IN BOLD AND WITH EMOJIS!** 🚀🔥\n\n"
        "👉 *(Example: `123456789012`)*",
        parse_mode="Markdown"
    )

async def deposit_crypto_paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting_crypto_proof"] = True
    await query.message.reply_text(
        "✨🎯 **PLEASE SEND YOUR TRANSACTION HASH (TXID) OR PROOF IN CHAT NOW!** 🚀🔥",
        parse_mode="Markdown"
    )

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_dm_context(update): return
    keyboard = [
        [InlineKeyboardButton("📱 **WITHDRAW VIA UPI**", callback_data="w_type_upi")],
        [InlineKeyboardButton("💎 **WITHDRAW VIA CRYPTO**", callback_data="w_type_crypto")]
    ]
    msg = update.callback_query.message if update.callback_query else update.message
    text = "📤 **SECURE ELITE WITHDRAWAL PORTAL**\n\n⚡ **SELECT YOUR TARGET PAYOUT METHOD:**"
    if update.callback_query:
        await update.callback_query.answer()
        await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def withdraw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "w_type_upi":
        context.user_data["withdrawal_flow"] = "UPI_AMOUNT"
        await query.message.edit_text("📱 **UPI PAYOUT SELECTED**\n\n🎯 **ENTER AMOUNT TO WITHDRAW:** `(₹50 - ₹5000)`", parse_mode="Markdown")
    elif data == "w_type_crypto":
        keyboard = [
            [InlineKeyboardButton("💎 USDT (BEP20)", callback_data="w_crypto_BEP20"), InlineKeyboardButton("⚡ TRON (TRC20)", callback_data="w_crypto_TRON")],
            [InlineKeyboardButton("☀️ SOLANA", callback_data="w_crypto_SOL"), InlineKeyboardButton("🔷 ETHEREUM (ERC20)", callback_data="w_crypto_ETH")]
        ]
        await query.message.edit_text("💎 **SELECT PREFERRED CRYPTO NETWORK:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data.startswith("w_crypto_"):
        chain = data.split("_")[-1]
        context.user_data["withdrawal_flow"] = f"CRYPTO_{chain}"
        await query.message.edit_text(
            f"💎 **{chain} PAYOUT SELECTED**\n\n"
            f"⚡ **PLEASE SEND AMOUNT & WALLET ADDRESS IN CHAT (FORMAT: `AMOUNT ADDRESS`)**",
            parse_mode="Markdown"
        )
    elif data == "w_use_saved_upi":
        amount = context.user_data.get("pending_w_amount", 50)
        user = update.effective_user
        conn = sqlite3.connect("playverse.db")
        cursor = conn.cursor()
        cursor.execute("SELECT balance, upi FROM users WHERE user_id = ?", (user.id,))
        row = cursor.fetchone()
        
        if not row or row[0] < amount:
            conn.close()
            await query.message.edit_text("❌ **INSUFFICIENT BALANCE FOR THIS PAYOUT REQUEST.**")
            return
            
        upi_address = row[1]
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user.id))
        cursor.execute("INSERT INTO transactions (user_id, type, amount, details, status) VALUES (?, 'WITHDRAWAL_UPI', ?, ?, 'PENDING')", (user.id, amount, upi_address))
        tx_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        admin_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ APPROVE", callback_data=f"ap_yes_{tx_id}_{user.id}_{amount}_WITHDRAWAL_UPI"),
             InlineKeyboardButton("❌ REJECT", callback_data=f"ap_no_{tx_id}_{user.id}_{amount}")]
        ])
        
        # Broadcast to all admins
        conn = sqlite3.connect("playverse.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        admins = cursor.fetchall()
        conn.close()
        
        for adm in admins:
            try:
                await context.bot.send_message(
                    chat_id=adm[0],
                    text=f"🔔 **NEW WITHDRAWAL REQUEST**\n\n• **ID:** `#{tx_id}`\n• **USER:** `{user.id}`\n• **UPI:** `{upi_address}`\n• **AMOUNT:** `₹{amount:.2f}`",
                    reply_markup=admin_markup,
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        await query.message.edit_text(
            "✅ **WITHDRAWAL PLACED SUCCESSFULLY!**\n\n⏳ **VERIFICATION IN PROGRESS (10-15 MINUTES).**",
            parse_mode="Markdown"
        )

# --- PVP COIN FLIP GAME ---
async def play_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("📋 **SYNTAX ERROR**\n\n⚡ **USAGE:** `/coin <amount> HEADS` or `/coin <amount> TAILS`", parse_mode="Markdown")
        return
    try:
        amount = float(args[0])
        choice = args[1].upper()
    except ValueError:
        await update.message.reply_text("❌ **INVALID NUMERICAL AMOUNT OR FORMAT.**", parse_mode="Markdown")
        return

    if choice not in ["HEADS", "TAILS"]:
        await update.message.reply_text("❌ **CHOOSE EITHER HEADS OR TAILS.**", parse_mode="Markdown")
        return

    user = update.effective_user
    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0.00

    if balance < 10 or balance < amount:
        conn.close()
        await update.message.reply_text(f"⚠️ **INSUFFICIENT BALANCE! REQUIRED: ₹{amount:.2f}**", parse_mode="Markdown")
        return

    landed = random.choice(["HEADS", "TAILS"])
    won = (choice == landed)
    payout = calculate_payout(amount, 1.90)

    cursor.execute("UPDATE users SET balance = balance - ?, total_wagered = total_wagered + ? WHERE user_id = ?", (amount, amount, user.id))
    if won:
        cursor.execute("UPDATE users SET balance = balance + ?, wins = wins + 1 WHERE user_id = ?", (payout, user.id))
        res = f"🪙 **COIN FLIP ROLLED: {landed}**\n🎉 **VICTORY! ₹{payout:.2f} CREDITED (1.90x)**"
    else:
        cursor.execute("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (user.id,))
        res = f"🪙 **COIN FLIP ROLLED: {landed}**\n📉 **DEFEAT! YOU LOST ₹{amount:.2f}**"

    conn.commit()
    conn.close()
    await update.message.reply_text(res, parse_mode="Markdown")

# --- GIFT CODE SYSTEM ---
async def giftcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("📋 **SYNTAX ERROR**\n\n⚡ **USAGE:** `/giftcode <CODE>`", parse_mode="Markdown")
        return
    code = args[0].strip().upper()
    user = update.effective_user
    
    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()
    cursor.execute("SELECT amount, max_uses, current_uses FROM gift_codes WHERE code = ?", (code,))
    gcode = cursor.fetchone()
    
    if not gcode or gcode[2] >= gcode[1]:
        conn.close()
        await update.message.reply_text("❌ **GIFT CODE EXPIRED OR INVALID.**", parse_mode="Markdown")
        return
        
    amount, max_uses, current_uses = gcode
    cursor.execute("SELECT id FROM gift_claims WHERE user_id = ? AND code = ?", (user.id, code))
    if cursor.fetchone():
        conn.close()
        await update.message.reply_text("❌ **ALREADY CLAIMED BY THIS ACCOUNT.**", parse_mode="Markdown")
        return
        
    cursor.execute("SELECT COUNT(*) FROM gift_claims WHERE user_id = ? AND claim_date = DATE('now')", (user.id,))
    if cursor.fetchone()[0] >= 3:
        conn.close()
        await update.message.reply_text("❌ **DAILY GIFT CODE CLAIM LIMIT REACHED (MAX 3/DAY).**", parse_mode="Markdown")
        return
        
    cursor.execute("INSERT INTO gift_claims (user_id, code) VALUES (?, ?)", (user.id, code))
    cursor.execute("UPDATE gift_codes SET current_uses = current_uses + 1 WHERE code = ?", (code,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user.id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"🎁 **GIFT CODE REDEEMED SUCCESSFULLY!**\n\n💵 **CREDITED:** `₹{amount:.2f}`", parse_mode="Markdown")

# --- ADVANCED ADMIN PANEL DASHBOARD & WIZARDS ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ **ACCESS DENIED.**")
        return

    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'PENDING'")
    pending_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(balance) FROM users")
    total_liability = cursor.fetchone()[0] or 0.00
    conn.close()

    keyboard = [
        [InlineKeyboardButton(f"🔔 Pending Requests ({pending_count})", callback_data="admin_view_pending")],
        [InlineKeyboardButton("👥 User Database Audit", callback_data="admin_users_list")],
        [InlineKeyboardButton("🎁 Create Gift Code Wizard", callback_data="admin_make_gift")],
        [InlineKeyboardButton("👑 Add Sub-Admin", callback_data="admin_add_sub")],
        [InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="admin_refresh")]
    ]

    msg = (
        "⚙️ **PLAYVERSE LIVE ADMIN CONTROL PANEL** ⚙️\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 **Total Registered Users:** `{total_users}`\n"
        f"⏳ **Pending Transactions:** `{pending_count}`\n"
        f"💰 **Total Liability (Balances):** `₹{total_liability:.2f}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 **Select action below:**"
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_panel_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if not is_admin(user.id):
        await query.answer("Unauthorized!", show_alert=True)
        return

    data = query.data
    await query.answer()

    if data in ["admin_refresh", "admin_stats"]:
        await admin_panel(update, context)
    elif data == "admin_view_pending":
        conn = sqlite3.connect("playverse.db")
        cursor = conn.cursor()
        cursor.execute("SELECT tx_id, user_id, type, amount, details FROM transactions WHERE status = 'PENDING' LIMIT 5")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            await query.message.edit_text(
                "✅ **NO PENDING REQUESTS FOUND!**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_refresh")]]),
                parse_mode="Markdown"
            )
            return

        for row in rows:
            tx_id, u_id, t_type, amt, details = row
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ APPROVE", callback_data=f"ap_yes_{tx_id}_{u_id}_{amt}_{t_type}"),
                 InlineKeyboardButton("❌ REJECT", callback_data=f"ap_no_{tx_id}_{u_id}_{amt}")]
            ])
            await context.bot.send_message(
                chat_id=user.id,
                text=f"📌 **TX #{tx_id}**\n• **Type:** `{t_type}`\n• **User ID:** `{u_id}`\n• **Details:** `{details}`",
                reply_markup=markup,
                parse_mode="Markdown"
            )
        await query.message.edit_text("📋 **Sent active requests above.**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_refresh")]]))

    elif data == "admin_users_list":
        conn = sqlite3.connect("playverse.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, balance FROM users LIMIT 10")
        users = cursor.fetchall()
        conn.close()
        
        text = "👥 **USER DATABASE RECORDS (TOP 10)**\n━━━━━━━━━━━━━━━━━━━━━\n"
        for u in users:
            text += f"• `{u[0]}` | @{u[1]} | Bal: ₹{u[2]:.2f}\n"
        text += "\n💡 *Use `/addbal <userid> <amt>` or `/msg <userid> <text>` to manage.*"
        
        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_refresh")]]),
            parse_mode="Markdown"
        )

    elif data == "admin_make_gift":
        context.user_data["gift_step"] = "AMOUNT"
        await query.message.edit_text(
            "🎁 **GIFT CODE WIZARD ACTIVATED**\n\n"
            "⚡ **PLEASE REPLY IN CHAT WITH THE AMOUNT FOR THIS GIFT CODE (e.g. `50`):**",
            parse_mode="Markdown"
        )

    elif data == "admin_add_sub":
        context.user_data["awaiting_sub_admin"] = True
        await query.message.edit_text(
            "👑 **ADD SUB-ADMIN WIZARD**\n\n"
            "⚡ **PLEASE REPLY IN CHAT WITH THE USERNAME OF THE NEW ADMIN (e.g. `@username`):**",
            parse_mode="Markdown"
        )

    elif data.startswith("ap_yes_") or data.startswith("ap_no_"):
        parts = data.split("_")
        action = parts[1]
        tx_id = parts[2]
        u_id = int(parts[3])
        conn = sqlite3.connect("playverse.db")
        cursor = conn.cursor()
        
        if action == "yes":
            amount = float(parts[4])
            t_type = parts[5]
            cursor.execute("UPDATE transactions SET status = 'APPROVED' WHERE tx_id = ?", (tx_id,))
            if "DEPOSIT" in t_type:
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, u_id))
            conn.commit()
            conn.close()
            await query.message.edit_text(f"✅ **Transaction #{tx_id} Approved Successfully.**")
            try:
                await context.bot.send_message(chat_id=u_id, text="✅ **YOUR TRANSACTION HAS BEEN APPROVED & CREDITED!**", parse_mode="Markdown")
            except Exception:
                pass
        else:
            cursor.execute("UPDATE transactions SET status = 'REJECTED' WHERE tx_id = ?", (tx_id,))
            conn.commit()
            conn.close()
            await query.message.edit_text(f"❌ **Transaction #{tx_id} Rejected.**")
            try:
                await context.bot.send_message(chat_id=u_id, text="❌ **YOUR TRANSACTION WAS DECLINED BY ADMIN.**", parse_mode="Markdown")
            except Exception:
                pass

# --- ADMIN COMMANDS: BROADCAST & BALANCE MGMT ---
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id): return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("📋 **USAGE:** `/broadcast <your announcement text>`")
        return
    
    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    sent = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=f"📢 **ADMIN BROADCAST**\n\n{text}", parse_mode="Markdown")
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ **BROADCAST SENT SUCCESSFULLY TO {sent} USERS.**")

async def addbal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id): return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("📋 **USAGE:** `/addbal <user_id> <amount>`")
        return
    try:
        target_id = int(args[0])
        amt = float(args[1])
    except ValueError:
        await update.message.reply_text("❌ **INVALID FORMAT.**")
        return

    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, target_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ **Successfully added ₹{amt:.2f} to user ID `{target_id}`.**", parse_mode="Markdown")

async def deductbal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id): return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("📋 **USAGE:** `/deductbal <user_id> <amount>`")
        return
    try:
        target_id = int(args[0])
        amt = float(args[1])
    except ValueError:
        await update.message.reply_text("❌ **INVALID FORMAT.**")
        return

    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amt, target_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ **Successfully deducted ₹{amt:.2f} from user ID `{target_id}`.**", parse_mode="Markdown")

async def custom_msg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id): return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("📋 **USAGE:** `/msg <user_id> <message>`")
        return
    try:
        target_id = int(args[0])
        msg_text = " ".join(args[1:])
    except ValueError:
        await update.message.reply_text("❌ **INVALID FORMAT.**")
        return

    try:
        await context.bot.send_message(chat_id=target_id, text=f"💬 **ADMIN MESSAGE:**\n\n{msg_text}", parse_mode="Markdown")
        await update.message.reply_text("✅ **Custom message sent successfully.**")
    except Exception as e:
        await update.message.reply_text(f"❌ **Failed to send:** `{e}`")

# --- MASTER TEXT MESSAGE & WIZARD HANDLER ---
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or update.message.caption or ""
    has_photo = bool(update.message.photo)
    
    # 1. Gift Code Wizard Step 1: Amount
    if context.user_data.get("gift_step") == "AMOUNT":
        try:
            amt = float(text)
            context.user_data["gift_amount"] = amt
            context.user_data["gift_step"] = "USERS"
            await update.message.reply_text("⚡ **GREAT! NOW REPLY WITH THE MAXIMUM NUMBER OF USERS WHO CAN CLAIM THIS CODE (e.g. `10`):**")
        except ValueError:
            await update.message.reply_text("❌ **PLEASE ENTER A VALID NUMERICAL AMOUNT.**")
        return

    # 2. Gift Code Wizard Step 2: Max Uses & Generation
    elif context.user_data.get("gift_step") == "USERS":
        try:
            max_uses = int(text)
            amt = context.user_data.get("gift_amount", 10.0)
            context.user_data["gift_step"] = None
            
            # Generate unique 12-digit code
            unique_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            
            conn = sqlite3.connect("playverse.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO gift_codes (code, amount, max_uses, current_uses) VALUES (?, ?, ?, 0)", (unique_code, amt, max_uses))
            conn.commit()
            conn.close()
            
            await update.message.reply_text(
                f"🎁 **GIFT CODE CREATED SUCCESSFULLY!**\n\n"
                f"• **UNIQUE CODE:** `{unique_code}`\n"
                f"• **AMOUNT:** `₹{amt:.2f}`\n"
                f"• **MAX USES:** `{max_uses}`",
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("❌ **PLEASE ENTER A VALID INTEGER NUMBER.**")
        return

    # 3. Sub-Admin Adder Wizard
    if context.user_data.get("awaiting_sub_admin") and is_admin(user.id):
        context.user_data["awaiting_sub_admin"] = False
        target_handle = text.replace("@", "")
        conn = sqlite3.connect("playverse.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE username = ?", (target_handle,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            await update.message.reply_text(f"❌ **USER `@{target_handle}` NOT FOUND IN DATABASE RECORD.**", parse_mode="Markdown")
            return
        sub_id = row[0]
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (sub_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"👑 **SUCCESSFULLY ADDED `@{target_handle}` AS A SUB-ADMIN!**", parse_mode="Markdown")
        return

    # 4. UPI UTR Handler
    if context.user_data.get("awaiting_utr"):
        context.user_data["awaiting_utr"] = False
        conn = sqlite3.connect("playverse.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO transactions (user_id, type, amount, details, status) VALUES (?, 'DEPOSIT_UPI', 100.0, ?, 'PENDING')", (user.id, text))
        tx_id = cursor.lastrowid
        conn.commit()
        conn.close()

        await update.message.reply_text(
            "⏳ **DEPOSIT REQUEST SUBMITTED! IT WILL VERIFY IN 10-15 MINUTES.**",
            parse_mode="Markdown"
        )
        
        admin_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ APPROVE", callback_data=f"ap_yes_{tx_id}_{user.id}_100_DEPOSIT_UPI"),
             InlineKeyboardButton("❌ REJECT", callback_data=f"ap_no_{tx_id}_{user.id}_100")]
        ])
        
        cursor = sqlite3.connect("playverse.db").cursor()
        cursor.execute("SELECT user_id FROM admins")
        admins = cursor.fetchall()
        
        for adm in admins:
            try:
                if has_photo:
                    await context.bot.send_photo(
                        chat_id=adm[0],
                        photo=update.message.photo[-1].file_id,
                        caption=f"📥 **NEW UPI DEPOSIT**\n• **TX ID:** `#{tx_id}`\n• **USER:** `{user.id}`\n• **UTR:** `{text}`",
                        reply_markup=admin_markup,
                        parse_mode="Markdown"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=adm[0],
                        text=f"📥 **NEW UPI DEPOSIT**\n• **TX ID:** `#{tx_id}`\n• **USER:** `{user.id}`\n• **UTR:** `{text}`",
                        reply_markup=admin_markup,
                        parse_mode="Markdown"
                    )
            except Exception:
                pass
        return

    # 5. Crypto Deposit Proof Handler
    if context.user_data.get("awaiting_crypto_proof"):
        chain = context.user_data.get("pending_crypto_chain", "CRYPTO")
        context.user_data["awaiting_crypto_proof"] = False
        conn = sqlite3.connect("playverse.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO transactions (user_id, type, amount, details, status) VALUES (?, ?, 450.0, ?, 'PENDING')", (user.id, f"DEPOSIT_{chain}", text))
        tx_id = cursor.lastrowid
        conn.commit()
        conn.close()

        await update.message.reply_text("⏳ **CRYPTO DEPOSIT SUBMITTED! IT WILL VERIFY IN 10-15 MINUTES.**", parse_mode="Markdown")
        admin_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ APPROVE", callback_data=f"ap_yes_{tx_id}_{user.id}_450_DEPOSIT_{chain}"),
             InlineKeyboardButton("❌ REJECT", callback_data=f"ap_no_{tx_id}_{user.id}_450")]
        ])
        
        cursor = sqlite3.connect("playverse.db").cursor()
        cursor.execute("SELECT user_id FROM admins")
        admins = cursor.fetchall()
        
        for adm in admins:
            try:
                if has_photo:
                    await context.bot.send_photo(chat_id=adm[0], photo=update.message.photo[-1].file_id, caption=f"💎 **CRYPTO DEPOSIT ({chain})**\n• **ID:** `#{tx_id}`\n• **USER:** `{user.id}`\n• **PROOF:** `{text}`", reply_markup=admin_markup, parse_mode="Markdown")
                else:
                    await context.bot.send_message(chat_id=adm[0], text=f"💎 **CRYPTO DEPOSIT ({chain})**\n• **ID:** `#{tx_id}`\n• **PROOF:** `{text}`", reply_markup=admin_markup, parse_mode="Markdown")
            except Exception:
                pass
        return

    # 6. UPI Withdrawal Amount & Crypto Payout Handler
    flow = context.user_data.get("withdrawal_flow")
    if flow == "UPI_AMOUNT":
        try:
            amount = float(text)
        except ValueError:
            await update.message.reply_text("❌ **PLEASE ENTER A VALID NUMERICAL AMOUNT.**")
            return
        if amount < 50 or amount > 5000:
            await update.message.reply_text("⚠️ **AMOUNT MUST BE BETWEEN ₹50 AND ₹5000.**")
            return
        context.user_data["pending_w_amount"] = amount
        context.user_data["withdrawal_flow"] = None
        
        conn = sqlite3.connect("playverse.db")
        cursor = conn.cursor()
        cursor.execute("SELECT upi FROM users WHERE user_id = ?", (user.id,))
        row = cursor.fetchone()
        conn.close()
        saved_upi = row[0] if row else "Not Set"
        
        keyboard = [[InlineKeyboardButton(f"💳 Saved UPI: {saved_upi}", callback_data="w_use_saved_upi")]]
        if saved_upi == "Not Set":
            keyboard[0] = [InlineKeyboardButton("⚠️ Add UPI via /saveupi", url=f"https://t.me/{context.bot.username}?start=saveupi")]
            
        await update.message.reply_text(f"📤 **CONFIRMED WITHDRAWAL: ₹{amount:.2f}**\n\n**SELECT DESTINATION:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif flow and flow.startswith("CRYPTO_"):
        chain = flow.split("_")[-1]
        parts = text.split(" ")
        if len(parts) < 2:
            await update.message.reply_text("❌ **FORMAT ERROR! PLEASE SEND AS: `AMOUNT ADDRESS`**")
            return
        try:
            amount = float(parts[0])
            address = parts[1].strip()
        except ValueError:
            await update.message.reply_text("❌ **INVALID AMOUNT FORMAT.**")
            return
            
        # Basic address validation check
        if len(address) < 15 or len(address) > 100 or " " in address:
            await update.message.reply_text("❌ **UNKNOWN ADDRESS TRY TO SEND ANOTHER ADDRESS OR CONTACT ADMIN**")
            return
            
        context.user_data["withdrawal_flow"] = None
        conn = sqlite3.connect("playverse.db")
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user.id,))
        row = cursor.fetchone()
        if not row or row[0] < amount:
            conn.close()
            await update.message.reply_text("❌ **INSUFFICIENT BALANCE FOR THIS PAYOUT.**")
            return
            
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user.id))
        cursor.execute("INSERT INTO transactions (user_id, type, amount, details, status) VALUES (?, ?, ?, ?, 'PENDING')", (user.id, f"WITHDRAWAL_{chain}", amount, address))
        tx_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        admin_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ APPROVE", callback_data=f"ap_yes_{tx_id}_{user.id}_{amount}_WITHDRAWAL_{chain}"),
             InlineKeyboardButton("❌ REJECT", callback_data=f"ap_no_{tx_id}_{user.id}_{amount}")]
        ])
        
        cursor = sqlite3.connect("playverse.db").cursor()
        cursor.execute("SELECT user_id FROM admins")
        admins = cursor.fetchall()
        for adm in admins:
            try:
                await context.bot.send_message(chat_id=adm[0], text=f"🔔 **NEW CRYPTO WITHDRAWAL**\n• **ID:** `#{tx_id}`\n• **USER:** `{user.id}`\n• **CHAIN:** `{chain}`\n• **AMOUNT:** `₹{amount:.2f}`\n• **ADDR:** `{address}`", reply_markup=admin_markup, parse_mode="Markdown")
            except Exception:
                pass
                
        await update.message.reply_text("✅ **CRYPTO WITHDRAWAL PLACED! VERIFICATION IN 10-15 MINUTES.**", parse_mode="Markdown")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler(["wallet", "balance"], wallet_balance))
    application.add_handler(CommandHandler("deposit", deposit))
    application.add_handler(CommandHandler("withdraw", withdraw))
    application.add_handler(CommandHandler("saveupi", saveupi))
    application.add_handler(CommandHandler("coin", play_coin))
    application.add_handler(CommandHandler("giftcode", giftcode_command))
    application.add_handler(CommandHandler("support", support_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("addbal", addbal_command))
    application.add_handler(CommandHandler("deductbal", deductbal_command))
    application.add_handler(CommandHandler("msg", custom_msg_command))

    application.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_"))
    application.add_handler(CallbackQueryHandler(admin_panel_callbacks, pattern="^ap_"))
    application.add_handler(CallbackQueryHandler(deposit_callback, pattern="^dep_"))
    application.add_handler(CallbackQueryHandler(deposit_paid_callback, pattern="^dep_paid_confirm$"))
    application.add_handler(CallbackQueryHandler(deposit_crypto_paid_callback, pattern="^dep_crypto_paid_confirm$"))
    application.add_handler(CallbackQueryHandler(withdraw_callback, pattern="^(w_type_|w_crypto_|w_use_saved_upi)"))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
    
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_messages))

    print("Playverse Enterprise Ultimate Bot Running Successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
