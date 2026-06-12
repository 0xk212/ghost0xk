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
from os import system, name
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse, urljoin, quote as url_quote
import threading
import queue
from collections import deque

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import phonenumbers
    from phonenumbers import carrier, geocoder, timezone as phone_timezone
except ImportError:
    print("[!] Install phonenumbers: pip install phonenumbers")
    pass

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    print("[!] Install PIL: pip install Pillow")
    pass

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
            
            metadata["File Size"] = str(os.path.getsize(filepath)) + " bytes"
            metadata["Image Format"] = image.format or "N/A"
            metadata["Image Size"] = f"{image.width}x{image.height}"
            metadata["Mode"] = image.mode
            
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
                        metadata["GPS Latitude"] = str(lat)
                        metadata["GPS Longitude"] = str(lon)
                        metadata["Google Maps"] = f"https://www.google.com/maps?q={lat},{lon}"
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
            with zipfile.ZipFile(filepath) as z:
                if 'docProps/core.xml' in z.namelist():
                    core = z.read('docProps/core.xml').decode('utf-8', errors='replace')
                    for tag in ['title', 'creator', 'lastModifiedBy', 'created', 'modified', 'subject']:
                        match = re.search(f'<cp:{tag}[^>]*>(.*?)</cp:{tag}>', core, re.I)
                        if match:
                            metadata[tag.capitalize()] = match.group(1).strip()
                if 'docProps/app.xml' in z.namelist():
                    app = z.read('docProps/app.xml').decode('utf-8', errors='replace')
                    for tag in ['Application', 'Company', 'TotalTime']:
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

def IP_Track():
    ip = input(f"\n{Wh}[?] Enter IP target {Gr}[e.g., 8.8.8.8]{Wh}: {Gr}").strip()
    if not validate_ip(ip):
        print(f"{R}[!] Invalid IP address!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}IP ADDRESS INFORMATION")
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
        "Latitude": ip_data.get("latitude", ip_data.get("lat", "N/A")),
        "Longitude": ip_data.get("longitude", ip_data.get("lon", "N/A")),
        "ISP": ip_data.get("connection", {}).get("isp", ip_data.get("isp", "N/A")),
        "Organization": ip_data.get("connection", {}).get("org", ip_data.get("org", "N/A")),
        "ASN": ip_data.get("connection", {}).get("asn", ip_data.get("as", "N/A")),
        "AS Name": ip_data.get("connection", {}).get("asn_org", ip_data.get("org", "N/A")),
        "AS Route": ip_data.get("asn_route", "N/A"),
        "AS Domain": ip_data.get("asn_domain", "N/A"),
        "Timezone": ip_data.get("timezone", {}).get("id", ip_data.get("timezone", "N/A")),
        "Continent": ip_data.get("continent", "N/A"),
    }
    
    for key, value in data.items():
        if value not in ("N/A", "unknown", None, False, "0"):
            print(f"{Wh} {key:<14}: {Gr}{value}")
    
    lat = data.get("Latitude")
    lon = data.get("Longitude")
    if lat != "N/A" and lon != "N/A":
        print(f"{Wh} Google Maps    : {C}https://www.google.com/maps/@{lat},{lon},15z{RS}")
        print(f"{Wh} OpenStreetMap  : {C}https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=15{RS}")
    
    print(f"\n{Y}[*] Checking abuse reports...{Wh}")
    abuse_data = check_ip_abuse(ip)
    if abuse_data.get("confidence", 0) > 0 or abuse_data.get("reports", 0) > 0:
        print(f"{R}[!] Abuse Confidence: {abuse_data['confidence']}% | Reports: {abuse_data['reports']}{Wh}")
        if abuse_data.get("categories"):
            print(f"{R}    Categories: {', '.join(abuse_data['categories'])}{Wh}")
    else:
        print(f"{Gr}[+] No abuse reports found")
    data["AbuseIPDB"] = abuse_data
    
    print(f"\n{Y}[?] Scan common ports? (y/n): {Wh}", end="")
    if input().lower() == 'y':
        print(f"{Wh}\n[*] Scanning ports...")
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
    
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="ip",
        target=ip,
        data=data
    )
    save_report(result)
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")

def phoneGW():
    print(f"\n {Wh}{'='*50}")
    print(f" {R}PHONE NUMBER TRACKER")
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
    print(f" {R}PHONE NUMBER INFORMATION")
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
        
        is_valid = phonenumbers.is_valid_number(parsed_number)
        is_possible = phonenumbers.is_possible_number(parsed_number)
        if is_valid:
            data["Validity Score"] = "High - Valid Number"
        elif is_possible:
            data["Validity Score"] = "Medium - Possible but Invalid"
        else:
            data["Validity Score"] = "Low - Impossible Number"
        
        for key, value in data.items():
            if value and value != "Unknown" and value != "Other":
                print(f"{Wh} {key:<18}: {Gr}{value}")
        
        print(f"\n{Gr}[+] Number appears to be a {num_type_str} number in {carrier_country}")
        
        clean_number = re.sub(r'[^\d+]', '', user_phone)
        if not clean_number.startswith('+'):
            clean_number = '+' + clean_number
        clean_digits = re.sub(r'\D', '', clean_number)
        
        print(f"\n {Wh}{'='*50}")
        print(f" {R}MESSAGING DIRECT LINKS")
        print(f" {Wh}{'='*50}")
        print(f"{Wh} WhatsApp       : {C}https://wa.me/{clean_number}{RS}")
        print(f"{Wh} Telegram       : {C}https://t.me/{clean_number}{RS}")
        print(f"{Wh} Signal         : {C}https://signal.me/#p/{clean_number}{RS}")
        print(f"{Wh} Viber          : {C}viber://chat?number={clean_digits}{RS}")
        
        print(f"\n {Wh}{'='*50}")
        print(f" {R}WEB SEARCH LINKS (open in browser)")
        print(f" {Wh}{'='*50}")
        print(f"{Wh} Google Search  : {C}https://www.google.com/search?q={clean_number}{RS}")
        print(f"{Wh} Truecaller     : {C}https://www.truecaller.com/search/{clean_digits}{RS}")
        print(f"{Wh} SpyDialer      : {C}https://spydialer.com/default.aspx?search={clean_digits}{RS}")
        print(f"{Wh} Whitepages     : {C}https://www.whitepages.com/phone/{clean_digits}{RS}")
        print(f"{Wh} Numcheck       : {C}https://www.numcheck.com/{clean_digits}{RS}")
        print(f"{Wh} PhoneInfoga    : {C}https://phoneinfoga.crvx.fr/?number={clean_number}{RS}")
        print(f"{Wh} Sync.Me        : {C}https://sync.me/search/?number={clean_digits}{RS}")
        print(f"{Wh} FreeCarrierLookup: {C}https://freecarrierlookup.com/getcarrier/{clean_digits}{RS}")
        
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

def email_osint():
    email = input(f"\n{Wh}[?] Enter email address {Gr}[e.g., user@example.com]{Wh}: {Gr}").strip()
    if not email or '@' not in email:
        print(f"{R}[!] Invalid email address!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}EMAIL OSINT INVESTIGATION")
    print(f" {Wh}{'='*50}")
    
    domain = email.split('@')[1]
    username = email.split('@')[0]
    email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
    email_sha1 = hashlib.sha1(email.lower().strip().encode()).hexdigest()
    
    data = {
        "Email": email,
        "Username": username,
        "Domain": domain,
        "MD5 Hash": email_hash,
        "SHA1 Hash": email_sha1,
    }
    
    print(f"{Wh} Username       : {Gr}{username}")
    print(f"{Wh} Domain         : {Gr}{domain}")
    print(f"{Wh} MD5 Hash       : {Gr}{email_hash}")
    
    print(f"\n{Y}[*] Checking domain email servers...{Wh}")
    domain_info = check_email_domain(domain)
    if domain_info.get("MX Records"):
        print(f"{Gr}[+] Domain has mail servers configured{Wh}")
        for mx in domain_info["MX Records"][:3]:
            print(f"    {Wh}MX: {Gr}{mx}")
        data["Email Domain Info"] = domain_info
    elif domain_info.get("A Records"):
        print(f"{Y}[+] Domain resolves to IP but no MX records{Wh}")
    else:
        print(f"{R}[!] Domain does not resolve - email may be invalid{Wh}")
    
    print(f"\n{Y}[*] Checking Gravatar...{Wh}")
    try:
        gravatar_url = f"https://www.gravatar.com/{email_hash}.json"
        gravatar_resp = requests.get(gravatar_url, timeout=5)
        if gravatar_resp.status_code == 200:
            grav_data = gravatar_resp.json()
            entries = grav_data.get("entry", [])
            if entries:
                profile = entries[0]
                print(f"{Gr}[+] Gravatar profile found:{Wh}")
                print(f"    {Wh}Name     : {Gr}{profile.get('displayName', 'N/A')}")
                print(f"    {Wh}Location : {Gr}{profile.get('currentLocation', 'N/A')}")
                print(f"    {Wh}Profile  : {C}https://www.gravatar.com/{email_hash}{RS}")
                data["Gravatar"] = profile
        else:
            print(f"{Y}[-] No Gravatar profile found")
            data["Gravatar"] = None
    except:
        print(f"{Y}[?] Could not check Gravatar")
    
    print(f"\n{Y}[*] Checking EmailRep.io reputation...{Wh}")
    try:
        erep = requests.get(f"https://emailrep.io/{email}", headers={"User-Agent": random.choice(CONFIG["user_agents"])}, timeout=10)
        if erep.status_code == 200:
            erep_data = erep.json()
            rep = erep_data.get("reputation", "unknown")
            susp = erep_data.get("suspicious", False)
            data["EmailRep"] = erep_data
            print(f"{Wh} Reputation    : {Gr}{rep}")
            print(f"{Wh} Suspicious    : {R}{susp}{Wh}" if susp else f"{Wh} Suspicious    : {Gr}No{Wh}")
            details = erep_data.get("details", {})
            if details.get("spam"):
                print(f"{Wh} Spam Activity : {R}Yes{Wh}")
            if details.get("malicious_activity"):
                print(f"{Wh} Malicious     : {R}Yes{Wh}")
            if details.get("credentials_leaked"):
                print(f"{Wh} Credentials Leaked: {R}Yes{Wh}")
            if details.get("data_breach"):
                print(f"{Wh} Data Breach   : {R}Yes{Wh}")
            profiles = erep_data.get("details", {}).get("profiles", [])
            if profiles:
                print(f"{Wh} Social Profiles: {Gr}{', '.join(profiles[:6])}{Wh}")
                data["EmailRep Profiles"] = profiles
        else:
            print(f"{Y}[-] EmailRep.io check unavailable")
            data["EmailRep"] = None
    except:
        print(f"{Y}[?] Could not check EmailRep.io")
        data["EmailRep"] = None
    
    print(f"\n{Y}[*] Attempting SMTP mailbox verification...{Wh}")
    try:
        import smtplib
        import dns.resolver
        mx_found = False
        for mx_rec in domain_info.get("MX Records", []):
            mx_host = mx_rec.split()[-1] if mx_rec.split() else mx_rec
            mx_host = mx_host.rstrip('.')
            try:
                smtp = smtplib.SMTP(mx_host, 25, timeout=8)
                smtp.ehlo_or_helo_if_needed()
                smtp.mail('check@test.com')
                code, msg = smtp.rcpt(email)
                smtp.quit()
                if code == 250:
                    print(f"{Gr}[+] Email appears valid (server accepted){Wh}")
                    data["SMTP Status"] = "Valid - Server Accepted"
                    mx_found = True
                    break
                elif code == 450:
                    print(f"{Y}[?] Email status: Temporary failure (try again){Wh}")
                    data["SMTP Status"] = "Temporary Failure"
                    mx_found = True
                    break
                elif code == 550:
                    print(f"{R}[!] Email does not exist on server{Wh}")
                    data["SMTP Status"] = "Invalid - Rejected by Server"
                    mx_found = True
                    break
            except:
                continue
        if not mx_found:
            print(f"{Y}[?] SMTP verification not possible (no MX or blocked){Wh}")
            data["SMTP Status"] = "Not Verified"
    except ImportError:
        print(f"{Y}[-] SMTP verification requires 'dnspython' package")
        print(f"{Y}    pip install dnspython")
        data["SMTP Status"] = "Library Missing"
    except Exception as e:
        print(f"{Y}[?] SMTP check skipped: {str(e)[:40]}{Wh}")
        data["SMTP Status"] = "Check Skipped"
    
    print(f"\n{Y}[*] Checking email breach status...{Wh}")
    breach_data = check_email_breach(email)
    if breach_data.get("breached") == True:
        sites = breach_data.get("sites", [])
        print(f"{R}[!] Email found in {len(sites)} data breaches!{Wh}")
        data["Breached"] = "Yes"
        data["Breach Sites"] = [s.get('Name', 'Unknown') for s in sites]
        for i, site in enumerate(sites[:8], 1):
            print(f"    {R}{i}. {Y}{site.get('Name', 'Unknown')} ({site.get('Domain', '')})")
        if len(sites) > 8:
            print(f"    {Y}... and {len(sites) - 8} more")
    elif breach_data.get("breached") == False:
        print(f"{Gr}[+] Email not found in known breaches")
        data["Breached"] = "No"
    else:
        print(f"{Y}[?] Could not check breach status (API limit?)")
        data["Breached"] = "Unknown"
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}LOOKUP LINKS (open in browser)")
    print(f" {Wh}{'='*50}")
    print(f"{Wh} GitHub search  : {C}https://api.github.com/search/users?q={email}{RS}")
    print(f"{Wh} Gravatar       : {C}https://www.gravatar.com/{email_hash}{RS}")
    print(f"{Wh} Hunter.io      : {C}https://hunter.io/search/{domain}{RS}")
    print(f"{Wh} EmailRep       : {C}https://emailrep.io/{email}{RS}")
    print(f"{Wh} LeakCheck      : {C}https://leak-check.net/search?query={email}{RS}")
    print(f"{Wh} DeHashed       : {C}https://dehashed.com/?q={email}{RS}")
    print(f"{Wh} HaveIBeenPwned : {C}https://haveibeenpwned.com/account/{email}{RS}")
    
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="email",
        target=email,
        data=data
    )
    save_report(result)
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")

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

def domain_osint():
    domain = input(f"\n{Wh}[?] Enter domain {Gr}[e.g., example.com]{Wh}: {Gr}").strip()
    if not domain:
        print(f"{R}[!] Domain cannot be empty!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    domain = domain.lower().replace('https://', '').replace('http://', '').split('/')[0].split('?')[0]
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}DOMAIN OSINT INVESTIGATION")
    print(f" {Wh}{'='*50}")
    
    data = {}
    
    print(f"{Y}[*] DNS Lookup (A, AAAA records)...{Wh}")
    dns_data = dns_lookup(domain)
    data["DNS"] = dns_data
    ip_addr = dns_data.get('A', 'N/A')
    print(f"{Wh} IPv4 Address   : {Gr}{ip_addr}")
    if dns_data.get("All A Records") and len(dns_data["All A Records"]) > 1:
        print(f"{Wh} All IPs        : {Gr}{', '.join(dns_data['All A Records'])}")
    
    print(f"{Y}[*] DNS Records (NS, MX, TXT, SOA)...{Wh}")
    full_dns = dns_records_full(domain)
    data["Full DNS"] = full_dns
    for rtype in ["NS", "MX", "TXT", "SOA"]:
        records = full_dns.get(rtype, [])
        if records:
            print(f"{Wh} {rtype:<14}: {Gr}{records[0][:80]}")
    
    print(f"{Y}[*] SSL Certificate Check...{Wh}")
    ssl_data = check_ssl_cert(domain)
    data["SSL"] = ssl_data
    if "error" not in ssl_data:
        print(f"{Wh} SSL Issuer     : {Gr}{ssl_data.get('Issuer', 'N/A')}")
        print(f"{Wh} SSL Subject    : {Gr}{ssl_data.get('Subject', 'N/A')}")
        print(f"{Wh} SSL Expiry     : {Gr}{ssl_data.get('Expiry', 'N/A')}")
        print(f"{Wh} SSL SAN        : {Gr}{ssl_data.get('SAN', 'N/A')}")
    else:
        print(f"{Y}[-] {ssl_data['error']}")
    
    print(f"{Y}[*] HTTP Headers & Technology Detection...{Wh}")
    try:
        hresp = requests.get(f"https://{domain}", timeout=CONFIG["request_timeout"], 
                           headers={"User-Agent": random.choice(CONFIG["user_agents"])})
        headers = dict(hresp.headers)
        data["HTTP Headers"] = headers
        server = headers.get("Server", "N/A")
        if server != "N/A":
            print(f"{Wh} Server          : {Gr}{server}")
        powered = headers.get("X-Powered-By", headers.get("X-AspNet-Version", "N/A"))
        if powered != "N/A":
            print(f"{Wh} Powered By      : {Gr}{powered}")
        cdn = headers.get("CF-RAY", headers.get("X-Sucuri-ID", headers.get("x-amz-cf-id", "")))
        if cdn:
            print(f"{Wh} WAF/CDN         : {Gr}Cloudflare" if "CF-RAY" in str(headers) else f"{Wh} WAF Detected   : {Gr}Yes")
        location = headers.get("Location", "")
        if location:
            print(f"{Wh} Redirects To    : {Gr}{location}")
        for tech_header in ["X-Generator", "X-Drupal-Cache", "X-Varnish", "X-Joomla-Version"]:
            val = headers.get(tech_header, "")
            if val:
                print(f"{Wh} {tech_header:<15}: {Gr}{val}")
        data["HTTP Status"] = hresp.status_code
    except:
        print(f"{Y}[-] HTTP check failed (no HTTPS?)")
        try:
            hresp = requests.get(f"http://{domain}", timeout=CONFIG["request_timeout"],
                               headers={"User-Agent": random.choice(CONFIG["user_agents"])})
            headers = dict(hresp.headers)
            data["HTTP Headers"] = headers
            server = headers.get("Server", "N/A")
            if server != "N/A":
                print(f"{Wh} Server          : {Gr}{server}")
            data["HTTP Status"] = hresp.status_code
        except:
            print(f"{Y}[-] HTTP check unavailable")
    
    print(f"{Y}[*] CRT.sh Certificate Transparency search...{Wh}")
    try:
        crt_resp = requests.get(f"https://crt.sh/?q=%.{domain}&output=json", timeout=10)
        if crt_resp.status_code == 200:
            certs = crt_resp.json()
            if isinstance(certs, list) and certs:
                issuers = set()
                subdomains = set()
                for cert in certs[:30]:
                    name_value = cert.get("name_value", "")
                    if name_value:
                        parts = name_value.split("\n")
                        for p in parts:
                            subdomains.add(p.lower())
                    issuer = cert.get("issuer_name", "")
                    if issuer:
                        issuers.add(issuer.split("CN=")[-1].split(",")[0] if "CN=" in issuer else issuer[:40])
                data["CRT.sh Subdomains"] = list(subdomains)[:30]
                data["CRT.sh Issuers"] = list(issuers)[:5]
                print(f"{Gr}[+] Found {len(subdomains)} subdomains in cert logs{Wh}")
                if subdomains:
                    sub_list = list(subdomains)[:10]
                    for s in sorted(sub_list):
                        print(f"    {Wh}- {C}{s}{RS}")
                    if len(subdomains) > 10:
                        print(f"    {Y}... and {len(subdomains)-10} more subdomains")
                if issuers:
                    print(f"{Wh} Cert Issuers   : {Gr}{', '.join(list(issuers)[:3])}")
            else:
                print(f"{Y}[-] No certificates found")
                data["CRT.sh Subdomains"] = []
        else:
            print(f"{Y}[-] CRT.sh unavailable (rate limited)")
            data["CRT.sh Subdomains"] = []
    except:
        print(f"{Y}[-] CRT.sh check failed")
        data["CRT.sh Subdomains"] = []
    
    print(f"{Y}[*] WHOIS Lookup...{Wh}")
    whois_data = whois_lookup(domain)
    if "raw" in whois_data:
        print(f"{Gr}[+] WHOIS data retrieved{Wh}")
        whois_text = whois_data["raw"][:600]
        data["WHOIS"] = whois_text
        registar_match = re.search(r'(Registrar|Sponsoring Registrar):\s*(.+)', whois_text, re.I)
        if registar_match:
            print(f"{Wh} Registrar      : {Gr}{registar_match.group(2).strip()[:50]}")
        date_match = re.search(r'(Creation Date|Created on|created):\s*(.+)', whois_text, re.I)
        if date_match:
            print(f"{Wh} Created        : {Gr}{date_match.group(2).strip()[:30]}")
        expire_match = re.search(r'(Expir\w+ Date|Registry Expiry|paid-till):\s*(.+)', whois_text, re.I)
        if expire_match:
            print(f"{Wh} Expires        : {Gr}{expire_match.group(2).strip()[:30]}")
        org_match = re.search(r'(Registrant Organization|OrgName|org-name):\s*(.+)', whois_text, re.I)
        if org_match:
            org_val = org_match.group(2).strip()[:50]
            if org_val not in ("N/A", "", " REDACTED FOR PRIVACY"):
                print(f"{Wh} Organization  : {Gr}{org_val}")
    else:
        print(f"{Y}[-] WHOIS not available (install whois CLI)")
    
    print(f"{Y}[*] Wayback Machine check...{Wh}")
    wayback_data = wayback_check(domain)
    if wayback_data.get("available"):
        print(f"{Gr}[+] Archived version found{Wh}")
        print(f"{Wh} Archived Date  : {Gr}{wayback_data.get('timestamp')}")
        print(f"{Wh} Archive URL    : {C}{wayback_data.get('url')}{RS}")
        data["Wayback"] = wayback_data
    else:
        print(f"{Y}[-] No archive found")
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}ADDITIONAL RESOURCES")
    print(f" {Wh}{'='*50}")
    print(f"{Wh} VirusTotal     : {C}https://www.virustotal.com/gui/domain/{domain}{RS}")
    print(f"{Wh} SecurityTrails  : {C}https://securitytrails.com/domain/{domain}{RS}")
    print(f"{Wh} URLScan.io     : {C}https://urlscan.io/domain/{domain}{RS}")
    print(f"{Wh} Shodan         : {C}https://www.shodan.io/domain/{domain}{RS}")
    print(f"{Wh} CRT.sh (certs) : {C}https://crt.sh/?q=%.{domain}{RS}")
    print(f"{Wh} BuiltWith      : {C}https://builtwith.com/{domain}{RS}")
    print(f"{Wh} Wappalyzer     : {C}https://www.wappalyzer.com/lookup/{domain}{RS}")
    
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="domain",
        target=domain,
        data=data
    )
    save_report(result)
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")

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
            stars = f"★{r['stars']}" if r['stars'] else ""
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
    
    platforms = [
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
        {"url": "https://discord.com/users/{}", "name": "Discord"},
        {"url": "https://steamcommunity.com/id/{}", "name": "Steam"},
        {"url": "https://soundcloud.com/{}", "name": "SoundCloud"},
        {"url": "https://www.wattpad.com/user/{}", "name": "Wattpad"},
        {"url": "https://vk.com/{}", "name": "VK"},
        {"url": "https://www.mixcloud.com/{}/", "name": "Mixcloud"},
        {"url": "https://tryhackme.com/p/{}", "name": "TryHackMe"},
        {"url": "https://news.ycombinator.com/user?id={}", "name": "HackerNews"},
        {"url": "https://gitlab.com/{}", "name": "GitLab"},
        {"url": "https://bitbucket.org/{}/", "name": "Bitbucket"},
        {"url": "https://angel.co/u/{}", "name": "AngelList"},
        {"url": "https://www.quora.com/profile/{}", "name": "Quora"},
        {"url": "https://www.codecademy.com/profiles/{}", "name": "Codecademy"},
        {"url": "https://www.youracclaim.com/users/{}", "name": "Acclaim"},
        {"url": "https://www.codewars.com/users/{}", "name": "CodeWars"},
        {"url": "https://www.hackerrank.com/{}", "name": "HackerRank"},
        {"url": "https://www.couchsurfing.com/people/{}", "name": "Couchsurfing"},
        {"url": "https://cash.app/{}", "name": "CashApp"},
        {"url": "https://venmo.com/{}", "name": "Venmo"},
        {"url": "https://imgur.com/user/{}", "name": "Imgur"},
        {"url": "https://letterboxd.com/{}/", "name": "Letterboxd"},
    ]
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}USERNAME TRACKING")
    print(f" {Wh}{'='*50}")
    print(f"{Y}[*] Searching {len(platforms)} platforms...")
    
    results = {}
    session = get_session()
    found_count = 0
    
    def check_platform(site: Dict) -> Tuple[str, Dict]:
        url = site['url'].format(username)
        name = site['name']
        try:
            random_delay()
            response = session.get(url, timeout=CONFIG["request_timeout"], allow_redirects=True, stream=True)
            body = response.text[:800].lower() if response.status_code == 200 else ""
            response.close()
            
            if response.status_code == 200:
                patterns = NOT_FOUND_PATTERNS.get(name, [])
                if patterns and any(p in body for p in patterns):
                    return name, {"status": "not_found", "url": url}
                return name, {"status": "found", "url": url}
            elif response.status_code == 403:
                return name, {"status": "found", "url": url}
            else:
                return name, {"status": "not_found", "url": url}
        except Exception as e:
            return name, {"status": "error", "url": url, "error": str(e)[:50]}
    
    with ThreadPoolExecutor(max_workers=CONFIG["max_threads"]) as executor:
        futures = {executor.submit(check_platform, site): site for site in platforms}
        
        for i, future in enumerate(as_completed(futures), 1):
            platform, result = future.result()
            results[platform] = result
            if result.get("status") == "found":
                found_count += 1
            
            progress = int((i / len(platforms)) * 100)
            print(f"\r{Y}[*] Progress: {progress}% | Found: {found_count}", end="", flush=True)
    
    print(f"\n\n {Wh}{'='*50}")
    print(f" {R}RESULTS SUMMARY")
    print(f" {Wh}{'='*50}")
    
    if found_count > 0:
        print(f"{Wh}\n {'='*40}")
        print(f" {Gr}FOUND PROFILES ({found_count})")
        print(f"{Wh} {'='*40}")
        for platform, data in sorted(results.items()):
            if data.get("status") == "found":
                print(f"{Wh} [+] {platform:<15}: {C}{data.get('url')}{RS}")
        
        not_found_list = [p for p, d in results.items() if d.get("status") == "not_found"]
        error_list = [p for p, d in results.items() if d.get("status") == "error"]
        if not_found_list:
            print(f"\n{Y} [-] Not found ({len(not_found_list)}): {', '.join(not_found_list[:10])}{'...' if len(not_found_list) > 10 else ''}")
        if error_list:
            print(f"{R} [!] Errors ({len(error_list)}): {', '.join(error_list)}")
        print(f"\n{Gr}[+] Total profiles found: {found_count}/{len(platforms)}")
    else:
        print(f"{Y}[!] No profiles found for '{username}' on any platform")
    
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="username",
        target=username,
        data=results
    )
    save_report(result, ["json", "txt", "csv"])
    input(f"\n{Wh}[+{Wh}] Press Enter to continue")

def reverse_image():
    print(f"\n {Wh}{'='*50}")
    print(f" {R}REVERSE IMAGE SEARCH")
    print(f" {Wh}{'='*50}")
    
    image_input = input(f"{Wh}[?] Enter image URL or local path: {Gr}").strip()
    
    if not image_input:
        print(f"{R}[!] Please enter a valid input!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    is_local = os.path.exists(image_input)
    
    engines = [
        {"name": "Google Lens", "url": f"https://lens.google.com/upload?url={image_input}" if not is_local else "https://images.google.com/ (upload manually)"},
        {"name": "Bing Images", "url": f"https://www.bing.com/images/search?q=imgurl:{image_input}"},
        {"name": "Yandex", "url": f"https://yandex.com/images/search?url={image_input}" if not is_local else "https://yandex.com/images/ (upload manually)"},
        {"name": "TinEye", "url": f"https://tineye.com/search?url={image_input}" if not is_local else "https://tineye.com/ (upload manually)"},
        {"name": "SauceNao", "url": f"https://saucenao.com/search.php?url={image_input}" if not is_local else "https://saucenao.com/ (upload manually)"},
    ]
    
    print(f"\n{Y}[*] Open these links in your browser:\n")
    for engine in engines:
        print(f" {Wh}[+] {engine['name']:<15}: {C}{engine['url']}{RS}")
    
    if is_local:
        print(f"\n{Gr}[+] Local file: {os.path.basename(image_input)}")
        print(f"{Wh} Size: {Gr}{os.path.getsize(image_input):,} bytes")
        print(f"{Wh} Last Modified: {Gr}{datetime.fromtimestamp(os.path.getmtime(image_input)).isoformat()}")
        metadata = extract_metadata(image_input)
        if metadata:
            print(f"\n{Y}[*] Found metadata ({len(metadata)} fields):{Wh}")
            for key in ["Make", "Model", "DateTimeOriginal", "GPS Latitude", "GPS Longitude", 
                        "Google Maps", "Image Size", "Image Format", "Software"]:
                if key in metadata:
                    if key in ("Google Maps",):
                        print(f"    {C}{key}: {metadata[key]}{RS}")
                    else:
                        print(f"    {Wh}{key:<20}: {Gr}{metadata[key][:100]}")
            other_count = len(metadata) - sum(1 for k in ["Make", "Model", "DateTimeOriginal", "GPS Latitude", "GPS Longitude", "Google Maps", "Image Size", "Image Format", "Software"] if k in metadata)
            if other_count > 0:
                print(f"    {Y}... and {other_count} more metadata fields (use Metadata Extractor)")
    
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

def website_downloader():
    if BeautifulSoup is None:
        print(f"{R}[!] Install BeautifulSoup4: pip install beautifulsoup4{RS}")
        input(f"\n{Wh}[+] Press Enter")
        return

    print(f"\n {Wh}{'='*50}")
    print(f" {R}WEBSITE DOWNLOADER")
    print(f" {Wh}{'='*50}")

    url = input(f"\n{Wh}[?] Enter website URL {Gr}[e.g., example.com]{Wh}: {Gr}").strip()
    if not url:
        print(f"{R}[!] URL cannot be empty!")
        input(f"\n{Wh}[+] Press Enter")
        return
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    print(f"\n{Y}[*] Preparing to download: {url}")
    print(f"{Y}[*] This may take significant time for large websites")

    depth_input = input(f"\n{Wh}[?] Max depth {Gr}[0=unlimited, default=3]{Wh}: {Gr}").strip()
    max_depth = int(depth_input) if depth_input.isdigit() else 3

    links_input = input(f"{Wh}[?] Max links {Gr}[default=500]{Wh}: {Gr}").strip()
    max_links = int(links_input) if links_input.isdigit() else 500

    print(f"\n{Y}[!] Target: {url} | Depth: {'∞' if max_depth==0 else max_depth} | Max Links: {max_links}{RS}")
    confirm = input(f"{Wh}[?] Start download? {Gr}(y/n){Wh}: {Gr}").strip().lower()
    if confirm != 'y':
        print(f"{Y}[!] Cancelled")
        input(f"\n{Wh}[+] Press Enter")
        return

    parsed = urlparse(url)
    domain = parsed.netloc
    safe_domain = re.sub(r'[^\w\-_.]', '_', domain)
    out_dir = Path(CONFIG["output_dir"]) / "websites" / safe_domain
    out_dir.mkdir(parents=True, exist_ok=True)

    visited = set()
    downloaded = set()
    failed = {}
    total_size = 0
    q = queue.Queue()
    q.put((url, 0))
    stats_lock = threading.Lock()
    active_count = 0
    active_lock = threading.Lock()
    stop_workers = False

    session = get_session()
    session.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    })

    print(f"\n{Wh}{'='*50}")
    print(f"{Gr}[*] Download started...")
    print(f"{Wh}{'='*50}\n")

    start_time = time.time()

    def save_file(content: bytes, filepath: Path) -> Path:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            f.write(content)
        return filepath

    def url_to_path(url: str) -> Path:
        p = urlparse(url)
        path = p.path
        if not path or path.endswith('/'):
            path += 'index.html'
        if path.startswith('/'):
            path = path[1:]
        return out_dir / path

    def extract_links(html: str, base: str) -> set:
        links = set()
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for tag, attr in [('a','href'),('link','href'),('script','src'),('img','src'),
                             ('source','src'),('video','src'),('audio','src'),('iframe','src'),
                             ('embed','src'),('object','data'),('form','action')]:
                for el in soup.find_all(tag):
                    val = el.get(attr)
                    if val:
                        full = urljoin(base, val)
                        parsed_full = urlparse(full)
                        if parsed_full.scheme in ('http','https'):
                            links.add(full)
            for style in soup.find_all('style'):
                if style.string:
                    for m in re.findall(r'url\([\'"]?([^\'"\)]+)[\'"]?\)', style.string):
                        links.add(urljoin(base, m))
            for el in soup.find_all(style=True):
                for m in re.findall(r'url\([\'"]?([^\'"\)]+)[\'"]?\)', el['style']):
                    links.add(urljoin(base, m))
        except:
            pass
        return links

    def worker():
        nonlocal active_count, total_size, stop_workers
        while not stop_workers:
            try:
                item_url, depth = q.get(timeout=1)
            except queue.Empty:
                with active_lock:
                    if active_count == 0:
                        break
                continue

            with active_lock:
                active_count += 1

            task_done_called = False
            try:
                with stats_lock:
                    if item_url in visited or len(visited) >= max_links:
                        continue
                    visited.add(item_url)

                ext = Path(urlparse(item_url).path).suffix.lower()
                is_html = not ext or ext in DESIRED_EXTENSIONS['html']

                try:
                    resp = session.get(item_url, timeout=CONFIG["request_timeout"])
                except Exception as e:
                    with stats_lock:
                        failed[item_url] = str(e)[:60]
                    q.task_done()
                    task_done_called = True
                    continue

                if resp.status_code != 200:
                    with stats_lock:
                        failed[item_url] = f"HTTP {resp.status_code}"
                    q.task_done()
                    task_done_called = True
                    continue

                content = resp.content
                size = len(content)
                filepath = url_to_path(item_url)

                with stats_lock:
                    downloaded.add(item_url)
                    total_size += size

                save_file(content, filepath)
                print(f"  {Gr}[+] {len(downloaded)}. {filepath.relative_to(out_dir)} ({size/1024:.1f}KB){RS}")

                if is_html and (max_depth == 0 or depth < max_depth):
                    try:
                        html_text = content.decode('utf-8', errors='replace')
                        links = extract_links(html_text, item_url)
                        for lk in links:
                            lk_parsed = urlparse(lk)
                            if lk_parsed.netloc == domain and lk not in visited:
                                q.put((lk, depth + 1))
                    except:
                        pass

                q.task_done()
                task_done_called = True

            except Exception as e:
                print(f"{R}[!] Worker error: {e}{RS}")
                if not task_done_called:
                    q.task_done()
            finally:
                with active_lock:
                    active_count -= 1

    q.put((url, 0))
    num_workers = min(CONFIG["max_threads"], 15)
    workers = []
    for _ in range(num_workers):
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        workers.append(t)

    try:
        q.join()
    except KeyboardInterrupt:
        print(f"\n{Y}[!] Interrupted, stopping...{RS}")
        stop_workers = True
    
    for w in workers:
        w.join(timeout=2)

    elapsed = time.time() - start_time
    print(f"\n {Wh}{'='*50}")
    print(f" {Gr}DOWNLOAD COMPLETE")
    print(f" {Wh}{'='*50}")
    print(f"{Wh} Files Downloaded: {Gr}{len(downloaded)}")
    print(f"{Wh} Failed:           {R}{len(failed)}")
    print(f"{Wh} Total Size:       {Gr}{total_size/1024/1024:.2f} MB")
    print(f"{Wh} Duration:         {Gr}{elapsed:.1f}s")
    print(f"{Wh} Output:           {C}{out_dir}{RS}")

    result_data = {
        "target": url,
        "domain": domain,
        "stats": {
            "downloaded": len(downloaded),
            "failed": len(failed),
            "total_size_bytes": total_size,
            "duration_seconds": elapsed,
        },
        "files": sorted(downloaded),
        "errors": failed,
    }
    result = ScanResult(
        timestamp=datetime.now().isoformat(),
        scan_type="website_download",
        target=url,
        data=result_data
    )
    save_report(result)
    input(f"\n{Wh}[+] Press Enter")


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
        risk_level = "CRITICAL 🔴"
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
    print(f" {R}🔥 ADVANCED IP ANALYSIS 🔥")
    print(f" {Wh}{'='*55}")
    
    print(f"\n{Y}[*] THREAT INTELLIGENCE & REPUTATION{Wh}")
    risk = get_ip_risk_score(ip)
    print(f" {Wh}┌─ Risk Score      : {risk['level']} ({risk['score']}/100)")
    if risk['reasons']:
        for reason in risk['reasons'][:3]:
            print(f" {Wh}│   └─ {R}⚠ {reason}{Wh}")
    
    print(f"\n{Y}[*] ENRICHED GEOLOCATION DATA{Wh}")
    advanced_geo = advanced_ip_lookup(ip)
    
    for source, data in advanced_geo.items():
        if data:
            print(f" {Wh}┌─ From {source.upper()}:")
            if 'location' in data:
                print(f" {Wh}│   ├─ Location : {Gr}{data.get('location', 'N/A')}{Wh}")
            if 'isp' in data:
                print(f" {Wh}│   ├─ ISP      : {Gr}{data.get('isp', 'N/A')}{Wh}")
            if 'asname' in data:
                print(f" {Wh}│   ├─ AS Name  : {Gr}{data.get('asname', 'N/A')}{Wh}")
            if 'mobile' in data:
                print(f" {Wh}│   ├─ Mobile   : {Gr}{'Yes' if data['mobile'] else 'No'}{Wh}")
    
    if lat and lon and lat != 'N/A' and lon != 'N/A':
        try:
            lat_f = float(lat) if isinstance(lat, (int, float)) else float(str(lat).replace(',', '.'))
            lon_f = float(lon) if isinstance(lon, (int, float)) else float(str(lon).replace(',', '.'))
            maps = create_ip_map_url(ip, lat_f, lon_f)
            print(f"\n{Y}[*] MAPS & SATELLITE VIEW{Wh}")
            for name, url in maps.items():
                print(f" {Wh}┌─ {name.replace('_', ' ').title()}:{RS}")
                print(f" {Wh}│   └─ {C}{url[:70]}...{RS}" if len(url) > 70 else f" {Wh}│   └─ {C}{url}{RS}")
        except:
            pass
    
    print(f"\n{Y}[*] NETWORK ROUTE TRACE (First 8 hops){Wh}")
    trace = trace_route_visual(ip)
    if trace:
        for i, hop in enumerate(trace[:8], 1):
            print(f" {Wh}├─ Hop {i:<2} : {Gr}{hop.get('ip', 'N/A'):<16}{Wh} [{hop.get('country', 'N/A')}, {hop.get('city', 'N/A')}]")
    else:
        print(f" {Wh}└─ {Y}Traceroute unavailable (requires system command)")
    
    print(f"\n{Y}[*] DETECTED SERVICES{Wh}")
    services = scan_ip_services(ip)
    if services:
        for port, service in services.items():
            if isinstance(service, str) and not str(port).endswith('_server'):
                print(f" {Wh}├─ Port {port:<5} : {Gr}{service}{Wh}")
                server_key = f"{port}_server"
                if server_key in services:
                    print(f" {Wh}│   └─ Server: {C}{services[server_key]}{Wh}")
    else:
        print(f" {Wh}└─ {Y}No common services detected")
    
    print(f"\n{Y}[*] WHOIS REGISTRATION DATA{Wh}")
    whois_detailed = ip_whois_detailed(ip)
    if whois_detailed:
        for key, value in list(whois_detailed.items())[:6]:
            print(f" {Wh}├─ {key.replace('_', ' ').title():<12}: {Gr}{value[:50]}{Wh}")
    else:
        print(f" {Wh}└─ {Y}Detailed WHOIS not available")
    
    print(f"\n{Y}[*] WEATHER INFORMATION{Wh}")
    weather = get_ip_weather(ip)
    if weather:
        print(f" {Wh}├─ Location    : {Gr}{weather.get('city', 'N/A')}{Wh}")
        if weather.get('conditions'):
            print(f" {Wh}├─ Conditions  : {C}{weather['conditions']}{Wh}")
        if weather.get('temperature_c'):
            print(f" {Wh}├─ Temperature : {Gr}{weather['temperature_c']}°C{Wh}")
        if weather.get('windspeed'):
            print(f" {Wh}├─ Wind        : {Gr}{weather['windspeed']} km/h{Wh}")
    
    print(f"\n{Y}[*] DEVICE FINGERPRINTING{Wh}")
    fingerprint = generate_ip_fingerprint(ip)
    if fingerprint.get('http_server'):
        print(f" {Wh}├─ HTTP Server : {Gr}{fingerprint['http_server']}{Wh}")
    if fingerprint.get('open_special_ports'):
        print(f" {Wh}├─ Special open: {Gr}{fingerprint['open_special_ports']}{Wh}")
    if fingerprint.get('ssl_issuer'):
        print(f" {Wh}├─ SSL Issuer  : {Gr}{fingerprint['ssl_issuer']}{Wh}")

original_IP_Track = IP_Track

def IP_Track_Enhanced():
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
    
    print(f"\n{Y}[?] Scan common ports? (y/n): {Wh}", end="")
    if input().lower() == 'y':
        print(f"{Wh}\n[*] Scanning ports...")
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

IP_Track = IP_Track_Enhanced


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
    print(f" {Gr}📱 PHONE NUMBER SUMMARY")
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

original_phoneGW = phoneGW

def phoneGW_Enhanced():
    print(f"\n {Wh}{'='*50}")
    print(f" {R}📱 PHONE NUMBER TRACKER (ENHANCED)")
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
    print(f" {R}📊 PHONE NUMBER INFORMATION")
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
        print(f" {R}🔗 MESSAGING DIRECT LINKS")
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
        print(f" {R}🌐 WEB SEARCH LINKS")
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

phoneGW = phoneGW_Enhanced


def check_email_breaches_advanced(email: str) -> Dict:
    """التحقق المتقدم من اختراقات البريد الإلكتروني"""
    results = {'breaches': [], 'total_breaches': 0, 'pastes': [], 'leaked_data': {}}
    
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
    print(f" {Gr}📧 EMAIL INVESTIGATION SUMMARY")
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

original_email_osint = email_osint

def email_osint_Enhanced():
    email = input(f"\n{Wh}[?] Enter email address {Gr}[e.g., user@example.com]{Wh}: {Gr}").strip()
    if not email or '@' not in email:
        print(f"{R}[!] Invalid email address!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}📧 EMAIL OSINT INVESTIGATION (ENHANCED)")
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

email_osint = email_osint_Enhanced


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


def TrackLu_Enhanced():
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
    print(f" {R}👤 RATED USERNAME TRACKING (0-100)")
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
    print(f" {R}📊 RESULTS WITH CONFIDENCE SCORES")
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

TrackLu = TrackLu_Enhanced


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


def domain_osint_Enhanced():
    domain = input(f"\n{Wh}[?] Enter domain {Gr}[e.g., example.com]{Wh}: {Gr}").strip()
    if not domain:
        print(f"{R}[!] Domain cannot be empty!")
        input(f"\n{Wh}[+{Wh}] Press Enter to continue")
        return
    
    domain = domain.lower().replace('https://', '').replace('http://', '').split('/')[0].split('?')[0]
    
    print(f"\n {Wh}{'='*50}")
    print(f" {R}🌐 DOMAIN OSINT INVESTIGATION (ENHANCED)")
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
            print(f"    {C}├─ {sub}{RS}")
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
            print(f"    {C}├─ {sim}{RS}")
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
    print(f" {R}🔗 ADDITIONAL RESOURCES")
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

domain_osint = domain_osint_Enhanced


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
                                form_data[inp_name] = 'testuser'
                            elif 'pass' in inp_name.lower() or 'pwd' in inp_name.lower():
                                form_data[inp_name] = 'testpass123'
                            elif 'email' in inp_name.lower():
                                form_data[inp_name] = 'test@example.com'
                            elif 'confirm' in inp_name.lower():
                                form_data[inp_name] = 'testpass123'
                            else:
                                form_data[inp_name] = inp_value if inp_value else 'test_' + inp_name
                
                try:
                    if method == 'POST':
                        response = session.post(action, data=form_data, timeout=15, allow_redirects=True)
                    else:
                        response = session.get(action, params=form_data, timeout=15, allow_redirects=True)
                    
                    form_file = output_dir / f"form_{i+1}_response.html"
                    with open(form_file, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    downloaded.append(str(form_file))
                    
                    for hist in response.history:
                        hist_file = output_dir / f"redirect_{len(response.history)}.html"
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


original_website_downloader = website_downloader

def website_downloader_enhanced():
    if BeautifulSoup is None:
        print(f"{R}[!] Install BeautifulSoup4: pip install beautifulsoup4{RS}")
        input(f"\n{Wh}[+] Press Enter")
        return

    print(f"\n {Wh}{'='*55}")
    print(f" {R}🌐 WEBSITE SOURCE DOWNLOADER")
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
        print(f" {Gr}✅ DOWNLOAD COMPLETE")
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

website_downloader = website_downloader_enhanced


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
    print(f" {R}🔐 DEHASHED BREACH SEARCH")
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
            print(f"\n{Wh}─── Entry #{i} ───")
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
    print(f" {R}🕵️ STEALTH BROWSER (Anti-Detection)")
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
    print(f" {R}🌑 DARK WEB OSINT")
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
    print(f" {R}📊 DARK WEB RESULTS")
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

    print(f"\n{Wh}─── Summary ───")
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
    print(f" {R}🔍 GOOGLE DORKS BUILDER")
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

    print(f"\n{Wh}─── Generated Dork ───")
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
    print(f" {R}🤖 AGENTIC AI OSINT INVESTIGATION")
    print(f" {Wh}{'='*55}")
    print(f"{Y}[!] Autonomous multi-step investigation engine{Wh}")
    print(f"{Y}[!] Starts with one input and recursively discovers everything{Wh}")

    target = input(f"\n{Wh}[+] Enter target {Gr}[email, username, phone, ip]{Wh}: {Gr}").strip()
    if not target:
        return

    print(f"\n{Wh}─── Starting investigation for: {C}{target}{RS} ───")
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
    print(f" {Gr}📊 INVESTIGATION REPORT")
    print(f" {Wh}{'='*55}")
    print(f"{Wh} Target          : {C}{target}")
    print(f"{Wh} Duration        : {Gr}{elapsed:.1f}s")
    print(f"{Wh} Depth Reached   : {Gr}{root.depth}")
    print(f"{Wh} Branches        : {Gr}{count_nodes(root)}{Wh}")

    def print_tree(node: InvestigationNode, indent: int = 0):
        prefix = "  " * indent
        icon = {"email": "📧", "username": "👤", "domain": "🌐", "ip": "🌍", "phone": "📱",
                "email_found": "📧", "phone_found": "📱", "avatar": "🖼️"}.get(node.data_type, "•")
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
    print(f" {R}📊 INVESTIGATION GRAPH")
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
    print(f" {R}🧑 AGE & GENDER DETECTION")
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

        print(f"\n{Wh}─── Results ───")
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

        print(f"\n{Wh}─── Results ───")
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
        {'num': 2, 'text': 'Phone Number Tracker', 'func': phoneGW},
        {'num': 3, 'text': 'Username Tracker', 'func': TrackLu},
        {'num': 4, 'text': 'Email OSINT', 'func': email_osint},
        {'num': 5, 'text': 'Domain OSINT', 'func': domain_osint},
        {'num': 6, 'text': 'Metadata Extractor', 'func': metadata_extractor},
        {'num': 7, 'text': 'Pastebin Search', 'func': pastebin_osint},
        {'num': 8, 'text': 'GitHub Code Search', 'func': github_osint},
        {'num': 9, 'text': 'Reverse Image Search', 'func': reverse_image},
        {'num': 10, 'text': 'Show My IP', 'func': showIP},
        {'num': 11, 'text': 'Website Downloader', 'func': website_downloader},
        {'num': 12, 'text': 'Stealth Browser', 'func': stealth_browser_menu},
        {'num': 13, 'text': 'DeHashed Breach Search', 'func': dehashed_menu},
        {'num': 14, 'text': 'Dark Web OSINT', 'func': darkweb_menu},
        {'num': 15, 'text': 'Google Dorks Builder', 'func': dork_builder_menu},
        {'num': 16, 'text': 'Agentic AI Investigation', 'func': agentic_investigation},
        {'num': 17, 'text': 'Visualization Graph', 'func': visualization_menu},
        {'num': 18, 'text': 'Age/Gender Detection', 'func': age_gender_menu},
        {'num': 0, 'text': 'Exit', 'func': exit},
    ]
    
    clear()
    run_banner()
    
    print(f"\n{Wh}╔════════════════════════════════════════╗")
    print(f"{Wh}║{C}            AVAILABLE TOOLS              {Wh}║")
    print(f"{Wh}╠════════════════════════════════════════╣")
    for opt in options:
        print(f"{Wh}║  {R}[{Gr}{opt['num']:2}{R}]{Wh}  {opt['text']:<30}║")
    print(f"{Wh}╚════════════════════════════════════════╝{RS}")
    
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
    main()

