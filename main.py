"""
Jupiter SDK
https://github.com/0xTaoDev/jupiter-python-sdk

Simplified Solana usage repo:
https://github.com/SeveighTech-Management/solana-py-implementation/tree/main
"""
from helpers import *

if __name__ == "__main__":
    """
    # create a new wallet
    public_address, private_key = create_new_wallet()
    print(f"Public address: {public_address}")
    print(f"Private key: {private_key}") """

    # sending SOL
    #send_sol(Solana_Simplified.set_solana_client(), load_keypair_from_private_key(os.getenv("SOL_PRIVATE_KEY")), "HHSiRFRJpyxrjVN3jpqLrczh4kfHVGWC87CDSpHwHiir", 0.0005)

    # buying and selling token
    #asyncio.run(buy_token(token_address="", sol_amount=0.0005, max_slippage=200, max_priority_fee_sol=0.004, max_attempts=5))
    #asyncio.run(sell_token(token_address="", percentage=100, max_slippage=200, max_priority_fee_sol=0.004, max_attempts=5))