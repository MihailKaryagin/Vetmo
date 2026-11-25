from django.db import migrations


def add_merch_photos(apps, schema_editor):
    # В миграции используем историческую модель через apps.
    Product = apps.get_model("main", "Product")
    photos = (
        ("ботин", "https://upload.wikimedia.org/wikipedia/commons/1/1f/Leather_boots_men%27s.jpg", "https://commons.wikimedia.org/wiki/File:Leather_boots_men%27s.jpg"),
        ("шлеп", "https://cdn.dummyjson.com/product-images/womens-shoes/black-&-brown-slipper/1.webp", "https://dummyjson.com/products/185"),
        ("пончо", "https://upload.wikimedia.org/wikipedia/commons/d/d0/Poncho_MET_CI40.65.12_d1.jpg", "https://commons.wikimedia.org/wiki/File:Poncho_MET_CI40.65.12_d1.jpg"),
        ("пумпон", "https://upload.wikimedia.org/wikipedia/commons/7/72/Beanie_hat_by_Polo_Ralph_Lauren.jpg", "https://commons.wikimedia.org/wiki/File:Beanie_hat_by_Polo_Ralph_Lauren.jpg"),
        ("колгот", "https://upload.wikimedia.org/wikipedia/commons/e/ec/Model_wears_black_opaque_tights_with_ballet_flats.jpg", "https://commons.wikimedia.org/wiki/File:Model_wears_black_opaque_tights_with_ballet_flats.jpg"),
    )
    # Заполняем только пустые ссылки и подбираем фото по названию товара.
    for product in Product.objects.using(schema_editor.connection.alias).filter(image_url=""):
        name = product.name.lower().replace("ё", "е")
        for keyword, image_url, source in photos:
            if keyword in name:
                product.image_url = image_url
                product.image_source = source
                product.save(using=schema_editor.connection.alias, update_fields=["image_url", "image_source"])
                break


class Migration(migrations.Migration):
    # Загружаем демонстрационные фотографии после добавления полей URL.
    dependencies = [("main", "0005_product_image_source_product_image_url")]

    operations = [migrations.RunPython(add_merch_photos, migrations.RunPython.noop)]
