import os
import asyncio
from dotenv import load_dotenv
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from spl.token.client import Token
from solders.keypair import Keypair
from solana.rpc.types import TxOpts
from solana.transaction import Transaction
from spl.token.constants import TOKEN_PROGRAM_ID
from solana.rpc.commitment import Confirmed, Finalized
from spl.token.instructions import transfer_checked, TransferCheckedParams
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price

load_dotenv('.env')
SECRETKEY= os.getenv('SECRETKEY')
PUBKEY = os.getenv('PUBKEY')
MINTADDRESS = os.getenv('MINT_ADDRESS')
PROGRAMID = os.getenv('PROGRAMID')
RPC_URL =os.getenv('RPC_URL')
mint = Pubkey.from_string(MINTADDRESS)
program_id = Pubkey.from_string(PROGRAMID)
source = Pubkey.from_string(PUBKEY)
solana_client = Client(RPC_URL)


async def send_spl(wallet,user_wallet,sk, amount):

    key_pair = Keypair.from_base58_string(sk)
    dest = Pubkey.from_string(wallet)
    spl_client = Token(
        conn=solana_client, pubkey=mint, program_id=program_id, payer=key_pair
    )
    source = Pubkey.from_string(user_wallet) 
    try:
        source_token_account = (
            spl_client.get_accounts_by_owner(
                owner=source, commitment=None, encoding="base64"
            )
            .value[0]
            .pubkey
        )
    except:
        source_token_account = spl_client.create_associated_token_account(
            owner=source, skip_confirmation=False, recent_blockhash=None
        )
    try:
        dest_token_account = (
            spl_client.get_accounts_by_owner(owner=dest, commitment=None, encoding="base64")
            .value[0]
            .pubkey
        )
        
    except:
        dest_token_account = spl_client.create_associated_token_account(
            owner=dest, skip_confirmation=False, recent_blockhash=None
        )
    compute_unit_price_instr = set_compute_unit_price(100000)
    compute_unit_limit_instr = set_compute_unit_limit(200_000)
    amount =int(float(amount) * 1000000)
    transaction = Transaction()
    transaction.add(compute_unit_price_instr)
    transaction.add(compute_unit_limit_instr)
    transaction.add(
        transfer_checked(
            TransferCheckedParams(
                TOKEN_PROGRAM_ID,
                source_token_account, 
                mint, 
                dest_token_account, 
                source, 
                amount, 
                6,
                signers=[]
            )
        )
    )
    transaction.fee_payer = source
    transaction.sign(key_pair)
    client = Client(endpoint=RPC_URL, commitment=Confirmed)
    owner = key_pair 
    transaction_result = client.send_transaction(
        transaction, owner, opts=None) 
     
    signature = transaction_result.value
    
    if not signature:
        return {"success": False, "error": "No signature received"}
    await asyncio.sleep(5)
    # Confirm transaction
    is_confirmed = await confirm_transaction(signature)
    if is_confirmed:
        return {"success": True, "result": "ok"}
    else:
        return {"success": False, "error": "Transaction not confirmed"}

async def confirm_transaction(signature, retries=4, delay=5):

    for _ in range(retries):

        transaction_info = solana_client.get_transaction(signature)
        if transaction_info and transaction_info.value:  # Transaction found
            return True

        await asyncio.sleep(delay)

    return False

 