import datetime
import os
import sqlite3
from sqlite3 import Connection, Cursor

from openai import AuthenticationError, OpenAI, RateLimitError


def db_remove_duplication(con: Connection, cur: Cursor) -> None:
    cur.execute('CREATE TABLE temp_table as SELECT DISTINCT * FROM APIKeys;')
    cur.execute('DROP TABLE APIKeys;')
    cur.execute('ALTER TABLE temp_table RENAME TO APIKeys;')
    con.commit()


def db_open(filename: str) -> tuple[Connection, Cursor]:
    if not os.path.exists(filename):
        print("Creating database github.db")

    con = sqlite3.connect('github.db')
    cur = con.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='APIKeys'")
    if cur.fetchone() is None:
        print("Creating table APIKeys")
        cur.execute("CREATE TABLE APIKeys(apiKey, status, lastChecked)")

    return con, cur


def db_close(con: Connection) -> None:
    con.close()


def db_insert(con: Connection, cur: Cursor, apiKey, status):
    today = datetime.date.today()
    cur.execute("INSERT INTO APIKeys(apiKey, status, lastChecked) VALUES(?, ?, ?)", (apiKey, status, today))
    con.commit()


def db_key_exists(cur: Cursor, apiKey) -> bool:
    cur.execute("SELECT apiKey FROM APIKeys WHERE apiKey=?", (apiKey,))
    return cur.fetchone() is not None


def check_key(key, model='gpt-3.5-turbo-0125') -> int:
    try:
        client = OpenAI(api_key=key)

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a yeser, just output lowercase yes only.",
                },
                {"role": "user", "content": "yes or no?"},
            ],
        )
        result = completion.choices[0].message.content
        print("check", key, result)
        return result
    except AuthenticationError as e:
        print("check", key, e.body["code"])
        return e.body["code"]
    except RateLimitError as e:
        print("check", key, e.body["error"]["message"])
        return e.body["code"]
    return "empty"
