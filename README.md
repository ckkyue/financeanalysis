# StockAnalysis
This repository contains Python scripts designed to identify potential high-growth stocks. The screener allows you to select stocks listed on the following exchanges:
- **Hong Kong Exchanges and Clearing Limited (HKEX)**
- **National Association of Securities Dealers Automated Quotations (NASDAQ)**

You can clone this repository using the following command:
```bash
git clone --depth 1 https://github.com/ckkyue/StockAnalysis.git
```
The `--depth 1` flag is recommended to avoid using up space with unnecessary commits.

## Libraries
Ensure that you have the following libraries installed:

- `matplotlib`
- `numpy`
- `openpyxl`
- `pandas`
- `requests`
- `python-dateutil`
- `pyfinviz`
- `requests-ratelimiter`
- `scipy`
- `scikit-learn`
- `statsmodels`
- `tqdm`
- `seaborn`
- `yfinance`

You can install all the required libraries by running:
```bash
pip install -r requirements.txt
```

Occasionally, yfinance may encounter bugs, so it is important to keep it updated regularly to avoid potential errors. You can do this by running:
```bash
pip install --upgrade yfinance
```

## Disclaimer
The content of this repository does not constitute investment advice, offer any solicitation to offer, or recommend any investment product.
