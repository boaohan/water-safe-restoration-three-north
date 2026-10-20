from pathlib import Path
import hashlib
root=Path(__file__).resolve().parents[1]
files=sorted(p for p in root.rglob('*') if p.is_file() and p.name!='checksums.sha256' and not any(x in p.relative_to(root).parts for x in ['.git','.venv','build','__pycache__']))
(root/'checksums.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+'\n' for p in files),encoding='utf-8')
print(f'Updated {len(files)} checksums')
