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


class APIKeyLeakageScanner:
    def __init__(self, db_file: str, keywords: list, languages: list):
        self.db_file = db_file
        log.info(f"📂 Opening database file {self.db_file}")
        self.con, self.cur = db_open(self.db_file)

        self.keywords = keywords
        self.languages = languages
        self.candidate_urls = [
            f"https://github.com/search?q={keyword}+AND+%28%2Fsk-%5Ba-zA-Z0-9%5D%7B48%7D%2F%29+language%3A{language}&type=code&ref=advsearch"
            for language in self.languages
            for keyword in self.keywords
        ]

    def _save_cookies(self):
        cookies = self.driver.get_cookies()
        with open("cookies.pkl", "wb") as file:
            pickle.dump(cookies, file)
            log.info("🍪 Cookies saved")

    def _load_cookies(self):
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

    def _test_cookies(self):
        """
        Test if the user is really logged in
        """
        log.info("🤗 Redirecting ...")
        self.driver.get("https://github.com/")

        if self.driver.find_elements(
            by=By.XPATH, value="//*[contains(text(), 'Sign in')]"
        ):
            return False
        return True

    def _hit_rate_limit(self):
        return self.driver.find_elements(
            by=By.XPATH,
            value="//*[contains(text(), 'You have exceeded a secondary rate limit')]",
        )

    def login_to_github(self):
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
            self._save_cookies()
        else:
            log.info("🍪 Cookies found, loading cookies")
            self._load_cookies()

        if not self._test_cookies():
            if os.path.exists("cookies.pkl"):
                os.remove("cookies.pkl")
            log.error("🔴 Error, you are not logged in, please restart and try again.")
            exit(1)

        # TODO: check if the user is logged in, if cookies are expired, etc.

    def _process_url(self, url: str):
        self.driver.get(url)
        pattern = re.compile(r"sk-[a-zA-Z0-9]{48}")

        while True:
            # If current webpage is reached the rate limit, then wait for 30 seconds
            if self._hit_rate_limit():
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
            except Exception as _:
                # log.info("    ⚪️ No more pages")
                break

    def _save_progress(self, from_iter: int):
        with open(".progress.txt", "w") as file:
            # Save the progress and timestamp
            file.write(f"{from_iter}/{len(self.candidate_urls)}/{time.time()}")

    def _load_progress(self):
        if not os.path.exists(".progress.txt"):
            return 0
        with open(".progress.txt", "r") as file:
            progress = file.read().strip().split("/")
            last = int(progress[0])
            totl = int(progress[1])
            tmst = float(progress[2])
            # if the time is less than 1 hour, then continue from the last progress
            if time.time() - tmst < 3600 and totl == len(self.candidate_urls):
                # ask the user if they want to continue from the last progress
                action = input(f"🔍 Progress found, do you want to continue from the last progress ({last}/{totl})? [yes] | no: ")
                if action.lower() == "yes" or action.lower() == "y" or action == "":
                    return int(progress[0])
                else:
                    return 0
            return 0

    def search(self, from_iter: int = None):
        pbar = tqdm(
            enumerate(self.candidate_urls),
            total=len(self.candidate_urls),
            desc="🔍 Searching ...",
        )

        if from_iter is None:
            from_iter = self._load_progress()

        for idx, url in enumerate(self.candidate_urls):
            if idx < from_iter:
                pbar.update()
                time.sleep(0.05)  # let tqdm print the bar
                log.debug(f"⚪️ Skip {url}")
                continue
            self._process_url(url)
            self._save_progress(idx)
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

    def all_available_keys(self) -> list:
        return db_get_all_keys(self.cur)

    def __del__(self):
        if hasattr(self, "driver"):
            self.driver.quit()
        self.con.commit()
        db_close(self.con)


def main(from_iter: int = None, check_existed_keys_only: bool = False):
    keywords = [
        "openai",
        "lab",
        "gpt4",
        "chatgpt",
        "apikey",
        "gpt-3",
        "gpt",
        "gpt-4",
        "llm",
        "conversational AI",
        "api key",
        "chatbot",
        "bot",
        "实验",
        "密钥",
        "AI ethics",
        "AI in customer service",
        "AI in education",
        "AI in finance",
        "AI in healthcare",
        "AI in marketing",
        "AI-driven automation",
        "AI-powered content creation",
        "CoT",
        "DPO",
        "RLHF",
        "agent",
        "ai model",
        "aios",
        "artificial intelligence",
        "chain of thought",
        "competitor analysis",
        "content strategy",
        "data analysis",
        "deep learning",
        "direct preference optimization",
        "experiment",
        "key",
        "keyword clustering",
        "keyword research",
        "language model experimentation",
        "large language model",
        "llama.cpp",
        "long-tail keywords",
        "machine learning",
        "multi-agent",
        "multi-agent systems",
        "natural language processing",
        "personalized AI",
        "project",
        "rag",
        "reinforcement learning from human feedback",
        "retrieval-augmented generation",
        "search intent",
        "semantic search",
        "thoughts",
        "virtual assistant",
        "测试",
        "语言模型",
    ]

    languages = [
        "Shell",
        "YAML",
        "JSON",
        "JavaScript",
        "Python",
        "Java",
        "Go",
        "PHP",
        "TypeScript",
        '"Jupyter Notebook"',
        "C%2B%2B",
    ]

    leakage = APIKeyLeakageScanner("github.db", keywords, languages)
    if not check_existed_keys_only:
        leakage.login_to_github()
        leakage.search(from_iter=from_iter)
    leakage.update_existed_keys()
    leakage.deduplication()
    keys = leakage.all_available_keys()

    log.info(f"🔑 Available keys ({len(keys)}):")
    for key in keys:
        log.info(key)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-iter", type=int, default=None, help="Start from the specific iteration")
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
