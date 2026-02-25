import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import yfinance as yf
import praw
import requests
import json
from datetime import datetime

load_dotenv()

# === YOUR KEYS (added as GitHub Secrets later) ===
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")      # optional for now
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = "camillo-agent"

# LLM (Groq = fast + free tier)
llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=GROQ_API_KEY, temperature=0.6)

# Camillo-style keywords (add your own — Ontario/Canada friendly)
KEYWORDS = [
    "basil mask viral", "kojic acid tiktok", "peptide lotion trend",
    "celsius energy drink", "crocs comfort 2026", "humanoid robot home",
    "ozempic alternative natural", "pickleball ontario", "rucking trend canada",
    "tim hortons viral item", "canadian cottage trend", "solar lawn mower"
]

def get_reddit_buzz(keyword):
    try:
        reddit = praw.Reddit(client_id=REDDIT_CLIENT_ID or "dummy", client_secret=REDDIT_CLIENT_SECRET or "dummy", user_agent=REDDIT_USER_AGENT)
        posts = reddit.subreddit("all").search(keyword, sort="new", time_filter="week")
        count = sum(1 for _ in posts)
        return count
    except:
        return 0

def analyze_trend(keyword):
    prompt = PromptTemplate(
        input_variables=["keyword", "reddit_buzz"],
        template="""
        You are Chris Camillo 2.0 — an expert at spotting asymmetric consumer trends before Wall Street.
        Keyword: {keyword}
        Recent Reddit mentions this week: {reddit_buzz}

        Rate asymmetry 1-10 (10 = massive edge).
        Write a 2-sentence thesis + 1-3 potential tickers.
        Output ONLY valid JSON:
        {{"asymmetry_score": int, "thesis": "string", "tickers": ["TICKER1", "TICKER2"], "conviction": "high/medium/low"}}
        """
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    response = chain.run(keyword=keyword, reddit_buzz=get_reddit_buzz(keyword))
    try:
        return json.loads(response)
    except:
        return {"asymmetry_score": 0, "thesis": "Error", "tickers": [], "conviction": "low"}

def get_stock_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        return f"{ticker} | Price ${info.get('currentPrice', 'N/A')} | MktCap ${info.get('marketCap', 'N/A'):,}"
    except:
        return f"{ticker} — data unavailable"

# Main run
print(f"🚀 Camillo Agent Run — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

report = ["**Camillo AI Daily Report**"]

for kw in KEYWORDS:
    analysis = analyze_trend(kw)
    if analysis.get("asymmetry_score", 0) >= 7:
        tickers_info = [get_stock_info(t) for t in analysis["tickers"]]
        report.append(f"\n🔥 **{kw.upper()}** — Score: {analysis['asymmetry_score']}/10 ({analysis['conviction']})")
        report.append(f"Thesis: {analysis['thesis']}")
        if tickers_info:
            report.append("Plays: " + "\n".join(tickers_info))

if len(report) == 1:
    report.append("No high-asymmetry signals today — normal day. Keep scanning!")

# Send to Discord
payload = {"content": "\n".join(report)}
requests.post(DISCORD_WEBHOOK, json=payload)

print("✅ Report sent!")
