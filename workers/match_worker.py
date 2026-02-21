# workers/match_worker.py
import os
import cv2
import numpy as np
import random
from PyQt5.QtCore import QThread, pyqtSignal

from config import ERROR_THRESHOLD, TILE_SIZE
from utils.image_processing import refine_tile_position


class WorkerMatch(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, bg_dir, mask_dir, output_file):
        super().__init__()
        self.bg_dir = bg_dir
        self.mask_dir = mask_dir
        self.output_file = output_file

    def run(self):
        try:
            self.process()
            self.finished.emit(True, "Обработка завершена успешно.")
        except Exception as e:
            self.finished.emit(False, f"Ошибка: {str(e)}")

    def process(self):
        img_exts = ('.png', '.bmp', '.jpg', '.jpeg', '.tif', '.tiff')

        # Загрузка фонов
        self.log.emit("Загрузка фонов...")
        bg_files = [f for f in os.listdir(self.bg_dir) if f.lower().endswith(img_exts)]
        if not bg_files:
            raise Exception("В директории с фонами нет изображений.")

        backgrounds = []
        for f in bg_files:
            path = os.path.join(self.bg_dir, f)
            img = cv2.imread(path)
            if img is None:
                self.log.emit(f"Предупреждение: не удалось загрузить {f}")
                continue
            backgrounds.append((f, img))
        self.log.emit(f"Загружено фонов: {len(backgrounds)}")

        # Загрузка масок
        self.log.emit("Загрузка масок...")
        mask_files = [f for f in os.listdir(self.mask_dir) if f.lower().endswith(img_exts)]
        if not mask_files:
            raise Exception("В директории с масками нет изображений.")
        self.log.emit(f"Найдено масок: {len(mask_files)}")

        with open(self.output_file, 'w', encoding='utf-8') as out:
            out.write("mask,background,bg_x,bg_y,mask_x,mask_y\n")

            total_masks = len(mask_files)
            for idx, mask_fname in enumerate(mask_files):
                self.log.emit(f"Обработка маски: {mask_fname}")
                mask_path = os.path.join(self.mask_dir, mask_fname)
                mask_img = cv2.imread(mask_path, cv2.IMREAD_UNCHANGED)
                if mask_img is None:
                    self.log.emit(f"  Не удалось загрузить маску, пропуск.")
                    self.update_progress(idx + 1, total_masks)
                    continue

                if mask_img.shape[2] != 4:
                    self.log.emit(f"  Маска без альфа-канала, пропуск.")
                    self.update_progress(idx + 1, total_masks)
                    continue

                alpha = mask_img[:, :, 3]
                h, w = mask_img.shape[:2]

                # Собираем все блоки 16x16, содержащие непрозрачные пиксели
                tiles = []
                for y in range(0, h, TILE_SIZE):
                    for x in range(0, w, TILE_SIZE):
                        if x + TILE_SIZE > w or y + TILE_SIZE > h:
                            continue
                        if np.any(alpha[y:y+TILE_SIZE, x:x+TILE_SIZE] > 0):
                            tiles.append((x, y))

                if not tiles:
                    self.log.emit(f"  В маске нет тайлов {TILE_SIZE}x{TILE_SIZE} с непрозрачными пикселями.")
                    self.update_progress(idx + 1, total_masks)
                    continue

                self.log.emit(f"  Найдено тайлов: {len(tiles)}")

                # Определяем фон по нескольким тайлам
                num_samples = min(5, len(tiles))
                sample_indices = random.sample(range(len(tiles)), num_samples)
                sample_tiles = [tiles[i] for i in sample_indices]

                bg_votes = {}
                bg_errors = {}

                for (tx, ty) in sample_tiles:
                    tile_rgb = mask_img[ty:ty+TILE_SIZE, tx:tx+TILE_SIZE, :3]
                    tile_alpha = alpha[ty:ty+TILE_SIZE, tx:tx+TILE_SIZE]
                    tile_mask_cv = (tile_alpha > 0).astype(np.uint8) * 255
                    best_bg = None
                    best_error = float('inf')
                    for bg_name, bg_img in backgrounds:
                        result = cv2.matchTemplate(bg_img, tile_rgb, cv2.TM_SQDIFF, mask=tile_mask_cv)
                        min_val, _, _, _ = cv2.minMaxLoc(result)
                        if min_val < best_error:
                            best_error = min_val
                            best_bg = bg_name
                    if best_bg:
                        bg_votes[best_bg] = bg_votes.get(best_bg, 0) + 1
                        bg_errors[best_bg] = bg_errors.get(best_bg, 0) + best_error

                if not bg_votes:
                    self.log.emit(f"  Не удалось определить фон ни по одному тайлу.")
                    self.update_progress(idx + 1, total_masks)
                    continue

                max_votes = max(bg_votes.values())
                candidates = [bg for bg, votes in bg_votes.items() if votes == max_votes]
                if len(candidates) == 1:
                    best_bg = candidates[0]
                else:
                    best_bg = min(candidates, key=lambda bg: bg_errors[bg])

                self.log.emit(f"  Фон определен: {best_bg} (голосов {bg_votes[best_bg]})")
                bg_img = next(bg for name, bg in backgrounds if name == best_bg)

                # Для всех тайлов выполняем точный поиск с уточнением
                for (tx, ty) in tiles:
                    tile_rgb = mask_img[ty:ty+TILE_SIZE, tx:tx+TILE_SIZE, :3]
                    tile_alpha = alpha[ty:ty+TILE_SIZE, tx:tx+TILE_SIZE]
                    tile_mask_cv = (tile_alpha > 0).astype(np.uint8) * 255
                    result = cv2.matchTemplate(bg_img, tile_rgb, cv2.TM_SQDIFF, mask=tile_mask_cv)
                    min_val, _, min_loc, _ = cv2.minMaxLoc(result)
                    refined_pos, refined_error = refine_tile_position(tile_rgb, tile_alpha, bg_img, min_loc, search_radius=4)

                    if refined_pos is None or refined_error > ERROR_THRESHOLD:
                        self.log.emit(f"  Тайл ({tx},{ty}) не найден на фоне (ошибка {refined_error:.2f})")
                    else:
                        out.write(f"{mask_fname},{best_bg},{refined_pos[0]},{refined_pos[1]},{tx},{ty}\n")

                self.update_progress(idx + 1, total_masks)

        self.log.emit("Обработка всех масок завершена.")

    def update_progress(self, current, total):
        percent = int(current * 100 / total)
        self.progress.emit(percent)