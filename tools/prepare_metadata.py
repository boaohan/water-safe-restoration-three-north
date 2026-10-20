"""Create citation metadata only from explicit author-supplied publication metadata."""
from pathlib import Path
import json, re
import yaml
root=Path(__file__).resolve().parents[1]
m=json.loads((root/'metadata/publication.json').read_text(encoding='utf-8'))
if not m['authors']:raise SystemExit('Fill authors with given-names, family-names, affiliation; optional orcid. No author was inferred from anonymized manuscripts.')
if m['license_choice']=='pending':raise SystemExit('Resolve license_choice and add the approved license texts before preparing a DOI release.')
if m['repository_url'] and not re.fullmatch(r'https://github.com/[^/]+/[^/]+/?',m['repository_url']):raise SystemExit('Use the real GitHub repository URL or leave it empty until created.')
for a in m['authors']:
    if not a.get('given-names') or not a.get('family-names'):raise SystemExit('Each author needs given-names and family-names.')
    if a.get('orcid') and not re.fullmatch(r'https://orcid.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]',a['orcid']):raise SystemExit('Use the full https://orcid.org/ ORCID URL.')
if not (root/'LICENSE').exists() and not (root/'LICENSES').is_dir():raise SystemExit('Add the approved LICENSE or LICENSES/ texts first; this tool does not grant rights.')
c={'cff-version':'1.2.0','message':'If you use this research companion, please cite this archive. Code: MIT; data and figures: CC BY 4.0. See LICENSE for scope.','type':'software','title':m['title'],'version':m['version'],'authors':m['authors'],'abstract':m['abstract'],'keywords':m['keywords'],'license':['MIT','CC-BY-4.0']}
if m['repository_url']:c['repository-code']=m['repository_url']
if m.get('publication_date'):c['date-released']=m['publication_date']
if m.get('archive_doi'):
    doi=m['archive_doi'].removeprefix('https://doi.org/')
    if not re.fullmatch(r'10\.\d{4,9}/\S+',doi):raise SystemExit('Invalid archive DOI syntax; use only the DOI assigned by the archive.')
    c['doi']=doi
# The two identifiers apply to separate materials as specified in LICENSE.
(root/'CITATION.cff').write_text(yaml.safe_dump(c,allow_unicode=True,sort_keys=False),encoding='utf-8')
print('Created CITATION.cff. Run cffconvert --validate before release; verify the Zenodo record license separately.')
