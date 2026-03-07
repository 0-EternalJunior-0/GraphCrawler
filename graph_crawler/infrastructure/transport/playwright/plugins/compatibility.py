"""
Система сумісності плагінів для Playwright драйвера.

Визначає:
- Які плагіни несумісні між собою
- Які плагіни замінюють інші
- Залежності між плагінами
- Автоматичне визначення конфліктів при реєстрації

Usage:
    from graph_crawler.infrastructure.transport.playwright.plugins.compatibility import (
        PluginCompatibilityChecker,
        check_plugin_compatibility,
    )

    # Перевірка сумісності
    checker = PluginCompatibilityChecker()
    issues = checker.check([plugin1, plugin2, plugin3])
    
    if issues.has_conflicts:
        print(issues.format_report())
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Type

logger = logging.getLogger(__name__)


class CompatibilityLevel(Enum):
    """Рівень сумісності між плагінами."""
    
    COMPATIBLE = "compatible"           # Повністю сумісні
    REDUNDANT = "redundant"             # Один замінює інший (попередження)
    PARTIAL_CONFLICT = "partial"        # Часткове перекриття функціоналу
    INCOMPATIBLE = "incompatible"       # Повна несумісність (помилка)


@dataclass
class CompatibilityIssue:
    """Опис проблеми сумісності."""
    
    plugin1: str
    plugin2: str
    level: CompatibilityLevel
    description: str
    recommendation: str


@dataclass
class CompatibilityReport:
    """Звіт про сумісність плагінів."""
    
    issues: List[CompatibilityIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def has_conflicts(self) -> bool:
        """Чи є серйозні конфлікти."""
        return any(
            issue.level == CompatibilityLevel.INCOMPATIBLE 
            for issue in self.issues
        )
    
    @property
    def has_warnings(self) -> bool:
        """Чи є попередження."""
        return len(self.warnings) > 0 or any(
            issue.level in (CompatibilityLevel.REDUNDANT, CompatibilityLevel.PARTIAL_CONFLICT)
            for issue in self.issues
        )
    
    def format_report(self) -> str:
        """Форматує звіт для виводу."""
        lines = ["=" * 60, "Plugin Compatibility Report", "=" * 60]
        
        if not self.issues and not self.warnings:
            lines.append("✅ All plugins are compatible!")
            return "\n".join(lines)
        
        # Помилки (несумісність)
        incompatible = [i for i in self.issues if i.level == CompatibilityLevel.INCOMPATIBLE]
        if incompatible:
            lines.append("\n❌ INCOMPATIBLE PLUGINS:")
            for issue in incompatible:
                lines.append(f"   • {issue.plugin1} ↔ {issue.plugin2}")
                lines.append(f"     Problem: {issue.description}")
                lines.append(f"     Solution: {issue.recommendation}")
        
        # Попередження (redundant/partial)
        warnings_issues = [i for i in self.issues if i.level != CompatibilityLevel.INCOMPATIBLE]
        if warnings_issues:
            lines.append("\n⚠️  WARNINGS:")
            for issue in warnings_issues:
                lines.append(f"   • {issue.plugin1} + {issue.plugin2}: {issue.description}")
                lines.append(f"     Recommendation: {issue.recommendation}")
        
        if self.warnings:
            lines.append("\n📝 NOTES:")
            for warning in self.warnings:
                lines.append(f"   • {warning}")
        
        lines.append("=" * 60)
        return "\n".join(lines)


# Матриця сумісності офіційних плагінів
COMPATIBILITY_MATRIX: Dict[str, Dict[str, tuple]] = {
    # (plugin1, plugin2): (CompatibilityLevel, description, recommendation)
    
    # StealthPlugin vs EnhancedStealthPlugin
    ("stealth", "enhanced_stealth"): (
        CompatibilityLevel.REDUNDANT,
        "EnhancedStealthPlugin включає весь функціонал StealthPlugin",
        "Використовуйте тільки EnhancedStealthPlugin"
    ),
    
    # HumanBehaviorPlugin vs EnhancedStealthPlugin з human_behavior=True
    ("human_behavior", "enhanced_stealth"): (
        CompatibilityLevel.PARTIAL_CONFLICT,
        "EnhancedStealthPlugin має вбудовану емуляцію людської поведінки",
        "Вимкніть human_behavior в EnhancedStealthPlugin або не використовуйте HumanBehaviorPlugin"
    ),
    
    # CloudflarePlugin vs EnhancedCloudflarePlugin
    ("cloudflare", "enhanced_cloudflare"): (
        CompatibilityLevel.REDUNDANT,
        "EnhancedCloudflarePlugin включає весь функціонал CloudflarePlugin",
        "Використовуйте тільки EnhancedCloudflarePlugin"
    ),
    
    # UserProfilePlugin vs ProfilePoolPlugin
    ("user_profile", "profile_pool"): (
        CompatibilityLevel.INCOMPATIBLE,
        "Обидва плагіни намагаються встановити user_data_dir",
        "Використовуйте тільки один з цих плагінів"
    ),
    
    # CaptchaDetectorPlugin + CaptchaSolverPlugin - OK, це зв'язка
    ("captcha_detector", "captcha_solver"): (
        CompatibilityLevel.COMPATIBLE,
        "CaptchaSolverPlugin потребує CaptchaDetectorPlugin",
        "Рекомендована комбінація"
    ),
}

# Плагіни які замінюють інші (для автоматичного вимкнення)
PLUGIN_SUPERSEDES: Dict[str, List[str]] = {
    "enhanced_stealth": ["stealth"],  # EnhancedStealthPlugin замінює StealthPlugin
    "enhanced_cloudflare": ["cloudflare"],  # EnhancedCloudflarePlugin замінює CloudflarePlugin
}

# Рекомендовані комбінації плагінів
RECOMMENDED_COMBINATIONS: List[tuple] = [
    # (назва, список плагінів, опис)
    (
        "Maximum Stealth",
        ["enhanced_stealth", "user_profile"],
        "Максимальний обхід anti-bot з профілем користувача"
    ),
    (
        "Cloudflare Bypass",
        ["enhanced_stealth", "enhanced_cloudflare"],
        "Для сайтів з Cloudflare захистом"
    ),
    (
        "Captcha Handling",
        ["enhanced_stealth", "captcha_detector", "captcha_solver"],
        "Автоматичне вирішення капчі"
    ),
    (
        "Scale Crawling",
        ["enhanced_stealth", "profile_pool"],
        "Для масштабного crawling з ротацією профілів"
    ),
]


class PluginCompatibilityChecker:
    """
    Перевіряє сумісність плагінів перед реєстрацією.
    
    Використання:
        checker = PluginCompatibilityChecker()
        report = checker.check(plugins)
        
        if report.has_conflicts:
            raise ValueError(report.format_report())
        elif report.has_warnings:
            logger.warning(report.format_report())
    """
    
    def __init__(
        self,
        compatibility_matrix: Dict = None,
        supersedes: Dict = None,
        strict_mode: bool = False
    ):
        """
        Args:
            compatibility_matrix: Кастомна матриця сумісності
            supersedes: Кастомний словник замін
            strict_mode: Якщо True, warnings теж вважаються помилками
        """
        self.matrix = compatibility_matrix or COMPATIBILITY_MATRIX
        self.supersedes = supersedes or PLUGIN_SUPERSEDES
        self.strict_mode = strict_mode
    
    def check(self, plugins: List) -> CompatibilityReport:
        """
        Перевіряє сумісність списку плагінів.
        
        Args:
            plugins: Список плагінів для перевірки
            
        Returns:
            CompatibilityReport з результатами
        """
        report = CompatibilityReport()
        
        # Отримуємо імена плагінів
        plugin_names = set()
        plugin_configs = {}
        
        for plugin in plugins:
            name = plugin.name if hasattr(plugin, 'name') else str(plugin)
            plugin_names.add(name)
            plugin_configs[name] = getattr(plugin, 'config', {})
        
        # Перевіряємо кожну пару плагінів
        checked_pairs: Set[tuple] = set()
        
        for name1 in plugin_names:
            for name2 in plugin_names:
                if name1 == name2:
                    continue
                
                # Уникаємо подвійної перевірки
                pair = tuple(sorted([name1, name2]))
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)
                
                # Шукаємо в матриці сумісності
                issue = self._check_pair(name1, name2, plugin_configs)
                if issue:
                    report.issues.append(issue)
        
        # Перевіряємо supersedes (плагіни які замінюють інші)
        for superior, inferior_list in self.supersedes.items():
            if superior in plugin_names:
                for inferior in inferior_list:
                    if inferior in plugin_names:
                        report.warnings.append(
                            f"'{superior}' замінює '{inferior}' - рекомендовано видалити '{inferior}'"
                        )
        
        # Перевіряємо специфічні конфігурації
        self._check_config_conflicts(plugin_names, plugin_configs, report)
        
        return report
    
    def _check_pair(
        self,
        name1: str,
        name2: str,
        configs: Dict
    ) -> Optional[CompatibilityIssue]:
        """Перевіряє пару плагінів на сумісність."""
        
        # Шукаємо в обох напрямках
        for pair in [(name1, name2), (name2, name1)]:
            if pair in self.matrix:
                level, description, recommendation = self.matrix[pair]
                return CompatibilityIssue(
                    plugin1=name1,
                    plugin2=name2,
                    level=level,
                    description=description,
                    recommendation=recommendation
                )
        
        return None
    
    def _check_config_conflicts(
        self,
        plugin_names: Set[str],
        configs: Dict,
        report: CompatibilityReport
    ):
        """Перевіряє конфлікти конфігурацій."""
        
        # Специфічна перевірка: human_behavior в обох плагінах
        if "human_behavior" in plugin_names and "enhanced_stealth" in plugin_names:
            es_config = configs.get("enhanced_stealth", {})
            if es_config.get("human_behavior", True):  # default True
                report.warnings.append(
                    "HumanBehaviorPlugin + EnhancedStealthPlugin(human_behavior=True) "
                    "можуть дублювати функціонал. "
                    "Рекомендація: EnhancedStealthPlugin.config(human_behavior=False)"
                )
    
    def get_recommended_combination(self, use_case: str) -> Optional[tuple]:
        """
        Повертає рекомендовану комбінацію плагінів для use case.
        
        Args:
            use_case: Назва use case (напр. 'Maximum Stealth')
            
        Returns:
            Tuple (назва, список плагінів, опис) або None
        """
        for combo in RECOMMENDED_COMBINATIONS:
            if combo[0].lower() == use_case.lower():
                return combo
        return None
    
    def list_recommended_combinations(self) -> List[tuple]:
        """Повертає всі рекомендовані комбінації."""
        return RECOMMENDED_COMBINATIONS.copy()


def check_plugin_compatibility(plugins: List, raise_on_conflict: bool = True) -> CompatibilityReport:
    """
    Швидка функція перевірки сумісності.
    
    Args:
        plugins: Список плагінів
        raise_on_conflict: Чи кидати помилку при конфліктах
        
    Returns:
        CompatibilityReport
        
    Raises:
        ValueError: Якщо є несумісні плагіни і raise_on_conflict=True
    """
    checker = PluginCompatibilityChecker()
    report = checker.check(plugins)
    
    if report.has_conflicts and raise_on_conflict:
        raise ValueError(f"Plugin compatibility issues:\n{report.format_report()}")
    
    if report.has_warnings:
        logger.warning(f"Plugin compatibility warnings:\n{report.format_report()}")
    
    return report


# Хелпери для вибору плагінів

def get_stealth_plugins(
    use_profile: bool = False,
    profile_path: str = None,
    use_cloudflare_bypass: bool = False,
    use_captcha_solver: bool = False,
    captcha_api_key: str = None,
) -> List:
    """
    Повертає рекомендований набір плагінів для stealth crawling.
    
    Args:
        use_profile: Чи використовувати профіль користувача
        profile_path: Шлях до профілю
        use_cloudflare_bypass: Чи потрібен обхід Cloudflare
        use_captcha_solver: Чи потрібне вирішення капчі
        captcha_api_key: API ключ для captcha сервісу
        
    Returns:
        Список плагінів
        
    Example:
        plugins = get_stealth_plugins(
            use_profile=True,
            profile_path="/home/user/.config/crawl-profile",
            use_cloudflare_bypass=True
        )
        driver = PlaywrightDriver(config, plugins=plugins)
    """
    # Імпортуємо тут щоб уникнути circular imports
    from graph_crawler.infrastructure.transport.playwright.plugins import (
        EnhancedStealthPlugin,
        EnhancedCloudflarePlugin,
        CaptchaDetectorPlugin,
        CaptchaSolverPlugin,
        UserProfilePlugin,
    )
    
    plugins = []
    
    # Базовий stealth - завжди
    plugins.append(EnhancedStealthPlugin(EnhancedStealthPlugin.config(
        stealth_level="maximum",
        human_behavior=True,  # Вбудована емуляція людської поведінки
        randomize_fingerprint=True,
        webrtc_protection=True,
    )))
    
    # Профіль користувача
    if use_profile and profile_path:
        plugins.append(UserProfilePlugin(UserProfilePlugin.config(
            profile_path=profile_path,
            create_backup=True,
            validate_profile=True,
        )))
        # Вимикаємо human_behavior в EnhancedStealthPlugin якщо є профіль
        # бо профіль вже має "прогріту" поведінку
        plugins[0].config["human_behavior"] = False
    
    # Cloudflare bypass
    if use_cloudflare_bypass:
        plugins.append(EnhancedCloudflarePlugin(EnhancedCloudflarePlugin.config(
            max_wait_time=30,
            auto_solve=True,
        )))
    
    # Captcha solving
    if use_captcha_solver:
        plugins.append(CaptchaDetectorPlugin())
        if captcha_api_key:
            plugins.append(CaptchaSolverPlugin(CaptchaSolverPlugin.config(
                service="2captcha",
                api_key=captcha_api_key,
            )))
    
    # Перевіряємо сумісність
    check_plugin_compatibility(plugins, raise_on_conflict=True)
    
    return plugins
