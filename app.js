(function () {
  "use strict";
  var D = window.__TREMORLENS__;
  if (!D) { console.error("Tremorlens live data not loaded"); return; }
  var U = window.__TREMORLENS_UNIFIED__ || null;
  var H = U || window.__TREMORLENS_HIST__ || null;
  var P = window.__TREMORLENS_PEER__ || null; // external network-peer HDF baseline
  function isDataStatus(st){ return st==="local" || st==="source" || st==="prior"; }

  var UM = 1e6; // m/s -> µm/s
  function toUm(v) { return v == null ? null : v * UM; }
  function fmt(v, d) { return v == null ? "\u2014" : Number(v).toFixed(d == null ? 2 : d); }

  // ---------- theme ----------
  var root = document.documentElement;
  var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  if (prefersDark) root.classList.add("dark");
  document.getElementById("themeToggle").addEventListener("click", function () {
    root.classList.toggle("dark");
    rebuildAllCharts();
  });

  // ---------- generated time (Detroit / EDT = UTC-4) ----------
  var MM = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  function genTimeStr() {
    var d = new Date(D.generated_utc);
    var loc = new Date(d.getTime() - 4 * 3600 * 1000);
    var h = loc.getUTCHours(), m = loc.getUTCMinutes(), s = loc.getUTCSeconds();
    var ap = h >= 12 ? "PM" : "AM"; var h12 = h % 12; if (h12 === 0) h12 = 12;
    function p(n){return (n<10?"0":"")+n;}
    return MM[loc.getUTCMonth()] + " " + loc.getUTCDate() + ", " + loc.getUTCFullYear() +
           " \u00b7 " + h12 + ":" + p(m) + ":" + p(s) + " " + ap + " EDT";
  }
  var gt = genTimeStr();
  document.getElementById("genTime").textContent = gt;
  document.getElementById("genTimeFoot").textContent = gt;

  var series = D.minute_series;
  var s = D.summary;

  // window range label
  function prettyDetroit(raw){ // "2026-07-12 03:20"
    var parts = raw.split(" "), t = parts[1], hm = t.split(":");
    var h = parseInt(hm[0],10), m = hm[1];
    var ap = h >= 12 ? "PM" : "AM"; var h12 = h % 12; if (h12===0) h12=12;
    return parts[0] + " " + h12 + ":" + m + " " + ap;
  }
  var firstT = series[0].t, lastT = series[series.length-1].t;
  document.getElementById("windowRange").textContent =
    "Source retrieval span: " + prettyDetroit(firstT) + " \u2192 " + prettyDetroit(lastT) + " EDT (" + series.length + " one-minute samples)";

  // ---------- pending detection ----------
  // Requested end = 3:48 AM EDT (07:48Z). Latest sample = summary.latest_sample_utc.
  var reqEndDetroitMin = 3*60 + 48; // minutes after midnight for 3:48 AM
  var latestUtc = new Date(s.latest_sample_utc + (s.latest_sample_utc.slice(-1)==="Z"?"":"Z"));
  var latestDetroit = new Date(latestUtc.getTime() - 4*3600*1000);
  var latestMinOfDay = latestDetroit.getUTCHours()*60 + latestDetroit.getUTCMinutes();
  // pending only if latest is before the requested end AND same/earlier day boundary
  var pendingMin = 0;
  // compute based on last observed minute vs 3:48 AM on Jul 13
  var lastParts = lastT.split(" ");
  if (lastParts[0] === "2026-07-13") {
    var lastMin = (function(){var hm=lastParts[1].split(":");return parseInt(hm[0],10)*60+parseInt(hm[1],10);})();
    if (lastMin < reqEndDetroitMin) pendingMin = reqEndDetroitMin - lastMin - 1;
  }
  var latestPretty = prettyDetroit(lastT).split(" ").slice(1).join(" ");

  // live status text
  var liveHead = document.getElementById("liveHead");
  var liveSub = document.getElementById("liveSub");
  if (pendingMin > 0) {
    liveHead.textContent = "Live feed \u2014 HDF data through " + latestPretty + " EDT";
    liveSub.innerHTML = pendingMin + " min to the requested 3:48 AM end are <em>pending</em> (FDSN lag) \u2014 not zero, not \u201cno change.\u201d";
  } else {
    liveHead.textContent = "Requested interval closed \u2014 latest source sample " + latestPretty + " EDT";
    liveSub.innerHTML = "The requested <strong>11:08 PM\u20133:48 AM</strong> window is fully covered by source data (0 pending minutes). Samples shown <em>after</em> 3:48 AM (through " + latestPretty + " EDT) are supplemental latest-source coverage beyond the requested endpoint; the FDSN feed can still lag for the most recent minutes.";
    document.getElementById("liveStatus").style.background = "var(--teal-soft)";
    document.getElementById("liveStatus").style.borderColor = "color-mix(in srgb,var(--teal) 35%,transparent)";
    var dot = document.querySelector("#liveStatus .live-dot"); if (dot) dot.style.background = "var(--teal)";
    liveHead.style.color = "var(--teal)";
  }

  // ---------- KPIs (HDF-first) ----------
  var preArr = s.pressure_pre_arrival_mean_pa;
  document.getElementById("kpiPre").innerHTML = fmt(preArr,3) + '<span class="kpi-unit">Pa</span>';
  var firstHour = D.hourly.length ? D.hourly[0].pressure_rms_mean_pa : null;
  document.getElementById("kpiFirst").innerHTML = fmt(firstHour,3) + '<span class="kpi-unit">Pa</span>';
  if (firstHour != null && preArr) {
    document.getElementById("kpiFirstNote").innerHTML = "11:08 PM\u201312:08 AM \u00b7 <strong>+" + Math.round((firstHour-preArr)/preArr*100) + "%</strong> vs pre-arrival hour (within-event)";
  }
  document.getElementById("kpiPeak").innerHTML = fmt(s.arrival_pressure_peak_pa,3) + '<span class="kpi-unit">Pa</span>';
  // find peak minute time
  var peakMin = null, peakVal = -1;
  series.forEach(function(m){ if(m.p!=null && m.p>peakVal){peakVal=m.p; peakMin=m.t;} });
  if (peakMin) document.getElementById("kpiPeakNote").textContent = "at " + prettyDetroit(peakMin).split(" ").slice(1).join(" ") + " EDT";
  document.getElementById("kpiObs").innerHTML = (s.arrival_sample_count != null ? s.arrival_sample_count : s.arrival_observed_minutes) + '<span class="kpi-unit">samples</span>';
  var kObsNote = document.getElementById("kpiObsNote");
  if (kObsNote) kObsNote.textContent = (s.arrival_elapsed_minutes != null ? s.arrival_elapsed_minutes : 291) + " min elapsed (11:08 PM \u2192 latest); inclusive one-minute samples";
  var r24pct = (s.rolling24_completeness_pct != null) ? s.rolling24_completeness_pct : s.completeness_pct;
  var r24present = (s.rolling24_present_bins != null) ? s.rolling24_present_bins : s.data_minutes;
  document.getElementById("kpiComplete").innerHTML = (Math.round(r24pct*10)/10) + '<span class="kpi-unit">%</span>';
  document.getElementById("kpiMinutes").textContent = r24present + " / 1440 one-minute bins (" +
    (s.rolling24_start_detroit ? s.rolling24_start_detroit.slice(11) : "04:00") + " prior day \u2192 " +
    (s.rolling24_end_detroit ? s.rolling24_end_detroit.slice(11) : "03:59") + ")";
  document.getElementById("kpiLatest").textContent = latestPretty + " EDT";
  var kLatNote = document.getElementById("kpiLatestNote");
  if (kLatNote) kLatNote.textContent = "Latest source sample (beyond the 3:48 AM requested end)";

  var kpiPendingCard = document.getElementById("kpiPendingCard");
  document.getElementById("kpiPending").innerHTML = pendingMin + '<span class="kpi-unit">min</span>';
  if (pendingMin > 0) {
    kpiPendingCard.classList.add("kpi-amber");
    document.getElementById("kpiPendingNote").textContent = "Awaiting FDSN toward 3:48 AM requested end";
  } else {
    kpiPendingCard.classList.add("kpi-good");
    document.getElementById("kpiPendingNote").textContent = "Requested 3:48 AM end reached; later data is supplemental";
  }

  // EHZ secondary KPIs
  document.getElementById("kpiVMean").innerHTML = fmt(toUm(s.arrival_velocity_mean_m_s)) + '<span class="kpi-unit">µm/s</span>';
  document.getElementById("kpiVPeak").innerHTML = fmt(toUm(s.arrival_velocity_peak_m_s)) + '<span class="kpi-unit">µm/s</span>';

  // ---------- hourly HDF table ----------
  function deltaCell(pct) {
    if (pct == null) return '<td class="num"><span class="na">pre-arrival</span></td>';
    var cls = pct > 0.5 ? "up" : (pct < -0.5 ? "down" : "flat");
    var arrow = pct > 0.5 ? "\u25b2" : (pct < -0.5 ? "\u25bc" : "\u25ac");
    var sign = pct > 0 ? "+" : "";
    return '<td class="num"><span class="delta ' + cls + '"><span class="arrow" aria-hidden="true">' +
           arrow + '</span>' + sign + pct.toFixed(0) + '%</span></td>';
  }
  var tbody = document.getElementById("hourlyBody");
  var rows = "";
  var pseq = [];
  D.hourly.forEach(function (h) {
    var partial = h.observed_minutes < 60;
    var rowCls = partial ? "row-partial" : "";
    var lbl = h.label_detroit + (partial ? ' <span class="chip chip-partial">' + h.observed_minutes + '-min partial</span>' : "");
    var vsPre = (h.pressure_rms_mean_pa != null && preArr) ? (h.pressure_rms_mean_pa - preArr)/preArr*100 : null;
    rows += '<tr class="' + rowCls + '">' +
      '<td class="hour-label">' + lbl + '</td>' +
      '<td class="num">' + h.observed_minutes + '</td>' +
      '<td class="num">' + fmt(h.pressure_rms_mean_pa, 3) + '</td>' +
      deltaCell(h.pressure_change_vs_prior_pct) +
      deltaCell(vsPre) +
      '<td class="num">' + fmt(h.pressure_rms_peak_pa, 3) + '</td>' +
      '<td class="num">' + fmt(h.pressure_rms_p95_pa, 3) + '</td>' +
      '</tr>';
    if (h.pressure_rms_mean_pa != null) pseq.push(h.pressure_rms_mean_pa.toFixed(3));
  });
  // pending row if applicable
  if (pendingMin > 0) {
    rows += '<tr class="row-pending">' +
      '<td class="hour-label">' + latestPretty + '\u20133:48 AM <span class="chip chip-pending">pending</span></td>' +
      '<td class="num">0</td>' +
      '<td class="num" colspan="5">Awaiting FDSN \u2014 not yet available. Not zero, not \u201cno change.\u201d</td>' +
      '</tr>';
  }
  tbody.innerHTML = rows;

  var foot = document.getElementById("hourlyFoot");
  var footHtml = "";
  var hasPartial = D.hourly.some(function(h){return h.observed_minutes<60;});
  if (hasPartial) footHtml += '<span class="chip chip-partial">partial</span> Partial bins cover fewer than 60 minutes and are <strong>not directly comparable</strong> to a full hour. ';
  if (pendingMin > 0) footHtml += '<span class="chip chip-pending">pending</span> The trailing row is <strong>awaiting FDSN</strong> \u2014 not zero and not \u201cno change.\u201d';
  else footHtml += 'The requested 11:08 PM\u20133:48 AM interval is fully closed by source data.';
  foot.innerHTML = footHtml;

  // ---------- finding sequence ----------
  document.getElementById("findPSeq").textContent = pseq.join(" \u2192 ") + " Pa";
  var pctList = D.hourly.filter(function(h){return h.pressure_rms_mean_pa!=null;})
    .map(function(h){ return (preArr? Math.round((h.pressure_rms_mean_pa-preArr)/preArr*100):null); });
  var detail = "Relative to the 10:08\u201311:08 PM pre-arrival hour of <strong>" + fmt(preArr,3) +
    " Pa</strong> (within-event comparison only, not a benchmark or reference distribution), hourly HDF RMS ran ";
  detail += pctList.map(function(p){return (p>=0?"+":"")+p+"%";}).join(", ") + ". ";
  detail += "The first hour was elevated by the ~11:57 PM\u201312:01 AM cluster (peak <strong>" + fmt(s.arrival_pressure_peak_pa,3) + " Pa</strong>); later hours settle toward the pre-arrival level.";
  document.getElementById("findPDetail").innerHTML = detail;

  // ---------- Chart.js helpers ----------
  function css(name){ return getComputedStyle(root).getPropertyValue(name).trim(); }
  var charts = [];
  function destroyCharts(){ charts.forEach(function(c){try{c.destroy();}catch(e){}}); charts = []; }

  function prettyTip(raw){
    var parts = raw.split(" "), t = parts[1], hm = t.split(":");
    var h = parseInt(hm[0],10), m = hm[1];
    var ap = h >= 12 ? "PM" : "AM"; var h12 = h % 12; if (h12===0) h12=12;
    return parts[0].slice(5) + " \u00b7 " + h12 + ":" + m + " " + ap + " EDT";
  }
  function baseOpts(unit, decimals, tipFn){
    var ink3 = css("--ink-3"), grid = css("--grid-line"), surface = css("--surface"), border = css("--border-strong"), ink = css("--ink");
    return {
      responsive:true, maintainAspectRatio:false,
      interaction:{ mode:"index", intersect:false },
      plugins:{
        legend:{ display:false },
        tooltip:{
          backgroundColor: surface, titleColor: ink, bodyColor: css("--ink-2"),
          borderColor: border, borderWidth:1, padding:10, displayColors:false,
          titleFont:{family:"General Sans", weight:"600"}, bodyFont:{family:"JetBrains Mono"},
          callbacks:{
            title:function(items){ return (tipFn||prettyTip)(items[0].label); },
            label:function(ctx){ return ctx.parsed.y == null ? "no data" : ctx.parsed.y.toFixed(decimals) + " " + unit; }
          }
        }
      },
      scales:{
        x:{ ticks:{ color:ink3, maxTicksLimit:8, font:{family:"JetBrains Mono", size:10},
             callback:function(v){ var raw=this.getLabelForValue(v); return (tipFn?raw:prettyTip(raw).split(" \u00b7 ")[1].replace(" EDT","")); } },
            grid:{ color:grid, drawTicks:false } },
        y:{ ticks:{ color:ink3, font:{family:"JetBrains Mono", size:10} },
            grid:{ color:grid, drawTicks:false }, beginAtZero:true }
      },
      elements:{ point:{ radius:0, hoverRadius:4, hoverBorderWidth:2 }, line:{ borderWidth:1.6, tension:.15 } }
    };
  }

  // live labels/values
  var labels = series.map(function(m){ return m.t; });
  var pre    = series.map(function(m){ return m.p; });
  var velUm  = series.map(function(m){ return m.v == null ? null : m.v * UM; });

  function buildLine(id, data, unit, decimals){
    var el = document.getElementById(id); if (!el) return;
    var teal = css("--teal");
    var ctx = el.getContext("2d");
    var grad = ctx.createLinearGradient(0,0,0,280);
    grad.addColorStop(0, teal + "33"); grad.addColorStop(1, teal + "00");
    var opts = baseOpts(unit, decimals); opts.spanGaps = false;
    var c = new Chart(ctx, {
      type:"line",
      data:{ labels:labels, datasets:[{ data:data, borderColor:teal, backgroundColor:grad, fill:true, pointBackgroundColor:teal }] },
      options: opts
    });
    charts.push(c);
  }

  // ---------- arrival zoom (HDF) ----------
  function inZoom(raw){
    var d = raw.split(" ")[0], t = raw.split(" ")[1];
    if (d === "2026-07-12"){ return t >= "22:00"; }
    if (d === "2026-07-13"){ return t <= "04:00"; }
    return false;
  }
  function buildZoom(){
    var el = document.getElementById("chartZoom"); if (!el) return;
    var zl=[], zv=[];
    series.forEach(function(m){ if(inZoom(m.t)){ zl.push(m.t); zv.push(m.p); } });
    // append pending nulls up to 3:48 if pending
    if (pendingMin > 0) {
      var lastMM = (function(){var p=zl[zl.length-1].split(" ")[1].split(":");return parseInt(p[1],10);})();
      var lastHH = parseInt(zl[zl.length-1].split(" ")[1].split(":")[0],10);
      var cur = lastHH*60 + lastMM + 1;
      while (cur <= reqEndDetroitMin) {
        var hh = Math.floor(cur/60), mmn = cur%60;
        zl.push("2026-07-13 " + (hh<10?"0"+hh:hh) + ":" + (mmn<10?"0"+mmn:mmn));
        zv.push(null); cur++;
      }
    }
    var teal = css("--teal"), amber = css("--amber-2"), border=css("--border-strong");
    var arrivalIdx = zl.indexOf("2026-07-12 23:08");
    var pendingStartIdx = pendingMin > 0 ? (zl.length - pendingMin) : -1;
    var ctx = el.getContext("2d");
    var grad = ctx.createLinearGradient(0,0,0,280);
    grad.addColorStop(0, teal + "33"); grad.addColorStop(1, teal + "00");
    var opts = baseOpts("Pa", 3); opts.spanGaps = false;

    var markerPlugin = {
      id:"markers",
      beforeDatasetsDraw:function(chart){
        var c2 = chart.ctx, xa = chart.scales.x, ya = chart.scales.y;
        if (pendingStartIdx >= 0){
          var xStart = xa.getPixelForValue(pendingStartIdx), xEnd = xa.right;
          c2.save(); c2.fillStyle = border + "22"; c2.fillRect(xStart, ya.top, xEnd - xStart, ya.bottom - ya.top);
          c2.strokeStyle = border + "55"; c2.lineWidth=1;
          for (var x = xStart; x < xEnd; x += 7){ c2.beginPath(); c2.moveTo(x, ya.bottom); c2.lineTo(x + (ya.bottom-ya.top), ya.top); c2.stroke(); }
          c2.restore();
        }
      },
      afterDatasetsDraw:function(chart){
        var c2 = chart.ctx, xa = chart.scales.x, ya = chart.scales.y;
        if (arrivalIdx >= 0){
          var x = xa.getPixelForValue(arrivalIdx);
          c2.save(); c2.strokeStyle = amber; c2.lineWidth=2; c2.setLineDash([5,4]);
          c2.beginPath(); c2.moveTo(x, ya.top); c2.lineTo(x, ya.bottom); c2.stroke(); c2.setLineDash([]);
          c2.fillStyle = amber; c2.font = "600 11px 'General Sans'";
          var t = "Arrival 11:08 PM", tw = c2.measureText(t).width;
          c2.fillText(t, Math.min(x + 6, xa.right - tw - 4), ya.top + 12); c2.restore();
        }
        if (pendingStartIdx >= 0){
          var px = xa.getPixelForValue(pendingStartIdx);
          c2.save(); c2.fillStyle = css("--ink-3"); c2.font = "500 10px 'JetBrains Mono'";
          c2.fillText("pending \u2192 3:48 AM", Math.min(px + 6, xa.right - 100), ya.bottom - 8); c2.restore();
        }
      }
    };
    var c = new Chart(ctx, {
      type:"line",
      data:{ labels:zl, datasets:[{ data:zv, borderColor:teal, backgroundColor:grad, fill:true, pointBackgroundColor:teal }] },
      options: opts, plugins:[markerPlugin]
    });
    charts.push(c);
  }

  // ---------- Historical view ----------
  var histChart = null;
  var histMetric = "mean";
  function destroyHist(){ if(histChart){try{histChart.destroy();}catch(e){}} histChart=null; }

  // ---------- external peer-baseline comparison chart ----------
  var peerChart = null;
  var peerMetric = "mean"; // "mean" | "peak"
  function destroyPeerChart(){ if(peerChart){try{peerChart.destroy();}catch(e){}} peerChart=null; }
  var PEER_BAND = {
    reference:{color:"#0f766e", label:"Reference <P75"},
    yellow:{color:"#ca8a04", label:"Yellow P75-<P95"},
    orange:{color:"#ea580c", label:"Orange P95-<P99"},
    red:{color:"#dc2626", label:"Red >=P99"}
  };
  function peerQ(metric){ if(!P) return null; return metric==="peak" ? P.peer_daily_peak_pa : P.peer_daily_mean_pa; }
  function bandOfVal(metric, v){
    var q=peerQ(metric); if(!q||v==null||q.p75==null||q.p95==null||q.p99==null) return null;
    if(v>=q.p99) return "red"; if(v>=q.p95) return "orange"; if(v>=q.p75) return "yellow"; return "reference";
  }
  function peerVals(metric){
    if(!P||!P.peers) return [];
    var key = metric==="peak" ? "daily_peak_pa" : "daily_mean_pa";
    return P.peers.map(function(p){return p[key];}).filter(function(x){return x!=null;}).sort(function(a,b){return a-b;});
  }
  function peerPctl(metric, v){
    var vals=peerVals(metric); if(!vals.length||v==null) return null;
    var below=0; for(var i=0;i<vals.length;i++){ if(vals[i]<v) below++; }
    return Math.round(1000*below/vals.length)/10;
  }
  function dayVal(d, metric){ return isDataStatus(d.status) ? d[metric] : null; }
  function metricLabel(metric){ return metric==="peak" ? "daily peak" : "daily mean"; }

  function buildHistorical(){
    if (!H) {
      // no historical data available yet
      var badge = document.getElementById("histTabBadge"); if (badge) badge.textContent = "pending";
      var stats = document.getElementById("histStats");
      if (stats) stats.innerHTML = '<div class="hstat" style="grid-column:1/-1"><div class="hstat-k">Historical HDF</div><div class="hstat-note">Daily source reconstruction is still being retrieved from FDSN, or was not bundled in this build. New daily MiniSEED can be merged here without redesign.</div></div>';
      return;
    }
    var days = H.days; // ordered array
    // correction note
    var corr = document.getElementById("histCorrNote");
    if (corr && H.note) corr.innerHTML = H.note;

    // summary stats
    var sourceDays = days.filter(function(d){return isDataStatus(d.status);});
    var gapDays = days.filter(function(d){return d.status==="gap"||d.status==="fetch_failed";});
    var priorDays = days.filter(function(d){return d.status==="prior";});
    var means = sourceDays.map(function(d){return d.mean;}).filter(function(x){return x!=null;});
    var overallMean = means.length? means.reduce(function(a,b){return a+b;},0)/means.length : null;
    var peakDay = sourceDays.reduce(function(a,b){return (b.peak!=null && (a==null||b.peak>a.peak))?b:a;}, null);
    var stats = document.getElementById("histStats");
    stats.innerHTML =
      '<div class="hstat"><div class="hstat-k">Days requested</div><div class="hstat-v">' + days.length + '</div><div class="hstat-note">across the requested ranges</div></div>' +
      '<div class="hstat"><div class="hstat-k">Source-reconstructed</div><div class="hstat-v">' + sourceDays.length + '</div><div class="hstat-note">retrieved from FDSN</div></div>' +
      '<div class="hstat"><div class="hstat-k">Gap days</div><div class="hstat-v">' + gapDays.length + '</div><div class="hstat-note">no source data</div></div>' +
      '<div class="hstat"><div class="hstat-k">Avg daily HDF mean</div><div class="hstat-v">' + (overallMean!=null?overallMean.toFixed(3):"\u2014") + '<span class="kpi-unit"> Pa</span></div><div class="hstat-note">' + (peakDay?("peak day "+peakDay.date+" @ "+peakDay.peak.toFixed(2)+" Pa"):"") + '</div></div>';

    buildHistChart();
    buildHistTable();
    buildPeerBaseline();
    buildPeerChart();
    buildExceedanceTable();
    buildPeerDrilldown();
    buildStatCards();
    buildGapInventory();
    buildSeverityLegend();
    buildPlainSummary();
    buildBriefing();
  }

  // ---------- gap inventory (synchronized to unified model) ----------
  function buildGapInventory(){
    var el = document.getElementById("gapInventory"); if (!el || !U) return;
    var inv = U.gap_inventory || [];
    if (!inv.length){ el.innerHTML = '<p class="table-foot">No coverage gaps recorded in the documented window.</p>'; return; }
    function fmtDur(sec){
      if (sec>=86400) return "full day";
      if (sec>=60) return (sec/60).toFixed(sec>=600?0:1)+" min";
      return sec.toFixed(1)+" s";
    }
    var intra = inv.filter(function(g){ return g.channel!=="day"; });
    var whole = inv.filter(function(g){ return g.channel==="day"; });
    var rows = inv.map(function(g){
      var span = g.channel==="day"
        ? (g.date+" (full day)")
        : (g.start.slice(11,19)+"–"+g.end.slice(11,19)+" UTC");
      return '<tr>'+
        '<td class="hour-label">'+g.date+'</td>'+
        '<td class="num">'+g.doy+'</td>'+
        '<td>'+(g.channel==="day"?"—":g.channel)+'</td>'+
        '<td>'+span+'</td>'+
        '<td class="num">'+fmtDur(g.seconds)+'</td>'+
        '<td>'+(g.reason||"intra-day dropout")+'</td>'+
      '</tr>';
    }).join("");
    el.innerHTML =
      '<p class="table-foot">'+intra.length+' intra-day dropout(s) within uploaded local days · '+
      whole.length+' whole-day gap(s) in the FDSN range. No values interpolated.</p>'+
      '<div class="table-wrap"><table class="data-table"><thead><tr>'+
      '<th scope="col">Date</th><th scope="col" class="num">DOY</th><th scope="col">Channel</th>'+
      '<th scope="col">Span</th><th scope="col" class="num">Duration</th><th scope="col">Reason</th>'+
      '</tr></thead><tbody>'+rows+'</tbody></table></div>';
  }

  // ---------- reference citations (cited in UI) ----------
  var REFS = {
    rsFdsn: "https://manual.raspberryshake.org/fdsn.html",
    rsDev: "https://manual.raspberryshake.org/developersCorner.html",
    rsData: "https://raspberryshake.org/legacy-data/",
    rsLicense: "https://shop.raspberryshake.org/license/",
    fdsnAM: "https://www.fdsn.org/networks/detail/AM/",
    peterson: "https://pubs.usgs.gov/of/2005/1438/pdf/OFR-1438.pdf",
    iso7196: "https://www.iso.org/standard/13813.html",
    niosh: "https://www.cdc.gov/niosh/hhe/reports/pdfs/2019-0119-3362.pdf",
    nycOctave: "https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-135567",
    detroit: "https://library.municode.com/mi/detroit/codes/code_of_ordinances",
    jasaMethod: "https://pubs.aip.org/jasa/article/144/5/3036/646264/Digital-acoustic-sensor-performance-across-the"
  };

  function num(v, d){ return v==null ? "\u2014" : Number(v).toFixed(d==null?2:d); }
  function umFmt(v){ return v==null ? "\u2014" : (v*1e6).toFixed(2); }

  // ---------- statistics cards (synchronized to unified model) ----------
  function buildStatCards(){
    var el = document.getElementById("statCards"); if (!el || !U) return;
    var c = U.counts, wi = U.worst_hdf_instant, ws = U.worst_hdf_sustained,
        ei = U.worst_ehz_instant, es2 = U.worst_ehz_sustained, bd = U.band_day_counts;
    function bandChip(k){
      var b = (U.bands||[]).filter(function(x){return x.key===k;})[0];
      if (!b) return "";
      return '<span class="band-chip" style="background:'+b.color+'">'+b.label+'</span>';
    }
    var cards = [];
    cards.push('<div class="stat-card"><div class="stat-k">Documented days</div><div class="stat-v">'+c.documented_days_overall+'</div>'+
      '<div class="stat-note">'+c.documented_days_local+' uploaded + '+c.documented_days_fdsn+' FDSN \u00b7 '+c.gap_days+' gap days</div></div>');
    cards.push('<div class="stat-card"><div class="stat-k">Per-channel documented</div><div class="stat-v">'+c.documented_days_hdf+' <span class="stat-sub">HDF</span></div>'+
      '<div class="stat-note">'+c.documented_days_ehz+' days EHZ (secondary, uploaded full-rate only)</div></div>');
    var wiBand = (wi&&wi.analysis_band) ? (" \u00b7 "+wi.analysis_band+" band") : "";
    var wsBand = (ws&&ws.analysis_band) ? (ws.analysis_band) : "0.1\u20138 Hz";
    cards.push('<div class="stat-card stat-hero"><div class="stat-k">Worst HDF instantaneous</div><div class="stat-v">'+num(wi&&wi.value,3)+'<span class="stat-unit"> Pa</span></div>'+
      '<div class="stat-note">'+(wi?(wi.date+(wi.time_detroit?(" \u00b7 "+wi.time_detroit.slice(11)+" EDT"):" \u00b7 daily peak")):"")+wiBand+' '+bandChip(wi&&wi.band)+'</div></div>');
    cards.push('<div class="stat-card stat-hero"><div class="stat-k">Worst HDF sustained event</div><div class="stat-v">'+(ws?ws.duration_minutes:0)+'<span class="stat-unit"> min</span></div>'+
      '<div class="stat-note">'+(ws?(ws.date+" \u00b7 "+ws.event_start_detroit.slice(11)+"\u2013"+ws.event_end_detroit.slice(11)+" EDT \u00b7 peak "+num(ws.peak_value,3)+" Pa"):"none above threshold")+' '+bandChip(ws&&ws.band)+'</div>'+
      '<div class="stat-fine">Event = contiguous minutes with HDF RMS \u2265 3\u00d7 that day\u2019s median (transparent, fixed rule). RMS passband '+wsBand+'.</div></div>');
    cards.push('<div class="stat-card"><div class="stat-k">Worst EHZ instantaneous <span class="sec-tag">secondary</span></div><div class="stat-v">'+umFmt(ei&&ei.value)+'<span class="stat-unit"> \u00b5m/s</span></div>'+
      '<div class="stat-note">'+(ei?(ei.date+(ei.time_detroit?(" \u00b7 "+ei.time_detroit.slice(11)+" EDT"):"")):"")+'</div></div>');
    var esTxt = es2 ? (es2.duration_minutes+" min \u00b7 "+es2.date) : "No EHZ minute exceeded 3\u00d7 median";
    cards.push('<div class="stat-card"><div class="stat-k">Worst EHZ sustained <span class="sec-tag">secondary</span></div><div class="stat-v">'+(es2?es2.duration_minutes:0)+'<span class="stat-unit"> min</span></div>'+
      '<div class="stat-note">'+esTxt+'</div></div>');
    el.innerHTML = cards.join("");
  }

  // ---------- external network-peer baseline (primary benchmark) ----------
  function pctlBandOf(meanPa){
    // classify an R6E8A daily-mean against fixed peer-percentile thresholds
    if (!P || !P.peer_daily_mean_pa) return null;
    var q = P.peer_daily_mean_pa;
    if (q.p99==null||q.p95==null||q.p75==null) return null;
    if (meanPa >= q.p99) return "red";
    if (meanPa >= q.p95) return "orange";
    if (meanPa >= q.p75) return "yellow";
    return "reference";
  }
  function peerDayCounts(){
    if (!U || !P || !P.peer_daily_mean_pa) return null;
    var c = {red:0,orange:0,yellow:0,reference:0};
    U.days.forEach(function(d){
      if (isDataStatus(d.status) && d.mean!=null){
        var b = pctlBandOf(d.mean); if (b) c[b]++;
      }
    });
    return c;
  }
  function buildPeerBaseline(){
    var note = document.getElementById("peerNote");
    var cardsEl = document.getElementById("peerCards");
    if (!note || !cardsEl) return;
    if (!P || !P.peer_daily_mean_pa || !P.peer_daily_mean_pa.n){
      note.className = "peer-note peer-unavailable";
      note.innerHTML = '<strong>External benchmark unavailable.</strong> Live retrieval of the public '+
        'Raspberry Shake HDF peer distribution did not return a usable sample for this build, so no peer '+
        'percentiles are shown. This station is <em>not</em> used as its own baseline. The published external-reference '+
        'framework below (units, weighting, and non-comparable context) still applies. No percentiles were fabricated.';
      cardsEl.innerHTML = '';
      return;
    }
    var m = P.peer_daily_mean_pa, pk = P.peer_daily_peak_pa, r = P.r6e8a, cc = P.counts;
    note.className = "peer-note";
    note.innerHTML =
      '<strong>Method &amp; provenance.</strong> Metric-matched cross-station comparison via the '+
      '<a href="'+REFS.rsFdsn+'" target="_blank" rel="noopener">Raspberry Shake FDSN web services</a> '+
      '(network <a href="'+REFS.fdsnAM+'" target="_blank" rel="noopener">AM</a>). '+
      'Matched window <span class="mono">'+P.matched_window_utc+' UTC</span>; metric = per-minute 60&nbsp;s demeaned RMS of HDF pressure (Pa), '+
      'daily mean-of-minutes; RMS band <span class="mono">'+P.rms_band+'</span>; identical per-station StationXML response removal. '+
      'Sample: <strong>'+m.n+'</strong> unique peer stations computed (of '+cc.available_with_data+' available with data on the day, '+
      cc.candidates_epoch_covers_day+' candidates whose epoch covers the day; '+cc.failed_retrieval+' failed retrieval), '+
      'selected by a deterministic longitude-stratified rule (&le;'+ (cc.selected/ Math.max(cc.longitude_bands,1) | 0) +' per band across '+cc.longitude_bands+' bands). '+
      'R6E8A excluded; each station counted once. Retrieved '+ (P.generated_utc||"").slice(0,16).replace("T"," ") +' UTC. '+
      '<span class="mono">data/peer_baseline.json</span> carries the full station list and per-station values. '+
      '<em>Not "all worldwide" &mdash; a documented, reproducible sample.</em>';
    function card(k,v,unit,sub,hero){
      return '<div class="stat-card'+(hero?' stat-hero':'')+'"><div class="stat-k">'+k+'</div>'+
        '<div class="stat-v">'+v+(unit?'<span class="stat-unit"> '+unit+'</span>':'')+'</div>'+
        '<div class="stat-note">'+sub+'</div></div>';
    }
    var cards = [];
    cards.push(card("Peer median daily-mean HDF", num(m.median,3), "Pa",
      "P75 "+num(m.p75,3)+" \u00b7 P90 "+num(m.p90,3)+" \u00b7 P95 "+num(m.p95,3)+" \u00b7 P99 "+num(m.p99,3)+" Pa"));
    cards.push(card('R6E8A vs peers <span class="pill pill-ext">external</span>',
      (r.mean_percentile_vs_peers!=null?r.mean_percentile_vs_peers:"\u2014"), "pctl",
      "Matched-day daily-mean "+num(r.matched_day_daily_mean_pa,3)+" Pa placed in the peer distribution", true));
    cards.push(card("Peer daily-peak reference", num(pk.median,3), "Pa",
      "Peer peak-minute P95 "+num(pk.p95,3)+" \u00b7 P99 "+num(pk.p99,3)+" Pa; R6E8A matched-day peak "+num(r.matched_day_daily_peak_pa,3)+" Pa (pctl "+(r.peak_percentile_vs_peers!=null?r.peak_percentile_vs_peers:"\u2014")+")"));
    cards.push(card("Peer sample &amp; coverage", m.n, "stations",
      "Matched window "+P.matched_window_utc+" \u00b7 band "+P.rms_band+" \u00b7 unweighted Pa RMS"));
    cardsEl.innerHTML = cards.join("");
  }

  // ---------- peer-baseline comparison chart ----------
  function buildPeerChart(){
    var el = document.getElementById("chartPeer"); if (!el || !H) return;
    destroyPeerChart();
    var days = H.days;
    var q = peerQ(peerMetric);
    var haveQ = !!(q && q.median!=null && q.p75!=null && q.p95!=null && q.p99!=null);
    var labels = days.map(function(d){return d.date;});
    var vals=[], colors=[], radii=[];
    var maxVal = 0;
    days.forEach(function(d){
      var v = dayVal(d, peerMetric);
      vals.push(v==null?null:v);
      if (v!=null && v>maxVal) maxVal=v;
      var b = bandOfVal(peerMetric, v);
      colors.push(b?PEER_BAND[b].color:"rgba(0,0,0,0)");
      radii.push(v==null?0:(b==="red"||b==="orange"?5:4));
    });
    var ink3=css("--ink-3"), grid=css("--grid-line"), surface=css("--surface"),
        border=css("--border-strong"), ink=css("--ink"), gapc=css("--amber-2");
    var yMax = haveQ ? Math.max(maxVal, q.p99)*1.08 : (maxVal*1.15||1);

    var gapPlugin = {
      id:"peergapbands",
      beforeDatasetsDraw:function(chart){
        var c2=chart.ctx, xa=chart.scales.x, ya=chart.scales.y;
        days.forEach(function(d,i){
          if (d.status==="gap"||d.status==="fetch_failed"){
            var xc=xa.getPixelForValue(i);
            var half=(xa.getPixelForValue(1)-xa.getPixelForValue(0))/2 || 6;
            c2.save(); c2.fillStyle=gapc+"1e"; c2.fillRect(xc-half, ya.top, half*2, ya.bottom-ya.top);
            c2.strokeStyle=gapc+"66"; c2.lineWidth=1;
            for (var x=xc-half; x<xc+half; x+=6){ c2.beginPath(); c2.moveTo(x, ya.bottom); c2.lineTo(x+(ya.bottom-ya.top), ya.top); c2.stroke(); }
            c2.restore();
          }
        });
      }
    };
    var pctlPlugin = {
      id:"peerpctllines",
      afterDatasetsDraw:function(chart){
        if (!haveQ) return;
        var c2=chart.ctx, xa=chart.scales.x, ya=chart.scales.y;
        var lines=[
          {v:q.median, c:"#64748b", t:"Median "+num(q.median,3)},
          {v:q.p75, c:"#ca8a04", t:"P75 "+num(q.p75,3)},
          {v:q.p95, c:"#ea580c", t:"P95 "+num(q.p95,3)},
          {v:q.p99, c:"#dc2626", t:"P99 "+num(q.p99,3)}
        ];
        c2.save();
        c2.font="10px JetBrains Mono, monospace";
        lines.forEach(function(ln){
          if (ln.v==null || ln.v>ya.max) return;
          var y=ya.getPixelForValue(ln.v);
          c2.strokeStyle=ln.c; c2.lineWidth=1.4; c2.setLineDash([6,4]);
          c2.beginPath(); c2.moveTo(xa.left, y); c2.lineTo(xa.right, y); c2.stroke();
          c2.setLineDash([]);
          var lbl=ln.t; var w=c2.measureText(lbl).width+8;
          c2.fillStyle=ln.c; c2.globalAlpha=0.92;
          c2.fillRect(xa.right-w-2, y-13, w, 13);
          c2.globalAlpha=1; c2.fillStyle="#fff"; c2.textAlign="left"; c2.textBaseline="middle";
          c2.fillText(lbl, xa.right-w+2, y-6);
        });
        c2.restore();
      }
    };
    var ctx=el.getContext("2d");
    peerChart=new Chart(ctx,{
      type:"line",
      data:{ labels:labels, datasets:[{
        data:vals, spanGaps:false,
        borderColor:css("--ink-3")+"66", borderWidth:1.4,
        pointBackgroundColor:colors, pointBorderColor:colors, pointRadius:radii,
        pointHoverRadius:7, tension:0.15
      }]},
      options:{
        responsive:true, maintainAspectRatio:false,
        interaction:{ mode:"index", intersect:false },
        plugins:{
          legend:{display:false},
          tooltip:{
            backgroundColor:surface, titleColor:ink, bodyColor:css("--ink-2"), borderColor:border, borderWidth:1,
            padding:10, displayColors:false, titleFont:{family:"General Sans",weight:"600"}, bodyFont:{family:"JetBrains Mono"},
            callbacks:{
              title:function(items){ var d=days[items[0].dataIndex]; return d.date+" (DOY "+d.doy+")"; },
              label:function(item){
                var d=days[item.dataIndex];
                if (d.status==="gap"||d.status==="fetch_failed") return "gap — no source data (not interpolated)";
                var v=dayVal(d, peerMetric);
                if (v==null) return "no "+metricLabel(peerMetric)+" value";
                var src = d.status==="local" ? "uploaded" : (d.status==="source"?"FDSN":d.status);
                var b=bandOfVal(peerMetric,v), bl=b?PEER_BAND[b].label:"—";
                var pctl=peerPctl(peerMetric,v);
                var out=[
                  "HDF "+metricLabel(peerMetric)+": "+num(v,3)+" Pa · "+src,
                  "band: "+bl+(pctl!=null?"  ·  peer pctl "+pctl:"")
                ];
                if (haveQ){
                  var ratio=v/q.median, db=20*Math.log10(v/q.median);
                  out.push("vs peer median: ×"+num(ratio,2)+"  ·  "+(db>=0?"+":"")+num(db,1)+" dB");
                }
                out.push("coverage: "+(d.coverage!=null?d.coverage+"%":"—"));
                return out;
              }
            }
          }
        },
        scales:{
          x:{ ticks:{ color:ink3, maxTicksLimit:14, font:{family:"JetBrains Mono",size:9},
               callback:function(v){ return this.getLabelForValue(v).slice(5); } }, grid:{ color:grid, drawTicks:false } },
          y:{ ticks:{ color:ink3, font:{family:"JetBrains Mono",size:10} }, grid:{ color:grid, drawTicks:false },
              beginAtZero:true, suggestedMax:yMax,
              title:{ display:true, text:"HDF "+metricLabel(peerMetric)+" (Pa) vs peer percentiles", color:ink3, font:{family:"General Sans",size:11} } }
        }
      },
      plugins:[gapPlugin, pctlPlugin]
    });

    // methodology beside chart
    var meth=document.getElementById("peerChartMethod");
    if (meth){
      if (!haveQ){
        meth.className="peer-note peer-unavailable";
        meth.innerHTML='<strong>External peer distribution unavailable</strong> for this build, so no baseline lines are drawn and no percentiles are shown. This station is not used as its own baseline; no values were fabricated.';
      } else {
        meth.className="peer-note";
        meth.innerHTML=
          '<strong>Baseline.</strong> '+q.n+' valid globally longitude-stratified public Raspberry Shake HDF peers, matched UTC day <span class="mono">'+
          P.matched_window_utc+'</span>, RMS band <span class="mono">'+P.rms_band+'</span>, response-corrected pressure (Pa), deterministic longitude-stratified selection, R6E8A excluded. '+
          'Retrieved '+(P.generated_utc||"").slice(0,16).replace("T"," ")+' UTC via '+
          '<a href="'+REFS.rsFdsn+'" target="_blank" rel="noopener">Raspberry Shake FDSN</a> (network <a href="'+REFS.fdsnAM+'" target="_blank" rel="noopener">AM</a>); '+
          'cross-station method per <a href="'+REFS.jasaMethod+'" target="_blank" rel="noopener">JASA</a>. '+
          metricLabel(peerMetric)+' thresholds: Median '+num(q.median,3)+' · P75 '+num(q.p75,3)+' · P95 '+num(q.p95,3)+' · P99 '+num(q.p99,3)+' Pa.';
      }
    }
  }

  function peerExceedRows(metric){
    if (!H) return [];
    var q=peerQ(metric); if(!q||q.p75==null) return [];
    var out=[];
    H.days.forEach(function(d){
      var v=dayVal(d, metric);
      if (v==null || v<q.p75) return;
      out.push({d:d, v:v, band:bandOfVal(metric,v), pctl:peerPctl(metric,v),
                ratio:(q.median?v/q.median:null),
                db:(q.median?20*Math.log10(v/q.median):null),
                src:(d.status==="local"?"uploaded":(d.status==="source"?"FDSN":d.status))});
    });
    out.sort(function(a,b){return b.v-a.v;});
    return out;
  }

  function buildExceedanceTable(){
    var body=document.getElementById("peerExceedBody"); if(!body) return;
    var lede=document.getElementById("peerExceedLede");
    var foot=document.getElementById("peerExceedFoot");
    var q=peerQ(peerMetric);
    if (!q || q.p75==null){
      body.innerHTML='<tr><td colspan="9">External peer distribution unavailable — exceedances cannot be computed. No values fabricated.</td></tr>';
      if (foot) foot.textContent="";
      return;
    }
    var rows=peerExceedRows(peerMetric);
    if (!rows.length){
      body.innerHTML='<tr><td colspan="9">No documented '+metricLabel(peerMetric)+' day reaches peer P75 ('+num(q.p75,3)+' Pa).</td></tr>';
    } else {
      body.innerHTML=rows.map(function(r){
        var bc=r.band?PEER_BAND[r.band]:null;
        var chip=bc?'<span class="band-chip" style="background:'+bc.color+'">'+bc.label+'</span>':"—";
        return '<tr>'+
          '<td class="hour-label">'+r.d.date+'</td>'+
          '<td class="num">'+r.d.doy+'</td>'+
          '<td class="num">'+num(r.v,3)+'</td>'+
          '<td>'+chip+'</td>'+
          '<td class="num">'+(r.pctl!=null?r.pctl:"—")+'</td>'+
          '<td class="num">'+(r.ratio!=null?"×"+num(r.ratio,2):"—")+'</td>'+
          '<td class="num">'+(r.db!=null?(r.db>=0?"+":"")+num(r.db,1):"—")+'</td>'+
          '<td><span class="pill pill-source">'+r.src+'</span></td>'+
          '<td class="num">'+(r.d.coverage!=null?r.d.coverage+"%":"—")+'</td>'+
        '</tr>';
      }).join("");
    }
    if (lede) lede.innerHTML='Documented days whose HDF <strong>'+metricLabel(peerMetric)+'</strong> reaches at least the 75th percentile of the peer '+
      (peerMetric==="peak"?"peak-minute":"daily-mean")+' distribution ('+num(q.p75,3)+' Pa), worst first. Use the toggle above to switch metric.';
    if (foot) foot.innerHTML=rows.length+' day(s) at/above peer P75 for the '+metricLabel(peerMetric)+' metric. dB vs median = 20&middot;log10(value/'+num(q.median,3)+' Pa), same metric/band only.';
  }

  function buildPeerDrilldown(){
    var el=document.getElementById("peerDrilldown"); if(!el||!H) return;
    var uploaded=H.days.filter(function(d){return d.status==="local";});
    var rows=uploaded.map(function(d){
      var w=d.hdf_worst||{};
      var pk=(d.peak!=null?num(d.peak,3):"—");
      var pt=w.peak_time_detroit||"—";
      var mab=(w.total_minutes_above_threshold!=null?w.total_minutes_above_threshold:"—");
      return '<tr><td class="hour-label">'+d.date+'</td><td class="num">'+d.doy+'</td>'+
        '<td class="num">'+pk+'</td><td>'+pt+'</td><td class="num">'+mab+'</td></tr>';
    }).join("");
    el.style.borderLeftColor="var(--amber-2)";
    el.innerHTML=
      '<strong style="color:var(--amber)">Uploaded days DOY102&ndash;109 &mdash; daily-summary granularity.</strong> '+
      'Full per-minute HDF RMS series are <em>not preserved in this static build</em>, so a per-minute spike timeline is not plotted here and none is fabricated. '+
      'The uploaded MiniSEED remains the authoritative source and the minute series is reproducible from it via <span class="mono">tools/</span>. '+
      'Below are the available within-day event descriptors for each uploaded day &mdash; the peak minute (Pa), its Detroit-local time, and the count of minutes above <em>that day&rsquo;s own</em> median&times;3 event rule. '+
      '<strong>These are within-event descriptors only</strong> (that day&rsquo;s own statistic), <strong>not</strong> a peer comparison and <strong>not</strong> a reference baseline; per-minute points are never compared to the daily peer thresholds.'+
      '<div class="table-wrap" style="margin-top:12px"><table class="data-table"><thead><tr>'+
      '<th scope="col">Date (Detroit)</th><th scope="col" class="num">DOY</th><th scope="col" class="num">Peak (Pa)</th>'+
      '<th scope="col">Peak minute</th><th scope="col" class="num">Min. &ge; own median&times;3</th>'+
      '</tr></thead><tbody>'+rows+'</tbody></table></div>';
  }

  // ---------- fixed severity legend ----------
  function buildSeverityLegend(){
    var el = document.getElementById("severityLegend"); if (!el || !U) return;
    var counts = peerDayCounts();
    var q = (P && P.peer_daily_mean_pa) ? P.peer_daily_mean_pa : null;
    function thr(band){
      if (!q) return "peer percentile unavailable";
      if (band==="red") return "\u2265 "+num(q.p99,3)+" Pa (peer P99)";
      if (band==="orange") return num(q.p95,3)+"\u2013"+num(q.p99,3)+" Pa (P95\u2013<P99)";
      if (band==="yellow") return num(q.p75,3)+"\u2013"+num(q.p95,3)+" Pa (P75\u2013<P95)";
      return "< "+num(q.p75,3)+" Pa (< P75)";
    }
    var bands = [
      {key:"red",    color:"#dc2626", label:"Priority 1 \u2014 at/above peer P99",
       desc:"R6E8A daily-mean HDF at or above the 99th percentile of the external Raspberry Shake HDF peer distribution."},
      {key:"orange", color:"#ea580c", label:"Priority 2 \u2014 peer P95\u2013<P99",
       desc:"Daily-mean between the 95th and 99th percentiles of the peer distribution."},
      {key:"yellow", color:"#ca8a04", label:"Priority 3 \u2014 peer P75\u2013<P95",
       desc:"Daily-mean between the 75th and 95th percentiles of the peer distribution."},
      {key:"reference", color:"#0f766e", label:"Reference \u2014 below peer P75",
       desc:"Daily-mean below the 75th percentile of the peer distribution."}
    ];
    var rows = bands.map(function(b){
      var cnt = counts ? (counts[b.key]+" days") : "N/A";
      return '<div class="sev-row">'+
        '<span class="sev-swatch" style="background:'+b.color+'"></span>'+
        '<div class="sev-main"><div class="sev-label">'+b.label+' <span class="sev-range mono">'+thr(b.key)+'</span></div>'+
        '<div class="sev-desc">'+b.desc+'</div></div>'+
        '<div class="sev-count"><strong>'+(counts?counts[b.key]:"N/A")+'</strong>'+(counts?" days":"")+'<span class="sev-min">R6E8A documented days</span></div>'+
      '</div>';
    }).join("");
    el.innerHTML = rows;
    var cav = document.getElementById("severityCaveat");
    if (cav) cav.innerHTML =
      '<p><strong>What these tiers are \u2014 and are not.</strong> They are a fixed <em>monitoring-priority</em> ordering defined against the '+
      'external <a href="'+REFS.rsFdsn+'" target="_blank" rel="noopener">Raspberry Shake HDF peer distribution</a>, not this station&rsquo;s own history and not a medical or human-exposure hazard band. '+
      'The rules (Red&nbsp;&ge;&nbsp;P99, Orange&nbsp;P95&ndash;&lt;P99, Yellow&nbsp;P75&ndash;&lt;P95, Reference&nbsp;&lt;&nbsp;P75) are immutable; only the R6E8A day counts placed against them change with the data. '+
      (q ? 'Peer thresholds are computed from '+q.n+' unique peer stations over the matched window '+P.matched_window_utc+' UTC (band '+P.rms_band+').'
         : 'The external peer distribution is currently unavailable, so day counts are shown as <strong>N/A</strong> rather than derived from this station alone.')+'</p>'+
      '<p class="sev-refs">These tiers do not convert HDF pressure into any published acoustic or seismic threshold. See <a href="#ctx-h">Frequency and pressure context</a> for why A-weighted ordinances (dBA), ISO&nbsp;7196 dBG, and the Peterson seismic PSD models are shown only as non-comparable context.</p>';
  }

  // ---------- plain-language summary ----------
  function buildPlainSummary(){
    var el = document.getElementById("plainSummary"); if (!el || !U) return;
    var c = U.counts, wi = U.worst_hdf_instant, ws = U.worst_hdf_sustained;
    var peerTxt;
    if (P && P.peer_daily_mean_pa && P.peer_daily_mean_pa.n && P.r6e8a && P.r6e8a.mean_percentile_vs_peers!=null){
      peerTxt = 'Compared with an external distribution of '+P.peer_daily_mean_pa.n+' other public Raspberry Shake HDF stations over the matched window '+
        P.matched_window_utc+' (identical units and band), R6E8A&rsquo;s daily-mean pressure sits at about the '+
        '<strong>'+P.r6e8a.mean_percentile_vs_peers+'th percentile</strong> of that peer distribution (peer median '+num(P.peer_daily_mean_pa.median,3)+' Pa). ';
    } else {
      peerTxt = 'The external Raspberry Shake HDF peer distribution used as the benchmark is currently unavailable, so no peer percentile is shown for this build (this station is not used as its own baseline). ';
    }
    el.innerHTML =
      '<h2 class="section-title" style="margin-top:0">In plain language</h2>'+
      '<p>This station (Raspberry Shake <span class="mono">AM.R6E8A</span>, Detroit) measures tiny air-pressure changes (infrasound, channel <strong>HDF</strong>) and ground motion (channel <strong>EHZ</strong>). Across <strong>'+c.documented_days_overall+' documented days</strong>, the strongest single HDF pressure reading was <strong>'+num(wi&&wi.value,2)+' Pa</strong>'+(wi?(" on "+wi.date):"")+', and the longest continuously elevated stretch lasted <strong>'+(ws?ws.duration_minutes:0)+' minutes</strong>'+(ws?(" on "+ws.date):"")+'. '+
      peerTxt+
      'These are measurements of a signal at one sensor. The station record does <em>not</em> by itself identify the source, the propagation path, conditions at other locations, or compliance with a differently weighted standard.</p>';
  }

  // ---------- 24-hour briefing ----------
  function briefingText(){
    if (!U) return "";
    var c = U.counts, wi = U.worst_hdf_instant, ws = U.worst_hdf_sustained,
        ei = U.worst_ehz_instant, agg = U.aggregate;
    var gen = genTimeStr();
    var counts = peerDayCounts();
    var q = (P && P.peer_daily_mean_pa) ? P.peer_daily_mean_pa : null;
    var L = [];
    L.push("R6E8A 24-Hour Watchdog \u2014 HDF Pressure / Infrasound Measurement Briefing");
    L.push("=".repeat(84));
    L.push("Station: Raspberry Shake AM.R6E8A (Detroit) \u00b7 Primary channel HDF (infrasound, Pa) \u00b7 Secondary EHZ (ground velocity, m/s)");
    L.push("Prepared: "+gen);
    L.push("Status: PREVIEW / EXPORT ONLY \u2014 not sent. No email dispatched from this dashboard.");
    L.push("");
    var DLY = window.__TREMORLENS_DAILY__ || null;
    if (DLY) {
      L.push("0A) FIXED DAILY 24-HOUR WINDOW");
      L.push("   Report window (fixed): "+DLY.report_window_et.start+" -> "+DLY.report_window_et.end+" (07:00 AM ET cutoff).");
      L.push("   Archived, not real-time; generated after the Raspberry Shake archive delay. Latest data-through: HDF "+
             (DLY.data_through_et.HDF||"-")+" ET, EHZ "+(DLY.data_through_et.EHZ||"-")+" ET.");
      L.push("");
    }
    if (EV) {
      L.push("0B) TOP EVENTS & AVERAGES vs CHANNEL AGGREGATE ARITHMETIC MEAN (percent difference; PRIMARY)");
      L.push("   Definition: TOP = contiguous one-minute intervals above the channel external peer aggregate mean.");
      L.push("   HDF aggregate mean "+EV.peer_means.hdf_pa.toFixed(4)+" Pa (N="+EV.peer_means.hdf_n+
             "); EHZ aggregate mean "+EV.peer_means.ehz_umps.toFixed(2)+" um/s (N="+EV.peer_means.ehz_n+").");
      ["hdf","ehz"].forEach(function(ch){
        var b=EV[ch], a=b.averages, u=ch==="ehz"?"um/s":"Pa", dec=ch==="ehz"?2:4, nm=ch.toUpperCase();
        function line(e){ return "     #"+e.rank+" "+e.date+" "+timePart(e.start_et)+"-"+timePart(e.end_et)+
          " ("+e.duration_min+" min) peak "+e.extreme.toFixed(dec)+" "+u+
          " = "+(e.percent_diff>=0?"+":"")+e.percent_diff.toFixed(1)+"% vs mean"; }
        L.push("   "+nm+" TOP (above mean), best 5 of "+b.top.length+":");
        b.top.slice(0,5).forEach(function(e){ L.push(line(e)); });
        L.push("   "+nm+" AVERAGE vs baseline: overall daily mean "+(a.overall_daily_mean==null?"-":a.overall_daily_mean.toFixed(dec)+" "+u)+
          " ("+(a.overall_pct_vs_peer==null?"-":(a.overall_pct_vs_peer>=0?"+":"")+a.overall_pct_vs_peer.toFixed(1)+"%")+" vs mean) across "+
          a.day_count+" local days; no-spike days: "+a.no_spike_count+(a.no_spike_count?(" ("+a.no_spike_dates.join(", ")+")"):""));
      });
      L.push("   Full Top 20 + daily/segment averages per channel + CSV exports are in the dashboard's primary tab.");
      L.push("   Note: occupancy/presence are separate user-supplied annotations, not instrument data.");
      L.push("");
    }
    L.push("1) DOCUMENTED COVERAGE");
    L.push("   Documented days (overall): "+c.documented_days_overall+"  [uploaded full-rate: "+c.documented_days_local+", FDSN: "+c.documented_days_fdsn+"]");
    L.push("   Per channel: HDF "+c.documented_days_hdf+" days; EHZ "+c.documented_days_ehz+" days (secondary, uploaded only)");
    L.push("   Gap days (no source data, never interpolated): "+c.gap_days);
    L.push("");
    L.push("2) WORST OBSERVED \u2014 HDF (PRIMARY, raw R6E8A values)");
    L.push("   Worst instantaneous point: "+num(wi&&wi.value,3)+" Pa"+(wi?(" on "+wi.date+(wi.time_detroit?(" at "+wi.time_detroit.slice(11)+" EDT"):" (daily peak)")):"")+"  [band: "+(wi&&wi.analysis_band||"0.1-8 Hz")+"]");
    if (ws) {
      L.push("   Worst sustained event: "+ws.duration_minutes+" min ("+ws.event_start_detroit.slice(11)+"\u2013"+ws.event_end_detroit.slice(11)+" EDT) on "+ws.date);
      L.push("     peak "+num(ws.peak_value,3)+" Pa; threshold "+num(ws.threshold_value,3)+" Pa (contiguous minutes >= 3x that day's median)");
    } else {
      L.push("   Worst sustained event: none exceeded the 3x-median threshold.");
    }
    L.push("");
    L.push("3) WORST OBSERVED \u2014 EHZ (SECONDARY)");
    L.push("   Worst instantaneous point: "+umFmt(ei&&ei.value)+" \u00b5m/s"+(ei?(" on "+ei.date+(ei.time_detroit?(" at "+ei.time_detroit.slice(11)+" EDT"):"")):""));
    L.push("");
    L.push("4) EXTERNAL REFERENCE \u2014 RASPBERRY SHAKE HDF NETWORK-PEER PERCENTILE (primary benchmark)");
    if (q && q.n && P.r6e8a && P.r6e8a.mean_percentile_vs_peers!=null){
      L.push("   Metric-matched across "+q.n+" unique public AM HDF peer stations; matched window "+P.matched_window_utc+" UTC; band "+P.rms_band+"; per-station response removal.");
      L.push("   Peer daily-mean HDF (Pa): median "+num(q.median,3)+" | P75 "+num(q.p75,3)+" | P90 "+num(q.p90,3)+" | P95 "+num(q.p95,3)+" | P99 "+num(q.p99,3));
      L.push("   R6E8A matched-day daily-mean "+num(P.r6e8a.matched_day_daily_mean_pa,3)+" Pa = ~"+P.r6e8a.mean_percentile_vs_peers+"th percentile of the peer distribution.");
      L.push("   FIXED monitoring-priority percentile bands (immutable rules; external peer thresholds):");
      L.push("     RED >= P99 ("+num(q.p99,3)+" Pa): "+(counts?counts.red:"N/A")+" days | ORANGE P95-<P99: "+(counts?counts.orange:"N/A")+" days"+
             " | YELLOW P75-<P95: "+(counts?counts.yellow:"N/A")+" days | REFERENCE < P75: "+(counts?counts.reference:"N/A")+" days");
      L.push("   Sample selection: deterministic longitude-stratified public AM HDF stations; R6E8A excluded; each station counted once. Not 'all worldwide'.");
    } else {
      L.push("   External peer distribution UNAVAILABLE for this build \u2014 no peer percentiles shown; band day counts N/A.");
      L.push("   This station is NOT used as its own baseline; no percentiles were fabricated.");
    }
    L.push("   Aggregate (raw R6E8A): mean of daily means "+num(agg.mean_of_daily_means,3)+" Pa; max daily peak "+num(agg.max_daily_peak,3)+" Pa.");
    L.push("");
    L.push("5) GAPS & PENDING");
    L.push("   Gap days: "+U.days.filter(function(d){return d.status==="gap";}).map(function(d){return d.date+" (DOY"+d.doy+")";}).join(", "));
    L.push("   Live HDF feed: requested 11:08 PM-3:48 AM window fully covered; latest source sample "+(D.summary.latest_sample_detroit||"")+" EDT.");
    L.push("");
    L.push("6) PROVENANCE");
    L.push("   HDF->Pa via StationXML response removal (uploaded full-rate decimated to 25 Hz; FDSN days to 20 Hz).");
    L.push("   DOY109 uploaded twice with identical SHA-256; counted once. No interpolation anywhere.");
    L.push("");
    L.push("7) MEASUREMENT LIMITATIONS (EVIDENCE-FIRST)");
    L.push("   These are measured pressure/infrasound and ground-motion signals at ONE sensor. The station record does not by");
    L.push("   itself identify the source, the propagation path, conditions at other locations, or compliance with a differently");
    L.push("   weighted standard. The percentile tiers are MONITORING-PRIORITY orderings against the external Raspberry Shake");
    L.push("   HDF peer distribution, not medical or human-exposure hazard bands. HDF Pa is unweighted/broadband; A-weighted");
    L.push("   ordinances (dBA), ISO 7196 dBG, and the Peterson seismic PSD models are different metrics and are context only,");
    L.push("   never applied as safety/hazard/exposure thresholds for this data.");
    L.push("");
    L.push("REFERENCES:");
    L.push("   Raspberry Shake FDSN web services: "+REFS.rsFdsn);
    L.push("   Raspberry Shake HDF conversion (Developer's Corner): "+REFS.rsDev);
    L.push("   Raspberry Shake data access / license: "+REFS.rsData+" ; "+REFS.rsLicense);
    L.push("   Infrasound cross-station methodology (JASA): "+REFS.jasaMethod);
    L.push("   Context (not comparable): ISO 7196 "+REFS.iso7196+" ; NIOSH "+REFS.niosh+" ; Peterson "+REFS.peterson);
    return L.join("\n");
  }

  function buildBriefing(){
    var pre = document.getElementById("briefingPreview"); if (!pre) return;
    pre.textContent = briefingText();
    var bt = document.getElementById("btnBriefTxt");
    if (bt) bt.addEventListener("click", function(){
      download("R6E8A_24h_briefing.txt", briefingText(), "text/plain");
    });
    var bc = document.getElementById("btnBriefCopy");
    if (bc) bc.addEventListener("click", function(){
      var txt = briefingText();
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(function(){ bc.textContent="Copied"; setTimeout(function(){bc.textContent="Copy to clipboard";},1500); })
          .catch(function(){ bc.textContent="Copy failed"; });
      } else { bc.textContent="Clipboard unavailable"; }
    });
  }

  function buildHistChart(){
    if (!H) return;
    var el = document.getElementById("chartHist"); if (!el) return;
    destroyHist();
    var days = H.days;
    var labels = days.map(function(d){return d.date;});
    var teal = css("--teal"), prior = css("--border-strong"), gapc = css("--amber-2");
    var vals=[], colors=[];
    days.forEach(function(d){
      var v = isDataStatus(d.status) ? (d[histMetric]!=null?d[histMetric]:d.mean) : null;
      vals.push(v);
      colors.push(isDataStatus(d.status)?(d.status==="prior"?prior:teal):"transparent");
    });
    var ink3 = css("--ink-3"), grid = css("--grid-line"), surface = css("--surface"), border = css("--border-strong"), ink = css("--ink");
    var gapPlugin = {
      id:"gapbands",
      beforeDatasetsDraw:function(chart){
        var c2=chart.ctx, xa=chart.scales.x, ya=chart.scales.y;
        days.forEach(function(d,i){
          if (d.status==="gap"||d.status==="fetch_failed"){
            var xc = xa.getPixelForValue(i);
            var half = (xa.getPixelForValue(1)-xa.getPixelForValue(0))/2 || 6;
            c2.save();
            c2.fillStyle = gapc + "1e";
            c2.fillRect(xc-half, ya.top, half*2, ya.bottom-ya.top);
            c2.strokeStyle = gapc + "66"; c2.lineWidth=1;
            for (var x=xc-half; x<xc+half; x+=6){ c2.beginPath(); c2.moveTo(x, ya.bottom); c2.lineTo(x+(ya.bottom-ya.top), ya.top); c2.stroke(); }
            c2.restore();
          }
        });
      }
    };
    var ctx = el.getContext("2d");
    histChart = new Chart(ctx, {
      type:"bar",
      data:{ labels:labels, datasets:[{ data:vals, backgroundColor:colors, borderRadius:2, maxBarThickness:26 }] },
      options:{
        responsive:true, maintainAspectRatio:false,
        interaction:{ mode:"index", intersect:false },
        plugins:{
          legend:{display:false},
          tooltip:{
            backgroundColor:surface, titleColor:ink, bodyColor:css("--ink-2"), borderColor:border, borderWidth:1, padding:10, displayColors:false,
            titleFont:{family:"General Sans",weight:"600"}, bodyFont:{family:"JetBrains Mono"},
            callbacks:{
              title:function(items){ var d=days[items[0].dataIndex]; return d.date + " (DOY " + d.doy + ")"; },
              label:function(ctx){
                var d=days[ctx.dataIndex];
                if (d.status==="gap"||d.status==="fetch_failed") return "gap \u2014 no source data";
                if (d.status==="prior") return "prior-summary only";
                var src = d.status==="local" ? " \u00b7 uploaded" : " \u00b7 FDSN";
                return "mean " + (d.mean!=null?d.mean.toFixed(3):"\u2014") + " Pa \u00b7 peak " + (d.peak!=null?d.peak.toFixed(2):"\u2014") + " Pa \u00b7 " + d.coverage + "% cov" + src;
              }
            }
          }
        },
        scales:{
          x:{ ticks:{ color:ink3, maxTicksLimit:14, font:{family:"JetBrains Mono",size:9},
               callback:function(v){ return this.getLabelForValue(v).slice(5); } }, grid:{ color:grid, drawTicks:false } },
          y:{ ticks:{ color:ink3, font:{family:"JetBrains Mono",size:10} }, grid:{ color:grid, drawTicks:false }, beginAtZero:true,
              title:{ display:true, text:"HDF "+histMetric+" (Pa)", color:ink3, font:{family:"General Sans",size:11} } }
        }
      },
      plugins:[gapPlugin]
    });
  }

  function buildHistTable(){
    if (!H) return;
    var body = document.getElementById("histBody"); if (!body) return;
    var rows = "";
    H.days.forEach(function(d){
      var pill, dot, rowCls="";
      if (d.status==="local"){ pill='<span class="pill pill-source">uploaded</span>'; dot='status-source'; }
      else if (d.status==="source"){ pill='<span class="pill pill-source">FDSN</span>'; dot='status-source'; }
      else if (d.status==="prior"){ pill='<span class="pill pill-prior">prior</span>'; dot='status-prior'; }
      else { pill='<span class="pill pill-gap">gap</span>'; dot='status-gap'; rowCls="row-gap"; }
      var isData = isDataStatus(d.status) && d.mean!=null;
      rows += '<tr class="' + rowCls + '">' +
        '<td class="hour-label"><span class="status-dot '+dot+'"></span>' + d.date + '</td>' +
        '<td class="num">' + d.doy + '</td>' +
        '<td>' + pill + '</td>' +
        '<td class="num">' + (d.obs!=null?d.obs:"\u2014") + '</td>' +
        '<td class="num">' + (d.coverage!=null?d.coverage+"%":"\u2014") + '</td>' +
        '<td class="num">' + (isData&&d.mean!=null?d.mean.toFixed(3):"\u2014") + '</td>' +
        '<td class="num">' + (isData&&d.median!=null?d.median.toFixed(3):"\u2014") + '</td>' +
        '<td class="num">' + (isData&&d.peak!=null?d.peak.toFixed(3):"\u2014") + '</td>' +
        '</tr>';
    });
    body.innerHTML = rows;
    var f = document.getElementById("histFoot");
    if (f) f.innerHTML = '<span class="pill pill-source">source</span> reconstructed from FDSN for this build. <span class="pill pill-prior">prior</span> from earlier report/inventory only. <span class="pill pill-gap">gap</span> no source data (shown as gap band, never interpolated).';
  }

  // metric toggle
  var mtButtons = document.querySelectorAll(".metric-toggle button");
  mtButtons.forEach(function(btn){
    btn.addEventListener("click", function(){
      mtButtons.forEach(function(b){b.setAttribute("aria-pressed","false");});
      btn.setAttribute("aria-pressed","true");
      histMetric = btn.getAttribute("data-metric");
      buildHistChart();
    });
  });

  // peer-baseline metric toggle
  var pcButtons = document.querySelectorAll("#pcMean, #pcPeak");
  pcButtons.forEach(function(btn){
    btn.addEventListener("click", function(){
      pcButtons.forEach(function(b){b.setAttribute("aria-pressed","false");});
      btn.setAttribute("aria-pressed","true");
      peerMetric = btn.getAttribute("data-pmetric");
      buildPeerChart();
      buildExceedanceTable();
    });
  });

  // ---------- events vs channel aggregate arithmetic mean ----------
  var EV = window.__TREMORLENS_EVENTS__ || null;
  var evChan = "hdf";
  var evCharts = [];
  var EV_TOP_COLOR = "#dc2626", EV_BOT_COLOR = "#ca8a04";
  var PUBLIC_TITLE = "Unit 2709 Infrasound & Seismic Pressure Data (Ongoing)";
  var MONTHS = ["January","February","March","April","May","June",
                "July","August","September","October","November","December"];
  function humanDate(iso){
    var m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(iso||""); if(!m) return null;
    return MONTHS[parseInt(m[2],10)-1]+" "+parseInt(m[3],10)+", "+m[1];
  }
  // Verified documented coverage → "first – last (latest archived data)" (derived, not assumed;
  // never fabricates "Present" — the daily refresh extends last_documented_date forward).
  function dataRangeLabel(){
    var cov=EV&&EV.coverage?EV.coverage:null;
    var first=cov?humanDate(cov.first_documented_date):null;
    var last=cov?humanDate(cov.last_documented_date):null;
    if(first&&last) return first+" – "+last+" (latest archived data)";
    return first ? first+" (latest archived data)" : "April 12 – May 27, 2026 (latest archived data)";
  }
  function applyDateRange(){
    var label=dataRangeLabel();
    ["titleDateRange","footDateRange"].forEach(function(id){
      var el=document.getElementById(id); if(el) el.textContent=label;
    });
  }
  function destroyEvCharts(){ evCharts.forEach(function(c){try{c.destroy();}catch(e){}}); evCharts=[]; }
  function evUnit(chan){ return chan==="ehz" ? "µm/s" : "Pa"; }
  function evDec(chan){ return chan==="ehz" ? 2 : 4; }
  function evSrcLabel(sources){
    if(!sources||!sources.length) return "—";
    return sources.map(function(s){
      if(s==="uploaded_miniseed") return "uploaded";
      if(s==="fdsn_dataselect") return "FDSN";
      return s;
    }).join(" + ");
  }
  function timePart(et){ var p=(et||"").split(" "); return p.length>1?p[1]:et; }
  function pctStr(p){ return (p>=0?"+":"") + p.toFixed(1) + "%"; }

  function evHeadline(){
    var host=document.getElementById("evHeadline"); if(!host||!EV) return;
    var cov=EV.coverage;
    function box(label,val,sub){
      return '<div class="ev-box"><div class="ev-box-label">'+label+'</div>'+
             '<div class="ev-box-val">'+val+'</div>'+
             '<div class="ev-box-sub">'+sub+'</div></div>';
    }
    function group(chan){
      var b=EV[chan], h=b.headline, a=b.averages;
      var unit=evUnit(chan), dec=evDec(chan);
      var chLabel=chan==="ehz"?"EHZ — ground velocity (µm/s)":"HDF — pressure / infrasound (Pa)";
      var tag=chan==="hdf"?'<span class="kpi-tag kpi-tag-primary">Primary</span>':'<span class="kpi-tag">Secondary</span>';
      var N=chan==="ehz"?EV.peer_means.ehz_n:EV.peer_means.hdf_n;
      var boxes=
        box("Channel aggregate baseline", b.peer_mean.toFixed(dec)+' <span class="ev-u">'+unit+'</span>',
            "External peer arithmetic mean · N="+N)+
        box("Highest % above", h.highest_pct_above==null?"—":pctStr(h.highest_pct_above),
            "Top event vs aggregate mean")+
        box("Overall daily average", a.overall_pct_vs_peer==null?"—":pctStr(a.overall_pct_vs_peer),
            "Mean of daily means vs aggregate")+
        box("Longest top run", h.longest_top_min+' <span class="ev-u">min</span>',
            "Contiguous minutes above mean")+
        box("No-spike days", String(a.no_spike_count),
            "Documented days with 0 min above mean");
      return '<div class="kpi-group kpi-'+chan+'">'+
               '<h3 class="kpi-group-title">'+chLabel+' '+tag+'</h3>'+
               '<div class="kpi-boxes">'+boxes+'</div>'+
             '</div>';
    }
    host.innerHTML=group("hdf")+group("ehz");
    var note=document.getElementById("evCovNote");
    if(note) note.innerHTML="Coverage: "+cov.documented_days+" documented days, "+cov.gap_days+
      " gap days (HDF "+cov.hdf_days_with_minutes+" / EHZ "+cov.ehz_days_with_minutes+
      " days with minute data). HDF and EHZ are never cross-compared.";
  }

  function evMethodNote(){
    var host=document.getElementById("evMethod"); if(!host||!EV) return;
    host.innerHTML =
      '<strong>Methodology.</strong> '+EV.definition+' Metric: '+EV.metric+
      '. Channel aggregate arithmetic means: HDF <span class="mono">'+EV.peer_means.hdf_pa.toFixed(4)+
      ' Pa</span> (N='+EV.peer_means.hdf_n+'), EHZ <span class="mono">'+EV.peer_means.ehz_umps.toFixed(2)+
      ' µm/s</span> (N='+EV.peer_means.ehz_n+'), each the arithmetic mean of the matched-window daily means '+
      'across the external Raspberry Shake peer set (band 0.1&ndash;8 Hz, response-corrected). '+
      'The viewer-facing metric is the <em>percent difference</em> = ((value &minus; aggregate mean) / aggregate mean) &times; 100; '+
      'values below the aggregate mean are shown as &ldquo;X% below aggregate mean&rdquo;. '+
      'Runs are maximal and non-overlapping and never span a data gap; no interpolation. Times are '+EV.tz+' (ET).';
  }

  function evRankChart(canvasId, events, color, chan, kind){
    var el=document.getElementById(canvasId); if(!el) return;
    var dec=evDec(chan), unit=evUnit(chan);
    var labels=events.map(function(e){return "#"+e.rank;});
    var data=events.map(function(e){return e.percent_diff;});
    var meta=events;
    var opts={
      responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{display:false},
        tooltip:{ backgroundColor:css("--surface"), titleColor:css("--ink"), bodyColor:css("--ink-2"),
          borderColor:css("--border-strong"), borderWidth:1, padding:10, displayColors:false,
          callbacks:{
            title:function(items){ var e=meta[items[0].dataIndex]; return "#"+e.rank+" · "+e.date; },
            label:function(ctx){ var e=meta[ctx.dataIndex];
              return [ (e.percent_diff>=0?"+":"")+e.percent_diff.toFixed(1)+"% vs mean",
                       "start "+timePart(e.start_et)+" · "+e.duration_min+" min",
                       (kind==="top"?"peak ":"min ")+e.extreme.toFixed(dec)+" "+unit ]; }
          } } },
      scales:{ x:{ ticks:{color:css("--ink-3"), font:{family:"JetBrains Mono",size:9}, maxTicksLimit:20},
                   grid:{color:css("--grid-line"),drawTicks:false} },
               y:{ ticks:{color:css("--ink-3"), font:{family:"JetBrains Mono",size:10},
                     callback:function(v){return (v>0?"+":"")+v+"%";} },
                   grid:{color:css("--grid-line"),drawTicks:false} } }
    };
    var c=new Chart(el.getContext("2d"), {
      type:"bar",
      data:{ labels:labels, datasets:[{ data:data, backgroundColor:color+"cc", borderColor:color, borderWidth:1 }] },
      options:opts
    });
    evCharts.push(c);
  }

  function evTableRows(bodyId, events, chan, kind){
    var body=document.getElementById(bodyId); if(!body) return;
    var dec=evDec(chan);
    if(!events.length){ body.innerHTML='<tr><td colspan="11" class="muted">No events for this channel.</td></tr>'; return; }
    body.innerHTML=events.map(function(e){
      var start=timePart(e.start_et);
      var end=(e.end_date&&e.end_date!==e.date)?(e.end_date.slice(5)+" "+timePart(e.end_et)):timePart(e.end_et);
      var pctCell = kind==="top"
        ? '<span class="ev-pct ev-pct-up">'+pctStr(e.percent_diff)+' above</span>'
        : '<span class="ev-pct ev-pct-down">'+Math.abs(e.percent_diff).toFixed(1)+'% below</span>';
      return "<tr>"+
        '<td class="num">'+e.rank+"</td>"+
        "<td>"+e.date+"</td>"+
        "<td>"+start+"</td>"+
        "<td>"+end+"</td>"+
        '<td class="num">'+e.duration_min+"</td>"+
        '<td class="num">'+e.extreme.toFixed(dec)+"</td>"+
        '<td class="num">'+e.event_mean.toFixed(dec)+"</td>"+
        '<td class="num">'+pctCell+"</td>"+
        '<td class="num">'+EV[chan].peer_mean.toFixed(dec)+"</td>"+
        "<td>"+evSrcLabel(e.sources)+"</td>"+
        "<td>contiguous ("+e.duration_min+" min)</td>"+
      "</tr>";
    }).join("");
  }

  function buildEvents(){
    if(!EV){
      var host=document.getElementById("evHeadline");
      if(host) host.innerHTML='<div class="ev-box"><div class="ev-box-label">Event data unavailable</div><div class="ev-box-val">—</div><div class="ev-box-sub">events_embed.js not loaded</div></div>';
      return;
    }
    destroyEvCharts();
    var b=EV[evChan], unit=evUnit(evChan), chLabel=evChan==="ehz"?"EHZ velocity":"HDF pressure";
    var chShort=evChan==="ehz"?"EHZ":"HDF";
    var topPrefix=evChan==="ehz"?"C.":"A.", avgPrefix=evChan==="ehz"?"D.":"B.";
    document.getElementById("topTitle").textContent=topPrefix+" "+chShort+" Top 20 ("+chLabel+") — longest/strongest runs above aggregate mean";
    document.getElementById("avgTitle").textContent=avgPrefix+" "+chShort+" Average vs Aggregate Baseline ("+chLabel+")";
    document.getElementById("topExtHdr").textContent="Event peak ("+unit+")";
    document.getElementById("avgMeanHdr").textContent="Daily mean ("+unit+")";
    evHeadline(); evMethodNote();
    evRankChart("chartEvTop", b.top, EV_TOP_COLOR, evChan, "top");
    evTableRows("bodyEvTop", b.top, evChan, "top");
    buildAvgPanel(evChan);
    var foot=document.getElementById("evFoot");
    if(foot) foot.innerHTML="Showing Top "+b.top.length+" of "+
      b.counts.runs_above_total+" above-mean runs across "+
      b.counts.minutes_total.toLocaleString()+" documented "+chLabel+" minutes ("+
      b.counts.minutes_above.toLocaleString()+" above the aggregate mean). Average panel covers "+
      b.averages.day_count+" local documented days.";
  }

  function buildAvgPanel(chan){
    if(!EV) return;
    var a=EV[chan].averages, unit=evUnit(chan), dec=evDec(chan), peer=a.peer_mean;
    // summary
    var sm=document.getElementById("avgSummary");
    if(sm) sm.innerHTML=
      '<div class="ev-box"><div class="ev-box-label">Aggregate baseline</div><div class="ev-box-val">'+
        peer.toFixed(dec)+' <span class="ev-u">'+unit+'</span></div><div class="ev-box-sub">External peer arithmetic mean</div></div>'+
      '<div class="ev-box"><div class="ev-box-label">Overall daily average</div><div class="ev-box-val">'+
        (a.overall_daily_mean==null?"—":a.overall_daily_mean.toFixed(dec)+' <span class="ev-u">'+unit+'</span>')+
        '</div><div class="ev-box-sub">'+(a.overall_pct_vs_peer==null?"—":pctStr(a.overall_pct_vs_peer)+" vs aggregate mean")+'</div></div>'+
      '<div class="ev-box"><div class="ev-box-label">Documented local days</div><div class="ev-box-val">'+
        a.day_count+'</div><div class="ev-box-sub">America/Detroit calendar days with data</div></div>'+
      '<div class="ev-box"><div class="ev-box-label">No-spike days</div><div class="ev-box-val">'+
        a.no_spike_count+'</div><div class="ev-box-sub">Zero minutes above aggregate mean</div></div>';
    // daily % vs peer chart
    evAvgChart("chartEvAvg", a.days, chan);
    // no-spike note
    var ns=document.getElementById("avgNoSpike");
    if(ns){
      var defn='A <strong>no-spike day</strong> is defined objectively as a documented local day with <strong>zero</strong> valid one-minute samples strictly above this channel&rsquo;s peer aggregate arithmetic mean ('+peer.toFixed(dec)+' '+unit+'). ';
      ns.innerHTML=defn+(a.no_spike_count
        ? 'No-spike days ('+a.no_spike_count+'): <span class="mono">'+a.no_spike_dates.join(", ")+'</span>.'
        : 'No no-spike days were observed on this channel across the documented record (every documented local day had at least one minute above the aggregate mean).');
    }
    // daily table
    var body=document.getElementById("bodyEvAvg");
    if(body) body.innerHTML=a.days.map(function(d){
      var badge=d.no_spike
        ? '<span class="badge badge-nospike">No-spike</span>'
        : '<span class="badge badge-spike">Spike ('+d.samples_above_mean+')</span>';
      var st=d.partial?'<span class="tag-partial">partial</span>':'<span class="tag-full">full</span>';
      return "<tr>"+
        "<td>"+d.date+"</td>"+
        "<td>"+st+"</td>"+
        '<td class="num">'+d.minutes+" ("+d.coverage_pct+"%)</td>"+
        '<td class="num">'+d.daily_mean.toFixed(dec)+"</td>"+
        '<td class="num">'+avgPctCell(d.pct_vs_peer)+"</td>"+
        '<td class="num">'+d.samples_above_mean+"</td>"+
        "<td>"+badge+"</td>"+
        "<td>"+evSrcLabel(d.sources)+"</td>"+
      "</tr>";
    }).join("");
    // segment table
    var seg=document.getElementById("bodyEvSeg");
    if(seg) seg.innerHTML=a.days.map(function(d){
      var cells=d.segments.map(function(s){
        if(s.mean==null) return '<td class="num"><span class="muted">gap</span></td>';
        return '<td class="num">'+s.mean.toFixed(dec)+" "+unit+"<br>"+avgPctCell(s.pct_vs_peer)+
               '<br><span class="muted">'+s.minutes+" min"+(s.status==="partial"?" · partial":"")+"</span></td>";
      }).join("");
      return "<tr><td>"+d.date+"</td>"+cells+"</tr>";
    }).join("");
  }

  function avgPctCell(p){
    if(p==null) return '<span class="muted">—</span>';
    var cls=p>=0?"ev-pct-up":"ev-pct-down";
    return '<span class="ev-pct '+cls+'">'+pctStr(p)+'</span>';
  }

  function evAvgChart(canvasId, days, chan){
    var el=document.getElementById(canvasId); if(!el) return;
    var dec=evDec(chan), unit=evUnit(chan);
    var labels=days.map(function(d){return d.date.slice(5);});
    var data=days.map(function(d){return d.pct_vs_peer;});
    var colors=days.map(function(d){return d.pct_vs_peer>=0?EV_TOP_COLOR:"#0f766e";});
    var c=new Chart(el.getContext("2d"), {
      type:"bar",
      data:{ labels:labels, datasets:[{ data:data,
        backgroundColor:colors.map(function(x){return x+"cc";}), borderColor:colors, borderWidth:1 }] },
      options:{ responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{display:false},
          tooltip:{ backgroundColor:css("--surface"), titleColor:css("--ink"), bodyColor:css("--ink-2"),
            borderColor:css("--border-strong"), borderWidth:1, padding:10, displayColors:false,
            callbacks:{ title:function(items){return days[items[0].dataIndex].date;},
              label:function(ctx){ var d=days[ctx.dataIndex];
                return [ (d.pct_vs_peer>=0?"+":"")+d.pct_vs_peer.toFixed(1)+"% vs mean",
                         "daily mean "+d.daily_mean.toFixed(dec)+" "+unit,
                         d.minutes+" min ("+d.coverage_pct+"%)"+(d.no_spike?" · no-spike":"") ]; } } } },
        scales:{ x:{ ticks:{color:css("--ink-3"), font:{family:"JetBrains Mono",size:9}, maxTicksLimit:24},
                     grid:{color:css("--grid-line"),drawTicks:false} },
                 y:{ ticks:{color:css("--ink-3"), font:{family:"JetBrains Mono",size:10},
                       callback:function(v){return (v>0?"+":"")+v+"%";} },
                     grid:{color:css("--grid-line"),drawTicks:false} } } }
    });
    evCharts.push(c);
  }

  document.querySelectorAll("[data-evchan]").forEach(function(btn){
    btn.addEventListener("click", function(){
      document.querySelectorAll("[data-evchan]").forEach(function(b){b.setAttribute("aria-pressed","false");});
      btn.setAttribute("aria-pressed","true");
      evChan=btn.getAttribute("data-evchan");
      buildEvents();
      setTimeout(function(){ evCharts.forEach(function(c){try{c.resize();}catch(e){}}); },30);
    });
  });

  function evCsvRows(events, chan, kind){
    var dec=evDec(chan);
    return events.map(function(e){
      return [e.rank, chan.toUpperCase(), kind, e.date, e.start_et, e.end_et, e.duration_min,
        e.extreme.toFixed(dec), e.event_mean.toFixed(dec), e.percent_diff.toFixed(2),
        EV[chan].peer_mean.toFixed(dec), evUnit(chan), evSrcLabel(e.sources), "contiguous"].join(",");
    });
  }
  var EV_CSV_HEADER="rank,channel,list,date,start_et,end_et,duration_min,event_extreme,event_mean,percent_vs_aggregate_mean,aggregate_mean,units,source,completeness";
  var AVG_CSV_HEADER="channel,date_et,status,minutes,coverage_pct,daily_mean,percent_vs_aggregate_mean,samples_above_mean,no_spike,aggregate_mean,units,source,"+
    "seg_00_06_mean,seg_00_06_pct,seg_00_06_min,seg_06_12_mean,seg_06_12_pct,seg_06_12_min,"+
    "seg_12_18_mean,seg_12_18_pct,seg_12_18_min,seg_18_24_mean,seg_18_24_pct,seg_18_24_min";
  function avgCsvRows(chan){
    var a=EV[chan].averages, dec=evDec(chan), unit=evUnit(chan);
    function sv(s,f){ return s.mean==null?"":(f==="mean"?s.mean.toFixed(dec):f==="pct"?s.pct_vs_peer.toFixed(2):s.minutes); }
    return a.days.map(function(d){
      var segvals=[];
      d.segments.forEach(function(s){ segvals.push(sv(s,"mean"),sv(s,"pct"),s.minutes); });
      return [chan.toUpperCase(), d.date, d.partial?"partial":"full", d.minutes, d.coverage_pct,
        d.daily_mean.toFixed(dec), d.pct_vs_peer.toFixed(2), d.samples_above_mean, d.no_spike?"yes":"no",
        a.peer_mean.toFixed(dec), unit, evSrcLabel(d.sources)].concat(segvals).join(",");
    });
  }
  var bEvTop=document.getElementById("btnEvTopCsv");
  if(bEvTop) bEvTop.addEventListener("click",function(){ if(!EV)return;
    download("R6E8A_"+evChan.toUpperCase()+"_top20_events.csv",
      EV_CSV_HEADER+"\n"+evCsvRows(EV[evChan].top,evChan,"top").join("\n"),"text/csv"); });
  var bEvAvg=document.getElementById("btnEvAvgCsv");
  if(bEvAvg) bEvAvg.addEventListener("click",function(){ if(!EV)return;
    download("R6E8A_"+evChan.toUpperCase()+"_daily_segment_averages.csv",
      AVG_CSV_HEADER+"\n"+avgCsvRows(evChan).join("\n"),"text/csv"); });
  var bEvAll=document.getElementById("btnEvAllCsv");
  if(bEvAll) bEvAll.addEventListener("click",function(){ if(!EV)return;
    var topRows=[].concat(evCsvRows(EV.hdf.top,"hdf","top"), evCsvRows(EV.ehz.top,"ehz","top"));
    var avgRows=[].concat(avgCsvRows("hdf"), avgCsvRows("ehz"));
    var content="# TOP 20 EVENTS (per channel)\n"+EV_CSV_HEADER+"\n"+topRows.join("\n")+
      "\n\n# DAILY + SEGMENT AVERAGES (per channel)\n"+AVG_CSV_HEADER+"\n"+avgRows.join("\n");
    download("R6E8A_events_and_averages.csv", content,"text/csv"); });

  // ---------- fixed daily 24-hour view labels ----------
  function buildDailyView(){
    var DLY=window.__TREMORLENS_DAILY__||null;
    var host=document.getElementById("dailyWindow"); if(!host) return;
    if(!DLY){ host.innerHTML='<div class="muted">Daily window metadata unavailable.</div>'; return; }
    var w=DLY.report_window_et;
    host.innerHTML=
      '<div class="daily-kv"><span class="dk">Report window (fixed)</span><span class="dv mono">'+
        w.start+' &rarr; '+w.end+'</span></div>'+
      '<div class="daily-kv"><span class="dk">Snapshot window</span><span class="dv mono">final '+
        DLY.window_minutes+' min to '+DLY.cutoff_et+'</span></div>'+
      '<div class="daily-kv"><span class="dk">Latest archived data-through</span><span class="dv mono">HDF '+
        (DLY.data_through_et.HDF||'—')+' ET · EHZ '+(DLY.data_through_et.EHZ||'—')+' ET</span></div>'+
      '<div class="daily-kv"><span class="dk">Generated (UTC)</span><span class="dv mono">'+
        DLY.generated_utc+'</span></div>';
  }

  // ---------- print-ready daily report ----------
  function dayRecord(chan, date){
    if(!EV) return null;
    var days=EV[chan].averages.days;
    for(var i=0;i<days.length;i++){ if(days[i].date===date) return days[i]; }
    return days.length?days[days.length-1]:null;
  }
  function reportDateFromDaily(DLY){
    if(DLY&&DLY.cutoff_et){ var m=DLY.cutoff_et.match(/\d{4}-\d{2}-\d{2}/); if(m) return m[0]; }
    if(EV&&EV.hdf.averages.days.length){ var d=EV.hdf.averages.days; return d[d.length-1].date; }
    return null;
  }
  function reportTopEvents(chan, date){
    if(!EV) return [];
    return EV[chan].top.filter(function(e){ return e.date===date || e.end_date===date; }).slice(0,5);
  }
  function segTableHtml(chan, rec){
    if(!rec) return "";
    var dec=evDec(chan), unit=evUnit(chan);
    var cells=rec.segments.map(function(s){
      if(s.mean==null) return "<td>gap</td>";
      return "<td>"+s.mean.toFixed(dec)+" "+unit+"<br>"+pctStr(s.pct_vs_peer)+"<br>"+s.minutes+" min"+(s.status==="partial"?" (partial)":"")+"</td>";
    }).join("");
    return "<table class='rep-table'><thead><tr><th>Segment (ET)</th><th>00:00–06:00</th><th>06:00–12:00</th>"+
      "<th>12:00–18:00</th><th>18:00–24:00</th></tr></thead><tbody><tr><td>"+chan.toUpperCase()+"</td>"+cells+"</tr></tbody></table>";
  }
  function chanReportRow(chan, rec){
    if(!rec) return "";
    var dec=evDec(chan), unit=evUnit(chan);
    return "<tr><td>"+chan.toUpperCase()+" ("+(chan==="ehz"?"velocity":"pressure")+")</td>"+
      "<td>"+EV[chan].averages.peer_mean.toFixed(dec)+" "+unit+"</td>"+
      "<td>"+rec.daily_mean.toFixed(dec)+" "+unit+"</td>"+
      "<td>"+pctStr(rec.pct_vs_peer)+"</td>"+
      "<td>"+rec.minutes+" ("+rec.coverage_pct+"%)"+(rec.partial?" partial":"")+"</td>"+
      "<td>"+(rec.no_spike?"No-spike":"Spike ("+rec.samples_above_mean+" min > mean)")+"</td>"+
      "<td>"+evSrcLabel(rec.sources)+"</td></tr>";
  }
  function topEventsHtml(chan, date){
    var evs=reportTopEvents(chan, date), dec=evDec(chan), unit=evUnit(chan);
    if(!evs.length) return "<p class='muted'>No Top-20 "+chan.toUpperCase()+" events fall within this archived period.</p>";
    var rows=evs.map(function(e){
      return "<tr><td>"+e.rank+"</td><td>"+e.start_et+"</td><td>"+e.end_et+"</td><td>"+e.duration_min+
        "</td><td>"+e.extreme.toFixed(dec)+" "+unit+"</td><td>"+pctStr(e.percent_diff)+"</td></tr>";
    }).join("");
    return "<table class='rep-table'><thead><tr><th>#</th><th>Start ET</th><th>End ET</th><th>Dur</th>"+
      "<th>Peak</th><th>% vs mean</th></tr></thead><tbody>"+rows+"</tbody></table>";
  }
  function buildDailyReport(){
    var host=document.getElementById("dailyReport"); if(!host) return null;
    var DLY=window.__TREMORLENS_DAILY__||null;
    var date=reportDateFromDaily(DLY);
    var hRec=dayRecord("hdf",date), eRec=dayRecord("ehz",date);
    var disc=(document.querySelector(".disclaimer-box")||{}).textContent||"";
    var attr="Data powered by Raspberry Shake, S.A., a citizen-science project. Please visit raspberryshake.org and join the Citizen Science Community today! DOI: https://doi.org/10.7914/SN/AM";
    var cutoff=DLY?DLY.cutoff_et:"—", gen=DLY?DLY.generated_utc:"—";
    var winStart=DLY&&DLY.report_window_et?DLY.report_window_et.start:"—";
    var winEnd=DLY&&DLY.report_window_et?DLY.report_window_et.end:"—";
    var through=DLY?("HDF "+(DLY.data_through_et.HDF||"—")+" ET · EHZ "+(DLY.data_through_et.EHZ||"—")+" ET"):"—";
    host.innerHTML=
      "<div class='rep-head'>"+
        "<h1>"+PUBLIC_TITLE+"</h1>"+
        "<div class='rep-sub'>Fixed daily 24-hour archived report · Station AM.R6E8A.00 · Detroit · Data range "+dataRangeLabel()+"</div>"+
        "<div class='rep-meta'>Report date (ET): <strong>"+(date||"—")+"</strong> · Fixed cutoff: "+cutoff+
          " · Snapshot window: "+winStart+" → "+winEnd+"<br>Latest archived data-through: "+through+
          " · Generated (UTC): "+gen+" · Rendered: "+new Date().toISOString()+"</div>"+
      "</div>"+
      "<h2>Channels at a glance</h2>"+
        "<div class='rep-glance'>"+
        "<p><strong>Primary · HDF</strong> — measures very-low-frequency air-pressure changes, in pascals (Pa). Much of the infrasound range (below 20 Hz) is below ordinary human audibility; a calibrated pressure sensor is needed to quantify it.</p>"+
        "<p><strong>Secondary · EHZ</strong> — measures vertical up/down ground-motion velocity, in µm/s. Provided only as separate context. HDF and EHZ units are never mixed.</p>"+
        "</div>"+
      "<h2>Channel daily means vs external peer aggregate mean</h2>"+
      "<table class='rep-table'><thead><tr><th>Channel</th><th>Aggregate mean</th><th>Daily mean</th>"+
        "<th>% vs mean</th><th>Minutes (cov)</th><th>Spike status</th><th>Source</th></tr></thead><tbody>"+
        chanReportRow("hdf",hRec)+chanReportRow("ehz",eRec)+"</tbody></table>"+
      "<h2>Quarter-day segment averages (fixed local America/Detroit windows)</h2>"+
        segTableHtml("hdf",hRec)+segTableHtml("ehz",eRec)+
      "<h2>Top events within this archived period</h2>"+
        "<h3>HDF (pressure)</h3>"+topEventsHtml("hdf",date)+
        "<h3>EHZ (velocity)</h3>"+topEventsHtml("ehz",date)+
      "<h2>Original composite images (independently generated; not raw waveform)</h2>"+
        "<div class='rep-imgs'>"+
          "<figure><img src='./assets/snapshot_hdf.png' alt='HDF composite'><figcaption>HDF — waveform, spectrogram, amplitude spectrum (final 60 min to cutoff)</figcaption></figure>"+
          "<figure><img src='./assets/snapshot_ehz.png' alt='EHZ composite'><figcaption>EHZ — waveform, spectrogram, amplitude spectrum (final 60 min to cutoff)</figcaption></figure>"+
        "</div>"+
      "<h2>What each channel measures</h2>"+
        "<div class='rep-chan'>"+
        "<p><strong>HDF</strong> is the official FDSN channel code for the Raspberry Boom / Shake pressure sensor (informally &ldquo;HDZ&rdquo;; HDF used throughout). It records band-limited, response-corrected air-pressure RMS in pascals (Pa).</p>"+
        "<p><strong>EHZ</strong> is the vertical geophone channel — how fast the ground moves up and down — displayed as response-corrected ground velocity in micrometers per second (µm/s).</p>"+
        "</div>"+
      "<h2>Baseline Source Credibility</h2>"+
        "<div class='rep-cred'>"+
        "<h3>Baseline data</h3>"+
        "<p>The quantitative comparison baseline is derived <strong>only</strong> from public Raspberry Shake peer channels — "+
        "HDF arithmetic mean <strong>0.120031 Pa</strong> across <strong>27</strong> valid matched peer stations; "+
        "EHZ arithmetic mean <strong>1.37637 µm/s</strong> across <strong>22</strong> valid matched peer stations. "+
        "Each peer value uses the same channel and units, is response-corrected, and is computed over the same frequency band and day window as R6E8A. "+
        "The peer set is a deterministic, reproducible sample. HDF and EHZ baselines are never cross-compared.</p>"+
        "<h3>Interpretive sources</h3>"+
        "<p>These sources interpret channel and perception context only and do not supply the peer baseline values above:</p>"+
        "<ul>"+
          "<li><a href='https://raspberryshake.org/raspberry-shake-basic-concepts/'>Raspberry Shake — Basic Concepts</a></li>"+
          "<li><a href='https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0229088'>PLOS ONE — perception of 8 Hz infrasound</a></li>"+
          "<li><a href='https://pmc.ncbi.nlm.nih.gov/articles/PMC7199630/'>NIH / PMC — review of infrasound effects</a></li>"+
        "</ul>"+
        "<p>These sources provide context only and do not supply any baseline value used here. The band-limited Pa RMS metric shown here is not a dB SPL exposure measurement.</p>"+
        "</div>"+
      "<h2>How to interpret each channel</h2>"+
        "<div class='rep-chan'>"+
        "<p><strong>HDF</strong> — audibility and perception thresholds at very low frequencies are high and vary substantially between people. When sufficiently intense, research indicates infrasound can be perceived through the auditory system, but the mechanism and individual perception vary. The band-limited Pa RMS values shown here are <strong>not</strong> dB SPL exposure measurements and cannot by themselves be used to establish harm.</p>"+
        "<p><strong>EHZ</strong> — secondary corroborating context only; compared solely to its own peer baseline and never cross-compared with HDF pressure values.</p>"+
        "</div>"+
      "<h2>Methodology</h2>"+
        "<p>"+(EV?EV.definition+" Metric: "+EV.metric+". ":"")+
        "Channel-specific external peer aggregate arithmetic means: HDF "+(EV?EV.peer_means.hdf_pa.toFixed(4):"—")+
        " Pa (N="+(EV?EV.peer_means.hdf_n:"—")+"), EHZ "+(EV?EV.peer_means.ehz_umps.toFixed(2):"—")+
        " µm/s (N="+(EV?EV.peer_means.ehz_n:"—")+"). HDF and EHZ are never cross-compared. Percent difference = "+
        "((value − aggregate mean) / aggregate mean) × 100. Segments use local timestamps (DST-safe); "+
        "actual available minute counts are disclosed. No interpolation.</p>"+
        "<p class='rep-note'>This is a <strong>derived archived-data report</strong> (metrics, tables, and static report images only). "+
        "It is not a raw-waveform distribution service and contains no MiniSEED. Occupancy or presence observations are separate, "+
        "user-supplied annotations and are not part of the instrument data unless later provided.</p>"+
      "<h2>Attribution</h2><p class='rep-attr'>"+attr+"</p>"+
      "<h2>Disclaimer</h2><p class='rep-disc'>"+disc+"</p>";
    return date;
  }
  var btnDailyReport=document.getElementById("btnDailyReport");
  if(btnDailyReport) btnDailyReport.addEventListener("click", function(){
    var date=buildDailyReport();
    var prevTitle=document.title;
    if(date) document.title="R6E8A_daily_report_"+date;
    document.body.classList.add("printing-report");
    var restore=function(){ document.body.classList.remove("printing-report"); document.title=prevTitle;
      window.removeEventListener("afterprint",restore); };
    window.addEventListener("afterprint",restore);
    window.print();
    setTimeout(restore, 1500);
  });

  // ---------- rebuild all ----------
  function rebuildAllCharts(){
    destroyCharts();
    buildLine("chartHdf", pre, "Pa", 3);
    buildLine("chartVel", velUm, "µm/s", 2);
    buildZoom();
    if (H) buildHistChart();
  }
  rebuildAllCharts();
  applyDateRange();
  buildHistorical();
  buildEvents();
  buildDailyView();

  // ---------- tabs ----------
  var tabs = document.querySelectorAll(".tab");
  var panels = { "panel-live":document.getElementById("panel-live"),
                 "panel-hist":document.getElementById("panel-hist"),
                 "panel-ehz":document.getElementById("panel-ehz") };
  tabs.forEach(function(tab){
    tab.addEventListener("click", function(){
      tabs.forEach(function(t){ t.setAttribute("aria-selected","false"); });
      tab.setAttribute("aria-selected","true");
      Object.keys(panels).forEach(function(k){
        var p = panels[k]; if(!p) return;
        var on = (k === tab.getAttribute("data-panel"));
        p.classList.toggle("active", on);
        if (on) p.removeAttribute("hidden"); else p.setAttribute("hidden","");
      });
      // charts sized to hidden panels need a resize when shown
      setTimeout(function(){ charts.forEach(function(c){try{c.resize();}catch(e){}}); if(histChart){try{histChart.resize();}catch(e){}} if(peerChart){try{peerChart.resize();}catch(e){}} evCharts.forEach(function(c){try{c.resize();}catch(e){}}); }, 30);
    });
  });

  // ---------- EHZ collapse ----------
  var ehzToggle = document.getElementById("ehzToggle");
  var ehzCollapse = document.getElementById("ehzCollapse");
  if (ehzToggle) {
    ehzToggle.addEventListener("click", function(){
      var open = ehzCollapse.getAttribute("open-state") === "open";
      ehzCollapse.setAttribute("open-state", open ? "closed" : "open");
      ehzToggle.setAttribute("aria-expanded", open ? "false" : "true");
      if (!open) setTimeout(function(){ charts.forEach(function(c){try{c.resize();}catch(e){}}); }, 30);
    });
  }

  // ---------- exports ----------
  function download(filename, content, type){
    var blob = new Blob([content], { type: type });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function(){ URL.revokeObjectURL(url); }, 500);
  }

  document.getElementById("btnCsv").addEventListener("click", function(){
    var header = "time_utc,time_detroit,pressure_rms_pa,velocity_rms_m_s,pressure_event_score,velocity_event_score";
    function g(x){ return x==null?"":x; }
    var lines = series.map(function(m){ return [m.u, m.t, g(m.p), g(m.v), g(m.pz), g(m.vz)].join(","); });
    download("R6E8A_HDF_live_minutes.csv", header + "\n" + lines.join("\n"), "text/csv");
  });

  document.getElementById("btnJson").addEventListener("click", function(){
    var out = {
      generated_utc: D.generated_utc, summary: s, hourly: D.hourly, method: D.method,
      minute_series: series.map(function(m){
        return { time_utc:m.u, time_detroit:m.t, pressure_rms_pa:m.p, velocity_rms_m_s:m.v,
                 pressure_event_score:m.pz, velocity_event_score:m.vz };
      })
    };
    download("R6E8A_HDF_live_analysis.json", JSON.stringify(out, null, 2), "application/json");
  });

  document.getElementById("btnPrint").addEventListener("click", function(){ window.print(); });

  // historical exports
  var bHistCsv = document.getElementById("btnHistCsv");
  if (bHistCsv) bHistCsv.addEventListener("click", function(){
    if (!H) { return; }
    var header = "date,day_of_year,status,observed_minutes,coverage_pct,hdf_mean_pa,hdf_median_pa,hdf_peak_pa,hdf_p95_pa";
    function g(x){ return x==null?"":x; }
    var lines = H.days.map(function(d){
      return [d.date, d.doy, d.status, g(d.obs), g(d.coverage), g(d.mean), g(d.median), g(d.peak), g(d.p95)].join(",");
    });
    download("R6E8A_HDF_historical_daily.csv", header + "\n" + lines.join("\n"), "text/csv");
  });
  var bHistJson = document.getElementById("btnHistJson");
  if (bHistJson) bHistJson.addEventListener("click", function(){
    if (!H) { return; }
    download("R6E8A_HDF_historical_daily.json", JSON.stringify(H, null, 2), "application/json");
  });

  // peer-baseline chart/table exports
  function g(x){ return x==null?"":x; }
  var bPeerChartCsv = document.getElementById("btnPeerChartCsv");
  if (bPeerChartCsv) bPeerChartCsv.addEventListener("click", function(){
    if (!H) return;
    var q=peerQ(peerMetric);
    var header="date,day_of_year,status,source,coverage_pct,metric,value_pa,peer_median_pa,peer_p75_pa,peer_p95_pa,peer_p99_pa,peer_percentile,band,ratio_vs_median,db_vs_median";
    var lines=H.days.map(function(d){
      var v=dayVal(d, peerMetric);
      var src = d.status==="local"?"uploaded":(d.status==="source"?"FDSN":(d.status==="gap"?"gap":d.status));
      var b=v==null?null:bandOfVal(peerMetric,v);
      var pctl=v==null?null:peerPctl(peerMetric,v);
      var ratio=(v!=null&&q&&q.median)?(v/q.median):null;
      var db=(v!=null&&q&&q.median)?(20*Math.log10(v/q.median)):null;
      return [d.date, d.doy, d.status, src, g(d.coverage), peerMetric, g(v==null?null:v.toFixed(5)),
        g(q?q.median:null), g(q?q.p75:null), g(q?q.p95:null), g(q?q.p99:null),
        g(pctl), g(b), g(ratio==null?null:ratio.toFixed(3)), g(db==null?null:db.toFixed(2))].join(",");
    });
    download("R6E8A_HDF_vs_peer_baseline_"+peerMetric+".csv", header+"\n"+lines.join("\n"), "text/csv");
  });
  var bPeerExceedCsv = document.getElementById("btnPeerExceedCsv");
  if (bPeerExceedCsv) bPeerExceedCsv.addEventListener("click", function(){
    if (!H) return;
    var q=peerQ(peerMetric);
    var header="rank,date,day_of_year,metric,value_pa,band,peer_percentile,ratio_vs_median,db_vs_median,source,coverage_pct";
    var rows=peerExceedRows(peerMetric);
    var lines=rows.map(function(r,i){
      return [i+1, r.d.date, r.d.doy, peerMetric, r.v.toFixed(5), g(r.band), g(r.pctl),
        g(r.ratio==null?null:r.ratio.toFixed(3)), g(r.db==null?null:r.db.toFixed(2)),
        r.src, g(r.d.coverage)].join(",");
    });
    var meta="# peer_metric="+peerMetric+" median="+(q?q.median:"")+" p75="+(q?q.p75:"")+" p95="+(q?q.p95:"")+" p99="+(q?q.p99:"")+" n="+(q?q.n:"");
    download("R6E8A_HDF_peer_exceedances_"+peerMetric+".csv", meta+"\n"+header+"\n"+lines.join("\n"), "text/csv");
  });

})();
