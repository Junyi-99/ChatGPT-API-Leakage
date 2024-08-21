import argparse
import logging
import os
import pickle
import re
import time
from concurrent.futures import ThreadPoolExecutor

from configs import keywords, languages, regex_list

# from functools import property
from selenium import webdriver
from selenium.common.exceptions import UnableToSetCookieException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm

from utils import check_key, db_close, db_delete, db_get_all_keys, db_insert, db_key_exists, db_open, db_remove_duplication

FORMAT = "%(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt="[%X]")
log = logging.getLogger("ChatGPT-API-Leakage")



class ProgressManager:
    def __init__(self, progress_file=".progress.txt"):
        self.progress_file = progress_file

    def save(self, from_iter: int, total: int):
        with open(self.progress_file, "w") as file:
            file.write(f"{from_iter}/{total}/{time.time()}")

    def load(self, total: int) -> int:
        if not os.path.exists(self.progress_file):
            return 0

        with open(self.progress_file, "r") as file:
            last, totl, tmst = file.read().strip().split("/")
            last, totl = int(last), int(totl)

        if time.time() - float(tmst) < 3600 and totl == total:
            action = input(f"🔍 Progress found, do you want to continue from the last progress ({last}/{totl})? [yes] | no: ").lower()
            if action in {"yes", "y", ""}:
                return last

        return 0

class Cookies:
    def __init__(self, driver):
        self.driver = driver

    def save(self):
        cookies = self.driver.get_cookies()
        with open("cookies.pkl", "wb") as file:
            pickle.dump(cookies, file)
            log.info("🍪 Cookies saved")

    def load(self):
        try:
            with open("cookies.pkl", "rb") as file:
                cookies = pickle.load(file)
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except UnableToSetCookieException as e:
                        log.debug(f"🟡 Warning, unable to set a cookie {cookie}")
        except (EOFError, pickle.UnpicklingError):
            os.remove("cookies.pkl") if os.path.exists("cookies.pkl") else None
            log.error("🔴 Error, unable to load cookies, invalid cookies has been removed, please restart.")

    def test(self):
        """
        Test if the user is really logged in
        """
        log.info("🤗 Redirecting ...")
        self.driver.get("https://github.com/")

        if self.driver.find_elements(by=By.XPATH, value="//*[contains(text(), 'Sign in')]"):
            os.remove("cookies.pkl") if os.path.exists("cookies.pkl") else None
            log.error("🔴 Error, you are not logged in, please restart and try again.")
            exit(1)
        return True


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
            for regex in regex_list
            for language in self.languages
            for keyword in self.keywords
            if regex.pattern != r"sk-proj-\S{74}T3BlbkFJ\S{73}A" and regex.pattern != r"sk-proj-\S{58}T3BlbkFJ\S{58}"
        ]
        self.candidate_urls.insert(0, f"https://github.com/search?q=(/{regex_list[0].pattern}/)&type=code&ref=advsearch")
        self.candidate_urls.insert(0, f"https://github.com/search?q=(/{regex_list[1].pattern}/)&type=code&ref=advsearch")

    def login_to_github(self):
        log.info("🌍 Opening Chrome ...")

        options = webdriver.ChromeOptions()
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")

        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(3)

        self.cookies = Cookies(self.driver)

        cookie_exists = os.path.exists("cookies.pkl")
        self.driver.get("https://github.com/login")

        if not cookie_exists:
            log.info("🤗 No cookies found, please login to GitHub first")
            input("Press Enter after you logged in: ")
            self.cookies.save()
        else:
            log.info("🍪 Cookies found, loading cookies")
            self.cookies.load()

        self.cookies.test()

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
                for regex in regex_list:
                    if regex.pattern == r"sk-proj-\S{74}T3BlbkFJ\S{73}A":
                        # Very Long Key
                        prefix_test = re.compile(r"sk-proj-\S{74}T3BlbkFJ")
                        if len(prefix_test.findall(element.text)) > 0:
                            # Need to show full code. (because the api key is too long)
                            # get the <a> tag
                            a_tag = element.find_element(by=By.XPATH, value=".//a")
                            expand_urls.append(a_tag.get_attribute("href"))
                    else:
                        apis.extend(regex.findall(element.text))

                if len(apis) == 0 and len(expand_urls) == 0:
                    continue

                apis = list(set(apis))
                apis = [api for api in apis if not db_key_exists(self.cur, api)]

                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(check_key, apis))
                    for idx, result in enumerate(results):
                        db_insert(self.con, self.cur, apis[idx], result)

            next_buttons = self.driver.find_elements(by=By.XPATH, value="//a[@aria-label='Next Page']")

            try:
                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, "//a[@aria-label='Next Page']")))

                next_buttons = self.driver.find_elements(by=By.XPATH, value="//a[@aria-label='Next Page']")
                next_buttons[0].click()
            except Exception as _:
                # log.info("    ⚪️ No more pages")
                break


        # Handle the expand_urls
        for expand_url in expand_urls:
            self.driver.get(expand_url)

            try:
                WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
            except Exception as _:
                log.error("🔴 Error, unable to find the iframe, continue anyway")
            time.sleep(3)
            regex = re.compile(r"sk-proj-\S{74}T3BlbkFJ\S{73}A")
            # apply the regex to the whole page
            apis = regex.findall(self.driver.page_source)
            apis = [api for api in apis if not db_key_exists(self.cur, api)]
            print(apis)
            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(check_key, apis))
                for idx, result in enumerate(results):
                    db_insert(self.con, self.cur, apis[idx], result)

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
