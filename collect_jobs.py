"""Collect published jobs from explicitly configured Greenhouse and Lever boards.
No CVs, user profiles, application history or secrets are read or published.
Python 3.11+; standard library only. Sample data is NOT used as live results.
"""
from __future__ import annotations
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'boards.json'
OUTPUT = ROOT / 'live-jobs.json'
UA = 'JobMatchPortfolio/0.1 (public ATS-feed reader; respectful requests)'
TAGS = re.compile(r'<[^>]+>')
SPACES = re.compile(r'\s+')
EMAIL = re.compile(r'(?<![\w.+-])([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})(?![\w.-])')
EXCLUDE_EMAIL_DOMAINS = ('example.com','example.org','test.com')

def clean(value):
    """Render ATS HTML as readable plain text, including entity-encoded markup."""
    raw=str(value or '')
    # Some providers supply HTML encoded once or twice; decode before stripping tags.
    for _ in range(3):
        decoded=html.unescape(raw)
        if decoded==raw:
            break
        raw=decoded
    raw=re.sub(r'(?i)<\s*br\s*/?\s*>|</\s*(?:p|div|li|h[1-6])\s*>', ' ', raw)
    return SPACES.sub(' ', TAGS.sub(' ', raw)).strip()

def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent':UA,'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=18) as resp:
        if resp.status != 200:
            raise RuntimeError(f'HTTP {resp.status}')
        return json.load(resp)

def validate_slug(slug):
    if not re.fullmatch(r'[A-Za-z0-9_-]{2,70}', str(slug)):
        raise ValueError('Invalid ATS slug')
    return slug

def norm_location(raw):
    """Conservative location classification; ambiguous remote means unverified."""
    loc=clean(raw).lower()
    has_spain=bool(re.search(r'\b(?:spain|españa)\b',loc))
    has_remote=bool(re.search(r'\b(?:remote|remoto|teletrabajo|work from home)\b',loc))
    if has_spain and has_remote:
        return 'remote_spain_explicit'
    if has_spain:
        return 'spain_location_check_remote'
    if has_remote or re.search(r'\b(?:worldwide|europe|emea)\b',loc):
        return 'remote_scope_unverified'
    return 'location_unverified'

def application_emails(description):
    # Only expose addresses published in vacancy text, never guess recruiter emails.
    # A published email is NOT necessarily an authorised application contact.
    found=[]
    for email in EMAIL.findall(description or ''):
        email=email.lower().rstrip('.,;:')
        if email.split('@')[-1] not in EXCLUDE_EMAIL_DOMAINS and email not in found:
            found.append(email)
    return found[:4]

def classify(text):
    s=text.lower()
    terms={'customer_operations':['customer support','customer service','customer operations','customer success','onboarding'],
           'business_operations':['operations associate','business operations','operations assistant','operations coordinator','business support'],
           'finance_support':['accounts payable','finance assistant','accounting assistant','finance operations','billing specialist'],
           'sales_operations':['sales support','sales operations','order management','crm specialist'],
           'project_support':['project assistant','project administrator','project coordinator']}
    return [key for key,words in terms.items() if any(w in s for w in words)]


# Conservative, explainable early-career indicators: not a hiring prediction.
INTERNSHIP_TITLE = re.compile(r"\b(intern(?:ship)?|pr[aá]ctic[ao]s?|becari[oa]|trainee(?:ship)?|apprentice(?:ship)?|working student|student placement|graduate programme|graduate program)\b", re.I)
SENIOR_TITLE = re.compile(r"\b(senior|sr\.?|lead|head|director|principal|staff|vice president|vp|chief|manager|architect|expert|supervisor)\b", re.I)
JUNIOR_TITLE = re.compile(r"\b(junior|jr\.?|associate|assistant|administrator|coordinator|specialist|representative|analyst|support|entry.level)\b", re.I)
YEARS_REQUIRED = re.compile(r"\b(?:minimum of |at least |requires? |required:?[ ]*)?(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\s*\+?\s*years?\s+(?:of\s+)?(?:relevant |professional |proven |hands.on |prior |work |industry )?experience\b", re.I)

def assess_early_career(title, desc):
    '''Return conservative suitability evidence, retaining uncertainty.'''
    if INTERNSHIP_TITLE.search(title):
        return 'excluded', 'Internship, trainee or placement title'
    if SENIOR_TITLE.search(title):
        return 'excluded', 'Senior/management title'
    years = [int(m.group(1)) for m in YEARS_REQUIRED.finditer(desc[:3500])]
    if years and min(years) >= 4:
        return 'excluded', f'Posting mentions {min(years)}+ years of experience; verify context'
    if years and min(years) <= 3:
        return 'worth_checking', f'Posting mentions {min(years)} years of experience; verify requirements'
    if JUNIOR_TITLE.search(title):
        return 'worth_checking', 'Early-career title; full requirements not verified'
    return 'worth_checking', 'Seniority not established from available information'

def pay_indicator(title, desc):
    '''Only a screening signal. Do not infer annual salary or employment type.'''
    txt = (title+' '+desc[:4000]).lower()
    if re.search(r'\b(unpaid|volunteer position|no compensation|sin remuneraci[oó]n|non.remunerated)\b', txt):
        return 'unpaid_indicated'
    return 'not_verified'

def normalise(provider, company, j):
    if provider=='greenhouse':
        title=clean(j.get('title')); loc=clean((j.get('location') or {}).get('name',''))
        desc=clean(j.get('content',''))
        url=j.get('absolute_url','')
        jid=str(j.get('id',''))
    else:
        title=clean(j.get('text')); loc=clean((j.get('categories') or {}).get('location',''))
        desc=clean(' '.join([str(j.get('descriptionPlain','')),str(j.get('additionalPlain','')),str(j.get('description',''))]))
        url=j.get('hostedUrl') or j.get('applyUrl') or ''
        jid=str(j.get('id',''))
    if not title or not jid or not url.startswith('https://'):
        return None
    groups=classify(title)
    fit_status, fit_reason = assess_early_career(title, desc)
    if pay_indicator(title,desc)=='unpaid_indicated':
        fit_status,fit_reason='excluded','Unpaid work indicated in posting'
    return {'id':f'{provider}:{company}:{jid}', 'company':company, 'title':title, 'location':loc,
            'location_status':norm_location(loc),'categories':groups,'early_career_status':fit_status,'early_career_reason':fit_reason,'pay_status':pay_indicator(title,desc),'seniority_hint':('senior_or_lead' if re.search(r'\b(?:senior|sr\.?|lead|head|director|manager|principal|staff)\b',title,re.I) else 'unspecified'),
            'url':url,'description_excerpt':desc[:650],
            'published_emails':application_emails(desc),
            'email_status':'found_in_posting_not_application_verified' if application_emails(desc) else 'none_found',
            'source':provider, 'last_checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}

def read_boards(config):
    out=[]
    for provider in ('greenhouse','lever'):
        for board in config.get(provider,[]):
            if isinstance(board,str): board={'slug':board,'company':board}
            slug=validate_slug(board['slug']); company=clean(board.get('company') or slug)
            yield provider,slug,company

def run():
    config=json.loads(CONFIG.read_text(encoding='utf8'))
    jobs=[]; errors=[]; succeeded=0
    for provider,slug,company in read_boards(config):
        url=(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true' if provider=='greenhouse'
             else f'https://api.lever.co/v0/postings/{slug}?mode=json')
        try:
            data=get_json(url)
            entries=data.get('jobs',[]) if provider=='greenhouse' else data
            if not isinstance(entries,list): raise ValueError('Unexpected API response')
            succeeded+=1
            for j in entries:
                item=normalise(provider,company,j)
                if item and item['categories']: jobs.append(item)
            print(f'{company}: checked {len(entries)} postings')
        except (urllib.error.URLError,TimeoutError,ValueError,RuntimeError,KeyError) as exc:
            errors.append(f'{provider}/{slug}: {type(exc).__name__}: {exc}')
            print(errors[-1],file=sys.stderr)
        time.sleep(0.4)  # moderate request rate; one request per company
    if succeeded==0:
        # Never overwrite a previously good file with an empty feed on outage/empty config.
        print('No boards fetched successfully: not replacing feed', file=sys.stderr)
        sys.exit(1)
    jobs=list({j['id']:j for j in jobs}.values())
    jobs.sort(key=lambda j:(j['company'].casefold(),j['title'].casefold()))
    output={'updated_utc':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
            'sources_checked':succeeded,'source_errors':len(errors),'jobs':jobs}
    temp=OUTPUT.with_suffix('.json.tmp')
    temp.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8')
    temp.replace(OUTPUT)
    print(f'Published {len(jobs)} relevant listings from {succeeded} boards. Source errors: {len(errors)}')
if __name__=='__main__': run()
