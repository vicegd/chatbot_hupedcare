import mysql.connector
import os

def collect_mysql_data(config):
    print("Collecting data from MySQL...")
    text_output = "--- DATABASE EXPORT ---\n"
    try:
        db = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        cursor = db.cursor(dictionary=True)
        
        # Iteramos sobre las queries definidas en tu config o .env
        # Suponiendo que las tienes en una lista
        queries = ["SELECT * FROM productos LIMIT 50", "SELECT * FROM novedades LIMIT 10"]
        
        for query in queries:
            cursor.execute(query)
            rows = cursor.fetchall()
            text_output += f"\nTable Data ({query}):\n"
            for row in rows:
                text_output += str(row) + "\n"
        
        db.close()
        return text_output
    except Exception as e:
        return f"MySQL Error: {e}"