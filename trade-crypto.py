import base64, hashlib, hmac, math, sys, time, urllib.parse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import scipy
import seaborn as sns
import statsmodels as sm
from statsmodels.tsa.stattools import adfuller

api_url = "https://api.binance.us"
api_key='6SNpMwb70FD780Sa9hSFQ8uLueYQoFHl6UIx8KjwhfM8JNGOiALFcePydTQCuTX4'
secret_key='61Kte2mrVs1ZthYaFN3faODVgtbgMSynVJJI737F35TXYCzDKAJU6QzNmgCaOm8f'

# get binanceus signature
def get_binanceus_signature(data, secret):
    postdata = urllib.parse.urlencode(data)
    message = postdata.encode()
    byte_key = bytes(secret, 'UTF-8')
    mac = hmac.new(byte_key, message, hashlib.sha256).hexdigest()
    return mac

# Attaches auth headers and returns results of a POST request
def binanceus_request(uri_path, data, api_key, api_sec):
    headers = {}
    headers['X-MBX-APIKEY'] = api_key
    signature = get_binanceus_signature(data, api_sec) 
    params={
        **data,
        "signature": signature,
        }           
    req = requests.get((api_url + uri_path), params=params, headers=headers)
    return req

def binanceus_trade_request(uri_path, data, api_key, api_sec):
    headers = {}
    headers['X-MBX-APIKEY'] = api_key
    signature = get_binanceus_signature(data, api_sec) 
    payload={
        **data,
        "signature": signature,
        }           
    req = requests.post((api_url + uri_path), headers=headers, data=payload)
    return req

def get_current_price(symbol):
    uri_path = 'https://api.binance.com/api/v3/ticker/price'
    params = {
        'symbol': symbol
    }
    resp = requests.get(uri_path, params=params)
    return resp.json()['price']


def get_trade_info(first_asset_symbol, second_asset_symbol):
    url = 'https://api.binance.com/api/v3/klines'
    params = {
        'symbol': second_asset_symbol + 'USDT',
        'interval': '1m',
        'limit': '1000'
    }
    columns=[
    'Open Time', 'Open Price', 'High Price', 'Low Price', 'Close Price', 'Volume',
    'Close Time', 'Quote Asset Volume', 'Number of Trades', 'Taker Buy Base Asset Volume',
    'Taker Buy Quote Asset Volume', 'Ignore'
    ]
    resp = requests.get(url, params=params)
    df_btc = pd.DataFrame(data=resp.json(), columns=columns)
    params['symbol'] = first_asset_symbol + 'USDT'
    resp = requests.get(url, params=params)
    df_eth = pd.DataFrame(data=resp.json(), columns=columns)
    Xmins = df_btc['Open Price'].astype(float)
    Ymins = df_eth['Open Price'].astype(float)
    adjusted_Xmins = Xmins.divide(pd.Series.max(Xmins))
    adjusted_Ymins = Ymins.divide(pd.Series.max(Ymins))
    adjusted_btc_eth = adjusted_Xmins.subtract(adjusted_Ymins)
    adjusted_btc_eth_z = scipy.stats.zscore(adjusted_btc_eth)
    latest_zscore = adjusted_btc_eth_z.iloc[-1]
    return latest_zscore

def get_balances(first_asset, second_asset):
    uri_path = "/api/v3/account"
    data = {
        "timestamp": int(round(time.time() * 1000))
    }
    get_account_result = binanceus_request(uri_path, data, api_key, secret_key)
    for asset in get_account_result.json()['balances']:
        if asset['asset'] == first_asset:
            first_asset_balance = float(asset['free'])
        elif asset['asset'] == second_asset:
            second_asset_balance = float(asset['free'])
    balance_data = {
        'first_asset': first_asset_balance,
        'second_asset': second_asset_balance
    }
    return balance_data

def trade(amount, side, symbol):
    uri_path = "/api/v3/order"
    data = {
        'symbol': symbol,
        'side': side,
        'type': 'MARKET',
        'quantity': str(math.trunc(amount * 10000) / 10000),
        'timestamp': int(round(time.time() * 1000)) 
    }
    result = binanceus_trade_request(uri_path, data, api_key, secret_key)
    return result

def wait_for_z_normalization(sign, first_asset_symbol, second_asset_symbol):
    z_score = get_trade_info(first_asset_symbol=first_asset_symbol, second_asset_symbol=second_asset_symbol)
    if sign == 'POSITIVE':
        while z_score > 0.5:
            z_score = get_trade_info()
            print("Current Z-Score: " + str(z_score))
            time.sleep(1000)
        return
    else:
        while z_score < -0.5:
            z_score = get_trade_info()
            print("Current Z-Score: " + str(z_score))
            time.sleep(1000)
        return

def z_based_trade(sign, first_asset_symbol, second_asset_symbol):
    balances = get_balances(first_asset_symbol, second_asset_symbol)
    second_asset_balance = balances['second_asset']
    resp = trade(amount=second_asset_balance, side='SELL', symbol=second_asset_symbol + 'USDT')
    if resp.status_code == 200:
        print('Successfully SOLD ' + str(second_asset_balance) + ' ' + str(second_asset_symbol))
        time.sleep(60)
        second_asset_price = get_current_price(symbol=second_asset_symbol + 'USDT')
        cash_amount = second_asset_balance * float(second_asset_price)
        first_asset_price = get_current_price(symbol=first_asset_symbol + 'USDT')
        first_asset_to_buy = cash_amount / float(first_asset_price) * 1.02
        resp = trade(amount=first_asset_to_buy, side='BUY', symbol=first_asset_symbol + 'USDT')
        if resp.status_code == 200:
            print('Successfully BOUGHT ' + str(first_asset_to_buy) + ' ' + str(first_asset_symbol))
            time.sleep(60)
            print('Waiting for Z-Score Normalization...')
            wait_for_z_normalization(sign=sign, first_asset_symbol=first_asset_symbol, second_asset_symbol=second_asset_symbol)
            resp = trade(amount=first_asset_to_buy, side='SELL', symbol=first_asset_symbol + 'USDT')
            if resp.status_code == 200:
                print('Successfully SOLD ' + str(first_asset_to_buy) + ' ' + str(first_asset_symbol))
            else:
                print(resp.json())
        else:
            print(resp.json())
    else:
        print('Balance of ' + str(second_asset_balance) + second_asset_symbol + ' Not Sufficient For Trade...')

def wait_for_trades(first_asset_symbol, second_asset_symbol):
    while True:
        latest_zscore = get_trade_info(first_asset_symbol=first_asset_symbol, second_asset_symbol=second_asset_symbol)
        if latest_zscore > 2.0:
            z_based_trade(sign='POSITIVE', first_asset_symbol=first_asset_symbol, second_asset_symbol=second_asset_symbol)
        elif latest_zscore < -2.0:
            z_based_trade(sign='NEGATIVE', first_asset_symbol=first_asset_symbol, second_asset_symbol=second_asset_symbol)
        else:
            print('......................................')
            print('Evaluating: No Current Trades...')
            print('Current Z-Score: ' + str(latest_zscore))
            print()
        for remaining in range(60, 0, -1):
            sys.stdout.write("\r")
            sys.stdout.write("{:2d} seconds remaining.".format(remaining)) 
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write("\rComplete!            \n")

wait_for_trades(first_asset_symbol=sys.argv[1], second_asset_symbol=sys.argv[2])
