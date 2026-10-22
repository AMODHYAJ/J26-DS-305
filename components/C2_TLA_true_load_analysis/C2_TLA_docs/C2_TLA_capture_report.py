"""Capture presentation figures from the running local C2 workbench."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parents[1]/'C2_TLA_tools'/'C2_TLA_browser'))
from playwright.sync_api import sync_playwright, expect

def main():
    out=ROOT/'C2_TLA_docs'/'C2_TLA_figures'
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        expect.set_options(timeout=180000)
        page.goto('http://127.0.0.1:8502',wait_until='domcontentloaded')
        expect(page.get_by_role('button',name='Export CSV',exact=True)).to_be_enabled()
        page.screenshot(path=str(out/'C2_TLA_overview.png'))
        page.locator('.analysis-grid').screenshot(path=str(out/'C2_TLA_demand_chart.png'))
        page.locator('.team-context').screenshot(path=str(out/'C2_TLA_c3_context.png'))
        page.get_by_label('Reconstruction method',exact=True).select_option('xgboost')
        expect(page.get_by_role('button',name='Export CSV',exact=True)).to_be_enabled()
        page.get_by_role('button',name='Explanations',exact=True).click()
        expect(page.get_by_role('heading',name='Individual prediction explanation')).to_be_visible()
        page.locator('.analysis-grid').screenshot(path=str(out/'C2_TLA_explanations.png'))
        page.get_by_role('button',name='Research evidence',exact=True).click()
        page.get_by_role('heading',name='Synthetic benchmark experiment').locator('..').locator('..').locator('..').screenshot(path=str(out/'C2_TLA_evidence.png'))
        browser.close()
    print('Saved five report figures to',out)

if __name__=='__main__':main()
