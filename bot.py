import sqlite3
import threading
import time
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# Define states for order process
NAME, MOBILE, HOSTEL, WING, CONFIRM_ORDER = range(5)

# Store status (open/closed)
store_open = True

# Connect to database
conn = sqlite3.connect("blackbox.db", check_same_thread=False)
cursor = conn.cursor()

# Create tables
cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY, 
                    name TEXT, 
                    mobile TEXT, 
                    hostel TEXT, 
                    wing TEXT, 
                    status TEXT, 
                    timestamp INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    item TEXT PRIMARY KEY, 
                    quantity INTEGER)''')
conn.commit()

def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Welcome to Black Box! Please enter your name:")
    return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    context.user_data['name'] = update.message.text
    update.message.reply_text("Enter your mobile number:")
    return MOBILE

def get_mobile(update: Update, context: CallbackContext) -> int:
    context.user_data['mobile'] = update.message.text
    update.message.reply_text("Select your hostel:", reply_markup=ReplyKeyboardMarkup([['KBH', 'GBH']], one_time_keyboard=True))
    return HOSTEL

def get_hostel(update: Update, context: CallbackContext) -> int:
    context.user_data['hostel'] = update.message.text
    update.message.reply_text("Select your wing:", reply_markup=ReplyKeyboardMarkup([['East', 'West', 'South']], one_time_keyboard=True))
    return WING

def get_wing(update: Update, context: CallbackContext) -> int:
    context.user_data['wing'] = update.message.text
    update.message.reply_text(f"Confirm order?\nName: {context.user_data['name']}\nMobile: {context.user_data['mobile']}\nHostel: {context.user_data['hostel']}\nWing: {context.user_data['wing']}", 
                              reply_markup=ReplyKeyboardMarkup([['Yes', 'Cancel']], one_time_keyboard=True))
    return CONFIRM_ORDER

def confirm_order(update: Update, context: CallbackContext) -> int:
    if update.message.text.lower() == 'yes':
        cursor.execute("INSERT INTO orders (name, mobile, hostel, wing, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                       (context.user_data['name'], context.user_data['mobile'], context.user_data['hostel'], context.user_data['wing'], "Pending", int(time.time())))
        conn.commit()
        update.message.reply_text("Your order has been placed! Managers will confirm soon.")
    else:
        update.message.reply_text("Order cancelled.")
    return ConversationHandler.END

def view_orders(update: Update, context: CallbackContext):
    cursor.execute("SELECT * FROM orders WHERE status='Pending'")
    orders = cursor.fetchall()
    if orders:
        message = "Pending Orders:\n" + '\n'.join([f"{order[0]} - {order[1]} ({order[2]})" for order in orders])
    else:
        message = "No pending orders."
    update.message.reply_text(message)

def accept_order(update: Update, context: CallbackContext):
    order_id = context.args[0]
    cursor.execute("UPDATE orders SET status='Accepted' WHERE id=?", (order_id,))
    conn.commit()
    update.message.reply_text(f"Order {order_id} accepted.")

def cancel_order(update: Update, context: CallbackContext):
    order_id = context.args[0]
    cursor.execute("UPDATE orders SET status='Cancelled' WHERE id=?", (order_id,))
    conn.commit()
    update.message.reply_text(f"Order {order_id} cancelled.")

def update_order_status(update: Update, context: CallbackContext):
    order_id, status = context.args[0], context.args[1]
    cursor.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    update.message.reply_text(f"Order {order_id} updated to {status}.")

def toggle_store(update: Update, context: CallbackContext):
    global store_open
    store_open = not store_open
    update.message.reply_text(f"Store is now {'OPEN' if store_open else 'CLOSED'}.")

def add_inventory(update: Update, context: CallbackContext):
    item, quantity = context.args[0], int(context.args[1])
    cursor.execute("INSERT INTO inventory (item, quantity) VALUES (?, ?) ON CONFLICT(item) DO UPDATE SET quantity = quantity + ?", (item, quantity, quantity))
    conn.commit()
    update.message.reply_text(f"Added {quantity} of {item} to inventory.")

def check_inventory(update: Update, context: CallbackContext):
    cursor.execute("SELECT * FROM inventory")
    items = cursor.fetchall()
    message = "Inventory:\n" + '\n'.join([f"{item[0]}: {item[1]}" for item in items]) if items else "Inventory is empty."
    update.message.reply_text(message)

def pending_order_reminder():
    while True:
        time.sleep(300)  # Check every 5 minutes
        cursor.execute("SELECT id FROM orders WHERE status='Pending' AND timestamp <= ?", (int(time.time()) - 300,))
        pending_orders = cursor.fetchall()
        if pending_orders:
            message = "Reminder: The following orders are still pending: " + ', '.join([str(order[0]) for order in pending_orders])
            print("Managers should be notified:", message)  # Replace with bot notification

def main():
    updater = Updater("YOUR_BOT_TOKEN", use_context=True)
    dp = updater.dispatcher

    threading.Thread(target=pending_order_reminder, daemon=True).start()

    order_conv = ConversationHandler(
        entry_points=[CommandHandler('order', start)],
        states={
            NAME: [MessageHandler(Filters.text & ~Filters.command, get_name)],
            MOBILE: [MessageHandler(Filters.text & ~Filters.command, get_mobile)],
            HOSTEL: [MessageHandler(Filters.text & ~Filters.command, get_hostel)],
            WING: [MessageHandler(Filters.text & ~Filters.command, get_wing)],
            CONFIRM_ORDER: [MessageHandler(Filters.text & ~Filters.command, confirm_order)]
        },
        fallbacks=[]
    )

    dp.add_handler(order_conv)
    dp.add_handler(CommandHandler("view_orders", view_orders))
    dp.add_handler(CommandHandler("accept_order", accept_order))
    dp.add_handler(CommandHandler("cancel_order", cancel_order))
    dp.add_handler(CommandHandler("update_order_status", update_order_status))
    dp.add_handler(CommandHandler("toggle_store", toggle_store))
    dp.add_handler(CommandHandler("add_inventory", add_inventory))
    dp.add_handler(CommandHandler("check_inventory", check_inventory))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()