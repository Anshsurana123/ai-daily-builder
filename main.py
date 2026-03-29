import os
import requests
import json
import base64
from datetime import datetime

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GITHUB_TOKEN = os.environ["GH_TOKEN"]
GITHUB_USERNAME = os.environ["GH_USERNAME"]

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


def ask_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 8192}
    }
    res = requests.post(url, json=body)
    res.raise_for_status()
    return res.json()["candidates"][0]["content"]["parts"][0]["text"]


def generate_idea_and_code():
    today = datetime.now().strftime("%B %d, %Y")
    prompt = f"""You are an AI that builds useful web tools daily. Today is {today}.

Your task:
1. Come up with a unique, genuinely useful single-page web tool idea (examples: unit converter, password generator, markdown previewer, color palette generator, pomodoro timer, BMI calculator, tip splitter, text diff checker, etc.)
2. Build it as a complete, working single HTML file with inline CSS and JS. No external dependencies except maybe a Google Font or a CDN library if truly needed.

Rules:
- The tool must actually work and be useful
- Make it look clean and modern (dark or light theme, your choice)
- No placeholder content — fully functional
- Do NOT repeat ideas that are too common — be creative

Respond ONLY in this exact JSON format (no markdown, no backticks):
{{
  "name": "short-repo-name-with-dashes",
  "title": "Human Readable Tool Title",
  "description": "One sentence describing what this tool does",
  "html": "FULL HTML CODE HERE"
}}"""

    raw = ask_gemini(prompt)

    # strip possible markdown fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()

    return json.loads(raw)


def create_github_repo(name, description):
    url = "https://api.github.com/user/repos"
    body = {
        "name": name,
        "description": description,
        "homepage": f"https://{GITHUB_USERNAME}.github.io/{name}",
        "private": False,
        "auto_init": False
    }
    res = requests.post(url, headers=HEADERS, json=body)
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
    if res.status_code in [201, 409]:  # 409 = already enabled
        print(f"✅ GitHub Pages enabled")
    else:
        print(f"⚠️ Pages status: {res.status_code} - {res.text}")


def update_index_repo(name, title, description, date_str):
    index_repo = f"{GITHUB_USERNAME}.github.io" if False else "ai-builds-index"
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{index_repo}/contents/README.md"

    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        data = res.json()
        current = base64.b64decode(data["content"]).decode()
        sha = data["sha"]
    else:
        current = "# 🤖 AI Daily Builds\n\nA new web tool, built and deployed every day by AI.\n\n| Date | Tool | Description | Live |\n|------|------|-------------|------|\n"
        sha = None

    new_row = f"| {date_str} | [{title}](https://github.com/{GITHUB_USERNAME}/{name}) | {description} | [Live](https://{GITHUB_USERNAME}.github.io/{name}) |\n"

    # insert after table header
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
    print(f"🚀 Starting daily build for {date_str}")

    print("🧠 Asking Gemini for idea + code...")
    data = generate_idea_and_code()

    name = f"{data['name']}-{date_str}"
    title = data["title"]
    description = data["description"]
    html = data["html"]

    print(f"💡 Idea: {title} — {description}")

    create_github_repo(name, description)

    readme = f"# {title}\n\n{description}\n\n🔗 **Live:** https://{GITHUB_USERNAME}.github.io/{name}\n\n> Built autonomously by AI on {date_str}"
    push_file(name, "README.md", readme, "Initial commit")
    push_file(name, "index.html", html, "Add web tool")

    enable_github_pages(name)
    update_index_repo(name, title, description, date_str)

    print(f"\n🎉 Done! Live at: https://{GITHUB_USERNAME}.github.io/{name}")


if __name__ == "__main__":
    main()
