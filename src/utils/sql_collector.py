import mysql.connector
import os
import utils.helper as helper
import utils.logger as logger

logger = logger.setup_logger(logger_name="sql_collector", log_filename="sql_collector.log")

def collect_sql_data(config):
    text_output = "--- DATABASE EXPORT ---\n"
    try:
        db = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=3306
        )
        cursor = db.cursor(dictionary=True)
        
        queries = config.get('database', {}).get('queries', [])
        
        if not queries:
            return "No queries configured in config.yaml"
        
        for query in queries:
            cursor.execute(query)
            rows = cursor.fetchall()
            
            for row in rows:
                header = ""
                content = ""
                
                #1. Detect if it is a Post/Page
                if 'post_content' in row:
                    title = row.get('post_title', 'Untitled')
                    date = row.get('post_date', '')
                    content = str(row.get('post_content', ''))
                    header = f"POST/PAGE: {title} (Date: {date})"
                
                #2. Detect if it is a User Comment
                elif 'comment_content' in row:
                    author = row.get('comment_author', 'Anonymous')
                    date = row.get('comment_date', '')
                    content = str(row.get('comment_content', ''))
                    header = f"USER COMMENT: {author} (Date: {date})"
                
                #3. Detect if it is a Site Author/User
                elif 'display_name' in row:
                    name = row.get('display_name', '')
                    email = row.get('user_email', '')
                    content = "Registered user on the platform as creator/author."
                    header = f"SITE AUTHOR: {name} ({email})"
                
                #4. Detect if it is a Category/Tag
                elif 'term_name' in row:
                    name = row.get('term_name', '')
                    tax = row.get('taxonomy', '')
                    content = str(row.get('description', ''))
                    header = f"STRUCTURE ({tax}): {name}"
                
                else:
                    continue #Ignore if it is an unexpected query

                from bs4 import BeautifulSoup
                import re
                
                #Remove WordPress Gutenberg comment blocks
                clean_content = re.sub(r'', '', content, flags=re.DOTALL)
                
                #Parse and remove HTML tags
                soup = BeautifulSoup(clean_content, 'html.parser')
                clean_text = soup.get_text(separator=' ')
                
                #Clean up extra spaces and line breaks using the helper
                final_text = helper.extract_clean_text(clean_text)
                
                #Append to the master context output
                text_output += f"\n[DB | {header}]\n"
                if final_text.strip():
                    text_output += f"{final_text}\n"
        
        db.close()
        return text_output
        
    except Exception as e:
        logger.error(f"MySQL Error: {e}")
        return f"MySQL Error: {e}"