# Verifies that the SAVE10 discount code applies a 10% reduction to Standard
# seats only, leaves VIP seats at full price, and that the displayed total
# equals (2 × standard_price × 0.9) + vip_price.
#
# Seats chosen:
#   C1, C2  — Standard tier, $65 each  (Neon Skyline / Riverside Arena)
#   A1      — VIP tier,      $120
#
# Expected after SAVE10:
#   C1 → $58.50   C2 → $58.50   A1 → $120.00
#   Total → $237.00
#
# Run via the BrowserStack Python SDK (browserstack-sdk), which reads
# ../browserstack.yml for credentials, the app, and device details, and
# transparently redirects this local Appium session to BrowserStack. Do not
# set capabilities here — they live in browserstack.yml.

import re

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

NAV_WAIT_SECONDS = 20
PAYMENT_WAIT_SECONDS = 30

# Event with both Standard (rows C–E, $65) and VIP (rows A–B, $120) seats.
EVENT_TEST_ID = "event-card-evt-01"   # Neon Skyline

# Seats to book: 2 Standard + 1 VIP
STANDARD_SEAT_1 = "seat-C1"
STANDARD_SEAT_2 = "seat-C2"
VIP_SEAT        = "seat-A1"

DISCOUNT_CODE = "SAVE10"
DISCOUNT_RATE = 0.10

# Prices read from the seat map content-desc during exploration.
STANDARD_PRICE = 65.00
VIP_PRICE      = 120.00


def by_resource_id(resource_id):
    return (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{resource_id}")')


def parse_price(text: str) -> float:
    """Strip currency symbols / whitespace and return a float."""
    return float(re.sub(r"[^0-9.]", "", text))


def test_save10_discount_mixed_tier():
    options = UiAutomator2Options()
    driver = webdriver.Remote("http://localhost:4723/wd/hub", options=options)

    try:
        wait = WebDriverWait(driver, NAV_WAIT_SECONDS)

        # ── 1. Continue as Guest ──────────────────────────────────────────────
        wait.until(
            EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Continue as Guest"))
        ).click()

        # ── 2. Open Neon Skyline ──────────────────────────────────────────────
        wait.until(EC.presence_of_element_located(by_resource_id("event-list-screen")))
        wait.until(
            EC.presence_of_element_located(
                (
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiScrollable(new UiSelector().resourceId("event-list").scrollable(true))'
                    f'.scrollIntoView(new UiSelector().resourceId("{EVENT_TEST_ID}"))',
                )
            )
        ).click()

        # ── 3. Go to seat selection ───────────────────────────────────────────
        wait.until(EC.presence_of_element_located(by_resource_id("select-seat-button"))).click()
        wait.until(EC.presence_of_element_located(by_resource_id("seat-selection-screen")))

        # ── 4. Select 2 Standard seats and 1 VIP seat ────────────────────────
        # Read prices from the seat content-desc to keep the test data-driven.
        std_elem = wait.until(EC.presence_of_element_located(by_resource_id(STANDARD_SEAT_1)))
        std_desc = std_elem.get_attribute("content-desc") or ""
        # content-desc format: "Seat C1, standard, available, $65"
        std_price_match = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", std_desc)
        assert std_price_match, f"Could not parse Standard price from: {std_desc!r}"
        standard_price = float(std_price_match.group(1))

        vip_elem = wait.until(EC.presence_of_element_located(by_resource_id(VIP_SEAT)))
        vip_desc = vip_elem.get_attribute("content-desc") or ""
        vip_price_match = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", vip_desc)
        assert vip_price_match, f"Could not parse VIP price from: {vip_desc!r}"
        vip_price = float(vip_price_match.group(1))

        std_elem.click()
        wait.until(EC.presence_of_element_located(by_resource_id(STANDARD_SEAT_2))).click()
        vip_elem.click()

        wait.until(
            EC.presence_of_element_located(by_resource_id("seat-selection-continue-button"))
        ).click()

        # ── 5. Enter and apply SAVE10 ─────────────────────────────────────────
        wait.until(EC.presence_of_element_located(by_resource_id("discount-screen")))
        wait.until(EC.presence_of_element_located(by_resource_id("discount-input"))).send_keys(
            DISCOUNT_CODE
        )
        wait.until(
            EC.presence_of_element_located(by_resource_id("discount-apply-button"))
        ).click()

        # Confirm the code was accepted (Apply button replaced by Remove button).
        wait.until(EC.presence_of_element_located(by_resource_id("discount-applied-label")))

        wait.until(
            EC.presence_of_element_located(by_resource_id("discount-continue-button"))
        ).click()

        # ── 6. Assert payment breakdown ───────────────────────────────────────
        pay_wait = WebDriverWait(driver, PAYMENT_WAIT_SECONDS)
        pay_wait.until(EC.presence_of_element_located(by_resource_id("payment-screen")))

        # Read per-seat prices from the payment screen.
        actual_std1_text = pay_wait.until(
            EC.presence_of_element_located(by_resource_id("payment-line-price-C1"))
        ).text
        actual_std2_text = pay_wait.until(
            EC.presence_of_element_located(by_resource_id("payment-line-price-C2"))
        ).text
        actual_vip_text = pay_wait.until(
            EC.presence_of_element_located(by_resource_id("payment-line-price-A1"))
        ).text
        actual_total_text = pay_wait.until(
            EC.presence_of_element_located(by_resource_id("payment-total"))
        ).text

        actual_std1  = parse_price(actual_std1_text)
        actual_std2  = parse_price(actual_std2_text)
        actual_vip   = parse_price(actual_vip_text)
        actual_total = parse_price(actual_total_text)

        # Compute expected values from the prices read off the seat map.
        expected_std_discounted = round(standard_price * (1 - DISCOUNT_RATE), 2)
        expected_total          = round(2 * expected_std_discounted + vip_price, 2)

        # Standard seats must show a 10 % reduction.
        assert actual_std1 == expected_std_discounted, (
            f"Seat C1 (Standard): expected ${expected_std_discounted:.2f} "
            f"(${standard_price:.2f} × 0.9), got ${actual_std1:.2f}"
        )
        assert actual_std2 == expected_std_discounted, (
            f"Seat C2 (Standard): expected ${expected_std_discounted:.2f} "
            f"(${standard_price:.2f} × 0.9), got ${actual_std2:.2f}"
        )

        # VIP seat must remain at full price (no discount).
        assert actual_vip == vip_price, (
            f"Seat A1 (VIP): expected ${vip_price:.2f} (no discount), "
            f"got ${actual_vip:.2f}"
        )

        # Total must equal (2 × discounted Standard) + full VIP.
        assert actual_total == expected_total, (
            f"Total: expected ${expected_total:.2f} "
            f"(2 × ${expected_std_discounted:.2f} + ${vip_price:.2f}), "
            f"got ${actual_total:.2f}"
        )

        print(
            f"[test_save10_discount] PASS — "
            f"std×2=${actual_std1:.2f}+{actual_std2:.2f}, "
            f"vip=${actual_vip:.2f}, total=${actual_total:.2f}"
        )

    finally:
        driver.quit()
