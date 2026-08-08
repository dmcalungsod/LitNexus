import sqlite3
from pathlib import Path
from src.downloader.logging_config import get_logger, start_operation

logger = get_logger(__name__)


class DatabaseManager:
    def __init__(self, db_path: str = "workspace.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initializes the database schema if it doesn't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Papers Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    doi TEXT PRIMARY KEY,
                    title TEXT,
                    authors TEXT,
                    year INTEGER,
                    abstract TEXT,
                    pdf_status TEXT DEFAULT 'pending',
                    generation INTEGER DEFAULT 0
                )
            """)

            # Migrations: add columns if they don't exist
            columns = [
                "abstract TEXT",
                "external_reference_count INTEGER",
                "external_citation_count INTEGER",
                "external_counts_source TEXT",
                "external_counts_fetched_at TEXT",
                "references_fetch_status TEXT",
                "citations_fetch_status TEXT",
                "local_filepath TEXT",
            ]
            for col in columns:
                try:
                    cursor.execute(f"ALTER TABLE papers ADD COLUMN {col}")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                except Exception:
                    logger.exception(
                        f"Failed to migrate column {col}",
                        extra={"event": "db_migration_error", "column": col},
                    )

            # Edges Table (Lineage)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    source_doi TEXT,
                    target_doi TEXT,
                    PRIMARY KEY (source_doi, target_doi),
                    FOREIGN KEY (source_doi) REFERENCES papers (doi),
                    FOREIGN KEY (target_doi) REFERENCES papers (doi)
                )
            """)

            # Discoveries Table (Provenance)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paper_discoveries (
                    paper_doi TEXT,
                    source_doi TEXT,
                    direction TEXT,
                    generation INTEGER,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (paper_doi, source_doi, direction)
                )
            """)

            # Sessions Table (Reproducibility)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seed_identifier TEXT,
                    date_started TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    target_depth INTEGER DEFAULT 1
                )
            """)

            conn.commit()
            logger.info(
                f"Database initialized at {self.db_path}",
                extra={"event": "db_init", "db_path": self.db_path},
            )

    def add_paper(
        self,
        doi: str,
        title: str = None,
        authors: str = None,
        year: int = None,
        abstract: str = None,
        generation: int = 0,
    ):
        """Adds a paper to the database. Ignores if it already exists to enforce deduplication."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO papers (doi, title, authors, year, abstract, generation)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (doi, title, authors, year, abstract, generation),
            )
            conn.commit()

    def add_edge(self, source_doi: str, target_doi: str):
        """Records that source_doi cited target_doi."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO edges (source_doi, target_doi)
                VALUES (?, ?)
            """,
                (source_doi, target_doi),
            )
            conn.commit()

    def add_discovery(self, paper_doi: str, source_doi: str, direction: str, generation: int):
        """Records how a paper entered the workspace."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO paper_discoveries (paper_doi, source_doi, direction, generation)
                VALUES (?, ?, ?, ?)
            """,
                (paper_doi, source_doi, direction, generation),
            )
            conn.commit()

    def get_provenance(self, doi: str):
        """Returns list of discoveries for a paper: [(source_doi, direction, source_title)]"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT d.source_doi, d.direction, p.title 
                FROM paper_discoveries d
                LEFT JOIN papers p ON d.source_doi = p.doi
                WHERE d.paper_doi = ?
            """,
                (doi,),
            )
            return cursor.fetchall()

    def get_all_papers(self):
        """Retrieves all papers for the data grid."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT doi, title, authors, year, generation, pdf_status, external_reference_count, external_citation_count FROM papers"
            )
            return cursor.fetchall()

    def get_root_papers(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT doi, title, authors, year, generation, pdf_status, external_reference_count, external_citation_count FROM papers WHERE generation = 0"
            )
            return cursor.fetchall()

    def get_past_references(self, doi: str):
        # Papers that this 'doi' cited (source_doi = doi, target_doi = reference)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.doi, p.title, p.authors, p.year, p.generation, p.pdf_status, p.external_reference_count, p.external_citation_count
                FROM papers p
                JOIN edges e ON p.doi = e.target_doi
                WHERE e.source_doi = ?
            """,
                (doi,),
            )
            return cursor.fetchall()

    def get_future_citations(self, doi: str):
        # Papers that cite this 'doi' (source_doi = citation, target_doi = doi)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.doi, p.title, p.authors, p.year, p.generation, p.pdf_status, p.external_reference_count, p.external_citation_count
                FROM papers p
                JOIN edges e ON p.doi = e.source_doi
                WHERE e.target_doi = ?
            """,
                (doi,),
            )
            return cursor.fetchall()

    def update_pdf_status(self, doi: str, status: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE papers SET pdf_status = ? WHERE doi = ?", (status, doi))
            conn.commit()

    def update_fetch_status(self, doi: str, edge_type: str, status: str):
        """Update fetch status. edge_type should be 'references' or 'citations'."""
        if edge_type not in ("references", "citations"):
            return
        column = f"{edge_type}_fetch_status"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE papers SET {column} = ? WHERE doi = ?", (status, doi))
            conn.commit()

    def update_paper_filepath(self, doi: str, filepath: str | None):
        """Store the exact local file path for a downloaded PDF."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE papers SET local_filepath = ? WHERE doi = ?", (filepath, doi))
            conn.commit()

    def get_paper_filepath(self, doi: str) -> str | None:
        """Return the stored local file path for a paper, or None."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT local_filepath FROM papers WHERE doi = ?", (doi,))
                row = cursor.fetchone()
                return row[0] if row and row[0] else None
            except Exception:
                return None

    def get_paper_generation(self, doi: str) -> int:
        """Returns the generation of a specific paper. Returns 0 if not found."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT generation FROM papers WHERE doi = ?", (doi,))
            row = cursor.fetchone()
            return row[0] if row else 0

    def update_paper_metadata(
        self,
        doi: str,
        title: str,
        year: int,
        authors: str = None,
        abstract: str = None,
        ext_ref: int = None,
        ext_cite: int = None,
    ):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Dynamically build the update query to only update provided counts if they exist
            update_parts = ["title = ?", "year = ?", "authors = ?", "abstract = ?"]
            params = [title, year, authors, abstract]

            if ext_ref is not None:
                update_parts.append("external_reference_count = ?")
                params.append(ext_ref)
            if ext_cite is not None:
                update_parts.append("external_citation_count = ?")
                params.append(ext_cite)

            params.append(doi)
            query = "UPDATE papers SET " + ", ".join(update_parts) + " WHERE doi = ?"

            cursor.execute(query, tuple(params))
            conn.commit()

    def get_paper_details(self, doi: str):
        """Returns details needed for the info dialogger."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT title, authors, year, abstract, pdf_status, generation,
                       external_reference_count, external_citation_count,
                       references_fetch_status, citations_fetch_status
                FROM papers WHERE doi = ?
            """,
                (doi,),
            )
            return cursor.fetchone()

    def get_edge_counts(self, doi: str):
        """Returns (references_count, cited_by_count) for a given paper."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM edges WHERE source_doi = ?", (doi,))
            references_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM edges WHERE target_doi = ?", (doi,))
            cited_by_count = cursor.fetchone()[0]

            return references_count, cited_by_count

    def clear_workspace(self):
        """Clears all data from the workspace."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM paper_discoveries")
            cursor.execute("DELETE FROM edges")
            cursor.execute("DELETE FROM papers")
            cursor.execute("DELETE FROM sessions")
            conn.commit()
            logger.info("Workspace database cleared", extra={"event": "db_clear_workspace"})
