import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# LangChain (modern LCEL)
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq

# Dependencies
import yfinance as yf
import praw
import tweepy  # For X scanning

load_dotenv()

# ────────────────────────────────────────────────
# Secrets from GitHub Secrets
# ────────────────────────────────────────────────
GROQ_API_KEY          = os.getenv("GROQ_API_KEY")
DISCORD_WEBHOOK       = os.getenv("DISCORD_WEBHOOK")
SERPER_API_KEY        = os.getenv("SERPER_API_KEY")

# Reddit (optional)
REDDIT_CLIENT_ID      = os.getenv("REDDIT_CLIENT_ID")     or ""
REDDIT_CLIENT_SECRET  = os.getenv("REDDIT_CLIENT_SECRET") or ""
REDDIT_USER_AGENT     = "camillo-agent:v1 (by /u/yourredditusername)"

# X/Twitter API credentials (add these to GitHub Secrets)
TWITTER_API_KEY       = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET    = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN  = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# LLM Setup
llm = ChatGroq(
    model="llama-3.1-70b-versatile",  # Stable fast model; change if needed
    api_key=GROQ_API_KEY,
    temperature=0.7,
    max_tokens=500
)

# Keywords (add your own Ontario/Canada ones)
KEYWORDS = [
    "basil mask viral", "kojic acid tiktok", "peptide lotion trend",
    "celsius energy drink", "crocs comfort 2026", "humanoid robot home",
    "ozempic alternative natural", "pickleball ontario", "rucking trend canada",
    "tim hortons viral item", "canadian cottage trend", "solar lawn mower"
]

# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────

def get_serper_buzz(keyword):
    if not SERPER_API_KEY:
        return 0, "Serper key not set"
    try:
        params = {
            "engine": "google",
            "q": f"{keyword} viral OR trend OR tiktok OR reddit",
            "api_key": SERPER_API_KEY,
            "num": 8,
            "location": "Canada"
        }
        resp = requests.get("https://google.serper.dev/search", params=params, timeout=10)
        data = resp.json()
        organic = len(data.get("organic", []))
        related = len(data.get("relatedSearches", [])) if "relatedSearches" in data else 0
        return organic + related * 2, f"{organic} organic + {related} related"
    except Exception as e:
        return 0, f"Serper error: {str(e)[:60]}"

def get_reddit_buzz(keyword):
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return 0
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        count = sum(1 for _ in reddit.subreddit("all").search(keyword, sort="new", time_filter="week", limit=10))
        return count
    except:
        return 0

def get_x_client():
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return None
    return tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET
    )

def get_x_buzz(keyword):
    client = get_x_client()
    if not client:
        return 0, "X API not configured"
    try:
        query = f"{keyword} lang:en -is:retweet"
        tweets = client.search_recent_tweets(query=query, max_results=20)
        count = tweets.meta.get('result_count', 0) if tweets.meta else 0
        return count, f"{count} recent X mentions"
    except Exception as e:
        return 0, f"X error: {str(e)[:60]}"

def check_camillo_signals():
    client = get_x_client()
    if not client:
        return "X monitoring skipped (no API keys set)"
    
    signals = []
    for username in ["ChrisCamillo", "DumbMoneyTV"]:
        try:
            user = client.get_user(username=username)
            if not user.data:
                continue
            tweets = client.get_users_tweets(
                id=user.data.id,
                max_results=5,
                tweet_fields=['created_at', 'text']
            )
            for tweet in tweets.data or []:
                text = tweet.text.lower()
                if any(kw in text for kw in ['long', 'position', 'buying', 'trade', 'conviction', 'asymmetric', 'niche', 'stock', 'ticker', 'buy', 'sell', 'hold', 'thesis']):
                    signals.append(f"@{username} ({tweet.created_at.date()}): \"{text[:120]}...\"[](https://x.com/{username}/status/{tweet.id})")
        except:
            pass
    
    if signals:
        return "\n".join(signals)
    return "No recent signal-like posts from @ChrisCamillo or @DumbMoneyTV"

# ────────────────────────────────────────────────
# Analysis (LCEL style)
# ────────────────────────────────────────────────
def analyze_trend(keyword):
    serper_score, serper_info = get_serper_buzz(keyword)
    reddit_score = get_reddit_buzz(keyword)
    x_score, x_info = get_x_buzz(keyword)
    
    total_buzz = serper_score + reddit_score * 3 + x_score * 2

    prompt = PromptTemplate.from_template(
        """
        You are an enhanced Chris Camillo AI spotting asymmetric consumer trends early.
        Keyword: {keyword}
        Buzz score: {buzz_score} (Serper: {serper_info} | Reddit new posts/week: {reddit_score} | X recent mentions: {x_info})

        Rate asymmetry 1-10 (10 = early viral, low coverage, big revenue potential, limited downside).
        Output ONLY valid JSON:
        {{
          "asymmetry_score": int,
          "thesis": "2-3 sentence explanation + why asymmetric",
          "tickers": ["TICKER1 or None", "TICKER2 or None"],
          "conviction": "high/medium/low",
          "sources_summary": "brief buzz evidence"
        }}
        """
    )

    chain = prompt | llm

    try:
        response = chain.invoke({
            "keyword": keyword,
            "buzz_score": total_buzz,
            "serper_info": serper_info,
            "reddit_score": reddit_score,
            "x_info": x_info
        })
        content = response.content.strip()
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        return json.loads(content)
    except Exception as e:
        return {
            "asymmetry_score": 0,
            "thesis": f"Error: {str(e)[:80]}",
            "tickers": [],
            "conviction": "low",
            "sources_summary": ""
        }

def get_stock_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        price = info.get("currentPrice", "N/A")
        mcap = info.get("marketCap", "N/A")
        if mcap != "N/A":
            mcap = f"${mcap:,}"
        return f"{ticker} | ${price} | MktCap {mcap}"
    except:
        return f"{ticker} — data unavailable"

# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────
def main():
    print(f"Camillo Agent Scan — {datetime.now().strftime('%Y-%m-%d %H:%M EST')}")

    report_lines = ["**Daily Asymmetric Scan Report** (Serper + Reddit + X)"]

    found_signals = False

    for kw in KEYWORDS:
        analysis = analyze_trend(kw)
        score = analysis.get("asymmetry_score", 0)

        if score >= 7:
            found_signals = True
            tickers = analysis.get("tickers", [])
            tickers_info = [get_stock_info(t) for t in tickers if t and t.lower() != "none"]
            report_lines.append(f"\n🔥 **{kw.upper()}** — Score: {score}/10 ({analysis.get('conviction', 'unknown')})")
            report_lines.append(f"Thesis: {analysis.get('thesis', 'No thesis')}")
            report_lines.append(f"Buzz: {analysis.get('sources_summary', 'No sources')}")
            if tickers_info:
                report_lines.append("Plays:\n" + "\n".join(tickers_info))
            report_lines.append("-" * 60)

    # Add Camillo/DumbMoney check
    camillo_update = check_camillo_signals()
    report_lines.append(f"\n**Camillo & DumbMoney X Check**:\n{camillo_update}")

    if not found_signals:
        report_lines.append("\nNo high-asymmetry signals today — keep scanning!")

    # Send to Discord
    if DISCORD_WEBHOOK:
        payload = {"content": "\n".join(report_lines)}
        try:
            requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
            print("Report sent to Discord")
        except Exception as e:
            print(f"Discord send failed: {e}")
    else:
        print("No webhook — printing report:")
        print("\n".join(report_lines))

    print("Scan complete.")

if __name__ == "__main__":
    main()
