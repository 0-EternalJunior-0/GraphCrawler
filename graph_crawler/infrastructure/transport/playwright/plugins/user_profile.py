"""
User Profile плагін для Playwright драйвера.

Дозволяє використовувати профілі реального користувача для обходу anti-bot систем.

Features:
- Підключення user_data_dir до браузера
- Валідація профілю перед використанням
- Автоматичний backup профілю
- Ротація профілів для pool (ProfilePoolPlugin)

Usage:
    plugin = UserProfilePlugin(UserProfilePlugin.config(
        profile_path="/home/user/.config/crawl-profile",
        create_backup=True
    ))
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage

logger = logging.getLogger(__name__)


class UserProfilePlugin(BaseDriverPlugin):
    """
    Плагін для роботи з профілями користувача Chrome/Chromium.

    Дозволяє використовувати існуючий профіль браузера з cookies,
    localStorage, історією для обходу anti-bot систем.

    Конфігурація:
        profile_path: Шлях до профілю користувача (обов'язково)
        create_backup: Створювати backup перед використанням (default: True)
        backup_path: Шлях для backup (default: profile_path + "_backup")
        validate_profile: Перевіряти наявність профілю (default: True)
        headless_warning: Попереджати про headless режим (default: True)
        executable_path: Шлях до Chrome/Chromium executable (optional)

    Приклад:
        >>> plugin = UserProfilePlugin(UserProfilePlugin.config(
        ...     profile_path="/home/user/.config/crawl-profile",
        ...     create_backup=True,
        ...     validate_profile=True
        ... ))
        >>> driver = PlaywrightDriver(config, plugins=[plugin])

    Шляхи до профілів за замовчуванням:
        Windows: %USERPROFILE%\\AppData\\Local\\Google\\Chrome\\User Data\\Default
        macOS:   ~/Library/Application Support/Google/Chrome/Default
        Linux:   ~/.config/google-chrome/Default
    """

    @property
    def name(self) -> str:
        return "user_profile"

    def get_hooks(self) -> List[str]:
        return [
            BrowserStage.BROWSER_LAUNCHING,
            BrowserStage.CONTEXT_CREATING,
        ]

    def setup(self):
        """Валідація конфігурації при ініціалізації."""
        profile_path = self.config.get("profile_path")

        if not profile_path:
            logger.warning(
                "UserProfilePlugin: profile_path not configured. "
                "Plugin will be inactive. Use UserProfilePlugin.config(profile_path='...')"
            )
            self.enabled = False
            return

        # Розширюємо ~ до повного шляху
        profile_path = os.path.expanduser(profile_path)
        self.config["profile_path"] = profile_path

        if self.config.get("validate_profile", True):
            if not self._validate_profile(profile_path):
                logger.error(f"Invalid profile path: {profile_path}")
                self.enabled = False
                return

        # Створюємо backup якщо потрібно
        if self.config.get("create_backup", True):
            backup_result = self._create_backup(profile_path)
            if backup_result:
                logger.info(f"Profile backup: {backup_result}")

        logger.info(f"✅ UserProfilePlugin initialized with profile: {profile_path}")

    def _validate_profile(self, profile_path: str) -> bool:
        """
        Перевіряє валідність профілю Chrome/Chromium.

        Args:
            profile_path: Шлях до директорії профілю

        Returns:
            True якщо профіль валідний
        """
        path = Path(profile_path)

        if not path.exists():
            logger.error(f"Profile directory does not exist: {profile_path}")
            return False

        if not path.is_dir():
            logger.error(f"Profile path is not a directory: {profile_path}")
            return False

        # Ключові файли Chrome/Chromium профілю
        required_indicators = ["Preferences"]
        optional_indicators = [
            "Cookies",
            "Local State",
            "History",
            "Bookmarks",
            "Login Data",
            "Web Data",
            "Local Storage",
        ]

        found_required = sum(
            1 for f in required_indicators if (path / f).exists()
        )
        found_optional = sum(
            1 for f in optional_indicators if (path / f).exists()
        )

        if found_required == 0 and found_optional == 0:
            logger.warning(
                f"Profile at {profile_path} doesn't look like a Chrome profile. "
                "Make sure you're pointing to the correct directory (e.g., 'Default' folder)."
            )
            # Не повертаємо False - можливо користувач знає що робить
            return True

        logger.debug(
            f"Profile validation: {found_required}/{len(required_indicators)} required, "
            f"{found_optional}/{len(optional_indicators)} optional files found"
        )
        return True

    def _create_backup(self, profile_path: str) -> Optional[str]:
        """
        Створює backup профілю.

        Args:
            profile_path: Шлях до профілю

        Returns:
            Шлях до backup або None якщо не вдалось
        """
        backup_path = self.config.get("backup_path")
        if not backup_path:
            backup_path = f"{profile_path}_backup"

        try:
            backup_dir = Path(backup_path)

            if backup_dir.exists():
                logger.debug(f"Backup already exists: {backup_path}")
                return backup_path

            # Копіюємо тільки необхідні файли (не весь cache)
            essential_files = [
                "Preferences",
                "Cookies",
                "Local State",
                "Bookmarks",
                "Login Data",
                "Web Data",
            ]
            essential_dirs = [
                "Local Storage",
                "Session Storage",
                "IndexedDB",
            ]

            backup_dir.mkdir(parents=True, exist_ok=True)
            profile_dir = Path(profile_path)

            # Копіюємо файли
            for file_name in essential_files:
                src = profile_dir / file_name
                if src.exists():
                    shutil.copy2(src, backup_dir / file_name)

            # Копіюємо директорії
            for dir_name in essential_dirs:
                src = profile_dir / dir_name
                if src.exists() and src.is_dir():
                    shutil.copytree(src, backup_dir / dir_name, dirs_exist_ok=True)

            logger.info(f"Profile backup created: {backup_path}")
            return backup_path

        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
            return None

    def _get_profile_size(self, profile_path: str) -> float:
        """Повертає розмір профілю в МБ."""
        try:
            path = Path(profile_path)
            if not path.exists():
                return 0.0
            total_size = sum(
                f.stat().st_size
                for f in path.rglob("*")
                if f.is_file()
            )
            return total_size / (1024 * 1024)
        except Exception:
            return 0.0

    async def on_browser_launching(self, ctx: BrowserContext) -> BrowserContext:
        """
        Хук перед запуском браузера.

        Попереджає про headless режим (profile краще працює в headed).
        """
        if not self.enabled:
            return ctx

        # Попередження про headless
        if self.config.get("headless_warning", True):
            headless = ctx.data.get("headless", True)
            if headless:
                logger.warning(
                    "⚠️ Using profile in headless mode may reduce effectiveness. "
                    "Consider using headless=False for better anti-bot bypass."
                )

        # Передаємо executable_path якщо вказано
        executable_path = self.config.get("executable_path")
        if executable_path:
            ctx.data["executable_path"] = executable_path
            logger.debug(f"Using custom browser executable: {executable_path}")

        return ctx

    async def on_context_creating(self, ctx: BrowserContext) -> BrowserContext:
        """
        Хук перед створенням контексту.

        Передає конфігурацію профілю в контекст для використання драйвером.
        """
        if not self.enabled:
            return ctx

        profile_path = self.config.get("profile_path")

        if not profile_path:
            return ctx

        # Передаємо шлях до профілю в data для використання драйвером
        ctx.data["user_data_dir"] = profile_path
        ctx.data["profile_enabled"] = True

        # Передаємо channel якщо вказано (chrome, msedge, etc.)
        channel = self.config.get("channel")
        if channel:
            ctx.data["channel"] = channel

        logger.info(f"🔑 Profile configured for browser context: {profile_path}")

        return ctx

    def get_profile_info(self) -> Dict[str, Any]:
        """
        Повертає інформацію про профіль.

        Returns:
            Словник з інформацією про профіль
        """
        profile_path = self.config.get("profile_path")
        if not profile_path:
            return {"enabled": False, "reason": "No profile configured"}

        path = Path(profile_path)

        info = {
            "enabled": self.enabled,
            "path": str(profile_path),
            "exists": path.exists(),
            "size_mb": self._get_profile_size(profile_path),
        }

        if path.exists():
            # Перевіряємо наявність cookies
            cookies_file = path / "Cookies"
            if cookies_file.exists():
                info["has_cookies"] = True
                info["cookies_size_kb"] = cookies_file.stat().st_size / 1024
            else:
                info["has_cookies"] = False

            # Перевіряємо Local Storage
            local_storage = path / "Local Storage"
            info["has_local_storage"] = local_storage.exists()

            # Перевіряємо історію
            history_file = path / "History"
            info["has_history"] = history_file.exists()

        return info


class ProfilePoolPlugin(BaseDriverPlugin):
    """
    Плагін для ротації профілів (для PooledPlaywrightDriver).

    Використовується коли потрібно розподілити запити між різними профілями
    для зменшення ризику блокування.

    Конфігурація:
        profiles: Список шляхів до профілів (обов'язково)
        rotation_strategy: Стратегія ротації:
            - 'round_robin': По черзі (default)
            - 'random': Випадково
            - 'least_used': Найменш використаний
        validate_profiles: Перевіряти наявність профілів (default: True)

    Приклад:
        >>> plugin = ProfilePoolPlugin(ProfilePoolPlugin.config(
        ...     profiles=[
        ...         "/home/user/.config/profile1",
        ...         "/home/user/.config/profile2",
        ...         "/home/user/.config/profile3",
        ...     ],
        ...     rotation_strategy='round_robin'
        ... ))
        >>> driver = PooledPlaywrightDriver(
        ...     config,
        ...     browsers=3,
        ...     tabs_per_browser=1,
        ...     plugins=[plugin]
        ... )
    """

    def __init__(self, config: Dict[str, Any] = None, priority: int = 10):
        super().__init__(config, priority)
        self._current_index = 0
        self._usage_count: Dict[str, int] = {}
        self._valid_profiles: List[str] = []

    @property
    def name(self) -> str:
        return "profile_pool"

    def get_hooks(self) -> List[str]:
        return [BrowserStage.CONTEXT_CREATING]

    def setup(self):
        """Ініціалізація та валідація профілів."""
        profiles = self.config.get("profiles", [])

        if not profiles:
            logger.warning(
                "ProfilePoolPlugin: No profiles configured. "
                "Use ProfilePoolPlugin.config(profiles=[...])"
            )
            self.enabled = False
            return

        # Розширюємо ~ в шляхах
        profiles = [os.path.expanduser(p) for p in profiles]

        # Валідуємо всі профілі
        validate = self.config.get("validate_profiles", True)
        valid_profiles = []

        for profile in profiles:
            if not validate or Path(profile).exists():
                valid_profiles.append(profile)
                self._usage_count[profile] = 0
            else:
                logger.warning(f"Profile not found, skipping: {profile}")

        if not valid_profiles:
            logger.error("ProfilePoolPlugin: No valid profiles found!")
            self.enabled = False
            return

        self._valid_profiles = valid_profiles
        self.config["profiles"] = valid_profiles

        logger.info(
            f"✅ ProfilePoolPlugin initialized with {len(valid_profiles)} profiles "
            f"(strategy: {self.config.get('rotation_strategy', 'round_robin')})"
        )

    def _get_next_profile(self) -> str:
        """
        Повертає наступний профіль згідно стратегії ротації.

        Returns:
            Шлях до профілю
        """
        profiles = self._valid_profiles
        strategy = self.config.get("rotation_strategy", "round_robin")

        if not profiles:
            raise RuntimeError("No profiles available")

        if strategy == "round_robin":
            profile = profiles[self._current_index % len(profiles)]
            self._current_index += 1

        elif strategy == "random":
            import random
            profile = random.choice(profiles)

        elif strategy == "least_used":
            profile = min(profiles, key=lambda p: self._usage_count.get(p, 0))

        else:
            logger.warning(f"Unknown rotation strategy: {strategy}, using first profile")
            profile = profiles[0]

        self._usage_count[profile] = self._usage_count.get(profile, 0) + 1
        return profile

    async def on_context_creating(self, ctx: BrowserContext) -> BrowserContext:
        """
        Призначає профіль для контексту.
        """
        if not self.enabled:
            return ctx

        try:
            profile = self._get_next_profile()
            ctx.data["user_data_dir"] = profile
            ctx.data["profile_from_pool"] = True

            logger.debug(f"🎲 Assigned profile from pool: {profile}")

        except Exception as e:
            logger.error(f"Failed to assign profile: {e}")

        return ctx

    def reset_usage(self):
        """Скидає статистику використання."""
        for profile in self._usage_count:
            self._usage_count[profile] = 0
        self._current_index = 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Повертає статистику використання профілів.

        Returns:
            Словник зі статистикою
        """
        return {
            "name": self.name,
            "enabled": self.enabled,
            "total_profiles": len(self._valid_profiles),
            "profiles": self._valid_profiles,
            "usage_count": dict(self._usage_count),
            "rotation_strategy": self.config.get("rotation_strategy", "round_robin"),
            "current_index": self._current_index,
        }


# Допоміжні функції

def get_default_chrome_profile_path() -> Optional[str]:
    """
    Повертає шлях до профілю Chrome за замовчуванням для поточної ОС.

    Returns:
        Шлях до профілю або None якщо не знайдено
    """
    import platform

    system = platform.system()

    if system == "Windows":
        base = os.path.expandvars(r"%USERPROFILE%\AppData\Local\Google\Chrome\User Data")
    elif system == "Darwin":  # macOS
        base = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    else:  # Linux
        base = os.path.expanduser("~/.config/google-chrome")

    default_profile = os.path.join(base, "Default")

    if os.path.exists(default_profile):
        return default_profile

    # Можливо профіль називається інакше
    if os.path.exists(base):
        return base

    return None


def get_default_chromium_profile_path() -> Optional[str]:
    """
    Повертає шлях до профілю Chromium за замовчуванням для поточної ОС.

    Returns:
        Шлях до профілю або None якщо не знайдено
    """
    import platform

    system = platform.system()

    if system == "Windows":
        base = os.path.expandvars(r"%USERPROFILE%\AppData\Local\Chromium\User Data")
    elif system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support/Chromium")
    else:
        base = os.path.expanduser("~/.config/chromium")

    default_profile = os.path.join(base, "Default")

    if os.path.exists(default_profile):
        return default_profile

    if os.path.exists(base):
        return base

    return None


def create_profile_copy(
    source_path: str,
    dest_path: str,
    essential_only: bool = True
) -> bool:
    """
    Створює копію профілю Chrome/Chromium.

    Args:
        source_path: Шлях до оригінального профілю
        dest_path: Шлях для копії
        essential_only: Копіювати тільки необхідні файли (без cache)

    Returns:
        True якщо успішно
    """
    try:
        source = Path(source_path)
        dest = Path(dest_path)

        if not source.exists():
            logger.error(f"Source profile does not exist: {source_path}")
            return False

        if dest.exists():
            logger.warning(f"Destination already exists: {dest_path}")
            return False

        if essential_only:
            # Копіюємо тільки необхідні файли
            essential_files = [
                "Preferences",
                "Cookies",
                "Local State",
                "Bookmarks",
                "Login Data",
                "Web Data",
                "Favicons",
            ]
            essential_dirs = [
                "Local Storage",
                "Session Storage",
                "IndexedDB",
                "Extension State",
            ]

            dest.mkdir(parents=True, exist_ok=True)

            for file_name in essential_files:
                src_file = source / file_name
                if src_file.exists():
                    shutil.copy2(src_file, dest / file_name)
                    logger.debug(f"Copied: {file_name}")

            for dir_name in essential_dirs:
                src_dir = source / dir_name
                if src_dir.exists() and src_dir.is_dir():
                    shutil.copytree(src_dir, dest / dir_name, dirs_exist_ok=True)
                    logger.debug(f"Copied directory: {dir_name}")

        else:
            # Повна копія
            shutil.copytree(source, dest)

        logger.info(f"Profile copied: {source_path} -> {dest_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to copy profile: {e}")
        return False
