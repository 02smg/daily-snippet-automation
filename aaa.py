# 나현이를 위한 코드 설명
from datetime import datetime, timedelta
import argparse
import requests
from notion_client import Client
import time
import json
import os
import pytz

# -------------------------- 설정 --------------------------

# 💥💥💥 중요: 이 URL이 바로 '진짜' 제출용 주소입니다! 💥💥💥
# 기본 URL 경로에 팀 ID를 직접 조합하여 사용합니다.
BASE_URL = "https://n8n.1000.school/webhook/"
TEAM_ID = "3545f2b3-480d-4aed-8e7b-c9d4f2a46027"
REAL_SUBMIT_URL = f"{BASE_URL}{TEAM_ID}"

NOTION_DB_ID = "2739cd3a02218004bb5cc43ba0ac2523" 

NOTION_DATE_PROP_NAME = "날짜"
NOTION_AUTHOR_PROP_NAME = "작성자"

TEAM_MEMBERS = [
    {"notion_author_name": "조세연", "full_name": "조세연/물리학과", "user_email": "toma12345@gachon.ac.kr"},
    {"notion_author_name": "송민근", "full_name": "송민근/컴퓨터공학부(컴퓨터공학전공)", "user_email": "badugi2482@gachon.ac.kr"},
    {"notion_author_name": "이수성", "full_name": "이수성/미술·디자인학부(디자인)", "user_email": "lss040228@gachon.ac.kr"},
    {"notion_author_name": "김나현", "full_name": "김나현/AI·소프트웨어학부(소프트웨어전공)", "user_email": "nh5102@gachon.ac.kr"}
]
# -----------------------------------------------------------

# --- (이하 모든 코드는 수정할 필요 없이 완벽합니다) ---

def rich_text_to_markdown(rich_text_array):
    md_text = ""
    for part in rich_text_array:
        content = part.get("plain_text", "")
        annotations = part.get("annotations", {})
        if annotations.get("bold"): content = f"**{content}**"
        if annotations.get("italic"): content = f"*{content}*"
        if annotations.get("strikethrough"): content = f"~~{content}~~"
        if annotations.get("code"): content = f"`{content}`"
        href = part.get("href")
        if href: content = f"[{content}]({href})"
        md_text += content
    return md_text

def blocks_to_markdown_recursive(notion, blocks, indent_level=0):
    markdown_lines = []
    indent = "    " * indent_level
    for block in blocks:
        block_type = block.get("type")
        if block_type in ["heading_1", "heading_2", "heading_3"]:
            if markdown_lines and markdown_lines[-1] != "":
                markdown_lines.append("")
        text = ""
        if block_type in ["heading_1", "heading_2", "heading_3", "paragraph", "bulleted_list_item", "numbered_list_item", "to_do", "quote"]:
            text = rich_text_to_markdown(block[block_type]["rich_text"])
        if block_type == "heading_1": markdown_lines.append(f"# {text}")
        elif block_type == "heading_2": markdown_lines.append(f"## {text}")
        elif block_type == "heading_3": markdown_lines.append(f"### {text}")
        elif block_type == "paragraph":
            is_pseudo_heading = text.startswith("**") and text.endswith("**")
            if is_pseudo_heading and markdown_lines and markdown_lines[-1] != "":
                markdown_lines.append("")
            markdown_lines.append(text)
        elif block_type == "bulleted_list_item": markdown_lines.append(f"{indent}* {text}")
        elif block_type == "numbered_list_item": markdown_lines.append(f"{indent}1. {text}")
        elif block_type == "to_do":
            prefix = "- [x]" if block["to_do"]["checked"] else "- [ ]"
            markdown_lines.append(f"{indent}{prefix} {text}")
        elif block_type == "quote":
            lines = text.split('\n')
            for line in lines:
                markdown_lines.append(f"> {line}")
        elif block_type == "divider": markdown_lines.append("\n---\n")
        if block.get("has_children"):
            child_blocks = notion.blocks.children.list(block_id=block["id"]).get("results", [])
            markdown_lines.append(blocks_to_markdown_recursive(notion, child_blocks, indent_level + 1))
    return "\n".join(markdown_lines)

def get_entries_for_date(notion, date_str):
    print(f"🔍 Notion에서 '{date_str}' 날짜에 작성된 모든 항목을 찾습니다...")
    try:
        response = notion.databases.query(
            database_id=NOTION_DB_ID,
            filter={"property": NOTION_DATE_PROP_NAME, "date": {"equals": date_str}}
        )
        entries = []
        for r in response.get("results", []):
            prop = r["properties"]
            page_id = r["id"]
            author_prop = prop.get(NOTION_AUTHOR_PROP_NAME, {}).get("people", [{}])
            author_name = author_prop[0].get("name", "") if author_prop else ""
            if author_name and page_id:
                top_level_blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
                page_content_md = blocks_to_markdown_recursive(notion, top_level_blocks)
                if page_content_md:
                    entries.append({"author": author_name, "content": page_content_md})
        return entries
    except Exception as e:
        print(f"❌ Notion 데이터 조회 중 오류 발생: {e}")
        return []

def send_single_snippet(snippet_object, date_str):
    author_name = snippet_object["full_name"]
    print(f"\n🚀 '{author_name}' 님의 스니펫을 [POST]로 전송합니다...")
    # 💥💥💥 수정된 부분: URL 파라미터가 더 이상 필요 없을 수 있으나, 안전을 위해 남겨둡니다. 💥💥💥
    params = {'api_id': TEAM_ID, 'date_from': date_str, 'date_to': date_str}
    payload = snippet_object
    
    try:
        # 💥💥💥 수정된 부분: REAL_SUBMIT_URL로 요청을 보냅니다. 💥💥💥
        res = requests.post(REAL_SUBMIT_URL, params=params, json=payload)
        
        if res.status_code >= 400:
            print(f"   ⚠️  '{author_name}' 님 스니펫 전송 결과: 서버가 요청을 거부했습니다 (HTTP {res.status_code})")
            print("      📄 이유:", res.json().get('detail', res.text))
        else:
            print(f"   ✅ '{author_name}' 님 스니펫 전송 성공!")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ 통신 오류 발생: {e}")

def main():
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        print("!!! 에러: GitHub Secret에 NOTION_TOKEN이 설정되지 않았습니다. !!!")
        return

    notion = Client(auth=notion_token)
    
    KST = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(KST)
    yesterday = now_kst - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    
    all_entries = get_entries_for_date(notion, yesterday_str)
    
    if not all_entries:
        print(f"\n🚫 처리 완료: '{yesterday_str}' 날짜에 Notion에 작성된 글이 없습니다.")
        return
    
    print(f"\n👍 Notion에서 총 {len(all_entries)}개의 항목을 찾았습니다. 팀원별로 전송을 시작합니다.")
    for member in TEAM_MEMBERS:
        member_entry = next((entry for entry in all_entries if entry['author'] == member['notion_author_name']), None)
        if not member_entry:
            continue
        content = member_entry['content']
        snippet_object = {
            "user_email": member["user_email"], "api_id": TEAM_ID,
            "snippet_date": yesterday_str, "content": content,
            "team_name": "7기-1팀", "full_name": member["full_name"],
        }
        send_single_snippet(snippet_object, yesterday_str)
        time.sleep(1)

if __name__ == "__main__":
    main()
