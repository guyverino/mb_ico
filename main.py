import os
import io
import struct
import win32api
import win32con
from PIL import Image, ImageDraw, ImageFont

# ================= КОНФИГУРАЦИЯ =================
INPUT_ICO = r"mb.ico"
OUTPUT_DLL = "mb_ico.dll"

# Настройки цветов
TARGET_COLORS = {
    "green": "#2ecc71",
    "blue": "#3498db",
    "red": "#e74c3c",
    "yellow": "#f1c40f",
    "white": "#ffffff",
    "black": "#000000",
    "pink": "#ff69b4",
    "purple": "#9b59b6",
    "orange": "#e67e22",
    "cyan": "#00bcd4",
    "teal": "#009688",
    "lime": "#cddc39",
    "gray": "#95a5a6",
    "brown": "#795548",
    "darkblue": "#2c3e50"
}

# Настройки шрифта для генерации цифр
FONT_CONFIG = {
    "path": r"C:\Windows\Fonts\impact.ttf", # Варианты: arial.ttf, tahoma.ttf, consola.ttf, times.ttf, cour.ttf, segoeui.ttf
    "size_percent": 70,   # Размер шрифта в процентах от высоты картинки
    "width_compress_percent": 80, # Сжатие шрифта по ширине (100 - нормальная ширина, 50 - уже в 2 раза)
    "x_percent": 96,      # Позиция X (правый край) в процентах от ширины
    "y_percent": 96,      # Позиция Y (нижний край) в процентах от высоты
    "fill_color": "white",
    "stroke_color": "black",
    "stroke_width": 8
}

NUMBERS_RANGE = range(1, 10)
# ================================================

def hex_to_rgb(hex_color):
    """Преобразует hex цвет в RGB кортеж."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def apply_solid_color(img, target_rgb):
    """Применяет сплошной цвет к RGB-каналам, сохраняя оригинальную прозрачность."""
    img = img.convert("RGBA")
    alpha = img.split()[3]
    solid = Image.new("RGB", img.size, target_rgb)
    solid.putalpha(alpha)
    return solid

def generate_number_images(base_size):
    """Генерирует изображения номеров в памяти с нужными размерами и прозрачным фоном."""
    width, height = base_size
    font_size = int(height * (FONT_CONFIG["size_percent"] / 100))
    x_pos = int(width * (FONT_CONFIG["x_percent"] / 100))
    y_pos = int(height * (FONT_CONFIG["y_percent"] / 100))
    compress_ratio = FONT_CONFIG.get("width_compress_percent", 100) / 100.0
    
    try:
        font = ImageFont.truetype(FONT_CONFIG["path"], font_size)
    except IOError:
        print(f"Шрифт {FONT_CONFIG['path']} не найден! Использую шрифт по умолчанию.")
        font = ImageFont.load_default()
        
    num_images = {}
    for i in NUMBERS_RANGE:
        text = str(i)
        
        # Временный холст с запасом размера
        temp_img = Image.new("RGBA", (width * 2, height * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(temp_img)
        
        anchor_x, anchor_y = width, height
        draw.text(
            (anchor_x, anchor_y), 
            text, 
            fill=FONT_CONFIG["fill_color"], 
            stroke_fill=FONT_CONFIG["stroke_color"], 
            stroke_width=FONT_CONFIG["stroke_width"], 
            font=font, 
            anchor="rb"
        )
        
        final_img = Image.new("RGBA", base_size, (0, 0, 0, 0))
        bbox = temp_img.getbbox()
        
        if bbox:
            text_crop = temp_img.crop(bbox)
            new_w = max(1, int(text_crop.width * compress_ratio))
            
            # Сжимаем ширину, если нужно
            if compress_ratio != 1.0:
                text_crop = text_crop.resize((new_w, text_crop.height), Image.Resampling.LANCZOS)
                
            # Вычисляем правильную позицию вставки с учетом якоря
            diff_x = anchor_x - bbox[2]
            diff_y = anchor_y - bbox[3]
            
            scaled_diff_x = diff_x * compress_ratio
            paste_x = int(x_pos - scaled_diff_x - new_w)
            paste_y = int(y_pos - diff_y - text_crop.height)
            
            final_img.alpha_composite(text_crop, (paste_x, paste_y))
            
        num_images[str(i)] = final_img
        
    return num_images

def create_dll(dll_name):
    """Создает пустую DLL библиотеку через csc.exe."""
    with open('empty.cs', 'w', encoding='utf-8') as f:
        f.write('public class Empty {}')
    csc_path = r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    os.system(f'"{csc_path}" /target:library /out:{dll_name} empty.cs >nul 2>&1')
    if os.path.exists('empty.cs'): 
        os.remove('empty.cs')
    return os.path.exists(dll_name)

def build_dll_from_memory(dll_name, ico_data_list):
    """Запаковывает список байтовых потоков ICO файлов в DLL."""
    if not create_dll(dll_name):
        print("Не удалось создать DLL файл.")
        return

    print(f"Упаковка {len(ico_data_list)} иконок в DLL...")

    curr_icon_id = 1
    curr_group_id = 1
    
    for data in ico_data_list:
        try:
            num_images = struct.unpack('<H', data[4:6])[0]
            v_group_data = bytearray(data[:6])
            
            handle = win32api.BeginUpdateResource(dll_name, 0)
            
            for i in range(num_images):
                entry_offset = 6 + i * 16
                header_part = data[entry_offset : entry_offset + 12]
                dwOffset = struct.unpack('<I', data[entry_offset + 12 : entry_offset + 16])[0]
                dwBytes = struct.unpack('<I', header_part[8:12])[0]
                img_data = data[dwOffset : dwOffset + dwBytes]
                
                win32api.UpdateResource(handle, win32con.RT_ICON, curr_icon_id, img_data)
                v_group_data.extend(header_part)
                v_group_data.extend(struct.pack('<H', curr_icon_id))
                curr_icon_id += 1
                
            win32api.UpdateResource(handle, win32con.RT_GROUP_ICON, curr_group_id, bytes(v_group_data))
            win32api.EndUpdateResource(handle, 0)
            
            curr_group_id += 1
            
        except Exception as e:
            print(f"Ошибка упаковки иконки ID {curr_group_id}: {e}")

    print(f"[УСПЕХ] DLL собрана: {dll_name}. Итого групп: {curr_group_id - 1}")

def main():
    if not os.path.exists(INPUT_ICO):
        print(f"Входной файл {INPUT_ICO} не найден.")
        return

    print("Извлечение базы 256x256 из оригинальной иконки...")
    with Image.open(INPUT_ICO) as img:
        bg_256 = None
        for i in range(getattr(img, 'n_frames', 1)):
            img.seek(i)
            if img.size == (256, 256):
                bg_256 = img.copy().convert("RGBA")
                break
        
        if not bg_256:
            print("Слой 256x256 не найден, изменяем размер первого слоя...")
            img.seek(0)
            bg_256 = img.copy().convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS)
            
    print("Создание цифровых оверлеев...")
    num_overlays = generate_number_images((256, 256))
    
    ico_byte_streams = []
    
    print("Добавление оригинальной иконки и её версий с цифрами...")
    buf = io.BytesIO()
    bg_256.save(buf, format='ICO', sizes=[(256, 256)])
    ico_byte_streams.append(buf.getvalue())
    
    for i in NUMBERS_RANGE:
        num_img = num_overlays[str(i)]
        final = bg_256.copy()
        final.alpha_composite(num_img)
        
        buf = io.BytesIO()
        final.save(buf, format='ICO', sizes=[(256, 256)])
        ico_byte_streams.append(buf.getvalue())
    
    print("Применение цветов и цифр, создание ICO буферов...")
    for color_name, hex_color in TARGET_COLORS.items():
        # Создаем базовую цветную иконку
        target_rgb = hex_to_rgb(hex_color)
        colored_base = apply_solid_color(bg_256, target_rgb)
        
        # Сохраняем иконку без цифры
        buf = io.BytesIO()
        colored_base.save(buf, format='ICO', sizes=[(256, 256)])
        ico_byte_streams.append(buf.getvalue())
        
        # Сохраняем иконку с каждой цифрой
        for i in NUMBERS_RANGE:
            num_img = num_overlays[str(i)]
            final = colored_base.copy()
            final.alpha_composite(num_img)
            
            buf = io.BytesIO()
            final.save(buf, format='ICO', sizes=[(256, 256)])
            ico_byte_streams.append(buf.getvalue())
            
    # Записываем все в DLL
    if os.path.exists(OUTPUT_DLL):
        try:
            os.remove(OUTPUT_DLL)
        except OSError:
            pass
            
    build_dll_from_memory(OUTPUT_DLL, ico_byte_streams)
    print("Обработка завершена! Все операции выполнены в памяти.")

if __name__ == "__main__":
    main()
