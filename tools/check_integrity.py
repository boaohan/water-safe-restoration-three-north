from pathlib import Path
import hashlib
root=Path(__file__).resolve().parents[1]
bad=[];count=0
for line in (root/'checksums.sha256').read_text(encoding='utf-8').splitlines():
    digest,name=line.split('  ',1);p=root/name;count+=1
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:bad.append(name)
if bad:raise SystemExit('Changed or missing files: '+str(bad))
print(f'PASS: {count} SHA-256 checksums')
