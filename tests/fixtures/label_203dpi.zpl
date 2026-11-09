{% set dpi = 203 %}
^XA
^FO50,50{{ qr(item.url, size_mm=25) }}
^FO50,300{{ code128(item.sku, width_mm=40, height_mm=10) }}
^FO50,450{{ ean13(item.ean) }}
^FO50,600^A0N,30,30^FD{{ item.name }}^FS
^XZ
