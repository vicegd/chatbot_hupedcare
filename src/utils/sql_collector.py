import os

import mysql.connector

import utils.helper as helper
import utils.logger as logger

logger = logger.setup_logger(logger_name="sql_collector", log_filename="sql_collector.log")

def collect_sql_data(config):
    """Collect and normalize SQL data for inclusion in the master context.

    Args:
        config: Application configuration dictionary containing the SQL queries
            to execute.

    Returns:
        A formatted text block ready to be appended to `master_context.txt`.
        If collection fails, a short error string is returned instead.
    """
    text_output = "--- DATABASE EXPORT ---\n"
    try:
        logger.debug("Opening MySQL connection for SQL collection")
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=3306
        )
        cursor = connection.cursor(dictionary=True)
        
        queries = config.get('database', {}).get('queries', [])
        logger.debug(f"Configured SQL query count: {len(queries)}")
        
        if not queries:
            logger.debug("No SQL queries configured")
            return "No queries configured in config.yaml"
        
        for query in queries:
            # The SQL list is intentionally config-driven so data sources can be extended without code changes.
            logger.debug(f"Executing SQL query: {query}")
            cursor.execute(query)
            rows = cursor.fetchall()
            logger.debug(f"Rows returned by query: {len(rows)}")
            
            for row in rows:
                header = ""
                content = ""
                
                # 1. Detect post or page records.
                if 'post_content' in row:
                    title = row.get('post_title', 'Untitled')
                    date = row.get('post_date', '')
                    content = str(row.get('post_content', ''))
                    header = f"POST/PAGE: {title} (Date: {date})"
                
                # 2. Detect user comment records.
                elif 'comment_content' in row:
                    author = row.get('comment_author', 'Anonymous')
                    date = row.get('comment_date', '')
                    content = str(row.get('comment_content', ''))
                    header = f"USER COMMENT: {author} (Date: {date})"
                
                # 3. Detect site author or user records.
                elif 'display_name' in row:
                    name = row.get('display_name', '')
                    email = row.get('user_email', '')
                    content = "Registered user on the platform as creator/author."
                    header = f"SITE AUTHOR: {name} ({email})"
                
                # 4. Detect taxonomy records such as categories or tags.
                elif 'term_name' in row:
                    name = row.get('term_name', '')
                    taxonomy = row.get('taxonomy', '')
                    content = str(row.get('description', ''))
                    header = f"STRUCTURE ({taxonomy}): {name}"
                
                else:
                    continue  # Ignore unexpected query output.

                import re

                from bs4 import BeautifulSoup
                
                # Remove WordPress editor comments before turning the content into plain text.
                clean_content = re.sub(r'', '', content, flags=re.DOTALL)
                
                # Parse and strip HTML tags.
                soup = BeautifulSoup(clean_content, 'html.parser')
                clean_text = soup.get_text(separator=' ')
                
                # Normalize whitespace using the shared helper.
                final_text = helper.extract_clean_text(clean_text)
                
                # Append the cleaned record to the master context output.
                text_output += f"\n[DB | {header}]\n"
                if final_text.strip():
                    text_output += f"{final_text}\n"
        
        connection.close()
        logger.debug("Closed MySQL connection after SQL collection")
        return text_output
        
    except Exception as e:
        logger.exception(f"MySQL error: {e}")
        return f"MySQL Error: {e}"