# config.py
# Порог среднеквадратичной ошибки на пиксель для признания тайла найденным
ERROR_THRESHOLD = 50.0

# Размер тайла
TILE_SIZE = 16

# Коэффициент увеличения
UPSCALE_FACTOR = 4

# Доступные методы сравнения для первой вкладки
MATCH_METHODS = {
    "SQDIFF + refine": "sqdiff_refine",
    "CCORR_NORMED + refine": "ccorr_normed_refine",
    "Пирамидальный SQDIFF": "pyramid_sqdiff"
}

# Метод по умолчанию
DEFAULT_METHOD = "sqdiff_refine"