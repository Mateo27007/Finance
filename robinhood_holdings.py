#%% Main: Retrieve Data and format dates

#Author: Mateo Arteaga
#Release: August 2024

# This is a python program that reads the Robinhood Report
# on your positions and separates your holdings by stock,
# returning the real APR gained through the years and elegibility
# for sale of long term stocks (+1 years) for tax puposes.

# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import os
import pandas as pd
import yfinance as yf
import numpy as np
import datetime

# Chane Directory where the CSV file is
os.chdir('/Users/mateo/Documents/PERSONAL/FINANZAS/')

# Load the CSV file into a DataFrame
file_path = 'robinhood_positions.csv'  # Replace with your CSV file path

# Read the file line by line
with open(file_path, 'r') as file:
    lines = file.readlines()

# Check if the last line contains the disclaimer
disclaimer_text = "The data provided is for informational purposes only."
if disclaimer_text in lines[-1]:
    # Remove the last line if it contains the disclaimer
    lines = lines[:-2]

# Write the cleaned lines back to the file or process them directly
with open(file_path, 'w') as file:
    file.writelines(lines)

df = pd.read_csv(file_path)

# Display the first few rows to understand the structure
print("Original Data:")
print(df)


def convert_datetime_data(df):
    for column in df.columns:
        if 'Date' in column:
            df[column] = pd.to_datetime(df[column])
    return df
            
def convert_to_numeric(value):
    # Remove currency symbols and commas
    if isinstance(value, str):
        value = value.replace('$', '').replace(',', '')
        try:
            return pd.to_numeric(value, errors='coerce')
        except ValueError:
            return None
    return value

#Search for the gift stock and turn it into 'Buy'
def gift_into_buy(df):
    indexes = df.loc[df['Trans Code'] == 'REC'].index
    
    for index in indexes:
        df_rec = df.loc[index]
        ticker_symbol = df_rec['Instrument']
        specific_date = df_rec['Settle Date']
    
        # Download historical data for the specific date
        data = yf.download(ticker_symbol, start=specific_date, end=specific_date+datetime.timedelta(days=1), progress=False)
        
        # Check if data is available for that date
        if not data.empty:
            df.loc[index, 'Price'] = data['Close'].iloc[0]
            amount = round(df_rec['Quantity']*df.loc[index, 'Price'],2)
            df.loc[index, 'Amount'] = '$'+str(amount)
        else:
            print(f"No data available for {specific_date}")
        df.loc[df['Trans Code'] == 'REC', 'Trans Code'] = 'Buy'
    return df
    
df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')

convert_datetime_data(df)

gift_into_buy(df)

# Convert the 'Amount_USD' column to numeric
df['Price'] = df['Price'].apply(convert_to_numeric)

# Calculate HOLD times

today = pd.Timestamp.now()

hold = today - df['Settle Date']
df['HOLD'] = hold.dt.days

#%% Stock Price Today

def get_current_prices(tickers):
    prices = {}
    for ticker in tickers:
        if ticker == 'BRK.B':
            stock = yf.Ticker('BRK-B')
            prices[ticker] = stock.history(period="1d")['Close'].iloc[-1]
        elif type(ticker)==float:
            continue
        else:
            stock = yf.Ticker(ticker)
            prices[ticker] = stock.history(period="1d")['Close'].iloc[-1]
    return prices

tickers = df['Instrument'].unique()
tickers = tickers[~pd.isnull(tickers)]
prices = get_current_prices(tickers)

# Map the prices to a new column
df['USD Today'] = df['Instrument'].map(prices)

# Summary of positions
summary = df[['Instrument', 'Trans Code', 'Settle Date' ,'Quantity', 'Price','Amount','USD Today','HOLD']]

# Display the summary DataFrame
print("\nLast Movements:")
print(summary.head())

#%% Stock Positions Summary

# Dictionary to store DataFrames for each ticker
positions = {}

# Loop through unique tickers and create a new DataFrame for each
for ticker in tickers:
    if pd.isna(ticker):  # Skip if the ticker is NaN
        continue
    ticker_df = summary[summary['Instrument'] == ticker]
    positions[ticker] = ticker_df
    print(f"\nSummary for {ticker}: ")
    print(ticker_df)
del ticker_df

#%% Check and Adjust for splits

print('\nChecking for stock splits in Portfolio: \n')

def get_stock_splits(ticker):
    if ticker == 'BRK.B':
        stock = yf.Ticker('BRK-B')
    else:
        stock = yf.Ticker(ticker)
        # Fetch the stock splits
    splits = stock.splits
    return splits

# Function to adjust prices based on splits
def adjust_prices_for_splits(df, splits):
    for date, ratio in splits.items():
        # Ensure date is a Timestamp
        split_date = date.tz_localize(None)
        # Adjust prices for dates after the split date       
        if any(df['Settle Date'] < split_date):
            
            print('Effective Split!')
            print(split_date.strftime('%Y-%m-%d'), ratio)
            print(df.loc[df['Settle Date'] < split_date].iloc[:, :6],'\n')
            
            df.loc[df['Settle Date'] < split_date, 'Price'] /= ratio
            df.loc[df['Settle Date'] < split_date, 'Quantity'] *= ratio
            print('Resulting Split Position:')
            print(df.loc[df['Settle Date'] < split_date].iloc[:, :6],'\n')
            
        
    return df

for ticker in tickers:
    splits = get_stock_splits(ticker)
    if splits.empty:
        print(f"No stock splits found for {ticker}. \n")
    else:
        # Adjust prices based on splits
        print(f"Stock splits for {ticker}: \n")
        print(splits, '\n')
        adjust_prices_for_splits(positions[ticker], splits)
        #print(adjusted_df, '\n')


#%% Filter Out: Buy Positions and Mature Holdings

#Buy Positions

p_buy = {}
for ticker in tickers:
    p_buy[ticker] = positions[ticker].loc[positions[ticker]['Trans Code']=='Buy']
    p_buy[ticker] = p_buy[ticker].copy()
    p_buy[ticker].loc[:,'Return'] = p_buy[ticker]['Quantity']*(p_buy[ticker]['USD Today']
                                                               -p_buy[ticker]['Price'])
    
    p_buy[ticker].loc[:,'APR'] = ((p_buy[ticker]['USD Today']
                             /p_buy[ticker]['Price'])**(360/p_buy[ticker]['HOLD'])-1) * 100
    p_buy[ticker]['APR'] = np.where(p_buy[ticker]['HOLD'] < 30, np.nan, p_buy[ticker]['APR'])

HoldingsSummary = pd.DataFrame({
    #'Instrument': tickers,
    'Settle Date': [p_buy[ticker]['Settle Date'].iloc[0] 
                    for ticker in tickers],
    'Quantity': [p_buy[ticker]['Quantity'].sum() for ticker in tickers],
    'Price': [(p_buy[ticker]['Quantity']*p_buy[ticker]['Price']).sum()
               /p_buy[ticker]['Quantity'].sum() for ticker in tickers],
    'Amount': [(p_buy[ticker]['Quantity']*p_buy[ticker]['Price']).sum()
               for ticker in tickers],
    'USD Today': [p_buy[ticker]['USD Today'].iloc[0] 
                       for ticker in tickers],
    'HOLD': [p_buy[ticker]['HOLD'].iloc[-1] 
             if not p_buy[ticker]['HOLD'].empty else np.nan
             for ticker in tickers]
    },index=tickers)

#Mature Position

p_mature = {}
for ticker in tickers:
    p_mature[ticker] = p_buy[ticker].loc[p_buy[ticker]['HOLD'] > 365]
    
    
HoldingsMature = pd.DataFrame({
    #'Instrument': tickers,
    'Settle Date': [p_mature[ticker]['Settle Date'].iloc[0] 
                    if not p_mature[ticker]['Settle Date'].empty else np.nan
                    for ticker in tickers],
    'Quantity': [p_mature[ticker]['Quantity'].sum() for ticker in tickers],
    'Price': [(p_mature[ticker]['Quantity']*p_mature[ticker]['Price']).sum()
               /p_mature[ticker]['Quantity'].sum()
               if p_mature[ticker]['Quantity'].sum() != 0
               else np.nan
               for ticker in tickers],
    'Amount': [(p_mature[ticker]['Quantity']*p_mature[ticker]['Price']).sum()
               for ticker in tickers],
    'USD Today': [p_mature[ticker]['USD Today'].iloc[0] 
                      if not p_mature[ticker]['USD Today'].empty else np.nan
                       for ticker in tickers],
     'HOLD': [p_mature[ticker]['HOLD'].iloc[-1] 
              if not p_mature[ticker]['HOLD'].empty else np.nan
              for ticker in tickers]
    },index=tickers)

# APR and Return

HoldingsMature['Return'] = HoldingsMature['Quantity']*(HoldingsMature['USD Today']
                                                             -HoldingsMature['Price'])
HoldingsSummary['Return'] = HoldingsSummary['Quantity']*(HoldingsSummary['USD Today']
                                                             -HoldingsSummary['Price'])

#HoldingsMature['APR'] = ((HoldingsMature['USD Today']
#                         /HoldingsMature['Price'])**(365/HoldingsMature['HOLD'])-1) * 100

#HoldingsSummary['APR'] = ((HoldingsSummary['USD Today']
#                          /HoldingsSummary['Price'])**(365/HoldingsSummary['HOLD'])-1) * 100

HoldingsSummary['APR'] = np.nan
HoldingsMature['APR'] = np.nan

hold_s_apr = HoldingsSummary['APR'].copy()
hold_m_apr = HoldingsMature['APR'].copy()

# APR Average

for ticker in tickers:
    hold_s_apr[ticker] = (p_buy[ticker]['APR']*p_buy[ticker]['Quantity']).sum()/p_buy[ticker]['Quantity'].sum()
    if p_mature[ticker]['Quantity'].sum() == 0:
        continue
    else:
        hold_m_apr[ticker] = (p_mature[ticker]['APR']*p_mature[ticker]['Quantity']).sum()/p_mature[ticker]['Quantity'].sum()

HoldingsSummary['APR'] = round(hold_s_apr, 2)
HoldingsMature['APR'] = round(hold_m_apr, 2)

HoldingsSummary['APR'] = np.where(HoldingsSummary['HOLD'] < 30, np.nan, HoldingsSummary['APR'])
HoldingsSummary['APR'] = np.where(HoldingsSummary['HOLD'] < 30, np.nan, HoldingsSummary['APR'])

HoldingsSummary['Price'] = round(HoldingsSummary['Price'], 2)
HoldingsMature['Price'] = round(HoldingsMature['Price'], 2)

HoldingsSummary['USD Today'] = round(HoldingsSummary['USD Today'], 2)
HoldingsMature['USD Today'] = round(HoldingsMature['USD Today'], 2)

HoldingsSummary['Amount'] = round(HoldingsSummary['Amount'], 2)
HoldingsMature['Amount'] = round(HoldingsMature['Amount'], 2)

HoldingsSummary['Return'] = round(HoldingsSummary['Return'], 2)
HoldingsMature['Return'] = round(HoldingsMature['Return'], 2)

pd.set_option('display.max_columns', None)

print('Consolidated Holdings:')
print(HoldingsSummary,'\n')

print('Long Term Holdings:')
print(HoldingsMature,'\n')

pd.reset_option('display.max_columns')

#%% Individual s_STCK with Results!

# for ticker in tickers: 
#     if pd.isna(ticker):  # Skip if the ticker is NaN
#         continue
#     # Dynamically create a DataFrame variable for each ticker
#     globals()[f"s_{ticker}"] = p_buy[ticker]
#     #print(f"\nDataFrame for {ticker}:")
#     #print(globals()[f"s_{ticker}"],'\n')




