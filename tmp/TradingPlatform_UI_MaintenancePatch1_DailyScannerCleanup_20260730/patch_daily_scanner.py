#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, shutil, sys
from pathlib import Path

TARGET_PANEL = "Market Ingestion"
TARGET_CONTROL = "Run governed ingestion before scanning"
EXTS = {".tsx", ".jsx", ".ts", ".js"}

TAG_TOKEN = re.compile(r"</?([A-Za-z][A-Za-z0-9_.:-]*)(?:\s[^<>]*?)?/?>", re.S)

def matching_element(text: str, pos: int, preferred: tuple[str, ...], require_hint: str | None = None):
    candidates=[]
    for m in TAG_TOKEN.finditer(text, 0, pos+1):
        if m.group(0).startswith('</') or m.group(0).endswith('/>'):
            continue
        tag=m.group(1)
        if tag not in preferred:
            continue
        if require_hint and require_hint.lower() not in m.group(0).lower():
            continue
        candidates.append(m)
    for start in reversed(candidates):
        tag=start.group(1); depth=0
        token_re=re.compile(rf"</?{re.escape(tag)}(?:\s[^<>]*?)?/?>", re.S)
        for tok in token_re.finditer(text, start.start()):
            raw=tok.group(0)
            if raw.startswith(f"</{tag}"):
                depth-=1
                if depth==0:
                    end=tok.end()
                    if start.start() <= pos <= end:
                        return start.start(), end
                    break
            elif not raw.endswith('/>'):
                depth+=1
    return None

def remove_containing(text: str, phrase: str, kind: str):
    changed=0
    while phrase.lower() in text.lower():
        pos=text.lower().find(phrase.lower())
        span=None
        if kind=="control":
            span=matching_element(text,pos,("label",)) or matching_element(text,pos,("div","section"),"control")
        else:
            span=(matching_element(text,pos,("section","article","div"),"ingestion")
                  or matching_element(text,pos,("section","article"))
                  or matching_element(text,pos,("div",)))
        if not span:
            raise RuntimeError(f"Could not safely identify JSX container for {phrase!r}")
        a,b=span
        while a>0 and text[a-1] in ' \t': a-=1
        if a>0 and text[a-1]=='\n': a-=1
        while b<len(text) and text[b] in ' \t': b+=1
        if b<len(text) and text[b]=='\n': b+=1
        text=text[:a]+text[b:]
        changed+=1
    return text,changed

def candidate_files(src: Path):
    for p in src.rglob('*'):
        if p.is_file() and p.suffix in EXTS and 'node_modules' not in p.parts and 'dist' not in p.parts:
            try: txt=p.read_text(encoding='utf-8')
            except UnicodeDecodeError: continue
            if TARGET_PANEL.lower() in txt.lower() or TARGET_CONTROL.lower() in txt.lower():
                yield p,txt

def apply(root: Path, backup_root: Path):
    src=root/'ui'/'workstation'/'src'
    if not src.is_dir():
        raise SystemExit(f"Missing workstation source directory: {src}")
    found=list(candidate_files(src))
    if not found:
        # Idempotent success if both phrases are already absent.
        print('Daily Scanner cleanup already applied; no target strings found.')
        return []
    changed=[]
    for path,text in found:
        new=text; counts={}
        if TARGET_CONTROL.lower() in new.lower():
            new,n=remove_containing(new,TARGET_CONTROL,'control'); counts['control']=n
        if TARGET_PANEL.lower() in new.lower():
            new,n=remove_containing(new,TARGET_PANEL,'panel'); counts['panel']=n
        if new!=text:
            rel=path.relative_to(root)
            backup=backup_root/rel
            backup.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,backup)
            path.write_text(new,encoding='utf-8')
            changed.append({'file':str(rel),'removed':counts})
    # Global postcondition: target UI strings absent from workstation source.
    leftovers=[]
    for p,txt in candidate_files(src):
        leftovers.append(str(p.relative_to(root)))
    if leftovers:
        raise RuntimeError('Cleanup incomplete; target strings remain in: '+', '.join(leftovers))
    return changed

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('root',type=Path)
    ap.add_argument('--backup-root',type=Path,required=True)
    args=ap.parse_args()
    root=args.root.resolve(); backup=args.backup_root.resolve()
    backup.mkdir(parents=True,exist_ok=True)
    changed=apply(root,backup)
    (backup/'manifest.json').write_text(json.dumps(changed,indent=2),encoding='utf-8')
    print(json.dumps({'status':'APPLIED','changed':changed},indent=2))
if __name__=='__main__': main()
