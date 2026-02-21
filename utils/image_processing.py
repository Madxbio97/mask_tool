# utils/image_processing.py
import cv2
import numpy as np

def refine_tile_position(tile_rgb, tile_alpha, bg_img, initial_pos, search_radius=4):
    """
    Уточняет позицию тайла на фоне, используя среднеквадратичную ошибку только по непрозрачным пикселям.
    :param tile_rgb: (16,16,3) цветной тайл
    :param tile_alpha: (16,16) альфа-канал (0-255), >0 означает непрозрачный
    :param bg_img: полное изображение фона (BGR)
    :param initial_pos: (x, y) приблизительная позиция
    :param search_radius: радиус поиска вокруг initial_pos
    :return: (best_x, best_y, best_error) или (None, None, inf) если не найдено
    """
    h, w = bg_img.shape[:2]
    mask = (tile_alpha > 0).astype(np.float32)
    nz = np.count_nonzero(mask)
    if nz == 0:
        return None, None, float('inf')

    tile_rgb_float = tile_rgb.astype(np.float32)
    best_error = float('inf')
    best_pos = None

    x0, y0 = initial_pos
    x_start = max(0, x0 - search_radius)
    x_end = min(w - 16, x0 + search_radius + 1)
    y_start = max(0, y0 - search_radius)
    y_end = min(h - 16, y0 + search_radius + 1)

    for y in range(y_start, y_end):
        for x in range(x_start, x_end):
            bg_patch = bg_img[y:y+16, x:x+16].astype(np.float32)
            diff = bg_patch - tile_rgb_float
            diff_sq = (diff ** 2) * mask[..., np.newaxis]
            error = np.sum(diff_sq) / nz
            if error < best_error:
                best_error = error
                best_pos = (x, y)

    return best_pos, best_error


def find_tile_sqdiff_refine(tile_rgb, tile_alpha, bg_img):
    """
    Поиск тайла методом SQDIFF с последующим уточнением.
    """
    tile_mask_cv = (tile_alpha > 0).astype(np.uint8) * 255
    result = cv2.matchTemplate(bg_img, tile_rgb, cv2.TM_SQDIFF, mask=tile_mask_cv)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)
    return refine_tile_position(tile_rgb, tile_alpha, bg_img, min_loc, search_radius=4)


def find_tile_ccorr_normed_refine(tile_rgb, tile_alpha, bg_img):
    """
    Поиск тайла методом нормализованной корреляции с последующим уточнением.
    """
    tile_mask_cv = (tile_alpha > 0).astype(np.uint8) * 255
    result = cv2.matchTemplate(bg_img, tile_rgb, cv2.TM_CCORR_NORMED, mask=tile_mask_cv)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    # Корреляция даёт максимум, но для уточнения нам нужна стартовая позиция
    # Используем тот же refine, который минимизирует ошибку
    return refine_tile_position(tile_rgb, tile_alpha, bg_img, max_loc, search_radius=4)


def find_tile_pyramid_sqdiff(tile_rgb, tile_alpha, bg_img, levels=2):
    """
    Пирамидальный поиск: уменьшаем фон и тайл, находим грубую позицию, затем уточняем на каждом уровне.
    """
    # Построение пирамиды для фона
    bg_pyramid = [bg_img]
    for _ in range(1, levels):
        bg_pyramid.append(cv2.pyrDown(bg_pyramid[-1]))

    # Уменьшаем тайл и его альфу
    tile_pyramid_rgb = [tile_rgb]
    tile_pyramid_alpha = [tile_alpha]
    for _ in range(1, levels):
        # Для альфы используем INTER_NEAREST чтобы сохранить форму
        tile_pyramid_rgb.append(cv2.pyrDown(tile_pyramid_rgb[-1]))
        small_alpha = cv2.resize(tile_pyramid_alpha[-1],
                                 (tile_pyramid_rgb[-1].shape[1], tile_pyramid_rgb[-1].shape[0]),
                                 interpolation=cv2.INTER_NEAREST)
        tile_pyramid_alpha.append(small_alpha)

    # Начинаем с самого маленького уровня
    coarse_x, coarse_y = 0, 0
    for level in reversed(range(levels)):
        scale = 2 ** level
        bg_lev = bg_pyramid[level]
        tile_lev_rgb = tile_pyramid_rgb[level]
        tile_lev_alpha = tile_pyramid_alpha[level]
        # Грубая позиция на этом уровне
        init_x = coarse_x // scale if level < levels-1 else 0
        init_y = coarse_y // scale if level < levels-1 else 0
        # Смещаем окно поиска
        search_rad = 2 if level < levels-1 else 4
        # Поиск с уточнением на текущем уровне
        best_pos, best_err = refine_tile_position(tile_lev_rgb, tile_lev_alpha, bg_lev, (init_x, init_y), search_radius=search_rad)
        if best_pos is None:
            return None, float('inf')
        coarse_x, coarse_y = best_pos[0] * scale, best_pos[1] * scale

    # Финальное уточнение на исходном уровне (уже выполнено на последней итерации)
    return best_pos, best_err


# Словарь методов для вызова по имени
METHODS = {
    "sqdiff_refine": find_tile_sqdiff_refine,
    "ccorr_normed_refine": find_tile_ccorr_normed_refine,
    "pyramid_sqdiff": find_tile_pyramid_sqdiff
}

def find_tile(tile_rgb, tile_alpha, bg_img, method="sqdiff_refine"):
    """
    Обёртка для выбора метода поиска.
    """
    if method not in METHODS:
        raise ValueError(f"Неизвестный метод: {method}")
    return METHODS[method](tile_rgb, tile_alpha, bg_img)