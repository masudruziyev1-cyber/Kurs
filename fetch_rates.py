"""Ipak Yo'li kurslarini o'qiydi va rates.json ga yozadi."""
import json, re, sys, os, datetime
from playwright.sync_api import sync_playwright

URL = 'https://ipakyulibank.uz/physical/valyuta-ayirboshlash'
TABS = {'ilova': 'Ilovada', 'kassa': 'Kassada', 'bankomat': 'Bankomatda'}
KEYS = {
    'USD': ['dollar'], 'EUR': ['yevro', 'evro'], 'JPY': ['iyena', 'yena'],
    'GBP': ['funt'], 'CHF': ['shveysariya', 'frank'], 'RUB': ['rubl'],
}
NUM = re.compile(r'^\d[\d\s\u00a0\u202f]*$')
DEBUG = 'debug'


def to_int(t):
    return int(re.sub(r'\D', '', t))


def parse(text):
    toks = [t.strip() for t in re.split(r'[\n\t]+', text) if t.strip()]
    out = {}
    for i, t in enumerate(toks):
        low = t.lower()
        if len(t) > 40 or i + 2 >= len(toks):
            continue
        for code, words in KEYS.items():
            if code in out or not any(w in low for w in words):
                continue
            if NUM.match(toks[i + 1]) and NUM.match(toks[i + 2]):
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


def click_tab(page, label):
    for loc in (page.get_by_role('button', name=label, exact=True),
                page.get_by_text(label, exact=True)):
        try:
            loc.first.click(timeout=8000)
            page.wait_for_timeout(1500)
            return True
        except Exception:
            continue
    return False


def main():
    os.makedirs(DEBUG, exist_ok=True)
    old = {}
    if os.path.exists('rates.json'):
        with open('rates.json', encoding='utf-8') as f:
            old = json.load(f)
    channels = dict(old.get('channels', {}))
    upd = None

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale='uz-UZ')
        page.goto(URL, wait_until='domcontentloaded', timeout=90000)
        page.wait_for_load_state('networkidle', timeout=60000)
        page.wait_for_timeout(3000)
        page.screenshot(path=f'{DEBUG}/start.png', full_page=True)

        for key, label in TABS.items():
            ok = click_tab(page, label)
            text = page.inner_text('body')
            with open(f'{DEBUG}/{key}.txt', 'w', encoding='utf-8') as f:
                f.write(text)
            r = parse(text)
            print(key, 'tab:', ok, 'parsed:', r)
            if 'USD' in r:
                channels[key] = r
                upd = upd or updated(text)
            if not ok or 'USD' not in r:
                page.screenshot(path=f'{DEBUG}/{key}_fail.png', full_page=True)
        browser.close()

    if not any('USD' in c for c in channels.values()):
        sys.exit('Kurs topilmadi. debug/ papkasini tekshiring.')

    with open('rates.json', 'w', encoding='utf-8') as f:
        json.dump({'updated': upd or old.get('updated'), 'source': URL,
                   'channels': channels}, f, ensure_ascii=False, indent=1)
    print('saqlandi:', upd)


if __name__ == '__main__':
    main()
