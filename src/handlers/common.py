import logging

from aiogram            import Router, types

from utils              import RegexFilter, Tools
from utils.decorators   import log
from services.coins     import FiatAPI, CryptoAPI, get_change_emoji

router      = Router()
tools       = Tools()
logger      = logging.getLogger()
crypto_api  = CryptoAPI()
fiat_api    = FiatAPI()

@router.message(RegexFilter(r"^(\d+(?:\.\d+)?\s+)?[a-zA-Z]+(\s+[a-zA-Z]+)?$"))
@log('COINS_CONVERTER')
async def convert_currency(message: types.Message):
    """Currency conversion handler"""
    try:
        # Parse the message
        parsed = tools.parse_currency_query(message.text)
        if not parsed:
            return
        
        amount, from_currency, to_currency = parsed
        
        # Try crypto conversion first
        crypto_price = await crypto_api.get_crypto_price_with_changes(from_currency, to_currency)
        if crypto_price:
            total = amount * crypto_price.current_price
            response = [
                f"<code>{amount} {from_currency.upper()} = {total:.2f} {to_currency.upper()}</code>",
                f"\n<b> - 24h Change:</b> {get_change_emoji(crypto_price.change_24h)} <code>{crypto_price.change_24h:.2f}%</code>",
                f"\n<b> - 7d Change:</b> {get_change_emoji(crypto_price.change_7d)} <code>{crypto_price.change_7d:.2f}%</code>"
            ]
            await message.reply("".join(response))
            return

        current_rate = await fiat_api.get_fiat_rate_with_change(from_currency, to_currency)
        if current_rate:
            total = amount * current_rate
            response = [
                f"<code>{amount:g} {from_currency.upper()} = {total:.2f} {to_currency.upper()}</code>",
            ]
            await message.reply("".join(response))
            return
        
    except Exception as e:
        print(f"Error in conversion handler: {str(e)}")