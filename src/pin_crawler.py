# Not working need fix
# Github: https://github.com/damirTAG/YABot-git
# Author: https://t.me/damirTAG  

"""
Not working need fix!
Not working need fix!
Not working need fix!
"""
import json
import random
import aiohttp
import asyncio
import os
from typing import Optional

class PinterestScraper:
    def __init__(self, query: Optional[str] = None) -> None:
        self.name = 'pinterest'
        self.query = query if query is not None else 'gorpcore'
        self.number_of_images = 200
        self.cookie = 'csrftoken=97b01583d6330b33b7e72656a4d5ed1c; _pinterest_sess=TWc9PSZSNnhlV2xkTWpGTFltVVEvQkRBbmxDWlRPcEx6MEhSdGRYR3g0ZmJaWUk5WVVXakQwS29Ia0F1RGZiYlpSdXByTy9mckF5dDRzTG9sU2FYV3ZlbXZNUFpDOFpqYVB1c1FYV2oxWk15MEQyTT0meU1oTWZRSGR5Q1Z6Zjd5bXc0a0gvejFPR1R3PQ==; _auth=0; _routing_id="b5a67db2-93e5-4513-ab31-05ca021c6667"; sessionFunnelEventLogged=1'
        self.x_crsftoken = '97b01583d6330b33b7e72656a4d5ed1c'
        self.start_url = f'https://ru.pinterest.com/resource/BaseSearchResource/get/?source_url=%2Fsearch%2Fpins%2F%3Fq%3D{self.query}%26rs%3Dtyped%26term_meta%5B%5D%3D{self.query}%257Ctyped&data=%7B%22options%22%3A%7B%22article%22%3A%22%22%2C%22appliedProductFilters%22%3A%22---%22%2C%22query%22%3A%22{self.query}%22%2C%22scope%22%3A%22pins%22%2C%22auto_correction_disabled%22%3A%22%22%2C%22top_pin_id%22%3A%22%22%2C%22filters%22%3A%22%22%7D%2C%22context%22%3A%7B%7D%7D&_=1660591241435'
        self.collectionItems = []

    async def fetch(self, session, url, payload=None):
        async with session.post(url, headers=self.get_headers(), data=payload) as response:
            print(f"Content-Type: {response.content_type}")
            if response.content_type == 'application/json' or response.content_type == 'application/octet-stream':
                try:
                    return await response.json()
                except json.JSONDecodeError:
                    return await response.text()
            else:
                return await response.text()

    async def download_image(self, session, image_url):
        async with session.get(image_url) as response:
            if response.status == 200:
                filename = os.path.basename(image_url)
                with open(filename, 'wb') as f:
                    f.write(await response.read())
                return filename
            else:
                return None

    def get_headers(self):
        return {
            'cookie': self.cookie,
            'x-csrftoken': self.x_crsftoken,
            'Content-Type': 'application/json'
        }

    async def parse(self):
        async with aiohttp.ClientSession() as session:
            response = await self.fetch(session, self.start_url)
            
            if isinstance(response, dict) and 'resource_response' in response:
                p = json.loads(json.dumps(response))
                results = p['resource_response']['data']['results']
                self.next_bookmark = p['resource']['options']['bookmarks']['bookmarks']

                for result in results:
                    if 'images' in result:
                        self.collectionItems.append({
                            "title": result['title'],
                            "image": result['images']['orig'],
                            "pinner": result['pinner'],
                            "board": result['board']
                        })

                while len(self.collectionItems) < self.number_of_images:
                    url = "https://ru.pinterest.com/resource/BaseSearchResource/get/"
                    payload = {
                        "source_url": f"/search/pins/?q={self.query}&rs=typed&term_meta[]={self.query}%7Ctyped",
                        "data": {
                            "options": {
                                "bookmarks": {
                                    "bookmarks": self.next_bookmark
                                },
                                "query": self.query,
                                "scope": "pins"
                            },
                            "context": {}
                        }
                    }

                    response = await self.fetch(session, url, json.dumps(payload))

                    if isinstance(response, dict) and 'resource_response' in response:
                        moreResults = json.loads(response.text)['resource_response']['data']['results']

                        for result in moreResults:
                            if 'images' in result:
                                self.collectionItems.append({
                                    "title": result['title'],
                                    "image": result['images']['orig'],
                                    "pinner": result['pinner'],
                                    "board": result['board']
                                })

                        self.next_bookmark = json.loads(response.text)['resource']['options']['bookmarks']['bookmarks']

                # Choose a random pin URL
                random_pin = random.choice(self.collectionItems)

                # Download the random image
                filename = await self.download_image(session, random_pin['image']['url'])
                return filename
            else:
                print(f"Error fetching data: {response}")

    def get_payload(self):
        return json.dumps({
            "source_url": '/search/pins/?q=' + self.query + '&rs=typed&term_meta[]=' + self.query + '%7Ctyped',
            "data": {
                "options": {
                    "article": "",
                    "appliedProductFilters": "---",
                    "query": self.query,
                    "scope": "pins",
                    "auto_correction_disabled": "",
                    "top_pin_id": "",
                    "filters": ""
                },
                "context": {}
            }
        })

if __name__ == "__main__":
    scraper = PinterestScraper()
    asyncio.run(scraper.parse())