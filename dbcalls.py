import os
import boto3
import aiomysql
from solders.keypair import Keypair
from dotenv import load_dotenv
from encryption import encrypt_private_key, decrypt_private_key

load_dotenv('.env')

#Add database client and connection details here ommitted for security#

TOKEN = os.getenv('TOKEN')  
DB_NAME = os.getenv('DB_NAME')  
DB_HOST = os.getenv('DB_HOST')  
DB_USER = os.getenv('DB_USER')  
DB_PASSWORD = os.getenv('DB_PASSWORD')
GROUPID = TELEGRAM_GROUP_ID #Replace
END = 0


async def generate_wallets_if_needed(cursor, table_name):

    await cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
    result = await cursor.fetchone()
    
    if result[0] >= 2:
        return  

    wallets = []
    for _ in range(2): 
        private_key = Keypair()
        wallet_address = str(private_key.pubkey())
        encrypted_private_key = encrypt_private_key(str(private_key))
        wallets.append(str(private_key))
        await cursor.execute(f'''
            INSERT INTO {table_name} (wallet_address, #Add encrypted data entry here#, token_balance)
            VALUES (%s, %s, 0)
        ''', (wallet_address, encrypted_private_key))
    
    return wallets

async def save_wallet_address_new(user_id: int, wallet_address: str, token_balance:float, private_key: str, earned:float, referrer_id: int = None):
    encrypted_private_key = encrypt_private_key(private_key)
    second_level_referrer_id = None

    async with aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    ) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if referrer_id:
                    await cursor.execute('SELECT referrer_id FROM table1 WHERE user_id = %s', (referrer_id,))
                    result = await cursor.fetchone()
                    if result:
                        second_level_referrer_id = result[0]

                await cursor.execute('''
                    INSERT INTO table1 (user_id, wallet_address, token_balance, #Add encrypted data entry here#, earned, referrer_id, second_level_referrer_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        wallet_address = VALUES(wallet_address),
                        token_balance = VALUES(token_balance),
                        
                        #Add encrypted data entry here# = VALUES(#Add encrypted data entry here#),
                        
                        earned = VALUES(earned),
                        referrer_id = VALUES(referrer_id),
                        second_level_referrer_id = VALUES(second_level_referrer_id)
                ''', (user_id, wallet_address, token_balance, encrypted_private_key,  earned, referrer_id, second_level_referrer_id))

async def get_credit_balance(user_id: int) -> str:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT token_balance FROM table1 WHERE user_id = %s", (user_id,))
            result = await cursor.fetchone()

    pool.close()
    await pool.wait_closed()

    if result and result[0] is not None:
        return str(result[0])
    else:
        return "0"
    
async def save_wallet_address(user_id: int, wallet_address: str = None, token_balance: float = None, 
                              private_key: str = None, earned: float = None, referrer_id: int = None):
    encrypted_private_key = encrypt_private_key(private_key) if private_key else None
    second_level_referrer_id = None

    async with aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    ) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if referrer_id:
                    await cursor.execute('SELECT referrer_id FROM table1 WHERE user_id = %s', (referrer_id,))
                    result = await cursor.fetchone()
                    if result:
                        second_level_referrer_id = result[0]

                updates = []
                params = []

                if wallet_address:
                    updates.append("wallet_address = %s")
                    params.append(wallet_address)
                if encrypted_private_key:
                    updates.append("#Add encrypted data entry here# = %s")
                    params.append(encrypted_private_key)
                if token_balance is not None:
                    updates.append("token_balance = %s")
                    params.append(token_balance)
                if earned is not None:
                    updates.append("earned = %s")
                    params.append(earned)
                if referrer_id is not None:
                    updates.append("referrer_id = %s")
                    params.append(referrer_id)
                if second_level_referrer_id is not None:
                    updates.append("second_level_referrer_id = %s")
                    params.append(second_level_referrer_id)

                params.append(user_id)

                if updates:
                    update_query = f'''
                        UPDATE table1
                        SET {', '.join(updates)}
                        WHERE user_id = %s
                    '''
                    await cursor.execute(update_query, params)

async def get_wallet_address(user_id: int) -> str:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('SELECT wallet_address FROM table1 WHERE user_id = %s', (user_id,))
            result = await cursor.fetchone()
            return result[0] if result else None

    pool.close()
    await pool.wait_closed()

async def get_user_id(wallet_address: str) -> str:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('SELECT user_id FROM table1 WHERE wallet_address = %s', (wallet_address,))
            result = await cursor.fetchone()
            return result[0] if result else None

    pool.close()
    await pool.wait_closed()

async def get_private_key(user_id: int) -> str:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('SELECT #Add encrypted entry here# FROM table1 WHERE user_id = %s', (user_id,))
            result = await cursor.fetchone()
            if result:
                return decrypt_private_key(result[0])
            else:
                return None

    pool.close()
    await pool.wait_closed()

async def get_game_private_key():
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('SELECT #Add encrypted data entry here# FROM gamedata LIMIT 1')
            result = await cursor.fetchone()
            if result:
                return decrypt_private_key(result[0])
            else:
                return None

    await pool.wait_closed() 

async def get_game_wallet(tablename: str) -> str:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(f"SELECT wallet_address FROM {tablename} WHERE id = 1")
            result = await cursor.fetchone()  
            
            if result:
                return result[0]  
            else:
                return None  

    pool.close()
    await pool.wait_closed()

async def get_burn_wallet(tablename: str) -> str:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
           
            await cursor.execute(f"SELECT wallet_address FROM {tablename} WHERE id = 2")
            result = await cursor.fetchone()  
            
            if result:
                return result[0]  
            else:
                return None  

    pool.close()
    await pool.wait_closed()

async def get_wallet_address_by_user_id(user_id: int) -> str:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT wallet_address FROM table1 WHERE user_id = %s", (user_id,))
            result = await cursor.fetchone()
            if result:
                return result[0]
            return None

    pool.close()
    await pool.wait_closed()

async def get_user_referrers(user_id: int) -> (str, str):
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT referrer_id, second_level_referrer_id FROM table1 WHERE user_id = %s", (user_id,))
            result = await cursor.fetchone()
            if result:
                
                ref1_user_id = result[0] if result[0] else None
                ref2_user_id = result[1] if result[1] else None
                return ref1_user_id, ref2_user_id
            return None, None

    pool.close()
    await pool.wait_closed()

async def get_user_ref_earned(user_id: int) -> str:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT earned FROM table1 WHERE user_id = %s", (user_id,))
            result = await cursor.fetchone()

    pool.close()
    await pool.wait_closed()

    if result and result[0] is not None:
        return str(result[0])
    else:
        return "0"

async def increment_user_earned_balance(user_id: int, earned: float) -> None:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:

            await cursor.execute("""
                UPDATE table1
                SET earned = COALESCE(earned, 0) + %s
                WHERE user_id = %s
            """, (earned, user_id))

    pool.close()
    await pool.wait_closed()

async def increment_user_credit_balance(user_id: int, token_balance: float) -> None:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:

            await cursor.execute("""
                UPDATE table1
                SET token_balance = COALESCE(token_balance, 0) + %s
                WHERE user_id = %s
            """, (token_balance, user_id))

    pool.close()
    await pool.wait_closed()

async def decrement_user_credit_balance(user_id: int, token_balance: float) -> None:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:

            await cursor.execute("""
                UPDATE table1
                SET token_balance = COALESCE(token_balance, 0) - %s
                WHERE user_id = %s
            """, (token_balance, user_id))

    pool.close()
    await pool.wait_closed()


async def increment_volume_total(total_volume_added: float) -> None:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            
            await cursor.execute("""
                UPDATE table2
                SET total_volume = total_volume + %s
            """, (total_volume_added,))


    pool.close()
    await pool.wait_closed()

async def decrement_volume_total(total_volume_added: float) -> None:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                UPDATE table2
                SET total_volume = total_volume - %s
            """, (total_volume_added,))

    pool.close()
    await pool.wait_closed()

async def get_referral_counts(user_id: int) -> dict:
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:

            await cursor.execute('''
                SELECT COUNT(*) 
                FROM table1 
                WHERE referrer_id = %s
            ''', (user_id,))
            ref_level_1_count = (await cursor.fetchone())[0]

            await cursor.execute('''
                SELECT COUNT(*) 
                FROM table1 
                WHERE second_level_referrer_id = %s
            ''', (user_id,))
            ref_level_2_count = (await cursor.fetchone())[0]

    pool.close()
    await pool.wait_closed()

    return {
        "ref_level_1": ref_level_1_count,
        "ref_level_2": ref_level_2_count
    }

async def get_total_volume():
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('SELECT total_volume FROM table2 LIMIT 1')
            result = await cursor.fetchone()
            if result:
                return result[0]
            else:
                return None

    await pool.wait_closed() 

async def add_new_wallets(table_name):
    private_keys = []
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            for _ in range(2):
                private_key = Keypair()
                wallet_address = str(private_key.pubkey())
                encrypted_private_key = encrypt_private_key(str(private_key))
                await cursor.execute(f'''
                    INSERT INTO {table_name} (wallet_address, #Add encrypted data entry here#, balance)
                    VALUES (%s, %s, 0)
                ''', (wallet_address, encrypted_private_key))

                private_keys.append(str(private_key))

    pool.close()
    await pool.wait_closed()

    return private_keys