from functools import wraps
import hashlib

from django.db import transaction
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone

from .models import FormThrottle, MerchOrder, Product, ProductVariant, Notification


def limit_posts(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method == 'POST':
            # лимит привязан к адресу и обработчику а не к данным формы
            identity = f'{request.META.get("REMOTE_ADDR", "")}/{getattr(view, "view_class", view).__name__}'
            key = hashlib.sha256(identity.encode()).hexdigest()
            with transaction.atomic():
                row, _ = FormThrottle.objects.get_or_create(key=key)
                row = FormThrottle.objects.select_for_update().get(pk=row.pk)
                if (timezone.now() - row.window_start).total_seconds() >= 60:
                    row.count = 0
                    row.window_start = timezone.now()
                if row.count >= 10:
                    response = HttpResponse('Слишком много отправок попробуйте через минуту', status=429)
                    response['Retry-After'] = '60'
                    return response
                row.count += 1
                row.save()
        return view(request, *args, **kwargs)
    return wrapped


@transaction.atomic
def change_order_status(order_id, status):
    order = MerchOrder.objects.select_for_update().get(pk=order_id)
    if status not in dict(MerchOrder._meta.get_field('status').choices):
        raise ValueError('Неизвестный статус')
    # отмененный заказ не открываем повторно без нового резервирования
    if order.status == 'cancelled' and status != 'cancelled':
        raise ValueError('Создайте новый заказ вместо повторного открытия отмененного')
    changed = order.status != status
    if status == 'cancelled' and not order.stock_returned:
        for item in order.items.select_related('product').order_by('product_id'):
            if item.product_id:
                Product.objects.filter(pk=item.product_id).update(counter=F('counter') + item.quantity)
                ProductVariant.objects.filter(product_id=item.product_id, size=item.size).update(stock=F('stock') + item.quantity)
        order.stock_returned = True
    order.status = status
    order.save(update_fields=['status', 'stock_returned'])
    if changed:
        order.history.create(status=status)
    if changed and order.account_id:
        Notification.objects.create(account=order.account, text=f'Заказ {str(order.pk)[:8]} · {order.get_status_display()}', url=f'/account/orders/{order.pk}/')
    return order
