# FinanceAnalysis

This repository contains Python scripts for identifying potential high-growth stocks across major exchanges.

## Supported Exchanges

- **HKEX** (Hong Kong Exchanges and Clearing Limited)
- **NASDAQ** (National Association of Securities Dealers Automated Quotations)

## Getting Started

Clone the repository:

```bash
git clone --depth 1 https://github.com/ckkyue/FinanceAnalysis.git
```

> **Note:** The `--depth 1` flag reduces disk usage by excluding commit history.

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

**Required libraries:**
- matplotlib
- numpy
- openpyxl
- pandas
- requests
- python-dateutil
- pyfinviz
- requests-ratelimiter
- scipy
- scikit-learn
- statsmodels
- tqdm
- seaborn
- yfinance

> **Important:** Keep `yfinance` updated regularly to avoid bugs:
> ```bash
> pip install --upgrade yfinance
> ```

## Disclaimer

This repository does not constitute investment advice or recommend any investment product.