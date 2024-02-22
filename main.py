import os
import pickle
import re
import logging
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.common.exceptions import UnableToSetCookieException
from selenium.webdriver.common.by import By
from tqdm import tqdm

from utils import (check_key, db_close, db_insert, db_key_exists, db_open,
                   db_remove_duplication)

logging.basicConfig(level=logging.INFO)

driver = webdriver.Chrome()

def login():
    global driver

    cookie_exists = os.path.exists('cookies.pkl')
    driver.get('https://github.com/login' if cookie_exists else 'https://github.com/')

    if not cookie_exists:
        logging.info("🤗 No cookies found, please login to GitHub first")
        input("Press Enter after logged in: ")
        with open("cookies.pkl", "wb") as file:
            pickle.dump(driver.get_cookies(), file)
            logging.info("🍪 Cookies saved")
    else:
        logging.info("🍪 Cookies found, loading cookies")
        with open("cookies.pkl", "rb") as file:
            cookies = pickle.load(file)

        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except UnableToSetCookieException as e:
                logging.debug(f"🟡 Warning, unable to set a cookie {cookie}")

    driver.get('https://github.com/')
    # TODO: check if the user is logged in, if cookies are expired, etc.

def search(url: str):
    con, cur = db_open('github.db')

    driver.get(url)
    pattern = re.compile(r'sk-[a-zA-Z0-9]{48}')

    while True:
        driver.implicitly_wait(5)

        # Expand all the code
        [element.click() for element in driver.find_elements(by=By.XPATH, value="//*[contains(text(), 'more match')]")]


        codes = driver.find_elements(by=By.CLASS_NAME, value='code-list') # find all elements with class name 'f4'
        for element in codes:
            apis = pattern.findall(element.text)
            if len(apis) == 0:
                continue

            apis = list(set(apis))
            apis = [api for api in apis if not db_key_exists(cur, api)]

            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(check_key, apis))
                for idx, result in enumerate(results):
                    db_insert(con, cur, apis[idx], result)

        next_buttons = driver.find_elements(by=By.XPATH, value="//a[@aria-label='Next Page']")
        if len(next_buttons) == 0:
            logging.debug("No more pages")
            break
        next_buttons[0].click()

    db_remove_duplication(con, cur)
    con.commit()
    db_close(con)

def main():
    login()
    keywords = [
        'openai',
        'gpt4',
        'lab',
        'experiment',
        'gpt',
        'chatgpt',
        'gpt-3',
        'llm',
        'agent',
        'rag',
        '实验',
        '测试',
        '语言模型',
    ]

    languages = [
        'Python',
        'C',
        'Java',
        'JavaScript',
        'Go',
        'Shell',
        'Rust',
        'TypeScript',
        'C++',
        'C#',
        'PHP',
        'Ruby',
        'Swift',
        'Kotlin',
        'Objective-C',
        'Dart',
        'Scala',
        'Lua',
        'Perl',
    ]

    candidate = []
    for keyword in keywords:
        for language in languages:
            candidate.append(f'https://github.com/search?q={keyword}+AND+%28%2Fsk-%5Ba-zA-Z0-9%5D%7B48%7D%2F%29+language%3A{language}&type=code&ref=advsearch')

    for url in tqdm(candidate):
        search(url)


if __name__ == '__main__':
    main()



