"""
This module is used to manage the progress and the cookies.

It includes the following classes:
- ProgressManager: to manage the progress
- CookieManager: to manage the cookies
- DatabaseManager: to manage the database
"""
import logging
import os
import sys
import pickle
import sqlite3
import time
from datetime import date
from sqlite3 import Connection, Cursor

from selenium.common.exceptions import UnableToSetCookieException
from selenium.webdriver.common.by import By

FORMAT = "%(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt="[%X]")
log = logging.getLogger("ChatGPT-API-Leakage")


class ProgressManager:
    def __init__(self, progress_file=".progress.txt"):
        self.progress_file = progress_file

    def save(self, from_iter: int, total: int):
        with open(self.progress_file, "w", encoding="utf-8") as file:
            file.write(f"{from_iter}/{total}/{time.time()}")

    def load(self, total: int) -> int:
        if not os.path.exists(self.progress_file):
            return 0

        with open(self.progress_file, "r", encoding="utf-8") as file:
            last_, totl_, tmst_ = file.read().strip().split("/")
            last, totl = int(last_), int(totl_)

        if time.time() - float(tmst_) < 3600 and totl == total:
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
                    except UnableToSetCookieException:
                        log.debug("🟡 Warning, unable to set a cookie %s", cookie)
        except (EOFError, pickle.UnpicklingError):
            if os.path.exists("cookies.pkl"):
                os.remove("cookies.pkl")
            log.error("🔴 Error, unable to load cookies, invalid cookies has been removed, please restart.")

    def verify_user_login(self):
        """
        Test if the user is really logged in
        """
        log.info("🤗 Redirecting ...")
        self.driver.get("https://github.com/")

        if self.driver.find_elements(by=By.XPATH, value="//*[contains(text(), 'Sign in')]"):
            if os.path.exists("cookies.pkl"):
                os.remove("cookies.pkl")
            log.error("🔴 Error, you are not logged in, please restart and try again.")
            sys.exit(1)
        return True


class DatabaseManager:
    """
    This class is used to manage the database.
    """
    def __init__(self, db_filename: str):
        self.db_filename = db_filename
        self.con: Connection | None = None
        self.cur: Cursor | None = None

    def __enter__(self):
        if not os.path.exists(self.db_filename):
            logging.info("Creating database github.db")

        self.con = sqlite3.connect(self.db_filename)
        self.cur = self.con.cursor()

        self.cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='APIKeys'")
        if self.cur.fetchone() is None:
            logging.info("Creating table APIKeys")
            self.cur.execute("CREATE TABLE APIKeys(apiKey, status, lastChecked)")

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.con:
            self.con.close()


    def all_keys(self) -> list:
        if self.cur is None:
            raise ValueError("Cursor is not initialized")
        self.cur.execute("SELECT apiKey FROM APIKeys WHERE status='yes'")
        return self.cur.fetchall()

    def deduplicate(self) -> None:
        if self.con is None:
            raise ValueError("Connection is not initialized")
        if self.cur is None:
            raise ValueError("Cursor is not initialized")
        self.cur.execute("CREATE TABLE temp_table as SELECT apiKey, status, MAX(lastChecked) as lastChecked FROM APIKeys GROUP BY apiKey;")
        self.cur.execute("DROP TABLE APIKeys;")
        self.cur.execute("ALTER TABLE temp_table RENAME TO APIKeys;")
        self.con.commit()

    def delete(self, api_key: str) -> None:
        if self.con is None:
            raise ValueError("Connection is not initialized")
        if self.cur is None:
            raise ValueError("Cursor is not initialized")
        self.cur.execute("DELETE FROM APIKeys WHERE apiKey=?", (api_key,))
        self.con.commit()

    def insert(self, api_key: str, status: str):
        if self.con is None:
            raise ValueError("Connection is not initialized")
        if self.cur is None:
            raise ValueError("Cursor is not initialized")
        today = date.today()
        self.cur.execute("INSERT INTO APIKeys(apiKey, status, lastChecked) VALUES(?, ?, ?)", (api_key, status, today))
        self.con.commit()

    def key_exists(self, api_key: str) -> bool:
        if self.cur is None:
            raise ValueError("Cursor is not initialized")
        self.cur.execute("SELECT apiKey FROM APIKeys WHERE apiKey=?", (api_key,))
        return self.cur.fetchone() is not None

    def __del__(self):
        if self.con:
            self.con.close()
