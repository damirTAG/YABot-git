import aiohttp
import asyncio

async def download_image(url, filename="image.jpg"):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                with open(filename, "wb") as f:
                    f.write(await response.read())
                print(f"Image saved as {filename}")
            else:
                print(f"Failed to download image: {response.status}")

async def main():
    urls: list = [
        "https://ddinstagram.com/images/DF79UMgt7cU/1",
        "https://ddinstagram.com/images/DF79UMgt7cU/2",
        "https://ddinstagram.com/images/DF79UMgt7cU/3",
        "https://ddinstagram.com/images/DF79UMgt7cU/4",
        "https://ddinstagram.com/images/DF79UMgt7cU/5",
        "https://ddinstagram.com/images/DF79UMgt7cU/6",
        "https://ddinstagram.com/images/DF79UMgt7cU/7",
        "https://ddinstagram.com/images/DF79UMgt7cU/8",
        "https://ddinstagram.com/images/DF79UMgt7cU/9",

        ]  # Original URLs
    for i, url in enumerate(urls):
        await download_image(url, filename=f'ig_Img_{i}.jpg')

asyncio.run(main())
