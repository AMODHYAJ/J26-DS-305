"""Build prefixed React sources using an ignored, tool-managed npm workspace."""
from pathlib import Path
import os
import shutil
import subprocess

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
    shutil.copy2(source/'C2_TLA_package.json',work/'package.json')
    lock=source/'C2_TLA_package-lock.json'
    if lock.exists(): shutil.copy2(lock,work/'package-lock.json')
    for file in source.iterdir():
        if file.suffix in ['.jsx','.css','.html','.js']: shutil.copy2(file,work/file.name)
    subprocess.run([str(node),str(cli),'ci' if lock.exists() else 'install','--no-audit','--no-fund'],cwd=work,env=env,check=True)
    if not lock.exists(): shutil.copy2(work/'package-lock.json',lock)
    subprocess.run([str(node),str(work/'node_modules'/'vite'/'bin'/'vite.js'),'build','--config','C2_TLA_vite.config.js'],cwd=work,env=env,check=True)
    print('React build ready:',ROOT/'C2_TLA_web'/'C2_TLA_index.html')


if __name__=='__main__': main()
