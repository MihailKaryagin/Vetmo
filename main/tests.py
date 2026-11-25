from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Publication


class PublicationTests(TestCase):
    # TestCase изолирует изменения в БД; общий набор записей создаётся для всего класса.
    @classmethod
    def setUpTestData(cls):
        # Проверяем все состояния: дневник, новость, черновик и отложенная запись.
        cls.diary = Publication.objects.create(
            title="История нашей победы", body="Первый абзац.\n\nВторой абзац.",
            is_published=True,
        )
        cls.news = Publication.objects.create(
            title="Турнир в субботу", body="Собираем команду.",
            kind=Publication.Kind.NEWS, is_published=True,
        )
        cls.draft = Publication.objects.create(title="Секретный черновик", body="Черновик")
        cls.future = Publication.objects.create(
            title="Будущая запись", body="Позже", is_published=True,
            published_at=timezone.now() + timedelta(days=1),
        )

    def test_lists_show_only_published_entries_in_their_section(self):
        # Публичные списки не должны смешивать разделы или раскрывать скрытые записи.
        for route, visible, hidden in (
            ("blog", self.diary, self.news), ("news", self.news, self.diary),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertContains(response, visible.title)
                for post in (hidden, self.draft, self.future):
                    self.assertNotContains(response, post.title)

    def test_hidden_entries_cannot_be_opened_directly(self):
        # Ограничение видимости действует и при обращении по известному ID.
        for post in (self.draft, self.future):
            self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 404)

    def test_detail_preserves_paragraphs_and_escapes_html(self):
        # Переносы строк превращаются в абзацы, но HTML автора остаётся текстом.
        self.diary.body = "Первый абзац.\n\n<script>alert('test')</script>"
        self.diary.save()
        response = self.client.get(self.diary.get_absolute_url())
        self.assertContains(response, "<p>Первый абзац.</p>", html=True)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert")

    def test_pagination(self):
        # Вместе с исходной записью 11 записей дают 9 на первой и 2 на второй странице.
        Publication.objects.bulk_create([
            Publication(title=f"Запись {i}", body="Текст", is_published=True)
            for i in range(10)
        ])
        response = self.client.get(reverse("blog"), {"page": 2})
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["page_obj"]), 2)

    def test_admin_can_create_and_publish_entry(self):
        # Полный сценарий редактора: авторизация, форма, сохранение и публичный просмотр.
        admin = get_user_model().objects.create_superuser(
            username="editor", email="editor@example.com", password="test-editor-password",
        )
        self.client.force_login(admin)
        url = reverse("admin:main_publication_add")
        response = self.client.get(url, {"kind": "news"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["adminform"].form.initial["kind"], "news")
        response = self.client.post(url, {
            "title": "Новая запись из админки", "kind": "diary",
            "summary": "Кратко о записи", "body": "Полный текст записи.",
            "is_published": "on", "published_at_0": "2026-01-01",
            "published_at_1": "12:00:00", "_save": "Сохранить",
        })
        self.assertEqual(response.status_code, 302)
        post = Publication.objects.get(title="Новая запись из админки")
        self.assertContains(self.client.get(post.get_absolute_url()), post.body)

    def test_anonymous_user_cannot_use_editor(self):
        # Гость вместо редактора получает перенаправление на вход в админку.
        response = self.client.get(reverse("admin:main_publication_add"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response.url)
