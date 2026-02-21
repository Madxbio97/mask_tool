# utils/image_processing.py
import cv2
import numpy as np

def refine_tile_position(tile_rgb, tile_alpha, bg_img, initial_pos, search_radius=4):
    """
    Уточняет позицию тайла на фоне, используя нормализованную ошибку только по непрозрачным пикселям.
    :param tile_rgb: (16,16,3) цветной тайл
    :param tile_alpha: (16,16) альфа-канал (0-255), >0 означает непрозрачный
    :param bg_img: полное изображение фона (BGR)
    :param initial_pos: (x, y) приблизительная позиция
    :param search_radius: радиус поиска вокруг initial_pos
    :return: (best_x, best_y, best_error) или (None, None, inf) если не найдено
    """
    h, w = bg_img.shape[:2]
    mask = (tile_alpha > 0).astype(np.float32)  # 0 или 1
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