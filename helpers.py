import base64
import requests
import base58
import json
import dotenv
import os
import asyncio
import time
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solders import message
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.signature import Signature

from jupiter_python_sdk.jupiter import Jupiter, Jupiter_DCA

from solana_simplified import Solana_Simplified

dotenv.load_dotenv()

LAMPORTS_PER_SOL = 1_000_000_000
RPC_BASE_URL = "https://solana-mainnet.gateway.tatum.io/"
RPC_API_KEY = os.getenv('TATUM_RPC_API_KEY')
RPC_BASE_URL = "https://solana-mainnet.g.alchemy.com/v2/"
RPC_API_KEY = os.getenv('ALCHEMY_RPC_API_KEY')
RPC_BASE_URL = "http://sample-endpoint-name.network.quiknode.pro/"
RPC_API_KEY = os.getenv('QUICKNODE_RPC_API_KEY')
RPC_BASE_URL = "https://api.mainnet-beta.solana.com"
RPC_API_KEY = ""
RPC_URL = RPC_BASE_URL+RPC_API_KEY

def load_keypair_from_private_key(private_key: str) -> Keypair:
    """Load a Keypair object from a private key in Base64 format."""
    decoded_key = base64.b64decode(private_key)
    return Keypair.from_bytes(decoded_key)

def create_new_wallet():
    """Create a new Solana wallet and return its public address and private key."""
    keypair = Keypair()
    private_key = base64.b64encode(bytes(keypair)).decode("utf-8")  # Get the private key bytes
    public_address = str(keypair.pubkey())  # Get the public key
    return public_address, private_key

def check_balance(public_address: str):
    """Check the SOL balance of a given wallet address."""
    print(f"\nChecking balance for address: {public_address}...")
    
    # Replace `client.get_balance` with a direct RPC call using requests
    alchemy_rpc_url = f"{RPC_BASE_URL}"
    payload = {
        "method": "getBalance",
        "params": [public_address],
        "jsonrpc": "2.0",
        "id": 1
    }
    headers = {"accept": "application/json",
               "content-type": "application/json",
               "x-api-key": RPC_API_KEY}
    response = requests.post(alchemy_rpc_url, json=payload, headers=headers).json()
    print(f"Raw getBalance response: {response}")

    # Parse the balance
    balance = response.get("result", {}).get("value", 0)
    print(f"Balance: {balance} lamports ({balance / 10**9} SOL)")
    return balance / 10**9  # Return the balance in SOL

def get_best_route(jupiter_api_url: str, input_mint: str, output_mint: str, amount: int):
    """Fetch the best route for the swap from Jupiter."""
    try:
        response = requests.get(
            f"{jupiter_api_url}/quote",
            params={
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": amount,
                "slippage": 1,  # Slippage percentage
            },
        )
        response.raise_for_status()
        response_data = response.json()
        
        # Extract route plan from the response
        route_plan = response_data.get("routePlan", [])
        if not route_plan:
            raise ValueError("No routes found. The token might not have sufficient liquidity.")
        
        # Return the first route in the route plan
        return route_plan[0]
    except requests.exceptions.RequestException as e:
        print(f"HTTP Error: {e}")
        raise
    except ValueError as ve:
        print(f"Invalid response: {ve}")
        raise

def send_sol(client, sender_keypair, recipient_address, sol_amount):
    """Send SOL from one wallet to another."""
    print(f"\nSending {sol_amount} SOL to {recipient_address}...")

    solana_transfer_transaction = Solana_Simplified.send_solana(client, sender_keypair.pubkey(), Pubkey.from_string(recipient_address), sender_keypair, sol_amount)
    solana_transaction_signature = Solana_Simplified.set_transaction_signature(solana_transfer_transaction)
    print(f"Transaction Signature: {solana_transaction_signature}")

async def swap_sol_to_spl_token_jupiter(token_address: str, sol_amount: float, slippage: int, max_priority_fee_sol: int = 0.002):
    private_key_base64 = os.getenv("SOL_PRIVATE_KEY")  # e.g., "MDEyMzQ1Njc4OQ=="
    decoded_key = base64.b64decode(private_key_base64)
    private_key = Keypair.from_bytes(decoded_key)
    async_client = AsyncClient(RPC_URL)  # Replace RPC_BASE_URL with your Solana RPC endpoint URL

    try:
        jupiter = Jupiter(
            async_client=async_client,
            keypair=private_key,
            quote_api_url="https://quote-api.jup.ag/v6/quote?",
            swap_api_url="https://quote-api.jup.ag/v6/swap",
            open_order_api_url="https://jup.ag/api/limit/v1/createOrder",
            cancel_orders_api_url="https://jup.ag/api/limit/v1/cancelOrders",
            query_open_orders_api_url="https://jup.ag/api/limit/v1/openOrders?wallet=",
            query_order_history_api_url="https://jup.ag/api/limit/v1/orderHistory",
            query_trade_history_api_url="https://jup.ag/api/limit/v1/tradeHistory",
        )

        # Define dynamic slippage and prioritization fee options
        dynamic_slippage = {
            "maxBps": slippage
        }
        max_priority_fee_lamports = int(max_priority_fee_sol * LAMPORTS_PER_SOL)
        prioritization_fee_lamports = {
            "priorityLevelWithMaxLamports": {
                "maxLamports": max_priority_fee_lamports,
                "global": False,
                "priorityLevel": "veryHigh"
            }
        }

        # Execute the swap
        transaction_data = await jupiter.swap(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint=token_address,
            amount=int(sol_amount * LAMPORTS_PER_SOL),
            dynamic_slippage=dynamic_slippage,
            prioritization_fee_lamports=prioritization_fee_lamports,
        )

        raw_transaction = VersionedTransaction.from_bytes(
            base64.b64decode(transaction_data)
        )
        signature = private_key.sign_message(
            message.to_bytes_versioned(raw_transaction.message)
        )
        signed_txn = VersionedTransaction.populate(
            raw_transaction.message, [signature]
        )
        opts = TxOpts(skip_preflight=False, preflight_commitment="finalized")
        
        result = await async_client.send_raw_transaction(
            txn=bytes(signed_txn), opts=opts
        )
        transaction_id = json.loads(result.to_json())["result"]
        print(f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}")
        return transaction_id
    
    except Exception as e:
        print(f"An error occurred: {e}")
        await async_client.close()
        return None

    finally:
        await async_client.close()  # Ensure the client is properly closed

async def swap_token_to_sol_jupiter(token_address: str, percentage: float, slippage: int, max_priority_fee_sol: int = 0.002):
    private_key_base64 = os.getenv("SOL_PRIVATE_KEY")
    decoded_key = base64.b64decode(private_key_base64)
    private_key = Keypair.from_bytes(decoded_key)
    async_client = AsyncClient(RPC_URL)

    try:
        jupiter = Jupiter(
            async_client=async_client,
            keypair=private_key,
            quote_api_url="https://quote-api.jup.ag/v6/quote?",
            swap_api_url="https://quote-api.jup.ag/v6/swap",
        )

        # Initialize Solana and SPL clients
        solana_client = Solana_Simplified.set_solana_client()
        spl_client = Solana_Simplified.set_spl_client(
            solana_client,
            Pubkey.from_string(token_address),
            Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"),
            private_key,
        )

        # Fetch the associated token account and balance
        token_account_address = Solana_Simplified.get_token_wallet_address_from_main_wallet_address(
            spl_client,
            private_key.pubkey(),
        )
        token_balance = float(Solana_Simplified.get_token_account_balance(spl_client, token_account_address))
        print(f"Token balance: {token_balance}")

        # Calculate amount to swap
        amount_to_swap = int(token_balance * percentage / 100 * (10 ** 6))  # Adjust decimals as needed
        print(f"Amount to swap: {amount_to_swap}")

        # Define dynamic slippage and prioritization fee options
        dynamic_slippage = {
            "maxBps": slippage
        }
        max_priority_fee_lamports = int(max_priority_fee_sol * LAMPORTS_PER_SOL)
        prioritization_fee_lamports = {
            "priorityLevelWithMaxLamports": {
                "maxLamports": max_priority_fee_lamports,
                "global": False,
                "priorityLevel": "veryHigh"
            }
        }

        # Execute the swap
        transaction_data = await jupiter.swap(
            input_mint=token_address,
            output_mint="So11111111111111111111111111111111111111112",  # SOL mint address
            amount=amount_to_swap,
            dynamic_slippage=dynamic_slippage,
            prioritization_fee_lamports=prioritization_fee_lamports,
        )

        raw_transaction = VersionedTransaction.from_bytes(
            base64.b64decode(transaction_data)
        )
        signature = private_key.sign_message(
            message.to_bytes_versioned(raw_transaction.message)
        )
        signed_txn = VersionedTransaction.populate(
            raw_transaction.message, [signature]
        )
        opts = TxOpts(skip_preflight=False, preflight_commitment="finalized")
        result = await async_client.send_raw_transaction(
            txn=bytes(signed_txn), opts=opts
        )
        transaction_id = json.loads(result.to_json())["result"]
        print(f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}")
        return transaction_id
    
    except Exception as e:
        print(f"An error occurred: {e}")
        await async_client.close()
        return None
    
    finally:
        await async_client.close()  # Ensure the client is properly closed

async def check_transaction_status(client: AsyncClient, tx_signature: str):
    try:
        # Convert the transaction signature string to a Signature object
        tx_signature_obj = Signature.from_string(tx_signature)

        # Fetch transaction details with max_supported_transaction_version
        response = await client.get_transaction(
            tx_signature_obj, 
            commitment="confirmed", 
            max_supported_transaction_version=0
        )

        # Access the transaction value
        transaction_result = response.value

        # Check if the transaction result exists
        if transaction_result is None:
            print("Transaction not found or not yet confirmed.")
            return False

        # Access the `meta` field for transaction status
        meta = transaction_result.transaction.meta
        if meta.err is None:
            print("Transaction was successful.")
            return True
        else:
            print(f"Transaction failed with error: {meta.err}")
            return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

    finally:
        await client.close()  # Ensure the client is properly closed
    
async def buy_token(token_address: str, sol_amount: float, max_slippage: int, max_priority_fee_sol: float, max_attempts: int = 5):
    """
    Buy a token using SOL.
    """
    print(f"\nSwapping {sol_amount} SOL for {token_address}...")
    tx_id = None
    attempt = 1
    while attempt <= max_attempts:
        print(f"Attempt {attempt}:")
        tx_id = await swap_sol_to_spl_token_jupiter(token_address, sol_amount, max_slippage, max_priority_fee_sol)
        time.sleep(10)  # Wait for 10 seconds before retrying
        tx_confirmed = await check_transaction_status(AsyncClient(RPC_URL), tx_id)
        if tx_confirmed:
            break
        attempt += 1

    if tx_id is None:
        print(f"Transaction failed after {max_attempts} attempts.")

async def sell_token(token_address: str, percentage: float, max_slippage: int, max_priority_fee_sol: float, max_attempts: int = 5):
    """
    Sell a token for SOL.
    """
    print(f"\nSwapping {token_address} for SOL...")
    tx_id = None
    attempt = 1
    while attempt <= max_attempts:
        print(f"Attempt {attempt}:")
        tx_id = await swap_token_to_sol_jupiter(token_address, percentage, max_slippage, max_priority_fee_sol)
        time.sleep(10)  # Wait for 10 seconds before retrying
        tx_confirmed = await check_transaction_status(AsyncClient(RPC_URL), tx_id)
        if tx_confirmed:
            break
        attempt += 1

    if tx_id is None:
        print(f"Transaction failed after {max_attempts} attempts.")
