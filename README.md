# Crypto Dashboard

A real-time cryptocurrency tracker that collects price data from CoinMarketCap and displays it on a Streamlit dashboard — running 24/7 on AWS Free Tier.

## Architecture

```
CoinMarketCap API → EC2 t4g.small → RDS PostgreSQL → Streamlit Dashboard
```

- **Collector:** fetches top 100 coins every 5 minutes (~8,640 API credits/month — within free tier)
- **Storage:** AWS RDS PostgreSQL db.t3.micro (free tier)
- **Dashboard:** Streamlit (coming soon)

## Project Structure

```
crypto-dashboard/
├── collector/
│   └── crypto_collector.py   # Data collection script
├── dashboard/
│   └── app.py                # Streamlit dashboard (coming soon)
├── .env.example              # Environment variables template
├── requirements.txt
└── README.md
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/crypto-dashboard.git
cd crypto-dashboard
```

### 2. Set up environment variables

```bash
cp .env.example .env
nano .env  # fill in your credentials
```

### 3. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 4. Run the collector

```bash
python3 collector/crypto_collector.py
```

## Deploying on EC2 (AWS Free Tier)

### Instance setup
- **AMI:** Amazon Linux 2023
- **Architecture:** 64-bit ARM
- **Instance type:** t4g.small (free until Dec 2026)
- **Auto-assign public IP:** enabled

### Run as a systemd service

```bash
sudo nano /etc/systemd/system/crypto-collector.service
```

```ini
[Unit]
Description=Crypto price collector
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/crypto-dashboard
EnvironmentFile=/home/ec2-user/crypto-dashboard/.env
ExecStart=/usr/bin/python3 /home/ec2-user/crypto-dashboard/collector/crypto_collector.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable crypto-collector
sudo systemctl start crypto-collector
```

Check status:
```bash
sudo systemctl status crypto-collector
sudo journalctl -u crypto-collector -f
```

## Data Collected

| Column | Description |
|---|---|
| symbol | Ticker (BTC, ETH, ...) |
| name | Full name |
| cmc_rank | CoinMarketCap ranking |
| price | Current price in USD |
| volume_24h | 24h trading volume |
| market_cap | Market capitalization |
| pct_1h | % change last 1 hour |
| pct_24h | % change last 24 hours |
| pct_7d | % change last 7 days |
| pct_30d | % change last 30 days |
| collected_at | Timestamp of collection |
