import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin
import hashlib
import re
from datetime import datetime

URL = "https://www.city.fukuyama.hiroshima.jp/site/koureisha-shien/276499.html"

OUTPUT = Path(__file__).parent / "fukuyama_kaigo.xml"

# 福山市のページを取得
response = requests.get(URL, timeout=30)
response.raise_for_status()
response.encoding = response.apparent_encoding

soup = BeautifulSoup(response.text, "html.parser")

# ページ内からPDFを探す
pdf_url = None

for a in soup.find_all("a", href=True):
    href = a["href"]

    if ".pdf" in href.lower():
        pdf_url = urljoin(URL, href)
        break

if not pdf_url:
    raise Exception("PDFが見つかりませんでした")

# ページ本文から「2026年10月1日更新」のような更新日を取得
page_text = soup.get_text(" ", strip=True)

date_match = re.search(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日更新",
    page_text
)

if date_match:
    year = int(date_match.group(1))
    month = int(date_match.group(2))
    day = int(date_match.group(3))
    update_date = f"{year}-{month:02d}-{day:02d}"
    display_date = f"{year}年{month}月{day}日"
else:
    update_date = datetime.now().strftime("%Y-%m-%d")
    display_date = update_date

# PDF URLを固有IDにする
guid = hashlib.sha256(pdf_url.encode("utf-8")).hexdigest()

new_item = {
    "title": f"新規・廃止・変更事業所一覧（{display_date}）",
    "description": f"福山市介護保険課　{display_date}更新",
    "link": pdf_url,
    "date": update_date,
    "guid": guid
}

# 以前のRSSを読み込む
old_items = []

if OUTPUT.exists():
    try:
        old_tree = ET.parse(OUTPUT)
        old_root = old_tree.getroot()

        for item in old_root.findall("./channel/item"):
            old_items.append({
                "title": item.findtext("title", ""),
                "description": item.findtext("description", ""),
                "link": item.findtext("link", ""),
                "date": item.findtext("pubDate", ""),
                "guid": item.findtext("guid", "")
            })
    except Exception:
        old_items = []

# 新しいもの＋過去分を合体して重複除去
all_items = []
seen = set()

for item in [new_item] + old_items:
    if item["guid"] in seen:
        continue

    seen.add(item["guid"])
    all_items.append(item)

# 過去60件まで保存
all_items = all_items[:60]

# RSS作成
rss = ET.Element("rss", version="2.0")
channel = ET.SubElement(rss, "channel")

ET.SubElement(channel, "title").text = "福山市 新規・廃止・変更事業所一覧"
ET.SubElement(channel, "link").text = URL
ET.SubElement(channel, "description").text = "福山市介護保険課が公表する新規・廃止・変更事業所一覧"
ET.SubElement(channel, "language").text = "ja"

for item in all_items:
    element = ET.SubElement(channel, "item")

    ET.SubElement(element, "title").text = item["title"]
    ET.SubElement(element, "link").text = item["link"]
    ET.SubElement(element, "description").text = item["description"]
    ET.SubElement(element, "pubDate").text = item["date"]

    guid_element = ET.SubElement(element, "guid")
    guid_element.set("isPermaLink", "false")
    guid_element.text = item["guid"]

tree = ET.ElementTree(rss)
ET.indent(tree, space="  ")

tree.write(
    OUTPUT,
    encoding="utf-8",
    xml_declaration=True
)

print("RSS作成成功")
print("タイトル:", new_item["title"])
print("PDF:", pdf_url)
print("RSS保存件数:", len(all_items))
print("保存先:", OUTPUT)