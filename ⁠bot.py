import os
import random
import string
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# CONFIGURATION (Replace with your actual tokens and IDs)
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
ADMIN_ID = 123456789          # Your Telegram User ID
ADMIN_CHANNEL_ID = -100123456789 # Admin Panel Channel ID for deposits/withdrawals

# MOCK DATABASES (Replace with real DB in production like PostgreSQL/SQLite)
ACTIVE_GIFT_CODES = {}
USER_BALANCES = {}
SAVED_UPIS = {}
SAVED_CRYPTO = {}

# CONVERSATION STATES
(
    DEP_METHOD,
    DEP_AMOUNT,
    DEP_WAIT_UTR,
    DEP_WAIT_SCREENSHOT,
    W_TYPE,
    W_AMOUNT,
    W_SAVE_ADDRESS
) = range(7)

# ==========================================
# 1. START & MAIN MENU
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    balance = USER_BALANCES.get(user_id, 0.0)
    
    text = (
        "<b>🎮 WELCOME TO VERSEBET BOT 🎮</b>\n\n"
        f"<b>👤 User:</b> {user.first_name}\n"
        f"<b>💰 Wallet Balance: ₹{balance:.2f}</b>\n\n"
        "<b>Choose an action from the menu below:</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("💰 Deposit", callback_data="menu_deposit"),
         InlineKeyboardButton("💸 Withdraw", callback_data="menu_withdraw")],
        [InlineKeyboardButton("🎲 Play Games", callback_data="menu_games"),
         InlineKeyboardButton("👤 Profile & Wallet", callback_data="menu_profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

# ==========================================
# 2. ADVANCED DEPOSIT SYSTEM
# ==========================================
async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🇮🇳 UPI Deposit", callback_data="dep_upi"),
         InlineKeyboardButton("🪙 Crypto Deposit", callback_data="dep_crypto")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    text = (
        "<b>💰 === DEPOSIT CENTER === 💰</b>\n\n"
        "<b>Select your preferred deposit method:</b>"
    )
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return DEP_AMOUNT

async def deposit_select_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    method = "UPI" if "upi" in query.data else "Crypto"
    context.user_data["dep_method"] = method
    
    text = (
        f"<b>🎯 {method} DEPOSIT SELECTED</b>\n\n"
        "<b>Enter your deposit amount (Range: ₹50 - ₹5000 / $10 - $1000):</b>"
    )
    await query.message.edit_text(text, parse_mode="HTML")
    return DEP_WAIT_UTR

async def deposit_receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("<b>❌ Invalid format! Please enter a valid amount between ₹50 and ₹5000:</b>", parse_mode="HTML")
        return DEP_WAIT_UTR

    if amount < 50 or amount > 5000:
        await update.message.reply_text("<b>⚠️ Limit Error: Amount must be between ₹50 and ₹5000. Try again:</b>", parse_mode="HTML")
        return DEP_WAIT_UTR

    context.user_data["dep_amount"] = amount
    method = context.user_data.get("dep_method", "UPI")
    
    pay_details = (
        "<code>merchantupi@oksbi</code>" if method == "UPI" else "<code>0xYourCryptoWalletAddressHere123456</code>"
    )
    
    pay_text = (
        f"<b>🎯 DEPOSIT ORDER GENERATED ({method})</b>\n\n"
        f"<b>Payable Amount: ₹{amount}</b>\n"
        f"<b>Target Address/UPI:</b> {pay_details}\n\n"
        "<b>👉 Step 1: Transfer exact funds to the details above.</b>\n"
        "<b>👉 Step 2: Click the button below once payment is completed.</b>"
    )
    
    keyboard = [[InlineKeyboardButton("✅ I Have Paid", callback_data="i_have_paid")]]
    await update.message.reply_text(pay_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return DEP_WAIT_SCREENSHOT

async def deposit_prompt_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "<b>📝 ENTER UTR CODE</b>\n\n"
        "<b>Please reply with your 12-digit unique transaction reference code (UTR):</b>"
    )
    await query.message.edit_text(text, parse_mode="HTML")
    return DEP_WAIT_SCREENSHOT

async def deposit_receive_utr_and_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if text is UTR or photo is screenshot
    if update.message.text and not context.user_data.get("dep_utr"):
        utr = update.message.text.strip()
        if len(utr) < 8:
            await update.message.reply_text("<b>❌ Invalid UTR code. Please send your valid 12-digit UTR code:</b>", parse_mode="HTML")
            return DEP_WAIT_SCREENSHOT
        context.user_data["dep_utr"] = utr
        await update.message.reply_text("<b>📸 UTR Saved! Now please upload your payment screenshot image:</b>", parse_mode="HTML")
        return DEP_WAIT_SCREENSHOT

    if update.message.photo:
        if not context.user_data.get("dep_utr"):
            await update.message.reply_text("<b>⚠️ Please type and send your 12-digit UTR code first before sending the screenshot.</b>", parse_mode="HTML")
            return DEP_WAIT_SCREENSHOT
            
        photo_file = update.message.photo[-1].file_id
        user = update.message.from_user
        amount = context.user_data.get("dep_amount")
        utr = context.user_data.get("dep_utr")
        method = context.user_data.get("dep_method")
        
        # Confirm user
        await update.message.reply_text(
            "<b>✅ DEPOSIT SUBMITTED SUCCESSFULLY!</b>\n\n"
            f"<b>Amount:</b> ₹{amount}\n"
            f"<b>UTR:</b> <code>{utr}</code>\n\n"
            "<b>Verified within 10-20 minutes by administration.</b>",
            parse_mode="HTML"
        )
        
        # Forward to Admin Channel
        admin_caption = (
            "<b>🔔 NEW DEPOSIT REQUEST PENDING</b>\n\n"
            f"<b>User:</b> {user.first_name} (@{user.username or 'None'})\n"
            f"<b>ID:</b> <code>{user.id}</code>\n"
            f"<b>Method:</b> {method}\n"
            f"<b>Amount: ₹{amount}</b>\n"
            f"<b>UTR:</b> <code>{utr}</code>"
        )
        admin_kb = [
            [InlineKeyboardButton("✅ Approve", callback_data=f"admin_app_{user.id}_{amount}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"admin_rej_{user.id}")]
        ]
        
        await context.bot.send_photo(
            chat_id=ADMIN_CHANNEL_ID,
            photo=photo_file,
            caption=admin_caption,
            reply_markup=InlineKeyboardMarkup(admin_kb),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    await update.message.reply_text("<b>❌ Please send a valid text UTR or image screenshot.</b>", parse_mode="HTML")
    return DEP_WAIT_SCREENSHOT

# ==========================================
# 3. ADVANCED WITHDRAWAL SYSTEM
# ==========================================
async def withdrawal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🇮🇳 Withdraw via UPI", callback_data="w_upi"),
         InlineKeyboardButton("🪙 Withdraw via Crypto", callback_data="w_crypto")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    text = "<b>💸 === WITHDRAWAL CENTER === 💸</b>\n\n<b>Select payout channel:</b>"
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return W_TYPE

async def withdrawal_choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    w_type = "UPI" if "upi" in query.data else "Crypto"
    context.user_data["w_type"] = w_type
    
    text = (
        f"<b>💸 {w_type} WITHDRAWAL</b>\n\n"
        "<b>Enter withdrawal amount (₹50 - ₹5000 / $10 - $1000):</b>"
    )
    await query.message.edit_text(text, parse_mode="HTML")
    return W_AMOUNT

async def withdrawal_process_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("<b>❌ Invalid amount format. Enter a valid number:</b>", parse_mode="HTML")
        return W_AMOUNT

    user_id = update.message.from_user.id
    w_type = context.user_data.get("w_type")
    
    # Check saved addresses
    saved_address = SAVED_UPIS.get(user_id) if w_type == "UPI" else SAVED_CRYPTO.get(user_id)
    
    if not saved_address:
        keyboard = [[InlineKeyboardButton(f"➕ Add {w_type} Address", callback_data=f"save_{w_type.lower()}")]]
        text = (
            f"<b>❌ {w_type} ADDRESS NOT FOUND!</b>\n\n"
            f"<b>You have not saved your payout address yet. Click below to configure via command:</b>"
        )
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return ConversationHandler.END

    success_msg = (
        "<b>✅ WITHDRAWAL REQUEST PLACED!</b>\n\n"
        f"<b>Method:</b> {w_type}\n"
        f"<b>Amount:</b> ₹{amount}\n"
        f"<b>Destination:</b> <code>{saved_address}</code>\n\n"
        "<b>Payout queued and will reach your wallet within 1-3 hours.</b>"
    )
    await update.message.reply_text(success_msg, parse_mode="HTML")
    return ConversationHandler.END

# Save Payout Commands
async def save_upi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("<b>Usage:</b> <code>/saveupi yourname@okhdfcbank</code>", parse_mode="HTML")
        return
    upi = args[0]
    SAVED_UPIS[user_id] = upi
    await update.message.reply_text(f"<b>✅ UPI ID Saved Successfully:</b> <code>{upi}</code>", parse_mode="HTML")

async def save_crypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("<b>Usage:</b> <code>/savecrypto [WalletAddress]</code>", parse_mode="HTML")
        return
    wallet = args[0]
    SAVED_CRYPTO[user_id] = wallet
    await update.message.reply_text(f"<b>✅ Crypto Wallet Saved Successfully:</b> <code>{wallet}</code>", parse_mode="HTML")

# ==========================================
# 4. GIFT CODE & ADMIN PANEL SYSTEM
# ==========================================
async def create_gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("<b>⛔ Unauthorized Access.</b>", parse_mode="HTML")
        return

    args = context.args
    if not args:
        await update.message.reply_text("<b>Usage:</b> <code>/creategift [amount]</code>", parse_mode="HTML")
        return

    try:
        amount = float(args[0])
    except ValueError:
        await update.message.reply_text("<b>❌ Invalid amount format.</b>", parse_mode="HTML")
        return

    code = f"VERSE-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
    ACTIVE_GIFT_CODES[code] = amount

    response = (
        "<b>🎁 GIFT CODE GENERATED!</b>\n\n"
        f"<b>Code:</b> <code>{code}</code>\n"
        f"<b>Value: ₹{amount}</b>\n\n"
        f"<b>Redeem command:</b> <code>/claim {code}</code>"
    )
    await update.message.reply_text(response, parse_mode="HTML")

async def claim_gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("<b>Usage:</b> <code>/claim [GIFT-CODE]</code>", parse_mode="HTML")
        return

    code = args[0].strip().upper()
    user_id = update.effective_user.id

    if code in ACTIVE_GIFT_CODES:
        amount = ACTIVE_GIFT_CODES.pop(code)
        USER_BALANCES[user_id] = USER_BALANCES.get(user_id, 0.0) + amount
        
        await update.message.reply_text(
            "<b>🎉 GIFT CODE CLAIMED SUCCESSFULLY!</b>\n\n"
            f"<b>Credited Balance: ₹{amount}</b>\n"
            f"<b>New Wallet Balance: ₹{USER_BALANCES[user_id]:.2f}</b>",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("<b>❌ Invalid or expired gift code!</b>", parse_mode="HTML")

# Admin Approval Callback Handler
async def admin_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    action = parts[1] # app or rej
    target_user_id = int(parts[2])
    
    if action == "app":
        amount = float(parts[3])
        USER_BALANCES[target_user_id] = USER_BALANCES.get(target_user_id, 0.0) + amount
        
        await query.edit_message_caption(caption=f"<b>✅ APPROVED & CREDITED (₹{amount})</b>", parse_mode="HTML")
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"<b>🎉 YOUR DEPOSIT OF ₹{amount} HAS BEEN APPROVED & CREDITED TO YOUR WALLET!</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    elif action == "rej":
        await query.edit_message_caption(caption="<b>❌ REJECTED BY ADMIN</b>", parse_mode="HTML")
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="<b>❌ Your deposit was rejected by administration.</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

# ==========================================
# 5. MINI GAMES MODULE
# ==========================================
async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🎲 Roll Dice Game", callback_data="play_dice"),
         InlineKeyboardButton("🪙 Coin Toss Game", callback_data="play_coin")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    text = "<b>🎮 === VERSEBET GAMES === 🎮</b>\n\n<b>Select your instant game option:</b>"
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def play_dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_dice(chat_id=query.message.chat_id, emoji="🎲")

async def play_coin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    outcome = random.choice(["HEADS", "TAILS"])
    text = f"<b>🪙 Coin Toss Result: {outcome}!</b>\n\n<b>Try again to double your balance!</b>"
    keyboard = [[InlineKeyboardButton("🔄 Toss Again", callback_data="play_coin"),
                 InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ==========================================
# APPLICATION ROUTER CONFIGURATION
# ==========================================
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation Handlers
    deposit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(deposit_start, pattern="^menu_deposit$")],
        states={
            DEP_AMOUNT: [CallbackQueryHandler(deposit_select_method, pattern="^dep_")],
            DEP_WAIT_UTR: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_receive_amount)],
            DEP_WAIT_SCREENSHOT: [
                CallbackQueryHandler(deposit_prompt_utr, pattern="^i_have_paid$"),
                MessageHandler(filters.TEXT | filters.PHOTO, deposit_receive_utr_and_screenshot)
            ],
        },
        fallbacks=[CallbackQueryHandler(start_command, pattern="^main_menu$")]
    )

    withdraw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(withdrawal_start, pattern="^menu_withdraw$")],
        states={
            W_TYPE: [CallbackQueryHandler(withdrawal_choose_type, pattern="^w_")],
            W_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, withdrawal_process_amount),
                CallbackQueryHandler(start_command, pattern="^save_")
            ],
        },
        fallbacks=[CallbackQueryHandler(start_command, pattern="^main_menu$")]
    )

    # Core Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("saveupi", save_upi_command))
    application.add_handler(CommandHandler("savecrypto", save_crypto_command))
    application.add_handler(CommandHandler("creategift", create_gift_command))
    application.add_handler(CommandHandler("claim", claim_gift_command))

    application.add_handler(deposit_conv)
    application.add_handler(withdraw_conv)

    # Menu & Game Callbacks
    application.add_handler(CallbackQueryHandler(start_command, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(games_menu, pattern="^menu_games$"))
    application.add_handler(CallbackQueryHandler(play_dice_game, pattern="^play_dice$"))
    application.add_handler(CallbackQueryHandler(play_coin_game, pattern="^play_coin$"))
    application.add_handler(CallbackQueryHandler(admin_approval_callback, pattern="^admin_"))

    # Start the Bot
    print("Bot is up and running smoothly...")
    application.run_polling()

if __name__ == "__main__":
    main()
