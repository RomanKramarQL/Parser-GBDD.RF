import base64
import os
import re

import cv2
import easyocr
import numpy as np


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time


def slove_image():
    image_path = 'captcha_image.jpg'

    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    blurred = cv2.GaussianBlur(img, (1, 1), 0)

    # Применяем threshold
    _, thresh = cv2.threshold(
        blurred, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    kernel = np.ones((3, 3), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)  # Удаляет мелкий шум
    # Утончение символов (если они слиплись)
    kernel = np.ones((2, 2), np.uint8)
    eroded = cv2.erode(cleaned, kernel, iterations=1)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(eroded, connectivity=8)
    for i in range(1, n_labels):
        if stats[i, cv2.CC_STAT_AREA] < 100:  # Удаляем объекты площадью <30 пикселей
            eroded[labels == i] = 0

    # Сохраняем обработанное изображение
    processed_path = "processed_" + image_path
    cv2.imwrite(processed_path, eroded)
    reader = easyocr.Reader(['en'])
    results = reader.readtext(eroded, allowlist='0123456789', detail=0)
    return results


def check_driver_license(license_number, issue_date, max_attempts=10):
    # Настройка драйвера Chrome
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')  # Работа в фоновом режиме (без открытия браузера)
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # Инициализация драйвера
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        # Открытие сайта
        driver.get('https://xn--90adear.xn--p1ai/check/driver#')

        # Ожидание загрузки страницы
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'checkDriverNum'))
        )

        # Ввод серии и номера водительского удостоверения
        num_input = driver.find_element(By.ID, 'checkDriverNum')
        num_input.clear()
        num_input.send_keys(license_number)
        time.sleep(3)

        # Ввод даты выдачи
        date_input = driver.find_element(By.ID, 'checkDriverDate')
        date_input.clear()
        date_input.send_keys(issue_date)

        # Нажатие кнопки "запросить проверку"
        check_button = driver.find_element(By.CSS_SELECTOR, 'a.checker[data-type="driver"]')
        check_button.click()

        attempt = 1
        success = False

        while attempt <= max_attempts and not success:
            print(f"Попытка {attempt}/{max_attempts}")

            # Ожидание появления капчи
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'img[src^="data:image"]'))
                )
            except:
                print("Капча не появилась, пробуем снова")
                check_button.click()
                time.sleep(3)
                attempt += 1
                continue

            try:
                # Скачивание и сохранение изображения капчи
                img_element = driver.find_element(By.CSS_SELECTOR, 'img[src^="data:image"]')
                img_src = img_element.get_attribute('src')

                if img_src.startswith('data:image/jpeg;base64,'):
                    base64_data = img_src.split(',')[1]
                    img_data = base64.b64decode(base64_data)

                    # Сохраняем изображение капчи
                    img_path = f'captcha_image.jpg'
                    with open(img_path, 'wb') as f:
                        f.write(img_data)
                    print(f"Изображение капчи сохранено как {os.path.abspath(img_path)}")

                    # Решаем капчу
                    captcha_text = slove_image()
                    print(f"Распознанный текст капчи: {captcha_text}")

                    # Вводим решение капчи
                    captcha_input = driver.find_element(By.NAME, 'captcha_num')
                    captcha_input.clear()
                    captcha_input.send_keys(captcha_text)

                    # Нажимаем кнопку отправки капчи
                    submit_button = driver.find_element(By.ID, 'captchaSubmit')
                    submit_button.click()
                    print("Капча отправлена")

                    # Проверяем наличие элемента с датой выдачи
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH,
                                                            f'//li/span[@class="caption"][contains(text(), "Дата выдачи:")]/following-sibling::span[@class="field doc-date"][contains(text(), "{issue_date}")]'))
                        )
                        success = True
                        print("Успешно! Найдена дата выдачи.")
                        os.remove(img_path)
                        break
                    except:
                        print("Дата выдачи не найдена, пробуем снова")
                        attempt += 1
                        os.remove(img_path)

                        # Проверяем наличие сообщения о том, что данные не найдены
                        try:
                            error_message = driver.find_element(By.CSS_SELECTOR, 'p.check-space.check-message')
                            if "не были найдены сведения" in error_message.text:
                                print("Сведения не найдены, завершаем проверку")
                                break
                        except:
                            # Если сообщение не найдено, продолжаем попытки
                            pass

                        # Если сообщение не появилось, пробуем снова
                        check_button = driver.find_element(By.CSS_SELECTOR, 'a.checker[data-type="driver"]')
                        check_button.click()
                        time.sleep(5)
                        continue

            except Exception as e:
                print(f"Ошибка при обработке капчи: {e}")
                attempt += 1
                continue

        if not success:
            print(f"Не удалось пройти проверку после {max_attempts} попыток")
            driver.quit()
            return

        # Сохранение HTML страницы с результатами
        with open('result.txt', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)

        print("Проверка выполнена. Результаты сохранены в result.txt")

        # Обработка результата и сохранение в отформатированном виде
        input_file = 'result.txt'
        output_file = 'processed_result.txt'
        with open(input_file, 'r', encoding='utf-8') as file:
            content = file.read()

        # Ищем все строки с нужной структурой
        pattern = re.compile(
            r'<li><span class="caption">([^<]+)</span>&nbsp;<span class="field[^"]*">([^<]+)</span></li>'
        )
        matches = pattern.findall(content)

        # Формируем отформатированные строки
        formatted_lines = []
        for caption, value in matches:
            # Пропускаем скрытые элементы (с display: none)
            if 'display: none' not in caption:
                formatted_lines.append(f"{caption.strip()} {value.strip()}")

        # Записываем результат в новый файл
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write('\n'.join(formatted_lines))

        print("Результаты обработаны и сохранены в processed_result.txt")

    except Exception as e:
        print(f"Произошла ошибка: {e}")
    finally:
        driver.quit()


# Пример использования
if __name__ == "__main__":
    license_number = "99 18 151233"  # Замените на реальные серию и номер
    issue_date = "25.11.2020"  # Замените на реальную дату выдачи

    check_driver_license(license_number, issue_date)