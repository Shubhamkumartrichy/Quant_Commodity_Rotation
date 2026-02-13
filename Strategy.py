import pandas_datareader.data as web
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import datetime

TICKERS = ['GLD.US', 'SLV.US']
START_DATE = datetime.datetime(2005, 1, 1)
END_DATE = datetime.datetime.now()
INITIAL_CAPITAL = 10000.0

def fetch_data(tickers, start, end):
    try:
        df = web.DataReader(tickers, 'stooq', start=start, end=end)
        df = df['Close'].sort_index()
        df.columns = [col.replace('.US', '') for col in df.columns]
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"Data Fetch Error: {e}")
        return pd.DataFrame()

class KalmanHedge:
    def __init__(self, delta=1e-4, R=1e-3):
        self.delta = delta #This is the Process Noise
        self.R = R #This is the Measurement Noise
    def update(self, y, x):
        n_obs = len(y)
        betas = np.zeros(n_obs)
        P = 1.0
        beta_hat = 0.0
        for t in range(n_obs):
            P = P + self.delta
            y_pred = beta_hat * x[t]
            error = y[t] - y_pred
            K = P * x[t] / (x[t]**2 * P + self.R) #Calculating Kalman Gain
            beta_hat = beta_hat + K * error #Updating Beta hat based on Gain and error.
            P = (1 - K * x[t]) * P
            betas[t] = beta_hat
        return betas

def run_stress_test(df, capital):
    print(f"Running 20-Year Stress Test on ${capital:,.0f}...")

    Y = df['GLD'].values
    X = df['SLV'].values

    kf = KalmanHedge(delta=0.0001)
    betas = kf.update(Y, X)

    strat = pd.DataFrame(index=df.index)
    strat['price_gld'] = Y
    strat['price_slv'] = X
    strat['beta'] = betas
    strat['beta_smooth'] = strat['beta'].rolling(window=6).mean() #6-SMA
    strat['beta_trend'] = strat['beta_smooth'].rolling(window=21).mean() #21-SMA

    strat['signal'] = 0
    strat.loc[strat['beta_smooth'] > strat['beta_trend'], 'signal'] = 1 #GLD
    strat.loc[strat['beta_smooth'] < strat['beta_trend'], 'signal'] = 2 #SLV

    strat['position'] = strat['signal'].shift(1).fillna(0) #This is for fixing look-ahead bias.

    strat['ret_gld'] = strat['price_gld'].pct_change().fillna(0)
    strat['ret_slv'] = strat['price_slv'].pct_change().fillna(0)

    strat['strategy_ret'] = 0.0
    strat.loc[strat['position'] == 1, 'strategy_ret'] = strat['ret_gld']
    strat.loc[strat['position'] == 2, 'strategy_ret'] = strat['ret_slv']
    
    strat['equity'] = capital * (1 + strat['strategy_ret']).cumprod()
    strat['benchmark'] = capital * (1 + strat['ret_gld']).cumprod()
    strat['benchmark_slv'] = capital * (1 + strat['ret_slv']).cumprod()


    return strat

def plot_stress_test(strat):
    final_equity = strat['equity'].iloc[-1]
    total_return = ((final_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    bench_return = ((strat['benchmark'].iloc[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    slv_return = ((strat['benchmark_slv'].iloc[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100

    sns.set_theme(style="darkgrid")
    plt.figure(figsize=(12, 6))

    plt.plot(strat.index, strat['equity'], label='Switcher Strategy', color='#2ca02c')
    plt.plot(strat.index, strat['benchmark'], label='Buy & Hold GLD', color='gold', alpha=0.5, linestyle='--')
    plt.plot(strat.index, strat['benchmark_slv'], label='Buy & Hold SLV', color='silver', alpha=0.7, linestyle=':')

    plt.axhline(INITIAL_CAPITAL, color='black', linestyle='--', alpha=0.3)
    plt.title(f"2005-Present Stress test")
    plt.ylabel("Account Balance(₹)")
    plt.legend()
    plt.show()

    print("-" * 30)
    print(f"Final Equity: ₹{final_equity:,.2f}")
    print(f"Total Return (Strategy): {total_return:.2f}%")
    print(f"Benchmark Return (GLD): {bench_return:.2f}%")
    print(f"Benchmark Return (SLV): {slv_return:.2f}%")




df_long = fetch_data(TICKERS, START_DATE, END_DATE)
if not df_long.empty:
    results_stress = run_stress_test(df_long, INITIAL_CAPITAL)
    plot_stress_test(results_stress)