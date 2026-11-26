"""Ipak Yo'li bank saytidan kurslarni o'qib rates.json ga yozadi (GitHub Actions ishlatadi)."""
import json, re, sys, datetime
from playwright.sync_api import sync_playwright

URL = 'https://ipakyulibank.uz/physical/valyuta-ayirboshlash'
KEYS = [('dollar', 'USD'), ('yevro', 'EUR'), ('iyena', 'JPY'), ('funt', 'GBP'), ('shveysariya', 'CHF'), ('rubl', 'RUB')]
TABS = [('ilova', 'Ilovada'), ('kassa', 'Kassada'), ('bankomat', 'Bankomatda')]
NUM = re.compile(r'^\d[\d\s\u00a0\u202f]*$')


def to_int(t):
    return int(re.sub(r'\D', '', t))


def parse(text):
    toks = [t.strip() for t in re.split(r'[\n\t]+', text) if t.strip()]
    out = {}
    for i, t in enumerate(toks):
        if len(t) > 32 or i + 2 >= len(toks):
            continue
        low = t.lower()
        for key, code in KEYS:
            if key in low and code not in out and NUM.match(toks[i + 1]) and NUM.match(toks[i + 2]):
                b, s = to_int(toks[i + 1]), to_int(toks[i + 2])
                if 0 < b <= s:
                    out[code] = {'b': b, 's': s}
    return out


def updated(text):
    m = re.search(r'yangilandi\s*(\d{2})\.(\d{2})\.(\d{4}),?\s*(\d{2}):(\d{2})', text, re.I)
    if m:
        d, mo, y, h, mi = m.groups()
        return f'{y}-{mo}-{d}T{h}:{mi}:00+05:00'
    tz = datetime.timezone(datetime.timedelta(hours=5))
    return datetime.datetime.now(tz).replace(microsecond=0).isoformat()


def main():
    channels, upd = {}, None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale='uz-UZ')
        page.goto(URL, wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)
        for n, (key, label) in enumerate(TABS):
            try:
                page.get_by_text(label, exact=True).first.click(timeout=8000)
                page.wait_for_timeout(1500)
            except Exception as e:
                print('tab', label, 'bosilmadi:', e)
                if n > 0:
                    continue
            text = page.inner_text('body')
            r = parse(text)
            print(key, r)
            if 'USD' in r:
                channels[key] = r
                upd = upd or updated(text)
        browser.close()
    if not channels:
        sys.exit('kurs topilmadi')
    with open('rates.json', 'w', encoding='utf-8') as f:
        json.dump({'updated': upd, 'source': URL, 'channels': channels}, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
