from aiohttp import ClientSession
from typing import Optional, Dict, NamedTuple
from datetime import datetime, timedelta


def get_change_emoji(change: float) -> str:
    """Return appropriate emoji based on price change"""
    if change > 5:
        return "🚀"  # Rocket for significant gain
    elif change > 0:
        return "📈"  # Chart up
    elif change < -5:
        return "📉💨"  # Chart down with wind
    elif change < 0:
        return "📉"  # Chart down
    return "➡️"  # Right arrow for no significant change

class PriceChange(NamedTuple):
    current_price: float
    change_24h: float
    change_7d: float

class CryptoAPI:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.session: Optional[ClientSession] = None
        self.coin_list: Dict[str, str] = {}  # symbol -> id mapping

    async def init_session(self):
        """Initialize session and coin list"""
        if not self.session:
            self.session = ClientSession()
            await self.update_coin_list()

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def update_coin_list(self):
        """Update internal coin list mapping"""
        if not self.session:
            await self.init_session()
        try:
            async with self.session.get(f"{self.base_url}/coins/list") as response:
                if response.status == 200:
                    coins = await response.json()
                    self.coin_list = {coin['symbol'].lower(): coin['id'] for coin in coins}
                else:
                    print(f"Failed to update coin list: {response.status}")
        except Exception as e:
            print(f"Error updating coin list: {str(e)}")
    
    async def get_crypto_price_with_changes(self, crypto: str, fiat: str) -> Optional[PriceChange]:
        """Get crypto price and changes in specified fiat currency"""
        if not self.session:
            await self.init_session()
            
        crypto = crypto.lower()
        fiat = fiat.lower()
        
        if not self.coin_list:
            await self.update_coin_list()
            
        if crypto not in self.coin_list:
            return None
            
        coin_id = self.coin_list[crypto]
        url = f"{self.base_url}/coins/{coin_id}"
        params = {
            'localization': 'false',
            'tickers': 'false',
            'community_data': 'false',
            'developer_data': 'false',
            'sparkline': 'false'
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    market_data = data['market_data']
                    return PriceChange(
                        current_price=market_data['current_price'].get(fiat, 0),
                        change_24h=market_data['price_change_percentage_24h_in_currency'].get(fiat, 0),
                        change_7d=market_data['price_change_percentage_7d_in_currency'].get(fiat, 0)
                    )
                print(f"Failed to get crypto price: {response.status}")
                return None
        except Exception as e:
            print(f"Error getting crypto price: {str(e)}")
            return None
        
class FiatAPI:
    def __init__(self):
        self.base_url = "https://open.er-api.com/v6/latest"
        self.session: Optional[ClientSession] = None
        self.rates: Dict[str, float] = {}
        self.last_update: Optional[datetime] = None
        self.base_currency = "USD"

    async def init_session(self):
        """Initialize session and rates"""
        if not self.session:
            self.session = ClientSession()
            await self.update_rates()

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def update_rates(self):
        """Update exchange rates"""
        if not self.session:
            await self.init_session()
            
        try:
            async with self.session.get(f"{self.base_url}/{self.base_currency}") as response:
                if response.status == 200:
                    data = await response.json()
                    self.rates = data['rates']
                    self.last_update = datetime.now()
                else:
                    print(f"Failed to update rates: {response.status}")
        except Exception as e:
            print(f"Error updating rates: {str(e)}")

    async def get_fiat_rate_with_change(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get current rate and its change from previous day"""
        if not self.session:
            await self.init_session()
            
        # Update rates if older than 1 hour
        if not self.last_update or datetime.now() - self.last_update > timedelta(hours=1):
            await self.update_rates()
            
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        if from_currency not in self.rates or to_currency not in self.rates:
            return None
            
        current_rate = self.rates[to_currency] / self.rates[from_currency]
        
        return current_rate
    
async def init_coins_apis():
    await CryptoAPI().init_session()
    await FiatAPI().init_session()