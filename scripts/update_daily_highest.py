#!/usr/bin/env python3
"""Refresh the live R6E8A HDF/EHZ instrument record.

The public dashboard uses this derived JSON plus Raspberry Shake's official
DataView embeds. Raw MiniSEED is streamed from FDSN and is never committed.
HDF and EHZ are processed independently and gaps are never interpolated.
"""
from __future__ import annotations

import io
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import requests
from obspy import UTCDateTime, read
from scipy import signal


STATION = "R6E8A"
NETWORK = "AM"
LOCATION = "00"  # Required internally by FDSN; intentionally hidden in public labels.
FDSN = "https://data.raspberryshake.org/fdsnws/dataselect/1/query"
ET = ZoneInfo("America/Detroit")
OUT = Path("data/daily-highest.json")
HISTORY = Path("data/daily-highest-history.json")
HDF_COUNTS_PER_PA = 56_000.0


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def format_et(value: datetime) -> str:
    return value.astimezone(ET).strftime("%b %-d - %-I:%M:%S %p EST")


def fetch(channel: str, start: datetime, end: datetime):
    params = {
        "net": NETWORK,
        "sta": STATION,
        "loc": LOCATION,
        "cha": channel,
        "start": iso_utc(start),
        "end": iso_utc(end),
        "format": "miniseed",
        "nodata": 404,
    }
    response = requests.get(
        FDSN,
        params=params,
        timeout=180,
        headers={"User-Agent": "r6e8a-dashboard/2.0"},
    )
    response.raise_for_status()
    stream = read(io.BytesIO(response.content), format="MSEED")
    stream.merge(method=0)
    return stream.split(), response.url


def per_second_records(stream):
    """Return sorted (UTC epoch second, RMS counts) without bridging gaps."""
    records = []
    for trace in stream:
        fs = int(round(float(trace.stats.sampling_rate)))
        if fs <= 0:
            continue
        values = np.asarray(trace.data, dtype=float)
        count = len(values) // fs
        if count <= 0:
            continue
        frames = values[: count * fs].reshape(count, fs)
        frames = signal.detrend(frames, axis=1, type="linear")
        rms = np.sqrt(np.mean(frames * frames, axis=1))
        start_epoch = float(trace.stats.starttime.timestamp)
        records.extend((start_epoch + index, float(value)) for index, value in enumerate(rms))
    records.sort(key=lambda item: item[0])
    return records


def dominant_frequency(stream, peak_epoch: float) -> float | None:
    """Use an eleven-second raw-count window centered on the event peak."""
    target = UTCDateTime(peak_epoch)
    for trace in stream:
        if trace.stats.starttime <= target <= trace.stats.endtime:
            fs = float(trace.stats.sampling_rate)
            center = int(round((target - trace.stats.starttime) * fs))
            half = max(1, int(round(5.0 * fs)))
            values = np.asarray(trace.data[max(0, center - half): center + half + 1], dtype=float)
            if values.size < max(8, int(fs)):
                return None
            values = signal.detrend(values)
            frequencies, power = signal.periodogram(
                values, fs=fs, window="hann", scaling="spectrum"
            )
            mask = (frequencies >= 0.1) & (frequencies <= 20.0)
            if not np.any(mask):
                return None
            indexes = np.where(mask)[0]
            peak_index = indexes[int(np.argmax(power[mask]))]
            peak = float(frequencies[peak_index])
            if 0 < peak_index < len(power) - 1:
                a, b, c = np.log(power[peak_index - 1:peak_index + 2] + 1e-300)
                denominator = a - 2 * b + c
                if denominator:
                    peak += float(
                        0.5 * (a - c) / denominator * (frequencies[1] - frequencies[0])
                    )
            return round(peak, 4)
    return None


def event_summary(records, stream, start: datetime, end: datetime):
    start_epoch = start.astimezone(timezone.utc).timestamp()
    end_epoch = end.astimezone(timezone.utc).timestamp()
    window = [(epoch, value) for epoch, value in records if start_epoch <= epoch < end_epoch]
    if not window:
        return None

    epochs = np.asarray([item[0] for item in window], dtype=float)
    rms = np.asarray([item[1] for item in window], dtype=float)
    median = float(np.median(rms))
    mad = float(1.4826 * np.median(np.abs(rms - median))) or 1.0
    robust_z = (rms - median) / mad
    hot_indexes = np.where(robust_z >= 8.0)[0]

    groups = []
    if hot_indexes.size:
        group = [int(hot_indexes[0])]
        for index in hot_indexes[1:]:
            index = int(index)
            if index == group[-1] + 1 and epochs[index] - epochs[group[-1]] <= 1.5:
                group.append(index)
            else:
                groups.append(group)
                group = [index]
        groups.append(group)
    else:
        groups = [[int(np.argmax(rms))]]

    chosen = max(groups, key=lambda indexes: float(np.max(rms[indexes])))
    peak_index = max(chosen, key=lambda index: float(rms[index]))
    event_start = datetime.fromtimestamp(float(epochs[chosen[0]]), tz=timezone.utc)
    event_end = datetime.fromtimestamp(float(epochs[chosen[-1]] + 1.0), tz=timezone.utc)
    peak_time = datetime.fromtimestamp(float(epochs[peak_index]), tz=timezone.utc)
    peak_rms = float(rms[peak_index])
    frequency = dominant_frequency(stream, float(epochs[peak_index]))

    return {
        "event_date_et": peak_time.astimezone(ET).date().isoformat(),
        "display_time_et": format_et(peak_time),
        "event_start_utc": iso_utc(event_start),
        "event_end_utc": iso_utc(event_end),
        "duration_s": round((event_end - event_start).total_seconds(), 2),
        "dominant_frequency_hz": frequency,
        "peak_rms_counts": round(peak_rms, 4),
        "window_median_rms_counts": round(median, 4),
        "above_window_median_percent": round((peak_rms / median - 1.0) * 100.0, 1)
        if median
        else None,
        "multiple_of_window_median": round(peak_rms / median, 2) if median else None,
        "robust_z": round(float(robust_z[peak_index]), 2),
        "observed_seconds": int(len(window)),
        "coverage_percent": round(100.0 * len(window) / max(1.0, end_epoch - start_epoch), 1),
        "latest_sample_utc": iso_utc(
            datetime.fromtimestamp(float(epochs[-1] + 1.0), tz=timezone.utc)
        ),
        "_peak_epoch": float(epochs[peak_index]),
    }


def z_at(records, start: datetime, end: datetime, epoch: float) -> float | None:
    start_epoch = start.astimezone(timezone.utc).timestamp()
    end_epoch = end.astimezone(timezone.utc).timestamp()
    window = [(t, value) for t, value in records if start_epoch <= t < end_epoch]
    if not window:
        return None
    values = np.asarray([item[1] for item in window], dtype=float)
    median = float(np.median(values))
    mad = float(1.4826 * np.median(np.abs(values - median))) or 1.0
    nearest = min(window, key=lambda item: abs(item[0] - epoch))
    if abs(nearest[0] - epoch) > 1.5:
        return None
    return round(float((nearest[1] - median) / mad), 2)


def public_event(event, channel: str):
    if event is None:
        return None
    clean = dict(event)
    for key in (
        "_peak_epoch",
        "window_median_rms_counts",
        "above_window_median_percent",
        "multiple_of_window_median",
        "robust_z",
    ):
        clean.pop(key, None)
    if channel == "HDF" and clean.get("peak_rms_counts") is not None:
        clean["estimated_pressure_pa_rms_nominal"] = round(
            float(clean["peak_rms_counts"]) / HDF_COUNTS_PER_PA, 6
        )
    return clean


def update_history(day_hdf, generated_utc):
    if day_hdf is None:
        return
    history = {
        "station": "AM.R6E8A",
        "timezone": "America/Detroit",
        "metric": "HDF one-second RMS detector record with a nominal pressure estimate",
        "calibration_note": (
            "Estimated unweighted HDF pressure uses the manufacturer's nominal "
            "56,000 counts/Pa sensitivity (estimated +/-10%). It is not response-corrected, "
            "dB(A), dB(C), dB(G), NC, RC, or a standards-compliance result."
        ),
        "days": [],
    }
    if HISTORY.exists():
        try:
            loaded = json.loads(HISTORY.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                history.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass

    record = public_event(day_hdf, "HDF")
    date_key = record["event_date_et"]
    public_keys = {
        "event_date_et",
        "display_time_et",
        "event_start_utc",
        "event_end_utc",
        "duration_s",
        "dominant_frequency_hz",
        "peak_rms_counts",
        "estimated_pressure_pa_rms_nominal",
        "observed_seconds",
        "coverage_percent",
        "latest_sample_utc",
        "source_commit",
    }
    days = []
    for item in history.get("days", []):
        if item.get("event_date_et") == date_key:
            continue
        cleaned = {key: value for key, value in item.items() if key in public_keys}
        if cleaned.get("peak_rms_counts") is not None:
            cleaned["estimated_pressure_pa_rms_nominal"] = round(
                float(cleaned["peak_rms_counts"]) / HDF_COUNTS_PER_PA, 6
            )
        days.append(cleaned)
    days.append(record)
    days.sort(key=lambda item: item.get("event_date_et", ""))
    history["days"] = days[-60:]
    history["generated_utc"] = generated_utc
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")


def main():
    now_et = datetime.now(ET)
    cutoff_et = now_et - timedelta(minutes=30)
    trailing_start_et = cutoff_et - timedelta(hours=24)
    day_start_et = cutoff_et.replace(hour=0, minute=0, second=0, microsecond=0)

    streams = {}
    records = {}
    source_urls = {}
    errors = {}
    for channel in ("HDF", "EHZ"):
        try:
            stream, source_url = fetch(channel, trailing_start_et, cutoff_et)
            streams[channel] = stream
            records[channel] = per_second_records(stream)
            source_urls[channel] = source_url
        except Exception as error:  # Keep the other channel available when one fails.
            streams[channel] = None
            records[channel] = []
            errors[channel] = f"{type(error).__name__}: {error}"

    trailing = {
        channel: event_summary(
            records[channel], streams[channel], trailing_start_et, cutoff_et
        )
        if streams[channel]
        else None
        for channel in ("HDF", "EHZ")
    }
    detroit_day = {
        channel: event_summary(records[channel], streams[channel], day_start_et, cutoff_et)
        if streams[channel]
        else None
        for channel in ("HDF", "EHZ")
    }

    day_hdf = detroit_day["HDF"]
    generated_utc = iso_utc(datetime.now(timezone.utc))

    channels = {}
    for channel in ("HDF", "EHZ"):
        event = detroit_day[channel]
        channels[channel] = {
            "available": event is not None,
            "role": "Primary pressure/infrasound" if channel == "HDF" else "Secondary vertical motion",
            "units": "instrument counts (one-second RMS)",
            "latest_sample_utc": event.get("latest_sample_utc") if event else None,
            "coverage_percent_since_midnight": event.get("coverage_percent") if event else 0.0,
            "detroit_day_highest": public_event(event, channel),
            "trailing_24h_highest": public_event(trailing[channel], channel),
            "error": errors.get(channel),
        }

    result = {
        "schema_version": 3,
        "station": "AM.R6E8A",
        "generated_utc": generated_utc,
        "analyzed_through_utc": iso_utc(cutoff_et),
        "analyzed_through_et": cutoff_et.strftime(
            "%B %-d, %Y, %-I:%M %p Eastern Time"
        ),
        "requested_window_utc": {
            "start": iso_utc(trailing_start_et),
            "end": iso_utc(cutoff_et),
        },
        "source": "Raspberry Shake FDSN dataselect",
        "source_urls": source_urls,
        "archive_delay_minutes": 30,
        "channels": channels,
        "calibration_note": (
            "Estimated unweighted HDF pressure uses the manufacturer's nominal 56,000 "
            "counts/Pa sensitivity (estimated +/-10%). It is not response-corrected, "
            "dB(A), dB(C), dB(G), NC, RC, or a standards-compliance result. "
            "HDF and EHZ remain independent."
        ),
    }

    # Legacy top-level fields retained for old report consumers, without percentile fields.
    if day_hdf is not None:
        result.update(
            {
                "channel": "HDF",
                "event_date_et": day_hdf["event_date_et"],
                "display_time_et": day_hdf["display_time_et"],
                "event_start_utc": day_hdf["event_start_utc"],
                "event_end_utc": day_hdf["event_end_utc"],
                "duration_s": day_hdf["duration_s"],
                "dominant_frequency_hz": day_hdf["dominant_frequency_hz"],
                "peak_rms_counts": day_hdf["peak_rms_counts"],
                "estimated_pressure_pa_rms_nominal": round(
                    day_hdf["peak_rms_counts"] / HDF_COUNTS_PER_PA, 6
                ),
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    update_history(day_hdf, generated_utc)

    if not day_hdf:
        print("HDF data were unavailable; preserved channel status in output")


if __name__ == "__main__":
    main()
