"""Життєвий цикл Node - 2 етапи."""

from enum import Enum


class NodeLifecycle(str, Enum):
    """
    Життєвий цикл Node має 2 ЧІТКІ ЕТАПИ:

    ЕТАП 1: СТВОРЕННЯ (URL_STAGE)
        Доступно: url, depth, should_scan, can_create_edges
        Що можна:
          * Аналізувати URL на ключові слова
          * Визначати параметри по домену
          * Встановлювати should_scan, can_create_edges
         Що НЕМОЖНА:
          * Працювати з HTML (його ще немає!)
          * Використовувати metadata (їх ще немає!)
          * Аналізувати контент сторінки

    ЕТАП 2: ОБРОБКА HTML (HTML_STAGE)
         INPUT (на початку process_html):
          * html - HTML контент (string)
          * html_tree - DOM дерево (після парсингу)
          * parser - Tree adapter для роботи з деревом

         ОБРОБКА (через плагіни):
          * Плагіни витягують metadata (title, h1, description, keywords)
          * Плагіни витягують посилання
          * Плагіни заповнюють user_data

         OUTPUT (після process_html):
          * metadata - заповнені метадані (dict)
          * user_data - дані від плагінів (dict)
          * extracted_links - список URL (list)

        Що можна:
          * Витягувати метадані через плагіни
          * Аналізувати текст сторінки
          * Шукати ключові слова в контенті
          * Витягувати посилання
         Що НЕМОЖНА:
          * Змінювати базові параметри ноди (url, depth)

    Це жорстке розділення запобігає помилкам:
    -  Пошук ключових слів в HTML до сканування
    -  Використання metadata при створенні ноди (їх ще немає!)
    -  Виклик методів не на своєму етапі
    """

    # ЕТАП 1: Створення ноди (тільки URL)
    URL_STAGE = "url_stage"

    # ЕТАП 2: Сканування (HTML доступний)
    HTML_STAGE = "html_stage"

    # Не просканована
    NOT_SCANNED = "not_scanned"


class NodeLifecycleError(Exception):
    """Помилка використання методу не на тому етапі життєвого циклу."""

    pass
