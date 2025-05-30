# Destination Search Sandbox

This is a Python-based web application that serves as a sandbox for experimenting with a search engine for hotel destination keywords. It uses Streamlit for the web interface and SQLite with its FTS5 extension for full-text search capabilities. The application allows users to input a search term and retrieve up to 20 matching destinations, categorized as either `city` or `area`.

## How to Run the Project

1. **Install Dependencies**:
   - Ensure Python is installed on your system.
   - Install the required libraries by running:
     ```bash
     pip install streamlit pandas
     ```

2. **Save the Code**:
   - Copy the code from `app.py` into a file named `app.py`.

3. **Launch the App**:
   - Open a terminal, navigate to the folder containing `app.py`, and run:
     ```bash
     streamlit run app.py
     ```
   - Your default web browser will open with the app running locally.

4. **Test the Search**:
   - Type a search term like "Par" to see results such as "Paris" (city) and "Eiffel Tower" (area).
   - The app returns up to 20 matching destinations.

## Features

- **Input**: A text field where users can enter search terms.
- **Output**: A table displaying up to 20 matching destinations with their types (`city` or `area`) and names.
- **Tech Stack**:
  - **Streamlit**: Provides the web-based interface.
  - **SQLite FTS5**: Handles efficient full-text search on destination names.
  - **Pandas**: Formats search results into a clean table.

## SQLite FTS5 Match Pattern Cheatsheet

Below is a cheatsheet for SQLite FTS5 match patterns, used in the `MATCH` operator to query full-text search tables efficiently.

| **Pattern**                 | **Description**                                                                 | **Example**                              | **Result**                                      |
|-----------------------------|--------------------------------------------------------------------------------|------------------------------------------|------------------------------------------------|
| **Simple Term**             | Matches exact words or phrases (case-insensitive).                             | `Paris`                                  | Matches "Paris", "paris", etc.                 |
| **Phrase Search**           | Matches exact sequence of words (enclose in quotes).                           | `"New York"`                             | Matches "New York" exactly.                    |
| **Prefix Search**           | Matches words starting with the term (use `*`).                                | `Par*`                                   | Matches "Paris", "Park", "Partial".            |
| **AND Operator**            | Matches documents containing all terms (implicit or explicit with `AND`).       | `Paris London` or `Paris AND London`     | Matches documents with both "Paris" and "London". |
| **OR Operator**             | Matches documents containing any of the terms.                                 | `Paris OR London`                        | Matches documents with either "Paris" or "London". |
| **NOT Operator**            | Excludes documents containing the term.                                        | `Paris NOT France`                       | Matches documents with "Paris" but not "France". |
| **NEAR Operator**           | Matches terms within a specified distance (default 10 words).                   | `Paris NEAR Eiffel`                      | Matches documents with "Paris" and "Eiffel" close together. |
| **NEAR with Distance**      | Specifies maximum distance between terms.                                      | `Paris NEAR/3 Eiffel`                    | Matches "Paris" and "Eiffel" within 3 words.   |
| **Column-Specific Search**  | Targets a specific column in the FTS table (prefix with column name).          | `name:Paris`                             | Matches "Paris" in the `name` column.          |
| **Boolean Combinations**    | Combines operators for complex queries (use parentheses for precedence).       | `(Paris OR London) NOT France`           | Matches documents with "Paris" or "London" but not "France". |
| **Wildcard in Phrase**      | Combines phrase and prefix search.                                             | `"New *"`                                | Matches phrases starting with "New", like "New York". |
| **Proximity with OR**       | Combines OR and NEAR for flexible proximity searches.                          | `(Paris OR London) NEAR Eiffel`          | Matches "Paris" or "London" near "Eiffel".     |

### Notes
- **Case Insensitivity**: FTS5 searches are case-insensitive by default.
- **Tokenization**: FTS5 breaks text into tokens (words) using a tokenizer (default: `unicode61`). You can customize this for specific needs (e.g., `porter` for stemming).
- **Ranking**: Use `rank` in queries to sort results by relevance (e.g., `ORDER BY rank`).
- **Syntax**: Use the `MATCH` operator in SQL queries, e.g., `SELECT * FROM destinations_fts WHERE name MATCH 'Paris*'`.
- **Limitations**: FTS5 does not support complex regex or fuzzy matching natively; for advanced use cases, consider combining with Python libraries like `fuzzywuzzy`.

### Example Usage in SQLite
```sql
-- Create FTS5 table
CREATE VIRTUAL TABLE destinations_fts USING fts5(name);

-- Insert data
INSERT INTO destinations_fts (name) VALUES ('Paris'), ('Eiffel Tower'), ('New York');

-- Query examples
SELECT * FROM destinations_fts WHERE name MATCH 'Par*'; -- Matches "Paris"
SELECT * FROM destinations_fts WHERE name MATCH '"New York"'; -- Matches exact phrase
SELECT * FROM destinations_fts WHERE name MATCH 'Paris NEAR Eiffel'; -- Matches proximity
```

This lightweight sandbox is perfect for data scientists experimenting with destination search functionality!