#!/usr/bin/env python3
"""Update the current Detroit-day highest HDF infrasound event for AM.R6E8A.00."""
from __future__ import annotations
import io, json, math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import requests
from obspy import read
from scipy import signal

STATION = "R6E8A"
NETWORK = "AM"
LOCATION = "00"
FDSN = "https://data.raspberryshake.org/fdsnws/dataselect/1/query"
ET = ZoneInfo("America/Detroit")
OUT = Path("data/daily-highest.json")

def fetch(channel: str, start: datetime, end: datetime):
    params = {"net": NETWORK, "sta": STATION, "loc": LOCATION, "cha": channel,
              "start": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
              "end": end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")}
    response = requests.get(FDSN, params=params, timeout=120)
    response.raise_for_status()
    stream = read(io.BytesIO(response.content), format="MSEED")
    stream.merge(method=1, fill_value="interpolate")
    return stream[0]

def per_second_rms(x: np.ndarray, fs: int):
    n = len(x) // fs
    y = x[:n * fs].reshape(n, fs)
    y = signal.detrend(y, axis=1, type="linear")
    return np.sqrt(np.mean(y * y, axis=1))

def dominant_frequency(x: np.ndarray, fs: float):
    x = signal.detrend(x.astype(float))
    frequency, power = signal.periodogram(x, fs=fs, window="hann", scaling="spectrum")
    mask = (frequency >= 0.1) & (frequency <= 20.0)
    indexes = np.where(mask)[0]
    peak_index = indexes[int(np.argmax(power[mask]))]
    peak = float(frequency[peak_index])
    if 0 < peak_index < len(power) - 1:
        a, b, c = np.log(power[peak_index - 1:peak_index + 2] + 1e-300)
        denominator = a - 2 * b + c
        if denominator:
            peak += float(0.5 * (a - c) / denominator * (frequency[1] - frequency[0]))
    return peak

def main():
    now_et = datetime.now(ET)
    end_et = now_et - timedelta(minutes=30)
    start_et = end_et.replace(hour=0, minute=0, second=0, microsecond=0)
    if end_et <= start_et + timedelta(minutes=1):
        start_et -= timedelta(days=1)
    hdf = fetch("HDF", start_et, end_et)
    ehz = fetch("EHZ", start_et, end_et)
    fs = int(round(hdf.stats.sampling_rate))
    data = np.asarray(hdf.data, dtype=float)
    rms = per_second_rms(data, fs)
    median = float(np.median(rms))
    mad = float(1.4826 * np.median(np.abs(rms - median))) or 1.0
    z = (rms - median) / mad
    hot = z >= 8.0
    groups = []
    i = 0
    while i < len(hot):
        if not hot[i]:
            i += 1
            continue
        j = i + 1
        while j < len(hot) and hot[j]:
            j += 1
        groups.append((i, j))
        i = j
    if not groups:
        peak = int(np.argmax(rms))
        groups = [(peak, peak + 1)]
    i, j = max(groups, key=lambda group: float(np.max(rms[group[0]:group[1]])))
    peak_i = i + int(np.argmax(rms[i:j]))
    hdf_start = hdf.stats.starttime.datetime.replace(tzinfo=timezone.utc)
    event_start = hdf_start + timedelta(seconds=i)
    event_end = hdf_start + timedelta(seconds=j)
    frequency = dominant_frequency(data[i * fs:j * fs], fs)
    efs = int(round(ehz.stats.sampling_rate))
    edata = np.asarray(ehz.data, dtype=float)
    erms = per_second_rms(edata, efs)
    emedian = float(np.median(erms))
    emad = float(1.4826 * np.median(np.abs(erms - emedian))) or 1.0
    peak_utc = hdf_start + timedelta(seconds=peak_i)
    ehz_start = ehz.stats.starttime.datetime.replace(tzinfo=timezone.utc)
    ehz_index = int((peak_utc - ehz_start).total_seconds())
    ehz_z = float((erms[ehz_index] - emedian) / emad) if 0 <= ehz_index < len(erms) else float("nan")
    peak_rms = float(rms[peak_i])
    p99 = float(np.percentile(rms, 99))
    peak_et = peak_utc.astimezone(ET)
    result = {
        "station": "AM.R6E8A.00", "channel": "HDF", "event_date_et": peak_et.date().isoformat(),
        "display_time_et": peak_et.strftime("%b %-d · %-I:%M:%S %p ET"),
        "event_start_utc": event_start.isoformat().replace("+00:00", "Z"),
        "event_end_utc": event_end.isoformat().replace("+00:00", "Z"),
        "duration_s": round((event_end - event_start).total_seconds(), 2),
        "dominant_frequency_hz": round(frequency, 4), "peak_rms_counts": round(peak_rms, 4),
        "daily_median_rms_counts": round(median, 4), "daily_99th_rms_counts": round(p99, 4),
        "above_median_percent": round((peak_rms / median - 1) * 100, 1),
        "multiple_of_median": round(peak_rms / median, 2),
        "multiple_of_99th_percentile": round(peak_rms / p99, 2),
        "hdf_robust_z": round(float(z[peak_i]), 2),
        "simultaneous_ehz_robust_z": None if math.isnan(ehz_z) else round(ehz_z, 2),
        "classification": "Predominantly HDF pressure/infrasound" if math.isnan(ehz_z) or ehz_z < 4 else "HDF event with elevated EHZ context",
        "analyzed_through_et": end_et.strftime("%B %-d, %Y, %-I:%M %p Eastern Time"),
        "calibration_note": "Instrument counts are not converted to dBA, dBC, NC or dBG without acoustic calibration."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")

if __name__ == "__main__":
    main()
