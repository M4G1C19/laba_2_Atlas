from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.common.exceptions import TimeoutException
import datetime
import pandas as pd

LOG_FILENAME = "parser_log.txt"

def time_logger(func):
    def inner(*args, **kwargs):
        t_start = time.time()
        t_stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        with open(LOG_FILENAME, "a", encoding="utf-8") as log:
            log.write(f"[{t_stamp}] Start: {func.__name__}\n")
        
        try:
            output = func(*args, **kwargs)
            return output
        finally:
            elapsed = time.time() - t_start
            t_stamp_end = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(LOG_FILENAME, "a", encoding="utf-8") as log:
                log.write(f"[{t_stamp_end}] Finish: {func.__name__} | Time: {elapsed:.2f} s.\n\n")
    
    return inner

class AtlasScraper:
    @time_logger
    def __init__(self, target_url, city_from, city_to):
        self.target_url = target_url
        
        browser_opts = Options()
        
        self.web_driver = webdriver.Firefox(options=browser_opts)
        
        self.web_driver.get(self.target_url)
        
        self.city_from = city_from
        self.city_to = city_to
        
        self.dep_times = []
        self.arr_times = []
        self.route_pairs = []
        self.final_data = {}

    @time_logger
    def close_cookie_banner(self):
        try:
            cookie_btn = WebDriverWait(self.web_driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'cm__btn'))
            )
            cookie_btn.click()
            print("Cookie accepted.")
            time.sleep(1)
        except TimeoutException:
            print("Element '.cm__btn' not found, continuing...")

    @time_logger
    def scrape_schedule(self):
        start_day = datetime.datetime.strptime('2026-11-14', '%Y-%m-%d')
        date_range = pd.date_range(start=start_day, periods=5, freq='D')
        
        formatted_dates = [d.strftime("%Y-%m-%d") for d in date_range]
        
        for current_date in formatted_dates:
            full_url = f'https://atlasbus.by/Маршруты/{self.city_from}/{self.city_to}?date={current_date}&passengers=1'
            self.web_driver.get(full_url)
            
            self.dep_times.clear()
            self.arr_times.clear()
            
            self.close_cookie_banner()
            
            index = 1
            while index < 50:
                try:
                    dep_text = WebDriverWait(self.web_driver, 0.5).until(
                        lambda d: d.find_element(By.XPATH, f"/html/body/div/div/main/div/div[2]/div[{index}]/div/div[2]/div/div[1]/div/div[1]/div/div[1]/div[1]").text
                    )
                    if dep_text:
                        self.dep_times.append(dep_text)
                except Exception:
                    try:
                        dep_text = WebDriverWait(self.web_driver, 0.5).until(
                            lambda d: d.find_element(By.XPATH, f"/html/body/div/div/main/div/div[2]/div[{index}]/div/div[1]/div/div[1]/div/div[1]/div[1]").text
                        )
                        if dep_text:
                            self.dep_times.append(dep_text)
                    except TimeoutException:
                        index += 1
                        continue

                try:
                    arr_text = WebDriverWait(self.web_driver, 0.5).until(
                        lambda d: d.find_element(By.XPATH, f"/html/body/div/div/main/div/div[2]/div[{index}]/div/div[2]/div/div[1]/div/div[2]/div/div[1]/div").text
                    )
                    if arr_text:
                        self.arr_times.append(arr_text)
                except Exception:
                    try:
                        arr_text = WebDriverWait(self.web_driver, 0.5).until(
                            lambda d: d.find_element(By.XPATH, f"/html/body/div/div/main/div/div[2]/div[{index}]/div/div[1]/div/div[2]/div/div[1]/div").text
                        )
                        if arr_text:
                            self.arr_times.append(arr_text)
                    except TimeoutException:
                        index += 1
                        continue
                
                index += 1

            self.route_pairs.clear()
            for j in range(len(self.dep_times)):
                self.route_pairs.append(f'{self.dep_times[j]}-{self.arr_times[j]}')

            self.final_data[current_date] = self.route_pairs

        output_df = pd.DataFrame(self.final_data)
        output_df.to_csv(f'res{self.city_from}-{self.city_to}.csv', index=0)

    @time_logger
    def __del__(self):
        print("Finished.")


def main():
    target_cities = ['Гродно', 'Витебск']
    
    for destination in target_cities:
        forward_parser = AtlasScraper(
            'https://atlasbus.by/',
            'Минск',
            destination
        )
        forward_parser.scrape_schedule()

        backward_parser = AtlasScraper(
            'https://atlasbus.by/',
            destination,
            'Минск'
        )
        backward_parser.scrape_schedule()


if __name__ == "__main__":
    main()