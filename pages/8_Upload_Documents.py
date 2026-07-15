import calendar
from datetime import date

import streamlit as st

from modules.auth import require_login
from modules.db import get_connection, init_db
from modules.document_matcher import best_match
from modules.documents import rematch_document, save_document
from modules.receipt_ocr import extract_amount, extract_text
from modules.storage import download_bytes
from modules.whatsapp_import import parse_export

init_db()
require_login()
st.title("📥 Upload Documents")
st.caption(
    "Attach receipts, invoices, and ad confirmations to ledger entries. Upload files one by one, "
    "or import a month's worth at once from a WhatsApp chat export."
)

IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}


def is_image(filename):
    return bool(filename) and filename.rsplit(".", 1)[-1].lower() in IMAGE_EXTS


def txn_label(t):
    amount = t["debit"] if t["debit"] else t["credit"]
    amount_str = f"RM{amount:,.2f}" if amount is not None else "RM?"
    return f"{t['date']} · {t['counterparty'] or '(no counterparty)'} · {amount_str} · {t['category'] or 'Uncategorized'}"


tab_manual, tab_whatsapp = st.tabs(["📄 Upload files", "💬 WhatsApp import"])

# ============================================================ Mode 1 =======
with tab_manual:
    st.subheader("Upload files one by one")

    conn = get_connection()
    all_months = [r["month"] for r in conn.execute(
        "SELECT DISTINCT month FROM transactions ORDER BY month DESC"
    ).fetchall()]
    conn.close()

    month_scope = st.multiselect(
        "Narrow the ledger-entry list to these months", options=all_months, default=all_months,
        key="manual_month_scope",
    )

    conn = get_connection()
    txn_rows = []
    if month_scope:
        q = ",".join("%s" for _ in month_scope)
        txn_rows = [dict(r) for r in conn.execute(
            f"SELECT * FROM transactions WHERE month IN ({q}) ORDER BY date DESC", month_scope
        ).fetchall()]
    conn.close()
    txn_options = {None: "— Leave unmatched (pending review) —"}
    for t in txn_rows:
        txn_options[t["id"]] = txn_label(t)
    txn_by_id = {t["id"]: t for t in txn_rows}

    uploaded_files = st.file_uploader(
        "Receipt / invoice photos or PDFs", type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True, key="manual_files",
    )

    if uploaded_files:
        with st.form("manual_upload_form"):
            for i, f in enumerate(uploaded_files):
                st.markdown(f"**{f.name}**")
                if is_image(f.name):
                    st.image(f.getvalue(), width=460)
                else:
                    st.caption("(no preview)")
                st.text_input("Caption / description", key=f"manual_caption_{i}")
                st.selectbox(
                    "Match to ledger entry", options=list(txn_options.keys()),
                    format_func=lambda k: txn_options[k], key=f"manual_match_{i}",
                )
                st.divider()

            if st.form_submit_button("💾 Save all", type="primary"):
                for i, f in enumerate(uploaded_files):
                    caption = st.session_state.get(f"manual_caption_{i}")
                    match_id = st.session_state.get(f"manual_match_{i}")
                    month = txn_by_id[match_id]["month"] if match_id is not None else None
                    flag_color, flag_note = (None, None)
                    if match_id is None:
                        flag_color, flag_note = "red", "Uploaded without a ledger match — pending review."
                    result = save_document(
                        file_bytes=f.getvalue(), filename=f.name, content_type=f.type,
                        caption=caption or None, month=month, document_type="receipt",
                        linked_transaction_id=match_id, flag_color=flag_color, flag_note=flag_note,
                        source="manual_upload",
                    )
                    if result["voucher_number"]:
                        st.success(f"**{f.name}**: saved, linked, and generated **{result['voucher_number']}**.")
                    elif match_id is not None:
                        st.success(f"**{f.name}**: saved and linked.")
                    else:
                        st.info(f"**{f.name}**: saved as unmatched — see Pending Review below.")
                st.balloons()

# ============================================================ Mode 2 =======
with tab_whatsapp:
    st.subheader("Import from a WhatsApp chat export")
    st.caption(
        "Upload WhatsApp's exported chat — a `.zip` from 'Export Chat' (with media), or the `_chat.txt` "
        "plus the media files selected alongside it — then pick the month to import. The full export can "
        "contain years of history; only messages in the selected month are parsed."
    )

    c1, c2 = st.columns(2)
    this_year = date.today().year
    wa_year = c1.selectbox(
        "Month to import — year", options=list(range(this_year - 2, this_year + 2)), index=2, key="wa_year"
    )
    wa_month_num = c2.selectbox(
        "Month to import — month", options=list(range(1, 13)),
        format_func=lambda m: calendar.month_name[m], index=date.today().month - 1, key="wa_month",
    )

    wa_files = st.file_uploader(
        "Chat export (.zip, or .txt + media files)",
        type=["zip", "txt", "jpg", "jpeg", "png", "gif", "webp", "mp4", "pdf", "opus", "3gp"],
        accept_multiple_files=True, key="wa_files",
    )

    if st.button("🔍 Parse export", disabled=not wa_files):
        try:
            with st.spinner("Parsing chat export and reading receipt images..."):
                parsed = parse_export(wa_files)
                in_month = [m for m in parsed if m["date"].year == wa_year and m["date"].month == wa_month_num]
                conn = get_connection()
                for item in in_month:
                    ocr_text = (
                        extract_text(item["media_bytes"])
                        if item["media_bytes"] and is_image(item["media_filename"]) else None
                    )
                    item["suggested_amount"] = extract_amount(ocr_text) or extract_amount(item["caption"])
                    match, confidence, reason = best_match(conn, item["date"].isoformat(), item["suggested_amount"])
                    item["suggested_transaction_id"] = match["id"] if match else None
                    item["confidence"] = confidence
                    item["reason"] = reason
                conn.close()
            st.session_state["wa_parsed"] = in_month
            st.session_state["wa_month_str"] = f"{wa_year:04d}-{wa_month_num:02d}"
            st.session_state["wa_total_found"] = len(parsed)
            st.session_state["wa_missing_media"] = sum(1 for m in parsed if m["media_bytes"] is None)
        except ValueError as e:
            st.error(str(e))

    parsed_items = st.session_state.get("wa_parsed")
    if parsed_items is not None:
        month_str = st.session_state["wa_month_str"]
        month_label = f"{calendar.month_name[int(month_str[5:])]} {month_str[:4]}"

        if not parsed_items:
            total_found = st.session_state.get("wa_total_found", 0)
            if total_found == 0:
                st.warning(
                    "No media messages were recognized anywhere in this export, not just this month — "
                    "the chat log's format probably isn't matching the parser (e.g. a WhatsApp export "
                    "variant this app doesn't handle yet). Double-check the .txt file is the real "
                    "`_chat.txt`, and if this keeps happening, share a couple of anonymized sample lines "
                    "from it so the parser can be fixed to match your export's exact format."
                )
            else:
                st.info(
                    f"Found {total_found} media message(s) elsewhere in the export, but none in "
                    f"{month_label} — try a different month, or double check the year."
                )
        else:
            st.write(f"**{len(parsed_items)}** receipt/media message(s) found for {month_label}. Review before saving.")
            missing = sum(1 for m in parsed_items if m["media_bytes"] is None)
            if missing:
                st.warning(
                    f"{missing} of these reference a media file that isn't in your upload (name mismatch, "
                    "or it wasn't selected/included in the zip) — those rows are unchecked by default "
                    "and won't be saved unless you re-upload the matching file."
                )

            conn = get_connection()
            txn_rows = [dict(r) for r in conn.execute(
                "SELECT * FROM transactions WHERE month = %s ORDER BY date ASC", (month_str,)
            ).fetchall()]
            conn.close()
            wa_txn_options = {None: "— Leave unmatched (pending review) —"}
            for t in txn_rows:
                wa_txn_options[t["id"]] = txn_label(t)
            option_ids = list(wa_txn_options.keys())

            with st.form("wa_confirm_form"):
                for i, item in enumerate(parsed_items):
                    st.markdown(f"**{item['date'].isoformat()} {item['time']}** — {item['sender']}")
                    if item["media_bytes"] and is_image(item["media_filename"]):
                        st.image(item["media_bytes"], width=460)
                    elif item["media_bytes"]:
                        st.caption(f"📎 {item['media_filename']} (no preview)")
                    else:
                        st.warning(f"⚠️ {item['media_filename']} not in upload")

                    st.write(item["caption"] or "_(no caption)_")
                    if item["suggested_amount"] is not None:
                        st.caption(f"Detected amount: RM{item['suggested_amount']:,.2f}")

                    default_idx = (
                        option_ids.index(item["suggested_transaction_id"])
                        if item["suggested_transaction_id"] in option_ids else 0
                    )
                    # Full row width (not squeezed into a side column) so the option text —
                    # date, counterparty, amount, category — isn't cut off.
                    st.selectbox(
                        "Match to ledger entry", options=option_ids, format_func=lambda k: wa_txn_options[k],
                        index=default_idx, key=f"wa_match_{i}",
                    )
                    if item["confidence"] == "red":
                        st.error(item["reason"])
                    elif item["confidence"] == "yellow":
                        st.warning(item["reason"])
                    st.checkbox("Include", value=item["media_bytes"] is not None, key=f"wa_include_{i}")
                    st.divider()

                if st.form_submit_button("✅ Confirm & save selected", type="primary"):
                    saved = 0
                    for i, item in enumerate(parsed_items):
                        if not st.session_state.get(f"wa_include_{i}"):
                            continue
                        match_id = st.session_state.get(f"wa_match_{i}")
                        if match_id is None:
                            flag_color, flag_note = "red", item["reason"] or "Left unmatched — pending review."
                        elif match_id == item["suggested_transaction_id"] and item["confidence"] is not None:
                            flag_color, flag_note = item["confidence"], item["reason"]
                        else:
                            flag_color, flag_note = None, None  # human-confirmed or auto-confident match
                        save_document(
                            file_bytes=item["media_bytes"], filename=item["media_filename"],
                            content_type=item["media_content_type"], caption=item["caption"] or None,
                            month=month_str, document_type="receipt", linked_transaction_id=match_id,
                            flag_color=flag_color, flag_note=flag_note, source="whatsapp_import",
                            message_date=item["date"].isoformat(),
                            notes=f"WhatsApp import — sender: {item['sender']}, file: {item['media_filename']}",
                        )
                        saved += 1
                    st.success(f"Saved {saved} document(s).")
                    del st.session_state["wa_parsed"]
                    st.balloons()

# ============================================================ Pending review
st.divider()
st.subheader("🔎 Pending review")
st.caption("Documents saved without a confident ledger match. Match them here whenever you're ready.")

conn = get_connection()
pending = [dict(r) for r in conn.execute(
    """SELECT * FROM documents WHERE linked_transaction_id IS NULL OR flag_color IS NOT NULL
       ORDER BY uploaded_date DESC"""
).fetchall()]
conn.close()

if not pending:
    st.success("Nothing pending — every uploaded document is confidently matched.")
else:
    st.write(f"**{len(pending)}** document(s) need a look.")
    conn = get_connection()
    review_months = [r["month"] for r in conn.execute(
        "SELECT DISTINCT month FROM transactions ORDER BY month DESC"
    ).fetchall()]
    conn.close()

    for doc in pending:
        label = f"{doc['filename'] or '(no file)'} — {doc['caption'] or '(no caption)'} — uploaded {doc['uploaded_date']}"
        with st.expander(label):
            if doc["flag_color"]:
                (st.error if doc["flag_color"] == "red" else st.warning)(doc["flag_note"] or "Flagged for review.")
            if doc["storage_path"] and is_image(doc["filename"]):
                st.image(download_bytes(doc["storage_path"]), width=460)

            scope = st.multiselect(
                "Ledger months to search", options=review_months, default=review_months,
                key=f"pending_scope_{doc['id']}",
            )
            conn = get_connection()
            candidates = []
            if scope:
                q = ",".join("%s" for _ in scope)
                candidates = [dict(r) for r in conn.execute(
                    f"SELECT * FROM transactions WHERE month IN ({q}) ORDER BY date DESC", scope
                ).fetchall()]
            conn.close()
            options = {None: "— Leave unmatched —"}
            for t in candidates:
                options[t["id"]] = txn_label(t)

            new_match = st.selectbox(
                "Match to ledger entry", options=list(options.keys()), format_func=lambda k: options[k],
                key=f"pending_match_{doc['id']}",
            )
            if st.button("Save match", key=f"pending_save_{doc['id']}"):
                if new_match is None:
                    st.warning("Pick a ledger entry to match, or leave this for later.")
                else:
                    voucher_number, _ = rematch_document(doc["id"], new_match)
                    st.success(f"Linked and generated **{voucher_number}**." if voucher_number else "Linked.")
                    st.rerun()
