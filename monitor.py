#!/usr/bin/env python3
"""
Enterprise Competitor Sitemap Monitor
----------------------------------------------------------------------
A high-performance, self-healing Python script to monitor sitemaps.
Zero dependencies. Zero cost. 
"""

# ====================================================================
# 1. CONFIGURATION BLOCK
# ====================================================================
COMPETITOR_SITEMAP = "https://example.com/sitemap.xml"
SLACK_WEBHOOK_URL = ""

# Enterprise Optimization Settings
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
HTTP_TIMEOUT = 15          # Seconds before abandoning a stuck connection
MAX_RETRIES = 3            # Auto-healing retry attempts for dropped connections
BACKOFF_FACTOR = 2.0       # Exponential wait time multiplier between retries
# ====================================================================

import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import datetime
import json
import gzip
import time
import ssl
import sys
from typing import Iterator, Optional, Set

# ====================================================================
# 2. HTTP REQUEST & XML PARSING ENGINE
# ====================================================================
def fetch_url_with_backoff(url: str) -> Optional[bytes]:
    """
    Self-healing network engine. Automatically retries failed requests, 
    bypasses bad SSL certs, and decodes GZIP payloads silently.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT,
        'Accept-Encoding': 'gzip, deflate'
    })
    
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=ctx) as response:
                data = response.read()
                
                # Dynamically heal compressed payloads
                if response.info().get('Content-Encoding') == 'gzip' or url.endswith('.gz'):
                    data = gzip.decompress(data)
                return data
                
        except urllib.error.HTTPError as e:
            # 429 = Rate Limit. 5xx = Server Issues. Auto-heal by waiting.
            if e.code in [429, 500, 502, 503, 504]:
                wait_time = BACKOFF_FACTOR ** attempt
                print(f"[!] Network bottleneck (HTTP {e.code}). Healing: Retrying {url} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"[!] Fatal HTTP Error for {url}: {e.code} {e.reason}")
                return None
        except (urllib.error.URLError, TimeoutError) as e:
            wait_time = BACKOFF_FACTOR ** attempt
            print(f"[!] Network lag/timeout. Healing: Retrying {url} in {wait_time}s...")
            time.sleep(wait_time)
        except Exception as e:
            print(f"[!] Unexpected network crash on {url}: {e}")
            return None
            
    print(f"[!] Max retries exhausted for {url}. Skipping to prevent system crash.")
    return None

def parse_sitemap_recursive(url: str, seen_urls: Set[str] = None) -> Iterator[dict]:
    """
    Zero-lag recursive generator. Identifies <sitemapindex> structures
    and unpacks them linearly, bypassing massive memory spikes.
    """
    if seen_urls is None:
        seen_urls = set()
        
    if url in seen_urls:
        return
    seen_urls.add(url)

    xml_bytes = fetch_url_with_backoff(url)
    if not xml_bytes:
        return
        
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"[!] XML Corruption detected in {url}: {e}. Healing: Dropping payload.")
        return

    is_index = root.tag.endswith('sitemapindex')
    
    for child in root:
        # Strip namespaces natively so standard schemas and custom ones both map perfectly
        tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        
        if tag_name in ('sitemap', 'url'):
            loc = None
            lastmod = None
            
            for subchild in child:
                sub_tag = subchild.tag.split('}')[-1] if '}' in subchild.tag else subchild.tag
                if sub_tag == 'loc':
                    loc = subchild.text.strip() if subchild.text else None
                elif sub_tag == 'lastmod':
                    lastmod = subchild.text.strip() if subchild.text else None
            
            if not loc:
                continue
                
            if is_index:
                # If the sitemap links to another sitemap, recurse into it seamlessly
                yield from parse_sitemap_recursive(loc, seen_urls)
            else:
                yield {'loc': loc, 'lastmod': lastmod}

# ====================================================================
# 3. TIME-BASED DELTA FILTERING
# ====================================================================
def parse_iso_datetime(date_string: str) -> Optional[datetime.datetime]:
    """
    Transforms volatile ISO date formats into stable, UTC-aware datetime objects.
    """
    if not date_string:
        return None

    d_str = date_string.strip().upper().replace('Z', '+00:00')
    
    if 'T' not in d_str:
        d_str += 'T00:00:00+00:00'
    
    time_part = d_str.split('T')[1]
    if '+' not in time_part and '-' not in time_part:
        d_str += '+00:00'

    try:
        dt = datetime.datetime.fromisoformat(d_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except ValueError:
        return None

# ====================================================================
# 4. NATIVE OUTPUT ALERTS
# ====================================================================
def send_slack_alert_with_backoff(page_url: str, modified_time: str) -> bool:
    """
    Dispatches native Slack webhooks with embedded rate-limit protection.
    """
    if not SLACK_WEBHOOK_URL or not SLACK_WEBHOOK_URL.startswith("http"):
        return False

    message = (
        "🚨 *Competitor Monitor Alert* 🚨\n"
        "A new page or offer change was detected on your competitor's website in the last 24 hours:\n\n"
        f"🔗 *URL:* {page_url}\n"
        f"📅 *Modified:* {modified_time}\n\n"
        "_System Note: Counter-strike outbound sequences should be initialized immediately._"
    )

    payload = {"text": message}
    data = json.dumps(payload).encode('utf-8')
    
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
                if response.status == 200:
                    print(f"[*] Slack alert successfully dispatched: {page_url}")
                    return True
        except Exception as e:
            wait_time = BACKOFF_FACTOR ** attempt
            print(f"[!] Alert dispatch bottleneck. Healing: Retrying Slack in {wait_time}s...")
            time.sleep(wait_time)
            
    return False

# ====================================================================
# ORCHESTRATION ENGINE
# ====================================================================
def monitor_sitemap():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    threshold_24h = now_utc - datetime.timedelta(hours=24)
    
    print(f"[*] Starting Enterprise Competitor Monitor at {now_utc.isoformat()}")
    print(f"[*] Evaluation Threshold: Pages modified after {threshold_24h.isoformat()}")

    alert_count = 0
    urls_scanned = 0

    try:
        # Evaluate URLs instantly as they stream out of the generator (Zero Lag)
        for page_data in parse_sitemap_recursive(COMPETITOR_SITEMAP):
            urls_scanned += 1
            
            page_url = page_data.get('loc')
            lastmod_raw = page_data.get('lastmod')
            
            if not page_url or not lastmod_raw:
                continue

            lastmod_dt = parse_iso_datetime(lastmod_raw)
            
            # Fire alert if threshold is breached
            if lastmod_dt and lastmod_dt > threshold_24h:
                print(f"[*] Trigger identified: {page_url} (Modified: {lastmod_dt.isoformat()})")
                send_slack_alert_with_backoff(page_url, lastmod_dt.isoformat())
                alert_count += 1

    except KeyboardInterrupt:
        print("\n[!] Monitor sequence manually interrupted.")
        sys.exit(0)
    except Exception as e:
        print(f"[!] Critical sequence failure: {e}")
        sys.exit(1)

    print(f"[*] Monitor sequence complete. Scanned {urls_scanned} URLs. Generated {alert_count} alerts.")


if __name__ == "__main__":
    monitor_sitemap()
