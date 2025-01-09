import os
import math
import time 
import boto3
import base58
import random
import asyncio
import logging
import asyncio
import aiomysql
import warnings
import threading
import pymysql.cursors
from sendSPL import send_spl
from dotenv import load_dotenv
from balance import get_balance
from solders.keypair import Keypair
from play import coinflip_game, dice_roll_game
from solana_utils import get_solana_token_amount
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext, ContextTypes
from dbcalls import generate_wallets_if_needed,save_wallet_address_new, get_credit_balance,save_wallet_address,get_wallet_address,get_private_key,get_game_private_key,get_game_wallet,get_burn_wallet,get_wallet_address_by_user_id,get_user_referrers,get_user_ref_earned,increment_user_earned_balance,increment_user_credit_balance,decrement_user_credit_balance,get_referral_counts,get_total_volume,increment_volume_total,decrement_volume_total

warnings.simplefilter("ignore")
load_dotenv('.env')
logging.basicConfig(level=logging.ERROR)

TOKEN = os.getenv('TOKEN')  
DB_NAME = os.getenv('DB_NAME')  
DB_HOST = os.getenv('DB_HOST')  
DB_USER = os.getenv('DB_USER')  
DB_PASSWORD = os.getenv('DB_PASSWORD')
GROUPID = int(os.getenv('TG_GROUP_ID'))  
END = 0
AUTHORIZED_USER_ID = os.getenv('AUTHORIZED_USER_ID')
bot = Bot(token=TOKEN)

#ADD YOUR DATABASE DETAILS HERE FOR DB CLIENT CREATION

user_last_start_time = {}
START_COMMAND_COOLDOWN = 1  
MAX_START_COMMAND_COOLDOWN = 30  
user_last_start_time = {}  
user_spam_count = {}  
user_notified = {}  

# Replace with your own photos :P

photo_filename1 = 'cf_winner.png'
photo_filename2 = 'dr_winner.png'
photo_filename3 = 'hl_winner.png'
photo_filename4 = 'burn.jpg'
photo_filename5 = 'winner.mp4'


CARD_RANK_VALUES = {
    'Ace': 1,
    '2': 2,
    '3': 3,
    '4': 4,
    '5': 5,
    '6': 6,
    '7': 7,
    '8': 8,
    '9': 9,
    '10': 10,
    'Jack': 11,
    'Queen': 12,
    'King': 13
}

CARD_STICKERS = {
    ('Ace', 'Spades'): 'CAACAgUAAxkBAAEwfwFndn3sH1RrNG1iAAGYkzKYlaUBldkAAnsBAAKAmcBV4Pja_u4WWqA2BA',
    #ADD stickers for full deck :)
}

async def setup_database():
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
            await cursor.execute(f"USE {DB_NAME}")
            await cursor.execute(f"GRANT ALL PRIVILEGES ON {DB_NAME}.* TO '{DB_USER}'@'%'")
            await cursor.execute("FLUSH PRIVILEGES")
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS table1 (
                    user_id BIGINT PRIMARY KEY,
                    wallet_address TEXT NOT NULL,
                    token_balance BIGINT,
                    # ADD your specific encrypted private key data here
                    referrer_id BIGINT,
                    second_level_referrer_id BIGINT,
                    earned DOUBLE DEFAULT 0,
                    FOREIGN KEY(referrer_id) REFERENCES table1(user_id),
                    FOREIGN KEY(second_level_referrer_id) REFERENCES table1(user_id)
                )
            ''')
            
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS table2 (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    wallet_address TEXT NOT NULL,
                    #ADD your specific encrypted private key data here
                    token_balance DOUBLE DEFAULT 0,
                    total_volume DOUBLE DEFAULT 0
                )
            ''')

            await asyncio.shield(generate_wallets_if_needed(cursor, 'table2'))

    pool.close()
    await pool.wait_closed()

    await asyncio.create_task(handle_burn())

async def private_chat_only(update: Update, context: CallbackContext):
    if update.effective_chat.type != 'private':
    
        return False
    return True

async def create_start_task(update: Update, context: CallbackContext) -> None:
    if not await private_chat_only(update, context):
        return

    user_id = update.effective_user.id
    current_time = time.time()

    if user_id in user_last_start_time:
        last_call_time = user_last_start_time[user_id]
        time_diff = current_time - last_call_time
        if time_diff < START_COMMAND_COOLDOWN:
            if user_id in user_spam_count:
                user_spam_count[user_id] += 1
            else:
                user_spam_count[user_id] = 1
            cooldown_time = START_COMMAND_COOLDOWN + (user_spam_count[user_id] * 3)
            cooldown_time = min(cooldown_time, MAX_START_COMMAND_COOLDOWN)
            if user_id not in user_notified:
                user_notified[user_id] = True
                await update.message.reply_text(
                    f"Please wait {cooldown_time} seconds before trying again."
                )
            return
        else:
            user_spam_count[user_id] = 0
            user_notified[user_id] = False
    user_last_start_time[user_id] = current_time

    asyncio.create_task(start(update, context, user_id))

async def start(update: Update, context: CallbackContext, user_id: int = None) -> None:

    if update and update.message and update.message.chat.type != "private":
        return

    if user_id and update and update.message and update.message.from_user.id != user_id:
        return
    
    await asyncio.sleep(1)

    try:
        if update.message:
            user_id = update.message.from_user.id

        wallet_address = await asyncio.shield(get_wallet_address(user_id))
        if wallet_address:
            balance = await asyncio.shield(get_balance(wallet_address))

            balance_rounded = math.floor(balance * 1000) / 1000
            balance_formatted = f"{balance_rounded:.3f}"
            balance_spl = await asyncio.shield(get_solana_token_amount(wallet_address))
            balance_spl_rounded = math.floor(balance_spl * 1000) / 1000
            balance_spl_formatted = f"{balance_spl_rounded:.3f}"
            credits = await get_credit_balance(user_id)
            welcome_message = (f"*Welcome to DeFlip!*\n\n"
                                f"🌟 *Exciting Crypto Games!*\n"
                                f"Try your luck in any DeFlip Games!\n\n"
                                f"•Deposit DeFlip Tokens to your wallet + enough Sol to cover transactional gas.\n"
                                f"•Deposit/Exchange DeFlip Tokens for Credits (You need credits to play) \n"
                                f"•Select the game you would like to play\n"
                                f"•Bet and may the odds be in your favour\n\n"
                                f"Refer friends to earn up to 15% of their bets\n\n"
                                f"*GAME CREDITS: {credits}*\n\n"
                                f"Balance: {balance_formatted} Sol\n"
                                f"Token: {balance_spl_formatted} DeFlip\n\n"
                                f"Wallet: `{wallet_address}`"
                                )                      
        else:
            private_key = Keypair()
            new_wallet = private_key.pubkey()  
            private_key_str = str(private_key)
            new_wallet_str = str(new_wallet)
            earned = 0
            spl_balance = 0
            credits = "0"
            token_balance = 0
            referrer_id = context.args[0] if context.args else None
            await asyncio.shield(save_wallet_address_new(user_id, new_wallet_str, token_balance, private_key_str, earned, referrer_id))
            balance = 0.0
            balance_rounded = math.floor(balance * 1000) / 1000
            balance_formatted = f"{balance_rounded:.3f}"
            welcome_message = (f"*Welcome to DeFlip!*\n\n"
                                f"🌟 *Exciting Crypto Games!*\n"
                                f"Try your luck in any DeFlip Games!\n\n"
                                f"•Deposit DeFlip Tokens to your wallet + enough Sol to cover transactional gas.\n"
                                f"•Deposit/Exchange DeFlip Tokens for Credits (You need credits to play) \n"
                                f"•Select the game you would like to play\n"
                                f"•Bet and may the odds be in your favour\n\n"
                                f"Refer friends to earn up to 15% of their bets\n\n"
                                f"*GAME CREDITS: {credits}*\n\n"
                                f"Balance: {balance_formatted} Sol\n"
                                f"Token: {spl_balance} DeFlip\n\n"
                                f"Wallet: `{new_wallet_str}`"
                                f"Your Wallet was auto generated"
                                )
        keyboard = [
                [InlineKeyboardButton("🕹 Play CoinFlip", callback_data='coinflip'),InlineKeyboardButton("🕹 Play Dice", callback_data='dice')],
                [InlineKeyboardButton("🕹 Play High/Low", callback_data='hl')],
                [InlineKeyboardButton("Withdraw", callback_data='withdraw'),InlineKeyboardButton("Deposit", callback_data='exchange')],
                [InlineKeyboardButton("How to Play?", callback_data='learn_more'),InlineKeyboardButton("Wallet", callback_data='wallet')],
                [InlineKeyboardButton("Referral", callback_data='referral')]
            ]
            
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.message:
            await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode = "markdown")
        else:
            await context.bot.send_message(chat_id=user_id, text=welcome_message, reply_markup=reply_markup,parse_mode = "markdown")
    except Exception as e:
        logging.error(f"Error processing start command for user {user_id}: {e}")
    
#CALLBACKS START

async def button(update: Update, context: Application) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    async def handle_query():

        if query.data == 'learn_more':
            how_it_works_message = (
                f"*How It Works:*\n\n"
                f"🎮 *Games Available:*\n\n"
                f"1️⃣ *Coin Flip*: Pays out *1.75x* your bet.\n"
                f"2️⃣ *Dice*: Pays out *4.5x* your bet.\n"
                f"3️⃣ *High/Low*: Pays out up to *2x* your bet.\n\n"
                f"🔥 *Token Burning Mechanics:*\n\n"
                f"• Every time someone loses, a percentage of their DeFlip Tokens is allocated for burning.\n"
                f"• If a user *loses*, *50% of their bet* is allocated to burning.\n\n"
                f"💱 *Deposit and Withdraw:*\n\n"
                f"• *Deposit*: Convert DeFlip Tokens into Game Credits to play games.\n"
                f"• *Withdraw*: Convert Game Credits back into DeFlip Tokens at a rate of *1:1*.\n\n"
                f"🎁 *Referrals:*\n\n"
                f"• Earn *10%* of the bet amount every time your referred user places a bet.\n"
                f"• Earn an additional *5%* of the bet amount from the users referred by your referrals (second-level referrals).\n"
                f"• This applies regardless of whether the referred users win or lose their bets.\n"
                f"• Referrals are a win-win for everyone! Share your unique referral link and start earning extra rewards!\n\n"
                f"May the odds be in your favor! 🚀"
            )
            await query.edit_message_text(how_it_works_message, parse_mode='Markdown')

            await start(update, context, user_id=user_id)



        elif query.data == 'exchange':
            keyboard = [
                [InlineKeyboardButton("10 000 DeFlip", callback_data='deposit_10000'),InlineKeyboardButton("25 000 DeFlip", callback_data='deposit_25000')],
                [InlineKeyboardButton("50 000 DeFlip", callback_data='deposit_50000'),InlineKeyboardButton("100 000 DeFlip", callback_data='deposit_100000')],
                [InlineKeyboardButton("250 000 DeFlip", callback_data='deposit_250000'),InlineKeyboardButton("500 000 DeFlip", callback_data='deposit_500000')],
                [InlineKeyboardButton("1 000 000 DeFlip", callback_data='deposit_1000000'),InlineKeyboardButton("2 000 000 DeFlip", callback_data='deposit_2000000')],
                [InlineKeyboardButton("Cancel", callback_data='no_deposit')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Select the amount of DeFlip you'd like to Deposit:\n\n1 DeFlip = 1 Credit",
                reply_markup=reply_markup
            )

        elif query.data == 'hl':
            credits_available = await get_credit_balance(user_id)
            credits_available_int = int(credits_available)
            if credits_available_int >=1000:
                keyboard = [
                    [InlineKeyboardButton("1 000 ", callback_data='hl_1000'),InlineKeyboardButton("5 000 ", callback_data='hl_5000')],
                    [InlineKeyboardButton("10 000 ", callback_data='hl_10000'),InlineKeyboardButton("25 000 ", callback_data='hl_25000')],
                    [InlineKeyboardButton("50 000 ", callback_data='hl_50000'),InlineKeyboardButton("100 000 ", callback_data='hl_100000')],
                    [InlineKeyboardButton("Cancel", callback_data='no_deposit')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "Select the amount you would like to bet",
                    reply_markup=reply_markup
                )
            else:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
                message = (f"Not enough Credits!\n"
                            f"Please exchnage DeFlip to credits from the deposit menu\n"
                            f"The minimum bet is 1000 Credits"
                            )
                insufficient_message = await context.bot.send_message(chat_id=user_id, text=message)

                await start(update, context, user_id=user_id)

        elif query.data.startswith("deposit_"):

            selected_deposit_amount = query.data.split('_')[-1]
            transfer_spl =  await handle_deposit(update, context,query,user_id,selected_deposit_amount) 

        elif query.data.startswith("hl_"):

            selected_bet1_amount = query.data.split('_')[-1]
            selected_bet1_amount_int = int(selected_bet1_amount)
            credit_balance = await get_credit_balance(user_id)
            credit_balance_int = int(credit_balance)
            if credit_balance_int >= selected_bet1_amount_int:
                hl_game =  await high_low_game(update, context,query,user_id,selected_bet1_amount)

            else:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
                message = (f"Not enough Credits!\n"
                            f"Please exchnage DeFlip to credits from the deposit menu\n"
                            )
                insufficient_message = await context.bot.send_message(chat_id=user_id, text=message)

                await start(update, context, user_id=user_id)  

        elif query.data == 'coinflip':

            credits_available = await get_credit_balance(user_id)
            credits_available_int = int(credits_available)
            if credits_available_int >= 1000:
                keyboard = [
                    [InlineKeyboardButton("Heads", callback_data='coinflip_heads')],
                    [InlineKeyboardButton("Tails", callback_data='coinflip_tails')],
                    [InlineKeyboardButton("Cancel", callback_data='no_deposit')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "Place your bets!!\n\nSelect Heads or Tails",
                    reply_markup=reply_markup
                )
            
            else:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
                message = (f"Not enough Credits!\n"
                            f"Please exchnage DeFlip to credits from the deposit menu\n"
                            f"The minimum bet is 1000 Credits"
                            )
                insufficient_message = await context.bot.send_message(chat_id=user_id, text=message)

                await start(update, context, user_id=user_id)

        elif query.data.startswith('coinflip_'):

            selected_choice = query.data.split('_')[-1]
            keyboard2 = [
                [InlineKeyboardButton("1 000", callback_data=f'coin_bet_1000_{selected_choice}'),InlineKeyboardButton("5 000", callback_data=f'coin_bet_5000_{selected_choice}')],
                [InlineKeyboardButton("10 000", callback_data=f'coin_bet_10000_{selected_choice}'),InlineKeyboardButton("25 000", callback_data=f'coin_bet_25000_{selected_choice}')],
                [InlineKeyboardButton("50 000", callback_data=f'coin_bet_50000_{selected_choice}'),InlineKeyboardButton("100 000", callback_data=f'coin_bet_100000_{selected_choice}')],
                [InlineKeyboardButton("Cancel", callback_data='no_deposit')]
            ]
            reply_markup2 = InlineKeyboardMarkup(keyboard2)
            await query.edit_message_text(
                f"You selected {selected_choice}.\n\nNow select bet amount",
                reply_markup=reply_markup2
            )

        elif query.data.startswith('coin_bet_'):
            
            parts = query.data.split('_')
            bet_amount = int(parts[2])
            selected_choice = parts[3]
            credit_balance = await get_credit_balance(user_id)
            credit_balance_int = int(credit_balance)
            if credit_balance_int >= bet_amount:
                await handle_coinflip(update, context, query, user_id, bet_amount, selected_choice)

            else:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
                message = (f"Not enough Credits to cover your bet!\n"
                            f"Please exchnage DeFlip to credits from the deposit menu\n"
                            )
                insufficient_message = await context.bot.send_message(chat_id=user_id, text=message)

                await start(update, context, user_id=user_id)
                
        elif query.data == 'dice':

            credits_available = await get_credit_balance(user_id)
            credits_available_int = int(credits_available)
            if credits_available_int >= 1000: 
                keyboard = [
                    [InlineKeyboardButton("1", callback_data='dice_num_1'), InlineKeyboardButton("2", callback_data='dice_num_2')],
                    [InlineKeyboardButton("3", callback_data='dice_num_3'), InlineKeyboardButton("4", callback_data='dice_num_4')],
                    [InlineKeyboardButton("5", callback_data='dice_num_5'), InlineKeyboardButton("6", callback_data='dice_num_6')],
                    [InlineKeyboardButton("Cancel", callback_data='no_deposit')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    f"Place your bets!!\n\nSelect the number you want to bet on:",
                    reply_markup=reply_markup
                )

            else:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
                message = (f"Not enough Credits!\n"
                            f"Please exchnage DeFlip to credits from the deposit menu\n"
                            f"The minimum bet is 1000 Credits"
                            )
                insufficient_message = await context.bot.send_message(chat_id=user_id, text=message)

                await start(update, context, user_id=user_id)

        elif query.data.startswith('dice_num_'):
            selected_number = int(query.data.split('_')[-1])

            keyboard = [
                [InlineKeyboardButton("1 000", callback_data=f'dice_bet_1000_{selected_number}'),InlineKeyboardButton("5 000", callback_data=f'dice_bet_5000_{selected_number}')],
                [InlineKeyboardButton("10 000", callback_data=f'dice_bet_10000_{selected_number}'), InlineKeyboardButton("25 000", callback_data=f'dice_bet_25000_{selected_number}')],
                [InlineKeyboardButton("Cancel", callback_data='no_deposit')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"You selected number {selected_number}.\n\nNow select your bet amount:",
                reply_markup=reply_markup
            )

        elif query.data.startswith('dice_bet_'):

            parts = query.data.split('_')
            bet_amount = int(parts[2])
            selected_number = int(parts[3])
            credit_balance = await get_credit_balance(user_id)
            credit_balance_int = int(credit_balance)
            if credit_balance_int >= bet_amount:
                await handle_dice(update, context, query, user_id, bet_amount, selected_number)

            else:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
                message = (f"Not enough Credits to cover your bet!\n"
                            f"Please exchnage DeFlip to credits from the deposit menu\n"
                            )
                insufficient_message = await context.bot.send_message(chat_id=user_id, text=message)

                await start(update, context, user_id=user_id)

        elif query.data == 'wallet':
            keyboard = [
                [InlineKeyboardButton("Secret Key", callback_data='secret_key'),InlineKeyboardButton("Import Wallet", callback_data='import_wallet')],
                [InlineKeyboardButton("Cancel", callback_data='cancel_button')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Wallet options:", reply_markup=reply_markup)

        elif query.data == 'referral':
            mylink = await referral(update, context=context)
            ref_earned = await get_user_ref_earned(user_id)
            ref_e_float = float(ref_earned)
            ref_earned_formatted = f"{ref_e_float:.4f}"
            fetch = await get_referral_counts(user_id)
            ref_level_1 = fetch["ref_level_1"]
            ref_level_2 = fetch["ref_level_2"]

            await query.edit_message_text(
                f"Earn 10% of your friends' bets when they join and play! 🎰💸\n\n"
                f"Plus, if they refer others, you’ll receive an additional 5% from their bets too! 🔄💵\n\n"
                f"Total Earnings: {ref_earned_formatted} Credits 💰\n\n"
                f"Level 1 Referrals (Direct): {ref_level_1}\n"
                f"Level 2 Referrals (Their Referrals): {ref_level_2}\n\n"
                f"Copy and share your referral link to start earning: \n`{mylink}`",
                parse_mode='Markdown'
            )

            await start(update, context, user_id=user_id)

        elif query.data == 'cancel_button':
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)

            await start(update, context, user_id=user_id)

        elif query.data == 'no_deposit':
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)

            await start(update, context, user_id=user_id)
            
        elif query.data == 'withdraw':

            keyboard = [
                [InlineKeyboardButton("Yes", callback_data='yes_withdraw')],
                [InlineKeyboardButton("No", callback_data='no_transfer')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            public_key = await get_wallet_address(user_id)
            await query.edit_message_text(f"This function will exchange all your credits back to DeFlip Tokens \n\n"
                                          f"Would you like to proceed?", reply_markup=reply_markup)
            
        elif query.data == 'yes_withdraw':
            
            await query.edit_message_text("Checking... Please wait!")
            withdraw = await initiate_withdraw(update, context,query,user_id)

        elif query.data == 'secret_key':
            private_key = await get_private_key(user_id)
            if private_key:
                message = await query.edit_message_text(
                    f"YOUR PRIVATE KEY: ||{private_key}||\n\n"
                    f"This message will disappear in 15 seconds",
                    parse_mode="MarkdownV2" 
                )
                await asyncio.sleep(15)
                await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
            else:
                await query.edit_message_text("No secret key found.")

            await start(update, context, user_id=user_id)


        elif query.data == 'import_wallet':
            keyboard = [
                [InlineKeyboardButton("Yes", callback_data='yes_wallet')],
                [InlineKeyboardButton("No", callback_data='no_wallet')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                                            "*Are you sure you want to update your wallet?*\n\n"
                                            "Please ensure you have:\n"
                                            "- Backed up your previous wallet.\n"
                                            "- Transferred any SOL and tokens out of your previous wallet.\n\n"
                                            "*Note: We do not store any of your wallets data*",
                                            reply_markup=reply_markup,
                                            parse_mode="Markdown"
                                        )

        elif query.data == 'yes_wallet':
            await query.edit_message_text("Please reply with your private key to import your wallet")
            handler = MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                lambda update, context: import_wallet(update, context, user_id, handler)
            )
            context.application.add_handler(handler)

        elif query.data == 'no_wallet':

            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)

            await start(update, context, user_id=user_id)


    asyncio.create_task(handle_query())

async def high_low_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_data = context.user_data.get('high_low_game', {})
    user_id = update.effective_user.id
    
    if not user_data or user_data.get('game_over', False):
        await query.answer("You don't have a current game active. Please start a new round.")
        return
    
    initial_bet = float(user_data.get('bet', 0)) 
    previous_card = user_data.get('previous_card', None)
    streak = user_data.get('streak', 0)
    rounds = user_data.get('rounds', 0)
    multiplier = user_data.get('multiplier', 1)  
    used_cards = user_data.get('used_cards', set()) 
    
    if not previous_card:
        await query.answer("Game has not started yet.")
        return

    if query.data.startswith("cash_out_"):
        cashout_amount = float(query.data[len("cash_out_"):])

        if cashout_amount == 0:
            await query.message.reply_text("You have no winnings to cash out yet. Please play a round first.")
            await start(update, context, user_id=user_id)
            return
    
        await increment_user_credit_balance(user_id, cashout_amount)
        await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        winnings = int(cashout_amount)
        await query.message.reply_video(
                                            video=open(photo_filename5, 'rb'),  # Ensure the file is opened in binary read mode
                                            caption=f"Congratulations! You cashed out with {winnings}. Your winnings have been added to your balance."
                                        )
        user_details = await context.bot.get_chat_member(chat_id=query.message.chat_id, user_id=user_id)
        user_name = user_details.user.first_name
        message1 = f"Winner! {user_name} just won {winnings} on High Low!\n\nPlay now: [Play now](https://t.me/DeFlip_bot)"
        await bot.send_photo(chat_id=GROUPID, photo=open(photo_filename3, 'rb'), caption=message1, parse_mode="Markdown")

        referrals = await get_user_referrers(user_id) 
        ref1_user_id, ref2_user_id = referrals  
        
        if ref1_user_id:
            ref1_credits = initial_bet * 0.10 
            await increment_user_credit_balance(ref1_user_id, ref1_credits)
            await increment_user_earned_balance(ref1_user_id, ref1_credits) 

        if ref2_user_id:
            ref2_credits = initial_bet * 0.05
            await increment_user_credit_balance(ref2_user_id, ref2_credits)
            await increment_user_earned_balance(ref2_user_id, ref2_credits) 

        context.user_data.pop('high_low_game', None) 
        
        await start(update, context, user_id=user_id)
        return
    

    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
    
    next_card = get_random_card(used_cards)  # Draw a new card
    used_cards.add(next_card)  # Ensure the new card is marked as used

    sticker = CARD_STICKERS[next_card]
    await query.message.reply_sticker(sticker)
    
    if previous_card[0] == next_card[0]:
        await query.message.reply_text(f"Game over! The next card was identical: {next_card[0]} of {next_card[1]}. There was no correct answer this time!")
        amount = initial_bet/2
        increase_burn_volume = await increment_volume_total(amount)
        
        referrals = await get_user_referrers(user_id)
        ref1_user_id, ref2_user_id = referrals  
        
        if ref1_user_id:
            ref1_credits = initial_bet * 0.10 
            await increment_user_credit_balance(ref1_user_id, ref1_credits) 
            await increment_user_earned_balance(ref1_user_id, ref1_credits) 

        if ref2_user_id:
            ref2_credits = initial_bet * 0.05 
            await increment_user_credit_balance(ref2_user_id, ref2_credits) 
            await increment_user_earned_balance(ref2_user_id, ref2_credits) 
        
        context.user_data.pop('high_low_game', None)  
        await start(update, context, user_id=user_id)
        return
    
    previous_card_value = CARD_RANK_VALUES[previous_card[0]] 
    next_card_value = CARD_RANK_VALUES[next_card[0]]
    
    correct_choice = "higher" if next_card_value > previous_card_value else "lower"
    
    is_correct = (query.data == "higher" and next_card_value > previous_card_value) or (query.data == "lower" and next_card_value < previous_card_value)
    
    if is_correct:
        streak += 1
        rounds += 1

        if rounds < 5:
            if rounds == 1:
                winnings = initial_bet * 0.75
            elif rounds == 2:
                winnings = initial_bet * 1
            elif rounds == 3:
                winnings = initial_bet * 1.25
            elif rounds == 4:
                winnings = initial_bet * 1.5
            elif rounds == 5:
                winnings = initial_bet * 2
            
            user_data['previous_win_amount'] = winnings
            cashout_amount = round(winnings, 2)

            additional = 0.25
            try_to_win = initial_bet * (0.75 + additional * rounds)  

            if rounds == 3:
                additional = 1.5
                try_to_win = initial_bet *  additional 

            if rounds == 4:
                additional = 2
                try_to_win = initial_bet * additional

            keyboard = [
                [InlineKeyboardButton(f"Cash Out {cashout_amount}", callback_data=f"cash_out_{cashout_amount}")],
                [InlineKeyboardButton("Higher", callback_data="higher"), InlineKeyboardButton("Lower", callback_data="lower")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                                            f"Congratulations! You won {cashout_amount}.\n"
                                            f"Cash out now or continue to try win {round(try_to_win, 2)}?",
                                            reply_markup=reply_markup
                                        )

        else:

            winnings = initial_bet*2
            await increment_user_credit_balance(user_id, winnings)
            referrals = await get_user_referrers(user_id)
            ref1_user_id, ref2_user_id = referrals 
            if ref1_user_id:
                ref1_credits = initial_bet * 0.10 
                await increment_user_credit_balance(ref1_user_id, ref1_credits)
                await increment_user_earned_balance(ref1_user_id, ref1_credits) 

            if ref2_user_id:
                ref2_credits = initial_bet * 0.05  
                await increment_user_credit_balance(ref2_user_id, ref2_credits) 
                await increment_user_earned_balance(ref2_user_id, ref2_credits) 


            await query.message.reply_video(
                                                    video=open(photo_filename5, 'rb'),  # Ensure the file is opened in binary read mode
                                                    caption=f"Congratulations! You won {winnings}. Your winnings have been added to your balance."
                                                )

        
            user_details = await context.bot.get_chat_member(chat_id=query.message.chat_id, user_id=user_id)
            user_name = user_details.user.first_name
            message1 = f"Winner! {user_name} just won {winnings} on High Low!\n\nPlay now: [Play now](https://t.me/DeFlip_bot)"
            await bot.send_photo(chat_id=GROUPID, photo=open(photo_filename3, 'rb'), caption=message1, parse_mode="Markdown")


            context.user_data.pop('high_low_game', None)
            await start(update, context, user_id=user_id)
            return
    else:
    
        user_guess = "higher" if query.data == "higher" else "lower"
        await query.message.reply_text(
            f"Game over! You guessed {user_guess}. The correct answer was {correct_choice}. The next card was {next_card[0]} of {next_card[1]}.")
        amount = initial_bet/2
        increase_burn_volume = await increment_volume_total(amount)
        await decrement_user_credit_balance(user_id, initial_bet)
        referrals = await get_user_referrers(user_id)  
        ref1_user_id, ref2_user_id = referrals  
        
        if ref1_user_id:
            ref1_credits = initial_bet * 0.10  
            await increment_user_credit_balance(ref1_user_id, ref1_credits) 
            await increment_user_earned_balance(ref1_user_id, ref1_credits) 

        if ref2_user_id:
            ref2_credits = initial_bet * 0.05  
            await increment_user_credit_balance(ref2_user_id, ref2_credits) 
            await increment_user_earned_balance(ref2_user_id, ref2_credits) 
        context.user_data['high_low_game']['game_over'] = True  
        context.user_data.pop('high_low_game', None)  
        await start(update, context, user_id=user_id)
    
    if not user_data.get('game_over', False):
        context.user_data['high_low_game'] = {
            'bet': initial_bet,
            'rounds': rounds,
            'previous_card': next_card,
            'streak': streak,
            'multiplier': multiplier,
            'game_over': False, 
            'used_cards': used_cards 
        }

#CALLBACKS END

def get_random_card(used):
    ranks = ['Ace', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King']
    suits = ['Spades', 'Hearts', 'Clubs', 'Diamonds']
    
    all_cards = [(rank, suit) for rank in ranks for suit in suits]
    available_cards = [card for card in all_cards if card not in used]
    
    if not available_cards:
        # All cards used, reset the deck
        used.clear()
        available_cards = all_cards
    
    selected_card = random.choice(available_cards)
    used.add(selected_card)  # Add the selected card to the used set
    return selected_card

async def high_low_game(update, context, query, user_id, bet_amount_selected):

    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
    
    if 'high_low_game' in context.user_data and not context.user_data['high_low_game'].get('game_over', True):
        
        await query.message.reply_text("You already have an active game. Please finish it first or cash out.")
        return

    bet_amount = bet_amount_selected
    rounds = 0
    used_cards = set()
    previous_card = get_random_card(used_cards)
    used_cards.add(previous_card)  # Add the initial card to the used set

    send_sticker = CARD_STICKERS[previous_card]
    await context.bot.send_sticker(sticker=send_sticker, chat_id=user_id)

    keyboard = [
        [InlineKeyboardButton("Higher", callback_data="higher"), InlineKeyboardButton("Lower", callback_data="lower")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(text=f"Initial card: {previous_card[0]} of {previous_card[1]}. Choose higher or lower.", reply_markup=reply_markup, chat_id=user_id)
    
    context.user_data['high_low_game'] = {
        'bet': bet_amount,
        'rounds': rounds,
        'previous_card': previous_card,
        'streak': 0,
        'game_over': False,  
        'used_cards': used_cards 
    }

async def continue_game(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_data = context.user_data.get('high_low_game', {})
    
    if not user_data or user_data.get('game_over', False):
        await update.message.reply_text("You don't have a current game active. Please start a new round.")
        return
    
    previous_card = user_data.get('previous_card', None)
    rounds = user_data.get('rounds', 0)
    streak = user_data.get('streak', 0)
    initial_bet = float(user_data.get('bet', 0))  
    used_cards = user_data.get('used_cards', set())
    print(rounds)
    print(initial_bet)
    if not previous_card:
        await update.message.reply_text("Game has not started yet.")
        return
    
    sticker = CARD_STICKERS[previous_card]
    additional = 0
    if rounds ==1:
        additional = 0.25
        current_winnings = initial_bet

    if rounds ==2:
        additional = 0.5
        current_winnings = initial_bet*(0.25+1)

    if rounds ==3:
        additional = 1
        current_winnings = initial_bet*(0.5+1)
    if rounds ==4:
        additional = 1.5
        current_winnings = initial_bet*additional
        current_winnings = initial_bet*(1+1)
    
    cashout_amount = current_winnings
    try_to_win = initial_bet * (0.75 + additional)  

    if rounds == 3:
        additional = 2
        try_to_win = initial_bet *  additional 

    if rounds == 4:
        additional = 2.5
        try_to_win = initial_bet * additional  

    keyboard = [
        [InlineKeyboardButton(f"Cash Out {cashout_amount}", callback_data=f"cash_out_{cashout_amount}")],
        [InlineKeyboardButton("Higher", callback_data="higher"), InlineKeyboardButton("Lower", callback_data="lower")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_sticker(sticker)
    await update.message.reply_text(
        f"You're continuing your game! Current winnings: {cashout_amount}\n"
        f"Try to win {round(try_to_win, 2)}. Choose higher or lower to continue.",
        reply_markup=reply_markup
    )

async def handle_deposit(update, context,query,user_id,amount):

    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
    user_wallet = await get_wallet_address_by_user_id(user_id)
    balance = await get_balance(user_wallet)
    spl_balance = await get_solana_token_amount(user_wallet)
    if balance >= 0.01:
        amount_float = float(amount)
        if spl_balance >= amount_float:
            message = (f"Deposit in progress...\n\n"
                    f"Exchanging DeFlip to Credits\n\n"
                    f"Please wait :)"
                    )
            
            ticket_process_message = await context.bot.send_message(chat_id=user_id, text=message)
            selected_deposit_amount = amount        
            table = "table2"
            sk = await get_private_key(user_id)
            wallet = await get_game_wallet(table)
            transfer_spl =  await send_spl(wallet,user_wallet,sk,selected_deposit_amount)
            pk = await get_game_private_key()

            if transfer_spl['success']:

                update_credit_balance = await increment_user_credit_balance(user_id, selected_deposit_amount)
                message = (f"Your transaction is successful!\n\n"
                    f"Loading start menu"
                    )
            
                success_message = await context.bot.send_message(chat_id=user_id, text=message)

        else:
            message = (f"You do not have enough DeFlip Tokens to cover this transaction\n\n"
                        f"Please add sufficient tokens and try again"
                        )
                
            insufficient_message = await context.bot.send_message(chat_id=user_id, text=message)
    else:
        message = (f"You do not have enough Sol in your wallet to cover this transaction\n\n"
                    f"Please ensure you have atleast 0.01 Sol available"
                    )
            
        insufficient_message = await context.bot.send_message(chat_id=user_id, text=message)

    await start(update, context, user_id=user_id)

async def handle_dice(update, context, query, user_id, bet_amount, selected_number):

    bet = bet_amount
    referrals = await get_user_referrers(user_id) 
    ref1_user_id, ref2_user_id = referrals 
    if ref1_user_id:
        ref1_credits = bet * 0.10  
        await increment_user_credit_balance(ref1_user_id, ref1_credits) 
        await increment_user_earned_balance(ref1_user_id, ref1_credits) 

    if ref2_user_id:
        ref2_credits = bet * 0.05  
        await increment_user_credit_balance(ref2_user_id, ref2_credits) 
        await increment_user_earned_balance(ref2_user_id, ref2_credits) 

    number = selected_number
    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)

    message = (f"You bet: {bet}\n"
               f"You chose: {number}\n\n"
               f"Potential winnings 4.5X bet amount"
               )
    
    pregame_message = await context.bot.send_message(chat_id=user_id, text=message)

    flip_result = await dice_roll_game()

    stickers = {
        1: "CAACAgIAAxkBAAEwbudncsqeWf6cZhleZ20kvnDj9GOhrwACixUAAu-iSEvcMCGEtWaZoDYE",
        2: "CAACAgIAAxkBAAEwbulncsq20dGk9aXDtNX222e6Ab3G0AACzxEAAlKRQEtOAAGmnvjK7y82BA",
        3: "CAACAgIAAxkBAAEwbutncsrQUMgYE8GvhUQGHuQavUVaLwACQBEAAiOsQUurmtw9CutR3zYE",
        4: "CAACAgIAAxkBAAEwbu9ncsrnCNz6kiwgjAdVTDrKimYOAANxEQAC7OxBS7UarNb9P6OkNgQ",
        5: "CAACAgIAAxkBAAEwbvNncssNDAXSF5pHKX-fU8AzKxnCngACoQ8AAkG1QUtuwcKEzQGhITYE",
        6: "CAACAgIAAxkBAAEwbvVncssrFGtE6vfplvQaos9-umv8hwAC9g0AAvetSEtWDywqQrcoYzYE"
    }

    if flip_result in stickers:
        sticker_file_unique_id = stickers[flip_result]
        await context.bot.send_sticker(sticker=sticker_file_unique_id, chat_id=user_id)

    await asyncio.sleep(2)
    message = f"Result: {flip_result}!!"
    RESULT_message = await context.bot.send_message(chat_id=user_id, text=message)

    if flip_result == number:
        winnings = int(bet * 4.5)
        await context.bot.send_video(
                                        chat_id=user_id,
                                        video=open(photo_filename5, 'rb'),  # Open the video in binary read mode
                                        caption=f"Congratulations! You won {winnings}. Your winnings have been added to your balance."
                                    )
        user_details = await context.bot.get_chat_member(chat_id=query.message.chat_id, user_id=user_id)
        user_name = user_details.user.first_name
        message1 = f"Winner! {user_name} just won {winnings} on Dice Roll!\n\nPlay now: [Play now](https://t.me/DeFlip_bot)"
        await bot.send_photo(chat_id=GROUPID, photo=open(photo_filename2, 'rb'), caption=message1, parse_mode="Markdown")
        add_winnings = await increment_user_credit_balance(user_id, winnings)

    else:
        message = "You lost, try again!"
        lose_message = await context.bot.send_message(chat_id=user_id, text=message)
        reduce_credits = await decrement_user_credit_balance(user_id, bet)
        amount = bet_amount/2
        increase_burn_volume = await increment_volume_total(amount)

    await start(update, context, user_id=user_id)

async def handle_coinflip(update, context, query, user_id, bet_amount, selected_choice):
    bet = bet_amount
    choice = selected_choice
    referrals = await get_user_referrers(user_id)
    ref1_user_id, ref2_user_id = referrals  
    
    if ref1_user_id:
        ref1_credits = bet * 0.10
        await increment_user_credit_balance(ref1_user_id, ref1_credits) 
        await increment_user_earned_balance(ref1_user_id, ref1_credits) 

    if ref2_user_id:
        ref2_credits = bet * 0.05 
        await increment_user_credit_balance(ref2_user_id, ref2_credits) 
        await increment_user_earned_balance(ref2_user_id, ref2_credits) 

    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)

    message = (f"You bet: {bet}\n"
               f"You chose: {choice}\n"
               f"Potential winnings 1.75X bet amount\n\n"
               f"Good Luck!!")
    pregame_message = await context.bot.send_message(chat_id=user_id, text=message)

    flip_result = await coinflip_game()

    stickers = {
        "heads": "CAACAgQAAxkBAAEwbuFncsk398dH3afX7UBp2pEPXN1VOwAC3xAAAqbxcR7QPHy1bKOARDYE",
        "tails": "CAACAgQAAxkBAAEwbt9ncsksrxjATIWdXHyiy4nnhQqe-AACRggAAqbxcR4DjdH7gZlEwTYE"
    }

    if flip_result in stickers:
        sticker_file_unique_id = stickers[flip_result]
        await context.bot.send_sticker(sticker=sticker_file_unique_id, chat_id=user_id)

    message = f"It's {flip_result}!!"
    RESULT_message = await context.bot.send_message(chat_id=user_id, text=message)

    if flip_result == choice:
        winnings = int(bet * 1.75)

        await context.bot.send_video(
                                        chat_id=user_id,
                                        video=open(photo_filename5, 'rb'),  # Open the video in binary read mode
                                        caption=f"Congratulations! You won {winnings}. Your winnings have been added to your balance."
                                    )
        user_details = await context.bot.get_chat_member(chat_id=query.message.chat_id, user_id=user_id)
        user_name = user_details.user.first_name
        message1 = f"Winner! {user_name} just won {winnings} on Coin Flip!\n\nPlay now: [Play now](https://t.me/DeFlip_bot)"
        await bot.send_photo(chat_id=GROUPID, photo=open(photo_filename1, 'rb'), caption=message1, parse_mode="Markdown")
        add_winnings = await increment_user_credit_balance(user_id, winnings)
    else:
        message = "You lost, try again!"
        lose_message = await context.bot.send_message(chat_id=user_id, text=message)
        reduce_credits = await decrement_user_credit_balance(user_id, bet)
        amount = bet_amount/2
        increase_burn_volume = await increment_volume_total(amount)

    await start(update, context, user_id=user_id)

    

async def handle_burn():
    while True:
        burn_balance = await get_total_volume()
        print('Burn Balance:',burn_balance)
        burn_balance_int = int(burn_balance)
        amount = burn_balance - 10

        if burn_balance_int >= 100000: 
            decrease_total_volume = await decrement_volume_total(amount)
            pk = await get_game_private_key()
            table = "table2"
            from_wallet = await get_game_wallet(table)
            table = "table2"
            to_wallet = await get_burn_wallet(table)
            transfer_to_burn = await send_spl(to_wallet, from_wallet, pk, amount)
            message1 = (
                f"Burn Baby Burn! {amount} DeFlip Tokens have been sent to the allocated burn wallet for destruction!\n\n"
                f"[Allocated Burn Wallet](https://solscan.io/account/2kjSnwhj6aATBJakPNwn4Y7pcZnss6F9TAEyievyHcPx?cluster)"
            )

            await bot.send_photo(
                chat_id=GROUPID,
                photo=open(photo_filename4, 'rb'),
                caption=message1,
                parse_mode="Markdown"
            )
        
        await asyncio.sleep(60)

async def initiate_withdraw(update, context,query,user_id):

    withdraw_amount = await get_credit_balance(user_id)
    withdraw_float = float(withdraw_amount)
    if withdraw_float > 0:
       
        message = (f"Withdrawal in progress...\n\n"
                        f"Exchanging Credits to DeFlip\n\n"
                        f"Please wait :)"
                        )
                
        progress_message = await context.bot.send_message(chat_id=user_id, text=message)        
        table = "table2"
        sk = await get_game_private_key()
        wallet = await get_wallet_address_by_user_id(user_id)
        user_wallet = await get_game_wallet(table)
        transfer_spl =  await send_spl(wallet,user_wallet,sk,withdraw_amount)
        pk = await get_game_private_key()
        if transfer_spl['success']:
            update_credit_balance = await decrement_user_credit_balance(user_id, withdraw_amount)
            message = (f"Your transaction is successful!\n\n"
                        f"Loading start menu"
                        )
                
            success_message = await context.bot.send_message(chat_id=user_id, text=message)

    else:
        message = (f"You do not have enough credits to make a withdrawal"
                    )
            
        insufficient_message = await context.bot.send_message(chat_id=user_id, text=message)

    await start(update, context, user_id=user_id)

async def import_wallet(update: Update, context: Application, user_id: int, handler: MessageHandler) -> None:

    if update.message.chat.type != "private":
        return

    if update.message.from_user.id != user_id:
        return

    private_key_base58 = update.message.text.strip()

    try:

        private_key_bytes = base58.b58decode(private_key_base58)
        private_key_hex = private_key_bytes.hex()
        
    except ValueError:
        raise ValueError("Invalid private key format")
    
    if len(private_key_hex) == 128:
        
        private_key = Keypair.from_base58_string(private_key_base58)
        update_wallet = str(private_key.pubkey())
        await save_wallet_address(user_id, wallet_address=update_wallet, private_key=private_key_base58)
        await update.message.reply_text(f"Your wallet {update_wallet} has been successfully imported!")
    else:
        await update.message.reply_text("Invalid private key format. Please retry.")

    try:
        await context.bot.delete_message(chat_id=update.message.chat.id, message_id=update.message.message_id)
    except Exception as e:
        print(f"Failed to delete message: {e}")

    context.application.remove_handler(handler)

    await start(update, context)

async def referral(update: Update, context: Application) -> str:
    if update.message:
        user_id = update.message.from_user.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
    else:
        raise ValueError("Update object has neither message nor callback_query attribute.")

    referral_link = f"https://t.me/DeFlip_bot?start={user_id}"
    return referral_link

async def wait_for_balance_update(wallet_address, old_balance, user_id, context):
    while True:
        new_balance = await get_balance(wallet_address)
        if new_balance != old_balance:
            break
        await asyncio.sleep(5)

    await context.bot.send_message(chat_id=user_id, text="Balances updated.")

#BOT START

def main():

    print('Starting the Bot')
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", create_start_task))
    application.add_handler(CommandHandler("continue", continue_game))
    application.add_handler(CallbackQueryHandler(high_low_callback, pattern=r'^(higher|lower|cash_out_.*)$'))
    application.add_handler(CallbackQueryHandler(button))
    threading.Thread(target=async_init, daemon=True).start()
    print('Polling')
    application.run_polling()

def async_init():
  
    asyncio.run(setup_database())
    
if __name__ == '__main__':
    main()
