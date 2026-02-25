import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# LangChain imports (modern LCEL style - no langchain.chains)
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq

# Other dependencies
import yfinance as yf
import praw  # Reddit (optional - can fail gracefully)

load_dotenv()

# ────────────────────────────────────────────────
# CONFIG - Secrets come from GitHub Secrets
# ────────────────────────────────────────────────
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
DISCORD_WEBHOOK    = os.getenv("DISCORD_WEBHOOK")
SERPER_API_KEY     = os.getenv("SERPER_API_KEY")

REDDIT_CLIENT_ID     = os.getenv("REDDIT_CLIENT_ID")     or ""
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET") or ""
REDDIT_USER_AGENT    = "camillo-agent:v1 (by /u/yourusername)"

# Keywords - feel free to customize (Ontario/Canada friendly)
KEYWORDS = [
    "basil mask viral",
    "kojic acid tiktok",
    "peptide lotion trend",
    "celsius energy drink",
    "crocs comfort 2026",
    "humanoid robot home",
    "ozempic alternative natural",
    "pickleball ontario",
    "rucking trend canada",
    "tim hortons viral item",
    "canadian cottage trend",
    "solar lawn mower"
]

# ────────────────────────────────────────────────
# LLM Setup (Groq - fast & free tier friendly)
# ────────────────────────────────────────────────
llm = ChatGroq(
    model="llama-3.1-70b-versatile",   # or "mixtral-8x7b-32768" if you prefer
    api_key=GROQ_API_KEY,
    temperature=0.7,
    max_tokens=500
)

# ────────────────────────────────────────────────
# Helper: Serper.dev web buzz (fallback if no key)
# ────────────────────────────────────────────────
def get_serper_buzz(keyword):
    if not SERPER_API_KEY:
        return 0, "Serper API key not set"
    try:
        params = {
            "engine": "google",
            "q": f"{keyword} viral OR trend OR tiktok OR reddit",
            "api_key": SERPER_API_KEY,
            "num": 8,
            "location": "Canada"
        }
        response = requests.get("https://google.serper.dev/search", params=params, timeout=10)
        data = response.json()
        organic = len(data.get("organic", []))
        related = len(data.get("relatedSearches", [])) if "relatedSearches" in data else 0
        return organic + related * 2, f"{organic} organic + {related} related"
    except Exception as e:
        return 0, f"Serper error: {str(e)[:60]}"

# ────────────────────────────────────────────────
# Helper: Reddit buzz (graceful fallback)
# ────────────────────────────────────────────────
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
    except Exception:
        return 0

# ────────────────────────────────────────────────
# Core analysis function (LCEL style)
# ────────────────────────────────────────────────
def analyze_trend(keyword):
    serper_score, serper_info = get_serper_buzz(keyword)
    reddit_score = get_reddit_buzz(keyword)
    total_buzz = serper_score + reddit_score * 3  # Reddit weighted higher

    prompt = PromptTemplate.from_template(
        """
        You are an enhanced Chris Camillo-style investor spotting early asymmetric consumer trends.
        Keyword: {keyword}
        Buzz score: {buzz_score}  (Serper info: {serper_info} | Reddit posts this week: {reddit_score})

        Rate asymmetry 1–10 (10 = very early viral signal, low Wall Street awareness, big potential revenue impact).
        Output **ONLY** valid JSON, nothing else:
        {{
          "asymmetry_score": number,
          "thesis": "2–3 sentence explanation + why it's asymmetric",
          "tickers": ["TICKER1 or None", "TICKER2 or None"],
          "conviction": "high | medium | low",
          "sources_summary": "short buzz evidence summary"
        }}
        """
    )

    chain = prompt | llm

    try:
        response = chain.invoke({
            "keyword": keyword,
            "buzz_score": total_buzz,
            "serper_info": serper_info,
            "reddit_score": reddit_score
        })
        content = response.content.strip()
        # Sometimes LLM adds ```json ... ``` - clean it
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        return json.loads(content)
    except Exception as e:
        return {
            "asymmetry_score": 0,
            "thesis": f"Analysis failed: {str(e)[:80]}",
            "tickers": [],
            "conviction": "low",
            "sources_summary": ""
        }

# ────────────────────────────────────────────────
# Stock info helper
# ────────────────────────────────────────────────
def get_stock_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        price = info.get("currentPrice", "N/A")
        mcap = info.get("marketCap", "N/A")
        if mcap != "N/A":
            mcap = f"${mcap:,}"
        return f"{ticker} | ${price} | Market Cap {mcap}"
    except:
        return f"{ticker} — data unavailable"

# ────────────────────────────────────────────────
# Main execution
# ────────────────────────────────────────────────
def main():
    print(f"Camillo Agent Scan — {datetime.now().strftime('%Y-%m-%d %H:%M EST')}")

    report_lines = ["**Daily Asymmetric Consumer Trend Scan**"]
    found_signals = False

    for kw in KEYWORDS:
        analysis = analyze_trend(kw)
        score = analysis.get("asymmetry_score", 0)

        if score >= 7:
            found_signals = True
            tickers = analysis.get("tickers", [])
            tickers_str = [get_stock_info(t) for t in tickers if t and t.lower() != "none"]
            report_lines.append(f"\n🔥 **{kw.upper()}** — Score: {score}/10 ({analysis.get('conviction', 'unknown')})")
            report_lines.append(f"Thesis: {analysis.get('thesis', 'No thesis')}")
            report_lines.append(f"Buzz: {analysis.get('sources_summary', 'No sources')}")
            if tickers_str:
                report_lines.append("Plays:\n" + "\n".join(tickers_str))
            report_lines.append("-" * 60)

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
        print("No Discord webhook set — printing report:")
        print("\n".join(report_lines))

    print("Scan complete.")

if __name__ == "__main__":
    main()
