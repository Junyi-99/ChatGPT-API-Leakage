# Read sqlite3 databse and export to csv.
# Import csv to sqlite3 database.


import sqlite3
import csv
import os
from utils import db_remove_duplication
def export_to_csv():
    if not os.path.exists('github.db'):
        print('File does not exist')
        return
    
    conn = sqlite3.connect('github.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM APIKeys ORDER BY status DESC;')
    with open('github.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([i[0] for i in cursor.description])
        writer.writerows(cursor)
    conn.close()


def import_to_sqlite3():
    if not os.path.exists('github.csv'):
        print('File does not exist')
        return
    
    conn = sqlite3.connect('github.db')
    cursor = conn.cursor()
    with open('github.csv', 'r') as file:
        reader = csv.reader(file)
        columns = next(reader)
        query = f'INSERT INTO APIKeys ({", ".join(columns)}) VALUES ({", ".join(["?" for _ in columns])});'
        for row in reader:
            cursor.execute(query, row)
    conn.commit()
    db_remove_duplication(conn, cursor)
    conn.close()
    
export_to_csv()

import_to_sqlite3()