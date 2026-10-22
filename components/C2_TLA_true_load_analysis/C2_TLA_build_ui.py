"""Build prefixed React sources using an ignored, tool-managed npm workspace."""
from pathlib import Path
import os
import shutil
import subprocess
import json

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def main():
    tools=REPO/'C2_TLA_tools'
    node=shutil.which('node')
    if not node:
        local=list((tools/'C2_TLA_node').glob('node-*/node.exe'))
        node=str(local[0]) if local else None
    if not node: raise SystemExit('Node.js 22.12+ or 24 is required to build the React UI. Install Node LTS, then rerun C2_TLA_launch.cmd build-ui.')
    node=Path(node).resolve()
    cli=node.parent/'node_modules'/'npm'/'bin'/'npm-cli.js'
    if not cli.exists(): raise SystemExit(f'npm CLI not found beside {node}. Install Node with npm included.')
    env=os.environ.copy(); env['PATH']=str(node.parent)+os.pathsep+env.get('PATH','')
    env['C2_TLA_WEB_OUTPUT']=str(ROOT/'C2_TLA_web')
    source=ROOT/'C2_TLA_frontend'; work=tools/'C2_TLA_react_build'
    work.mkdir(parents=True,exist_ok=True)
    package_changed=not (work/'package.json').exists() or (work/'package.json').read_bytes()!=(source/'C2_TLA_package.json').read_bytes()
    shutil.copy2(source/'C2_TLA_package.json',work/'package.json')
    lock=source/'C2_TLA_package-lock.json'
    lock_changed=lock.exists() and (not (work/'package-lock.json').exists() or (work/'package-lock.json').read_bytes()!=lock.read_bytes())
    if lock.exists(): shutil.copy2(lock,work/'package-lock.json')
    for file in source.iterdir():
        if file.suffix in ['.jsx','.css','.html','.js']: shutil.copy2(file,work/file.name)
    # Reuse current main's C3 frontend unchanged apart from local import filenames.
    c3=REPO/'components'/'gis_risk_mapper'/'frontend'/'src'
    (work/'C2_TLA_C3_App.jsx').write_text((c3/'App.jsx').read_text(encoding='utf-8').replace("'./App.css'","'./C2_TLA_C3_App.css'"),encoding='utf-8')
    shutil.copy2(c3/'App.css',work/'C2_TLA_C3_App.css')
    shutil.copy2(c3/'index.css',work/'C2_TLA_C3_index.css')
    manifest=json.loads((source/'C2_TLA_package.json').read_text())
    direct={**manifest['dependencies'],**manifest['devDependencies']}
    installed=all((work/'node_modules'/name/'package.json').exists() and json.loads((work/'node_modules'/name/'package.json').read_text())['version']==version for name,version in direct.items())
    if package_changed or lock_changed or not installed:
        operation='install' if (work/'node_modules').exists() or not lock.exists() else 'ci'
        subprocess.run([str(node),str(cli),operation,'--prefer-offline','--no-audit','--no-fund'],cwd=work,env=env,check=True)
        shutil.copy2(work/'package-lock.json',lock)
    else: print('Reusing verified installed frontend dependencies.',flush=True)
    subprocess.run([str(node),str(work/'node_modules'/'vite'/'bin'/'vite.js'),'build','--config','C2_TLA_vite.config.js'],cwd=work,env=env,check=True)
    print('React build ready:',ROOT/'C2_TLA_web'/'C2_TLA_index.html')


if __name__=='__main__': main()
