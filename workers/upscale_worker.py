# workers/upscale_worker.py
import os
import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from config import UPSCALE_FACTOR, TILE_SIZE


class WorkerUpscale(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, upscaled_bg_dir, csv_path, original_mask_dir, output_dir):
        super().__init__()
        self.upscaled_bg_dir = upscaled_bg_dir
        self.csv_path = csv_path
        self.original_mask_dir = original_mask_dir
        self.output_dir = output_dir

    def run(self):
        try:
            self.process()
            self.finished.emit(True, "Генерация увеличенных масок завершена.")
        except Exception as e:
            self.finished.emit(False, f"Ошибка: {str(e)}")

    def process(self):
        # Чтение CSV
        self.log.emit(f"Чтение CSV: {self.csv_path}")
        if not os.path.isfile(self.csv_path):
            raise Exception("CSV файл не найден.")

        # Группировка записей по маске
        mask_records = {}
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            header = f.readline().strip().split(',')
            if len(header) < 6:
                raise Exception("CSV должен содержать колонки: mask,background,bg_x,bg_y,mask_x,mask_y")
            for line in f:
                parts = line.strip().split(',')
                if len(parts) < 6:
                    continue
                mask_name = parts[0]
                bg_name = parts[1]
                bg_x = int(parts[2])
                bg_y = int(parts[3])
                mask_x = int(parts[4])
                mask_y = int(parts[5])
                mask_records.setdefault(mask_name, []).append((bg_name, bg_x, bg_y, mask_x, mask_y))

        if not mask_records:
            raise Exception("В CSV нет данных.")

        self.log.emit(f"Найдено масок в CSV: {len(mask_records)}")

        # Кеш для увеличенных фонов
        upscaled_bg_cache = {}

        total_masks = len(mask_records)
        for idx, (mask_name, records) in enumerate(mask_records.items()):
            self.log.emit(f"Обработка маски: {mask_name}")

            # Загружаем оригинальную маску (для получения альфа-канала и размеров)
            orig_mask_path = os.path.join(self.original_mask_dir, mask_name)
            if not os.path.isfile(orig_mask_path):
                self.log.emit(f"  Оригинальная маска не найдена: {mask_name}, пропуск.")
                self.update_progress(idx + 1, total_masks)
                continue

            orig_mask = cv2.imread(orig_mask_path, cv2.IMREAD_UNCHANGED)
            if orig_mask is None or orig_mask.shape[2] != 4:
                self.log.emit(f"  Оригинальная маска без альфа-канала или не загружена: {mask_name}, пропуск.")
                self.update_progress(idx + 1, total_masks)
                continue

            h, w = orig_mask.shape[:2]
            new_h, new_w = h * UPSCALE_FACTOR, w * UPSCALE_FACTOR
            new_mask = np.zeros((new_h, new_w, 4), dtype=np.uint8)

            for (bg_name, bg_x, bg_y, mask_x, mask_y) in records:
                # Загружаем увеличенный фон
                if bg_name not in upscaled_bg_cache:
                    bg_path = os.path.join(self.upscaled_bg_dir, bg_name)
                    if not os.path.isfile(bg_path):
                        self.log.emit(f"  Увеличенный фон не найден: {bg_name}, тайл пропущен.")
                        continue
                    bg_img = cv2.imread(bg_path)
                    if bg_img is None:
                        self.log.emit(f"  Не удалось загрузить увеличенный фон: {bg_name}")
                        continue
                    upscaled_bg_cache[bg_name] = bg_img
                else:
                    bg_img = upscaled_bg_cache[bg_name]

                crop_x = bg_x * UPSCALE_FACTOR
                crop_y = bg_y * UPSCALE_FACTOR
                crop_size = TILE_SIZE * UPSCALE_FACTOR
                if crop_x + crop_size > bg_img.shape[1] or crop_y + crop_size > bg_img.shape[0]:
                    self.log.emit(f"  Выход за границы фона для тайла {mask_name} ({bg_x},{bg_y})")
                    continue

                fg_crop = bg_img[crop_y:crop_y+crop_size, crop_x:crop_x+crop_size]

                # Альфа из оригинальной маски
                orig_alpha = orig_mask[mask_y:mask_y+TILE_SIZE, mask_x:mask_x+TILE_SIZE, 3]
                alpha_upscaled = cv2.resize(orig_alpha, (crop_size, crop_size), interpolation=cv2.INTER_NEAREST)

                dst_y = mask_y * UPSCALE_FACTOR
                dst_x = mask_x * UPSCALE_FACTOR
                new_mask[dst_y:dst_y+crop_size, dst_x:dst_x+crop_size, :3] = fg_crop[:, :, :3]
                new_mask[dst_y:dst_y+crop_size, dst_x:dst_x+crop_size, 3] = alpha_upscaled

            output_path = os.path.join(self.output_dir, mask_name)
            cv2.imwrite(output_path, new_mask)
            self.log.emit(f"  Сохранено: {output_path}")

            self.update_progress(idx + 1, total_masks)

        self.log.emit("Генерация всех увеличенных масок завершена.")

    def update_progress(self, current, total):
        percent = int(current * 100 / total)
        self.progress.emit(percent)