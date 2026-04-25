#!/usr/bin/env python3
"""
Web Performance Assessment Script
Analyzes Core Web Vitals, technical optimizations, and provides actionable recommendations

Installation:
    pip install requests dnspython beautifulsoup4
    
    # Optional for JavaScript-rendered pages:
    pip install selenium
    # Also install Chrome/Chromium browser

Usage:
    python web_performance_audit.py <url> <crux_api_key> [--no-browser]
    
Examples:
    python web_performance_audit.py www.example.gov.au YOUR_API_KEY
    python web_performance_audit.py www.example.gov.au YOUR_API_KEY --no-browser
"""

import requests
import dns.resolver
import dns.message
import dns.query
import dns.flags
import dns.rdatatype
import json
import sys
import shutil
import subprocess
from urllib.parse import urlparse, urljoin
from datetime import datetime
import socket
import re
from bs4 import BeautifulSoup
import ipaddress
from typing import Callable

class WebPerformanceAuditor:
    def __init__(self, url, crux_api_key, use_browser=False, additional_first_party_domains=None, progress_callback=None):
        self.url = url if url.startswith('http') else f'https://{url}'
        self.crux_api_key = crux_api_key
        self.use_browser = use_browser
        self.domain = urlparse(self.url).netloc
        self.progress_callback: Callable[[str], None] | None = progress_callback
        self.browser_protocol_events = []
        self.browser_protocol_by_url = {}
        self.lcp_resource_url = None
        self.browser_render_blocking_events = []
        # Normalise additional first-party domains (strip leading dot/whitespace).
        self.additional_first_party_domains = [
            d.strip().lstrip('.').lower()
            for d in (additional_first_party_domains or [])
            if d.strip()
        ]
        self.results = {
            'url': self.url,
            'timestamp': datetime.now().isoformat(),
            'rendering_method': 'browser' if use_browser else 'static',
            'crux_data': {},
            'technical_checks': {},
            'recommendations': []
        }

    def _report_progress(self, message):
        if self.progress_callback:
            self.progress_callback(message)
    
    def run_full_audit(self):
        """Execute all audit checks"""
        print(f"\n{'='*60}")
        print(f"Web Performance Audit: {self.url}")
        print(f"{'='*60}\n")
        
        # 1. CrUX Data Analysis
        self._report_progress("Fetching CrUX data...")
        print("📊 Fetching Chrome User Experience Report data...")
        self.check_crux_data()
        
        # 2. DNS Configuration
        self._report_progress("Checking DNS and IPv6...")
        print("\n🔍 Checking DNS configuration...")
        self.check_dns_ttl()
        self.check_ipv6_support()
        
        # 3. Parse HTML and extract resources
        self._report_progress("Fetching page and rendering HTML...")
        print("\n📄 Parsing HTML and extracting resources...")
        if self.use_browser:
            print("   ℹ️  Using headless browser mode for JavaScript rendering")
        self.fetch_and_parse_html()
        
        # 4. CDN Detection (improved with IP-based lookup)
        self._report_progress("Detecting CDN usage...")
        print("\n☁️  Detecting CDN usage...")
        self.detect_cdn_advanced()
        
        # 5. Check first-party static resources compression
        self._report_progress("Checking compression on first-party assets...")
        print("\n📦 Checking first-party CSS/JS compression...")
        self.check_first_party_compression()
        
        # 6. Analyze render-blocking resources in HEAD
        self._report_progress("Analyzing render-blocking resources...")
        print("\n⚡ Analyzing render-blocking resources in <head>...")
        self.analyze_head_blocking_resources()
        
        # 7. Additional resource analysis
        self._report_progress("Analyzing resource hints, images, fonts, protocol, and caching...")
        print("\n🔍 Additional resource analysis...")
        self.analyze_additional_resources()

        # 8. Slow resource analysis from browser network timings
        self._report_progress("Analyzing slow resources from browser timings...")
        print("\n🐢 Checking slow resources from browser timings...")
        self.analyze_slow_resources()

        # 9. Heavy payload analysis from browser network timings
        self._report_progress("Analyzing heavy resources from browser timings...")
        print("\n📦 Checking heavy resources from browser timings...")
        self.analyze_heavy_resources()

        # 10. Per-domain protocol breakdown
        self._report_progress("Analyzing protocol usage by domain...")
        print("\n🌐 Checking per-domain HTTP protocol usage...")
        self.check_resource_protocols()

        # 11. Generate Report
        self._report_progress("Finalizing audit results...")
        print("\n" + "="*60)
        self.generate_report()
        
        return self.results

    def run_dns_only_audit(self):
        """Execute only DNS-related checks."""
        print(f"\n{'='*60}")
        print(f"DNS-Only Audit: {self.url}")
        print(f"{'='*60}\n")

        self._report_progress("Checking DNS and IPv6...")
        print("🔍 Checking DNS configuration...")
        self.check_dns_ttl()
        self.check_ipv6_support()

        self._report_progress("Detecting CDN usage...")
        print("\n☁️  Detecting CDN usage...")
        self.detect_cdn_advanced()

        self._report_progress("Finalizing DNS audit results...")
        print("\n" + "="*60)
        self.generate_report()

        return self.results
    
    def format_url_display(self, url, max_length=None):
        """Return compact URL display as domain/.../resource, marking truncation when needed."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc
            path = parsed.path

            # Show compact shape: domain/.../resource-name
            segments = [s for s in path.split('/') if s]
            resource_name = segments[-1] if segments else ''

            if resource_name:
                display = f"{domain}/.../{resource_name}"
            else:
                display = domain

            # If caller asks for a max width, keep the compact shape but mark hard truncation.
            if max_length and len(display) > max_length:
                marker = " [truncated]"
                cut_len = max(0, max_length - len(marker))
                display = display[:cut_len] + marker

            return display
        except Exception:
            # Fallback: still make truncation explicit when max_length applies.
            if max_length and len(url) > max_length:
                marker = " [truncated]"
                cut_len = max(0, max_length - len(marker))
                return url[:cut_len] + marker
            return url
    
    def check_crux_data(self):
        """Fetch CrUX data for current and historical trends"""
        try:
            # Current data - try both URL and origin
            crux_url = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
            params = {"key": self.crux_api_key}
            
            # Try URL-level first
            payload = {
                "url": self.url,
                "formFactor": "PHONE"
            }
            
            response = requests.post(crux_url, json=payload, params=params, timeout=10)
            
            # If URL-level fails, try origin-level
            if response.status_code == 400:
                parsed = urlparse(self.url)
                origin = f"{parsed.scheme}://{parsed.netloc}"
                payload = {
                    "origin": origin,
                    "formFactor": "PHONE"
                }
                response = requests.post(crux_url, json=payload, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.results['crux_data'] = self.parse_crux_data(data)
                self.print_crux_summary(data)
            else:
                print(f"   ⚠️  CrUX data not available (Status: {response.status_code})")
                if response.status_code == 400:
                    print(f"   ℹ️  Response: {response.text[:200]}")
                self.results['crux_data'] = {'status': 'not_available'}
                
        except Exception as e:
            print(f"   ❌ Error fetching CrUX data: {str(e)}")
            self.results['crux_data'] = {'error': str(e)}
    
    def parse_crux_data(self, data):
        """Parse and categorize CrUX metrics"""
        parsed = {}
        
        if 'record' not in data:
            return {'status': 'no_data'}
        
        metrics = data['record'].get('metrics', {})
        
        for metric_key, metric_data in metrics.items():
            percentiles = metric_data.get('percentiles', {})
            histogram = metric_data.get('histogram', [])
            
            parsed[metric_key] = {
                'p75': percentiles.get('p75'),
                'histogram': histogram
            }
        
        return parsed
    
    def print_crux_summary(self, data):
        """Print formatted CrUX summary"""
        if 'record' not in data:
            return
        
        metrics = data['record'].get('metrics', {})
        
        print("\n   Core Web Vitals (Mobile - 75th percentile):")
        print("   " + "-"*50)
        
        # LCP
        if 'largest_contentful_paint' in metrics:
            lcp = metrics['largest_contentful_paint']['percentiles']['p75']
            lcp = int(lcp) if isinstance(lcp, str) else lcp
            lcp_status = self.get_cwv_status(lcp, 2500, 4000)
            print(f"   LCP: {lcp}ms {lcp_status}")
        
        # INP (replacing FID)
        if 'interaction_to_next_paint' in metrics:
            inp = metrics['interaction_to_next_paint']['percentiles']['p75']
            inp = int(inp) if isinstance(inp, str) else inp
            inp_status = self.get_cwv_status(inp, 200, 500)
            print(f"   INP: {inp}ms {inp_status}")
        
        # CLS
        if 'cumulative_layout_shift' in metrics:
            cls_raw = metrics['cumulative_layout_shift']['percentiles']['p75']
            cls_raw = float(cls_raw) if isinstance(cls_raw, str) else cls_raw
            cls = cls_raw / 100
            cls_status = self.get_cwv_status(cls, 0.1, 0.25)
            print(f"   CLS: {cls:.3f} {cls_status}")
        
        # TTFB
        if 'time_to_first_byte' in metrics:
            ttfb = metrics['time_to_first_byte']['percentiles']['p75']
            ttfb = int(ttfb) if isinstance(ttfb, str) else ttfb
            ttfb_status = self.get_cwv_status(ttfb, 800, 1800)
            print(f"   TTFB: {ttfb}ms {ttfb_status}")
        
        # FCP
        if 'first_contentful_paint' in metrics:
            fcp = metrics['first_contentful_paint']['percentiles']['p75']
            fcp = int(fcp) if isinstance(fcp, str) else fcp
            fcp_status = self.get_cwv_status(fcp, 1800, 3000)
            print(f"   FCP: {fcp}ms {fcp_status}")
    
    def get_cwv_status(self, value, good_threshold, poor_threshold):
        """Determine if metric is good, needs improvement, or poor"""
        if value <= good_threshold:
            return "✅ Good"
        elif value <= poor_threshold:
            return "⚠️  Needs Improvement"
        else:
            return "❌ Poor"

    def _get_crux_p75(self, metric_keys):
        """Return first available CrUX p75 value for any provided metric key."""
        crux_data = self.results.get('crux_data', {})
        for key in metric_keys:
            metric = crux_data.get(key)
            if not metric:
                continue
            p75 = metric.get('p75')
            if p75 is None:
                continue
            try:
                return float(p75)
            except (TypeError, ValueError):
                continue
        return None

    def _normalize_http_version(self, version_text):
        """Normalize curl/HTTP library version text into HTTP/x labels."""
        value = (version_text or '').strip().upper().replace('HTTP/', '')
        if value.startswith('H3'):
            return 'HTTP/3'
        if value in {'H2', '2', '2.0'}:
            return 'HTTP/2'
        if value in {'3', '3.0'}:
            return 'HTTP/3'
        if value in {'1.1', '1'}:
            return 'HTTP/1.1'
        return 'HTTP/1.1'

    def _normalize_browser_url(self, url):
        """Normalize browser URLs for reliable lookup."""
        return (url or '').split('#', 1)[0].rstrip('/')

    def _capture_browser_protocols(self, driver):
        """Capture protocol/header/timing info from Chrome DevTools logs."""
        events_by_request_id = {}
        request_start_times = {}

        try:
            raw_logs = driver.get_log('performance')
        except Exception:
            self.browser_protocol_events = []
            self.browser_protocol_by_url = {}
            return

        for entry in raw_logs:
            try:
                message = json.loads(entry['message']).get('message', {})
                method = message.get('method')
                params = message.get('params', {})

                if method == 'Network.requestWillBeSent':
                    request_id = params.get('requestId')
                    timestamp = params.get('timestamp')
                    if request_id and timestamp is not None:
                        request_start_times[request_id] = float(timestamp)
                    continue

                if method == 'Network.loadingFinished':
                    request_id = params.get('requestId')
                    end_ts = params.get('timestamp')
                    if request_id and end_ts is not None and request_id in events_by_request_id:
                        start_ts = request_start_times.get(request_id)
                        if start_ts is not None:
                            duration_ms = max(0.0, (float(end_ts) - float(start_ts)) * 1000)
                            events_by_request_id[request_id]['duration_ms'] = round(duration_ms, 1)
                        encoded_len = params.get('encodedDataLength')
                        if encoded_len is not None:
                            try:
                                events_by_request_id[request_id]['transfer_size_bytes'] = int(encoded_len)
                            except (TypeError, ValueError):
                                pass
                    continue

                if method != 'Network.responseReceived':
                    continue

                request_id = params.get('requestId')
                response = params.get('response', {})
                url = response.get('url', '')
                protocol = self._normalize_http_version(response.get('protocol', ''))
                resource_type = params.get('type', 'Other')
                status_code = int(response.get('status', 0) or 0)
                mime_type = (response.get('mimeType') or '').lower()
                content_type = ''
                headers = response.get('headers', {}) or {}
                if isinstance(headers, dict):
                    content_type = (
                        headers.get('content-type')
                        or headers.get('Content-Type')
                        or ''
                    ).lower()
                cache_control = ''
                if isinstance(headers, dict):
                    cache_control = (
                        headers.get('cache-control')
                        or headers.get('Cache-Control')
                        or ''
                    ).lower()
                content_length = None
                if isinstance(headers, dict):
                    raw_length = headers.get('content-length') or headers.get('Content-Length')
                    if raw_length is not None:
                        try:
                            content_length = int(str(raw_length).strip())
                        except ValueError:
                            content_length = None

                if not url:
                    continue

                normalized_url = self._normalize_browser_url(url)
                event = {
                    'url': normalized_url,
                    'domain': urlparse(url).netloc.lower(),
                    'protocol': protocol,
                    'resource_type': resource_type,
                    'status': status_code,
                    'mime_type': mime_type,
                    'content_type': content_type or mime_type,
                    'cache_control': cache_control,
                    'duration_ms': None,
                    'transfer_size_bytes': content_length,
                }

                if request_id:
                    events_by_request_id[request_id] = event
            except Exception:
                continue

        events = list(events_by_request_id.values())
        self.browser_protocol_events = events

        events_by_url = {}
        for event in events:
            events_by_url[event['url']] = event
        self.browser_protocol_by_url = events_by_url

    def _capture_lcp_resource(self, driver):
        """Capture current LCP resource URL from the browser performance API."""
        try:
            lcp_url = driver.execute_script(
                """
                const entries = performance.getEntriesByType('largest-contentful-paint');
                if (!entries || entries.length === 0) return '';
                const last = entries[entries.length - 1];
                if (last.url) return last.url;
                if (last.element && last.element.currentSrc) return last.element.currentSrc;
                if (last.element && last.element.src) return last.element.src;
                return '';
                """
            )
            if lcp_url:
                self.lcp_resource_url = self._normalize_browser_url(lcp_url)
                return
        except Exception:
            pass
        self.lcp_resource_url = None

    def _capture_render_blocking_from_performance_api(self, driver):
        """Use PerformanceResourceTiming.renderBlockingStatus to find truly render-blocking
        resources. This is the authoritative signal from Chrome's rendering engine
        (Chrome 107+) and is the same data source Lighthouse uses internally.

        Unlike HTML attribute inspection (async/defer), this correctly handles:
        - type="module" scripts (deferred by default — not blocking)
        - Dynamically injected vs parser-inserted resources
        - Preloaded resources that are non-blocking at fetch time
        - Cross-origin vs same-origin blocking differences
        """
        try:
            events = driver.execute_script(
                """
                return performance.getEntriesByType('resource')
                    .filter(function(r) { return r.renderBlockingStatus === 'blocking'; })
                    .map(function(r) {
                        return {
                            url: r.name,
                            initiator_type: r.initiatorType,
                            start_time_ms: Math.round(r.startTime),
                            duration_ms: Math.round(r.duration),
                            transfer_size_bytes: r.transferSize,
                            encoded_body_size: r.encodedBodySize
                        };
                    });
                """
            )
            self.browser_render_blocking_events = events if isinstance(events, list) else []
        except Exception:
            self.browser_render_blocking_events = []

    def _lookup_browser_protocol(self, url):
        """Lookup protocol for a URL from captured browser DevTools events."""
        if not self.browser_protocol_by_url:
            return None

        normalized_url = self._normalize_browser_url(url)
        if normalized_url in self.browser_protocol_by_url:
            return self.browser_protocol_by_url[normalized_url]['protocol']

        # Redirects can change exact URL; fall back to document/domain match.
        target_domain = urlparse(url).netloc.lower()
        for event in self.browser_protocol_events:
            if event['resource_type'] == 'Document' and event['domain'] == target_domain:
                return event['protocol']

        return None

    def _detect_http_protocol(self, url, timeout_seconds=12):
        """Detect negotiated HTTP protocol for a URL using curl, with requests fallback."""
        if self.use_browser:
            browser_protocol = self._lookup_browser_protocol(url)
            if browser_protocol:
                return browser_protocol, 'chrome-devtools'

        curl_path = shutil.which('curl')
        if curl_path:
            try:
                result = subprocess.run(
                    [
                        curl_path,
                        '-sS',
                        '-L',
                        '--compressed',
                        '--range', '0-0',
                        '--connect-timeout', '5',
                        '--max-time', str(timeout_seconds),
                        '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        '-o', '/dev/null',
                        '-w', '%{http_version}',
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    return self._normalize_http_version(result.stdout), 'curl'
            except Exception:
                pass

        # Fallback: requests typically only reflects HTTP/1.1, but keep it as last resort.
        try:
            response = requests.get(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                timeout=timeout_seconds,
                allow_redirects=True,
                stream=True,
            )
            protocol_map = {20: 'HTTP/2', 30: 'HTTP/3'}
            return protocol_map.get(response.raw.version, 'HTTP/1.1'), 'requests-fallback'
        except Exception:
            return None, 'unavailable'

    def _extract_max_age(self, cache_control):
        """Extract max-age seconds from Cache-Control header."""
        if not cache_control:
            return None
        match = re.search(r'max-age=(\d+)', cache_control.lower())
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _is_static_event(self, event):
        """Return static asset category for an event, or None if not static."""
        resource_type = (event.get('resource_type') or '').lower()
        content_type = (event.get('content_type') or '').lower()

        if resource_type == 'stylesheet' or 'text/css' in content_type:
            return 'css'
        if resource_type == 'script' or 'javascript' in content_type:
            return 'js'
        if resource_type == 'image' or content_type.startswith('image/'):
            return 'images'
        if resource_type == 'font' or 'font/' in content_type or 'woff' in content_type or 'ttf' in content_type:
            return 'fonts'
        return None

    def _analyze_caching_from_browser_events(self):
        """Analyze caching from browser-loaded responses, first-party only."""
        first_party_events = [
            e for e in self.browser_protocol_events
            if e.get('url') and self.is_first_party(e['url'])
        ]

        # Document cache-control (main HTML page from browser network events)
        doc_event = None
        final_norm = self._normalize_browser_url(self.final_url)
        for event in first_party_events:
            if event.get('resource_type') == 'Document' and event.get('url') == final_norm:
                doc_event = event
                break
        if not doc_event:
            for event in first_party_events:
                if event.get('resource_type') == 'Document':
                    doc_event = event
                    break

        doc_cache_control = (doc_event or {}).get('cache_control', '')
        doc_max_age = self._extract_max_age(doc_cache_control)

        static_counts = {'css': 0, 'js': 0, 'fonts': 0, 'images': 0}
        static_low_cache_counts = {'css': 0, 'js': 0, 'fonts': 0, 'images': 0}
        static_missing_cache = {'css': 0, 'js': 0, 'fonts': 0, 'images': 0}
        low_ttl_resources = []

        seen_urls = set()
        for event in first_party_events:
            url = event.get('url')
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            asset_type = self._is_static_event(event)
            if not asset_type:
                continue

            static_counts[asset_type] += 1
            max_age = self._extract_max_age(event.get('cache_control', ''))
            if max_age is None:
                static_missing_cache[asset_type] += 1
            elif max_age < 86400:
                static_low_cache_counts[asset_type] += 1
                low_ttl_resources.append({
                    'type': asset_type,
                    'url': url,
                    'ttl_seconds': max_age,
                    'cache_control': event.get('cache_control', ''),
                })

        self.results['technical_checks']['cache_control'] = {
            'source': 'chrome-devtools',
            'first_party_document_cache_control': doc_cache_control,
            'first_party_document_max_age': doc_max_age,
            'first_party_static_resources': {
                'total': static_counts,
                'low_cache_lt_1_day': static_low_cache_counts,
                'missing_max_age': static_missing_cache,
                'ttl_lt_1_day_resources': low_ttl_resources,
            },
        }

        if doc_max_age is None:
            print("   Browser Caching (1st-party HTML): ❌ No cache-control max-age set")
            self.results['recommendations'].append({
                'category': 'Caching',
                'severity': 'MEDIUM',
                'issue': 'No cache-control max-age header on first-party HTML response',
                'recommendation': 'Set explicit cache-control max-age/s-maxage policy for HTML as appropriate for content freshness.'
            })
        elif doc_max_age < 3600:
            print(f"   Browser Caching (1st-party HTML): ❌ Too short ({doc_max_age}s)")
        elif doc_max_age < 86400:
            print(f"   Browser Caching (1st-party HTML): ⚠️  Could be longer ({doc_max_age}s)")
        else:
            print(f"   Browser Caching (1st-party HTML): ✅ Good ({doc_max_age/86400:.1f} days)")

        total_static = sum(static_counts.values())
        low_or_missing = sum(static_low_cache_counts.values()) + sum(static_missing_cache.values())
        if total_static > 0:
            print(
                f"   Browser Caching (1st-party static): {low_or_missing}/{total_static} "
                "resources have missing or <1 day max-age"
            )

        if low_ttl_resources:
            print("\n   1st-party static resources with TTL < 1 day:")
            print(f"   {'Type':<8} {'TTL(s)':>8}  URL (domain/.../resource)")
            print(f"   {'-'*8} {'-'*8}  {'-'*60}")
            for item in sorted(low_ttl_resources, key=lambda x: x['ttl_seconds'])[:40]:
                url_display = self.format_url_display(item['url'])
                print(f"   {item['type']:<8} {item['ttl_seconds']:>8}  {url_display}")

        if low_or_missing > 0:
            self.results['recommendations'].append({
                'category': 'Caching',
                'severity': 'HIGH',
                'issue': (
                    f'{low_or_missing} first-party static resource(s) (CSS/JS/fonts/images) '
                    'have missing or <1 day cache lifetime'
                ),
                'recommendation': (
                    'Use asset versioning/fingerprinting (hashed filenames) and increase downstream '
                    'browser/CDN cache duration (e.g., max-age >= 86400, ideally 1 year for immutable assets).'
                )
            })
    
    def check_dns_ttl(self):
        """Check DNS TTL values, prioritizing first-level CNAME when present."""
        try:
            record_type = 'A'
            cname_target = None

            # Prefer the first-level CNAME TTL (e.g. www -> edgekey) when present.
            try:
                cname_answers = dns.resolver.resolve(self.domain, 'CNAME')
                first_cname = next(iter(cname_answers), None)
                if first_cname is not None:
                    cname_target = str(first_cname.target).rstrip('.')
                    record_type = 'CNAME'
            except Exception:
                pass

            ttl, details = self._get_authoritative_ttl(record_type, query_name=self.domain)

            # Keep compatibility with existing report consumers.
            self.results['technical_checks']['dns_ttl'] = ttl
            self.results['technical_checks']['dns_ttl_details'] = details
            self.results['technical_checks']['dns_ttl_record_type'] = record_type
            if cname_target:
                self.results['technical_checks']['dns_first_cname_target'] = cname_target

            source = details.get('source')
            if source == 'authoritative':
                print(f"   DNS TTL ({record_type}, authoritative): {ttl}s")
                if cname_target:
                    print(f"   First CNAME hop: {self.domain} -> {cname_target}")
                if len(details.get('nameserver_ttls', {})) > 1:
                    print(f"   Authoritative NS TTLs: {details['nameserver_ttls']}")
            elif source == 'doh_recursive_estimate':
                print(f"   DNS TTL ({record_type}, External DNS recursive estimate): {ttl}s")
                if cname_target:
                    print(f"   First CNAME hop: {self.domain} -> {cname_target}")
            else:
                print(
                    f"   DNS TTL ({record_type}, resolver fallback): {ttl}s "
                    "⚠️  Could be from cached recursive response"
                )
            
            if ttl < 300:
                status = "❌ Too low"
                self.results['recommendations'].append({
                    'category': 'DNS',
                    'issue': f'DNS TTL is very low ({ttl}s)',
                    'recommendation': 'Increase DNS TTL to at least 3600s (1 hour) for better caching at resolvers and clients'
                })
            elif ttl < 3600:
                status = "⚠️  Could be higher"
            else:
                status = "✅ Good"
            
            print(f"   DNS TTL assessment: {ttl}s {status}")
            
        except Exception as e:
            print(f"   ❌ DNS TTL check failed: {str(e)}")
            self.results['technical_checks']['dns_ttl'] = None

    def _get_authoritative_ttl(self, record_type='A', query_name=None):
        """Return TTL from authoritative name servers, bypassing recursive cache."""
        from collections import Counter

        target_name = (query_name or self.domain).rstrip('.')

        details = {
            'source': 'authoritative',
            'zone': None,
            'nameservers': [],
            'nameserver_ttls': {},
            'ttl_mismatch': False,
            'query_name': target_name,
        }

        try:
            zone_text = self._find_authoritative_zone(target_name)
            details['zone'] = zone_text

            ns_answers = dns.resolver.resolve(zone_text, 'NS')
            ns_hosts = [str(rdata.target).rstrip('.') for rdata in ns_answers]
            details['nameservers'] = ns_hosts

            ttl_values = []

            for ns_host in ns_hosts:
                try:
                    ns_ips = self._resolve_nameserver_ips(ns_host)
                    if not ns_ips:
                        continue

                    for ns_ip in ns_ips:
                        query = dns.message.make_query(target_name, record_type)
                        query.flags &= ~dns.flags.RD
                        try:
                            response = dns.query.udp(query, ns_ip, timeout=4)
                        except Exception:
                            # Some authoritative NS are stricter on UDP; retry over TCP.
                            response = dns.query.tcp(query, ns_ip, timeout=4)
                        if bool(response.flags & dns.flags.TC):
                            # Retry over TCP when UDP response is truncated.
                            response = dns.query.tcp(query, ns_ip, timeout=4)

                        # Only accept authoritative responses from the target NS.
                        if not bool(response.flags & dns.flags.AA):
                            continue

                        ttl = self._extract_ttl_from_answer(response, record_type, target_name)
                        if ttl is not None:
                            ttl_values.append(ttl)
                            details['nameserver_ttls'][ns_host] = ttl
                            break
                except Exception:
                    continue

            if ttl_values:
                if len(set(ttl_values)) > 1:
                    details['ttl_mismatch'] = True
                # Use consensus TTL (most common across authoritative NS),
                # not the minimum, to avoid single-node outlier skew.
                ttl_counter = Counter(ttl_values)
                selected_ttl = sorted(ttl_counter.items(), key=lambda item: (-item[1], -item[0]))[0][0]
                details['selected_ttl'] = selected_ttl
                details['selection_strategy'] = 'most_common_authoritative_ttl'
                return selected_ttl, details

            # Fallback path using local dig against discovered NS (@ns), similar to DigWebInterface.
            dig_ttl, dig_ns, dig_authoritative = self._get_ttl_via_dig_cli(
                record_type=record_type,
                query_name=target_name,
                nameservers=ns_hosts,
            )
            if dig_ttl is not None and dig_authoritative:
                details['source'] = 'authoritative'
                details['nameserver_ttls'] = {dig_ns: dig_ttl} if dig_ns else {}
                details['selected_ttl'] = dig_ttl
                details['selection_strategy'] = 'dig_cli_authoritative_ns'
                return dig_ttl, details

            # Try DigWebInterface (web-based DNS query service) to bypass local interception.
            dig_web_ttl, dig_web_details = self._get_ttl_via_digwebinterface(
                record_type=record_type,
                query_name=target_name,
                nameservers=ns_hosts,
            )
            if dig_web_ttl is not None:
                details['source'] = 'digwebinterface'
                details['nameserver_ttls'] = {}
                details['selected_ttl'] = dig_web_ttl
                details['selection_strategy'] = 'digwebinterface_web_query'
                details['digwebinterface_details'] = dig_web_details
                return dig_web_ttl, details

            # If local DNS is intercepted, use external DNS-over-HTTPS recursive estimates.
            doh_ttl, doh_details = self._get_ttl_via_doh_resolvers(
                record_type=record_type,
                query_name=target_name,
            )
            if doh_ttl is not None:
                details['source'] = 'doh_recursive_estimate'
                details['nameserver_ttls'] = {}
                details['selected_ttl'] = doh_ttl
                details['selection_strategy'] = 'doh_max_ttl_estimate'
                details['doh_resolvers'] = doh_details
                return doh_ttl, details
        except Exception:
            pass

        # Fallback to resolver behavior if authoritative queries are unavailable.
        answers = dns.resolver.resolve(target_name, record_type)
        details['source'] = 'resolver_fallback'
        details['nameserver_ttls'] = {}
        details['ttl_mismatch'] = False
        return answers.rrset.ttl, details

    def _get_ttl_via_dig_cli(self, record_type, query_name, nameservers):
        """Use local dig @nameserver queries to fetch TTL directly from authoritative NS."""
        dig_path = shutil.which('dig')
        if not dig_path or not nameservers:
            return None, None, False

        target = query_name.rstrip('.') + '.'
        wanted_type = (record_type or '').upper()

        for ns in nameservers:
            try:
                result = subprocess.run(
                    [
                        dig_path,
                        '+time=4',
                        '+tries=1',
                        '+nocmd',
                        '+noquestion',
                        '+nostats',
                        '+noauthority',
                        target,
                        wanted_type,
                        f'@{ns}',
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    continue

                # Accept dig response as authoritative only when AA flag is present.
                dig_is_authoritative = False
                for line in result.stdout.splitlines():
                    line = line.strip().lower()
                    if 'flags:' in line:
                        dig_is_authoritative = ' aa' in line or ' aa;' in line
                        break

                best_effort_ttl = None
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line or line.startswith(';'):
                        continue

                    parts = line.split()
                    if len(parts) < 5:
                        continue

                    name, ttl_text, _dns_class, rr_type = parts[0], parts[1], parts[2], parts[3]
                    try:
                        ttl_val = int(ttl_text)
                    except ValueError:
                        continue

                    # First line TTL is a useful fallback in alias chains.
                    if best_effort_ttl is None:
                        best_effort_ttl = ttl_val

                    if rr_type.upper() == wanted_type and name.rstrip('.') == query_name.rstrip('.'):
                        return ttl_val, ns, dig_is_authoritative

                if best_effort_ttl is not None:
                    return best_effort_ttl, ns, dig_is_authoritative
            except Exception:
                continue

        return None, None, False

    def _get_ttl_via_digwebinterface(self, record_type, query_name, nameservers):
        """Query DNS using DigWebInterface web service to bypass local interception."""
        if not nameservers:
            return None, {}

        wanted_type = (record_type or 'A').upper()
        
        for ns in nameservers:
            try:
                # DigWebInterface URL: https://digwebinterface.com/?host=<domain>&type=<type>&nameserver=<ns>
                url = 'https://digwebinterface.com/'
                params = {
                    'host': query_name.rstrip('.'),
                    'type': wanted_type,
                    'nameserver': ns,
                    'edns': 'on',
                }
                
                resp = requests.get(url, params=params, timeout=8)
                if resp.status_code != 200:
                    continue
                
                html = resp.text.lower()
                
                # Look for TTL value in the response HTML.
                # DigWebInterface typically shows "TTL = <value>" or similar format.
                import re
                
                # Try to find TTL patterns in the response.
                ttl_patterns = [
                    r'ttl\s*[=:]\s*(\d+)',
                    r'ttl\s+(\d+)',
                    r'(\d+)\s+(?:in|internet)',
                ]
                
                for pattern in ttl_patterns:
                    matches = re.findall(pattern, html)
                    if matches:
                        try:
                            ttl_val = int(matches[0])
                            if ttl_val > 0:
                                return ttl_val, {'nameserver': ns, 'response_url': resp.url}
                        except (ValueError, IndexError):
                            continue
                
            except Exception:
                continue
        
        return None, {}

    def _get_ttl_via_doh_resolvers(self, record_type, query_name):
        """Get DNS TTL estimate from public DoH resolvers when local DNS is intercepted."""
        resolvers = [
            ('google', 'https://dns.google/resolve'),
            ('quad9', 'https://dns.quad9.net/dns-query'),
        ]

        wanted_type = (record_type or 'A').upper()
        ttl_samples = []
        details = {}

        for resolver_name, endpoint in resolvers:
            try:
                headers = {'accept': 'application/dns-json'}
                params = {
                    'name': query_name,
                    'type': wanted_type,
                    'cd': '1',
                    'do': '1',
                    'edns_client_subnet': '0.0.0.0/0',
                }
                resp = requests.get(endpoint, params=params, headers=headers, timeout=6)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                answers = data.get('Answer') or []
                if not answers:
                    continue

                candidate_ttl = None
                for answer in answers:
                    ttl_val = answer.get('TTL')
                    ans_type = answer.get('type')
                    if ttl_val is None:
                        continue
                    try:
                        ttl_int = int(ttl_val)
                    except (TypeError, ValueError):
                        continue

                    if candidate_ttl is None:
                        candidate_ttl = ttl_int
                    if wanted_type == 'A' and ans_type == 1:
                        candidate_ttl = ttl_int
                        break
                    if wanted_type == 'CNAME' and ans_type == 5:
                        candidate_ttl = ttl_int
                        break

                if candidate_ttl is not None:
                    ttl_samples.append(candidate_ttl)
                    details[resolver_name] = {
                        'ttl': candidate_ttl,
                        'status': data.get('Status'),
                    }
            except Exception:
                continue

        if not ttl_samples:
            return None, {}

        # Use the maximum observed TTL to approximate configured policy TTL.
        return max(ttl_samples), details

    def _find_authoritative_zone(self, hostname):
        """Find the closest delegated DNS zone for a hostname."""
        hostname = hostname.rstrip('.')

        # Prefer SOA-derived zone: resolver returns SOA at authoritative zone apex.
        try:
            soa_answers = dns.resolver.resolve(hostname, 'SOA')
            soa_zone = str(soa_answers.rrset.name).rstrip('.')
            if soa_zone:
                return soa_zone
        except Exception:
            pass

        labels = hostname.split('.')
        for index in range(len(labels) - 1):
            candidate = '.'.join(labels[index:])
            # Skip bare TLD candidates such as "com" or "net".
            if '.' not in candidate:
                continue
            try:
                soa_answers = dns.resolver.resolve(candidate, 'SOA')
                soa_zone = str(soa_answers.rrset.name).rstrip('.')
                if soa_zone:
                    return soa_zone
            except Exception:
                continue

        zone_name = dns.resolver.zone_for_name(hostname)
        return str(zone_name).rstrip('.')

    def _resolve_nameserver_ips(self, ns_host):
        """Resolve nameserver hostname to all reachable IP addresses."""
        ips = []

        try:
            a_answers = dns.resolver.resolve(ns_host, 'A')
            for rdata in a_answers:
                ips.append(str(rdata))
        except Exception:
            pass

        try:
            aaaa_answers = dns.resolver.resolve(ns_host, 'AAAA')
            for rdata in aaaa_answers:
                ips.append(str(rdata))
        except Exception:
            pass

        # Preserve order while removing duplicates.
        unique_ips = []
        for ip in ips:
            if ip not in unique_ips:
                unique_ips.append(ip)
        return unique_ips

    def _extract_ttl_from_answer(self, response, record_type, query_name):
        """Extract TTL for the requested record type from a DNS response."""
        requested_type = dns.rdatatype.from_text(record_type)
        target_name = query_name.rstrip('.')

        for rrset in response.answer:
            if rrset.rdtype == requested_type and str(rrset.name).rstrip('.') == target_name:
                return rrset.ttl

        # CNAME or other aliasing cases: use the first answer TTL as best effort.
        if response.answer:
            return response.answer[0].ttl

        return None
    
    def check_ipv6_support(self):
        """Check if domain responds to IPv6"""
        try:
            answers = dns.resolver.resolve(self.domain, 'AAAA')
            ipv6_addresses = [str(rdata) for rdata in answers]
            
            self.results['technical_checks']['ipv6_support'] = True
            self.results['technical_checks']['ipv6_addresses'] = ipv6_addresses
            
            print(f"   IPv6 Support: ✅ Yes ({len(ipv6_addresses)} addresses)")
            
        except dns.resolver.NoAnswer:
            print("   IPv6 Support: ❌ No")
            self.results['technical_checks']['ipv6_support'] = False
            self.results['recommendations'].append({
                'category': 'Network',
                'issue': 'No IPv6 support detected',
                'recommendation': 'Enable IPv6 for improved performance, especially for mobile devices'
            })
        except Exception as e:
            print(f"   IPv6 check failed: {str(e)}")
            self.results['technical_checks']['ipv6_support'] = None
    
    def check_http_headers(self):
        """Analyze HTTP response headers"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Encoding': 'gzip, deflate, br'
            }
            
            response = requests.get(self.url, headers=headers, timeout=15, allow_redirects=True)
            
            # Store response for later analysis
            self.response = response
            
            # Check compression
            content_encoding = response.headers.get('content-encoding', '').lower()
            if 'br' in content_encoding:
                print("   Compression: ✅ Brotli")
                self.results['technical_checks']['compression'] = 'brotli'
            elif 'gzip' in content_encoding:
                print("   Compression: ⚠️  Gzip (consider Brotli)")
                self.results['technical_checks']['compression'] = 'gzip'
                self.results['recommendations'].append({
                    'category': 'Compression',
                    'issue': 'Using Gzip instead of Brotli',
                    'recommendation': 'Enable Brotli compression for ~20% better compression than Gzip'
                })
            else:
                print("   Compression: ❌ None detected")
                self.results['technical_checks']['compression'] = None
                self.results['recommendations'].append({
                    'category': 'Compression',
                    'issue': 'No compression detected',
                    'recommendation': 'Enable Brotli or at least Gzip compression to reduce transfer sizes'
                })
            
            # Check caching
            cache_control = response.headers.get('cache-control', '')
            self.results['technical_checks']['cache_control'] = cache_control
            
            if 'max-age' in cache_control.lower():
                import re
                match = re.search(r'max-age=(\d+)', cache_control.lower())
                if match:
                    max_age = int(match.group(1))
                    days = max_age / 86400
                    
                    if max_age < 3600:
                        status = "❌ Too short"
                        self.results['recommendations'].append({
                            'category': 'Caching',
                            'issue': f'Cache max-age is very short ({max_age}s)',
                            'recommendation': 'Increase cache duration for static assets to at least 1 year (31536000s)'
                        })
                    elif max_age < 86400:
                        status = "⚠️  Could be longer"
                    else:
                        status = f"✅ Good ({days:.1f} days)"
                    
                    print(f"   Browser Caching: {status}")
            else:
                print("   Browser Caching: ❌ No max-age set")
                self.results['recommendations'].append({
                    'category': 'Caching',
                    'issue': 'No cache-control max-age header',
                    'recommendation': 'Set appropriate cache-control headers with max-age for static resources'
                })
            
            # Check HTTP version
            http_version = 'HTTP/2' if response.raw.version == 20 else 'HTTP/3' if response.raw.version == 30 else 'HTTP/1.1'
            self.results['technical_checks']['http_version'] = http_version
            
            if 'HTTP/3' in http_version or 'HTTP/2' in http_version:
                print(f"   HTTP Protocol: ✅ {http_version}")
            else:
                print(f"   HTTP Protocol: ❌ {http_version}")
                self.results['recommendations'].append({
                    'category': 'Protocol',
                    'issue': f'Using {http_version}',
                    'recommendation': 'Enable HTTP/2 or HTTP/3 for multiplexing and better performance'
                })
            
            # Check 103 Early Hints
            # Note: This is hard to detect from a simple request
            early_hints = 'link' in response.headers
            if early_hints:
                print("   103 Early Hints: ✅ Detected (Link headers)")
            else:
                print("   103 Early Hints: ℹ️  Not detected")
            
            self.results['technical_checks']['early_hints'] = early_hints
            
        except Exception as e:
            print(f"   ❌ HTTP header analysis failed: {str(e)}")
    
    def detect_cdn(self):
        """Detect CDN usage"""
        cdn_headers = {
            'cf-ray': 'Cloudflare',
            'x-amz-cf-id': 'Amazon CloudFront',
            'x-cache': 'Various CDNs',
            'x-fastly-request-id': 'Fastly',
            'x-akamai-request-id': 'Akamai',
            'server': 'cloudflare'
        }
        
        detected_cdns = []
        
        if hasattr(self, 'response'):
            for header, cdn_name in cdn_headers.items():
                if header in self.response.headers:
                    if cdn_name not in detected_cdns:
                        detected_cdns.append(cdn_name)
            
            # Check server header specifically
            server = self.response.headers.get('server', '').lower()
            if 'cloudflare' in server:
                detected_cdns.append('Cloudflare')
            elif 'akamai' in server:
                detected_cdns.append('Akamai')
        
        if detected_cdns:
            print(f"   CDN: ✅ {', '.join(set(detected_cdns))}")
            self.results['technical_checks']['cdn'] = list(set(detected_cdns))
        else:
            print("   CDN: ⚠️  Not detected")
            self.results['technical_checks']['cdn'] = None
            self.results['recommendations'].append({
                'category': 'CDN',
                'issue': 'No CDN detected',
                'recommendation': 'Consider using a CDN to reduce latency and improve global performance'
            })
    
    def fetch_and_parse_html(self):
        """Fetch and parse HTML content"""
        try:
            if self.use_browser:
                self._report_progress("Launching headless browser...")
                print("   🌐 Using headless browser to render JavaScript...")
                self.fetch_with_browser()
            else:
                self._report_progress("Fetching static HTML...")
                print("   📄 Fetching static HTML...")
                self.fetch_static()
            
            # Store final URL after redirects
            self.final_domain = urlparse(self.final_url).netloc
            
            # Get base domain for first-party detection
            self.base_domain = self.get_base_domain(self.final_domain)
            
            print(f"   ✅ HTML fetched ({len(self.html)} bytes)")
            print(f"   📍 Final URL: {self.final_url}")
            print(f"   🏠 Base domain: {self.base_domain}")
            
        except Exception as e:
            print(f"   ❌ Failed to fetch HTML: {str(e)}")
            self.html = ""
            self.soup = None
    
    def fetch_static(self):
        """Fetch static HTML without JavaScript rendering"""
        self._report_progress("Downloading static HTML response...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Encoding': 'gzip, deflate, br'
        }
        
        self.response = requests.get(self.url, headers=headers, timeout=15, allow_redirects=True)
        self.html = self.response.text
        self.soup = BeautifulSoup(self.html, 'html.parser')
        self.final_url = self.response.url
    
    def fetch_with_browser(self):
        """Fetch HTML using headless browser to execute JavaScript"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import time
        except ImportError:
            print("   ⚠️  Selenium not installed. Install with: pip install selenium")
            print("   ⚠️  Falling back to static HTML fetch...")
            self.fetch_static()
            return
        
        driver = None
        try:
            # Setup Chrome options
            self._report_progress("Configuring browser driver...")
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')  # New headless mode
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
            # Try to initialize Chrome driver
            try:
                driver = webdriver.Chrome(options=chrome_options)
                try:
                    driver.set_page_load_timeout(60)
                except Exception:
                    pass
                try:
                    driver.execute_cdp_cmd('Network.enable', {})
                except Exception:
                    pass
            except Exception as e:
                # Try Firefox as fallback
                self._report_progress("Chrome unavailable, falling back to Firefox...")
                print(f"   ⚠️  Chrome failed ({str(e)}), trying Firefox...")
                from selenium.webdriver.firefox.options import Options as FirefoxOptions
                firefox_options = FirefoxOptions()
                firefox_options.add_argument('--headless')
                driver = webdriver.Firefox(options=firefox_options)
                try:
                    driver.set_page_load_timeout(60)
                except Exception:
                    pass
            
            # Navigate to URL
            self._report_progress("Opening page in browser...")
            driver.get(self.url)
            
            # Wait for page to load and JavaScript to execute
            self._report_progress("Waiting for JavaScript execution...")
            time.sleep(3)  # Give JavaScript time to execute
            
            # Try to wait for images to load
            try:
                self._report_progress("Waiting for initial page content...")
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "img"))
                )
            except:
                pass  # Continue even if no images found
            
            # Scroll to trigger lazy loading
            self._report_progress("Scrolling page to trigger lazy-loaded resources...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Get the rendered HTML
            self._report_progress("Collecting rendered HTML and browser timing data...")
            self.html = driver.page_source
            self.final_url = driver.current_url
            self.soup = BeautifulSoup(self.html, 'html.parser')

            # Capture LCP resource from browser timing APIs.
            self._capture_lcp_resource(driver)

            # Capture render-blocking resources from Chrome Performance API (Chrome 107+).
            self._capture_render_blocking_from_performance_api(driver)

            # Capture network protocol data from Chrome DevTools if available.
            self._capture_browser_protocols(driver)
            
            # Get response headers by making a HEAD request
            self._report_progress("Fetching final response headers...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Encoding': 'gzip, deflate, br'
            }
            self.response = requests.get(self.final_url, headers=headers, timeout=15, allow_redirects=True)
            
            print(f"   ✅ JavaScript rendered successfully")
            
        except Exception as e:
            print(f"   ❌ Browser rendering failed: {str(e)}")
            print(f"   ℹ️  Falling back to static HTML fetch...")
            self.fetch_static()
        finally:
            if driver:
                driver.quit()
    
    def get_base_domain(self, domain):
        """Return the registered domain (eTLD+1), handling multi-part TLDs."""
        # Known two-part TLDs requiring three labels for the registered domain.
        multi_part_tlds = {
            'com.au', 'net.au', 'org.au', 'gov.au', 'edu.au', 'asn.au',
            'co.uk', 'org.uk', 'gov.uk', 'ac.uk', 'me.uk',
            'co.nz', 'org.nz', 'net.nz', 'govt.nz',
            'co.jp', 'co.in', 'org.in', 'net.in', 'gov.in',
            'com.br', 'com.sg', 'com.hk', 'com.mx', 'com.ar',
        }
        domain = domain.lower().rstrip('.')
        parts = domain.split('.')
        if len(parts) < 2:
            return domain
        if len(parts) >= 3:
            two_part_tld = f'{parts[-2]}.{parts[-1]}'
            if two_part_tld in multi_part_tlds:
                return '.'.join(parts[-3:])   # e.g. .com.au
        return '.'.join(parts[-2:])           # e.g. example.media

    def is_first_party(self, url):
        """
        Return True when the URL belongs to a first-party domain.

        First-party = any of:
          1. Same registered domain (eTLD+1) as the audited site — ALL subdomains
             are automatically included (e.g. chatwidget.example.com.au).
          2. A domain explicitly listed via --additional-first-party-domains
             (and any subdomain thereof) for owner-controlled domains on a
             different TLD (e.g. cdn0.example.media).
        """
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return True  # relative URL

            resource_domain = parsed.netloc.lower().split(':')[0]  # strip optional port

            # Rule 1: same registered domain as the audited site.
            if self.get_base_domain(resource_domain) == self.base_domain:
                return True

            # Rule 2: explicitly declared additional first-party domains.
            for extra in self.additional_first_party_domains:
                extra_registered = self.get_base_domain(extra)
                resource_registered = self.get_base_domain(resource_domain)
                if (resource_registered == extra_registered
                        or resource_domain == extra
                        or resource_domain.endswith('.' + extra)):
                    return True

            return False
        except Exception:
            return False

    def analyze_slow_resources(self):
        """Highlight slow resources (>800ms) from browser network timings."""
        if not (self.use_browser and self.browser_protocol_events):
            print("   ℹ️  Slow resource analysis requires browser mode with DevTools logs")
            self.results['technical_checks']['slow_resources'] = {
                'threshold_ms': 800,
                'source': 'not_available',
                'resources': []
            }
            return

        threshold_ms = 800

        critical_urls = set()
        head_blocking = self.results.get('technical_checks', {}).get('head_blocking', {})
        for item in head_blocking.get('scripts', []):
            url = item.get('url')
            if url:
                critical_urls.add(self._normalize_browser_url(url))
        for item in head_blocking.get('stylesheets', []):
            url = item.get('url')
            if url:
                critical_urls.add(self._normalize_browser_url(url))

        lcp_url = self._normalize_browser_url(self.lcp_resource_url) if self.lcp_resource_url else None

        slow_by_url = {}
        for event in self.browser_protocol_events:
            duration_ms = event.get('duration_ms')
            url = event.get('url')
            if not url or duration_ms is None or duration_ms <= threshold_ms:
                continue
            existing = slow_by_url.get(url)
            if existing is None or duration_ms > existing.get('duration_ms', 0):
                slow_by_url[url] = event

        slow_resources = []
        severity_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}

        for url, event in sorted(slow_by_url.items(), key=lambda item: item[1].get('duration_ms', 0), reverse=True):
            is_critical = url in critical_urls
            is_lcp = bool(lcp_url and url == lcp_url)

            if is_critical or is_lcp:
                severity = 'HIGH'
            elif self.is_first_party(url):
                severity = 'MEDIUM'
            else:
                severity = 'LOW'

            severity_counts[severity] += 1
            slow_resources.append({
                'url': url,
                'domain': event.get('domain'),
                'resource_type': event.get('resource_type', 'Other'),
                'duration_ms': event.get('duration_ms'),
                'first_party': self.is_first_party(url),
                'is_critical_css_js': is_critical,
                'is_lcp_resource': is_lcp,
                'severity': severity,
            })

            self.results['recommendations'].append({
                'category': 'Slow Resource',
                'severity': severity,
                'issue': (
                    f"{event.get('resource_type', 'Resource')} took {event.get('duration_ms')}ms: {url}"
                ),
                'recommendation': (
                    'Reduce response time by optimizing backend processing, CDN delivery, payload size, '
                    'and caching strategy for this resource.'
                )
            })

        self.results['technical_checks']['slow_resources'] = {
            'threshold_ms': threshold_ms,
            'source': 'chrome-devtools',
            'count': len(slow_resources),
            'severity_counts': severity_counts,
            'lcp_resource_url': lcp_url,
            'resources': slow_resources,
        }

        if slow_resources:
            print(
                f"   Slow resources > {threshold_ms}ms: {len(slow_resources)} "
                f"(HIGH: {severity_counts['HIGH']}, MEDIUM: {severity_counts['MEDIUM']}, LOW: {severity_counts['LOW']})"
            )
        else:
            print(f"   Slow resources > {threshold_ms}ms: ✅ none detected")

    def analyze_heavy_resources(self):
        """Highlight heavy resources (>200KB) from browser network timings."""
        if not (self.use_browser and self.browser_protocol_events):
            print("   ℹ️  Heavy resource analysis requires browser mode with DevTools logs")
            self.results['technical_checks']['heavy_resources'] = {
                'threshold_bytes': 204800,
                'source': 'not_available',
                'heavy_images': [],
                'heavy_resources': [],
            }
            return

        threshold_bytes = 200 * 1024
        seen_urls = set()
        heavy_images = []
        heavy_resources = []

        for event in self.browser_protocol_events:
            url = event.get('url')
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            size_bytes = event.get('transfer_size_bytes')
            if size_bytes is None or size_bytes <= threshold_bytes:
                continue

            resource_type = event.get('resource_type', 'Other')
            content_type = (event.get('content_type') or '').lower()
            record = {
                'url': url,
                'domain': event.get('domain'),
                'resource_type': resource_type,
                'content_type': content_type,
                'transfer_size_bytes': size_bytes,
                'transfer_size_kb': round(size_bytes / 1024, 1),
                'first_party': self.is_first_party(url),
            }

            is_image = resource_type == 'Image' or content_type.startswith('image/')
            if is_image:
                heavy_images.append(record)
            else:
                heavy_resources.append(record)

        heavy_images.sort(key=lambda x: x['transfer_size_bytes'], reverse=True)
        heavy_resources.sort(key=lambda x: x['transfer_size_bytes'], reverse=True)

        self.results['technical_checks']['heavy_resources'] = {
            'threshold_bytes': threshold_bytes,
            'source': 'chrome-devtools',
            'heavy_images': heavy_images,
            'heavy_resources': heavy_resources,
            'counts': {
                'heavy_images': len(heavy_images),
                'heavy_resources': len(heavy_resources),
            },
        }

        if heavy_images:
            print(f"   Heavy images > 200KB: {len(heavy_images)}")
            for item in heavy_images[:10]:
                url_display = self.format_url_display(item['url'], max_length=80)
                print(f"      🖼️  {item['transfer_size_kb']}KB - {url_display}")
            self.results['recommendations'].append({
                'category': 'Images',
                'severity': 'HIGH',
                'issue': f'{len(heavy_images)} image resource(s) larger than 200KB detected',
                'recommendation': 'Optimize heavy images using responsive sizing, stronger compression, and modern formats (WebP/AVIF) to reduce payload and improve LCP.'
            })
        else:
            print("   Heavy images > 200KB: ✅ none detected")

        if heavy_resources:
            print(f"   Other heavy resources > 200KB: {len(heavy_resources)}")
            for item in heavy_resources[:10]:
                url_display = self.format_url_display(item['url'], max_length=80)
                print(f"      📄 {item['resource_type']}: {item['transfer_size_kb']}KB - {url_display}")
            self.results['recommendations'].append({
                'category': 'Resource Weight',
                'severity': 'MEDIUM',
                'issue': f'{len(heavy_resources)} non-image resource(s) larger than 200KB detected',
                'recommendation': 'Reduce large resource payloads through code splitting, minification, compression, and caching strategy improvements.'
            })
        else:
            print("   Other heavy resources > 200KB: ✅ none detected")
    
    def detect_cdn_advanced(self):
        """Advanced CDN detection using DNS resolution and IP ownership lookup"""
        try:
            print(f"\n   Analyzing DNS for: {self.domain}")
            
            cdn_info = {
                'cdn_detected': None,
                'delivery_method': None,  # CNAME or A record (ZAM)
                'cname_chain': [],
                'final_ips': [],
                'ip_owner': None,
                'akamai_dns_ttl_check': 'not_applicable'
            }
            
            # Step 1: Check for CNAME records
            try:
                cname_answers = dns.resolver.resolve(self.domain, 'CNAME')
                cname_chain = [str(rdata.target).rstrip('.') for rdata in cname_answers]
                cdn_info['cname_chain'] = cname_chain
                cdn_info['delivery_method'] = 'CNAME'
                
                print(f"   📍 CNAME detected: {' -> '.join(cname_chain)}")
                
                # Check for CDN patterns in CNAME
                for cname in cname_chain:
                    cname_lower = cname.lower()
                    
                    # Akamai patterns
                    if 'edgekey.net' in cname_lower or 'edgesuite.net' in cname_lower or 'akamaiedge.net' in cname_lower:
                        cdn_info['cdn_detected'] = 'Akamai'
                        print(f"   ✅ CDN: Akamai (via CNAME: {cname})")

                        # Check TTL of the edge hostname
                        self.check_akamai_edge_ttl(cname)
                        cdn_info['akamai_dns_ttl_check'] = 'performed'
                        break
                    
                    # Cloudflare patterns
                    elif 'cloudflare' in cname_lower or cname_lower.endswith('.cdn.cloudflare.net'):
                        cdn_info['cdn_detected'] = 'Cloudflare'
                        print(f"   ✅ CDN: Cloudflare (via CNAME: {cname})")
                        break
                    
                    # Fastly patterns
                    elif 'fastly' in cname_lower or 'fastly.net' in cname_lower:
                        cdn_info['cdn_detected'] = 'Fastly'
                        print(f"   ✅ CDN: Fastly (via CNAME: {cname})")
                        break
                    
                    # CloudFront patterns
                    elif 'cloudfront.net' in cname_lower:
                        cdn_info['cdn_detected'] = 'Amazon CloudFront'
                        print(f"   ✅ CDN: Amazon CloudFront (via CNAME: {cname})")
                        break
                    
                    # Cloudinary
                    elif 'cloudinary' in cname_lower:
                        cdn_info['cdn_detected'] = 'Cloudinary'
                        print(f"   ✅ CDN: Cloudinary (via CNAME: {cname})")
                        break
                    
                    # Azure CDN
                    elif 'azureedge.net' in cname_lower:
                        cdn_info['cdn_detected'] = 'Azure CDN'
                        print(f"   ✅ CDN: Azure CDN (via CNAME: {cname})")
                        break
                
            except dns.resolver.NoAnswer:
                cdn_info['delivery_method'] = 'A record (possibly ZAM/Direct)'
                print(f"   📍 No CNAME - using A record (Direct IP / ZAM)")
            except dns.resolver.NXDOMAIN:
                print(f"   ❌ Domain does not exist")
                return
            except Exception as e:
                print(f"   ⚠️  CNAME lookup failed: {str(e)}")
            
            # Step 2: Get A records (final IPs)
            try:
                a_answers = dns.resolver.resolve(self.domain, 'A')
                ips = [str(rdata) for rdata in a_answers]
                cdn_info['final_ips'] = ips
                
                print(f"   🌐 IP Addresses: {', '.join(ips)}")
                
                # Step 3: If CDN not detected via CNAME, check IP ownership
                if not cdn_info['cdn_detected'] and ips:
                    ip_owner = self.check_ip_ownership(ips[0])
                    cdn_info['ip_owner'] = ip_owner
                    
                    if ip_owner:
                        # Check if IP owner indicates a CDN
                        owner_lower = ip_owner.lower()
                        
                        if 'akamai' in owner_lower:
                            cdn_info['cdn_detected'] = 'Akamai (Zone Apex Mapping)'
                            cdn_info['delivery_method'] = 'A record (Zone Apex Mapping)'
                            cdn_info['akamai_dns_ttl_check'] = 'skipped_zone_apex_mapping'
                            print(f"   ✅ CDN: Akamai - Zone Apex Mapping (direct A record)")
                            print(f"   ℹ️  IP Owner: {ip_owner}")
                            print("   ℹ️  Skipping DNS - Akamai CNAME TTL check for Zone Apex Mapping")
                        elif 'cloudflare' in owner_lower:
                            cdn_info['cdn_detected'] = 'Cloudflare'
                            print(f"   ✅ CDN: Cloudflare")
                            print(f"   ℹ️  IP Owner: {ip_owner}")
                        elif 'fastly' in owner_lower:
                            cdn_info['cdn_detected'] = 'Fastly'
                            print(f"   ✅ CDN: Fastly")
                            print(f"   ℹ️  IP Owner: {ip_owner}")
                        elif 'amazon' in owner_lower or 'aws' in owner_lower:
                            cdn_info['cdn_detected'] = 'Amazon CloudFront / AWS'
                            print(f"   ✅ CDN: Amazon CloudFront / AWS")
                            print(f"   ℹ️  IP Owner: {ip_owner}")
                        else:
                            print(f"   ℹ️  IP Owner: {ip_owner}")
                            print(f"   ⚠️  No well-known CDN detected")
                
            except Exception as e:
                print(f"   ⚠️  A record lookup failed: {str(e)}")
            
            # Store results
            self.results['technical_checks']['cdn'] = cdn_info
            
            # Add recommendation if no CDN detected
            if not cdn_info['cdn_detected']:
                self.results['recommendations'].append({
                    'category': 'CDN',
                    'severity': 'HIGH',
                    'issue': 'No CDN detected',
                    'recommendation': 'Consider using a CDN (Akamai, Cloudflare, Fastly, etc.) to reduce latency, improve global performance, and increase reliability'
                })
            
        except Exception as e:
            print(f"   ❌ CDN detection failed: {str(e)}")
            self.results['technical_checks']['cdn'] = {'error': str(e)}
    
    def check_akamai_edge_ttl(self, edge_hostname):
        """Check Akamai edge CNAME TTL from authoritative nameservers."""
        try:
            # Prefer CNAME TTL for the Akamai edge hostname (e.g. edgekey -> akamaiedge),
            # since that is the policy TTL the user typically wants to audit.
            ttl, details = self._get_authoritative_ttl('CNAME', query_name=edge_hostname)
            record_type = 'CNAME'

            # Some hostnames may not have a CNAME at this stage; fallback to A TTL.
            if details.get('source') == 'resolver_fallback' and not details.get('nameservers'):
                ttl, details = self._get_authoritative_ttl('A', query_name=edge_hostname)
                record_type = 'A'

            ttl_hours = ttl / 3600

            source = details.get('source', 'unknown')
            if source == 'authoritative':
                source_label = 'authoritative'
            elif source == 'doh_recursive_estimate':
                source_label = 'External DNS recursive estimate'
            else:
                source_label = 'resolver fallback'

            # Persist edge-hostname TTL details so follow-up Q&A can answer
            # hostname vs edge-hostname TTL questions deterministically.
            self.results['technical_checks']['edge_hostname_ttl'] = ttl
            self.results['technical_checks']['edge_hostname_ttl_record_type'] = record_type
            self.results['technical_checks']['edge_hostname'] = edge_hostname
            self.results['technical_checks']['edge_hostname_ttl_source'] = source_label
            print(
                f"   🕐 Akamai Edge Hostname {record_type} TTL ({source_label}): "
                f"{ttl}s ({ttl_hours:.1f} hours)"
            )

            # Low CDN edge TTLs can be intentional; only flag very low values for review.
            if ttl < 60:
                self.results['recommendations'].append({
                    'category': 'DNS - Akamai',
                    'severity': 'LOW',
                    'issue': (
                        f'Akamai edge hostname ({edge_hostname}) has very low '
                        f'authoritative {record_type} TTL: {ttl}s'
                    ),
                    'recommendation': 'Verify this low edge TTL is intentional for traffic steering or failover behavior'
                })
                print("   ⚠️  Very low edge TTL observed; verify this is intentional")
            else:
                print("   ✅ Edge TTL appears reasonable for CDN behavior")
                
        except Exception as e:
            print(f"   ⚠️  Could not check edge hostname TTL: {str(e)}")
    
    def check_ip_ownership(self, ip):
        """Check IP ownership using ip-api.com (free, no key required)"""
        try:
            # Using ip-api.com - free tier allows 45 requests per minute
            response = requests.get(f'http://ip-api.com/json/{ip}', timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    org = data.get('org', 'Unknown')
                    isp = data.get('isp', 'Unknown')
                    
                    # Prefer org over isp as it's usually more specific
                    owner = org if org != 'Unknown' else isp
                    return owner
            
            # Fallback: try ipinfo.io (also free, no key needed for basic info)
            response = requests.get(f'https://ipinfo.io/{ip}/json', timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('org', 'Unknown')
                
        except Exception as e:
            print(f"   ⚠️  IP ownership lookup failed: {str(e)}")
        
        return None
    
    def detect_cdn_from_headers(self):
        """Detect CDN from HTTP headers (fallback method)"""
        cdn_headers = {
            'cf-ray': 'Cloudflare',
            'x-amz-cf-id': 'Amazon CloudFront',
            'x-fastly-request-id': 'Fastly',
            'x-akamai-request-id': 'Akamai',
        }
        
        detected = set()
        
        for header, cdn_name in cdn_headers.items():
            if header in self.response.headers:
                detected.add(cdn_name)
        
        # Check server header
        server = self.response.headers.get('server', '').lower()
        if 'cloudflare' in server:
            detected.add('Cloudflare')
        elif 'akamai' in server:
            detected.add('Akamai')
        
        return detected
    
    def check_first_party_compression(self):
        """Check compression for all first-party HTML/CSS/JS resources >= 2KB."""
        if not self.soup:
            print("   ⚠️  Cannot check - HTML not parsed")
            return

        MIN_SIZE_BYTES = 2048  # resources smaller than 2KB are not worth compressing

        req_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Encoding': 'gzip, deflate, br'
        }

        # Collect candidate resources.
        candidates = []

        # HTML document itself.
        candidates.append(('HTML', self.final_url))

        # CSS.
        for tag in self.soup.find_all('link', rel='stylesheet'):
            href = tag.get('href', '')
            if href:
                full_url = urljoin(self.final_url, href)
                if self.is_first_party(full_url):
                    candidates.append(('CSS', full_url))

        # JS.
        for tag in self.soup.find_all('script', src=True):
            src = tag.get('src', '')
            if src:
                full_url = urljoin(self.final_url, src)
                if self.is_first_party(full_url):
                    candidates.append(('JS', full_url))

        print(f"\n   Found {len(candidates)} first-party HTML/CSS/JS resources to check")

        # counters per type per compression bucket
        from collections import defaultdict
        # buckets: 'br', 'gzip', 'none', 'skipped_small'
        counts = defaultdict(lambda: defaultdict(int))   # counts[type][bucket]
        sizes  = defaultdict(lambda: defaultdict(int))   # compressed sizes
        results = []

        for resource_type, url in candidates:
            try:
                resp = requests.get(url, headers=req_headers, timeout=10)
                size_bytes = len(resp.content)
                content_encoding = resp.headers.get('content-encoding', '').lower()

                if 'br' in content_encoding:
                    bucket = 'br'
                elif 'gzip' in content_encoding or 'deflate' in content_encoding:
                    bucket = 'gzip'
                else:
                    bucket = 'none'

                # Skip tiny resources from recommendation logic but still record them.
                if size_bytes < MIN_SIZE_BYTES and bucket == 'none':
                    effective_bucket = 'skipped_small'
                else:
                    effective_bucket = bucket

                counts[resource_type][effective_bucket] += 1
                sizes[resource_type][effective_bucket] += size_bytes

                results.append({
                    'type': resource_type,
                    'url': url,
                    'compression': bucket,
                    'size_bytes': size_bytes,
                    'skipped_small': size_bytes < MIN_SIZE_BYTES and bucket == 'none'
                })

            except Exception as e:
                url_display = self.format_url_display(url, max_length=70)
                print(f"   ⚠️  Failed to check {url_display} — {e}")

        self.results['technical_checks']['first_party_compression'] = results
        self.results['technical_checks']['first_party_compression_summary'] = {
            rtype: dict(buckets) for rtype, buckets in counts.items()
        }

        # --- Print summary table ---
        types_seen = [t for t in ['HTML', 'CSS', 'JS'] if t in counts]
        if types_seen:
            col_w = 12
            header = f"   {'Type':<6}  {'Brotli':>{col_w}}  {'Gzip':>{col_w}}  {'Uncompressed':>{col_w}}  {'<2KB(skip)':>{col_w}}"
            print(f"\n{header}")
            print(f"   {'-'*6}  {'-'*col_w}  {'-'*col_w}  {'-'*col_w}  {'-'*col_w}")
            for t in types_seen:
                b = counts[t]
                print(
                    f"   {t:<6}  "
                    f"{b['br']:>{col_w}}  "
                    f"{b['gzip']:>{col_w}}  "
                    f"{b['none']:>{col_w}}  "
                    f"{b['skipped_small']:>{col_w}}"
                )

        # --- Recommendations ---
        # Aggregate across all types, ignoring skipped_small.
        total_br   = sum(counts[t]['br']   for t in types_seen)
        total_gzip = sum(counts[t]['gzip'] for t in types_seen)
        total_none = sum(counts[t]['none'] for t in types_seen)
        total_significant = total_br + total_gzip + total_none

        if total_significant == 0:
            return

        none_size = sum(sizes[t]['none'] for t in types_seen)

        # Uncompressed resources that are large enough to matter.
        if total_none > 0:
            self.results['recommendations'].append({
                'category': 'Compression',
                'severity': 'HIGH',
                'issue': (
                    f'{total_none} first-party resource(s) served without compression '
                    f'({none_size / 1024:.1f} KB uncompressed)'
                ),
                'recommendation': (
                    'Enable Brotli (preferred) or Gzip compression for all first-party '
                    'HTML/CSS/JS resources. Brotli typically reduces transfer size by '
                    '60–80% and is supported by all modern browsers.'
                )
            })

        # If Brotli is absent but Gzip is dominant, recommend upgrading.
        elif total_gzip > 0 and total_br == 0:
            self.results['recommendations'].append({
                'category': 'Compression',
                'severity': 'MEDIUM',
                'issue': (
                    f'All {total_gzip} compressed first-party resource(s) use Gzip; '
                    'Brotli is not enabled'
                ),
                'recommendation': (
                    'Enable Brotli compression alongside Gzip. Brotli provides ~20% '
                    'better compression than Gzip for text resources and is supported '
                    'by all modern browsers.'
                )
            })

        # Mixed: some Gzip, some Brotli — flag Gzip-only ones as informational.
        elif total_gzip > 0 and total_br > 0:
            gzip_types = [t for t in types_seen if counts[t]['gzip'] > 0 and counts[t]['br'] == 0]
            if gzip_types:
                self.results['recommendations'].append({
                    'category': 'Compression',
                    'severity': 'LOW',
                    'issue': (
                        f'Some first-party resources still use Gzip instead of Brotli: '
                        f'{", ".join(gzip_types)}'
                    ),
                    'recommendation': (
                        'Upgrade remaining Gzip-served resources to Brotli for an '
                        'additional ~20% transfer size saving.'
                    )
                })
    
    def _analyze_blocking_from_devtools(self):
        """Extract render-blocking resources from Chrome's PerformanceResourceTiming API data.

        Uses renderBlockingStatus='blocking' — the ground truth from Chrome's rendering
        engine. Handles type=module deferral, inline scripts, and cross-origin cases
        that HTML attribute inspection misses.
        """
        blocking_scripts = []
        blocking_styles = []
        third_party_blocking = []

        for event in self.browser_render_blocking_events:
            url = event.get('url', '')
            if not url:
                continue
            initiator_type = (event.get('initiator_type') or '').lower()
            is_first_party = self.is_first_party(url)

            # Cross-reference with DevTools network events for confirmed content-type.
            browser_event = self.browser_protocol_by_url.get(self._normalize_browser_url(url), {})
            content_type = (browser_event.get('content_type') or '').lower()

            record = {
                'url': url,
                'first_party': is_first_party,
                'start_time_ms': event.get('start_time_ms'),
                'duration_ms': event.get('duration_ms'),
                'transfer_size_bytes': event.get('transfer_size_bytes'),
            }

            is_script = initiator_type == 'script' or 'javascript' in content_type
            is_style = initiator_type in ('link', 'css') or 'text/css' in content_type

            if is_style:
                blocking_styles.append(record)
            else:
                # Treat unknown initiator types conservatively as scripts.
                blocking_scripts.append(record)
                if not is_first_party:
                    third_party_blocking.append(url)

        # Preserve parser order (resources are sorted by start_time by the browser).
        blocking_scripts.sort(key=lambda x: x.get('start_time_ms') or 0)
        blocking_styles.sort(key=lambda x: x.get('start_time_ms') or 0)
        return blocking_scripts, blocking_styles, third_party_blocking

    def _analyze_blocking_from_html(self, head):
        """Fallback: determine render-blocking resources from HTML attributes.

        Used when Chrome's PerformanceResourceTiming.renderBlockingStatus is unavailable
        (static mode, Firefox, or pre-Chrome-107). Less accurate — operates on the
        post-render DOM rather than the original parser state, and misses inline scripts.
        """
        blocking_scripts = []
        third_party_blocking = []
        blocking_styles = []

        if head:
            for script in head.find_all('script', src=True):
                src = script.get('src', '')
                is_async = script.get('async') is not None
                is_defer = script.get('defer') is not None
                # type=module scripts are deferred by default — not render-blocking.
                is_module = (script.get('type') or '').lower() == 'module'
                if not is_async and not is_defer and not is_module:
                    full_url = urljoin(self.final_url, src)
                    is_first_party = self.is_first_party(full_url)
                    blocking_scripts.append({
                        'url': full_url,
                        'first_party': is_first_party,
                        'start_time_ms': None,
                        'duration_ms': None,
                        'transfer_size_bytes': None,
                    })
                    if not is_first_party:
                        third_party_blocking.append(full_url)

            for link in head.find_all('link', rel='stylesheet'):
                href = link.get('href', '')
                media = link.get('media', 'all')
                # media=print (or other non-screen queries) is not render-blocking.
                if media in ('all', 'screen', '') or not media:
                    full_url = urljoin(self.final_url, href)
                    is_first_party = self.is_first_party(full_url)
                    blocking_styles.append({
                        'url': full_url,
                        'first_party': is_first_party,
                        'start_time_ms': None,
                        'duration_ms': None,
                        'transfer_size_bytes': None,
                    })

        return blocking_scripts, blocking_styles, third_party_blocking

    def analyze_head_blocking_resources(self):
        """Analyze render-blocking resources.

        Browser mode (Chrome 107+): uses PerformanceResourceTiming.renderBlockingStatus
        — the authoritative signal from Chrome's rendering engine, identical to what
        Lighthouse reports. Correctly handles type=module deferral, inline scripts,
        preloaded vs parser-blocking resources, and cross-origin cases.

        Static / pre-Chrome-107 fallback: HTML attribute analysis (script in <head>
        without async/defer/type=module, link rel=stylesheet without media=print).
        """
        if not self.soup:
            print("   ⚠️  Cannot analyze - HTML not parsed")
            return

        head = self.soup.find('head')
        use_browser_api = self.use_browser and bool(self.browser_render_blocking_events)

        if use_browser_api:
            blocking_scripts, blocking_styles, third_party_blocking = self._analyze_blocking_from_devtools()
            source = 'chrome-performance-api'
            label = 'Chrome DevTools'
        else:
            if self.use_browser:
                print("   ℹ️  renderBlockingStatus unavailable (pre-Chrome 107?); using HTML attribute analysis")
            blocking_scripts, blocking_styles, third_party_blocking = self._analyze_blocking_from_html(head)
            source = 'html-analysis'
            label = 'HTML analysis'

        third_party_blocking_styles = [s['url'] for s in blocking_styles if not s['first_party']]
        critical_third_party_resources = third_party_blocking + third_party_blocking_styles
        critical_third_party_domains = sorted({urlparse(url).netloc for url in critical_third_party_resources})

        self.results['technical_checks']['head_blocking'] = {
            'source': source,
            'scripts': blocking_scripts,
            'stylesheets': blocking_styles,
            'third_party_scripts': third_party_blocking,
            'third_party_stylesheets': third_party_blocking_styles,
            'critical_third_party_domains': critical_third_party_domains,
        }

        print(f"\n   Render-Blocking Scripts [{label}]: {len(blocking_scripts)}")
        if blocking_scripts:
            for script in blocking_scripts[:5]:
                party = "1st" if script['first_party'] else "3rd"
                url_display = self.format_url_display(script['url'], max_length=70)
                timing = f" ({script['duration_ms']}ms)" if script.get('duration_ms') else ""
                print(f"      ⚠️  [{party}]{timing} {url_display}")

        print(f"\n   Render-Blocking Stylesheets [{label}]: {len(blocking_styles)}")
        if blocking_styles:
            for style in blocking_styles[:5]:
                party = "1st" if style['first_party'] else "3rd"
                url_display = self.format_url_display(style['url'], max_length=70)
                timing = f" ({style['duration_ms']}ms)" if style.get('duration_ms') else ""
                print(f"      ℹ️  [{party}]{timing} {url_display}")

        # Recommendations (same logic, unchanged).
        if blocking_scripts:
            severity = "CRITICAL" if third_party_blocking else "HIGH"
            issue_desc = f"{len(blocking_scripts)} render-blocking scripts in <head>"
            if third_party_blocking:
                issue_desc += f" ({len(third_party_blocking)} third-party - SPOF risk!)"
            self.results['recommendations'].append({
                'category': 'Render Blocking',
                'severity': severity,
                'issue': issue_desc,
                'recommendation': 'Add async/defer attributes to scripts. Third-party scripts are especially problematic as they can cause Single Point of Failure (SPOF).'
            })

        if third_party_blocking:
            self.results['recommendations'].append({
                'category': 'Third-Party SPOF',
                'severity': 'CRITICAL',
                'issue': f'{len(third_party_blocking)} third-party scripts blocking render in <head>',
                'recommendation': 'URGENT: Third-party blocking scripts can cause complete page failure. Load them asynchronously or use fallback mechanisms.'
            })

        if len(blocking_styles) > 2:
            self.results['recommendations'].append({
                'category': 'Render Blocking',
                'severity': 'MEDIUM',
                'issue': f'{len(blocking_styles)} blocking stylesheets',
                'recommendation': 'Consider inlining critical CSS and loading non-critical styles asynchronously.'
            })

        if critical_third_party_resources and head:
            preconnect_links = head.find_all('link', rel=lambda v: v and 'preconnect' in ' '.join(v).lower() if isinstance(v, list) else v and 'preconnect' in v.lower())
            preconnect_domains = set()
            for link in preconnect_links:
                href = link.get('href', '')
                if href:
                    preconnect_domains.add(urlparse(urljoin(self.final_url, href)).netloc)

            preload_links = head.find_all('link', rel=lambda v: v and 'preload' in ' '.join(v).lower() if isinstance(v, list) else v and 'preload' in v.lower())
            preloaded_urls = set()
            for link in preload_links:
                href = link.get('href', '')
                if href:
                    preloaded_urls.add(urljoin(self.final_url, href))

            missing_preconnect_domains = [d for d in critical_third_party_domains if d and d not in preconnect_domains]
            missing_preload_count = sum(1 for u in critical_third_party_resources if u not in preloaded_urls)

            rec = (
                'Critical CSS/JS is served from third-party domains. '
                'Use rel=preconnect for those origins and rel=preload for critical assets, '
                'or serve the most critical render-path assets from the same domain as the main HTML to reduce connection and DNS overhead.'
            )

            if missing_preconnect_domains or missing_preload_count > 0:
                self.results['recommendations'].append({
                    'category': 'Critical Resources',
                    'severity': 'HIGH',
                    'issue': (
                        f'{len(critical_third_party_resources)} critical third-party CSS/JS resources in render path '
                        f'({len(missing_preconnect_domains)} domains without preconnect, '
                        f'{missing_preload_count} resources not preloaded)'
                    ),
                    'recommendation': rec
                })

    def analyze_additional_resources(self):
        """Analyze additional resource optimizations"""
        if not self.soup:
            print("   ⚠️  Cannot analyze resources - HTML not parsed")
            return
        
        html = self.html
        
        # Check page size
        page_size_kb = len(html.encode('utf-8')) / 1024
        self.results['technical_checks']['html_size_kb'] = round(page_size_kb, 2)
        
        if page_size_kb > 500:
            print(f"   HTML Size: ❌ {page_size_kb:.1f}KB (too large)")
            self.results['recommendations'].append({
                'category': 'Page Weight',
                'severity': 'HIGH',
                'issue': f'HTML document is {page_size_kb:.1f}KB',
                'recommendation': 'Reduce HTML size by minimizing inline scripts/styles and removing unused code'
            })
        elif page_size_kb > 200:
            print(f"   HTML Size: ⚠️  {page_size_kb:.1f}KB")
        else:
            print(f"   HTML Size: ✅ {page_size_kb:.1f}KB")
        
        # Check actual image formats by fetching resources
        self.check_image_formats()
        
        # Check for preload/preconnect
        has_preload = 'rel="preload"' in html or "rel='preload'" in html
        has_preconnect = 'rel="preconnect"' in html or "rel='preconnect'" in html
        
        self.results['technical_checks']['resource_hints'] = {
            'preload': has_preload,
            'preconnect': has_preconnect
        }
        
        if has_preload:
            print("   Preload: ✅ Implemented")
        else:
            print("   Preload: ⚠️  Not detected")
        
        if has_preconnect:
            print("   Preconnect: ✅ Implemented")
        else:
            print("   Preconnect: ⚠️  Consider for third-party resources")
        
        # Check for WOFF2 fonts
        if self.use_browser and self.browser_protocol_events:
            font_events = []
            seen_font_urls = set()
            for event in self.browser_protocol_events:
                url = event.get('url')
                if not url or url in seen_font_urls:
                    continue
                if not self.is_first_party(url):
                    continue

                resource_type = (event.get('resource_type') or '').lower()
                content_type = (event.get('content_type') or '').lower()
                if resource_type != 'font' and 'font/' not in content_type and 'woff' not in content_type and 'ttf' not in content_type:
                    continue

                seen_font_urls.add(url)
                font_events.append(event)

            woff2_count = 0
            woff_count = 0
            ttf_count = 0
            other_count = 0
            for event in font_events:
                content_type = (event.get('content_type') or '').lower()
                url = event.get('url', '').lower()
                if 'woff2' in content_type or url.endswith('.woff2'):
                    woff2_count += 1
                elif 'woff' in content_type or url.endswith('.woff'):
                    woff_count += 1
                elif 'ttf' in content_type or 'truetype' in content_type or url.endswith('.ttf'):
                    ttf_count += 1
                else:
                    other_count += 1

            self.results['technical_checks']['font_formats'] = {
                'source': 'chrome-devtools',
                'first_party_only': True,
                'woff2': woff2_count,
                'woff': woff_count,
                'ttf': ttf_count,
                'other': other_count,
                'total_first_party_fonts': len(font_events),
            }

            non_woff2 = woff_count + ttf_count + other_count
            if len(font_events) == 0:
                print("   Font Formats (1st-party): ℹ️  No first-party fonts detected")
            elif non_woff2 == 0:
                print(f"   Font Formats (1st-party): ✅ All WOFF2 ({woff2_count} fonts)")
            else:
                print(
                    f"   Font Formats (1st-party): ⚠️  WOFF2: {woff2_count}, "
                    f"non-WOFF2: {non_woff2}"
                )
                self.results['recommendations'].append({
                    'category': 'Fonts',
                    'severity': 'MEDIUM',
                    'issue': f'{non_woff2} first-party font resource(s) are not WOFF2',
                    'recommendation': 'Deliver first-party fonts in WOFF2 format for better compression and faster rendering.'
                })
        else:
            woff2_count = html.lower().count('.woff2')
            woff_count = html.lower().count('.woff') - woff2_count
            ttf_count = html.lower().count('.ttf')

            self.results['technical_checks']['font_formats'] = {
                'source': 'html-heuristic',
                'first_party_only': False,
                'woff2': woff2_count,
                'woff': woff_count,
                'ttf': ttf_count
            }

            if woff2_count > 0 and woff_count == 0 and ttf_count == 0:
                print(f"   Font Formats: ✅ All WOFF2 ({woff2_count} fonts)")
            elif woff2_count > 0:
                print(f"   Font Formats: ⚠️  Mixed (WOFF2: {woff2_count}, others: {woff_count + ttf_count})")
                self.results['recommendations'].append({
                    'category': 'Fonts',
                    'severity': 'MEDIUM',
                    'issue': 'Not all fonts using WOFF2 format',
                    'recommendation': 'Convert all first-party fonts to WOFF2 format for optimal compression and faster rendering.'
                })
            else:
                print(f"   Font Formats: ❌ No WOFF2 detected")
                if woff_count > 0 or ttf_count > 0:
                    self.results['recommendations'].append({
                        'category': 'Fonts',
                        'severity': 'MEDIUM',
                        'issue': 'Using legacy font formats',
                        'recommendation': 'Convert first-party fonts to WOFF2 format for better compression.'
                    })
        
        # Check HTTP protocol for the first-party origin only.
        if hasattr(self, 'response'):
            http_version, protocol_source = self._detect_http_protocol(self.final_url)
            if http_version is None:
                http_version = 'HTTP/1.1'
            self.results['technical_checks']['http_version'] = http_version
            self.results['technical_checks']['http_version_detection'] = protocol_source

            # Determine whether the first-party origin is HTTP/3-enabled across loaded resources.
            first_party_protocol_counts = {'HTTP/3': 0, 'HTTP/2': 0, 'HTTP/1.1': 0}
            if self.use_browser and self.browser_protocol_events:
                seen_urls = set()
                for event in self.browser_protocol_events:
                    event_url = event.get('url')
                    if not event_url or event_url in seen_urls:
                        continue
                    seen_urls.add(event_url)
                    if not self.is_first_party(event_url):
                        continue

                    event_protocol = event.get('protocol', 'HTTP/1.1')
                    if event_protocol not in first_party_protocol_counts:
                        event_protocol = 'HTTP/1.1'
                    first_party_protocol_counts[event_protocol] += 1

            first_party_resource_count = sum(first_party_protocol_counts.values())
            first_party_http3_enabled = (
                first_party_protocol_counts['HTTP/3'] > 0
                if first_party_resource_count > 0
                else http_version == 'HTTP/3'
            )

            self.results['technical_checks']['first_party_protocol_summary'] = {
                'main_document_protocol': http_version,
                'main_document_detection': protocol_source,
                'first_party_resource_count': first_party_resource_count,
                'first_party_protocol_counts': first_party_protocol_counts,
                'http3_enabled': first_party_http3_enabled,
            }

            if first_party_http3_enabled:
                if http_version == 'HTTP/3':
                    print(f"   Main Origin HTTP Protocol: ✅ {http_version}")
                else:
                    print(
                        "   Main Origin HTTP Protocol: ℹ️  "
                        f"Main document={http_version}, but first-party resources include HTTP/3"
                    )
            else:
                severity = 'HIGH' if http_version == 'HTTP/1.1' else 'MEDIUM'
                print(f"   Main Origin HTTP Protocol: ⚠️  {http_version} (HTTP/3 not enabled on {self.final_domain})")
                self.results['recommendations'].append({
                    'category': 'Protocol',
                    'severity': severity,
                    'issue': (
                        f'First-party origin ({self.final_domain}) does not appear to use HTTP/3 '
                        f'(main document currently {http_version})'
                    ),
                    'recommendation': (
                        'Enable HTTP/3 (QUIC) with HTTP/2 fallback on the first-party origin to improve '
                        'connection setup, reduce head-of-line blocking, and improve resilience on lossy/mobile networks.'
                    )
                })

            # Heuristic check for 103 Early Hints visibility.
            early_hints_detected = bool(self.response.headers.get('link'))
            self.results['technical_checks']['early_hints'] = early_hints_detected

            crux_ttfb = self._get_crux_p75(['experimental_time_to_first_byte', 'time_to_first_byte'])
            crux_lcp = self._get_crux_p75(['largest_contentful_paint'])
            high_ttfb = crux_ttfb is not None and crux_ttfb > 800
            high_lcp = crux_lcp is not None and crux_lcp > 2500

            if early_hints_detected:
                print("   103 Early Hints: ✅ Potentially detected (Link header present)")
            else:
                print("   103 Early Hints: ⚠️  Not detected")
                severity = 'HIGH' if (high_ttfb and high_lcp) else 'MEDIUM'
                issue = '103 Early Hints not detected'
                if high_ttfb or high_lcp:
                    issue += (
                        f" (CrUX signals: TTFB={int(crux_ttfb) if crux_ttfb is not None else 'n/a'}ms, "
                        f"LCP={int(crux_lcp) if crux_lcp is not None else 'n/a'}ms)"
                    )
                self.results['recommendations'].append({
                    'category': 'Protocol',
                    'severity': severity,
                    'issue': issue,
                    'recommendation': 'Implement HTTP 103 Early Hints to send preload/preconnect hints before final HTML response, especially beneficial when HTML TTFB is high and LCP is a concern.'
                })

            # Check caching: prefer browser-loaded DevTools responses and first-party resources.
            if self.use_browser and self.browser_protocol_events:
                self._analyze_caching_from_browser_events()
            else:
                cache_control = self.response.headers.get('cache-control', '')
                self.results['technical_checks']['cache_control'] = {
                    'source': 'requests-fallback',
                    'first_party_document_cache_control': cache_control,
                    'first_party_document_max_age': self._extract_max_age(cache_control),
                }

                max_age = self._extract_max_age(cache_control)
                if max_age is not None:
                    days = max_age / 86400
                    if max_age < 3600:
                        print(f"   Browser Caching: ❌ Too short ({max_age}s)")
                        self.results['recommendations'].append({
                            'category': 'Caching',
                            'severity': 'MEDIUM',
                            'issue': f'Cache max-age is very short ({max_age}s)',
                            'recommendation': 'Increase cache duration for static assets to at least 1 year (31536000s)'
                        })
                    elif max_age < 86400:
                        print(f"   Browser Caching: ⚠️  Could be longer ({max_age}s)")
                    else:
                        print(f"   Browser Caching: ✅ Good ({days:.1f} days)")
                else:
                    print("   Browser Caching: ❌ No max-age set")
                    self.results['recommendations'].append({
                        'category': 'Caching',
                        'severity': 'MEDIUM',
                        'issue': 'No cache-control max-age header',
                        'recommendation': 'Set appropriate cache-control headers with max-age for static resources'
                    })
    
    def check_resource_protocols(self):
        """Sample resources across all domains and build a per-domain HTTP protocol breakdown."""
        if not self.soup:
            print("   ⚠️  Cannot check - HTML not parsed")
            return

        if self.use_browser and self.browser_protocol_events:
            from collections import defaultdict

            domain_results = {}
            by_domain = defaultdict(list)
            for event in self.browser_protocol_events:
                if not event.get('domain'):
                    continue
                by_domain[event['domain']].append(event)

            for domain, events in sorted(by_domain.items()):
                proto_counts = {'HTTP/3': 0, 'HTTP/2': 0, 'HTTP/1.1': 0}
                seen_urls = set()
                for event in events:
                    if event['url'] in seen_urls:
                        continue
                    seen_urls.add(event['url'])
                    proto_counts[event['protocol']] = proto_counts.get(event['protocol'], 0) + 1

                total_resources = sum(proto_counts.values())
                if total_resources == 0:
                    continue

                if proto_counts['HTTP/3'] > 0:
                    best_proto = 'HTTP/3'
                elif proto_counts['HTTP/2'] > 0:
                    best_proto = 'HTTP/2'
                else:
                    best_proto = 'HTTP/1.1'

                domain_results[domain] = {
                    'total_resources': total_resources,
                    'sampled': total_resources,
                    'best_protocol': best_proto,
                    'protocol_counts': proto_counts,
                    'detection_methods': ['chrome-devtools'],
                    'first_party': self.is_first_party(f'https://{domain}/')
                }

            self.results['technical_checks']['resource_protocols'] = domain_results

            if domain_results:
                print(f"\n   {'Domain':<45} {'Resources':>10}  {'Best Protocol':<12}  Party")
                print(f"   {'-'*45} {'-'*10}  {'-'*12}  -----")
                for domain, info in sorted(domain_results.items(), key=lambda x: (-x[1]['total_resources'], x[0])):
                    party = '1st' if info['first_party'] else '3rd'
                    proto_icon = '✅' if info['best_protocol'] == 'HTTP/3' else ('🟡' if info['best_protocol'] == 'HTTP/2' else '❌')
                    print(
                        f"   {domain:<45} {info['total_resources']:>10}  "
                        f"{proto_icon} {info['best_protocol']:<10}  {party}"
                    )

                heavy_http1_third_parties = [
                    (d, i) for d, i in domain_results.items()
                    if not i['first_party']
                    and i['best_protocol'] == 'HTTP/1.1'
                    and i['total_resources'] >= 5
                ]
                if heavy_http1_third_parties:
                    domains_str = ', '.join(d for d, _ in heavy_http1_third_parties)
                    self.results['recommendations'].append({
                        'category': 'Protocol',
                        'severity': 'MEDIUM',
                        'issue': (
                            f'{len(heavy_http1_third_parties)} third-party domain(s) serve a significant '
                            f'number of resources over HTTP/1.1: {domains_str}'
                        ),
                        'recommendation': (
                            'Contact these third-party providers to enable HTTP/2 or HTTP/3 on their CDN/origin, '
                            'or evaluate alternative providers that support modern protocols.'
                        )
                    })
            else:
                print("   ℹ️  No Chrome DevTools protocol events found")
            return

        # Collect all external resource URLs from the parsed HEAD/BODY.
        resource_urls = []
        for tag in self.soup.find_all(['script', 'link', 'img'], src=True):
            src = tag.get('src', '')
            if src and src.startswith('http'):
                resource_urls.append(src)
        for tag in self.soup.find_all('link', href=True):
            href = tag.get('href', '')
            if href and href.startswith('http'):
                resource_urls.append(href)

        # Group URLs by netloc, cap per-domain to avoid excessive requests.
        from collections import defaultdict
        by_domain = defaultdict(list)
        for url in resource_urls:
            netloc = urlparse(url).netloc
            if netloc:
                by_domain[netloc].append(url)

        SAMPLE_PER_DOMAIN = 3   # HEAD requests per domain
        THIRD_PARTY_HTTP1_THRESHOLD = 5  # flag 3rd party only if >= this many resources on HTTP/1.1

        domain_results = {}

        for domain, urls in sorted(by_domain.items()):
            sample = urls[:SAMPLE_PER_DOMAIN]
            proto_counts = {'HTTP/3': 0, 'HTTP/2': 0, 'HTTP/1.1': 0}
            detection_methods = set()
            for url in sample:
                try:
                    proto, method = self._detect_http_protocol(url, timeout_seconds=8)
                    if not proto:
                        continue
                    proto_counts[proto] += 1
                    detection_methods.add(method)
                except Exception:
                    pass
            total_sampled = sum(proto_counts.values())
            if total_sampled == 0:
                continue
            # Best protocol seen in the sample represents the domain capability.
            if proto_counts['HTTP/3'] > 0:
                best_proto = 'HTTP/3'
            elif proto_counts['HTTP/2'] > 0:
                best_proto = 'HTTP/2'
            else:
                best_proto = 'HTTP/1.1'

            domain_results[domain] = {
                'total_resources': len(urls),
                'sampled': total_sampled,
                'best_protocol': best_proto,
                'protocol_counts': proto_counts,
                'detection_methods': sorted(detection_methods),
                'first_party': self.is_first_party(f'https://{domain}/')
            }

        self.results['technical_checks']['resource_protocols'] = domain_results

        if domain_results:
            print(f"\n   {'Domain':<45} {'Resources':>10}  {'Best Protocol':<12}  Party")
            print(f"   {'-'*45} {'-'*10}  {'-'*12}  -----")
            for domain, info in sorted(domain_results.items(),
                                       key=lambda x: (-x[1]['total_resources'], x[0])):
                party = '1st' if info['first_party'] else '3rd'
                proto_icon = '✅' if info['best_protocol'] == 'HTTP/3' else ('🟡' if info['best_protocol'] == 'HTTP/2' else '❌')
                print(
                    f"   {domain:<45} {info['total_resources']:>10}  "
                    f"{proto_icon} {info['best_protocol']:<10}  {party}"
                )

            # Recommend for 3rd-party domains with many resources stuck on HTTP/1.1.
            heavy_http1_third_parties = [
                (d, i) for d, i in domain_results.items()
                if not i['first_party']
                and i['best_protocol'] == 'HTTP/1.1'
                and i['total_resources'] >= THIRD_PARTY_HTTP1_THRESHOLD
            ]
            if heavy_http1_third_parties:
                domains_str = ', '.join(d for d, _ in heavy_http1_third_parties)
                self.results['recommendations'].append({
                    'category': 'Protocol',
                    'severity': 'MEDIUM',
                    'issue': (
                        f'{len(heavy_http1_third_parties)} third-party domain(s) serve a significant '
                        f'number of resources over HTTP/1.1: {domains_str}'
                    ),
                    'recommendation': (
                        'Contact these third-party providers to enable HTTP/2 or HTTP/3 on their CDN/origin, '
                        'or evaluate alternative providers that support modern protocols.'
                    )
                })
        else:
            print("   ℹ️  No external resource URLs found to sample")

    def check_image_formats(self):
        """Check actual image formats, preferring browser-loaded responses when available."""
        if not self.soup:
            print("   ⚠️  Cannot check images - HTML not parsed")
            return
        
        print("\n   🖼️  Analyzing image formats...")

        if self.use_browser and self.browser_protocol_events:
            image_events = []
            seen_urls = set()
            for event in self.browser_protocol_events:
                if event.get('resource_type') != 'Image':
                    continue
                url = event.get('url')
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                image_events.append(event)

            if image_events:
                image_formats = {
                    'webp': 0,
                    'avif': 0,
                    'jpeg': 0,
                    'png': 0,
                    'gif': 0,
                    'svg': 0,
                    'other': 0
                }
                format_details = []

                for event in image_events:
                    content_type = (event.get('content_type') or event.get('mime_type') or '').lower()
                    detected_format = 'other'

                    if 'webp' in content_type:
                        detected_format = 'webp'
                        image_formats['webp'] += 1
                    elif 'avif' in content_type:
                        detected_format = 'avif'
                        image_formats['avif'] += 1
                    elif 'jpeg' in content_type or 'jpg' in content_type:
                        detected_format = 'jpeg'
                        image_formats['jpeg'] += 1
                    elif 'png' in content_type:
                        detected_format = 'png'
                        image_formats['png'] += 1
                    elif 'gif' in content_type:
                        detected_format = 'gif'
                        image_formats['gif'] += 1
                    elif 'svg' in content_type:
                        detected_format = 'svg'
                        image_formats['svg'] += 1
                    else:
                        image_formats['other'] += 1

                    entry = {
                        'url': event['url'],
                        'content_type': content_type,
                        'format': detected_format,
                        'source': 'chrome-devtools',
                    }
                    # Include transfer size so the JSON can answer size questions directly.
                    size_bytes = event.get('transfer_size_bytes')
                    if size_bytes is not None:
                        try:
                            entry['transfer_size_bytes'] = int(size_bytes)
                            entry['transfer_size_kb'] = round(int(size_bytes) / 1024, 1)
                        except (TypeError, ValueError):
                            pass
                    format_details.append(entry)

                self.results['technical_checks']['image_formats'] = {
                    'summary': image_formats,
                    'details': format_details,
                    'checked': len(format_details),
                    'total_found': len(format_details),
                    'source': 'chrome-devtools'
                }

                total_images = sum(image_formats.values())
                modern_images = image_formats['webp'] + image_formats['avif']
                legacy_images = image_formats['jpeg'] + image_formats['png']
                raster_images = modern_images + legacy_images

                print(f"   Using browser-loaded image responses ({len(format_details)} unique images)")
                print(f"\n   Image Format Analysis (checked {total_images}/{len(format_details)} images):")
                if image_formats['webp'] > 0:
                    print(f"      ✅ WebP: {image_formats['webp']}")
                if image_formats['avif'] > 0:
                    print(f"      ✅ AVIF: {image_formats['avif']}")
                if image_formats['jpeg'] > 0:
                    print(f"      ⚠️  JPEG: {image_formats['jpeg']}")
                if image_formats['png'] > 0:
                    print(f"      ⚠️  PNG: {image_formats['png']}")
                if image_formats['gif'] > 0:
                    print(f"      ℹ️  GIF: {image_formats['gif']}")
                if image_formats['svg'] > 0:
                    print(f"      ✅ SVG: {image_formats['svg']}")
                if image_formats['other'] > 0:
                    print(f"      ⚠️  Other/Unknown: {image_formats['other']}")

                if modern_images == 0 and legacy_images > 0:
                    print(f"\n   ❌ No modern image formats detected!")
                    self.results['recommendations'].append({
                        'category': 'Images',
                        'severity': 'HIGH',
                        'issue': f'All {legacy_images}/{raster_images} browser-loaded raster images use legacy formats (JPEG/PNG)',
                        'recommendation': 'Convert images to WebP (30% smaller) or AVIF (50% smaller) for significant bandwidth savings. Use <picture> element for fallbacks.'
                    })
                elif modern_images > 0 and legacy_images > 0:
                    modern_percentage = (modern_images / raster_images) * 100 if raster_images else 0
                    print(f"\n   ⚠️  Mixed formats: {modern_percentage:.0f}% modern, {100-modern_percentage:.0f}% legacy")
                    self.results['recommendations'].append({
                        'category': 'Images',
                        'severity': 'MEDIUM',
                        'issue': (
                            f'Only {modern_images}/{raster_images} browser-loaded raster images '
                            f'(JPEG/PNG/WebP/AVIF) use modern formats; {legacy_images} remain JPEG/PNG'
                        ),
                        'recommendation': f'Convert remaining {legacy_images} JPEG/PNG images to WebP or AVIF for better performance'
                    })
                elif modern_images > 0:
                    print(f"\n   ✅ Good use of modern image formats!")
                return
        
        # Find all image elements with various attributes
        img_tags = self.soup.find_all('img')
        picture_sources = self.soup.find_all('source')
        
        image_urls = []
        
        # Collect img src (including lazy-loaded images)
        for img in img_tags:
            # Try multiple attributes where image URLs might be
            src = (img.get('src') or 
                   img.get('data-src') or 
                   img.get('data-lazy-src') or 
                   img.get('data-original') or
                   img.get('data-srcset', '').split(',')[0].split()[0] if img.get('data-srcset') else None)
            
            if src and not src.startswith('data:') and len(src) > 5:  # Skip data URLs and placeholders
                # Skip placeholder/loading images
                if 'placeholder' not in src.lower() and 'loading' not in src.lower():
                    full_url = urljoin(self.final_url, src)
                    image_urls.append(full_url)
        
        # Collect picture source srcset (modern format delivery)
        for source in picture_sources:
            srcset = source.get('srcset') or source.get('data-srcset', '')
            if srcset:
                # srcset can have multiple URLs with descriptors, take the first
                first_url = srcset.split(',')[0].strip().split()[0]
                if not first_url.startswith('data:') and len(first_url) > 5:
                    full_url = urljoin(self.final_url, first_url)
                    image_urls.append(full_url)
        
        # Also check for background images in inline styles
        style_tags = self.soup.find_all(style=True)
        for tag in style_tags[:20]:  # Check first 20 elements with inline styles
            style = tag.get('style', '')
            if 'background-image' in style or 'background:' in style:
                # Extract URL from url(...) 
                import re
                urls = re.findall(r'url\(["\']?([^"\'()]+)["\']?\)', style)
                for url in urls:
                    if not url.startswith('data:') and len(url) > 5:
                        full_url = urljoin(self.final_url, url)
                        image_urls.append(full_url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_images = []
        for url in image_urls:
            if url not in seen:
                seen.add(url)
                unique_images.append(url)
        
        image_urls = unique_images[:20]  # Check first 20 unique images
        
        if not image_urls:
            print(f"   ℹ️  No images found in HTML")
            print(f"   ℹ️  Found {len(img_tags)} <img> tags, but no valid src attributes")
            print(f"   ℹ️  (Images might be loaded dynamically via JavaScript)")
            self.results['technical_checks']['image_formats'] = {
                'summary': {},
                'details': [],
                'note': 'No images found in static HTML'
            }
            return
        
        print(f"   Found {len(image_urls)} images to check...")
        
        image_formats = {
            'webp': 0,
            'avif': 0,
            'jpeg': 0,
            'png': 0,
            'gif': 0,
            'svg': 0,
            'other': 0
        }
        
        format_details = []
        checked_count = 0
        
        for url in image_urls:
            try:
                # HEAD request to get content-type without downloading full image
                resp = requests.head(url, timeout=5, allow_redirects=True)
                content_type = resp.headers.get('content-type', '').lower()
                
                # Some servers don't support HEAD, try GET with stream
                if not content_type or resp.status_code != 200:
                    resp = requests.get(url, timeout=5, stream=True, allow_redirects=True)
                    content_type = resp.headers.get('content-type', '').lower()
                    resp.close()  # Close stream immediately
                
                if not content_type:
                    continue
                
                # Determine format from Content-Type header
                detected_format = 'other'
                
                if 'webp' in content_type:
                    detected_format = 'webp'
                    image_formats['webp'] += 1
                elif 'avif' in content_type:
                    detected_format = 'avif'
                    image_formats['avif'] += 1
                elif 'jpeg' in content_type or 'jpg' in content_type:
                    detected_format = 'jpeg'
                    image_formats['jpeg'] += 1
                elif 'png' in content_type:
                    detected_format = 'png'
                    image_formats['png'] += 1
                elif 'gif' in content_type:
                    detected_format = 'gif'
                    image_formats['gif'] += 1
                elif 'svg' in content_type:
                    detected_format = 'svg'
                    image_formats['svg'] += 1
                else:
                    image_formats['other'] += 1
                
                format_details.append({
                    'url': url,
                    'content_type': content_type,
                    'format': detected_format
                })
                
                checked_count += 1
                
            except Exception as e:
                # Silently continue on errors
                pass
        
        self.results['technical_checks']['image_formats'] = {
            'summary': image_formats,
            'details': format_details,
            'checked': checked_count,
            'total_found': len(image_urls),
            'source': 'requests'
        }
        
        # Report findings
        total_images = sum(image_formats.values())
        
        if total_images == 0:
            print(f"   ⚠️  Could not analyze any of the {len(image_urls)} images found")
            print(f"   ℹ️  (Possible causes: CORS issues, timeouts, or images require authentication)")
            return
        
        modern_images = image_formats['webp'] + image_formats['avif']
        legacy_images = image_formats['jpeg'] + image_formats['png']
        raster_images = modern_images + legacy_images
        
        print(f"\n   Image Format Analysis (checked {total_images}/{len(image_urls)} images):")
        if image_formats['webp'] > 0:
            print(f"      ✅ WebP: {image_formats['webp']}")
        if image_formats['avif'] > 0:
            print(f"      ✅ AVIF: {image_formats['avif']}")
        if image_formats['jpeg'] > 0:
            print(f"      ⚠️  JPEG: {image_formats['jpeg']}")
        if image_formats['png'] > 0:
            print(f"      ⚠️  PNG: {image_formats['png']}")
        if image_formats['gif'] > 0:
            print(f"      ℹ️  GIF: {image_formats['gif']}")
        if image_formats['svg'] > 0:
            print(f"      ✅ SVG: {image_formats['svg']}")
        if image_formats['other'] > 0:
            print(f"      ⚠️  Other/Unknown: {image_formats['other']}")
        
        # Add recommendations
        if modern_images == 0 and legacy_images > 0:
            print(f"\n   ❌ No modern image formats detected!")
            self.results['recommendations'].append({
                'category': 'Images',
                'severity': 'HIGH',
                'issue': f'All {legacy_images}/{raster_images} sampled raster images use legacy formats (JPEG/PNG)',
                'recommendation': 'Convert images to WebP (30% smaller) or AVIF (50% smaller) for significant bandwidth savings. Use <picture> element for fallbacks.'
            })
        elif modern_images > 0 and legacy_images > 0:
            modern_percentage = (modern_images / raster_images) * 100 if raster_images else 0
            print(f"\n   ⚠️  Mixed formats: {modern_percentage:.0f}% modern, {100-modern_percentage:.0f}% legacy")
            self.results['recommendations'].append({
                'category': 'Images',
                'severity': 'MEDIUM',
                'issue': (
                    f'Only {modern_images}/{raster_images} sampled raster images '
                    f'(JPEG/PNG/WebP/AVIF) use modern formats; {legacy_images} remain JPEG/PNG'
                ),
                'recommendation': f'Convert remaining {legacy_images} JPEG/PNG images to WebP or AVIF for better performance'
            })
        elif modern_images > 0:
            print(f"\n   ✅ Good use of modern image formats!")
    
    def generate_report(self):
        """Generate final summary report"""
        print("\n📋 RECOMMENDATIONS SUMMARY")
        print("="*60)
        
        if not self.results['recommendations']:
            print("✅ No major issues found! Site is well optimized.")
        else:
            # Sort by severity
            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_recs = sorted(
                self.results['recommendations'], 
                key=lambda x: severity_order.get(x.get('severity', 'MEDIUM'), 2)
            )
            
            # Group by category
            by_category = {}
            for rec in sorted_recs:
                cat = rec['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(rec)
            
            for category, recommendations in by_category.items():
                print(f"\n{category}:")
                for i, rec in enumerate(recommendations, 1):
                    severity = rec.get('severity', 'MEDIUM')
                    severity_icon = {
                        'CRITICAL': '🔴',
                        'HIGH': '🟠', 
                        'MEDIUM': '🟡',
                        'LOW': '🟢'
                    }.get(severity, '⚪')
                    
                    print(f"  {severity_icon} [{severity}] {rec['issue']}")
                    print(f"     → {rec['recommendation']}")
        
        # Save to JSON
        import os
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        output_file_name = f"performance_audit_{self.domain.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file = os.path.join(output_dir, output_file_name)

        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n💾 Full report saved to: {output_file}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Web Performance Audit Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Default audit with browser rendering enabled
  python web_performance_audit.py example.com YOUR_API_KEY

        # Run only DNS/CDN checks
        python web_performance_audit.py example.com YOUR_API_KEY --dns-only
  
    # Static-only audit without browser rendering
    python web_performance_audit.py example.com YOUR_API_KEY --no-browser
  
Get your CrUX API key from:
https://developers.google.com/web/tools/chrome-user-experience-report/api/reference
        """
    )
    
    parser.add_argument('url', help='URL to audit (e.g., example.com or https://example.com)')
    parser.add_argument('crux_api_key', help='Chrome UX Report API key')
    parser.add_argument('--dns-only', action='store_true',
                       help='Run only DNS-related checks (DNS TTL, IPv6, CDN)')
    parser.add_argument('--no-browser', action='store_true',
                       help='Disable headless browser rendering and use static HTML only')
    parser.add_argument(
        '--additional-first-party-domains', '-d',
        nargs='+',
        metavar='DOMAIN',
        default=[],
        help=(
            'Extra domains (and all their subdomains) treated as first-party. '
            'Use for owner-controlled domains on a different TLD, e.g. example.media. '
            'All subdomains of the audited site\'s own TLD are already first-party automatically. '
            'Example: --additional-first-party-domains example.media examplerewards.com.au'
        )
    )

    args = parser.parse_args()

    use_browser = not args.no_browser

    if use_browser and not args.dns_only:
        print("\n⚠️  Browser mode enabled - This will:")
        print("   • Render JavaScript like a real browser")
        print("   • Detect lazy-loaded images")
        print("   • Take longer to complete (~10-15 seconds)")
        print("   • Require Selenium: pip install selenium\n")

    if args.additional_first_party_domains:
        print(f"ℹ️  Additional first-party domains: {', '.join(args.additional_first_party_domains)}\n")

    auditor = WebPerformanceAuditor(
        args.url,
        args.crux_api_key,
        use_browser,
        additional_first_party_domains=args.additional_first_party_domains
    )
    if args.dns_only:
        auditor.run_dns_only_audit()
    else:
        auditor.run_full_audit()


if __name__ == "__main__":
    main()
