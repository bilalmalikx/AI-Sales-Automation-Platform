"""Inline, table-based email layout with no scripts, remote assets or tracking."""

from html import escape


def render_email(
    subject: str,
    body: str,
    sender: str,
    *,
    unsubscribe: str | None = None,
    label: str = "A MESSAGE FROM SKILLEDHAT",
    details: list[tuple[str, str]] | None = None,
) -> str:
    paragraphs = "".join(
        '<p style="margin:0 0 18px;font-size:16px;line-height:1.7;color:#424b63;">'
        + escape(part).replace("\n", "<br>")
        + "</p>"
        for part in body.split("\n\n")
    )
    rows = "".join(
        '<tr><td style="padding:9px 0;color:#747d94;font-size:13px;vertical-align:top;">'
        + escape(key)
        + '</td><td style="padding:9px 0 9px 16px;color:#263049;font-size:13px;text-align:right;overflow-wrap:anywhere;word-break:break-word;">'
        + escape(value)
        + "</td></tr>"
        for key, value in (details or [])
    )
    panel = (
        (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0 0;background:#f5f5fc;border:1px solid #e6e7f2;border-radius:12px;">'
            '<tr><td style="padding:12px 20px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            + rows
            + "</table></td></tr></table>"
        )
        if rows
        else ""
    )
    preference = (
        (
            '<p style="margin:12px 0 0;font-size:12px;line-height:1.6;">'
            '<a href="'
            + escape(unsubscribe, quote=True)
            + '" style="color:#636b82;text-decoration:underline;">Stop outreach from this workspace</a></p>'
        )
        if unsubscribe
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#f1f3f9;font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(subject)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f3f9;"><tr><td align="center" style="padding:40px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;table-layout:fixed;">
<tr><td style="padding:0 6px 24px;"><table role="presentation" cellpadding="0" cellspacing="0"><tr><td style="width:42px;height:42px;background:#5b57c9;border-radius:12px;color:#ffffff;text-align:center;font-size:22px;font-weight:bold;">S</td><td style="padding-left:12px;"><strong style="font-size:20px;letter-spacing:-.5px;color:#252c43;">Skilledhat</strong><br><span style="font-size:10px;letter-spacing:1.7px;color:#8088a1;">SALESWAY WORKSPACE</span></td></tr></table></td></tr>
<tr><td style="height:4px;background:#5b57c9;border-radius:16px 16px 0 0;"></td></tr>
<tr><td style="padding:32px 28px;background:#ffffff;border:1px solid #e0e4ef;border-top:0;border-radius:0 0 16px 16px;overflow-wrap:anywhere;">
<p style="margin:0 0 14px;font-size:11px;font-weight:bold;letter-spacing:1.5px;color:#5b57c9;">{escape(label)}</p>
<h1 style="margin:0 0 24px;font-size:28px;line-height:1.25;letter-spacing:-.7px;color:#252c43;font-weight:700;">{escape(subject)}</h1>
{paragraphs}{panel}
<p style="margin:26px 0 0;padding-top:22px;border-top:1px solid #e9ebf3;font-size:13px;color:#747d94;">Sent by {escape(sender)}</p>
</td></tr>
<tr><td align="center" style="padding:22px 14px;color:#8088a1;font-size:12px;line-height:1.7;">Skilledhat · Thoughtfully connected.{preference}</td></tr>
</table></td></tr></table></body></html>"""
