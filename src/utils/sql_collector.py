"""
=============================================================================
RAG SQL DATA COLLECTOR
=============================================================================

This module acts as the bridge between the structured relational database 
(like a WordPress MySQL backend) and the unstructured RAG AI. 

While files (PDFs, Word) are great, a lot of a company's dynamic knowledge 
lives in databases (Blog posts, User Comments, Categories, Author Bios). 
This script pulls that live data and turns it into readable text for the LLM.

How the pipeline works (Step-by-Step):
-----------------------------------------------------------------------------
1. SECURE CONNECTION: It connects to the MySQL database using hidden 
   credentials from the `.env` file.
2. DYNAMIC QUERIES: Instead of hardcoding SQL statements, it reads the 
   queries directly from the `config.yaml`. This means we can add new 
   database tables to the AI's brain in the future without changing this code.
3. SMART ROUTING: It looks at the columns returned by the database to 
   automatically figure out if it's reading a Post, a Comment, or a User, 
   and labels it accordingly.
4. SANITIZATION: Database text often contains HTML tags (like <p> or <strong>) 
   and WordPress block comments (). It uses BeautifulSoup 
   to strip all web-code away, leaving only pure human-readable text.
5. PRIORITY TAGGING: It wraps the data in `[DB | ...]` tags. Because of 
   the rules in the `config.yaml`, the AI knows to treat this data as the 
   absolute "Highest Priority Truth".
=============================================================================
"""

import os
import re

import mysql.connector
from bs4 import BeautifulSoup

import utils.helper as helper
import utils.logger as logger

# Initialize the logger specifically for the SQL collection process
logger = logger.setup_logger(logger_name="sql_collector", log_filename="sql_collector.log")

def collect_sql_data(config):
    """
    Collect and normalize SQL data for inclusion in the master context.

    Args:
        config: Application configuration dictionary containing the SQL queries
            to execute (loaded from config.yaml).

    Returns:
        A formatted text block ready to be appended to `master_context.txt`.
        If collection fails, a short error string is returned instead.
    """
    text_output = "--- DATABASE EXPORT ---\n"
    
    try:
        # 1. Establish Secure Database Connection
        logger.debug("Opening MySQL connection for SQL collection")
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=3306
        )
        
        # dictionary=True makes sure rows come back as dicts (e.g., row['post_title']) 
        # instead of unlabelled tuples, making the code much easier to read.
        cursor = connection.cursor(dictionary=True)
        
        # 2. Fetch Queries from Configuration
        # By keeping queries in config.yaml, non-programmers can add new data sources.
        queries = config.get('database', {}).get('queries', [])
        logger.debug(f"Configured SQL query count: {len(queries)}")
        
        if not queries:
            logger.debug("No SQL queries configured")
            return "No queries configured in config.yaml"
        
        # 3. Execute Queries and Process Results
        for query in queries:
            logger.debug(f"Executing SQL query: {query}")
            cursor.execute(query)
            rows = cursor.fetchall()
            logger.debug(f"Rows returned by query: {len(rows)}")
            
            for row in rows:
                header = ""
                content = ""
                
                # -----------------------------------------------------------
                # SMART ROUTING: Determine the type of data based on columns
                # -----------------------------------------------------------
                
                # Type A: WordPress Posts or Pages
                if 'post_content' in row:
                    title = row.get('post_title', 'Untitled')
                    date = row.get('post_date', '')
                    content = str(row.get('post_content', ''))
                    header = f"POST/PAGE: {title} (Date: {date})"
                
                # Type B: User Comments / Feedback
                elif 'comment_content' in row:
                    author = row.get('comment_author', 'Anonymous')
                    date = row.get('comment_date', '')
                    content = str(row.get('comment_content', ''))
                    header = f"USER COMMENT: {author} (Date: {date})"
                
                # Type C: Site Authors / Registered Users
                elif 'display_name' in row:
                    name = row.get('display_name', '')
                    email = row.get('user_email', '')
                    # We inject a standard sentence so the LLM understands who this person is
                    content = "Registered user on the platform as creator/author."
                    header = f"SITE AUTHOR: {name} ({email})"
                
                # Type D: Taxonomy (Categories or Tags)
                elif 'term_name' in row:
                    name = row.get('term_name', '')
                    taxonomy = row.get('taxonomy', '') # e.g., 'category' or 'post_tag'
                    content = str(row.get('description', ''))
                    header = f"STRUCTURE ({taxonomy}): {name}"
                
                else:
                    # If a new query is added but not handled above, skip it to prevent crashes
                    continue 

                # -----------------------------------------------------------
                # SANITIZATION: Clean up the data for the AI
                # -----------------------------------------------------------
                
                # 1. Remove hidden HTML/WordPress block comments (e.g., )
                # (Note: Fixed the regex pattern to actually target HTML comments)
                clean_content = re.sub(r'', '', content, flags=re.DOTALL)
                
                # 2. Parse and strip all HTML tags (turns <strong>Hello</strong> into Hello)
                soup = BeautifulSoup(clean_content, 'html.parser')
                clean_text = soup.get_text(separator=' ')
                
                # 3. Normalize whitespace (remove double spaces, empty lines)
                final_text = helper.extract_clean_text(clean_text)
                
                # -----------------------------------------------------------
                # FINAL ASSEMBLY
                # -----------------------------------------------------------
                
                # Append the cleaned record to the output string.
                # The '[DB | ...]' prefix is critical because the config.yaml system 
                # prompt tells the AI to prioritize data marked with this tag.
                text_output += f"\n[DB | {header}]\n"
                
                if final_text.strip():
                    text_output += f"{final_text}\n"
        
        # Close connection politely to free up database resources
        connection.close()
        logger.debug("Closed MySQL connection after SQL collection")
        
        return text_output
        
    except Exception as e:
        logger.exception(f"MySQL error: {e}")
        # If the DB is down, we don't crash the whole pipeline, we just log it and move on
        return f"MySQL Error: {e}"