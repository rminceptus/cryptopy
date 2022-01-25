import hashlib
import hmac
import math
import sys
import time
import urllib.parse

import pandas as pd
import pyfiglet
import requests
import scipy
import statsmodels.tsa.stattools as ts

api_url = "https://api.binance.us"
api_key='6SNpMwb70FD780Sa9hSFQ8uLueYQoFHl6UIx8KjwhfM8JNGOiALFcePydTQCuTX4'
secret_key='61Kte2mrVs1ZthYaFN3faODVgtbgMSynVJJI737F35TXYCzDKAJU6QzNmgCaOm8f'

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

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


def get_trade_series(first_asset_symbol, second_asset_symbol):
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
    return Xmins, Ymins


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


def cointegration_test(first_asset_symbol, second_asset_symbol):
    Xmins, Ymins = get_trade_series(first_asset_symbol, second_asset_symbol)
    coint_result = list(ts.coint(Xmins, Ymins, return_results=False))
    return coint_result[1]


def get_asset_list():
    uri_path = "/api/v3/account"
    data = {
        "timestamp": int(round(time.time() * 1000))
    }
    asset_array = []
    try:
        get_account_result = binanceus_request(uri_path, data, api_key, secret_key)
        for asset in get_account_result.json()['balances']:
            asset_array.append(asset['asset'])
    except:
        get_account_result = binanceus_request(uri_path, data, api_key, secret_key)
        for asset in get_account_result.json()['balances']:
            asset_array.append(asset['asset'])
    return asset_array


def get_coint_pairs(asset_symbol):
    asset_list = get_asset_list()
    pairs_list = []
    for asset in asset_list:
        if asset != asset_symbol:
            pair = [asset_symbol, asset]
            pairs_list.append(pair)
    coint_pairs = []
    num_pairs = len(pairs_list)
    count = 1
    for pair in pairs_list:
        try:
            result = cointegration_test(pair[0], pair[1])
            if result < 0.05:
                coint_pairs.append(pair)
            sys.stdout.write("\r")
            sys.stdout.write(str(count) + "/" + str(num_pairs) + " Pairs Analyzed") 
            sys.stdout.flush()
        except:
            pass
        count += 1
    sys.stdout.write("\rComplete!            \n")
    return coint_pairs


def get_current_price(symbol):
    uri_path = 'https://api.binance.com/api/v3/ticker/price'
    params = {
        'symbol': symbol
    }
    resp = requests.get(uri_path, params=params)
    return resp.json()['price']


def get_balances(first_asset, second_asset):
    uri_path = "/api/v3/account"
    data = {
        "timestamp": int(round(time.time() * 1000))
    }
    get_account_result = binanceus_request(uri_path, data, api_key, secret_key)
    try:
        for asset in get_account_result.json()['balances']:
            if asset['asset'] == first_asset:
                first_asset_balance = float(asset['free'])
            elif asset['asset'] == second_asset:
                second_asset_balance = float(asset['free'])
        balance_data = {
            'first_asset': first_asset_balance,
            'second_asset': second_asset_balance
        }
    except:
        balance_data = {
            'first_asset': 0.0,
            'second_asset': 0.0
        }
    return balance_data


def trade(amount, side, symbol):
    uri_path = "/api/v3/order"
    params = {
        "symbol": symbol
    }
    try:
        resp = requests.get('https://api.binance.us/api/v3/exchangeInfo', params=params)
        val = resp.json()['symbols'][0]['filters'][2]['stepSize']
        decimal = 0
        is_decimal = False
        for c in val:
            if is_decimal == True:
                decimal += 1
            if c == '1':
                break
            if c == '.':
                is_decimal = True
    except:
        decimal = 5
    data = {
        'symbol': symbol,
        'side': side,
        'type': 'MARKET',
        'quantity': str(round(amount, decimal)),
        'timestamp': int(round(time.time() * 1000)) 
    }
    result = binanceus_trade_request(uri_path, data, api_key, secret_key)
    return result


def wait_for_z_normalization(first_asset_symbol, second_asset_symbol):
    z_score = get_trade_info(first_asset_symbol=first_asset_symbol, second_asset_symbol=second_asset_symbol)
    count = 0
    while z_score > 0.75 and count < 90:
        new_z_score = get_trade_info(first_asset_symbol=first_asset_symbol, second_asset_symbol=second_asset_symbol)
        difference = float(new_z_score) - float(z_score)
        if difference > 0:
            print("Current Z-Score: " + str(round(new_z_score,4)) + bcolors.OKGREEN + " (+" + str(round(difference,4)) + ")" + bcolors.ENDC)
        else:
            print("Current Z-Score: " + str(round(new_z_score,4)) + bcolors.FAIL + " (" + str(round(difference,4)) + ")" + bcolors.ENDC)
        z_score = new_z_score
        for remaining in range(60, 0, -1):
            sys.stdout.write("\r")
            sys.stdout.write("{:2d} seconds remaining.".format(remaining)) 
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write("\rComplete!            \n")
        count += 1
    return


def z_based_trade(first_asset_symbol, second_asset_symbol):
    balances = get_balances(first_asset_symbol, second_asset_symbol)
    USDT_balance = get_balances('USDT', 'BTC')['first_asset']
    second_asset_balance = balances['second_asset']
    active_balances = get_active_balances()
    total_usd_value = 0
    for balance in active_balances:
        if balance[0] != 'USD' and balance[0] != 'USDT':
            asset_price = get_current_price(str(balance[0]) + 'USDT')
            usd_value = float(balance[1]) * float(asset_price)
            total_usd_value += usd_value
        else:
            usd_value = balance[1]
            total_usd_value += usd_value
    if second_asset_balance > 0.00001:
        resp = trade(amount=second_asset_balance, side='SELL', symbol=second_asset_symbol + 'USDT')
        print('Successfully SOLD ' + str(second_asset_balance) + ' ' + str(second_asset_symbol))
        time.sleep(5)
    if USDT_balance > 1: 
        first_asset_price = get_current_price(symbol=first_asset_symbol + 'USDT')
        first_asset_to_buy = (float(USDT_balance) / (float(first_asset_price)*1.05))
        resp = trade(amount=first_asset_to_buy, side='BUY', symbol=first_asset_symbol + 'USDT')
        if resp.status_code == 200:
            print('Successfully BOUGHT ' + str(first_asset_to_buy) + ' ' + str(first_asset_symbol))
            print('Verifying Transaction...')
            time.sleep(20)
            amount_to_sell = get_balances(first_asset_symbol, second_asset_symbol)['first_asset']
            print('Waiting for Z-Score Normalization...')
            print('Assets: ' + first_asset_symbol + ' & ' + second_asset_symbol)
            wait_for_z_normalization(first_asset_symbol=first_asset_symbol, second_asset_symbol=second_asset_symbol)
            resp = trade(amount=amount_to_sell, side='SELL', symbol=first_asset_symbol + 'USDT')
            print('Successfully SOLD ' + str(amount_to_sell) + ' ' + str(first_asset_symbol))
            active_balances = get_active_balances()
            total_usd_value_final = 0
            for balance in active_balances:
                if balance[0] != 'USD' and balance[0] != 'USDT':
                    asset_price = get_current_price(str(balance[0]) + 'USDT')
                    usd_value = float(balance[1]) * float(asset_price)
                    total_usd_value += usd_value
                else:
                    usd_value = balance[1]
                    total_usd_value_final += usd_value
            print(bcolors.OKGREEN + 'TRADE PROFIT: $' + str(round((total_usd_value_final - total_usd_value), 3)) + bcolors.ENDC)
        else:
            print(resp.json())
    else:
        print('Balance Not Sufficient For Trade...')


def get_active_balances():
    uri_path = "/api/v3/account"
    data = {
        "timestamp": int(round(time.time() * 1000))
    }
    get_account_result = binanceus_request(uri_path, data, api_key, secret_key)
    active_balances = []
    try:
        for asset in get_account_result.json()['balances']:
            if float(asset['free']) > 0.0:
                active_balances.append([asset['asset'], float(asset['free'])])
    except:
        print('Error Retrieving Balances Data...')
    return active_balances


def wait_for_trades(first_asset_symbol, second_asset_symbol):
    latest_zscore = get_trade_info(first_asset_symbol=first_asset_symbol, second_asset_symbol=second_asset_symbol)
    active_balances = get_active_balances()
    if latest_zscore > 2.4:
        z_based_trade(first_asset_symbol=first_asset_symbol, second_asset_symbol=second_asset_symbol)
    elif latest_zscore < -2.4:
        z_based_trade(first_asset_symbol=second_asset_symbol, second_asset_symbol=first_asset_symbol)
    else:
        print('......................................')
        print('Evaluating: ' + first_asset_symbol + ' & ' + second_asset_symbol)
        print('Current Z-Score: ' + str(round(latest_zscore,4)))
        print('Active Balances: ')
        total_usd_value = 0
        for balance in active_balances:
            if balance[0] != 'USD' and balance[0] != 'USDT':
                asset_price = get_current_price(str(balance[0]) + 'USDT')
                usd_value = float(balance[1]) * float(asset_price)
                total_usd_value += usd_value
            else:
                usd_value = balance[1]
                total_usd_value += usd_value
            print(' - Asset: ' + str(balance[0]) + ', Amount: ' + str(round(balance[1],6)) + ' ( $' + str(round(usd_value,3)) + ' )')
        print('Total USD Value: $' + str(round(total_usd_value,3)))
        print()
    for remaining in range(1, 0, -1):
        sys.stdout.write("\r")
        sys.stdout.write("{:2d} seconds remaining.".format(remaining)) 
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\rComplete!            \n")


def trade_pairs():
    z_score = 0
    all_z_scores = {}
    scores = {}
    optimal_asset = ""
    optimal_val = 0
    print('Calculating Cointegrated Pairs')
    print('This may take a moment...')
    coint_pairs = get_coint_pairs('ETH')
    print()
    for pair in coint_pairs:
        z_score = get_trade_info(pair[0], pair[1])
        all_z_scores[pair[1]] = z_score
        print('Asset Pair: ETH & ' + pair[1])
        print('Z-Score: ' + str(z_score))
        print()
    for key, val in all_z_scores.items():
        scores[key] = abs(val)
    max_z = max(scores.values())
    for key, val in scores.items():
        if val == max_z:
            optimal_asset = key
            optimal_val = val
    print('***OPTIMAL ASSET***: ' + optimal_asset)
    print('Z-Score: ' + str(optimal_val))
    print()
    print("Calculating Second Degree Cointegrated Pairs...")
    print(".............................................")
    coint_pairs = get_coint_pairs(optimal_asset)
    print()
    for i in range(10):
        for pair in coint_pairs:
            wait_for_trades(pair[0], pair[1])
        i += 1


banner = pyfiglet.figlet_format('CryptoPy', font='larry3d')
print()
print(banner)
print(bcolors.OKCYAN + 'Created By: Ryan Mazon (2022)' + bcolors.ENDC)

while True:
    trade_pairs()
