# /// script
# requires-python = ">=3.10"
# dependencies = ["praat-parselmouth", "numpy"]
# ///
"""Prosody analysis for presentation practice audio.

Usage:
    uv run prosody_analysis.py <audio.wav> [whisper_segments.json] > prosody.json

Outputs JSON to stdout with:
- pitch statistics (median, 5-95% range in semitones, SD in semitones)
- intensity (energy) dynamics
- per-minute breakdown to locate monotone stretches
- acoustic pause detection (silence runs in the intensity track)
- speaking rate per segment (chars/sec, from whisper JSON if given)

All processing is local. No network access is required.
"""
import argparse
import json
import sys

import numpy as np
import parselmouth


def semitones(f0_hz, ref_hz):
    return 12 * np.log2(f0_hz / ref_hz)


def parse_args():
    p = argparse.ArgumentParser(
        description="Analyze pitch, energy, pauses and speaking rate of a practice recording.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("audio", help="mono WAV file (16 kHz recommended; any rate works)")
    p.add_argument("segments", nargs="?", default=None,
                   help="whisper JSON (with 'segments' list) for speaking-rate stats")
    p.add_argument("--pitch-floor", type=float, default=60.0, help="Hz")
    p.add_argument("--pitch-ceiling", type=float, default=400.0, help="Hz")
    p.add_argument("--window", type=float, default=60.0,
                   help="window length in seconds for the per-window breakdown")
    p.add_argument("--min-pause", type=float, default=0.3,
                   help="minimum acoustic silence length (s) counted as a pause")
    return p.parse_args()


def main():
    args = parse_args()

    try:
        snd = parselmouth.Sound(args.audio)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"error: could not read audio '{args.audio}': {e}")
    total_dur = snd.get_total_duration()

    # ---- Pitch ----
    pitch = snd.to_pitch(time_step=0.01, pitch_floor=args.pitch_floor,
                         pitch_ceiling=args.pitch_ceiling)
    f0 = pitch.selected_array["frequency"]
    times = pitch.xs()
    voiced = f0 > 0
    f0v = f0[voiced]
    tv = times[voiced]
    if len(f0v) < 50:
        sys.exit("error: almost no voiced frames found; is this a speech recording?")

    med = float(np.median(f0v))
    st = semitones(f0v, med)  # semitones relative to speaker median
    p5, p95 = np.percentile(st, [5, 95])

    # ---- Intensity ----
    intensity = snd.to_intensity(time_step=0.01)
    ivals = intensity.values[0]
    itimes = intensity.xs()
    ivoiced = ivals[ivals > 30]  # ignore silence floor
    if len(ivoiced) == 0:
        sys.exit("error: recording is silent (intensity never exceeds 30 dB)")

    # ---- Per-window breakdown: pitch variability & energy ----
    win = args.window
    windows = []
    for w0 in np.arange(0, total_dur, win):
        w1 = min(w0 + win, total_dur)
        m = (tv >= w0) & (tv < w1)
        im = (itimes >= w0) & (itimes < w1)
        iw = ivals[im]
        iw = iw[iw > 30]
        if m.sum() < 50:
            continue
        stw = semitones(f0v[m], med)
        windows.append({
            "start_min": round(w0 / 60, 1),
            "f0_median_hz": round(float(np.median(f0v[m])), 1),
            "pitch_range_st_5_95": round(float(np.percentile(stw, 95) - np.percentile(stw, 5)), 2),
            "pitch_sd_st": round(float(np.std(stw)), 2),
            "intensity_sd_db": round(float(np.std(iw)), 2) if len(iw) else None,
        })

    # ---- Acoustic pause detection (silence runs in the intensity track) ----
    speech_level = float(np.percentile(ivoiced, 80))
    sil_thresh = speech_level - 20  # 20 dB below typical speech level = silence
    silent = ivals < sil_thresh
    acoustic_pauses = []
    run_start = None
    for i, s in enumerate(silent):
        if s and run_start is None:
            run_start = itimes[i]
        elif not s and run_start is not None:
            dur = itimes[i] - run_start
            if dur >= args.min_pause:
                acoustic_pauses.append((run_start, dur))
            run_start = None
    if run_start is not None:
        acoustic_pauses.append((run_start, itimes[-1] - run_start))
    # ignore leading/trailing silence
    acoustic_pauses = [(t, d) for t, d in acoustic_pauses if t > 1 and t + d < total_dur - 1]

    # ---- Pauses & rate from whisper segments ----
    pauses, rates, seg_out = [], [], []
    if args.segments:
        with open(args.segments, encoding="utf-8") as f:
            data = json.load(f)
        segs = data.get("segments", data) if isinstance(data, dict) else data
        prev_end = None
        for s in segs:
            text = s["text"].strip()
            dur = s["end"] - s["start"]
            if prev_end is not None:
                gap = s["start"] - prev_end
                if gap > 0.25:
                    pauses.append({"t": round(prev_end, 1), "dur": round(gap, 2),
                                   "before": text[:20]})
            prev_end = s["end"]
            if dur > 0.3 and len(text) > 2:
                rate = len(text) / dur
                rates.append(rate)
                seg_out.append({"t": round(s["start"], 1), "chars_per_sec": round(rate, 1),
                                "text": text[:30]})

    result = {
        "duration_sec": round(total_dur, 1),
        "pitch": {
            "median_hz": round(med, 1),
            "range_st_5_95": round(float(p95 - p5), 2),
            "sd_st": round(float(np.std(st)), 2),
            "voiced_ratio": round(float(voiced.mean()), 3),
        },
        "intensity": {
            "mean_db": round(float(np.mean(ivoiced)), 1),
            "sd_db": round(float(np.std(ivoiced)), 1),
        },
        "per_minute": windows,
        "speaking_rate": {
            "mean_chars_per_sec": round(float(np.mean(rates)), 2) if rates else None,
            "p10": round(float(np.percentile(rates, 10)), 2) if rates else None,
            "p90": round(float(np.percentile(rates, 90)), 2) if rates else None,
            "fastest_segments": sorted(seg_out, key=lambda x: -x["chars_per_sec"])[:8],
        },
        "pauses_acoustic": {
            "count_over_0.3s": len(acoustic_pauses),
            "count_over_0.7s": sum(1 for _, d in acoustic_pauses if d > 0.7),
            "count_over_1.5s": sum(1 for _, d in acoustic_pauses if d > 1.5),
            "median_dur": round(float(np.median([d for _, d in acoustic_pauses])), 2) if acoustic_pauses else None,
            "per_minute_count": round(len(acoustic_pauses) / (total_dur / 60), 1),
            "longest": [{"t": round(t, 1), "dur": round(d, 2)}
                        for t, d in sorted(acoustic_pauses, key=lambda x: -x[1])[:10]],
        },
        "pauses_from_segments": {
            "count_over_0.25s": len(pauses),
            "longest": sorted(pauses, key=lambda p: -p["dur"])[:5],
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
