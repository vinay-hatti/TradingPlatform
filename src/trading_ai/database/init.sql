CREATE DATABASE trading_ai;

CREATE TABLE watchlist (

id SERIAL PRIMARY KEY,

symbol VARCHAR(20),

sector VARCHAR(50)

);

CREATE TABLE trades (

id SERIAL PRIMARY KEY,

symbol VARCHAR(20),

strategy VARCHAR(50),

entry_price NUMERIC,

exit_price NUMERIC,

pnl NUMERIC,

created TIMESTAMP DEFAULT NOW()

);

CREATE TABLE market_data (

id SERIAL PRIMARY KEY,

symbol VARCHAR(20),

date DATE,

open NUMERIC,

high NUMERIC,

low NUMERIC,

close NUMERIC,

volume BIGINT

);
