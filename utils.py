import datetime
import os
import sqlite3
import logging
from sqlite3 import Connection, Cursor

from openai import AuthenticationError, OpenAI, RateLimitError


def db_get_all_keys(cur: Cursor) -> list:
    # cur.execute("SELECT apiKey FROM APIKeys WHERE status!='access_terminated' AND status!='account_deactivated' AND status!='invalid_api_key' ANS status!='no_organization'")
    cur.execute("SELECT apiKey FROM APIKeys WHERE status='yes'")
    return cur.fetchall()


def db_remove_duplication(con: Connection, cur: Cursor) -> None:
    cur.execute("CREATE TABLE temp_table as SELECT apiKey, status, MAX(lastChecked) as lastChecked FROM APIKeys GROUP BY apiKey;")
    cur.execute("DROP TABLE APIKeys;")
    cur.execute("ALTER TABLE temp_table RENAME TO APIKeys;")
    con.commit()


def db_open(filename: str) -> tuple[Connection, Cursor]:
    if not os.path.exists(filename):
        print("Creating database github.db")

    con = sqlite3.connect(filename)
    cur = con.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='APIKeys'")
    if cur.fetchone() is None:
        print("Creating table APIKeys")
        cur.execute("CREATE TABLE APIKeys(apiKey, status, lastChecked)")

    return con, cur


def db_close(con: Connection) -> None:
    con.close()


def db_delete(con: Connection, cur: Cursor, apiKey) -> None:
    cur.execute("DELETE FROM APIKeys WHERE apiKey=?", (apiKey,))
    con.commit()


def db_insert(con: Connection, cur: Cursor, apiKey, status):
    today = datetime.date.today()
    cur.execute(
        "INSERT INTO APIKeys(apiKey, status, lastChecked) VALUES(?, ?, ?)",
        (apiKey, status, today),
    )
    con.commit()


def db_key_exists(cur: Cursor, apiKey) -> bool:
    cur.execute("SELECT apiKey FROM APIKeys WHERE apiKey=?", (apiKey,))
    return cur.fetchone() is not None


def check_key(key, model="gpt-3.5-turbo") -> int:
    try:
        client = OpenAI(api_key=key)

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a yeser, you only output lowercase yes.",
                },
                {"role": "user", "content": "yes or no? say yes"},
            ],
        )
        result = completion.choices[0].message.content
        logging.info(f"🔑 check ok: {key}: {result}\n")
        return result
    except AuthenticationError as e:
        logging.info(f"🔑 check ok: {key}: {e.body['code']}\n")
        return e.body["code"]
    except RateLimitError as e:
        logging.info(f"🔑 check ok: {key}: {e.body['code']}\n")
        return e.body["code"]
    except Exception as e:
        logging.error(f"🔑 check error: {key}: {e}\n")
        return "empty"
