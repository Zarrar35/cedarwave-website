#!/usr/bin/env python3
"""Fail-closed regressions for Cedarwave's public Roofmates claim boundary."""

from __future__ import annotations

import contextlib
import hashlib
import io
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_site


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
INDEPENDENT_REQUIRED_TRUTHS = (
    "Household membership alone does not expose every expense.",
    "does not hold or transfer roommate funds",
    "does not create or change a lease, tenancy, or ownership right",
)
INDEPENDENT_INDEX_TRUTHS = (
    "with explicit participant boundaries and no money movement.",
)
INDEPENDENT_PREVIEW_NAME = (
    "Illustrative Roofmates launch preview showing a shared expense, "
    "participant-scoped balance, and Home, Wallet, House, and You destinations"
)
INDEPENDENT_RETIRED_CLAIMS = (
    "Create Events for the house",
    "Start Pools together",
    "Use the household Chat",
    "Track Chores",
    "Manage Groceries",
    "Report Maintenance",
    "Open the Safety Center",
    "Run a fit check",
    "See a compatibility score",
    "Request introductions",
    "Identity verified",
    "Upload lease documents",
    "Use Finder",
    "Unlock Premium",
    "Roofmates moves money",
    "Roofmates changes tenancy",
    "Send messages",
    "Verify your identity",
    "Direct roommate payment",
    "92% match",
    "Identity verification",
    "Sign a lease",
    "Pay your roommate right in Roofmates",
    "Pay roommates in the app",
    "Send cash to your roommate via Roofmates.",
    "Transfer cash to your roommate via Roofmates.",
    "92 percent match",
    "Confirm who you are before joining",
    "Execute your rental contract",
)
INDEPENDENT_RETIRED_SCREENSHOT_SHA256 = "8752f835453bfff550d7374e6484829d15c26c322abe719de26965895237cdca"
INDEPENDENT_CONTRAST_PAIRS = {
    ".pill": ("#1c2721", "#e3eadb"),
    ".launch-preview__notice": ("#a83217", "#f6eddf"),
    ".button--product:hover": ("#fffaf2", "#a7381b"),
    ".button--wine:hover": ("#fffaf2", "#641f38"),
}


class PublicRoofmatesClaimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.site_root = (Path(self.temporary.name) / "site").resolve()
        shutil.copytree(
            REPOSITORY_ROOT,
            self.site_root,
            ignore=shutil.ignore_patterns(".git", "__pycache__"),
        )
        self.original_root = validate_site.ROOT
        validate_site.ROOT = self.site_root

    def tearDown(self) -> None:
        validate_site.ROOT = self.original_root
        self.temporary.cleanup()

    def run_validation(self) -> int:
        return self.run_validation_with_errors()[0]

    def run_validation_with_errors(self) -> tuple[int, list[str]]:
        validation = validate_site.Validation()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = validation.run()
        return result, validation.errors

    def mutate_public_page(self, page_name: str, markup: str) -> None:
        page = self.site_root / page_name
        source = page.read_text(encoding="utf-8")
        page.write_text(source.replace("</main>", f"{markup}</main>"), encoding="utf-8")

    def test_current_launch_copy_passes(self) -> None:
        self.assertEqual(tuple(validate_site.REQUIRED_ROOFMATES_TRUTHS), INDEPENDENT_REQUIRED_TRUTHS)
        self.assertEqual(tuple(validate_site.REQUIRED_INDEX_TRUTHS), INDEPENDENT_INDEX_TRUTHS)
        self.assertEqual(validate_site.EXPECTED_PREVIEW_ACCESSIBLE_NAME, INDEPENDENT_PREVIEW_NAME)
        self.assertEqual(validate_site.RETIRED_SCREENSHOT_SHA256, INDEPENDENT_RETIRED_SCREENSHOT_SHA256)
        self.assertEqual(self.run_validation(), 0)

    def test_every_retired_feature_claim_fails_closed_on_both_launch_pages(self) -> None:
        baselines = {
            name: (self.site_root / name).read_text(encoding="utf-8")
            for name in ("index.html", "roofmates.html")
        }
        for page_name in baselines:
            for claim in INDEPENDENT_RETIRED_CLAIMS:
                with self.subTest(page=page_name, claim=claim):
                    for name, source in baselines.items():
                        (self.site_root / name).write_text(source, encoding="utf-8")
                    self.mutate_public_page(page_name, f"<p>{claim}</p>")
                    self.assertEqual(self.run_validation(), 1)

    def test_semantic_claim_scan_decodes_entities_and_reads_metadata(self) -> None:
        roofmates = self.site_root / "roofmates.html"
        baseline = roofmates.read_text(encoding="utf-8")
        self.mutate_public_page("roofmates.html", "<p>Create Ev&#101;nts together</p>")
        self.assertEqual(self.run_validation(), 1)

        roofmates.write_text(
            baseline.replace("</head>", '<meta property="x-product-claim" content="Roofmates moves money"></head>'),
            encoding="utf-8",
        )
        self.assertEqual(self.run_validation(), 1)

    def test_required_boundaries_must_be_rendered_not_commented_out(self) -> None:
        page = self.site_root / "roofmates.html"
        baseline = page.read_text(encoding="utf-8")
        for truth in INDEPENDENT_REQUIRED_TRUTHS:
            with self.subTest(truth=truth):
                self.assertIn(truth, baseline)
                page.write_text(baseline.replace(truth, f"<!-- {truth} -->"), encoding="utf-8")
                self.assertEqual(self.run_validation(), 1)

    def test_required_boundaries_do_not_count_when_hidden(self) -> None:
        page = self.site_root / "roofmates.html"
        baseline = page.read_text(encoding="utf-8")
        for truth in INDEPENDENT_REQUIRED_TRUTHS:
            with self.subTest(truth=truth):
                page.write_text(
                    baseline.replace(truth, f'<span hidden>{truth}</span>'),
                    encoding="utf-8",
                )
                self.assertEqual(self.run_validation(), 1)

    def test_required_boundaries_do_not_count_when_hidden_by_stylesheet(self) -> None:
        stylesheet = self.site_root / "styles.css"
        baseline_styles = stylesheet.read_text(encoding="utf-8")
        mutations = (
            ("roofmates.html", *INDEPENDENT_REQUIRED_TRUTHS),
            ("index.html", *INDEPENDENT_INDEX_TRUTHS),
        )
        hiding_rules = (
            "display: none !important;",
            "opacity: 0 !important;",
            "opacity: 0% !important;",
            "opacity: calc(0) !important;",
            "position: absolute; width: 1px; height: 1px; overflow: hidden; "
            "clip: rect(0, 0, 0, 0) !important;",
            "position: absolute; width: 1px; height: 1px; overflow: hidden; "
            "clip-path: inset(50%) !important;",
        )
        for page_name, *truths in mutations:
            page = self.site_root / page_name
            baseline_page = page.read_text(encoding="utf-8")
            for truth in truths:
                for hiding_rule in hiding_rules:
                    with self.subTest(page=page_name, truth=truth, hiding_rule=hiding_rule):
                        page.write_text(
                            baseline_page.replace(truth, f'<span class="review-cloak">{truth}</span>'),
                            encoding="utf-8",
                        )
                        stylesheet.write_text(
                            baseline_styles + f"\nhtml body .review-cloak {{ {hiding_rule} }}\n",
                            encoding="utf-8",
                        )
                        self.assertEqual(self.run_validation(), 1)
                        page.write_text(baseline_page, encoding="utf-8")
                        stylesheet.write_text(baseline_styles, encoding="utf-8")

    def test_homepage_boundary_does_not_count_when_visually_clipped_inline(self) -> None:
        page = self.site_root / "index.html"
        baseline = page.read_text(encoding="utf-8")
        truth = INDEPENDENT_INDEX_TRUTHS[0]
        hiding_styles = (
            "opacity: 0",
            "opacity: 0%",
            "opacity: calc(0)",
            "position: absolute; width: 1px; height: 1px; overflow: hidden; "
            "clip: rect(0, 0, 0, 0)",
            "position: absolute; width: 1px; height: 1px; overflow: hidden; "
            "clip-path: inset(50%)",
        )
        for hiding_style in hiding_styles:
            with self.subTest(hiding_style=hiding_style):
                page.write_text(
                    baseline.replace(truth, f'<span style="{hiding_style}">{truth}</span>'),
                    encoding="utf-8",
                )
                self.assertEqual(self.run_validation(), 1)
                page.write_text(baseline, encoding="utf-8")

    def test_hidden_aria_labelledby_claim_is_scanned_as_accessible_content(self) -> None:
        page = self.site_root / "roofmates.html"
        source = page.read_text(encoding="utf-8")
        source = source.replace(
            f'aria-label="{INDEPENDENT_PREVIEW_NAME}"',
            'aria-labelledby="unsafe-preview-label"',
            1,
        )
        source = source.replace(
            "</main>",
            '<span id="unsafe-preview-label" hidden>Direct roommate payment</span></main>',
        )
        page.write_text(source, encoding="utf-8")
        result, errors = self.run_validation_with_errors()
        self.assertEqual(result, 1)
        self.assertTrue(
            any("unsupported Roofmates claim found: direct roommate payment" in error for error in errors),
            errors,
        )

    def test_required_money_privacy_and_tenancy_boundaries_fail_closed(self) -> None:
        page = self.site_root / "roofmates.html"
        baseline = page.read_text(encoding="utf-8")
        for truth in INDEPENDENT_REQUIRED_TRUTHS:
            with self.subTest(truth=truth):
                self.assertIn(truth, baseline)
                page.write_text(baseline.replace(truth, "boundary removed"), encoding="utf-8")
                self.assertEqual(self.run_validation(), 1)

    def test_homepage_money_boundary_fails_closed(self) -> None:
        page = self.site_root / "index.html"
        baseline = page.read_text(encoding="utf-8")
        for truth in INDEPENDENT_INDEX_TRUTHS:
            with self.subTest(truth=truth):
                page.write_text(baseline.replace(truth, "with simpler household coordination."), encoding="utf-8")
                self.assertEqual(self.run_validation(), 1)

    def test_preview_role_name_and_viewport_are_exact_on_both_pages(self) -> None:
        for page_name in ("index.html", "roofmates.html"):
            page = self.site_root / page_name
            baseline = page.read_text(encoding="utf-8")
            mutations = (
                ('role="img"', 'role="presentation"'),
                (f'aria-label="{INDEPENDENT_PREVIEW_NAME}"', 'aria-label="Product preview"'),
                ('content="width=device-width, initial-scale=1"', 'content="width=1024"'),
            )
            for old, new in mutations:
                with self.subTest(page=page_name, old=old):
                    poisoned = baseline.replace(old, new, 1)
                    self.assertNotEqual(poisoned, baseline)
                    page.write_text(poisoned, encoding="utf-8")
                    self.assertEqual(self.run_validation(), 1)
                    page.write_text(baseline, encoding="utf-8")

    def test_retired_screenshot_cannot_return_through_html_or_css(self) -> None:
        retired_asset = self.site_root / "assets" / "roofmates-phone-ios.png"
        retired_asset.write_bytes(b"test-only-placeholder")
        self.mutate_public_page(
            "index.html",
            '<img src="assets/roofmates-phone-ios.png" alt="Roofmates product screenshot">',
        )
        self.assertEqual(self.run_validation(), 1)

    def test_retired_screenshot_digest_cannot_return_under_another_filename(self) -> None:
        payload = b"independent retired screenshot digest fixture"
        expected_digest = hashlib.sha256(payload).hexdigest()
        previous_digest = validate_site.RETIRED_SCREENSHOT_SHA256
        previous_size = validate_site.RETIRED_SCREENSHOT_SIZE
        renamed_asset = self.site_root / "assets" / "renamed-launch-art.bin"
        renamed_asset.write_bytes(payload)
        try:
            validate_site.RETIRED_SCREENSHOT_SHA256 = expected_digest
            validate_site.RETIRED_SCREENSHOT_SIZE = len(payload)
            self.assertEqual(self.run_validation(), 1)
        finally:
            validate_site.RETIRED_SCREENSHOT_SHA256 = previous_digest
            validate_site.RETIRED_SCREENSHOT_SIZE = previous_size

    def test_inline_send_beacon_tracking_fails_closed(self) -> None:
        self.mutate_public_page(
            "index.html",
            "<script>navigator.sendBeacon('/collect', JSON.stringify({event: 'view'}));</script>",
        )
        self.assertEqual(self.run_validation(), 1)

        index = self.site_root / "index.html"
        index.write_text(
            (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.mutate_public_page(
            "index.html",
            "<script>navigator.sendBeacon ('/collect', 'view');</script>",
        )
        self.assertEqual(self.run_validation(), 1)

        index.write_text(
            (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.mutate_public_page(
            "index.html",
            "<script>navigator.sendBeacon /* review gap */ ('/collect', 'view');</script>",
        )
        self.assertEqual(self.run_validation(), 1)

        index.write_text(
            (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.mutate_public_page(
            "index.html",
            "<script>navigator.sendBeacon // review gap\n('/collect', 'view');</script>",
        )
        self.assertEqual(self.run_validation(), 1)

        index.write_text(
            (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.mutate_public_page(
            "index.html",
            "<script>navigator['sendBeacon']('/collect', 'view');</script>",
        )
        self.assertEqual(self.run_validation(), 1)

        index.write_text(
            (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        site_script = self.site_root / "site.js"
        baseline_site_script = site_script.read_text(encoding="utf-8")
        site_script.write_text(
            baseline_site_script
            + "\nnavigator.sendBeacon('/collect', JSON.stringify({event: 'view'}));\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_validation(), 1)
        site_script.write_text(baseline_site_script, encoding="utf-8")

        index.write_text(
            (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        stylesheet = self.site_root / "styles.css"
        stylesheet.write_text(
            stylesheet.read_text(encoding="utf-8")
            + "\n.reintroduced-shot { background-image: url('assets/roofmates-phone-ios.png'); }\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_validation(), 1)

    def test_all_reviewed_normal_text_contrast_pairs_fail_closed(self) -> None:
        stylesheet = self.site_root / "styles.css"
        baseline = stylesheet.read_text(encoding="utf-8")
        for selector, (foreground, background) in INDEPENDENT_CONTRAST_PAIRS.items():
            with self.subTest(selector=selector):
                self.assertGreaterEqual(validate_site.contrast_ratio(foreground, background), 4.5)
                pattern = re.compile(
                    rf"({re.escape(selector)}\s*\{{[^}}]*\bcolor:\s*){re.escape(foreground)}",
                    re.DOTALL,
                )
                poisoned, count = pattern.subn(rf"\g<1>{background}", baseline, count=1)
                self.assertEqual(count, 1)
                stylesheet.write_text(poisoned, encoding="utf-8")
                self.assertEqual(self.run_validation(), 1)
                stylesheet.write_text(baseline, encoding="utf-8")

    def test_duplicate_css_override_cannot_bypass_reviewed_contrast(self) -> None:
        stylesheet = self.site_root / "styles.css"
        baseline = stylesheet.read_text(encoding="utf-8")
        stylesheet.write_text(
            baseline + "\n.pill { color: #e3eadb !important; background: #e3eadb; }\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_validation(), 1)

    def test_higher_specificity_css_override_cannot_bypass_reviewed_contrast(self) -> None:
        stylesheet = self.site_root / "styles.css"
        baseline = stylesheet.read_text(encoding="utf-8")
        for selector, (_, background) in INDEPENDENT_CONTRAST_PAIRS.items():
            with self.subTest(selector=selector):
                poisoned_selector = f"html body main {selector}"
                stylesheet.write_text(
                    baseline
                    + f"\n{poisoned_selector} {{ color: {background} !important; "
                    + f"background: {background} !important; }}\n",
                    encoding="utf-8",
                )
                self.assertEqual(self.run_validation(), 1)
                stylesheet.write_text(baseline, encoding="utf-8")

    def test_important_attribute_selector_cannot_bypass_reviewed_contrast(self) -> None:
        stylesheet = self.site_root / "styles.css"
        baseline = stylesheet.read_text(encoding="utf-8")
        for selector, (_, background) in INDEPENDENT_CONTRAST_PAIRS.items():
            class_name, _, pseudo = selector.removeprefix(".").partition(":")
            for attribute in (
                f"[class~='{class_name}']",
                f"[class~={class_name}]",
                f"[class~='{class_name}' i]",
                f"[class~={class_name} i]",
            ):
                with self.subTest(selector=selector, attribute=attribute):
                    attribute_selector = f"html body {attribute}"
                    if pseudo:
                        attribute_selector += f":{pseudo}"
                    stylesheet.write_text(
                        baseline
                        + f"\n{attribute_selector} {{ color: {background} !important; "
                        + f"background: {background} !important; }}\n",
                        encoding="utf-8",
                    )
                    self.assertEqual(self.run_validation(), 1)
                    stylesheet.write_text(baseline, encoding="utf-8")

    def test_launch_status_heading_contrast_fails_closed(self) -> None:
        stylesheet = self.site_root / "styles.css"
        source = stylesheet.read_text(encoding="utf-8")
        poisoned = source.replace(
            ".launch-band h2 { margin: 9px 0 0; color: var(--ink);",
            ".launch-band h2 { margin: 9px 0 0; color: var(--paper);",
        )
        self.assertNotEqual(poisoned, source)
        stylesheet.write_text(poisoned, encoding="utf-8")
        self.assertEqual(self.run_validation(), 1)


if __name__ == "__main__":
    unittest.main()
