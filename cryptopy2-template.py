import datetime
import hashlib
import hmac
import glob
import time
import threading
import urllib.parse
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyfiglet
import requests

warnings.filterwarnings('ignore')

api_url = "https://api.binance.us"
api_key='<YOUR_API_KEY>'
secret_key='<YOUR_API_SECRET>'

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


def get_binanceus_signature(data, secret):
    postdata = urllib.parse.urlencode(data)
    message = postdata.encode()
    byte_key = bytes(secret, 'UTF-8')
    mac = hmac.new(byte_key, message, hashlib.sha256).hexdigest()
    return mac


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


def get_asset_trade_info(asset_symbol, interval, limit):
    url = 'https://api.binance.com/api/v3/klines'
    params = {
        'symbol': asset_symbol + 'USDT',
        'interval': interval,
        'limit': limit
    }
    columns=[
    'Open Time', 'Open Price', 'High Price', 'Low Price', 'Close Price', 'Volume',
    'Close Time', 'Volume (other)', '# of Trades', 'Base Asset Volume',
    'Quote Asset Volume', 'Ignore'
    ]
    resp = requests.get(url, params=params)
    df = pd.DataFrame(data=resp.json(), columns=columns).drop(columns='Ignore')
    return df


def get_latest_mfi(asset_symbol, interval, limit):
    df = get_asset_trade_info(asset_symbol=asset_symbol, interval=interval, limit=limit)
    typical_price = (df['Close Price'].astype(float) + df['High Price'].astype(float) + df['Low Price'].astype(float)) / 3.0
    period = 14
    money_flow = df['Volume'].astype(float) * typical_price

    positive_flow =[]
    negative_flow = []

    for i in range(1, len(typical_price)):
        if typical_price[i] > typical_price[i-1]: #if the present typical price is greater than yesterdays typical price
            positive_flow.append(money_flow[i-1])# Then append money flow at position i-1 to the positive flow list
            negative_flow.append(0) #Append 0 to the negative flow list
        elif typical_price[i] < typical_price[i-1]:#if the present typical price is less than yesterdays typical price
            negative_flow.append(money_flow[i-1])# Then append money flow at position i-1 to negative flow list
            positive_flow.append(0)#Append 0 to the positive flow list
        else: #Append 0 if the present typical price is equal to yesterdays typical price
            positive_flow.append(0)
            negative_flow.append(0)

    positive_mf =[]
    negative_mf = [] 

    for i in range(period-1, len(positive_flow)):
        positive_mf.append(sum(positive_flow[i+1-period : i+1]))
    #Get all of the negative money flows within the time period  
    for i in range(period-1, len(negative_flow)):
        negative_mf.append(sum(negative_flow[i+1-period : i+1]))

    mfi = 100 * (np.array(positive_mf) / (np.array(positive_mf)  + np.array(negative_mf) ))
    return mfi


def get_macd_info(asset_symbol, interval, limit):
    df = get_asset_trade_info(asset_symbol=asset_symbol, interval=interval, limit=limit)
    k = df['Close Price'].ewm(span=12, adjust=False, min_periods=12).mean()
    d = df['Close Price'].ewm(span=26, adjust=False, min_periods=26).mean()
    macd = k - d
    macd_s = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    macd_h = macd - macd_s
    macd_df = pd.DataFrame()
    macd_df['macd'] = df.index.map(macd)
    macd_df['macd_h'] = df.index.map(macd_h)
    macd_df['macd_s'] = df.index.map(macd_s)
    return macd_df['macd']


def get_rsi_info(asset_symbol, interval, limit, periods=14, ema=True):
    df = get_asset_trade_info(asset_symbol=asset_symbol, interval=interval, limit=limit)
    close_delta = df['Close Price'].astype(float).diff()

    # Make two series: one for lower closes and one for higher closes
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)
    
    if ema == True:
	    # Use exponential moving average
        ma_up = up.ewm(com = periods - 1, adjust=True, min_periods = periods).mean()
        ma_down = down.ewm(com = periods - 1, adjust=True, min_periods = periods).mean()
    else:
        # Use simple moving average
        ma_up = up.rolling(window = periods, adjust=False).mean()
        ma_down = down.rolling(window = periods, adjust=False).mean()
        
    rsi = ma_up / ma_down
    rsi = 100 - (100/(1 + rsi))
    return rsi


def get_day_metrics(asset_symbol, interval='1d', limit='365'):
    mfi = get_latest_mfi(asset_symbol=asset_symbol, interval=interval, limit=limit)
    mfi_length = len(mfi)
    mfi = round(mfi[mfi_length - 1],3)

    macd = get_macd_info(asset_symbol=asset_symbol, interval=interval, limit=limit)
    macd_length = len(macd)
    macd = round(macd[macd_length-1],3)

    rsi = get_rsi_info(asset_symbol=asset_symbol, interval=interval, limit=limit)
    rsi_length = len(rsi)
    rsi = round(rsi[rsi_length-1],3)
    return [mfi, macd, rsi]


def get_minute_metrics(asset_symbol, interval='1m', limit='1000'):
    mfi = get_latest_mfi(asset_symbol=asset_symbol, interval=interval, limit=limit)
    mfi_length = len(mfi)
    mfi = round(mfi[mfi_length - 1],3)

    macd = get_macd_info(asset_symbol=asset_symbol, interval=interval, limit=limit)
    macd_length = len(macd)
    macd = round(macd[macd_length-1],3)

    rsi = get_rsi_info(asset_symbol=asset_symbol, interval=interval, limit=limit)
    rsi_length = len(rsi)
    rsi = round(rsi[rsi_length-1],3)
    return [mfi, macd, rsi]


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


def normalize_series(df):
    normalized=(df-df.min())/(df.max()-df.min())
    return normalized


def get_high_volume_assets():
    print()
    asset_list = get_asset_list()
    high_volume_assets = []
    for asset in asset_list:
        try:
            df = get_asset_trade_info(asset, interval='1d', limit='365')
            if(df['Volume'].astype(float).values[:1] > 100000):
                high_volume_assets.append(asset)
                print('ADDING ' + asset + ' TO ASSET LIST')
        except:
            pass
    return high_volume_assets


def get_balances():
    uri_path = "/api/v3/account"
    data = {
        "timestamp": int(round(time.time() * 1000))
    }
    get_account_result = binanceus_request(uri_path, data, api_key, secret_key)
    balances = {}
    try:
        for asset in get_account_result.json()['balances']:
            if float(asset['free']) > 0.0:
                balances[asset['asset']] = float(asset['free'])
    except:
        pass
    return balances


def get_latest_signal(asset):
    minute_limit = '1000'

    minute_close_prices = pd.DataFrame(get_asset_trade_info(asset, interval='1m', limit=minute_limit))
    minute_mfi = pd.DataFrame(get_latest_mfi(asset, interval='1m', limit=minute_limit))
    minute_macd = pd.DataFrame(get_macd_info(asset, interval='1m', limit=minute_limit))
    minute_rsi = pd.DataFrame(get_rsi_info(asset, interval='1m', limit=minute_limit))

    normalized_minute_prices = normalize_series(minute_close_prices['Close Price'].astype(float))
    normalized_minute_mfi = normalize_series(minute_mfi)
    normalized_minute_macd = normalize_series(minute_macd)
    normalized_minute_rsi = normalize_series(minute_rsi)

    minute_price_ma = normalized_minute_prices.rolling(40).mean()

    df = pd.DataFrame()
    df['mfi'] = normalized_minute_mfi
    df['macd'] = normalized_minute_macd
    df['rsi'] = normalized_minute_rsi
    df['average'] = df.mean(axis=1)
    blend_ma = df['average'].rolling(40).mean()

    signal = blend_ma.dropna() - minute_price_ma.dropna()
    return signal.dropna().iloc[-1]


def find_available_assets():
    high_volume_assets = ['BNB', 'LTC', 'XLM', 'AAVE', 'XLM', 'GRT', 'LINK', 'OXT', 'ADA', 'CRV', 'ALGO',
        'BAT', 'NEO', 'QTUM', 'FTM', 'UNI', 'ETH', 'BTC']
    available_assets = []
    asset_signal_dict = {}
    for asset in high_volume_assets:
        signal = float(get_latest_signal(asset))
        print(asset)
        print('SIGNAL: ' + str(round(signal,3)) + '\n')
        if signal > 0.07:
            available_assets+=asset
        asset_signal_dict[asset] = signal
    if len(available_assets) == 0:
        available_assets = sorted(asset_signal_dict, key=asset_signal_dict.get)[0]
    return available_assets


def get_balance(asset):
    uri_path = "/api/v3/account"
    data = {
        "timestamp": int(round(time.time() * 1000))
    }
    get_account_result = binanceus_request(uri_path, data, api_key, secret_key)
    try:
        for account_asset in get_account_result.json()['balances']:
            if account_asset['asset'] == asset:
                first_asset_balance = float(account_asset['free']) + float(account_asset['locked'])
        balance_data = first_asset_balance
    except:
        balance_data = 0.0
    return balance_data


def evaluate_trade_distribution():
    assets = find_available_assets()
    USDT_balance = get_balance('USDT')
    if len(assets) > 0:
        distribution = USDT_balance / len(assets)
    else:
        distribution = 0
    return distribution


def make_trades():
    distro = evaluate_trade_distribution()
    while distro == 0:
        print('NO CURRENT TRADES\n')
        print('EVALUATING...')
        time.sleep(30)
        distro = evaluate_trade_distribution()
    assets = find_available_assets()
    for asset in assets:
        print('ATTEMPTING TO TRADE ' + 'USDT' + ' FOR ' + asset)
        result = trade(amount=distro, side='BUY', symbol=asset+'USDT')
        if result.status_code == 200:
            asset_balance = get_balance(asset)
            print('TRADED ' + str(round(distro,3)) + ' USDT FOR ' + str(round(asset_balance,3)) + asset)
            return distro
        else:
            print(result.json())
            exit
        

def wait_for_signals(distro):
    og_balances = get_balances()
    balances = []
    for asset in og_balances.keys:
        price = float(get_current_price(asset+'USDT'))
        if price > 10.0:
            balances += asset
    while len(balances) > 0:
        for asset in balances:
            signal = float(get_latest_signal(asset))
            if signal < 0.05:
                asset_balance = get_balance(asset)
                result = trade(amount=distro, side='SELL', symbol=asset+'USDT')
                if result.status_code == 200:
                    USDT_balance = get_balance('USDT')
                    print('TRADED ' + str(round(asset_balance,3)) + asset + ' FOR ' + str(round(USDT_balance,3)) + ' USDT')
                else:
                    print(result.json())
                    exit
        og_balances = get_balances()
        balances = []
        for asset in og_balances.keys:
            price = float(get_current_price(asset+'USDT'))
            if price > 10.0:
                balances += asset

def distributed_trade_cycle():
    trading = True
    while trading:
        distro = make_trades()
        wait_for_signals(distro)


def trade_cycle(low_mfi, high_mfi, low_signal, high_signal):
    high_volume_assets = ['BNB', 'LTC', 'XLM', 'AAVE', 'XLM', 'GRT', 'LINK', 'OXT', 'ADA', 'CRV', 'ALGO',
        'BAT', 'NEO', 'QTUM', 'FTM']
    high_volume_assets.append('UNI')
    high_volume_assets.append('ETH')
    high_volume_assets.append('BTC')

    print()
    potential_trades = {}
    logs = {}
    empty = True
    asset_to_trade = ''
    to_match = 0
    mfi_roc = 0
    while empty:
        for asset in high_volume_assets:

            minute_limit = '1000'

            minute_close_prices = pd.DataFrame(get_asset_trade_info(asset, interval='1m', limit=minute_limit))
            minute_mfi = pd.DataFrame(get_latest_mfi(asset, interval='1m', limit=minute_limit))
            minute_macd = pd.DataFrame(get_macd_info(asset, interval='1m', limit=minute_limit))
            minute_rsi = pd.DataFrame(get_rsi_info(asset, interval='1m', limit=minute_limit))

            normalized_minute_prices = normalize_series(minute_close_prices['Close Price'].astype(float))
            normalized_minute_mfi = normalize_series(minute_mfi)
            normalized_minute_macd = normalize_series(minute_macd)
            normalized_minute_rsi = normalize_series(minute_rsi)

            minute_price_ma = normalized_minute_prices.rolling(40).mean()

            df = pd.DataFrame()
            df['mfi'] = normalized_minute_mfi
            df['macd'] = normalized_minute_macd
            df['rsi'] = normalized_minute_rsi
            df['average'] = df.mean(axis=1)
            blend_ma = df['average'].rolling(40).mean()

            signal = get_latest_signal(asset)
            mfi = pd.DataFrame(get_latest_mfi(asset, '1m', '1000')).dropna().iloc[-1,0]
            latest_mfi = normalize_series(pd.DataFrame(get_latest_mfi(asset, '1m', '1000')))
            normalized_mfi = latest_mfi.dropna().iloc[-1,0]

            mfi_roc = float(((normalized_minute_mfi.dropna().iloc[-1,0] + normalized_minute_mfi.dropna().iloc[-2,0]) / 2) / ((normalized_minute_mfi.dropna().iloc[-3,0] + normalized_minute_mfi.dropna().iloc[-4,0]) / 2))

            if float(signal) > high_signal:
                print(bcolors.OKGREEN + 'SIGNAL (' + asset + '): ' + str(round(signal,5)) + bcolors.ENDC)
            else:
                print('SIGNAL (' + asset + '): ' + str(round(signal,5)) + bcolors.ENDC)
            print(' - MFI: ' + str(round(mfi,3)))
            print(' - NORM(MFI): ' + str(round(normalized_mfi,3)))
            print(' - MFI ROC: ' + str(round(mfi_roc,3)))
            print()
            if float(signal) > high_signal and float(normalized_mfi) > high_mfi and mfi_roc > 1:
                potential_trades[asset] = float(signal)
                print(asset + ' ADDED TO POTENTIAL TRADES')
                print()
            
                plt.style.use('fivethirtyeight')
                plt.figure()
                plt.plot(minute_price_ma, label='PRICE')
                plt.plot(blend_ma, label='BLEND')
                plt.plot(signal, label='SIGNAL')
                plt.xlabel('Minutes')
                plt.ylabel('Normalized Value')
                plt.title('Indicator Moving Averages (1000m) - ' + asset)
                plt.legend()
                plt.savefig('charts/' + asset + '_indicator_ma.png', dpi=500)
        try:
            to_match = max(potential_trades.values())
            empty = False
        except:
            pass
    for key,val in potential_trades.items():
        if to_match == val:
            asset_to_trade = key
    balances = get_balances()
    USDT_balance = balances['USDT']
    asset_price = get_current_price(symbol=asset_to_trade+'USDT')
    print('USDT BALANCE: ' + str(USDT_balance))
    print(asset_to_trade + ' PRICE: ' + str(asset_price))
    asset_to_buy = (float(USDT_balance) / (float(asset_price)*1.015))
    print('ATTEMPTING TO BUY ' + str(asset_to_buy) + ' ' + str(asset_to_trade))
    symbol = asset_to_trade + 'USDT'
    error = True
    while error:
        resp = trade(amount=float(USDT_balance)/1.1, side='BUY', symbol=symbol)
        if resp.status_code == 200:
            print('SOLD ' + 'USDT FOR ' + str(round(float(USDT_balance)/1.1,3)))
            signal = get_latest_signal(asset_to_trade)
            mfi = pd.DataFrame(get_latest_mfi(asset, '1m', '1000')).dropna().iloc[-1,0]
            latest_mfi = normalize_series(pd.DataFrame(get_latest_mfi(asset, '1m', '1000')))
            normalized_mfi = latest_mfi.dropna().iloc[-1,0]
            logs['asset'] = asset_to_trade
            logs['price bought'] = float(asset_price)
            logs['time bought'] = datetime.datetime.now()
            logs['signal'] = signal
            logs['mfi bought'] = mfi
            logs['normalized mfi bought'] = normalized_mfi
            logs['mfi roc bought'] = mfi_roc
            error = False
        else:
            print(resp.json())
            print('RETRYING...')
    normalized_minute_mfi = normalize_series(minute_mfi)
    normalized_minute_mfi = minute_mfi.dropna().iloc[-1,0]
    starting_value = asset_to_buy * float(get_current_price(asset_to_trade + 'USDT'))
    while float(signal) > low_signal and float(normalized_mfi) > low_mfi:

        signal = get_latest_signal(asset_to_trade)
        asset_price = get_current_price(asset_to_trade+'USDT')
        value = float(asset_to_buy) * float(asset_price)
        print()
        print(asset_to_trade + ' CURRENT PRICE: ' + str(round(float(asset_price),5)))
        print('STARTING VALUE: ' + str(round(starting_value,3)))
        if float(starting_value) < float(value):
            print(bcolors.OKGREEN + 'CURRENT VALUE: ' + str(round(value,3)) + bcolors.ENDC)
        else:
            print(bcolors.FAIL + 'CURRENT VALUE: ' + str(round(value,3)) + bcolors.ENDC)
        print('CURRENT SIGNAL: ' + str(round(signal,4)))
        mfi = pd.DataFrame(get_latest_mfi(asset, '1m', '1000')).dropna().iloc[-1,0]
        latest_mfi = normalize_series(pd.DataFrame(get_latest_mfi(asset, '1m', '1000')))
        normalized_mfi = latest_mfi.dropna().iloc[-1,0]
        mfi_roc = ((latest_mfi.dropna().iloc[-1,0] + latest_mfi.dropna().iloc[-2,0]) / 2) / ((latest_mfi.dropna().iloc[-3,0] + latest_mfi.dropna().iloc[-4,0]) / 2)
        print('CURRENT MFI: ' + str(round(mfi,3)))
        print('CURRENT NORMALIZED MFI: ' + str(round(normalized_mfi,3)))
        print('CURRENT MFI ROC: ' + str(round(mfi_roc,3)))
        signal = get_latest_signal(asset_to_trade)

        time.sleep(30)

    asset_price = get_current_price(asset_to_trade+'USDT')
    logs['price sold'] = float(asset_price)
    logs['time sold'] = datetime.datetime.now()
    logs['mfi sold'] = mfi
    logs['normalized mfi sold'] = normalized_mfi
    logs['mfi roc sold'] = mfi_roc
    resp = trade(amount=float(asset_to_buy), side='SELL', symbol=asset_to_trade+'USDT')
    if resp.status_code == 200:
        print('BOUGHT USDT FOR ' + str(asset_to_buy) + ' ' + asset_to_trade)
        profit_on_trade = float(starting_value) - (float(asset_to_buy)*float(asset_price))
        print()
        if profit_on_trade < 0.0:
            print(bcolors.FAIL + 'LOSS ON TRADE: ' + str(round(profit_on_trade,3)) + bcolors.ENDC)
        else:
            print(bcolors.OKGREEN + 'PROFIT ON TRADE: ' + str(round(profit_on_trade,3)) + bcolors.ENDC)
        return logs
    else:
        print(resp.json())
    


def generate_chart(asset):
    minute_limit = '1000'

    minute_close_prices = pd.DataFrame(get_asset_trade_info(asset, interval='1m', limit=minute_limit))
    minute_mfi = pd.DataFrame(get_latest_mfi(asset, interval='1m', limit=minute_limit))
    minute_macd = pd.DataFrame(get_macd_info(asset, interval='1m', limit=minute_limit))
    minute_rsi = pd.DataFrame(get_rsi_info(asset, interval='1m', limit=minute_limit))

    normalized_minute_prices = normalize_series(minute_close_prices['Close Price'].astype(float))
    normalized_minute_mfi = normalize_series(minute_mfi)
    normalized_minute_macd = normalize_series(minute_macd)
    normalized_minute_rsi = normalize_series(minute_rsi)

    minute_price_ma = normalized_minute_prices.rolling(40).mean()

    df = pd.DataFrame()
    df['mfi'] = normalized_minute_mfi
    df['macd'] = normalized_minute_macd
    df['rsi'] = normalized_minute_rsi
    df['average'] = df.mean(axis=1)
    blend_ma = df['average'].rolling(40).mean()

    uri_path = "/api/v3/account"
    data = {
        "timestamp": int(round(time.time() * 1000))
    }
    get_account_result = binanceus_request(uri_path, data, api_key, secret_key)
    try:
        for account_asset in get_account_result.json()['balances']:
            if account_asset['asset'] == asset:
                first_asset_balance = float(account_asset['free']) + float(account_asset['locked'])
        balance_data = first_asset_balance
    except:
        balance_data = 0.0
    price = get_current_price(asset+'USDT')
    account_value = float(price) * balance_data

    signal = blend_ma.dropna() - minute_price_ma.dropna()
    mfi = pd.DataFrame(get_latest_mfi(asset, '1m', '1000')).dropna().iloc[-1,0]
    latest_mfi = normalize_series(pd.DataFrame(get_latest_mfi(asset, '1m', '1000')))
    normalized_mfi = latest_mfi.dropna().iloc[-1,0]
    mfi_roc = ((latest_mfi.dropna().iloc[-1,0] + latest_mfi.dropna().iloc[-2,0]) / 2) / ((latest_mfi.dropna().iloc[-3,0] + latest_mfi.dropna().iloc[-4,0]) / 2)
    print('MFI: ' + str(round(mfi,3)))
    print('NORMALIZED MFI: ' + str(round(normalized_mfi,3)))
    if mfi_roc > 1.0:
        print(bcolors.OKGREEN + 'MFI ROC: ' + str(round(mfi_roc,3)) + bcolors.ENDC)
    else:
        print('MFI ROC: ' + str(round(mfi_roc,3)))
    if signal.dropna().iloc[-1] > 0.0:
        print(bcolors.OKGREEN + 'SIGNAL: ' + str(round(signal.dropna().iloc[-1],3)) + bcolors.ENDC)
    else:
        print('SIGNAL: ' + str(round(signal.dropna().iloc[-1],3)))
    if minute_close_prices['Close Price'].astype(float).iloc[-1] > minute_close_prices['Close Price'].astype(float).iloc[-2]:
        print(bcolors.OKGREEN + 'PRICE: ' + str(minute_close_prices['Close Price'].astype(float).iloc[-1]) + bcolors.ENDC)
    else:
        print('PRICE: ' + str(minute_close_prices['Close Price'].astype(float).iloc[-1]))
    print('BALANCE: ' + str(round(balance_data,3)))
    if minute_close_prices['Close Price'].astype(float).iloc[-1] > minute_close_prices['Close Price'].astype(float).iloc[-2]:
        print(bcolors.OKGREEN + 'VALUE: ' + str(round(account_value,2)) + bcolors.ENDC)
    else:
        print('VALUE: ' + str(round(account_value,2)))
        
    plt.style.use('fivethirtyeight')
    plt.figure()
    plt.plot(minute_price_ma, label='PRICE')
    plt.plot(blend_ma, label='BLEND')
    plt.plot(signal, label='SIGNAL')
    plt.xlabel('Minutes')
    plt.ylabel('Normalized Value')
    plt.title('Indicator Moving Averages (1000m) - ' + asset)
    plt.legend()
    plt.savefig('charts/' + asset + '_indicator_ma.png', dpi=500)


def run_trade_cycle(low_mfi, high_mfi, low_signal, high_signal):
    running = True
    while running:
        logs = trade_cycle(low_mfi, high_mfi, low_signal, high_signal)
        logs_df = pd.DataFrame(logs, index=[1])
        logs_df.to_csv('logs/log_cryptopy_' + datetime.datetime.now().strftime('%m%d%Y-%H%M%S'))
        running = False
        print('\n*DONE*\n')


def run_chart_cycle(asset):
    running = True
    while running:
        generate_chart(asset)
        print('CHART UPDATED')
        print()
        time.sleep(60)
    

banner = pyfiglet.figlet_format('CRYPTOPY2', font='big')
print()
print(banner)
print(bcolors.OKCYAN + 'Created By: Ryan Mazon (2022)' + bcolors.ENDC)
print()

print('MODES:')
print()
print(' (1) TRADE')
print(' (2) CHART')
print(' (3) ANALYZE')
print(' (4) DISTRIBUTED TRADE')
print()
selection = input('SELECT A MODE: ')

if selection == '1':
    print('SELECT A LOW/HIGH MFI AND SIGNAL')
    print(' - SUGGESTED LOW SIGNAL: 0.05')
    print(' - SUGGESTED HIGH SIGNAL: 0.07')
    print(' - SUGGESTED LOW NORM(MFI): 0.25')
    print(' - SUGGESTED HIGH NORM(MFI): 0.55')
    print()
    low_signal = input('LOW SIGNAL: ')
    high_signal = input('HIGH SIGNAL: ')
    low_mfi = input('LOW NORM(MFI): ')
    high_mfi = input('HIGH NORM(MFI): ')
    low_signal = float(low_signal)
    high_signal = float(high_signal)
    low_mfi = float(low_mfi)
    high_mfi = float(high_mfi)
    trading = True
    while trading:
        run_trade_cycle(low_mfi, high_mfi, low_signal, high_signal)
elif selection == '2':
    asset = input('ASSET TO ANALYZE: ')
    print()
    run_chart_cycle(asset)
elif selection == '3':
    path = r'logs'
    all_files = glob.glob(path + "/*")

    li = []

    if len(all_files) > 1:
        for filename in all_files:
            df = pd.read_csv(filename, index_col=None, header=0)
            li.append(df)
        frame = pd.concat(li, axis=0, ignore_index=True)
        frame.to_csv('data/trades_data.csv')
        print('LOGS WRITTEN TO DATA FOLDER')
    else:
        print('NOT ENOUGH DATA TO WRITE')
elif selection == '4':
    distributed_trade_cycle()
