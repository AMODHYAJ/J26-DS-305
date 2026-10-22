"""Run against the built React workbench; uses installed Chrome, no browser download."""
from pathlib import Path
import argparse
import json
import sys
import re

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parents[1]/'C2_TLA_tools'/'C2_TLA_browser'))
from playwright.sync_api import sync_playwright, expect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8502')
    parser.add_argument('--ceb-path',required=True)
    args=parser.parse_args()
    out=ROOT/'C2_TLA_outputs'; out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True)
        page=context.new_page(); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
        expect.set_options(timeout=120000)
        page.goto(args.url,wait_until='domcontentloaded')
        export=page.get_by_role('button',name='Export CSV',exact=True)
        expect(export).to_be_enabled()
        expect(page.get_by_role('heading',name='True Load Analysis')).to_be_visible()
        assert page.locator('.recharts-surface').count()>0
        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--lime').trim().toUpperCase()")=='#D7FA75'
        page.screenshot(path=str(out/'C2_TLA_react_desktop.png'),full_page=True)
        page.get_by_label('Data source',exact=True).select_option('synthetic')
        expect(page.locator('.snapshot-box>strong')).to_have_text('SYNTHETIC_F1')
        expect(export).to_be_enabled()
        page.get_by_label('Reconstruction method',exact=True).select_option('xgboost')
        expect(page.locator('.section-toolbar')).to_contain_text('Synthetic-trained XGBoost')
        expect(export).to_be_enabled()
        page.get_by_role('button',name='Explanations',exact=True).click()
        expect(page.get_by_role('heading',name='Individual prediction explanation')).to_be_visible()
        expect(page.locator('.bar-wrap svg.recharts-surface')).to_be_visible()
        slider=page.get_by_label('Explanation interval',exact=True); slider.focus(); slider.press('ArrowRight')
        expect(page.locator('.explanation-range')).to_contain_text('Interval 2 of')
        assert page.locator('.feature-bars>div').count()==6
        page.get_by_role('button',name='Research evidence',exact=True).click()
        expect(page.get_by_role('heading',name='Synthetic benchmark experiment')).to_be_visible()
        expect(page.get_by_text('xgboost',exact=True)).to_be_visible()
        with page.expect_download() as download:
            export.click()
        target=out/'C2_TLA_react_download.csv'; download.value.save_as(target)
        text=target.read_text(encoding='utf-8')
        assert text.startswith('feeder_id,timestamp,') and 'SYNTHETIC_F1' in text
        page.get_by_role('button',name='Demand analysis',exact=True).click()
        page.get_by_role('tab',name='Solar & uncertainty',exact=True).click()
        expect(page.get_by_role('heading',name='Solar generation envelope')).to_be_visible()
        assert page.locator('.chart-wrap svg.recharts-surface').count()==2
        page.get_by_role('tab',name='Visibility',exact=True).click()
        expect(page.get_by_role('heading',name='Visibility Loss Index over time')).to_be_visible()
        page.get_by_role('tab',name='Data quality',exact=True).click()
        expect(page.get_by_role('heading',name='Interval data quality & indicators')).to_be_visible()
        assert page.locator('tbody tr').count()==50
        page.get_by_role('button',name='Next',exact=True).click()
        expect(page.locator('.table-footer')).to_contain_text('51–100')
        page.get_by_label('Data source',exact=True).select_option('ceb')
        expect(page.locator('.snapshot-box>strong')).to_have_text('3_EMBIL_F2')
        expect(export).to_be_enabled()
        page.get_by_label('Feeder',exact=True).select_option('3_EMBIL_F6')
        expect(page.locator('.methodology-panel')).to_contain_text('Near-zero telemetry channel')
        details=page.locator('.advanced-controls')
        details.locator('summary').click()
        page.get_by_label('CEB directory',exact=True).fill('Z:/C2_TLA_missing')
        page.get_by_role('button',name='Load directory',exact=True).click()
        expect(page.get_by_role('alert')).to_contain_text('CEB directory not found')
        expect(page.get_by_label('Data source',exact=True)).to_have_value('ceb')
        page.get_by_label('CEB directory',exact=True).fill(args.ceb_path)
        page.get_by_role('button',name='Load directory',exact=True).click()
        expect(export).to_be_enabled()
        page.get_by_role('button',name='Overview',exact=True).click()
        page.get_by_role('tab',name='Demand curves',exact=True).click()
        details.locator('summary').click()
        page.set_viewport_size({'width':390,'height':844})
        expect(page.get_by_role('heading',name='True Load Analysis')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'),'Mobile page overflows horizontally'
        page.screenshot(path=str(out/'C2_TLA_react_mobile.png'),full_page=True)
        assert not errors,errors
        page.set_viewport_size({'width':1440,'height':1050})
        expect(page.get_by_role('heading',name='Connected C3 transformer context')).to_be_visible()
        expect(page.locator('.team-context')).to_contain_text('PROVISIONAL')
        page.get_by_role('button',name='Grid intelligence · C3',exact=True).click()
        frame=page.frame_locator('iframe[title="C3 grid intelligence dashboard"]')
        expect(frame.get_by_role('heading',name='Transformer Intelligence')).to_be_visible()
        expect(frame.get_by_role('heading',name='Transformer GIS map')).to_be_visible()
        expect(frame.locator('.leaflet-container')).to_be_visible()
        assert frame.locator('tbody tr').count()>0
        page.screenshot(path=str(out/'C2_TLA_shared_c3_desktop.png'),full_page=True)
        page.get_by_role('button',name='Demand intelligence · C2',exact=True).click()
        expect(page.get_by_role('heading',name='True Load Analysis')).to_be_visible()
        expect(page.locator('.chart-wrap svg.recharts-surface').first).to_be_visible()
        assert not errors,errors
        page.get_by_role('button',name='Curtailment intelligence · C4',exact=True).click()
        c4=page.frame_locator('iframe[title="C4 curtailment intelligence dashboard"]')
        expect(c4.get_by_role('heading',name='Fairness ranking',exact=True)).to_be_visible()
        expect(c4.locator('#ranking tbody tr')).to_have_count(5)
        c4.get_by_role('button',name='Run assessment',exact=True).click()
        expect(c4.get_by_text('Assessment completed',exact=True)).to_be_visible()
        expect(c4.get_by_role('heading',name='Assessment rationale',exact=True)).to_be_visible()
        page.screenshot(path=str(out/'C2_TLA_shared_c4_desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
        assert c4.locator('body').evaluate('(el)=>document.documentElement.scrollWidth <= window.innerWidth + 1')
        page.screenshot(path=str(out/'C2_TLA_shared_c4_mobile.png'),full_page=True)
        page.get_by_role('button',name='Demand intelligence · C2',exact=True).click()
        expect(page.get_by_role('heading',name='True Load Analysis')).to_be_visible()
        assert not errors,errors
        result={'passed':True,'flows':['CEB default','synthetic switch','XGBoost','individual/global SHAP','evidence','CSV download','solar uncertainty','VLI','table pagination','near-zero telemetry','invalid path without fallback','recovery','mobile layout','provisional C2-C3 feeder context','actual current-main C3 dashboard','C3 GIS map and table','shared workspace navigation','C4 actual candidate-history ranking','C4 synthetic assessment','C4 mobile layout','return from C4 to C2'], 'javascript_errors':errors}
        (out/'C2_TLA_react_browser_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))
        browser.close()


if __name__=='__main__':main()
