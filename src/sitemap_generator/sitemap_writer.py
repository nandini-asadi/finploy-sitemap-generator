"""Sitemap writer for generating XML sitemaps compliant with sitemaps.org standards."""

import logging
import os
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin
from lxml import etree
from .types import URLRecord, SitemapEntry
from .config import get_url_priority, get_url_changefreq
from .utils import create_directory_if_not_exists, get_current_timestamp, format_number

logger = logging.getLogger(__name__)


class SitemapWriter:
    """Generates XML sitemaps following sitemaps.org standards."""
    
    def __init__(self, output_dir: str, max_urls_per_sitemap: int = 50000):
        self.output_dir = output_dir
        self.max_urls_per_sitemap = max_urls_per_sitemap
        self.sitemap_namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
        
        # Ensure output directory exists
        create_directory_if_not_exists(output_dir)
    
    def generate_sitemaps(
        self, 
        urls: List[URLRecord], 
        base_url: str = "https://www.finploy.com"
    ) -> List[str]:
        """
        Generate sitemap files from URL records.
        
        Args:
            urls: List of URL records to include in sitemaps
            base_url: Base URL for sitemap locations
            
        Returns:
            List of generated sitemap file paths
        """
        if not urls:
            logger.warning("No URLs provided for sitemap generation")
            return []
        
        logger.info(f"Generating sitemaps for {format_number(len(urls))} URLs")
        
        # Convert URL records to sitemap entries
        sitemap_entries = [self._create_sitemap_entry(url_record) for url_record in urls]
        
        # Split into chunks if necessary
        sitemap_files = []
        
        if len(sitemap_entries) <= self.max_urls_per_sitemap:
            # Single sitemap file
            filename = "sitemap.xml"
            filepath = os.path.join(self.output_dir, filename)
            self._write_sitemap_xml(sitemap_entries, filepath)
            sitemap_files.append(filepath)
            logger.info(f"Generated single sitemap: {filename}")
        else:
            # Multiple sitemap files
            chunks = self._chunk_entries(sitemap_entries, self.max_urls_per_sitemap)
            
            for i, chunk in enumerate(chunks, 1):
                filename = f"sitemap_{i:03d}.xml"
                filepath = os.path.join(self.output_dir, filename)
                self._write_sitemap_xml(chunk, filepath)
                sitemap_files.append(filepath)
            
            logger.info(f"Generated {len(chunks)} sitemap files")
        
        # Generate sitemap index if multiple files
        if len(sitemap_files) > 1:
            index_file = self._generate_sitemap_index(sitemap_files, base_url)
            logger.info(f"Generated sitemap index: {os.path.basename(index_file)}")
        
        return sitemap_files
    
    def _create_sitemap_entry(self, url_record: URLRecord) -> SitemapEntry:
        """Create sitemap entry from URL record."""
        # Calculate lastmod
        lastmod = None
        if url_record.last_crawled:
            lastmod = url_record.last_crawled.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        
        # Get priority and change frequency
        priority = get_url_priority(url_record.url)
        changefreq = get_url_changefreq(url_record.url)
        
        return SitemapEntry(
            loc=url_record.url,
            lastmod=lastmod,
            changefreq=changefreq,
            priority=priority
        )
    
    def _write_sitemap_xml(self, entries: List[SitemapEntry], filepath: str) -> None:
        """Write sitemap entries to XML file."""
        try:
            # Create root element with namespace
            root = etree.Element(
                "urlset",
                nsmap={None: self.sitemap_namespace}
            )
            
            # Add URL entries
            for entry in entries:
                url_element = etree.SubElement(root, "url")
                
                # Location (required)
                loc_element = etree.SubElement(url_element, "loc")
                loc_element.text = entry.loc
                
                # Last modified (optional)
                if entry.lastmod:
                    lastmod_element = etree.SubElement(url_element, "lastmod")
                    lastmod_element.text = entry.lastmod
                
                # Change frequency (optional)
                if entry.changefreq:
                    changefreq_element = etree.SubElement(url_element, "changefreq")
                    changefreq_element.text = entry.changefreq.value
                
                # Priority (optional)
                if entry.priority is not None:
                    priority_element = etree.SubElement(url_element, "priority")
                    priority_element.text = f"{entry.priority:.1f}"
            
            # Write to file with proper formatting
            tree = etree.ElementTree(root)
            tree.write(
                filepath,
                encoding="utf-8",
                xml_declaration=True,
                pretty_print=True
            )
            
            logger.debug(f"Written sitemap with {len(entries)} URLs to {filepath}")
            
        except Exception as e:
            logger.error(f"Error writing sitemap to {filepath}: {e}")
            raise
    
    def _generate_sitemap_index(self, sitemap_files: List[str], base_url: str) -> str:
        """Generate sitemap index file."""
        index_filepath = os.path.join(self.output_dir, "sitemap_index.xml")
        
        try:
            # Create root element
            root = etree.Element(
                "sitemapindex",
                nsmap={None: self.sitemap_namespace}
            )
            
            current_time = get_current_timestamp()
            
            # Add sitemap entries
            for sitemap_file in sitemap_files:
                sitemap_element = etree.SubElement(root, "sitemap")
                
                # Location
                filename = os.path.basename(sitemap_file)
                sitemap_url = urljoin(base_url.rstrip('/') + '/', f"sitemap/{filename}")
                
                loc_element = etree.SubElement(sitemap_element, "loc")
                loc_element.text = sitemap_url
                
                # Last modified
                lastmod_element = etree.SubElement(sitemap_element, "lastmod")
                lastmod_element.text = current_time
            
            # Write to file
            tree = etree.ElementTree(root)
            tree.write(
                index_filepath,
                encoding="utf-8",
                xml_declaration=True,
                pretty_print=True
            )
            
            return index_filepath
            
        except Exception as e:
            logger.error(f"Error writing sitemap index to {index_filepath}: {e}")
            raise
    
    def _chunk_entries(self, entries: List[SitemapEntry], chunk_size: int) -> List[List[SitemapEntry]]:
        """Split entries into chunks of specified size."""
        chunks = []
        for i in range(0, len(entries), chunk_size):
            chunk = entries[i:i + chunk_size]
            chunks.append(chunk)
        return chunks
    
    def validate_sitemap(self, filepath: str) -> bool:
        """Validate sitemap XML against schema."""
        try:
            # Parse XML
            tree = etree.parse(filepath)
            root = tree.getroot()
            
            # Basic validation
            if root.tag != f"{{{self.sitemap_namespace}}}urlset":
                logger.error(f"Invalid root element in {filepath}")
                return False
            
            # Check URL count
            urls = root.findall(f".//{{{self.sitemap_namespace}}}url")
            if len(urls) > self.max_urls_per_sitemap:
                logger.error(f"Too many URLs in sitemap: {len(urls)}")
                return False
            
            # Validate each URL
            for url_elem in urls:
                loc_elem = url_elem.find(f"{{{self.sitemap_namespace}}}loc")
                if loc_elem is None or not loc_elem.text:
                    logger.error("URL missing location")
                    return False
                
                # Validate URL format
                if not loc_elem.text.startswith(('http://', 'https://')):
                    logger.error(f"Invalid URL format: {loc_elem.text}")
                    return False
            
            logger.info(f"Sitemap validation passed: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating sitemap {filepath}: {e}")
            return False
    
    def get_sitemap_stats(self, filepath: str) -> dict:
        """Get statistics about a sitemap file."""
        try:
            tree = etree.parse(filepath)
            root = tree.getroot()
            
            urls = root.findall(f".//{{{self.sitemap_namespace}}}url")
            
            stats = {
                'total_urls': len(urls),
                'file_size_mb': os.path.getsize(filepath) / (1024 * 1024),
                'has_lastmod': 0,
                'has_changefreq': 0,
                'has_priority': 0,
                'priority_distribution': {},
                'changefreq_distribution': {}
            }
            
            for url_elem in urls:
                # Count optional elements
                if url_elem.find(f"{{{self.sitemap_namespace}}}lastmod") is not None:
                    stats['has_lastmod'] += 1
                
                changefreq_elem = url_elem.find(f"{{{self.sitemap_namespace}}}changefreq")
                if changefreq_elem is not None:
                    stats['has_changefreq'] += 1
                    freq = changefreq_elem.text
                    stats['changefreq_distribution'][freq] = stats['changefreq_distribution'].get(freq, 0) + 1
                
                priority_elem = url_elem.find(f"{{{self.sitemap_namespace}}}priority")
                if priority_elem is not None:
                    stats['has_priority'] += 1
                    priority = priority_elem.text
                    stats['priority_distribution'][priority] = stats['priority_distribution'].get(priority, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting sitemap stats for {filepath}: {e}")
            return {}
    
    def generate_robots_txt(self, base_url: str, sitemap_files: List[str]) -> str:
        """Generate robots.txt file with sitemap references."""
        robots_filepath = os.path.join(self.output_dir, "robots.txt")
        
        try:
            with open(robots_filepath, 'w', encoding='utf-8') as f:
                f.write("User-agent: *\n")
                f.write("Allow: /\n\n")
                
                # Add sitemap references
                if len(sitemap_files) == 1:
                    # Single sitemap
                    filename = os.path.basename(sitemap_files[0])
                    sitemap_url = urljoin(base_url.rstrip('/') + '/', f"sitemap/{filename}")
                    f.write(f"Sitemap: {sitemap_url}\n")
                else:
                    # Multiple sitemaps - reference index
                    index_url = urljoin(base_url.rstrip('/') + '/', "sitemap/sitemap_index.xml")
                    f.write(f"Sitemap: {index_url}\n")
            
            logger.info(f"Generated robots.txt: {robots_filepath}")
            return robots_filepath
            
        except Exception as e:
            logger.error(f"Error generating robots.txt: {e}")
            raise
    
    def compress_sitemaps(self, sitemap_files: List[str]) -> List[str]:
        """Compress sitemap files with gzip (optional optimization)."""
        import gzip
        
        compressed_files = []
        
        for sitemap_file in sitemap_files:
            try:
                compressed_file = f"{sitemap_file}.gz"
                
                with open(sitemap_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        f_out.writelines(f_in)
                
                compressed_files.append(compressed_file)
                logger.debug(f"Compressed sitemap: {compressed_file}")
                
            except Exception as e:
                logger.error(f"Error compressing {sitemap_file}: {e}")
        
        return compressed_files
    
    def cleanup_old_sitemaps(self) -> None:
        """Remove old sitemap files from output directory."""
        try:
            for filename in os.listdir(self.output_dir):
                if filename.startswith('sitemap') and filename.endswith('.xml'):
                    filepath = os.path.join(self.output_dir, filename)
                    os.remove(filepath)
                    logger.debug(f"Removed old sitemap: {filename}")
            
            logger.info("Cleaned up old sitemap files")
            
        except Exception as e:
            logger.error(f"Error cleaning up old sitemaps: {e}")


def create_sitemap_writer(output_dir: str, max_urls_per_sitemap: int = 50000) -> SitemapWriter:
    """Factory function to create sitemap writer."""
    return SitemapWriter(output_dir, max_urls_per_sitemap)
