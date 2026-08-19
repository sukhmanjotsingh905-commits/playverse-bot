import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

ADMIN_BOT_TOKEN = "8963774797:AAGrUY3BXQXB3wSqVqPoascdktlZqql3SEw"
PLAYVERSE_BOT_TOKEN = "8955259098:AAEHDsM2TvsMNrAI1SNz1zyQC5UbCtw_rk4"

async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    parts = data.split("_")
    action = parts[0]   # app or rej
    type_tx = parts[1]  # dep or wd
    user_id = int(parts[2])
    amount = float(parts[3])

    conn = sqlite3.connect("playverse.db")
    cursor = conn.cursor()

    if type_tx == "dep":
        if action == "app":
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            cursor.execute("UPDATE transactions SET status = 'APPROVED' WHERE user_id = ? AND type = 'DEPOSIT' AND status = 'PENDING'", (user_id,))
            conn.commit()
            await query.edit_message_text(f"✅ Deposit of ₹{amount} for user `{user_id}` has been APPROVED and credited.")
            
            # Notify user via main bot
            app_main = Application.builder().token(PLAYVERSE_BOT_TOKEN).build()
            async with app_main:
                await app_main.bot.send_message(chat_id=user_id, text=f"Your deposit of ₹{amount} has been successfully approved & credited! ✅")
        else:
            cursor.execute("UPDATE transactions SET status = 'REJECTED' WHERE user_id = ? AND type = 'DEPOSIT' AND status = 'PENDING'", (user_id,))
            conn.commit()
            await query.edit_message_text(f"❌ Deposit of ₹{amount} for user `{user_id}` was REJECTED.")
            
            app_main = Application.builder().token(PLAYVERSE_BOT_TOKEN).build()
            async with app_main:
                await app_main.bot.send_message(chat_id=user_id, text=f"Your deposit request of ₹{amount} was rejected by admin ❌")

    elif type_tx == "wd":
        if action == "app":
            cursor.execute("UPDATE transactions SET status = 'PAID' WHERE user_id = ? AND type = 'WITHDRAWAL' AND status = 'PENDING'", (user_id,))
            conn.commit()
            await query.edit_message_text(f"✅ Withdrawal of ₹{amount} for user `{user_id}` marked as PAID.")
            
            app_main = Application.builder().token(PLAYVERSE_BOT_TOKEN).build()
            async with app_main:
                await app_main.bot.send_message(chat_id=user_id, text=f"Your withdrawal request of ₹{amount} has been approved & paid to your UPI! ✅")
        else:
            # Refund balance if rejected
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            cursor.execute("UPDATE transactions SET status = 'REJECTED' WHERE user_id = ? AND type = 'WITHDRAWAL' AND status = 'PENDING'", (user_id,))
            conn.commit()
            await query.edit_message_text(f"❌ Withdrawal of ₹{amount} for user `{user_id}` was REJECTED and refunded.")
            
            app_main = Application.builder().token(PLAYVERSE_BOT_TOKEN).build()
            async with app_main:
                await app_main.bot.send_message(chat_id=user_id, text=f"Your withdrawal of ₹{amount} was rejected. Amount refunded to wallet.")

    conn.close()

def main():
    app = Application.builder().token(ADMIN_BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(admin_callbacks))
    print("Admin Notification Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
