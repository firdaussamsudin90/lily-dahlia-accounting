"""
Parses a WhatsApp chat export — either a single .zip ("Export Chat" with
media) or the _chat.txt plus its media files uploaded alongside it — into a
list of dated messages with any attached media resolved to bytes.

Handles the two common export line formats:
  Android: "21/05/2026, 14:32 - Firdaus: <caption>"
  iOS:     "[21/05/2026, 14:32:00] Firdaus: <caption>"
Lines that don't start with a timestamp are continuations of the previous
message's caption (WhatsApp wraps multi-line captions this way).
"""
import io
import re
import zipfile
from datetime import datetime

LINE_RE_ANDROID = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?:\s?[APap][Mm])?)\s*-\s*([^:]+):\s?(.*)$"
)
LINE_RE_IOS = re.compile(
    r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\]\s*([^:]+):\s?(.*)$"
)

MEDIA_RE = re.compile(r"([\w\-]+\.(?:jpg|jpeg|png|gif|webp|mp4|3gp|opus|pdf))", re.IGNORECASE)

CONTENT_TYPE_BY_EXT = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "pdf": "application/pdf",
    "mp4": "video/mp4", "3gp": "video/3gpp", "opus": "audio/ogg",
}


def _parse_date(date_str):
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _parse_lines(text):
    messages = []
    for raw_line in text.splitlines():
        line = raw_line.strip("‎‏﻿ ")
        if not line:
            continue
        m = LINE_RE_ANDROID.match(line) or LINE_RE_IOS.match(line)
        if m:
            date_str, time_str, sender, message = m.groups()
            messages.append({
                "date": _parse_date(date_str), "time": time_str,
                "sender": sender.strip(), "message": message,
            })
        elif messages:
            messages[-1]["message"] += "\n" + line
    return messages


def _guess_content_type(filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return CONTENT_TYPE_BY_EXT.get(ext, "application/octet-stream")


def parse_export(uploaded_files):
    """uploaded_files: list of Streamlit UploadedFile objects — either a
    single .zip, or one .txt chat log plus any number of loose media files
    selected alongside it.

    Returns a list of dicts: date, time, sender, caption, media_filename,
    media_bytes, media_content_type — one per chat message that referenced a
    media attachment. Messages whose media file isn't present in the upload
    still get an entry (media_bytes=None) so nothing silently disappears.
    """
    media_bytes_by_name = {}
    chat_text = None

    zips = [f for f in uploaded_files if f.name.lower().endswith(".zip")]
    if zips:
        with zipfile.ZipFile(io.BytesIO(zips[0].getvalue())) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                data = zf.read(name)
                base = name.rsplit("/", 1)[-1]
                if base.lower().endswith(".txt"):
                    chat_text = data.decode("utf-8", errors="replace")
                else:
                    media_bytes_by_name[base] = data
    else:
        for f in uploaded_files:
            if f.name.lower().endswith(".txt"):
                chat_text = f.getvalue().decode("utf-8", errors="replace")
            else:
                media_bytes_by_name[f.name] = f.getvalue()

    if chat_text is None:
        raise ValueError("No _chat.txt (or other .txt chat log) found in the upload.")

    results = []
    for msg in _parse_lines(chat_text):
        if msg["date"] is None:
            continue
        media_match = MEDIA_RE.search(msg["message"])
        if not media_match:
            continue  # only messages with an attached file matter for document import
        media_filename = media_match.group(1)
        caption = msg["message"]
        caption = re.sub(r"[<>]|\(file attached\)|attached:", "", caption)
        caption = caption.replace(media_filename, "").strip(" ‎‏\n")
        results.append({
            "date": msg["date"],
            "time": msg["time"],
            "sender": msg["sender"],
            "caption": caption,
            "media_filename": media_filename,
            "media_bytes": media_bytes_by_name.get(media_filename),
            "media_content_type": _guess_content_type(media_filename),
        })
    return results
