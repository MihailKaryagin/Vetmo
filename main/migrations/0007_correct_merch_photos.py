from django.db import migrations


def correct_photos(apps, schema_editor):
    # Точечно заменяем неподходящие источники фотографий.
    Product = apps.get_model("main", "Product")
    replacements = (
        (
            "https://cdn.dummyjson.com/product-images/womens-shoes/black-&-brown-slipper/1.webp",
            "https://upload.wikimedia.org/wikipedia/commons/4/47/Flip_flop.jpg",
            "https://commons.wikimedia.org/wiki/File:Flip_flop.jpg",
        ),
        (
            "https://upload.wikimedia.org/wikipedia/commons/e/ec/Model_wears_black_opaque_tights_with_ballet_flats.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/2/23/Black_dance_tights.jpg/960px-Black_dance_tights.jpg",
            "https://commons.wikimedia.org/wiki/File:Black_dance_tights.jpg",
        ),
    )
    for old_url, image_url, image_source in replacements:
        Product.objects.using(schema_editor.connection.alias).filter(image_url=old_url).update(
            image_url=image_url, image_source=image_source,
        )


class Migration(migrations.Migration):
    # Корректировка выполняется поверх миграции с первоначальными фото.
    dependencies = [("main", "0006_merch_photos")]
    operations = [migrations.RunPython(correct_photos, migrations.RunPython.noop)]
