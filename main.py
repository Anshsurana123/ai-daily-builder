import os
import re
import random
import string
import requests
import base64
from datetime import datetime

GITHUB_TOKEN = os.environ["GH_PAT"]
GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
CEREBRAS_API_KEY = os.environ["CEREBRAS_API_KEY"]

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


def ask_groq(prompt, model="llama-3.3-70b-versatile", max_tokens=2048):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.9
    }
    res = requests.post(url, headers=headers, json=body)
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]


def ask_cerebras(prompt, max_tokens=30000):
    from cerebras.cloud.sdk import Cerebras
    client = Cerebras(api_key=CEREBRAS_API_KEY)
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="qwen-3-235b-a22b-instruct-2507",
        max_tokens=max_tokens,
        temperature=0.9
    )
    return response.choices[0].message.content


def ask_for_code(prompt):
    try:
        print("🧠 Using Cerebras for code...")
        return ask_cerebras(prompt)
    except Exception as e:
        print(f"⚠️ Cerebras failed: {e}, falling back to Groq...")
        return ask_groq(prompt, max_tokens=32000)


def get_past_ideas():
    """Fetch last 30 app titles from ai-builds-index to avoid repeats."""
    url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/ai-builds-index/main/README.md"
    try:
        res = requests.get(url)
        if res.status_code != 200:
            return []
        lines = res.text.splitlines()
        titles = []
        for line in lines:
            if line.startswith("|") and not line.startswith("| Date") and not line.startswith("|---"):
                parts = [p.strip() for p in line.split("|")]
                # title is in column 2, format: [Title](url)
                match = re.search(r'\[(.+?)\]', parts[2])
                if match:
                    titles.append(match.group(1))
        return titles[-30:]  # last 30 only
    except Exception as e:
        print(f"⚠️ Could not fetch past ideas: {e}")
        return []


def generate_idea_and_code():
    today = datetime.now().strftime("%B %d, %Y")
    past_ideas = get_past_ideas()

    past_ideas_str = ""
    if past_ideas:
        past_ideas_str = "\n\nALREADY BUILT (do not repeat these):\n" + "\n".join(f"- {t}" for t in past_ideas)

    # Step 1: get structured project brief from Groq
    idea_prompt = f"""You are a creative product designer for an AI that ships a new web app every single day. Today is {today}.

Come up with a UNIQUE, specific, and genuinely useful web app idea. Think beyond generic tools — consider apps for writers, musicians, developers, students, travelers, gamers, designers, chefs, athletes etc.

BANNED ideas (too generic):
- Habit tracker
- Todo list
- Goal tracker
- Pomodoro timer
- Budget tracker
- Mood tracker
- Password generator
- Unit converter
{past_ideas_str}

Return a structured project brief in EXACTLY this format with no extra text:

REPO: repo-name-with-dashes
TITLE: Human Readable App Title
DESCRIPTION: One sentence description (max 200 chars)
FEATURES:
- Core feature 1
- Core feature 2
- Core feature 3
- Core feature 4
- more core features if any
VIBE: Describe the UI aesthetic in one sentence (e.g. dark glassmorphism, neon cyberpunk, clean minimalist white)
BUTTONS: Specify buttons
LIBS: List any CDN libraries needed (e.g. Chart.js, Tone.js, Three.js) or write "none" """

    brief_raw = ask_groq(idea_prompt).strip()
    print(f"📋 Brief:\n{brief_raw}\n")

    # Parse the brief
    def extract(key, text):
        match = re.search(rf'{key}:\s*(.+)', text)
        return match.group(1).strip() if match else ""

    name = extract("REPO", brief_raw).lower().replace(" ", "-").replace("_", "-")
    title = extract("TITLE", brief_raw)
    description = extract("DESCRIPTION", brief_raw)
    vibe = extract("VIBE", brief_raw)
    libs = extract("LIBS", brief_raw)

    # Extract features list
    features_match = re.search(r'FEATURES:\n((?:- .+\n?)+)', brief_raw)
    features = features_match.group(1).strip() if features_match else "- Core functionality"

    if not name or not title or not description:
        raise ValueError(f"Failed to parse brief. Raw output:\n{brief_raw}")

    print(f"💡 Idea: {title} — {description}")

    # Step 2: build the app using the full brief
    libs_instruction = f"Use these CDN libraries: {libs}" if libs.lower() != "none" else "No external libraries needed unless absolutely necessary"

    code_prompt = f"""You are an expert frontend developer. Build a complete, fully functional web app based on this brief:

TITLE: {title}
DESCRIPTION: {description}

FEATURES TO IMPLEMENT:
{features}

UI VIBE: {vibe}

TECHNICAL REQUIREMENTS:
- Single HTML file with all CSS and JS inline
- {libs_instruction}
- Every single feature must be FULLY FUNCTIONAL — no placeholders, no "coming soon", no fake data
- The app must feel like a real product someone would actually pay for
- Smooth animations and transitions throughout
- Responsive design
- Error handling for edge cases
- Complete clickable buttons that actually do something

IMPORTANT: The HTML must be 100% complete. Do not cut off mid-code. Keep it under 800 lines if possible but never sacrifice functionality.

Respond with ONLY the raw HTML code. No explanation, no markdown, no backticks."""

    html = ask_for_code(code_prompt).strip()
    if html.startswith("```"):
        html = html.split("```")[1]
        if html.startswith("html"):
            html = html[4:]
        html = html.strip().rstrip("```").strip()

    return {
        "name": name,
        "title": title,
        "description": description[:200],
        "html": html
    }


def create_github_repo(name, description):
    url = "https://api.github.com/user/repos"
    body = {
        "name": name,
        "description": description[:350],
        "homepage": f"https://{GITHUB_USERNAME}.github.io/{name}",
        "private": False,
        "auto_init": False
    }
    res = requests.post(url, headers=HEADERS, json=body)
    if not res.ok:
        print(f"❌ GitHub error: {res.status_code} - {res.text}")
    res.raise_for_status()
    print(f"✅ Repo created: {name}")
    return res.json()


def push_file(repo_name, file_path, content, message):
    encoded = base64.b64encode(content.encode()).decode()
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{file_path}"
    body = {
        "message": message,
        "content": encoded
    }
    res = requests.put(url, headers=HEADERS, json=body)
    res.raise_for_status()
    print(f"✅ Pushed: {file_path}")


def enable_github_pages(repo_name):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/pages"
    body = {"source": {"branch": "main", "path": "/"}}
    res = requests.post(url, headers=HEADERS, json=body)
    if res.status_code in [201, 409]:
        print(f"✅ GitHub Pages enabled")
    else:
        print(f"⚠️ Pages status: {res.status_code} - {res.text}")


def update_index_repo(name, title, description, date_str):
    index_repo = "ai-builds-index"
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{index_repo}/contents/README.md"

    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        data = res.json()
        current = base64.b64decode(data["content"]).decode()
        sha = data["sha"]
    else:
        current = "# 🤖 AI Daily Builds\n\nA new web app, built and deployed every day by AI.\n\n| Date | App | Description | Live |\n|------|-----|-------------|------|\n"
        sha = None

    new_row = f"| {date_str} | [{title}](https://github.com/{GITHUB_USERNAME}/{name}) | {description} | [Live](https://{GITHUB_USERNAME}.github.io/{name}) |\n"

    lines = current.splitlines(keepends=True)
    insert_at = None
    for i, line in enumerate(lines):
        if line.startswith("|---"):
            insert_at = i + 1
            break

    if insert_at is not None:
        lines.insert(insert_at, new_row)
        updated = "".join(lines)
    else:
        updated = current + new_row

    encoded = base64.b64encode(updated.encode()).decode()
    body = {
        "message": f"📦 Added {title} ({date_str})",
        "content": encoded
    }
    if sha:
        body["sha"] = sha

    res = requests.put(url, headers=HEADERS, json=body)
    if res.status_code in [200, 201]:
        print(f"✅ Index updated")
    else:
        print(f"⚠️ Index update status: {res.status_code}")


def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    suffix = ''.join(random.choices(string.ascii_lowercase, k=4))
    print(f"🚀 Starting daily build for {date_str}")

    data = generate_idea_and_code()

    name = f"{data['name']}-{date_str}-{suffix}"
    title = data["title"]
    description = data["description"]
    html = data["html"]

    create_github_repo(name, description)

    readme = f"# {title}\n\n{description}\n\n🔗 **Live:** https://{GITHUB_USERNAME}.github.io/{name}\n\n> Built autonomously by AI on {date_str}"
    push_file(name, "README.md", readme, "Initial commit")
    push_file(name, "index.html", html, "Add web app")

    enable_github_pages(name)
    update_index_repo(name, title, description, date_str)

    print(f"\n🎉 Done! Live at: https://{GITHUB_USERNAME}.github.io/{name}")


if __name__ == "__main__":
    main()
