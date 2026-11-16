from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import TimeoutException
import datetime
import pandas as pd

LOG_FILENAME = "parsering_log.txt"

def time_logger(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        start_stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        with open(LOG_FILENAME, "a", encoding="utf-8") as log_file:
            log_file.write(f"[{start_stamp}] Start: {func.__name__}\n")
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = time.time()
            end_stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            duration = end_time - start_time
            with open(LOG_FILENAME, "a", encoding="utf-8") as log_file:
                log_file.write(f"[{end_stamp}] Finish: {func.__name__} | Time: {duration:.2f} s.\n\n")
    
    return wrapper


class AtlasScraper:
    @time_logger
    def __init__(self, target_url, city_from, city_to):
        self.target_url = target_url
        self.city_from = city_from
        self.city_to = city_to
        
        options = Options()
        self.driver = webdriver.Firefox(options=options)
        self.driver.get(self.target_url)
        
        self.departure_times = []
        self.arrival_times = []
        self.all_data = {}

    @time_logger
    def close_cookie_banner(self):
        try:
            cookie_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'cm__btn'))
            )
            cookie_button.click()
            time.sleep(1)
        except TimeoutException:
            pass

    @time_logger
    def scrape_schedule(self, start_offset_days=1):
        start_date = datetime.datetime.now() + datetime.timedelta(days=start_offset_days)
        date_range = pd.date_range(start=start_date, periods=5, freq='D')
        
        for current_date in date_range:
            date_string = current_date.strftime("%Y-%m-%d")
            url = f'https://atlasbus.by/Маршруты/{self.city_from}/{self.city_to}?date={date_string}&passengers=1'
            self.driver.get(url)
            
            time.sleep(2)
            
            self.departure_times = []
            self.arrival_times = []
            
            self.close_cookie_banner()
            
            row_index = 1
            while row_index < 50:
                try:
                    dep_text = WebDriverWait(self.driver, 0.5).until(
                        lambda d: d.find_element(By.XPATH, f"/html/body/div/div/main/div/div[2]/div[{row_index}]/div/div[2]/div/div[1]/div/div[1]/div/div[1]/div[1]").text
                    )
                    if dep_text:
                        self.departure_times.append(dep_text)
                except Exception:
                    try:
                        dep_text = WebDriverWait(self.driver, 0.5).until(
                            lambda d: d.find_element(By.XPATH, f"/html/body/div/div/main/div/div[2]/div[{row_index}]/div/div[1]/div/div[1]/div/div[1]/div[1]").text
                        )
                        if dep_text:
                            self.departure_times.append(dep_text)
                    except TimeoutException:
                        row_index += 1
                        continue

                try:
                    arr_text = WebDriverWait(self.driver, 0.5).until(
                        lambda d: d.find_element(By.XPATH, f"/html/body/div/div/main/div/div[2]/div[{row_index}]/div/div[2]/div/div[1]/div/div[2]/div/div[1]/div").text
                    )
                    if arr_text:
                        self.arrival_times.append(arr_text)
                except Exception:
                    try:
                        arr_text = WebDriverWait(self.driver, 0.5).until(
                            lambda d: d.find_element(By.XPATH, f"/html/body/div/div/main/div/div[2]/div[{row_index}]/div/div[1]/div/div[2]/div/div[1]/div").text
                        )
                        if arr_text:
                            self.arrival_times.append(arr_text)
                    except TimeoutException:
                        row_index += 1
                        continue
                
                row_index += 1

            trips = []
            for i in range(len(self.departure_times)):
                trips.append(f'{self.departure_times[i]}-{self.arrival_times[i]}')
            
            self.all_data[date_string] = trips
            print(f"Scraped {date_string}: {len(trips)} trips")

        return self.all_data

    @time_logger
    def __del__(self):
        self.driver.quit()


def process_and_link(forward_data, backward_data, route_name):
    print(f"\n--- Processing and linking: {route_name} ---")
    
    def align_lists(data_dict):
        max_len = max(len(v) for v in data_dict.values()) if data_dict else 0
        for key in data_dict:
            while len(data_dict[key]) < max_len:
                data_dict[key].append('')
        return data_dict
    
    align_lists(forward_data)
    align_lists(backward_data)
    
    forward_df = pd.DataFrame(forward_data)
    backward_df = pd.DataFrame(backward_data)
    
    all_tickets = []
    
    for forward_date in forward_df.columns:
        forward_datetime = datetime.datetime.strptime(forward_date, "%Y-%m-%d")
        backward_datetime = forward_datetime + datetime.timedelta(days=7)
        backward_date = backward_datetime.strftime("%Y-%m-%d")
        
        forward_trips = forward_df[forward_date].dropna().tolist()
        
        if backward_date in backward_df.columns:
            backward_trips = backward_df[backward_date].dropna().tolist()
        else:
            backward_trips = []
        
        forward_trips = [trip for trip in forward_trips if trip != '']
        backward_trips = [trip for trip in backward_trips if trip != '']
        
        if not forward_trips and not backward_trips:
            continue
            
        max_len = max(len(forward_trips), len(backward_trips))
        
        for i in range(max_len):
            forward_trip = forward_trips[i] if i < len(forward_trips) else 'No forward trips'
            backward_trip = backward_trips[i] if i < len(backward_trips) else 'No backward trips'
            
            all_tickets.append({
                'Forward Date': forward_date,
                'Forward Trip': forward_trip,
                'Return Date': backward_date,
                'Return Trip': backward_trip
            })
    
    result_df = pd.DataFrame(all_tickets)
    result_df.drop_duplicates(inplace=True)
    result_df.dropna(inplace=True)
    
    output_file = f'{route_name}_билеты.csv'
    result_df.to_csv(output_file, index=0, encoding='utf-8-sig')
    print(f"Saved: {output_file} (total: {len(result_df)} rows)")


def main():
    target_cities = ['Гродно', 'Витебск']
    
    for destination in target_cities:
        route_name = destination
        print(f"PROCESSING ROUTE: {route_name}")
        
        try:
            forward_parser = AtlasScraper('https://atlasbus.by/', 'Минск', destination)
            forward_data = forward_parser.scrape_schedule(start_offset_days=1)
        except Exception as e:
            print(f"ОШИБКА при парсинге {route_name}: {e}")
            continue

        try:
            backward_route = f'{destination}-Минск'
            backward_parser = AtlasScraper('https://atlasbus.by/', destination, 'Минск')
            backward_data = backward_parser.scrape_schedule(start_offset_days=8)
        except Exception as e:
            print(f"ОШИБКА при парсинге {backward_route}: {e}")
            continue
        
        process_and_link(forward_data, backward_data, route_name)
    
    print("ALL DONE!")


if __name__ == "__main__":
    main()