import smtplib

from app.services import email_service
from app.services import notification_service as ns
from app.services.notification_service import FightFacts

BASE = "https://fightlytics.example.com"


def _fight(**overrides):
    facts = dict(
        id=7, title="Juric vs Nogueira", purpose="ai_labeled", labeled_at_set=False,
        uploader_email="up@example.com",
    )
    return FightFacts(**{**facts, **overrides})


# --- queued: admins --------------------------------------------------------------

def test_queued_email_goes_to_each_admin_and_lists_the_whole_queue():
    emails = ns.queued_emails(["a@example.com", "b@example.com"], ["One", "Two"], BASE)
    assert [e.to for e in emails] == ["a@example.com", "b@example.com"]
    assert emails[0].subject == "Fightlytics: 2 videos waiting for processing"
    assert "  - One\n  - Two" in emails[0].body
    assert "deploy/worker.sh" in emails[0].body


def test_nothing_to_send_without_admins_or_a_queue():
    assert ns.queued_emails([], ["One"], BASE) == []
    assert ns.queued_emails(["a@example.com"], [], BASE) == []


def test_queued_is_silent_while_a_worker_is_online(monkeypatch):
    monkeypatch.setattr(ns, "_base_url", lambda: BASE)
    monkeypatch.setattr(ns, "_admin_emails", lambda: ["a@example.com"])
    monkeypatch.setattr(ns, "_queued_titles", lambda: ["One"])
    monkeypatch.setattr(ns, "_worker_online", lambda: True)
    assert ns._emails_for(1, "queued") == []
    monkeypatch.setattr(ns, "_worker_online", lambda: False)
    assert [e.to for e in ns._emails_for(1, "queued")] == ["a@example.com"]


def test_progress_states_send_nothing():
    assert ns._emails_for(1, "detecting") == []


# --- finished: the uploader ----------------------------------------------------------

def test_completed_ai_fight_links_to_the_player():
    [email] = ns.uploader_emails("completed", _fight(), BASE)
    assert email.to == "up@example.com"
    assert email.subject == "Fightlytics: Juric vs Nogueira is ready"
    assert f"{BASE}/fights/7\n" in email.body


def test_first_labelling_state_links_to_annotate():
    [email] = ns.uploader_emails("labeling_in_progress", _fight(purpose="training_data"), BASE)
    assert f"{BASE}/fights/7/annotate" in email.body


def test_reopened_labelling_sends_nothing():
    fight = _fight(purpose="training_data", labeled_at_set=True)
    assert ns.uploader_emails("labeling_in_progress", fight, BASE) == []


def test_failed_and_invalid_tell_the_uploader():
    [failed] = ns.uploader_emails("failed", _fight(), BASE)
    assert failed.subject == "Fightlytics: processing failed for Juric vs Nogueira"
    [invalid] = ns.uploader_emails("invalid", _fight(reported_frames=24712, decoded_frames=8147), BASE)
    assert "Only 8147 of its 24712 frames could be decoded." in invalid.body


def test_unknown_uploader_gets_nothing():
    assert ns.uploader_emails("completed", _fight(uploader_email=None), BASE) == []


def test_dev_accounts_are_never_emailed():
    assert ns._real_addresses(["dev-admin@fightai.local", "x@example.com", None]) == ["x@example.com"]


def test_title_prefers_fighter_names():
    assert ns._title("fight_videos/A_vs_B.mp4", "Ivan Juric", "Joao Nogueira") == "Ivan Juric vs Joao Nogueira"
    assert ns._title("fight_videos/A_vs_B.mp4", None, "Joao Nogueira") == "A_vs_B"


# --- sending --------------------------------------------------------------------

def test_send_is_off_without_smtp_host(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)

    def must_not_connect(*args, **kwargs):
        raise AssertionError("connected to SMTP while email is off")

    monkeypatch.setattr(smtplib, "SMTP", must_not_connect)
    email_service.send("x@example.com", "Subject", "Body")


def test_send_uses_starttls_and_logs_in(monkeypatch):
    seen = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            seen["server"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, context):
            seen["starttls"] = True

        def login(self, user, password):
            seen["login"] = (user, password)

        def send_message(self, msg):
            seen["msg"] = msg

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "bot@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.delenv("SMTP_SECURITY", raising=False)
    monkeypatch.delenv("MAIL_FROM", raising=False)

    email_service.send("x@example.com", "Hello", "Body")

    assert seen["server"] == ("smtp.example.com", 587)
    assert seen["starttls"] is True
    assert seen["login"] == ("bot@example.com", "app-password")
    assert seen["msg"]["From"] == "bot@example.com"
    assert seen["msg"]["To"] == "x@example.com"
    assert seen["msg"]["Subject"] == "Hello"
