from io import StringIO
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, Product, ProductVariant, PartyListing, PartyResponse, Notification, MerchOrder, Person


class CommunityTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='owner', password='test-password-123')
        self.other = get_user_model().objects.create_user(username='other', password='test-password-123')
        self.listing = PartyListing.objects.create(account=self.owner, nickname='Игрок', schedule='вечером', mmr_min=2000, mmr_max=4000)

    def test_root_and_auth_pages_render(self):
        for url in ('/', reverse('login'), reverse('signup')):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('account')).status_code, 200)
        self.assertEqual(self.client.get(reverse('password_change')).status_code, 200)

    def test_account_ownership_is_not_granted_by_browser_key(self):
        session = self.client.session
        session['community_key'] = 'shared-browser'
        session.save()
        self.listing.visitor_key = 'shared-browser'
        self.listing.save()
        self.client.force_login(self.other)
        response = self.client.post(reverse('party_close', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(self.client.get(reverse('party_detail', args=[self.listing.pk])), 'Закрыть объявление')

    def test_owner_can_close_from_another_browser(self):
        self.client.force_login(self.owner)
        self.client.post(reverse('party_close', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertFalse(self.listing.is_active)
        self.assertEqual(self.client.get(reverse('party_detail', args=[self.listing.pk])).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('party_detail', args=[self.listing.pk])).status_code, 404)

    def test_only_owner_can_edit_listing(self):
        url = reverse('party_edit', args=[self.listing.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(url), 'Изменить объявление')

    def test_response_creates_one_private_notification(self):
        url = reverse('party_detail', args=[self.listing.pk])
        for _ in range(2):
            self.client.post(url, {'nickname': 'Друг', 'contact': '@friend', 'message': 'готов'})
        self.assertEqual(PartyResponse.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(account=self.owner).count(), 1)
        self.assertNotContains(self.client.get(url), '@friend')

    def test_mmr_and_schedule_filters(self):
        response = self.client.get(reverse('party'), {'mmr': 3000, 'schedule': 'вечер'})
        self.assertEqual(len(response.context['listings']), 1)
        response = self.client.get(reverse('party'), {'mmr': 5000})
        self.assertEqual(len(response.context['listings']), 0)
        self.assertEqual(self.client.get(reverse('party'), {'mmr': 'bad'}).status_code, 200)

    def test_signup_creates_account_and_profile(self):
        response = self.client.post(reverse('signup'), {'username': 'new-player', 'email': 'new@example.com', 'password1': 'Very-strong-pass-345', 'password2': 'Very-strong-pass-345'})
        self.assertRedirects(response, reverse('account'))
        self.assertTrue(Person.objects.filter(account__username='new-player').exists())

    def test_backup_can_be_loaded(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'copy.json.gz'
            call_command('backup_database', output=str(path), stdout=StringIO())
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                self.assertTrue(json.load(stream))
            self.listing.delete()
            call_command('loaddata', str(path), stdout=StringIO())
            self.assertTrue(PartyListing.objects.filter(nickname='Игрок').exists())


class OrderStockTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='лето', category='мерч')
        self.product = Product.objects.create(name='Футболка', sale=1000, material='хлопок', data_prod=timezone.localdate(), counter=8, cat_id=category)
        self.variant = ProductVariant.objects.create(product=self.product, size='M', stock=2)
        ProductVariant.objects.create(product=self.product, size='L', stock=6)
        self.data = {'name': 'Игрок', 'contact': '@player', 'delivery': 'Москва', 'size': 'M', 'quantity': 2}

    def test_order_reserves_selected_size_and_is_private(self):
        user = get_user_model().objects.create_user(username='buyer', password='test-password')
        self.client.force_login(user)
        response = self.client.post(reverse('merch_order', args=[self.product.pk]), self.data)
        self.assertRedirects(response, reverse('order_success'))
        self.variant.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.variant.stock, 0)
        self.assertEqual(self.product.counter, 6)
        order = MerchOrder.objects.get()
        self.assertEqual(order.account, user)
        self.assertEqual(order.total, 2000)
        self.client.logout()
        other = get_user_model().objects.create_user(username='stranger')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('account_order', args=[order.pk])).status_code, 404)

    def test_insufficient_size_does_not_create_order(self):
        self.data['quantity'] = 3
        response = self.client.post(reverse('merch_order', args=[self.product.pk]), self.data)
        self.assertContains(response, 'Недостаточно товара выбранного размера')
        self.assertFalse(MerchOrder.objects.exists())
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 2)

    def test_sold_out_size_has_measurements_but_cannot_be_ordered(self):
        self.variant.stock = 0
        self.variant.width_cm = 54
        self.variant.length_cm = 72
        self.variant.save()
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))
        self.assertContains(response, '<tr><th scope="row">M</th><td>Закончился</td><td>54</td><td>72</td></tr>', html=True)
        self.assertNotContains(response, '<option value="M"')
        self.assertContains(response, '<option value="L"')
        self.client.post(reverse('merch_order', args=[self.product.pk]), self.data)
        self.assertFalse(MerchOrder.objects.exists())

    def test_stock_exhausted_after_form_opened_shows_error(self):
        self.product.counter = 0
        self.product.save(update_fields=['counter'])
        response = self.client.post(reverse('merch_order', args=[self.product.pk]), self.data)
        self.assertContains(response, 'Недостаточно товара в наличии.')
        self.assertNotContains(response, 'Оформить заказ')
        self.assertFalse(MerchOrder.objects.exists())

    def test_history_shows_only_actual_transitions_and_order_reference(self):
        from .services import change_order_status

        self.client.post(reverse('merch_order', args=[self.product.pk]), self.data)
        order = MerchOrder.objects.get()
        for status in ('confirmed', 'confirmed', 'cancelled'):
            change_order_status(order.pk, status)
        events = list(order.history.all())
        self.assertEqual([e.status for e in events], ['new', 'confirmed', 'cancelled'])
        self.assertEqual(events[0].changed_at, order.created_at)
        self.assertLessEqual(events[0].changed_at, events[1].changed_at)
        self.assertLessEqual(events[1].changed_at, events[2].changed_at)
        response = self.client.get(reverse('order_success'))
        self.assertContains(response, 'Отправки не будет')
        self.assertContains(response, f'data-order-question="{order.pk}"')
        self.assertNotContains(response, self.data['contact'])
