"""
SendGrid email service for SYNAPSE notifications.

Provides two delivery methods:
  1. Django's built-in email backend (smtp / console / filebased)
     — works out of the box, uses EMAIL_BACKEND setting
  2. SendGrid Python SDK (direct API call)
     — used when SENDGRID_API_KEY is set and SENDGRID_USE_SDK=True

Phase 4.2 implementation.
Phase 2 (TASK-201): Weekly AI digest email.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


# ── Plain Django send_mail (SMTP / console) ───────────────────────────────────


def send_notification_email(
    to_email: str,
    subject: str,
    message: str,
    html_message: str | None = None,
) -> bool:
    """
    Send a transactional notification email using Django's email backend.

    In development (EMAIL_BACKEND = console), the email is printed to stdout.
    In production, set EMAIL_BACKEND = smtp and configure SendGrid SMTP credentials.

    Args:
        to_email:     Recipient email address
        subject:      Email subject line
        message:      Plain-text body
        html_message: Optional HTML body (falls back to plain text)

    Returns:
        True if sent successfully, False on error
    """
    try:
        from_email = settings.DEFAULT_FROM_EMAIL
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[to_email],
            html_message=html_message or _build_html(subject, message),
            fail_silently=False,
        )
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send email to {to_email}: {exc}")
        return False


def send_workflow_completion_email(
    user, workflow_name: str, run_status: str, run_id: str
) -> bool:
    """
    Send a workflow completion email notification.

    Args:
        user:          Django User instance
        workflow_name: Name of the completed workflow
        run_status:    'success' or 'failed'
        run_id:        UUID string of the WorkflowRun

    Returns:
        True if sent successfully
    """
    emoji = "✅" if run_status == "success" else "❌"
    status_label = "completed successfully" if run_status == "success" else "failed"

    subject = f"{emoji} Workflow '{workflow_name}' {status_label}"
    message = (
        f"Hi {user.first_name or user.email},\n\n"
        f"Your SYNAPSE workflow '{workflow_name}' has {status_label}.\n\n"
        f"Run ID: {run_id}\n"
        f"Status: {run_status.upper()}\n\n"
        f"Log in to SYNAPSE to view the full run history.\n\n"
        f"— The SYNAPSE Team"
    )
    html_message = _build_workflow_html(
        user=user,
        workflow_name=workflow_name,
        run_status=run_status,
        run_id=run_id,
        emoji=emoji,
        status_label=status_label,
    )
    return send_notification_email(user.email, subject, message, html_message)


def send_welcome_email(user) -> bool:
    """Send a welcome email to a newly registered user."""
    subject = "👋 Welcome to SYNAPSE!"
    message = (
        f"Hi {user.first_name or user.email},\n\n"
        f"Welcome to SYNAPSE — your AI-powered tech intelligence platform!\n\n"
        f"You can now:\n"
        f"  • Browse the tech feed\n"
        f"  • Explore arXiv research papers\n"
        f"  • Chat with the AI assistant\n"
        f"  • Set up automation workflows\n\n"
        f"Get started at https://synapse.ai\n\n"
        f"— The SYNAPSE Team"
    )
    return send_notification_email(user.email, subject, message)


# ── Weekly AI Digest (TASK-201) ───────────────────────────────────────────────


def send_weekly_digest_email(user, articles: list, papers: list, repos: list) -> bool:
    """
    Send the weekly AI digest email to a single user.

    Args:
        user:     Django User instance (must have digest_enabled=True)
        articles: List of Article instances (top trending this week)
        papers:   List of ResearchPaper instances (top this week)
        repos:    List of Repository instances (top this week)

    Returns:
        True if delivered successfully, False on error.
    """
    name = user.first_name or user.email.split("@")[0]
    subject = "⚡ Your Weekly SYNAPSE Digest"
    plain_lines = [
        f"Hi {name},",
        "",
        "Here's your weekly roundup of the top tech content from SYNAPSE.",
        "",
    ]

    if articles:
        plain_lines.append("── Top Articles ──")
        for a in articles[:5]:
            plain_lines.append(f"  • {a.title}")
        plain_lines.append("")

    if papers:
        plain_lines.append("── Research Papers ──")
        for p in papers[:5]:
            plain_lines.append(f"  • {p.title}")
        plain_lines.append("")

    if repos:
        plain_lines.append("── Trending Repositories ──")
        for r in repos[:5]:
            plain_lines.append(f"  • {r.name} — ⭐ {r.stars:,}")
        plain_lines.append("")

    plain_lines += [
        "View your full feed at https://synapse.ai/feed",
        "",
        "— The SYNAPSE Team",
        "",
        "You're receiving this because weekly digest is enabled on your account.",
        "Update preferences at https://synapse.ai/settings",
    ]

    plain_message = "\n".join(plain_lines)
    html_message = _build_digest_html(
        user=user, articles=articles, papers=papers, repos=repos
    )
    return send_notification_email(user.email, subject, plain_message, html_message)


# ── SendGrid SDK (optional, direct API) ──────────────────────────────────────


def send_via_sendgrid_sdk(
    to_email: str,
    subject: str,
    html_content: str,
    plain_content: str | None = None,
) -> bool:
    """
    Send email directly via the SendGrid Python SDK.

    Only used when:
      - sendgrid package is installed
      - SENDGRID_API_KEY is set in environment

    Falls back to Django's email backend on any error.

    Args:
        to_email:      Recipient email address
        subject:       Email subject line
        html_content:  HTML email body
        plain_content: Optional plain-text fallback

    Returns:
        True if sent successfully
    """
    api_key = getattr(settings, "SENDGRID_API_KEY", "")
    if not api_key:
        logger.warning(
            "SENDGRID_API_KEY not set — falling back to Django email backend"
        )
        return send_notification_email(
            to_email, subject, plain_content or strip_tags(html_content), html_content
        )

    try:
        import sendgrid
        from sendgrid.helpers.mail import Content, Email, Mail, To

        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        mail = Mail(
            from_email=Email(settings.DEFAULT_FROM_EMAIL),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_content),
        )
        if plain_content:
            mail.add_content(Content("text/plain", plain_content))

        response = sg.send(mail)
        success = 200 <= response.status_code < 300
        if success:
            logger.info(
                f"SendGrid SDK: email sent to {to_email} (status {response.status_code})"
            )
        else:
            logger.error(
                f"SendGrid SDK: failed for {to_email} (status {response.status_code})"
            )
        return success

    except ImportError:
        logger.warning(
            "sendgrid package not installed — falling back to Django email backend"
        )
        return send_notification_email(
            to_email, subject, plain_content or strip_tags(html_content), html_content
        )
    except Exception as exc:
        logger.error(f"SendGrid SDK error for {to_email}: {exc}")
        return False


# ── HTML templates (inline, no template files needed) ────────────────────────


def _build_digest_html(user, articles: list, papers: list, repos: list) -> str:
    """Build the weekly digest HTML email."""
    from django.conf import settings as _settings

    name = user.first_name or user.email.split("@")[0]
    frontend_url = getattr(_settings, "FRONTEND_URL", "https://synapse.ai")
    settings_url = f"{frontend_url}/settings"
    feed_url = f"{frontend_url}/feed"

    def _article_rows(items, limit=5):
        if not items:
            return '<p style="color:#64748b;font-size:14px;margin:0;">No articles this week.</p>'
        rows = []
        for item in items[:limit]:
            topic = getattr(item, "topic", "") or ""
            badge = (
                f'<span style="background:#6366f1;color:#fff;font-size:10px;'
                f'border-radius:4px;padding:2px 6px;margin-left:8px;">{topic.upper()}</span>'
                if topic
                else ""
            )
            summary = getattr(item, "summary", "") or ""
            short = summary[:120] + "…" if len(summary) > 120 else summary
            rows.append(
                f'<tr><td style="padding:12px 0;border-bottom:1px solid #1e293b;">'
                f'<p style="margin:0 0 4px;color:#e2e8f0;font-size:14px;font-weight:500;">'
                f"{item.title}{badge}</p>"
                f'<p style="margin:0;color:#64748b;font-size:12px;">{short}</p>'
                f"</td></tr>"
            )
        return f'<table width="100%" style="border-collapse:collapse;">{"".join(rows)}</table>'

    def _paper_rows(items, limit=5):
        if not items:
            return '<p style="color:#64748b;font-size:14px;margin:0;">No papers this week.</p>'
        rows = []
        for item in items[:limit]:
            authors = getattr(item, "authors", "") or ""
            short_authors = authors[:60] + "…" if len(authors) > 60 else authors
            rows.append(
                f'<tr><td style="padding:12px 0;border-bottom:1px solid #1e293b;">'
                f'<p style="margin:0 0 4px;color:#e2e8f0;font-size:14px;font-weight:500;">'
                f"{item.title}</p>"
                f'<p style="margin:0;color:#64748b;font-size:12px;">{short_authors}</p>'
                f"</td></tr>"
            )
        return f'<table width="100%" style="border-collapse:collapse;">{"".join(rows)}</table>'

    def _repo_rows(items, limit=5):
        if not items:
            return '<p style="color:#64748b;font-size:14px;margin:0;">No repositories this week.</p>'
        rows = []
        for item in items[:limit]:
            stars = getattr(item, "stars", 0) or 0
            language = getattr(item, "language", "") or ""
            lang_badge = (
                f'<span style="background:#0f172a;color:#94a3b8;font-size:10px;'
                f'border-radius:4px;padding:2px 6px;margin-left:8px;">{language}</span>'
                if language
                else ""
            )
            rows.append(
                f'<tr><td style="padding:12px 0;border-bottom:1px solid #1e293b;">'
                f'<p style="margin:0 0 4px;color:#e2e8f0;font-size:14px;font-weight:500;">'
                f"{item.name}{lang_badge}"
                f'<span style="color:#f59e0b;font-size:12px;margin-left:8px;">⭐ {stars:,}</span>'
                f"</p>"
                f'<p style="margin:0;color:#64748b;font-size:12px;">'
                f'{(getattr(item, "description", "") or "")[:100]}</p>'
                f"</td></tr>"
            )
        return f'<table width="100%" style="border-collapse:collapse;">{"".join(rows)}</table>'

    section_style = (
        "background:#1e293b;border-radius:10px;border:1px solid #334155;"
        "padding:20px 24px;margin-bottom:20px;"
    )
    section_title_style = (
        "margin:0 0 16px;color:#e2e8f0;font-size:15px;font-weight:600;"
        "border-bottom:1px solid #334155;padding-bottom:10px;"
    )

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Your Weekly SYNAPSE Digest</title>
</head>
<body style="margin:0;padding:0;background:#0f172a;font-family:Inter,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="620" cellpadding="0" cellspacing="0"
             style="max-width:620px;width:100%;">

        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#6366f1,#06b6d4);
                        border-radius:12px 12px 0 0;padding:28px 32px;">
          <h1 style="margin:0;color:#fff;font-size:24px;font-weight:700;">⚡ SYNAPSE</h1>
          <p style="margin:6px 0 0;color:rgba(255,255,255,0.8);font-size:14px;">
            Weekly AI Digest
          </p>
        </td></tr>

        <!-- Greeting -->
        <tr><td style="background:#141c2f;padding:24px 32px;">
          <p style="margin:0;color:#e2e8f0;font-size:16px;">
            Hi <strong>{name}</strong> 👋
          </p>
          <p style="margin:8px 0 0;color:#94a3b8;font-size:14px;line-height:1.6;">
            Here's your personalised weekly roundup of the top tech content curated by SYNAPSE.
          </p>
        </td></tr>

        <!-- Articles Section -->
        <tr><td style="background:#141c2f;padding:0 32px 20px;">
          <div style="{section_style}">
            <h2 style="{section_title_style}">📰 Top Articles</h2>
            {_article_rows(articles)}
          </div>
        </td></tr>

        <!-- Papers Section -->
        <tr><td style="background:#141c2f;padding:0 32px 20px;">
          <div style="{section_style}">
            <h2 style="{section_title_style}">🔬 Research Papers</h2>
            {_paper_rows(papers)}
          </div>
        </td></tr>

        <!-- Repos Section -->
        <tr><td style="background:#141c2f;padding:0 32px 20px;">
          <div style="{section_style}">
            <h2 style="{section_title_style}">💻 Trending Repositories</h2>
            {_repo_rows(repos)}
          </div>
        </td></tr>

        <!-- CTA -->
        <tr><td style="background:#141c2f;padding:0 32px 28px;text-align:center;">
          <a href="{feed_url}"
             style="display:inline-block;background:linear-gradient(135deg,#6366f1,#06b6d4);
                    color:#fff;text-decoration:none;padding:14px 32px;border-radius:10px;
                    font-size:14px;font-weight:600;letter-spacing:0.02em;">
            View Full Feed →
          </a>
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:#0f172a;border-radius:0 0 12px 12px;
                        padding:20px 32px;border-top:1px solid #1e293b;">
          <p style="margin:0;color:#475569;font-size:12px;line-height:1.6;">
            You received this email because weekly digest is enabled on your SYNAPSE account.<br>
            <a href="{settings_url}" style="color:#6366f1;text-decoration:none;">
              Manage digest preferences
            </a>
            &nbsp;·&nbsp; © 2026 SYNAPSE. All rights reserved.
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _build_html(subject: str, body: str) -> str:
    """Build a simple branded HTML email."""
    body_html = body.replace("\n", "<br>")
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:Inter,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#1e293b;border-radius:12px;overflow:hidden;border:1px solid #334155;">
        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#6366f1,#06b6d4);padding:24px 32px;">
          <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">⚡ SYNAPSE</h1>
          <p style="margin:4px 0 0;color:rgba(255,255,255,0.7);font-size:13px;">
            AI-Powered Tech Intelligence
          </p>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:32px;">
          <p style="color:#94a3b8;font-size:14px;line-height:1.7;margin:0;">
            {body_html}
          </p>
        </td></tr>
        <!-- Footer -->
        <tr><td style="padding:16px 32px;border-top:1px solid #334155;">
          <p style="margin:0;color:#475569;font-size:12px;">
            You received this email because you have a SYNAPSE account.<br>
            © 2026 SYNAPSE. All rights reserved.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _build_workflow_html(
    user,
    workflow_name: str,
    run_status: str,
    run_id: str,
    emoji: str,
    status_label: str,
) -> str:
    """Build a workflow completion HTML email."""
    color = "#22c55e" if run_status == "success" else "#ef4444"
    bg = "rgba(34,197,94,0.1)" if run_status == "success" else "rgba(239,68,68,0.1)"
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Workflow {status_label}</title></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:Inter,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#1e293b;border-radius:12px;overflow:hidden;border:1px solid #334155;">
        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#6366f1,#06b6d4);padding:24px 32px;">
          <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">⚡ SYNAPSE</h1>
          <p style="margin:4px 0 0;color:rgba(255,255,255,0.7);font-size:13px;">Automation Center</p>
        </td></tr>
        <!-- Status badge -->
        <tr><td style="padding:32px 32px 0;">
          <div style="background:{bg};border:1px solid {color};border-radius:8px;
                      padding:16px 20px;text-align:center;">
            <p style="margin:0;font-size:28px;">{emoji}</p>
            <p style="margin:8px 0 0;color:{color};font-size:16px;font-weight:600;">
              Workflow {status_label.title()}
            </p>
          </div>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:24px 32px;">
          <p style="color:#e2e8f0;font-size:15px;margin:0 0 16px;">
            Hi {user.first_name or user.email},
          </p>
          <p style="color:#94a3b8;font-size:14px;line-height:1.7;margin:0 0 20px;">
            Your workflow has finished executing. Here are the details:
          </p>
          <table width="100%" style="border-collapse:collapse;">
            <tr>
              <td style="color:#64748b;font-size:13px;padding:8px 0;border-bottom:1px solid #334155;
                         width:40%;">Workflow</td>
              <td style="color:#e2e8f0;font-size:13px;padding:8px 0;border-bottom:1px solid #334155;
                         font-weight:500;">{workflow_name}</td>
            </tr>
            <tr>
              <td style="color:#64748b;font-size:13px;padding:8px 0;border-bottom:1px solid #334155;">
                Status</td>
              <td style="color:{color};font-size:13px;padding:8px 0;border-bottom:1px solid #334155;
                         font-weight:600;">{run_status.upper()}</td>
            </tr>
            <tr>
              <td style="color:#64748b;font-size:13px;padding:8px 0;">Run ID</td>
              <td style="color:#94a3b8;font-size:12px;padding:8px 0;font-family:monospace;">
                {run_id}</td>
            </tr>
          </table>
        </td></tr>
        <!-- CTA -->
        <tr><td style="padding:0 32px 32px;">
          <a href="http://localhost:3000/automation"
             style="display:inline-block;background:linear-gradient(135deg,#6366f1,#06b6d4);
                    color:#fff;text-decoration:none;padding:12px 24px;border-radius:8px;
                    font-size:14px;font-weight:600;">
            View in Automation Center →
          </a>
        </td></tr>
        <!-- Footer -->
        <tr><td style="padding:16px 32px;border-top:1px solid #334155;">
          <p style="margin:0;color:#475569;font-size:12px;">
            © 2026 SYNAPSE. All rights reserved.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
