import os
from datetime import datetime

import mysql.connector

# NAS MariaDB Connection Configuration
DB_CONFIG = {
    "host": "192.168.5.254",
    "port": 3306,
    "database": "Sandbox5",
    "user": "Sandbox5",
    "password": os.environ.get("DB_PASS", ""),  # kept in .env, not on GitHub
    "connection_timeout": 3,  # don't hang if the NAS is down
}


def insert_match(started_at, player_a, player_b):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        sql = """
            INSERT INTO matches (started_at, player_a, player_b)
            VALUES (%s, %s, %s)
        """
        cursor.execute(sql, (started_at, player_a, player_b))
        conn.commit()
        match_id = cursor.lastrowid
        cursor.close()
        conn.close()
        print(f"[DB INSERT SUCCESS] Match {match_id} started")
        return match_id
    except mysql.connector.Error as err:
        print(f"[ERROR] Database error: {err}")
        return None


def insert_point(match_id, scored_at, scorer, rally_length):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        sql = """
            INSERT INTO points (match_id, scored_at, scorer, rally_length)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (match_id, scored_at, scorer, rally_length))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[DB INSERT SUCCESS] Point for {scorer} | Rally: {rally_length}")
    except mysql.connector.Error as err:
        print(f"[ERROR] Database error: {err}")


def end_match(match_id, ended_at, score_a, score_b, winner, longest_rally):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        sql = """
            UPDATE matches
            SET ended_at = %s, score_a = %s, score_b = %s, winner = %s, longest_rally = %s
            WHERE match_id = %s
        """
        cursor.execute(
            sql, (ended_at, score_a, score_b, winner, longest_rally, match_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[DB UPDATE SUCCESS] Match {match_id} over | Winner: {winner}")
    except mysql.connector.Error as err:
        print(f"[ERROR] Database error: {err}")


def get_board():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        sql = """
            SELECT match_id, longest_rally, ended_at FROM matches
            WHERE ended_at IS NOT NULL
            ORDER BY longest_rally DESC LIMIT 10
        """
        cursor.execute(sql)
        rows = []
        for match_id, rally, at in cursor.fetchall():
            rows.append({"rally": rally, "match_id": match_id, "at": at.isoformat()})
        cursor.close()
        conn.close()
        return rows
    except mysql.connector.Error as err:
        print(f"[ERROR] Database error: {err}")
        return []
