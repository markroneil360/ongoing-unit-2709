#!/usr/bin/env python3
"""Generate ORIGINAL composite daily snapshot PNGs for AM.R6E8A.00 (HDF + EHZ):
waveform + spectrogram (Inferno) + amplitude spectrum, for a technically useful
window ending at the fixed 7:00 AM ET report cutoff.

Independently generated from R6E8A data with matplotlib/scipy — inspired by, but
NOT copied from, DataView/Spectroid UI artwork. Response-corrected to physical units
(HDF Pa, EHZ um/s). Window length is labeled on the figure.

Writes:
  assets/snapshot_hdf.png
  assets/snapshot_ehz.png
  data/snapshot_meta.json  (window, generated/retrieved times, data-through)

Source preference: latest fully-documented uploaded day if raw present; otherwise the
most recent FDSN day. Raw MiniSEED is streamed/processed and never written to repo.
"""
import io, os, json, time, datetime, urllib.request
from zoneinfo import ZoneInfo
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from scipy.signal import spectrogram, get_window
from obspy import read, read_inventory, UTCDateTime

ROOT = "/home/user/workspace/tremorlens-r6e8a-restored"
WS = "/home/user/workspace"
INV = read_inventory(f"{WS}/R6E8A_stationxml.xml")
UP = f"{WS}/uploaded_attachments/aa8aa6fbb2e246dd8383886d5f55ea59"
ASSETS = f"{ROOT}/assets"
BASE = "https://data.raspberryshake.org/fdsnws"
TZ = ZoneInfo("America/Detroit")
PREFILT = (0.05, 0.1, 8, 9)
WINDOW_MIN = 60  # final 60 minutes up to the 7:00 ET cutoff

CFG = {
    "HDF": {"output": "DEF", "scale": 1.0, "unit": "Pa", "label": "HDF infrasound pressure"},
    "EHZ": {"output": "VEL", "scale": 1e6, "unit": "um/s", "label": "EHZ ground velocity"},
}


def http(url, timeout=180, tries=3):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "r6e8a-snap/1.0"})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception:
            time.sleep(3 * (k + 1))
    return None


def load_window(chan, day_utc_date, t0, t1):
    """Return a decimated, response-corrected obspy Trace for [t0,t1) or None."""
    doy = t0.utcdatetime.julday if False else None
    st = None
    # try uploaded file for that UTC date
    for d in (day_utc_date,):
        f = f"{UP}/AM.R6E8A.00.{chan}.D.2026.{d:03d}"
        if os.path.exists(f):
            st = read(f)
            src = ("uploaded_miniseed", os.path.basename(f))
            break
    if st is None:
        url = (f"{BASE}/dataselect/1/query?net=AM&sta=R6E8A&loc=00&cha={chan}"
               f"&start={t0.isoformat()}&end={t1.isoformat()}&format=miniseed&nodata=404")
        raw = http(url)
        if not raw:
            return None, None
        st = read(io.BytesIO(raw))
        src = ("fdsn_dataselect", url)
    st.trim(t0, t1)
    if len(st) == 0:
        return None, None
    st.merge(method=0)
    st = st.split()
    st.detrend("demean")
    for tr in st:
        factor = int(round(tr.stats.sampling_rate / 20.0))
        if factor >= 2:
            tr.decimate(factor, no_filter=False)
    st.remove_response(inventory=INV, output=CFG[chan]["output"],
                       pre_filt=PREFILT, water_level=60)
    st.merge(method=0)
    st = st.split()
    if len(st) == 0:
        return None, None
    return st[0], src


def draw(chan, tr, t0, t1, data_through_et):
    cfg = CFG[chan]
    y = tr.data.astype("float64") * cfg["scale"]
    sr = tr.stats.sampling_rate
    n = len(y)
    t_utc0 = tr.stats.starttime
    times = [ (t_utc0 + i / sr).datetime.replace(tzinfo=datetime.timezone.utc).astimezone(TZ)
              for i in range(n) ]

    fig, ax = plt.subplots(3, 1, figsize=(9, 8.2), constrained_layout=True)
    fig.patch.set_facecolor("white")

    # 1) waveform
    ax[0].plot(times, y, lw=0.5, color="#0f766e")
    ax[0].set_title(f"R6E8A {cfg['label']} — final {WINDOW_MIN} min to 07:00 ET cutoff",
                    fontsize=11, fontweight="bold")
    ax[0].set_ylabel(cfg["unit"])
    ax[0].grid(alpha=0.25)
    ax[0].xaxis.set_major_formatter(DateFormatter("%H:%M", tz=TZ))

    # 2) spectrogram (Inferno)
    win = get_window("hann", min(1024, n))
    nps = len(win)
    f, tt, Sxx = spectrogram(y, fs=sr, window=win, nperseg=nps,
                             noverlap=int(nps * 0.75), scaling="density", mode="magnitude")
    Sxx_db = 20 * np.log10(Sxx + 1e-12)
    extent = [0, (n / sr) / 60.0, f[0], f[-1]]
    im = ax[1].imshow(Sxx_db, origin="lower", aspect="auto", cmap="inferno",
                      extent=extent)
    ax[1].set_ylim(0, 8)
    ax[1].set_ylabel("Hz")
    ax[1].set_xlabel("minutes into window")
    ax[1].set_title("Spectrogram (0.1–8 Hz band emphasis)", fontsize=10)
    cb = fig.colorbar(im, ax=ax[1], pad=0.01)
    cb.set_label(f"dB re 1 {cfg['unit']}/√Hz", fontsize=8)

    # 3) amplitude spectrum
    Y = np.abs(np.fft.rfft(y - y.mean())) / n
    fr = np.fft.rfftfreq(n, d=1.0 / sr)
    ax[2].semilogy(fr, Y + 1e-12, lw=0.7, color="#b45309")
    ax[2].set_xlim(0, 8)
    ax[2].set_xlabel("Hz")
    ax[2].set_ylabel(f"amp ({cfg['unit']})")
    ax[2].set_title("Amplitude spectrum", fontsize=10)
    ax[2].grid(alpha=0.25)

    fig.suptitle(
        f"Original composite generated from R6E8A data · data through {data_through_et} ET",
        fontsize=8, y=1.005, color="#475569")
    out = f"{ASSETS}/snapshot_{chan.lower()}.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def main():
    os.makedirs(ASSETS, exist_ok=True)
    # choose reference cutoff: 07:00 ET on the most recent fully-documented uploaded day.
    # DOY108 = 2026-04-18 is 100%-coverage uploaded; use its 07:00 ET cutoff.
    cutoff_et = datetime.datetime(2026, 4, 18, 7, 0, tzinfo=TZ)
    t1 = UTCDateTime(cutoff_et.astimezone(datetime.timezone.utc))
    t0 = t1 - WINDOW_MIN * 60
    day_utc_date = int(t0.strftime("%j"))
    meta = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "window_minutes": WINDOW_MIN,
        "cutoff_et": cutoff_et.strftime("%Y-%m-%d %H:%M %Z"),
        "window_start_et": t0.datetime.replace(tzinfo=datetime.timezone.utc)
                              .astimezone(TZ).strftime("%Y-%m-%d %H:%M %Z"),
        "window_end_et": cutoff_et.strftime("%Y-%m-%d %H:%M %Z"),
        "note": ("Original composite (waveform + Inferno spectrogram + amplitude "
                 "spectrum) independently generated from R6E8A data; not copied from "
                 "any third-party UI. Window ends at the fixed 07:00 ET report cutoff."),
        "channels": {},
    }
    for chan in ("HDF", "EHZ"):
        tr, src = load_window(chan, day_utc_date, t0, t1)
        if tr is None:
            meta["channels"][chan] = {"ok": False, "note": "no data for window"}
            print(chan, "NO DATA")
            continue
        through = (tr.stats.endtime.datetime.replace(tzinfo=datetime.timezone.utc)
                   .astimezone(TZ).strftime("%Y-%m-%d %H:%M"))
        out = draw(chan, tr, t0, t1, through)
        meta["channels"][chan] = {"ok": True, "png": os.path.basename(out),
                                  "source": src[0], "data_through_et": through,
                                  "unit": CFG[chan]["unit"]}
        print(chan, "wrote", out, "through", through)
    with open(f"{ROOT}/data/snapshot_meta.json", "w") as f:
        json.dump(meta, f, indent=1)
    print("WROTE data/snapshot_meta.json")

    # file://-safe embed for the daily-view window labels + attribution
    daily = {
        "report_window_et": {"start": meta["window_start_et"],
                             "end": meta["window_end_et"]},
        "cutoff_et": meta["cutoff_et"],
        "window_minutes": meta["window_minutes"],
        "generated_utc": meta["generated_utc"],
        "data_through_et": {k: v.get("data_through_et") for k, v in meta["channels"].items()},
        "snapshots": meta["channels"],
        "small_print": ("This archived 24-hour report uses a fixed 7:00 AM ET cutoff and is "
                        "generated after the Raspberry Shake archive delay; it is not a "
                        "real-time feed. The official DataView panel below provides the "
                        "closest available live view."),
        "attribution": ("Data powered by Raspberry Shake, S.A., a citizen-science project. "
                        "Please visit raspberryshake.org and join the Citizen Science "
                        "Community today! DOI: https://doi.org/10.7914/SN/AM"),
    }
    with open(f"{ROOT}/data/daily_embed.js", "w") as f:
        f.write("// Auto-generated by tools/make_snapshot.py — do not edit by hand.\n")
        f.write("window.__TREMORLENS_DAILY__ = ")
        json.dump(daily, f, separators=(",", ":"))
        f.write(";\n")
    print("WROTE data/daily_embed.js")


if __name__ == "__main__":
    main()
