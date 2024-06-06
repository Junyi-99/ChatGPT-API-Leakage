import argparse
import logging
import os
import pickle
import re
import time
from concurrent.futures import ThreadPoolExecutor
from sqlite3 import Connection, Cursor

from selenium import webdriver
from selenium.common.exceptions import UnableToSetCookieException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm

from utils import (
    check_key,
    db_close,
    db_delete,
    db_get_all_keys,
    db_insert,
    db_key_exists,
    db_open,
    db_remove_duplication,
)

FORMAT = "%(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt="[%X]")
log = logging.getLogger("ChatGPT-API-Leakage")

class Leakage:
    def __init__(self, db_file: str, keywords: list, languages: list):
        self.db_file = db_file
        log.info(f"📂 Opening database file {self.db_file}")
        self.con, self.cur = db_open(self.db_file)
        self.keywords = keywords
        self.languages = languages
        self.candidate = []
        for language in self.languages:
            for keyword in self.keywords:
                self.candidate.append(
                    f"https://github.com/search?q={keyword}+AND+%28%2Fsk-%5Ba-zA-Z0-9%5D%7B48%7D%2F%29+language%3A{language}&type=code&ref=advsearch"
                )

    def login(self):
        log.info("🌍 Opening Chrome ...")
        self.options = webdriver.ChromeOptions()
        self.options.add_argument("--ignore-certificate-errors")
        self.options.add_argument("--ignore-ssl-errors")
        self.driver = webdriver.Chrome(options=self.options)
        self.driver.implicitly_wait(3)

        cookie_exists = os.path.exists("cookies.pkl")
        self.driver.get("https://github.com/login")

        if not cookie_exists:
            log.info("🤗 No cookies found, please login to GitHub first")
            input("Press Enter after you logged in: ")
            with open("cookies.pkl", "wb") as file:
                pickle.dump(self.driver.get_cookies(), file)
                log.info("🍪 Cookies saved")
        else:
            log.info("🍪 Cookies found, loading cookies")
            try:
                with open("cookies.pkl", "rb") as file:
                    cookies = pickle.load(file)

                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except UnableToSetCookieException as e:
                        log.debug(f"🟡 Warning, unable to set a cookie {cookie}")
            except EOFError as e:
                if os.path.exists("cookies.pkl"):
                    os.remove("cookies.pkl")
                log.error(
                    "🔴 Error, unable to load cookies, invalid cookies has been removed, please restart."
                )
            except pickle.UnpicklingError as e:
                if os.path.exists("cookies.pkl"):
                    os.remove("cookies.pkl")
                log.error(
                    "🔴 Error, load cookies failed, invalid cookies has been removed, please restart."
                )

        log.info("🤗 Redirecting ...")
        self.driver.get("https://github.com/")

        if self.driver.find_elements(
            by=By.XPATH, value="//*[contains(text(), 'Sign in')]"
        ):
            if os.path.exists("cookies.pkl"):
                os.remove("cookies.pkl")
            log.error(
                "🔴 Error, you are not logged in, please restart and try again."
            )
            exit(1)

        # TODO: check if the user is logged in, if cookies are expired, etc.

    def __search(self, url: str):
        self.driver.get(url)
        pattern = re.compile(r"sk-[a-zA-Z0-9]{48}")

        while True:

            # If current webpage is reached the rate limit, then wait for 30 seconds
            if self.driver.find_elements(
                by=By.XPATH,
                value="//*[contains(text(), 'You have exceeded a secondary rate limit')]",
            ):
                for _ in tqdm(range(30), desc="⏳ Rate limit reached, waiting ..."):
                    time.sleep(1)
                self.driver.refresh()
                continue

            # Expand all the code
            [
                element.click()
                for element in self.driver.find_elements(
                    by=By.XPATH, value="//*[contains(text(), 'more match')]"
                )
            ]

            codes = self.driver.find_elements(
                by=By.CLASS_NAME, value="code-list"
            )  # find all elements with class name 'f4'
            for element in codes:
                apis = pattern.findall(element.text)
                if len(apis) == 0:
                    continue

                apis = list(set(apis))
                apis = [api for api in apis if not db_key_exists(self.cur, api)]

                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(check_key, apis))
                    for idx, result in enumerate(results):
                        db_insert(self.con, self.cur, apis[idx], result)

            next_buttons = self.driver.find_elements(
                by=By.XPATH, value="//a[@aria-label='Next Page']"
            )

            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//a[@aria-label='Next Page']")
                    )
                )

                next_buttons = self.driver.find_elements(
                    by=By.XPATH, value="//a[@aria-label='Next Page']"
                )
                next_buttons[0].click()
            except Exception as e:
                log.info("    ⚪️ No more pages")
                break

    def search(self, from_iter: int = 0):
        pbar = tqdm(
            enumerate(self.candidate),
            total=len(self.candidate),
            desc="🔍 Searching ...",
        )
        for idx, url in enumerate(self.candidate):
            if idx < from_iter:
                pbar.update()
                time.sleep(0.05)  # let tqdm print the bar
                log.debug(f"⚪️ Skip {url}")
                continue
            self.__search(url)
            log.debug(f"\n🔍 Finished {url}")
            pbar.update()
        pbar.close()

    def deduplication(self):
        db_remove_duplication(self.con, self.cur)

    def update_existed_keys(self):
        log.info("🔄 Updating existed keys")
        keys = db_get_all_keys(self.cur)
        for key in tqdm(keys, desc="🔄 Updating existed keys ..."):
            result = check_key(key[0])
            db_delete(self.con, self.cur, key[0])
            db_insert(self.con, self.cur, key[0], result)

    def __del__(self):
        if hasattr(self, "driver"):
            self.driver.quit()
        self.con.commit()
        db_close(self.con)


def main(from_iter: int = 0, check_existed_keys_only: bool = False):
    keywords = [
        "chatgpt",
        "project",
        "llama.cpp",
        "aios",
        "multi-agent",
        "thoughts",
        "RLHF",
        "DPO",
        "CoT",
        "rag",
        "lab",
        "agent",
        "chatbot",
        "llm",
        "openai",
        "gpt4",
        "experiment",
        "gpt",
        "key",
        "apikey",
        "chatgpt",
        "gpt-3",
        "llm",
        "实验",
        "测试",
        "语言模型",
        "密钥",
    ]

    languages = [
        '"Jupyter Notebook"',
        "Python",
        "Shell",
        "JavaScript",
        "TypeScript",
        "Java",
        "Go",
        "C%2B%2B",
        "PHP",
    ]

    leakage = Leakage("github.db", keywords, languages)
    if not check_existed_keys_only:
        leakage.login()
        leakage.search(from_iter=from_iter)
    leakage.update_existed_keys()
    leakage.deduplication()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-iter", type=int, default=0)
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug mode, otherwise INFO mode. Default is False (INFO mode)",
    )
    parser.add_argument(
        "-ceko",
        "--check-existed-keys-only",
        action="store_true",
        default=False,
        help="Only check existed keys",
    )
    args = parser.parse_args()

    if args.debug:
        log.getLogger().setLevel(log.DEBUG)

    main(from_iter=args.from_iter, check_existed_keys_only=args.check_existed_keys_only)
