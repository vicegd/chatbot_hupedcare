import csv, json, re, sys, time, urllib.parse, urllib.request, collections
import xml.etree.ElementTree as ET

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
TOOL = "huped_corpus_survey"
TERM = ('(pediatric[Title] OR paediatric[Title] OR children[Title] OR child[Title] OR neonatal[Title] OR neonates[Title] '
        'OR newborns[Title] OR infants[Title] OR adolescents[Title]) AND pain[Title] AND (review[Title] OR guideline[Title] '
        'OR guidelines[Title] OR recommendations[Title] OR management[Title] OR assessment[Title]) '
        'AND "cc by license"[filter] AND 2015:2026[pdat]')
OUT = sys.argv[1]
EXCLUDE = re.compile(r"protocol for|study protocol|case report|case series|erratum|correction|retract|corrigendum|veterinar|\brats?\b|\bmice\b", re.I)
TOPICS = [
    ("neonatal", r"neonat|newborn|preterm|infant"),
    ("procedural", r"procedur|needle|venipuncture|vaccin|immuni[sz]ation|emergency"),
    ("postoperative", r"post-?operative|surgery|surgical|tonsillectomy|perioperative"),
    ("cancer_palliative", r"cancer|oncolog|palliative|life-limiting|sickle"),
    ("chronic", r"chronic|persistent|functional|migraine|headache|musculoskeletal|abdominal"),
    ("assessment", r"assess|scale|measure|tool"),
    ("non_pharmacological", r"non-?pharmacolog|distraction|music|virtual reality|psycholog|cognitive|massage|parent|family"),
    ("pharmacological", r"analges|opioid|ibuprofen|paracetamol|acetaminophen|ketamine|pharmacolog|dexmedetomidine"),
]


def get(endpoint, params):
    params = {**params, "tool": TOOL}
    data = urllib.parse.urlencode(params).encode()
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(BASE + endpoint, data=data), timeout=120) as r:
                return r.read()
        except Exception:
            time.sleep(2 ** attempt)
    raise RuntimeError(endpoint)


ids = json.loads(get("esearch.fcgi", {"db": "pmc", "term": TERM, "retmode": "json", "retmax": 1000}))["esearchresult"]["idlist"]
print("search hits", len(ids), flush=True)
rows, reasons = [], collections.Counter()
for start in range(0, len(ids), 40):
    batch = ids[start:start + 40]
    root = ET.fromstring(get("efetch.fcgi", {"db": "pmc", "id": ",".join(batch), "retmode": "xml"}))
    for article in root.iter("article"):
        meta = article.find("front/article-meta")
        if meta is None:
            reasons["no metadata"] += 1
            continue
        title = " ".join("".join(meta.find("title-group/article-title").itertext()).split())
        ids_found = {a.get("pub-id-type"): a.text for a in meta.findall("article-id")}
        licenses = []
        for lic in meta.iter("license"):
            licenses += [v for k, v in lic.attrib.items() if k.endswith("href")]
            licenses += [(x.text or "") for x in lic if x.tag.endswith("license_ref")]
            licenses += [v for x in lic.iter("ext-link") for k, v in x.attrib.items() if k.endswith("href")]
        cc = sorted({l.strip() for l in licenses if "creativecommons.org" in l})
        body = article.find("body")
        words = len(" ".join(body.itertext()).split()) if body is not None else 0
        journal = (article.findtext("front/journal-meta/journal-title-group/journal-title") or "").strip()
        years = [p.findtext("year") for p in meta.findall("pub-date") if p.findtext("year")]
        kind = article.get("article-type", "")
        topics = [name for name, pattern in TOPICS if re.search(pattern, title, re.I)]
        if EXCLUDE.search(title):
            status = "excluded title"
        elif not cc or not all(re.search(r"licenses/by/\d", l) for l in cc):
            status = "licence not CC BY"
        elif words < 1500:
            status = "no full text"
        elif kind not in ("review-article", "research-article", "systematic-review", "practice-guideline", "other"):
            status = "article type"
        else:
            status = "ok"
        reasons[status] += 1
        rows.append({"status": status, "pmcid": ids_found.get("pmc") or ids_found.get("pmcid") or "", "doi": ids_found.get("doi", ""),
                     "year": max(years) if years else "", "kind": kind, "words": words, "journal": journal,
                     "topics": ";".join(topics), "license": " ".join(cc), "title": title})
    time.sleep(0.5)
    print(start + len(batch), flush=True)

with open(OUT, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
ok = [r for r in rows if r["status"] == "ok"]
print("reasons", dict(reasons))
print("ok", len(ok), "words", sum(r["words"] for r in ok))
print("kinds", collections.Counter(r["kind"] for r in ok))
print("topics", collections.Counter(t for r in ok for t in r["topics"].split(";") if t), "untagged", sum(not r["topics"] for r in ok))
print("years", sorted(collections.Counter(r["year"] for r in ok).items()))
print("licences", collections.Counter(re.sub(r"https?://(www\.)?", "", r["license"]) for r in ok).most_common(6))
print("journals", collections.Counter(r["journal"] for r in ok).most_common(10))
print("guideline-like:")
for r in ok:
    if re.search(r"guideline|recommendation|consensus|position|standard", r["title"], re.I):
        print(" ", r["pmcid"], r["year"], r["journal"][:30], "|", r["title"][:120])
