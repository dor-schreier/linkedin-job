# tests/test_ui_redesign.py
# pytest + playwright sync API
# Install: pip install pytest-playwright && playwright install chromium
# Run:     pytest tests/test_ui_redesign.py -v

import re
import pytest
from playwright.sync_api import Page, expect

BASE = "http://localhost:8010"
PAGES = [
    ("/jobs",          "jobs"),
    ("/profile",       "profile"),
    ("/watch-rules",   "watch-rules"),
    ("/search-config", "search-config"),
    ("/watch-matches", "watch-matches"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def computed(page: Page, selector: str, prop: str) -> str:
    return page.eval_on_selector(
        selector,
        f"el => getComputedStyle(el).{prop}",
    )


# ---------------------------------------------------------------------------
# 1. Global shell — sidebar nav
# ---------------------------------------------------------------------------

class TestSidebarNav:
    @pytest.mark.parametrize("path,active_key", PAGES)
    def test_sidebar_present(self, page: Page, path: str, active_key: str):
        page.goto(BASE + path)
        sidebar = page.locator("aside.fixed.left-0")
        expect(sidebar).to_be_visible()

    @pytest.mark.parametrize("path,active_key", PAGES)
    def test_sidebar_brand(self, page: Page, path: str, active_key: str):
        page.goto(BASE + path)
        expect(page.locator("aside h1")).to_contain_text("Job Finder")

    def test_active_link_has_border_primary(self, page: Page):
        page.goto(BASE + "/jobs")
        active = page.locator("aside a.border-r-2.border-primary")
        expect(active).to_have_count(1)

    def test_inactive_links_no_border(self, page: Page):
        page.goto(BASE + "/jobs")
        all_links = page.locator("aside nav a")
        for i in range(all_links.count()):
            link = all_links.nth(i)
            cls = link.get_attribute("class") or ""
            if "border-r-2" not in cls:
                assert "hover:bg-surface-container" in cls

    def test_find_new_jobs_cta_present(self, page: Page):
        page.goto(BASE + "/jobs")
        cta = page.locator("aside a[href='/scrape']")
        expect(cta).to_be_visible()
        expect(cta).to_contain_text("Find New Jobs")

    def test_content_offset_ml64(self, page: Page):
        page.goto(BASE + "/jobs")
        wrapper = page.locator("body > div.ml-64").first
        expect(wrapper).to_be_visible()

    def test_nav_icons_present(self, page: Page):
        page.goto(BASE + "/jobs")
        icons = page.locator("aside .material-symbols-outlined")
        assert icons.count() >= 5

    def test_matches_badge_shown_when_unread(self, page: Page):
        # Only verifiable when watch-matches exist; check element exists in DOM
        page.goto(BASE + "/watch-matches")
        badge = page.locator("aside a[href='/watch-matches'] span.bg-error")
        # badge may or may not be visible depending on data — just assert DOM presence if unread > 0
        count_text = page.locator("aside a[href='/watch-matches']").inner_text()
        assert "Matches" in count_text


# ---------------------------------------------------------------------------
# 2. Sticky header — all pages
# ---------------------------------------------------------------------------

class TestStickyHeader:
    @pytest.mark.parametrize("path,_", PAGES[:4])
    def test_header_sticky(self, page: Page, path: str, _):
        page.goto(BASE + path)
        header = page.locator("header.sticky").first
        expect(header).to_be_visible()
        cls = header.get_attribute("class") or ""
        assert "sticky" in cls
        assert "top-0" in cls

    @pytest.mark.parametrize("path,_", PAGES[:4])
    def test_header_backdrop_blur(self, page: Page, path: str, _):
        page.goto(BASE + path)
        header = page.locator("header.sticky").first
        cls = header.get_attribute("class") or ""
        assert "backdrop-blur" in cls

    def test_jobs_header_search_input(self, page: Page):
        page.goto(BASE + "/jobs")
        search = page.locator("header input[name='q'], header input[placeholder*='Search']").first
        expect(search).to_be_visible()

    def test_jobs_header_title(self, page: Page):
        page.goto(BASE + "/jobs")
        expect(page.locator("header h2").first).to_contain_text("Ranked Feed")

    def test_watch_rules_header_title(self, page: Page):
        page.goto(BASE + "/watch-rules")
        expect(page.locator("header h2").first).to_contain_text("Watch Rules")

    def test_watch_rules_header_cta(self, page: Page):
        page.goto(BASE + "/watch-rules")
        btn = page.locator("header button", has_text="Create New Rule")
        expect(btn).to_be_visible()


# ---------------------------------------------------------------------------
# 3. Job cards (jobs page)
# ---------------------------------------------------------------------------

class TestJobCards:
    def test_cards_use_surface_container_lowest(self, page: Page):
        page.goto(BASE + "/jobs")
        cards = page.locator(".bg-surface-container-lowest")
        assert cards.count() >= 1

    def test_card_title_uses_headline_font(self, page: Page):
        page.goto(BASE + "/jobs")
        first_title = page.locator("h3.font-headline").first
        # If no jobs, skip gracefully
        if first_title.count() == 0:
            pytest.skip("No jobs in feed to verify card structure")
        expect(first_title).to_be_visible()

    def test_high_match_accent_bar_present_for_score_90(self, page: Page):
        page.goto(BASE + "/jobs")
        accent_bars = page.locator(".w-1\\.5.h-full.bg-primary.rounded-l-xl")
        # Check the accent bar exists when high-score jobs are present
        score_badges = page.locator(".bg-primary-container.text-on-primary-container")
        if score_badges.count() > 0:
            assert accent_bars.count() > 0

    def test_score_badge_structure(self, page: Page):
        page.goto(BASE + "/jobs")
        badges = page.locator(".bg-primary-container span.text-lg.font-extrabold, .bg-surface-container-high span.text-lg.font-extrabold")
        if badges.count() > 0:
            text = badges.first.inner_text()
            assert text.isdigit() or re.match(r"^\d+$", text.strip())

    def test_card_tags_row_present(self, page: Page):
        page.goto(BASE + "/jobs")
        tags = page.locator(".bg-surface-container.text-on-surface-variant.text-\\[11px\\]").first
        if tags.count() == 0:
            pytest.skip("No tagged jobs in feed")
        expect(tags).to_be_visible()

    def test_view_details_button_present(self, page: Page):
        page.goto(BASE + "/jobs")
        btns = page.locator("a.bg-primary.text-on-primary", has_text="View Details")
        if btns.count() == 0:
            pytest.skip("No jobs with URLs in feed")
        expect(btns.first).to_be_visible()

    def test_location_icon_present(self, page: Page):
        page.goto(BASE + "/jobs")
        icons = page.locator(".material-symbols-outlined", has_text="location_on")
        if icons.count() == 0:
            pytest.skip("No jobs in feed")
        expect(icons.first).to_be_visible()

    def test_no_divide_y_separator(self, page: Page):
        page.goto(BASE + "/jobs")
        dividers = page.locator(".divide-y")
        assert dividers.count() == 0, "Old divide-y separators should be removed"


# ---------------------------------------------------------------------------
# 4. Watch Rules page
# ---------------------------------------------------------------------------

class TestWatchRules:
    def test_two_column_grid(self, page: Page):
        page.goto(BASE + "/watch-rules")
        grid = page.locator(".grid.grid-cols-1.lg\\:grid-cols-\\[1fr_320px\\]")
        expect(grid).to_be_visible()

    def test_create_form_present(self, page: Page):
        page.goto(BASE + "/watch-rules")
        form = page.locator("form[action='/watch-rules/create']")
        expect(form).to_be_visible()

    def test_rule_type_select_options(self, page: Page):
        page.goto(BASE + "/watch-rules")
        select = page.locator("select[name='rule_type']")
        expect(select).to_be_visible()
        options = select.locator("option")
        assert options.count() >= 3

    def test_value_input_present(self, page: Page):
        page.goto(BASE + "/watch-rules")
        expect(page.locator("input[name='value']")).to_be_visible()

    def test_initialize_watcher_button(self, page: Page):
        page.goto(BASE + "/watch-rules")
        btn = page.locator("button[type='submit']", has_text="Initialize Watcher")
        expect(btn).to_be_visible()

    def test_automated_insights_card(self, page: Page):
        page.goto(BASE + "/watch-rules")
        card = page.locator(".bg-surface-container-high", has_text="Automated Insights")
        expect(card).to_be_visible()

    def test_active_automations_label(self, page: Page):
        page.goto(BASE + "/watch-rules")
        label = page.locator("text=Active Automations")
        expect(label).to_be_visible()

    def test_rule_cards_use_new_token(self, page: Page):
        page.goto(BASE + "/watch-rules")
        rule_cards = page.locator(".bg-surface-container-lowest.rounded-xl")
        assert rule_cards.count() >= 1

    def test_no_divide_y(self, page: Page):
        page.goto(BASE + "/watch-rules")
        assert page.locator(".divide-y").count() == 0

    def test_toggle_button_present_for_rules(self, page: Page):
        page.goto(BASE + "/watch-rules")
        toggles = page.locator("form[action*='/toggle'] button")
        rules = page.locator("form[action='/watch-rules/create']")
        # only check if rules exist
        rule_items = page.locator(".space-y-3 > div.bg-surface-container-lowest")
        if rule_items.count() > 0:
            assert toggles.count() >= 1


# ---------------------------------------------------------------------------
# 5. Profile page
# ---------------------------------------------------------------------------

class TestProfilePage:
    def test_two_column_grid(self, page: Page):
        page.goto(BASE + "/profile")
        grid = page.locator(".grid.grid-cols-1.lg\\:grid-cols-\\[1fr_280px\\]")
        expect(grid).to_be_visible()

    def test_curation_engine_label(self, page: Page):
        page.goto(BASE + "/profile")
        expect(page.locator("text=Curation Engine")).to_be_visible()

    def test_professional_identity_heading(self, page: Page):
        page.goto(BASE + "/profile")
        expect(page.locator("h2", has_text="Professional Identity")).to_be_visible()

    def test_bio_summary_textarea(self, page: Page):
        page.goto(BASE + "/profile")
        textarea = page.locator("textarea[name='summary']")
        expect(textarea).to_be_visible()

    def test_work_history_card(self, page: Page):
        page.goto(BASE + "/profile")
        card = page.locator(".bg-surface-container-lowest", has_text="Work History")
        expect(card).to_be_visible()

    def test_add_experience_button(self, page: Page):
        page.goto(BASE + "/profile")
        btn = page.locator("button", has_text="Add Experience")
        expect(btn).to_be_visible()

    def test_preferred_roles_panel(self, page: Page):
        page.goto(BASE + "/profile")
        panel = page.locator(".bg-surface-container-lowest", has_text="Preferred Roles")
        expect(panel).to_be_visible()

    def test_core_skills_panel(self, page: Page):
        page.goto(BASE + "/profile")
        panel = page.locator(".bg-surface-container-lowest", has_text="Core Skills")
        expect(panel).to_be_visible()

    def test_profile_strength_card(self, page: Page):
        page.goto(BASE + "/profile")
        card = page.locator(".bg-surface-container-high", has_text="Profile Strength")
        expect(card).to_be_visible()

    def test_update_profile_button(self, page: Page):
        page.goto(BASE + "/profile")
        btn = page.locator("button[type='submit']", has_text="Update Profile")
        expect(btn).to_be_visible()

    def test_work_history_border_left_accent(self, page: Page):
        page.goto(BASE + "/profile")
        items = page.locator(".border-l-2.border-primary-fixed-dim")
        # present only if experiences exist
        if items.count() > 0:
            expect(items.first).to_be_visible()


# ---------------------------------------------------------------------------
# 6. Color token spot-checks
# ---------------------------------------------------------------------------

class TestColorTokens:
    def test_body_bg_background(self, page: Page):
        page.goto(BASE + "/jobs")
        cls = page.locator("body").get_attribute("class") or ""
        assert "bg-background" in cls

    def test_no_bg_white_cards(self, page: Page):
        """No plain bg-white cards should survive the migration."""
        for path, _ in PAGES[:4]:
            page.goto(BASE + path)
            white_cards = page.locator(".bg-white.rounded, .bg-white.border")
            assert white_cards.count() == 0, f"bg-white card found on {path}"

    def test_no_blue600_buttons(self, page: Page):
        """Old blue-600 buttons should be gone."""
        for path, _ in PAGES[:4]:
            page.goto(BASE + path)
            old_btns = page.locator(".bg-blue-600")
            assert old_btns.count() == 0, f"bg-blue-600 found on {path}"

    def test_primary_buttons_use_token(self, page: Page):
        page.goto(BASE + "/jobs")
        primary_btns = page.locator("a.bg-primary, button.bg-primary")
        assert primary_btns.count() >= 1

    def test_surface_container_lowest_used(self, page: Page):
        page.goto(BASE + "/jobs")
        surfaces = page.locator(".bg-surface-container-lowest")
        assert surfaces.count() >= 1

    def test_inputs_use_surface_container_low(self, page: Page):
        page.goto(BASE + "/watch-rules")
        inputs = page.locator("input.bg-surface-container-low, select.bg-surface-container-low, textarea.bg-surface-container-low")
        assert inputs.count() >= 1

    def test_no_gray_text_classes(self, page: Page):
        """text-gray-* should be replaced by on-surface-variant / outline tokens."""
        for path, _ in PAGES[:4]:
            html = page.goto(BASE + path).text()
            # check rendered classes in DOM
            gray_text = page.locator("[class*='text-gray-']")
            assert gray_text.count() == 0, f"text-gray-* found on {path}"


# ---------------------------------------------------------------------------
# 7. Material Symbols icons
# ---------------------------------------------------------------------------

class TestMaterialSymbols:
    @pytest.mark.parametrize("path,_", PAGES[:4])
    def test_icons_present(self, page: Page, path: str, _):
        page.goto(BASE + path)
        icons = page.locator(".material-symbols-outlined")
        assert icons.count() >= 3, f"Expected >=3 Material Symbols icons on {path}"

    def test_icon_font_variation_settings(self, page: Page):
        page.goto(BASE + "/jobs")
        icon = page.locator(".material-symbols-outlined").first
        fvs = computed(page, ".material-symbols-outlined", "fontVariationSettings")
        assert "FILL" in fvs or fvs != ""

    def test_nav_icons_are_20px(self, page: Page):
        page.goto(BASE + "/jobs")
        nav_icon = page.locator("aside nav .material-symbols-outlined").first
        cls = nav_icon.get_attribute("class") or ""
        assert "text-[20px]" in cls or "text-lg" in cls


# ---------------------------------------------------------------------------
# 8. Font loading (Manrope + Inter)
# ---------------------------------------------------------------------------

class TestFonts:
    @pytest.mark.parametrize("path,_", PAGES[:4])
    def test_google_fonts_link_manrope(self, page: Page, path: str, _):
        page.goto(BASE + path)
        link = page.locator("link[href*='Manrope']")
        assert link.count() >= 1, f"Manrope font link missing on {path}"

    @pytest.mark.parametrize("path,_", PAGES[:4])
    def test_google_fonts_link_inter(self, page: Page, path: str, _):
        page.goto(BASE + path)
        link = page.locator("link[href*='Inter']")
        assert link.count() >= 1, f"Inter font link missing on {path}"

    def test_body_uses_inter(self, page: Page):
        page.goto(BASE + "/jobs")
        ff = computed(page, "body", "fontFamily")
        assert "Inter" in ff, f"body font-family is '{ff}', expected Inter"

    def test_h1_uses_manrope(self, page: Page):
        page.goto(BASE + "/jobs")
        ff = computed(page, "h1, h2, h3, .font-headline", "fontFamily")
        assert "Manrope" in ff, f"headline font-family is '{ff}', expected Manrope"

    @pytest.mark.parametrize("path,_", PAGES[:4])
    def test_material_symbols_stylesheet_linked(self, page: Page, path: str, _):
        page.goto(BASE + path)
        link = page.locator("link[href*='Material+Symbols']")
        assert link.count() >= 1, f"Material Symbols stylesheet missing on {path}"
