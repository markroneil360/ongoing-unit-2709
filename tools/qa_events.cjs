const { chromium } = require('/home/user/node_modules/playwright');
const path = require('path');

const FILE = 'file://' + path.resolve(__dirname, '..', 'index.html');
const TITLE_EXPECT = 'Unit 2709 Infrasound & Seismic Pressure Data (Ongoing)';
const DATE_RANGE_EXPECT = 'April 12, 2026 – May 27, 2026 (latest archived data)';
const BANNED = /\b(unsafe|hazardous|dangerous|health limit|exposure limit|medically|health risk|safe level)\b/i;

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const results = {};

  for (const vp of [{name:'desktop',w:1280,h:900},{name:'mobile',w:375,h:812}]) {
    const ctx = await browser.newContext({ viewport:{width:vp.w,height:vp.h} });
    const page = await ctx.newPage();
    page.on('console', m => { if (m.type()==='error') errors.push(`[${vp.name} console] ${m.text()}`); });
    page.on('pageerror', e => errors.push(`[${vp.name} pageerror] ${e.message}`));
    page.on('requestfailed', r => { const u=r.url();
      // DataView iframe + fontshare are remote; ignore remote failures, flag local only
      if(!u.startsWith('data:') && u.startsWith('file:')) errors.push(`[${vp.name} reqfail] ${u}`); });
    await page.goto(FILE, { waitUntil:'domcontentloaded' });
    await page.waitForTimeout(900);

    const r = await page.evaluate(() => {
      const q = s => document.querySelector(s);
      const txt = s => { const e=q(s); return e ? e.textContent.trim() : null; };
      const disc = txt('.disclaimer-box');
      return {
        title: document.title,
        brandTitle: txt('.brand-name'),
        dateRange: txt('#titleDateRange'),
        footDateRange: txt('#footDateRange'),
        // default tab must be Historical vs Aggregate Baseline
        defaultTabHist: document.getElementById('tab-hist').getAttribute('aria-selected')==='true',
        histPanelActive: document.getElementById('panel-hist').classList.contains('active'),
        // dual HDF+EHZ KPI groups shown first (5 boxes each)
        evHeadlineBoxes: document.querySelectorAll('#evHeadline .ev-box').length,
        kpiGroups: document.querySelectorAll('#evHeadline .kpi-group').length,
        firstKpiGroupHdf: (function(){ const g=document.querySelector('#evHeadline .kpi-group'); return g? g.className.indexOf('kpi-hdf')>=0 : false; })(),
        covNoteText: txt('#evCovNote'),
        // methodology paragraph must come AFTER the KPI groups in DOM order
        methodAfterKpi: (function(){ const h=document.getElementById('evHeadline'), m=document.getElementById('evMethod');
          if(!h||!m) return false; return !!(h.compareDocumentPosition(m)&Node.DOCUMENT_POSITION_FOLLOWING); })(),
        // Compact "Channels at a glance" at the very top (HDF first, EHZ second), concise
        glanceCount: document.querySelectorAll('.glance .glance-item').length,
        glanceHdfFirst: (function(){ const g=document.querySelector('.glance .glance-item'); return g? g.className.indexOf('glance-hdf')>=0 : false; })(),
        glanceHdfText: (function(){ const g=document.querySelector('.glance .glance-item.glance-hdf p'); return g?g.textContent.replace(/\s+/g,' ').trim():''; })(),
        glanceEhzText: (function(){ const g=document.querySelector('.glance .glance-item.glance-ehz p'); return g?g.textContent.replace(/\s+/g,' ').trim():''; })(),
        // glance must appear ABOVE the KPI groups
        glanceAboveKpi: (function(){ const g=document.querySelector('.glance'), h=document.getElementById('evHeadline');
          if(!g||!h) return false; return !!(g.compareDocumentPosition(h)&Node.DOCUMENT_POSITION_FOLLOWING); })(),
        // Distributed cards: "What measures" after KPI groups; "How to interpret" near credibility (below it)
        whatCardCount: document.querySelectorAll('#whatCards .mini-card').length,
        interpCardCount: document.querySelectorAll('#interpCards .mini-card').length,
        whatText: (function(){ const c=document.getElementById('whatCards'); return c?c.textContent.replace(/\s+/g,' ').trim():''; })(),
        interpText: (function(){ const c=document.getElementById('interpCards'); return c?c.textContent.replace(/\s+/g,' ').trim():''; })(),
        whatAfterKpi: (function(){ const h=document.getElementById('evHeadline'), w=document.getElementById('whatCards');
          if(!h||!w) return false; return !!(h.compareDocumentPosition(w)&Node.DOCUMENT_POSITION_FOLLOWING); })(),
        whatBeforeCred: (function(){ const w=document.getElementById('whatCards'), c=document.getElementById('credibilityBox');
          if(!w||!c) return false; return !!(w.compareDocumentPosition(c)&Node.DOCUMENT_POSITION_FOLLOWING); })(),
        interpAfterCred: (function(){ const c=document.getElementById('credibilityBox'), i=document.getElementById('interpCards');
          if(!c||!i) return false; return !!(c.compareDocumentPosition(i)&Node.DOCUMENT_POSITION_FOLLOWING); })(),
        interpBeforePanels: (function(){ const i=document.getElementById('interpCards'), p=document.getElementById('panelTop');
          if(!i||!p) return false; return !!(i.compareDocumentPosition(p)&Node.DOCUMENT_POSITION_FOLLOWING); })(),
        // no horizontal overflow / clipping at this viewport
        noOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
        ehc12Present: (function(){ const hits=[];
          if(/Environmental Health Criteria 12|EHC 12|9241540729/i.test(document.body.innerText)) hits.push('text');
          if(Array.from(document.querySelectorAll('a')).some(a=>(a.getAttribute('href')||'').indexOf('9241540729')>=0)) hits.push('link');
          return hits.length?hits:null; })(),
        // No WHO anywhere user-visible (any who.int URL, or WHO / World Health Organization text)
        whoLinks: Array.from(document.querySelectorAll('a')).map(a=>a.getAttribute('href')||'').filter(h=>/who\.int/i.test(h)),
        whoBody: (function(){ const m=document.body.innerText.match(/\bWHO\b|World Health Organization/i); return m?m[0]:null; })(),
        // Baseline Source Credibility box: present, after KPI groups, before methodology, with baseline+interpretive split and 4 links
        credPresent: !!document.getElementById('credibilityBox'),
        credAfterKpi: (function(){ const h=document.getElementById('evHeadline'), c=document.getElementById('credibilityBox');
          if(!h||!c) return false; return !!(h.compareDocumentPosition(c)&Node.DOCUMENT_POSITION_FOLLOWING); })(),
        credBeforeMethod: (function(){ const c=document.getElementById('credibilityBox'), m=document.getElementById('evMethod');
          if(!c||!m) return false; return !!(c.compareDocumentPosition(m)&Node.DOCUMENT_POSITION_FOLLOWING); })(),
        credText: (function(){ const c=document.getElementById('credibilityBox'); return c?c.textContent.replace(/\s+/g,' ').trim():''; })(),
        credLinks: (function(){ const c=document.getElementById('credibilityBox'); if(!c) return []; return Array.from(c.querySelectorAll('a')).map(a=>a.getAttribute('href')); })(),
        // disclaimer must be near the bottom: after the citations section, before the footer
        discAfterCite: (function(){ const cite=document.getElementById('cite-h'), d=document.querySelector('.disclaimer-box');
          if(!cite||!d) return false; return !!(cite.compareDocumentPosition(d)&Node.DOCUMENT_POSITION_FOLLOWING); })(),
        discBeforeFooter: (function(){ const f=document.querySelector('.site-footer'), d=document.querySelector('.disclaimer-box');
          if(!f||!d) return false; return !!(d.compareDocumentPosition(f)&Node.DOCUMENT_POSITION_FOLLOWING); })(),
        topTitle: txt('#topTitle'),
        avgTitle: txt('#avgTitle'),
        evTopRows: document.querySelectorAll('#bodyEvTop tr').length,
        evAvgRows: document.querySelectorAll('#bodyEvAvg tr').length,
        evSegRows: document.querySelectorAll('#bodyEvSeg tr').length,
        avgSummaryBoxes: document.querySelectorAll('#avgSummary .ev-box').length,
        evTopCanvas: !!(document.getElementById('chartEvTop')||{}).width,
        evAvgCanvas: !!(document.getElementById('chartEvAvg')||{}).width,
        noSpikeNote: /no-spike/i.test(txt('#avgNoSpike')||''),
        occupancyNote: /occupancy|presence/i.test(txt('#occupancyNote')||''),
        bottomGone: !document.getElementById('panelBottom') && !document.getElementById('bodyEvBot'),
        methodHasPct: /percent difference|value . aggregate|aggregate mean/i.test(txt('#evMethod')||''),
        // percentage language in a top row
        topRowHasPct: /%/.test(txt('#bodyEvTop')||''),
        avgRowHasPct: /%/.test(txt('#bodyEvAvg')||''),
        disc: disc ? disc.slice(0,12) : null,
        discEndsProject: disc ? /project\.$/.test(disc.trim()) : null,
        bodyText: document.body.innerText,
      };
    });

    const bad = r.bodyText.split('\n').filter(l => BANNED.test(l) &&
      !/none is used here to label|not a medical or human-exposure|not\b.*hazard/i.test(l));
    const weaponLines = r.bodyText.split('\n').filter(l => /\bweapon/i.test(l));
    results[vp.name] = { ...r, bannedLines: bad, weaponLines };
    delete results[vp.name].bodyText;

    // switch event channel to EHZ
    const ehzBtn = await page.$('#evEhz');
    if (ehzBtn) { await ehzBtn.click(); await page.waitForTimeout(400); }
    results[vp.name].ehzToggle = await page.evaluate(() => ({
      pressed: document.getElementById('evEhz').getAttribute('aria-pressed')==='true',
      topTitleC: (document.getElementById('topTitle')||{}).textContent||'',
      avgTitleD: (document.getElementById('avgTitle')||{}).textContent||'',
      unitUm: /µm\/s/.test((document.getElementById('topExtHdr')||{}).textContent||''),
      avgRows: document.querySelectorAll('#bodyEvAvg tr').length,
    }));
    // back to HDF
    const hdfBtn = await page.$('#evHdf'); if (hdfBtn){ await hdfBtn.click(); await page.waitForTimeout(300); }

    // open daily 24h tab, verify DataView iframes + snapshots + small print
    const liveTab = await page.$('#tab-live');
    if (liveTab) { await liveTab.click(); await page.waitForTimeout(500); }
    results[vp.name].daily = await page.evaluate(() => ({
      dvHdf: !!document.getElementById('dvHdf'),
      dvEhz: !!document.getElementById('dvEhz'),
      dvHdfSrc: (document.getElementById('dvHdf')||{}).getAttribute ? document.getElementById('dvHdf').getAttribute('src') : null,
      snapHdf: !!document.getElementById('snapHdf'),
      snapEhz: !!document.getElementById('snapEhz'),
      smallPrint: /fixed 7:00 AM ET cutoff/i.test((document.getElementById('dailySmallPrint')||{}).textContent||''),
      attribution: /citizen-science|10\.7914\/SN\/AM/i.test((document.getElementById('dvAttribution')||{}).textContent||''),
      windowKv: document.querySelectorAll('#dailyWindow .daily-kv').length,
      reportBtn: !!document.getElementById('btnDailyReport'),
    }));

    // daily print report: click the real button (populates #dailyReport as a side effect)
    const rptBtn = await page.$('#btnDailyReport');
    if (rptBtn) { await rptBtn.click(); await page.waitForTimeout(400); }
    results[vp.name].report = await page.evaluate(() => {
      const r = document.getElementById('dailyReport');
      const t = r ? r.textContent : '';
      const idx = s => t.indexOf(s);
      const rptHrefs = r ? Array.from(r.querySelectorAll('a')).map(a=>a.getAttribute('href')||'') : [];
      return {
        present: !!r,
        len: t.length,
        hasTitle: /Unit 2709 Infrasound & Seismic Pressure Data \(Ongoing\)/.test(t),
        hasDataRange: /April 12, 2026 – May 27, 2026 \(latest archived data\)/.test(t),
        hasAttribution: /10\.7914\/SN\/AM/.test(t),
        hasDerivedNote: /derived archived-data report/i.test(t),
        hasMeans: /daily mean|aggregate/i.test(t),
        hasSegments: /00:00|06:00|18:00/.test(t),
        hasGlance: /Channels at a glance/.test(t) && /Primary · HDF/.test(t) && /Secondary · EHZ/.test(t),
        hasWhat: /What each channel measures/.test(t),
        hasInterp: /How to interpret each channel/.test(t),
        hasCred: /Baseline Source Credibility/.test(t) && /Interpretive sources/.test(t),
        // concise hierarchy: glance near top (before means table), what-measures + credibility + interpret before methodology
        glanceNearTop: idx('Channels at a glance')>=0 && idx('Channels at a glance')<idx('Channel daily means'),
        credBeforeMethod: idx('Baseline Source Credibility')>=0 && idx('Methodology')>idx('Baseline Source Credibility'),
        whatBeforeMethod: idx('What each channel measures')>=0 && idx('Methodology')>idx('What each channel measures'),
        interpBeforeMethod: idx('How to interpret each channel')>=0 && idx('Methodology')>idx('How to interpret each channel'),
        discLast: idx('Disclaimer')>idx('Attribution') && idx('Attribution')>=0,
        noWeapon: !/\bweapon/i.test(t),
        noEhc12: !/Environmental Health Criteria 12|EHC 12|9241540729/i.test(t),
        noWho: !/\bWHO\b|World Health Organization/i.test(t) && !rptHrefs.some(h=>/who\.int/i.test(h)),
        hasDbSplLimit: /not[^.]*dB SPL/i.test(t) && /establish harm/i.test(t),
        noSymptomClaim: !/\byour (health|symptoms?|body)\b/i.test(t),
      };
    });

    if (vp.name==='desktop') { await page.screenshot({ path: path.resolve(__dirname,'..','qa_events_desktop.png'), fullPage:true }); }
    else { await page.screenshot({ path: path.resolve(__dirname,'..','qa_events_mobile.png'), fullPage:true }); }

    // print-layout sanity: emulate print media with the report class and screenshot (desktop)
    if (vp.name==='desktop') {
      await page.evaluate(() => document.body.classList.add('printing-report'));
      await page.emulateMedia({ media:'print' });
      await page.screenshot({ path: path.resolve(__dirname,'..','qa_events_print.png'), fullPage:true });
      results[vp.name].printLayout = await page.evaluate(() => {
        const r = document.getElementById('dailyReport');
        const cs = r ? getComputedStyle(r) : null;
        return { reportVisible: cs ? cs.display!=='none' : false };
      });
      await page.emulateMedia({ media:'screen' });
      await page.evaluate(() => document.body.classList.remove('printing-report'));
    }

    // CSV download smoke (desktop): switch back to hist tab first
    if (vp.name==='desktop') {
      const h = await page.$('#tab-hist'); if (h){ await h.click(); await page.waitForTimeout(300); }
      const dls = {};
      for (const id of ['btnEvTopCsv','btnEvAvgCsv','btnEvAllCsv']) {
        try {
          const [dl] = await Promise.all([
            page.waitForEvent('download', { timeout: 4000 }),
            page.click('#'+id)
          ]);
          dls[id] = dl.suggestedFilename();
        } catch(e) { dls[id] = 'NO_DOWNLOAD'; }
      }
      results[vp.name].downloads = dls;
    }
    await ctx.close();
  }

  await browser.close();
  console.log(JSON.stringify({ errors, results }, null, 2));

  const d = results.desktop, fails = [];
  if (errors.length) fails.push('JS/local-network errors: '+errors.length);
  if (d.title !== TITLE_EXPECT) fails.push('doc title not new public title (got "'+d.title+'")');
  if (d.brandTitle !== TITLE_EXPECT) fails.push('brand title not new public title (got "'+d.brandTitle+'")');
  if (d.dateRange !== DATE_RANGE_EXPECT) fails.push('title date range wrong (got "'+d.dateRange+'")');
  if (d.footDateRange !== DATE_RANGE_EXPECT) fails.push('footer date range wrong (got "'+d.footDateRange+'")');
  if (!d.defaultTabHist) fails.push('default tab is not Historical vs Aggregate Baseline');
  if (!d.histPanelActive) fails.push('hist panel not active by default');
  if (d.kpiGroups !== 2) fails.push('expected 2 KPI groups (HDF+EHZ), got '+d.kpiGroups);
  if (!d.firstKpiGroupHdf) fails.push('first KPI group is not HDF');
  if (d.evHeadlineBoxes < 10) fails.push('KPI boxes < 10 (5 per channel), got '+d.evHeadlineBoxes);
  if (!d.methodAfterKpi) fails.push('methodology not below KPI groups');
  if (!/documented days/i.test(d.covNoteText||'')) fails.push('coverage note missing');
  if (!/A\. HDF Top 20/.test(d.topTitle||'')) fails.push('top title not "A. HDF Top 20"');
  if (!/B\. HDF Average/.test(d.avgTitle||'')) fails.push('average title not "B. HDF Average"');
  if (!d.bottomGone) fails.push('Bottom 20 panel/table still present');
  if (d.evTopRows < 1) fails.push('no HDF top rows');
  if (d.evAvgRows < 1) fails.push('no HDF average day rows');
  if (d.evSegRows < 1) fails.push('no HDF segment rows');
  if (d.avgSummaryBoxes < 4) fails.push('average summary boxes < 4 (got '+d.avgSummaryBoxes+')');
  if (!d.topRowHasPct) fails.push('top rows missing % language');
  if (!d.avgRowHasPct) fails.push('average rows missing % language');
  if (!d.noSpikeNote) fails.push('no-spike note missing');
  if (!d.occupancyNote) fails.push('occupancy/presence note missing');
  if (!d.methodHasPct) fails.push('methodology note missing % definition');
  if (!d.ehzToggle.pressed) fails.push('EHZ channel toggle did not switch');
  if (!/C\. EHZ Top 20/.test(d.ehzToggle.topTitleC)) fails.push('EHZ top title not "C. EHZ Top 20"');
  if (!/D\. EHZ Average/.test(d.ehzToggle.avgTitleD)) fails.push('EHZ average title not "D. EHZ Average"');
  if (d.ehzToggle.avgRows < 1) fails.push('no EHZ average rows after toggle');
  if (!d.ehzToggle.unitUm) fails.push('EHZ units not µm/s after toggle');
  if (d.discEndsProject!==true) fails.push('disclaimer not ending in project.');
  if (d.bannedLines.length) fails.push('banned lines: '+JSON.stringify(d.bannedLines));
  // Task 8: compact "Channels at a glance" top summary (HDF first, concise) + distributed cards
  const wc = s => (s||'').split(/\s+/).filter(Boolean).length;
  if (d.glanceCount !== 2) fails.push('expected 2 glance items, got '+d.glanceCount);
  if (!d.glanceHdfFirst) fails.push('glance HDF item is not first');
  if (!d.glanceAboveKpi) fails.push('glance not above KPI groups');
  if (!/pascals|Pa\b/.test(d.glanceHdfText||'')) fails.push('glance HDF text missing Pa');
  if (!/µm\/s/.test(d.glanceEhzText||'')) fails.push('glance EHZ text missing µm/s');
  if (wc(d.glanceHdfText) > 55) fails.push('glance HDF summary not concise ('+wc(d.glanceHdfText)+' words)');
  if (wc(d.glanceEhzText) > 55) fails.push('glance EHZ summary not concise ('+wc(d.glanceEhzText)+' words)');
  // Long explanatory content moved lower into small cards
  if (d.whatCardCount !== 2) fails.push('expected 2 "What measures" cards, got '+d.whatCardCount);
  if (d.interpCardCount !== 2) fails.push('expected 2 "How to interpret" cards, got '+d.interpCardCount);
  if (!d.whatAfterKpi) fails.push('"What measures" cards not after KPI groups');
  if (!d.whatBeforeCred) fails.push('"What measures" cards not before credibility box');
  if (!d.interpAfterCred) fails.push('"How to interpret" cards not after credibility box');
  if (!d.interpBeforePanels) fails.push('"How to interpret" cards not before Top-20 panel');
  if (!/FDSN|Raspberry Boom|Pa\b/.test(d.whatText||'')) fails.push('"What HDF measures" card content missing');
  if (!/µm\/s|geophone/.test(d.whatText||'')) fails.push('"What EHZ measures" card content missing');
  // Cautious perception + dB SPL limitation now live in interpretation cards
  if (!/perceived through the auditory system/i.test(d.interpText||'')) fails.push('interpret cards missing cautious perception language');
  if (!/not\b[^.]*dB SPL/i.test(d.interpText||'')) fails.push('interpret cards missing "not dB SPL" limitation');
  if (!/establish harm/i.test(d.interpText||'')) fails.push('interpret cards missing "cannot establish harm"');
  if (!/never cross-compared/i.test(d.interpText||'')) fails.push('interpret cards missing HDF/EHZ no-cross-compare');
  if (!d.noOverflow) fails.push('horizontal overflow / clipping detected (desktop)');
  if (results.mobile && !results.mobile.noOverflow) fails.push('horizontal overflow / clipping detected (mobile)');
  if (!d.credPresent) fails.push('Baseline Source Credibility box missing');
  if (!d.credAfterKpi) fails.push('credibility box not after KPI groups');
  if (!d.credBeforeMethod) fails.push('credibility box not before methodology');
  if (!/Baseline data/i.test(d.credText||'')) fails.push('credibility box missing "Baseline data" subsection');
  if (!/Interpretive sources/i.test(d.credText||'')) fails.push('credibility box missing "Interpretive sources" subsection');
  if (!/0\.120031 Pa/.test(d.credText||'')||!/27/.test(d.credText||'')) fails.push('credibility box missing HDF 0.120031 Pa / 27 peers');
  if (!/1\.37637 µm\/s/.test(d.credText||'')||!/22/.test(d.credText||'')) fails.push('credibility box missing EHZ 1.37637 µm/s / 22 peers');
  if (/\b75\b/.test(d.credText||'')) fails.push('credibility box wrongly mentions 75');
  const REQ_LINKS = ['raspberryshake.org/raspberry-shake-basic-concepts','journals.plos.org/plosone/article?id=10.1371/journal.pone.0229088','pmc.ncbi.nlm.nih.gov/articles/PMC7199630'];
  for (const lk of REQ_LINKS) { if (!(d.credLinks||[]).some(h=>(h||'').indexOf(lk)>=0)) fails.push('credibility box missing source link: '+lk); }
  // No WHO anywhere user-visible: no who.int link, no "WHO"/"World Health Organization" text in body
  if (d.whoLinks && d.whoLinks.length) fails.push('WHO URL present in UI: '+JSON.stringify(d.whoLinks));
  if (d.whoBody) fails.push('WHO text present in UI body: '+JSON.stringify(d.whoBody));
  // EHC 12 (1980) must be fully removed everywhere (URL + text)
  if (d.ehc12Present) fails.push('EHC 12 (1980) reference still present: '+JSON.stringify(d.ehc12Present));
  if (!d.discAfterCite) fails.push('disclaimer not after citations section');
  if (!d.discBeforeFooter) fails.push('disclaimer not before footer');
  if (d.weaponLines && d.weaponLines.length) fails.push('weapon phrase present in UI: '+JSON.stringify(d.weaponLines));
  if (!d.daily.dvHdf || !d.daily.dvEhz) fails.push('DataView iframes missing');
  if (!/dataview\.raspberryshake\.org.*HDF/.test(d.daily.dvHdfSrc||'')) fails.push('HDF DataView src wrong');
  if (!d.daily.snapHdf || !d.daily.snapEhz) fails.push('snapshot images missing');
  if (!d.daily.smallPrint) fails.push('daily small print missing/verbatim');
  if (!d.daily.attribution) fails.push('DataView attribution/DOI missing');
  if (!d.daily.reportBtn) fails.push('daily Print/Save PDF report button missing');
  if (!d.report.present || d.report.len < 200) fails.push('daily report container not populated');
  if (!d.report.hasTitle) fails.push('daily report missing new public title');
  if (!d.report.hasDataRange) fails.push('daily report missing data range');
  if (!d.report.hasAttribution) fails.push('daily report missing DOI attribution');
  if (!d.report.hasDerivedNote) fails.push('daily report missing derived-report note');
  if (!d.report.hasSegments) fails.push('daily report missing segment averages');
  if (!d.report.hasGlance) fails.push('daily report missing concise "Channels at a glance"');
  if (!d.report.hasWhat) fails.push('daily report missing "What each channel measures"');
  if (!d.report.hasInterp) fails.push('daily report missing "How to interpret each channel"');
  if (!d.report.hasCred) fails.push('daily report missing Baseline Source Credibility');
  if (!d.report.glanceNearTop) fails.push('report glance not near top (before daily means table)');
  if (!d.report.whatBeforeMethod) fails.push('report "What measures" not before methodology');
  if (!d.report.credBeforeMethod) fails.push('report credibility not before methodology');
  if (!d.report.interpBeforeMethod) fails.push('report "How to interpret" not before methodology');
  if (!d.report.discLast) fails.push('report disclaimer not last (after attribution)');
  if (!d.report.noWeapon) fails.push('report contains weapon phrase');
  if (!d.report.noEhc12) fails.push('report still contains EHC 12 (1980) reference');
  if (!d.report.noWho) fails.push('report still contains WHO text or who.int URL');
  if (!d.report.hasDbSplLimit) fails.push('report missing general "not dB SPL / establish harm" limitation');
  if (!d.report.noSymptomClaim) fails.push('report contains personal symptom/health claim');
  if (!(d.printLayout&&d.printLayout.reportVisible)) fails.push('report not visible under print media');
  if (d.downloads.btnEvTopCsv==='NO_DOWNLOAD') fails.push('top CSV did not download');
  if (d.downloads.btnEvAvgCsv==='NO_DOWNLOAD') fails.push('average CSV did not download');
  if (d.downloads.btnEvAllCsv==='NO_DOWNLOAD') fails.push('all-events CSV did not download');

  console.log('\nFAILS:', fails.length?fails.join(' | '):'NONE');
  process.exit(fails.length?1:0);
})();
