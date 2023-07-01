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
        'User-Agent': ( 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0 '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/114.0.0.0 Safari/537.36'),
        'Accept-Language': 'en-US,en;q=0.5'
}

HEADERS_NEW = [{
        'User-Agent': ( 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0'),
        'Accept-Language': 'en-US,en;q=0.5'
    },
    {
        'User-Agent': ( 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7 '
                        'AppleWebKit/605.1.15 (KHTML, like Gecko) '
                        'Version/15.0 Safari/605.1.15'),
        'Accept-Language': 'en-gb'
    },
    {
        'User-Agent': ( 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'),
        'Accept-Language': 'en-US,en;q=0.9'
    }
]
PRODUCT_URL_CSV = "products.csv"
SAVE_TO_CSV = True
PRICES_CSV = "prices.csv"
SEND_MAIL = True
ALERT_PRICE_INDEX = 1
CHECK_STOCK_INDEX = 2
STOCK_INDEX = 3
ALERT_INDEX = 6

# duplicate_stores = []

def get_urls(csv_file):
    df = pd.read_csv(csv_file)
    return df

def process_products(df):
    updated_products = []
    for product in df.to_dict("records"):
        store = product["URL"].split('.', 2)[1]
        html = get_response(product["URL"], store)
        product["TITLE"] = get_title(html, store)
        product["PRICE"] = get_price(html, store)

        if product["CHECK_STOCK"]:
            product["STOCK"] = get_stock(html, store)
        else:
            product["STOCK"] = None

        product["ALERT"] = product["PRICE"] < product["ALERT_PRICE"]
        updated_products.append(product)
    return pd.DataFrame(updated_products)

def get_response(url, store):
    # if store in duplicate_stores:
    #     wait
    header = HEADERS_NEW[random.randint(0,2)]
    response = requests.get(url, headers=header)
    # duplicate_stores.append(store)
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
    elif store == "gamenerdz":
        element = soup.find('span', {'class':'price price--withoutTax'}).text.strip()
        price = Price.fromstring(element)
    elif store == "walmart":
        element = soup.find('span', {'itemprop':'price'}).text.strip()
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
    elif store == "gamenerdz":
        title = soup.find('h1', {'class':'productView-title'}).text.strip()
    elif store == "walmart":
        title = soup.find('h1', {'itemprop':'name'}).text.strip()
    return title

def get_stock(html, store):
    soup = BeautifulSoup(html, "lxml")
    if store == "bestbuy":
        stock = soup.find('div', {'class':'fulfillment-add-to-cart-button'}).text.strip()
        if stock != "Coming Soon" and stock != "Sold Out":
            stock = True
        else:
            stock = False
    elif store == "gamenerdz":
        stock = soup.find('a', {'data-type':'restock'}).text.strip()
        if stock != "Set Restock Notification":
            stock = True
        else:
            stock = False
    else:
        stock = None
    return stock

def get_mail(df):
    subject = "Price/Stock Change Detected"
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

    # Must remove index in order of lowest to highest since list is changing. Pop removes alert
    for element in list_of_data:
        del element[CHECK_STOCK_INDEX]
        del element[ALERT_PRICE_INDEX]
        element.pop()
        if element[STOCK_INDEX] == None:
            element[STOCK_INDEX] = "N/A"
    
    column_names = list(df)
    column_names = format_columns(column_names)
    total_datas = len(column_names)

    # Display data in terminal and email
    row_index = 0
    while row_index < total_rows:
        data_index = 0
        
        while data_index < total_datas:
            body += f"{column_names[data_index] + ':':<8}" + str(list_of_data[row_index][data_index]) + "\n"
            data_index += 1

        # If current price less than desired price then green and mail
        if list_of_data[row_index][2] < df["ALERT_PRICE"].values[row_index]:
            print(colored(body, 'light_green', attrs=["bold"]))
            mail_body += body
        # If product is in stock then green and email, but only for certain products
        elif list_of_data[row_index][3] == True:
            print(colored(body, 'light_green', attrs=["bold"]))
            mail_body += body
        elif list_of_data[row_index][2] == df["ALERT_PRICE"].values[row_index]:
            print(colored(body, 'light_yellow', attrs=["bold"]))
        else:
            print(colored(body, 'red', attrs=["bold"]))

        body = ""
        row_index += 1

    return mail_body

def format_columns(columns):
    column_names = [name for name in columns if not ("ALERT_PRICE" in name or "CHECK_STOCK" in name or "ALERT" in name)]
    return column_names

def main():
    pd.options.display.max_colwidth = 100
    df = get_urls(PRODUCT_URL_CSV)
    try:
        df_updated = process_products(df)
    except Exception as e:
        logging.error(e)
        time_to_wait = random.uniform(25.5, 35.5)
        print(f'\nRetrying in {time_to_wait} seconds...')
        time.sleep(time_to_wait)
        df_updated = process_products(df)

    if SAVE_TO_CSV:
        df_updated.to_csv(PRICES_CSV, index=False)
    # Check if send_mail is set to true and if alert or in stock stock is true
    if SEND_MAIL & (df_updated["ALERT"].any(axis=None) == True or df_updated["STOCK"].any(axis=None) == True):
        send_mail(df_updated)
    else:
        get_message(df_updated)

while(True):
    main()
    time_to_wait = random.uniform(5.5, 15.5)*60.0
    logging.info("Waiting " + str(round(time_to_wait/60.0, 2)) + " minutes to check again...\n")
    time.sleep(time_to_wait)