"""URL manager for storing and managing discovered URLs in SQLite database."""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Tuple
import aiosqlite
from .types import URLRecord, CrawlStatus, CrawlStatistics
from .utils import normalize_url, create_directory_if_not_exists
import os

logger = logging.getLogger(__name__)


class URLManager:
    """Manages URL storage and retrieval using SQLite database."""
    
    def __init__(self, database_path: str):
        self.database_path = database_path
        self._ensure_database_directory()
        self._lock = asyncio.Lock()
    
    def _ensure_database_directory(self) -> None:
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.database_path)
        if db_dir:
            create_directory_if_not_exists(db_dir)
    
    async def initialize(self) -> None:
        """Initialize database tables."""
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    discovered_at TIMESTAMP NOT NULL,
                    last_crawled TIMESTAMP,
                    status_code INTEGER,
                    content_type TEXT,
                    is_dynamic BOOLEAN DEFAULT FALSE,
                    depth INTEGER DEFAULT 0,
                    parent_url TEXT,
                    crawl_status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    response_time REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS crawl_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    priority INTEGER DEFAULT 0,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_processing BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (url) REFERENCES urls (url)
                )
            """)
            
            # Create indexes for performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_urls_url ON urls (url)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_urls_status ON urls (crawl_status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_urls_depth ON urls (depth)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_queue_priority ON crawl_queue (priority, added_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_queue_processing ON crawl_queue (is_processing)")
            
            await db.commit()
            logger.info(f"Database initialized at {self.database_path}")
    
    async def add_url(
        self,
        url: str,
        parent_url: Optional[str] = None,
        depth: int = 0,
        is_dynamic: bool = False,
        priority: int = 0
    ) -> bool:
        """
        Add URL to database and crawl queue.
        Returns True if URL was added, False if it already exists.
        """
        normalized_url = normalize_url(url)
        
        async with self._lock:
            async with aiosqlite.connect(self.database_path) as db:
                try:
                    # Check if URL already exists
                    cursor = await db.execute(
                        "SELECT id FROM urls WHERE url = ?", (normalized_url,)
                    )
                    existing = await cursor.fetchone()
                    
                    if existing:
                        return False
                    
                    # Insert URL
                    now = datetime.utcnow()
                    await db.execute("""
                        INSERT INTO urls (
                            url, discovered_at, is_dynamic, depth, parent_url, crawl_status
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        normalized_url, now, is_dynamic, depth, parent_url, CrawlStatus.PENDING.value
                    ))
                    
                    # Add to crawl queue
                    await db.execute("""
                        INSERT INTO crawl_queue (url, priority) VALUES (?, ?)
                    """, (normalized_url, priority))
                    
                    await db.commit()
                    logger.debug(f"Added URL to queue: {normalized_url} (depth: {depth})")
                    return True
                    
                except aiosqlite.IntegrityError:
                    # URL already exists (race condition)
                    return False
    
    async def add_urls_batch(
        self,
        urls: List[Tuple[str, Optional[str], int, bool, int]]
    ) -> int:
        """
        Add multiple URLs in batch.
        Each tuple contains: (url, parent_url, depth, is_dynamic, priority)
        Returns number of URLs actually added.
        """
        if not urls:
            return 0
        
        added_count = 0
        normalized_urls = []
        
        for url, parent_url, depth, is_dynamic, priority in urls:
            normalized_url = normalize_url(url)
            normalized_urls.append((normalized_url, parent_url, depth, is_dynamic, priority))
        
        async with self._lock:
            async with aiosqlite.connect(self.database_path) as db:
                now = datetime.utcnow()
                
                for normalized_url, parent_url, depth, is_dynamic, priority in normalized_urls:
                    try:
                        # Check if URL already exists
                        cursor = await db.execute(
                            "SELECT id FROM urls WHERE url = ?", (normalized_url,)
                        )
                        existing = await cursor.fetchone()
                        
                        if not existing:
                            # Insert URL
                            await db.execute("""
                                INSERT INTO urls (
                                    url, discovered_at, is_dynamic, depth, parent_url, crawl_status
                                ) VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                normalized_url, now, is_dynamic, depth, parent_url, CrawlStatus.PENDING.value
                            ))
                            
                            # Add to crawl queue
                            await db.execute("""
                                INSERT INTO crawl_queue (url, priority) VALUES (?, ?)
                            """, (normalized_url, priority))
                            
                            added_count += 1
                            
                    except aiosqlite.IntegrityError:
                        continue
                
                await db.commit()
                
        if added_count > 0:
            logger.info(f"Added {added_count} URLs to queue in batch")
        
        return added_count
    
    async def get_next_urls_to_crawl(self, limit: int = 100) -> List[str]:
        """Get next URLs to crawl from the queue."""
        async with self._lock:
            async with aiosqlite.connect(self.database_path) as db:
                cursor = await db.execute("""
                    SELECT url FROM crawl_queue 
                    WHERE is_processing = FALSE 
                    ORDER BY priority DESC, added_at ASC 
                    LIMIT ?
                """, (limit,))
                
                urls = [row[0] for row in await cursor.fetchall()]
                
                if urls:
                    # Mark as processing
                    placeholders = ",".join("?" * len(urls))
                    await db.execute(f"""
                        UPDATE crawl_queue 
                        SET is_processing = TRUE 
                        WHERE url IN ({placeholders})
                    """, urls)
                    
                    await db.commit()
                
                return urls
    
    async def mark_crawled(
        self,
        url: str,
        status_code: int,
        content_type: Optional[str] = None,
        error_message: Optional[str] = None,
        response_time: float = 0.0
    ) -> None:
        """Mark URL as crawled with results."""
        normalized_url = normalize_url(url)
        now = datetime.utcnow()
        
        crawl_status = CrawlStatus.SUCCESS if 200 <= status_code < 400 else CrawlStatus.ERROR
        if error_message:
            crawl_status = CrawlStatus.ERROR
        
        async with self._lock:
            async with aiosqlite.connect(self.database_path) as db:
                # Update URL record
                await db.execute("""
                    UPDATE urls 
                    SET last_crawled = ?, status_code = ?, content_type = ?, 
                        crawl_status = ?, error_message = ?, response_time = ?, updated_at = ?
                    WHERE url = ?
                """, (
                    now, status_code, content_type, crawl_status.value, 
                    error_message, response_time, now, normalized_url
                ))
                
                # Remove from crawl queue
                await db.execute("DELETE FROM crawl_queue WHERE url = ?", (normalized_url,))
                
                await db.commit()
    
    async def mark_skipped(self, url: str, reason: str) -> None:
        """Mark URL as skipped."""
        normalized_url = normalize_url(url)
        now = datetime.utcnow()
        
        async with self._lock:
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute("""
                    UPDATE urls 
                    SET crawl_status = ?, error_message = ?, updated_at = ?
                    WHERE url = ?
                """, (CrawlStatus.SKIPPED.value, reason, now, normalized_url))
                
                # Remove from crawl queue
                await db.execute("DELETE FROM crawl_queue WHERE url = ?", (normalized_url,))
                
                await db.commit()
    
    async def get_all_valid_urls(self) -> List[URLRecord]:
        """Get all URLs with successful status codes for sitemap generation."""
        async with aiosqlite.connect(self.database_path) as db:
            cursor = await db.execute("""
                SELECT url, discovered_at, last_crawled, status_code, content_type,
                       is_dynamic, depth, parent_url, crawl_status, error_message
                FROM urls 
                WHERE crawl_status = 'success' AND status_code BETWEEN 200 AND 399
                ORDER BY url
            """)
            
            records = []
            async for row in cursor:
                record = URLRecord(
                    url=row[0],
                    discovered_at=datetime.fromisoformat(row[1]) if row[1] else datetime.utcnow(),
                    last_crawled=datetime.fromisoformat(row[2]) if row[2] else None,
                    status_code=row[3],
                    content_type=row[4],
                    is_dynamic=bool(row[5]),
                    depth=row[6],
                    parent_url=row[7],
                    crawl_status=CrawlStatus(row[8]) if row[8] else CrawlStatus.PENDING,
                    error_message=row[9]
                )
                records.append(record)
            
            return records
    
    async def get_statistics(self) -> CrawlStatistics:
        """Get crawling statistics."""
        async with aiosqlite.connect(self.database_path) as db:
            # Total URLs discovered
            cursor = await db.execute("SELECT COUNT(*) FROM urls")
            total_discovered = (await cursor.fetchone())[0]
            
            # URLs by status
            cursor = await db.execute("""
                SELECT crawl_status, COUNT(*) 
                FROM urls 
                GROUP BY crawl_status
            """)
            status_counts = dict(await cursor.fetchall())
            
            # Dynamic vs static
            cursor = await db.execute("""
                SELECT is_dynamic, COUNT(*) 
                FROM urls 
                WHERE crawl_status = 'success'
                GROUP BY is_dynamic
            """)
            dynamic_counts = dict(await cursor.fetchall())
            
            # Pending URLs
            cursor = await db.execute("SELECT COUNT(*) FROM crawl_queue")
            pending_count = (await cursor.fetchone())[0]
            
            successful_crawls = status_counts.get('success', 0)
            failed_crawls = status_counts.get('error', 0)
            skipped_urls = status_counts.get('skipped', 0)
            total_crawled = successful_crawls + failed_crawls + skipped_urls
            
            return CrawlStatistics(
                total_urls_discovered=total_discovered,
                total_urls_crawled=total_crawled,
                successful_crawls=successful_crawls,
                failed_crawls=failed_crawls,
                skipped_urls=skipped_urls,
                dynamic_pages_crawled=dynamic_counts.get(1, 0),  # 1 = True
                static_pages_crawled=dynamic_counts.get(0, 0),   # 0 = False
            )
    
    async def get_queue_size(self) -> int:
        """Get number of URLs remaining in crawl queue."""
        async with aiosqlite.connect(self.database_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM crawl_queue WHERE is_processing = FALSE")
            return (await cursor.fetchone())[0]
    
    async def clear_processing_flags(self) -> None:
        """Clear processing flags (useful for recovery after crashes)."""
        async with self._lock:
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute("UPDATE crawl_queue SET is_processing = FALSE")
                await db.commit()
                logger.info("Cleared processing flags from crawl queue")
    
    async def reset_database(self) -> None:
        """Reset database by dropping all tables."""
        async with self._lock:
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute("DROP TABLE IF EXISTS crawl_queue")
                await db.execute("DROP TABLE IF EXISTS urls")
                await db.commit()
                logger.info("Database reset completed")
        
        # Reinitialize
        await self.initialize()
    
    async def close(self) -> None:
        """Close database connections and cleanup."""
        # SQLite connections are closed automatically with context managers
        logger.debug("URL manager closed")
    
    async def export_urls_to_file(self, file_path: str) -> None:
        """Export all URLs to a text file for debugging."""
        async with aiosqlite.connect(self.database_path) as db:
            cursor = await db.execute("""
                SELECT url, crawl_status, status_code, depth, is_dynamic
                FROM urls 
                ORDER BY depth, url
            """)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("URL\tStatus\tHTTP Code\tDepth\tDynamic\n")
                async for row in cursor:
                    f.write(f"{row[0]}\t{row[1]}\t{row[2] or 'N/A'}\t{row[3]}\t{row[4]}\n")
            
            logger.info(f"Exported URLs to {file_path}")
