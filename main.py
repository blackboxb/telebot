import telebot
import sqlite3
import threading
import time

bot = telebot.TeleBot("7573502469:AAGGyXpPFlzUwUJ3NpfzF9S0dGvDgk2ewKM")
store_open = True
conn = sqlite3.connect("blackbox.db", check_same_thread=False)
cursor = conn.cursor()

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

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, f"Hey! {message.from_user.first_name}, welcome to Black Box! Use /order to place an order.")

@bot.message_handler(commands=['order'])
def order(message):
    bot.reply_to(message, "Please enter your name:")
    bot.register_next_step_handler(message, get_name)

def get_name(message):
    name = message.text
    bot.send_message(message.chat.id, "Enter your mobile number:")
    bot.register_next_step_handler(message, get_mobile, name)

def get_mobile(message, name):
    mobile = message.text
    bot.send_message(message.chat.id, "Select your hostel: KBH or GBH")
    bot.register_next_step_handler(message, get_hostel, name, mobile)

def get_hostel(message, name, mobile):
    hostel = message.text
    bot.send_message(message.chat.id, "Select your wing: East, West, or South")
    bot.register_next_step_handler(message, get_wing, name, mobile, hostel)

def get_wing(message, name, mobile, hostel):
    wing = message.text
    bot.send_message(message.chat.id, f"Confirm order?\nName: {name}\nMobile: {mobile}\nHostel: {hostel}\nWing: {wing}\nType 'yes' to confirm or 'cancel' to abort.")
    bot.register_next_step_handler(message, confirm_order, name, mobile, hostel, wing)

def confirm_order(message, name, mobile, hostel, wing):
    if message.text.lower() == 'yes':
        cursor.execute("INSERT INTO orders (name, mobile, hostel, wing, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                       (name, mobile, hostel, wing, "Pending", int(time.time())))
        conn.commit()
        bot.send_message(message.chat.id, "Your order has been placed! Managers will confirm soon.")
    else:
        bot.send_message(message.chat.id, "Order cancelled.")

@bot.message_handler(commands=['view_orders'])
def view_orders(message):
    cursor.execute("SELECT * FROM orders WHERE status='Pending'")
    orders = cursor.fetchall()
    response = "Pending Orders:\n" + '\n'.join([f"{order[0]} - {order[1]} ({order[2]})" for order in orders]) if orders else "No pending orders."
    bot.reply_to(message, response)

@bot.message_handler(commands=['accept_order'])
def accept_order(message):
    order_id = message.text.split()[1]
    cursor.execute("UPDATE orders SET status='Accepted' WHERE id=?", (order_id,))
    conn.commit()
    bot.reply_to(message, f"Order {order_id} accepted.")

@bot.message_handler(commands=['cancel_order'])
def cancel_order(message):
    order_id = message.text.split()[1]
    cursor.execute("UPDATE orders SET status='Cancelled' WHERE id=?", (order_id,))
    conn.commit()
    bot.reply_to(message, f"Order {order_id} cancelled.")

@bot.message_handler(commands=['toggle_store'])
def toggle_store(message):
    global store_open
    store_open = not store_open
    bot.reply_to(message, f"Store is now {'OPEN' if store_open else 'CLOSED'}.")

@bot.message_handler(commands=['add_inventory'])
def add_inventory(message):
    args = message.text.split()
    item, quantity = args[1], int(args[2])
    cursor.execute("INSERT INTO inventory (item, quantity) VALUES (?, ?) ON CONFLICT(item) DO UPDATE SET quantity = quantity + ?", (item, quantity, quantity))
    conn.commit()
    bot.reply_to(message, f"Added {quantity} of {item} to inventory.")

@bot.message_handler(commands=['check_inventory'])
def check_inventory(message):
    cursor.execute("SELECT * FROM inventory")
    items = cursor.fetchall()
    response = "Inventory:\n" + '\n'.join([f"{item[0]}: {item[1]}" for item in items]) if items else "Inventory is empty."
    bot.reply_to(message, response)

def pending_order_reminder():
    while True:
        time.sleep(300)
        cursor.execute("SELECT id FROM orders WHERE status='Pending' AND timestamp <= ?", (int(time.time()) - 300,))
        pending_orders = cursor.fetchall()
        if pending_orders:
            message = "Reminder: The following orders are still pending: " + ', '.join([str(order[0]) for order in pending_orders])
            print("Managers should be notified:", message)

def main():
    threading.Thread(target=pending_order_reminder, daemon=True).start()
    bot.polling()

if __name__ == '__main__':
    main()
