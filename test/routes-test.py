# # import requests
# # from bs4 import BeautifulSoup
# # import sqlite3

# import sqlite3

# # Connect to SQLite database
# conn = sqlite3.connect('telegram-bot/yerzhanakh-py/database/routes.db')
# cursor = conn.cursor()

# # Remove tables with IDs from 1 to 23

# cursor.execute("DELETE FROM routes WHERE id = 109")

# conn.commit()
# conn.close()

# print("Tables with IDs removed successfully from routes.db.")

# # # Fetch the webpage content
# # url = 'https://mountain.kz/ru/climbing-routes-maps/?c=mountaineering-routes'
# # response = requests.get(url)
# # soup = BeautifulSoup(response.content, 'html.parser')

# # # Find all <ul> tags
# # ul_tags = soup.find_all('ul')

# # # Extract required information from <ul> tags
# # routes_info = []
# # for ul in ul_tags:
# #     li_tags = ul.find_all('li')
# #     for li in li_tags:
# #         a_tag = li.find('a')
# #         if a_tag:
# #             route_name = a_tag.text.strip()
# #             route_link = a_tag['href']
# #             routes_info.append((route_name, route_link))

# # # Create SQLite database and table
# # conn = sqlite3.connect('routes.db')
# # cursor = conn.cursor()

# # cursor.execute('''CREATE TABLE IF NOT EXISTS routes
# #                   (id INTEGER PRIMARY KEY AUTOINCREMENT,
# #                    route_name TEXT,
# #                    route_link TEXT)''')

# # # Insert data into SQLite database
# # for route in routes_info:
# #     cursor.execute("INSERT INTO routes (route_name, route_link) VALUES (?, ?)", route)

# # conn.commit()
# # conn.close()

# # print("Data inserted successfully into routes.db table.")

