"""Build a standalone Word report from reviewed Markdown and saved experiment evidence.

Uses only Python's standard library plus already-installed Pillow for figure dimensions.
No private customer records or raw input files are embedded.
"""
from pathlib import Path
import json
import re
import zipfile
from xml.sax.saxutils import escape
from xml.etree import ElementTree as ET
from PIL import Image

DOCS=Path(__file__).resolve().parent
ROOT=DOCS.parent
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS=f'xmlns:w="{W}" xmlns:r="{R}"'

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])

def resolve_evidence(source):
    local=json.loads((ROOT/'C2_TLA_models'/'C2_TLA_evaluation.json').read_text(encoding='utf-8'))
    demo=json.loads((ROOT/'C2_TLA_demo'/'C2_TLA_evaluation.json').read_text(encoding='utf-8'))
    def benchmarks(ev):
        rows=[]
        for name,value in ev['benchmarks'].items():
            m=value['overall']
            rows.append([name.replace('_',' '),f"{m['mae_mw']:.4f}",f"{m['rmse_mw']:.4f}",f"{m['r2']:.4f}",f"{m['mape_pct']:.3f}",f"{m['daily_peak_magnitude_recovery_pct']:.2f}",f"{m['daily_peak_timing_mae_minutes']:.2f}",m['n']])
        return table(['Method','MAE MW','RMSE MW','R²','MAPE %','Peak recovery %','Timing MAE min','n'],rows)
    source=source.replace('{{LOCAL_BENCHMARKS}}',benchmarks(local)).replace('{{DEMO_BENCHMARKS}}',benchmarks(demo))
    rows=[]
    for f,m in local['benchmarks']['xgboost']['by_feeder'].items():
        rows.append([f,f"{m['mae_mw']:.4f}",f"{m['rmse_mw']:.4f}",f"{m['r2']:.4f}",f"{m['mape_pct']:.3f}",m['n']])
    source=source.replace('{{FEEDER_METRICS}}',table(['Synthetic feeder','MAE MW','RMSE MW','R²','MAPE %','n'],rows))
    rows=[]
    for name,m in local['scenarios'].items():
        rows.append([name.replace('_',' '),f"{m['mae_mw']:.4f}",f"{m['rmse_mw']:.4f}",f"{m['r2']:.4f}",f"{m['mape_pct']:.3f}",m['n']])
    source=source.replace('{{SCENARIO_METRICS}}',table(['Scenario subset','MAE MW','RMSE MW','R²','MAPE %','n'],rows))
    import csv
    with (ROOT/'C2_TLA_outputs'/'C2_TLA_global_shap.csv').open(encoding='utf-8',newline='') as file:
        rows=[[r[0],f'{float(r[1]):.6f}'] for r in list(csv.reader(file))[1:]]
    return source.replace('{{SHAP_TABLE}}',table(['Feature','Mean absolute SHAP, MW'],rows))

def run(text,bold=False):
    props='<w:rPr><w:b/></w:rPr>' if bold else ''
    return f'<w:r>{props}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'

def para(text='',style='Normal',extra=''):
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{extra}</w:pPr>{run(text)}</w:p>'

def xml_table(lines):
    rows=[[c.strip() for c in line.strip().strip('|').split('|')] for line in lines]
    rows=[row for i,row in enumerate(rows) if i!=1]
    cols=len(rows[0]); total=9700
    # Keep metric columns compact while allowing method names to wrap cleanly.
    widths=([1850]+[(total-1850)//(cols-1)]*(cols-1)) if cols>=6 else [total//cols]*cols
    body=[]
    for index,row in enumerate(rows):
        cells=[]
        for i,value in enumerate(row):
            shade='173C3A' if index==0 else ('F0F5F3' if index%2 else 'FFFFFF')
            textprops='<w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>' if index==0 else '<w:rPr><w:color w:val="223432"/></w:rPr>'
            p=f'<w:p><w:pPr><w:pStyle w:val="TableText"/></w:pPr><w:r>{textprops}<w:t xml:space="preserve">{escape(value)}</w:t></w:r></w:p>'
            cells.append(f'<w:tc><w:tcPr><w:tcW w:w="{widths[i]}" w:type="dxa"/><w:shd w:fill="{shade}"/><w:vAlign w:val="top"/></w:tcPr>{p}</w:tc>')
        header='<w:tblHeader/>' if index==0 else ''
        body.append('<w:tr><w:trPr><w:cantSplit/>'+header+'</w:trPr>'+''.join(cells)+'</w:tr>')
    grid=''.join(f'<w:gridCol w:w="{v}"/>' for v in widths)
    props='<w:tblPr><w:tblW w:w="9700" w:type="dxa"/><w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="85" w:type="dxa"/><w:left w:w="90" w:type="dxa"/><w:bottom w:w="85" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tblCellMar><w:tblBorders><w:bottom w:val="single" w:sz="4" w:color="D8E4DF"/><w:insideH w:val="single" w:sz="4" w:color="D8E4DF"/></w:tblBorders></w:tblPr>'
    return '<w:tbl>'+props+'<w:tblGrid>'+grid+'</w:tblGrid>'+''.join(body)+'</w:tbl>'+para('',extra='<w:spacing w:after="30"/>')

def image_xml(path,rid,index):
    with Image.open(path) as im: width,height=im.size
    cx=6150000; cy=int(cx*height/width)
    if cy>6600000: cx=int(cx*6600000/cy);cy=6600000
    name=escape(path.name)
    return f'''<w:p><w:pPr><w:jc w:val="center"/><w:keepNext/></w:pPr><w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{index}" name="{name}"/><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="0" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''

STYLES=f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="21"/><w:color w:val="243632"/><w:lang w:val="en-GB"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="110" w:line="266" w:lineRule="auto"/><w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="1700" w:after="260"/></w:pPr><w:rPr><w:b/><w:sz w:val="64"/><w:color w:val="173C3A"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="360"/></w:pPr><w:rPr><w:sz w:val="30"/><w:color w:val="55796E"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="300" w:after="160"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="173C3A"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="220" w:after="110"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="25"/><w:color w:val="286053"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="Table text"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="25" w:line="230" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="17"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="20" w:line="230" w:lineRule="auto"/><w:shd w:fill="F0F5F3"/><w:ind w:left="140" w:right="140"/></w:pPr><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="16"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="Caption"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="180"/><w:jc w:val="center"/></w:pPr><w:rPr><w:i/><w:sz w:val="18"/><w:color w:val="55796E"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Footer"><w:name w:val="Footer"/><w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="16"/><w:color w:val="55796E"/></w:rPr></w:style>
</w:styles>'''

def build():
    sourcefile=DOCS/'C2_TLA_research_report.md'
    source=resolve_evidence(sourcefile.read_text(encoding='utf-8'))
    if '{{' in source: raise ValueError('Unresolved evidence placeholder')
    sourcefile.write_text(source,encoding='utf-8')
    lines=source.splitlines(); body=[]; relationships=[('rIdStyles','styles','styles.xml'),('rIdHeader','header','header1.xml'),('rIdFooter','footer','footer1.xml')]; media=[]
    relationships.append(('rIdSettings','settings','settings.xml'))
    i=0; first_subtitle=True
    while i<len(lines):
        line=lines[i]
        if not line.strip(): i+=1;continue
        if line.startswith('```'):
            i+=1
            while i<len(lines) and not lines[i].startswith('```'):
                body.append(para(lines[i],style='Code'));i+=1
            body.append(para(''));i+=1;continue
        if line.startswith('|'):
            block=[]
            while i<len(lines) and lines[i].startswith('|'):block.append(lines[i]);i+=1
            body.append(xml_table(block));continue
        match=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',line)
        if match:
            path=DOCS/match[2];n=len(media)+1;rid=f'rIdImage{n}'
            if not path.is_file():raise FileNotFoundError(path)
            media.append(path);relationships.append((rid,'image',f'media/{path.name}'))
            body.extend([image_xml(path,rid,n),para(match[1],style='Caption')]);i+=1;continue
        if line.startswith('# '):body.append(para(line[2:],style='Title'))
        elif line.startswith('## '):
            if first_subtitle:
                body.append(para(line[3:],style='Subtitle'));first_subtitle=False
            else:
                # Start the substantive report after its cover and guide.
                extra='<w:pageBreakBefore/>' if line.startswith('## 1.') else ''
                body.append(para(line[3:],style='Heading1',extra=extra))
        elif line.startswith('### '):body.append(para(line[4:],style='Heading2'))
        else:body.append(para(line))
        i+=1
    section='<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1050" w:right="1100" w:bottom="1050" w:left="1100" w:header="450" w:footer="450"/><w:titlePg/></w:sectPr>'
    document=f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {NS}><w:body>'+''.join(body)+section+'</w:body></w:document>'
    relns='http://schemas.openxmlformats.org/package/2006/relationships'
    rels=f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{relns}">'+''.join(f'<Relationship Id="{rid}" Type="{R}/{kind}" Target="{target}"/>' for rid,kind,target in relationships)+'</Relationships>'
    contenttypes='''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/><Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>'''
    package_rels=f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{relns}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>'
    header=f'<?xml version="1.0" encoding="UTF-8"?><w:hdr {NS}>'+para('SOLAVERA   /   COMPONENT 02                                      RESEARCH IMPLEMENTATION REPORT',style='Footer')+'</w:hdr>'
    footer=f'''<?xml version="1.0" encoding="UTF-8"?><w:ftr {NS}><w:p><w:pPr><w:pStyle w:val="Footer"/><w:jc w:val="right"/></w:pPr>{run('True Load Analysis  |  22 October 2026  |  ')}<w:fldSimple w:instr="PAGE"/>{run(' / ')}<w:fldSimple w:instr="NUMPAGES"/></w:p></w:ftr>'''
    settings=f'<?xml version="1.0" encoding="UTF-8"?><w:settings xmlns:w="{W}"><w:defaultTabStop w:val="720"/><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>'
    core='''<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>True Load Analysis — Component 2 research implementation report</dc:title><dc:creator>Vinuki Charithma</dc:creator><dc:subject>CEB evidence, synthetic experiments, models, evaluation, dashboard and integration</dc:subject><dc:description>Software baseline d4307b8; prepared 22 October 2026; synthetic scores are not field accuracy.</dc:description></cp:coreProperties>'''
    files={'[Content_Types].xml':contenttypes,'_rels/.rels':package_rels,'word/document.xml':document,'word/styles.xml':STYLES,'word/_rels/document.xml.rels':rels,'word/header1.xml':header,'word/footer1.xml':footer,'word/settings.xml':settings,'docProps/core.xml':core}
    target=DOCS/'C2_TLA_Research_Implementation_Report.docx'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,content in files.items():ET.fromstring(content);archive.writestr(name,content)
        for path in media:archive.write(path,f'word/media/{path.name}')
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            if name.endswith(('.xml','.rels')):ET.fromstring(archive.read(name))
        root=ET.fromstring(archive.read('word/document.xml'))
        texts=' '.join(root.itertext())
        assert '0.0445' in texts and '0.0754' in texts
        assert len(root.findall(f'.//{{{W}}}drawing'))==5
    print(json.dumps({'file':str(target),'bytes':target.stat().st_size,'words':len(source.split()),'tables':len(root.findall(f'.//{{{W}}}tbl')),'figures':len(media),'xml_validation':'passed'},indent=2))

if __name__=='__main__':build()
