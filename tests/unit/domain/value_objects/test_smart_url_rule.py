"""Тести для SmartURLRule та Rule type alias."""

import pytest
from graph_crawler.domain.value_objects.models import (
    URLRule,
    SmartURLRule,
    RuleScope,
    Rule,
    build_smart_rules,
)

class TestSmartURLRule:
    """Тести для SmartURLRule класу."""

    def test_creates_with_pattern_and_scope(self):
        """SmartURLRule створюється з pattern та scope."""
        rule = SmartURLRule(pattern=r"^/jobs/?", scope=RuleScope.PATH)
        assert rule.pattern == r"^/jobs/?"
        assert rule.scope == RuleScope.PATH

    def test_default_scope_is_full_url(self):
        """За замовчуванням scope = FULL_URL."""
        rule = SmartURLRule(pattern=r"example\.com")
        assert rule.scope == RuleScope.FULL_URL

    def test_default_is_regex_true(self):
        """За замовчуванням is_regex = True."""
        rule = SmartURLRule(pattern=r"^/jobs/?", scope=RuleScope.PATH)
        assert rule.is_regex is True

    def test_matches_path_scope(self):
        """SmartURLRule з scope=PATH матчить тільки path частину URL."""
        rule = SmartURLRule(pattern=r"^/jobs/?", scope=RuleScope.PATH)

        # Повинен матчити path
        assert rule.matches("https://careers.epam.com/jobs") is True
        assert rule.matches("https://careers.epam.com/jobs/dev") is True

        # НЕ повинен матчити subdomain
        assert rule.matches("https://jobs.epam.com/") is False

    def test_matches_subdomain_scope(self):
        """SmartURLRule з scope=SUBDOMAIN матчить subdomain."""
        rule = SmartURLRule(pattern=r"careers", scope=RuleScope.SUBDOMAIN)

        assert rule.matches("https://careers.epam.com/jobs") is True
        assert rule.matches("https://jobs.epam.com/") is False
        # Не матчить path
        assert rule.matches("https://epam.com/careers") is False

    def test_matches_domain_scope(self):
        """SmartURLRule з scope=DOMAIN матчить базовий домен."""
        rule = SmartURLRule(pattern=r"epam\.com", scope=RuleScope.DOMAIN)

        assert rule.matches("https://careers.epam.com/jobs") is True
        assert rule.matches("https://epam.com/about") is True
        assert rule.matches("https://google.com/") is False

    def test_matches_query_scope(self):
        """SmartURLRule з scope=QUERY матчить query параметри."""
        rule = SmartURLRule(pattern=r"utm_", scope=RuleScope.QUERY)

        assert rule.matches("https://example.com/?utm_source=google") is True
        assert rule.matches("https://example.com/?ref=123") is False

    def test_exact_match_with_is_regex_false(self):
        """При is_regex=False використовується точний матч."""
        rule = SmartURLRule(
            pattern="epam.com",
            scope=RuleScope.DOMAIN,
            is_regex=False
        )

        assert rule.matches("https://careers.epam.com/jobs") is True
        assert rule.matches("https://example.com/") is False

    def test_priority_default(self):
        """Пріоритет за замовчуванням = 5."""
        rule = SmartURLRule(pattern=r"test", scope=RuleScope.PATH)
        assert rule.priority == 5

    def test_priority_custom(self):
        """Можна задати кастомний пріоритет."""
        rule = SmartURLRule(pattern=r"test", scope=RuleScope.PATH, priority=8)
        assert rule.priority == 8

    def test_should_scan_default_none(self):
        """should_scan за замовчуванням = None."""
        rule = SmartURLRule(pattern=r"test", scope=RuleScope.PATH)
        assert rule.should_scan is None

    def test_should_scan_explicit(self):
        """Можна явно задати should_scan."""
        rule = SmartURLRule(pattern=r"test", scope=RuleScope.PATH, should_scan=True)
        assert rule.should_scan is True

    def test_to_url_rule_conversion(self):
        """SmartURLRule конвертується в URLRule."""
        smart_rule = SmartURLRule(
            pattern=r"^/jobs/?",
            scope=RuleScope.PATH,
            priority=8,
            should_scan=True,
            should_follow_links=False,
        )

        url_rule = smart_rule.to_url_rule()

        assert isinstance(url_rule, URLRule)
        assert url_rule.pattern == smart_rule.pattern
        assert url_rule.priority == smart_rule.priority
        assert url_rule.should_scan == smart_rule.should_scan
        assert url_rule.should_follow_links == smart_rule.should_follow_links

    def test_repr(self):
        """__repr__ показує scope та інші параметри."""
        rule = SmartURLRule(
            pattern=r"^/jobs/?",
            scope=RuleScope.PATH,
            priority=8,
            should_scan=True,
        )
        repr_str = repr(rule)

        assert "SmartURLRule" in repr_str
        assert "^/jobs/?" in repr_str
        assert "path" in repr_str
        assert "priority=8" in repr_str
        assert "should_scan=True" in repr_str

class TestRuleTypeAlias:
    """Тести для Rule = Union[URLRule, SmartURLRule]."""

    def test_rule_accepts_url_rule(self):
        """Rule приймає URLRule."""
        rule: Rule = URLRule(pattern=r"test")
        assert isinstance(rule, URLRule)

    def test_rule_accepts_smart_url_rule(self):
        """Rule приймає SmartURLRule."""
        rule: Rule = SmartURLRule(pattern=r"test", scope=RuleScope.PATH)
        assert isinstance(rule, SmartURLRule)

    def test_mixed_rules_list(self):
        """Можна створити список з обох типів."""
        rules: list[Rule] = [
            URLRule(pattern=r"block\.com", should_scan=False),
            SmartURLRule(pattern=r"^/jobs/?", scope=RuleScope.PATH, should_scan=True),
            SmartURLRule(pattern=r"careers", scope=RuleScope.SUBDOMAIN, priority=7),
            URLRule(pattern=r"epam\.com", priority=5),
        ]

        assert len(rules) == 4
        assert isinstance(rules[0], URLRule)
        assert isinstance(rules[1], SmartURLRule)

class TestBuildSmartRules:
    """Тести для build_smart_rules хелпера."""

    def test_creates_rules_for_domain(self):
        """Створює правила для базового домену."""
        rules = build_smart_rules("https://careers.epam.com/jobs")

        # Повинен бути хоча б один rule для domain
        domain_rules = [r for r in rules if r.scope == RuleScope.DOMAIN]
        assert len(domain_rules) >= 1

    def test_creates_rules_for_subdomain(self):
        """Створює правила для subdomain якщо є."""
        rules = build_smart_rules("https://careers.epam.com/jobs")

        subdomain_rules = [r for r in rules if r.scope == RuleScope.SUBDOMAIN]
        assert len(subdomain_rules) >= 1

    def test_adds_path_patterns(self):
        """Додає path patterns якщо передано."""
        rules = build_smart_rules(
            "https://careers.epam.com/jobs",
            path_patterns=[
                (r"^/jobs/?", 8),
                (r"^/careers/?", 7),
            ],
        )

        path_rules = [r for r in rules if r.scope == RuleScope.PATH]
        assert len(path_rules) == 2

    def test_adds_blocked_domains(self):
        """Додає blocked domains з priority=10."""
        rules = build_smart_rules(
            "https://careers.epam.com/jobs",
            blocked_domains=["facebook.com", "twitter.com"],
        )

        blocked_rules = [r for r in rules if r.should_scan is False]
        assert len(blocked_rules) == 2
        for rule in blocked_rules:
            assert rule.priority == 10

    def test_rules_sorted_by_priority(self):
        """Правила відсортовані за пріоритетом (вищий першим)."""
        rules = build_smart_rules(
            "https://careers.epam.com/jobs",
            path_patterns=[(r"^/jobs/?", 8)],
            blocked_domains=["facebook.com"],
        )

        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities, reverse=True)
