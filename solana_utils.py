import os 
import requests
from dotenv import load_dotenv
from solana.rpc.api import Client
from solathon import Client
load_dotenv('.env')

MINTADDRESS = os.getenv('MINT_ADDRESS')
RPC_URL =os.getenv('RPC_URL')
solana_client = Client(RPC_URL)

async def get_solana_token_amount(wallet_address):
    token_mint = MINTADDRESS
    url = RPC_URL
    headers = {"accept": "application/json", "content-type": "application/json"}
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet_address,
            {"mint": token_mint},
            {"encoding": "jsonParsed"},
        ],
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response_json = response.json()
        if response.status_code != 200:
            raise ValueError(f"API returned non-200 status: {response.status_code}")
        if "result" in response_json and "value" in response_json["result"] and response_json["result"]["value"]:
            token_amount = response_json["result"]["value"][0]["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"]
            return token_amount
        else:
            return 0.0  

    except Exception as e:
        print(f"Error in get_solana_token_amount: {e}")
        return 0.0  
