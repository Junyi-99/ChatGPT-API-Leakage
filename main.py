import argparse
import logging
import os
import pickle
import re
import time
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm

from configs import keywords, languages, REGEX_LIST
from utils import (check_key, db_close, db_delete, db_get_all_keys, db_insert,
                   db_key_exists, db_open, db_remove_duplication)

from manager import CookieManager, ProgressManager

FORMAT = "%(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt="[%X]")
log = logging.getLogger("ChatGPT-API-Leakage")
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)


class APIKeyLeakageScanner:
    def __init__(self, db_file: str, keywords: list, languages: list):
        self.db_file = db_file
        self.progress = ProgressManager()

        log.info(f"📂 Opening database file {self.db_file}")
        self.con, self.cur = db_open(self.db_file)

        self.keywords = keywords
        self.languages = languages
        self.candidate_urls = [
            f"https://github.com/search?q={keyword}+AND+(/{regex.pattern}/)+language:{language}&type=code&ref=advsearch"
            for regex in REGEX_LIST[2:] # Skip the first two regex
            for language in self.languages
            for keyword in self.keywords
        ]
        self.candidate_urls.insert(0, f"https://github.com/search?q=(/{REGEX_LIST[0].pattern}/)&type=code&ref=advsearch")
        self.candidate_urls.insert(0, f"https://github.com/search?q=(/{REGEX_LIST[1].pattern}/)&type=code&ref=advsearch")

    def login_to_github(self):
        log.info("🌍 Opening Chrome ...")

        options = webdriver.ChromeOptions()
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")

        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(3)

        self.cookies = CookieManager(self.driver)

        cookie_exists = os.path.exists("cookies.pkl")
        self.driver.get("https://github.com/login")

        if not cookie_exists:
            log.info("🤗 No cookies found, please login to GitHub first")
            input("Press Enter after you logged in: ")
            self.cookies.save()
        else:
            log.info("🍪 Cookies found, loading cookies")
            self.cookies.load()

        self.cookies.verify_user_login()

    def _process_url(self, url: str):
        self.driver.get(url)

        expand_urls = []
        while True:
            # If current webpage is reached the rate limit, then wait for 30 seconds
            if self.driver.find_elements(by=By.XPATH, value="//*[contains(text(), 'You have exceeded a secondary rate limit')]"):
                for _ in tqdm(range(30), desc="⏳ Rate limit reached, waiting ..."):
                    time.sleep(1)
                self.driver.refresh()
                continue

            # Expand all the code
            [element.click() for element in self.driver.find_elements(by=By.XPATH, value="//*[contains(text(), 'more match')]")]

            codes = self.driver.find_elements(by=By.CLASS_NAME, value="code-list")  # find all elements with class name 'f4'
            for element in codes:
                apis = []
                # Check all regex for each code block
                for regex in REGEX_LIST[2:]:
                    apis.extend(regex.findall(element.text))
                if len(apis) == 0:
                    # Need to show full code. (because the api key is too long)
                    # get the <a> tag
                    a_tag = element.find_element(by=By.XPATH, value=".//a")
                    expand_urls.append(a_tag.get_attribute("href"))

                apis = list(set(apis))
                apis = [api for api in apis if not db_key_exists(self.cur, api)]

                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(check_key, apis))
                    for idx, result in enumerate(results):
                        db_insert(self.con, self.cur, apis[idx], result)

            log.info(f"🌕 There are {len(expand_urls)} urls waiting to be expanded")

            next_buttons = self.driver.find_elements(by=By.XPATH, value="//a[@aria-label='Next Page']")

            try:
                log.info("    🔍 Clicking next page")
                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, "//a[@aria-label='Next Page']")))

                next_buttons = self.driver.find_elements(by=By.XPATH, value="//a[@aria-label='Next Page']")
                next_buttons[0].click()
            except Exception as _:
                log.info("    ⚪️ No more pages")
                break


        # Handle the expand_urls
        for expand_url in tqdm(expand_urls, desc="🔍 Expanding URLs ..."):
            self.driver.get(expand_url)
            time.sleep(3)

            retry = 0
            while retry <= 3:
                matches = []
                for regex in REGEX_LIST:
                    matches.extend(regex.findall(self.driver.page_source))

                if len(matches) == 0:
                    log.info(f"    ⚪️ No matches found in the expanded page, retrying [{retry}/3]...")
                    retry += 1
                    time.sleep(3)
                    continue
                
                new_apis = [api for api in matches if not db_key_exists(self.cur, api)]
                new_apis = list(set(new_apis))

                log.info(f"    🟢 Found {len(matches)} matches in the expanded page, leaving {len(new_apis)} new APIs to check")
                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(check_key, new_apis))
                    for idx, result in enumerate(results):
                        db_insert(self.con, self.cur, new_apis[idx], result)
                break

    def search(self, from_iter: int | None = None):
        total = len(self.candidate_urls)
        pbar = tqdm(
            enumerate(self.candidate_urls),
            total=total,
            desc="🔍 Searching ...",
        )

        if from_iter is None:
            from_iter = self.progress.load(total=total)

        for idx, url in enumerate(self.candidate_urls):
            if idx < from_iter:
                pbar.update()
                time.sleep(0.05)  # let tqdm print the bar
                log.debug(f"⚪️ Skip {url}")
                continue
            self._process_url(url)
            self.progress.save(idx, total)
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
