"""Real-browser V1 acceptance tests; requires the API and built frontend to be running."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import sys
import time
import urllib.error
import urllib.request

from playwright.sync_api import expect, sync_playwright

FRONTEND_URL = os.getenv("E2E_FRONTEND_URL", "http://127.0.0.1:5173")
API_URL = os.getenv("E2E_API_URL", "http://127.0.0.1:8000")
ADMIN_EMAIL = "v1-e2e-admin@example.test"
STAFF_EMAIL = "v1-e2e-staff@example.test"
ADMIN_PASSWORD = os.getenv("E2E_ADMIN_PASSWORD", "")
STAFF_PASSWORD = os.getenv("E2E_STAFF_PASSWORD", "")
MEMBER_PASSWORD = "MemberStartPassphrase!2026"


def wait_for(url: str) -> None:
    for _ in range(60):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    raise RuntimeError(f"Service did not become ready: {url}")


def login_token(request, email: str, password: str) -> str:
    response = request.post(f"{API_URL}/api/auth/login", data={"email": email, "password": password})
    assert response.status == 200, f"Login failed for seeded E2E identity: {response.status} {response.text()}"
    return response.json()["access_token"]


def member_registration_and_dashboard(browser, api_request) -> None:
    page = browser.new_page()
    email = f"e2e-member-{time.time_ns()}@example.test"
    page.goto(FRONTEND_URL, wait_until="networkidle")
    expect(page.get_by_role("heading", name="Welcome back.")).to_be_visible()
    page.get_by_role("button", name="Create account").click()
    page.get_by_label("Full name").fill("E2E Member")
    page.get_by_label("Email address").fill(email)
    page.locator('input[type="password"]').fill(MEMBER_PASSWORD)
    with page.expect_response(lambda r: r.url.endswith("/api/auth/register") and r.request.method == "POST") as registration_response:
        page.get_by_role("button", name="Create Account").click()
    registered = registration_response.value
    assert registered.status == 201, f"Registration failed: {registered.status} {registered.text()}"
    member_id = registered.json()["id"]

    admin_token = login_token(api_request, ADMIN_EMAIL, ADMIN_PASSWORD)
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    membership_response = api_request.post(
        f"{API_URL}/api/memberships",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={
            "user_id": member_id, "tier": "performance", "status": "active",
            "start_date": (today - timedelta(days=1)).isoformat(), "expiry_date": (today + timedelta(days=365)).isoformat(),
        },
    )
    assert membership_response.status == 201, f"Membership creation failed: {membership_response.status} {membership_response.text()}"

    class_start = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=10)
    class_start = class_start.replace(minute=0, second=0, microsecond=0)
    class_payload = {
        "title": "E2E V2 Mobility Flow",
        "description": "An acceptance-test session for class booking and cancellation.",
        "instructor_name": "Avery Trainer",
        "class_type": "Mobility",
        "location_name": "E2E Acceptance Club",
        "starts_at": class_start.isoformat(),
        "ends_at": (class_start + timedelta(minutes=50)).isoformat(),
        "capacity": 2,
        "waitlist_limit": 3,
        "cancellation_cutoff_minutes": 120,
    }
    class_response = api_request.post(
        f"{API_URL}/api/classes",
        headers={"Authorization": f"Bearer {admin_token}"},
        data=class_payload,
    )
    assert class_response.status == 201, f"V2 class setup failed: {class_response.status} {class_response.text()}"

    page.get_by_label("Email address").fill(email)
    page.locator('input[type="password"]').fill(MEMBER_PASSWORD)
    page.get_by_role("button", name="Sign In").click()
    expect(page.get_by_text("ACTIVE MEMBERSHIP")).to_be_visible(timeout=15000)
    expect(page.get_by_role("heading", name="Performance")).to_be_visible()

    with page.expect_response(lambda r: r.url.endswith("/api/check-ins/qr-token") and r.request.method == "POST") as pass_response:
        page.get_by_role("button", name="Generate Digital Pass").click()
    pass_result = pass_response.value
    assert pass_result.status == 200, f"QR pass not issued: {pass_result.status} {pass_result.text()}"
    qr_token = pass_result.json()["qr_token"]
    expect(page.locator(".qr-live svg")).to_be_visible()

    page.get_by_label("Full name").fill("Journey Member Updated")
    page.get_by_role("button", name="Save profile").click()
    expect(page.get_by_role("heading", name="Good to see you, Journey.")).to_be_visible()

    page.locator('input[type="checkbox"]').first.check()
    page.get_by_role("button", name="Save privacy preferences").click()
    expect(page.get_by_text("Privacy preferences saved.")).to_be_visible()

    page.get_by_label("Request category").select_option("access")
    page.get_by_label("Subject").fill("E2E scanner acceptance issue")
    page.get_by_label("Details").fill("Acceptance test support ticket created through the member UI.")
    page.get_by_role("button", name="Submit support request").click()
    expect(page.get_by_text("E2E scanner acceptance issue")).to_be_visible()

    staff_token = login_token(api_request, STAFF_EMAIL, STAFF_PASSWORD)
    validation = api_request.post(
        f"{API_URL}/api/check-ins/validate",
        headers={"Authorization": f"Bearer {staff_token}"},
        data={"qr_token": qr_token, "location_name": "E2E Acceptance Club"},
    )
    assert validation.status == 201, f"Check-in validation failed: {validation.status} {validation.text()}"
    replay = api_request.post(
        f"{API_URL}/api/check-ins/validate",
        headers={"Authorization": f"Bearer {staff_token}"},
        data={"qr_token": qr_token, "location_name": "E2E Acceptance Club"},
    )
    assert replay.status == 409, f"Replay was not rejected: {replay.status} {replay.text()}"

    page.get_by_role("button", name="Refresh data").click()
    expect(page.get_by_text("E2E Acceptance Club", exact=True)).to_be_visible(timeout=10000)
    expect(page.get_by_text("Support request received")).to_be_visible()

    # Product V2: discover a class, book it, cancel it, freeze/resume the membership,
    # then request and approve a renewal without implying that payment was collected.
    expect(page.get_by_role("heading", name="Classes & bookings")).to_be_visible(timeout=10000)
    class_card = page.locator(".class-card").filter(has_text="E2E V2 Mobility Flow")
    expect(class_card).to_be_visible(timeout=10000)
    class_card.get_by_role("button", name="Book Spot").click()
    expect(page.get_by_text("Your class spot is confirmed.")).to_be_visible(timeout=10000)
    class_card.get_by_role("button", name="Cancel Booking").click()
    expect(page.get_by_text("Booking cancelled.")).to_be_visible(timeout=10000)

    page.get_by_role("button", name="Freeze for 7 days").click()
    expect(page.get_by_role("button", name="Resume Membership")).to_be_visible(timeout=10000)
    page.get_by_role("button", name="Resume Membership").click()
    expect(page.get_by_role("button", name="Request Renewal")).to_be_visible(timeout=10000)
    page.get_by_role("button", name="Request Renewal").click()
    expect(page.get_by_text("Renewal requests")).to_be_visible()
    member_token = login_token(api_request, email, MEMBER_PASSWORD)
    member_headers = {"Authorization": f"Bearer {member_token}"}
    renewal_requests = api_request.get(f"{API_URL}/api/memberships/renewals/me", headers=member_headers)
    assert renewal_requests.status == 200 and renewal_requests.json(), "V2 renewal request was not persisted"
    renewal_id = renewal_requests.json()[0]["id"]
    approval = api_request.patch(
        f"{API_URL}/api/memberships/renewals/{renewal_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"status": "approved"},
    )
    assert approval.status == 200 and approval.json()["status"] == "approved", f"Renewal approval failed: {approval.status} {approval.text()}"
    page.get_by_role("button", name="Refresh data").first.click()
    expect(page.get_by_text("approved", exact=True)).to_be_visible(timeout=10000)

    page.get_by_role("button", name="Mark all as read").click()
    expect(page.get_by_text("All notifications marked as read.")).to_be_visible()
    page.screenshot(path="v2-acceptance-dashboard.png", full_page=True)
    page.close()
    print("PASS: browser V1 identity/access plus V2 class discovery, booking/cancellation, freeze/resume, renewal approval, notifications, and dashboard history")


def password_recovery_flow(browser) -> None:
    page = browser.new_page()
    email = f"e2e-recovery-{time.time_ns()}@example.test"
    old_password = "RecoveryStartPassphrase!2026"
    new_password = "RecoveryChangedPassphrase!2026"
    page.goto(FRONTEND_URL, wait_until="networkidle")
    page.get_by_role("button", name="Create account").click()
    page.get_by_label("Full name").fill("Recovery Member")
    page.get_by_label("Email address").fill(email)
    page.locator('input[type="password"]').fill(old_password)
    page.get_by_role("button", name="Create Account").click()
    page.get_by_role("button", name="Recover account").click()
    page.get_by_label("Email address").fill(email)
    page.get_by_role("button", name="Send Reset Instructions").click()
    expect(page.get_by_label("Password reset token")).to_be_visible(timeout=10000)
    page.get_by_label("New password").fill(new_password)
    page.get_by_role("button", name="Reset Password").click()
    expect(page.get_by_role("heading", name="Welcome back.")).to_be_visible(timeout=10000)
    page.get_by_label("Email address").fill(email)
    page.locator('input[type="password"]').fill(new_password)
    page.get_by_role("button", name="Sign In").click()
    expect(page.get_by_role("heading", name="Membership access unavailable")).to_be_visible(timeout=15000)
    page.close()
    print("PASS: browser account recovery, one-use reset token, password change, and subsequent login")



def staff_class_scheduling_flow(browser) -> None:
    page = browser.new_page()
    page.goto(FRONTEND_URL, wait_until="networkidle")
    page.get_by_label("Email address").fill(STAFF_EMAIL)
    page.locator('input[type="password"]').fill(STAFF_PASSWORD)
    page.get_by_role("button", name="Sign In").click()
    expect(page.get_by_role("heading", name="Front-desk staff account")).to_be_visible(timeout=15000)
    page.get_by_text("Schedule a class").click()
    title = f"E2E Staff Schedule {time.time_ns()}"
    starts = datetime.now() + timedelta(days=12)
    starts = starts.replace(minute=0, second=0, microsecond=0)
    ends = starts + timedelta(minutes=50)
    page.get_by_label("Class name").fill(title)
    page.get_by_label("Instructor").fill("V2 E2E Instructor")
    page.get_by_label("Class type").select_option("Yoga")
    page.get_by_label("Club / studio").fill("E2E Staff Studio")
    page.get_by_label("Starts at").fill(starts.strftime("%Y-%m-%dT%H:%M"))
    page.get_by_label("Ends at").fill(ends.strftime("%Y-%m-%dT%H:%M"))
    page.get_by_label("Capacity").fill("12")
    page.get_by_label("Waitlist limit").fill("5")
    page.get_by_role("button", name="Publish class").click()
    expect(page.get_by_text(title, exact=True)).to_be_visible(timeout=10000)
    page.close()
    print("PASS: staff class creation from the browser UI")


def main() -> int:
    if not ADMIN_PASSWORD or not STAFF_PASSWORD:
        print("Set E2E_ADMIN_PASSWORD and E2E_STAFF_PASSWORD to test-only passwords.", file=sys.stderr)
        return 2
    wait_for(f"{API_URL}/api/health/ready")
    wait_for(FRONTEND_URL)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        api_request = playwright.request.new_context()
        try:
            member_registration_and_dashboard(browser, api_request)
            staff_class_scheduling_flow(browser)
            password_recovery_flow(browser)
        finally:
            api_request.dispose()
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
