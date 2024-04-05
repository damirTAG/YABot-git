import sqlite3
import aiohttp
import asyncio
from bs4 import BeautifulSoup

class Routes:
    def __init__(self) -> None:
        self.conn = sqlite3.connect('database/routes.db')
        self.cursor = self.conn.cursor()

    async def parse(self, route_name):
        print(f"Searching for route: {route_name}")
        self.cursor.execute("SELECT route_link FROM routes WHERE route_name LIKE ?", (f'%{route_name}%',))
        route_link = self.cursor.fetchone()

        if not route_link:
            print('capitalizing due to failed search')
            transformed_route_name = route_name.capitalize()
            transformed_route_name = transformed_route_name[:-1] + transformed_route_name[-1].upper()
            self.cursor.execute("SELECT route_link FROM routes WHERE route_name LIKE ?", (f'%{transformed_route_name}%',))
            route_link = self.cursor.fetchone()

        if not route_link:
            print('searching by id')
            self.cursor.execute("SELECT route_link FROM routes WHERE id = ?", (route_name,))
            
            route_link = self.cursor.fetchone()

        if not route_link:
            print("Route not found.")
            self.conn.close()
            return "Route not found.", []

        route_link = route_link[0]
        #print(route_link)
        async with aiohttp.ClientSession() as session:
            async with session.get(route_link) as response:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                content_div = soup.find('div', {'id': 'content'})
                photo_gallery_div = soup.find('div', {'id': 'photo-gallery'})

                description = ""
                images = []

                    # Handle multiple <p> tags
                p_tags = content_div.find_all('p')
                if p_tags:
                    for p_tag in p_tags:
                        description += p_tag.get_text() + "\n"


                if photo_gallery_div:
                    a_tags = photo_gallery_div.find_all('a', {'rel': 'lightbox[id366]'})
                    for a_tag in a_tags:
                        image_relative_url = a_tag['href']
                        base_url = "https://mountain.kz/"
                        image_href = f"{base_url}{image_relative_url}"
                        images.append(image_href)
                    

                if not images:
                    a_tags = content_div.find_all('a', {'rel': 'lightbox'})
                    for a_tag in a_tags:
                        image_relative_url = a_tag['href']
                        base_url = "https://mountain.kz/"
                        image_href = f"{base_url}{image_relative_url}"
                        images.append(image_href)

                if not description and not images:
                    description = "Description and images not found."

                return description.strip(), images    

    async def get_route_images(self, image_hrefs, route_name):
        image_filenames = []
        
        for image_href in image_hrefs:
            if image_href:
                image_filename = f"{route_name.replace(' ', '_')}_{image_hrefs.index(image_href) + 1}.jpg"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_href) as response:
                        with open(image_filename, 'wb') as f:
                            f.write(await response.read())
                
                image_filenames.append(image_filename)

        return image_filenames


    def get_routes(self):
        self.cursor.execute("SELECT id, route_name FROM routes")
        routes = self.cursor.fetchall()
        
        if not routes:
            return []
        
        route_data = [{"id": route[0], "name": route[1]} for route in routes]
        return route_data

async def main():
    routes = Routes()
    route_name = "абая 1б".capitalize()
    transformed_route_name = route_name.capitalize()
    transformed_route_name = transformed_route_name[:-1] + transformed_route_name[-1].upper()

    result = await routes.parse(transformed_route_name)
    description, image_href = result
    print("Description:", description)
    
    if image_href:
        image_filename = await routes.get_route_image(image_href, route_name)
        print("Image Filename:", image_filename)

# asyncio.run(main())
