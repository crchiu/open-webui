
"""
Speaker / word timestamp alignment for Open WebUI 0.13.3.
"""

def assign_speaker(start, end, turns):
    """Select the speaker with the greatest temporal overlap."""
    if not turns:
        return "UNKNOWN"

    midpoint = (start + end) / 2
    best_speaker = None
    best_overlap = 0.0

    for turn in turns:
        overlap = max(
            0.0,
            min(end, turn["end"]) - max(start, turn["start"]),
        )
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = turn["speaker"]

    if best_speaker is not None:
        return best_speaker

    # No overlap: use the closest speaker interval.
    closest = min(
        turns,
        key=lambda t: min(
            abs(midpoint - t["start"]),
            abs(midpoint - t["end"]),
        ),
    )
    return closest["speaker"]


def align_words(words, turns, max_gap=1.2):
    """
    Assign speakers to timestamped words and group adjacent
    words from the same speaker.
    """
    words = sorted(words, key=lambda w: (w["start"], w["end"]))
    turns = sorted(turns, key=lambda t: (t["start"], t["end"]))

    grouped = []

    for word in words:
        text = word["text"]
        if not text.strip():
            continue

        start = float(word["start"])
        end = float(word["end"])

        if end < start:
            continue

        speaker = assign_speaker(start, end, turns)

        if (
            grouped
            and grouped[-1]["speaker"] == speaker
            and start - grouped[-1]["end"] <= max_gap
        ):
            grouped[-1]["text"] += text
            grouped[-1]["end"] = max(
                grouped[-1]["end"], end
            )
        else:
            grouped.append({
                "speaker": speaker,
                "start": start,
                "end": end,
                "text": text,
            })

    for item in grouped:
        item["start"] = round(item["start"], 3)
        item["end"] = round(item["end"], 3)
        item["text"] = item["text"].strip()

    return grouped
