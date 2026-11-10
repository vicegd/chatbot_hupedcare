import csv, json, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

proposed, raw_dir, out_path = sys.argv[1:4]
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
UA = {"User-Agent": "huped-corpus-check/1.0"}
EXTRA = ["PMC7507957"]


def post(endpoint, params):
    data = urllib.parse.urlencode({**params, "tool": "huped_corpus_check"}).encode()
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(EUTILS + endpoint, data=data, headers=UA), timeout=180) as r:
                return r.read()
        except Exception:
            time.sleep(2 ** attempt)
    raise RuntimeError(endpoint)


rows = list(csv.DictReader(open(proposed, encoding="utf-8")))
wanted = sorted({r["pmcid"] for r in rows} | set(EXTRA))
os.makedirs(raw_dir, exist_ok=True)
meta = {}
for start in range(0, len(wanted), 30):
    batch = [p.replace("PMC", "") for p in wanted[start:start + 30]]
    root = ET.fromstring(post("efetch.fcgi", {"db": "pmc", "id": ",".join(batch), "retmode": "xml"}))
    for article in root.iter("article"):
        ids = {a.get("pub-id-type"): a.text for a in article.findall("front/article-meta/article-id")}
        pmcid = ids.get("pmc") or ids.get("pmcid")
        pmcid = pmcid if pmcid.startswith("PMC") else "PMC" + pmcid
        with open(os.path.join(raw_dir, pmcid + ".xml"), "wb") as handle:
            handle.write(ET.tostring(article, encoding="utf-8"))
        title = " ".join("".join(article.find("front/article-meta/title-group/article-title").itertext()).split())
        licences = sorted({v for lic in article.find("front/article-meta").iter("license") for x in lic.iter() for k, v in x.attrib.items() if k.endswith("href") and "creativecommons" in v}
                          | {(x.text or "").strip() for lic in article.find("front/article-meta").iter("license") for x in lic if x.tag.endswith("license_ref") and "creativecommons" in (x.text or "")})
        meta[pmcid] = {"pmid": ids.get("pmid"), "doi": ids.get("doi"), "title": title, "licences": licences}
    time.sleep(0.5)
    print("xml", start + len(batch), flush=True)

pmids = [m["pmid"] for m in meta.values() if m["pmid"]]
flags = {}
for start in range(0, len(pmids), 100):
    root = ET.fromstring(post("efetch.fcgi", {"db": "pubmed", "id": ",".join(pmids[start:start + 100]), "retmode": "xml"}))
    for item in root.iter("PubmedArticle"):
        pmid = item.findtext("MedlineCitation/PMID")
        types = [t.text for t in item.iter("PublicationType")]
        refs = [c.get("RefType") for c in item.iter("CommentsCorrections")]
        flags[pmid] = {"types": types, "refs": sorted(set(refs))}
    time.sleep(0.5)

BAD_PUBMED = {"Retracted Publication", "Retraction of Publication", "Expression of Concern"}
BAD_REFS = {"RetractionIn", "RetractionOf", "ExpressionOfConcernIn", "ErratumIn", "CorrectionIn"}
for pmcid, m in meta.items():
    f = flags.get(m["pmid"] or "", {})
    m["pubmed_found"] = bool(f)
    m["pubmed_flags"] = sorted((set(f.get("types", [])) & BAD_PUBMED) | (set(f.get("refs", [])) & BAD_REFS))
    m["crossref"] = None
    if m["doi"]:
        url = "https://api.crossref.org/works/" + urllib.parse.quote(m["doi"], safe="")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                msg = json.load(r)["message"]
            m["crossref"] = sorted({u.get("type", "") for u in msg.get("updated-by", [])})
        except Exception as error:
            m["crossref"] = f"error {type(error).__name__}"
        time.sleep(0.2)

with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(meta, handle, indent=1, ensure_ascii=False)
print("articles", len(meta), "of", len(wanted), "missing", sorted(set(wanted) - set(meta)))
print("no pubmed record", [p for p, m in meta.items() if not m["pubmed_found"]])
print("crossref errors", [p for p, m in meta.items() if isinstance(m["crossref"], str)])
print("not CC BY", [(p, m["licences"]) for p, m in meta.items() if not m["licences"] or not all(re.search(r"licenses/by/\d", l) for l in m["licences"])])
print("pubmed flags", {p: m["pubmed_flags"] for p, m in meta.items() if m["pubmed_flags"]})
print("crossref updates", {p: m["crossref"] for p, m in meta.items() if m["crossref"] and not isinstance(m["crossref"], str)})
print("duplicate titles", len(meta) - len({m["title"].lower() for m in meta.values()}))
for p, m in sorted(meta.items()):
    print(p, "|", m["title"][:130])
