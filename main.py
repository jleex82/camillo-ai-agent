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
from serpapi import GoogleSearch  # Serper client (pip install google-search-results)

load_dotenv()

# Keys from GitHub Secrets
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")      # Add these if using full Reddit
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = "camillo-agent:v1 (by /u/yourredditusername)"

llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=GROQ_API_KEY, temperature=0.6)

# Keywords — add Ontario/Canada-specific for local edge
KEYWORDS = [
    "basil mask viral", "kojic acid tiktok", "peptide lotion trend",
    "celsius energy drink", "crocs comfort 2026", "humanoid robot home",
    "ozempic alternative natural", "pickleball ontario", "rucking trend canada",
    "tim hortons viral item", "canadian cottage trend", "solar lawn mower"
]

def get_serper_buzz(keyword):
    """Use Serper for recent web/SERP velocity proxy (mentions, related queries)"""
    if not SERPER_API_KEY:
        return 0, "Serper key missing"
    
    params = {
        "engine": "google",
        "q": f"{keyword} viral OR trend OR tiktok OR reddit after:2026-02-01",  # recent filter
        "api_key": SERPER_API_KEY,
        "num": 10,
        "location": "Canada"  # bias toward your location
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        organic_count = len(results.get("organic", []))
        related = len(results.get("related_searches", [])) if "related_searches" in results else 0
        return organic_count + related * 2, f"{organic_count} organic hits + related"
    except Exception as e:
        return 0, str(e)

def get_reddit_buzz(keyword):
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID or "dummy",
            client_secret=REDDIT_CLIENT_SECRET or "dummy",
            user_agent=REDDIT_USER_AGENT
        )
        subreddit = reddit.subreddit("all")
        count = sum(1 for _ in subreddit.search(keyword, sort="new", time_filter="week", limit=20))
        return count
    except:
        return 0

def analyze_trend(keyword):
    serper_score, serper_info = get_serper_buzz(keyword)
    reddit_score = get_reddit_buzz(keyword)
    total_buzz = serper_score + reddit_score * 3  # weight Reddit higher for community virality

    prompt = PromptTemplate(
        input_variables=["keyword", "buzz_score", "serper_info", "reddit_score"],
        template="""
        You are an enhanced Chris Camillo AI: spot asymmetric investments from consumer trends EARLY.
        Keyword: {keyword}
        Combined buzz score: {buzz_score} (Serper web hits/info: {serper_info} | Reddit new posts this week: {reddit_score})

        Rate asymmetry 1-10 (high = early viral, low analyst coverage, big potential revenue impact, limited downside).
        Output ONLY valid JSON:
        {{
          "asymmetry_score": int,
          "thesis": "2-3 sentence explanation + why asymmetric",
          "tickers": ["TICKER1 or None", "TICKER2"],
          "conviction": "high/medium/low",
          "sources_summary": "brief on buzz evidence"
        }}
        """
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    response = chain.run(
        keyword=keyword,
        buzz_score=total_buzz,
        serper_info=serper_info,
        reddit_score=reddit_score
    )
    try:
        return json.loads(response)
    except:
        return {"asymmetry_score": 0, "thesis": "Parse error", "tickers": [], "conviction": "low", "sources_summary": ""}

def get_stock_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        return f"{ticker} | ${info.get('currentPrice', 'N/A')} | MktCap ${info.get('marketCap', 'N/A'):,} | {info.get('longBusinessSummary', '')[:100]}..."
    except:
        return f"{ticker} — no data"

# Run scan
print(f"🚀 Enhanced Camillo Agent Run — {datetime.now().strftime('%Y-%m-%d %H:%M EST')} (Uxbridge, ON)")

report = ["**Daily Asymmetric Scan Report** (Serper + Reddit + Groq-powered)"]

high_signals = []

for kw in KEYWORDS:
    analysis = analyze_trend(kw)
    if analysis.get("asymmetry_score", 0) >= 7:
        tickers_info = [get_stock_info(t) for t in analysis["tickers"] if t and t != "None"]
        report.append(f"\n🔥 **{kw.upper()}** — Asymmetry: {analysis['asymmetry_score']}/10 ({analysis['conviction']})")
        report.append(f"Thesis: {analysis['thesis']}")
        report.append(f"Buzz Evidence: {analysis['sources_summary']}")
        if tickers_info:
            report.append("Potential Plays:\n" + "\n".join(tickers_info))
        high_signals.append(kw)

if not high_signals:
    report.append("\nNo high-conviction asymmetric signals today. Market quiet — or add more keywords!")

# Send to Discord
payload = {"content": "\n".join(report)}
requests.post(DISCORD_WEBHOOK, json=payload)

print("✅ Scan complete & report sent!")
