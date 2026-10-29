"""Fetch original NASA data; never substitute synthetic data on download failure."""
import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile
from .data import SUBSETS

URL = 'https://data.nasa.gov/docs/legacy/CMAPSSData.zip'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out',type=Path,default=Path('data/raw'))
    p.add_argument('--archive',type=Path,help='Use an official archive downloaded manually')
    p.add_argument('--expected-sha256',help='Optional independently trusted archive checksum')
    a = p.parse_args()
    if a.out.exists() and any(a.out.iterdir()):
        p.error('Output must be empty; preserve original data')
    if a.archive:
        b = a.archive.read_bytes()
    else:
        with urllib.request.urlopen(URL,timeout=60) as r:
            b = r.read(50*1024*1024+1)
        if len(b) > 50*1024*1024:
            raise ValueError('Unexpectedly large archive')
    digest = hashlib.sha256(b).hexdigest()
    if a.expected_sha256 and digest != a.expected_sha256:
        raise ValueError('Archive checksum mismatch')
    wanted = {f'{kind}_{subset}.txt' for subset in SUBSETS for kind in ['train','test','RUL']}
    found = {}
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        for info in z.infolist():
            name = PurePosixPath(info.filename).name
            if name in wanted or name.lower() == 'readme.txt':
                if name in found or info.file_size > 30*1024*1024:
                    raise ValueError('Duplicate or oversized archive member')
                found[name] = z.read(info)
    if not wanted.issubset(found):
        raise ValueError('Missing expected C-MAPSS files')
    a.out.mkdir(parents=True,exist_ok=True)
    for name,content in found.items():
        (a.out/name).write_bytes(content)
    manifest = {'url':URL,'downloaded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'archive_sha256':digest,'files':{n:hashlib.sha256(v).hexdigest() for n,v in found.items()}}
    (a.out.parent/'source.json').write_text(json.dumps(manifest,indent=2))
    print(f'Saved {len(found)} original files. Archive SHA256: {digest}')


if __name__ == '__main__':
    main()
