import logging
import os
import pickle
import time

from selenium.common.exceptions import UnableToSetCookieException
from selenium.webdriver.common.by import By

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


class CookieManager:
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

    def verify_user_login(self):
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
