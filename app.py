#!/usr/bin/env python

import os
from os.path import join, dirname
import smtplib
import pandas as pd
import requests
from bs4 import BeautifulSoup
from price_parser import Price
from dotenv import load_dotenv
import time
import random
from termcolor import colored
import logging

os.system('color')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%I:%M:%S')

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

HEADERS = {
    'User-Agent': ( 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0'
                    'AppleWebKit/537.36 (KHTML, like Gecko)'
                    'Chrome/114.0.0.0 Safari/537.36'),
    'Accept-Language': 'en-US, en;q=0.5'
}
PRODUCT_URL_CSV = "products.csv"
SAVE_TO_CSV = True
PRICES_CSV = "prices.csv"
SEND_MAIL = True
ALERT_PRICE_INDEX = 1
ALERT_INDEX = 4

def get_urls(csv_file):
    df = pd.read_csv(csv_file)
    return df

def process_products(df):
    updated_products = []
    for product in df.to_dict("records"):
        html = get_response(product["URL"])
        store = product["URL"].split('.', 2)[1]
        product["TITLE"] = get_title(html, store)
        product["PRICE"] = get_price(html, store)
        product["ALERT"] = product["PRICE"] < product["ALERT_PRICE"]
        updated_products.append(product)
    return pd.DataFrame(updated_products)

def get_response(url):
    response = requests.get(url, headers=HEADERS)
    return response.text

def get_price(html, store):
    soup = BeautifulSoup(html, "lxml")

    if store == "amazon":
        element1 = soup.find('span', {'class':"a-price-whole"}).text.strip()
        element2 = soup.find('span', {'class':"a-price-fraction"}).text.strip()
        price = Price.fromstring(element1 + element2)
    elif store == "newegg":
        element = soup.find('li', {'class':"price-current"}).text.strip()
        price = Price.fromstring(element)
    elif store == "bhphotovideo":
        element = soup.find('div', {'data-selenium':'pricingPrice'}).text.strip()
        price = Price.fromstring(element)
    elif store == "bestbuy":
        element = soup.find('div', {'class':'priceView-hero-price priceView-customer-price'}).text.strip()
        price = Price.fromstring(element)
    elif store == "centralcomputer":
        element = soup.find('span', {'class':'price'}).text.strip()
        price = Price.fromstring(element)

    return price.amount_float

def get_title(html, store):
    soup = BeautifulSoup(html, "lxml")
    if store == "amazon":
        title = soup.find('span', {'id':'productTitle'}).text.strip()
    elif store == "newegg":
        title = soup.find('h1', {'class':'product-title'}).text.strip()
    elif store == "bhphotovideo":
        title = soup.find('h1', {'data-selenium':'productTitle'}).text.strip()
    elif store == "bestbuy":
        title = soup.find('div', {'class':'sku-title'}).text.strip()
    elif store == "centralcomputer":
        title = soup.find('div', {'class':'productname'}).text.strip()
    return title

def get_mail(df):
    subject = "Price Drop on Tracked Item"
    mail_body = get_message(df)
    subject_and_message = f"Subject:{subject}\n\n{mail_body}".encode('utf-8')
    return subject_and_message

def send_mail(df):
    if df.empty:
        return
    
    message_text = get_mail(df)
    with smtplib.SMTP(os.environ.get("MAIL_DOMAIN"), 587) as smtp:
        smtp.starttls()
        smtp.login(os.environ.get("MAIL_USER"), os.environ.get("MAIL_PASS"))
        smtp.sendmail(os.environ.get("MAIL_USER"), os.environ.get("MAIL_TO"), message_text)

def get_message(df):
    body = ""
    mail_body = ""

    # Formatting data in dataframe to be able to display it properly
    list_of_data = df.values.tolist()
    total_rows = len(list_of_data)
    for element in list_of_data:
        del element[ALERT_PRICE_INDEX]
        del element[ALERT_INDEX-1]
    column_names = list(df)
    column_names.pop()
    del column_names[1]
    total_datas = len(column_names)

    # Display data in terminal and email
    row_index = 0
    while row_index < total_rows:
        data_index = 0
        
        while data_index < total_datas:
            body += f"{column_names[data_index] + ':':<8}" + str(list_of_data[row_index][data_index]) + "\n"
            data_index += 1

        if list_of_data[row_index][2] < df["ALERT_PRICE"].values[row_index]:
            print(colored(body, 'light_green', attrs=["bold"]))
            mail_body += body
        elif list_of_data[row_index][2] == df["ALERT_PRICE"].values[row_index]:
            print(colored(body, 'light_yellow', attrs=["bold"]))
        else:
            print(colored(body, 'red', attrs=["bold"]))

        body = ""
        row_index += 1

    return mail_body

def main():
    pd.options.display.max_colwidth = 100
    df = get_urls(PRODUCT_URL_CSV)
    df_updated = process_products(df)

    if SAVE_TO_CSV:
        df_updated.to_csv(PRICES_CSV, index=False, mode="a")
    if SEND_MAIL & df_updated.any(axis=None, bool_only=True):
        send_mail(df_updated)
    else:
        get_message(df_updated)

while(True):
    main()
    time_to_wait = random.uniform(2.0, 4.0)*60.0
    # current_time = datetime.now().strftime("%H:%M:%S")
    logging.info("Waiting " + str(round(time_to_wait/60.0, 2)) + " minutes to check again...\n")
    time.sleep(time_to_wait)