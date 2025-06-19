import base64
import os
import re
import random
import json
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

# Файлы для хранения списков
BLACKLIST_FILE = 'blacklist.json'
WHITELIST_FILE = 'whitelist.json'
VALID_RESULTS_FILE = 'valid_results.txt'


def load_list(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"entries": []}


def save_list(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def is_in_blacklist(license_number, issue_date):
    blacklist = load_list(BLACKLIST_FILE)
    for entry in blacklist["entries"]:
        if entry["license_number"] == license_number and entry["issue_date"] == issue_date:
            return True
    return False


def is_in_whitelist(license_number, issue_date):
    whitelist = load_list(WHITELIST_FILE)
    for entry in whitelist["entries"]:
        if entry["license_number"] == license_number and entry["issue_date"] == issue_date:
            return True
    return False


def add_to_blacklist(license_number, issue_date):
    blacklist = load_list(BLACKLIST_FILE)
    if not is_in_blacklist(license_number, issue_date):
        blacklist["entries"].append({
            "license_number": license_number,
            "issue_date": issue_date
        })
        save_list(BLACKLIST_FILE, blacklist)


def add_to_whitelist(license_number, issue_date, data):
    whitelist = load_list(WHITELIST_FILE)
    if not is_in_whitelist(license_number, issue_date):
        whitelist["entries"].append({
            "license_number": license_number,
            "issue_date": issue_date,
            "data": data
        })
        save_list(WHITELIST_FILE, whitelist)

        with open(VALID_RESULTS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"License: {license_number}, Date: {issue_date}\n")
            for line in data:
                f.write(f"{line}\n")
            f.write("\n")


def generate_license_number(issue_date):
    while True:
        part1 = random.randint(10, 99)
        part2 = random.randint(10, 99)
        part3 = random.randint(100000, 999999)
        license_number = f"{part1} {part2} {part3}"
        if not is_in_blacklist(license_number, issue_date):
            return license_number


def solve_image():
    image_path = 'captcha_image.jpg'
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    blurred = cv2.GaussianBlur(img, (1, 1), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    kernel = np.ones((2, 2), np.uint8)
    eroded = cv2.erode(cleaned, kernel, iterations=1)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(eroded, connectivity=8)
    for i in range(1, n_labels):
        if stats[i, cv2.CC_STAT_AREA] < 100:
            eroded[labels == i] = 0

    processed_path = "processed_" + image_path
    cv2.imwrite(processed_path, eroded)
    reader = easyocr.Reader(['en'])
    results = reader.readtext(eroded, allowlist='0123456789', detail=0)
    return results


def process_page_content(content):
    pattern = re.compile(
        r'<li><span class="caption">([^<]+)</span>&nbsp;<span class="field[^"]*">([^<]+)</span></li>'
    )
    matches = pattern.findall(content)
    formatted_lines = []
    for caption, value in matches:
        if 'display: none' not in caption:
            formatted_lines.append(f"{caption.strip()} {value.strip()}")
    return formatted_lines


def check_driver_license(issue_date, max_attempts=10):
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        license_number = generate_license_number(issue_date)

        while True:
            print(f"\nПроверка для номера: {license_number} и даты: {issue_date}")

            if is_in_whitelist(license_number, issue_date):
                print("Эта комбинация уже есть в whitelist, пропускаем")
                license_number = generate_license_number(issue_date)
                continue

            driver.get('https://xn--90adear.xn--p1ai/check/driver#')
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'checkDriverNum'))
            )

            # Ввод данных
            num_input = driver.find_element(By.ID, 'checkDriverNum')
            num_input.clear()
            num_input.send_keys('99 18 151233')
            time.sleep(2)

            date_input = driver.find_element(By.ID, 'checkDriverDate')
            date_input.clear()
            date_input.send_keys(issue_date)
            time.sleep(1)

            check_button = driver.find_element(By.CSS_SELECTOR, 'a.checker[data-type="driver"]')
            check_button.click()

            attempt = 1
            captcha_solved = False
            data_found = False

            while attempt <= max_attempts and not captcha_solved and not data_found:
                print(f"Попытка решения капчи {attempt}/{max_attempts}")

                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'img[src^="data:image"]'))
                    )
                except:
                    print("Капча не появилась, пробуем снова")
                    attempt += 1
                    check_button.click()
                    continue

                try:
                    img_element = driver.find_element(By.CSS_SELECTOR, 'img[src^="data:image"]')
                    img_src = img_element.get_attribute('src')

                    if img_src.startswith('data:image/jpeg;base64,'):
                        base64_data = img_src.split(',')[1]
                        img_data = base64.b64decode(base64_data)

                        img_path = 'captcha_image.jpg'
                        with open(img_path, 'wb') as f:
                            f.write(img_data)

                        captcha_text = solve_image()
                        print(f"Распознанный текст капчи: {captcha_text}")

                        captcha_input = driver.find_element(By.NAME, 'captcha_num')
                        captcha_input.clear()
                        captcha_input.send_keys(captcha_text)

                        submit_button = driver.find_element(By.ID, 'captchaSubmit')
                        submit_button.click()
                        print("Капча отправлена")

                        # Проверяем результат после отправки капчи
                        try:
                            # Проверяем наличие элемента "Выполняется запрос" и ждем его исчезновения
                            try:
                                WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located(
                                        (By.XPATH, '//span[contains(text(), "Выполняется запрос")]'))
                                )
                                print("Ожидаем завершения запроса...")
                                WebDriverWait(driver, 30).until(
                                    EC.invisibility_of_element_located(
                                        (By.XPATH, '//span[contains(text(), "Выполняется запрос")]'))
                                )
                            except:
                                pass  # Элемент "Выполняется запрос" не найден, продолжаем

                            # Теперь проверяем результат капчи и наличие данных
                            try:
                                # Сначала проверяем наличие элемента с датой выдачи
                                WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located((By.XPATH,
                                                                    f'//li/span[@class="caption"][contains(text(), "Дата выдачи:")]/following-sibling::span[@class="field doc-date"][contains(text(), "{issue_date}")]'))
                                )
                                print("Капча решена успешно, данные найдены")
                                captcha_solved = True
                                os.remove(img_path)

                                # Обрабатываем найденные данные
                                page_content = driver.page_source
                                formatted_data = process_page_content(page_content)
                                add_to_whitelist(license_number, issue_date, formatted_data)
                                data_found = True

                                # Генерируем новый номер для следующей итерации
                                license_number = generate_license_number(issue_date)
                                break

                            except:
                                # Если элемент с датой не найден, проверяем сообщение об ошибке
                                try:
                                    error_message = WebDriverWait(driver, 3).until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, 'p.check-space.check-message'))
                                    )
                                    if "не были найдены сведения" in error_message.text:
                                        print("Капча решена успешно, но данные не найдены")
                                        captcha_solved = True
                                        os.remove(img_path)
                                        add_to_blacklist(license_number, issue_date)
                                        data_found = True

                                        # Генерируем новый номер для следующей итерации
                                        license_number = generate_license_number(issue_date)
                                        break

                                except:
                                    # Если ни один из элементов не найден - капча решена неверно
                                    print("Капча решена неверно, пробуем снова")
                                    attempt += 1
                                    try:
                                        os.remove(img_path)
                                    except:
                                        pass

                                    # Повторно нажимаем кнопку проверки
                                    check_button = driver.find_element(By.CSS_SELECTOR, 'a.checker[data-type="driver"]')
                                    check_button.click()
                                    continue

                        except Exception as e:
                            print(f"Ошибка при проверке результата: {e}")
                            attempt += 1
                            check_button.click()
                            continue

                except Exception as e:
                    print(f"Ошибка при обработке капчи: {e}")
                    attempt += 1
                    check_button.click()
                    continue

            if not captcha_solved and not data_found:
                print(f"Не удалось решить капчу после {max_attempts} попыток для номера {license_number}")
                license_number = generate_license_number(issue_date)

    except Exception as e:
        print(f"Произошла ошибка: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    issue_date = "25.11.2020"  # Укажите нужную дату выдачи
    check_driver_license(issue_date)
